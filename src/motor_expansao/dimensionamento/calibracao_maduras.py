"""Consolidacao da base de calibracao das unidades maduras (BLK-DIM).

Cruza a serie historica da Growth API (`growth_api_historico.parquet`, agregados
diarios por unidade/data), o catchment censitario (`unidades_ultra_catchment.parquet`)
e o performance parquet (`unidades_ultra_performance_hex.parquet`, READ-ONLY) numa
linha por unidade, com steady-state (mediana dos ultimos N meses), maturacao real
(via `inauguracao`) e coluna `lacunas` de auditoria.

ZERO PII em disco; READ-ONLY sobre o M1.
"""

from __future__ import annotations

import pandas as pd

from motor_expansao.dimensionamento import config
from motor_expansao.dimensionamento.growth_api_client import normalizar_unidade

# Reexport para o Passo 3/4 partilharem a mesma normalizacao.
__all__ = ["normalizar_unidade", "consolidar_base_calibracao"]

# Campos cuja ausencia/NaN entra na auditoria `lacunas`.
_CAMPOS_LACUNA = (
    "pagantes_steady_state",
    "churn_steady",
    "ticket_steady",
    "meses_desde_inauguracao",
    "pop_captacao",
    "renda_per_capita_captacao",
    "metragem",
    "faturamento",
)


