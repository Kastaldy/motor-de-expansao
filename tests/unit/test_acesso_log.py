"""Trilha de acesso do piloto web (DEC-027) — gravador + middleware.

Cobre o modulo `motor_expansao.dashboard.acesso_log` (filtro de ruido,
normalizacao com tetos, JSONL diario, poda de retencao, resiliencia a falha de
disco) e o caminho fim-a-fim pelo middleware do backend — invocado DIRETO com
requisicao/resposta fake, sem TestClient/httpx, como o resto da suite do piloto.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from motor_expansao.dashboard import acesso_log

_REPO = Path(__file__).resolve().parents[2]  # tests/unit/ -> raiz do worktree
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402  (backend do piloto; web/server no sys.path acima)


@pytest.fixture(autouse=True)
def _reset_estado_do_gravador():
    """O gravador tem estado de processo (gatilho da poda + aviso unico de falha)."""
    acesso_log._ultimo_dia_podado = None
    acesso_log._avisou_falha = False
    yield


# ---------------------------------------------------------------------------
# 1) Filtro de ruido — o "sem inflar" do contrato
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "caminho",
    [
        "/api/health",
        "/assets/index-DhX2.js",
        "/assets/ibm-plex-mono-latin-400-normal.woff2",
        "/favicon.ico",
        "/logo.png",
        "/robots.txt",
        "/mapa/tiles/sprite.JPEG",
    ],
)
def test_relevante_filtra_ruido(caminho: str) -> None:
    assert not acesso_log.relevante(caminho)


@pytest.mark.parametrize(
    "caminho",
    [
        "/",
        "/api/ufs",
        "/api/rede/carteira",
        "/api/relatorio/pontual",
        "/api/viabilidade",
        "/executiva",  # deep-link do SPA (html=True devolve o index)
    ],
)
def test_relevante_mantem_acoes(caminho: str) -> None:
    assert acesso_log.relevante(caminho)


# ---------------------------------------------------------------------------
# 2) Normalizacao do evento — tetos, defaults e tipos
# ---------------------------------------------------------------------------


def test_montar_evento_normaliza_e_aplica_tetos() -> None:
    evento = acesso_log.montar_evento(
        usuario="  felipe.silva  ",
        ip="189.69.25.227",
        metodo="GET",
        rota="/api/rede/carteira",
        query="x" * 5000,
        status="200",
        duracao_ms=12.0,
        agente="a" * 500,
        tamanho="1234",
    )
    assert evento["usuario"] == "felipe.silva"
    assert evento["ip"] == "189.69.25.227"
    assert evento["metodo"] == "GET"
    assert evento["rota"] == "/api/rede/carteira"
    assert evento["status"] == 200
    assert evento["duracao_ms"] == 12
    assert evento["bytes"] == 1234
    assert len(evento["query"]) == 2000
    assert len(evento["agente"]) == 200


def test_montar_evento_defaults_sem_identidade() -> None:
    """Sem header de identidade (dev local, sem Caddy) o autor nao e' inventado."""
    evento = acesso_log.montar_evento(metodo="GET", rota="/", status=200, duracao_ms=1)
    assert evento["usuario"] == "desconhecido"
    assert evento["ip"] is None
    assert "query" not in evento
    assert "agente" not in evento
    assert "bytes" not in evento


# ---------------------------------------------------------------------------
# 3) Gravacao JSONL diaria + poda de retencao
# ---------------------------------------------------------------------------


def test_registrar_escreve_jsonl_do_dia(tmp_path: Path) -> None:
    # `antes`/`depois` cercam o relogio interno do gravador: se a suite cruzar a
    # meia-noite UTC (21h BRT) no meio, o teste continua valido em vez de flakar.
    antes = datetime.now(UTC).date()
    acesso_log.registrar({"rota": "/api/ufs", "status": 200}, base=tmp_path)
    acesso_log.registrar({"rota": "/api/ufs", "status": 200}, base=tmp_path)
    depois = datetime.now(UTC).date()

    arquivos = sorted(tmp_path.glob("acesso-*.jsonl"))
    nomes_validos = {f"acesso-{d.isoformat()}.jsonl" for d in (antes, depois)}
    assert arquivos and {a.name for a in arquivos} <= nomes_validos
    linhas = [
        linha for a in arquivos for linha in a.read_text(encoding="utf-8").splitlines()
    ]
    assert len(linhas) == 2
    registro = json.loads(linhas[0])
    assert registro["rota"] == "/api/ufs"
    assert registro["status"] == 200
    assert registro["quando"][:10] in {antes.isoformat(), depois.isoformat()}


