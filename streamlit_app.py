from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit.runtime.scriptrunner import get_script_run_ctx
from streamlit.web import cli as stcli

from motor_expansao.dashboard.censo_map import render_mapa_censitario_estatico_png  # noqa: F401
from motor_expansao.dashboard.censo_point import analisar_ponto_censitario_setores  # noqa: F401
from motor_expansao.dashboard.censo_report import (  # noqa: F401
    gerar_csv_setores_censitarios,
    gerar_payloads_download_relatorio_censitario,
    gerar_pdf_relatorio_pontual_censitario,
    render_downloads_relatorio_censitario,
)
from motor_expansao.dashboard.competitors import (  # noqa: F401
    load_competitor_points,
    load_ultra_points,
    preload_logos,
)
from motor_expansao.dashboard.components import (  # noqa: F401
    _build_multihex_selection_layer,
    _carteira_prioridade_color,
    _category_options,
    _derivar_faixa_hibrida,
    _sort_carteira_by_m1,
    apply_exec_layout,
    build_analise_pontual_map,
    build_business_answers,
    build_dominio_map_figure,
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
    build_multihex_analysis_map,
    build_ranking_table,
    build_residual_by_uf_figure,
    build_residual_heatmap_figure,
    build_residual_score_dist_figure,
    build_scatter_figure,
    build_score_distribution_figure,
    build_top_bottom_uf_figure,
    build_top_cities_residual_figure,
    build_top_city_figure,
    build_top_uf_figure,
    build_uf_metric_figure,
    build_ultra_network_kpis,
    build_ultra_presence_map,
    build_unified_map_figure,
    filter_points_to_radius,
    render_answer_card,
    render_censo_score_legend,
    render_competitor_legend,
    render_dominio_tese_legend,
    render_faixa_legend,
    render_geographic_source_legend,
    render_manifest_footer,
    render_pop_cut_legend,
    render_residual_legend,
    render_residual_score_legend,
    render_score_bands_legend,
    render_ultra_legend,
    resolve_map_view,
    style_ranking_table,
)
from motor_expansao.dashboard.constants import (  # noqa: F401
    BOOL_COLUMNS,
    BRASIL_CENTER,
    CENSO_SCORE_COLORS,
    CENSO_TRACE_LOAD_COLS,
    CENSO_UFS,
    COLOR_MODE_DEFAULT,
    COLOR_MODE_IDS,
    COLOR_MODES,
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
    OVERLAY_IDS,
    OVERLAYS,
    REQUIRED_COLUMNS,
    RESIDUAL_MERCADO_COLS,
    RESIDUAL_SCORE_BANDS,
    TABLE_ROW_LIMIT,
    TEXT_COLUMNS,
    color_mode_available,
    overlay_available,
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
    agregar_cenario_multihex,
    analisar_entorno_ponto,
    apply_global_filters,
    build_city_summary,
    build_pop_cut_lookup,
    build_uf_summary,
    derive_pop_cut_columns,
    enrich_dashboard_data,
    haversine_km,
    list_censo_geo_municipios,
    list_partitioned_ufs,
    lookup_hex_by_coord,
    parse_coordinate_input,
    parse_hex_ids_from_text,
    read_censo_geo_partition,
    read_enriched_uf_partition,
    resolve_cod_municipio_from_geo_dir,
)
from motor_expansao.dashboard.pages import (  # noqa: F401
    DASHBOARD_TAB_LABELS,
    _extract_click_coord_from_selection,
    _hex_id_to_centroid,
    _render_multihex_controls,
    _render_multihex_kpis,
    inject_styles,
    render_analise_pontual,
    render_analise_territorial,
    render_carteira_e_plano,
    render_carteira_expansao,
    render_comparacao_uf,
    render_coord_search_sidebar,
    render_empty_state,
    render_expansao_dominio,
    render_header,
    render_hex_search_result,
    render_mapa_pydeck_fragment,
    render_mapa_territorial,
    render_modelo_hibrido,
    render_modelo_hibrido_v2,
    render_plano_expansao,
    render_ranking_priorizacao,
    render_relatorio_pontual_censitario,
    render_sidebar_filters,
    render_tab_selector,
    render_uf_selectbox,
    render_visao_executiva,
)
from motor_expansao.dashboard.schemas import validate_dashboard_frame  # noqa: F401
from motor_expansao.dashboard.utils import (  # noqa: F401
    _censo_score_to_color,
    _residual_score_to_color,
    format_density,
    format_int,
    format_pct,
    format_score,
    hex_to_rgba,
    score_band_to_color,
)

