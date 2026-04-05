import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import pyarrow
import pyarrow.parquet as pq
import streamlit as st
from streamlit.runtime.scriptrunner import get_script_run_ctx
from streamlit.web import cli as stcli


st.set_page_config(
    page_title="Motor de Expansão — Fase 1",
    layout="wide",
)

DATA_DIR = Path(__file__).resolve().parent / "data" / "outputs"
REQUIRED_OUTPUT_FILES = [
    "hexagonos_mapa_sample.parquet",
    "hexagonos_brasil_dashboard.parquet",
    "top_oportunidades_resumo.csv",
    "resumo_por_uf.csv",
]
PARQUET_COLUMNS = [
    "hex_id",
    "lat",
    "lng",
    "uf",
    "cidade",
    "regiao",
    "score_oficial",
    "score_priorizacao",
    "hex_score_estrutural",
    "faixa_oportunidade",
    "flag_viavel",
    "rank_brasil",
    "rank_uf",
    "rank_cidade",
    "motivo_priorizacao",
    "observacao_estrategica",
]
DISPLAY_SCORE_CANDIDATES = [
    "score_oficial",
    "score_priorizacao",
    "hex_score_estrutural",
]
DISPLAY_SCORE_LABEL = "Score oficial"
FAIXA_ORDEM = [
    "prioridade_maxima",
    "alta",
    "media",
    "baixa",
    "descartado",
]
MAPA_BRASIL_LIMITE = 120000
MAPA_LOCAL_LIMITE = 20000


def _ensure_required_outputs() -> None:
    missing = [name for name in REQUIRED_OUTPUT_FILES if not (DATA_DIR / name).exists()]
    if missing:
        raise FileNotFoundError(
            "Artefatos oficiais do M1 ausentes em data/outputs: "
            + ", ".join(missing)
            + ". Gere-os com `python base_h3_brasil.py` e `python hex_enrichment.py --brasil`."
        )


def _read_parquet_subset(path: Path, columns: list[str]) -> pd.DataFrame:
    available_columns = set(pq.read_schema(path).names)
    selected = [column for column in columns if column in available_columns]
    if not selected:
        raise ValueError(f"Nenhuma das colunas esperadas foi encontrada em {path}.")
    return pd.read_parquet(path, columns=selected)


def _resolve_score_column(columns) -> str:
    for column in DISPLAY_SCORE_CANDIDATES:
        if column in columns:
            return column
    raise ValueError(
        "Nenhuma coluna de score compativel encontrada. Esperado um de: "
        + ", ".join(DISPLAY_SCORE_CANDIDATES)
    )


def _prepare_dashboard_like(df: pd.DataFrame) -> pd.DataFrame:
    prepared = df.copy()
    score_column = _resolve_score_column(prepared.columns)
    prepared["score_exibicao"] = pd.to_numeric(prepared[score_column], errors="coerce")
    prepared["faixa_oportunidade"] = pd.Categorical(
        prepared["faixa_oportunidade"],
        categories=FAIXA_ORDEM,
        ordered=True,
    )
    return prepared


@st.cache_data(show_spinner=False)
def load_data():
    _ensure_required_outputs()

    df_mapa = _prepare_dashboard_like(
        _read_parquet_subset(DATA_DIR / "hexagonos_mapa_sample.parquet", PARQUET_COLUMNS)
    )
    df_dashboard = _prepare_dashboard_like(
        _read_parquet_subset(DATA_DIR / "hexagonos_brasil_dashboard.parquet", PARQUET_COLUMNS)
    )
    df_top = pd.read_csv(DATA_DIR / "top_oportunidades_resumo.csv", sep=";")
    df_resumo = pd.read_csv(DATA_DIR / "resumo_por_uf.csv", sep=";")
    df_top["score_exibicao"] = pd.to_numeric(
        df_top[_resolve_score_column(df_top.columns)],
        errors="coerce",
    )

    return df_mapa, df_dashboard, df_top, df_resumo


