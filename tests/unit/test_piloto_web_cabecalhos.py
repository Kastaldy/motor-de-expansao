"""Cabecalhos de seguranca do piloto web: CSP (Report-Only), COOP e CORP (B1/B12 do
pentest de 11/2026).

Chama o app ASGI pelo protocolo cru (sem httpx / sem subir servidor), como a familia
`test_piloto_web_*`. O middleware `_cabecalhos_de_seguranca` so' roda pela pilha ASGI, nao
chamando a funcao de rota direto -- por isso aqui vai pelo `pilot.app`.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import re
import sys
from pathlib import Path
from typing import Any

from starlette.responses import Response

_REPO = Path(__file__).resolve().parents[2]  # tests/unit/ -> raiz do worktree
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402  (backend do piloto; web/server no sys.path acima)


def _get(caminho: str) -> tuple[int, dict[str, str], bytes]:
    """GET no app ASGI. Devolve (status, headers minusculos, corpo)."""
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": caminho,
        "raw_path": caminho.encode("ascii"),
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"testserver")],
        "client": ("127.0.0.1", 51234),
        "server": ("testserver", 443),
    }

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    recebidas: list[dict[str, Any]] = []

    async def send(msg: dict[str, Any]) -> None:
        recebidas.append(msg)

    asyncio.run(pilot.app(scope, receive, send))
    inicio = next(m for m in recebidas if m["type"] == "http.response.start")
    headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in inicio["headers"]}
    corpo = b"".join(m.get("body", b"") for m in recebidas if m["type"] == "http.response.body")
    return int(inicio["status"]), headers, corpo


def test_csp_report_only_no_health() -> None:
    status, headers, _ = _get("/api/health")
    assert status == 200
    # Fase 1: RELATA, nao bloqueia -> nunca o cabecalho de aplicar.
    assert "content-security-policy" not in headers
    csp = headers["content-security-policy-report-only"]
    assert pilot._HASH_SCRIPT_TEMA in csp
    assert "script-src 'self' '" + pilot._HASH_SCRIPT_TEMA + "'" in csp
    assert "'unsafe-inline'" not in csp
    assert "'unsafe-eval'" not in csp
    assert "worker-src 'self' blob:" in csp
    assert "basemaps.cartocdn.com" in csp  # tiles/estilos da CARTO no connect/img
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp


def test_coop_corp_no_health() -> None:
    _, headers, _ = _get("/api/health")
    assert headers["cross-origin-opener-policy"] == "same-origin"
    assert headers["cross-origin-resource-policy"] == "same-origin"


def test_o_hash_bate_com_os_tres_bootstraps() -> None:
    """O hash cravado em `_HASH_SCRIPT_TEMA` e' o sha256 (base64) dos bytes LF entre
    `<script>` e `</script>` -- e os 3 HTML tem o MESMO script de tema. Se alguem editar o
    bootstrap sem recalcular, a fase 2 da CSP o bloquearia; este teste pega antes."""
    for nome in ("index.html", "entrar.html", "portal.html"):
        html = (_REPO / "web" / nome).read_text(encoding="utf-8")
        m = re.search(r"<script>(.*?)</script>", html, re.S)
        assert m, f"{nome} sem <script> de tema"
        corpo = m.group(1).replace("\r\n", "\n").encode("utf-8")
        calc = "sha256-" + base64.b64encode(hashlib.sha256(corpo).digest()).decode()
        assert calc == pilot._HASH_SCRIPT_TEMA, f"{nome}: hash {calc} != {pilot._HASH_SCRIPT_TEMA}"


def test_rota_com_csp_propria_e_preservada() -> None:
    """A pagina de confirmacao do SSO manda a PROPRIA CSP; o middleware (setdefault por `in`)
    nao pode sobrescreve-la nem acrescentar a Report-Only."""
    propria = Response(
        status_code=200, headers={"Content-Security-Policy": "frame-ancestors 'none'"}
    )

    async def call_next(_req: Any) -> Response:
        return propria

    saida = asyncio.run(pilot._cabecalhos_de_seguranca(None, call_next))
    assert saida.headers["content-security-policy"] == "frame-ancestors 'none'"
    assert "content-security-policy-report-only" not in saida.headers
    # COOP/CORP entram por setdefault, mesmo com CSP propria.
    assert saida.headers["cross-origin-opener-policy"] == "same-origin"