def test_poda_remove_apenas_antigos_com_o_padrao_proprio(tmp_path: Path) -> None:
    hoje = datetime.now(UTC).date()
    antigo = tmp_path / "acesso-2020-01-01.jsonl"
    recente = tmp_path / f"acesso-{(hoje - timedelta(days=1)).isoformat()}.jsonl"
    alheio = tmp_path / "cadastro_log.jsonl"  # jamais tocar arquivo fora do padrao
    invalido = tmp_path / "acesso-9999-99-99.jsonl"  # padrao ok, data impossivel
    for arquivo in (antigo, recente, alheio, invalido):
        arquivo.write_text("{}\n", encoding="utf-8")

    acesso_log.registrar({"rota": "/", "status": 200}, base=tmp_path)

    assert not antigo.exists(), "alem da retencao (90d) e' podado"
    assert recente.exists()
    assert alheio.exists()
    assert invalido.exists()


def test_poda_preserva_o_dia_limite_exato(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Fronteira da retencao: exatamente `hoje - 90d` ainda esta DENTRO do prazo."""
    monkeypatch.delenv("MOTOR_ACESSO_RETENCAO_DIAS", raising=False)
    hoje = date(2026, 8, 17)  # `_podar` recebe o dia: a fronteira fica deterministica
    no_limite = tmp_path / f"acesso-{(hoje - timedelta(days=90)).isoformat()}.jsonl"
    alem = tmp_path / f"acesso-{(hoje - timedelta(days=91)).isoformat()}.jsonl"
    for arquivo in (no_limite, alem):
        arquivo.write_text("{}\n", encoding="utf-8")

    acesso_log._podar(tmp_path, hoje)

    assert no_limite.exists(), "o arquivo do dia-limite exato nao pode ser podado (`<`, nao `<=`)"
    assert not alem.exists()


def test_poda_roda_uma_vez_por_dia_e_reativa_na_virada(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """O gate `_ultimo_dia_podado`: poda so' na 1a escrita do dia; virada reativa."""
    chamadas: list[object] = []
    monkeypatch.setattr(acesso_log, "_podar", lambda *args: chamadas.append(args))

    acesso_log.registrar({"rota": "/", "status": 200}, base=tmp_path)
    acesso_log.registrar({"rota": "/", "status": 200}, base=tmp_path)
    assert len(chamadas) == 1, "2a escrita do MESMO dia nao pode rodar a poda de novo"

    acesso_log._ultimo_dia_podado = datetime.now(UTC).date() - timedelta(days=1)
    acesso_log.registrar({"rota": "/", "status": 200}, base=tmp_path)
    assert len(chamadas) == 2, "virada de dia tem de reativar a poda"


def test_retencao_dias_configuravel_com_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MOTOR_ACESSO_RETENCAO_DIAS", raising=False)
    assert acesso_log.retencao_dias() == acesso_log.RETENCAO_DIAS_DEFAULT
    monkeypatch.setenv("MOTOR_ACESSO_RETENCAO_DIAS", "30")
    assert acesso_log.retencao_dias() == 30
    for invalido in ("0", "-5", "abc"):
        monkeypatch.setenv("MOTOR_ACESSO_RETENCAO_DIAS", invalido)
        assert acesso_log.retencao_dias() == acesso_log.RETENCAO_DIAS_DEFAULT


def test_registrar_nunca_levanta_com_destino_invalido(tmp_path: Path) -> None:
    """Rastro, nao transacao: volume ausente/errado nao pode derrubar a requisicao."""
    destino = tmp_path / "nao_e_diretorio"
    destino.write_text("ocupado", encoding="utf-8")  # mkdir() vai falhar com OSError
    acesso_log.registrar({"rota": "/", "status": 200}, base=destino)  # nao levanta


def test_default_do_diretorio_e_data_acesso_log_na_raiz(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem a env var (dev local), o default tem de cair em `<repo>/data/acesso_log` —
    que e' o caminho coberto pelo .gitignore. O `parents[3]` do modulo e' posicional;
    este teste trava a resolucao contra mudanca de layout do src/."""
    monkeypatch.delenv("MOTOR_ACESSO_LOG_DIR", raising=False)
    assert acesso_log.acesso_log_dir() == _REPO / "data" / "acesso_log"


# ---------------------------------------------------------------------------
# 4) Fim-a-fim: o middleware do backend, invocado DIRETO (sem TestClient)
# ---------------------------------------------------------------------------


class _Cabecalhos:
    """`.get` case-insensitive, como o Headers do Starlette."""

    def __init__(self, bruto: dict[str, str]):
        self._bruto = {chave.lower(): valor for chave, valor in bruto.items()}

    def get(self, chave: str, default: str | None = None) -> str | None:
        return self._bruto.get(chave.lower(), default)


class _Url:
    def __init__(self, caminho: str, query: str):
        self.path = caminho
        self.query = query


class _Cliente:
    def __init__(self, host: str):
        self.host = host


class _Requisicao:
    def __init__(
        self,
        caminho: str,
        headers: dict[str, str] | None = None,
        metodo: str = "GET",
        query: str = "",
        host: str = "172.19.0.5",
    ):
        self.url = _Url(caminho, query)
        self.headers = _Cabecalhos(headers or {})
        self.method = metodo
        self.client = _Cliente(host)


class _Resposta:
    status_code = 200
    headers = {"content-length": "42"}  # so precisa de `.get`


def _rodar_middleware(requisicao: _Requisicao, falhar: bool = False) -> object:
    async def _proximo(_req: object) -> _Resposta:
        if falhar:
            raise RuntimeError("explodiu no handler")
        return _Resposta()

    return asyncio.run(pilot._trilha_acesso(requisicao, _proximo))


def _linhas_da_trilha(diretorio: Path) -> list[dict[str, object]]:
    linhas: list[dict[str, object]] = []
    for arquivo in sorted(diretorio.glob("acesso-*.jsonl")):
        for bruta in arquivo.read_text(encoding="utf-8").splitlines():
            linhas.append(json.loads(bruta))
    return linhas


def test_middleware_esta_registrado_no_app() -> None:
    """Trava o `@app.middleware("http")`: sem isto, remover o decorator deixaria a
    suite verde com a trilha morta em producao (os demais testes chamam a funcao
    direto). Falso-verde reproduzido na revisao adversarial de 2026-08-17."""
    dispatches = [
        getattr(m, "kwargs", {}).get("dispatch") for m in pilot.app.user_middleware
    ]
    assert pilot._trilha_acesso in dispatches, (
        "middleware da trilha de acesso nao esta registrado no app"
    )


def test_middleware_registra_usuario_ip_e_latencia(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    trilha = tmp_path / "trilha"
    monkeypatch.setenv("MOTOR_ACESSO_LOG_DIR", str(trilha))

    requisicao = _Requisicao(
        "/api/rede/carteira",
        headers={
            "Remote-User": "felipe.silva",
            "X-Forwarded-For": "189.69.25.227, 172.19.0.5",
            "User-Agent": "pytest",
        },
        query="inicio=2026-08-01&fim=2026-08-16",
    )
    resposta = _rodar_middleware(requisicao)

    assert isinstance(resposta, _Resposta), "middleware devolve a resposta do handler"
    registros = _linhas_da_trilha(trilha)
    assert len(registros) == 1
    registro = registros[0]
    assert registro["usuario"] == "felipe.silva"
    # Pentest Onda A (2026-08-19): o Caddy ANEXA o peer real ao FIM do X-Forwarded-For;
    # os tokens a esquerda sao forjaveis pelo cliente. O IP da trilha e' o ULTIMO hop.
    assert registro["ip"] == "172.19.0.5", "ultimo hop do X-Forwarded-For = anexado pelo Caddy"
    assert registro["metodo"] == "GET"
    assert registro["rota"] == "/api/rede/carteira"
    assert registro["query"] == "inicio=2026-08-01&fim=2026-08-16"
    assert registro["status"] == 200
    assert registro["bytes"] == 42
    assert registro["agente"] == "pytest"
    assert isinstance(registro["duracao_ms"], int) and registro["duracao_ms"] >= 0


def test_middleware_sem_caddy_cai_no_ip_do_socket_e_desconhecido(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    trilha = tmp_path / "trilha"
    monkeypatch.setenv("MOTOR_ACESSO_LOG_DIR", str(trilha))

    _rodar_middleware(_Requisicao("/api/ufs", host="127.0.0.1"))

    (registro,) = _linhas_da_trilha(trilha)
    assert registro["usuario"] == "desconhecido"
    assert registro["ip"] == "127.0.0.1"


def test_middleware_ignora_health_e_estaticos(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    trilha = tmp_path / "trilha"
    monkeypatch.setenv("MOTOR_ACESSO_LOG_DIR", str(trilha))

    for caminho in ("/api/health", "/assets/index-abc.js", "/favicon.ico"):
        _rodar_middleware(_Requisicao(caminho))

    assert not trilha.exists(), "ruido de maquina/estatico fica fora da trilha"


def test_middleware_registra_erro_e_propaga(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Excecao nao tratada vira 500 la fora; a trilha registra ANTES de propagar."""
    trilha = tmp_path / "trilha"
    monkeypatch.setenv("MOTOR_ACESSO_LOG_DIR", str(trilha))

    with pytest.raises(RuntimeError):
        _rodar_middleware(_Requisicao("/api/viabilidade", metodo="POST"), falhar=True)

    (registro,) = _linhas_da_trilha(trilha)
    assert registro["status"] == 500
    assert registro["rota"] == "/api/viabilidade"


def test_middleware_nao_derruba_requisicao_com_trilha_quebrada(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ocupado = tmp_path / "arquivo"
    ocupado.write_text("ocupado", encoding="utf-8")
    monkeypatch.setenv("MOTOR_ACESSO_LOG_DIR", str(ocupado))

    resposta = _rodar_middleware(_Requisicao("/api/ufs"))
    assert isinstance(resposta, _Resposta), "falha da trilha nao pode virar 500"
