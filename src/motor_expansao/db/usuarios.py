"""Administracao de usuarios: quem existe, com que perfil, e quem mudou o que.

O que esta camada resolve
-------------------------
Antes do banco, mudar o acesso de alguem era editar o `acesso_abas.json` no volume `:rw` -- sem
rebuild, sem deploy. Com o RBAC no banco, a mesma mudanca vira `UPDATE` manual na VPS. Isso e' uma
REGRESSAO de operabilidade, e e' o que este modulo existe para desfazer.

Por que o SQL mora aqui, e nao no `app.py`
------------------------------------------
A suite unitaria nao tem Postgres (decisao de 25/08; desde 24/10/2026 o CI sobe um banco de ensaio
so' para a integracao) e quem executa contra banco real e' o Vinicius. Isso impoe
uma consequencia de arquitetura: o SQL precisa ser LOCALIZAVEL -- em arquivos ou num modulo de
queries nomeadas, nunca interpolado no meio da logica de rota. Sem isso, nem o gate de sintaxe
offline (`pglast`) alcanca tudo, nem ha o que revisar antes de rodar.

Uma unidade de trabalho por acao
--------------------------------
Toda escrita daqui faz DUAS coisas na MESMA transacao: muda a linha de `usuarios` e grava o evento
correspondente. Se as duas nao forem atomicas, o sistema fica com estados que ninguem consegue
explicar depois -- perfil trocado sem registro de quem trocou, ou registro de uma troca que nao
aconteceu. O `transacao(id_usuario=...)` carimba o autor para as triggers do D19 (§8.1) e o mesmo
autor vai no `id_usuario` do evento.

Quando a tela muda perfil E status de uma vez, os dois passos vao numa transacao SO'
(`alterar_acesso`), com um evento cada: atomicidade nao e' colapsar a trilha. Ate' 24/10/2026 eram
duas transacoes, e a falha da segunda deixava a primeira gravada sob um 503 (#463, follow-up B).

As duas pessoas de cada linha
-----------------------------
Em `eventos`, `id_usuario` e' QUEM FEZ e `entidade_id` e' QUEM SOFREU. E' para isso que a D24 pos
`usuario` no `CHECK` de `entidade`. Confundir as duas produz uma trilha que parece certa e responde
errado -- por isso os parametros aqui se chamam `autor` e `id_alvo`, e nunca so' "usuario".

As duas excecoes a essa forma (D26)
-----------------------------------
`criar` e' o unico caso em que o alvo NAO existe antes da chamada: nao ha estado anterior para ler,
nada para travar, e o `entidade_id` do evento so' aparece depois do `RETURNING`.

`trocar_a_propria_senha` e' o unico caso em que autor e alvo sao a MESMA pessoa de propósito. O
`_recusar_auto_alvo` existe para impedir que alguem mude o proprio PERFIL; trocar a propria SENHA e'
o oposto -- e' a unica coisa que so' a propria pessoa deveria poder fazer. A assinatura nem aceita
id de alvo, para nao haver como chamar isso para outra pessoa por engano.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .postgres import conexao, transacao

#: Vocabulario de `tipo` do `docs/eventos_contrato.md` §2.7. Fora desta lista e' defeito.
EVENTO_PERFIL_ALTERADO = "usuario.perfil_alterado"
EVENTO_DESATIVADO = "usuario.desativado"
EVENTO_REATIVADO = "usuario.reativado"
EVENTO_CRIADO = "usuario.criado"
EVENTO_SENHA_DEFINIDA = "usuario.senha_definida"
#: Os dois gestos sobre a senha DE OUTRA PESSOA (15/09). Antes deles o `UPDATE` direto era o unico
#: caminho, e nao deixava evento -- ver o fim da §2.7 do contrato.
EVENTO_SENHA_REDEFINIDA = "usuario.senha_redefinida"
EVENTO_TROCA_EXIGIDA = "usuario.troca_exigida"
#: Os paises de uma pessoa (DEC-081, Fase 2 do P4). metadados = {"pais": sigla}, sem PII.
EVENTO_PAIS_ATRIBUIDO = "usuario.pais_atribuido"
EVENTO_PAIS_REMOVIDO = "usuario.pais_removido"
#: O vinculo da pessoa com master(s) franquia mudou (emenda 1 da DEC-087). UM evento por gesto,
#: e nao um por nome como nos paises: o nome do master e' nome de PESSOA, e PII fica fora de
#: `metadados` (convencoes §5). Sobram as contagens `{"antes": n, "depois": n}`; quem audita
#: le o estado atual em `usuario_masters`.
EVENTO_MASTERS_ALTERADOS = "usuario.masters_alterados"
#: Os avisos que a pessoa recebe mudaram (DEC-090, migration 028). Um evento por gesto, com o
#: conjunto antes e depois: os identificadores (`estudo_master`, `imovel_master`) nao sao PII.
EVENTO_AVISOS_ALTERADOS = "usuario.avisos_alterados"

#: Valor de `entidade` para os eventos daqui (D24).
ENTIDADE_USUARIO = "usuario"

#: O perfil do master franqueado (DEC-087, migration 025). E' o UNICO perfil que leva vinculo em
#: `usuario_masters`: o recorte da Visao Executiva casa esses nomes com o `master_franquia` do
#: cadastro, e master sem vinculo ve a carteira vazia. Identificador, sem acento.
PERFIL_MASTER = "master"


class UsuarioDesconhecido(LookupError):
    """`id_usuario` que nao existe. 404 na rota -- nunca criar na hora."""


class PerfilDesconhecido(LookupError):
    """`nome_perfil` fora dos que o seed criou."""


class AlvoEhOAutor(PermissionError):
    """Tentativa de mudar o proprio acesso. Ver `_recusar_auto_alvo`."""


class LoginEmUso(ValueError):
    """Ja' existe usuario ATIVO com este login.

    Traduz a `UniqueViolation` de `idx_usuarios_login_ativo` (013), que e' um indice unico
    PARCIAL (`WHERE ativo`). Sem esta traducao a rota devolveria 500 para um conflito que e'
    perfeitamente explicavel -- e o indice ser parcial e' de proposito: login de quem foi
    desativado volta a ser reutilizavel (D9/D23).
    """


class EmailEmUso(ValueError):
    """Ja' existe usuario ATIVO com este e-mail. Espelho do acima, para `idx_usuarios_email_ativo`."""


class SenhaAtualIncorreta(PermissionError):
    """A senha atual informada nao casa com o hash guardado. 403 na rota."""


# `login_usuario` e' a chave que casa com o `Remote-User` do Authelia (D23). Vem junto porque e' o
# que a tela mostra e o que a trilha da DEC-027 grava -- sem ele, cruzar as duas exige adivinhacao.
# As duas ultimas colunas vem da 016 e a tela precisa das duas separadas: `senha_propria` diz se a
# pessoa JA' definiu a dela alguma vez, `deve_trocar` diz se precisa definir AGORA. Um admin pode
# forcar troca de quem ja' definiu, e nesse caso as duas sao verdadeiras ao mesmo tempo.
SQL_LISTAR = """
SELECT u.id_usuario, u.login_usuario, u.nome_usuario, u.email,
       p.nome_perfil, u.ativo, u.criado_em_usuario, u.atualizado_em_usuario,
       (u.senha_definida_em_usuario IS NOT NULL) AS senha_propria,
       u.deve_trocar_senha_usuario,
       COALESCE((SELECT array_agg(up.pais ORDER BY up.pais)
                 FROM usuario_paises up WHERE up.id_usuario = u.id_usuario), ARRAY[]::text[]) AS paises,
       COALESCE((SELECT array_agg(um.master_franquia ORDER BY um.master_franquia)
                 FROM usuario_masters um WHERE um.id_usuario = u.id_usuario),
                ARRAY[]::text[]) AS masters,
       COALESCE((SELECT array_agg(ua.aviso ORDER BY ua.aviso)
                 FROM usuario_avisos ua WHERE ua.id_usuario = u.id_usuario),
                ARRAY[]::text[]) AS avisos
FROM usuarios u
JOIN perfis p ON p.id_perfil = u.id_perfil
ORDER BY u.ativo DESC, u.login_usuario
"""

#: A tela precisa das opcoes do seletor. `descricao_perfil` vira rotulo, e por isso ela e' medida
#: por encoding na verificacao -- ver a nota da 012 sobre duplo-encoding.
SQL_PERFIS = """
SELECT p.nome_perfil, p.descricao_perfil, count(pp.id_permissao) AS capacidades
FROM perfis p
LEFT JOIN perfil_permissoes pp ON pp.id_perfil = p.id_perfil
GROUP BY p.nome_perfil, p.descricao_perfil
ORDER BY count(pp.id_permissao), p.nome_perfil
"""