st.set_page_config(
    page_title="Ultra Academia | Mapa Territorial",
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
PLANO_DOMINIO_PATH = Path(__file__).resolve().parent / "data" / "outputs" / "plano_expansao_dominio.parquet"
ENRIQUECIDO_DIR = (
    Path(__file__).resolve().parent / "data" / "outputs" / "hexagonos_dashboard_enriquecido"
)
CENSO_GEO_DIR = Path(__file__).resolve().parent / "data" / "outputs" / "setores_censitarios_2022_geo"
MANIFEST_PATH = Path(__file__).resolve().parent / "data" / "outputs" / "_manifest.json"

preload_logos(CONCORRENTES_DIR, ultra_dir=ULTRA_PATH.parent)


def _ensure_dataset() -> None:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            "Arquivo oficial ausente: `data/outputs/hexagonos_brasil_dashboard.parquet`."
        )


def _read_m1_frame() -> pd.DataFrame:
    _ensure_dataset()
    df = _read_parquet_subset(DATASET_PATH, REQUIRED_COLUMNS)
    validate_dashboard_frame(df, source=str(DATASET_PATH))
    return _prepare_dataframe(df)


def _read_hybrid_frame() -> pd.DataFrame:
    return _prepare_dataframe(_read_optional_parquet_subset(HYBRID_PATH, HYBRID_LOAD_COLS))


def _read_censo_trace_frame() -> pd.DataFrame:
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


def _read_estrutural_pop_frame() -> pd.DataFrame:
    """Carrega pop_total do parquet estrutural para corrigir o fallback de população no tooltip."""
    return _read_optional_parquet_subset(ESTRUTURAL_PATH, ["hex_id", "pop_total"])


@st.cache_resource(show_spinner=False)
def load_data() -> pd.DataFrame:
    return _read_m1_frame()


@st.cache_resource(show_spinner=False)
def load_hybrid_data() -> pd.DataFrame:
    return _read_hybrid_frame()


@st.cache_resource(show_spinner=False)
def load_censo_trace_data() -> pd.DataFrame:
    return _read_censo_trace_frame()


@st.cache_resource(show_spinner=False)
def load_estrutural_pop() -> pd.DataFrame:
    return _read_estrutural_pop_frame()


@st.cache_resource(show_spinner=False)
def build_dashboard_dataset() -> pd.DataFrame:
    # Le e funde via helpers nao-cacheados: os insumos intermediarios (M1, hibrido,
    # censo, estrutural ~600 MB) viram locais liberados apos o merge, em vez de
    # ficarem residentes em caches @st.cache_resource paralelos. Os loaders cacheados
    # acima seguem disponiveis para uso pontual e testes, sem entrar no caminho do app.
    return enrich_dashboard_data(
        _read_m1_frame(),
        _read_hybrid_frame(),
        _read_censo_trace_frame(),
        estrutural_pop_df=_read_estrutural_pop_frame(),
    )


@st.cache_data(show_spinner=False)
def load_uf_catalog() -> list[str]:
    # Catalogo leve para a sidebar: lista as particoes `uf=XX` do dataset
    # enriquecido (Bloco 3) sem carregar dados. Fallback: le apenas a coluna `uf`
    # do parquet oficial M1 quando o artefato particionado ainda nao existe.
    ufs = list_partitioned_ufs(ENRIQUECIDO_DIR)
    if ufs:
        return ufs
    _ensure_dataset()
    uf_df = _read_optional_parquet_subset(DATASET_PATH, ["uf"])
    if uf_df.empty:
        return []
    return sorted(uf_df["uf"].dropna().astype(str).unique().tolist())


