"""Testes do uplift de composicao por setor — foco na validacao HONESTA (DEC-008).

Cobre o achado ALTA do BLK (R2 in-sample -> out-of-fold), a flag de extrapolacao, o raking, o
invariante de layout do Big Numbers (grid 4x2 cabe na pagina 960x540) e o acento da band nova.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from motor_expansao.dashboard import censo_report
from motor_expansao.dashboard.constants import RENDA_MEDIA_DOMICILIAR_BANDS
from motor_expansao.pipelines.derivar_uplift_composicao_setor import (
    FEATURES,
    UPLIFT_MAX,
    UPLIFT_MIN,
    ajustar_coeficientes,
    aplicar_e_rakear,
    validar_out_of_fold,
)


# --- Fixtures sinteticas -----------------------------------------------------------------------
def _dados_lineares(n: int = 600, ruido: float = 0.3, seed: int = 0):
    rng = np.random.default_rng(seed)
    x1, x2, x3 = rng.normal(size=n), rng.normal(size=n), rng.normal(size=n)
    y = 1.5 + 0.8 * x1 + 0.2 * x2 - 0.3 * x3 + rng.normal(scale=ruido, size=n)
    X = np.column_stack([np.ones(n), x1, x2, x3])
    return X, y, np.ones(n)


def _fixture_setores_uplift(n_mun: int = 150, seed: int = 3):
    """150 municipios (> guard de 100), cada um com alguns setores; uplift municipal = f(features)."""
    rng = np.random.default_rng(seed)
    linhas = []
    for m in range(n_mun):
        cod_mun = f"{3500000 + m:07d}"
        for s in range(int(rng.integers(2, 5))):
            linhas.append(
                {
                    "cod_setor": f"{cod_mun}{s:08d}",
                    "cod_municipio": cod_mun,
                    "conjuges_por_domicilio": float(rng.uniform(0.3, 0.9)),
                    "adultos_outros_por_domicilio": float(rng.uniform(0.1, 0.6)),
                    "fracao_unipessoal": float(rng.uniform(0.05, 0.4)),
                    "domicilios_parentesco": float(rng.integers(50, 500)),
                    "features_completas": True,
                }
            )
    setores = pd.DataFrame(linhas)

    mun = (
        setores.groupby("cod_municipio")
        .apply(
            lambda g: pd.Series(
                {f: float(np.average(g[f], weights=g["domicilios_parentesco"])) for f in FEATURES}
            ),
            include_groups=False,
        )
        .reset_index()
    )
    mun["uplift_composicao"] = (
        1.4
        + 0.8 * mun["conjuges_por_domicilio"]
        + 0.2 * mun["adultos_outros_por_domicilio"]
        - 0.4 * mun["fracao_unipessoal"]
        + rng.normal(scale=0.05, size=len(mun))
    )
    mun["domicilios_municipio"] = (
        setores.groupby("cod_municipio")["domicilios_parentesco"].sum().to_numpy()
    )
    mun["uplift_confiavel"] = True
    mun["uf"] = "SP"
    mun["uplift_composicao_final"] = mun["uplift_composicao"]
    return setores, mun


# --- A CV HONESTA e o coracao do achado ALTA ---------------------------------------------------
def test_out_of_fold_detecta_sinal_real():
    X, y, w = _dados_lineares()
    d = validar_out_of_fold(X, y, w)
    assert d["r2_oof"] > 0.5
    assert d["r2_oof_ic_baixo"] > 0  # IC95 nao cruza zero
    assert d["r2_oof_ic_baixo"] <= d["r2_oof"] <= d["r2_oof_ic_alto"]
    assert d["intervalo_95"] > 0


def test_out_of_fold_nao_infla_em_ruido_puro():
    """O nucleo do achado ALTA: com 30 features espurias o R2 IN-SAMPLE infla; o out-of-fold nao.

    E' exatamente o cenario que `fit(X, y) -> predict(X)` esconde e a DEC-008 proibe.
    """
    rng = np.random.default_rng(1)
    n = 200
    X = np.column_stack([np.ones(n), rng.normal(size=(n, 30))])
    y = rng.normal(size=n)
    w = np.ones(n)

    coef = np.linalg.lstsq(X, y, rcond=None)[0]
    r2_in_sample = 1.0 - np.sum((y - X @ coef) ** 2) / np.sum((y - y.mean()) ** 2)

    d = validar_out_of_fold(X, y, w)
    assert r2_in_sample > 0.10  # in-sample infla com ruido
    assert d["r2_oof"] < 0.05  # out-of-fold NAO infla (aqui, negativo)
    assert d["r2_oof"] < r2_in_sample - 0.10


def test_out_of_fold_reprodutivel_com_seed_fixa():
    X, y, w = _dados_lineares()
    assert validar_out_of_fold(X, y, w) == validar_out_of_fold(X, y, w)


# --- ajustar_coeficientes: reporta out-of-fold, NUNCA in-sample --------------------------------
def test_ajustar_coeficientes_reporta_oof_e_nao_insample():
    setores, mun = _fixture_setores_uplift()
    coef, diag = ajustar_coeficientes(setores, mun)

    # A chave banida do R2 in-sample nao pode mais existir.
    assert "r2_ponderado" not in diag
    for chave in ("r2_oof", "r2_oof_ic_baixo", "r2_oof_ic_alto", "intervalo_95", "envelope"):
        assert chave in diag
    assert diag["r2_oof"] > 0.3  # o fixture tem sinal forte
    assert diag["r2_oof_ic_baixo"] > 0
    assert set(diag["envelope"]) == set(FEATURES)
    assert len(coef) == len(FEATURES) + 1  # intercepto + 1 por feature


# --- aplicar_e_rakear: flag de extrapolacao + raking preserva o IBGE ---------------------------
def test_flag_extrapolacao_marca_setor_fora_do_envelope():
    setores, mun = _fixture_setores_uplift()
    coef, diag = ajustar_coeficientes(setores, mun)

    # Um setor com composicao MUITO acima do envelope de calibracao deve ser marcado.
    fora = setores.copy()
    lo, hi = diag["envelope"]["conjuges_por_domicilio"]
    fora.loc[fora.index[0], "conjuges_por_domicilio"] = hi + 10.0

    df = aplicar_e_rakear(fora, coef, mun, diag["envelope"])
    assert "flag_extrapolacao" in df.columns
    assert bool(df.loc[df.index[0], "flag_extrapolacao"]) is True
    # A grande maioria dos setores dentro da faixa NAO e' extrapolacao.
    assert df["flag_extrapolacao"].mean() < 0.5


def test_raking_preserva_uplift_municipal_do_ibge():
    setores, mun = _fixture_setores_uplift()
    coef, diag = ajustar_coeficientes(setores, mun)
    df = aplicar_e_rakear(setores, coef, mun, diag["envelope"])

    proprios = df[df["fonte_uplift_setor"] == "parentesco_setor"]
    # Nenhum setor no fixture bate os limites de clip -> raking e' exato.
    assert proprios["uplift_composicao_setor"].between(UPLIFT_MIN, UPLIFT_MAX).all()
    recomposto = (
        proprios.groupby("cod_municipio")
        .apply(
            lambda g: float(
                np.average(g["uplift_composicao_setor"], weights=g["domicilios_parentesco"])
            ),
            include_groups=False,
        )
    )
    alvo = mun.set_index("cod_municipio")["uplift_composicao_final"].reindex(recomposto.index)
    assert np.allclose(recomposto.to_numpy(), alvo.to_numpy(), atol=1e-6)


# --- Layout do Big Numbers: o grid 4x2 cabe na pagina fixa 960x540 -----------------------------
def test_big_numbers_grid_4x2_cabe_na_pagina():
    """Invariante do layout do PDF: as 2 linhas + a nota ficam ACIMA do rodape (y=_PAGE_H-22).

    Grade reduzida de 9->8 cards em 2026-07-17 (card "Score censitario medio" removido).
    """
    top = censo_report._BIG_NUMBERS_TOP
    gap = censo_report._BIG_NUMBERS_GAP
    card_h = censo_report._BIG_NUMBERS_CARD_H
    rows = censo_report._BIG_NUMBERS_ROWS
    rodape_y = censo_report._PAGE_H - 22.0

    ultima_linha_base = top + (rows - 1) * (card_h + gap) + card_h
    nota_y = top + rows * (card_h + gap) + 2.0
    assert ultima_linha_base <= censo_report._PAGE_H
    assert nota_y + 11.0 <= rodape_y  # a nota de fonte nao invade o rodape

    # 8 cards em 4 colunas => exatamente 2 linhas (nenhum card "vaza" para uma 3a linha).
    n_cards = 8
    assert (n_cards + censo_report._BIG_NUMBERS_COLS - 1) // censo_report._BIG_NUMBERS_COLS == rows


# --- Rotulo da band SEM acento (excecao de RENDER ao §2) ---------------------------------------
def test_band_renda_media_domiciliar_sem_acento_para_legenda_png():
    # Decisao de Felipe (2026-07-17): a legenda do choropleth de renda domiciliar e' rasterizada num
    # PNG (Pillow) cujo font renderiza 'á' BUGADO; por isso os rotulos usam "ate" SEM acento, igual a
    # RENDA_PER_CAPITA_BANDS (mesmo caminho de render). Excecao de rendering ao §2 (como o limite
    # latin-1 do fpdf2), nao regressao de texto acentuavel.
    labels = [label for _, label, _ in RENDA_MEDIA_DOMICILIAR_BANDS]
    assert not any(any(ord(ch) > 127 for ch in s) for s in labels)  # nenhum caractere acentuado
    assert any(s.startswith("ate ") for s in labels)  # "ate" sem acento, como a per capita
