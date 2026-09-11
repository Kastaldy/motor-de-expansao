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

from dataclasses import dataclass
from typing import Any

from .postgres import conexao, transacao

#: Vocabulario de `tipo` do `docs/eventos_contrato.md` §2.7. Fora desta lista e' defeito.
EVENTO_PERFIL_ALTERADO = "usuario.perfil_alterado"
EVENTO_DESATIVADO = "usuario.desativado"
EVENTO_REATIVADO = "usuario.reativado"
EVENTO_CRIADO = "usuario.criado"
EVENTO_SENHA_DEFINIDA = "usuario.senha_definida"

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

# Os tres campos andam juntos e por isso vao no MESMO UPDATE: gravar o hash sem carimbar a data
# deixaria a coluna da 016 mentindo, e limpar `deve_trocar` sem gravar o hash liberaria a pessoa
# de uma troca que nao aconteceu.
SQL_DEFINIR_SENHA = """
UPDATE usuarios
SET senha_hash = %s,
    senha_definida_em_usuario = now(),
    deve_trocar_senha_usuario = FALSE
WHERE id_usuario = %s
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