@st.cache_resource(show_spinner=False)
def load_uf_slice(uf: str) -> pd.DataFrame:
    # Carga lazy por UF (cache por UF). Caminho rapido: particao `uf=XX` do dataset
    # enriquecido (Bloco 3). Fallback: funde o Brasil em runtime e filtra a UF
    # quando a particao nao existe. Nao recalcula score nem altera artefatos.
    slice_df = read_enriched_uf_partition(ENRIQUECIDO_DIR, uf)
    if not slice_df.empty:
        return slice_df
    full = build_dashboard_dataset()
    return full.loc[full["uf"] == uf].reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_censo_geo_municipios(uf: str) -> list[str]:
    return list_censo_geo_municipios(CENSO_GEO_DIR, uf)


@st.cache_data(show_spinner=False)
def load_censo_geo_setores(uf: str, cod_municipio: str | None = None) -> pd.DataFrame:
    return read_censo_geo_partition(CENSO_GEO_DIR, uf, cod_municipio)


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
        "pop_hex_base", "tam_populacao_hex", "tam_fitness_potencial",
        "sam_fitness_potencial", "capacidade_default_concorrente_alunos",
        "oferta_consumida_mercado_estimada", "oferta_consumida_ultra_real",
        "n_unidades_ultra_performance_hex", "oferta_efetiva_disponivel",
        "penetracao_fitness_mercado_estimada", "share_ultra_estimado_hex",
        "score_oportunidade_residual",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ["flag_outlier_espacial", "flag_baixa_pop_setor", "flag_join_uf_restrito",
                "flag_monitoramento_prioritario", "flag_sam_fitness"]:
        if col in df.columns:
            df[col] = df[col].fillna(False).astype(bool)
    return df