# `FOR UPDATE` trava a linha ate' o fim da transacao. Sem ele, dois admins mexendo na mesma pessoa
# ao mesmo tempo produzem dois eventos com o MESMO `de` -- a trilha diria que o perfil saiu de
# `expansao` duas vezes, e o estado final seria de quem escreveu por ultimo, sem registro disso.
SQL_ESTADO_ATUAL = """
SELECT u.id_usuario, u.login_usuario, p.nome_perfil, u.ativo
FROM usuarios u
JOIN perfis p ON p.id_perfil = u.id_perfil
WHERE u.id_usuario = %s
FOR UPDATE OF u
"""

SQL_ID_DO_PERFIL = "SELECT id_perfil FROM perfis WHERE nome_perfil = %s"

SQL_TROCAR_PERFIL = """
UPDATE usuarios SET id_perfil = %s WHERE id_usuario = %s
"""

SQL_DEFINIR_ATIVO = """
UPDATE usuarios SET ativo = %s WHERE id_usuario = %s
"""

# `RETURNING id_usuario` e' obrigatorio, e nao conveniencia: sem ele nao ha `entidade_id` para o
# evento `usuario.criado` -- e um evento de criacao sem o id de quem foi criado nao responde nada.
#
# O `id_perfil` chega resolvido por `SQL_ID_DO_PERFIL`, como no `alterar_perfil`: a mesma forma para
# a mesma pergunta, e um perfil inexistente vira `PerfilDesconhecido` ANTES de qualquer escrita.
#
# `senha_hash` recebe o hash da senha inicial (`senhas.hash_da_senha_inicial`), com sal proprio.
# `senha_definida_em_usuario` fica NULO de proposito -- a pessoa nao definiu nada ainda -- e
# `deve_trocar_senha_usuario` fica no DEFAULT TRUE da 016.
SQL_CRIAR = """
INSERT INTO usuarios (login_usuario, nome_usuario, email, senha_hash, id_perfil)
VALUES (%s, %s, %s, %s, %s)
RETURNING id_usuario
"""

# Companheiro de SQL_CRIAR: o pais da pessoa (DEC-081, P4) entra na MESMA transacao da criacao,
# uma linha por pais. A PK composta (021) recusa pais repetido; o CHECK chk_usuario_paises_sigla
# recusa sigla fora de `^[A-Z]{2}$`. A validacao em Python so' adianta o erro com mensagem clara.
SQL_CRIAR_PAIS = """
INSERT INTO usuario_paises (id_usuario, pais) VALUES (%s, %s)
"""

# Companheiros do SQL_CRIAR_PAIS para a Fase 2 (editar/remover pais de usuario existente). A
# remocao e' um DELETE por linha (o GRANT de DELETE ao `app` entra no §3 do
# papeis-e-privilegios.md); a leitura serve para computar o diff do replace-all.
SQL_REMOVER_PAIS = """
DELETE FROM usuario_paises WHERE id_usuario = %s AND pais = %s
"""

SQL_PAISES_DO_USUARIO = """
SELECT pais FROM usuario_paises WHERE id_usuario = %s ORDER BY pais
"""

# O vinculo pessoa -> master franquia (025, DEC-087), no molde dos tres de cima: INSERT por nome
# novo, DELETE por nome que saiu, e a leitura do conjunto atual para o diff do replace-all. A
# PK composta recusa o mesmo nome duas vezes; o CHECK `chk_usuario_masters_nome` recusa espaco nas
# pontas e tamanho fora de 2 a 120 -- `_normalizar_masters` adianta as duas recusas com mensagem.
#
# A leitura NAO filtra `u.ativo`, ao contrario do `rbac.SQL_MASTERS_DO_USUARIO`: aquela decide o
# recorte de quem ESTA' entrando; esta serve a quem administra, que precisa ver e mexer no vinculo
# de quem esta' inativo tambem (reativar devolve o mesmo recorte).
SQL_CRIAR_MASTER = """
INSERT INTO usuario_masters (id_usuario, master_franquia) VALUES (%s, %s)
"""

SQL_REMOVER_MASTER = """
DELETE FROM usuario_masters WHERE id_usuario = %s AND master_franquia = %s
"""

SQL_MASTERS_DO_ALVO = """
SELECT master_franquia FROM usuario_masters WHERE id_usuario = %s ORDER BY master_franquia
"""

# Os avisos que a pessoa recebe alem dos do perfil (028, DEC-090), no molde dos masters: INSERT
# por aviso novo, DELETE por aviso que saiu, e a leitura do conjunto atual para o diff.
SQL_CRIAR_AVISO = """
INSERT INTO usuario_avisos (id_usuario, aviso) VALUES (%s, %s)
"""

SQL_REMOVER_AVISO = """
DELETE FROM usuario_avisos WHERE id_usuario = %s AND aviso = %s
"""

SQL_AVISOS_DO_ALVO = """
SELECT aviso FROM usuario_avisos WHERE id_usuario = %s ORDER BY aviso
"""

#: Mesma regra do CHECK `chk_usuario_masters_nome` (025): de 2 a 120 caracteres, sem espaco nas
#: pontas (o `_normalizar_masters` apara antes de medir).
_MASTER_TAMANHO_MIN = 2
_MASTER_TAMANHO_MAX = 120

#: As duas recusas de vinculo que dependem do PERFIL. Constantes porque a rota e os testes citam o
#: mesmo texto, e a tela o mostra como veio (422).
MSG_MASTER_OBRIGATORIO = "Escolha ao menos um master para o perfil Master."
MSG_MASTER_SO_DO_PERFIL_MASTER = "Master franquia só se vincula ao perfil Master."

#: Mesma regra do CHECK `chk_usuario_paises_sigla` (021:19) e do `perfil._RE_PAIS`: 2 letras
#: MAIUSCULAS. Replicado aqui (e nao importado de `perfil`, outra camada) para a camada de dados
#: nao depender da de aplicacao. NAO e' `if pais == "XX"`: valida FORMATO, nao uma sigla (DEC-047).
_RE_SIGLA_PAIS = re.compile(r"^[A-Z]{2}$")

# Le o hash para conferir a senha atual, e trava a linha ate' o fim da transacao: sem `FOR UPDATE`,
# duas trocas simultaneas gravariam dois hashes e a segunda venceria sem registro da primeira.
SQL_ESTADO_DA_SENHA = """
SELECT u.id_usuario, u.senha_hash, u.senha_definida_em_usuario IS NOT NULL, u.ativo
FROM usuarios u
WHERE u.id_usuario = %s
FOR UPDATE OF u
"""

# LEITURA do estado da senha, para a tela saber se deve oferecer a troca. Separado do
# `SQL_ESTADO_DA_SENHA` acima de proposito: aquele tem `FOR UPDATE` e e' o caminho de ESCRITA --
# `conexao()` abre READ ONLY e o servidor recusaria o `FOR UPDATE` ali dentro.
#
# Chaveia por LOGIN e nao por id porque quem chama e' o `/api/me`, que so' tem o header de
# identidade na mao; resolver o id antes seria uma ida a mais ao banco para o mesmo fim.
#
# `AND u.ativo` espelha o `SQL_IDENTIDADE` do rbac: pessoa inativa nao tem estado de senha a
# exibir, porque nao tem tela onde exibir.
SQL_ESTADO_DA_SENHA_POR_LOGIN = """
SELECT u.deve_trocar_senha_usuario, u.senha_definida_em_usuario IS NOT NULL
FROM usuarios u
WHERE u.login_usuario = %s AND u.ativo
"""

