from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
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
from motor_expansao.dashboard.competitors import load_competitor_points, load_ultra_points, preload_logos  # noqa: F401
from motor_expansao.dashboard.components import (  # noqa: F401
    _carteira_prioridade_color,
    _category_options,
    _derivar_faixa_hibrida,
    _sort_carteira_by_m1,
    apply_exec_layout,
    build_business_answers,
    build_faixa_comparison_figure,
    build_hybrid_alerts,
    build_hybrid_kpis,
    build_hybrid_map_figure,
    build_hybrid_municipios_table,
    build_hybrid_portfolio_table,
    build_hybrid_score_comparison_figure,
    build_hybrid_top_hexes_table,
    build_indicator_snapshot,
    build_kpis,
    build_map_figure,
    build_map_scope_caption,
    build_ranking_table,
    build_scatter_figure,
    build_score_distribution_figure,
    build_top_bottom_uf_figure,
    build_top_city_figure,
    build_top_uf_figure,
    build_uf_metric_figure,
    render_answer_card,
    render_censo_score_legend,
    render_competitor_legend,
    render_faixa_legend,
    render_geographic_source_legend,
    render_pop_cut_legend,
    render_ultra_legend,
    resolve_map_view,
    style_ranking_table,
)
from motor_expansao.dashboard.data import (  # noqa: F401
    _coalesce_columns,
    _derive_confianca_geografica,
    _derive_hybrid_labels,
    _has_censo_signal,
    _normalized_join_quality,
    _prepare_censo_trace,
    _prepare_dataframe,
    _read_optional_parquet_subset,
    _read_parquet_subset,
    apply_global_filters,
    build_city_summary,
    build_pop_cut_lookup,
    build_uf_summary,
    derive_pop_cut_columns,
    enrich_dashboard_data,
    lookup_hex_by_coord,
    parse_coordinate_input,
)
from motor_expansao.dashboard.pages import (  # noqa: F401
    inject_styles,
    render_analise_territorial,
    render_carteira_expansao,
    render_comparacao_uf,
    render_coord_search_sidebar,
    render_empty_state,
    render_header,
    render_hex_search_result,
    render_modelo_hibrido,
    render_modelo_hibrido_v2,
    render_plano_expansao,
    render_ranking_priorizacao,
    render_sidebar_filters,
    render_visao_executiva,
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
CONCORRENTES_DIR = Path(__file__).resolve().parent / "concorrentes"
ULTRA_PATH = Path(__file__).resolve().parent / "data" / "ultra" / "Ultra.csv"
CENSO_CORE_PATH = Path(__file__).resolve().parent / "data" / "staging" / "censo2022_setores_calibrado.parquet"
CENSO_EXPANDED_PATH = (
    Path(__file__).resolve().parent / "data" / "staging" / "censo2022_setores_calibrado_piloto_expandido.parquet"
)
CENSO_VALIDATED_PATH = (
    Path(__file__).resolve().parent / "data" / "staging" / "censo2022_setores_validado_v2.parquet"
)
ESTRUTURAL_PATH = (
    Path(__file__).resolve().parent / "data" / "staging" / "brasil_estrutural.parquet"
)

preload_logos(CONCORRENTES_DIR, ultra_dir=ULTRA_PATH.parent)


def _ensure_dataset() -> None:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            "Arquivo oficial ausente: `data/outputs/hexagonos_brasil_dashboard.parquet`."
        )


@st.cache_resource(show_spinner=False)
def load_data() -> pd.DataFrame:
    _ensure_dataset()
    df = _read_parquet_subset(DATASET_PATH, REQUIRED_COLUMNS)
    return _prepare_dataframe(df)


@st.cache_resource(show_spinner=False)
def load_hybrid_data() -> pd.DataFrame:
    return _prepare_dataframe(_read_optional_parquet_subset(HYBRID_PATH, HYBRID_LOAD_COLS))


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


@st.cache_resource(show_spinner=False)
def load_estrutural_pop() -> pd.DataFrame:
    """Carrega pop_total do parquet estrutural para corrigir o fallback de população no tooltip."""
    return _read_optional_parquet_subset(ESTRUTURAL_PATH, ["hex_id", "pop_total"])


@st.cache_resource(show_spinner=False)
def build_dashboard_dataset() -> pd.DataFrame:
    return enrich_dashboard_data(
        load_data(),
        load_hybrid_data(),
        load_censo_trace_data(),
        estrutural_pop_df=load_estrutural_pop(),
    )


@st.cache_data(show_spinner=False)
def load_competitors() -> pd.DataFrame:
    return load_competitor_points(CONCORRENTES_DIR)


@st.cache_data(show_spinner=False)
def load_ultra() -> pd.DataFrame:
    return load_ultra_points(ULTRA_PATH)


@st.cache_data(show_spinner=False)
def load_carteira() -> pd.DataFrame:
    if not CARTEIRA_PATH.exists():
        return pd.DataFrame()
    df = pd.read_parquet(CARTEIRA_PATH)
    for col in [
        "score_priorizacao", "score_expansao_hibrido", "score_setor_2022_calibrado",
        "score_priorizacao_municipio", "coverage_pct_setor_2022", "rank_brasil", "rank_uf",
        "rank_carteira_brasil", "rank_carteira_uf", "rank_municipio_uf",
        "rank_municipio_brasil", "rank_hex_intraurbano",
    ]:
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
    for col in [
        "score_expansao_hibrido", "score_setor_2022_calibrado", "score_priorizacao",
        "score_priorizacao_municipio", "coverage_pct_setor_2022", "rank_brasil", "rank_uf",
        "rank_carteira_brasil", "rank_carteira_uf", "rank_municipio_uf",
        "rank_municipio_brasil", "rank_hex_intraurbano",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ["flag_outlier_espacial", "flag_baixa_pop_setor", "flag_join_uf_restrito"]:
        if col in df.columns:
            df[col] = df[col].fillna(False).astype(bool)
    return df


def main() -> None:
    inject_styles()
    render_header()

    try:
        df = build_dashboard_dataset()
    except (FileNotFoundError, ValueError) as exc:
        st.error(str(exc))
        st.stop()

    pop_lookup = build_pop_cut_lookup(df)
    carteira_df = load_carteira()
    plano_df = load_plano()
    competitors_df = load_competitors()
    ultra_df = load_ultra()

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

    search_pin = render_coord_search_sidebar()
    _search_result = lookup_hex_by_coord(*search_pin, df) if search_pin is not None else None
    search_hex_id = _search_result["hex_id"] if _search_result is not None else None

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

    if search_pin is not None:
        render_hex_search_result(
            search_pin,
            full_df=df,
            filtered_df=filtered_df,
            pop_cut_lookup=pop_lookup,
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
            competitors_df=competitors_df,
            ultra_df=ultra_df,
            search_pin=search_pin,
            search_hex_id=search_hex_id,
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
            competitors_df=competitors_df,
            ultra_df=ultra_df,
            search_pin=search_pin,
            search_hex_id=search_hex_id,
        )

    with tabs[5]:
        render_carteira_expansao(
            carteira_df,
            selected_ufs=selected_ufs,
            selected_cities=selected_cities,
            pop_cut_lookup=pop_lookup,
        )

    with tabs[6]:
        render_plano_expansao(plano_df, pop_cut_lookup=pop_lookup)


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
