from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st

from dashboard.constants import (
    BRASIL_CENTER,
    CENSO_UFS,
    COLORS,
    FAIXA_COLORS,
    FAIXA_ORDEM,
    MAP_POINT_LIMIT,
    TABLE_ROW_LIMIT,
)
from dashboard.utils import (
    _censo_score_to_color,
    format_density,
    format_int,
    format_pct,
    format_score,
    hex_to_rgba,
)
from motor_expansao.dashboard.data import _has_censo_signal, _normalized_join_quality


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
