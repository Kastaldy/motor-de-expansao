from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.constants import (
    COLORS,
    COVERAGE_BUCKET_ORDER,
    FAIXA_ORDEM,
    HYBRID_ELIGIBILITY_ORDER,
    JOIN_QUALITY_ORDER,
    TABLE_ROW_LIMIT,
)
from dashboard.utils import format_int, format_score
from motor_expansao.dashboard.components import (
    _carteira_prioridade_color,
    _category_options,
    _sort_carteira_by_m1,
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
    render_faixa_legend,
    render_geographic_source_legend,
    style_ranking_table,
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

    view = carteira.copy()
    if ufs_sel:
        view = view[view["uf"].isin(ufs_sel)]
    if muns_sel:
        view = view[view["nome_municipio"].isin(muns_sel)]
    if prioridades_sel:
        view = view[view["prioridade_abertura"].isin(prioridades_sel)]
    view = _sort_carteira_by_m1(view)

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