def _to_dt(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", dayfirst=True)


def _mediana_ultimos_meses(
    sub: pd.DataFrame,
    coluna: str,
    data_ref: pd.Timestamp,
    n_meses: int,
) -> float:
    if coluna not in sub.columns:
        return float("nan")
    corte = data_ref - pd.DateOffset(months=n_meses)
    janela = sub.loc[sub["_data"] >= corte, coluna]
    valores = pd.to_numeric(janela, errors="coerce").dropna()
    if valores.empty:
        # fallback: usa toda a serie da unidade se a janela ficou vazia
        valores = pd.to_numeric(sub[coluna], errors="coerce").dropna()
    return float(valores.median()) if not valores.empty else float("nan")


def consolidar_base_calibracao(
    perf_df: pd.DataFrame,
    historico_df: pd.DataFrame,
    catchment_df: pd.DataFrame,
    n_meses_steady: int = config.N_MESES_STEADY,
    meses_madura: int = config.MESES_MADURA,
) -> pd.DataFrame:
    """Consolida 1 linha por unidade (chave = `unidade_norm`)."""
    perf = perf_df.copy()
    perf["unidade_norm"] = perf["unidade"].map(normalizar_unidade)

    hist = historico_df.copy()
    if not hist.empty:
        hist["unidade_norm"] = hist["unidade"].map(normalizar_unidade)
        hist["_data"] = _to_dt(hist["data"]) if "data" in hist.columns else pd.NaT
    else:
        hist["unidade_norm"] = pd.Series(dtype="object")
        hist["_data"] = pd.Series(dtype="datetime64[ns]")

    catch = catchment_df.copy()
    if "unidade_norm" not in catch.columns and "unidade" in catch.columns:
        catch["unidade_norm"] = catch["unidade"].map(normalizar_unidade)

    # data de referencia global = data mais recente observada no historico.
    data_ref = (
        hist["_data"].max()
        if "_data" in hist.columns and hist["_data"].notna().any()
        else pd.Timestamp.today().normalize()
    )

    linhas: list[dict] = []
    for unidade_norm, perf_row in perf.groupby("unidade_norm", dropna=False).first().iterrows():
        sub = hist.loc[hist["unidade_norm"] == unidade_norm] if not hist.empty else hist
        registro: dict = {
            "unidade": perf_row.get("unidade"),
            "unidade_norm": unidade_norm,
            "uf": perf_row.get("uf"),
            "cidade": perf_row.get("cidade"),
            "metragem": pd.to_numeric(perf_row.get("metragem"), errors="coerce"),
            "faturamento": pd.to_numeric(perf_row.get("faturamento"), errors="coerce"),
            "alunos_por_m2": pd.to_numeric(perf_row.get("alunos_por_m2"), errors="coerce"),
            "ticket_medio_aluno": pd.to_numeric(
                perf_row.get("ticket_medio_aluno"), errors="coerce"
            ),
        }

        # steady-state da serie temporal (mediana dos ultimos n_meses).
        registro["pagantes_steady_state"] = _mediana_ultimos_meses(
            sub, "pagantes", data_ref, n_meses_steady
        )
        registro["churn_steady"] = _mediana_ultimos_meses(
            sub, "churn", data_ref, n_meses_steady
        )
        registro["ticket_steady"] = _mediana_ultimos_meses(
            sub, "ticket_medio", data_ref, n_meses_steady
        )
        registro["cancelados_steady"] = _mediana_ultimos_meses(
            sub, "cancelados", data_ref, n_meses_steady
        )
        registro["ativos_total_steady"] = _mediana_ultimos_meses(
            sub, "ativos_total", data_ref, n_meses_steady
        )
        registro["inadimplente_steady"] = _mediana_ultimos_meses(
            sub, "inadimplente", data_ref, n_meses_steady
        )

        # maturacao real via inauguracao.
        inaug = pd.NaT
        if not sub.empty and "inauguracao" in sub.columns:
            inaug_vals = _to_dt(sub["inauguracao"]).dropna()
            if not inaug_vals.empty:
                inaug = inaug_vals.iloc[0]
        if pd.notna(inaug):
            meses = (data_ref.year - inaug.year) * 12 + (data_ref.month - inaug.month)
            registro["inauguracao"] = inaug.date().isoformat()
            registro["meses_desde_inauguracao"] = int(meses)
            registro["flag_madura"] = bool(meses >= meses_madura)
        else:
            registro["inauguracao"] = None
            registro["meses_desde_inauguracao"] = float("nan")
            registro["flag_madura"] = False

        linhas.append(registro)

    base = pd.DataFrame(linhas)

    # join do catchment por unidade_norm.
    catch_cols = [
        c
        for c in ("unidade_norm", "pop_captacao", "renda_per_capita_captacao", "n_setores_captacao", "raio_km")
        if c in catch.columns
    ]
    if catch_cols and "unidade_norm" in catch_cols:
        base = base.merge(
            catch[catch_cols].drop_duplicates("unidade_norm"),
            on="unidade_norm",
            how="left",
        )

    # coluna `lacunas`: lista dos campos NaN/ausentes por unidade (auditoria).
    def _lacunas(row: pd.Series) -> list[str]:
        out: list[str] = []
        for campo in _CAMPOS_LACUNA:
            if campo not in row.index:
                out.append(campo)
                continue
            val = row[campo]
            if val is None or (isinstance(val, float) and pd.isna(val)) or (
                isinstance(val, str) and not val.strip()
            ):
                out.append(campo)
        return out

    base["lacunas"] = base.apply(_lacunas, axis=1)
    return base.reset_index(drop=True)


def resumo_consolidacao(base: pd.DataFrame) -> dict:
    """Metricas de auditoria: % inauguracao real, distribuicao de maturacao."""
    n = len(base)
    com_inaug = (
        base["inauguracao"].notna() & (base["inauguracao"].astype(str).str.strip() != "")
        if "inauguracao" in base.columns
        else pd.Series([False] * n)
    )
    meses_validos = (
        pd.to_numeric(base["meses_desde_inauguracao"], errors="coerce").dropna()
        if "meses_desde_inauguracao" in base.columns
        else pd.Series(dtype="float64")
    )
    return {
        "n_unidades": n,
        "pct_inauguracao_real": round(100.0 * float(com_inaug.sum()) / max(1, n), 1),
        "n_maduras": int(base["flag_madura"].sum()) if "flag_madura" in base.columns else 0,
        "meses_desde_inauguracao_nunique": int(meses_validos.nunique()),
        "meses_min": float(meses_validos.min()) if not meses_validos.empty else None,
        "meses_max": float(meses_validos.max()) if not meses_validos.empty else None,
        "n_com_lacunas": int((base["lacunas"].map(len) > 0).sum())
        if "lacunas" in base.columns
        else 0,
    }
