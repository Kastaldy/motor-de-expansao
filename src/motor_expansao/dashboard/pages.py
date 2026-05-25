from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pandas as pd
import streamlit as st

from dashboard.constants import (
    COLOR_MODE_DEFAULT,
    COLOR_MODES,
    COLORS,
    COVERAGE_BUCKET_ORDER,
    FAIXA_ORDEM,
    HYBRID_ELIGIBILITY_ORDER,
    JOIN_QUALITY_ORDER,
    OVERLAYS,
    POP_MIN_ACIONAVEL,
    TABLE_ROW_LIMIT,
    color_mode_available,
)
from dashboard.utils import format_int, format_pct, format_score
from motor_expansao.dashboard.components import (
    _build_multihex_selection_layer,
    _carteira_prioridade_color,
    _category_options,
    _sort_carteira_by_m1,
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
    build_analise_pontual_map,
    build_multihex_analysis_map,
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
    render_pop_cut_legend,
    render_residual_legend,
    render_residual_score_legend,
    render_score_bands_legend,
    render_ultra_legend,
    style_ranking_table,
)
from motor_expansao.dashboard.data import (
    agregar_cenario_multihex,
    analisar_entorno_ponto,
    lookup_hex_by_coord,
    parse_coordinate_input,
    parse_hex_ids_from_text,
    resolve_cod_municipio_from_geo_dir,
)
from motor_expansao.dashboard.censo_map import render_mapa_censitario_estatico_png
from motor_expansao.dashboard.censo_point import (
    RAIO_CENSITARIO_DEFAULT_KM,
    analisar_ponto_censitario_setores,
)
from motor_expansao.dashboard.censo_report import render_downloads_relatorio_censitario


RESIDUAL_SORT_COLUMNS = [
    "oferta_efetiva_disponivel",
    "score_oportunidade_residual",
    "rank_brasil",
]


def _has_residual_metrics(df: pd.DataFrame) -> bool:
    return "oferta_efetiva_disponivel" in df.columns and df["oferta_efetiva_disponivel"].notna().any()


def _sort_by_residual(df: pd.DataFrame) -> pd.DataFrame:
    cols = [column for column in RESIDUAL_SORT_COLUMNS if column in df.columns]
    if not cols:
        return df
    ascending = [False if column != "rank_brasil" else True for column in cols]
    return df.sort_values(cols, ascending=ascending, kind="stable")


def _format_residual_display_columns(df: pd.DataFrame) -> pd.DataFrame:
    formatted = df.copy()
    for col in ["SAM Fitness", "Oferta Residual", "Consumo Conc. (est.)", "Consumo Ultra (real)", "Consumo Total Instalado"]:
        if col in formatted.columns:
            formatted[col] = formatted[col].map(lambda v: format_int(v) if pd.notna(v) else "-")
    if "Score Residual" in formatted.columns:
        formatted["Score Residual"] = formatted["Score Residual"].map(
            lambda v: f"{v:.1f}" if pd.notna(v) else "-"
        )
    if "Share Ultra" in formatted.columns:
        formatted["Share Ultra"] = formatted["Share Ultra"].map(
            lambda v: format_pct(float(v) * 100) if pd.notna(v) else "-"
        )
    return formatted


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


def render_uf_selectbox(uf_options: list[str]) -> str | None:
    """Renderiza apenas o seletor de UF a partir do catalogo leve.

    A carga lazy por UF (Bloco 4) depende deste valor: o dataset so e lido apos a
    escolha da UF, evitando fundir o Brasil inteiro a frio.
    """
    st.sidebar.markdown("### Filtros globais")
    st.sidebar.caption("Refine o recorte executivo do M1 e da camada hibrida sem alterar o score oficial.")
    return st.sidebar.selectbox(
        "UF",
        options=uf_options,
        index=None,
        placeholder="Selecione uma UF",
    )


DASHBOARD_TAB_LABELS = [
    "Visao Executiva",
    "Mapa Territorial",
    "Expansao de Dominio",
    "Carteira e Plano",
]


def render_tab_selector(
    labels: list[str] | None = None,
    *,
    key: str = "dashboard_active_tab",
) -> str:
    """Seletor de aba que gateia o render: so a aba ativa e construida por rerun.

    Substitui `st.tabs` (que executa o corpo das 4 abas a cada rerun) por um
    `st.segmented_control` com estado em `session_state`, preservando a UX de abas
    mas chamando apenas o `render_*` da aba ativa (Bloco 5 — render lazy das abas).
    """
    opts = labels or DASHBOARD_TAB_LABELS
    last_key = f"{key}_last"
    selected = st.segmented_control(
        "Navegacao do dashboard",
        options=opts,
        default=opts[0],
        key=key,
        label_visibility="collapsed",
    )
    # selection_mode="single" permite desmarcar (None); manter a ultima aba ativa.
    if not selected:
        selected = st.session_state.get(last_key) or opts[0]
    st.session_state[last_key] = selected
    return selected


def render_sidebar_filters(
    df: pd.DataFrame,
    selected_uf: str | None = None,
) -> tuple[list[str], list[str], list[str], list[str], list[str], list[str], bool, bool]:
    # `df` ja chega como o slice da UF selecionada (carga lazy do Bloco 4); o
    # seletor de UF e renderizado antes, por `render_uf_selectbox`.
    selected_ufs = [selected_uf] if selected_uf else []

    all_cities = _category_options(df["nome_municipio"], observed=True)
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


def render_coord_search_sidebar() -> tuple[float, float] | None:
    """Render coordinate search widget in sidebar. Returns ``(lat, lng)`` or ``None``."""
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Busca por coordenada")
    st.sidebar.caption("Localize um hexagono pela coordenada. Offline, sem API externa.")
    raw = st.sidebar.text_input(
        "Coordenada (lat, lng)",
        placeholder="-23.55, -46.63",
        key="coord_search_input",
    )
    if not raw or not raw.strip():
        return None
    result = parse_coordinate_input(raw)
    if result is None:
        st.sidebar.error(
            "Formato invalido ou fora dos limites do Brasil. "
            "Use: -23.55, -46.63  ou  -23,55; -46,63  ou  -23.55 -46.63"
        )
    return result


def render_hex_search_result(
    search_coord: tuple[float, float] | None,
    *,
    full_df: pd.DataFrame,
    filtered_df: pd.DataFrame,
    pop_cut_lookup: pd.DataFrame | None = None,
) -> None:
    """Render the detail card for the searched coordinate, if any."""
    if search_coord is None:
        return

    lat, lng = search_coord
    result = lookup_hex_by_coord(lat, lng, full_df)

    st.markdown("---")
    st.markdown(f"#### Hexagono pesquisado para `{lat:.5f}, {lng:.5f}`")

    if result is None:
        st.warning("Nao foi possivel converter a coordenada para um hexagono H3.")
        return

    hex_id = result["hex_id"]

    if result.get("_not_found"):
        st.info(
            f"Hexagono `{hex_id}` nao encontrado na base oficial M1. "
            "Pode ser uma area rural, maritima ou fora dos municipios mapeados."
        )
        return

    # Check visibility in current filters
    in_recorte = bool(
        not filtered_df.empty and not filtered_df.loc[filtered_df["hex_id"] == hex_id].empty
    )

    # Check pop cut removal
    pop_flag = True
    if pop_cut_lookup is not None and not pop_cut_lookup.empty and "hex_id" in pop_cut_lookup.columns:
        pop_row = pop_cut_lookup.loc[pop_cut_lookup["hex_id"] == hex_id]
        if not pop_row.empty:
            pop_flag = bool(pop_row.iloc[0].get("flag_pop_min_5k", True))

    status_lines = []
    if not in_recorte and not filtered_df.empty:
        uf_hex = result.get("uf", "")
        selected_ufs_in_view = sorted(filtered_df["uf"].dropna().unique().tolist()) if "uf" in filtered_df.columns else []
        if uf_hex and selected_ufs_in_view and uf_hex not in selected_ufs_in_view:
            status_lines.append(f"Fora do recorte atual (UF {uf_hex} nao selecionada).")
        else:
            status_lines.append("Fora do recorte atual (verificar filtros de faixa, cidade ou hibrido).")
    if not pop_flag:
        status_lines.append(f"Descartado pela regua de populacao minima ({format_int(POP_MIN_ACIONAVEL)} hab).")

    if status_lines:
        st.warning("  ".join(status_lines))
    else:
        st.success("Hexagono visivel no recorte atual.")

    cols = st.columns(4)
    cols[0].metric("Score M1", format_score(result.get("score_priorizacao")))
    cols[1].metric("Rank Brasil", format_int(result.get("rank_brasil")) if result.get("rank_brasil") is not None else "-")
    pop_val = result.get("pop_total_setor_2022") or result.get("pop_total") or result.get("populacao_proxy")
    cols[2].metric("Populacao", format_int(pop_val) if pop_val is not None else "-")
    renda_val = result.get("renda_per_capita_setor_2022_calibrada") or result.get("renda_per_capita")
    cols[3].metric("Renda per capita", f"R$ {format_int(renda_val)}" if renda_val is not None else "-")

    detail_cols = st.columns(3)
    detail_cols[0].metric("Hex ID", hex_id)
    detail_cols[1].metric("UF / Cidade", f"{result.get('uf', '-')} / {result.get('nome_municipio') or result.get('cidade', '-')}")
    detail_cols[2].metric("Fonte geografica", str(result.get("confianca_geografica", "municipal")))

    score_censo = result.get("score_setor_2022_calibrado")
    if score_censo is not None and not pd.isna(score_censo):
        extra_cols = st.columns(3)
        extra_cols[0].metric("Score Censitario", format_score(score_censo))
        extra_cols[1].metric("Elegibilidade hibrida", str(result.get("elegibilidade_hibrida", "-")))
        extra_cols[2].metric("Qualidade join", str(result.get("qualidade_join_uf", "-")))


