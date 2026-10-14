"""Bloco `mercado` de `GET /api/ponto` no RAIO de 1,0 km (DEC-070).

A rota roda de verdade sobre um `data/staging` SINTETICO (um hexagono no artefato de
mercado, uma academia de rede no centro do raio, uma Ultra colada no ponto); so' o motor
censitario e a malha viram stub, porque a populacao do raio e' insumo e nao o que esta sob
teste. O que se trava:

- os nomes de sempre (`sam`, `residual`, `score_residual`) agora valem para o RAIO;
- as duas parcelas do consumo entram no payload e a conta FECHA:
  `residual == max(sam - (consumo_concorrentes + consumo_ultra), 0)`;
- a Ultra e' contada pelo disco de 1 km (uma vez), nao pelo fallback de 2 km do hexagono;
- o hexagono viaja so' como auditoria;
- sem `data/staging`, consumo e residual saem `None` com motivo, nunca zero.
"""

from __future__ import annotations

import sys
from pathlib import Path

import h3
import pandas as pd
import pytest

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402

LAT, LNG = -23.55, -46.63


def _staging(dir_: Path) -> None:
    dir_.mkdir(parents=True, exist_ok=True)
    cell = h3.latlng_to_cell(LAT, LNG, 7)
    pd.DataFrame({
        "hex_id": [cell],
        "faixa_oportunidade": ["prioridade_maxima"],
        "taxa_fitness_mercado_calibrada": [0.2],
        "sam_fitness_potencial": [12_000.0],
        "oferta_efetiva_disponivel": [0.0],
        "score_oportunidade_residual": [0.0],
        "oferta_consumida_mercado_estimada": [9_000.0],
        "oferta_consumida_ultra_estimada": [5_000.0],
    }).to_parquet(dir_ / "hexagonos_mercado_mapeado.parquet", index=False)
    pd.DataFrame({
        "concorrente_id": ["c1"], "rede": ["smart_fit"], "lat": [LAT], "lng": [LNG],
        "status_registro": ["valido"],
    }).to_parquet(dir_ / "concorrentes_mapeados.parquet", index=False)
    pd.DataFrame({
        "lat": [LAT], "lng": [LNG], "flag_coord_valida": [True], "hex_id_res7": [cell],
    }).to_parquet(dir_ / "unidades_ultra_mapeadas.parquet", index=False)


@pytest.fixture
def rota(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from motor_expansao.api import service as api_service
    from motor_expansao.dashboard import censo_point

    setores = pd.DataFrame({"cod_setor": ["355030801000001"], "nome_municipio": ["São Paulo"]})
    monkeypatch.setattr(
        api_service, "_resolver_e_carregar", lambda lat, lng, cfg: ("SP", "3550308", setores)
    )
    # Oferta UNIDA da contagem (DEC-046) fica fora: o mercado tem insumo proprio.
    monkeypatch.setattr(api_service, "_competitors_ultra", lambda cfg: (None, None))
    monkeypatch.setattr(
        censo_point,
        "analisar_ponto_censitario_setores",
        lambda *a, **k: {"pop_total_raio": 30_000.0, "n_setores": 40},
    )

    def _apontar(staging: Path) -> None:
        monkeypatch.setattr(pilot, "STAGING_DIR", staging)

    return _apontar


def test_mercado_do_ponto_e_do_raio_e_a_conta_fecha(rota, tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    _staging(staging)
    rota(staging)

    m = pilot.ponto(lat=LAT, lng=LNG)["mercado"]

    assert m["disponivel"] is True
    assert m["grao"] == "raio" and m["raio_km"] == 1.0
    assert m["sam"] == 6_000  # 30.000 x 0,2 -- populacao do RAIO, nao do hexagono
    assert m["consumo_concorrentes"] == 2_500
    # Ultra colada no ponto: o disco de 1 km dela cai inteiro no raio -> 2.500 UMA vez.
    assert m["consumo_ultra"] == 2_500
    assert m["consumo_total"] == m["consumo_concorrentes"] + m["consumo_ultra"]
    assert m["residual"] == max(m["sam"] - m["consumo_total"], 0)
    assert m["score_residual"] == pytest.approx(100 * 1_000 / 2_500, abs=0.1)
    assert m["gate"]["passa"] is True
    assert m["gate"]["faixa_m1"] == "prioridade_maxima"  # valor bruto, sem acento
    # Auditoria: o hexagono continua visivel, sem alimentar nada.
    assert m["hexagono"]["sam"] == 12_000
    assert m["hexagono"]["consumo_ultra"] == 5_000


def test_criterio_de_residual_le_o_residual_do_raio(rota, tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    _staging(staging)
    rota(staging)

    body = pilot.ponto(lat=LAT, lng=LNG)
    crit = {c["chave"]: c for c in body["criterios"]}
    assert crit["residual"]["valor"] == body["mercado"]["residual"]


def test_sem_staging_consumo_e_residual_nao_viram_zero(rota, tmp_path: Path) -> None:
    vazio = tmp_path / "vazio"
    vazio.mkdir()
    rota(vazio)

    m = pilot.ponto(lat=LAT, lng=LNG)["mercado"]
    assert m["disponivel"] is False
    assert m["motivo"] and len(m["motivo"]) > 20
    for chave in ("sam", "consumo_concorrentes", "consumo_ultra", "consumo_total", "residual"):
        assert m[chave] is None, chave
