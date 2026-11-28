"""Cache-Control dos estaticos da SPA (B11 do pentest de 11/2026).

`_EstaticosDaSpa` carimba `immutable` nos diretorios com hash (`/assets/`, `/entrar-assets/`,
`/portal-assets/`) e `no-cache` no resto -- no 200 E no 304, e nunca no 404.

Monta a propria `_EstaticosDaSpa` sobre um dist temporario e a chama pelo protocolo ASGI cru
(sem httpx). Em producao o mount so' existe quando `dist/` existe (`if _DIST_DIR.is_dir()`),
que o CI nao tem; por isso o teste constroi o seu.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import pytest
from starlette.exceptions import HTTPException

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402


def _dist(tmp: Path) -> Path:
    (tmp / "assets").mkdir()
    (tmp / "assets" / "app-abc123.js").write_text("console.log(1)", encoding="utf-8")
    (tmp / "index.html").write_text("<!doctype html><title>x</title>", encoding="utf-8")
    return tmp


def _get(estaticos: Any, caminho: str, extra: dict[bytes, bytes] | None = None) -> tuple[int, dict[str, str]]:
    headers = [(b"host", b"testserver")]
    headers += list((extra or {}).items())
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
        "headers": headers,
        "client": ("127.0.0.1", 51234),
        "server": ("testserver", 443),
    }

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    recebidas: list[dict[str, Any]] = []

    async def send(msg: dict[str, Any]) -> None:
        recebidas.append(msg)

    asyncio.run(estaticos(scope, receive, send))
    inicio = next(m for m in recebidas if m["type"] == "http.response.start")
    hdr = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in inicio["headers"]}
    return int(inicio["status"]), hdr


def test_index_vai_no_cache(tmp_path: Path) -> None:
    est = pilot._EstaticosDaSpa(directory=str(_dist(tmp_path)), html=True)
    status, hdr = _get(est, "/")
    assert status == 200
    assert hdr["cache-control"] == "no-cache"


def test_asset_com_hash_e_imutavel(tmp_path: Path) -> None:
    est = pilot._EstaticosDaSpa(directory=str(_dist(tmp_path)), html=True)
    status, hdr = _get(est, "/assets/app-abc123.js")
    assert status == 200
    assert hdr["cache-control"] == "public, max-age=31536000, immutable"


def test_asset_com_hash_imutavel_tambem_no_304(tmp_path: Path) -> None:
    est = pilot._EstaticosDaSpa(directory=str(_dist(tmp_path)), html=True)
    _, hdr = _get(est, "/assets/app-abc123.js")
    etag = hdr["etag"]
    status, hdr304 = _get(est, "/assets/app-abc123.js", {b"if-none-match": etag.encode("ascii")})
    assert status == 304
    assert hdr304["cache-control"] == "public, max-age=31536000, immutable"


def test_inexistente_nao_passa_por_file_response(tmp_path: Path) -> None:
    """O 404 do `StaticFiles` e' levantado ANTES de `file_response` -- onde mora o
    `immutable`. Logo, um caminho inexistente sob `/assets/` nunca recebe o cabecalho. Em
    producao o mount vive num app com tratador de excecao, que vira o 404 em resposta sem
    `immutable`; aqui, chamado direto, a `HTTPException` prova que `file_response` nao roda."""
    est = pilot._EstaticosDaSpa(directory=str(_dist(tmp_path)), html=True)
    with pytest.raises(HTTPException) as exc:
        _get(est, "/assets/naoexiste-xyz.js")
    assert exc.value.status_code == 404


def test_os_prefixos_com_hash_sao_os_do_vite() -> None:
    assert pilot._PREFIXOS_COM_HASH == ("/assets/", "/entrar-assets/", "/portal-assets/")
