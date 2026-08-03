"""Reancoragem BLK-WEB-19 (DEC-022): formatadores e rampa residual sem Streamlit.

`_residual_score_to_color`, `format_score` e `format_pct` so eram exercitados
pelos testes da UI Streamlit (que serao deletados). Reancoragem direta:
- a rampa residual hardcoded precisa continuar ESPELHANDO a paleta canonica
  `RESIDUAL_SCORE_BANDS` (10 faixas de 10 pontos) — se alguem mudar a constante
  sem mudar a funcao (ou vice-versa), o mapa e a legenda divergem em silencio;
- NaN/None nos formatadores viram "-" (mesma familia do bug de prod do
  `format_int` em Sao Vicente: NaN nao e None e quebrava a formatacao).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from motor_expansao.dashboard.constants import RESIDUAL_SCORE_BANDS
from motor_expansao.dashboard.utils import (
    _residual_score_to_color,
    format_pct,
    format_score,
    hex_to_rgba,
)

# Cor neutra (cinza translucido) de score ausente — hex sem camada residual.
_COR_SEM_SCORE = [120, 120, 140, 70]

# Alpha por faixa: as faixas baixas sao mais opacas de proposito (vermelhos de
# alerta saltam no mapa escuro); e parte do contrato visual, nao um acidente.
_ALPHA_POR_FAIXA = [190, 185, 178, 175, 170, 165, 165, 165, 165, 170]


# ---------------------------------------------------------------------------
# _residual_score_to_color — todas as faixas, limites, NaN e fora de faixa
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("valor", [float("nan"), np.nan, pd.NA, None])
def test_residual_score_nan_ou_none_vira_cinza_neutro(valor) -> None:
    """Score ausente nao pode pintar faixa nenhuma: cai no cinza translucido."""
    assert _residual_score_to_color(valor) == _COR_SEM_SCORE


@pytest.mark.parametrize(
    ("score", "faixa_idx"),
    [
        # Interior de cada faixa + o LIMITE inferior (que pertence a faixa de cima:
        # `s < 10` etc. sao estritos, entao 10.0 ja e a faixa 10-20, e assim por diante).
        (0.0, 0),
        (9.99, 0),
        (10.0, 1),
        (19.99, 1),
        (20.0, 2),
        (29.99, 2),
        (30.0, 3),
        (39.99, 3),
        (40.0, 4),
        (49.99, 4),
        (50.0, 5),
        (59.99, 5),
        (60.0, 6),
        (69.99, 6),
        (70.0, 7),
        (79.99, 7),
        (80.0, 8),
        (89.99, 8),
        (90.0, 9),
        (100.0, 9),
    ],
)
def test_residual_score_espelha_a_paleta_canonica_por_faixa(score: float, faixa_idx: int) -> None:
    """O RGBA de cada faixa tem de ser exatamente o hex de RESIDUAL_SCORE_BANDS
    com o alpha da faixa — e o que mantem mapa e legenda na MESMA cor."""
    _, cor_hex = RESIDUAL_SCORE_BANDS[faixa_idx]
    esperado = hex_to_rgba(cor_hex, _ALPHA_POR_FAIXA[faixa_idx])
    assert _residual_score_to_color(score) == esperado


def test_residual_score_fora_de_faixa_satura_nos_extremos() -> None:
    """Valores fora de [0,100] nao levantam: saturam no vermelho (baixo) e no
    verde (alto) — defesa contra score sujo vindo de parquet legado."""
    assert _residual_score_to_color(-5.0) == hex_to_rgba(RESIDUAL_SCORE_BANDS[0][1], 190)
    assert _residual_score_to_color(250.0) == hex_to_rgba(RESIDUAL_SCORE_BANDS[-1][1], 170)


def test_residual_score_aceita_string_numerica() -> None:
    """`float(score)` no corpo tolera score serializado como texto (parquet/CSV
    legado): "42" cai na faixa 40-50 normalmente."""
    assert _residual_score_to_color("42") == hex_to_rgba(RESIDUAL_SCORE_BANDS[4][1], 170)


# ---------------------------------------------------------------------------
# format_score / format_pct — branches de ausencia e formatacao
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("valor", [float("nan"), np.nan, pd.NA, None])
def test_format_score_ausente_retorna_traco(valor) -> None:
    """NaN *e* None viram "-" (pd.isna cobre ambos; guarda `is not None` nao basta)."""
    assert format_score(valor) == "-"


def test_format_score_formata_com_duas_casas() -> None:
    assert format_score(87.456) == "87.46"
    assert format_score(90) == "90.00"  # int e coagido a float antes de formatar
    assert format_score(0.0) == "0.00"


@pytest.mark.parametrize("valor", [float("nan"), np.nan, pd.NA, None])
def test_format_pct_ausente_retorna_traco(valor) -> None:
    assert format_pct(valor) == "-"


def test_format_pct_formata_com_uma_casa_e_sufixo() -> None:
    assert format_pct(12.34) == "12.3%"
    assert format_pct(99.96) == "100.0%"  # arredonda antes do sufixo
    assert format_pct(0) == "0.0%"
