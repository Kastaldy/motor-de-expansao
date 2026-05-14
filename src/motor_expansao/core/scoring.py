"""Pure scoring helpers for the M1 expansion model."""

from __future__ import annotations

import pandas as pd

from motor_expansao.core.constants import (
    M1_POP_MINIMA_PROXY,
    PERCENTIL_CORTE_INFERIOR,
    PERCENTIL_CORTE_SUPERIOR,
    PESOS_HEX_SCORE,
    PESOS_HEX_SCORE_ESTRUTURAL,
    PESOS_HEX_SCORE_FINAL,
)


def _serie_numerica(df: pd.DataFrame, coluna: str) -> pd.Series:
    if coluna not in df.columns:
        return pd.Series([float("nan")] * len(df), index=df.index, dtype="float64")
    return pd.to_numeric(df[coluna], errors="coerce")


def normalizar_serie(serie: pd.Series) -> pd.Series:
    mn, mx = serie.min(), serie.max()
    if mx == mn:
        return pd.Series([50.0] * len(serie), index=serie.index)
    return ((serie - mn) / (mx - mn)) * 100


normalizar_0_100 = normalizar_serie


def _normalizar_serie_disponivel(
    serie: pd.Series,
    considerar_zero_como_ausente: bool = True,
) -> pd.Series:
    serie = pd.to_numeric(serie, errors="coerce")
    mascara = serie.notna()
    if considerar_zero_como_ausente:
        mascara &= serie > 0

    resultado = pd.Series([float("nan")] * len(serie), index=serie.index, dtype="float64")
    if not mascara.any():
        return resultado

    resultado.loc[mascara] = normalizar_serie(serie.loc[mascara])
    return resultado


def _calcular_percentil_nacional(serie: pd.Series) -> pd.Series:
    serie = pd.to_numeric(serie, errors="coerce")
    resultado = pd.Series([float("nan")] * len(serie), index=serie.index, dtype="float64")
    mascara = serie.notna()
    if not mascara.any():
        return resultado

    serie_validos = serie.loc[mascara]
    if len(serie_validos) == 1:
        resultado.loc[mascara] = 0.5
        return resultado

    ranks = serie_validos.rank(method="average")
    resultado.loc[mascara] = (ranks - 1) / (len(serie_validos) - 1)
    return resultado.round(6)


def _combinar_scores_proporcionalmente(
    index: pd.Index,
    componentes: list[tuple[pd.Series, float, pd.Series]],
) -> pd.Series:
    numerador = pd.Series(0.0, index=index, dtype="float64")
    denominador = pd.Series(0.0, index=index, dtype="float64")

    for serie_score, peso, disponibilidade in componentes:
        score = pd.to_numeric(serie_score, errors="coerce")
        numerador = numerador.add(score.fillna(0.0) * peso, fill_value=0.0)
        denominador = denominador.add(disponibilidade.astype(float) * peso, fill_value=0.0)

    resultado = pd.Series([float("nan")] * len(index), index=index, dtype="float64")
    mascara = denominador > 0
    if mascara.any():
        resultado.loc[mascara] = (numerador.loc[mascara] / denominador.loc[mascara]).round(2)
    return resultado


def calcular_populacao_proxy(df: pd.DataFrame) -> pd.Series:
    pop_18_45 = _serie_numerica(df, "pop_18_45")
    pop_total = _serie_numerica(df, "pop_total")
    return pop_18_45.where(pop_18_45 > 0, pop_total)


def calcular_ajuste_executivo(
    renda_pct_nacional: pd.Series,
    pop_pct_nacional: pd.Series,
) -> pd.Series:
    renda_pct_nacional = pd.to_numeric(renda_pct_nacional, errors="coerce")
    pop_pct_nacional = pd.to_numeric(pop_pct_nacional, errors="coerce")

    renda_alta = renda_pct_nacional >= PERCENTIL_CORTE_SUPERIOR
    pop_alta = pop_pct_nacional >= PERCENTIL_CORTE_SUPERIOR
    renda_baixa = renda_pct_nacional < PERCENTIL_CORTE_INFERIOR
    pop_baixa = pop_pct_nacional < PERCENTIL_CORTE_INFERIOR

    bonus = pd.Series(0.0, index=renda_pct_nacional.index, dtype="float64")
    bonus.loc[renda_alta & pop_alta] = 5.0
    bonus.loc[renda_alta & ~pop_alta] = 2.0
    bonus.loc[pop_alta & ~renda_alta] = 1.0

    penalidade = pd.Series(0.0, index=renda_pct_nacional.index, dtype="float64")
    penalidade.loc[renda_baixa] -= 5.0
    penalidade.loc[pop_baixa] -= 3.0

    return (bonus + penalidade).round(2)


def resumir_distribuicao_score(serie: pd.Series) -> dict:
    serie = pd.to_numeric(serie, errors="coerce").dropna()
    if serie.empty:
        return {
            "count": 0,
            "min": None,
            "max": None,
            "media": None,
            "mediana": None,
            "std": None,
            "p90": None,
            "p95": None,
        }
    return {
        "count": int(len(serie)),
        "min": round(float(serie.min()), 2),
        "max": round(float(serie.max()), 2),
        "media": round(float(serie.mean()), 2),
        "mediana": round(float(serie.median()), 2),
        "std": round(float(serie.std(ddof=0)), 2),
        "p90": round(float(serie.quantile(0.90)), 2),
        "p95": round(float(serie.quantile(0.95)), 2),
    }