# A credencial para o LOGIN do P19 (D30). Constante PROPRIA, e as duas vizinhas explicam por que
# nenhuma delas serve:
#   * `SQL_ESTADO_DA_SENHA` devolve o hash, mas e' por `id_usuario` -- e quem esta' entrando
#     informa LOGIN, nao id -- e trava a linha com `FOR UPDATE`, porque e' do fluxo de TROCA.
#     Travar a linha de `usuarios` a cada tentativa de login serializaria as entradas da pessoa e
#     poria escrita no caminho de quem so' quer entrar;
#   * `SQL_ESTADO_DA_SENHA_POR_LOGIN` e' por login, mas NAO traz hash nem id -- ela existe para o
#     `/api/me` oferecer a troca, e o comentario da vizinha diz a regra que ela honra: "ler um hash
#     que nao sera' usado e' tirar o hash do banco a toa". Aqui o hash SERA' usado.
#
# `AND u.ativo` e' a trava de desligamento: quem foi desativado nao entra, e nao ha' caminho de
# login que contorne isso. Mesmo espelho do D9/D23 que o `SQL_IDENTIDADE` do rbac usa.
#
# `deve_trocar_senha_usuario` vem junto porque a resposta do login precisa dizer a' SPA se ela
# deve abrir a tela de troca imediatamente (D26). Buscar isso depois seria uma segunda ida ao
# banco para um dado que ja' estava na mesma linha.
SQL_CREDENCIAL_POR_LOGIN = """
SELECT u.id_usuario, u.senha_hash, u.deve_trocar_senha_usuario,
       u.senha_expira_em_usuario, u.senha_redefinida_em_usuario
FROM usuarios u
WHERE u.login_usuario = %s AND u.ativo
"""

# Os campos andam juntos e por isso vao no MESMO UPDATE: gravar o hash sem carimbar a data
# deixaria a coluna da 016 mentindo, e limpar `deve_trocar` sem gravar o hash liberaria a pessoa
# de uma troca que nao aconteceu.
#
# `senha_expira_em_usuario = NULL` e' obrigatorio aqui, nao higiene: a senha que a pessoa acabou
# de escolher nao expira, e deixar o prazo da TEMPORARIA para tras daria uma senha propria com
# validade -- a pessoa barrada com a senha certa, lendo "Login ou senha incorretos". O
# `ck_usuarios_prazo_exige_troca` (019) recusa a escrita se esta linha sumir.
SQL_DEFINIR_SENHA = """
UPDATE usuarios
SET senha_hash = %s,
    senha_definida_em_usuario = now(),
    deve_trocar_senha_usuario = FALSE,
    senha_expira_em_usuario = NULL
WHERE id_usuario = %s
"""

# O estado da senha visto por QUEM ADMINISTRA, com a linha travada. Separado do
# `SQL_ESTADO_DA_SENHA` de proposito: aquele devolve o hash para conferir a senha atual, e o admin
# nunca confere senha de ninguem -- ler um hash que nao sera' usado e' tirar o hash do banco a toa.
SQL_ESTADO_DA_SENHA_PARA_ADMIN = """
SELECT u.id_usuario, u.senha_definida_em_usuario IS NOT NULL, u.deve_trocar_senha_usuario
FROM usuarios u
WHERE u.id_usuario = %s
FOR UPDATE OF u
"""

# O espelho de uma linha nascida por `criar` nas tres colunas do ciclo da senha: hash da inicial,
# data NULA (a pessoa nao definiu nada) e a marca ligada. Os tres no MESMO UPDATE pelo motivo do
# `SQL_DEFINIR_SENHA` -- separados, a 016 mentiria no intervalo.
SQL_REDEFINIR_SENHA = """
UPDATE usuarios
SET senha_hash = %s,
    senha_definida_em_usuario = NULL,
    deve_trocar_senha_usuario = TRUE,
    senha_expira_em_usuario = now() + make_interval(hours => %s),
    senha_redefinida_em_usuario = now()
WHERE id_usuario = %s
"""

# So' a marca. A senha que a pessoa tem continua valendo ate' ela trocar -- e por isso
# `senha_definida_em_usuario` nao entra: ela DEFINIU a dela, e a coluna tem de continuar dizendo.
SQL_EXIGIR_TROCA = """
UPDATE usuarios SET deve_trocar_senha_usuario = TRUE WHERE id_usuario = %s
"""

# `entidade`/`entidade_id` = quem SOFREU (D24); `id_usuario` = quem FEZ. Sem PII em `metadados`
# (convencoes §5): nunca login nem e-mail do alvo -- o id basta, e quem le resolve em `usuarios`.
SQL_REGISTRAR_EVENTO = """
INSERT INTO eventos (id_usuario, tipo, entidade, entidade_id, metadados)
VALUES (%s, %s, %s, %s, %s)
"""


@dataclass(frozen=True)
class UsuarioAdmin:
    """Uma linha da tela de administracao."""

    id_usuario: int
    login: str
    nome: str
    email: str
    perfil: str
    ativo: bool
    #: Se a pessoa ja' definiu a senha dela alguma vez (016). `False` = ainda na senha inicial.
    senha_propria: bool = False
    #: Se a proxima entrada dela deve pedir troca (016).
    deve_trocar_senha: bool = True
    #: Paises que a pessoa pode acessar (DEC-081, siglas). Tupla (imutavel) p/ o frozen dataclass.
    paises: tuple[str, ...] = ()
    #: Masters franquia vinculados (`usuario_masters`, emenda 1 da DEC-087), na grafia gravada.
    #: So' o perfil `master` os tem; para os outros, vazio.
    masters: tuple[str, ...] = ()
    #: Os avisos marcados para a pessoa na aba Acessos (`usuario_avisos`, DEC-090), alem dos que o
    #: perfil ja' da'.
    avisos: tuple[str, ...] = ()

    def como_json(self) -> dict[str, Any]:
        return {
            "id_usuario": self.id_usuario,
            "login": self.login,
            "nome": self.nome,
            "email": self.email,
            "perfil": self.perfil,
            "ativo": self.ativo,
            # Nunca `senha_hash` aqui, nem mascarado. O payload vai para o navegador de quem
            # administra, e o hash nao tem por que sair do banco -- a tela precisa saber se a
            # pessoa ja' definiu a dela, e isso e' um booleano.
            "senha_propria": self.senha_propria,
            "deve_trocar_senha": self.deve_trocar_senha,
            "paises": list(self.paises),
            "masters": list(self.masters),
            "avisos": list(self.avisos),
        }


def listar() -> list[UsuarioAdmin]:
    """Todos os usuarios, ativos primeiro. Inclui INATIVOS de proposito.

    Esconder quem foi desativado tornaria a reativacao impossivel pela tela, e e' justamente o
    caso de quem volta de licenca ou muda de area e volta.
    """
    with conexao() as con:
        linhas = con.execute(SQL_LISTAR).fetchall()
    return [
        UsuarioAdmin(
            id_usuario=linha[0],
            login=str(linha[1]),
            nome=str(linha[2]),
            email=str(linha[3]),
            perfil=str(linha[4]),
            ativo=bool(linha[5]),
            senha_propria=bool(linha[8]),
            deve_trocar_senha=bool(linha[9]),
            paises=tuple(linha[10] or ()),
            masters=tuple(linha[11] or ()),
            avisos=tuple(linha[12] or ()),
        )
        for linha in linhas
    ]


def perfis() -> list[dict[str, Any]]:
    """Os perfis do seed, do menor para o maior. A ordem e' a hierarquia da D22."""
    with conexao() as con:
        linhas = con.execute(SQL_PERFIS).fetchall()
    return [
        {"perfil": str(nome), "descricao": str(descricao), "capacidades": int(qtd)}
        for nome, descricao, qtd in linhas
    ]


def _recusar_auto_alvo(id_alvo: int, autor: int) -> None:
    """Ninguem muda o proprio acesso por esta tela.

    Nao e' paternalismo: sao dois modos de falha concretos. Um admin que se rebaixa por engano
    perde a tela que usaria para desfazer -- e o conserto vira `UPDATE` manual na VPS, que e'
    exatamente o que esta tela existe para evitar. E auto-desativacao derruba a propria sessao no
    meio da requisicao seguinte, sem ninguem para reverter se ele for o unico admin.
    """
    if id_alvo == autor:
        raise AlvoEhOAutor(
            "Você não pode alterar o seu próprio acesso por aqui. Peça a outra pessoa do perfil "
            "Growth, ou faça pelo banco se for o único."
        )


def _estado_atual(con: Any, id_alvo: int) -> tuple[str, bool]:
    """Perfil e status de agora, com a linha travada ate' o fim da transacao."""
    linha = con.execute(SQL_ESTADO_ATUAL, (id_alvo,)).fetchone()
    if linha is None:
        raise UsuarioDesconhecido(f"usuário {id_alvo} não existe")
    return str(linha[2]), bool(linha[3])


def _registrar(con: Any, *, autor: int, tipo: str, id_alvo: int, metadados: Any) -> None:
    """Grava o evento na MESMA transacao da mudanca. Ver o cabecalho do modulo."""
    from psycopg.types.json import Jsonb  # import tardio: so' quem escreve paga

    con.execute(
        SQL_REGISTRAR_EVENTO,
        (autor, tipo, ENTIDADE_USUARIO, id_alvo, Jsonb(metadados) if metadados else None),
    )


