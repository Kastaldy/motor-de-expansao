"""Testes unitarios para BLK-LTV-03 — correlacao_territorio_retencao.

Fixtures 100% sinteticas via pd.DataFrame em memoria; NUNCA le parquet real.
Cobre os casos (a)-(i) do plano aprovado (secao 6).
"""

from __future__ import annotations

import inspect

import numpy as np
import pandas as pd

from motor_expansao.lifetime.correlacao_territorio_retencao import (
    ALVO_ABSOLUTO,
    ALVOS_RANKING,
    FEATURES_TERRITORIAIS,
    LIMIAR_RHO_GO,
    N_MIN_PAR,
    PARES,
    ResultadoPar,
    _bootstrap_spearman_ci,
    _montar_relatorio,
    _veredito,
    analisar_correlacao_territorio_retencao,
)


# ---------------------------------------------------------------------------
# Helpers de fixture sintetica
# ---------------------------------------------------------------------------
def _df_sintetico(n: int = 40, seed: int = 7) -> pd.DataFrame:
    """DataFrame sintetico com todas as features/alvos usados pelos PARES."""
    rng = np.random.default_rng(seed)
    cols = set(FEATURES_TERRITORIAIS) | set(ALVOS_RANKING) | {ALVO_ABSOLUTO, "hex_id"}
    data: dict[str, object] = {}
    for c in cols:
        if c == "hex_id":
            data[c] = [f"87a{i:012x}" for i in range(n)]
        else:
            data[c] = rng.normal(size=n)
    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# (a) ResultadoPar tem os campos esperados
# ---------------------------------------------------------------------------
def test_resultado_par_tem_campos():
    df = _df_sintetico()
    resultados = analisar_correlacao_territorio_retencao(df)
    assert resultados, "esperava >=1 par"
    r = resultados[0]
    for campo in ("feature", "target", "n", "rho", "ci_low", "ci_high", "p_value"):
        assert hasattr(r, campo), f"ResultadoPar sem campo {campo}"
    # 21 pares determinicos (14 ranking + 7 absoluto)
    assert len(resultados) == 21
    assert len(PARES) == 21


# ---------------------------------------------------------------------------
# (b) N por par == contagem real de nao-nulos do subset
# ---------------------------------------------------------------------------
def test_n_por_par_conta_nao_nulos():
    df = _df_sintetico(n=30)
    # Injeta 4 NaN numa feature -> os pares dessa feature devem ter N=26.
    df.loc[df.index[:4], "renda_per_capita"] = np.nan
    resultados = analisar_correlacao_territorio_retencao(df)
    pares_renda = [
        r for r in resultados if r.feature == "renda_per_capita"
    ]
    assert pares_renda
    for r in pares_renda:
        assert r.n == 26, f"esperava N=26 apos 4 NaN, obtido {r.n}"
    # feature sem NaN mantem N=30
    outra = next(r for r in resultados if r.feature == "score_priorizacao")
    assert outra.n == 30


# ---------------------------------------------------------------------------
# (c) Determinismo do bootstrap sob seed fixo
# ---------------------------------------------------------------------------
def test_bootstrap_determinista():
    rng = np.random.default_rng(123)
    x = rng.normal(size=50)
    y = 2.0 * x + rng.normal(scale=0.1, size=50)
    ic1 = _bootstrap_spearman_ci(x, y)
    ic2 = _bootstrap_spearman_ci(x, y)
    assert ic1 == ic2, "mesmo (x, y, seed) deve produzir o mesmo IC"


# ---------------------------------------------------------------------------
# (d) Sanidade: relacao crescente perfeita -> rho ~ +1, IC nao cruza zero
# ---------------------------------------------------------------------------
def test_monotonica_crescente_rho_positivo():
    x = np.arange(30, dtype=float)
    y = 2.0 * x  # monotonica crescente perfeita
    df = pd.DataFrame(
        {
            "renda_per_capita": x,
            "PROB_CANCEL_90D_MEDIA": y,
            "hex_id": [f"h{i}" for i in range(30)],
        }
    )
    resultados = analisar_correlacao_territorio_retencao(df)
    r = next(
        r
        for r in resultados
        if r.feature == "renda_per_capita" and r.target == "PROB_CANCEL_90D_MEDIA"
    )
    assert r.rho > 0.99
    assert r.ci_low > 0.0
    assert not r.ic_cruza_zero


