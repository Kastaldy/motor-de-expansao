"""Regressao dos helpers de formatacao do dashboard (BLK-FIX hex search NaN).

Bug em prod (Sao Vicente, litoral SP): hex costeiro do universo BLK-FIX-06 sem setor
censitario -> `pop_total_setor_2022 = NaN`. O guarda `is not None` nao pega NaN, e
`format_int(NaN)` fazia `int(round(NaN))` -> ValueError: cannot convert float NaN to integer.
"""

from __future__ import annotations

import numpy as np

from motor_expansao.dashboard.utils import format_int


def test_format_int_nan_retorna_traco() -> None:
    # Causa raiz do crash em prod: NaN nao e None e quebrava int(round(...)).
    assert format_int(float("nan")) == "-"
    assert format_int(np.nan) == "-"


def test_format_int_none_retorna_traco() -> None:
    assert format_int(None) == "-"  # type: ignore[arg-type]


def test_format_int_valor_valido_formata_com_separador_de_milhar() -> None:
    assert format_int(1234567) == "1.234.567"
    assert format_int(1234.6) == "1.235"  # arredonda
    assert format_int(0) == "0"