def _aplicar_perfil(
    con: Any, id_alvo: int, perfil_antes: str, novo_perfil: str, *, autor: int
) -> dict[str, Any]:
    """O passo da troca de perfil, DENTRO de uma transacao aberta e com a linha ja' travada.

    Redacao UNICA da regra, usada por `alterar_perfil` e por `alterar_acesso`: duas copias do
    mesmo passo desencontram em silencio (DEC-044).
    """
    linha = con.execute(SQL_ID_DO_PERFIL, (novo_perfil,)).fetchone()
    if linha is None:
        raise PerfilDesconhecido(f"perfil '{novo_perfil}' não existe")

    # Nada a fazer e' sucesso, nao erro -- mas NAO gera evento: a trilha registra mudanca, e
    # uma linha `de: growth, para: growth` polui a auditoria com ruido que parece sinal.
    if perfil_antes == novo_perfil:
        return {"id_usuario": id_alvo, "de": perfil_antes, "para": novo_perfil, "mudou": False}

    con.execute(SQL_TROCAR_PERFIL, (linha[0], id_alvo))
    _registrar(
        con,
        autor=autor,
        tipo=EVENTO_PERFIL_ALTERADO,
        id_alvo=id_alvo,
        metadados={"de": perfil_antes, "para": novo_perfil},
    )
    return {"id_usuario": id_alvo, "de": perfil_antes, "para": novo_perfil, "mudou": True}


def _aplicar_ativo(
    con: Any, id_alvo: int, ativo_antes: bool, ativo: bool, *, autor: int
) -> dict[str, Any]:
    """O passo de desativar/reativar, DENTRO de uma transacao aberta. Mesma razao do de cima."""
    if ativo_antes == ativo:
        return {"id_usuario": id_alvo, "ativo": ativo, "mudou": False}

    con.execute(SQL_DEFINIR_ATIVO, (ativo, id_alvo))
    _registrar(
        con,
        autor=autor,
        tipo=EVENTO_REATIVADO if ativo else EVENTO_DESATIVADO,
        id_alvo=id_alvo,
        metadados=None,
    )
    return {"id_usuario": id_alvo, "ativo": ativo, "mudou": True}


def _aplicar_paises(
    con: Any, id_alvo: int, paises_antes: list[str], paises_desejados: list[str], *, autor: int
) -> dict[str, Any]:
    """O passo de ajustar os paises de uma pessoa (replace-all), DENTRO de uma transacao aberta.

    `paises_desejados` ja' vem de `_normalizar_paises` (MAIUSCULAS, sem repetido, NAO-vazio) --
    conjunto vazio nunca chega aqui, e e' assim que a Fase 2 impede alguem de ficar sem pais (o
    gate fail-closed, o proprio bug do P4). Computa o diff contra `paises_antes` e aplica so' a
    diferenca: um INSERT por pais novo, um DELETE por pais removido, cada um com SEU evento (a
    mesma regra "sem mudanca, sem evento" de `_aplicar_perfil`). A remocao e' um DELETE porque
    `usuario_paises` nao tem trigger de historico -- o evento `usuario.pais_removido` e' o rastro.
    """
    antes, desejados = set(paises_antes), set(paises_desejados)
    adicionar = [p for p in paises_desejados if p not in antes]
    remover = sorted(antes - desejados)
    de, para = sorted(antes), sorted(desejados)
    if not adicionar and not remover:
        return {"id_usuario": id_alvo, "de": de, "para": para, "mudou": False}
    for sigla in adicionar:
        con.execute(SQL_CRIAR_PAIS, (id_alvo, sigla))
        _registrar(
            con, autor=autor, tipo=EVENTO_PAIS_ATRIBUIDO, id_alvo=id_alvo, metadados={"pais": sigla}
        )
    for sigla in remover:
        con.execute(SQL_REMOVER_PAIS, (id_alvo, sigla))
        _registrar(
            con, autor=autor, tipo=EVENTO_PAIS_REMOVIDO, id_alvo=id_alvo, metadados={"pais": sigla}
        )
    return {"id_usuario": id_alvo, "de": de, "para": para, "mudou": True}


def _masters_do_alvo(con: Any, id_alvo: int) -> list[str]:
    """Os masters vinculados agora, DENTRO da transacao (a linha de `usuarios` ja' travada)."""
    return [str(r[0]) for r in con.execute(SQL_MASTERS_DO_ALVO, (id_alvo,)).fetchall()]


def _aplicar_masters(
    con: Any,
    id_alvo: int,
    masters_antes: list[str],
    masters_desejados: list[str],
    virando_master: bool = False,
    *,
    autor: int,
) -> dict[str, Any]:
    """O passo de ajustar o vinculo com masters franquia (replace-all), DENTRO de uma transacao.

    Mesma forma do `_aplicar_paises`: diff contra o conjunto atual, um INSERT por nome novo e um
    DELETE por nome que saiu, e "sem mudanca, sem evento". Tres diferencas, todas de proposito:
      * conjunto VAZIO e' aceito aqui -- e' assim que quem deixa de ser master perde o vinculo. A
        regra "perfil master exige ao menos um" e' do chamador, que conhece o perfil resultante;
      * UM evento por gesto (`usuario.masters_alterados`), so' com as contagens: o nome do master
        e' nome de pessoa, e nao vai para `metadados`;
      * `virando_master`: quem VIRA master tem o recorte DADO naquele gesto, mesmo que o conjunto
        escolhido coincida com linhas que sobraram de antes (o vinculo de quem nao era master nao
        recortava nada). Sem diff, nada e' escrito, mas o evento sai e `mudou` e' verdadeiro --
        senao a trilha mostraria so' a troca de perfil e ninguem saberia quem deu aquele recorte.
    A comparacao e' EXATA (com caixa): trocar "dalmo ribeiro" por "Dalmo Ribeiro" e' mudanca de
    grafia gravada, e a grafia do cadastro e' a que deve ficar.
    """
    antes = set(masters_antes)
    adicionar = [m for m in masters_desejados if m not in antes]
    remover = sorted(antes - set(masters_desejados))
    de, para = sorted(antes), sorted(set(masters_desejados))
    if not adicionar and not remover and not virando_master:
        return {"id_usuario": id_alvo, "de": de, "para": para, "mudou": False}
    for nome in remover:
        con.execute(SQL_REMOVER_MASTER, (id_alvo, nome))
    for nome in adicionar:
        con.execute(SQL_CRIAR_MASTER, (id_alvo, nome))
    _registrar(
        con,
        autor=autor,
        tipo=EVENTO_MASTERS_ALTERADOS,
        id_alvo=id_alvo,
        metadados={"antes": len(de), "depois": len(para)},
    )
    return {"id_usuario": id_alvo, "de": de, "para": para, "mudou": True}


def _masters_resultantes(
    con: Any,
    id_alvo: int,
    *,
    perfil_antes: str,
    perfil_final: str,
    masters_norm: list[str] | None,
) -> tuple[list[str], list[str], bool] | None:
    """Decide o vinculo final ANTES de qualquer escrita. `None` = nao mexer no vinculo.

    Devolve `(antes, desejados, virando_master)`, na ordem dos parametros do `_aplicar_masters`.
    As regras, todas pelo perfil RESULTANTE da mesma chamada:
      * perfil final `master` com vinculo pedido: o pedido nao pode ser vazio -- master sem
        vinculo entraria e veria a carteira vazia sem nada acusar;
      * quem VIRA master agora tem de mandar o vinculo, SEMPRE. O que esta' gravado nao conta:
        linha de quem nao e' master e' sobra (antes da emenda 1 da DEC-087 a troca de perfil nao
        apagava o vinculo, e a 025 ja' estava no ar), e voltar a ser master exige escolher de
        novo, nao herdar um nome velho sem conferencia no cadastro e sem evento. Por isso
        `alterar_perfil(.., 'master')` e' sempre recusado: o caminho e' o `alterar_acesso` com
        `masters`;
      * quem JA' era master e nao teve o vinculo pedido nao e' conferido: desativar um master sem
        vinculo nao pode ser barrado por isso;
      * perfil final de outro tipo: pedir nome e' erro; quem SAI de master perde o vinculo
        inteiro, na mesma transacao da troca de perfil (o vinculo de quem nao e' master nao
        recorta nada).
    """
    if perfil_final == PERFIL_MASTER:
        virando_master = perfil_antes != PERFIL_MASTER
        if masters_norm is None:
            if virando_master:
                raise ValueError(MSG_MASTER_OBRIGATORIO)
            return None
        if not masters_norm:
            raise ValueError(MSG_MASTER_OBRIGATORIO)
        return _masters_do_alvo(con, id_alvo), masters_norm, virando_master
    if masters_norm:
        raise ValueError(MSG_MASTER_SO_DO_PERFIL_MASTER)
    if masters_norm is not None or perfil_antes == PERFIL_MASTER:
        return _masters_do_alvo(con, id_alvo), [], False
    return None


