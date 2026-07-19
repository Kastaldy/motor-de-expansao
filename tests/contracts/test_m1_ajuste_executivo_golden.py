"""Golden da MATRIZ COMPLETA de `calcular_ajuste_executivo` (ajuste executivo do M1).

Aditivo (review de refatoracao, Fase 0 -- "golden de formula"). NAO altera codigo-fonte.

`tests/unit/test_scoring.py` cobre 4 das 9 combinacoes de (renda_pct, pop_pct); as 5
restantes -- em especial as penalidades mistas (-1, -3, -4, -5) e o neutro (0) -- ficavam
sem trava. Este golden fixa a matriz inteira, que a eventual decomposicao de
`hex_enrichment.py` (God-file) precisa preservar byte-a-byte.

Regra (core/scoring.py::calcular_ajuste_executivo, cortes 0.75/0.25):
  bonus:      renda_alta & pop_alta = +5 ; renda_alta & ~pop_alta = +2 ; pop_alta & ~renda_alta = +1
  penalidade: renda_baixa = -5 ; pop_baixa = -3
  alta = pct >= 0.75 ; baixa = pct < 0.25
"""

from __future__ import annotations

import pandas as pd

from motor_expansao.core.scoring import calcular_ajuste_executivo

# (renda_pct, pop_pct) -> ajuste esperado. Cobre alta/media/baixa em cada eixo.
_MATRIZ = [
    (0.90, 0.90, 5.0),   # ambas altas -> +5
    (0.90, 0.50, 2.0),   # renda alta, pop media -> +2
    (0.90, 0.10, -1.0),  # renda alta (+2), pop baixa (-3) -> -1
    (0.50, 0.90, 1.0),   # renda media, pop alta -> +1
    (0.50, 0.50, 0.0),   # ambas medias -> 0
    (0.50, 0.10, -3.0),  # renda media, pop baixa -> -3
    (0.10, 0.90, -4.0),  # renda baixa (-5), pop alta (+1) -> -4
    (0.10, 0.50, -5.0),  # renda baixa, pop media -> -5
    (0.10, 0.10, -8.0),  # ambas baixas -> -5-3 = -8
]


def test_matriz_completa_bonus_e_penalidade():
    renda_pct = pd.Series([r for r, _, _ in _MATRIZ])
    pop_pct = pd.Series([p for _, p, _ in _MATRIZ])
    esperado = [a for _, _, a in _MATRIZ]
    assert calcular_ajuste_executivo(renda_pct, pop_pct).tolist() == esperado


def test_limites_de_corte_sao_inclusivo_superior_e_exclusivo_inferior():
    # Corte superior >= 0.75 (inclusivo); corte inferior < 0.25 (exclusivo).
    # (0.75, 0.75) ambas altas -> +5 ; (0.25, 0.25) nenhuma baixa/alta -> 0.
    resultado = calcular_ajuste_executivo(
        pd.Series([0.75, 0.25]),
        pd.Series([0.75, 0.25]),
    )
    assert resultado.tolist() == [5.0, 0.0]