# ---------------------------------------------------------------------------
# (e) Relacao decrescente perfeita -> rho ~ -1, IC alto < 0
# ---------------------------------------------------------------------------
def test_monotonica_decrescente_rho_negativo():
    x = np.arange(30, dtype=float)
    y = -3.0 * x  # monotonica decrescente perfeita
    df = pd.DataFrame(
        {
            "renda_per_capita": x,
            "PROB_CANCEL_90D_MEDIA": y,
            "hex_id": [f"h{i}" for i in range(30)],
        }
    )
    resultados = analisar_correlacao_territorio_retencao(df)
    r = next(
        r
        for r in resultados
        if r.feature == "renda_per_capita" and r.target == "PROB_CANCEL_90D_MEDIA"
    )
    assert r.rho < -0.99
    assert r.ci_high < 0.0
    assert not r.ic_cruza_zero


# ---------------------------------------------------------------------------
# (f) N insuficiente (< N_MIN_PAR) -> rho NaN, ic_cruza_zero True, sem excecao
# ---------------------------------------------------------------------------
def test_n_insuficiente_vira_nan():
    n = N_MIN_PAR - 1
    df = _df_sintetico(n=n)
    resultados = analisar_correlacao_territorio_retencao(df)
    for r in resultados:
        assert r.n == n
        assert np.isnan(r.rho)
        assert r.ic_cruza_zero is True


# ---------------------------------------------------------------------------
# (g) Veredito GO/NO-GO
# ---------------------------------------------------------------------------
def test_veredito_go_quando_ha_par_forte():
    forte = ResultadoPar(
        feature="renda_per_capita",
        target="PROB_CANCEL_90D_MEDIA",
        n=56,
        rho=0.55,
        ci_low=0.30,
        ci_high=0.72,
        p_value=0.001,
        eixo="ranking",
        ic_cruza_zero=False,
    )
    veredito, _just = _veredito([forte])
    assert veredito == "GO"


def test_veredito_nogo_quando_todos_cruzam_zero():
    fraco = ResultadoPar(
        feature="renda_per_capita",
        target="PROB_CANCEL_90D_MEDIA",
        n=56,
        rho=0.12,
        ci_low=-0.15,
        ci_high=0.36,
        p_value=0.40,
        eixo="ranking",
        ic_cruza_zero=True,
    )
    veredito, _just = _veredito([fraco])
    assert veredito == "NO-GO"


def test_veredito_nogo_quando_significativo_mas_rho_pequeno():
    # IC nao cruza zero, mas |rho| < 0.30 -> NAO e GO (relevancia material).
    pequeno = ResultadoPar(
        feature="renda_per_capita",
        target="PROB_CANCEL_90D_MEDIA",
        n=56,
        rho=0.20,
        ci_low=0.02,
        ci_high=0.38,
        p_value=0.03,
        eixo="ranking",
        ic_cruza_zero=False,
    )
    assert abs(pequeno.rho) < LIMIAR_RHO_GO
    veredito, _just = _veredito([pequeno])
    assert veredito == "NO-GO"


# ---------------------------------------------------------------------------
# (h) Sem imports proibidos
# ---------------------------------------------------------------------------
def test_no_extra_m1_imports():
    import motor_expansao.lifetime.correlacao_territorio_retencao as mod

    src = inspect.getsource(mod)
    banned_imports = [
        "import motor_expansao.pipelines.m1",
        "from motor_expansao.pipelines.m1",
        "from motor_expansao.dashboard",
        "import motor_expansao.dashboard",
        "from motor_expansao.censo",
        "import motor_expansao.censo",
        "from motor_expansao.api",
        "import motor_expansao.api",
    ]
    for banned in banned_imports:
        assert banned not in src, f"Import proibido detectado: {banned}"


# ---------------------------------------------------------------------------
# (i) _montar_relatorio: contem "Confounds"/"maturidade" e nao escreve disco
# ---------------------------------------------------------------------------
def test_montar_relatorio_contem_confounds_e_maturidade():
    df = _df_sintetico()
    resultados = analisar_correlacao_territorio_retencao(df)
    veredito, justificativa = _veredito(resultados)
    texto = _montar_relatorio(resultados, veredito, justificativa)
    baixo = texto.lower()
    assert "confounds" in baixo
    assert "maturidade" in baixo
    assert veredito in texto
    # funcao pura: retorna string (nao toca disco). Basta ser str nao-vazia.
    assert isinstance(texto, str) and len(texto) > 100
