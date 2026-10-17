"""O RBAC pelo banco FORA do event loop, com teto de tempo e fail-closed no corpo da consulta.

O defeito (17/10/2026)
----------------------
Com `MOTOR_DATABASE_URL` setada, o middleware `async def _controle_de_acesso_por_aba` chamava
`acesso.motivo_bloqueio_por_banco` -> `rbac.identidade()` DIRETO, e o `rbac` consulta o Postgres
com psycopg SINCRONO. O piloto roda num unico worker de uvicorn, entao cada requisicao controlada
prendia o loop inteiro enquanto o banco nao respondesse: ate' 5 s por requisicao com o banco fora
(espera do pool), sem limite com ele travado -- e o `/api/health` e os estaticos congelavam junto.

Tres outras metades do mesmo problema, cobertas aqui:

* erro no CORPO da consulta (`statement_timeout`, `lock_timeout`, conexao que cai) nao virava
  `BancoIndisponivel`, e o gate so' pega essa classe: 500 em toda rota controlada em vez do
  fail-closed desenhado (403 so' nas capacidades sensiveis);
* o pool nao tinha teto de tempo por comando nem de espera por lock;
* conexao morta no pool (restart do Postgres) virava "banco indisponivel" em vez de ser trocada.

Nenhum teste aqui toca banco: o ensaio contra Postgres real esta' descrito no PR.
"""

from __future__ import annotations

import ast
import asyncio
import errno
import inspect
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import anyio
import pytest

psycopg = pytest.importorskip("psycopg")

_SERVER = Path(__file__).resolve().parents[2] / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import acesso  # noqa: E402
import app as pilot  # noqa: E402

from motor_expansao import db  # noqa: E402
from motor_expansao.db import postgres as mod  # noqa: E402
from motor_expansao.db import rbac  # noqa: E402
from motor_expansao.db import sessoes as db_sessoes  # noqa: E402

#: Quanto a identidade "lenta" demora. Grande o bastante para medir, pequeno para a suite.
LENTO_S = 0.6

#: Teto para o que NAO pode esperar pelo banco. Folgado contra CI lento, e ainda assim uma
#: fracao do `LENTO_S`: se o loop estivesse preso, a medida seria >= LENTO_S.
RAPIDO_S = 0.25


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.delenv("MOTOR_CADASTRO_DIR", raising=False)
    monkeypatch.delenv("MOTOR_ACESSO_FAIL_CLOSED", raising=False)
    monkeypatch.delenv(db_sessoes.ENV_AUTENTICACAO_PROPRIA, raising=False)
    db.fechar_pool()
    yield
    db.fechar_pool()


# --------------------------------------------------------------------------------------
# Dubles
# --------------------------------------------------------------------------------------


class _Url:
    def __init__(self, caminho: str) -> None:
        self.path = caminho


class _Requisicao:
    """O que o `_controle_de_acesso_por_aba` le: headers, `url.path` e `method`."""

    def __init__(self, caminho: str, metodo: str = "GET", usuario: str = "ana") -> None:
        self.url = _Url(caminho)
        self.method = metodo
        self.headers = {"Remote-User": usuario}


class _Resposta:
    status_code = 200


async def _proximo(_req: Any) -> _Resposta:
    return _Resposta()


def _identidade_lenta(
    monkeypatch: pytest.MonkeyPatch, permissoes: set[str], chamadas: list[str]
) -> None:
    """`rbac.identidade` que BLOQUEIA a thread, como o psycopg sincrono faz."""

    def lenta(remote_user: object) -> rbac.Identidade:
        chamadas.append(threading.current_thread().name)
        time.sleep(LENTO_S)
        return rbac.Identidade(
            id_usuario=1, login=str(remote_user), perfil="t", permissoes=frozenset(permissoes)
        )

    monkeypatch.setattr(rbac, "identidade", lenta)
    monkeypatch.setattr(acesso, "banco_no_comando", lambda: True)


async def _latencia_do_loop() -> float:
    """Quanto o loop demora para atender um `sleep(0)` -- o proxy do `/api/health`."""
    await asyncio.sleep(0.05)  # deixa as requisicoes lentas entrarem primeiro
    inicio = time.perf_counter()
    await asyncio.sleep(0)
    return time.perf_counter() - inicio


# --------------------------------------------------------------------------------------
# 1. O gate do RBAC nao prende o event loop
# --------------------------------------------------------------------------------------


def test_identidade_lenta_nao_prende_o_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """Duas requisicoes controladas com o banco lento rodam EM PARALELO, e o loop segue livre.

    Antes da correcao: o loop ficava preso LENTO_S a cada uma, em serie -- a latencia medida
    seria >= LENTO_S e o total >= 2*LENTO_S.
    """
    chamadas: list[str] = []
    _identidade_lenta(monkeypatch, {"territorio.explorar"}, chamadas)

    async def cenario() -> tuple[list[Any], float, float]:
        inicio = time.perf_counter()
        r1 = asyncio.create_task(
            pilot._controle_de_acesso_por_aba(_Requisicao("/api/uf/SP"), _proximo)
        )
        r2 = asyncio.create_task(
            pilot._controle_de_acesso_por_aba(_Requisicao("/api/uf/RJ"), _proximo)
        )
        latencia = await _latencia_do_loop()
        respostas = await asyncio.gather(r1, r2)
        return respostas, latencia, time.perf_counter() - inicio

    respostas, latencia, total = asyncio.run(cenario())

    assert [r.status_code for r in respostas] == [200, 200]
    assert latencia < RAPIDO_S, f"loop preso {latencia:.3f}s pelo RBAC"
    assert total < 2 * LENTO_S, f"as duas rodaram em serie ({total:.3f}s)"
    assert len(chamadas) == 2
    assert all(nome != threading.main_thread().name for nome in chamadas)


