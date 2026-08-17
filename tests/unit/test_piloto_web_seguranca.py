"""Travas de seguranca do backend do piloto web (BLK-SEC-05).

Cobrem:
  - guardrail path-traversal em `_uf_partition` (sink de todas as leituras por UF) e
    na validacao de fronteira do `RelatorioMunicipalIn.uf`;
  - tetos anti-DoS de upload de foto (constantes).

Segue o padrao de `test_piloto_web_api.py`: poe `web/server` no sys.path e chama as
funcoes direto (sem TestClient/httpx).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot_app  # noqa: E402  (backend do piloto; web/server no sys.path acima)
from fastapi import HTTPException  # noqa: E402
from pydantic import ValidationError  # noqa: E402


@pytest.mark.parametrize(
    "mau",
    ["../../etc/passwd", "x/../../y", "S/P", "abc", "s", "12", "..", "SP/..", "", "  "],
)
def test_uf_partition_recusa_uf_perigosa(mau: str) -> None:
    with pytest.raises(HTTPException) as exc:
        pilot_app._uf_partition(mau)
    assert exc.value.status_code == 400


@pytest.mark.parametrize("uf", ["SP", "sp", "Rj", "MG"])
def test_uf_partition_aceita_sigla_valida(uf: str) -> None:
    part = pilot_app._uf_partition(uf)
    assert part.name == f"uf={uf.upper()}"  # so a sigla normalizada compoe o caminho


@pytest.mark.parametrize("mau", ["../../etc", "ABC", "S", "s/p", "12"])
def test_relatorio_municipal_in_recusa_uf_invalida(mau: str) -> None:
    with pytest.raises(ValidationError):
        pilot_app.RelatorioMunicipalIn(uf=mau, municipio="Cidade")


def test_relatorio_municipal_in_aceita_uf_valida() -> None:
    modelo = pilot_app.RelatorioMunicipalIn(uf="sp", municipio="Campinas")
    assert modelo.uf == "sp"
    assert modelo.municipio == "Campinas"


def test_relatorio_municipal_in_recusa_municipio_absurdo() -> None:
    with pytest.raises(ValidationError):
        pilot_app.RelatorioMunicipalIn(uf="SP", municipio="x" * 500)


def test_limites_de_foto_sao_sensatos() -> None:
    assert pilot_app._FOTOS_MAX >= 2  # o PDF usa 2; sobra margem minima
    assert 0 < pilot_app._FOTO_MAX_BYTES <= 32 * 1024 * 1024