def _normalizar_coluna_ou_padrao(
    df: pd.DataFrame,
    colunas: tuple[str, ...],
    default: float,
) -> pd.Series:
    for coluna in colunas:
        if coluna in df.columns and df[coluna].notna().any():
            return normalizar_serie(pd.to_numeric(df[coluna], errors="coerce").fillna(0.0))
    return pd.Series([default] * len(df), index=df.index)


def calcular_hex_score(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["renda_norm"] = _normalizar_coluna_ou_padrao(df, ("renda_per_capita", "renda_media"), 50.0)
    df["pop_norm"] = _normalizar_coluna_ou_padrao(df, ("pop_18_45",), 50.0)

    coluna_concorrencia = "n_academias_osm" if "n_academias_osm" in df.columns else "n_concorrentes"
    if coluna_concorrencia in df.columns:
        concorrencia = pd.to_numeric(df[coluna_concorrencia], errors="coerce").fillna(0.0)
    else:
        concorrencia = pd.Series([0.0] * len(df), index=df.index)
    df["concorrencia_norm"] = normalizar_serie(1 / (concorrencia + 1))

    if "score_vitalidade" in df.columns:
        df["vitalidade_norm"] = pd.to_numeric(df["score_vitalidade"], errors="coerce").fillna(50.0)
    else:
        df["vitalidade_norm"] = 50.0

    df["hex_score"] = (
        df["renda_norm"] * PESOS_HEX_SCORE["renda_normalizada"]
        + df["pop_norm"] * PESOS_HEX_SCORE["pop_jovem_normalizada"]
        + df["concorrencia_norm"] * PESOS_HEX_SCORE["ausencia_concorrencia"]
        + df["vitalidade_norm"] * PESOS_HEX_SCORE["vitalidade_comercial"]
    ).round(2)
    return df


def calcular_hex_score_estrutural(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["renda_per_capita"] = _serie_numerica(df, "renda_per_capita")
    df["pop_total"] = _serie_numerica(df, "pop_total")
    df["pop_18_45"] = _serie_numerica(df, "pop_18_45")
    df["populacao_proxy"] = calcular_populacao_proxy(df)

    hex_populado = df["populacao_proxy"] >= M1_POP_MINIMA_PROXY
    df["hex_sem_populacao"] = ~hex_populado

    df["renda_pct_nacional"] = _calcular_percentil_nacional(
        df["renda_per_capita"].where(hex_populado)
    )
    df["pop_pct_nacional"] = _calcular_percentil_nacional(
        df["populacao_proxy"].where(hex_populado)
    )
    df["hex_score_estrutural"] = (
        100
        * (
            PESOS_HEX_SCORE_ESTRUTURAL["renda_per_capita"] * df["renda_pct_nacional"]
            + PESOS_HEX_SCORE_ESTRUTURAL["populacao_proxy"] * df["pop_pct_nacional"]
        )
    ).round(2)
    df["ajuste_executivo"] = calcular_ajuste_executivo(
        df["renda_pct_nacional"],
        df["pop_pct_nacional"],
    )
    df.loc[~hex_populado, ["hex_score_estrutural", "ajuste_executivo"]] = 0.0
    df["score_priorizacao"] = (
        (df["hex_score_estrutural"] + df["ajuste_executivo"]).clip(lower=0, upper=100)
    ).round(2)
    return df


def calcular_score_concorrencia(df: pd.DataFrame) -> pd.Series:
    contagem = _serie_numerica(df, "n_academias_osm")
    mascara = contagem.notna() & (contagem >= 0)
    resultado = pd.Series([float("nan")] * len(df), index=df.index, dtype="float64")
    if mascara.any():
        resultado.loc[mascara] = normalizar_serie(1 / (contagem.loc[mascara] + 1)).round(2)
    return resultado


def calcular_hex_score_final(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["score_concorrencia"] = (
        _serie_numerica(df, "score_concorrencia")
        if "score_concorrencia" in df.columns
        else calcular_score_concorrencia(df)
    )
    df["hex_score_estrutural"] = _serie_numerica(df, "hex_score_estrutural")
    bruto = _combinar_scores_proporcionalmente(
        df.index,
        [
            (
                df["hex_score_estrutural"],
                PESOS_HEX_SCORE_FINAL["hex_score_estrutural"],
                df["hex_score_estrutural"].notna(),
            ),
            (
                df["score_concorrencia"],
                PESOS_HEX_SCORE_FINAL["score_concorrencia"],
                df["score_concorrencia"].notna(),
            ),
        ],
    )
    df["hex_score_final"] = pd.Series([float("nan")] * len(df), index=df.index, dtype="float64")
    mascara = bruto.notna()
    if mascara.any():
        df.loc[mascara, "hex_score_final"] = normalizar_serie(bruto.loc[mascara]).round(2)
    return df