def test_rota_livre_nao_consulta_o_banco_nem_espera_por_ele(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`/api/health` passa enquanto uma requisicao controlada espera o banco -- e sem consulta."""
    chamadas: list[str] = []
    _identidade_lenta(monkeypatch, {"territorio.explorar"}, chamadas)

    async def cenario() -> tuple[Any, float]:
        lenta = asyncio.create_task(
            pilot._controle_de_acesso_por_aba(_Requisicao("/api/uf/SP"), _proximo)
        )
        await asyncio.sleep(0.05)
        inicio = time.perf_counter()
        health = await pilot._controle_de_acesso_por_aba(_Requisicao("/api/health"), _proximo)
        decorrido = time.perf_counter() - inicio
        await lenta
        return health, decorrido

    health, decorrido = asyncio.run(cenario())
    assert health.status_code == 200
    assert decorrido < RAPIDO_S
    assert len(chamadas) == 1, "a rota sem capacidade nao pode consultar o RBAC"


def test_sem_banco_o_caminho_do_json_segue_no_loop_e_identico(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem `MOTOR_DATABASE_URL` nada muda: o mapa JSON e' lido no proprio loop, sem threadpool."""
    threads: list[str] = []

    def motivo(path: str, usuario: object) -> str | None:
        threads.append(threading.current_thread().name)
        return "negado" if path.startswith("/api/rede/") else None

    def nunca(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("sem banco, o RBAC nao pode ser consultado")

    monkeypatch.setattr(acesso, "banco_no_comando", lambda: False)
    monkeypatch.setattr(acesso, "motivo_bloqueio", motivo)
    monkeypatch.setattr(acesso, "motivo_bloqueio_por_banco", nunca)

    ok = asyncio.run(pilot._controle_de_acesso_por_aba(_Requisicao("/api/uf/SP"), _proximo))
    barrada = asyncio.run(
        pilot._controle_de_acesso_por_aba(_Requisicao("/api/rede/carteira"), _proximo)
    )
    assert ok.status_code == 200
    assert barrada.status_code == 403
    assert threads == [threading.main_thread().name] * 2


# --------------------------------------------------------------------------------------
# 2. Fail-closed tambem para erro no CORPO da consulta
# --------------------------------------------------------------------------------------


class _ConexaoQueFalha:
    """Conexao que aceita o `SET TRANSACTION READ ONLY` e falha na consulta do RBAC."""

    autocommit = False

    def __init__(self, erro: Exception) -> None:
        self._erro = erro

    def execute(self, sql: str, params: Any = None) -> Any:
        if sql == mod.SQL_SOMENTE_LEITURA or sql.startswith("SELECT set_config"):
            return None
        raise self._erro


class _PoolFalso:
    def __init__(self, con: Any) -> None:
        self._con = con
        self.kwargs: dict[str, Any] = {}

    @contextmanager
    def connection(self):  # type: ignore[no-untyped-def]
        yield self._con

    def open(self, wait: bool = False) -> None:
        pass

    def close(self) -> None:
        pass


def _instalar(monkeypatch: pytest.MonkeyPatch, con: Any) -> _PoolFalso:
    pool = _PoolFalso(con)

    def fabrica(**kwargs: Any) -> _PoolFalso:
        pool.kwargs = kwargs
        return pool

    monkeypatch.setattr(mod, "_driver", lambda: fabrica)
    monkeypatch.setenv(mod.ENV_URL, "postgresql://fake/motor")
    return pool


ERROS_OPERACIONAIS = [
    pytest.param(
        psycopg.errors.QueryCanceled("canceling statement due to statement timeout"),
        id="statement_timeout",
    ),
    pytest.param(
        psycopg.errors.LockNotAvailable("canceling statement due to lock timeout"),
        id="lock_timeout",
    ),
    pytest.param(
        psycopg.OperationalError("server closed the connection unexpectedly"), id="conexao_caiu"
    ),
    pytest.param(
        psycopg.errors.AdminShutdown("terminating connection due to administrator"),
        id="pg_terminate_backend",
    ),
]


@pytest.mark.parametrize("erro", ERROS_OPERACIONAIS)
def test_falha_operacional_no_corpo_vira_banco_indisponivel(
    monkeypatch: pytest.MonkeyPatch, erro: Exception
) -> None:
    _instalar(monkeypatch, _ConexaoQueFalha(erro))
    with pytest.raises(db.BancoIndisponivel) as leitura:
        with db.conexao() as con:
            con.execute("SELECT 1")
    assert type(erro).__name__ in str(leitura.value)

    with pytest.raises(db.BancoIndisponivel):
        with db.transacao(id_usuario=1) as con:
            con.execute("INSERT INTO eventos DEFAULT VALUES")


@pytest.mark.parametrize(
    "erro",
    [
        pytest.param(
            psycopg.errors.UndefinedTable('relation "usuarios" does not exist'), id="tabela_ausente"
        ),
        pytest.param(psycopg.errors.SyntaxError("syntax error at or near"), id="sql_errado"),
        pytest.param(psycopg.errors.UniqueViolation("duplicate key"), id="integridade"),
    ],
)
def test_erro_de_programacao_e_integridade_continuam_visiveis(
    monkeypatch: pytest.MonkeyPatch, erro: Exception
) -> None:
    """Traduzir estes faria um defeito permanente se passar por incidente passageiro -- e, no
    gate, liberaria as rotas nao sensiveis sem checar permissao. Seguem com a classe deles."""
    _instalar(monkeypatch, _ConexaoQueFalha(erro))
    with pytest.raises(type(erro)):
        with db.conexao() as con:
            con.execute("SELECT 1")
    with pytest.raises(type(erro)):
        with db.transacao(id_usuario=1) as con:
            con.execute("SELECT 1")


#: Falhas que PROVAM que o servidor saiu do alcance (conexao perdida, servidor saindo) --
#: e as que nao provam: o servidor RESPONDEU, com erro, numa conexao viva.
ERROS_COM_PROVA = [p for p in ERROS_OPERACIONAIS if p.id in {"conexao_caiu", "pg_terminate_backend"}]
ERROS_SEM_PROVA = [p for p in ERROS_OPERACIONAIS if p.id in {"statement_timeout", "lock_timeout"}]


@pytest.mark.parametrize("erro", ERROS_COM_PROVA)
def test_gate_com_erro_no_corpo_nega_so_as_sensiveis_em_producao(
    monkeypatch: pytest.MonkeyPatch, erro: Exception
) -> None:
    """Ponta a ponta pelo `rbac` REAL: o 403 so' nas sensiveis, o resto passa -- e nada de 500."""
    _instalar(monkeypatch, _ConexaoQueFalha(erro))
    monkeypatch.setenv("MOTOR_CADASTRO_DIR", "/app/cadastro")  # sinal de producao

    assert acesso.motivo_bloqueio_por_banco("/api/uf/SP", "GET", "ana") is None
    assert acesso.motivo_bloqueio_por_banco("/api/pin-concorrente/1", "GET", "ana") is None
    assert acesso.motivo_bloqueio_por_banco("/api/rede/carteira", "GET", "ana") is not None
    assert acesso.motivo_bloqueio_por_banco("/api/oportunidades/1/dossie", "GET", "ana") is not None
    assert acesso.abas_do_usuario_por_banco("ana") == acesso.ABAS_VALIDAS - acesso.ABAS_SENSIVEIS


def test_gate_com_erro_no_corpo_pelo_middleware_devolve_403_e_200(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O mesmo, medido no status HTTP que o middleware devolve (antes: excecao -> 500)."""
    _instalar(
        monkeypatch,
        _ConexaoQueFalha(psycopg.OperationalError("server closed the connection unexpectedly")),
    )
    monkeypatch.setenv("MOTOR_CADASTRO_DIR", "/app/cadastro")

    def rodar(caminho: str) -> int:
        return asyncio.run(
            pilot._controle_de_acesso_por_aba(_Requisicao(caminho), _proximo)
        ).status_code

    assert rodar("/api/uf/SP") == 200
    assert rodar("/api/rede/carteira") == 403


@pytest.mark.parametrize("erro", ERROS_SEM_PROVA)
def test_gate_com_lock_ou_statement_timeout_responde_503_e_nao_degrada(
    monkeypatch: pytest.MonkeyPatch, erro: Exception
) -> None:
    """3a revisao de 17/10/2026: `lock_timeout`/`statement_timeout` numa conexao VIVA sao o
    servidor RESPONDENDO. Tratados como banco fora, a degradacao liberava as rotas nao
    sensiveis a quem nao tem a capacidade. Sem prova de queda: 503 em toda rota controlada,
    e a evidencia de queda continua limpa."""
    _instalar(monkeypatch, _ConexaoQueFalha(erro))
    monkeypatch.setenv("MOTOR_CADASTRO_DIR", "/app/cadastro")

    def rodar(caminho: str) -> int:
        return asyncio.run(
            pilot._controle_de_acesso_por_aba(_Requisicao(caminho), _proximo)
        ).status_code

    assert rodar("/api/uf/SP") == 503
    assert rodar("/api/pin-concorrente/1") == 503
    assert rodar("/api/rede/carteira") == 503
    assert not acesso.banco_em_falha()


def test_gate_com_erro_de_programacao_nao_vira_fail_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tabela ausente (schema fora de sincronia) NAO e' engolida como "banco fora"."""
    _instalar(monkeypatch, _ConexaoQueFalha(psycopg.errors.UndefinedTable("usuarios")))
    monkeypatch.setenv("MOTOR_CADASTRO_DIR", "/app/cadastro")
    with pytest.raises(psycopg.errors.UndefinedTable):
        acesso.motivo_bloqueio_por_banco("/api/uf/SP", "GET", "ana")


# --------------------------------------------------------------------------------------
# 3. Tetos de tempo e troca de conexao morta no pool da aplicacao
# --------------------------------------------------------------------------------------


def test_pool_leva_os_tetos_de_tempo_em_cada_conexao(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = _instalar(monkeypatch, _ConexaoQueFalha(RuntimeError("nao usado")))
    mod._obter_pool()

    parametros = pool.kwargs["kwargs"]
    assert parametros["connect_timeout"] == mod.TIMEOUT_CONEXAO_S
    assert f"-c statement_timeout={mod.STATEMENT_TIMEOUT_MS}" in parametros["options"]
    assert f"-c lock_timeout={mod.LOCK_TIMEOUT_MS}" in parametros["options"]
    assert mod.LOCK_TIMEOUT_MS < mod.STATEMENT_TIMEOUT_MS
    assert mod.STATEMENT_TIMEOUT_MS / 1000 < mod.TIMEOUT_POOL_S


def test_o_que_a_url_declara_vence(monkeypatch: pytest.MonkeyPatch) -> None:
    """`options` da URL vai DEPOIS das nossas (ultimo `-c` ganha); `connect_timeout` dela fica."""
    parametros = mod._parametros_de_conexao(
        "postgresql://app@h/db?connect_timeout=9&options=-c%20statement_timeout%3D30000"
    )
    assert "connect_timeout" not in parametros  # a URL ja' traz; o kwargs nao sobrescreve
    opcoes = parametros["options"]
    assert opcoes.index("statement_timeout=2000") < opcoes.index("statement_timeout=30000")


class _ConexaoRoteirizada:
    """Conexao que pode estar MORTA (como depois de um restart do Postgres) ou viva."""

    autocommit = False

    def __init__(self, morta: bool, erro_vivo: Exception | None = None) -> None:
        self.morta = morta
        self.broken = False
        self._erro_vivo = erro_vivo
        self.executados: list[str] = []

    def execute(self, sql: str, params: Any = None) -> Any:
        if self.morta:
            self.broken = True
            raise psycopg.OperationalError("server closed the connection unexpectedly")
        if self._erro_vivo is not None:
            raise self._erro_vivo
        self.executados.append(sql)
        return None


class _PoolRoteirizado:
    """Entrega as conexoes na ordem dada e registra quantas foram devolvidas."""

    def __init__(self, conexoes: list[Any]) -> None:
        self._fila = list(conexoes)
        self.emprestadas = 0
        self.devolvidas_com_erro = 0

    @contextmanager
    def connection(self):  # type: ignore[no-untyped-def]
        self.emprestadas += 1
        con = self._fila.pop(0)
        if isinstance(con, BaseException):  # o pool nao entregou conexao (`PoolTimeout`)
            raise con
        try:
            yield con
        except BaseException:
            self.devolvidas_com_erro += 1
            raise

    def open(self, wait: bool = False) -> None:
        pass

    def close(self) -> None:
        pass


def _instalar_roteiro(monkeypatch: pytest.MonkeyPatch, conexoes: list[Any]) -> _PoolRoteirizado:
    pool = _PoolRoteirizado(conexoes)
    monkeypatch.setattr(mod, "_driver", lambda: lambda **_kw: pool)
    monkeypatch.setenv(mod.ENV_URL, "postgresql://fake/motor")
    return pool


def test_conexao_morta_e_trocada_na_hora(monkeypatch: pytest.MonkeyPatch) -> None:
    """Depois de um restart do Postgres o pool so' tem conexao morta. Antes: cada uma virava
    um "banco indisponivel" (no gate, sensivel negada a quem tem acesso) ate' o pool esvaziar.
    Agora a requisicao troca de conexao sem espera e recebe a resposta certa."""
    viva = _ConexaoRoteirizada(morta=False)
    pool = _instalar_roteiro(
        monkeypatch, [_ConexaoRoteirizada(morta=True), _ConexaoRoteirizada(morta=True), viva]
    )
    inicio = time.perf_counter()
    with db.conexao() as con:
        assert con is viva
    assert time.perf_counter() - inicio < RAPIDO_S  # sem o backoff do `check` do pool
    assert pool.emprestadas == 3
    assert pool.devolvidas_com_erro == 2  # as mortas voltam ao pool, que as descarta
    assert viva.executados == [mod.SQL_SOMENTE_LEITURA]


def test_escrita_tambem_troca_a_conexao_morta(monkeypatch: pytest.MonkeyPatch) -> None:
    viva = _ConexaoRoteirizada(morta=False)
    _instalar_roteiro(monkeypatch, [_ConexaoRoteirizada(morta=True), viva])
    with db.transacao(id_usuario=7) as con:
        assert con is viva
    assert viva.executados == [mod.SQL_DEFINIR_AUTOR]


def test_falha_em_conexao_VIVA_nao_e_repetida(monkeypatch: pytest.MonkeyPatch) -> None:
    """Timeout ou lock numa conexao viva sao a resposta: repetir dobraria a espera."""
    pool = _instalar_roteiro(
        monkeypatch,
        [
            _ConexaoRoteirizada(morta=False, erro_vivo=psycopg.errors.QueryCanceled("timeout")),
            _ConexaoRoteirizada(morta=False),
        ],
    )
    with pytest.raises(db.BancoIndisponivel, match="QueryCanceled"):
        with db.conexao():
            pass
    assert pool.emprestadas == 1


def test_as_trocas_sao_limitadas_pelo_tamanho_do_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    """Todas mortas: desiste depois de `POOL_MAX + 1` tentativas, sem laco."""
    pool = _instalar_roteiro(
        monkeypatch, [_ConexaoRoteirizada(morta=True) for _ in range(mod.POOL_MAX + 3)]
    )
    with pytest.raises(db.BancoIndisponivel, match="OperationalError"):
        with db.conexao():
            pass
    assert pool.emprestadas == mod.POOL_MAX + 1


def test_o_pool_nao_usa_o_check_com_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """O `check` do psycopg_pool espera 1 s, 2 s, 4 s entre conexoes mortas: medido, a
    primeira requisicao depois de um restart estourava os 5 s do pool. A troca e' nossa."""
    pool = _instalar(monkeypatch, _ConexaoQueFalha(RuntimeError("nao usado")))
    mod._obter_pool()
    assert "check" not in pool.kwargs


def test_os_tetos_do_pool_nao_alcancam_a_cli() -> None:
    """Migration, D20 e backup abrem conexao propria: o teto de 2 s do pool nao pode vazar
    para la' (uma migration longa morreria no meio). A cli nao toca o pool da aplicacao."""
    fonte = (Path(mod.__file__).parent / "cli.py").read_text(encoding="utf-8")
    assert "_obter_pool" not in fonte
    assert "postgres.conexao(" not in fonte
    assert "postgres.transacao(" not in fonte


# --------------------------------------------------------------------------------------
# 4. Relatorio e portao de sessao fora do loop
# --------------------------------------------------------------------------------------


def test_relatorio_grava_o_evento_fora_do_loop_com_banco(monkeypatch: pytest.MonkeyPatch) -> None:
    threads: list[str] = []

    def lento(remote_user: Any, **kw: Any) -> str:
        threads.append(threading.current_thread().name)
        time.sleep(LENTO_S)
        return "R-1"

    monkeypatch.setattr(acesso, "banco_no_comando", lambda: True)
    monkeypatch.setattr(pilot, "_registrar_relatorio_gerado", lento)

    async def cenario() -> tuple[str, float]:
        tarefa = asyncio.create_task(
            pilot._registrar_relatorio_gerado_fora_do_loop(
                "ana", relatorio="pontual", formato="pdf"
            )
        )
        latencia = await _latencia_do_loop()
        return await tarefa, latencia

    report_id, latencia = asyncio.run(cenario())
    assert report_id == "R-1"
    assert latencia < RAPIDO_S
    assert threads and threads[0] != threading.main_thread().name


def test_relatorio_sem_banco_segue_direto_sem_salto_de_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    threads: list[str] = []

    def direto(remote_user: Any, **kw: Any) -> str:
        threads.append(threading.current_thread().name)
        return "R-2"

    monkeypatch.setattr(acesso, "banco_no_comando", lambda: False)
    monkeypatch.setattr(pilot, "_registrar_relatorio_gerado", direto)
    report_id = asyncio.run(
        pilot._registrar_relatorio_gerado_fora_do_loop("ana", relatorio="municipal", formato="pdf")
    )
    assert report_id == "R-2"
    assert threads == [threading.main_thread().name]


def test_portao_de_sessao_valida_fora_do_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    threads: list[str] = []

    def validar(_token: str) -> None:
        threads.append(threading.current_thread().name)
        return None  # sessao invalida -> 401, o que basta para provar onde rodou

    monkeypatch.setenv(db_sessoes.ENV_AUTENTICACAO_PROPRIA, "1")
    monkeypatch.setattr(db_sessoes, "validar", validar)

    class Req:
        def __init__(self) -> None:
            self.url = _Url("/api/uf/SP")
            self.cookies: dict[str, str] = {}
            self.scope: dict[str, Any] = {"headers": []}

    resposta = asyncio.run(pilot._portao_de_sessao(Req(), _proximo))
    assert resposta.status_code == 401
    assert threads and threads[0] != threading.main_thread().name


# --------------------------------------------------------------------------------------
# 5. Revisao adversarial (17/10/2026): limite proprio de threads, disjuntor, COMMIT
# --------------------------------------------------------------------------------------


def test_banco_lento_nao_esgota_as_threads_do_resto_do_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mais requisicoes controladas do que o pool PADRAO tem de threads (40), todas esperando
    o banco: uma chamada ao pool padrao (o que rotas `def` e estaticos usam) segue na hora.

    Antes: o gate usava o `run_in_threadpool` padrao, e 200 pedidos com o banco fora levaram o
    `/api/health` a 25 s. Agora o banco tem limite proprio e o excesso espera no loop.
    """
    monkeypatch.setattr(acesso, "banco_no_comando", lambda: True)
    em_voo: list[int] = []
    pico: list[int] = [0]
    trava = threading.Lock()

    def lenta(remote_user: object) -> rbac.Identidade:
        with trava:
            em_voo.append(1)
            pico[0] = max(pico[0], len(em_voo))
        time.sleep(0.15)
        with trava:
            em_voo.pop()
        return rbac.Identidade(
            id_usuario=1, login="ana", perfil="t", permissoes=frozenset({"territorio.explorar"})
        )

    monkeypatch.setattr(rbac, "identidade", lenta)

    async def cenario() -> float:
        tarefas = [
            asyncio.create_task(
                pilot._controle_de_acesso_por_aba(_Requisicao(f"/api/uf/U{i}"), _proximo)
            )
            for i in range(45)
        ]
        await asyncio.sleep(0.05)
        inicio = time.perf_counter()
        await anyio.to_thread.run_sync(lambda: None)  # pool padrao
        decorrido = time.perf_counter() - inicio
        respostas = await asyncio.gather(*tarefas)
        assert {r.status_code for r in respostas} == {200}
        return decorrido

    decorrido = asyncio.run(cenario())
    assert decorrido < RAPIDO_S, f"pool padrao esperou {decorrido:.3f}s pelo banco"
    assert pico[0] <= pilot.LIMITE_THREADS_BANCO


def test_limite_de_threads_do_banco_acompanha_o_pool() -> None:
    """O limite fica no app (sem importar o pacote do banco no import), mas tem de seguir o
    pool: menor que ele desperdica conexao; muito maior volta a tomar thread dos outros."""
    assert mod.POOL_MAX < pilot.LIMITE_THREADS_BANCO <= mod.POOL_MAX + 4


def test_health_nao_espera_thread() -> None:
    """`/api/health` e' `async def`: nao depende de thread livre no pool padrao."""
    assert inspect.iscoroutinefunction(pilot.health)
    assert asyncio.run(pilot.health()) == {"status": "ok"}


def test_rota_livre_nao_salta_para_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    """Contar consultas nao basta: a rota sem capacidade nao pode nem ENTRAR na fila do banco."""
    saltos: list[Any] = []

    async def espiao(funcao: Any, *a: Any, **k: Any) -> Any:
        saltos.append(funcao)
        return None

    monkeypatch.setattr(acesso, "banco_no_comando", lambda: True)
    monkeypatch.setattr(pilot, "_no_banco", espiao)
    for caminho in ("/api/health", "/api/me", "/"):
        resposta = asyncio.run(pilot._controle_de_acesso_por_aba(_Requisicao(caminho), _proximo))
        assert resposta.status_code == 200
    assert saltos == []
    asyncio.run(pilot._controle_de_acesso_por_aba(_Requisicao("/api/uf/SP"), _proximo))
    assert saltos == [acesso.motivo_bloqueio_por_banco]


def test_portao_de_sessao_toca_a_sessao_fora_do_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    threads: list[str] = []

    class Sessao:
        id_sessao = 9
        identidade = rbac.Identidade(id_usuario=3, login="ana", perfil="t", permissoes=frozenset())

    def validar(_token: str) -> Any:
        return Sessao()

    def tocar(**_kw: Any) -> None:
        threads.append(threading.current_thread().name)

    monkeypatch.setenv(db_sessoes.ENV_AUTENTICACAO_PROPRIA, "1")
    monkeypatch.setattr(db_sessoes, "validar", validar)
    monkeypatch.setattr(db_sessoes, "tocar", tocar)

    class Req:
        def __init__(self) -> None:
            self.url = _Url("/api/uf/SP")
            self.cookies: dict[str, str] = {}
            self.scope: dict[str, Any] = {"headers": []}
            self.headers: dict[str, str] = {}

    asyncio.run(pilot._portao_de_sessao(Req(), _proximo))
    assert threads, "o portao nao chegou a tocar a sessao"
    assert threads[0] != threading.main_thread().name


#: Chamadas que vao ao Postgres e que NENHUMA `async def` do app pode fazer direto.
_IDAS_AO_BANCO_NOMES = {"_registrar_relatorio_gerado"}
_IDAS_AO_BANCO_MODULOS = {"db_sessoes", "rbac", "db", "db_eventos", "db_usuarios"}
_IDAS_AO_BANCO_ATRIBUTOS = {"motivo_bloqueio_por_banco", "abas_do_usuario_por_banco"}
#: Leem so' variavel de ambiente: nao vao ao banco, e o portao precisa delas no loop.
_SEM_IO = {"db_sessoes.ligada"}
#: O proprio despachante chama a versao sincrona no ramo SEM banco, que nao faz I/O.
_ASYNC_PERMITIDAS = {"_registrar_relatorio_gerado_fora_do_loop"}


def _chamadas_diretas(funcao: ast.AsyncFunctionDef) -> list[str]:
    """Chamadas ao banco no CORPO da funcao, sem descer em `def`/`lambda` aninhados (esses
    rodam onde o chamador mandar -- tipicamente no threadpool)."""
    achadas: list[str] = []
    pendentes: list[ast.AST] = list(funcao.body)
    while pendentes:
        no = pendentes.pop()
        if isinstance(no, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
            continue
        if isinstance(no, ast.Call):
            alvo = no.func
            if isinstance(alvo, ast.Name) and alvo.id in _IDAS_AO_BANCO_NOMES:
                achadas.append(alvo.id)
            if isinstance(alvo, ast.Attribute):
                dono = alvo.value.id if isinstance(alvo.value, ast.Name) else ""
                nome = f"{dono}.{alvo.attr}"
                if nome in _SEM_IO:
                    pass
                elif dono in _IDAS_AO_BANCO_MODULOS or alvo.attr in _IDAS_AO_BANCO_ATRIBUTOS:
                    achadas.append(nome)
        pendentes.extend(ast.iter_child_nodes(no))
    return achadas


def test_nenhuma_async_do_app_vai_ao_banco_direto() -> None:
    """Trava por AST, e nao por regex: as quatro rotas de relatorio, o gate e o portao.
    Passar a funcao como ARGUMENTO (`_no_banco(db_sessoes.validar, ...)`) e' permitido -- nao
    e' chamada; chamar `db_sessoes.validar(...)` dentro de `async def` nao e'."""
    arvore = ast.parse((_SERVER / "app.py").read_text(encoding="utf-8"))
    violacoes = {
        no.name: achadas
        for no in ast.walk(arvore)
        if isinstance(no, ast.AsyncFunctionDef)
        and no.name not in _ASYNC_PERMITIDAS
        and (achadas := _chamadas_diretas(no))
    }
    assert violacoes == {}
    # E as quatro rotas de relatorio de fato usam o despachante (nao sumiram do mapa).
    fonte = (_SERVER / "app.py").read_text(encoding="utf-8")
    assert fonte.count("await _registrar_relatorio_gerado_fora_do_loop(") == 4


def test_os_tetos_sao_positivos_e_chegam_literais_na_conexao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`0` DESLIGA `statement_timeout`/`lock_timeout` no Postgres, sem erro nenhum."""
    assert mod.STATEMENT_TIMEOUT_MS > 0
    assert mod.LOCK_TIMEOUT_MS > 0
    assert mod.LOCK_TIMEOUT_MS <= mod.STATEMENT_TIMEOUT_MS
    assert mod.TIMEOUT_CONEXAO_S >= 2  # o libpq trata menos de 2 como 2
    pool = _instalar(monkeypatch, _ConexaoQueFalha(RuntimeError("nao usado")))
    mod._obter_pool()
    opcoes = pool.kwargs["kwargs"]["options"]
    assert f"-c statement_timeout={mod.STATEMENT_TIMEOUT_MS}" in opcoes
    assert f"-c lock_timeout={mod.LOCK_TIMEOUT_MS}" in opcoes


class _PoolQueCaiNoCommit:
    """O `pool.connection()` real faz `with conn:`: o COMMIT roda na SAIDA, depois do corpo."""

    def __init__(self, erro: Exception) -> None:
        self._erro = erro

    @contextmanager
    def connection(self):  # type: ignore[no-untyped-def]
        yield _ConexaoRoteirizada(morta=False)
        raise self._erro

    def open(self, wait: bool = False) -> None:
        pass

    def close(self) -> None:
        pass


@pytest.mark.parametrize("abrir", ["leitura", "escrita"])
def test_conexao_que_cai_no_commit_vira_banco_indisponivel(
    monkeypatch: pytest.MonkeyPatch, abrir: str
) -> None:
    pool = _PoolQueCaiNoCommit(psycopg.OperationalError("server closed the connection"))
    monkeypatch.setattr(mod, "_driver", lambda: lambda **_kw: pool)
    monkeypatch.setenv(mod.ENV_URL, "postgresql://fake/motor")
    contexto = db.conexao() if abrir == "leitura" else db.transacao(id_usuario=1)
    with pytest.raises(db.BancoIndisponivel, match="OperationalError"):
        with contexto as con:
            con.execute("SELECT 1")


def test_erro_de_integridade_no_commit_continua_visivel(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = _PoolQueCaiNoCommit(psycopg.errors.UniqueViolation("duplicate key"))
    monkeypatch.setattr(mod, "_driver", lambda: lambda **_kw: pool)
    monkeypatch.setenv(mod.ENV_URL, "postgresql://fake/motor")
    with pytest.raises(psycopg.errors.UniqueViolation):
        with db.transacao(id_usuario=1):
            pass


class _PoolSemConexao:
    """Cada pedido espera e devolve `PoolTimeout`, como o psycopg_pool.

    `recusa=True` e' o BANCO FORA: enquanto o pedido espera, a thread do pool tenta abrir
    conexao e o servidor recusa (o que `_classe_de_conexao` registra). `recusa=False` e' o
    POOL SATURADO com o banco no ar: as conexoes estao todas emprestadas, ninguem recusa."""

    def __init__(self, espera_s: float, recusa: bool = True) -> None:
        self._espera_s = espera_s
        self._recusa = recusa
        self.pedidos = 0

    @contextmanager
    def connection(self):  # type: ignore[no-untyped-def]
        from psycopg_pool import PoolTimeout

        self.pedidos += 1
        if self._recusa:
            mod._registrar_recusa_de_conexao()
        time.sleep(self._espera_s)
        raise PoolTimeout("couldn't get a connection after 5.00 sec")
        yield  # pragma: no cover

    def open(self, wait: bool = False) -> None:
        pass

    def close(self) -> None:
        pass


def test_disjuntor_responde_na_hora_depois_de_um_pool_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("psycopg_pool")
    pool = _PoolSemConexao(espera_s=0.3)
    monkeypatch.setattr(mod, "_driver", lambda: lambda **_kw: pool)
    monkeypatch.setenv(mod.ENV_URL, "postgresql://fake/motor")

    with pytest.raises(db.BancoIndisponivel, match="PoolTimeout"):
        with db.conexao():
            pass
    assert pool.pedidos == 1
    inicio = time.perf_counter()
    for abrir in (db.conexao, lambda: db.transacao(id_usuario=1)):
        with pytest.raises(db.BancoIndisponivel, match="nova tentativa"):
            with abrir():
                pass
    assert time.perf_counter() - inicio < RAPIDO_S
    assert pool.pedidos == 1, "com o disjuntor aberto, o pool nao pode ser tocado"

    # Janela vencida: volta a tentar o banco de verdade.
    # Atribuicao direta, NAO `monkeypatch.setattr`: o monkeypatch desfaz DEPOIS do teardown
    # do `_ambiente` e restauraria o disjuntor ABERTO para o teste seguinte (medido: 2,7 s).
    mod._disjuntor_ate = time.monotonic() - 1
    with pytest.raises(db.BancoIndisponivel, match="PoolTimeout"):
        with db.conexao():
            pass
    assert pool.pedidos == 2


def test_pool_saturado_nao_e_prova_de_queda_nem_arma_o_disjuntor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """3a revisao de 17/10/2026: `PoolTimeout` com o servidor no ar (as quatro conexoes
    emprestadas a quem esta' RESPONDENDO, ou presas atras da GIL) armava o disjuntor e
    carimbava a evidencia -- e o gate liberava as rotas nao sensiveis a quem nao tem a
    capacidade. Sem recusa de conexao, nao prova nada."""
    pytest.importorskip("psycopg_pool")
    pool = _PoolSemConexao(espera_s=0.0, recusa=False)
    monkeypatch.setattr(mod, "_driver", lambda: lambda **_kw: pool)
    monkeypatch.setenv(mod.ENV_URL, "postgresql://fake/motor")
    for _ in range(2):
        with pytest.raises(db.BancoSemProvaDeQueda, match="PoolTimeout"):
            with db.conexao():
                pass
    assert pool.pedidos == 2, "pool saturado nao pode abrir o disjuntor"
    assert not acesso.banco_em_falha()


def test_conexao_morta_seguida_de_pool_timeout_e_prova_de_queda(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O `docker stop` no Windows (e qualquer queda em que a recusa nao chega a tempo): as
    conexoes do pool estao MORTAS, o servidor as derrubou, e o `PoolTimeout` vem depois de
    troca-las. A conexao derrubada e' a prova -- sem ela, a queda inteira seria 503."""
    from psycopg_pool import PoolTimeout

    _instalar_roteiro(
        monkeypatch,
        [_ConexaoRoteirizada(morta=True), PoolTimeout("couldn't get a connection")],
    )
    with pytest.raises(db.BancoIndisponivel) as falha:
        with db.conexao():
            pass
    assert not isinstance(falha.value, db.BancoSemProvaDeQueda)
    assert acesso.banco_em_falha()


def test_recusa_anterior_ao_ultimo_sucesso_nao_prova_a_queda_de_agora(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A recusa e' ESTADO ate' o banco responder: uma queda ja' superada nao transforma o
    proximo pool saturado em "banco fora"."""
    pytest.importorskip("psycopg_pool")
    mod._registrar_recusa_de_conexao()
    pool = _instalar_roteiro(monkeypatch, [_ConexaoRoteirizada(morta=False)])
    with db.conexao():
        pass
    saturado = _PoolSemConexao(espera_s=0.0, recusa=False)
    monkeypatch.setattr(pool, "connection", saturado.connection)
    with pytest.raises(db.BancoSemProvaDeQueda):
        with db.conexao():
            pass
    assert not acesso.banco_em_falha()


@pytest.mark.parametrize(
    ("erro", "prova"),
    [
        pytest.param(psycopg.errors.QueryCanceled("statement timeout"), False, id="statement"),
        pytest.param(psycopg.errors.LockNotAvailable("lock timeout"), False, id="lock"),
        pytest.param(psycopg.errors.ConnectionTimeout("timeout expired"), False, id="conectar"),
        pytest.param(psycopg.OperationalError("server closed the connection"), True, id="caiu"),
        pytest.param(psycopg.errors.AdminShutdown("terminating connection"), True, id="saindo"),
    ],
)
@pytest.mark.parametrize("abrir", ["leitura", "escrita"])
def test_so_o_que_o_processo_nao_fabrica_carimba_a_evidencia(
    monkeypatch: pytest.MonkeyPatch, erro: Exception, prova: bool, abrir: str
) -> None:
    _instalar(monkeypatch, _ConexaoQueFalha(erro))
    with pytest.raises(db.BancoIndisponivel) as falha:
        with db.conexao() if abrir == "leitura" else db.transacao(id_usuario=1) as con:
            con.execute("SELECT 1")
    assert isinstance(falha.value, db.BancoSemProvaDeQueda) is (not prova)
    assert acesso.banco_em_falha() is prova


def test_a_conexao_do_pool_registra_recusa_mas_nao_tempo_esgotado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O `connect_timeout` do psycopg 3 e' medido em PYTHON: com a GIL disputada ele estoura
    contra um banco saudavel. So' a recusa (o servidor dizendo "nao") vira prova."""
    classe = mod._classe_de_conexao()
    erros: list[Exception] = []

    def conectar(cls: Any, *_a: Any, **_k: Any) -> Any:
        raise erros[-1]

    monkeypatch.setattr(psycopg.Connection, "connect", classmethod(conectar))
    erros.append(psycopg.errors.ConnectionTimeout("connection timeout expired"))
    with pytest.raises(psycopg.errors.ConnectionTimeout):
        classe.connect("host=x")
    assert mod._ultima_recusa == 0
    erros.append(psycopg.OperationalError("connection refused"))
    with pytest.raises(psycopg.OperationalError):
        classe.connect("host=x")
    assert mod._ultima_recusa > 0


def test_o_pool_usa_a_conexao_que_registra_recusa(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = _instalar(monkeypatch, _ConexaoRoteirizada(morta=False))
    with db.conexao():
        pass
    assert pool.kwargs["connection_class"] is mod._classe_de_conexao()


def test_pool_saturado_com_banco_no_ar_nao_libera_rota_pelo_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A propriedade, ponta a ponta pelo `rbac` real: com o banco NO AR, quem nao tem a
    capacidade nunca recebe 200 -- nem quando o pool nao entrega conexao. Reproducao da
    revisao: Postgres saudavel, 2 threads de CPU e 40 do `/api/me`, 513 de 600 pins com 200."""
    pytest.importorskip("psycopg_pool")
    pool = _PoolSemConexao(espera_s=0.0, recusa=False)
    monkeypatch.setattr(mod, "_driver", lambda: lambda **_kw: pool)
    monkeypatch.setenv(mod.ENV_URL, "postgresql://fake/motor")
    monkeypatch.setenv("MOTOR_ACESSO_FAIL_CLOSED", "1")
    monkeypatch.setattr(acesso, "banco_no_comando", lambda: True)
    caminhos = ["/api/pin-concorrente/1", "/api/uf/SP", "/api/oportunidades", "/api/rede/carteira"]

    async def cenario() -> list[int]:
        respostas = await asyncio.gather(
            *(pilot._controle_de_acesso_por_aba(_Requisicao(c), _proximo) for c in caminhos * 5)
        )
        return [r.status_code for r in respostas]

    assert set(asyncio.run(cenario())) == {503}


def test_sem_prova_nesta_chamada_degrada_se_a_queda_ja_foi_provada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Durante uma queda PROVADA (e nenhum uso bom desde entao), o `PoolTimeout` seguinte
    nao precisa provar de novo: a degradacao de sempre, 403 so' nas sensiveis."""
    pytest.importorskip("psycopg_pool")
    pool = _PoolSemConexao(espera_s=0.0, recusa=False)
    monkeypatch.setattr(mod, "_driver", lambda: lambda **_kw: pool)
    monkeypatch.setenv(mod.ENV_URL, "postgresql://fake/motor")
    monkeypatch.setenv("MOTOR_ACESSO_FAIL_CLOSED", "1")
    monkeypatch.setattr(acesso, "banco_no_comando", lambda: True)
    mod._marcar_indisponivel()

    def rodar(caminho: str) -> int:
        return asyncio.run(
            pilot._controle_de_acesso_por_aba(_Requisicao(caminho), _proximo)
        ).status_code

    assert rodar("/api/pin-concorrente/1") == 200
    assert rodar("/api/rede/carteira") == 403


def test_lock_e_statement_timeout_nao_armam_o_disjuntor(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sao de UMA consulta, nao do banco: a proxima requisicao tem de tentar de novo."""
    pool = _instalar_roteiro(
        monkeypatch,
        [
            _ConexaoRoteirizada(morta=False, erro_vivo=psycopg.errors.LockNotAvailable("lock")),
            _ConexaoRoteirizada(morta=False),
        ],
    )
    with pytest.raises(db.BancoIndisponivel, match="LockNotAvailable"):
        with db.conexao():
            pass
    with db.conexao():
        pass
    assert pool.emprestadas == 2


def test_gate_com_banco_fora_nao_enfileira_o_mapa(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ponta a ponta pelo `rbac` real: 30 pins com o banco fora. Sem o disjuntor, o limite de
    threads faria lotes de seis esperarem o `PoolTimeout` cada um (5 lotes x espera); com ele,
    so' o primeiro lote espera e o resto recebe o fail-closed na hora."""
    pytest.importorskip("psycopg_pool")
    espera = 0.4
    pool = _PoolSemConexao(espera_s=espera)
    monkeypatch.setattr(mod, "_driver", lambda: lambda **_kw: pool)
    monkeypatch.setenv(mod.ENV_URL, "postgresql://fake/motor")
    monkeypatch.setenv("MOTOR_ACESSO_FAIL_CLOSED", "1")
    monkeypatch.setattr(acesso, "banco_no_comando", lambda: True)

    async def cenario() -> tuple[list[Any], float]:
        inicio = time.perf_counter()
        respostas = await asyncio.gather(
            *(
                pilot._controle_de_acesso_por_aba(
                    _Requisicao(f"/api/pin-concorrente/{i}"), _proximo
                )
                for i in range(30)
            )
        )
        return respostas, time.perf_counter() - inicio

    respostas, total = asyncio.run(cenario())
    assert {r.status_code for r in respostas} == {200}  # nao sensivel: fail-closed deixa passar
    assert total < 2 * espera, f"o mapa enfileirou: {total:.2f}s"
    assert pool.pedidos <= pilot.LIMITE_THREADS_BANCO


def test_toda_ida_ao_banco_do_codigo_async_usa_o_limite_proprio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Relatorio, gate e portao passam pelo `_no_banco` -- e nao pelo `run_in_threadpool`
    padrao, que divide as 40 threads com o `/api/health` e os estaticos."""
    usados: list[Any] = []

    async def espiao(funcao: Any, *a: Any, **k: Any) -> Any:
        usados.append(funcao)
        return "R-3"

    def proibido(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("ida ao banco pelo threadpool padrao")

    monkeypatch.setattr(acesso, "banco_no_comando", lambda: True)
    monkeypatch.setattr(pilot, "_no_banco", espiao)
    monkeypatch.setattr(pilot, "run_in_threadpool", proibido)
    report_id = asyncio.run(
        pilot._registrar_relatorio_gerado_fora_do_loop("ana", relatorio="pontual", formato="pdf")
    )
    assert report_id == "R-3"
    assert usados == [pilot._registrar_relatorio_gerado]


def test_fila_do_banco_cheia_da_o_fail_closed_no_prazo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Todas as threads do banco presas (lock de migration): quem chega depois NAO espera a
    fila sem fundo -- recebe, no prazo, a mesma resposta do banco fora. Medido antes do prazo:
    com 200 pedidos e `LOCK TABLE usuarios`, 84 estouravam os 30 s do cliente."""
    monkeypatch.setenv("MOTOR_ACESSO_FAIL_CLOSED", "1")
    monkeypatch.setattr(pilot, "ESPERA_FILA_BANCO_S", 0.1)
    # A evidencia de queda: o banco acabou de levantar `BancoIndisponivel`.
    monkeypatch.setattr(acesso, "banco_em_falha", lambda: True)
    chamadas: list[str] = []
    _identidade_lenta(monkeypatch, {"territorio.explorar", "rede.ver"}, chamadas)

    async def cenario() -> tuple[list[Any], list[Any], float]:
        presas = [
            asyncio.create_task(
                pilot._controle_de_acesso_por_aba(_Requisicao(f"/api/uf/U{i}"), _proximo)
            )
            for i in range(pilot.LIMITE_THREADS_BANCO)
        ]
        await asyncio.sleep(0.05)
        inicio = time.perf_counter()
        atrasadas = await asyncio.gather(
            pilot._controle_de_acesso_por_aba(_Requisicao("/api/rede/carteira"), _proximo),
            pilot._controle_de_acesso_por_aba(_Requisicao("/api/pin-concorrente/1"), _proximo),
        )
        decorrido = time.perf_counter() - inicio
        return list(atrasadas), list(await asyncio.gather(*presas)), decorrido

    atrasadas, presas, decorrido = asyncio.run(cenario())
    assert [r.status_code for r in presas] == [200] * pilot.LIMITE_THREADS_BANCO
    sensivel, comum = atrasadas
    assert sensivel.status_code == 403  # `rede.ver` e' sensivel: negado sem o banco
    assert comum.status_code == 200  # nao sensivel: passa, como com o banco fora
    assert decorrido < LENTO_S, f"esperou a fila em vez do prazo ({decorrido:.3f}s)"
    assert len(chamadas) == pilot.LIMITE_THREADS_BANCO  # as atrasadas nao chegaram ao banco


@pytest.mark.parametrize("fail_closed", ["1", ""])
@pytest.mark.parametrize(
    "caminho", ["/api/rede/carteira", "/api/pin-concorrente/1", "/api/health", "/api/uf/SP"]
)
def test_resposta_sem_banco_e_a_mesma_pelos_dois_caminhos(
    monkeypatch: pytest.MonkeyPatch, caminho: str, fail_closed: str
) -> None:
    """A degradacao isolada (`motivo_bloqueio_banco_indisponivel`, usada na fila cheia) da' o
    MESMO que o gate quando o banco levanta -- uma regra, nao duas copias."""
    monkeypatch.setenv("MOTOR_ACESSO_FAIL_CLOSED", fail_closed)

    def fora(_u: object) -> Any:
        raise db.BancoIndisponivel("fora")

    monkeypatch.setattr(rbac, "identidade", fora)
    pelo_banco = acesso.motivo_bloqueio_por_banco(caminho, "GET", "ana")
    isolada = acesso.motivo_bloqueio_banco_indisponivel(caminho, "GET", "fila cheia")
    assert isolada == pelo_banco


def test_relatorio_espera_a_vez_sem_prazo(monkeypatch: pytest.MonkeyPatch) -> None:
    """O registro de relatorio NAO tem prazo de fila: desistir so' criaria id orfao a mais."""
    pedidos: list[dict[str, Any]] = []

    async def espiao(funcao: Any, *a: Any, **k: Any) -> Any:
        pedidos.append(k)
        return "R-4"

    monkeypatch.setattr(acesso, "banco_no_comando", lambda: True)
    monkeypatch.setattr(pilot, "_no_banco", espiao)
    asyncio.run(
        pilot._registrar_relatorio_gerado_fora_do_loop("ana", relatorio="pontual", formato="pdf")
    )
    assert pedidos and "prazo_na_fila_s" not in pedidos[0]


def _inundar_com_banco_lento(
    monkeypatch: pytest.MonkeyPatch, permissoes: set[str]
) -> tuple[list[Any], list[str]]:
    """Todas as vagas presas numa chamada de `LENTO_S`, e mais seis rotas controladas chegando.

    O banco esta' NO AR: as chamadas presas terminam bem. Elas so' estao LENTAS -- e quando
    as atrasadas desistem da fila, as presas ja' tem idade de varias esperas de fila."""
    monkeypatch.setenv("MOTOR_ACESSO_FAIL_CLOSED", "1")
    monkeypatch.setattr(pilot, "ESPERA_FILA_BANCO_S", 0.1)
    chamadas: list[str] = []
    _identidade_lenta(monkeypatch, permissoes, chamadas)
    caminhos = [
        "/api/uf/SP",
        "/api/relatorio/pontual",
        "/api/oportunidades",
        "/api/pin-concorrente/1",
        "/api/rede/carteira",
        "/api/oportunidades/9/dossie",
    ]

    async def cenario() -> list[Any]:
        presas = [
            asyncio.create_task(
                pilot._controle_de_acesso_por_aba(_Requisicao(f"/api/uf/U{i}"), _proximo)
            )
            for i in range(pilot.LIMITE_THREADS_BANCO)
        ]
        await asyncio.sleep(0.05)
        atrasadas = await asyncio.gather(
            *(pilot._controle_de_acesso_por_aba(_Requisicao(c), _proximo) for c in caminhos)
        )
        await asyncio.gather(*presas)
        return list(atrasadas)

    return asyncio.run(cenario()), caminhos


def test_fila_cheia_com_banco_no_ar_nao_libera_quem_nao_tem_a_capacidade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O FURO da revisao de 17/10/2026: fila cheia com o banco SAUDAVEL era tratada como banco
    fora, e a degradacao liberava as rotas nao sensiveis sem checar permissao -- um usuario
    SEM capacidade nenhuma passava 532 de 1500 pedidos so' por inundar o piloto. Sem
    evidencia de queda, nenhuma rota controlada pode responder 200: e' 503, com Retry-After."""
    respostas, caminhos = _inundar_com_banco_lento(monkeypatch, set())
    assert [r.status_code for r in respostas] == [503] * len(caminhos)
    assert all(r.headers.get("retry-after") for r in respostas)


def test_fila_cheia_sem_evidencia_nega_tambem_a_quem_tem_acesso(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O preco declarado: sob carga real, ate' quem tem a capacidade recebe 503 -- e nunca
    um 403 que pareceria falta de permissao."""
    respostas, caminhos = _inundar_com_banco_lento(
        monkeypatch, {"territorio.explorar", "rede.ver", "imovel.dossie_ver"}
    )
    assert [r.status_code for r in respostas] == [503] * len(caminhos)


def test_chamada_antiga_em_voo_nao_e_prova_de_queda(monkeypatch: pytest.MonkeyPatch) -> None:
    """3a revisao de 17/10/2026: a versao anterior tratava "a chamada mais antiga em voo
    passou de `BANCO_SEM_RESPOSTA_S`" como prova de queda. Essa idade mede o PROCESSO --
    espera do pool, da GIL, do proprio loop --, e com o Postgres saudavel um usuario SEM
    permissao recebia 200 (36 com seis operacoes lentas; 3483 com uma pausa de 2,1 s do loop;
    513 de 600 com duas threads de CPU). Idade nenhuma prova queda: aqui as presas tem ~6x
    a espera da fila, e o limiar antigo e' zerado (se ele voltar com qualquer nome que este
    teste conheca, o teste pega). Tudo 503."""
    monkeypatch.setattr(pilot, "BANCO_SEM_RESPOSTA_S", 0.0, raising=False)
    respostas, caminhos = _inundar_com_banco_lento(monkeypatch, set())
    assert not acesso.banco_em_falha()
    assert [r.status_code for r in respostas] == [503] * len(caminhos)


def test_evidencia_de_queda_vem_do_banco_e_some_com_o_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    """`BancoIndisponivel` de `conexao()` carimba a evidencia; `fechar_pool` a apaga; erro de
    PROGRAMACAO nao carimba (senao um schema errado viraria "banco fora" e liberaria rota)."""
    assert not acesso.banco_em_falha()
    _instalar(monkeypatch, _ConexaoQueFalha(psycopg.errors.UndefinedTable("nao existe")))
    with pytest.raises(psycopg.errors.UndefinedTable):
        with db.conexao() as con:
            con.execute("SELECT 1")
    assert not acesso.banco_em_falha()
    db.fechar_pool()
    _instalar(monkeypatch, _ConexaoQueFalha(psycopg.OperationalError("caiu")))
    with pytest.raises(db.BancoIndisponivel):
        with db.conexao() as con:
            con.execute("SELECT 1")
    assert acesso.banco_em_falha()
    db.fechar_pool()
    assert not acesso.banco_em_falha()


@pytest.mark.parametrize("abrir", ["leitura", "escrita"])
def test_evidencia_dura_ate_o_banco_responder(
    monkeypatch: pytest.MonkeyPatch, abrir: str
) -> None:
    """ESTADO, nao janela: sem trafego, a evidencia nao envelhece -- a primeira rajada depois
    de um silencio, com o banco ainda fora, tem de cair na degradacao e nao no 503 (medido em
    `docker stop` com a janela de 10 s). Ela so' some quando um uso termina BEM."""
    pool = _instalar_roteiro(
        monkeypatch, [_ConexaoRoteirizada(morta=False), _ConexaoRoteirizada(morta=False)]
    )
    mod._marcar_indisponivel()
    assert acesso.banco_em_falha()
    with pytest.raises(KeyError):  # erro da APLICACAO no corpo nao prova nada sobre o banco
        with db.conexao() if abrir == "leitura" else db.transacao(id_usuario=1):
            raise KeyError("x")
    assert acesso.banco_em_falha()
    with db.conexao() if abrir == "leitura" else db.transacao(id_usuario=1):
        pass
    assert not acesso.banco_em_falha()
    assert pool.emprestadas == 2


def test_disjuntor_aberto_renova_a_evidencia(monkeypatch: pytest.MonkeyPatch) -> None:
    """Com o banco fora, quem renova a evidencia durante a janela e' o proprio disjuntor."""
    mod._disjuntor_ate = time.monotonic() + 1
    mod._em_falha = False
    with pytest.raises(db.BancoIndisponivel, match="nova tentativa"):
        with db.conexao():
            pass
    assert mod.banco_em_falha()


def test_fila_nao_deixa_furar() -> None:
    """Revisao de 17/10/2026: o `CapacityLimiter` do anyio 4.13 deixava uma recem-chegada
    furar a fila -- ao liberar, ele acorda quem espera, mas a vaga so' e' tomada quando essa
    tarefa volta a rodar. Reproduzido: 7 emprestimos num limite de 6, e a 7a requisicao
    esperava a THREAD sem prazo. Cenario deterministico: seis presas, W esperando, uma vaga
    liberada e N agendada ANTES de W voltar a rodar. So' W pode entrar."""

    async def cenario() -> list[str]:
        fila, _threads = pilot._limites_banco()
        soltar = [anyio.Event() for _ in range(pilot.LIMITE_THREADS_BANCO)]
        entraram: list[str] = []

        async def presa(i: int) -> None:
            await fila.acquire()
            try:
                await soltar[i].wait()
            finally:
                fila.release()

        async def chega(nome: str) -> None:
            await fila.acquire()
            entraram.append(nome)

        async with anyio.create_task_group() as tg:
            for i in range(pilot.LIMITE_THREADS_BANCO):
                tg.start_soon(presa, i)
            await anyio.sleep(0.02)
            tg.start_soon(chega, "W")
            await anyio.sleep(0.02)
            soltar[0].set()  # a presa 0 roda primeiro e libera a vaga...
            tg.start_soon(chega, "N")  # ...e N roda antes de W voltar
            await anyio.sleep(0.05)
            resultado = list(entraram)
            tg.cancel_scope.cancel()
        return resultado

    assert asyncio.run(cenario()) == ["W"]


def test_portao_de_sessao_com_fila_cheia_responde_503_no_prazo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O `validar` do portao tem prazo de fila: sem ele, com as vagas presas, o login de todo
    mundo esperaria o banco sem fundo em vez de ouvir 503."""
    monkeypatch.setattr(pilot, "ESPERA_FILA_BANCO_S", 0.1)
    monkeypatch.setenv(db_sessoes.ENV_AUTENTICACAO_PROPRIA, "1")

    def validar_lento(_token: str) -> None:
        time.sleep(LENTO_S)
        return None

    monkeypatch.setattr(db_sessoes, "validar", validar_lento)

    class Req:
        def __init__(self) -> None:
            self.url = _Url("/api/uf/SP")
            self.cookies: dict[str, str] = {}
            self.scope: dict[str, Any] = {"headers": []}

    async def cenario() -> tuple[Any, float, list[Any]]:
        presas = [
            asyncio.create_task(pilot._portao_de_sessao(Req(), _proximo))
            for _ in range(pilot.LIMITE_THREADS_BANCO)
        ]
        await asyncio.sleep(0.05)
        inicio = time.perf_counter()
        atrasada = await pilot._portao_de_sessao(Req(), _proximo)
        decorrido = time.perf_counter() - inicio
        return atrasada, decorrido, list(await asyncio.gather(*presas))

    atrasada, decorrido, presas = asyncio.run(cenario())
    assert atrasada.status_code == 503
    assert decorrido < LENTO_S, f"o portao esperou a fila ({decorrido:.3f}s)"
    assert {r.status_code for r in presas} == {401}


def test_no_banco_nao_usa_o_pool_padrao_de_threads() -> None:
    """Com o pool PADRAO tomado (rotas `def`, estaticos), a ida ao banco segue: ela tem o
    limitador de threads proprio, e nao disputa thread com o resto do app."""

    async def cenario() -> float:
        padrao = anyio.to_thread.current_default_thread_limiter()
        padrao.total_tokens = 1
        ocupando = asyncio.create_task(anyio.to_thread.run_sync(time.sleep, LENTO_S))
        await asyncio.sleep(0.05)
        inicio = time.perf_counter()
        assert await pilot._no_banco(lambda: 7, prazo_na_fila_s=1.0) == 7
        decorrido = time.perf_counter() - inicio
        await ocupando
        return decorrido

    decorrido = asyncio.run(cenario())
    assert decorrido < RAPIDO_S, f"a ida ao banco esperou o pool padrao ({decorrido:.3f}s)"


def test_os_tempos_cabem_um_no_outro() -> None:
    """Os testes de comportamento trocam os prazos por monkeypatch: estes asserts travam o
    TETO dos valores reais, que nenhum deles via (mutantes de 600 s / 300 s / 30 s passavam).

    * a fila desiste ANTES do pool: senao "fila cheia" chega depois de o banco ja' responder;
    * a conexao abre ANTES do pool desistir: senao o pool desiste de toda conexao nova;
    * o disjuntor nao fica mais aberto que uma espera de pool.
    """
    assert 0 < pilot.ESPERA_FILA_BANCO_S < mod.TIMEOUT_POOL_S
    assert mod.TIMEOUT_CONEXAO_S < mod.TIMEOUT_POOL_S
    assert 0 < mod.JANELA_DISJUNTOR_S <= mod.TIMEOUT_POOL_S


def test_keepalive_tcp_chega_na_conexao_e_a_url_vence(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem keepalive, uma queda de rede sem RST prendia thread e conexao por 15 min a 2 h: o
    `statement_timeout` e' do servidor, e o servidor nao esta' mais la'."""
    parametros = mod._parametros_de_conexao("postgresql://u:s@h/b")
    assert parametros["keepalives"] == 1
    assert parametros["keepalives_idle"] == mod.KEEPALIVES_IDLE_S
    assert parametros["keepalives_interval"] == mod.KEEPALIVES_INTERVALO_S
    assert parametros["keepalives_count"] == mod.KEEPALIVES_CONTAGEM
    assert parametros["tcp_user_timeout"] == mod.TCP_USER_TIMEOUT_MS
    deteccao_s = mod.KEEPALIVES_IDLE_S + mod.KEEPALIVES_INTERVALO_S * mod.KEEPALIVES_CONTAGEM
    assert deteccao_s <= 30
    assert 0 < mod.TCP_USER_TIMEOUT_MS <= 30_000
    da_url = mod._parametros_de_conexao("postgresql://u:s@h/b?keepalives_idle=60")
    assert "keepalives_idle" not in da_url  # o que a URL declara vence
    assert da_url["keepalives_count"] == mod.KEEPALIVES_CONTAGEM


def test_log_de_rbac_indisponivel_e_um_por_episodio(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Antes, um ERROR por pedido degradado: milhares por segundo, controlados pelo usuario."""
    monkeypatch.setenv("MOTOR_ACESSO_FAIL_CLOSED", "1")
    monkeypatch.setattr(acesso, "_rbac_indisponivel_logado", False)

    def fora(_u: object) -> Any:
        raise db.BancoIndisponivel("fora")

    def no_ar(u: object) -> rbac.Identidade:
        return rbac.Identidade(id_usuario=1, login=str(u), perfil="t", permissoes=frozenset())

    def erros() -> int:
        return sum(1 for r in caplog.records if "RBAC indisponivel (" in r.getMessage())

    caplog.set_level("ERROR", logger=acesso._LOG.name)
    monkeypatch.setattr(rbac, "identidade", fora)
    for _ in range(50):
        acesso.motivo_bloqueio_por_banco("/api/rede/carteira", "GET", "ana")
        acesso.motivo_bloqueio_banco_indisponivel("/api/uf/SP", "GET", "fila")
    assert erros() == 1
    monkeypatch.setattr(rbac, "identidade", no_ar)  # o banco volta: fim do episodio
    acesso.motivo_bloqueio_por_banco("/api/rede/carteira", "GET", "ana")
    monkeypatch.setattr(rbac, "identidade", fora)
    acesso.motivo_bloqueio_por_banco("/api/rede/carteira", "GET", "ana")
    assert erros() == 2


def test_no_banco_devolve_a_vaga_mesmo_quando_a_chamada_falha() -> None:
    """Vaga presa por excecao encolheria a fila ate' travar o gate de vez."""

    def falha() -> None:
        raise db.BancoIndisponivel("x")

    async def cenario() -> int:
        for _ in range(pilot.LIMITE_THREADS_BANCO * 2):
            with pytest.raises(db.BancoIndisponivel):
                await pilot._no_banco(falha, prazo_na_fila_s=0.2)
        fila, _threads = pilot._limites_banco()
        return fila.value

    assert asyncio.run(cenario()) == pilot.LIMITE_THREADS_BANCO


def _com_causa(mensagem: str, causa: BaseException) -> Exception:
    """`OperationalError` encadeado a um `OSError`, como o driver faz com `raise ... from`."""
    erro = psycopg.OperationalError(mensagem)
    erro.__cause__ = causa
    return erro


ERROS_DE_RECURSO_LOCAL = [
    pytest.param(
        psycopg.OperationalError(
            'connection to server at "postgres" failed: could not create socket: '
            "Too many open files"
        ),
        id="emfile_mensagem",
    ),
    pytest.param(
        _com_causa("connection failed", OSError(errno.EMFILE, "x")), id="emfile_errno"
    ),
    pytest.param(
        _com_causa("connection failed", OSError(errno.ENFILE, "x")), id="enfile_errno"
    ),
    pytest.param(psycopg.OperationalError("out of memory"), id="enomem_libpq"),
    pytest.param(
        psycopg.OperationalError("could not receive data: Cannot allocate memory"),
        id="enomem_mensagem",
    ),
    pytest.param(
        _com_causa("connection failed", OSError(errno.ENOMEM, "x")), id="enomem_errno"
    ),
    pytest.param(
        psycopg.OperationalError("could not send data: No buffer space available"),
        id="enobufs_mensagem",
    ),
    pytest.param(
        psycopg.OperationalError("n\u00e3o p\u00f4de criar soquete: Arquivos abertos demais"),
        id="emfile_pt_br",
    ),
    pytest.param(
        # So' casa SEM o acento: trava a normalizacao contra a mensagem traduzida.
        psycopg.OperationalError("could not receive data: N\u00e3o foi poss\u00edvel alocar mem\u00f3ria"),
        id="enomem_pt_br",
    ),
    pytest.param(
        # Medido (python:3.12-slim, psycopg 3.3.4): host em IP literal + EMFILE.
        psycopg.OperationalError("connection is bad: no error details available"),
        id="emfile_ip_sem_detalhe",
    ),
    pytest.param(
        # Medido: host por NOME + EMFILE -- a resolucao em Python falha antes da libpq.
        psycopg.OperationalError(
            "failed to resolve host 'postgres': [Errno 24] Too many open files: "
            "'/usr/local/lib/python3.12/encodings/idna.py'"
        ),
        id="emfile_resolucao_psycopg",
    ),
]

SINAIS_REAIS_DE_QUEDA = [
    pytest.param(
        psycopg.OperationalError(
            'could not translate host name "postgres" to address: Name or service not known'
        ),
        id="dns_servico_sumiu",
    ),
    pytest.param(
        psycopg.OperationalError(
            'could not translate host name "postgres" to address: '
            "Temporary failure in name resolution"
        ),
        id="dns_temporario",
    ),
    pytest.param(
        # Texto REAL do psycopg 3.3 (resolve o nome em Python), medido com o container parado.
        psycopg.OperationalError(
            "failed to resolve host 'postgres': [Errno -2] Name or service not known"
        ),
        id="dns_psycopg_servico_sumiu",
    ),
    pytest.param(
        # Texto REAL do psycopg 3.3 com a porta fechada (medido).
        psycopg.OperationalError(
            'connection failed: connection to server at "127.0.0.1", port 5432 failed: '
            "Connection refused\n\tIs the server running on that host and accepting "
            "TCP/IP connections?"
        ),
        id="recusada_psycopg",
    ),
    pytest.param(
        psycopg.OperationalError(
            'connection to server at "10.0.0.5", port 5432 failed: Connection refused'
        ),
        id="recusada",
    ),
    pytest.param(
        psycopg.OperationalError("server closed the connection unexpectedly"), id="fechou"
    ),
    pytest.param(
        psycopg.OperationalError("terminating connection due to administrator command"),
        id="terminando",
    ),
    pytest.param(psycopg.OperationalError("consuming input failed: EOF"), id="perdida"),
    pytest.param(psycopg.errors.AdminShutdown("terminating connection"), id="57P01"),
    pytest.param(psycopg.errors.CrashShutdown("crash"), id="57P02"),
    pytest.param(psycopg.errors.CannotConnectNow("starting up"), id="57P03"),
]


@pytest.mark.parametrize("erro", ERROS_DE_RECURSO_LOCAL)
def test_falta_de_recurso_local_nao_e_prova_de_queda(erro: Exception) -> None:
    """claude-review do PR #463: `OperationalError` SEM sqlstate contava sempre como prova,
    e `EMFILE` (descritores esgotados -- provocavel por um cliente que abre conexoes demais
    com o piloto), `ENFILE`, `ENOMEM` e `ENOBUFS` caem nesse ramo sem o banco ser consultado.
    Contados como queda, abriam o disjuntor e o gate liberava rota sem checar permissao."""
    assert mod._prova_de_queda(erro) is False


@pytest.mark.parametrize("erro", SINAIS_REAIS_DE_QUEDA)
def test_sinais_reais_de_queda_continuam_sendo_prova(erro: Exception) -> None:
    """O outro lado: host que deixa de resolver (no Docker, o nome do servico some quando o
    container para -- o sinal medido nas revisoes), recusa, conexao fechada/perdida e os
    SQLSTATE 57P0x seguem provando a queda."""
    assert mod._prova_de_queda(erro) is True


@pytest.mark.parametrize("erro", ERROS_DE_RECURSO_LOCAL)
@pytest.mark.parametrize("abrir", ["leitura", "escrita"])
def test_falta_de_recurso_local_vira_sem_prova_e_nao_carimba(
    monkeypatch: pytest.MonkeyPatch, erro: Exception, abrir: str
) -> None:
    _instalar(monkeypatch, _ConexaoQueFalha(erro))
    with pytest.raises(db.BancoSemProvaDeQueda):
        with db.conexao() if abrir == "leitura" else db.transacao(id_usuario=1) as con:
            con.execute("SELECT 1")
    assert not acesso.banco_em_falha()


@pytest.mark.parametrize("erro", ERROS_DE_RECURSO_LOCAL)
def test_gate_com_falta_de_recurso_local_responde_503_e_nao_degrada(
    monkeypatch: pytest.MonkeyPatch, erro: Exception
) -> None:
    """Ponta a ponta pelo middleware: falta de recurso local e' 503 em toda rota controlada,
    nunca a liberacao das nao sensiveis."""
    _instalar(monkeypatch, _ConexaoQueFalha(erro))
    monkeypatch.setenv("MOTOR_CADASTRO_DIR", "/app/cadastro")

    def rodar(caminho: str) -> int:
        return asyncio.run(
            pilot._controle_de_acesso_por_aba(_Requisicao(caminho), _proximo)
        ).status_code

    assert rodar("/api/uf/SP") == 503
    assert rodar("/api/pin-concorrente/1") == 503
    assert rodar("/api/rede/carteira") == 503
    assert not acesso.banco_em_falha()


def test_conexao_do_pool_nao_registra_recusa_por_falta_de_recurso_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem isto, `EMFILE` ao abrir o socket carimbava "o servidor recusou", e o `PoolTimeout`
    seguinte virava prova de queda pela outra porta."""
    classe = mod._classe_de_conexao()
    erros: list[Exception] = []

    def conectar(cls: Any, *_a: Any, **_k: Any) -> Any:
        raise erros[-1]

    monkeypatch.setattr(psycopg.Connection, "connect", classmethod(conectar))
    erros.append(psycopg.OperationalError("could not create socket: Too many open files"))
    with pytest.raises(psycopg.OperationalError):
        classe.connect("host=x")
    assert mod._ultima_recusa == 0
    erros.append(
        psycopg.OperationalError(
            'could not translate host name "postgres" to address: Name or service not known'
        )
    )
    with pytest.raises(psycopg.OperationalError):
        classe.connect("host=x")
    assert mod._ultima_recusa > 0