def alterar_perfil(id_alvo: int, novo_perfil: str, *, autor: int) -> dict[str, Any]:
    """Troca o perfil e registra `usuario.perfil_alterado`. Devolve o de-para aplicado."""
    _recusar_auto_alvo(id_alvo, autor)

    with transacao(id_usuario=autor) as con:
        perfil_antes, _ = _estado_atual(con, id_alvo)
        # A regra do vinculo com master vale aqui tambem (uma redacao so', `_masters_resultantes`):
        # virar master por aqui e' sempre recusado (esta funcao nao recebe o vinculo, e o gravado
        # nao conta), e sair de master leva o vinculo junto.
        plano = _masters_resultantes(
            con, id_alvo, perfil_antes=perfil_antes, perfil_final=novo_perfil, masters_norm=None
        )
        resultado = _aplicar_perfil(con, id_alvo, perfil_antes, novo_perfil, autor=autor)
        if plano is not None:
            _aplicar_masters(con, id_alvo, *plano, autor=autor)
    return resultado


def definir_ativo(id_alvo: int, ativo: bool, *, autor: int) -> dict[str, Any]:
    """Desativa ou reativa, e registra o evento correspondente.

    Desativar e' o caminho de quem sai da empresa, e ele e' SOFT (D9/D23): a linha fica, o login
    sai do indice unico parcial e volta a ser reutilizavel, e a trilha historica da pessoa
    continua existindo. Nunca apagar -- `eventos.id_usuario` e' `ON DELETE SET NULL`, entao um
    DELETE de verdade orfanaria toda a autoria dela de uma vez.
    """
    _recusar_auto_alvo(id_alvo, autor)

    with transacao(id_usuario=autor) as con:
        _, ativo_antes = _estado_atual(con, id_alvo)
        resultado = _aplicar_ativo(con, id_alvo, ativo_antes, ativo, autor=autor)
    return resultado


def _aplicar_avisos(
    con: Any, id_alvo: int, avisos_desejados: list[str], *, autor: int
) -> dict[str, Any]:
    """O passo de ajustar os avisos de uma pessoa (replace-all), DENTRO de uma transacao aberta.

    Mesma forma do `_aplicar_masters`: diff contra o conjunto atual, um INSERT por aviso novo e um
    DELETE por aviso que saiu, "sem mudanca, sem evento", e UM evento por gesto
    (`usuario.avisos_alterados`) com o conjunto antes e depois. Vazio e' aceito: e' assim que a
    pessoa deixa de receber o que estava marcado."""
    antes = {str(r[0]) for r in con.execute(SQL_AVISOS_DO_ALVO, (id_alvo,)).fetchall()}
    adicionar = [a for a in avisos_desejados if a not in antes]
    remover = sorted(antes - set(avisos_desejados))
    de, para = sorted(antes), sorted(set(avisos_desejados))
    if not adicionar and not remover:
        return {"id_usuario": id_alvo, "de": de, "para": para, "mudou": False}
    for aviso in remover:
        con.execute(SQL_REMOVER_AVISO, (id_alvo, aviso))
    for aviso in adicionar:
        con.execute(SQL_CRIAR_AVISO, (id_alvo, aviso))
    _registrar(
        con,
        autor=autor,
        tipo=EVENTO_AVISOS_ALTERADOS,
        id_alvo=id_alvo,
        metadados={"antes": de, "depois": para},
    )
    return {"id_usuario": id_alvo, "de": de, "para": para, "mudou": True}


def _normalizar_avisos(avisos: list[str]) -> list[str]:
    """Os avisos pedidos, sem repetido e so' os que existem (`avisos.AVISOS`, o mesmo conjunto do
    CHECK `chk_usuario_avisos_tipo`): aviso desconhecido e' recusado com mensagem, antes do banco."""
    from .avisos import AVISOS

    vistos: list[str] = []
    for aviso in avisos:
        chave = str(aviso).strip()
        if chave not in AVISOS:
            raise ValueError(f"Aviso desconhecido: {chave!r}.")
        if chave not in vistos:
            vistos.append(chave)
    return vistos


def alterar_acesso(
    id_alvo: int,
    *,
    autor: int,
    perfil: str | None = None,
    ativo: bool | None = None,
    paises: list[str] | None = None,
    masters: list[str] | None = None,
    avisos: list[str] | None = None,
) -> dict[str, Any]:
    """Perfil, status, paises, masters e/ou avisos de UMA pessoa numa transacao SO', com um evento por
    mudanca.

    E' o que o `PATCH /api/acessos/usuarios/{id}` chama (#463, follow-up B). Ate' 24/10/2026 a
    rota chamava `alterar_perfil` e `definir_ativo` em sequencia -- DUAS transacoes. Se a
    segunda falhasse (o banco caiu entre as duas, um lock timeout), a primeira ja' estava
    gravada e a resposta era um 503 que nao dizia isso: a tela mostrava "Indisponivel" e a
    pessoa tinha mudado de perfil mesmo assim. Aqui as duas mudancas e os dois eventos
    commitam juntos, ou nada commita.

    OS EVENTOS CONTINUAM SEPARADOS, de proposito: "virou Growth" e "foi desativado" respondem a
    perguntas diferentes na auditoria. UMA trava (`_estado_atual`), lida uma vez: os dois passos
    partem do MESMO estado anterior, e a ordem (perfil, depois status) e' a de sempre.

    `alterar_perfil` e `definir_ativo` ficam com a assinatura de sempre; as tres compartilham os
    passos (`_aplicar_perfil`, `_aplicar_ativo`), entao cada regra tem UMA redacao.

    `masters` (emenda 1 da DEC-087) e' o conjunto DESEJADO de masters franquia (replace-all);
    `None` = nao mexe. As regras que dependem do perfil resultante estao em `_masters_resultantes`
    e rodam ANTES de qualquer escrita; quem sai de master perde o vinculo nesta mesma transacao,
    e a resposta traz o bloco `masters` tambem nesse caso. Os nomes chegam ja' na grafia do
    cadastro: conferir que existem e' da rota, que conhece o cadastro.

    `avisos` (DEC-090) e' o conjunto DESEJADO de avisos marcados para a pessoa (replace-all);
    `None` = nao mexe. Independe do perfil: o que o perfil ja' da' nao entra aqui.
    """
    if perfil is None and ativo is None and paises is None and masters is None and avisos is None:
        raise ValueError(
            "Informe `perfil`, `ativo`, `paises`, `masters`, `avisos`, ou uma combinação."
        )
    _recusar_auto_alvo(id_alvo, autor)
    # Normaliza/valida FORA da transacao (recusa vazio cedo -- vazio e' o bug do P4); o
    # pertencimento ao catalogo (BR/AR) ja' foi conferido na rota.
    paises_norm = _normalizar_paises(paises) if paises is not None else None
    masters_norm = _normalizar_masters(masters) if masters is not None else None
    avisos_norm = _normalizar_avisos(avisos) if avisos is not None else None

    resultado: dict[str, Any] = {"id_usuario": id_alvo}
    with transacao(id_usuario=autor) as con:
        perfil_antes, ativo_antes = _estado_atual(con, id_alvo)
        plano_masters = _masters_resultantes(
            con,
            id_alvo,
            perfil_antes=perfil_antes,
            perfil_final=perfil if perfil is not None else perfil_antes,
            masters_norm=masters_norm,
        )
        if perfil is not None:
            resultado["perfil"] = _aplicar_perfil(con, id_alvo, perfil_antes, perfil, autor=autor)
        if ativo is not None:
            resultado["status"] = _aplicar_ativo(con, id_alvo, ativo_antes, ativo, autor=autor)
        if paises_norm is not None:
            paises_antes = [
                str(r[0]) for r in con.execute(SQL_PAISES_DO_USUARIO, (id_alvo,)).fetchall()
            ]
            resultado["paises"] = _aplicar_paises(
                con, id_alvo, paises_antes, paises_norm, autor=autor
            )
        if plano_masters is not None:
            resultado["masters"] = _aplicar_masters(con, id_alvo, *plano_masters, autor=autor)
        if avisos_norm is not None:
            resultado["avisos"] = _aplicar_avisos(con, id_alvo, avisos_norm, autor=autor)
    return resultado


