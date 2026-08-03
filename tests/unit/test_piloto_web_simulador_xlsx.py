"""Contrato do endpoint do simulador financeiro em XLSX (POST /api/simulador/xlsx).

Pedido do dono do produto (Felipe, 2026-07-24): baixar do piloto uma planilha COMPLETA
do cenario (DRE, folha de pagamento, fluxo de caixa) com FORMULAS VIVAS, para abrir na
frente do investidor e editar as premissas ali mesmo. Este arquivo cobre o CANO — a
rota, o content-type, os bytes binarios e o nome do arquivo — nao a planilha em si (a
montagem vive em `motor_expansao.dimensionamento.simulador_xlsx`).

Como os testes chamam o backend:
  - Sem `TestClient`: o CI instala `.[dev,api_mvp]`, que NAO tem `httpx` (mesma razao
    pela qual `test_piloto_web_api.py` chama as rotas direto). Aqui a chamada e pelo
    proprio protocolo ASGI (`_pedir`), o que exercita a pilha INTEIRA do FastAPI —
    inclusive a validacao de corpo que devolve 422 — sem dependencia nova.
  - O gerador do XLSX e substituido por um stub: o teste tem de ser rapido e nao pode
    depender do modulo do motor, que nasceu em paralelo a esta rota.
"""

from __future__ import annotations

import ast
import asyncio
import json
import sys
import threading
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import pytest

_REPO = Path(__file__).resolve().parents[2]  # tests/unit/ -> raiz do worktree
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402  (backend do piloto; web/server no sys.path acima)

_ROTA = "/api/simulador/xlsx"
_MEDIA_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
# Assinatura de um container ZIP — todo .xlsx e um ZIP (OOXML). Se o corpo nao comeca
# com isso, o Excel recusa o arquivo.
_ZIP_MAGIC = b"PK\x03\x04"

# Caso golden do ciclo (Boulevard Londrina): os mesmos inputs do /api/viabilidade.
_INPUTS: dict[str, Any] = {
    "lat": -23.31,
    "lng": -51.16,
    "m2": 1050,
    "aluguel": 30000,
    "demanda": 2304,
    "ticket": 147,
    "rampa_meses": 8,
    "obra": 600000,
    "parcelas_obra": 4,
    "equipamentos": 1400000,
    "prazo_equipamentos": 60,
    "juros_equipamentos_am": 0.018,
    "taxa_franquia": 160000,
}


# ---------------------------------------------------------------------------
# Chamada HTTP real, pelo protocolo ASGI (sem httpx / sem subir servidor)
# ---------------------------------------------------------------------------


def _pedir(
    caminho: str, corpo: dict[str, Any] | None = None, **query: str
) -> tuple[int, dict[str, str], bytes]:
    """POST no app ASGI. Devolve (status, headers, corpo em bytes)."""
    body = json.dumps(corpo or {}).encode("utf-8")
    qs = urlencode(query).encode("ascii")
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": caminho,
        "raw_path": caminho.encode("ascii"),
        "query_string": qs,
        "root_path": "",
        "headers": [
            (b"host", b"testserver"),
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
        ],
        "client": ("127.0.0.1", 51234),
        "server": ("testserver", 80),
    }

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": body, "more_body": False}

    recebidas: list[dict[str, Any]] = []

    async def send(msg: dict[str, Any]) -> None:
        recebidas.append(msg)

    asyncio.run(pilot.app(scope, receive, send))

    inicio = next(m for m in recebidas if m["type"] == "http.response.start")
    headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in inicio["headers"]}
    conteudo = b"".join(
        m.get("body", b"") for m in recebidas if m["type"] == "http.response.body"
    )
    return int(inicio["status"]), headers, conteudo


# ---------------------------------------------------------------------------
# Stub do gerador (o modulo real vive no motor e monta a planilha de verdade)
# ---------------------------------------------------------------------------


