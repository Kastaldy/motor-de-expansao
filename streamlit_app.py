from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import pydeck as pdk
import pyarrow.parquet as pq
import streamlit as st
from streamlit.runtime.scriptrunner import get_script_run_ctx
from streamlit.web import cli as stcli

from dashboard.constants import (  # noqa: F401
    BOOL_COLUMNS,
    BRASIL_CENTER,
    CENSO_SCORE_COLORS,
    CENSO_TRACE_LOAD_COLS,
    CENSO_UFS,
    COLORS,
    COVERAGE_BUCKET_ORDER,
    FAIXA_COLORS,
    FAIXA_ORDEM,
    FLOAT_COLUMNS,
    HYBRID_ELIGIBILITY_ORDER,
    HYBRID_LOAD_COLS,
    JOIN_QUALITY_ORDER,
    MAP_POINT_LIMIT,
    MAP_SORT_ASCENDING,
    MAP_SORT_COLUMNS,
    OPTIONAL_DATASET_COLUMNS,
    REQUIRED_COLUMNS,
    TABLE_ROW_LIMIT,
    TEXT_COLUMNS,
)
from dashboard.utils import (  # noqa: F401
    _censo_score_to_color,
    format_density,
    format_int,
    format_pct,
    format_score,
    hex_to_rgba,
)