# ---------------------------------------------------------------------------
# Criacao e senha (D26 / migration 016)
# ---------------------------------------------------------------------------

#: Nome dos dois indices unicos parciais, para traduzir a violacao no erro certo. Sao PARCIAIS
#: (`WHERE ativo`) de proposito: login e e-mail de quem saiu voltam a ser reutilizaveis (D9/D23).
INDICE_LOGIN = "idx_usuarios_login_ativo"
INDICE_EMAIL = "idx_usuarios_email_ativo"


def _traduzir_conflito(erro: Exception) -> Exception:
    """`UniqueViolation` -> erro de dominio, pelo nome do indice que estourou.

    Sem isto a rota devolveria 500 para um conflito que a tela sabe explicar ("esse login ja'
    esta em uso"). Casar pelo NOME do indice, e nao pela mensagem, porque a mensagem do Postgres
    e' localizada -- o cluster do Vinicius responde em portugues.
    """
    nome = ""
    diag = getattr(erro, "diag", None)
    if diag is not None:
        nome = str(getattr(diag, "constraint_name", "") or "")
    texto = f"{nome} {erro}"

    if INDICE_LOGIN in texto:
        return LoginEmUso(
            "Já existe um usuário ativo com esse login. Se a pessoa saiu e voltou, reative o "
            "cadastro dela em vez de criar outro."
        )
    if INDICE_EMAIL in texto:
        return EmailEmUso("Já existe um usuário ativo com esse e-mail.")
    return erro


def _normalizar_paises(paises: list[str]) -> list[str]:
    """Normaliza e valida os paises de uma pessoa (DEC-081, P4).

    strip + MAIUSCULAS, remove repetidos preservando a ordem, e RECUSA lista vazia -- vazio e' o
    proprio bug do P4 (pessoa sem pais cai no gate fail-closed e nao entra em lugar nenhum). Valida
    o FORMATO de cada sigla (2 letras maiusculas), nunca uma sigla especifica (DEC-047); o
    pertencimento ao catalogo da plataforma (BR/AR) e' checado na rota, que conhece o catalogo.
    """
    vistos: list[str] = []
    for bruto in paises:
        sigla = bruto.strip().upper()
        if not _RE_SIGLA_PAIS.match(sigla):
            raise ValueError(f"País inválido: {bruto!r}. Use a sigla de 2 letras (ex.: BR, AR).")
        if sigla not in vistos:
            vistos.append(sigla)
    if not vistos:
        raise ValueError("Selecione pelo menos um país.")
    return vistos


def _normalizar_masters(masters: list[str]) -> list[str]:
    """Normaliza os nomes de master franquia de um vinculo (emenda 1 da DEC-087).

    Apara as pontas e colapsa espacos internos (um espaco duplo que ninguem ve faria o vinculo
    nunca casar com o cadastro), e remove repetidos SEM CAIXA, mantendo a primeira grafia --
    "Dalmo Ribeiro" e "dalmo ribeiro" sao o mesmo master. Recusa nome fora de 2 a 120 caracteres,
    a regra do CHECK `chk_usuario_masters_nome` (025), com mensagem em vez do 500 cru do banco.

    Lista vazia NAO e' recusada aqui, ao contrario dos paises: vazio e' legitimo para quem nao e'
    master. A regra "master exige ao menos um" depende do perfil e mora em `criar` e em
    `_masters_resultantes`. Que o nome EXISTE no cadastro e' conferido na rota.
    """
    vistos: list[str] = []
    chaves: set[str] = set()
    for bruto in masters:
        nome = " ".join(str(bruto).split())
        if not _MASTER_TAMANHO_MIN <= len(nome) <= _MASTER_TAMANHO_MAX:
            raise ValueError(
                f"Nome de master inválido: {bruto!r}. Use de {_MASTER_TAMANHO_MIN} a "
                f"{_MASTER_TAMANHO_MAX} caracteres."
            )
        chave = nome.casefold()
        if chave not in chaves:
            chaves.add(chave)
            vistos.append(nome)
    return vistos


def _validar_login(login: str) -> None:
    """Recusa o login que o piloto nao consegue carregar inteiro (revisao de seguranca de 06/11/2026).

    Duas regras, e as duas existem pela MESMA razao: o login atravessa um header HTTP (latin-1)
    e o RBAC re-resolve a pessoa pelo texto que chegou. Caractere que o header descarta faz o
    login virar OUTRO login (`felipe` + U+200B chegava como `felipe`); caractere invisivel ou de
    controle, mesmo dentro de latin-1, faz dois logins parecerem um so' na tela de Acessos.

    Acento continua valendo (`joão` cabe em latin-1) -- a regra nao e' "so' ASCII", e' "o que
    entra e' o que chega".
    """
    try:
        login.encode("latin-1")
    except UnicodeEncodeError:
        raise ValueError(
            "Login com caractere não aceito. Use letras, números, ponto, hífen ou sublinhado."
        ) from None
    for caractere in login:
        if caractere.isspace() or unicodedata.category(caractere) in ("Cc", "Cf"):
            raise ValueError(
                "Login com espaço ou caractere invisível. Use letras, números, ponto, hífen ou "
                "sublinhado."
            )


def criar(
    *,
    login: str,
    nome: str,
    email: str,
    perfil: str,
    paises: list[str],
    autor: int,
    masters: list[str] | None = None,
) -> dict[str, Any]:
    """Cria a pessoa com a senha INICIAL e registra `usuario.criado`. Devolve o id novo.

    `masters` (emenda 1 da DEC-087): o vinculo com master(s) franquia, gravado na MESMA transacao
    da criacao. O perfil `master` EXIGE ao menos um (sem vinculo, a pessoa entraria e veria a
    carteira vazia); qualquer outro perfil o RECUSA. Quando ha' vinculo, sai tambem o evento
    `usuario.masters_alterados` (de 0 para n), para a trilha dizer quem deu aquele recorte.

    E' o unico caso desta camada em que o alvo NAO existe antes da chamada -- logo, nao ha
    `_estado_atual`, nao ha `FOR UPDATE` e nao ha `_recusar_auto_alvo`: ninguem cria a si mesmo,
    porque quem esta criando ja' existe.

    A senha entregue e' a INICIAL COMPARTILHADA (`MOTOR_SENHA_INICIAL`), com sal proprio por
    linha, e a pessoa nasce com `deve_trocar_senha_usuario = TRUE`. Se a env nao estiver
    configurada, a criacao e' RECUSADA antes de abrir transacao -- criar alguem com uma senha que
    ninguem sabe qual e' seria pior que nao criar.

    Ate' 16/11/2026 a resposta trazia `falta_cadastrar_no_authelia`: o passo manual no
    `authelia/users_database.yml`, sem o qual a pessoa nao entrava (chave desligada) ou ficava
    fora de um rollback do corte (chave ligada). O Estagio 3 da DEC-081 aposentou o Authelia e o
    campo saiu. A rota acrescenta `login_proprio` para a tela dizer se a pessoa ja' entra.
    """
    from . import senhas

    login = login.strip()
    nome = nome.strip()
    email = email.strip()
    if not login or not nome or not email:
        raise ValueError("Login, nome e e-mail são obrigatórios.")
    _validar_login(login)
    if "@" not in email:
        raise ValueError("E-mail inválido.")
    paises_norm = _normalizar_paises(paises)
    masters_norm = _normalizar_masters(masters or [])
    if perfil == PERFIL_MASTER and not masters_norm:
        raise ValueError(MSG_MASTER_OBRIGATORIO)
    if perfil != PERFIL_MASTER and masters_norm:
        raise ValueError(MSG_MASTER_SO_DO_PERFIL_MASTER)

    # Fora da transacao de proposito: hashear custa ~64 MB e ~100 ms, e segurar uma transacao
    # aberta durante isso prenderia a linha de `perfis` sem motivo.
    hash_inicial = senhas.hash_da_senha_inicial()

    with transacao(id_usuario=autor) as con:
        linha_perfil = con.execute(SQL_ID_DO_PERFIL, (perfil,)).fetchone()
        if linha_perfil is None:
            raise PerfilDesconhecido(f"perfil '{perfil}' não existe")

        try:
            linha = con.execute(
                SQL_CRIAR, (login, nome, email, hash_inicial, linha_perfil[0])
            ).fetchone()
        except Exception as erro:  # noqa: BLE001 - traduzido para erro de dominio
            traduzido = _traduzir_conflito(erro)
            if traduzido is erro:
                raise
            raise traduzido from erro

        if linha is None:  # pragma: no cover - `RETURNING` de INSERT bem-sucedido sempre traz linha
            raise RuntimeError("INSERT em usuarios nao devolveu id")
        id_novo = int(linha[0])

        # Os paises da pessoa, na MESMA transacao da criacao (DEC-081, P4): criacao+pais sao
        # atomicos. Sem isto a pessoa nasce com conjunto vazio e o gate fail-closed a barra em
        # todo host -- o bug que esta fase estanca.
        for sigla in paises_norm:
            con.execute(SQL_CRIAR_PAIS, (id_novo, sigla))

        # `metadados` leva SO' o perfil. Nunca login, nome ou e-mail: e' PII, e a §4 do contrato
        # vale aqui como em todo lugar -- o `entidade_id` basta para quem le resolver em `usuarios`.
        _registrar(
            con,
            autor=autor,
            tipo=EVENTO_CRIADO,
            id_alvo=id_novo,
            metadados={"perfil": perfil},
        )

        # O vinculo com master(s), tambem na transacao da criacao: perfil `master` sem vinculo
        # nunca chega a existir. O evento proprio vem DEPOIS do `usuario.criado`, na ordem em que
        # as coisas aconteceram, e so' com contagens (nome de master e' PII).
        if masters_norm:
            _aplicar_masters(con, id_novo, [], masters_norm, autor=autor)

    return {
        "id_usuario": id_novo,
        "login": login,
        "perfil": perfil,
        "paises": paises_norm,
        "masters": sorted(masters_norm),
    }


