from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import pyarrow.parquet as pq
import streamlit as st
from streamlit.runtime.scriptrunner import get_script_run_ctx
from streamlit.web import cli as stcli


st.set_page_config(
    page_title="Ultra Academia | Dashboard Executivo M1",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATASET_PATH = Path(__file__).resolve().parent / "data" / "outputs" / "hexagonos_brasil_dashboard.parquet"
REQUIRED_COLUMNS = [
    "hex_id",
    "lat",
    "lng",
    "uf",
    "cidade",
    "regiao",
    "score_priorizacao",
    "hex_score_estrutural",
    "ajuste_executivo",
    "faixa_oportunidade",
    "flag_viavel",
    "flag_prioridade",
    "rank_brasil",
    "rank_uf",
    "rank_cidade",
    "renda_per_capita",
    "populacao_proxy",
]
FAIXA_ORDEM = [
    "prioridade_maxima",
    "alta",
    "media",
    "baixa",
    "descartado",
]
MAP_POINT_LIMIT = 35000
TABLE_ROW_LIMIT = 1000
BRASIL_CENTER = {"lat": -14.235, "lon": -51.9253}
COLORS = {
    "bg": "#0A0C18",
    "bg_alt": "#12162A",
    "panel": "rgba(17, 24, 39, 0.88)",
    "panel_solid": "#12172A",
    "panel_soft": "#18203A",
    "border": "rgba(120, 137, 210, 0.24)",
    "text": "#F3F7FF",
    "muted": "#A7B3D1",
    "brand": "#3E2A78",
    "brand_alt": "#19B7FF",
    "accent": "#FF4D8D",
    "accent_alt": "#7C5CFF",
    "good": "#22C55E",
    "bad": "#FF5A6B",
    "warning": "#F59E0B",
}
FAIXA_COLORS = {
    "prioridade_maxima":  "#C2410C",
    "alta": "#D97706",
    "media": "#0F6CBD",
    "baixa":"#1F7A5A",
    "descartado": "#94A3B8",
}


def format_int(value: int | float) -> str:
    return f"{int(round(float(value))):,}".replace(",", ".")


def format_score(value: float) -> str:
    if pd.isna(value):
        return "-"
    return f"{float(value):.2f}"


def format_pct(value: float) -> str:
    if pd.isna(value):
        return "-"
    return f"{float(value):.1f}%"


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
            <h1>Dashboard Executivo M1</h1>
            <p>Leitura rapida para decidir onde expandir, quais UFs e cidades priorizar e onde evitar expansao usando apenas o parquet oficial do M1.</p>
            <div class="strip">
                <span class="pill">Fonte unica: <strong>&nbsp;hexagonos_brasil_dashboard.parquet</strong></span>
                <span class="pill">Score oficial: <strong>&nbsp;score_priorizacao</strong></span>
                <span class="pill">Filtros recolhidos na <strong>&nbsp;sidebar</strong></span>
                <span class="pill">Pronto para rodar localmente em <strong>&nbsp;localhost</strong></span>
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
    return pd.read_parquet(path, columns=columns)


def _prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    prepared = df.copy()
    numeric_columns = [
        "lat",
        "lng",
        "score_priorizacao",
        "hex_score_estrutural",
        "ajuste_executivo",
        "rank_brasil",
        "rank_uf",
        "rank_cidade",
        "renda_per_capita",
        "populacao_proxy",
    ]
    for column in numeric_columns:
        prepared[column] = pd.to_numeric(prepared[column], errors="coerce")

    for column in ["flag_viavel", "flag_prioridade"]:
        prepared[column] = prepared[column].fillna(False).astype(bool)

    for column in ["uf", "cidade", "regiao"]:
        prepared[column] = prepared[column].fillna("Nao informado").astype(str)

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
    prepared["UF"] = prepared["uf"]
    prepared["nome_municipio"] = prepared["cidade"]
    prepared["score_exibicao"] = prepared["score_priorizacao"]
    return prepared


@st.cache_data(show_spinner=False)
def load_data() -> pd.DataFrame:
    _ensure_dataset()
    df = _read_parquet_subset(DATASET_PATH, REQUIRED_COLUMNS)
    return _prepare_dataframe(df)


def apply_global_filters(
    df: pd.DataFrame,
    *,
    selected_ufs: list[str],
    selected_cities: list[str],
    selected_faixas: list[str],
) -> pd.DataFrame:
    filtered = df
    if selected_ufs:
        filtered = filtered.loc[filtered["uf"].isin(selected_ufs)]
    if selected_cities:
        filtered = filtered.loc[filtered["cidade"].isin(selected_cities)]
    if selected_faixas:
        filtered = filtered.loc[filtered["faixa_oportunidade"].astype(str).isin(selected_faixas)]
    return filtered.copy()


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
            ]
        )

    grouped = (
        df.groupby(["uf", "cidade"], as_index=False)
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
        df.groupby("uf", as_index=False)
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


def build_map_figure(
    df: pd.DataFrame,
    *,
    title: str,
    selected_ufs: list[str],
    selected_cities: list[str],
):
    map_df = (
        df.dropna(subset=["lat", "lng", "score_priorizacao"])
        .sort_values(
            ["flag_prioridade", "flag_viavel", "score_priorizacao", "rank_brasil"],
            ascending=[False, False, False, True],
            kind="stable",
        )
        .head(MAP_POINT_LIMIT)
        .copy()
    )
    if map_df.empty:
        return None, 0

    map_df["faixa_label"] = map_df["faixa_oportunidade"].astype(str)
    center, zoom = resolve_map_view(
        map_df,
        selected_ufs=selected_ufs,
        selected_cities=selected_cities,
    )

    fig = px.scatter_map(
        map_df,
        lat="lat",
        lon="lng",
        color="faixa_label",
        color_discrete_map=FAIXA_COLORS,
        hover_name="cidade",
        hover_data={
            "uf": True,
            "score_priorizacao": ":.2f",
            "hex_score_estrutural": ":.2f",
            "flag_viavel": True,
            "flag_prioridade": True,
            "lat": False,
            "lng": False,
        },
        labels={
            "uf": "UF",
            "score_priorizacao": "Score",
            "hex_score_estrutural": "Score estrutural",
            "faixa_label": "Faixa",
        },
        center=center,
        zoom=zoom,
        opacity=0.62,
        map_style="carto-positron",
    )
    fig.update_traces(marker={"size": 6})
    fig.update_layout(
        legend_title_text="Faixa",
        coloraxis_showscale=False,
    )
    apply_exec_layout(fig, title=title, height=600)
    return fig, len(map_df)


def build_top_city_figure(city_summary: pd.DataFrame):
    ranking = city_summary.sort_values(
        ["score_medio", "oportunidades_viaveis", "melhor_rank_brasil", "cidade"],
        ascending=[False, False, True, True],
        kind="stable",
    ).head(10)
    if ranking.empty:
        return None

    ranking = ranking.sort_values("score_medio", ascending=True, kind="stable")
    ranking["cidade_label"] = ranking["cidade"] + " / " + ranking["uf"]
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
    scatter_df["cidade_label"] = scatter_df["cidade"] + " / " + scatter_df["uf"]
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
    table_df = (
        df.sort_values(["rank_brasil", "score_priorizacao"], ascending=[True, False], kind="stable")
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


def render_sidebar_filters(df: pd.DataFrame) -> tuple[list[str], list[str], list[str]]:
    st.sidebar.markdown("### Filtros globais")
    st.sidebar.caption("Abra a sidebar para refinar o recorte executivo do M1.")
    all_ufs = sorted(df["uf"].dropna().astype(str).unique().tolist())
    selected_ufs = st.sidebar.multiselect(
        "UF",
        options=all_ufs,
        placeholder="Selecione UFs",
    )

    city_source = df.loc[df["uf"].isin(selected_ufs)] if selected_ufs else df
    all_cities = sorted(city_source["cidade"].dropna().astype(str).unique().tolist())
    selected_cities = st.sidebar.multiselect(
        "nome_municipio",
        options=all_cities,
        placeholder="Selecione cidades",
    )

    faixas_presentes = [faixa for faixa in FAIXA_ORDEM if faixa in set(df["faixa_oportunidade"].astype(str))]
    selected_faixas = st.sidebar.multiselect(
        "faixa_oportunidade",
        options=faixas_presentes,
        placeholder="Selecione faixas",
    )
    st.sidebar.caption(
        "Os filtros afetam todas as abas. Cidade e UF usam os aliases executivos do M1."
    )
    return selected_ufs, selected_cities, selected_faixas


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
    render_faixa_legend()
    map_figure, points_used = build_map_figure(
        df,
        title="Territorio priorizado no recorte atual",
        selected_ufs=selected_ufs,
        selected_cities=selected_cities,
    )
    if map_figure is None:
        st.info("Sem pontos geograficos validos para o mapa neste recorte.")
    else:
        if len(df) > points_used:
            st.caption(
                f"Mapa limitado aos {format_int(points_used)} hexagonos mais relevantes do recorte para manter fluidez local."
            )
        st.plotly_chart(map_figure, use_container_width=True)

    chart_col_1, chart_col_2 = st.columns(2)
    with chart_col_1:
        top_city_fig = build_top_city_figure(city_summary)
        if top_city_fig is not None:
            st.plotly_chart(top_city_fig, use_container_width=True)
    with chart_col_2:
        top_uf_fig = build_top_uf_figure(uf_summary)
        if top_uf_fig is not None:
            st.plotly_chart(top_uf_fig, use_container_width=True)


def render_analise_territorial(df: pd.DataFrame, city_summary: pd.DataFrame) -> None:
    scatter_col, side_col = st.columns([1.6, 1.0])
    with scatter_col:
        scatter_fig = build_scatter_figure(city_summary)
        if scatter_fig is not None:
            st.plotly_chart(scatter_fig, use_container_width=True)
    with side_col:
        score_fig = build_score_distribution_figure(df)
        if score_fig is not None:
            st.plotly_chart(score_fig, use_container_width=True)
        faixa_fig = build_faixa_comparison_figure(df)
        if faixa_fig is not None:
            st.plotly_chart(faixa_fig, use_container_width=True)

    st.markdown("#### Indicadores medios")
    st.dataframe(
        build_indicator_snapshot(df),
        use_container_width=True,
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
        use_container_width=True,
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
            st.plotly_chart(fig_opps, use_container_width=True)
    with chart_col_2:
        fig_score = build_uf_metric_figure(
            uf_summary,
            metric="score_medio",
            label="Score medio",
            color=COLORS["good"],
        )
        if fig_score is not None:
            st.plotly_chart(fig_score, use_container_width=True)
    with chart_col_3:
        fig_top_bottom = build_top_bottom_uf_figure(uf_summary)
        if fig_top_bottom is not None:
            st.plotly_chart(fig_top_bottom, use_container_width=True)


def main() -> None:
    inject_styles()
    render_header()

    try:
        df = load_data()
    except (FileNotFoundError, ValueError) as exc:
        st.error(str(exc))
        st.stop()

    selected_ufs, selected_cities, selected_faixas = render_sidebar_filters(df)
    filtered_df = apply_global_filters(
        df,
        selected_ufs=selected_ufs,
        selected_cities=selected_cities,
        selected_faixas=selected_faixas,
    )

    st.caption(
        f"Recorte atual: {format_int(len(filtered_df))} hexagonos | "
        f"{format_int(filtered_df['uf'].nunique()) if not filtered_df.empty else '0'} UFs | "
        f"{format_int(filtered_df['cidade'].nunique()) if not filtered_df.empty else '0'} cidades"
    )

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
