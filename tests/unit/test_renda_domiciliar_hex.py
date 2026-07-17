"""Testes da renda media domiciliar por HEX no tooltip (components._renda_media_domiciliar_series).

READ-ONLY sobre o M1: camada de visualizacao, computada em tempo de render a partir das colunas ja
servidas + tabela municipal (moradores + uplift). Cobre a formula (renda_pc x moradores_muni x
uplift_muni x fator_temporal), fallbacks (calibrada ausente -> renda_per_capita; cod_municipio
ausente -> NaN; renda ausente -> NaN) e a variacao por municipio.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from pytest import approx

from motor_expansao.dashboard.components import _renda_media_domiciliar_series
from motor_expansao.dashboard.constants import (
    FATOR_TEMPORAL_RENDA,
    moradores_por_domicilio,
    uplift_renda_domiciliar,
)


def _fator(uf: str, cod: str) -> float:
    return (
        moradores_por_domicilio(uf, cod)
        * uplift_renda_domiciliar(uf, cod)
        * float(FATOR_TEMPORAL_RENDA)
    )


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "hex_id": ["a", "b", "c"],
            "uf": ["SP", "SP", "RJ"],
            "cod_municipio": ["3550308", "3509502", "3304557"],
            "renda_per_capita_setor_2022_calibrada": [1500.0, 2000.0, np.nan],
            "renda_per_capita": [1400.0, 1900.0, 1700.0],
        }
    )


def test_formula_usa_moradores_e_uplift_municipais():
    r = _renda_media_domiciliar_series(_frame())
    assert r.notna().all()
    assert r.iloc[0] == approx(1500.0 * _fator("SP", "3550308"))
    assert r.iloc[1] == approx(2000.0 * _fator("SP", "3509502"))


def test_fallback_para_renda_per_capita_quando_calibrada_ausente():
    r = _renda_media_domiciliar_series(_frame())
    # hex c: calibrada NaN -> usa renda_per_capita 1700
    assert r.iloc[2] == approx(1700.0 * _fator("RJ", "3304557"))


def test_varia_por_municipio():
    """Municipios diferentes -> fatores (moradores x uplift) diferentes: renda nao e' so escala fixa."""
    df = pd.DataFrame(
        {
            "hex_id": ["a", "b"],
            "uf": ["SP", "SP"],
            "cod_municipio": ["3550308", "3509502"],
            "renda_per_capita_setor_2022_calibrada": [1000.0, 1000.0],
        }
    )
    r = _renda_media_domiciliar_series(df)
    # mesma renda per capita, municipios distintos -> so iguais se os fatores coincidirem
    if _fator("SP", "3550308") != _fator("SP", "3509502"):
        assert r.iloc[0] != r.iloc[1]


def test_sem_cod_municipio_retorna_nan():
    df = _frame().drop(columns=["cod_municipio"])
    r = _renda_media_domiciliar_series(df)
    assert r.isna().all()


def test_cod_municipio_nan_por_linha_retorna_nan():
    """Contrato: hex sem municipio resolvido (cod_municipio NaN, uf presente) -> NaN, e NAO uma
    estimativa de nivel UF. Cobre o caso do valor NaN por linha (coluna presente)."""
    df = pd.DataFrame(
        {
            "hex_id": ["a", "b"],
            "uf": ["SP", "SP"],
            "cod_municipio": ["3550308", np.nan],
            "renda_per_capita_setor_2022_calibrada": [1500.0, 900.0],
        }
    )
    r = _renda_media_domiciliar_series(df)
    assert r.iloc[0] == approx(1500.0 * _fator("SP", "3550308"))  # municipio resolvido
    assert np.isnan(r.iloc[1])  # cod_municipio NaN -> tooltip vazio (nao fallback UF)


def test_sem_nenhuma_renda_retorna_nan():
    df = _frame().drop(columns=["renda_per_capita_setor_2022_calibrada", "renda_per_capita"])
    r = _renda_media_domiciliar_series(df)
    assert r.isna().all()


def test_preserva_indice_nao_sequencial():
    df = _frame()
    df.index = [10, 20, 30]
    r = _renda_media_domiciliar_series(df)
    assert list(r.index) == [10, 20, 30]
    assert r.loc[10] == approx(1500.0 * _fator("SP", "3550308"))
