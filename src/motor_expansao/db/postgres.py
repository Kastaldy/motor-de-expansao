"""Pool, transacoes e diagnostico do PostgreSQL. Interface publica no `__init__` do pacote.

Por que psycopg3 SINCRONO e sem ORM
-----------------------------------
O backend do piloto e' sincrono (as rotas sao `def`, nao `async def`), entao um pool
sincrono encaixa sem reescrever rota nenhuma; o caminho async arrastaria uma refatoracao
que nada neste trabalho exige. E sem ORM porque o esquema do `banco-de-reservas` e' SQL
escrito a mao, com triggers `SECURITY DEFINER`, indices parciais e checagem condicional de
JSONB -- coisas que um ORM nao expressa e que ja' foram validadas em cluster real.

Por que o driver e' importado com tolerancia
--------------------------------------------
O motor tem de subir sem banco. "Sem banco" inclui "sem o extra `db` instalado": quem
roda os pipelines do M1 nao precisa do psycopg. Um `import` no topo sem protecao faria o
`app.py` inteiro falhar no boot por falta de uma dependencia que aquele caminho nao usa.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from typing import Any

_LOG = logging.getLogger("motor.db")

#: Env que LIGA o banco. Ausente ou vazia = banco nao configurado, e nenhuma conexao
#: e' tentada. Prefixo `MOTOR_` para acompanhar `MOTOR_DATA_DIR`/`MOTOR_CADASTRO_DIR`
#: (e para nao colidir com o `DATABASE_URL` morto do `config.py`, que a limpeza remove).
ENV_URL = "MOTOR_DATABASE_URL"

#: Tetos do pool. Pequenos de proposito: o piloto roda num unico worker de uvicorn e a
#: VPS ja' divide RAM entre `web` (8 GB) e `api` (6 GB).
POOL_MIN = 1
POOL_MAX = 4

#: Segundos para o pool entregar uma conexao antes de desistir. Curto: uma rota que
#: espera 30s por conexao ja' perdeu o usuario -- melhor falhar e deixar o erro aparecer.
TIMEOUT_POOL_S = 5.0

#: Segundos para o `saude()` desistir. Ele responde ao diagnostico de admin, que o
#: operador abre justamente quando desconfia do banco: nao pode pendurar a requisicao.
TIMEOUT_SAUDE_S = 2.0

#: Tabela de controle das migrations, criada pela `000`. O `saude()` apenas TENTA le-la
#: e degrada em silencio quando ela nao existe -- que e' o estado de um banco levantado a
#: mao pelo roteiro 001->010 do `banco-de-reservas`, antes de a 000 rodar.
#:
#: `migracoes_aplicadas`, e nao `migracoes`: o diretorio dos arquivos `.sql` ja' se chama
#: `migracoes/`, e o nome tambem e' mais fiel -- a tabela guarda quais foram APLICADAS,
#: quando e com que hash, nao as migrations em si.
TABELA_MIGRACOES = "migracoes_aplicadas"

#: Tabela cuja auditoria o D19 protege. O `saude()` pergunta o privilegio EFETIVO sobre
#: ela para responder "o provisionamento do D20 esta de pe?" -- ver `_provisionamento`.
TABELA_HISTORICO = "perfil_permissoes_historico"
TRIGGER_AUDITORIA = "trg_perfil_permissoes_auditoria"

#: O `id_usuario` vai para o banco como TEXTO e e' validado la' pelo mesmo padrao
#: (`^[0-9]{1,18}$`, D19) antes do cast. Repetimos a validacao aqui para falhar cedo,
#: com erro legivel, em vez de gravar lixo que a trigger vai descartar em silencio.
_PADRAO_ID_USUARIO = re.compile(r"^[0-9]{1,18}$")

# --- SQL, em constantes nomeadas -------------------------------------------------------
# Todo SQL do motor fica LOCALIZAVEL, nunca interpolado no meio da logica: quem executa
# contra o banco real e' o Vinicius, e ele precisa ter o que revisar num lugar so'. E' a
# mesma razao pela qual o gate de sintaxe offline (pglast) consegue alcancar tudo.

SQL_PING = "SELECT 1"
SQL_VERSAO_POSTGIS = "SELECT postgis_version()"
SQL_VERSAO_SERVIDOR = "SHOW server_version"
SQL_SOMENTE_LEITURA = "SET TRANSACTION READ ONLY"
# `set_config(..., true)` e NAO `SET LOCAL app.id_usuario = %s`: o `SET` nao aceita
# parametro bindado, o que forcaria interpolar o valor na string -- e uma variavel de
# sessao interpolada e' injecao esperando acontecer. O terceiro argumento `true` e' o que
# torna a variavel LOCAL a transacao, morrendo no commit junto com ela.
SQL_DEFINIR_AUTOR = "SELECT set_config('app.id_usuario', %s, true)"
# Mesma forma para o timeout: era o UNICO SQL montado por f-string neste modulo, o que
# contrariava a politica declarada logo acima. Nao era injetavel (o valor passava por
# `int()`), mas "nao e' exploravel hoje" e' garantia mais fraca que "nao ha caminho".
SQL_DEFINIR_TIMEOUT = "SELECT set_config('statement_timeout', %s, true)"
SQL_VERSAO_MIGRACAO = (
    f"SELECT versao_migracao FROM {TABELA_MIGRACOES} ORDER BY versao_migracao DESC LIMIT 1"
)
# Diagnostico do provisionamento (D20). Sem estas tres respostas, um `MOTOR_DATABASE_URL`
# apontando para o DONO do schema -- o caminho de menor resistencia num deploy apressado --
# derruba a auditoria inteira sem sinal nenhum: dono desliga a propria trigger.
SQL_USUARIO_ATUAL = "SELECT current_user"
SQL_PODE_ESCREVER_HISTORICO = "SELECT has_table_privilege(%s, 'INSERT')"
SQL_ESTADO_TRIGGER = "SELECT tgenabled FROM pg_trigger WHERE tgname = %s"

# --- Estado do modulo ------------------------------------------------------------------

_TRAVA = threading.Lock()
_pool: Any = None
_pool_da_url: str | None = None


class BancoNaoConfigurado(RuntimeError):
    """Nao ha `MOTOR_DATABASE_URL` (ou falta o driver): o motor roda sem banco."""


class BancoIndisponivel(RuntimeError):
    """Configurado, mas a conexao falhou. Distinto de nao-configurado de proposito:
    um e' escolha de operacao, o outro e' incidente -- e o diagnostico os separa."""


class AutocommitProibido(RuntimeError):
    """Escrita numa conexao em autocommit: o carimbo de autor evaporaria em silencio."""


def _driver() -> Any:
    """`ConnectionPool` do psycopg_pool, ou `None` se o extra `db` nao esta instalado."""
    try:
        from psycopg_pool import ConnectionPool
    except ImportError:
        return None
    return ConnectionPool


def url_configurada() -> str | None:
    """A URL de conexao, ou `None`. Valor vazio/em branco conta como ausente."""
    bruto = os.environ.get(ENV_URL, "")
    return bruto.strip() or None


def _sem_segredo(texto: str) -> str:
    """Remove a URL de conexao e a senha dela de uma mensagem de erro.

    O libpq nao costuma citar a senha, mas uma URL malformada faz o proprio parse
    levantar com um fragmento da string de conexao dentro -- e esse texto ia inteiro
    para o JSON do diagnostico. Mascarar aqui e' mais barato que auditar cada driver.
    """
    url = url_configurada()
    if not url:
        return texto
    texto = texto.replace(url, "<" + ENV_URL + ">")
    # A senha e' o trecho entre o primeiro dois-pontos depois do esquema e o arroba; ela
    # some isolada tambem, para o caso de a mensagem citar so' um pedaco da URL.
    achado = re.search(r"://[^:/@\s]+:([^@\s]+)@", url)
    if achado and achado.group(1):
        texto = texto.replace(achado.group(1), "<senha>")
    return texto


def _falha(erro: Exception) -> BancoIndisponivel:
    """Normaliza falha de driver/rede, preservando a CLASSE e escondendo segredo."""
    return BancoIndisponivel(f"{type(erro).__name__}: {_sem_segredo(str(erro))}")


def motivo_indisponivel() -> str | None:
    """`None` = da' para tentar conectar. String = por que nao da', em uma linha."""
    if url_configurada() is None:
        return f"{ENV_URL} nao definida"
    if _driver() is None:
        return (
            "driver psycopg nao instalado -- "
            'python -m pip install "psycopg[binary,pool]>=3.2,<4" -c constraints.txt'
        )
    return None


def configurado() -> bool:
    """Se ha URL E driver. NAO diz que o banco responde -- para isso, `saude()`."""
    return motivo_indisponivel() is None


def _obter_pool() -> Any:
    """Pool aberto, criado sob demanda. Levanta `BancoNaoConfigurado` se nao da'.

    `open=False` + `open(wait=False)`: sem isso o construtor tentaria conectar e
    BLOQUEARIA o boot quando o banco estivesse fora -- justo o que este modulo existe
    para evitar. Com `wait=False` o pool sobe vazio e reconecta sozinho em segundo
    plano, entao o motor se recupera quando o banco volta, sem restart.
    """
    global _pool, _pool_da_url

    motivo = motivo_indisponivel()
    if motivo is not None:
        raise BancoNaoConfigurado(motivo)

    url = url_configurada()
    with _TRAVA:
        # URL trocada (teste, ou reconfiguracao) invalida o pool antigo: sem esta
        # checagem, mudar a env em runtime deixaria conexoes apontando para o banco velho.
        if _pool is not None and _pool_da_url == url:
            return _pool
        if _pool is not None:
            _fechar_sem_trava()

        classe = _driver()
        _pool = classe(
            conninfo=url,
            min_size=POOL_MIN,
            max_size=POOL_MAX,
            timeout=TIMEOUT_POOL_S,
            open=False,
            name="motor-db",
        )
        _pool_da_url = url
        _pool.open(wait=False)
        _LOG.info("pool do banco criado (min=%d max=%d)", POOL_MIN, POOL_MAX)
        return _pool


def _pool_ou_falha() -> Any:
    """`_obter_pool()` com a falha de CRIACAO ja' normalizada.

    Falha ao construir o pool (URL malformada, host inalcancavel) e' banco indisponivel,
    e precisa chegar ao chamador com a classe da excecao original preservada e sem
    segredo. Fica numa funcao propria para que `conexao()`/`transacao()` possam
    chama-la ANTES do `try` que envolve o `yield` -- que e' o que impede excecao do
    chamador de ser convertida.
    """
    try:
        return _obter_pool()
    except BancoNaoConfigurado:
        raise
    except Exception as erro:  # noqa: BLE001 - falha de driver/rede ao abrir o pool
        raise _falha(erro) from erro


def _fechar_sem_trava() -> None:
    global _pool, _pool_da_url
    if _pool is not None:
        try:
            _pool.close()
        except Exception:  # noqa: BLE001 - fechar pool nunca deve derrubar quem chamou
            _LOG.warning("falha ao fechar o pool do banco", exc_info=True)
    _pool = None
    _pool_da_url = None


def fechar_pool() -> None:
    """Encerra o pool. Para o shutdown do app e para isolar testes entre si."""
    with _TRAVA:
        _fechar_sem_trava()


@contextmanager
def conexao() -> Iterator[Any]:
    """Conexao de LEITURA. A transacao e' aberta `READ ONLY`.

    Nao e' documentacao nem convencao: o servidor recusa escrita em tabela permanente e
    DDL dentro dela, e a recusa vale inclusive para funcao `SECURITY DEFINER` chamada de
    dentro -- o modo e' checado no executor, nao pelo papel efetivo.

    LIMITE, para nao prometer mais do que entrega: a garantia e' da TRANSACAO, nao da
    conexao. Um `con.commit()` no meio do bloco encerra esta transacao, e a proxima
    nasce read-write. O que fecha isso de vez e' um papel de leitura dedicado com
    `default_transaction_read_only = on` (D20), nao este comando. Tambem passam, por
    desenho do Postgres: escrita em tabela temporaria ja' existente, `nextval()` e
    `LISTEN`/`NOTIFY`.

    Isso importa porque o guardrail que hoje prova o read-only do piloto
    (`test_leituras_nao_mutam_artefatos`, por snapshot do filesystem) e' CEGO a um
    INSERT -- e ficaria cego sem substituto ate' os papeis do D20 existirem.
    """
    pool = _pool_ou_falha()
    # O `yield` fica FORA de qualquer `except Exception`. Com ele dentro, o
    # `contextlib` relanca no ponto do yield toda excecao do corpo do `with` do
    # chamador -- e um `KeyError` da aplicacao virava `BancoIndisponivel`, com o texto
    # de uma excecao interna arbitraria viajando dentro de uma classe cuja semantica
    # convida a renderizar como `detail` de um 503.
    with ExitStack() as pilha:
        try:
            con = pilha.enter_context(pool.connection())
            con.execute(SQL_SOMENTE_LEITURA)
        except Exception as erro:  # noqa: BLE001 - so' o SETUP e' traduzido
            raise _falha(erro) from erro
        yield con


@contextmanager
def transacao(*, id_usuario: int | str | None) -> Iterator[Any]:
    """Conexao de ESCRITA, com o autor carimbado na transacao.

    `id_usuario` e' obrigatorio como PARAMETRO e pode ser `None` como VALOR: acao de
    sistema existe e o D19 a preve ("sem ela, a acao e' registrada com autoria nula").
    O que nao pode existir e' escrita cujo autor ficou nulo por esquecimento -- por isso
    o parametro e' nomeado e sem default.

    CUIDADO ao usar: um `con.commit()` no meio do bloco encerra a transacao e leva a
    variavel junto (ela e' local a transacao, de proposito). As escritas seguintes do
    MESMO bloco sairiam auditadas com `registrado_por` nulo, sem erro nenhum. Uma
    unidade de trabalho por bloco.
    """
    autor = _normalizar_autor(id_usuario)
    pool = _pool_ou_falha()
    with ExitStack() as pilha:
        try:
            con = pilha.enter_context(pool.connection())
            # Autocommit faria o `set_config(..., true)` rodar na propria transacao
            # implicita e evaporar antes do INSERT: nenhuma excecao, e toda linha de
            # auditoria a partir dali com autor nulo. Falha MUDA, e por isso barrada.
            if getattr(con, "autocommit", False):
                raise AutocommitProibido(
                    "conexao em autocommit: o carimbo de app.id_usuario nao sobreviveria "
                    "ate' a escrita, e a auditoria sairia sem autor"
                )
            # Primeiro comando da transacao: se a escrita seguinte falhar, o autor cai
            # junto no rollback -- variavel local a transacao nao sobrevive ao aborto.
            con.execute(SQL_DEFINIR_AUTOR, (autor,))
        except AutocommitProibido:
            raise
        except Exception as erro:  # noqa: BLE001 - so' o SETUP e' traduzido
            raise _falha(erro) from erro
        yield con


def _normalizar_autor(id_usuario: int | str | None) -> str | None:
    """`None` (sistema) ou digitos. Qualquer outra coisa e' erro de programacao aqui."""
    if id_usuario is None:
        return None
    texto = str(id_usuario).strip()
    if not _PADRAO_ID_USUARIO.match(texto):
        raise ValueError(
            f"id_usuario invalido para app.id_usuario: {id_usuario!r} "
            "(esperado inteiro positivo de ate 18 digitos, ou None para acao de sistema)"
        )
    return texto


def saude(timeout_s: float = TIMEOUT_SAUDE_S) -> dict[str, Any]:
    """Diagnostico para a rota de ADMIN. NUNCA levanta -- o health e' sinal, nao rota.

    Separa tres estados que dao no mesmo para o usuario e sao muito diferentes para
    quem opera: nao configurado (escolha), configurado e fora (incidente), configurado
    e no ar (normal). `migracao` fica `None` enquanto a tabela de controle nao existir,
    que e' o estado de um banco levantado a mao pelo roteiro 001->010.

    NAO vai para o `/api/health`: aquela rota e' livre e foi emudecida de proposito
    (pentest Onda B #8). E o healthcheck do container tambem nao olha o banco -- o
    piloto serve sem ele, e amarrar os dois faria o Docker reiniciar o `web` a cada
    piscada do Postgres, derrubando o que ainda funcionava.
    """
    estado: dict[str, Any] = {
        "configurado": False,
        "conectado": False,
        "postgis": None,
        "servidor": None,
        "migracao": None,
        "provisionamento": None,
        "erro": None,
    }

    motivo = motivo_indisponivel()
    if motivo is not None:
        estado["erro"] = motivo
        return estado

    estado["configurado"] = True
    try:
        with conexao() as con:
            con.execute(SQL_DEFINIR_TIMEOUT, (f"{int(timeout_s * 1000)}ms",))
            con.execute(SQL_PING)
            estado["conectado"] = True
            estado["servidor"] = _primeiro_valor(con, SQL_VERSAO_SERVIDOR)
            # PostGIS pode nao estar habilitado (migration 001 nao rodou): e' informacao,
            # nao falha -- o banco responde, e e' isso que `conectado` afirma.
            estado["postgis"] = _primeiro_valor(con, SQL_VERSAO_POSTGIS, tolerar_erro=True)
            estado["migracao"] = _primeiro_valor(con, SQL_VERSAO_MIGRACAO, tolerar_erro=True)
            estado["provisionamento"] = _provisionamento(con)
    except Exception as erro:  # noqa: BLE001 - health nunca derruba a requisicao
        estado["erro"] = _sem_segredo(str(erro))
    return estado


def _provisionamento(con: Any) -> dict[str, Any]:
    """O D20 esta de pe? Responde com FATO, nao com suposicao.

    A 009 afirma que o `SECURITY DEFINER` impede a aplicacao de forjar linha no
    historico -- mas isso so' vale se quem conecta NAO for o dono do schema. Sendo dono,
    a aplicacao teria `INSERT` direto no historico e poderia `ALTER TABLE ... DISABLE
    TRIGGER` na propria auditoria. Nada no motor detectava esse estado, e ele e' o
    caminho de menor resistencia num deploy apressado.

    `tgenabled`: 'O' = habilitada no modo normal (o padrao) e 'A' = ENABLE ALWAYS, que e'
    o unico pedaco de DDL do D20 e o que resiste a `session_replication_role = replica`
    -- que deixou de exigir superusuario no PostgreSQL 15.
    """
    dados: dict[str, Any] = {
        "usuario": _primeiro_valor(con, SQL_USUARIO_ATUAL, tolerar_erro=True),
        "pode_escrever_no_historico": None,
        "trigger_auditoria": None,
    }
    dados["pode_escrever_no_historico"] = _primeiro_valor(
        con, SQL_PODE_ESCREVER_HISTORICO, (TABELA_HISTORICO,), tolerar_erro=True
    )
    dados["trigger_auditoria"] = _primeiro_valor(
        con, SQL_ESTADO_TRIGGER, (TRIGGER_AUDITORIA,), tolerar_erro=True
    )
    return dados


def _primeiro_valor(
    con: Any,
    sql: str,
    parametros: tuple[Any, ...] | None = None,
    *,
    tolerar_erro: bool = False,
) -> Any:
    """Primeira coluna da primeira linha, ou `None`.

    Com `tolerar_erro`, a consulta roda em SAVEPOINT: sem ele, uma tabela ausente
    aborta a transacao inteira no PostgreSQL e as consultas SEGUINTES falhariam com
    "current transaction is aborted" -- o health perderia o `migracao` E o `postgis`
    por causa de um so' deles faltar.
    """
    if not tolerar_erro:
        linha = con.execute(sql, parametros).fetchone() if parametros else con.execute(sql).fetchone()
        return linha[0] if linha else None
    try:
        with con.transaction():
            cursor = con.execute(sql, parametros) if parametros else con.execute(sql)
            linha = cursor.fetchone()
            return linha[0] if linha else None
    except Exception:  # noqa: BLE001 - ausencia de extensao/tabela e' informacao
        return None