def _xlsx_de_verdade() -> bytes:
    """Um .xlsx minimo, REAL, em memoria.

    De proposito nao e um `b"PK..."` falso: assim a checagem da assinatura ZIP prova
    que o cano entrega os bytes intactos (sem virar texto/base64 pelo caminho), e nao
    apenas que o stub devolveu a constante do teste.
    """
    import openpyxl

    wb = openpyxl.Workbook()
    wb.active["A1"] = "=1+1"  # formula viva, como a planilha de verdade
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture
def gerador_stub(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Troca o gerador do motor por um stub que registra o que recebeu."""
    visto: dict[str, Any] = {}

    def stub(demanda: float, premissas: Any, investimento: dict[str, Any], **extras: Any) -> bytes:
        visto["demanda"] = demanda
        visto["premissas"] = premissas
        visto["investimento"] = investimento
        visto["extras"] = extras
        visto["thread"] = threading.get_ident()
        return _xlsx_de_verdade()

    monkeypatch.setattr(pilot, "_gerador_simulador_xlsx", lambda: stub)
    return visto


# ===========================================================================
# 1) A rota existe e entrega um XLSX
# ===========================================================================


def test_rota_registrada_no_app() -> None:
    """A rota tem de estar montada no app — o gerador ja existia no repo e nunca
    esteve exposto no piloto (nenhum endpoint, nenhum botao)."""
    rotas = {
        (r.path, metodo)
        for r in pilot.app.routes
        for metodo in getattr(r, "methods", set()) or set()
    }
    assert (_ROTA, "POST") in rotas


def test_devolve_xlsx_binario_com_content_type_e_nome(gerador_stub: dict[str, Any]) -> None:
    status, headers, corpo = _pedir(_ROTA, _INPUTS)

    assert status == 200
    assert headers["content-type"] == _MEDIA_XLSX
    # Corpo binario de OOXML (ZIP), nao JSON nem texto.
    assert corpo.startswith(_ZIP_MAGIC)
    disp = headers["content-disposition"]
    assert disp.startswith("attachment;")
    assert disp.endswith('.xlsx"')
    assert "simulador_viabilidade" in disp


def test_nome_do_arquivo_e_slug_ascii_falante(gerador_stub: dict[str, Any]) -> None:
    """O nome do arquivo e a excecao ASCII do §2 do CLAUDE.md: texto de usuario leva
    acento, nome de arquivo NAO (acento no Content-Disposition sai mojibake)."""
    _status, headers, _corpo = _pedir(
        _ROTA, _INPUTS, rotulo="Boulevard Shopping Londrina - Âncora L2"
    )
    disp = headers["content-disposition"]
    assert disp == (
        'attachment; filename="simulador_viabilidade_boulevard-shopping-londrina-ancora-l2.xlsx"'
    )
    assert disp.isascii()


def test_sem_rotulo_o_nome_cai_num_default_estavel(gerador_stub: dict[str, Any]) -> None:
    _status, headers, _corpo = _pedir(_ROTA, _INPUTS)
    assert 'filename="simulador_viabilidade_cenario.xlsx"' in headers["content-disposition"]


@pytest.mark.parametrize(
    "rotulo,esperado",
    [
        ("Ponto 3 — Zona Sul", "ponto-3-zona-sul"),
        ("   ", "cenario"),  # so espaco -> default, nunca nome vazio
        ("...///", "cenario"),  # so pontuacao -> default
        ("ÁÉÍÓÚ Ção", "aeiou-cao"),
    ],
)
def test_slug_arquivo(rotulo: str, esperado: str) -> None:
    assert pilot._slug_arquivo(rotulo) == esperado


# ===========================================================================
# 2) Reuso: a rota NAO reimplementa a conversao do corpo
# ===========================================================================


def test_reusa_premissas_e_investimento_do_viabilidade(gerador_stub: dict[str, Any]) -> None:
    """O gerador recebe exatamente o que `_premissas_do_body`/`_investimento` produzem.

    E a regressao do anti-padrao que o FIN-VIAB-01 existe para matar: uma segunda
    conversao de corpo -> premissas viveria em paralelo e divergiria do /api/viabilidade.
    """
    status, _headers, _corpo = _pedir(_ROTA, _INPUTS)
    assert status == 200

    body = pilot.ViabilidadeIn(**_INPUTS)
    premissas_esperadas = pilot._premissas_do_body(body)
    inv_esperado = pilot._investimento(body)

    assert gerador_stub["demanda"] == pytest.approx(2304.0)
    assert gerador_stub["premissas"] == premissas_esperadas
    assert gerador_stub["investimento"] == inv_esperado
    # Sanity dos numeros do caso golden (Boulevard Londrina).
    assert gerador_stub["premissas"].ticket_cheio == pytest.approx(147.0)
    assert gerador_stub["premissas"].aluguel_mes == pytest.approx(30_000.0)
    assert gerador_stub["investimento"]["obra"] == pytest.approx(600_000.0)
    assert gerador_stub["investimento"]["equipamentos"] == pytest.approx(1_400_000.0)
    assert gerador_stub["investimento"]["taxa_franquia"] == pytest.approx(160_000.0)


def test_extras_opcionais_nao_quebram_gerador_enxuto(monkeypatch: pytest.MonkeyPatch) -> None:
    """Um gerador que aceita SO os 3 argumentos essenciais tem de funcionar.

    Os extras (`rotulo`/`m2`) sao enfeite de cabecalho da planilha; a rota os filtra
    pela assinatura do gerador. Sem esse filtro, um nome diferente do outro lado viraria
    TypeError -> HTTP 500 no lugar do arquivo.
    """

    def gerador_minimo(demanda: float, premissas: Any, investimento: dict[str, Any]) -> bytes:
        return _xlsx_de_verdade()

    monkeypatch.setattr(pilot, "_gerador_simulador_xlsx", lambda: gerador_minimo)
    status, headers, corpo = _pedir(_ROTA, _INPUTS, rotulo="Ponto A")
    assert status == 200
    assert corpo.startswith(_ZIP_MAGIC)
    assert headers["content-type"] == _MEDIA_XLSX


# ===========================================================================
# 3) Corpo invalido -> 422 (validacao do FastAPI, nao 500)
# ===========================================================================


@pytest.mark.parametrize(
    "corpo",
    [
        {},  # sem nada
        {k: v for k, v in _INPUTS.items() if k != "demanda"},  # falta a premissa central
        {**_INPUTS, "demanda": 0},  # demanda tem de ser > 0
        {**_INPUTS, "m2": -1},  # metragem negativa
        {**_INPUTS, "aluguel": "trinta mil"},  # tipo errado
        {**_INPUTS, "n_studios": 9},  # fora do 0..3
    ],
)
def test_corpo_invalido_devolve_422(corpo: dict[str, Any], gerador_stub: dict[str, Any]) -> None:
    status, _headers, _resposta = _pedir(_ROTA, corpo)
    assert status == 422
    # E o gerador nem foi chamado: nao se monta planilha de cenario invalido.
    assert not gerador_stub


# ===========================================================================
# 4) Degradacao graciosa e event loop livre
# ===========================================================================


def test_modulo_do_gerador_ausente_devolve_503(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem o modulo do motor a rota responde 503 com mensagem clara, nao 500 cru."""
    monkeypatch.setitem(sys.modules, "motor_expansao.dimensionamento.simulador_xlsx", None)
    status, _headers, corpo = _pedir(_ROTA, _INPUTS)
    assert status == 503
    assert "simulador_xlsx" in corpo.decode("utf-8")


def test_geracao_roda_no_threadpool_nao_no_event_loop(gerador_stub: dict[str, Any]) -> None:
    """A montagem e SINCRONA e pesada; rodando no event loop ela travaria o unico worker
    do uvicorn e toda outra requisicao ficaria na fila (foi o defeito medido no PDF em
    2026-07-24). Prova: o gerador executa em OUTRA thread que a do event loop."""
    thread_do_loop: dict[str, int] = {}

    async def rodar() -> None:
        thread_do_loop["ident"] = threading.get_ident()
        await pilot.simulador_xlsx(pilot.ViabilidadeIn(**_INPUTS), None)

    asyncio.run(rodar())
    assert gerador_stub["thread"] != thread_do_loop["ident"]


# ===========================================================================
# 5) Guardrail READ-ONLY (AST): a rota nova nao escreve em disco
# ===========================================================================

# A planilha sai em BytesIO. Um `to_excel`/`to_csv` aqui seria arquivo temporario no
# servidor (e, no caminho de um artefato, escrita sobre o M1).
_ESCRITORES_PROIBIDOS = {"to_parquet", "to_csv", "to_excel", "to_pickle", "to_feather"}


def test_backend_nao_escreve_arquivo_por_ast() -> None:
    tree = ast.parse((_SERVER / "app.py").read_text(encoding="utf-8"))
    ofensas = [
        (node.func.attr, node.lineno)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in _ESCRITORES_PROIBIDOS
    ]
    assert not ofensas, f"o backend do piloto escreve em disco: {ofensas}"
