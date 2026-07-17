"""Testes do calculo da renda media domiciliar por HEX (data._add_renda_media_domiciliar_hex).

READ-ONLY sobre o M1: e camada de visualizacao. Cobre a formula (renda_pc x moradores x uplift
municipal x fator temporal), o fallback gracioso (sem domicilios -> coluna nao criada; domicilios=0
ou insumo ausente -> NaN) e a coerencia com as funcoes puras de uplift/fator de constants.py.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from pytest import approx

from motor_expansao.dashboard.constants import FATOR_TEMPORAL_RENDA, uplift_renda_domiciliar
from motor_expansao.dashboard.data import _add_renda_media_domiciliar_hex


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "hex_id": ["a", "b", "c", "d"],
            "uf": ["SP", "SP", "RJ", "SP"],
            "cod_municipio": ["3550308", "3550308", "3304557", "3550308"],
            "pop_total_setor_2022": [3000.0, 6000.0, np.nan, 4000.0],
            "domicilios_setor_2022": [1000.0, 0.0, 500.0, 1000.0],
            "renda_per_capita_setor_2022_calibrada": [1500.0, 2000.0, 1800.0, np.nan],
            "renda_per_capita": [1400.0, 1900.0, 1700.0, 1200.0],
        }
    )


def test_formula_bate_com_uplift_municipal_e_fator_temporal():
    out = _add_renda_media_domiciliar_hex(_frame())
    assert "renda_media_domiciliar_hex" in out.columns

    uplift_sp = uplift_renda_domiciliar("SP", "3550308")
    # hex a: renda_pc 1500 x moradores(3000/1000=3) x uplift x fator
    esperado_a = 1500.0 * 3.0 * uplift_sp * float(FATOR_TEMPORAL_RENDA)
    assert out.loc[0, "renda_media_domiciliar_hex"] == approx(esperado_a)


def test_fallback_renda_per_capita_quando_calibrada_ausente():
    out = _add_renda_media_domiciliar_hex(_frame())
    uplift_sp = uplift_renda_domiciliar("SP", "3550308")
    # hex d: calibrada NaN -> usa renda_per_capita 1200; moradores 4000/1000=4
    esperado_d = 1200.0 * 4.0 * uplift_sp * float(FATOR_TEMPORAL_RENDA)
    assert out.loc[3, "renda_media_domiciliar_hex"] == approx(esperado_d)


def test_nan_quando_domicilios_zero_ou_pop_ausente():
    out = _add_renda_media_domiciliar_hex(_frame())
    assert np.isnan(out.loc[1, "renda_media_domiciliar_hex"])  # domicilios = 0
    assert np.isnan(out.loc[2, "renda_media_domiciliar_hex"])  # pop = NaN


def test_sem_domicilios_no_frame_nao_cria_coluna():
    df = _frame().drop(columns=["domicilios_setor_2022"])
    out = _add_renda_media_domiciliar_hex(df)
    assert "renda_media_domiciliar_hex" not in out.columns


def test_coluna_calibrada_ausente_nao_crasha_usa_per_capita():
    """Regressao: com domicilios presente mas a coluna CALIBRADA ausente (schema parcial), a funcao
    NAO pode estourar AttributeError — deve cair no fallback renda_per_capita, sem derrubar o enrich."""
    df = _frame().drop(columns=["renda_per_capita_setor_2022_calibrada"])
    out = _add_renda_media_domiciliar_hex(df)  # nao deve levantar
    uplift_sp = uplift_renda_domiciliar("SP", "3550308")
    # hex a: usa renda_per_capita 1400 (calibrada ausente) x moradores 3 x uplift x fator
    esperado_a = 1400.0 * 3.0 * uplift_sp * float(FATOR_TEMPORAL_RENDA)
    assert out.loc[0, "renda_media_domiciliar_hex"] == approx(esperado_a)


def test_sem_nenhuma_coluna_de_renda_nao_crasha_coluna_nan():
    """Regressao: sem calibrada E sem renda_per_capita, a coluna e' toda NaN (fallback gracioso),
    nunca um crash."""
    df = _frame().drop(
        columns=["renda_per_capita_setor_2022_calibrada", "renda_per_capita"]
    )
    out = _add_renda_media_domiciliar_hex(df)  # nao deve levantar
    assert "renda_media_domiciliar_hex" in out.columns
    assert out["renda_media_domiciliar_hex"].isna().all()


def test_read_only_nao_toca_score_m1():
    df = _frame()
    df["score_priorizacao"] = [80.0, 90.0, 70.0, 60.0]
    out = _add_renda_media_domiciliar_hex(df)
    assert list(out["score_priorizacao"]) == [80.0, 90.0, 70.0, 60.0]