def format_int(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def build_map(
    df: pd.DataFrame,
    *,
    title: str,
    center: dict[str, float],
    zoom: float,
    height: int,
):
    fig = px.scatter_mapbox(
        df,
        lat="lat",
        lon="lng",
        color="score_exibicao",
        color_continuous_scale="YlOrRd",
        hover_name="cidade",
        hover_data={
            "uf": True,
            "score_exibicao": ":.2f",
            "hex_score_estrutural": ":.2f",
            "faixa_oportunidade": True,
            "lat": False,
            "lng": False,
        },
        labels={
            "score_exibicao": DISPLAY_SCORE_LABEL,
            "hex_score_estrutural": "Score estrutural",
        },
        center=center,
        zoom=zoom,
        height=height,
    )
    fig.update_traces(marker={"size": 7, "opacity": 0.65})
    fig.update_layout(
        mapbox_style="carto-positron",
        margin={"l": 0, "r": 0, "t": 48, "b": 0},
        title=title,
        coloraxis_colorbar_title=DISPLAY_SCORE_LABEL,
    )
    return fig


def main():
    _ = pyarrow.__version__
    df_mapa, df_dashboard, df_top, df_resumo = load_data()

    st.title("Motor de Expansão — Fase 1")
    st.caption(
        "Dashboard leve para leitura executiva da Fase 1, usando apenas os artefatos "
        "oficiais gerados em data/outputs."
    )

    tab_brasil, tab_local, tab_ranking = st.tabs(
        ["Visão Brasil", "Exploração Local", "Ranking"]
    )

    with tab_brasil:
        total_hexagonos = len(df_dashboard)
        pct_viaveis = df_dashboard["flag_viavel"].mean() * 100
        total_prioridade_maxima = (
            df_dashboard["faixa_oportunidade"] == "prioridade_maxima"
        ).sum()
        total_alta = (df_dashboard["faixa_oportunidade"] == "alta").sum()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total hexágonos", format_int(total_hexagonos))
        col2.metric("% viáveis", f"{pct_viaveis:.1f}%")
        col3.metric("Total prioridade_maxima", format_int(total_prioridade_maxima))
        col4.metric("Total alta", format_int(total_alta))

        df_mapa_brasil = df_mapa.sort_values("rank_brasil").head(MAPA_BRASIL_LIMITE)
        st.caption(
            f"Mapa Brasil carregado com a amostra oficial e limitado a "
            f"{format_int(len(df_mapa_brasil))} pontos para manter fluidez."
        )
        fig_brasil = build_map(
            df_mapa_brasil,
            title="Mapa nacional de oportunidade executiva",
            center={"lat": -14.235, "lon": -51.9253},
            zoom=3.2,
            height=620,
        )
        st.plotly_chart(fig_brasil, use_container_width=True)

        faixa_counts = (
            df_dashboard["faixa_oportunidade"]
            .value_counts(sort=False)
            .rename_axis("faixa_oportunidade")
            .reset_index(name="total")
        )
        fig_faixas = px.bar(
            faixa_counts,
            x="faixa_oportunidade",
            y="total",
            color="faixa_oportunidade",
            category_orders={"faixa_oportunidade": FAIXA_ORDEM},
            title="Distribuição por faixa_oportunidade",
        )
        fig_faixas.update_layout(
            showlegend=False,
            margin={"l": 0, "r": 0, "t": 48, "b": 0},
            xaxis_title="Faixa",
            yaxis_title="Hexágonos",
        )
        st.plotly_chart(fig_faixas, use_container_width=True)

    with tab_local:
        ufs = sorted(df_dashboard["uf"].dropna().unique().tolist())
        uf_default = ufs.index("SP") if "SP" in ufs else 0
        uf_selecionada = st.selectbox("UF", ufs, index=uf_default, key="local_uf")

        cidades = sorted(
            df_dashboard.loc[df_dashboard["uf"] == uf_selecionada, "cidade"]
            .dropna()
            .unique()
            .tolist()
        )
        cidade_selecionada = st.selectbox(
            "Cidade",
            ["Todas"] + cidades,
            index=0,
            key="local_cidade",
        )

        df_filtrado = df_dashboard.loc[df_dashboard["uf"] == uf_selecionada].copy()
        if cidade_selecionada != "Todas":
            df_filtrado = df_filtrado.loc[df_filtrado["cidade"] == cidade_selecionada]

        info1, info2, info3 = st.columns(3)
        info1.metric("Hexágonos no recorte", format_int(len(df_filtrado)))
        info2.metric("Score médio", f"{df_filtrado['score_exibicao'].mean():.2f}")
        info3.metric(
            "Viáveis no recorte",
            format_int(int(df_filtrado["flag_viavel"].sum())),
        )

        sort_column = "rank_cidade" if cidade_selecionada != "Todas" else "rank_uf"
        df_mapa_local = df_filtrado.sort_values(sort_column).head(MAPA_LOCAL_LIMITE)
        if len(df_filtrado) > MAPA_LOCAL_LIMITE:
            st.caption(
                f"Mapa local limitado aos {format_int(MAPA_LOCAL_LIMITE)} hexágonos "
                "mais bem ranqueados para evitar lentidão no recorte amplo."
            )

        fig_local = build_map(
            df_mapa_local,
            title=f"Exploração local — {uf_selecionada}"
            + (f" / {cidade_selecionada}" if cidade_selecionada != "Todas" else ""),
            center={
                "lat": float(df_mapa_local["lat"].mean()),
                "lon": float(df_mapa_local["lng"].mean()),
            },
            zoom=8.0 if cidade_selecionada != "Todas" else 5.2,
            height=560,
        )
        st.plotly_chart(fig_local, use_container_width=True)

        tabela_local = (
            df_filtrado.loc[
                :,
                [
                    "hex_id",
                    "rank_uf",
                    "rank_cidade",
                    "score_exibicao",
                    "faixa_oportunidade",
                    "motivo_priorizacao",
                ],
            ]
            .sort_values(sort_column)
            .rename(
                columns={
                    "hex_id": "hex_id",
                    "rank_uf": "rank_uf",
                    "rank_cidade": "rank_cidade",
                    "score_exibicao": "score",
                    "faixa_oportunidade": "faixa",
                    "motivo_priorizacao": "motivo_priorizacao",
                }
            )
        )
        st.dataframe(
            tabela_local,
            use_container_width=True,
            hide_index=True,
            height=460,
        )

    with tab_ranking:
        st.subheader("Top Brasil")
        top_brasil = (
            df_top.sort_values("rank_brasil")
            .head(100)
            .rename(
                columns={
                    "score_exibicao": "score",
                    "faixa_oportunidade": "faixa",
                }
            )
        )
        st.dataframe(top_brasil, use_container_width=True, hide_index=True, height=420)

        st.subheader("Top por UF")
        uf_ranking = st.selectbox("UF do ranking", ufs, index=uf_default, key="ranking_uf")
        top_por_uf = (
            df_dashboard.loc[
                df_dashboard["uf"] == uf_ranking,
                [
                    "rank_uf",
                    "cidade",
                    "score_exibicao",
                    "faixa_oportunidade",
                    "motivo_priorizacao",
                ],
            ]
            .sort_values("rank_uf")
            .head(50)
            .rename(
                columns={
                    "score_exibicao": "score",
                    "faixa_oportunidade": "faixa",
                }
            )
        )
        st.dataframe(top_por_uf, use_container_width=True, hide_index=True, height=420)

        st.subheader("Resumo por UF")
        st.dataframe(df_resumo, use_container_width=True, hide_index=True, height=320)


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
    else:
        main()
