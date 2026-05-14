from __future__ import annotations

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from pathlib import Path

from dashboard.constants import (
    BOOL_COLUMNS,
    COVERAGE_BUCKET_ORDER,
    FAIXA_ORDEM,
    FLOAT_COLUMNS,
    HYBRID_ELIGIBILITY_ORDER,
    JOIN_QUALITY_ORDER,
    MAP_SORT_ASCENDING,
    MAP_SORT_COLUMNS,
    OPTIONAL_DATASET_COLUMNS,
    TEXT_COLUMNS,
)


def _read_parquet_subset(path: Path, columns: list[str]) -> pd.DataFrame:
    available_columns = pq.read_schema(path).names
    missing = [column for column in columns if column not in available_columns]
    if missing:
        raise ValueError(
            "O dataset oficial nao contem todas as colunas obrigatorias do dashboard: "
            + ", ".join(missing)
        )
    optional_columns = [
        column for column in OPTIONAL_DATASET_COLUMNS
        if column in available_columns and column not in columns
    ]
    return pd.read_parquet(path, columns=columns + optional_columns)


def _read_optional_parquet_subset(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    available_columns = pq.read_schema(path).names
    cols = [column for column in columns if column in available_columns]
    if not cols:
        return pd.DataFrame()
    return pd.read_parquet(path, columns=cols)


def _normalized_join_quality(df: pd.DataFrame) -> pd.Series:
    if "qualidade_join_uf" not in df.columns:
        return pd.Series("", index=df.index, dtype="object")
    return (
        df["qualidade_join_uf"]
        .astype(object)
        .where(df["qualidade_join_uf"].notna(), "")
        .astype(str)
        .str.upper()
    )


def _has_censo_signal(df: pd.DataFrame) -> pd.Series:
    signal = pd.Series(False, index=df.index)
    if "flag_censo_disponivel" in df.columns:
        signal |= df["flag_censo_disponivel"].fillna(False).astype(bool)
    if "score_setor_2022_calibrado" in df.columns:
        signal |= df["score_setor_2022_calibrado"].notna()
    return signal


def _derive_confianca_geografica(df: pd.DataFrame) -> pd.Series:
    if "confianca_geografica" in df.columns:
        base = (
            df["confianca_geografica"]
            .astype(object)
            .where(df["confianca_geografica"].notna(), "municipal")
            .astype(str)
            .str.lower()
        )
        base = base.where(base.isin(["granular", "municipal"]), "municipal")
    else:
        base = pd.Series("municipal", index=df.index, dtype="object")

    granular_mask = _normalized_join_quality(df).isin(["A", "B"]) & _has_censo_signal(df)
    return pd.Series(
        np.where(granular_mask, "granular", base),
        index=df.index,
        dtype="object",
    )


def _prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    prepared = df.copy()
    for column in FLOAT_COLUMNS:
        if column in prepared.columns:
            prepared[column] = pd.to_numeric(prepared[column], errors="coerce").astype("Float32")

    for column in BOOL_COLUMNS:
        if column in prepared.columns:
            prepared[column] = prepared[column].astype("boolean").fillna(False).astype(bool)

    for column in TEXT_COLUMNS:
        if column in prepared.columns:
            prepared[column] = (
                prepared[column]
                .astype(object)
                .where(prepared[column].notna(), "Nao informado")
                .astype("category")
            )

    if "faixa_oportunidade" in prepared.columns:
        prepared["faixa_oportunidade"] = (
            prepared["faixa_oportunidade"]
            .astype(object)
            .where(prepared["faixa_oportunidade"].notna(), "Nao informado")
        )
        prepared["faixa_oportunidade"] = pd.Categorical(
            prepared["faixa_oportunidade"],
            categories=FAIXA_ORDEM + ["Nao informado"],
            ordered=True,
        )

    if "elegibilidade_hibrida" in prepared.columns:
        prepared["elegibilidade_hibrida"] = pd.Categorical(
            prepared["elegibilidade_hibrida"].fillna("Sem camada"),
            categories=HYBRID_ELIGIBILITY_ORDER,
            ordered=True,
        )

    if "cobertura_censitaria_bucket" in prepared.columns:
        prepared["cobertura_censitaria_bucket"] = pd.Categorical(
            prepared["cobertura_censitaria_bucket"].fillna("Sem camada"),
            categories=COVERAGE_BUCKET_ORDER,
            ordered=True,
        )

    if "qualidade_camada" in prepared.columns:
        prepared["qualidade_camada"] = pd.Categorical(
            prepared["qualidade_camada"].fillna("Sem camada"),
            categories=JOIN_QUALITY_ORDER,
            ordered=True,
        )

    prepared = prepared.sort_values(
        MAP_SORT_COLUMNS,
        ascending=MAP_SORT_ASCENDING,
        kind="stable",
    ).reset_index(drop=True)
    prepared["UF"] = prepared["uf"]
    if "nome_municipio" in prepared.columns:
        prepared["nome_municipio"] = prepared["nome_municipio"].fillna(prepared["cidade"])
    else:
        prepared["nome_municipio"] = prepared["cidade"]
    prepared["score_exibicao"] = prepared["score_priorizacao"]
    return prepared


def _prepare_censo_trace(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    prepared = df.copy()
    if "classe_join_uf" in prepared.columns and "qualidade_join_uf" not in prepared.columns:
        prepared = prepared.rename(columns={"classe_join_uf": "qualidade_join_uf"})

    for column in [
        "score_setor_2022_calibrado",
        "densidade_pop_setor_hab_km2",
        "coverage_pct_setor_2022",
        "delta_vs_vizinhos",
        "renda_per_capita_setor_2022_calibrada",
    ]:
        if column in prepared.columns:
            prepared[column] = pd.to_numeric(prepared[column], errors="coerce").astype("Float32")

    for column in ["flag_join_uf_restrito", "flag_baixa_pop_setor", "flag_outlier_espacial"]:
        if column in prepared.columns:
            prepared[column] = prepared[column].fillna(False).astype(bool)

    return prepared


def _coalesce_columns(df: pd.DataFrame, base_column: str, overlay_column: str) -> pd.DataFrame:
    if overlay_column not in df.columns:
        return df
    if base_column in df.columns:
        df[base_column] = df[base_column].where(df[base_column].notna(), df[overlay_column])
    else:
        df[base_column] = df[overlay_column]
    return df.drop(columns=[overlay_column])


def _derive_hybrid_labels(df: pd.DataFrame) -> pd.DataFrame:
    derived = df.copy()
    available = derived["flag_censo_disponivel"].fillna(False) | derived["score_setor_2022_calibrado"].notna()
    eligible = derived["flag_censo_elegivel"].fillna(False)
    derived["elegibilidade_hibrida"] = np.where(
        eligible,
        "Elegivel",
        np.where(available, "Nao elegivel", "Sem camada"),
    )

    coverage = pd.to_numeric(derived["coverage_pct_setor_2022"], errors="coerce")
    derived["cobertura_censitaria_bucket"] = np.select(
        [
            coverage.ge(99.95).fillna(False).to_numpy(),
            coverage.ge(95.0).fillna(False).to_numpy(),
            coverage.ge(85.0).fillna(False).to_numpy(),
            coverage.notna().to_numpy(),
        ],
        ["100%", "95-99,9%", "85-94,9%", "<85%"],
        default="Sem camada",
    )

    quality = (
        derived["qualidade_join_uf"]
        .astype(object)
        .where(derived["qualidade_join_uf"].notna(), "")
        .astype(str)
        .str.upper()
    )
    derived["qualidade_camada"] = np.where(
        quality.isin(["A", "B", "C"]),
        quality,
        "Sem camada",
    )
    return derived


def enrich_dashboard_data(
    base_df: pd.DataFrame,
    hybrid_df: pd.DataFrame | None = None,
    censo_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    enriched = base_df.copy()
    hybrid_df = hybrid_df if hybrid_df is not None else pd.DataFrame()
    censo_df = censo_df if censo_df is not None else pd.DataFrame()

    hybrid_extra_cols = [
        "hex_id",
        "nome_municipio",
        "confianca_geografica",
        "score_setor_2022_calibrado",
        "score_expansao_hibrido",
        "densidade_pop_setor_hab_km2",
        "top_municipio",
        "top_hex_intraurbano",
        "flag_censo_elegivel",
        "flag_censo_disponivel",
        "flag_hex_hibrido_elegivel",
        "top_municipio_hibrido",
        "municipio_censo_disponivel",
        "rank_municipio_uf",
        "rank_municipio_brasil",
        "rank_hex_intraurbano",
        "rank_hibrido_brasil",
        "rank_hibrido_uf",
        "top_oportunidade_municipio",
        "top_oportunidade_brasil",
        "top_oportunidade_uf",
        "qualidade_join_uf",
        "flag_join_uf_restrito",
        "flag_baixa_pop_setor",
        "flag_outlier_espacial",
        "coverage_pct_setor_2022",
        "motivo_nao_elegivel_censo",
        "status_espacial_uf",
        "fonte_camada_censitaria",
        "flag_monitoramento_prioritario",
        "criterio_score_expansao_hibrido",
        "camada_modelo_hibrido",
    ]
    if not hybrid_df.empty:
        hybrid_subset = hybrid_df[[column for column in hybrid_extra_cols if column in hybrid_df.columns]]
        enriched = enriched.merge(hybrid_subset, on="hex_id", how="left")

    censo_extra_cols = [
        "hex_id",
        "nome_municipio",
        "confianca_geografica",
        "score_setor_2022_calibrado",
        "densidade_pop_setor_hab_km2",
        "coverage_pct_setor_2022",
        "qualidade_join_uf",
        "flag_join_uf_restrito",
        "flag_baixa_pop_setor",
        "flag_outlier_espacial",
        "causa_outlier_espacial",
        "delta_vs_vizinhos",
        "metodo_join_setor_2022",
        "motivo_fallback_setor_2022",
        "renda_per_capita_setor_2022_calibrada",
    ]
    if not censo_df.empty:
        censo_subset = censo_df[[column for column in censo_extra_cols if column in censo_df.columns]]
        enriched = enriched.merge(censo_subset, on="hex_id", how="left", suffixes=("", "_censo"))

        for column in [
            "nome_municipio",
            "score_setor_2022_calibrado",
            "densidade_pop_setor_hab_km2",
            "coverage_pct_setor_2022",
            "qualidade_join_uf",
            "flag_join_uf_restrito",
            "flag_baixa_pop_setor",
            "flag_outlier_espacial",
        ]:
            censo_column = f"{column}_censo"
            enriched = _coalesce_columns(enriched, column, censo_column)

    for column in [
        "top_municipio",
        "top_hex_intraurbano",
        "flag_censo_elegivel",
        "flag_censo_disponivel",
        "flag_hex_hibrido_elegivel",
        "top_municipio_hibrido",
        "municipio_censo_disponivel",
        "flag_join_uf_restrito",
        "flag_baixa_pop_setor",
        "flag_outlier_espacial",
        "flag_monitoramento_prioritario",
        "top_oportunidade_municipio",
        "top_oportunidade_brasil",
        "top_oportunidade_uf",
    ]:
        if column not in enriched.columns:
            enriched[column] = False

    for column in [
        "qualidade_join_uf",
        "motivo_nao_elegivel_censo",
        "status_espacial_uf",
        "fonte_camada_censitaria",
        "criterio_score_expansao_hibrido",
        "camada_modelo_hibrido",
        "causa_outlier_espacial",
        "metodo_join_setor_2022",
        "motivo_fallback_setor_2022",
    ]:
        if column not in enriched.columns:
            enriched[column] = pd.NA

    if "nome_municipio" not in enriched.columns:
        enriched["nome_municipio"] = enriched["cidade"]

    enriched["nome_municipio"] = (
        enriched["nome_municipio"]
        .fillna(enriched["cidade"])
        .replace({"": pd.NA})
        .fillna(enriched["cidade"])
    )
    enriched["confianca_geografica"] = _derive_confianca_geografica(enriched)
    enriched = _derive_hybrid_labels(enriched)
    return _prepare_dataframe(enriched)


def apply_global_filters(
    df: pd.DataFrame,
    *,
    selected_ufs: list[str],
    selected_cities: list[str],
    selected_faixas: list[str],
    selected_hybrid_eligibility: list[str] | None = None,
    selected_coverage_buckets: list[str] | None = None,
    selected_join_quality: list[str] | None = None,
    only_top_municipio: bool = False,
    only_top_hex_intraurbano: bool = False,
) -> pd.DataFrame:
    selected_hybrid_eligibility = selected_hybrid_eligibility or []
    selected_coverage_buckets = selected_coverage_buckets or []
    selected_join_quality = selected_join_quality or []
    mask = pd.Series(True, index=df.index)
    if selected_ufs:
        mask &= df["uf"].isin(selected_ufs)
    if selected_cities:
        city_col = "nome_municipio" if "nome_municipio" in df.columns else "cidade"
        mask &= df[city_col].isin(selected_cities)
    if selected_faixas:
        mask &= df["faixa_oportunidade"].isin(selected_faixas)
    if selected_hybrid_eligibility and "elegibilidade_hibrida" in df.columns:
        mask &= df["elegibilidade_hibrida"].isin(selected_hybrid_eligibility)
    if selected_coverage_buckets and "cobertura_censitaria_bucket" in df.columns:
        mask &= df["cobertura_censitaria_bucket"].isin(selected_coverage_buckets)
    if selected_join_quality and "qualidade_camada" in df.columns:
        mask &= df["qualidade_camada"].isin(selected_join_quality)
    if only_top_municipio and "top_municipio" in df.columns:
        mask &= df["top_municipio"] == True
    if only_top_hex_intraurbano and "top_hex_intraurbano" in df.columns:
        mask &= df["top_hex_intraurbano"] == True
    return df.loc[mask]


def build_city_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=[
                "uf",
                "cidade",
                "total_hexagonos",
                "oportunidades_viaveis",
                "hexagonos_priorizados",
                "score_medio",
                "renda_per_capita",
                "populacao_proxy",
                "melhor_rank_brasil",
                "pct_priorizados",
            ]
        )

    grouped = (
        df.groupby(["uf", "cidade"], as_index=False, observed=True)
        .agg(
            total_hexagonos=("hex_id", "size"),
            oportunidades_viaveis=("flag_viavel", "sum"),
            hexagonos_priorizados=("flag_prioridade", "sum"),
            score_medio=("score_priorizacao", "mean"),
            renda_per_capita=("renda_per_capita", "mean"),
            populacao_proxy=("populacao_proxy", "mean"),
            melhor_rank_brasil=("rank_brasil", "min"),
        )
        .copy()
    )
    grouped["pct_priorizados"] = (
        grouped["hexagonos_priorizados"] / grouped["total_hexagonos"] * 100
    ).fillna(0.0)
    return grouped


def build_uf_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=[
                "uf",
                "total_hexagonos",
                "oportunidades_viaveis",
                "hexagonos_priorizados",
                "score_medio",
                "pct_priorizados",
            ]
        )

    grouped = (
        df.groupby("uf", as_index=False, observed=True)
        .agg(
            total_hexagonos=("hex_id", "size"),
            oportunidades_viaveis=("flag_viavel", "sum"),
            hexagonos_priorizados=("flag_prioridade", "sum"),
            score_medio=("score_priorizacao", "mean"),
        )
        .copy()
    )
    grouped["pct_priorizados"] = (
        grouped["hexagonos_priorizados"] / grouped["total_hexagonos"] * 100
    ).fillna(0.0)
    return grouped
