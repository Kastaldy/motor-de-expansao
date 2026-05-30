from __future__ import annotations

import math

import pandas as pd
import pytest

from motor_expansao.pipelines.fase_a_piloto_expandido import (
    classificar_qualidade_join,
    parse_k_global,
    resumir_metricas_uf,
)


def test_parse_k_global_extrai_valor():
    assert parse_k_global("multiplicativo_global_k=1.0213") == pytest.approx(1.0213)


def test_parse_k_global_falha_sem_valor():
    with pytest.raises(ValueError, match="sem k global"):
        parse_k_global("metodo_sem_parametro")


@pytest.mark.parametrize(
    ("mismatch_pct", "classe"),
    [
        (0.35, "A"),
        (1.99, "A"),
        (2.00, "B"),
        (5.00, "B"),
        (5.01, "C"),
    ],
)
def test_classificar_qualidade_join(mismatch_pct: float, classe: str):
    assert classificar_qualidade_join(mismatch_pct) == classe


def test_resumir_metricas_uf_aplica_gates_e_ganhos():
    df = pd.DataFrame(
        {
            "score_setor_2022_calibrado": [10.0, 20.0, 60.0, 80.0, 90.0],
            "score_priorizacao": [45.0, 50.0, 55.0, 60.0, 65.0],
        }
    )
    outlier_result = {
        "critical_outliers": 0,
        "threshold": 35.0,
        "avaliados": 5,
    }

    result = resumir_metricas_uf(
        df,
        uf="MG",
        mismatch_pct=1.5,
        outlier_result=outlier_result,
    )

    assert result["uf"] == "MG"
    assert result["coverage_pct"] == 100.0
    assert result["classe_join"] == "A"
    assert result["gate_cobertura"] is True
    assert result["gate_amplitude"] is True
    assert result["join_gate"] is True
    assert result["status_espacial"] == "GO"
    assert result["status_tecnico"] == "GO"
    assert result["ganho_amplitude_vs_m1"] > 0
    assert result["ganho_std_vs_m1"] > 0
    assert not math.isnan(result["spearman_vs_m1"])