def render_visao_executiva(
    df: pd.DataFrame,
    city_summary: pd.DataFrame,
    uf_summary: pd.DataFrame,
    *,
    selected_ufs: list[str],
    selected_cities: list[str],
    competitors_df: pd.DataFrame | None = None,
    ultra_df: pd.DataFrame | None = None,
    carteira_df: pd.DataFrame | None = None,
    plano_dominio_df: pd.DataFrame | None = None,
    search_pin: tuple[float, float] | None = None,
    search_hex_id: str | None = None,
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

    st.markdown("#### Presenca Ultra Academia")
    st.caption(
        "Mapa institucional da rede propria. Exibe apenas unidades Ultra com filtros de UF/cidade. "
        "Para analise de hexagonos, scores e residual, use a aba Mapa Territorial."
    )
    render_ultra_legend(ultra_df)
    ultra_map, ultra_count = build_ultra_presence_map(
        ultra_df,
        selected_ufs=selected_ufs,
        selected_cities=selected_cities,
    )
    if ultra_map is None:
        st.info(
            "Dados de unidades Ultra nao disponíveis ou sem unidades no recorte selecionado. "
            "Verifique `data/ultra/Ultra.csv`."
        )
    else:
        st.caption(f"Exibindo {ultra_count} unidade(s) Ultra no recorte atual.")
        st.pydeck_chart(ultra_map, width="stretch", height=500)

    st.markdown("---")
    st.markdown("#### Rede Ultra e Mercado")
    net_kpis = build_ultra_network_kpis(
        df,
        ultra_df,
        carteira_df,
        plano_dominio_df,
        selected_ufs=selected_ufs,
        selected_cities=selected_cities,
    )
    kpi_row1 = st.columns(3)
    kpi_row1[0].metric("Unidades Ultra no recorte", net_kpis["ultra_units"])
    kpi_row1[1].metric("Cidades com Ultra", net_kpis["cidades_com_ultra"])
    kpi_row1[2].metric("Score medio M1", net_kpis["score_medio_m1"])
    kpi_row2 = st.columns(3)
    kpi_row2[0].metric("Residual total (alunos)", net_kpis["residual_total"])
    kpi_row2[1].metric("Oportunidades sem Ultra proxima", net_kpis["opps_sem_ultra"])
    kpi_row2[2].metric("Ancoras de dominio", net_kpis["ancoras_dominio"])

    res_col1, res_col2 = st.columns(2)
    with res_col1:
        res_uf_fig = build_residual_by_uf_figure(carteira_df)
        if res_uf_fig is not None:
            st.plotly_chart(res_uf_fig, width="stretch")
    with res_col2:
        res_dist_fig = build_residual_score_dist_figure(carteira_df)
        if res_dist_fig is not None:
            st.plotly_chart(res_dist_fig, width="stretch")

    top_res_fig = build_top_cities_residual_figure(carteira_df)
    if top_res_fig is not None:
        st.plotly_chart(top_res_fig, width="stretch")

    st.markdown("---")
    st.markdown("#### Analise Comparativa por UF")
    chart_col_1, chart_col_2 = st.columns(2)
    with chart_col_1:
        top_city_fig = build_top_city_figure(city_summary)
        if top_city_fig is not None:
            st.plotly_chart(top_city_fig, width="stretch")
    with chart_col_2:
        top_uf_fig = build_top_uf_figure(uf_summary)
        if top_uf_fig is not None:
            st.plotly_chart(top_uf_fig, width="stretch")

    answers_uf = build_business_answers(city_summary, uf_summary)
    uf_col1, uf_col2, uf_col3 = st.columns(3)
    with uf_col1:
        render_answer_card("UFs a priorizar", answers_uf["ufs_priorizar"])
    with uf_col2:
        fig_opps = build_uf_metric_figure(
            uf_summary, metric="oportunidades_viaveis", label="Oportunidades viaveis", color=COLORS["brand_alt"]
        )
        if fig_opps is not None:
            st.plotly_chart(fig_opps, width="stretch")
    with uf_col3:
        fig_top_bottom = build_top_bottom_uf_figure(uf_summary)
        if fig_top_bottom is not None:
            st.plotly_chart(fig_top_bottom, width="stretch")


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
    competitors_df: pd.DataFrame | None = None,
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

    kpis = build_hybrid_kpis(hdf)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Municipios top M1 (top 20%)", kpis["municipios_top_m1"])
    k2.metric("Hexes top intraurbano", kpis["hexes_top_intraurbano"])
    k3.metric("UFs com camada censitaria", kpis["ufs_censo"])
    k4.metric("Registros p/ monitoramento", kpis["registros_monitoramento"])

    st.markdown("---")

    st.markdown("#### Mapa de Oportunidades Intraurbanas")
    st.caption(
        "Hexes com `top_hex_intraurbano=True` coloridos pelo `score_setor_2022_calibrado`. "
        "Apenas UFs com camada censitaria elegivel (DF, GO, MG, RJ, RS, SP)."
    )
    render_score_bands_legend("Score Censitario (score_setor_2022_calibrado)")

    hybrid_map, n_points = build_hybrid_map_figure(
        hdf,
        selected_ufs=selected_ufs,
        selected_cities=selected_cities,
        competitors_df=competitors_df,
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
    competitors_df: pd.DataFrame | None = None,
    ultra_df: pd.DataFrame | None = None,
    search_pin: tuple[float, float] | None = None,
    search_hex_id: str | None = None,
) -> None:
    if hdf.empty:
        st.warning("Dataset hibrido nao disponivel. Verifique `data/outputs/oportunidades_expansao_hibrido.parquet`.")
        return

    st.markdown("#### Como interpretar os tres modelos")
    card_cols = st.columns(3)
    with card_cols[0]:
        st.markdown(
            """
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
            "Mapa Residual Fitness",
        ]
    )

    with subtabs[0]:
        st.markdown("##### Mapa com residual fitness")
        st.caption(
            "Mapa colorido por `score_oportunidade_residual` (potencial residual apos desconto da oferta instalada). "
            "Linhas vermelhas indicam join restrito ou qualidade C."
        )
        render_score_bands_legend("Score Residual (score_oportunidade_residual)")
        render_pop_cut_legend()
        render_ultra_legend(ultra_df)
        hybrid_map, n_points = build_hybrid_map_figure(
            hdf,
            selected_ufs=selected_ufs,
            selected_cities=selected_cities,
            selected_faixas=selected_faixas,
            color_col="score_oportunidade_residual",
            competitors_df=competitors_df,
            ultra_df=ultra_df,
            search_pin=search_pin,
            search_hex_id=search_hex_id,
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

    with subtabs[4]:
        st.caption(
            "Mapa colorido por `score_oportunidade_residual`: potencial de mercado residual apos desconto "
            "da oferta ja instalada (concorrentes + Ultra). Verde escuro = alta oportunidade residual; "
            "vermelho escuro = mercado ja ocupado ou potencial pequeno."
        )
        render_score_bands_legend("Score Residual (score_oportunidade_residual)")
        render_pop_cut_legend()
        render_ultra_legend(ultra_df)
        residual_map, n_residual = build_residual_heatmap_figure(
            hdf,
            selected_ufs=selected_ufs,
            selected_cities=selected_cities,
            competitors_df=competitors_df,
            ultra_df=ultra_df,
            search_pin=search_pin,
            search_hex_id=search_hex_id,
        )
        if residual_map is None:
            st.info("Nao ha score residual disponivel no recorte atual.")
        else:
            if len(hdf) > n_residual:
                st.caption(
                    f"Mapa limitado aos {format_int(n_residual)} hexes mais relevantes do recorte para manter performance local."
                )
            st.pydeck_chart(residual_map, width="stretch", height=580)


def render_carteira_expansao(
    carteira: pd.DataFrame,
    *,
    selected_ufs: list[str],
    selected_cities: list[str],
    pop_cut_lookup: pd.DataFrame | None = None,
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

    residual_disponivel = _has_residual_metrics(carteira)
    ufs_disponiveis = sorted(carteira["uf"].dropna().unique().tolist())
    municipios_disponiveis = sorted(carteira["nome_municipio"].dropna().unique().tolist())

    fc1, fc2, fc3, fc4, fc5 = st.columns([1.4, 2.2, 1.2, 1.8, 1.8])
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
    with fc4:
        if residual_disponivel and "quartil_oportunidade_residual" in carteira.columns:
            quartis_opcoes = sorted(carteira["quartil_oportunidade_residual"].dropna().unique().tolist())
            quartis_sel = st.multiselect(
                "Quartil residual",
                options=quartis_opcoes,
                default=quartis_opcoes,
                key="carteira_quartil_residual",
            )
        else:
            quartis_sel = []
    with fc5:
        if residual_disponivel:
            ordenacao = st.selectbox(
                "Ordenacao",
                options=["M1 oficial", "Oportunidade residual"],
                index=0,
                key="carteira_ordenacao",
            )
        else:
            ordenacao = "M1 oficial"

    view = carteira.copy()
    if ufs_sel:
        view = view[view["uf"].isin(ufs_sel)]
    if muns_sel:
        view = view[view["nome_municipio"].isin(muns_sel)]
    if prioridades_sel:
        view = view[view["prioridade_abertura"].isin(prioridades_sel)]
    if quartis_sel and "quartil_oportunidade_residual" in view.columns:
        view = view[view["quartil_oportunidade_residual"].isin(quartis_sel)]

    if pop_cut_lookup is not None and not pop_cut_lookup.empty and "hex_id" in view.columns:
        lookup_cols = [c for c in ["hex_id", "populacao_corte_hex", "fonte_populacao_corte", "flag_pop_min_5k"] if c in pop_cut_lookup.columns]
        view = view.merge(pop_cut_lookup[lookup_cols], on="hex_id", how="left")
        view["flag_pop_min_5k"] = view["flag_pop_min_5k"].fillna(False).astype(bool)
        n_descartados = int((~view["flag_pop_min_5k"]).sum())
        if n_descartados > 0:
            st.warning(
                f"{format_int(n_descartados)} oportunidades removidas pela regua de {format_int(POP_MIN_ACIONAVEL)} habitantes "
                f"(populacao_corte_hex < {format_int(POP_MIN_ACIONAVEL)} ou ausente). "
                "Essas oportunidades continuam no M1 oficial — apenas excluidas da carteira acionavel."
            )
        view = view[view["flag_pop_min_5k"]]

    if ordenacao == "Oportunidade residual":
        view = _sort_by_residual(view)
    else:
        view = _sort_carteira_by_m1(view)

    st.markdown("---")
    metric_cols = st.columns(5 if residual_disponivel else 4)
    n_oportunidades = len(view)
    n_municipios = view["cod_municipio"].nunique() if "cod_municipio" in view.columns else view["nome_municipio"].nunique()
    n_altas = int((view["prioridade_abertura"] == "Alta").sum())
    n_ufs = view["uf"].nunique()
    metric_cols[0].metric("Oportunidades no recorte", format_int(n_oportunidades))
    metric_cols[1].metric("Municipios no recorte", format_int(n_municipios))
    metric_cols[2].metric("Prioridade Alta", format_int(n_altas))
    metric_cols[3].metric("UFs representadas", format_int(n_ufs))
    if residual_disponivel:
        residual_total = pd.to_numeric(view.get("oferta_efetiva_disponivel"), errors="coerce").fillna(0.0).sum()
        metric_cols[4].metric("Oferta residual", format_int(residual_total))

    if view.empty:
        st.info("Nenhuma oportunidade no recorte selecionado.")
        return

    st.markdown("##### Top oportunidades por UF")
    st.caption(
        "Melhor hex de cada UF no recorte atual, respeitando a ordenacao escolhida. "
        "A ordenacao padrao segue o `rank_brasil` oficial do M1."
    )
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
        "sam_fitness_potencial": "SAM Fitness",
        "oferta_efetiva_disponivel": "Oferta Residual",
        "score_oportunidade_residual": "Score Residual",
        "quartil_oportunidade_residual": "Quartil Residual",
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
    uf_disp = _format_residual_display_columns(uf_disp)
    st.dataframe(uf_disp, width="stretch", hide_index=True, height=min(250, 38 + 35 * len(uf_disp)))

    st.markdown("##### Tabela principal — onde abrir agora?")
    if ordenacao == "Oportunidade residual":
        st.caption(
            "Ordenada por `oferta_efetiva_disponivel` como leitura auxiliar de potencial absoluto; "
            "o ranking oficial M1 permanece preservado nas colunas."
        )
    else:
        st.caption(
            "Ordenada pelo `rank_brasil` oficial do M1. O Censitario, o Hibrido e o residual aparecem apenas como apoio para leitura local e sizing operacional."
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
        "sam_fitness_potencial": "SAM Fitness",
        "oferta_efetiva_disponivel": "Oferta Residual",
        "score_oportunidade_residual": "Score Residual",
        "quartil_oportunidade_residual": "Quartil Residual",
        "share_ultra_estimado_hex": "Share Ultra",
        "oferta_consumida_mercado_estimada": "Consumo Conc. (est.)",
        "oferta_consumida_ultra_real": "Consumo Ultra (real)",
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
    tbl = _format_residual_display_columns(tbl)

    height_tbl = min(620, 38 + 35 * min(len(tbl), 100))
    st.dataframe(tbl.head(TABLE_ROW_LIMIT), width="stretch", hide_index=True, height=height_tbl)

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


def render_expansao_dominio(
    plano: pd.DataFrame,
    *,
    selected_ufs: list[str] | None = None,
    selected_cities: list[str] | None = None,
    competitors_df: pd.DataFrame | None = None,
    ultra_df: pd.DataFrame | None = None,
) -> None:
    if plano.empty:
        st.warning(
            "Plano de Expansao de Dominio nao disponivel. Execute "
            "`python jobs/pipelines/gerar_plano_expansao_dominio.py` para gerar o arquivo."
        )
        return

    st.markdown("#### Expansao de Dominio — Plano sequencial de ocupacao territorial")
    st.caption(
        "Camada paralela ao M1: transforma o ranking de hexes em sequencia de aberturas coordenadas "
        "por cidade, priorizando residual fitness, cobertura espacial e protecao contra canibalizacao. "
        "Nao substitui o M1, a carteira acionavel nem o plano de curto prazo."
    )

    ufs_disp = sorted(plano["uf"].dropna().unique().tolist())
    muns_disp = sorted(plano["nome_municipio"].dropna().unique().tolist())
    teses_disp = sorted(plano["tese_dominio"].dropna().unique().tolist()) if "tese_dominio" in plano.columns else []

    df1, df2, df3 = st.columns([2, 3, 2])
    with df1:
        default_ufs = [u for u in (selected_ufs or []) if u in ufs_disp] or ufs_disp
        ufs_sel = st.multiselect("UF", options=ufs_disp, default=default_ufs, key="dominio_uf")
    with df2:
        muns_opcoes = sorted(
            plano[plano["uf"].isin(ufs_sel)]["nome_municipio"].dropna().unique().tolist()
            if ufs_sel else muns_disp
        )
        default_muns = [m for m in (selected_cities or []) if m in muns_opcoes]
        muns_sel = st.multiselect("Municipio", options=muns_opcoes, default=default_muns, key="dominio_mun")
    with df3:
        teses_sel = st.multiselect("Tese de dominio", options=teses_disp, default=teses_disp, key="dominio_tese")

    view = plano.copy()
    if ufs_sel:
        view = view[view["uf"].isin(ufs_sel)]
    if muns_sel:
        view = view[view["nome_municipio"].isin(muns_sel)]
    if teses_sel and "tese_dominio" in view.columns:
        view = view[view["tese_dominio"].isin(teses_sel)]

    st.markdown("---")
    kpi_cols = st.columns(4)
    n_ancoras = len(view)
    n_cidades = view["nome_municipio"].nunique() if not view.empty else 0
    n_ufs = view["uf"].nunique() if not view.empty else 0
    residual_cap = (
        pd.to_numeric(view["residual_incremental_capturado"], errors="coerce").fillna(0.0).sum()
        if "residual_incremental_capturado" in view.columns else 0.0
    )
    kpi_cols[0].metric("Ancoras recomendadas", format_int(n_ancoras))
    kpi_cols[1].metric("Cidades cobertas", format_int(n_cidades))
    kpi_cols[2].metric("UFs representadas", format_int(n_ufs))
    kpi_cols[3].metric("Residual capturado estimado", format_int(residual_cap))

    if view.empty:
        st.info("Nenhuma ancora no recorte selecionado.")
        return

    st.markdown("##### Mapa de dominio — ancoras e clusters recomendados")
    st.caption(
        "Ancoras coloridas por ordem de abertura (cyan = primeira, azul = posterior). "
        "Borda indica a tese estrategica. Pins Ultra e concorrentes como camada de contexto."
    )
    render_dominio_tese_legend()
    dominio_map, n_ancoras_mapa = build_dominio_map_figure(
        view,
        selected_ufs=ufs_sel or None,
        selected_cities=muns_sel or None,
        competitors_df=competitors_df,
        ultra_df=ultra_df,
    )
    if dominio_map is None:
        st.info("Sem ancoras com coordenadas validas no recorte atual.")
    else:
        st.caption(f"{format_int(n_ancoras_mapa)} ancoras exibidas no mapa.")
        st.pydeck_chart(dominio_map, width="stretch", height=560)

    st.markdown("---")
    st.markdown("##### Tabela operacional — sequencia de aberturas")
    st.caption(
        "Ordenada por `rank_dominio_brasil`. "
        "Cada linha e um hex ancora recomendado com ordem de abertura na cidade, tese estrategica e residual capturado estimado."
    )

    display_cols = {
        "rank_dominio_brasil": "Rank Brasil",
        "rank_dominio_uf": "Rank UF",
        "uf": "UF",
        "nome_municipio": "Cidade",
        "cluster_id": "Cluster",
        "hex_id": "Hex Ancora",
        "ordem_expansao_cidade": "Ordem na Cidade",
        "score_oportunidade_residual": "Score Residual",
        "residual_incremental_capturado": "Residual Capturado",
        "oferta_efetiva_disponivel": "Oferta Disponivel",
        "oferta_consumida_mercado_estimada": "Consumo Conc. (est.)",
        "oferta_consumida_ultra_real": "Consumo Ultra (real)",
        "dist_ultra_mais_proxima_m": "Dist. Ultra (m)",
        "n_concorrentes_mapeados_2km": "Concorrentes 2km",
        "tese_dominio": "Tese",
        "rank_dominio_cidade": "Rank Cidade",
    }

    if "rank_dominio_brasil" in view.columns:
        view = view.sort_values("rank_dominio_brasil")

    tbl = view[[c for c in display_cols if c in view.columns]].rename(
        columns={k: v for k, v in display_cols.items() if k in view.columns}
    )

    for col in ["Score Residual"]:
        if col in tbl.columns:
            tbl[col] = tbl[col].map(lambda v: f"{v:.1f}" if pd.notna(v) else "-")
    for col in ["Residual Capturado", "Oferta Disponivel", "Consumo Conc. (est.)", "Consumo Ultra (real)"]:
        if col in tbl.columns:
            tbl[col] = tbl[col].map(lambda v: format_int(v) if pd.notna(v) else "-")
    for col in ["Dist. Ultra (m)"]:
        if col in tbl.columns:
            tbl[col] = tbl[col].map(lambda v: f"{int(v):,}".replace(",", ".") if pd.notna(v) else "-")
    for col in ["Rank Brasil", "Rank UF", "Rank Cidade", "Ordem na Cidade", "Concorrentes 2km"]:
        if col in tbl.columns:
            tbl[col] = tbl[col].map(lambda v: int(v) if pd.notna(v) else "-")

    height_tbl = min(700, 38 + 35 * min(len(tbl), 100))
    st.dataframe(tbl.head(TABLE_ROW_LIMIT), width="stretch", hide_index=True, height=height_tbl)

    st.markdown("---")
    note_cols = st.columns(2)
    with note_cols[0]:
        st.markdown(
            """
            <div class="section-card">
                <h4>Como ler o plano de dominio</h4>
                <p><strong>Ordem na Cidade</strong>: sequencia de abertura greedy por residual capturado.</p>
                <p><strong>Residual Capturado</strong>: potencial incremental estimado para o hex ancora considerando decaimento espacial de 2 km.</p>
                <p><strong>Dist. Ultra (m)</strong>: distancia da unidade Ultra mais proxima — piso de 1 km por guardrail.</p>
                <p><strong>Tese</strong>: classificacao estrategica do hex ancora.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with note_cols[1]:
        st.markdown(
            """
            <div class="section-card">
                <h4>Teses de dominio</h4>
                <p><strong>dominar_white_space</strong>: area sem oferta — captura rapida e baixo risco.</p>
                <p><strong>abrir_com_disputa</strong>: concorrente presente — precisa de vantagem diferencial.</p>
                <p><strong>proteger_corredor_ultra</strong>: entre 1-2 km de Ultra existente — fortalece marca.</p>
                <p><strong>adensar_cluster</strong>: segunda ancora ou mais no cluster — maior cobertura local.</p>
                <p><strong>monitorar</strong>: oportunidade presente mas sem sinal forte o suficiente ainda.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_plano_expansao(plano: pd.DataFrame, *, pop_cut_lookup: pd.DataFrame | None = None) -> None:
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

    residual_disponivel = _has_residual_metrics(plano)
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

    if pop_cut_lookup is not None and not pop_cut_lookup.empty and "hex_id" in view.columns:
        lookup_cols = [c for c in ["hex_id", "populacao_corte_hex", "fonte_populacao_corte", "flag_pop_min_5k"] if c in pop_cut_lookup.columns]
        view = view.merge(pop_cut_lookup[lookup_cols], on="hex_id", how="left")
        view["flag_pop_min_5k"] = view["flag_pop_min_5k"].fillna(False).astype(bool)
        n_descartados = int((~view["flag_pop_min_5k"]).sum())
        if n_descartados > 0:
            st.warning(
                f"{format_int(n_descartados)} oportunidades removidas pela regua de {format_int(POP_MIN_ACIONAVEL)} habitantes "
                f"(populacao_corte_hex < {format_int(POP_MIN_ACIONAVEL)} ou ausente). "
                "Essas oportunidades continuam no M1 oficial — apenas excluidas do plano acionavel."
            )
        view = view[view["flag_pop_min_5k"]]

    st.markdown("---")
    metric_cols = st.columns(6 if residual_disponivel else 5)
    metric_cols[0].metric("Oportunidades", format_int(len(view)))
    metric_cols[1].metric("Municipios", format_int(view["cod_municipio"].nunique() if "cod_municipio" in view.columns else view["nome_municipio"].nunique()))
    metric_cols[2].metric("Estrategico", format_int(int((view["nivel_prioridade_final"] == "Estrategico").sum())))
    metric_cols[3].metric("Alta", format_int(int((view["nivel_prioridade_final"] == "Alta").sum())))
    metric_cols[4].metric("Tatica", format_int(int((view["nivel_prioridade_final"] == "Tatica").sum())))
    if residual_disponivel:
        residual_total = pd.to_numeric(view.get("oferta_efetiva_disponivel"), errors="coerce").fillna(0.0).sum()
        metric_cols[5].metric("Oferta residual", format_int(residual_total))

    if view.empty:
        st.info("Nenhuma oportunidade no recorte selecionado.")
        return

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
        "oferta_efetiva_disponivel": "Oferta Residual",
        "score_oportunidade_residual": "Score Residual",
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
    top_uf_disp = _format_residual_display_columns(top_uf_disp)
    st.dataframe(top_uf_disp, width="stretch", hide_index=True, height=min(280, 38 + 35 * len(top_uf_disp)))

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
        "sam_fitness_potencial": "SAM Fitness",
        "oferta_efetiva_disponivel": "Oferta Residual",
        "score_oportunidade_residual": "Score Residual",
        "quartil_oportunidade_residual": "Quartil Residual",
        "share_ultra_estimado_hex": "Share Ultra",
        "oferta_consumida_mercado_estimada": "Consumo Conc. (est.)",
        "oferta_consumida_ultra_real": "Consumo Ultra (real)",
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
    tbl = _format_residual_display_columns(tbl)

    height_tbl = min(700, 38 + 35 * min(len(tbl), 100))
    st.dataframe(tbl, width="stretch", hide_index=True, height=height_tbl)

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


def _render_unified_legend(
    color_mode: str,
    enabled_overlays: list[str],
    *,
    competitors_df: "pd.DataFrame | None" = None,
    ultra_df: "pd.DataFrame | None" = None,
) -> None:
    if color_mode == "m1":
        render_score_bands_legend("Score M1 (score_priorizacao)")
        render_geographic_source_legend()
        render_pop_cut_legend()
    elif color_mode == "hibrido":
        render_score_bands_legend("Score Hibrido (score_expansao_hibrido)")
        render_pop_cut_legend()
    elif color_mode == "censitario":
        render_score_bands_legend("Score Censitario (score_setor_2022_calibrado)")
        render_pop_cut_legend()
    elif color_mode == "residual":
        render_score_bands_legend("Score Residual (score_oportunidade_residual)")
        render_pop_cut_legend()
    elif color_mode == "dominio":
        render_dominio_tese_legend()
    if "concorrentes" in enabled_overlays:
        render_competitor_legend(competitors_df)
    if "ultra" in enabled_overlays:
        render_ultra_legend(ultra_df)


def render_carteira_e_plano(
    carteira: pd.DataFrame,
    plano: pd.DataFrame,
    *,
    selected_ufs: list[str],
    selected_cities: list[str],
    pop_cut_lookup: "pd.DataFrame | None" = None,
) -> None:
    """Carteira de Expansao e Plano Curto Prazo em tabs internas."""
    inner = st.tabs(["Carteira de Expansao", "Plano Curto Prazo"])
    with inner[0]:
        render_carteira_expansao(
            carteira,
            selected_ufs=selected_ufs,
            selected_cities=selected_cities,
            pop_cut_lookup=pop_cut_lookup,
        )
    with inner[1]:
        render_plano_expansao(plano, pop_cut_lookup=pop_cut_lookup)


def _render_analise_pontual_multihex(
    search_pin: "tuple[float, float] | None",
    df: "pd.DataFrame",
    multihex_ids: "list[str]",
    *,
    competitors_df: "pd.DataFrame | None" = None,
    ultra_df: "pd.DataFrame | None" = None,
    raio_km: float = 1.6,
) -> None:
    """Renders aggregated multi-hex analysis inside Analise Pontual de Entorno.

    Shows KPIs for the full selected set, map with highlighted hexes, and secondary table.
    search_pin, when present, adds radius reference circle and competitor/Ultra pins.
    Does not alter score_priorizacao or any official M1 artifact.
    """
    agg = agregar_cenario_multihex(df, multihex_ids)
    n = agg["qtd_hexes"]

    if n == 0:
        st.info("Nenhum dos hex_ids do cenario foi encontrado no dataset atual.")
        st.caption(
            "Adicione hexes validos pelo campo de busca ou pelo botao '+ Incluir hex ativo' acima."
        )
        return

    lat_ref: "float | None" = search_pin[0] if search_pin else None
    lng_ref: "float | None" = search_pin[1] if search_pin else None

    st.markdown(f"**Cenario multi-hex — {n} hex(es) selecionado(s)**")
    if search_pin is not None:
        area_km2 = round(3.14159265358979 * raio_km ** 2, 2)
        st.caption(
            f"Referencia ativa: `{lat_ref:.5f}, {lng_ref:.5f}` | Raio: {raio_km} km (~{area_km2} km²). "
            "KPIs abaixo sao dos hexes selecionados no cenario, nao apenas do raio."
        )
    else:
        st.caption(
            "Sem ponto ativo. KPIs do conjunto de hexes selecionados. "
            "Clique em um hex ou informe coordenada na sidebar para ativar referencia de raio."
        )
    st.caption(
        "Leitura por centroide H3 res-7: precisao aproximada ~0.5-1 km. "
        "Nao altera score_priorizacao, carteira, plano ou artefatos do M1."
    )

    def _fi(v: "float | None") -> str:
        return format_int(int(v)) if v is not None else "-"

    def _fs(v: "float | None") -> str:
        return f"{v:.1f}" if v is not None else "-"

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Hexes selecionados", str(n))
    k2.metric("Habitantes", _fi(agg["pop_total"]))
    k3.metric("Renda per capita med.", f"R$ {_fi(agg['renda_per_capita_media'])}" if agg["renda_per_capita_media"] is not None else "-")
    k4.metric("Residual fitness", _fi(agg["residual_total"]))

    k5, k6, k7, k8, k9 = st.columns(5)
    k5.metric("Consumo concorrentes", _fi(agg["consumo_concorrentes_total"]))
    k6.metric("Consumo Ultra", _fi(agg["consumo_ultra_total"]))
    k7.metric("Consumo total instalado", _fi(agg["consumo_total_instalado"]))
    k8.metric("Presenca Ultra", "Sim" if agg["presenca_ultra"] else "Nao")
    k9.metric("Concorrentes (hexes)", _fi(agg["n_concorrentes_total"]))

    k9, k10, k11 = st.columns(3)
    k9.metric("Score M1 med.", _fs(agg["score_m1_medio"]), delta=f"max {_fs(agg['score_m1_max'])}", delta_color="off")
    k10.metric("Score Residual med.", _fs(agg["score_residual_medio"]), delta=f"max {_fs(agg['score_residual_max'])}", delta_color="off")
    k11.metric("Score Dominio Hibrido med.", _fs(agg["score_dominio_hibrido_medio"]), delta=f"max {_fs(agg['score_dominio_hibrido_max'])}", delta_color="off")

    multihex_map = build_multihex_analysis_map(
        multihex_ids,
        lat=lat_ref,
        lng=lng_ref,
        raio_km=raio_km,
        competitors_df=competitors_df,
        ultra_df=ultra_df,
    )
    if multihex_map is not None:
        st.pydeck_chart(multihex_map, width="stretch", height=420)

    if search_pin is not None:
        competitors_raio = filter_points_to_radius(
            competitors_df, lat_ref, lng_ref, raio_km,
            required_columns={"rede", "nome_unidade"},
        )
        ultra_raio = filter_points_to_radius(
            ultra_df, lat_ref, lng_ref, raio_km,
            required_columns={"nome_unidade"},
        )
        if not competitors_raio.empty:
            render_competitor_legend(competitors_raio)
        if not ultra_raio.empty:
            render_ultra_legend(ultra_raio)

    if agg["hex_ids_ausentes"]:
        st.caption(f"hex_ids nao encontrados no recorte atual: {', '.join(agg['hex_ids_ausentes'])}")

    selecionados = agg["hexes_selecionados"]
    if not selecionados.empty:
        st.markdown("##### Hexes selecionados")
        display_cols = {
            "hex_id": "Hex ID",
            "nome_municipio": "Municipio",
            "uf": "UF",
            "score_priorizacao": "Score M1",
            "score_setor_2022_calibrado": "Score Censo",
            "score_oportunidade_residual": "Score Residual",
            "score_expansao_hibrido": "Score Hibrido",
            "populacao_proxy": "Pop. proxy",
            "pop_total_setor_2022": "Pop. setor",
            "renda_per_capita": "Renda per capita",
            "oferta_efetiva_disponivel": "Residual (alunos)",
            "oferta_consumida_mercado_estimada": "Consumo Conc. (est.)",
            "oferta_consumida_ultra_real": "Consumo Ultra (real)",
        }
        cols = [c for c in display_cols if c in selecionados.columns]
        tbl = selecionados[cols].rename(columns={k: v for k, v in display_cols.items() if k in cols}).copy()
        for col in ["Score M1", "Score Censo", "Score Residual", "Score Hibrido"]:
            if col in tbl.columns:
                tbl[col] = tbl[col].map(lambda v: f"{v:.1f}" if pd.notna(v) else "-")
        for col in ["Pop. proxy", "Pop. setor", "Residual (alunos)", "Consumo Conc. (est.)", "Consumo Ultra (real)"]:
            if col in tbl.columns:
                tbl[col] = tbl[col].map(lambda v: format_int(int(v)) if pd.notna(v) else "-")
        if "Renda per capita" in tbl.columns:
            tbl["Renda per capita"] = tbl["Renda per capita"].map(
                lambda v: f"R$ {format_int(int(v))}" if pd.notna(v) else "-"
            )
        st.dataframe(
            tbl,
            column_config={"Hex ID": st.column_config.TextColumn("Hex ID", width="large")},
            width="stretch",
            hide_index=True,
            height=min(420, 38 + 35 * len(tbl)),
        )


def render_analise_pontual(
    search_pin: tuple[float, float] | None,
    df: pd.DataFrame,
    competitors_df: pd.DataFrame | None = None,
    ultra_df: pd.DataFrame | None = None,
    dominio_df: pd.DataFrame | None = None,
    raio_km: float = 1.6,
    multihex_ids: list[str] | None = None,
) -> None:
    """Renders the Analise Pontual de Entorno section.

    When multihex_ids is non-empty, shows aggregated KPIs and map for all selected hexes.
    search_pin, when present, adds radius circle and competitor/Ultra pins as reference.
    Falls back to single-point mode when no multi-hex is active.
    Does not alter score_priorizacao, carteira, plano or any official M1 artifact.
    """
    _multihex = list(multihex_ids) if multihex_ids else []

    if _multihex:
        _render_analise_pontual_multihex(
            search_pin,
            df,
            _multihex,
            competitors_df=competitors_df,
            ultra_df=ultra_df,
            raio_km=raio_km,
        )
        return

    if search_pin is None:
        st.info(
            "Clique em um hexagono no mapa ou digite uma coordenada na barra lateral "
            "(ex: -23.55, -46.63) para ativar a Analise Pontual de Entorno."
        )
        st.caption(
            "Clique em objeto de mapa: suportado via `st.pydeck_chart` com `on_select` (Streamlit 1.26+). "
            "Botao direito: nao suportado pelo componente `st.pydeck_chart`. "
            "Fallback: campo de coordenada na barra lateral."
        )
        return

    lat, lng = search_pin
    area_km2 = round(3.14159265358979 * raio_km ** 2, 2)

    resultado = analisar_entorno_ponto(
        lat,
        lng,
        hex_df=df,
        raio_km=raio_km,
        competitors_df=competitors_df,
        ultra_df=ultra_df,
        dominio_df=dominio_df,
    )

    st.caption(
        f"Ponto: `{lat:.5f}, {lng:.5f}` | Raio: {raio_km} km | Area aproximada: {area_km2} km²"
    )
    st.caption(
        "Leitura por centroide de hexagono H3 res-7: precisao aproximada ~0.5-1 km. "
        "Nao altera score_priorizacao, carteira, plano ou artefatos do M1."
    )

    coord_gmaps = f"{lat:.6f},{lng:.6f}"
    st.markdown(f"**Coordenada para Google Maps / GPS:** `{coord_gmaps}`")

    _hex_lookup = lookup_hex_by_coord(lat, lng, df)
    if _hex_lookup is not None:
        _hex_id_found = str(_hex_lookup["hex_id"])
        _id_col, _btn_col = st.columns([5, 3])
        with _id_col:
            st.caption("Hex ID do ponto selecionado:")
            st.code(_hex_id_found, language=None)
        with _btn_col:
            if "multihex_cenario" not in st.session_state:
                st.session_state["multihex_cenario"] = []
            _cenario_atual = list(st.session_state["multihex_cenario"])
            if _hex_id_found not in _cenario_atual:
                if st.button("+ Adicionar ao cenario", key="btn_analise_pontual_add_hex"):
                    st.session_state["multihex_cenario"] = _cenario_atual + [_hex_id_found]
            else:
                if st.button("- Remover do cenario", key="btn_analise_pontual_remove_hex"):
                    st.session_state["multihex_cenario"] = [h for h in _cenario_atual if h != _hex_id_found]

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Hexes no raio", resultado["n_hexes"])
    pop_total = resultado["pop_total_raio"]
    k2.metric("Populacao no raio", format_int(int(pop_total)) if pop_total is not None else "-")
    renda_media = resultado["renda_per_capita_media_raio"]
    k3.metric("Renda per capita med.", f"R$ {format_int(int(renda_media))}" if renda_media is not None else "-")
    res_total = resultado["residual_total"]
    k4.metric("Residual total", format_int(int(res_total)) if res_total is not None else "-")

    st.caption(
        "Populacao: "
        f"{resultado['fonte_pop_total_raio']} ({resultado['n_hexes_com_pop']} hexes com dado). "
        "Renda: "
        f"{resultado['metodo_renda_raio']} ({resultado['n_hexes_com_renda']} hexes com dado)."
    )

    k5, k6, k7, k8 = st.columns(4)
    score_res = resultado["score_residual_medio"]
    k5.metric("Score residual med.", f"{score_res:.1f}" if score_res is not None else "-")
    score_m1 = resultado["score_m1_medio"]
    k6.metric("Score M1 med.", f"{score_m1:.1f}" if score_m1 is not None else "-")
    k7.metric("Concorrentes no raio", resultado["n_concorrentes"])
    k8.metric("Ultra no raio", resultado["n_ultra"])

    _fmt_int_none = lambda v: format_int(int(v)) if v is not None else "-"
    consumo_conc = resultado.get("consumo_concorrentes_raio")
    consumo_ultra_val = resultado.get("consumo_ultra_raio")
    if consumo_conc is not None or consumo_ultra_val is not None:
        ka, kb, kc = st.columns(3)
        ka.metric("Consumo concorrentes", _fmt_int_none(consumo_conc))
        kb.metric("Consumo Ultra", _fmt_int_none(consumo_ultra_val))
        consumo_tot = (consumo_conc or 0.0) + (consumo_ultra_val or 0.0)
        kc.metric("Consumo total instalado", format_int(int(consumo_tot)))
        st.caption("Consumo fitness instalado: leitura de mercado (alunos estimados ocupando capacidade), nao score oficial.")

    hexes_entorno = resultado["hexes_entorno"]
    pontual_map = build_analise_pontual_map(
        lat,
        lng,
        raio_km,
        hexes_entorno,
        competitors_df=competitors_df,
        ultra_df=ultra_df,
    )
    if pontual_map is not None:
        st.pydeck_chart(pontual_map, width="stretch", height=420)

    competitors_raio = filter_points_to_radius(
        competitors_df,
        lat,
        lng,
        raio_km,
        required_columns={"rede", "nome_unidade"},
    )
    ultra_raio = filter_points_to_radius(
        ultra_df,
        lat,
        lng,
        raio_km,
        required_columns={"nome_unidade"},
    )
    if competitors_raio.empty and ultra_raio.empty:
        st.caption("Sem concorrentes ou unidades Ultra mapeadas dentro do raio analisado.")
    else:
        if not competitors_raio.empty:
            render_competitor_legend(competitors_raio)
        if not ultra_raio.empty:
            render_ultra_legend(ultra_raio)

    if not hexes_entorno.empty:
        st.markdown("##### Hexes no entorno")
        display_cols = {
            "hex_id": "Hex ID",
            "dist_km": "Dist. (km)",
            "uf": "UF",
            "nome_municipio": "Cidade",
            "score_priorizacao": "Score M1",
            "score_expansao_hibrido": "Score Hibrido",
            "score_oportunidade_residual": "Score Residual",
            "oferta_efetiva_disponivel": "Residual (alunos)",
            "oferta_consumida_mercado_estimada": "Consumo Conc. (est.)",
            "oferta_consumida_ultra_real": "Consumo Ultra (real)",
            "pop_total_raio_hex": "Pop. usada",
            "fonte_pop_total_raio_hex": "Fonte pop.",
            "renda_per_capita_raio_hex": "Renda usada",
            "fonte_renda_per_capita_raio_hex": "Fonte renda",
        }
        tbl = hexes_entorno[[c for c in display_cols if c in hexes_entorno.columns]].rename(
            columns={k: v for k, v in display_cols.items() if k in hexes_entorno.columns}
        ).copy()
        for col in ["Score M1", "Score Hibrido", "Score Residual"]:
            if col in tbl.columns:
                tbl[col] = tbl[col].map(lambda v: f"{v:.1f}" if pd.notna(v) else "-")
        if "Dist. (km)" in tbl.columns:
            tbl["Dist. (km)"] = tbl["Dist. (km)"].map(lambda v: f"{v:.2f}" if pd.notna(v) else "-")
        for col in ["Residual (alunos)", "Consumo Conc. (est.)", "Consumo Ultra (real)"]:
            if col in tbl.columns:
                tbl[col] = tbl[col].map(lambda v: format_int(int(v)) if pd.notna(v) else "-")
        if "Pop. usada" in tbl.columns:
            tbl["Pop. usada"] = tbl["Pop. usada"].map(
                lambda v: format_int(int(v)) if pd.notna(v) else "-"
            )
        if "Renda usada" in tbl.columns:
            tbl["Renda usada"] = tbl["Renda usada"].map(
                lambda v: f"R$ {format_int(int(v))}" if pd.notna(v) else "-"
            )
        st.dataframe(tbl, width="stretch", hide_index=True, height=min(420, 38 + 35 * len(tbl)))
    else:
        st.info(
            f"Nenhum hexagono encontrado no raio de {raio_km} km a partir de "
            f"({lat:.5f}, {lng:.5f}). Tente uma coordenada dentro de uma area urbana mapeada."
        )


def _render_multihex_controls(
    active_hex_id: "str | None",
    multihex_ids: "list[str]",
) -> None:
    """Renderiza controles do cenario multi-hex: incluir, remover, limpar e colar lista."""
    st.markdown("##### Cenario Multi-Hex")

    if active_hex_id is not None:
        st.caption("Hex ativo:")
        st.code(active_hex_id, language=None)

    btn_col, clear_col, count_col = st.columns([2, 2, 4])
    with btn_col:
        if active_hex_id is not None:
            if active_hex_id not in multihex_ids:
                if st.button("+ Incluir no cenario", key="btn_multihex_add"):
                    st.session_state["multihex_cenario"] = multihex_ids + [active_hex_id]
            else:
                if st.button("- Remover do cenario", key="btn_multihex_remove"):
                    st.session_state["multihex_cenario"] = [h for h in multihex_ids if h != active_hex_id]
        else:
            st.caption("Selecione um hex no mapa ou via busca para incluir no cenario.")
    with clear_col:
        if multihex_ids:
            if st.button("Limpar cenario", key="btn_multihex_clear"):
                st.session_state["multihex_cenario"] = []
    with count_col:
        st.caption(f"{len(multihex_ids)} hex(es) no cenario")

    with st.expander("Adicionar hexes por ID (colar lista)", expanded=False):
        paste_raw = st.text_area(
            "hex_ids (um por linha, ou separados por virgula, ponto e virgula ou espaco):",
            value="",
            key="multihex_paste_input",
            placeholder="87ad...abc\n87be...xyz",
            height=80,
        )
        if st.button("Adicionar lista", key="btn_multihex_paste_add") and paste_raw.strip():
            parsed = parse_hex_ids_from_text(paste_raw)
            existing_set = set(st.session_state.get("multihex_cenario", []))
            new_ids = [h for h in parsed if h not in existing_set]
            dupes = len(parsed) - len(new_ids)
            st.session_state["multihex_cenario"] = list(existing_set) + new_ids
            if new_ids:
                msg = f"{len(new_ids)} hex(es) adicionado(s)."
                if dupes:
                    msg += f" {dupes} duplicado(s) ignorado(s)."
            elif dupes:
                msg = f"Nenhum hex novo. {dupes} duplicado(s) ignorado(s)."
            else:
                msg = "Nenhum hex_id valido encontrado."
            st.caption(msg)

    current = list(st.session_state.get("multihex_cenario", []))
    if current:
        with st.expander(f"Hexes no cenario ({len(current)})", expanded=len(current) <= 10):
            for hid in list(current):
                col_hex, col_btn = st.columns([8, 1])
                with col_hex:
                    st.code(hid, language=None)
                with col_btn:
                    if st.button("x", key=f"multihex_rem_{hid}"):
                        st.session_state["multihex_cenario"] = [h for h in st.session_state["multihex_cenario"] if h != hid]


def _render_multihex_kpis(df: "pd.DataFrame", multihex_ids: "list[str]") -> None:
    """Exibe KPIs agregados e tabela dos hexes do cenario multi-hex."""
    from dashboard.utils import format_int, format_score

    agg = agregar_cenario_multihex(df, multihex_ids)
    n = agg["qtd_hexes"]
    if n == 0:
        st.info("Nenhum dos hex_ids do cenario foi encontrado no dataset atual.")
        return

    st.markdown(f"**Potencial agregado — {n} hex(es) selecionado(s)**")

    def _fmt_int(v: "float | None") -> str:
        return format_int(int(v)) if v is not None else "-"

    def _fmt_score(v: "float | None") -> str:
        return f"{v:.1f}" if v is not None else "-"

    def _fmt_brl(v: "float | None") -> str:
        return f"R$ {format_int(int(v))}" if v is not None else "-"

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Habitantes", _fmt_int(agg["pop_total"]))
    with c2:
        st.metric("Renda per capita media", _fmt_brl(agg["renda_per_capita_media"]))
    with c3:
        st.metric("Residual fitness (alunos)", _fmt_int(agg["residual_total"]))

    c4, c5, c6 = st.columns(3)
    with c4:
        st.metric("Consumo concorrentes", _fmt_int(agg["consumo_concorrentes_total"]))
    with c5:
        st.metric("Consumo Ultra", _fmt_int(agg["consumo_ultra_total"]))
    with c6:
        st.metric("Consumo total instalado", _fmt_int(agg["consumo_total_instalado"]))

    c7, c8, c9 = st.columns(3)
    with c7:
        lbl = "Score M1 medio"
        val = _fmt_score(agg["score_m1_medio"])
        mx = _fmt_score(agg["score_m1_max"])
        st.metric(lbl, val, delta=f"max {mx}", delta_color="off")
    with c8:
        lbl = "Score Censo medio"
        val = _fmt_score(agg["score_censo_medio"])
        mx = _fmt_score(agg["score_censo_max"])
        st.metric(lbl, val, delta=f"max {mx}", delta_color="off")
    with c9:
        lbl = "Score Dominio Hibrido medio"
        val = _fmt_score(agg["score_dominio_hibrido_medio"])
        mx = _fmt_score(agg["score_dominio_hibrido_max"])
        st.metric(lbl, val, delta=f"max {mx}", delta_color="off")

    if agg["hex_ids_ausentes"]:
        st.caption(f"hex_ids nao encontrados no recorte atual: {', '.join(agg['hex_ids_ausentes'])}")

    # Tabela dos hexes selecionados
    selecionados = agg["hexes_selecionados"]
    if not selecionados.empty:
        display_cols = {
            "hex_id": "Hex ID",
            "nome_municipio": "Municipio",
            "uf": "UF",
            "score_priorizacao": "Score M1",
            "score_setor_2022_calibrado": "Score Censo",
            "score_oportunidade_residual": "Score Residual",
            "score_expansao_hibrido": "Score Hibrido",
            "populacao_proxy": "Pop. proxy",
            "pop_total_setor_2022": "Pop. setor",
            "renda_per_capita": "Renda per capita",
            "oferta_efetiva_disponivel": "Residual (alunos)",
        }
        cols = [c for c in display_cols if c in selecionados.columns]
        tbl = selecionados[cols].rename(columns={k: v for k, v in display_cols.items() if k in cols}).copy()
        for col in ["Score M1", "Score Censo", "Score Residual", "Score Hibrido"]:
            if col in tbl.columns:
                tbl[col] = tbl[col].map(lambda v: f"{v:.1f}" if pd.notna(v) else "-")
        for col in ["Pop. proxy", "Pop. setor", "Residual (alunos)"]:
            if col in tbl.columns:
                tbl[col] = tbl[col].map(lambda v: format_int(int(v)) if pd.notna(v) else "-")
        if "Renda per capita" in tbl.columns:
            tbl["Renda per capita"] = tbl["Renda per capita"].map(
                lambda v: f"R$ {format_int(int(v))}" if pd.notna(v) else "-"
            )
        st.dataframe(
            tbl,
            column_config={"Hex ID": st.column_config.TextColumn("Hex ID", width="large")},
            width="stretch",
            hide_index=True,
            height=min(420, 38 + 35 * len(tbl)),
        )


def _extract_click_coord_from_selection(map_event) -> "tuple[float, float] | None":
    """Extract (lat, lng) from a pydeck on_select map event.

    Returns None when the event is absent, the selection is empty, or the
    selected object does not contain both 'lat' and 'lng' fields.  Robust
    against MagicMock objects used in unit tests.
    """
    if map_event is None:
        return None
    try:
        selection = getattr(map_event, "selection", None)
        if selection is None:
            return None
        objects = getattr(selection, "objects", None)
        if not isinstance(objects, dict):
            return None
        for rows in objects.values():
            if not isinstance(rows, list) or not rows:
                continue
            row = rows[0]
            if isinstance(row, dict) and "lat" in row and "lng" in row:
                return (float(row["lat"]), float(row["lng"]))
    except (TypeError, ValueError, AttributeError):
        pass
    return None


def _normalizar_cod_municipio(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none"}:
        return None
    number = pd.to_numeric(text, errors="coerce")
    if pd.notna(number):
        text = str(int(number))
    return text.zfill(7) if text.isdigit() else text


def _resolve_censo_context(
    search_pin: tuple[float, float],
    df: pd.DataFrame,
    censo_geo_dir: Path | None = None,
) -> dict[str, str] | None:
    lat, lng = search_pin
    found = lookup_hex_by_coord(lat, lng, df)
    if found is None or found.get("_not_found"):
        return None

    uf = str(found.get("uf") or "").upper()
    cod_municipio = _normalizar_cod_municipio(found.get("cod_municipio"))
    nome_municipio = str(found.get("nome_municipio") or found.get("cidade") or "").strip()

    if not cod_municipio and "cod_municipio" in df.columns:
        rows = df.loc[df["hex_id"].astype(str) == str(found.get("hex_id"))]
        if not rows.empty:
            cod_municipio = _normalizar_cod_municipio(rows.iloc[0].get("cod_municipio"))

    if not cod_municipio and uf and nome_municipio and censo_geo_dir is not None:
        cod_municipio = resolve_cod_municipio_from_geo_dir(censo_geo_dir, uf, nome_municipio)

    if not uf or not cod_municipio:
        return None
    return {
        "uf": uf,
        "cod_municipio": cod_municipio,
        "nome_municipio": nome_municipio or cod_municipio,
        "hex_id": str(found.get("hex_id", "")),
    }


def _format_brl(value: object) -> str:
    return f"R$ {format_int(int(value))}" if value is not None and pd.notna(value) else "-"


def _render_setores_censitarios_table(setores: pd.DataFrame) -> None:
    if setores is None or setores.empty:
        st.info("Nenhum setor censitario intersectado no raio.")
        return
    display_cols = {
        "cod_setor": "Setor",
        "nome_municipio": "Municipio",
        "area_intersecao_m2": "Area intersecao (m2)",
        "peso_area_setor": "Peso area",
        "pop_estimada_intersecao": "Pop. estimada",
        "renda_per_capita_setor_2022_calibrada": "Renda per capita",
        "score_setor_2022_calibrado": "Score censo",
        "qualidade_join_uf": "Qualidade",
    }
    table = setores[[c for c in display_cols if c in setores.columns]].rename(
        columns={k: v for k, v in display_cols.items() if k in setores.columns}
    ).copy()
    for col in ["Area intersecao (m2)", "Pop. estimada"]:
        if col in table.columns:
            table[col] = table[col].map(lambda v: format_int(int(v)) if pd.notna(v) else "-")
    if "Peso area" in table.columns:
        table["Peso area"] = table["Peso area"].map(lambda v: f"{float(v):.3f}" if pd.notna(v) else "-")
    if "Renda per capita" in table.columns:
        table["Renda per capita"] = table["Renda per capita"].map(_format_brl)
    if "Score censo" in table.columns:
        table["Score censo"] = table["Score censo"].map(lambda v: f"{float(v):.1f}" if pd.notna(v) else "-")

    st.dataframe(
        table.head(80),
        width="stretch",
        hide_index=True,
        height=min(420, 38 + 35 * min(len(table), 80)),
    )


def render_relatorio_pontual_censitario(
    search_pin: tuple[float, float] | None,
    df: pd.DataFrame,
    *,
    censo_geo_loader: Callable[[str, str | None], pd.DataFrame] | None = None,
    censo_geo_dir: Path | None = None,
    competitors_df: pd.DataFrame | None = None,
    ultra_df: pd.DataFrame | None = None,
    raio_km: float = RAIO_CENSITARIO_DEFAULT_KM,
) -> None:
    """Renderiza o fluxo Streamlit do relatorio pontual censitario 1.5 km."""
    st.caption(
        "Usa setores censitarios reais IBGE 2022 e intersecao geometrica com raio fixo de "
        f"{raio_km:.1f} km. Camada complementar: nao altera M1, carteira ou plano."
    )

    if search_pin is None:
        st.info(
            "Clique em um hexagono no mapa ou informe uma coordenada na sidebar para gerar "
            "o Relatorio Pontual Censitario."
        )
        return

    if censo_geo_loader is None:
        st.warning("Loader da base setorial nao configurado para o relatorio censitario.")
        return

    context = _resolve_censo_context(search_pin, df, censo_geo_dir=censo_geo_dir)
    if context is None:
        st.warning(
            "Nao foi possivel identificar UF e municipio na base M1 para esta coordenada. "
            "Tente uma coordenada urbana dentro do recorte carregado."
        )
        return

    lat, lng = search_pin
    uf = context["uf"]
    cod_municipio = context["cod_municipio"]
    nome_municipio = context["nome_municipio"]

    setores_df = censo_geo_loader(uf, cod_municipio)
    if setores_df is None or setores_df.empty:
        st.warning(
            "Base setorial geografica nao encontrada para "
            f"{nome_municipio}/{uf} (`cod_municipio={cod_municipio}`). "
            "Materialize `data/outputs/setores_censitarios_2022_geo/` para habilitar o relatorio."
        )
        return

    metric_options = {
        "Populacao estimada": "pop_estimada_intersecao",
        "Renda per capita": "renda_per_capita_setor_2022_calibrada",
        "Score censitario": "score_setor_2022_calibrado",
        "Peso de area": "peso_area_setor",
    }
    metric_label = st.selectbox(
        "Metrica do mapa censitario",
        options=list(metric_options),
        index=0,
        key="relatorio_censitario_metric",
    )
    metric_column = metric_options[metric_label]

    result = analisar_ponto_censitario_setores(
        lat,
        lng,
        setores_df,
        raio_km=raio_km,
        competitors_df=competitors_df,
        ultra_df=ultra_df,
    )
    mapa_png = render_mapa_censitario_estatico_png(
        lat,
        lng,
        setores_df,
        raio_km=raio_km,
        metric_column=metric_column,
        competitors_df=competitors_df,
        ultra_df=ultra_df,
    )

    st.markdown(f"**Ponto analisado:** `{lat:.5f}, {lng:.5f}` | `{nome_municipio}/{uf}`")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Setores", format_int(result["n_setores"]))
    k2.metric("Populacao estimada", format_int(int(result["pop_total_raio"])) if result["pop_total_raio"] is not None else "-")
    k3.metric("Renda per capita", _format_brl(result["renda_per_capita_media_raio"]))
    dens = result["densidade_pop_raio_hab_km2"]
    k4.metric("Densidade", f"{format_int(int(dens))} hab/km2" if dens is not None else "-")

    k5, k6, k7, k8 = st.columns(4)
    score = result["score_setor_medio"]
    k5.metric("Score censo medio", f"{score:.1f}" if score is not None else "-")
    score_max = result["score_setor_max"]
    k6.metric("Score censo max", f"{score_max:.1f}" if score_max is not None else "-")
    k7.metric("Concorrentes", format_int(result["n_concorrentes"]))
    k8.metric("Ultra", format_int(result["n_ultra"]))

    st.caption(
        f"Metodo: `{result['metodo']}`. Populacao estimada por peso de area; "
        "renda e scores ponderados por populacao estimada, com fallback por area."
    )
    st.image(mapa_png, caption=f"Mapa censitario offline por {metric_label.lower()}.", width="stretch")

    st.markdown("##### Setores intersectados")
    _render_setores_censitarios_table(result["setores_intersectados"])

    render_downloads_relatorio_censitario(
        st,
        result,
        mapa_png,
        filename_prefix=f"relatorio_censitario_{uf}_{cod_municipio}_{lat:.5f}_{lng:.5f}".replace("-", "m").replace(".", "p"),
    )


@st.fragment
def render_mapa_pydeck_fragment(
    deck: "pdk.Deck",
    n_points: int,
    selected_ufs: "list[str]",
    multihex_ids: "list[str]",
) -> None:
    """Fragmento isolado para renderizacao do pydeck_chart e captura de clique.

    - on_select="rerun" dentro do fragmento dispara rerun so do fragmento (comportamento esperado).
    - Ao detectar clique novo: escreve em session_state["click_coord"] e chama st.rerun()
      (rerun completo da aba) para propagar o novo ponto para os expanders dependentes.
    - Sem clique novo: fragmento reroda a si mesmo sem propagar rerun da aba.
    - Nao contem chamadas a st.sidebar (restricao do Streamlit).
    - Nao recalcula score, carteira, plano nem artefatos oficiais do M1.
    """
    from dashboard.constants import MAP_POINT_LIMIT
    st.caption(build_map_scope_caption(n_points, selected_ufs=selected_ufs, capped=n_points >= MAP_POINT_LIMIT))
    st.caption(
        "Clique em um hexagono no mapa para ativar a Analise Pontual de Entorno (raio 1.6 km). "
        "Botao direito nao e suportado pelo componente de mapa."
    )
    map_event = st.pydeck_chart(
        deck, on_select="rerun", key="main_unified_map", width="stretch", height=600
    )
    _new_click = _extract_click_coord_from_selection(map_event)
    _prev_click: "tuple[float, float] | None" = st.session_state.get("click_coord")
    if _new_click is not None and _new_click != _prev_click:
        st.session_state["click_coord"] = _new_click
        st.rerun()  # rerun completo da aba para propagar click_coord aos expanders
    click_coord: "tuple[float, float] | None" = st.session_state.get("click_coord")
    if click_coord is not None:
        _col_btn, _cap_col = st.columns([1, 4])
        with _col_btn:
            if st.button("Limpar selecao do mapa", key="clear_click_coord"):
                st.session_state.pop("click_coord", None)
                st.rerun()  # rerun completo para limpar estado dos expanders
        if st.session_state.get("click_coord") is not None:
            with _cap_col:
                st.caption(
                    f"Ponto ativo: `{click_coord[0]:.5f}, {click_coord[1]:.5f}` "
                    "(centroide do hex selecionado). "
                    "Para coordenada exata, use lat,lng na barra lateral."
                )


def render_mapa_territorial(
    df: "pd.DataFrame",
    *,
    selected_ufs: list[str],
    selected_cities: list[str],
    competitors_df: "pd.DataFrame | None" = None,
    ultra_df: "pd.DataFrame | None" = None,
    search_pin: "tuple[float, float] | None" = None,
    search_hex_id: "str | None" = None,
    dominio_df: "pd.DataFrame | None" = None,
    city_summary: "pd.DataFrame | None" = None,
    uf_summary: "pd.DataFrame | None" = None,
    selected_faixas: "list[str] | None" = None,
    censo_geo_loader: Callable[[str, str | None], pd.DataFrame] | None = None,
    censo_geo_dir: Path | None = None,
) -> None:
    """Mapa Territorial Unificado: modo de cor selecionavel com overlays opcionais.

    Camada visual: nao altera score_priorizacao, carteira, plano nem artefatos oficiais do M1.
    """
    # Inicializa estado do cenario multi-hex
    if "multihex_cenario" not in st.session_state:
        st.session_state["multihex_cenario"] = []
    multihex_ids: list[str] = list(st.session_state["multihex_cenario"])

    st.markdown("#### Mapa Territorial Unificado")
    st.caption(
        "Selecione o modo de cor e os overlays desejados. "
        "Camadas visuais nao alteram score, ranking, carteira nem artefatos oficiais do M1."
    )

    ctrl_col1, ctrl_col2 = st.columns([1.6, 2.4])

    with ctrl_col1:
        mode_labels = {mode_id: cfg["label"] for mode_id, cfg in COLOR_MODES.items()}
        available_modes = [
            mode_id for mode_id in COLOR_MODES
            if mode_id == "dominio" or color_mode_available(df, mode_id)
        ]
        if not available_modes:
            available_modes = [COLOR_MODE_DEFAULT]
        default_idx = available_modes.index(COLOR_MODE_DEFAULT) if COLOR_MODE_DEFAULT in available_modes else 0
        selected_mode = st.selectbox(
            "Modo de cor",
            options=available_modes,
            format_func=lambda m: mode_labels.get(m, m),
            index=default_idx,
            key="mapa_territorial_color_mode",
        )

    with ctrl_col2:
        overlay_labels = {oid: cfg["label"] for oid, cfg in OVERLAYS.items()}
        default_overlays = [oid for oid, cfg in OVERLAYS.items() if cfg["default"]]
        enabled_overlays = st.multiselect(
            "Overlays",
            options=list(OVERLAYS),
            default=default_overlays,
            format_func=lambda o: overlay_labels.get(o, o),
            key="mapa_territorial_overlays",
        )

    if selected_mode != "dominio" and not color_mode_available(df, selected_mode):
        st.warning(
            f"Modo '{mode_labels.get(selected_mode, selected_mode)}' nao disponivel no recorte atual. "
            "Verifique se os arquivos de dados necessarios estao presentes em `data/outputs/`."
        )
        return

    if selected_mode == "dominio" and (dominio_df is None or dominio_df.empty):
        st.info(
            "Dados de dominio nao disponiveis. "
            "Execute `python jobs/pipelines/gerar_plano_expansao_dominio.py` para habilitar este modo."
        )
        return

    _render_unified_legend(selected_mode, enabled_overlays, competitors_df=competitors_df, ultra_df=ultra_df)

    deck, n_points = build_unified_map_figure(
        df,
        color_mode=selected_mode,
        enabled_overlays=enabled_overlays,
        selected_ufs=selected_ufs,
        selected_cities=selected_cities,
        competitors_df=competitors_df,
        ultra_df=ultra_df,
        search_pin=search_pin,
        search_hex_id=search_hex_id,
        dominio_df=dominio_df,
    )

    if deck is None:
        st.info(
            "Sem dados para o modo selecionado no recorte atual. "
            "Ajuste os filtros globais ou selecione outro modo de cor."
        )
        return

    # Adiciona camada de destaque multi-hex sem alterar cores dos modos existentes
    if multihex_ids:
        deck.layers.append(_build_multihex_selection_layer(multihex_ids))

    render_mapa_pydeck_fragment(deck, n_points, selected_ufs, multihex_ids)

    # Leitura de click_coord apos o fragmento (pode ter sido atualizado)
    click_coord: "tuple[float, float] | None" = st.session_state.get("click_coord")

    # --- Cenario Multi-Hex ---
    # Determina o hex ativo a partir do clique ou da busca por coordenada
    active_hex_id: "str | None" = None
    if click_coord is not None:
        _click_result = lookup_hex_by_coord(*click_coord, df)
        if _click_result is not None and not _click_result.get("_not_found"):
            active_hex_id = str(_click_result["hex_id"])
    elif search_hex_id is not None:
        active_hex_id = str(search_hex_id)

    st.markdown("---")
    _render_multihex_controls(active_hex_id, multihex_ids)

    # Re-le estado apos possiveis mutacoes dos botoes
    multihex_ids = list(st.session_state.get("multihex_cenario", []))

    if city_summary is not None:
        st.markdown("---")
        with st.expander("Analise Territorial", expanded=False):
            render_analise_territorial(df, city_summary)
        with st.expander("Ranking de Priorizacao", expanded=False):
            render_ranking_priorizacao(df)
        if "score_expansao_hibrido" in df.columns and df["score_expansao_hibrido"].notna().any():
            with st.expander("Camada Hibrida — Detalhe", expanded=False):
                render_modelo_hibrido_v2(
                    df,
                    selected_ufs=selected_ufs,
                    selected_cities=selected_cities,
                    selected_faixas=selected_faixas,
                    competitors_df=competitors_df,
                    ultra_df=ultra_df,
                    search_pin=search_pin,
                    search_hex_id=search_hex_id,
                )
        effective_pin = click_coord or search_pin
        with st.expander(
            "Analise Pontual de Entorno",
            expanded=bool(multihex_ids) or effective_pin is not None,
        ):
            render_analise_pontual(
                effective_pin,
                df,
                competitors_df=competitors_df,
                ultra_df=ultra_df,
                dominio_df=dominio_df,
                multihex_ids=multihex_ids,
            )
        with st.expander(
            "Relatorio Pontual Censitario",
            expanded=effective_pin is not None,
        ):
            render_relatorio_pontual_censitario(
                effective_pin,
                df,
                censo_geo_loader=censo_geo_loader,
                censo_geo_dir=censo_geo_dir,
                competitors_df=competitors_df,
                ultra_df=ultra_df,
            )