@st.cache_data(show_spinner=False)
def load_plano_dominio() -> pd.DataFrame:
    if not PLANO_DOMINIO_PATH.exists():
        return pd.DataFrame()
    df = pd.read_parquet(PLANO_DOMINIO_PATH)
    for col in [
        "score_oportunidade_residual", "oferta_efetiva_disponivel", "sam_fitness_potencial",
        "residual_incremental_capturado", "residual_cluster_pos_acao",
        "dist_ultra_mais_proxima_m", "dist_nova_ancora_mais_proxima_m",
        "pressao_concorrencial_score_2km", "pressao_concorrencial_media",
        "n_hex_cluster", "residual_total_cluster", "score_residual_max",
        "score_residual_medio", "sam_total_cluster", "dist_ultra_min_cluster",
        "n_concorrentes_mapeados_2km",
        "rank_dominio_brasil", "rank_dominio_uf", "rank_dominio_cidade",
        "ordem_expansao_cidade",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ["flag_sam_fitness", "flag_canibalizacao_ultra_1km", "flag_white_space_2km"]:
        if col in df.columns:
            df[col] = df[col].fillna(False).astype(bool)
    return df


@st.cache_data(show_spinner=False)
def load_plano() -> pd.DataFrame:
    if not PLANO_PATH.exists():
        return pd.DataFrame()
    df = pd.read_parquet(PLANO_PATH)
    for col in [
        "score_expansao_hibrido", "score_setor_2022_calibrado", "score_priorizacao",
        "score_priorizacao_municipio", "coverage_pct_setor_2022", "rank_brasil", "rank_uf",
        "rank_carteira_brasil", "rank_carteira_uf", "rank_municipio_uf",
        "rank_municipio_brasil", "rank_hex_intraurbano",
        "pop_hex_base", "tam_populacao_hex", "tam_fitness_potencial",
        "sam_fitness_potencial", "capacidade_default_concorrente_alunos",
        "oferta_consumida_mercado_estimada", "oferta_consumida_ultra_real",
        "n_unidades_ultra_performance_hex", "oferta_efetiva_disponivel",
        "penetracao_fitness_mercado_estimada", "share_ultra_estimado_hex",
        "score_oportunidade_residual",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ["flag_outlier_espacial", "flag_baixa_pop_setor", "flag_join_uf_restrito", "flag_sam_fitness"]:
        if col in df.columns:
            df[col] = df[col].fillna(False).astype(bool)
    return df


def main() -> None:
    inject_styles()
    render_header()

    try:
        uf_catalog = load_uf_catalog()
    except (FileNotFoundError, ValueError) as exc:
        st.error(str(exc))
        st.stop()

    # Seletor de UF primeiro (catalogo leve): a carga so acontece apos a escolha,
    # lendo somente a particao da UF em vez de fundir o Brasil inteiro a frio.
    selected_uf = render_uf_selectbox(uf_catalog)

    if not selected_uf:
        st.info("Selecione uma UF na barra lateral para iniciar a analise do dashboard.")
        st.stop()

    try:
        df = load_uf_slice(selected_uf)
    except (FileNotFoundError, ValueError) as exc:
        st.error(str(exc))
        st.stop()

    if df.empty:
        render_empty_state()
        return

    pop_lookup = build_pop_cut_lookup(df)
    carteira_df = load_carteira()
    plano_df = load_plano()
    plano_dominio_df = load_plano_dominio()
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
    ) = render_sidebar_filters(df, selected_uf)

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

    if filtered_df.empty:
        render_empty_state()
        return

    # Render lazy por aba (Bloco 5): so a aba ativa e construida por rerun, em vez
    # de `st.tabs` executar o corpo das 4 abas a cada interacao. Os summaries so sao
    # calculados para as abas que os consomem.
    active_tab = render_tab_selector(DASHBOARD_TAB_LABELS)

    if active_tab in ("Visao Executiva", "Mapa Territorial"):
        city_summary = build_city_summary(filtered_df)
        uf_summary = build_uf_summary(filtered_df)

    if active_tab == "Visao Executiva":
        render_visao_executiva(
            filtered_df,
            city_summary,
            uf_summary,
            selected_ufs=selected_ufs,
            selected_cities=selected_cities,
            competitors_df=competitors_df,
            ultra_df=ultra_df,
            carteira_df=carteira_df,
            plano_dominio_df=plano_dominio_df,
            search_pin=search_pin,
            search_hex_id=search_hex_id,
        )
    elif active_tab == "Mapa Territorial":
        render_mapa_territorial(
            filtered_df,
            selected_ufs=selected_ufs,
            selected_cities=selected_cities,
            competitors_df=competitors_df,
            ultra_df=ultra_df,
            search_pin=search_pin,
            search_hex_id=search_hex_id,
            dominio_df=plano_dominio_df,
            city_summary=city_summary,
            uf_summary=uf_summary,
            selected_faixas=selected_faixas,
            censo_geo_loader=load_censo_geo_setores,
            censo_geo_dir=CENSO_GEO_DIR,
        )
    elif active_tab == "Expansao de Dominio":
        render_expansao_dominio(
            plano_dominio_df,
            selected_ufs=selected_ufs,
            selected_cities=selected_cities,
            competitors_df=competitors_df,
            ultra_df=ultra_df,
        )
    elif active_tab == "Carteira e Plano":
        render_carteira_e_plano(
            carteira_df,
            plano_df,
            selected_ufs=selected_ufs,
            selected_cities=selected_cities,
            pop_cut_lookup=pop_lookup,
        )

    # Rodape read-only de proveniencia (BLK-OPS-03): fora dos branches de aba,
    # idempotente; ausencia do _manifest.json nao quebra o app.
    render_manifest_footer(MANIFEST_PATH)


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
