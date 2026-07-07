"""Testes do gate de viabilidade absoluto (flag_gate_atratividade) — BLK-ATR-02.

Etapa 1 do funil de atratividade: coluna PARALELA na camada de mercado
(`calcular_colunas_mercado.py`). READ-ONLY sobre o M1 — nao altera
`score_priorizacao`, `hex_score_estrutural`, `flag_sam`, `flag_viavel` nem artefatos oficiais.

flag_gate_atratividade = populacao_corte_hex >= 5000 AND renda_per_capita >= 1500.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from motor_expansao.pipelines.calcular_colunas_mercado import (
    RENDA_PER_CAPITA_MIN_ATR,
    calcular,
)


def _df(**kwargs) -> pd.DataFrame:
    """DataFrame-fixture minimo (1 linha) que satisfaz as colunas lidas por `calcular()`.

    Defaults plausiveis para o pipeline rodar sem erro; sobrescreva o que o teste precisar.
    """
    defaults = {
        "hex_id": "h1",
        "flag_censo_elegivel": False,
        "pop_total_setor_2022": np.nan,
        "populacao_proxy": 10_000.0,
        "renda_per_capita": 3_000.0,
        "score_priorizacao": 88.0,
        "hex_score_estrutural": 82.0,
        "faixa_oportunidade": "alta",
        "pop_total": 10_000.0,
        "flag_hex_hibrido_elegivel": False,
        "score_expansao_hibrido": np.nan,
        "renda_per_capita_setor_2022_calibrada": np.nan,
        "flag_viavel": True,
        "top_municipio": True,
        "flag_white_space_2km": True,
        "flag_canibalizacao_ultra_1km": False,
        "n_concorrentes_mapeados_2km": 0.0,
        "oferta_efetiva_mapeada_2km": 0.0,
        "gap_competitivo_2km": 1.0,
        "pressao_concorrencial_score_2km": 0.0,
        "confianca_geografica": "municipal",
        "qualidade_join_uf": "C",
        "total_hex_municipio": 1.0,
        "n_unidades_ultra_2km": 0.0,
    }
    defaults.update(kwargs)
    return pd.DataFrame(
        {k: v if isinstance(v, list) else [v] for k, v in defaults.items()}
    )


def test_constante_do_gate_de_renda():
    assert RENDA_PER_CAPITA_MIN_ATR == 1_500


def test_acima_dos_dois_pisos_true():
    df = calcular(_df(pop_total=10_000.0, renda_per_capita=3_000.0))
    assert bool(df.loc[0, "flag_gate_atratividade"]) is True
    assert df["flag_gate_atratividade"].dtype == bool
    assert df["flag_gate_atratividade"].isna().sum() == 0


def test_abaixo_do_piso_populacao_false():
    df = calcular(_df(pop_total=3_000.0, renda_per_capita=3_000.0))
    assert bool(df.loc[0, "flag_gate_atratividade"]) is False


def test_abaixo_do_piso_renda_false():
    df = calcular(_df(pop_total=10_000.0, renda_per_capita=1_000.0))
    assert bool(df.loc[0, "flag_gate_atratividade"]) is False


def test_renda_nan_false():
    df = calcular(_df(pop_total=10_000.0, renda_per_capita=np.nan))
    assert bool(df.loc[0, "flag_gate_atratividade"]) is False


def test_renda_exatamente_no_limiar_true():
    df = calcular(_df(pop_total=10_000.0, renda_per_capita=1_500.0))
    assert bool(df.loc[0, "flag_gate_atratividade"]) is True


def test_score_priorizacao_e_estrutural_inalterados():
    df = calcular(_df(score_priorizacao=88.0, hex_score_estrutural=82.0))
    assert float(df.loc[0, "score_priorizacao"]) == 88.0
    assert float(df.loc[0, "hex_score_estrutural"]) == 82.0
