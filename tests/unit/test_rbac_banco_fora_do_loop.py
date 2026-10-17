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

import asyncio
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

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


@pytest.mark.parametrize("erro", ERROS_OPERACIONAIS)
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
    _instalar(monkeypatch, _ConexaoQueFalha(psycopg.errors.LockNotAvailable("lock timeout")))
    monkeypatch.setenv("MOTOR_CADASTRO_DIR", "/app/cadastro")

    def rodar(caminho: str) -> int:
        return asyncio.run(
            pilot._controle_de_acesso_por_aba(_Requisicao(caminho), _proximo)
        ).status_code

    assert rodar("/api/uf/SP") == 200
    assert rodar("/api/rede/carteira") == 403


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
