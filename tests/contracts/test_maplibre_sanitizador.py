"""Contrato: o maplibre-gl do lock tem o sanitizador de HTML corrigido (B2 do pentest de
11/2026, GHSA-jrc7-96c5-q579 / CVE-2026-85061).

O conserto chegou na 5.24.1 (ultima do ramo 5) e, no ramo 6, so' se completou na 6.12.0
(NamedNodeMap 6.4.1 -> ... -> lista de permissao 6.11.1 -> tag nao fechada 6.12.0). Trava o
lock para nao regredir abaixo do piso de cada ramo.
"""

from __future__ import annotations

import json
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_LOCK = _REPO / "web" / "package-lock.json"

_PISO_RAMO_5 = (5, 24, 1)
_PISO_RAMO_6 = (6, 12, 0)


def _versao_do_lock() -> tuple[int, int, int]:
    dados = json.loads(_LOCK.read_text(encoding="utf-8"))
    bruto = dados["packages"]["node_modules/maplibre-gl"]["version"]
    partes = bruto.split("-")[0].split(".")  # ignora sufixo pre-release, se houver
    return tuple(int(p) for p in partes[:3])  # type: ignore[return-value]


def test_maplibre_com_sanitizador_corrigido() -> None:
    ver = _versao_do_lock()
    maior = ver[0]
    if maior == 5:
        assert ver >= _PISO_RAMO_5, f"maplibre {ver} < {_PISO_RAMO_5} (ramo 5 sem o conserto)"
    elif maior == 6:
        assert ver >= _PISO_RAMO_6, f"maplibre {ver} < {_PISO_RAMO_6} (ramo 6 sem o sanitizador completo)"
    else:
        assert maior >= 7, f"maplibre {ver}: ramo inesperado/antigo"
