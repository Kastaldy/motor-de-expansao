"""Testes do BLK-DIM-05: features exogenas na aderencia (LOO-CV multi-feature).

Fixtures anti-circulares: `df_features_sinal` injeta uma feature exogena (n_conc)
INDEPENDENTE de pop/renda mas correlacionada com log(pagantes) -> captura sinal real.
`df_features_ruido` gera n_conc/densidade ALEATORIOS sem correlacao com pagantes ->
controle negativo (sem GO espurio). Tudo offline, seeds fixos, sem leitura de parquet.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from motor_expansao.dimensionamento.features_exogenas import (
    FEATURE_SETS,
    LIMIAR_R2_GO,
    ResultadoModeloFeatures,
    _loo_ridge_multifeature,
    comparar_modelos_aderencia,
    derivar_n_concorrentes_raio,
    montar_df_features,
)


def _df_base(rng: np.random.Generator, n: int = 30) -> dict:
    """pop/renda log-espacados + alvo de baseline; retorna dict de colunas."""
    pop = np.geomspace(3000.0, 120000.0, n)
    renda = rng.permutation(np.geomspace(700.0, 14000.0, n))
    return {"pop": pop, "renda": renda}


@pytest.fixture
def df_features_sinal() -> pd.DataFrame:
    """log(pagantes) = b0 + b1*log(pop) + b3*n_conc + ruido, com n_conc INDEPENDENTE.

    n_conc e gerado a parte (nao deriva de pop/renda) -> des-circular. Densidade/renda_resp
    sao preenchidas com valores plausiveis nao-correlacionados (so para completar o set B).
    """
    rng = np.random.default_rng(7)
    n = 36
    base = _df_base(rng, n)
    pop, renda = base["pop"], base["renda"]
    n_conc = rng.integers(0, 12, n).astype(float)  # feature exogena independente
    log_pagantes = (
        -1.0 + 0.7 * np.log(pop) + 0.12 * n_conc + rng.normal(0, 0.18, n)
    )
    pagantes = np.exp(log_pagantes)
    return pd.DataFrame(
        {
            "unidade": [f"U{i}" for i in range(n)],
            "pagantes_steady_state": pagantes,
            "pop_captacao": pop,
            "renda_per_capita_captacao": renda,
            "n_concorrentes_raio_1_5km": n_conc,
            "densidade_pop_catchment_hab_km2": rng.uniform(500, 9000, n),
            "renda_responsavel_media_catchment": rng.uniform(700, 14000, n),
        }
    )


@pytest.fixture
def df_features_ruido() -> pd.DataFrame:
    """Alvo gerado SO de pop+ruido; n_conc/densidade ALEATORIOS sem correlacao.

    Controle negativo: adicionar ruido exogeno NAO deve melhorar materialmente o baseline.
    """
    rng = np.random.default_rng(11)
    n = 36
    base = _df_base(rng, n)
    pop, renda = base["pop"], base["renda"]
    log_pagantes = -1.0 + 0.7 * np.log(pop) + rng.normal(0, 0.20, n)
    pagantes = np.exp(log_pagantes)
    return pd.DataFrame(
        {
            "unidade": [f"U{i}" for i in range(n)],
            "pagantes_steady_state": pagantes,
            "pop_captacao": pop,
            "renda_per_capita_captacao": renda,
            "n_concorrentes_raio_1_5km": rng.uniform(0, 12, n),  # ruido puro
            "densidade_pop_catchment_hab_km2": rng.uniform(500, 9000, n),  # ruido
            "renda_responsavel_media_catchment": rng.uniform(700, 14000, n),  # ruido
        }
    )


# --- 1. derivar_n_concorrentes_raio: conta certo -----------------------------
def test_derivar_n_concorrentes_retorna_coluna() -> None:
    """Conta concorrentes VALIDOS e NAO-duplicados no raio; ignora invalido/duplicado."""
    # Unidade na origem aproximada (lat0, lng0). 1 grau ~ 111 km.
    lat0, lng0 = -23.5, -46.6
    unidades = pd.DataFrame({"unidade": ["A"], "lat": [lat0], "lng": [lng0]})
    # ~0.005 grau ~ 0.55 km (dentro de 1.5 km); ~0.05 grau ~ 5.5 km (fora).
    concorrentes = pd.DataFrame(
        {
            "lat": [lat0 + 0.005, lat0 + 0.008, lat0 + 0.05, lat0 + 0.004, lat0 + 0.006],
            "lng": [lng0, lng0, lng0, lng0, lng0],
            "flag_coord_valida": [True, True, True, False, True],
            "flag_duplicado_rede_coord": [False, False, False, False, True],
        }
    )
    out = derivar_n_concorrentes_raio(unidades, concorrentes, raio_km=1.5)
    assert list(out.columns) == ["unidade", "n_concorrentes_raio_1_5km"]
    # Dentro do raio + valido + nao-duplicado: linhas 0 e 1. Linha 3 invalida, linha 4
    # duplicada, linha 2 fora do raio -> total 2.
    assert out.loc[0, "n_concorrentes_raio_1_5km"] == 2.0


# --- 2. raio muito pequeno -> 0 (e lat/lng NaN -> NaN) -----------------------
def test_derivar_n_concorrentes_sem_vizinhos() -> None:
    """Raio minusculo -> 0 para todos; unidade sem lat/lng -> NaN (nao 0)."""
    lat0, lng0 = -23.5, -46.6
    unidades = pd.DataFrame(
        {"unidade": ["A", "B"], "lat": [lat0, np.nan], "lng": [lng0, np.nan]}
    )
    concorrentes = pd.DataFrame(
        {
            "lat": [lat0 + 0.005],
            "lng": [lng0],
            "flag_coord_valida": [True],
            "flag_duplicado_rede_coord": [False],
        }
    )
    out = derivar_n_concorrentes_raio(unidades, concorrentes, raio_km=0.0001)
    assert out.loc[0, "n_concorrentes_raio_1_5km"] == 0.0
    assert pd.isna(out.loc[1, "n_concorrentes_raio_1_5km"])


# --- 3. comparar_modelos retorna dict com 3 chaves ---------------------------
def test_comparar_modelos_retorna_dict_com_chaves(
    df_features_sinal: pd.DataFrame,
) -> None:
    """3 feature_sets -> 3 ResultadoModeloFeatures com veredito valido."""
    resultados = comparar_modelos_aderencia(df_features_sinal)
    assert set(resultados.keys()) == set(FEATURE_SETS.keys())
    assert len(resultados) == 3
    for r in resultados.values():
        assert isinstance(r, ResultadoModeloFeatures)
        assert r.veredito in {"GO", "NO-GO"}
        assert np.isfinite(r.r2_loo_log)
        assert r.n_treinamento >= 5


# --- 4. baseline LOO em fixture SEM sinal exogeno ----------------------------
def test_comparar_modelos_baseline_r2_loo(df_features_ruido: pd.DataFrame) -> None:
    """Com ruido exogeno, o componente A/B nao melhora materialmente o baseline."""
    resultados = comparar_modelos_aderencia(df_features_ruido)
    base_r2 = resultados["baseline_pop_renda"].r2_loo_log
    # Adicionar ruido (n_conc/densidade aleatorios) NAO melhora materialmente (>+0.05).
    assert resultados["A_pop_renda_conc"].r2_loo_log <= base_r2 + LIMIAR_R2_GO
    assert (
        resultados["B_pop_renda_conc_dens_rendaresp"].r2_loo_log
        <= base_r2 + LIMIAR_R2_GO
    )


# --- 5. controle positivo: feature correlacionada captura sinal --------------
def test_comparar_modelos_com_sinal_injetado(df_features_sinal: pd.DataFrame) -> None:
    """Feature n_conc correlacionada com pagantes -> modelo A supera o baseline."""
    resultados = comparar_modelos_aderencia(df_features_sinal)
    base_r2 = resultados["baseline_pop_renda"].r2_loo_log
    conc_r2 = resultados["A_pop_renda_conc"].r2_loo_log
    # O pipeline CAPTA sinal exogeno real quando ele existe.
    assert conc_r2 > base_r2


# --- 6. controle negativo: features aleatorias nao dao GO espurio ------------
def test_controle_negativo_features_aleatorias(
    df_features_ruido: pd.DataFrame,
) -> None:
    """Features sem correlacao -> nenhum GO MATERIAL espurio nos sets exogenos."""
    resultados = comparar_modelos_aderencia(df_features_ruido)
    base_r2 = resultados["baseline_pop_renda"].r2_loo_log
    for nome in ("A_pop_renda_conc", "B_pop_renda_conc_dens_rendaresp"):
        r = resultados[nome]
        material = r.r2_loo_log > LIMIAR_R2_GO and r.r2_loo_log > base_r2 + LIMIAR_R2_GO
        assert not material, f"{nome} virou GO material espurio com features de ruido"


# --- 7. montar_df_features remove linhas com NaN em lat/lng ------------------
def test_montar_df_features_remove_nan(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unidade sem lat/lng e removida; censo e mockado (sem I/O real)."""
    df_maduras = pd.DataFrame(
        {
            "unidade": ["A", "B", "C"],
            "uf": ["SP", "SP", "RJ"],
            "pagantes_steady_state": [800.0, 1200.0, 600.0],
            "pop_captacao": [20000.0, 35000.0, 15000.0],
            "renda_per_capita_captacao": [3000.0, 4500.0, 2500.0],
        }
    )
    df_catchment = pd.DataFrame(
        {
            "unidade": ["A", "B", "C"],
            "lat": [-23.5, np.nan, -22.9],  # B sem lat
            "lng": [-46.6, np.nan, -43.2],
        }
    )
    df_conc = pd.DataFrame(
        {
            "lat": [-23.501],
            "lng": [-46.6],
            "flag_coord_valida": [True],
            "flag_duplicado_rede_coord": [False],
        }
    )

    # Mockar derivar_features_censo para nao tocar geo parquets.
    def _fake_censo(df_unidades, geo_base_dir, raio_km=1.5, setores_loader=None):
        return pd.DataFrame(
            {
                "unidade": df_unidades["unidade"].tolist(),
                "densidade_pop_catchment_hab_km2": [1000.0] * len(df_unidades),
                "renda_responsavel_media_catchment": [3000.0] * len(df_unidades),
                "pop_total_raio": [np.nan] * len(df_unidades),
                "n_setores_captacao_censo": [0] * len(df_unidades),
            }
        )

    monkeypatch.setattr(
        "motor_expansao.dimensionamento.features_exogenas.derivar_features_censo",
        _fake_censo,
    )

    out = montar_df_features(df_maduras, df_catchment, df_conc, geo_base_dir="/nonexistent")
    # B removida por lat/lng NaN -> N efetivo 2.
    assert len(out) == 2
    assert set(out["unidade"]) == {"A", "C"}
    assert "n_concorrentes_raio_1_5km" in out.columns
    assert "densidade_pop_catchment_hab_km2" in out.columns


