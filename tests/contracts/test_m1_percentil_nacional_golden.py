"""Golden das semanticas de `_calcular_percentil_nacional` (nucleo do score do M1).

Aditivo (review de refatoracao, Fase 0 -- "golden de formula"). NAO altera codigo-fonte.

Motivacao (da critica adversarial do review): o `score_priorizacao` usa percentil
NACIONAL sobre ~1,54M hexes. Um golden de SUBSET nao reproduz o percentil nacional, mas
as SEMANTICAS da funcao -- tratamento de empate (`rank(method="average")`), valor unico,
zeros como validos, preservacao de indice e arredondamento em 6 casas -- sao justamente o
que um refactor behavior-preserving nao pode alterar. Este golden trava essas semanticas
de forma portavel e independente de escala (complementa `tests/unit/test_scoring.py`, que
cobre apenas nulos/indice).
"""

from __future__ import annotations

import math

import pandas as pd

from motor_expansao.core.scoring import _calcular_percentil_nacional


def test_empates_usam_rank_medio():
    # [10, 10, 20] -> ranks average [1.5, 1.5, 3] -> (r-1)/(n-1) com n=3.
    resultado = _calcular_percentil_nacional(pd.Series([10.0, 10.0, 20.0]))
    assert list(resultado) == [0.25, 0.25, 1.0]


def test_zeros_sao_validos_nao_ausentes():
    # Diferente de _normalizar_serie_disponivel, aqui 0 NAO e tratado como ausente.
    resultado = _calcular_percentil_nacional(pd.Series([0.0, 5.0, 10.0]))
    assert list(resultado) == [0.0, 0.5, 1.0]


def test_valor_unico_valido_vira_meio():
    # Um unico valido entre NaN -> 0.5 (evita divisao por zero em n-1).
    resultado = _calcular_percentil_nacional(pd.Series([float("nan"), 5.0, float("nan")]))
    assert resultado.iloc[1] == 0.5
    assert math.isnan(resultado.iloc[0]) and math.isnan(resultado.iloc[2])


def test_todos_nan_retorna_todos_nan():
    resultado = _calcular_percentil_nacional(pd.Series([float("nan"), float("nan")]))
    assert resultado.isna().all()


def test_arredonda_em_seis_casas():
    # [1,2,3,4] -> (r-1)/3 = [0, 1/3, 2/3, 1] -> round(6).
    resultado = _calcular_percentil_nacional(pd.Series([1.0, 2.0, 3.0, 4.0]))
    assert list(resultado) == [0.0, 0.333333, 0.666667, 1.0]


def test_preserva_indice_e_ignora_nulos():
    serie = pd.Series([100.0, float("nan"), 300.0], index=["a", "b", "c"])
    resultado = _calcular_percentil_nacional(serie)
    assert list(resultado.index) == ["a", "b", "c"]
    assert resultado.loc["a"] == 0.0
    assert math.isnan(resultado.loc["b"])
    assert resultado.loc["c"] == 1.0