@dataclass(frozen=True)
class Credencial:
    """O que o login precisa conferir, e nada mais.

    `senha_hash` e' `repr=False` DE PROPOSITO: dataclass imprime todos os campos no `repr`, e
    um traceback -- ou um `_LOG.debug("%s", cred)` distraido -- levaria o hash para o log. O hash
    nao e' a senha, mas tambem nao e' dado de log: e' material de ataque offline se o log vazar.
    """

    # `senha_hash` vem POR ULTIMO por exigencia do type checker: `field(...)` conta como campo
    # com default para ele, e campo sem default nao pode vir depois de um com default. Em tempo
    # de execucao `field(repr=False)` nao da' default nenhum -- mas o gate e' o `mypy src/`, e a
    # ordem custa nada.
    id_usuario: int
    deve_trocar: bool
    senha_hash: str = field(repr=False)
    #: Ate' quando o hash guardado vale. `None` = nao expira (senha que a pessoa escolheu).
    #: Quem compara com `now()` e' a rota de login -- DEPOIS do Argon2, para que "senha temporaria
    #: vencida" e "senha errada" custem o mesmo tempo e nao virem oraculo.
    expira_em: datetime | None = None
    #: Quando um administrador redefiniu esta senha pela ultima vez. E' PISO da trava de
    #: tentativas: sem ele a pessoa que errou cinco vezes antes de ligar receberia a senha nova e
    #: continuaria barrada, lendo a mesma mensagem de senha errada.
    redefinida_em: datetime | None = None


def credenciais_por_login(login: str) -> Credencial | None:
    """A credencial de quem esta' tentando entrar. `None` = login inexistente OU inativo.

    OS DOIS CASOS CAEM NO MESMO `None`, e isso e' decisao de seguranca, nao economia: distinguir
    "esse login nao existe" de "existe e esta' desativado" entrega ao visitante um oraculo de
    quem trabalha aqui. Quem precisa do detalhe olha a tabela.

    LEITURA, nunca transacao de escrita: entrar nao muda `usuarios`. E' o que permite tentativa
    de login concorrente sem serializar ninguem -- ver o comentario do `SQL_CREDENCIAL_POR_LOGIN`
    sobre o `FOR UPDATE` da constante vizinha.

    O que esta funcao NAO faz: conferir a senha. Isso e' de `senhas.verificar`, que recebe o hash
    e nunca levanta por senha errada. Separar as duas mantem o hash fora de qualquer decisao de
    fluxo aqui dentro.
    """
    if not login or not login.strip():
        return None
    with conexao() as con:
        linha = con.execute(SQL_CREDENCIAL_POR_LOGIN, (login.strip(),)).fetchone()
    if linha is None:
        return None
    return Credencial(
        id_usuario=int(linha[0]),
        senha_hash=str(linha[1]),
        deve_trocar=bool(linha[2]),
        expira_em=linha[3],
        redefinida_em=linha[4],
    )


def estado_da_senha(login: str) -> dict[str, bool] | None:
    """`{"deve_trocar": bool, "propria": bool}` de quem esta' logado. `None` se nao ha' linha.

    E' o que falta ao `/api/me` para a tela poder OFERECER a troca: ate' 11/09 o payload trazia
    usuario, abas e perfil, e nada dizia que a pessoa ainda esta' na senha inicial compartilhada.
    Sem este campo a tela nao tem como saber a quem oferecer, e o `deve_trocar_senha_usuario` da
    016 ficava sendo uma coluna que ninguem le'. Desde 24/10/2026 o `/api/me` so' pergunta com o
    login proprio LIGADO (`_estado_da_minha_senha`): desligado, a senha do banco nao abre porta.

    Os DOIS campos, e nao so' o primeiro: `deve_trocar` e' a INTENCAO (o admin pode forca-la de
    novo um dia) e `propria` e' o FATO (a pessoa ja' definiu senha alguma vez). Eles se separam
    no dia em que o admin forcar troca de quem ja' tinha senha propria -- ai' os dois sao `True`,
    e a tela precisa dizer "troque de novo", nao "defina a primeira".

    LEITURA PURA: `conexao()` e' READ ONLY e esta funcao nao escreve nada. Nao levanta se a
    pessoa nao existe -- devolve `None`, porque "sem cadastro no banco" e' estado legitimo
    enquanto o Authelia autentica (P19) e nao pode derrubar a abertura do app.
    """
    with conexao() as con:
        linha = con.execute(SQL_ESTADO_DA_SENHA_POR_LOGIN, (login,)).fetchone()
    if linha is None:
        return None
    return {"deve_trocar": bool(linha[0]), "propria": bool(linha[1])}


def trocar_a_propria_senha(*, autor: int, senha_atual: str, nova_senha: str) -> dict[str, Any]:
    """A pessoa troca a SENHA DELA. Registra `usuario.senha_definida`.

    Aqui o autor E' o alvo, e essa e' a inversao proposital do `_recusar_auto_alvo`: mudar o
    proprio PERFIL e' o que aquela guarda existe para impedir, e trocar a propria SENHA e' a
    unica coisa que so' a propria pessoa deveria poder fazer. Por isso a assinatura nao aceita
    id de alvo -- nao ha como chamar isto para outra pessoa por engano.

    Exige a senha atual. No primeiro acesso ela e' a inicial compartilhada, o que ainda vale a
    conferencia: sem ela, qualquer requisicao que chegasse com o header de identidade de alguem
    trocaria a senha daquela pessoa.
    """
    from . import senhas

    # A politica roda ANTES de abrir transacao: senha curta e' erro de quem digitou, e nao ha por
    # que travar linha nenhuma para descobrir isso. O `gerar` valida de novo antes de hashear --
    # ele e' o unico produtor legitimo do hash e nao confia em quem o chama.
    senhas.validar(nova_senha)

    with transacao(id_usuario=autor) as con:
        linha = con.execute(SQL_ESTADO_DA_SENHA, (autor,)).fetchone()
        if linha is None:
            raise UsuarioDesconhecido(f"usuário {autor} não existe")

        guardado = str(linha[1]) if linha[1] else None
        primeira_vez = not bool(linha[2])
        if not senhas.verificar(senha_atual, guardado):
            raise SenhaAtualIncorreta("A senha atual não confere.")

        # Hashear depois de conferir: a ordem inversa faria toda tentativa errada pagar 64 MB de
        # Argon2 de graca. A linha fica travada durante o hash, e isso e' inofensivo -- e' a
        # propria linha de quem esta trocando, e ninguem mais a disputa.
        con.execute(SQL_DEFINIR_SENHA, (senhas.gerar(nova_senha), autor))
        # `metadados` diz apenas se foi a primeira definicao -- o dado util para saber quem ainda
        # esta na senha inicial. Nunca a senha, nunca o hash, nunca parte de nenhum dos dois.
        _registrar(
            con,
            autor=autor,
            tipo=EVENTO_SENHA_DEFINIDA,
            id_alvo=autor,
            metadados={"primeira_vez": primeira_vez},
        )

    return {"id_usuario": autor, "primeira_vez": primeira_vez}