# --- extra: _loo_ridge_multifeature retorna chaves esperadas -----------------
def test_loo_ridge_multifeature_chaves() -> None:
    rng = np.random.default_rng(3)
    n = 30
    X = rng.normal(size=(n, 4))
    y = 0.5 * X[:, 0] - 0.3 * X[:, 1] + rng.normal(0, 0.2, n)
    out = _loo_ridge_multifeature(X, y)
    esperadas = {
        "alpha_selecionado",
        "r2_loo_log",
        "rmse_loo_log",
        "r2_loo_pagantes",
        "rmse_loo_pagantes",
        "r2_insample_log",
        "coef",
        "intercepto_log",
    }
    assert esperadas <= set(out.keys())
    assert np.isfinite(out["r2_loo_log"])
    assert out["coef"].shape == (4,)


# --- extra: n insuficiente levanta ValueError --------------------------------
def test_comparar_levanta_se_n_insuficiente() -> None:
    df = pd.DataFrame(
        {
            "pagantes_steady_state": [800.0, 1200.0, 600.0],
            "pop_captacao": [20000.0, 35000.0, 15000.0],
            "renda_per_capita_captacao": [3000.0, 4500.0, 2500.0],
            "n_concorrentes_raio_1_5km": [3.0, 5.0, 1.0],
            "densidade_pop_catchment_hab_km2": [1000.0, 2000.0, 800.0],
            "renda_responsavel_media_catchment": [3000.0, 4500.0, 2500.0],
        }
    )
    with pytest.raises(ValueError, match="insuficientes"):
        comparar_modelos_aderencia(df)
