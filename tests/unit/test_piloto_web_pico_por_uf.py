"""O piloto resolve o ESTADO do ponto para o padrão do pico (emenda de 2026-10-29 da DEC-078).

A resolução é pela malha municipal (a mesma do catchment e do `/api/ponto`) e NUNCA derruba a
Viabilidade: sem estado, ficam os 10 do motor, como antes da emenda.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402  (backend do piloto; web/server no sys.path acima)

from motor_expansao.api import service  # noqa: E402
from motor_expansao.dimensionamento import pico_por_uf as p  # noqa: E402


class _Malha:
    def __init__(self, resposta: object) -> None:
        self.resposta = resposta

    def resolver(self, _lat: float, _lng: float) -> object:
        if isinstance(self.resposta, Exception):
            raise self.resposta
        return self.resposta


def test_uf_do_ponto_devolve_a_sigla(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "_carregar_malha", lambda _d: _Malha(("sp", "3550308")))
    assert pilot._uf_do_ponto(-23.55, -46.63) == "SP"


@pytest.mark.parametrize("resposta", [None, RuntimeError("malha ilegível")])
def test_uf_do_ponto_nunca_derruba_a_viabilidade(
    monkeypatch: pytest.MonkeyPatch, resposta: object
) -> None:
    monkeypatch.setattr(service, "_carregar_malha", lambda _d: _Malha(resposta))
    assert pilot._uf_do_ponto(-23.55, -46.63) is None


def test_pico_padrao_do_ponto_le_o_staging_do_deploy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    p.limpar_cache()
    medicao = p.Medicao(33, 10, 60, 8, {"SP": (17, 12)}, "2026-09", (1.0,) * 12)
    p.gravar_atomico(tmp_path / p.ARQUIVO, p.montar_artefato(medicao, {"SP": 11}, {"SP": 12}))
    monkeypatch.setattr(pilot, "STAGING_DIR", tmp_path)
    monkeypatch.setattr(pilot, "_uf_do_ponto", lambda _lat, _lng: "SP")
    try:
        assert pilot._pico_padrao_do_ponto(-23.55, -46.63) == 11
    finally:
        p.limpar_cache()
