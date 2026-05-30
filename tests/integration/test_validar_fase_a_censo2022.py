from __future__ import annotations

import h3
import pandas as pd

import motor_expansao.pipelines.fase_a_censo2022_setores as fase_a_module
from motor_expansao.pipelines.fase_a_censo2022_setores import (
    ler_renda_nacional_uf_preservando_suprimidos,
)
from motor_expansao.pipelines.validar_fase_a_censo2022 import (
    aplicar_flags_validacao,
    detectar_outliers_espaciais,
    medir_intraurbano,
)


def _make_city_hexes(n: int = 7) -> list[str]:
    center = h3.latlng_to_cell(-16.6864, -49.2643, 7)
    neighbors = [cell for cell in h3.grid_disk(center, 1) if cell != center]
    return [center] + neighbors[: max(0, n - 1)]


def test_detecta_outlier_espacial_isolado():
    center = h3.latlng_to_cell(-16.6864, -49.2643, 7)
    hexes = [center] + [cell for cell in h3.grid_disk(center, 2) if cell != center]
    df = pd.DataFrame(
        {
            "hex_id": hexes,
            "score_setor_2022_exp": [120.0] + [10.0] * (len(hexes) - 1),
        }
    )
    result = detectar_outliers_espaciais(df, absolute_floor=35.0, min_neighbors=5)
    assert result["critical_outliers"] >= 1


def test_mede_ganho_intraurbano_com_baseline_uniforme():
    hexes = _make_city_hexes()
    df = pd.DataFrame(
        {
            "hex_id": hexes,
            "uf": ["GO"] * len(hexes),
            "cod_municipio": ["5208707"] * len(hexes),
            "score_priorizacao": [100.0] * len(hexes),
            "score_setor_2022_exp": [10.0, 20.0, 30.0, 60.0, 80.0, 90.0, 95.0],
        }
    )
    result = medir_intraurbano(df)
    go = result[result["uf"] == "GO"].iloc[0]
    assert bool(go["ganho_intraurbano_confirmado"]) is True
    assert go["correlacao_modelos"] == "NA_baseline_uniforme"


def test_aplica_flags_de_validacao_por_uf():
    validado = pd.DataFrame(
        {
            "hex_id": ["abc"],
            "uf": ["GO"],
            "score_setor_2022_exp": [50.0],
        }
    )
    join_audit = pd.DataFrame(
        {
            "uf": ["GO"],
            "mismatch_renda_total_pct": [0.35],
            "join_consistente": [True],
        }
    )
    renda_proxy = pd.DataFrame(
        {
            "uf": ["GO"],
            "corr_proxy_vs_m1": [0.36],
            "transformacao_v0005_melhor_que_bruta": [True],
        }
    )
    renda_dist = pd.DataFrame({"uf": ["GO"], "distribuicao_coerente": [True]})
    intraurbano = pd.DataFrame(
        {
            "uf": ["GO"],
            "ganho_amplitude": [71.78],
            "ganho_intraurbano_confirmado": [True],
        }
    )
    spatial = pd.DataFrame(
        {
            "uf": ["GO"],
            "critical_outliers": [0],
            "spatial_status": ["GO"],
        }
    )

    result = aplicar_flags_validacao(
        validado=validado,
        join_audit=join_audit,
        renda_proxy=renda_proxy,
        renda_dist=renda_dist,
        intraurbano=intraurbano,
        spatial=spatial,
    )
    row = result.iloc[0]
    assert row["status_validacao_join_uf"] == "GO"
    assert row["qualidade_join_uf"] == "A"
    assert row["status_distribuicao_renda_uf"] == "GO"
    assert row["status_intraurbano_uf"] == "GO"
    assert row["status_validacao_fase_a_uf"] == "GO"


def test_loader_nacional_preserva_suprimidos_sem_escrever_em_disco(monkeypatch):
    fake_df = pd.DataFrame(
        {
            "CD_SETOR": ["5,20E+14", "5,20E+14", "5,20E+14"],
            "V06001": ["100", "120", "140"],
            "V06004": ["2500,00", "X", "3100,00"],
        }
    )

    def fake_read_csv(*args, **kwargs):
        return fake_df.copy()

    monkeypatch.setattr(fase_a_module.pd, "read_csv", fake_read_csv)
    df = ler_renda_nacional_uf_preservando_suprimidos("fake.csv", "GO")
    assert len(df) == 3
    assert df["renda_per_capita_setor_2022"].notna().sum() == 2
    assert pd.isna(df.loc[1, "renda_per_capita_setor_2022"])