def redefinir_senha(id_alvo: int, *, autor: int) -> dict[str, Any]:
    """Devolve o alvo a senha INICIAL e liga a marca de troca. Registra `usuario.senha_redefinida`.

    O caminho de quem esqueceu a propria senha. O estado final e' o de uma linha nascida por
    `criar` nas tres colunas do ciclo da senha -- hash da inicial com sal proprio, data nula, marca
    ligada --, e nao "identico" a ela: `trg_usuarios_upd` move `atualizado_em_usuario`, que e' o
    rastro esperado de toda escrita nesta tabela.

    Ninguem redefine a PROPRIA senha por aqui (`_recusar_auto_alvo`): quem sabe a sua troca em
    `trocar_a_propria_senha`, e quem nao sabe precisa de outra pessoa -- que e' justamente o que
    deixa o gesto com dois nomes na trilha.

    Sempre escreve e sempre registra, mesmo quando a pessoa ja' estava na inicial. Ao contrario de
    trocar perfil, aqui o "ja' estava assim" nao e' verificavel: o hash guardado pode ser de
    qualquer coisa -- ate' 14/09 quatro linhas guardavam `hash_de_teste_*` e nao autenticavam nada.
    Redefinir e' o botao que conserta, e o clique e' ato deliberado de quem administra.

    `metadados.tinha_senha_propria` diz se o gesto APAGOU uma senha que a pessoa escolheu -- a
    diferenca entre arrumar o acesso de quem nunca entrou e derrubar a senha de alguem. Nunca a
    senha, nunca o hash, nunca parte de nenhum dos dois.
    """
    from . import senhas

    _recusar_auto_alvo(id_alvo, autor)

    # A senha e' NOVA e so' desta pessoa (D31). Ate' 18/09/2026 entregava-se
    # `senhas.hash_da_senha_inicial()`, a MESMA senha para todo mundo -- e quem conhecesse aquele
    # valor entrava na conta de qualquer um recem-redefinido.
    #
    # Hashear FORA da transacao, como `criar`: ~64 MB e ~100 ms, e segurar a linha travada durante
    # isso nao protege nada.
    temporaria = senhas.gerar_temporaria()
    hash_temporario = senhas.gerar(temporaria)

    with transacao(id_usuario=autor) as con:
        linha = con.execute(SQL_ESTADO_DA_SENHA_PARA_ADMIN, (id_alvo,)).fetchone()
        if linha is None:
            raise UsuarioDesconhecido(f"usuário {id_alvo} não existe")
        tinha_senha_propria = bool(linha[1])

        con.execute(SQL_REDEFINIR_SENHA, (hash_temporario, senhas.VALIDADE_TEMPORARIA_H, id_alvo))
        _registrar(
            con,
            autor=autor,
            tipo=EVENTO_SENHA_REDEFINIDA,
            id_alvo=id_alvo,
            # NUNCA a senha, nem o hash, nem parte de nenhum dos dois. `validade_horas` e' politica
            # aplicada, nao segredo, e responde "por quanto tempo aquela senha valeu" a quem audita.
            metadados={
                "tinha_senha_propria": tinha_senha_propria,
                "validade_horas": senhas.VALIDADE_TEMPORARIA_H,
            },
        )

    # A senha em TEXTO PURO sai daqui uma unica vez, para o administrador ler e repassar. Ela nao
    # e' guardada em lugar nenhum -- se ele a perder, o caminho e' gerar outra, o que mata esta.
    return {
        "id_usuario": id_alvo,
        "tinha_senha_propria": tinha_senha_propria,
        "senha_temporaria": temporaria,
        "validade_horas": senhas.VALIDADE_TEMPORARIA_H,
    }


def exigir_troca(id_alvo: int, *, autor: int) -> dict[str, Any]:
    """Liga a marca de troca sem mexer na senha. Registra `usuario.troca_exigida`.

    A migration 016 previa este gesto e ele nao existia: a marca so' andava de `TRUE` para `FALSE`,
    na troca da propria senha. Serve depois de uma suspeita de vazamento, ou quando alguem conta ter
    compartilhado a senha.

    Diferente do `redefinir_senha`, aqui o "ja' estava assim" E' verificavel -- e' uma coluna
    booleana --, entao vale a regra das outras escritas desta tela: sem mudanca, sem evento.
    """
    _recusar_auto_alvo(id_alvo, autor)

    with transacao(id_usuario=autor) as con:
        linha = con.execute(SQL_ESTADO_DA_SENHA_PARA_ADMIN, (id_alvo,)).fetchone()
        if linha is None:
            raise UsuarioDesconhecido(f"usuário {id_alvo} não existe")
        if bool(linha[2]):
            return {"id_usuario": id_alvo, "mudou": False}

        con.execute(SQL_EXIGIR_TROCA, (id_alvo,))
        _registrar(
            con,
            autor=autor,
            tipo=EVENTO_TROCA_EXIGIDA,
            id_alvo=id_alvo,
            metadados=None,
        )

    return {"id_usuario": id_alvo, "mudou": True}


# --- Alinhar a senha inicial (preparacao do corte do P19) -------------------------------
#
# CONTEXTO, porque isto so' faz sentido com ele: o hash de cada pessoa foi gravado NO
# MOMENTO EM QUE ELA FOI CRIADA, a partir da `MOTOR_SENHA_INICIAL` de ENTAO. Se a env mudou
# depois, ou se a linha nasceu por SQL a mao (com `hash_de_teste_*` ou coisa parecida), a
# pessoa NAO ENTRA quando o motor passar a autenticar -- `senhas.verificar` recusa qualquer
# coisa fora do formato PHC, e um hash de outra senha nao casa com a que ela digita.
#
# Enquanto o Authelia autentica isso e' inofensivo (a coluna nao abre porta nenhuma). No dia
# do corte vira gente trancada, descoberta uma a uma pelo telefone.

#: Quem esta' em que estado. As tres classes sao EXCLUDENTES e a ordem importa para a
#: decisao: so' a primeira e' segura de reescrever sem falar com ninguem.
#:
#:   `sem_propria`  -> nunca escolheu senha. A inicial compartilhada E' a senha dela por
#:                     definicao, entao regravar o hash da inicial nao lhe tira nada.
#:   `propria_quebrada` -> escolheu senha, mas o hash nao e' PHC valido. Esta' trancada, e
#:                     consertar significa PERDER a senha que ela escolheu -- decisao de
#:                     gente, nao de comando. Por isso aqui so' se RELATA.
#:   `propria_ok`   -> nada a fazer.
#:
#: `senha_hash LIKE '$argon2id$%%'`: o `%%` e' escape do proprio psycopg, nao do SQL -- esta
#: consulta leva parametro, e um `%` solitario viraria placeholder e morreria com
#: "syntax error at or near". Ja' aconteceu neste repositorio, em `SQL_CONTAGENS`.
SQL_ESTADO_DA_SENHA_INICIAL = """
SELECT u.id_usuario, u.login_usuario, u.senha_hash,
       CASE
         WHEN u.senha_definida_em_usuario IS NULL THEN 'sem_propria'
         WHEN u.senha_hash IS NULL OR u.senha_hash NOT LIKE %s THEN 'propria_quebrada'
         ELSE 'propria_ok'
       END AS classe
FROM usuarios u
WHERE u.ativo
ORDER BY u.login_usuario
"""

#: Regrava o hash de UMA pessoa com a senha inicial. NAO e' o `SQL_DEFINIR_SENHA`, e a
#: diferenca e' o ponto: aquele marca `senha_definida_em_usuario = now()` e
#: `deve_trocar = FALSE`, porque ele registra uma ESCOLHA. Aqui nao houve escolha nenhuma --
#: a pessoa continua na senha compartilhada, e as duas colunas tem de dizer isso. Marcar
#: `deve_trocar = TRUE` e' o que faz a tela convidar para a troca no primeiro acesso.
SQL_ALINHAR_SENHA_INICIAL = """
UPDATE usuarios
SET senha_hash = %s,
    senha_definida_em_usuario = NULL,
    deve_trocar_senha_usuario = TRUE,
    senha_expira_em_usuario = NULL
WHERE id_usuario = %s
"""