st.set_page_config(
    page_title="Ultra Academia | Dashboard Executivo M1 + Hibrido",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATASET_PATH = Path(__file__).resolve().parent / "data" / "outputs" / "hexagonos_brasil_dashboard.parquet"
HYBRID_PATH = Path(__file__).resolve().parent / "data" / "outputs" / "oportunidades_expansao_hibrido.parquet"
CARTEIRA_PATH = Path(__file__).resolve().parent / "data" / "outputs" / "carteira_expansao_acionavel.parquet"
PLANO_PATH = Path(__file__).resolve().parent / "data" / "outputs" / "plano_expansao_curto_prazo.parquet"
CENSO_CORE_PATH = Path(__file__).resolve().parent / "data" / "staging" / "censo2022_setores_calibrado.parquet"
CENSO_EXPANDED_PATH = (
    Path(__file__).resolve().parent / "data" / "staging" / "censo2022_setores_calibrado_piloto_expandido.parquet"
)
CENSO_VALIDATED_PATH = (
    Path(__file__).resolve().parent / "data" / "staging" / "censo2022_setores_validado_v2.parquet"
)


def inject_styles() -> None:
    st.markdown(
        f"""
        <style>
            .stApp {{
                background:
                    radial-gradient(circle at 12% 18%, rgba(25, 183, 255, 0.18), transparent 28%),
                    radial-gradient(circle at 82% 12%, rgba(255, 77, 141, 0.18), transparent 26%),
                    radial-gradient(circle at 58% 72%, rgba(124, 92, 255, 0.14), transparent 30%),
                    linear-gradient(180deg, {COLORS["bg"]} 0%, {COLORS["bg_alt"]} 100%);
                color: {COLORS["text"]};
                font-family: "Bahnschrift", "Aptos", "Segoe UI", sans-serif;
            }}
            .block-container {{
                padding-top: 1.4rem;
                padding-bottom: 2rem;
            }}
            [data-testid="stSidebar"] {{
                background:
                    radial-gradient(circle at top, rgba(25, 183, 255, 0.12), transparent 30%),
                    linear-gradient(180deg, #0E1324 0%, #0A0F1F 100%);
                border-right: 1px solid {COLORS["border"]};
            }}
            [data-testid="stSidebar"] * {{
                color: {COLORS["text"]};
            }}
            [data-testid="stMetric"] {{
                background: linear-gradient(180deg, rgba(18, 23, 42, 0.96) 0%, rgba(14, 19, 36, 0.96) 100%);
                border: 1px solid {COLORS["border"]};
                border-radius: 18px;
                padding: 1rem 1.1rem;
                box-shadow: 0 16px 36px rgba(0, 0, 0, 0.28);
            }}
            div[data-testid="stMetricLabel"] {{
                color: {COLORS["muted"]};
                font-weight: 600;
            }}
            div[data-testid="stMetricValue"] {{
                color: {COLORS["text"]};
            }}
            div[data-testid="stMetricValue"] > div {{
                color: {COLORS["text"]};
            }}
            .hero {{
                background:
                    radial-gradient(circle at left top, rgba(255, 77, 141, 0.24), transparent 22%),
                    radial-gradient(circle at right center, rgba(25, 183, 255, 0.24), transparent 26%),
                    linear-gradient(135deg, rgba(29, 16, 58, 0.98) 0%, rgba(19, 23, 48, 0.98) 52%, rgba(7, 55, 112, 0.96) 100%);
                color: #FFFFFF;
                padding: 1.35rem 1.5rem;
                border-radius: 22px;
                margin-bottom: 1rem;
                border: 1px solid rgba(133, 151, 228, 0.2);
                box-shadow: 0 22px 48px rgba(0, 0, 0, 0.34);
            }}
            .hero h1 {{
                margin: 0;
                font-size: 1.9rem;
                line-height: 1.15;
                letter-spacing: 0.01em;
            }}
            .hero p {{
                margin: 0.45rem 0 0;
                color: rgba(255, 255, 255, 0.86);
                font-size: 0.98rem;
            }}
            .strip {{
                display: flex;
                gap: 0.6rem;
                flex-wrap: wrap;
                margin-top: 0.8rem;
            }}
            .pill {{
                display: inline-flex;
                align-items: center;
                padding: 0.38rem 0.72rem;
                border-radius: 999px;
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(172, 192, 255, 0.18);
                font-size: 0.82rem;
            }}
            .section-card {{
                background: linear-gradient(180deg, rgba(18, 23, 42, 0.96) 0%, rgba(14, 19, 36, 0.96) 100%);
                border: 1px solid {COLORS["border"]};
                border-radius: 18px;
                padding: 1rem 1.1rem;
                min-height: 160px;
                box-shadow: 0 16px 36px rgba(0, 0, 0, 0.22);
            }}
            .section-card h4 {{
                margin: 0 0 0.55rem;
                color: {COLORS["text"]};
                font-size: 1rem;
            }}
            .section-card p {{
                margin: 0.28rem 0;
                color: {COLORS["text"]};
                line-height: 1.45;
                font-size: 0.92rem;
            }}
            .section-card strong {{
                color: {COLORS["text"]};
            }}
            .model-card {{
                background: linear-gradient(180deg, rgba(18, 23, 42, 0.96) 0%, rgba(14, 19, 36, 0.96) 100%);
                border: 1px solid {COLORS["border"]};
                border-radius: 18px;
                padding: 1rem 1.1rem;
                box-shadow: 0 16px 36px rgba(0, 0, 0, 0.22);
            }}
            .model-card h4 {{
                margin: 0 0 0.45rem;
                font-size: 1rem;
            }}
            .model-card p {{
                margin: 0.2rem 0;
                color: {COLORS["muted"]};
                line-height: 1.45;
                font-size: 0.88rem;
            }}
            .model-card .badge {{
                display: inline-block;
                padding: 0.18rem 0.55rem;
                border-radius: 999px;
                font-size: 0.78rem;
                font-weight: 700;
                margin-bottom: 0.45rem;
            }}
            .legend-row {{
                display: flex;
                flex-wrap: wrap;
                gap: 0.6rem;
                margin: 0.2rem 0 0.8rem;
            }}
            .legend-chip {{
                display: inline-flex;
                gap: 0.35rem;
                align-items: center;
                padding: 0.35rem 0.65rem;
                border-radius: 999px;
                background: rgba(18, 23, 42, 0.92);
                border: 1px solid {COLORS["border"]};
                font-size: 0.82rem;
                color: {COLORS["text"]};
            }}
            .legend-dot {{
                width: 10px;
                height: 10px;
                border-radius: 999px;
                display: inline-block;
            }}
            div[data-testid="stDataFrame"] {{
                border: 1px solid {COLORS["border"]};
                border-radius: 18px;
                overflow: hidden;
                box-shadow: 0 16px 36px rgba(0, 0, 0, 0.22);
            }}
            [data-baseweb="tab-list"] {{
                gap: 0.35rem;
            }}
            [data-baseweb="tab"] {{
                background: rgba(255, 255, 255, 0.02);
                border-radius: 12px 12px 0 0;
                color: {COLORS["muted"]};
                padding-left: 0.85rem;
                padding-right: 0.85rem;
            }}
            [data-baseweb="tab"][aria-selected="true"] {{
                background: rgba(25, 183, 255, 0.08);
                color: {COLORS["text"]};
            }}
            .stCaption {{
                color: {COLORS["muted"]};
            }}
            .stMarkdown, .stText, .stAlert, label, .stSelectbox, .stMultiSelect {{
                color: {COLORS["text"]};
            }}
            .stMultiSelect [data-baseweb="tag"] {{
                background: rgba(25, 183, 255, 0.14);
                border: 1px solid rgba(25, 183, 255, 0.28);
            }}
            .stMultiSelect [data-baseweb="select"], .stSelectbox [data-baseweb="select"] {{
                background: rgba(18, 23, 42, 0.92);
                border-radius: 12px;
                border: 1px solid {COLORS["border"]};
            }}
            .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {{
                font-size: 0.92rem;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    st.markdown(
        """
        <div class="hero">
            <h1>Dashboard Executivo M1 + Modelo Hibrido</h1>
            <p>Onde expandir (M1 municipal) · Qual bairro priorizar (Censitario 2022) · Fila operacional combinada (Hibrido).</p>
            <div class="strip">
                <span class="pill">M1: <strong>&nbsp;score_priorizacao</strong></span>
                <span class="pill">Censitario: <strong>&nbsp;score_setor_2022_calibrado</strong></span>
                <span class="pill">Hibrido: <strong>&nbsp;score_expansao_hibrido</strong></span>
                <span class="pill">UFs censo: <strong>&nbsp;DF GO MG RJ RS SP</strong></span>
                <span class="pill">Filtros na <strong>&nbsp;sidebar</strong></span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _ensure_dataset() -> None:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            "Arquivo oficial ausente: `data/outputs/hexagonos_brasil_dashboard.parquet`."
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


@st.cache_resource(show_spinner=False)
def load_data() -> pd.DataFrame:
    _ensure_dataset()
    df = _read_parquet_subset(DATASET_PATH, REQUIRED_COLUMNS)
    return _prepare_dataframe(df)


@st.cache_resource(show_spinner=False)
def load_hybrid_data() -> pd.DataFrame:
    return _prepare_dataframe(_read_optional_parquet_subset(HYBRID_PATH, HYBRID_LOAD_COLS))


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


@st.cache_resource(show_spinner=False)
def load_censo_trace_data() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in [CENSO_CORE_PATH, CENSO_EXPANDED_PATH]:
        frame = _prepare_censo_trace(_read_optional_parquet_subset(path, CENSO_TRACE_LOAD_COLS))
        if not frame.empty:
            frames.append(frame)

    if not frames:
        return pd.DataFrame()

    censo = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["hex_id"], keep="first")
    validated = _prepare_censo_trace(_read_optional_parquet_subset(CENSO_VALIDATED_PATH, CENSO_TRACE_LOAD_COLS))
    if validated.empty:
        return censo

    overlay_columns = [
        "qualidade_join_uf",
        "flag_join_uf_restrito",
        "flag_baixa_pop_setor",
        "flag_outlier_espacial",
        "causa_outlier_espacial",
        "delta_vs_vizinhos",
        "metodo_join_setor_2022",
        "motivo_fallback_setor_2022",
    ]
    validated = validated[[column for column in ["hex_id"] + overlay_columns if column in validated.columns]]
    censo = censo.merge(validated, on="hex_id", how="left", suffixes=("", "_validado"))

    for column in overlay_columns:
        validated_column = f"{column}_validado"
        censo = _coalesce_columns(censo, column, validated_column)

    return censo


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


@st.cache_resource(show_spinner=False)
def build_dashboard_dataset() -> pd.DataFrame:
    return enrich_dashboard_data(
        load_data(),
        load_hybrid_data(),
        load_censo_trace_data(),
    )


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


def build_kpis(
    df: pd.DataFrame,
    city_summary: pd.DataFrame,
    uf_summary: pd.DataFrame,
) -> dict[str, str]:
    if df.empty:
        return {
            "total_oportunidades_viaveis": "0",
            "total_hexagonos_priorizados": "0",
            "uf_lider_oportunidades": "-",
            "cidade_lider_score": "-",
        }

    uf_lider = (
        uf_summary.sort_values(
            ["oportunidades_viaveis", "score_medio", "uf"],
            ascending=[False, False, True],
            kind="stable",
        )
        .head(1)
        .iloc[0]
    )
    cidade_lider = (
        city_summary.sort_values(
            ["score_medio", "melhor_rank_brasil", "cidade"],
            ascending=[False, True, True],
            kind="stable",
        )
        .head(1)
        .iloc[0]
    )
    return {
        "total_oportunidades_viaveis": format_int(int(df["flag_viavel"].sum())),
        "total_hexagonos_priorizados": format_int(int(df["flag_prioridade"].sum())),
        "uf_lider_oportunidades": f"{uf_lider['uf']}",
        "cidade_lider_score": f"{cidade_lider['cidade']} / {cidade_lider['uf']}",
    }


def build_business_answers(
    city_summary: pd.DataFrame,
    uf_summary: pd.DataFrame,
) -> dict[str, list[str]]:
    if uf_summary.empty or city_summary.empty:
        return {"expandir": [], "priorizar": [], "ufs_priorizar": [], "evitar": []}

    top_expandir = uf_summary.sort_values(
        ["oportunidades_viaveis", "score_medio", "pct_priorizados", "uf"],
        ascending=[False, False, False, True],
        kind="stable",
    ).head(3)
    top_ufs_priorizar = uf_summary.sort_values(
        ["score_medio", "oportunidades_viaveis", "pct_priorizados", "uf"],
        ascending=[False, False, False, True],
        kind="stable",
    ).head(3)
    top_priorizar = city_summary.sort_values(
        ["score_medio", "oportunidades_viaveis", "melhor_rank_brasil", "cidade"],
        ascending=[False, False, True, True],
        kind="stable",
    ).head(3)
    top_evitar = uf_summary.sort_values(
        ["oportunidades_viaveis", "score_medio", "uf"],
        ascending=[True, True, True],
        kind="stable",
    ).head(3)

    return {
        "expandir": [
            f"{row.uf}: {format_int(row.oportunidades_viaveis)} viaveis | score medio {format_score(row.score_medio)}"
            for row in top_expandir.itertuples(index=False)
        ],
        "priorizar": [
            f"{row.cidade}/{row.uf}: score {format_score(row.score_medio)} | rank Brasil {format_int(row.melhor_rank_brasil)}"
            for row in top_priorizar.itertuples(index=False)
        ],
        "ufs_priorizar": [
            f"{row.uf}: score medio {format_score(row.score_medio)} | {format_int(row.oportunidades_viaveis)} viaveis"
            for row in top_ufs_priorizar.itertuples(index=False)
        ],
        "evitar": [
            f"{row.uf}: {format_int(row.oportunidades_viaveis)} viaveis | score medio {format_score(row.score_medio)}"
            for row in top_evitar.itertuples(index=False)
        ],
    }


def render_answer_card(title: str, lines: list[str]) -> None:
    body = "".join(f"<p>{line}</p>" for line in lines) if lines else "<p>Sem dados no recorte atual.</p>"
    st.markdown(
        f"""
        <div class="section-card">
            <h4>{title}</h4>
            {body}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_faixa_legend() -> None:
    chips = "".join(
        [
            (
                f"<span class='legend-chip'>"
                f"<span class='legend-dot' style='background:{FAIXA_COLORS[faixa]};'></span>"
                f"{faixa}"
                f"</span>"
            )
            for faixa in FAIXA_ORDEM
        ]
    )
    st.markdown(f"<div class='legend-row'>{chips}</div>", unsafe_allow_html=True)


def render_geographic_source_legend() -> None:
    entries = [
        ("#C8D3EA", "Setor censitario (qualidade A/B)"),
        ("#F59E0B", "Dado municipal (fallback M1)"),
    ]
    chips = "".join(
        (
            f"<span class='legend-chip'>"
            f"<span class='legend-dot' style='background:{color};'></span>"
            f"{label}"
            f"</span>"
        )
        for color, label in entries
    )
    st.markdown(f"<div class='legend-row'>{chips}</div>", unsafe_allow_html=True)


def render_censo_score_legend() -> None:
    entries = [
        ("#B41E1E", "0-25"),
        ("#DC3232", "25-50"),
        ("#F59E0B", "50-75"),
        ("#14C850", "75-100"),
    ]
    chips = "".join(
        f"<span class='legend-chip'><span class='legend-dot' style='background:{color};'></span>Score {label}</span>"
        for color, label in entries
    )
    st.markdown(f"<div class='legend-row'>{chips}</div>", unsafe_allow_html=True)


def apply_exec_layout(fig, *, title: str, height: int) -> None:
    fig.update_layout(
        title=title,
        height=height,
        paper_bgcolor=COLORS["panel_solid"],
        plot_bgcolor=COLORS["panel_solid"],
        font={"family": "Aptos, Bahnschrift, Segoe UI, sans-serif", "color": COLORS["text"]},
        margin={"l": 12, "r": 12, "t": 56, "b": 12},
        title_font={"size": 18, "color": COLORS["text"]},
        legend={
            "font": {"color": COLORS["text"], "size": 12},
            "title": {"font": {"color": COLORS["text"], "size": 12}},
        },
    )
    fig.update_xaxes(
        showgrid=True,
        gridcolor="rgba(167, 179, 209, 0.12)",
        zeroline=False,
        tickfont={"color": COLORS["text"], "size": 12},
        title_font={"color": COLORS["text"], "size": 13},
    )
    fig.update_yaxes(
        showgrid=False,
        zeroline=False,
        tickfont={"color": COLORS["text"], "size": 12},
        title_font={"color": COLORS["text"], "size": 13},
    )


def resolve_map_view(
    df: pd.DataFrame,
    *,
    selected_ufs: list[str],
    selected_cities: list[str],
) -> tuple[dict[str, float], float]:
    if df.empty:
        return BRASIL_CENTER, 3.2
    if selected_cities:
        center = {"lat": float(df["lat"].mean()), "lon": float(df["lng"].mean())}
        return center, 7.2
    if len(selected_ufs) == 1:
        center = {"lat": float(df["lat"].mean()), "lon": float(df["lng"].mean())}
        return center, 5.2
    return BRASIL_CENTER, 3.2


def build_map_scope_caption(points_used: int, *, selected_ufs: list[str]) -> str:
    scope_label = "da UF selecionada" if len(selected_ufs) == 1 else "do recorte atual"
    return (
        f"Mostrando todos os hexagonos validos {scope_label} "
        f"({format_int(points_used)} no recorte atual), preservando a geometria granular onde ela e confiavel."
    )


def build_map_figure(
    df: pd.DataFrame,
    *,
    selected_ufs: list[str],
    selected_cities: list[str],
):
    map_columns = [
        "hex_id",
        "lat",
        "lng",
        "cidade",
        "nome_municipio",
        "uf",
        "faixa_oportunidade",
        "score_priorizacao",
        "hex_score_estrutural",
        "flag_viavel",
        "flag_prioridade",
        "score_setor_2022_calibrado",
        "coverage_pct_setor_2022",
        "qualidade_join_uf",
        "flag_censo_disponivel",
        "confianca_geografica",
    ]
    valid = df.loc[
        df["hex_id"].notna()
        & df["lat"].notna()
        & df["lng"].notna()
        & df["score_priorizacao"].notna(),
        [column for column in map_columns if column in df.columns],
    ].copy()
    if valid.empty:
        return None, 0

    if "nome_municipio" not in valid.columns:
        valid["nome_municipio"] = valid["cidade"]
    else:
        valid["nome_municipio"] = valid["nome_municipio"].fillna(valid["cidade"])

    if selected_ufs:
        valid = valid.loc[valid["uf"].isin(selected_ufs)].copy()
    if selected_cities:
        valid = valid.loc[valid["nome_municipio"].isin(selected_cities)].copy()
    if valid.empty:
        return None, 0

    quality = _normalized_join_quality(valid)
    has_censo = _has_censo_signal(valid)
    granular_ufs = set(valid.loc[quality.isin(["A", "B"]) & has_censo, "uf"].dropna().tolist())

    granular_rows = valid["uf"].isin(granular_ufs) & has_censo
    municipal_rows = ~valid["uf"].isin(granular_ufs)
    map_df = valid.loc[granular_rows | municipal_rows].copy()
    if map_df.empty:
        return None, 0

    map_df["confianca_geografica"] = np.where(
        map_df["uf"].isin(granular_ufs),
        "granular",
        "municipal",
    )
    map_df = map_df.drop_duplicates(subset=["hex_id"], keep="first").reset_index(drop=True)

    if "score_setor_2022_calibrado" not in map_df.columns:
        map_df["score_setor_2022_calibrado"] = pd.NA
    if "coverage_pct_setor_2022" not in map_df.columns:
        map_df["coverage_pct_setor_2022"] = pd.NA
    if "qualidade_join_uf" not in map_df.columns:
        map_df["qualidade_join_uf"] = pd.NA

    map_df["faixa_label"] = map_df["faixa_oportunidade"].astype(str)
    map_df["fill_color"] = map_df.apply(
        lambda row: (
            _censo_score_to_color(row.get("score_setor_2022_calibrado"))
            if row["confianca_geografica"] == "granular"
            and not pd.isna(row.get("score_setor_2022_calibrado"))
            else hex_to_rgba(
                FAIXA_COLORS.get(row["faixa_label"], COLORS["muted"]),
                96,
            )
        ),
        axis=1,
    )
    map_df["line_color"] = map_df["confianca_geografica"].map(
        {
            "granular": hex_to_rgba(COLORS["map_line"], 122),
            "municipal": [245, 158, 11, 220],
        }
    )
    map_df["fonte_geografica_label"] = map_df["confianca_geografica"].map(
        {
            "granular": "Setor censitario (qualidade A/B)",
            "municipal": "Dado municipal (fallback M1)",
        }
    )
    map_df["score_priorizacao_fmt"] = map_df["score_priorizacao"].map(format_score)
    map_df["hex_score_estrutural_fmt"] = map_df["hex_score_estrutural"].map(format_score)
    map_df["score_censo_fmt"] = map_df["score_setor_2022_calibrado"].map(format_score)
    map_df["coverage_fmt"] = map_df["coverage_pct_setor_2022"].map(format_pct)
    map_df["qualidade_join_label"] = (
        map_df["qualidade_join_uf"]
        .astype(object)
        .where(map_df["qualidade_join_uf"].notna(), "Sem camada")
        .astype(str)
    )
    map_df["flag_viavel_label"] = map_df["flag_viavel"].map({True: "Sim", False: "Nao"})
    map_df["flag_prioridade_label"] = map_df["flag_prioridade"].map({True: "Sim", False: "Nao"})
    center, zoom = resolve_map_view(
        map_df,
        selected_ufs=selected_ufs,
        selected_cities=selected_cities,
    )

    hex_layer = pdk.Layer(
        "H3HexagonLayer",
        data=map_df,
        get_hexagon="hex_id",
        get_fill_color="fill_color",
        get_line_color="line_color",
        filled=True,
        stroked=True,
        extruded=False,
        pickable=True,
        auto_highlight=True,
        highlight_color=[255, 255, 255, 42],
        opacity=0.78,
        line_width_min_pixels=1,
    )

    deck = pdk.Deck(
        map_style=pdk.map_styles.CARTO_DARK,
        initial_view_state=pdk.ViewState(
            latitude=center["lat"],
            longitude=center["lon"],
            zoom=zoom,
            min_zoom=3,
            max_zoom=14,
            pitch=0,
            bearing=0,
        ),
        layers=[hex_layer],
        tooltip={
            "html": (
                "<b>{nome_municipio}</b> / {uf}<br/>"
                "Fonte geografica: <b>{fonte_geografica_label}</b><br/>"
                "Faixa M1: {faixa_label}<br/>"
                "Score M1: {score_priorizacao_fmt}<br/>"
                "Score estrutural: {hex_score_estrutural_fmt}<br/>"
                "Score censitario: {score_censo_fmt}<br/>"
                "Qualidade join: {qualidade_join_label}<br/>"
                "Coverage censitario: {coverage_fmt}<br/>"
                "Viavel: {flag_viavel_label}<br/>"
                "Prioridade: {flag_prioridade_label}"
            ),
            "style": {
                "backgroundColor": "rgba(10, 15, 31, 0.94)",
                "color": COLORS["text"],
                "border": f"1px solid {COLORS['border']}",
                "borderRadius": "10px",
                "fontFamily": "Bahnschrift, Aptos, Segoe UI, sans-serif",
            },
        },
    )
    return deck, len(map_df)


def _derivar_faixa_hibrida(df: pd.DataFrame) -> pd.Series:
    col = "score_expansao_hibrido"
    if col not in df.columns or df[col].isna().all():
        col = "score_setor_2022_calibrado"
    if col not in df.columns or df[col].isna().all():
        return pd.Series("descartado", index=df.index)
    pct = df[col].rank(method="max", pct=True, na_option="keep") * 100
    return pd.cut(
        pct,
        bins=[-float("inf"), 35, 50, 65, 80, float("inf")],
        labels=["descartado", "baixa", "media", "alta", "prioridade_maxima"],
        right=False,
    ).astype(object).fillna("descartado")


def build_hybrid_map_figure(
    hdf: pd.DataFrame,
    *,
    selected_ufs: list[str],
    selected_cities: list[str],
    selected_faixas: list[str] | None = None,
):
    if "score_setor_2022_calibrado" not in hdf.columns:
        return None, 0

    map_columns = [
        "hex_id",
        "lat",
        "lng",
        "uf",
        "nome_municipio",
        "score_setor_2022_calibrado",
        "score_priorizacao",
        "score_expansao_hibrido",
        "densidade_pop_setor_hab_km2",
        "qualidade_join_uf",
        "flag_join_uf_restrito",
        "flag_baixa_pop_setor",
        "flag_outlier_espacial",
        "causa_outlier_espacial",
        "coverage_pct_setor_2022",
        "motivo_nao_elegivel_censo",
        "elegibilidade_hibrida",
        "rank_hex_intraurbano",
        "top_hex_intraurbano",
        "top_oportunidade_municipio",
    ]
    map_df = hdf.loc[
        hdf["score_setor_2022_calibrado"].notna()
        & hdf["lat"].notna()
        & hdf["lng"].notna(),
        [column for column in map_columns if column in hdf.columns],
    ].copy()
    if map_df.empty:
        return None, 0

    if selected_ufs:
        map_df = map_df.loc[map_df["uf"].isin(selected_ufs)].copy()
    if selected_cities:
        city_col = "nome_municipio" if "nome_municipio" in map_df.columns else "uf"
        map_df = map_df.loc[map_df[city_col].isin(selected_cities)].copy()
    if map_df.empty:
        return None, 0

    if selected_faixas:
        map_df["_faixa_hibrida"] = _derivar_faixa_hibrida(map_df)
        map_df = map_df.loc[map_df["_faixa_hibrida"].isin(selected_faixas)].copy()
        map_df = map_df.drop(columns=["_faixa_hibrida"])
    if map_df.empty:
        return None, 0

    sort_cols = [
        column
        for column in ["top_hex_intraurbano", "top_oportunidade_municipio", "score_expansao_hibrido", "score_setor_2022_calibrado"]
        if column in map_df.columns
    ]
    ascending = [False for _ in sort_cols]
    if sort_cols:
        map_df = map_df.sort_values(sort_cols, ascending=ascending, kind="stable")
    map_df = map_df.head(MAP_POINT_LIMIT)

    map_df["fill_color"] = map_df["score_setor_2022_calibrado"].map(_censo_score_to_color)
    map_df["line_color"] = map_df.apply(
        lambda row: (
            [255, 90, 107, 220]
            if bool(row.get("flag_join_uf_restrito", False)) or str(row.get("qualidade_join_uf", "")) == "C"
            else ([245, 158, 11, 220] if bool(row.get("flag_outlier_espacial", False)) else hex_to_rgba(COLORS["map_line"], 100))
        ),
        axis=1,
    )
    map_df["score_censo_fmt"] = map_df["score_setor_2022_calibrado"].map(format_score)
    map_df["score_m1_fmt"] = map_df["score_priorizacao"].map(format_score)
    map_df["score_hibrido_fmt"] = map_df["score_expansao_hibrido"].map(format_score)
    map_df["densidade_fmt"] = map_df["densidade_pop_setor_hab_km2"].map(format_density)
    map_df["coverage_fmt"] = map_df["coverage_pct_setor_2022"].map(format_pct)
    map_df["outlier_label"] = map_df["flag_outlier_espacial"].map({True: "Sim (revisar)", False: "Nao"})
    map_df["join_restrito_label"] = map_df["flag_join_uf_restrito"].map({True: "Sim", False: "Nao"})
    map_df["baixa_pop_label"] = map_df["flag_baixa_pop_setor"].map({True: "Sim (<5.000 hab/km2)", False: "Nao"})
    map_df["causa_outlier_label"] = map_df["causa_outlier_espacial"].astype(object).fillna("-").astype(str)
    map_df["rank_hex_fmt"] = map_df["rank_hex_intraurbano"].map(
        lambda v: str(int(v)) if not pd.isna(v) else "-"
    )
    map_df["top_hex_label"] = map_df["top_hex_intraurbano"].map({True: "Sim", False: "Nao"})
    map_df["motivo_label"] = map_df["motivo_nao_elegivel_censo"].astype(object).fillna("-").astype(str)

    center, zoom = resolve_map_view(map_df, selected_ufs=selected_ufs, selected_cities=selected_cities)

    hex_layer = pdk.Layer(
        "H3HexagonLayer",
        data=map_df,
        get_hexagon="hex_id",
        get_fill_color="fill_color",
        get_line_color="line_color",
        filled=True,
        stroked=True,
        extruded=False,
        pickable=True,
        auto_highlight=True,
        highlight_color=[255, 255, 255, 60],
        opacity=0.85,
        line_width_min_pixels=1,
    )

    deck = pdk.Deck(
        map_style=pdk.map_styles.CARTO_DARK,
        initial_view_state=pdk.ViewState(
            latitude=center["lat"],
            longitude=center["lon"],
            zoom=zoom,
            min_zoom=3,
            max_zoom=15,
            pitch=0,
            bearing=0,
        ),
        layers=[hex_layer],
        tooltip={
            "html": (
                "<b>{nome_municipio}</b> / {uf}<br/>"
                "Score Censitario 2022: <b>{score_censo_fmt}</b><br/>"
                "Score M1: {score_m1_fmt}<br/>"
                "Score Hibrido: {score_hibrido_fmt}<br/>"
                "Densidade setorial: {densidade_fmt} hab/km2<br/>"
                "Rank Intraurbano: {rank_hex_fmt}<br/>"
                "Top intraurbano: {top_hex_label}<br/>"
                "Elegibilidade: {elegibilidade_hibrida}<br/>"
                "Coverage: {coverage_fmt}<br/>"
                "Qualidade join: {qualidade_join_uf}<br/>"
                "Join restrito: {join_restrito_label}<br/>"
                "Abaixo do piso densidade: {baixa_pop_label}<br/>"
                "Outlier espacial: {outlier_label}<br/>"
                "Causa do outlier: {causa_outlier_label}<br/>"
                "Motivo editorial: {motivo_label}"
            ),
            "style": {
                "backgroundColor": "rgba(10, 15, 31, 0.94)",
                "color": COLORS["text"],
                "border": f"1px solid {COLORS['border']}",
                "borderRadius": "10px",
                "fontFamily": "Bahnschrift, Aptos, Segoe UI, sans-serif",
            },
        },
    )
    return deck, len(map_df)


def build_top_city_figure(city_summary: pd.DataFrame):
    ranking = city_summary.sort_values(
        ["score_medio", "oportunidades_viaveis", "melhor_rank_brasil", "cidade"],
        ascending=[False, False, True, True],
        kind="stable",
    ).head(10)
    if ranking.empty:
        return None

    ranking = ranking.sort_values("score_medio", ascending=True, kind="stable")
    ranking["cidade_label"] = (
        ranking["cidade"].astype(str) + " / " + ranking["uf"].astype(str)
    )
    fig = px.bar(
        ranking,
        x="score_medio",
        y="cidade_label",
        orientation="h",
        color="score_medio",
        color_continuous_scale=[COLORS["brand"], COLORS["brand_alt"]],
        labels={"score_medio": "Score medio", "cidade_label": "Cidade"},
        text="score_medio",
    )
    fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
    apply_exec_layout(fig, title="Top cidades por score medio", height=430)
    fig.update_layout(coloraxis_showscale=False)
    return fig


def build_top_uf_figure(uf_summary: pd.DataFrame):
    ranking = uf_summary.sort_values(
        ["oportunidades_viaveis", "score_medio", "uf"],
        ascending=[False, False, True],
        kind="stable",
    ).head(10)
    if ranking.empty:
        return None

    ranking = ranking.sort_values("oportunidades_viaveis", ascending=True, kind="stable")
    fig = px.bar(
        ranking,
        x="oportunidades_viaveis",
        y="uf",
        orientation="h",
        color_discrete_sequence=[COLORS["good"]],
        labels={"oportunidades_viaveis": "Oportunidades viaveis", "uf": "UF"},
        text="oportunidades_viaveis",
    )
    fig.update_traces(texttemplate="%{text:.0f}", textposition="outside")
    apply_exec_layout(fig, title="Top UFs por oportunidades viaveis", height=430)
    fig.update_layout(showlegend=False)
    return fig


def build_scatter_figure(city_summary: pd.DataFrame):
    scatter_df = city_summary.dropna(
        subset=["renda_per_capita", "populacao_proxy", "score_medio"]
    ).copy()
    if scatter_df.empty:
        return None

    scatter_df = scatter_df.sort_values(
        ["score_medio", "total_hexagonos"],
        ascending=[False, False],
        kind="stable",
    ).head(1500)
    scatter_df["cidade_label"] = (
        scatter_df["cidade"].astype(str) + " / " + scatter_df["uf"].astype(str)
    )
    fig = px.scatter(
        scatter_df,
        x="renda_per_capita",
        y="populacao_proxy",
        size="total_hexagonos",
        color="score_medio",
        hover_name="cidade_label",
        hover_data={
            "oportunidades_viaveis": True,
            "hexagonos_priorizados": True,
            "renda_per_capita": ":.2f",
            "populacao_proxy": ":.0f",
            "score_medio": ":.2f",
        },
        labels={
            "renda_per_capita": "Renda per capita",
            "populacao_proxy": "Populacao proxy",
            "score_medio": "Score medio",
        },
        color_continuous_scale="Blues",
    )
    apply_exec_layout(fig, title="Renda per capita x populacao proxy", height=520)
    return fig


def build_score_distribution_figure(df: pd.DataFrame):
    hist_df = df.dropna(subset=["score_priorizacao"]).copy()
    if hist_df.empty:
        return None

    fig = px.histogram(
        hist_df,
        x="score_priorizacao",
        nbins=20,
        color_discrete_sequence=[COLORS["brand_alt"]],
        labels={"score_priorizacao": "Score priorizacao", "count": "Hexagonos"},
    )
    apply_exec_layout(fig, title="Distribuicao de score_priorizacao", height=340)
    return fig


def build_faixa_comparison_figure(df: pd.DataFrame):
    faixa_df = (
        df.groupby("faixa_oportunidade", observed=False, as_index=False)
        .agg(score_medio=("score_priorizacao", "mean"))
        .copy()
    )
    faixa_df["faixa_oportunidade"] = pd.Categorical(
        faixa_df["faixa_oportunidade"],
        categories=FAIXA_ORDEM,
        ordered=True,
    )
    faixa_df = faixa_df.sort_values("faixa_oportunidade").dropna(subset=["score_medio"])
    if faixa_df.empty:
        return None

    faixa_df["faixa_label"] = faixa_df["faixa_oportunidade"].astype(str)
    fig = px.bar(
        faixa_df,
        x="faixa_label",
        y="score_medio",
        color="faixa_label",
        color_discrete_map=FAIXA_COLORS,
        labels={"faixa_label": "Faixa", "score_medio": "Score medio"},
        text="score_medio",
    )
    fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
    apply_exec_layout(fig, title="Score medio por faixa_oportunidade", height=340)
    fig.update_layout(showlegend=False)
    return fig


def build_uf_metric_figure(
    uf_summary: pd.DataFrame,
    *,
    metric: str,
    label: str,
    color: str,
):
    if uf_summary.empty:
        return None

    ranking = uf_summary.sort_values(
        [metric, "uf"],
        ascending=[False, True],
        kind="stable",
    )
    fig = px.bar(
        ranking,
        x=metric,
        y="uf",
        orientation="h",
        color_discrete_sequence=[color],
        labels={metric: label, "uf": "UF"},
        text=metric,
    )
    if metric == "score_medio":
        fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
    else:
        fig.update_traces(texttemplate="%{text:.0f}", textposition="outside")
    apply_exec_layout(fig, title=label + " por UF", height=620)
    fig.update_layout(showlegend=False)
    return fig


def build_top_bottom_uf_figure(uf_summary: pd.DataFrame):
    if uf_summary.empty:
        return None

    ordered = uf_summary.sort_values(
        ["score_medio", "oportunidades_viaveis", "uf"],
        ascending=[False, False, True],
        kind="stable",
    )
    highlight = pd.concat([ordered.head(5), ordered.tail(5)]).drop_duplicates("uf").copy()
    if highlight.empty:
        return None

    top_ufs = set(ordered.head(5)["uf"])
    highlight["grupo"] = highlight["uf"].map(
        lambda value: "Top 5 score" if value in top_ufs else "Bottom 5 score"
    )
    highlight = highlight.sort_values(
        ["grupo", "score_medio", "uf"],
        ascending=[True, True, True],
        kind="stable",
    )
    fig = px.bar(
        highlight,
        x="score_medio",
        y="uf",
        orientation="h",
        color="grupo",
        color_discrete_map={
            "Top 5 score": COLORS["good"],
            "Bottom 5 score": COLORS["bad"],
        },
        labels={"score_medio": "Score medio", "uf": "UF"},
        text="score_medio",
    )
    fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
    apply_exec_layout(fig, title="Top e bottom UFs por score medio", height=620)
    return fig


def build_indicator_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            {
                "Indicador": [
                    "Score medio",
                    "Renda per capita media",
                    "Populacao proxy media",
                    "% viavel",
                    "% priorizado",
                ],
                "Valor": ["-", "-", "-", "-", "-"],
            }
        )

    return pd.DataFrame(
        {
            "Indicador": [
                "Score medio",
                "Renda per capita media",
                "Populacao proxy media",
                "% viavel",
                "% priorizado",
            ],
            "Valor": [
                format_score(df["score_priorizacao"].mean()),
                format_score(df["renda_per_capita"].mean()),
                format_int(df["populacao_proxy"].mean()),
                format_pct(df["flag_viavel"].mean() * 100),
                format_pct(df["flag_prioridade"].mean() * 100),
            ],
        }
    )


def build_ranking_table(df: pd.DataFrame) -> pd.DataFrame:
    ranking_source = df.loc[df["rank_brasil"].notna()].nsmallest(TABLE_ROW_LIMIT, columns="rank_brasil")
    table_df = (
        ranking_source.sort_values(
            ["rank_brasil", "score_priorizacao"],
            ascending=[True, False],
            kind="stable",
        )
        .head(TABLE_ROW_LIMIT)
        .loc[
            :,
            [
                "UF",
                "nome_municipio",
                "score_priorizacao",
                "rank_brasil",
                "rank_uf",
                "rank_cidade",
                "faixa_oportunidade",
                "flag_prioridade",
                "flag_viavel",
            ],
        ]
        .copy()
    )
    table_df = table_df.rename(
        columns={
            "score_priorizacao": "Score Priorizacao",
            "rank_brasil": "Rank Brasil",
            "rank_uf": "Rank UF",
            "rank_cidade": "Rank Cidade",
            "faixa_oportunidade": "Faixa",
            "flag_prioridade": "Prioridade",
            "flag_viavel": "Viavel",
            "nome_municipio": "Cidade",
        }
    )
    table_df["Prioridade"] = table_df["Prioridade"].map({True: "Sim", False: "Nao"})
    table_df["Viavel"] = table_df["Viavel"].map({True: "Sim", False: "Nao"})
    return table_df


def build_hybrid_top_hexes_table(hdf: pd.DataFrame) -> pd.DataFrame:
    if "score_setor_2022_calibrado" not in hdf.columns:
        return pd.DataFrame()

    top = hdf[hdf["score_setor_2022_calibrado"].notna()].copy()
    if top.empty:
        return pd.DataFrame()

    cols_wanted = [
        "uf",
        "nome_municipio",
        "hex_id",
        "score_setor_2022_calibrado",
        "score_priorizacao",
        "score_expansao_hibrido",
        "rank_hex_intraurbano",
        "rank_hibrido_brasil",
        "top_hex_intraurbano",
        "top_oportunidade_municipio",
        "qualidade_join_uf",
        "coverage_pct_setor_2022",
        "flag_join_uf_restrito",
        "flag_baixa_pop_setor",
        "flag_outlier_espacial",
        "causa_outlier_espacial",
        "motivo_nao_elegivel_censo",
    ]
    cols_available = [c for c in cols_wanted if c in top.columns]
    sort_candidates = [
        c
        for c in [
            "top_hex_intraurbano",
            "top_oportunidade_municipio",
            "rank_hibrido_brasil",
            "rank_hex_intraurbano",
            "score_expansao_hibrido",
        ]
        if c in top.columns
    ]
    ascending = []
    for column in sort_candidates:
        ascending.append(column in {"rank_hibrido_brasil", "rank_hex_intraurbano"})
    top = (
        top[cols_available]
        .sort_values(
            sort_candidates,
            ascending=ascending,
            kind="stable",
        )
        .head(TABLE_ROW_LIMIT)
    )
    rename_map = {
        "uf": "UF",
        "nome_municipio": "Municipio",
        "hex_id": "Hex ID",
        "score_setor_2022_calibrado": "Score Censo 2022",
        "score_priorizacao": "Score M1",
        "score_expansao_hibrido": "Score Hibrido",
        "rank_hex_intraurbano": "Rank Intraurbano",
        "rank_hibrido_brasil": "Rank Hibrido Brasil",
        "top_hex_intraurbano": "Top Hex",
        "top_oportunidade_municipio": "Carteira Municipio",
        "qualidade_join_uf": "Qualidade Join",
        "coverage_pct_setor_2022": "Coverage %",
        "flag_join_uf_restrito": "Join Restrito",
        "flag_baixa_pop_setor": "Dens. < 5k",
        "flag_outlier_espacial": "Outlier Espacial",
        "causa_outlier_espacial": "Causa Outlier",
        "motivo_nao_elegivel_censo": "Status Editorial",
    }
    top = top.rename(columns={k: v for k, v in rename_map.items() if k in top.columns})
    for col in ["Top Hex", "Carteira Municipio", "Join Restrito", "Dens. < 5k", "Outlier Espacial"]:
        if col in top.columns:
            top[col] = top[col].map({True: "Sim", False: "Nao"})
    return top


def build_hybrid_municipios_table(hdf: pd.DataFrame) -> pd.DataFrame:
    if "top_municipio" not in hdf.columns:
        return pd.DataFrame()

    mun = hdf[hdf["top_municipio"] == True].copy()
    if mun.empty:
        return pd.DataFrame()

    best_hex = (
        mun[mun["score_setor_2022_calibrado"].notna()]
        .sort_values(
            [c for c in ["rank_hex_intraurbano", "score_expansao_hibrido", "score_setor_2022_calibrado"] if c in mun.columns],
            ascending=[True, False, False][: len([c for c in ["rank_hex_intraurbano", "score_expansao_hibrido", "score_setor_2022_calibrado"] if c in mun.columns])],
            kind="stable",
        )
        .drop_duplicates(subset=["uf", "nome_municipio"])
    )

    mun_summary = (
        mun.sort_values(
            [c for c in ["rank_municipio_uf", "score_priorizacao"] if c in mun.columns],
            ascending=[True, False][: len([c for c in ["rank_municipio_uf", "score_priorizacao"] if c in mun.columns])],
            kind="stable",
        )
        .drop_duplicates(subset=["uf", "nome_municipio"])
        .copy()
    )

    best_cols = [
        "uf",
        "nome_municipio",
        "hex_id",
        "score_setor_2022_calibrado",
        "score_expansao_hibrido",
        "rank_hex_intraurbano",
        "top_oportunidade_municipio",
        "coverage_pct_setor_2022",
        "qualidade_join_uf",
        "flag_baixa_pop_setor",
        "flag_outlier_espacial",
    ]
    best_subset = best_hex[[column for column in best_cols if column in best_hex.columns]].rename(
        columns={
            "hex_id": "melhor_hex_id",
            "score_setor_2022_calibrado": "melhor_score_setor_2022_calibrado",
            "score_expansao_hibrido": "melhor_score_expansao_hibrido",
            "rank_hex_intraurbano": "melhor_rank_hex_intraurbano",
            "top_oportunidade_municipio": "melhor_top_oportunidade_municipio",
            "coverage_pct_setor_2022": "melhor_coverage_pct_setor_2022",
            "qualidade_join_uf": "melhor_qualidade_join_uf",
            "flag_baixa_pop_setor": "melhor_flag_baixa_pop_setor",
            "flag_outlier_espacial": "melhor_flag_outlier_espacial",
        }
    )
    mun = mun_summary.merge(best_subset, on=["uf", "nome_municipio"], how="left")
    mun = mun.head(TABLE_ROW_LIMIT)

    rename_map = {
        "uf": "UF",
        "nome_municipio": "Municipio",
        "score_priorizacao": "Score M1",
        "rank_municipio_uf": "Rank Mun UF",
        "rank_municipio_brasil": "Rank Mun Brasil",
        "flag_censo_disponivel": "Censo Disponivel",
        "top_municipio_hibrido": "Municipio Elegivel Hibrido",
        "top_municipio": "Top M1",
        "melhor_hex_id": "Melhor Hex",
        "melhor_score_setor_2022_calibrado": "Melhor Score Censo",
        "melhor_score_expansao_hibrido": "Melhor Score Hibrido",
        "melhor_rank_hex_intraurbano": "Rank Melhor Hex",
        "melhor_top_oportunidade_municipio": "Carteira Municipio",
        "melhor_coverage_pct_setor_2022": "Coverage %",
        "melhor_qualidade_join_uf": "Qualidade Join",
        "melhor_flag_baixa_pop_setor": "Melhor Hex Dens. < 5k",
        "melhor_flag_outlier_espacial": "Melhor Hex Outlier",
    }
    mun = mun[
        [column for column in rename_map if column in mun.columns]
    ].rename(columns={k: v for k, v in rename_map.items() if k in mun.columns})
    for col in [
        "Censo Disponivel",
        "Municipio Elegivel Hibrido",
        "Top M1",
        "Carteira Municipio",
        "Melhor Hex Dens. < 5k",
        "Melhor Hex Outlier",
    ]:
        if col in mun.columns:
            mun[col] = mun[col].map({True: "Sim", False: "Nao"})
    return mun


def build_hybrid_kpis(hdf: pd.DataFrame) -> dict[str, str]:
    if hdf.empty:
        return {
            "municipios_elegiveis": "0",
            "hexes_elegiveis": "0",
            "municipios_cobertos": "0",
            "registros_monitoramento": "0",
            "comparativo_m1_hibrido": "0 -> 0",
        }

    municipio_keys = [column for column in ["uf", "nome_municipio"] if column in hdf.columns]
    municipios_elegiveis = (
        hdf[hdf["top_municipio_hibrido"] == True][municipio_keys].drop_duplicates().shape[0]
        if "top_municipio_hibrido" in hdf.columns and municipio_keys
        else 0
    )
    municipios_cobertos = (
        hdf[hdf["flag_censo_disponivel"] == True][municipio_keys].drop_duplicates().shape[0]
        if "flag_censo_disponivel" in hdf.columns and municipio_keys
        else 0
    )
    hexes_elegiveis = int(hdf["flag_hex_hibrido_elegivel"].sum()) if "flag_hex_hibrido_elegivel" in hdf.columns else 0
    monitoramento = (
        int(hdf["flag_monitoramento_prioritario"].sum())
        if "flag_monitoramento_prioritario" in hdf.columns
        else 0
    )
    oportunidades_m1 = int(hdf["flag_prioridade"].sum()) if "flag_prioridade" in hdf.columns else 0

    return {
        "municipios_elegiveis": format_int(municipios_elegiveis),
        "hexes_elegiveis": format_int(hexes_elegiveis),
        "municipios_cobertos": format_int(municipios_cobertos),
        "registros_monitoramento": format_int(monitoramento),
        "comparativo_m1_hibrido": f"{format_int(oportunidades_m1)} -> {format_int(hexes_elegiveis)}",
    }


def build_hybrid_score_comparison_figure(hdf: pd.DataFrame):
    censo_ufs_mask = hdf["uf"].isin(CENSO_UFS) if "uf" in hdf.columns else pd.Series(False, index=hdf.index)
    plot_df = hdf.loc[
        censo_ufs_mask & hdf["score_setor_2022_calibrado"].notna() & hdf["score_priorizacao"].notna()
    ].copy()

    if plot_df.empty or len(plot_df) < 10:
        return None

    plot_df = plot_df.sample(min(5000, len(plot_df)), random_state=42)
    plot_df["uf_label"] = plot_df["uf"].astype(str)

    fig = px.scatter(
        plot_df,
        x="score_priorizacao",
        y="score_setor_2022_calibrado",
        color="uf_label",
        labels={
            "score_priorizacao": "Score M1 (municipal)",
            "score_setor_2022_calibrado": "Score Censitario 2022 (intraurbano)",
            "uf_label": "UF",
        },
        opacity=0.55,
        title="M1 vs Censitario 2022 — cada ponto e um hex",
    )
    apply_exec_layout(fig, title="Comparativo M1 vs Censitario 2022 por hex", height=420)
    return fig


def build_hybrid_portfolio_table(hdf: pd.DataFrame) -> pd.DataFrame:
    if hdf.empty or "flag_hex_hibrido_elegivel" not in hdf.columns:
        return pd.DataFrame()

    portfolio = hdf[hdf["flag_hex_hibrido_elegivel"] == True].copy()
    if portfolio.empty:
        return pd.DataFrame()

    priority_mask = pd.Series(False, index=portfolio.index)
    for column in [
        "top_oportunidade_brasil",
        "top_oportunidade_uf",
        "top_oportunidade_municipio",
        "top_hex_intraurbano",
    ]:
        if column in portfolio.columns:
            priority_mask |= portfolio[column].fillna(False)
    portfolio = portfolio[priority_mask].copy()
    if portfolio.empty:
        return pd.DataFrame()

    sort_cols = [
        column
        for column in ["rank_hibrido_brasil", "rank_hibrido_uf", "rank_hex_intraurbano", "score_expansao_hibrido"]
        if column in portfolio.columns
    ]
    ascending = [True, True, True, False][: len(sort_cols)]
    portfolio = portfolio.sort_values(sort_cols, ascending=ascending, kind="stable").head(TABLE_ROW_LIMIT)

    rename_map = {
        "uf": "UF",
        "nome_municipio": "Municipio",
        "hex_id": "Hex ID",
        "rank_hibrido_brasil": "Rank Hibrido Brasil",
        "rank_hibrido_uf": "Rank Hibrido UF",
        "rank_hex_intraurbano": "Rank Intraurbano",
        "score_priorizacao": "Score M1",
        "score_setor_2022_calibrado": "Score Censo 2022",
        "score_expansao_hibrido": "Score Hibrido",
        "coverage_pct_setor_2022": "Coverage %",
        "qualidade_join_uf": "Qualidade Join",
        "flag_join_uf_restrito": "Join Restrito",
        "flag_baixa_pop_setor": "Dens. < 5k",
        "flag_outlier_espacial": "Outlier",
        "flag_monitoramento_prioritario": "Monitorar",
    }
    portfolio = portfolio[
        [column for column in rename_map if column in portfolio.columns]
    ].rename(columns={k: v for k, v in rename_map.items() if k in portfolio.columns})
    for column in ["Join Restrito", "Dens. < 5k", "Outlier", "Monitorar"]:
        if column in portfolio.columns:
            portfolio[column] = portfolio[column].map({True: "Sim", False: "Nao"})
    return portfolio


def build_hybrid_alerts(hdf: pd.DataFrame) -> list[str]:
    if hdf.empty:
        return []

    alerts: list[str] = []
    join_restrito = int(hdf["flag_join_uf_restrito"].sum()) if "flag_join_uf_restrito" in hdf.columns else 0
    outliers = int(hdf["flag_outlier_espacial"].sum()) if "flag_outlier_espacial" in hdf.columns else 0
    coverage_baixa = (
        int((pd.to_numeric(hdf["coverage_pct_setor_2022"], errors="coerce") < 85).fillna(False).sum())
        if "coverage_pct_setor_2022" in hdf.columns
        else 0
    )

    if join_restrito > 0:
        alerts.append(
            f"{format_int(join_restrito)} hexes no recorte estao com join restrito. Trate o Censitario como leitura exploratoria e mantenha o M1 como evidencia principal."
        )
    if coverage_baixa > 0:
        alerts.append(
            f"{format_int(coverage_baixa)} hexes estao abaixo do gate de 85% de coverage censitario. Evite usar esse sinal como evidencia forte."
        )
    if outliers > 0:
        alerts.append(
            f"{format_int(outliers)} hexes carregam `flag_outlier_espacial=True`. Revise o contexto local antes de priorizar um bairro."
        )
    return alerts


def _category_options(series: pd.Series, *, observed: bool = False) -> list[str]:
    if hasattr(series, "cat"):
        categories = (
            series.cat.remove_unused_categories().cat.categories
            if observed
            else series.cat.categories
        )
        return [str(value) for value in categories.tolist()]
    return sorted(series.dropna().astype(str).unique().tolist())


def style_ranking_table(table_df: pd.DataFrame):
    if table_df.empty:
        return table_df

    score_min = float(table_df["Score Priorizacao"].min())
    score_max = float(table_df["Score Priorizacao"].max())

    def faixa_style(value: str) -> str:
        bg = FAIXA_COLORS.get(str(value), "#FFFFFF")
        text_color = "#FFFFFF" if value != "descartado" else COLORS["text"]
        return f"background-color: {bg}; color: {text_color}; font-weight: 600;"

    def flag_style(value: str) -> str:
        if value == "Sim":
            return f"color: {COLORS['good']}; font-weight: 700;"
        return f"color: {COLORS['bad']};"

    def score_style(value: float) -> str:
        if pd.isna(value):
            return ""
        if score_max <= score_min:
            ratio = 1.0
        else:
            ratio = (float(value) - score_min) / (score_max - score_min)
        if ratio >= 0.85:
            bg = "#0F6CBD"
            text = "#FFFFFF"
        elif ratio >= 0.60:
            bg = "#D9EAF9"
            text = COLORS["text"]
        elif ratio >= 0.35:
            bg = "#EEF4FA"
            text = COLORS["text"]
        else:
            bg = "#F8FBFD"
            text = COLORS["muted"]
        return f"background-color: {bg}; color: {text}; font-weight: 600;"

    return (
        table_df.style.format(
            {
                "Score Priorizacao": "{:.2f}",
                "Rank Brasil": "{:.0f}",
                "Rank UF": "{:.0f}",
                "Rank Cidade": "{:.0f}",
            }
        )
        .map(score_style, subset=["Score Priorizacao"])
        .map(faixa_style, subset=["Faixa"])
        .map(flag_style, subset=["Prioridade", "Viavel"])
    )


def render_sidebar_filters(
    df: pd.DataFrame,
) -> tuple[list[str], list[str], list[str], list[str], list[str], list[str], bool, bool]:
    st.sidebar.markdown("### Filtros globais")
    st.sidebar.caption("Refine o recorte executivo do M1 e da camada hibrida sem alterar o score oficial.")
    all_ufs = _category_options(df["uf"])
    uf_selecionada = st.sidebar.selectbox(
        "UF",
        options=all_ufs,
        index=None,
        placeholder="Selecione uma UF",
    )
    selected_ufs = [uf_selecionada] if uf_selecionada else []

    city_source = df.loc[df["uf"] == uf_selecionada, "nome_municipio"] if uf_selecionada else df["nome_municipio"]
    all_cities = _category_options(city_source, observed=True)
    selected_cities = st.sidebar.multiselect(
        "Municipio",
        options=all_cities,
        placeholder="Selecione municipios",
    )

    faixas_presentes = [
        faixa for faixa in FAIXA_ORDEM if faixa in set(_category_options(df["faixa_oportunidade"]))
    ]
    selected_faixas = st.sidebar.multiselect(
        "Faixa de oportunidade",
        options=faixas_presentes,
        placeholder="Selecione faixas",
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Camada Hibrida")
    st.sidebar.caption("Esses filtros refinam M1 + Censitario + Hibrido no recorte visivel.")
    selected_hybrid_eligibility = st.sidebar.multiselect(
        "Elegibilidade hibrida",
        options=HYBRID_ELIGIBILITY_ORDER,
        placeholder="Elegivel, nao elegivel ou sem camada",
    )
    selected_coverage_buckets = st.sidebar.multiselect(
        "Cobertura censitaria",
        options=COVERAGE_BUCKET_ORDER,
        placeholder="Faixas de coverage da camada",
    )
    selected_join_quality = st.sidebar.multiselect(
        "Qualidade da camada",
        options=JOIN_QUALITY_ORDER,
        placeholder="Classes A, B, C ou sem camada",
    )
    only_top_municipio = st.sidebar.checkbox(
        "Apenas top_municipio",
        value=False,
    )
    only_top_hex_intraurbano = st.sidebar.checkbox(
        "Apenas top_hex_intraurbano",
        value=False,
    )

    st.sidebar.caption(
        "M1 = decisao municipal. Censitario = decisao intraurbana. Hibrido = uso combinado."
    )
    return (
        selected_ufs,
        selected_cities,
        selected_faixas,
        selected_hybrid_eligibility,
        selected_coverage_buckets,
        selected_join_quality,
        only_top_municipio,
        only_top_hex_intraurbano,
    )


def render_empty_state() -> None:
    st.warning("Nenhum dado encontrado para o recorte atual. Ajuste os filtros globais.")


def render_visao_executiva(
    df: pd.DataFrame,
    city_summary: pd.DataFrame,
    uf_summary: pd.DataFrame,
    *,
    selected_ufs: list[str],
    selected_cities: list[str],
) -> None:
    kpis = build_kpis(df, city_summary, uf_summary)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Oportunidades viaveis", kpis["total_oportunidades_viaveis"])
    col2.metric("Hexagonos priorizados", kpis["total_hexagonos_priorizados"])
    col3.metric("UF lider em oportunidades", kpis["uf_lider_oportunidades"])
    col4.metric("Cidade lider em score", kpis["cidade_lider_score"])

    answers = build_business_answers(city_summary, uf_summary)
    answer_cols = st.columns(3)
    with answer_cols[0]:
        render_answer_card("Onde expandir", answers["expandir"])
    with answer_cols[1]:
        render_answer_card("Quais cidades priorizar", answers["priorizar"])
    with answer_cols[2]:
        render_answer_card("Onde evitar expansao", answers["evitar"])

    st.markdown("#### Mapa principal")
    st.caption(
        "Mapa executivo exibe todos os hexagonos validos da UF selecionada, usando setor censitario nas UFs com `qualidade_join_uf` A/B e fallback municipal nas UFs C."
    )
    render_faixa_legend()
    render_geographic_source_legend()
    map_figure, points_used = build_map_figure(
        df,
        selected_ufs=selected_ufs,
        selected_cities=selected_cities,
    )
    if map_figure is None:
        st.info("Sem pontos geograficos validos para o mapa neste recorte.")
    else:
        st.markdown("##### Territorio priorizado no recorte atual")
        st.caption(build_map_scope_caption(points_used, selected_ufs=selected_ufs))
        st.pydeck_chart(map_figure, width="stretch", height=600)

    chart_col_1, chart_col_2 = st.columns(2)
    with chart_col_1:
        top_city_fig = build_top_city_figure(city_summary)
        if top_city_fig is not None:
            st.plotly_chart(top_city_fig, width="stretch")
    with chart_col_2:
        top_uf_fig = build_top_uf_figure(uf_summary)
        if top_uf_fig is not None:
            st.plotly_chart(top_uf_fig, width="stretch")


def render_analise_territorial(df: pd.DataFrame, city_summary: pd.DataFrame) -> None:
    scatter_col, side_col = st.columns([1.6, 1.0])
    with scatter_col:
        scatter_fig = build_scatter_figure(city_summary)
        if scatter_fig is not None:
            st.plotly_chart(scatter_fig, width="stretch")
    with side_col:
        score_fig = build_score_distribution_figure(df)
        if score_fig is not None:
            st.plotly_chart(score_fig, width="stretch")
        faixa_fig = build_faixa_comparison_figure(df)
        if faixa_fig is not None:
            st.plotly_chart(faixa_fig, width="stretch")

    st.markdown("#### Indicadores medios")
    st.dataframe(
        build_indicator_snapshot(df),
        width="stretch",
        hide_index=True,
    )


def render_ranking_priorizacao(df: pd.DataFrame) -> None:
    st.caption(
        "Tabela ordenada por `rank_brasil`. Para manter leitura executiva e performance local, exibimos no maximo 1.000 linhas por recorte."
    )
    if len(df) > TABLE_ROW_LIMIT:
        st.info(
            f"Recorte atual possui {format_int(len(df))} linhas. Exibindo as {format_int(TABLE_ROW_LIMIT)} melhores por rank."
        )
    table_df = build_ranking_table(df)
    st.dataframe(
        style_ranking_table(table_df),
        width="stretch",
        hide_index=True,
        height=640,
    )


def render_comparacao_uf(city_summary: pd.DataFrame, uf_summary: pd.DataFrame) -> None:
    answers = build_business_answers(city_summary, uf_summary)
    callout_cols = st.columns(3)
    with callout_cols[0]:
        render_answer_card("Onde expandir", answers["expandir"])
    with callout_cols[1]:
        render_answer_card("UFs a priorizar", answers["ufs_priorizar"])
    with callout_cols[2]:
        render_answer_card("Onde evitar", answers["evitar"])

    chart_col_1, chart_col_2, chart_col_3 = st.columns(3)
    with chart_col_1:
        fig_opps = build_uf_metric_figure(
            uf_summary,
            metric="oportunidades_viaveis",
            label="Oportunidades viaveis",
            color=COLORS["brand_alt"],
        )
        if fig_opps is not None:
            st.plotly_chart(fig_opps, width="stretch")
    with chart_col_2:
        fig_score = build_uf_metric_figure(
            uf_summary,
            metric="score_medio",
            label="Score medio",
            color=COLORS["good"],
        )
        if fig_score is not None:
            st.plotly_chart(fig_score, width="stretch")
    with chart_col_3:
        fig_top_bottom = build_top_bottom_uf_figure(uf_summary)
        if fig_top_bottom is not None:
            st.plotly_chart(fig_top_bottom, width="stretch")


def render_modelo_hibrido(
    hdf: pd.DataFrame,
    df_m1: pd.DataFrame,
    *,
    selected_ufs: list[str],
    selected_cities: list[str],
) -> None:
    if hdf.empty:
        st.warning("Dataset hibrido nao disponivel. Verifique `data/outputs/oportunidades_expansao_hibrido.parquet`.")
        return

    # --- Explicacao dos modelos ---
    st.markdown("#### Como interpretar os tres modelos")
    card_cols = st.columns(3)
    with card_cols[0]:
        st.markdown(
            f"""
            <div class="model-card">
                <span class="badge" style="background:rgba(25,183,255,0.18);color:#19B7FF;border:1px solid rgba(25,183,255,0.3);">M1 — OFICIAL</span>
                <h4>Score de Priorizacao Municipal</h4>
                <p><strong>score_priorizacao</strong></p>
                <p>Decide <em>quais municipios</em> entram na fila de expansao.</p>
                <p>Baseado em renda per capita e populacao do entorno via IBGE/SIDRA.</p>
                <p>Valido para todos os municipios do Brasil.</p>
                <p>Correlacao real com faturamento: rho=0.42 (p=0.007).</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with card_cols[1]:
        st.markdown(
            f"""
            <div class="model-card">
                <span class="badge" style="background:rgba(34,197,94,0.18);color:#22C55E;border:1px solid rgba(34,197,94,0.3);">CENSO 2022 — EXPERIMENTAL</span>
                <h4>Score Intraurbano Censitario</h4>
                <p><strong>score_setor_2022_calibrado</strong></p>
                <p>Decide <em>qual bairro/hex</em> priorizar dentro de um municipio aprovado.</p>
                <p>Baseado em setores censitarios do Censo 2022 (V06004/v0005).</p>
                <p>Disponivel para: DF, GO, MG, RJ, RS, SP.</p>
                <p>NAO substitui o M1. Uso editorial local.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with card_cols[2]:
        st.markdown(
            f"""
            <div class="model-card">
                <span class="badge" style="background:rgba(255,77,141,0.18);color:#FF4D8D;border:1px solid rgba(255,77,141,0.3);">HIBRIDO — OPERACIONAL</span>
                <h4>Fila Operacional Combinada</h4>
                <p><strong>score_expansao_hibrido</strong></p>
                <p>Combina M1 (decisao municipal) + Censo 2022 (desempate intraurbano).</p>
                <p>Etapa 1: municipios top 20% por UF via score_priorizacao.</p>
                <p>Etapa 2: hexes top 10% dentro do municipio via score_setor_2022_calibrado.</p>
                <p>GO para uso controlado nas UFs cobertas.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # --- KPIs ---
    kpis = build_hybrid_kpis(hdf)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Municipios top M1 (top 20%)", kpis["municipios_top_m1"])
    k2.metric("Hexes top intraurbano", kpis["hexes_top_intraurbano"])
    k3.metric("UFs com camada censitaria", kpis["ufs_censo"])
    k4.metric("Registros p/ monitoramento", kpis["registros_monitoramento"])

    st.markdown("---")

    # --- Mapa intraurbano ---
    st.markdown("#### Mapa de Oportunidades Intraurbanas")
    st.caption(
        "Hexes com `top_hex_intraurbano=True` coloridos pelo `score_setor_2022_calibrado`. "
        "Apenas UFs com camada censitaria elegivel (DF, GO, MG, RJ, RS, SP)."
    )
    render_censo_score_legend()

    hybrid_map, n_points = build_hybrid_map_figure(
        hdf,
        df_m1,
        selected_ufs=selected_ufs,
        selected_cities=selected_cities,
    )
    if hybrid_map is None:
        st.info(
            "Nenhum hex com top_hex_intraurbano=True no recorte atual. "
            "Selecione UFs com cobertura censitaria (DF, GO, MG, RJ, RS, SP) ou remova filtros."
        )
    else:
        st.caption(f"{format_int(n_points)} hexes intraurbanos priorizados no mapa.")
        st.pydeck_chart(hybrid_map, width="stretch", height=580)

    st.markdown("---")

    # --- Comparativo M1 vs Censitario ---
    st.markdown("#### Comparativo M1 vs Score Censitario 2022")
    st.caption(
        "Cada ponto e um hex nas UFs com cobertura censitaria. "
        "Hexes com M1 alto e score censitario alto sao os melhores candidatos hibridos."
    )
    cmp_fig = build_hybrid_score_comparison_figure(hdf)
    if cmp_fig is not None:
        st.plotly_chart(cmp_fig, width="stretch")
    else:
        st.info("Sem dados suficientes para o comparativo no recorte atual.")

    st.markdown("---")

    # --- Tabelas ---
    tbl_col1, tbl_col2 = st.columns([1.2, 1.0])

    with tbl_col1:
        st.markdown("##### Top hexes intraurbanos")
        st.caption(
            "Hexes com `top_hex_intraurbano=True` ordenados por rank intraurbano. "
            "Flags de qualidade incluidos para rastreabilidade."
        )
        top_hexes_tbl = build_hybrid_top_hexes_table(hdf)
        if top_hexes_tbl.empty:
            st.info("Nenhum hex intraurbano prioritario no recorte.")
        else:
            st.dataframe(top_hexes_tbl, width="stretch", hide_index=True, height=480)

    with tbl_col2:
        st.markdown("##### Municipios aprovados no M1")
        st.caption(
            "Municipios `top_municipio=True` com status da camada censitaria. "
            "Municipios sem 'Censo Elegivel' usam apenas o M1."
        )
        mun_tbl = build_hybrid_municipios_table(hdf)
        if mun_tbl.empty:
            st.info("Nenhum municipio no recorte com top_municipio=True.")
        else:
            st.dataframe(mun_tbl, width="stretch", hide_index=True, height=480)

    st.markdown("---")

    # --- Rastreabilidade ---
    st.markdown("#### Rastreabilidade e Qualidade dos Dados")
    flag_cols = st.columns(2)
    with flag_cols[0]:
        st.markdown(
            f"""
            <div class="section-card">
                <h4>Flags de qualidade da camada censitaria</h4>
                <p><strong>qualidade_join_uf</strong>: A (&le;2%), B (2-5%), C (&gt;5% — so M1).</p>
                <p><strong>flag_outlier_espacial</strong>: hex com delta alto vs vizinhos. Verificar antes de uso.</p>
                <p><strong>flag_baixa_pop_setor</strong>: hex abaixo do piso de 5.000 hab/km2. Sai da elegibilidade intraurbana.</p>
                <p><strong>flag_join_uf_restrito</strong>: join com restricao estrutural (AM, RR). Usar apenas M1.</p>
                <p><strong>coverage_pct_setor_2022</strong>: % de hexes com dado censitario. Gate &ge;85%.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with flag_cols[1]:
        st.markdown(
            f"""
            <div class="section-card">
                <h4>Quando usar cada modelo</h4>
                <p><strong>Decidir qual municipio abrir</strong>: usar rank_municipio_uf e top_municipio (M1).</p>
                <p><strong>Escolher o ponto dentro da cidade</strong>: usar rank_hex_intraurbano e score_setor_2022_calibrado (Censo).</p>
                <p><strong>Fila operacional combinada</strong>: usar score_expansao_hibrido e top_oportunidade_municipio (Hibrido).</p>
                <p><strong>UFs sem cobertura censitaria</strong>: usar apenas M1 para todas as decisoes.</p>
                <p><strong>Restricao</strong>: score_setor_2022_calibrado e EXPERIMENTAL — nao substitui score_priorizacao.</p>
            </div>
            """,
                unsafe_allow_html=True,
            )


def render_modelo_hibrido_v2(
    hdf: pd.DataFrame,
    *,
    selected_ufs: list[str],
    selected_cities: list[str],
    selected_faixas: list[str] | None = None,
) -> None:
    if hdf.empty:
        st.warning("Dataset hibrido nao disponivel. Verifique `data/outputs/oportunidades_expansao_hibrido.parquet`.")
        return

    st.markdown("#### Como interpretar os tres modelos")
    card_cols = st.columns(3)
    with card_cols[0]:
        st.markdown(
            f"""
            <div class="model-card">
                <span class="badge" style="background:rgba(25,183,255,0.18);color:#19B7FF;border:1px solid rgba(25,183,255,0.3);">M1 - OFICIAL</span>
                <h4>Score de Priorizacao Municipal</h4>
                <p><strong>score_priorizacao</strong></p>
                <p>M1 = decisao municipal.</p>
                <p>Decide quais municipios entram na fila de expansao.</p>
                <p>Continua sendo o score oficial e nao foi alterado.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with card_cols[1]:
        st.markdown(
            """
            <div class="model-card">
                <span class="badge" style="background:rgba(34,197,94,0.18);color:#22C55E;border:1px solid rgba(34,197,94,0.3);">CENSITARIO - LOCAL</span>
                <h4>Score Intraurbano Censitario</h4>
                <p><strong>score_setor_2022_calibrado</strong></p>
                <p>Censitario = decisao intraurbana.</p>
                <p>Ajuda a escolher bairro e hex dentro de municipios aprovados.</p>
                <p>Uso editorial local, sempre com rastreabilidade de coverage e join.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with card_cols[2]:
        st.markdown(
            """
            <div class="model-card">
                <span class="badge" style="background:rgba(255,77,141,0.18);color:#FF4D8D;border:1px solid rgba(255,77,141,0.3);">HIBRIDO - COMBINADO</span>
                <h4>Fila Operacional Combinada</h4>
                <p><strong>score_expansao_hibrido</strong></p>
                <p>Hibrido = uso combinado.</p>
                <p>Primeiro o M1 aprova o municipio; depois o Censitario refina os melhores hexes.</p>
                <p>Serve para ordenar a carteira operacional, sem substituir o M1.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")
    kpis = build_hybrid_kpis(hdf)
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Municipios elegiveis no hibrido", kpis["municipios_elegiveis"])
    k2.metric("Hexes elegiveis", kpis["hexes_elegiveis"])
    k3.metric("Municipios cobertos pelo Censitario", kpis["municipios_cobertos"])
    k4.metric("Prontos para monitoramento", kpis["registros_monitoramento"])
    k5.metric("M1 vs Hibrido", kpis["comparativo_m1_hibrido"])

    for alert in build_hybrid_alerts(hdf):
        st.warning(alert)

    st.caption(
        "M1 continua decidindo o municipio. O Censitario entra como leitura local e o Hibrido organiza a fila operacional combinada."
    )
    st.caption(
        "Dado restrito, densidade setorial abaixo do piso ou outlier espacial devem ser tratados como sinal editorial de cautela, nao como evidencia forte isolada."
    )

    subtabs = st.tabs(
        [
            "Oportunidades Hibridas",
            "Ranking Intraurbano",
            "M1 vs Censitario",
            "Municipios + Melhores Hexes",
        ]
    )

    with subtabs[0]:
        st.markdown("##### Mapa com score intraurbano")
        st.caption(
            "Mapa colorido por `score_setor_2022_calibrado`, com hover de rastreabilidade. Linhas vermelhas indicam join restrito ou qualidade C."
        )
        render_censo_score_legend()
        hybrid_map, n_points = build_hybrid_map_figure(
            hdf,
            selected_ufs=selected_ufs,
            selected_cities=selected_cities,
            selected_faixas=selected_faixas,
        )
        if hybrid_map is None:
            st.info("Nao ha score censitario disponivel no recorte atual.")
        else:
            if len(hdf) > n_points:
                st.caption(
                    f"Mapa limitado aos {format_int(n_points)} hexes mais relevantes do recorte para manter performance local."
                )
            st.pydeck_chart(hybrid_map, width="stretch", height=580)

        st.markdown("##### Carteira imediata do modelo hibrido")
        portfolio = build_hybrid_portfolio_table(hdf)
        if portfolio.empty:
            st.info("Nenhuma oportunidade hibrida prioritaria no recorte atual.")
        else:
            st.dataframe(portfolio, width="stretch", hide_index=True, height=420)

    with subtabs[1]:
        st.markdown("##### Ranking intraurbano por municipio")
        st.caption(
            "Use esta tabela para escolher os melhores hexes dentro de municipios aprovados no M1, com status editorial e flags de qualidade."
        )
        top_hexes_tbl = build_hybrid_top_hexes_table(hdf)
        if top_hexes_tbl.empty:
            st.info("Nenhum hex com score censitario disponivel no recorte.")
        else:
            st.dataframe(top_hexes_tbl, width="stretch", hide_index=True, height=620)

    with subtabs[2]:
        st.markdown("##### Comparacao M1 vs Censitario")
        st.caption(
            "Cada ponto e um hex. M1 continua uniforme no nivel municipal; o Censitario adiciona a diferenciacao intraurbana."
        )
        cmp_fig = build_hybrid_score_comparison_figure(hdf)
        if cmp_fig is not None:
            st.plotly_chart(cmp_fig, width="stretch")
        else:
            st.info("Sem dados suficientes para o comparativo no recorte atual.")

    with subtabs[3]:
        st.markdown("##### Municipios elegiveis + melhores hexes")
        st.caption(
            "Tabela para leitura executiva: municipios top do M1 ao lado do melhor hex conhecido e da qualidade da camada local."
        )
        mun_tbl = build_hybrid_municipios_table(hdf)
        if mun_tbl.empty:
            st.info("Nenhum municipio no recorte com top_municipio=True.")
        else:
            st.dataframe(mun_tbl, width="stretch", hide_index=True, height=620)

        flag_cols = st.columns(2)
        with flag_cols[0]:
            st.markdown(
                """
                <div class="section-card">
                    <h4>Flags de qualidade da camada censitaria</h4>
                    <p><strong>qualidade_join_uf</strong>: A e B sao aceitaveis; C indica uso apenas exploratorio.</p>
                    <p><strong>flag_outlier_espacial</strong>: revisar contexto local antes de tratar o score como evidencia forte.</p>
                    <p><strong>flag_join_uf_restrito</strong>: manter M1 como criterio principal.</p>
                    <p><strong>coverage_pct_setor_2022</strong>: o gate operacional minimo continua em 85%.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with flag_cols[1]:
            st.markdown(
                """
                <div class="section-card">
                    <h4>Leitura executiva recomendada</h4>
                    <p><strong>M1</strong>: decide o municipio.</p>
                    <p><strong>Censitario</strong>: decide o melhor hex dentro da cidade.</p>
                    <p><strong>Hibrido</strong>: organiza a fila operacional combinada.</p>
                    <p><strong>Regra de ouro</strong>: dado restrito nao deve ser interpretado como evidencia forte.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )


@st.cache_data(show_spinner=False)
def load_carteira() -> pd.DataFrame:
    if not CARTEIRA_PATH.exists():
        return pd.DataFrame()
    df = pd.read_parquet(CARTEIRA_PATH)
    for col in ["score_priorizacao", "score_expansao_hibrido", "score_setor_2022_calibrado", "score_priorizacao_municipio",
                "coverage_pct_setor_2022", "rank_brasil", "rank_uf", "rank_carteira_brasil", "rank_carteira_uf",
                "rank_municipio_uf", "rank_municipio_brasil", "rank_hex_intraurbano"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ["flag_outlier_espacial", "flag_baixa_pop_setor", "flag_join_uf_restrito",
                "flag_monitoramento_prioritario"]:
        if col in df.columns:
            df[col] = df[col].fillna(False).astype(bool)
    return df


def load_plano() -> pd.DataFrame:
    if not PLANO_PATH.exists():
        return pd.DataFrame()
    df = pd.read_parquet(PLANO_PATH)
    for col in ["score_expansao_hibrido", "score_setor_2022_calibrado", "score_priorizacao",
                "score_priorizacao_municipio", "coverage_pct_setor_2022", "rank_brasil", "rank_uf",
                "rank_carteira_brasil", "rank_carteira_uf", "rank_municipio_uf",
                "rank_municipio_brasil", "rank_hex_intraurbano"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ["flag_outlier_espacial", "flag_baixa_pop_setor", "flag_join_uf_restrito"]:
        if col in df.columns:
            df[col] = df[col].fillna(False).astype(bool)
    return df


def _carteira_prioridade_color(p: str) -> str:
    return {"Alta": COLORS["accent"], "Media": COLORS["brand_alt"]}.get(p, COLORS["muted"])


def _sort_carteira_by_m1(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    sort_cols = [
        column
        for column in ["rank_brasil", "rank_uf", "score_priorizacao", "rank_hex_intraurbano", "score_setor_2022_calibrado"]
        if column in df.columns
    ]
    if not sort_cols:
        return df

    ascending = [column in {"rank_brasil", "rank_uf", "rank_hex_intraurbano"} for column in sort_cols]
    return df.sort_values(sort_cols, ascending=ascending, kind="stable")


def render_carteira_expansao(
    carteira: pd.DataFrame,
    *,
    selected_ufs: list[str],
    selected_cities: list[str],
) -> None:
    if carteira.empty:
        st.warning(
            "Carteira acionavel nao disponivel. Execute "
            "`python -m jobs.pipelines.gerar_carteira_acionavel` para gerar o arquivo."
        )
        return

    total_ufs_carteira = int(carteira["uf"].nunique()) if "uf" in carteira.columns else 0
    total_municipios_carteira = (
        int(carteira["cod_municipio"].nunique())
        if "cod_municipio" in carteira.columns
        else int(carteira["nome_municipio"].nunique())
    )
    ufs_com_fallback = (
        int(
            carteira.loc[
                carteira["modo_selecao_carteira"] == "fallback_municipal_m1", "uf"
            ].nunique()
        )
        if "modo_selecao_carteira" in carteira.columns and "uf" in carteira.columns
        else 0
    )

    st.markdown("#### Carteira de Expansao — Decisao pratica de onde abrir")
    st.caption(
        f"M1 continua sendo a ancora oficial da carteira. Base atual: {len(carteira)} oportunidades, "
        f"{total_municipios_carteira} municipios e {total_ufs_carteira} UFs. "
        "Quando ha camada granular, o Censitario refina o hex; quando nao ha, a carteira usa fallback municipal/M1."
    )

    # ---------- filtros locais ----------
    ufs_disponiveis = sorted(carteira["uf"].dropna().unique().tolist())
    municipios_disponiveis = sorted(carteira["nome_municipio"].dropna().unique().tolist())

    fc1, fc2, fc3 = st.columns([2, 3, 2])
    with fc1:
        ufs_sel = st.multiselect(
            "UF",
            options=ufs_disponiveis,
            default=[u for u in selected_ufs if u in ufs_disponiveis] or ufs_disponiveis,
            key="carteira_uf",
        )
    with fc2:
        muns_opcoes = sorted(
            carteira[carteira["uf"].isin(ufs_sel)]["nome_municipio"].dropna().unique().tolist()
            if ufs_sel else municipios_disponiveis
        )
        muns_sel = st.multiselect(
            "Municipio",
            options=muns_opcoes,
            default=[m for m in selected_cities if m in muns_opcoes],
            key="carteira_mun",
        )
    with fc3:
        prioridades_opcoes = ["Alta", "Media"]
        prioridades_sel = st.multiselect(
            "Prioridade",
            options=prioridades_opcoes,
            default=prioridades_opcoes,
            key="carteira_prior",
        )

    # aplica filtros
    view = carteira.copy()
    if ufs_sel:
        view = view[view["uf"].isin(ufs_sel)]
    if muns_sel:
        view = view[view["nome_municipio"].isin(muns_sel)]
    if prioridades_sel:
        view = view[view["prioridade_abertura"].isin(prioridades_sel)]
    view = _sort_carteira_by_m1(view)

    # ---------- KPIs ----------
    st.markdown("---")
    k1, k2, k3, k4 = st.columns(4)
    n_oportunidades = len(view)
    n_municipios = view["cod_municipio"].nunique() if "cod_municipio" in view.columns else view["nome_municipio"].nunique()
    n_altas = int((view["prioridade_abertura"] == "Alta").sum())
    n_ufs = view["uf"].nunique()
    k1.metric("Oportunidades no recorte", format_int(n_oportunidades))
    k2.metric("Municipios no recorte", format_int(n_municipios))
    k3.metric("Prioridade Alta", format_int(n_altas))
    k4.metric("UFs representadas", format_int(n_ufs))

    if view.empty:
        st.info("Nenhuma oportunidade no recorte selecionado.")
        return

    # ---------- top oportunidades por UF ----------
    st.markdown("##### Top oportunidades por UF")
    st.caption("Melhor hex de cada UF no recorte atual, ordenado pelo `rank_brasil` oficial do M1.")
    top_por_uf = (
        view.groupby("uf", sort=False)
        .first()
        .reset_index()
    )
    uf_display_cols = {
        "uf": "UF",
        "nome_municipio": "Municipio",
        "prioridade_abertura": "Prioridade",
        "rank_brasil": "Rank Brasil",
        "rank_uf": "Rank UF",
        "score_priorizacao": "Score M1",
        "modo_selecao_carteira": "Modo Hex",
        "rank_hex_intraurbano": "Rank Intraurbano",
        "score_setor_2022_calibrado": "Score Censo",
        "qualidade_join_uf": "Join",
    }
    uf_disp = top_por_uf[[c for c in uf_display_cols if c in top_por_uf.columns]].rename(
        columns={k: v for k, v in uf_display_cols.items() if k in top_por_uf.columns}
    )
    for col in ["Score M1", "Score Censo"]:
        if col in uf_disp.columns:
            uf_disp[col] = uf_disp[col].map(lambda v: f"{v:.1f}" if pd.notna(v) else "-")
    for col in ["Rank Brasil", "Rank UF", "Rank Intraurbano"]:
        if col in uf_disp.columns:
            uf_disp[col] = uf_disp[col].map(lambda v: int(v) if pd.notna(v) else "-")
    st.dataframe(uf_disp, width="stretch", hide_index=True, height=min(250, 38 + 35 * len(uf_disp)))

    # ---------- tabela principal ----------
    st.markdown("##### Tabela principal — onde abrir agora?")
    st.caption(
        "Ordenada pelo `rank_brasil` oficial do M1. O Censitario e o Hibrido aparecem apenas como apoio para leitura local e desempate operacional."
    )

    display_cols_order = {
        "rank_brasil": "Rank Brasil",
        "rank_uf": "Rank UF",
        "score_priorizacao": "Score M1",
        "prioridade_abertura": "Prioridade",
        "uf": "UF",
        "nome_municipio": "Municipio",
        "hex_id": "Hex ID",
        "modo_selecao_carteira": "Modo Hex",
        "rank_hex_intraurbano": "Rank Intraurbano",
        "score_setor_2022_calibrado": "Score Censo",
        "score_expansao_hibrido": "Score Hibrido (apoio)",
        "rank_municipio_uf": "Rank Mun. UF",
        "rank_municipio_brasil": "Rank Mun. Brasil",
        "motivo_priorizacao": "Motivo",
        "qualidade_join_uf": "Join",
        "coverage_pct_setor_2022": "Coverage %",
        "flag_outlier_espacial": "Outlier",
        "flag_baixa_pop_setor": "Dens. < 5k",
        "flag_join_uf_restrito": "Join Restrito",
    }
    tbl = view[[c for c in display_cols_order if c in view.columns]].rename(
        columns={k: v for k, v in display_cols_order.items() if k in view.columns}
    )
    for col in ["Score M1", "Score Censo", "Score Hibrido (apoio)"]:
        if col in tbl.columns:
            tbl[col] = tbl[col].map(lambda v: f"{v:.1f}" if pd.notna(v) else "-")
    for col in ["Coverage %"]:
        if col in tbl.columns:
            tbl[col] = tbl[col].map(lambda v: f"{v:.1f}%" if pd.notna(v) else "-")
    for col in ["Outlier", "Dens. < 5k", "Join Restrito"]:
        if col in tbl.columns:
            tbl[col] = tbl[col].map({True: "Sim", False: "Nao", "True": "Sim", "False": "Nao"}).fillna("Nao")
    for col in ["Rank Brasil", "Rank UF", "Rank Mun. UF", "Rank Mun. Brasil", "Rank Intraurbano"]:
        if col in tbl.columns:
            tbl[col] = tbl[col].map(lambda v: int(v) if pd.notna(v) else "-")

    height_tbl = min(620, 38 + 35 * min(len(tbl), 100))
    st.dataframe(tbl.head(TABLE_ROW_LIMIT), width="stretch", hide_index=True, height=height_tbl)

    # ---------- notas editoriais ----------
    st.markdown("---")
    note_cols = st.columns(2)
    with note_cols[0]:
        st.markdown(
            """
            <div class="section-card">
                <h4>Como usar esta carteira</h4>
                <p><strong>Rank Brasil</strong>: ordem oficial do M1 para leitura executiva da carteira.</p>
                <p><strong>Prioridade Alta</strong>: municipio no top 5 da UF ou top 50 nacional.</p>
                <p><strong>Score M1</strong>: ancora oficial para decidir quais municipios entram na fila.</p>
                <p><strong>Rank Intraurbano + Score Censo</strong>: ajudam a escolher o melhor ponto dentro da cidade.</p>
                <p><strong>Motivo</strong>: resumo auditavel dos sinais que formam a prioridade.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with note_cols[1]:
        st.markdown(
            f"""
            <div class="section-card">
                <h4>Restricoes e rastreabilidade</h4>
                <p><strong>UFs cobertas</strong>: base nacional com {total_ufs_carteira} UFs e {total_municipios_carteira} municipios.</p>
                <p><strong>Fallback municipal/M1</strong>: usado quando nao ha hex granular elegivel; hoje aparece em {ufs_com_fallback} UFs na carteira.</p>
                <p><strong>Join A</strong>: confiavel; <strong>Join B</strong>: aceitavel com cautela.</p>
                <p><strong>Join C</strong>: mantido na carteira apenas via fallback municipal/M1, sem usar o score local como ancora.</p>
                <p><strong>Outlier espacial</strong>: fenomeno real, nao erro; ler contexto antes de agir.</p>
                <p><strong>score_priorizacao</strong> M1 nao foi alterado e continua sendo a base da carteira.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_plano_expansao(plano: pd.DataFrame) -> None:
    """Aba Plano de Expansao — shortlist executiva de curto prazo."""
    if plano.empty:
        st.warning(
            "Plano de curto prazo nao disponivel. Execute "
            "`python -m jobs.pipelines.gerar_plano_expansao_curto_prazo` para gerar o arquivo."
        )
        return

    total_ufs_plano = int(plano["uf"].nunique()) if "uf" in plano.columns else 0
    total_municipios_plano = (
        int(plano["cod_municipio"].nunique())
        if "cod_municipio" in plano.columns
        else int(plano["nome_municipio"].nunique())
    )
    ufs_com_fallback_plano = (
        int(
            plano.loc[
                plano["modo_selecao_carteira"] == "fallback_municipal_m1", "uf"
            ].nunique()
        )
        if "modo_selecao_carteira" in plano.columns and "uf" in plano.columns
        else 0
    )

    st.markdown("#### Plano de Expansao — Curto Prazo")
    st.caption(
        f"Shortlist executiva: Top 50 Brasil + Top 10 por UF ({len(plano)} oportunidades, "
        f"{total_municipios_plano} municipios, {total_ufs_plano} UFs). "
        "Nivel Estrategico = top 20 Brasil | Alta = top 21-50 | Tatica = top 10 UF fora do top 50."
    )

    # ---------- filtros locais ----------
    ufs_disp = sorted(plano["uf"].dropna().unique().tolist())
    muns_disp = sorted(plano["nome_municipio"].dropna().unique().tolist())
    niveis_disp = ["Estrategico", "Alta", "Tatica"]

    pf1, pf2, pf3 = st.columns([2, 3, 2])
    with pf1:
        ufs_sel = st.multiselect("UF", options=ufs_disp, default=ufs_disp, key="plano_uf")
    with pf2:
        muns_opcoes = sorted(
            plano[plano["uf"].isin(ufs_sel)]["nome_municipio"].dropna().unique().tolist()
            if ufs_sel else muns_disp
        )
        muns_sel = st.multiselect("Municipio", options=muns_opcoes, default=[], key="plano_mun")
    with pf3:
        niveis_sel = st.multiselect("Nivel", options=niveis_disp, default=niveis_disp, key="plano_nivel")

    view = plano.copy()
    if ufs_sel:
        view = view[view["uf"].isin(ufs_sel)]
    if muns_sel:
        view = view[view["nome_municipio"].isin(muns_sel)]
    if niveis_sel:
        view = view[view["nivel_prioridade_final"].isin(niveis_sel)]

    # ---------- KPIs ----------
    st.markdown("---")
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Oportunidades", format_int(len(view)))
    k2.metric("Municipios", format_int(view["cod_municipio"].nunique() if "cod_municipio" in view.columns else view["nome_municipio"].nunique()))
    k3.metric("Estrategico", format_int(int((view["nivel_prioridade_final"] == "Estrategico").sum())))
    k4.metric("Alta", format_int(int((view["nivel_prioridade_final"] == "Alta").sum())))
    k5.metric("Tatica", format_int(int((view["nivel_prioridade_final"] == "Tatica").sum())))

    if view.empty:
        st.info("Nenhuma oportunidade no recorte selecionado.")
        return

    # ---------- top por UF ----------
    st.markdown("##### Top oportunidade por UF")
    st.caption("Melhor hex de cada UF no recorte atual.")
    top_uf = (
        view.sort_values("rank_carteira_brasil")
        .groupby("uf", sort=False)
        .first()
        .reset_index()
    )
    top_uf_cols = {
        "uf": "UF",
        "nome_municipio": "Municipio",
        "nivel_prioridade_final": "Nivel",
        "rank_carteira_brasil": "Rank Brasil",
        "score_expansao_hibrido": "Score Hibrido",
        "score_priorizacao": "Score M1",
        "modo_selecao_carteira": "Modo Hex",
        "score_setor_2022_calibrado": "Score Censo",
        "qualidade_join_uf": "Join",
        "status_pipeline": "Status",
    }
    top_uf_disp = top_uf[[c for c in top_uf_cols if c in top_uf.columns]].rename(
        columns={k: v for k, v in top_uf_cols.items() if k in top_uf.columns}
    )
    for col in ["Score Hibrido", "Score M1", "Score Censo"]:
        if col in top_uf_disp.columns:
            top_uf_disp[col] = top_uf_disp[col].map(lambda v: f"{v:.1f}" if pd.notna(v) else "-")
    if "Rank Brasil" in top_uf_disp.columns:
        top_uf_disp["Rank Brasil"] = top_uf_disp["Rank Brasil"].map(lambda v: int(v) if pd.notna(v) else "-")
    st.dataframe(top_uf_disp, width="stretch", hide_index=True, height=min(280, 38 + 35 * len(top_uf_disp)))

    # ---------- tabela principal ----------
    st.markdown("##### Top 50 Brasil + Top 10 por UF — lista completa")
    st.caption("Ordenada por nivel (Estrategico > Alta > Tatica) e rank Brasil. Fonte: carteira_acionavel + plano_curto_prazo.")

    tbl_cols = {
        "rank_carteira_brasil": "Rank Brasil",
        "rank_carteira_uf": "Rank UF",
        "nivel_prioridade_final": "Nivel",
        "uf": "UF",
        "nome_municipio": "Municipio",
        "hex_id": "Hex ID",
        "modo_selecao_carteira": "Modo Hex",
        "score_expansao_hibrido": "Score Hibrido",
        "score_priorizacao": "Score M1",
        "score_setor_2022_calibrado": "Score Censo",
        "qualidade_join_uf": "Join",
        "coverage_pct_setor_2022": "Coverage %",
        "motivo_priorizacao": "Motivo",
        "flag_outlier_espacial": "Outlier",
        "flag_baixa_pop_setor": "Dens. < 5k",
        "status_pipeline": "Status",
    }
    tbl = view[[c for c in tbl_cols if c in view.columns]].rename(
        columns={k: v for k, v in tbl_cols.items() if k in view.columns}
    )
    for col in ["Score Hibrido", "Score M1", "Score Censo"]:
        if col in tbl.columns:
            tbl[col] = tbl[col].map(lambda v: f"{v:.1f}" if pd.notna(v) else "-")
    if "Coverage %" in tbl.columns:
        tbl["Coverage %"] = tbl["Coverage %"].map(lambda v: f"{v:.1f}%" if pd.notna(v) else "-")
    for col in ["Outlier", "Dens. < 5k"]:
        if col in tbl.columns:
            tbl[col] = tbl[col].map({True: "Sim", False: "Nao", "True": "Sim", "False": "Nao"}).fillna("Nao")
    for col in ["Rank Brasil", "Rank UF"]:
        if col in tbl.columns:
            tbl[col] = tbl[col].map(lambda v: int(v) if pd.notna(v) else "-")

    height_tbl = min(700, 38 + 35 * min(len(tbl), 100))
    st.dataframe(tbl, width="stretch", hide_index=True, height=height_tbl)

    # ---------- notas editoriais ----------
    st.markdown("---")
    nc1, nc2 = st.columns(2)
    with nc1:
        st.markdown(
            """
            <div class="section-card">
                <h4>Como usar o Plano</h4>
                <p><strong>Estrategico</strong>: top 20 Brasil — decisao imediata da diretoria.</p>
                <p><strong>Alta</strong>: top 21-50 Brasil — prospecao prioritaria no trimestre.</p>
                <p><strong>Tatica</strong>: top 10 por UF fora do top 50 — pipeline regional.</p>
                <p><strong>Status</strong>: "Novo" indica que ainda nao entrou no pipeline de prospecao.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with nc2:
        st.markdown(
            f"""
            <div class="section-card">
                <h4>Restricoes e rastreabilidade</h4>
                <p><strong>score_priorizacao M1</strong> nao foi alterado — serve de ancora municipal.</p>
                <p><strong>Score Censo</strong> refina o hex dentro do municipio aprovado pelo M1 quando ha camada granular.</p>
                <p><strong>Fallback municipal/M1</strong>: mantem a shortlist nacional ativa mesmo sem camada local; hoje aparece em {ufs_com_fallback_plano} UFs do plano.</p>
                <p><strong>Outlier espacial</strong>: fenomeno real; ler contexto antes de agir.</p>
                <p><strong>UFs cobertas</strong>: base nacional com {total_ufs_plano} UFs e {total_municipios_plano} municipios.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def main() -> None:
    inject_styles()
    render_header()

    try:
        df = build_dashboard_dataset()
    except (FileNotFoundError, ValueError) as exc:
        st.error(str(exc))
        st.stop()

    carteira_df = load_carteira()
    plano_df = load_plano()

    (
        selected_ufs,
        selected_cities,
        selected_faixas,
        selected_hybrid_eligibility,
        selected_coverage_buckets,
        selected_join_quality,
        only_top_municipio,
        only_top_hex_intraurbano,
    ) = render_sidebar_filters(df)

    filtered_df = apply_global_filters(
        df,
        selected_ufs=selected_ufs,
        selected_cities=selected_cities,
        selected_faixas=selected_faixas,
        selected_hybrid_eligibility=selected_hybrid_eligibility,
        selected_coverage_buckets=selected_coverage_buckets,
        selected_join_quality=selected_join_quality,
        only_top_municipio=only_top_municipio,
        only_top_hex_intraurbano=only_top_hex_intraurbano,
    )

    st.caption(
        f"Recorte atual: {format_int(len(filtered_df))} hexagonos | "
        f"{format_int(filtered_df['uf'].nunique()) if not filtered_df.empty else '0'} UFs | "
        f"{format_int(filtered_df['nome_municipio'].nunique()) if not filtered_df.empty else '0'} cidades"
    )
    st.caption(
        "Base oficial preservada: `data/outputs/hexagonos_brasil_dashboard.parquet` continua sendo a fonte do M1. "
        "As camadas censitaria e hibrida entram apenas como enriquecimento local."
    )

    if not selected_ufs:
        st.info("Selecione uma UF na barra lateral para iniciar a analise do dashboard.")
        st.stop()

    if filtered_df.empty:
        render_empty_state()
        return

    city_summary = build_city_summary(filtered_df)
    uf_summary = build_uf_summary(filtered_df)

    tabs = st.tabs(
        [
            "Visao Executiva",
            "Analise Territorial",
            "Ranking e Priorizacao",
            "Comparacao por UF",
            "Modelo Hibrido",
            "Carteira de Expansao",
            "Plano de Expansao",
        ]
    )

    with tabs[0]:
        render_visao_executiva(
            filtered_df,
            city_summary,
            uf_summary,
            selected_ufs=selected_ufs,
            selected_cities=selected_cities,
        )

    with tabs[1]:
        render_analise_territorial(filtered_df, city_summary)

    with tabs[2]:
        render_ranking_priorizacao(filtered_df)

    with tabs[3]:
        render_comparacao_uf(city_summary, uf_summary)

    with tabs[4]:
        render_modelo_hibrido_v2(
            filtered_df,
            selected_ufs=selected_ufs,
            selected_cities=selected_cities,
            selected_faixas=selected_faixas,
        )

    with tabs[5]:
        render_carteira_expansao(
            carteira_df,
            selected_ufs=selected_ufs,
            selected_cities=selected_cities,
        )

    with tabs[6]:
        render_plano_expansao(plano_df)


if __name__ == "__main__":
    if get_script_run_ctx(suppress_warning=True) is None:
        sys.argv = [
            "streamlit",
            "run",
            str(Path(__file__).resolve()),
            "--server.address",
            "localhost",
            "--server.port",
            "5000",
            "--server.headless",
            "true",
            "--server.showEmailPrompt",
            "false",
            "--browser.gatherUsageStats",
            "false",
        ]
        raise SystemExit(stcli.main())
    main()
