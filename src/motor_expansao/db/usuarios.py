"""Administracao de usuarios: quem existe, com que perfil, e quem mudou o que.

O que esta camada resolve
-------------------------
Antes do banco, mudar o acesso de alguem era editar o `acesso_abas.json` no volume `:rw` -- sem
rebuild, sem deploy. Com o RBAC no banco, a mesma mudanca vira `UPDATE` manual na VPS. Isso e' uma
REGRESSAO de operabilidade, e e' o que este modulo existe para desfazer.

Por que o SQL mora aqui, e nao no `app.py`
------------------------------------------
O CI nao tem Postgres (decisao de 25/08) e quem executa contra banco real e' o Vinicius. Isso impoe
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

#: Valor de `entidade` para os eventos daqui (D24).
ENTIDADE_USUARIO = "usuario"


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
       u.deve_trocar_senha_usuario
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


def alterar_perfil(id_alvo: int, novo_perfil: str, *, autor: int) -> dict[str, Any]:
    """Troca o perfil e registra `usuario.perfil_alterado`. Devolve o de-para aplicado."""
    _recusar_auto_alvo(id_alvo, autor)

    with transacao(id_usuario=autor) as con:
        perfil_antes, _ = _estado_atual(con, id_alvo)

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


def criar(*, login: str, nome: str, email: str, perfil: str, autor: int) -> dict[str, Any]:
    """Cria a pessoa com a senha INICIAL e registra `usuario.criado`. Devolve o id novo.

    E' o unico caso desta camada em que o alvo NAO existe antes da chamada -- logo, nao ha
    `_estado_atual`, nao ha `FOR UPDATE` e nao ha `_recusar_auto_alvo`: ninguem cria a si mesmo,
    porque quem esta criando ja' existe.

    A senha entregue e' a INICIAL COMPARTILHADA (`MOTOR_SENHA_INICIAL`), com sal proprio por
    linha, e a pessoa nasce com `deve_trocar_senha_usuario = TRUE`. Se a env nao estiver
    configurada, a criacao e' RECUSADA antes de abrir transacao -- criar alguem com uma senha que
    ninguem sabe qual e' seria pior que nao criar.

    O que esta funcao NAO faz, e a tela precisa dizer: cadastrar a pessoa no
    `authelia/users_database.yml`. Enquanto o Authelia autenticar, uma linha em `usuarios` sem a
    entrada de la' nao deixa ninguem entrar.
    """
    from . import senhas

    login = login.strip()
    nome = nome.strip()
    email = email.strip()
    if not login or not nome or not email:
        raise ValueError("Login, nome e e-mail são obrigatórios.")
    if "@" not in email:
        raise ValueError("E-mail inválido.")

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

        # `metadados` leva SO' o perfil. Nunca login, nome ou e-mail: e' PII, e a §4 do contrato
        # vale aqui como em todo lugar -- o `entidade_id` basta para quem le resolver em `usuarios`.
        _registrar(
            con,
            autor=autor,
            tipo=EVENTO_CRIADO,
            id_alvo=id_novo,
            metadados={"perfil": perfil},
        )

    return {
        "id_usuario": id_novo,
        "login": login,
        "perfil": perfil,
        # A tela usa isto para mostrar o recado do Authelia, que e' o passo que falta.
        "falta_cadastrar_no_authelia": True,
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
    016 ficava sendo uma coluna que ninguem le'.

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
