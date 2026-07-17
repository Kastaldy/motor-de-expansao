from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st

from motor_expansao.dashboard.competitors import (
    build_icon_atlas,
    competitor_legend_entries,
    ultra_legend_entry,
)
from motor_expansao.dashboard.constants import (
    BRASIL_CENTER,
    CENSO_UFS,
    COLORS,
    COMPETITOR_CLUSTER_LIMIT,
    COMPETITOR_CLUSTER_RES,
    COMPETITOR_CLUSTER_TOP_REDES,
    COMPETITOR_PIN_LIMIT,
    FAIXA_COLORS,
    FAIXA_COLORS_POR_LABEL,
    FAIXA_LABELS,
    FAIXA_ORDEM,
    FATOR_TEMPORAL_RENDA,
    MAP_POINT_LIMIT,
    MAP_POINT_LIMIT_LARGE,
    MAP_SORT_ASCENDING,
    MAP_SORT_COLUMNS,
    MAP_SOURCE_COLUMNS_HYBRID,
    MAP_SOURCE_COLUMNS_M1,
    OVERLAYS,
    RESIDUAL_SCORE_BANDS,
    TABLE_ROW_LIMIT,
    ULTRA_PIN_LIMIT,
    moradores_por_domicilio,
    uplift_renda_domiciliar,
)
from motor_expansao.dashboard.data import _has_censo_signal, _normalized_join_quality, haversine_km
from motor_expansao.dashboard.utils import (
    format_int,
    format_pct,
    format_score,
    hex_to_rgba,
    score_band_to_color,
)

# BLK-PERF-01b: bound de memória do cache do deck do Mapa Territorial. NÃO é expiração por
# tempo (D2 proíbe TTL); apenas limita quantas entradas de deck ficam memoizadas por processo
# (~6 recortes × 4 modos). Vive aqui (path do ciclo), não em constants.py.
MAP_FIGURE_CACHE_MAX_ENTRIES = 24


def _map_frame_token(df: pd.DataFrame | None, cols: list[str]) -> str:
    """Token leve e determinístico do conteúdo de um DataFrame para chave de cache.

    None -> "none"; vazio -> "n0"; senão f"n{len}:{sha1(hash_pandas_object(cols presentes))[:16]}".
    hash_pandas_object é vetorizado em C e sensível ao CONTEÚDO (inclui dtype object como hex_id).
    Recorte com conjunto de linhas/valores diferente -> token diferente -> MISS correto; conjuntos
    distintos nunca colidem (impossível false-hit entre UFs). READ-ONLY: só deriva identidade.
    """
    if df is None:
        return "none"
    if len(df) == 0:
        return "n0"
    present = [c for c in cols if c in df.columns]
    if not present:
        return f"n{len(df)}:nocols"
    hashed = pd.util.hash_pandas_object(df[present], index=False).to_numpy().tobytes()
    return f"n{len(df)}:{hashlib.sha1(hashed).hexdigest()[:16]}"


@st.cache_data(show_spinner=False, max_entries=MAP_FIGURE_CACHE_MAX_ENTRIES)  # sem expiracao por tempo (D2)
def build_unified_map_figure_cached(
    _df: pd.DataFrame,
    _competitors_df: pd.DataFrame | None,
    _ultra_df: pd.DataFrame | None,
    _dominio_df: pd.DataFrame | None,
    *,
    color_mode: str,
    enabled_overlays: tuple[str, ...],
    selected_ufs: tuple[str, ...],
    selected_cities: tuple[str, ...],
    selected_faixas: tuple[str, ...],
    search_pin: tuple[float, float] | None,
    search_hex_id: str | None,
    df_token: str,
    competitors_token: str,
    ultra_token: str,
    dominio_token: str,
    _vazios_df: pd.DataFrame | None = None,
    vazios_token: str = "none",
):
    """Wrapper cacheado (@st.cache_data, SEM ttl) do dispatcher do Mapa Territorial.

    Os DataFrames entram como parâmetros underscore (IGNORADOS no hash do Streamlit); a
    identidade do recorte vem dos *_token calculados por _map_frame_token. multihex_cenario
    FICA FORA da chave (a layer de destaque é anexada pós-cache no render). cache_data devolve
    uma cópia por chamada -> anexar layer ao deck retornado não vaza para outros hits.
    READ-ONLY M1: não recalcula score, carteira, plano nem artefatos oficiais.

    `_vazios_df`/`vazios_token` (BLK-TP-03-FU1): overlay opcional "Vazio competitivo LC",
    keyword-only com default — compatível com qualquer chamador existente que não os passa.
    """
    return build_unified_map_figure(
        _df,
        color_mode=color_mode,
        enabled_overlays=list(enabled_overlays),
        selected_ufs=list(selected_ufs),
        selected_cities=list(selected_cities),
        selected_faixas=(list(selected_faixas) or None),
        competitors_df=_competitors_df,
        ultra_df=_ultra_df,
        search_pin=search_pin,
        search_hex_id=search_hex_id,
        dominio_df=_dominio_df,
        vazios_df=_vazios_df,
    )


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
            f"{row.uf}: {format_int(row.oportunidades_viaveis)} viáveis | score médio {format_score(row.score_medio)}"
            for row in top_expandir.itertuples(index=False)
        ],
        "priorizar": [
            f"{row.cidade}/{row.uf}: score {format_score(row.score_medio)} | rank Brasil {format_int(row.melhor_rank_brasil)}"
            for row in top_priorizar.itertuples(index=False)
        ],
        "ufs_priorizar": [
            f"{row.uf}: score médio {format_score(row.score_medio)} | {format_int(row.oportunidades_viaveis)} viáveis"
            for row in top_ufs_priorizar.itertuples(index=False)
        ],
        "evitar": [
            f"{row.uf}: {format_int(row.oportunidades_viaveis)} viáveis | score médio {format_score(row.score_medio)}"
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
                f"{FAIXA_LABELS.get(faixa, faixa)}"
                f"</span>"
            )
            for faixa in FAIXA_ORDEM
        ]
    )
    st.markdown(f"<div class='legend-row'>{chips}</div>", unsafe_allow_html=True)


def render_geographic_source_legend() -> None:
    entries = [
        ("#C8D3EA", "Setor censitário (qualidade A/B)"),
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


def render_competitor_legend(competitors_df: pd.DataFrame | None = None) -> None:
    if competitors_df is None or competitors_df.empty or "rede" not in competitors_df.columns:
        return

    entries = competitor_legend_entries(competitors_df["rede"])
    if not entries:
        return

    chips = "".join(
        (
            f"<span class='legend-chip'>"
            f"<span style='display:inline-flex;align-items:center;justify-content:center;"
            f"width:22px;height:22px;border-radius:999px;background:{entry['bg']};"
            f"color:{entry['fg']};font-size:0.62rem;font-weight:800;border:2px solid rgba(255,255,255,0.84);'>"
            f"{entry['short']}</span>"
            f"{entry['label']}"
            f"</span>"
        )
        for entry in entries
    )
    st.markdown(f"<div class='legend-row'>{chips}</div>", unsafe_allow_html=True)


def render_ultra_legend(ultra_df: pd.DataFrame | None = None) -> None:
    if ultra_df is None or ultra_df.empty:
        return
    entry = ultra_legend_entry()
    chip = (
        f"<span class='legend-chip'>"
        f"<span style='display:inline-flex;align-items:center;justify-content:center;"
        f"width:22px;height:22px;border-radius:999px;background:{entry['bg']};"
        f"color:{entry['fg']};font-size:0.62rem;font-weight:800;border:2px solid rgba(255,255,255,0.84);'>"
        f"{entry['short']}</span>"
        f"{entry['label']}"
        f"</span>"
    )
    st.markdown(f"<div class='legend-row'>{chip}</div>", unsafe_allow_html=True)


def _vectorized_cidade_uf_line(df: pd.DataFrame) -> pd.Series:
    """Linha de tooltip 'Cidade/UF: X / Y' vetorizada (sem .apply(axis=1)),
    com mesmo texto de hoje: '-' quando cidade e uf ausentes/vazios."""
    cidade = df.get("cidade", pd.Series([""] * len(df), index=df.index)).map(_clean_tooltip_value)
    uf = df.get("uf", pd.Series([""] * len(df), index=df.index)).map(_clean_tooltip_value)
    ambos_vazios = (cidade == "-") & (uf == "-")
    par = cidade.astype(str) + " / " + uf.astype(str)
    return "Cidade/UF: " + np.where(ambos_vazios, "-", par)


def _vectorized_coord_line(df: pd.DataFrame) -> pd.Series:
    """Linha de tooltip 'Coordenadas: lat, lng' vetorizada (sem .apply(axis=1)),
    com mesmo formato de _format_coordinate_pair (.5f, '-' se NaN)."""
    lat = pd.to_numeric(df["lat"], errors="coerce")
    lng = pd.to_numeric(df["lng"], errors="coerce")
    valido = lat.notna() & lng.notna()
    par = lat.map(lambda v: f"{float(v):.5f}" if pd.notna(v) else "-") + ", " + lng.map(
        lambda v: f"{float(v):.5f}" if pd.notna(v) else "-"
    )
    return "Coordenadas: " + np.where(valido, par, "-")


def _ultra_icon_layer_from_frame(ultra: pd.DataFrame):
    """Constroi a IconLayer de pins Ultra a partir de um frame JA filtrado.

    Aplica cap duro (ULTRA_PIN_LIMIT, amostragem deterministica), monta o atlas
    de icone (chave unica '__ultra__'), tooltips vetorizados (mesmos textos de
    hoje) e payload enxuto. Logo preservado via atlas. Camada visual: nao altera
    score nem artefatos M1."""
    if ultra.empty:
        return None

    for column in ["cidade", "uf", "arquivo_origem"]:
        if column not in ultra.columns:
            ultra[column] = ""

    # cap duro deterministico
    if len(ultra) > ULTRA_PIN_LIMIT:
        ultra = (
            ultra.sort_values(["nome_unidade", "lat", "lng"], kind="stable")
            .head(ULTRA_PIN_LIMIT)
            .reset_index(drop=True)
        )

    atlas, mapping = build_icon_atlas(["__ultra__"])

    ultra["icon_key"] = "__ultra__"
    ultra["icon_size"] = 38
    ultra["tooltip_title"] = "Ultra Academia: " + ultra["nome_unidade"].astype(str)
    ultra["tooltip_line_1"] = "Tipo: Unidade Ultra Academia"
    ultra["tooltip_line_2"] = _vectorized_cidade_uf_line(ultra)
    ultra["tooltip_line_3"] = _vectorized_coord_line(ultra)
    ultra["tooltip_line_4"] = "Fonte: " + ultra["arquivo_origem"].astype(str)

    frame = _icon_layer_frame(ultra, icon_key_col="icon_key", n_tooltip_lines=4)

    return pdk.Layer(
        "IconLayer",
        data=frame,
        get_icon="icon_key",
        get_position="[lng, lat]",
        get_size="icon_size",
        size_units="pixels",
        size_scale=1,
        size_min_pixels=26,
        size_max_pixels=46,
        pickable=True,
        billboard=True,
        icon_atlas='"' + atlas + '"',
        icon_mapping=mapping,
    )


def _build_ultra_icon_layer(
    ultra_df: pd.DataFrame | None,
    reference_df: pd.DataFrame,
):
    if ultra_df is None or ultra_df.empty:
        return None
    if reference_df.empty or not {"lat", "lng"} <= set(reference_df.columns):
        return None
    if not {"lat", "lng", "nome_unidade"} <= set(ultra_df.columns):
        return None

    ultra = ultra_df.loc[ultra_df["lat"].notna() & ultra_df["lng"].notna()].copy()
    if ultra.empty:
        return None

    lat_span = float(reference_df["lat"].max() - reference_df["lat"].min())
    lng_span = float(reference_df["lng"].max() - reference_df["lng"].min())
    padding = max(0.05, min(0.8, max(lat_span, lng_span) * 0.08))

    ultra = ultra.loc[
        ultra["lat"].between(float(reference_df["lat"].min()) - padding, float(reference_df["lat"].max()) + padding)
        & ultra["lng"].between(float(reference_df["lng"].min()) - padding, float(reference_df["lng"].max()) + padding)
    ].copy()
    if ultra.empty:
        return None

    return _ultra_icon_layer_from_frame(ultra)


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


def build_map_scope_caption(
    points_used: int,
    *,
    selected_ufs: list[str],
    capped: bool = False,
    effective_cap: int = MAP_POINT_LIMIT,
) -> str:
    scope_label = "da UF selecionada" if len(selected_ufs) == 1 else "do recorte atual"
    if capped:
        return (
            f"Mostrando os {format_int(effective_cap)} hexágonos de maior prioridade {scope_label} "
            f"(recorte total maior que o limite de renderização). "
            "Aplique filtros de município para ver o recorte completo."
        )
    return (
        f"Mostrando todos os hexágonos válidos {scope_label} "
        f"({format_int(points_used)} no recorte atual), preservando a geometria granular onde ela é confiável."
        " Para densidade total de uma área, selecione um município no filtro lateral."
    )


def _clean_tooltip_value(value: object, fallback: str = "-") -> str:
    if pd.isna(value):
        return fallback
    text = str(value).strip()
    return text if text else fallback


def _format_coordinate_pair(lat: Any, lng: Any) -> str:
    if pd.isna(lat) or pd.isna(lng):
        return "-"
    return f"{float(lat):.5f}, {float(lng):.5f}"


def _has_residual_signal(map_df: pd.DataFrame) -> bool:
    return (
        "oferta_efetiva_disponivel" in map_df.columns
        and pd.to_numeric(map_df["oferta_efetiva_disponivel"], errors="coerce").notna().any()
    )


def _apply_residual_tooltip_fields(map_df: pd.DataFrame) -> pd.DataFrame:
    if not _has_residual_signal(map_df):
        map_df["score_residual_fmt"] = "-"
        map_df["tooltip_residual_1"] = "Residual Fitness: -"
        return map_df

    na_float = pd.Series(pd.NA, index=map_df.index, dtype="Float64")
    oferta = pd.to_numeric(map_df.get("oferta_efetiva_disponivel", na_float), errors="coerce")
    score = pd.to_numeric(map_df.get("score_oportunidade_residual", na_float), errors="coerce")
    map_df["score_residual_fmt"] = score.map(format_score)
    map_df["tooltip_residual_1"] = (
        "Residual Fitness: " + oferta.map(lambda v: format_int(v) if pd.notna(v) else "-")
    )
    return map_df


# BLK-PERF-01c (D4): rotulo + coluna ja formatada do "Score do modo ativo" (2a linha do
# tooltip enxuto), por modo. Em mode="censitario" a linha 2 e' o Score Censitario; para NAO
# duplicar, `_apply_hex_tooltip_fields` mostra o Score M1 na linha 3 nesse modo (desduplicado).
_ACTIVE_SCORE_SPEC: dict[str, tuple[str, str]] = {
    "m1": ("Score M1", "score_priorizacao_fmt"),
    "hibrido": ("Score Híbrido", "score_hibrido_fmt"),
    "censitario": ("Score Censitário", "score_censo_fmt"),
    "residual": ("Score Residual", "score_residual_fmt"),
}


def _renda_media_domiciliar_series(map_df: pd.DataFrame) -> pd.Series:
    """Renda media domiciliar por hex (R$/mes) para o tooltip, computada em tempo de render.

    `renda_pc_calibrada(hex) x moradores_municipio x uplift_municipio x FATOR_TEMPORAL`. Moradores e
    uplift sao MUNICIPAIS (por `cod_municipio`) — um hex res-7 cobre varios setores, entao o uplift
    setorial do #124 nao se aplica a 1 hex. READ-ONLY sobre o M1 (so exibicao). Fallback gracioso:
    NaN quando falta renda, ou quando `cod_municipio` esta ausente (coluna OU valor NaN por linha) —
    hexes sem cobertura censitaria (costeiros/nao-granulares) ficam com o tooltip em branco em vez de
    exibir uma estimativa de nivel UF. Sem o parquet municipal, moradores/uplift de municipios
    conhecidos caem no nacional (~2.79 / 1.632). Nao depende do artefato enriquecido — so das
    colunas ja servidas.
    """
    idx = map_df.index
    renda_pc = pd.to_numeric(
        map_df.get("renda_per_capita_setor_2022_calibrada", pd.Series(np.nan, index=idx)),
        errors="coerce",
    )
    if "renda_per_capita" in map_df.columns:
        renda_pc = renda_pc.where(
            renda_pc.notna(), pd.to_numeric(map_df["renda_per_capita"], errors="coerce")
        )
    if "cod_municipio" not in map_df.columns:
        return pd.Series(np.nan, index=idx)

    def _s(value: object) -> str | None:
        return None if pd.isna(value) else str(value)

    uf_col = map_df["uf"] if "uf" in map_df.columns else pd.Series(pd.NA, index=idx)
    keys = pd.DataFrame(
        {"uf": uf_col.astype("string"), "cod_municipio": map_df["cod_municipio"].astype("string")}
    )
    fator_temporal = float(FATOR_TEMPORAL_RENDA)
    uniq = keys.drop_duplicates().copy()
    uniq["_fator_dom"] = [
        moradores_por_domicilio(_s(uf), _s(cod))
        * uplift_renda_domiciliar(_s(uf), _s(cod))
        * fator_temporal
        for uf, cod in uniq.itertuples(index=False, name=None)
    ]
    fatores = keys.merge(uniq, on=["uf", "cod_municipio"], how="left")["_fator_dom"].to_numpy()
    resultado = pd.Series(renda_pc.to_numpy() * fatores, index=idx)
    # Contrato: sem municipio resolvido (cod_municipio ausente/NaN por linha) -> tooltip vazio, e
    # nao uma estimativa de nivel UF. Simetrico ao NaN quando falta renda.
    return resultado.where(map_df["cod_municipio"].notna())


def _apply_hex_tooltip_fields(map_df: pd.DataFrame, *, mode: str, show_discarded: bool = True) -> pd.DataFrame:
    map_df = _apply_residual_tooltip_fields(map_df)
    map_df["tooltip_title"] = map_df["nome_municipio"].astype(str) + " / " + map_df["uf"].astype(str)

    active_label, active_col = _ACTIVE_SCORE_SPEC[mode]
    active_fmt = map_df[active_col] if active_col in map_df.columns else pd.Series("-", index=map_df.index)
    map_df["tooltip_line_1"] = "Faixa M1: " + map_df["faixa_label"].astype(str)
    map_df["tooltip_line_2"] = f"{active_label}: " + active_fmt.astype(str)
    # Linha 3 = Score Censitario, EXCETO no modo censitario: ali a linha 2 (score do modo ativo) JA
    # e o censitario, entao repetir seria a duplicacao reportada. No modo censitario mostramos o
    # Score M1 -> a linha 3 nunca duplica a linha 2, e cada modo exibe dois scores distintos.
    if mode == "censitario":
        m1_score = (
            map_df["score_priorizacao"]
            if "score_priorizacao" in map_df.columns
            else pd.Series(pd.NA, index=map_df.index)
        )
        map_df["tooltip_line_3"] = "Score M1: " + m1_score.map(format_score).astype(str)
    else:
        map_df["tooltip_line_3"] = "Score Censitário: " + map_df["score_censo_fmt"].astype(str)
    map_df["tooltip_line_4"] = "Habitantes: " + map_df["pop_fmt"].astype(str)
    map_df["tooltip_line_5"] = "Renda per capita: R$ " + map_df["renda_fmt"].astype(str)
    map_df["tooltip_line_6"] = map_df["tooltip_residual_1"]
    # Linha 7 (NOVO, por ULTIMO): renda media domiciliar por hex, computada em tempo de render a
    # partir das colunas ja servidas + tabela municipal (ver _renda_media_domiciliar_series). Fica na
    # ultima linha DE PROPOSITO: quando vazia (NaN, sem renda/cod_municipio) nao deixa gap no meio do
    # tooltip nem exibe "-". READ-ONLY sobre o M1 (so exibicao).
    renda_dom = _renda_media_domiciliar_series(map_df)
    map_df["tooltip_line_7"] = renda_dom.map(
        lambda v: f"Renda média domiciliar: R$ {format_int(v)}" if pd.notna(v) else ""
    )

    if "flag_pop_min_5k" in map_df.columns and show_discarded:
        discarded = ~map_df["flag_pop_min_5k"].fillna(True)
        map_df.loc[discarded, "tooltip_title"] = (
            map_df.loc[discarded, "tooltip_title"].astype(str) + " - Descartado <5k hab"
        )
    return map_df


def _ensure_columns(map_df: pd.DataFrame, defaults: dict[str, object]) -> pd.DataFrame:
    for column, default in defaults.items():
        if column not in map_df.columns:
            map_df[column] = default
    return map_df


def _infer_confianca_geografica(map_df: pd.DataFrame) -> pd.Series:
    quality = _normalized_join_quality(map_df)
    has_censo = _has_censo_signal(map_df)
    inferred = pd.Series(
        np.where(quality.isin(["A", "B"]) & has_censo, "granular", "municipal"),
        index=map_df.index,
        dtype="object",
    )
    if "confianca_geografica" not in map_df.columns:
        return inferred

    current = (
        map_df["confianca_geografica"]
        .astype(object)
        .where(map_df["confianca_geografica"].notna(), inferred)
        .astype(str)
        .str.lower()
    )
    return current.where(current.isin(["granular", "municipal"]), inferred)


def _compute_faixa_label(faixa: pd.Series) -> pd.Series:
    def _label(v: object) -> str:
        if pd.isna(v):
            return "Não informado"
        key = str(v)
        return FAIXA_LABELS.get(key, key)

    return faixa.map(_label).astype(str)


def _prepare_m1_tooltip_fields(map_df: pd.DataFrame) -> pd.DataFrame:
    map_df = map_df.copy()
    _ensure_columns(
        map_df,
        {
            "cidade": "-",
            "nome_municipio": pd.NA,
            "uf": "-",
            "faixa_oportunidade": "Não informado",
            "score_priorizacao": pd.NA,
            "hex_score_estrutural": pd.NA,
            "flag_viavel": pd.NA,
            "flag_prioridade": pd.NA,
            "score_setor_2022_calibrado": pd.NA,
            "coverage_pct_setor_2022": pd.NA,
            "qualidade_join_uf": pd.NA,
            "populacao_proxy": pd.NA,
            "renda_per_capita": pd.NA,
        },
    )
    map_df["nome_municipio"] = map_df["nome_municipio"].fillna(map_df["cidade"])
    map_df["confianca_geografica"] = _infer_confianca_geografica(map_df)
    map_df["faixa_label"] = _compute_faixa_label(map_df["faixa_oportunidade"])
    map_df["score_priorizacao_fmt"] = map_df["score_priorizacao"].map(format_score)
    map_df["score_censo_fmt"] = map_df["score_setor_2022_calibrado"].map(format_score)

    is_granular = map_df["confianca_geografica"].eq("granular")
    na_float = pd.Series(pd.NA, index=map_df.index, dtype="Float64")
    pop_municipal = map_df["pop_total"] if "pop_total" in map_df.columns else map_df.get("populacao_proxy", na_float)
    has_setor_pop = "pop_total_setor_2022" in map_df.columns and map_df["pop_total_setor_2022"].notna().any()
    if has_setor_pop:
        use_setor_pop = is_granular & map_df["pop_total_setor_2022"].notna()
        pop_val = map_df["pop_total_setor_2022"].where(use_setor_pop, pop_municipal)
        pop_suffix = np.where(use_setor_pop, "", " (municipal)")
    else:
        pop_val = pop_municipal
        pop_suffix = np.full(len(map_df), " (municipal)")
    map_df["pop_fmt"] = pop_val.map(lambda v: format_int(v) if pd.notna(v) else "-") + pop_suffix

    has_setor_renda = (
        "renda_per_capita_setor_2022_calibrada" in map_df.columns
        and map_df["renda_per_capita_setor_2022_calibrada"].notna().any()
    )
    if has_setor_renda:
        use_setor_renda = is_granular & map_df["renda_per_capita_setor_2022_calibrada"].notna()
        renda_val = map_df["renda_per_capita_setor_2022_calibrada"].where(
            use_setor_renda,
            map_df.get("renda_per_capita", na_float),
        )
        renda_suffix = np.where(use_setor_renda, "", " (municipal)")
    else:
        renda_val = map_df.get("renda_per_capita", na_float)
        renda_suffix = np.full(len(map_df), " (municipal)")
    map_df["renda_fmt"] = renda_val.map(lambda v: format_int(v) if pd.notna(v) else "-") + renda_suffix
    return map_df


def _prepare_hybrid_tooltip_fields(map_df: pd.DataFrame) -> pd.DataFrame:
    map_df = map_df.copy()
    _ensure_columns(
        map_df,
        {
            "nome_municipio": "-",
            "uf": "-",
            "faixa_oportunidade": pd.NA,
            "score_setor_2022_calibrado": pd.NA,
            "score_priorizacao": pd.NA,
            "score_expansao_hibrido": pd.NA,
            "densidade_pop_setor_hab_km2": pd.NA,
            "qualidade_join_uf": pd.NA,
            "flag_outlier_espacial": pd.NA,
            "motivo_nao_elegivel_censo": pd.NA,
            "elegibilidade_hibrida": "-",
            "rank_hex_intraurbano": pd.NA,
            "top_hex_intraurbano": pd.NA,
            "populacao_proxy": pd.NA,
            "renda_per_capita": pd.NA,
        },
    )
    map_df["faixa_label"] = _compute_faixa_label(map_df["faixa_oportunidade"])
    map_df["score_censo_fmt"] = map_df["score_setor_2022_calibrado"].map(format_score)
    # score_hibrido_fmt: mantido (nao removido, apesar do passo A/4 do plano do Planner
    # listar sua remocao) porque e o "Score do modo ativo" (_ACTIVE_SCORE_SPEC["hibrido"])
    # consumido pelo fallback de busca de build_hybrid_map_figure quando mode="hibrido"
    # (hex pesquisado fora do recorte filtrado usa este caminho, nao o calculo inline);
    # removê-lo quebraria esse fallback (ver teste
    # test_build_hybrid_map_figure_destaque_hex_usa_tooltip_enxuto, linha "Score Híbrido: 93.00").
    map_df["score_hibrido_fmt"] = map_df["score_expansao_hibrido"].map(format_score)

    na_float = pd.Series(pd.NA, index=map_df.index, dtype="Float64")
    pop_municipal = map_df["pop_total"] if "pop_total" in map_df.columns else map_df.get("populacao_proxy", na_float)
    has_setor_pop = "pop_total_setor_2022" in map_df.columns and map_df["pop_total_setor_2022"].notna().any()
    if has_setor_pop:
        use_setor_pop = map_df["pop_total_setor_2022"].notna()
        pop_val = map_df["pop_total_setor_2022"].where(use_setor_pop, pop_municipal)
        pop_suffix = np.where(use_setor_pop, "", " (municipal)")
    else:
        pop_val = pop_municipal
        pop_suffix = np.full(len(map_df), " (municipal)")
    map_df["pop_fmt"] = pop_val.map(lambda v: format_int(v) if pd.notna(v) else "-") + pop_suffix

    has_setor_renda = (
        "renda_per_capita_setor_2022_calibrada" in map_df.columns
        and map_df["renda_per_capita_setor_2022_calibrada"].notna().any()
    )
    if has_setor_renda:
        use_setor_renda = map_df["renda_per_capita_setor_2022_calibrada"].notna()
        renda_val = map_df["renda_per_capita_setor_2022_calibrada"].where(
            use_setor_renda,
            map_df.get("renda_per_capita", na_float),
        )
        renda_suffix = np.where(use_setor_renda, "", " (municipal)")
    else:
        renda_val = map_df.get("renda_per_capita", na_float)
        renda_suffix = np.full(len(map_df), " (municipal)")
    map_df["renda_fmt"] = renda_val.map(lambda v: format_int(v) if pd.notna(v) else "-") + renda_suffix
    return map_df


def _filter_competitors_to_reference(
    competitors_df: pd.DataFrame | None,
    reference_df: pd.DataFrame,
) -> pd.DataFrame:
    if competitors_df is None or competitors_df.empty:
        return pd.DataFrame()
    if reference_df.empty or not {"lat", "lng"} <= set(reference_df.columns):
        return pd.DataFrame()
    if not {"lat", "lng", "rede", "nome_unidade"} <= set(competitors_df.columns):
        return pd.DataFrame()

    comp = competitors_df.loc[
        competitors_df["lat"].notna() & competitors_df["lng"].notna()
    ].copy()
    if comp.empty:
        return comp

    lat_span = float(reference_df["lat"].max() - reference_df["lat"].min())
    lng_span = float(reference_df["lng"].max() - reference_df["lng"].min())
    padding = max(0.05, min(0.8, max(lat_span, lng_span) * 0.08))

    lat_min = float(reference_df["lat"].min()) - padding
    lat_max = float(reference_df["lat"].max()) + padding
    lng_min = float(reference_df["lng"].min()) - padding
    lng_max = float(reference_df["lng"].max()) + padding

    return comp.loc[
        comp["lat"].between(lat_min, lat_max) & comp["lng"].between(lng_min, lng_max)
    ].copy()


def _filter_ultra_to_reference(
    ultra_df: pd.DataFrame | None,
    reference_df: pd.DataFrame,
) -> pd.DataFrame:
    """Filtra os pins Ultra ao bbox da referencia (mesma logica de padding de
    _build_ultra_icon_layer). Usado por count_pins_in_scope para o caption."""
    if ultra_df is None or ultra_df.empty:
        return pd.DataFrame()
    if reference_df.empty or not {"lat", "lng"} <= set(reference_df.columns):
        return pd.DataFrame()
    if not {"lat", "lng", "nome_unidade"} <= set(ultra_df.columns):
        return pd.DataFrame()

    ultra = ultra_df.loc[ultra_df["lat"].notna() & ultra_df["lng"].notna()].copy()
    if ultra.empty:
        return ultra

    lat_span = float(reference_df["lat"].max() - reference_df["lat"].min())
    lng_span = float(reference_df["lng"].max() - reference_df["lng"].min())
    padding = max(0.05, min(0.8, max(lat_span, lng_span) * 0.08))

    return ultra.loc[
        ultra["lat"].between(
            float(reference_df["lat"].min()) - padding,
            float(reference_df["lat"].max()) + padding,
        )
        & ultra["lng"].between(
            float(reference_df["lng"].min()) - padding,
            float(reference_df["lng"].max()) + padding,
        )
    ].copy()


def count_pins_in_scope(
    competitors_df: pd.DataFrame | None,
    ultra_df: pd.DataFrame | None,
    reference_df: pd.DataFrame,
) -> tuple[int, int]:
    """Conta concorrentes e pins Ultra dentro do recorte (bbox da referencia),
    usando os mesmos filtros dos builders das IconLayers. Determinístico; nao
    depende do retorno dos builders. Camada visual: nao altera score/carteira."""
    n_comp = len(_filter_competitors_to_reference(competitors_df, reference_df))
    n_ultra = len(_filter_ultra_to_reference(ultra_df, reference_df))
    return n_comp, n_ultra


def competitor_cluster_mode(
    selected_ufs: list[str] | None,
    selected_cities: list[str] | None,
    selected_faixas: list[str] | None = None,
) -> bool:
    """Gate puro do clustering de concorrentes (BLK-FIX-07-B): True em recortes
    amplos (Brasil inteiro OU uma unica UF inteira), False assim que ha filtro de
    municipio ou faixa (volta aos pins individuais com logo da Fase A). Decisao
    travada; nao altera score, ranking, carteira nem artefatos M1."""
    return (
        len(selected_ufs or []) <= 1
        and not (selected_cities or [])
        and not (selected_faixas or [])
    )


def pins_amostrados_caption(n_comp: int, n_ultra: int) -> str | None:
    """Retorna uma frase honesta de 'amostrado' SE algum total exceder o cap de
    render (COMPETITOR_PIN_LIMIT/ULTRA_PIN_LIMIT); senao None. Deixa claro que e
    limite de RENDER e NAO afeta score nem carteira (CLAUDE.md §2)."""
    partes: list[str] = []
    if n_comp > COMPETITOR_PIN_LIMIT:
        partes.append(
            f"concorrentes: exibindo os primeiros {COMPETITOR_PIN_LIMIT:,} de {n_comp:,}".replace(",", ".")
        )
    if n_ultra > ULTRA_PIN_LIMIT:
        partes.append(
            f"Ultra: exibindo as primeiras {ULTRA_PIN_LIMIT:,} de {n_ultra:,}".replace(",", ".")
        )
    if not partes:
        return None
    return (
        "Pins amostrados por limite de renderização (" + "; ".join(partes) + "). "
        "Refine o filtro de município para ver todas. "
        "Limite apenas visual: não afeta score, ranking nem carteira."
    )


def _build_competitor_icon_layer(
    competitors_df: pd.DataFrame | None,
    reference_df: pd.DataFrame,
):
    comp = _filter_competitors_to_reference(competitors_df, reference_df)
    if comp.empty:
        return None, comp

    if "rede_label" not in comp.columns:
        comp["rede_label"] = comp["rede"].astype(str)
    for column in ["cidade", "uf", "arquivo_origem"]:
        if column not in comp.columns:
            comp[column] = ""

    # cap duro deterministico (limita o payload da IconLayer independente do total;
    # garante o bound de ~40k concorrentes sem OOM client-side).
    if len(comp) > COMPETITOR_PIN_LIMIT:
        comp = (
            comp.sort_values(["rede_label", "nome_unidade", "lat", "lng"], kind="stable")
            .head(COMPETITOR_PIN_LIMIT)
            .reset_index(drop=True)
        )

    # atlas unico para as redes presentes; cada linha leva so a chave 'rede'
    redes = sorted(comp["rede"].astype(str).unique())
    atlas, mapping = build_icon_atlas(redes)

    comp["rede"] = comp["rede"].astype(str)
    comp["icon_size"] = 34
    comp["tooltip_title"] = (
        comp["rede_label"].map(_clean_tooltip_value).astype(str)
        + ": "
        + comp["nome_unidade"].map(_clean_tooltip_value).astype(str)
    )
    comp["tooltip_line_1"] = "Tipo: Concorrente mapeado"
    comp["tooltip_line_2"] = "Rede: " + comp["rede_label"].astype(str)
    comp["tooltip_line_3"] = _vectorized_cidade_uf_line(comp)
    comp["tooltip_line_4"] = _vectorized_coord_line(comp)
    comp["tooltip_line_5"] = "Fonte: " + comp["arquivo_origem"].astype(str)

    frame = _icon_layer_frame(comp, icon_key_col="rede", n_tooltip_lines=5)

    layer = pdk.Layer(
        "IconLayer",
        data=frame,
        get_icon="rede",
        get_position="[lng, lat]",
        get_size="icon_size",
        size_units="pixels",
        size_scale=1,
        size_min_pixels=24,
        size_max_pixels=42,
        pickable=True,
        billboard=True,
        icon_atlas='"' + atlas + '"',
        icon_mapping=mapping,
    )
    return layer, comp


def _build_competitor_cluster_layer(
    competitors_df: pd.DataFrame | None,
    reference_df: pd.DataFrame,
) -> tuple[pdk.Layer | None, pd.DataFrame]:
    """BLK-FIX-07-B: em recortes amplos (UF inteira / Brasil) agrega concorrentes
    por celula H3 coarse (COMPETITOR_CLUSTER_RES) e renderiza uma bolha de densidade
    por celula (ScatterplotLayer), em vez de cortar pins (Fase A). Bolha dimensionada
    por contagem; tooltip mostra total + breakdown por rede. Camada VISUAL apenas:
    nao recalcula score, ranking, carteira nem altera artefatos M1."""
    comp = _filter_competitors_to_reference(competitors_df, reference_df)
    if comp.empty:
        return None, comp

    import h3

    if "rede_label" not in comp.columns:
        comp["rede_label"] = comp["rede"].astype(str)
    comp["rede_label"] = comp["rede_label"].map(_clean_tooltip_value).astype(str)

    comp["cluster_cell"] = [
        h3.latlng_to_cell(float(lat), float(lng), COMPETITOR_CLUSTER_RES)
        for lat, lng in zip(comp["lat"], comp["lng"], strict=True)
    ]

    total_por_cell = comp.groupby("cluster_cell", sort=False).size()
    rede_counts = comp.groupby(["cluster_cell", "rede_label"], sort=False).size()

    def _breakdown(cell: str) -> str:
        counts = rede_counts.loc[cell].sort_values(ascending=False, kind="stable")
        partes = [
            f"{rede}: {int(n)}"
            for rede, n in counts.head(COMPETITOR_CLUSTER_TOP_REDES).items()
        ]
        extra = len(counts) - COMPETITOR_CLUSTER_TOP_REDES
        if extra > 0:
            partes.append(f"+{extra} redes")
        return "; ".join(partes)

    rows: list[dict[str, Any]] = []
    for cell, total_raw in total_por_cell.items():
        total = int(total_raw)
        cell_lat, cell_lng = h3.cell_to_latlng(cell)
        rows.append(
            {
                "cluster_cell": str(cell),
                "lat": float(cell_lat),
                "lng": float(cell_lng),
                "total": total,
                "breakdown": _breakdown(cell),
            }
        )

    cluster_df = pd.DataFrame(rows)
    if cluster_df.empty:
        return None, cluster_df

    # cap duro deterministico: mantem as celulas mais densas (estavel por total desc,
    # depois cluster_cell). Garante payload << 3MB independente do numero de celulas.
    if len(cluster_df) > COMPETITOR_CLUSTER_LIMIT:
        cluster_df = (
            cluster_df.sort_values(
                ["total", "cluster_cell"], ascending=[False, True], kind="stable"
            )
            .head(COMPETITOR_CLUSTER_LIMIT)
            .reset_index(drop=True)
        )
    else:
        cluster_df = cluster_df.reset_index(drop=True)

    # raio em pixels proporcional a contagem (raiz p/ achatar caudas longas), preso
    # entre 8 e 40 px (mesmo bound do radius_min/max_pixels da layer).
    max_total = int(cluster_df["total"].max())
    if max_total <= 1:
        scaled = pd.Series(8.0, index=cluster_df.index)
    else:
        frac = np.sqrt(cluster_df["total"].astype(float) / float(max_total))
        scaled = 8.0 + frac * (40.0 - 8.0)
    cluster_df["cluster_size"] = scaled.clip(8.0, 40.0).astype(float)

    cluster_df["tooltip_title"] = cluster_df["total"].map(
        lambda t: f"Cluster: {int(t)} concorrentes"
    )
    cluster_df["tooltip_line_1"] = "Densidade de concorrentes (recorte amplo)"
    cluster_df["tooltip_line_2"] = cluster_df["total"].map(lambda t: f"Total: {int(t)}")
    cluster_df["tooltip_line_3"] = cluster_df["breakdown"]

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=cluster_df,
        get_position="[lng, lat]",
        get_radius="cluster_size",
        radius_units="pixels",
        radius_min_pixels=8,
        radius_max_pixels=40,
        get_fill_color=[148, 163, 184, 170],
        get_line_color=[226, 232, 240, 230],
        line_width_min_pixels=1,
        stroked=True,
        filled=True,
        pickable=True,
    )
    return layer, cluster_df


def _competitor_layer_for_scope(
    competitors_df: pd.DataFrame | None,
    reference_df: pd.DataFrame,
    *,
    cluster: bool,
) -> tuple[pdk.Layer | None, pd.DataFrame]:
    """Seletor fino entre a camada de cluster (recorte amplo) e a IconLayer de pins
    individuais (Fase A). Nao altera score, ranking, carteira nem artefatos M1."""
    if cluster:
        return _build_competitor_cluster_layer(competitors_df, reference_df)
    return _build_competitor_icon_layer(competitors_df, reference_df)


def build_cluster_scope_caption(
    n_clusters: int,
    n_comp_total: int,
    *,
    capped: bool = False,
) -> str:
    """Frase honesta do modo cluster: explica que os concorrentes foram agregados em
    bolhas de densidade no recorte amplo e como voltar aos pins individuais. Espelha
    o estilo das demais legendas; camada visual, nao afeta score/ranking/carteira."""
    base = (
        f"Concorrentes agregados em {n_clusters:,} clusters de densidade "
        f"({n_comp_total:,} no recorte). "
        "Selecione um município ou filtro p/ ver pins individuais com logo. "
        "Camada visual: não afeta score, ranking nem carteira."
    ).replace(",", ".")
    if capped:
        base += (
            f" Exibindo as {COMPETITOR_CLUSTER_LIMIT:,} células mais densas "
            "(limite apenas de renderização)."
        ).replace(",", ".")
    return base


def filter_points_to_radius(
    points_df: pd.DataFrame | None,
    lat: float,
    lng: float,
    raio_km: float,
    *,
    required_columns: set[str] | None = None,
) -> pd.DataFrame:
    """Return valid point rows within raio_km of a center coordinate."""
    if points_df is None or points_df.empty:
        return pd.DataFrame()
    required = {"lat", "lng"} | (required_columns or set())
    if not required <= set(points_df.columns):
        return pd.DataFrame()

    points = points_df.loc[points_df["lat"].notna() & points_df["lng"].notna()].copy()
    if points.empty:
        return points

    dists = haversine_km(
        lat,
        pd.to_numeric(points["lat"], errors="coerce").to_numpy(dtype=float),
        lng,
        pd.to_numeric(points["lng"], errors="coerce").to_numpy(dtype=float),
    )
    points["dist_km"] = np.round(dists, 4)
    return points.loc[points["dist_km"] <= raio_km].copy()


def _shared_map_tooltip() -> dict[str, object]:
    return {
        "html": (
            "<b>{tooltip_title}</b><br/>"
            "{tooltip_line_1}<br/>"
            "{tooltip_line_2}<br/>"
            "{tooltip_line_3}<br/>"
            "{tooltip_line_4}<br/>"
            "{tooltip_line_5}<br/>"
            "{tooltip_line_6}<br/>"
            "{tooltip_line_7}<br/>"
            "{tooltip_line_8}<br/>"
            "{tooltip_line_9}<br/>"
            "{tooltip_line_10}<br/>"
            "{tooltip_line_11}<br/>"
            "{tooltip_line_12}<br/>"
            "{tooltip_line_13}<br/>"
            "{tooltip_line_14}"
        ),
        "style": {
            "backgroundColor": "rgba(10, 15, 31, 0.94)",
            "color": COLORS["text"],
            "border": f"1px solid {COLORS['border']}",
            "borderRadius": "10px",
            "fontFamily": "Bahnschrift, Aptos, Segoe UI, sans-serif",
            "fontSize": "13px",
            "padding": "8px 10px",
            "maxWidth": "300px",
            "lineHeight": "1.35",
        },
    }


def _hex_map_tooltip() -> dict[str, object]:
    """Tooltip enxuto (Título + 7 linhas) compartilhado pelos 4 modos de hexágono do Mapa
    Territorial (M1/Híbrido/Censitário/Residual). A linha 6 (renda média domiciliar) foi
    acrescentada e o Residual passou para a linha 7 — ver `_apply_hex_tooltip_fields`."""
    return {
        "html": (
            "<b>{tooltip_title}</b><br/>"
            "{tooltip_line_1}<br/>"
            "{tooltip_line_2}<br/>"
            "{tooltip_line_3}<br/>"
            "{tooltip_line_4}<br/>"
            "{tooltip_line_5}<br/>"
            "{tooltip_line_6}<br/>"
            "{tooltip_line_7}"
        ),
        "style": {
            "backgroundColor": "rgba(10, 15, 31, 0.94)",
            "color": COLORS["text"],
            "border": f"1px solid {COLORS['border']}",
            "borderRadius": "10px",
            "fontFamily": "Bahnschrift, Aptos, Segoe UI, sans-serif",
            "fontSize": "13px",
            "padding": "8px 10px",
            "maxWidth": "300px",
            "lineHeight": "1.35",
        },
    }


# Cor do hex DESCARTADO pelo corte de pop <5k (visivel, alpha 150) — gate humano
# (Felipe, 2026-06-03, BLK-FIX-06-C). Distinta das 10 faixas de RESIDUAL_SCORE_BANDS.
_DISCARDED_FILL = [150, 150, 170, 150]
_DISCARDED_LINE = [170, 170, 190, 200]
# Cor de fallback para hex SEM score (score_* NaN) nos modos operacionais — distinta
# tanto das faixas de score quanto de _DISCARDED_FILL (gate humano, BLK-FIX-06-C).
_NAN_SCORE_FILL = [110, 116, 140, 150]

# Cor do overlay "Vazio competitivo LC" (BLK-TP-03-FU1) — roxo/violeta #7C5CFF
# (COLORS["accent_alt"]), distinto de turquesa Ultra, magenta concorrente/pin,
# ambar Ancoras Dominio e amarelo hex pesquisado. Gate humano: Felipe, 2026-07-15
# (item 1 do gate de UX do handoff do Planner). Preenchimento bem translucido para
# nao esconder a cor de score do hex por baixo; contorno grosso e bem visivel.
_VAZIOS_LC_FILL_RGBA = [124, 92, 255, 60]
_VAZIOS_LC_LINE_RGBA = [124, 92, 255, 230]


def _apply_pop_cut_colors(map_df: pd.DataFrame, *, show_discarded: bool = True) -> pd.DataFrame:
    # BLK-FIX-11 (overlay descartados_5k): quando o overlay esta desligado
    # (show_discarded=False), nao aplica o cinza _DISCARDED_FILL; os hexes <5k
    # permanecem visiveis com a cor de score normal (DV-3, aprovado por Felipe
    # em 2026-06-10). READ-ONLY sobre o M1.
    if not show_discarded:
        return map_df
    if "flag_pop_min_5k" not in map_df.columns:
        return map_df
    discarded = ~map_df["flag_pop_min_5k"].fillna(True)
    if not discarded.any():
        return map_df
    map_df["fill_color"] = [
        _DISCARDED_FILL if d else c
        for d, c in zip(discarded, map_df["fill_color"], strict=False)
    ]
    map_df["line_color"] = [
        _DISCARDED_LINE if d else c
        for d, c in zip(discarded, map_df["line_color"], strict=False)
    ]
    return map_df


def render_pop_cut_legend() -> None:
    st.markdown(
        "<div class='legend-row'>"
        "<span class='legend-chip'>"
        "<span class='legend-dot' style='background:#9696AA;opacity:0.59;'></span>"
        "Descartado &lt;5k hab (mapa)"
        "</span></div>",
        unsafe_allow_html=True,
    )


def render_ancoras_dominio_legend() -> None:
    # BLK-FIX-11: legenda do overlay ancoras_dominio (ambar #F59E0B alinhado ao
    # ScatterplotLayer [245, 158, 11, 220]). DV-4, aprovado por Felipe 2026-06-10.
    st.markdown(
        "<div class='legend-row'>"
        "<span class='legend-chip'>"
        "<span class='legend-dot' style='background:#F59E0B;opacity:0.86;'></span>"
        "Âncora Domínio"
        "</span></div>",
        unsafe_allow_html=True,
    )


def render_vazios_competitivos_legend() -> None:
    # BLK-TP-03-FU1: legenda do overlay vazios_competitivos_lc (roxo #7C5CFF,
    # alinhado ao H3HexagonLayer [124, 92, 255, 60]/[124, 92, 255, 230]). Gate
    # humano: Felipe, 2026-07-15.
    st.markdown(
        "<div class='legend-row'>"
        "<span class='legend-chip'>"
        "<span class='legend-dot' style='background:#7C5CFF;opacity:0.86;'></span>"
        "Vazio competitivo LC"
        "</span></div>",
        unsafe_allow_html=True,
    )


def render_residual_legend(df: pd.DataFrame | None = None) -> None:
    if df is not None and (
        df.empty or "oferta_efetiva_disponivel" not in df.columns
    ):
        return
    st.markdown(
        "<div class='legend-row'>"
        "<span class='legend-chip'>"
        "<span class='legend-dot' style='background:#22C55E;opacity:0.85;'></span>"
        "Oferta residual: leitura auxiliar absoluta"
        "</span>"
        "<span class='legend-chip'>Quartis: apoio visual, não ranking oficial</span>"
        "</div>",
        unsafe_allow_html=True,
    )


def render_residual_score_legend() -> None:
    render_score_bands_legend("Score Residual")


def render_score_bands_legend(mode_label: str = "Score") -> None:
    """Renders the canonical 10-band (0-10, 10-20, …, 90-100) score legend.

    mode_label names the active score, e.g. 'Score M1 (score_priorizacao)'.
    """
    chips = "".join(
        f"<span class='legend-chip'><span class='legend-dot' style='background:{color};'></span>{label}</span>"
        for label, color in RESIDUAL_SCORE_BANDS
    )
    st.markdown(
        f"<div class='legend-row'><strong style='color:#A7B3D1;margin-right:6px;font-size:0.75rem;'>{mode_label}:</strong>{chips}</div>",
        unsafe_allow_html=True,
    )


def _search_hex_payload(hex_id: str, tooltip_source: pd.DataFrame | None = None) -> pd.DataFrame:
    tooltip_columns = ["tooltip_title"] + [f"tooltip_line_{i}" for i in range(1, 15)]
    if tooltip_source is not None and not tooltip_source.empty and "hex_id" in tooltip_source.columns:
        source = tooltip_source.loc[tooltip_source["hex_id"].astype(str) == str(hex_id)].head(1).copy()
        if not source.empty and "tooltip_title" in source.columns:
            for column in tooltip_columns:
                if column not in source.columns:
                    source[column] = ""
            return source[["hex_id", *tooltip_columns]]

    return pd.DataFrame([{
        "hex_id": hex_id,
        "tooltip_title": f"Hex pesquisado: {hex_id}",
        "tooltip_line_1": "Destaque de busca por coordenada",
        **{f"tooltip_line_{i}": "" for i in range(2, 15)},
    }])


def _build_search_hex_layer(hex_id: str, tooltip_source: pd.DataFrame | None = None):
    hex_df = _search_hex_payload(hex_id, tooltip_source)
    return pdk.Layer(
        "H3HexagonLayer",
        data=hex_df,
        get_hexagon="hex_id",
        get_fill_color=[255, 230, 0, 50],
        get_line_color=[255, 230, 0, 240],
        filled=True,
        stroked=True,
        extruded=False,
        pickable=True,
        line_width_min_pixels=3,
        opacity=1.0,
    )


def _build_search_pin_layer(lat: float, lng: float):
    pin_df = pd.DataFrame([{
        "lat": lat,
        "lng": lng,
        "tooltip_title": "Coordenada pesquisada",
        "tooltip_line_1": f"Lat: {lat:.5f}",
        "tooltip_line_2": f"Lng: {lng:.5f}",
        **{f"tooltip_line_{i}": "" for i in range(3, 15)},
    }])
    return pdk.Layer(
        "ScatterplotLayer",
        data=pin_df,
        get_position="[lng, lat]",
        get_radius=300,
        radius_min_pixels=10,
        radius_max_pixels=22,
        get_fill_color=[255, 230, 0, 230],
        get_line_color=[0, 0, 0, 200],
        line_width_min_pixels=2,
        stroked=True,
        filled=True,
        pickable=True,
    )


def _build_ancoras_dominio_layer(
    dominio_df: pd.DataFrame | None,
    selected_ufs: list[str],
    selected_cities: list[str],
) -> pdk.Layer | None:
    """Camada de ancoras de dominio (overlay ancoras_dominio do Mapa Territorial).

    Marca os hexes do plano de dominio com um ScatterplotLayer ambar
    [245, 158, 11, 220] (DV-1/DV-2, aprovado por Felipe em 2026-06-10).
    No-op silencioso (retorna None) quando dominio_df e None/vazio ou nao tem as
    colunas minimas {lat, lng, hex_id}. READ-ONLY sobre o M1: nao recalcula score
    nem altera artefatos oficiais."""
    if dominio_df is None or dominio_df.empty:
        return None
    if not {"lat", "lng", "hex_id"} <= set(dominio_df.columns):
        return None

    dom = dominio_df.copy()
    if selected_ufs and "uf" in dom.columns:
        dom = dom[dom["uf"].isin(selected_ufs)]
    if selected_cities:
        city_col = "nome_municipio" if "nome_municipio" in dom.columns else None
        if city_col is not None:
            dom = dom[dom[city_col].isin(selected_cities)]
    dom = dom.loc[dom["lat"].notna() & dom["lng"].notna()]
    if dom.empty:
        return None

    # Tooltip minimo compativel com _shared_map_tooltip (tooltip_title +
    # tooltip_line_1..14); colunas nao usadas ficam vazias para nao quebrar o html.
    layer_df = dom[["lat", "lng", "hex_id"]].copy().reset_index(drop=True)
    layer_df["tooltip_title"] = "Âncora Domínio: " + layer_df["hex_id"].astype(str)
    for i in range(1, 15):
        layer_df[f"tooltip_line_{i}"] = ""
    return pdk.Layer(
        "ScatterplotLayer",
        data=layer_df,
        get_position="[lng, lat]",
        get_radius=250,
        radius_min_pixels=8,
        radius_max_pixels=20,
        get_fill_color=[245, 158, 11, 220],
        get_line_color=[255, 255, 255, 200],
        line_width_min_pixels=2,
        stroked=True,
        filled=True,
        pickable=True,
    )


def _build_vazios_competitivos_layer(vazios_df: pd.DataFrame | None) -> pdk.Layer | None:
    """Camada de destaque dos hexes de vazio competitivo do concorrente low-cost.

    Overlay `vazios_competitivos_lc` do Mapa Territorial (BLK-TP-03-FU1). Consome o
    parquet `data/staging/vazios_competitivos_lc.parquet` (229 hexes, contrato
    `vazios_competitivos_v1`, BLK-TP-03) ja materializado — READ-ONLY sobre o M1:
    nenhuma coluna de score e recalculada aqui, apenas lida/formatada para exibicao
    (`score_priorizacao` no tooltip). No-op silencioso (retorna None) quando
    `vazios_df` e None/vazio ou nao tem `hex_id` — nunca lanca excecao.

    H3HexagonLayer roxo `#7C5CFF` (gate humano: Felipe, 2026-07-15), preenchimento
    bem translucido para nao esconder a cor de score do hex por baixo.
    """
    if vazios_df is None or vazios_df.empty:
        return None
    if "hex_id" not in vazios_df.columns:
        return None

    vazios = vazios_df.drop_duplicates(subset=["hex_id"], keep="first").copy()
    if vazios.empty:
        return None

    n = len(vazios)
    membros_gt5km = pd.to_numeric(
        vazios.get("membros_gt5km_concorrente_lc", pd.Series([pd.NA] * n, index=vazios.index)),
        errors="coerce",
    )
    uf = vazios.get("uf", pd.Series([pd.NA] * n, index=vazios.index)).map(_clean_tooltip_value)
    nome_municipio = vazios.get(
        "nome_municipio", pd.Series([pd.NA] * n, index=vazios.index)
    ).map(_clean_tooltip_value)
    score_priorizacao = pd.to_numeric(
        vazios.get("score_priorizacao", pd.Series([pd.NA] * n, index=vazios.index)),
        errors="coerce",
    )

    layer_df = vazios[["hex_id"]].copy().reset_index(drop=True)
    layer_df["tooltip_title"] = "Vazio competitivo LC: " + layer_df["hex_id"].astype(str)
    layer_df["tooltip_line_1"] = (
        "Membros >5km do concorrente: "
        + membros_gt5km.reset_index(drop=True).map(lambda v: format_int(v) if pd.notna(v) else "-")
    )
    layer_df["tooltip_line_2"] = "UF: " + uf.reset_index(drop=True).astype(str)
    layer_df["tooltip_line_3"] = "Município: " + nome_municipio.reset_index(drop=True).astype(str)
    layer_df["tooltip_line_4"] = "Score M1: " + score_priorizacao.reset_index(drop=True).map(format_score)
    for i in range(5, 15):
        layer_df[f"tooltip_line_{i}"] = ""

    return pdk.Layer(
        "H3HexagonLayer",
        data=layer_df,
        get_hexagon="hex_id",
        get_fill_color=_VAZIOS_LC_FILL_RGBA,
        get_line_color=_VAZIOS_LC_LINE_RGBA,
        filled=True,
        stroked=True,
        extruded=False,
        pickable=True,
        line_width_min_pixels=3,
        opacity=0.9,
    )


def _downsample_map_index(
    key_df: pd.DataFrame,
    *,
    sort_columns: list[str],
    ascending: list[bool],
    limit: int = MAP_POINT_LIMIT,
    dedup_column: str | None = None,
) -> pd.Index:
    """Indice das ate `limit` linhas de maior prioridade da fonte do mapa.

    Calculado sobre uma projecao leve (apenas chaves de ordenacao/granularidade)
    ANTES de materializar todas as colunas do mapa. Mantem o cap MAP_POINT_LIMIT
    identico ao fluxo anterior — mesma chave de ordenacao, mesmo dedup e mesmo
    head — apenas evita copiar todas as colunas das UFs grandes (ex.: AM 293k)
    so para descartar o excedente. Nao altera score nem artefatos oficiais.
    """
    ordered = key_df
    present_sort = [column for column in sort_columns if column in ordered.columns]
    if present_sort:
        asc = [ascending[sort_columns.index(column)] for column in present_sort]
        ordered = ordered.sort_values(present_sort, ascending=asc, kind="stable")
    if dedup_column is not None and dedup_column in ordered.columns:
        ordered = ordered.drop_duplicates(subset=[dedup_column], keep="first")
    return ordered.head(limit).index


# Colunas que o H3HexagonLayer/tooltip do pydeck realmente consomem. As demais
# (auxiliares *_fmt/*_label/tooltip_residual_*, colunas-fonte) sao insumo
# intermediario e NAO entram no payload serializado ao frontend (corrige
# MessageSizeError em UFs grandes). Nao recalcula score nem altera artefatos M1.
_DECK_RENDER_COLUMNS = ("hex_id", "fill_color", "line_color")


def _deck_layer_frame(map_df: pd.DataFrame) -> pd.DataFrame:
    """Projeta map_df para SOMENTE as colunas consumidas pelo H3HexagonLayer
    (hex_id/fill_color/line_color) + as colunas de tooltip (tooltip_title,
    tooltip_line_*) realmente presentes. Nao muta map_df (o df completo segue
    alimentando busca por hex, pins e resolve_map_view). Nao recalcula score."""
    tooltip_cols = [
        c
        for c in map_df.columns
        if c == "tooltip_title" or c.startswith("tooltip_line_")
    ]
    keep = [c for c in (*_DECK_RENDER_COLUMNS, *tooltip_cols) if c in map_df.columns]
    # dedup preservando ordem
    seen: set[str] = set()
    ordered: list[str] = []
    for c in keep:
        if c not in seen:
            seen.add(c)
            ordered.append(c)
    return map_df.loc[:, ordered].copy()


# Colunas minimas que a IconLayer de pins (concorrentes/Ultra) serializa ao
# frontend (BLK-FIX-07 Fase A). Reduz o payload por linha: sem o dict de data-URI
# (substituido pelo atlas) e sem os campos vazios tooltip_line_6..14 (o template
# compartilhado renderiza vazio para chave ausente). Nao recalcula score.
_ICON_RENDER_COLUMNS = ("lng", "lat", "icon_size", "tooltip_title")


def _icon_layer_frame(
    df: pd.DataFrame, *, icon_key_col: str, n_tooltip_lines: int
) -> pd.DataFrame:
    """Projeta o frame de pins para SOMENTE as colunas consumidas pela IconLayer:
    chave de icone (`icon_key_col`), posicao (lng/lat), tamanho (icon_size),
    tooltip_title e tooltip_line_1..n REALMENTE preenchidos. Analogo a
    `_deck_layer_frame`; remove a data-URI por linha e os campos de tooltip vazios.
    Nao muta o df de origem. Nao recalcula score nem altera artefatos M1."""
    tooltip_cols = [
        f"tooltip_line_{i}"
        for i in range(1, n_tooltip_lines + 1)
    ]
    keep = [
        c
        for c in (icon_key_col, *_ICON_RENDER_COLUMNS, *tooltip_cols)
        if c in df.columns
    ]
    seen: set[str] = set()
    ordered: list[str] = []
    for c in keep:
        if c not in seen:
            seen.add(c)
            ordered.append(c)
    return df.loc[:, ordered].copy()


def build_map_figure(
    df: pd.DataFrame,
    *,
    selected_ufs: list[str],
    selected_cities: list[str],
    competitors_df: pd.DataFrame | None = None,
    ultra_df: pd.DataFrame | None = None,
    search_pin: tuple[float, float] | None = None,
    search_hex_id: str | None = None,
    cluster_competitors: bool = False,
    show_discarded: bool = True,
):
    present_columns = [column for column in MAP_SOURCE_COLUMNS_M1 if column in df.columns]

    scope = (
        df["hex_id"].notna()
        & df["lat"].notna()
        & df["lng"].notna()
        & df["score_priorizacao"].notna()
    )
    if selected_ufs:
        scope = scope & df["uf"].isin(selected_ufs)
    if selected_cities:
        if "nome_municipio" in df.columns:
            nome_municipio = (
                df["nome_municipio"].fillna(df["cidade"]) if "cidade" in df.columns else df["nome_municipio"]
            )
        elif "cidade" in df.columns:
            nome_municipio = df["cidade"]
        else:
            nome_municipio = pd.Series(pd.NA, index=df.index)
        scope = scope & nome_municipio.isin(selected_cities)
    if not bool(scope.any()):
        return None, 0

    # Projeção leve (chaves de granularidade + ordenação) para fazer o downsample
    # antes do cap: as colunas completas do mapa só são copiadas para os ≤MAP_POINT_LIMIT
    # sobreviventes, em vez de todo o slice da UF.
    key_columns = [
        column
        for column in [
            "hex_id",
            "uf",
            "qualidade_join_uf",
            "flag_censo_disponivel",
            "score_setor_2022_calibrado",
            *MAP_SORT_COLUMNS,
        ]
        if column in df.columns
    ]
    key = df.loc[scope, key_columns].copy()

    quality = _normalized_join_quality(key)
    has_censo = _has_censo_signal(key)
    granular_ufs = set(key.loc[quality.isin(["A", "B"]) & has_censo, "uf"].dropna().tolist())
    # BLK-FIX-06-C-FU (display; aprovado por Felipe em 2026-06-03): NAO descartar hexes
    # validos do M1 (ja no scope: score_priorizacao.notna()) so por nao terem setor
    # censitario numa UF granular. A orla costeira e as margens de agua recuperadas no
    # BLK-FIX-06-B (ex.: Praia Grande/Mongagua, score 78-100, sobre agua sem setor IBGE)
    # caiam exatamente aqui: o filtro antigo `key.loc[granular_rows | municipal_rows]`
    # removia `uf in granular_ufs & ~has_censo`, sumindo a orla do mapa executivo M1.
    # Agora granular/municipal e so ROTULO de confianca (confianca_geografica/line_color
    # abaixo), nao filtro de exibicao. Nao recalcula score nem altera artefatos M1.
    if key.empty:
        return None, 0

    # Cap efetivo dinamico: recortes que saturam MAP_POINT_LIMIT (UFs grandes:
    # SP/AM/PA/MT/MG/BA) caem no cap reduzido p/ mitigar OOM client-side; recortes
    # com <= MAP_POINT_LIMIT linhas ficam byte-identicos ao comportamento anterior.
    effective_limit = MAP_POINT_LIMIT_LARGE if len(key) > MAP_POINT_LIMIT else MAP_POINT_LIMIT
    survive_index = _downsample_map_index(
        key,
        sort_columns=MAP_SORT_COLUMNS,
        ascending=MAP_SORT_ASCENDING,
        limit=effective_limit,
        dedup_column="hex_id",
    )

    map_df = df.loc[survive_index, present_columns].copy().reset_index(drop=True)
    if "nome_municipio" not in map_df.columns:
        map_df["nome_municipio"] = map_df["cidade"]
    else:
        map_df["nome_municipio"] = map_df["nome_municipio"].fillna(map_df["cidade"])

    # Rotulo de confianca: granular SO quando a UF e granular E a linha tem censo. Hexes
    # sem censo (orla/margens de agua) numa UF granular ficam "municipal" (borda ambar,
    # confianca menor) em vez de descartados. Calculado sobre o slice sobrevivente
    # completo (df.loc[survive_index] tem as colunas de censo, alinhado posicionalmente).
    _survive_slice = df.loc[survive_index]
    map_df["confianca_geografica"] = np.where(
        _survive_slice["uf"].isin(granular_ufs).to_numpy()
        & _has_censo_signal(_survive_slice).to_numpy(),
        "granular",
        "municipal",
    )

    map_df = _prepare_m1_tooltip_fields(map_df)
    map_df["fill_color"] = map_df["score_priorizacao"].map(score_band_to_color)
    map_df["line_color"] = map_df["confianca_geografica"].map(
        {
            "granular": hex_to_rgba(COLORS["map_line"], 122),
            "municipal": [245, 158, 11, 220],
        }
    )
    map_df = _apply_pop_cut_colors(map_df, show_discarded=show_discarded)
    map_df = _apply_hex_tooltip_fields(map_df, mode="m1", show_discarded=show_discarded)
    search_tooltip_source = None
    if search_hex_id is not None:
        search_source = df.loc[
            df["hex_id"].astype(str) == str(search_hex_id),
            present_columns,
        ].copy()
        if not search_source.empty:
            search_source = search_source.drop_duplicates(subset=["hex_id"], keep="first")
            search_tooltip_source = _apply_hex_tooltip_fields(
                _prepare_m1_tooltip_fields(search_source),
                mode="m1",
                show_discarded=show_discarded,
            )
    center, zoom = resolve_map_view(
        map_df,
        selected_ufs=selected_ufs,
        selected_cities=selected_cities,
    )

    # Simplificacao enxuta da camada SO no cap reduzido (UF grande): desliga
    # highlight/contorno p/ cortar vertices e custo de GPU. Cor de fill INALTERADA
    # (score_band_to_color). Em cap cheio mantem parametros identicos aos atuais.
    _stroked = effective_limit == MAP_POINT_LIMIT
    _auto_highlight = effective_limit == MAP_POINT_LIMIT
    layer_df = _deck_layer_frame(map_df)
    _hex_layer_kwargs: dict[str, Any] = dict(
        get_hexagon="hex_id",
        get_fill_color="fill_color",
        get_line_color="line_color",
        filled=True,
        stroked=_stroked,
        extruded=False,
        pickable=True,
        auto_highlight=_auto_highlight,
        highlight_color=[255, 255, 255, 42],
        opacity=0.78,
    )
    if _stroked:
        _hex_layer_kwargs["line_width_min_pixels"] = 1
    hex_layer = pdk.Layer("H3HexagonLayer", data=layer_df, **_hex_layer_kwargs)
    competitor_layer, _ = _competitor_layer_for_scope(
        competitors_df, map_df, cluster=cluster_competitors
    )
    ultra_layer = _build_ultra_icon_layer(ultra_df, map_df)
    layers = [hex_layer]
    if competitor_layer is not None:
        layers.append(competitor_layer)
    if ultra_layer is not None:
        layers.append(ultra_layer)
    if search_pin is not None:
        layers.append(_build_search_pin_layer(*search_pin))
        center = {"lat": search_pin[0], "lon": search_pin[1]}
        zoom = 10.0
    if search_hex_id is not None:
        layers.append(_build_search_hex_layer(search_hex_id, search_tooltip_source))

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
        layers=layers,
        tooltip=_hex_map_tooltip(),
    )
    # FU1: corte real = len(key) > effective_limit (nao a heuristica n_points>=cap,
    # que mentia na janela 18k-34.999 em UF grande). Propaga sem mudar a assinatura.
    deck._ultra_capped = len(key) > effective_limit
    deck._ultra_effective_cap = effective_limit
    return deck, len(map_df)


def build_ultra_presence_map(
    ultra_df: pd.DataFrame | None,
    *,
    selected_ufs: list[str],
    selected_cities: list[str],
):
    if ultra_df is None or ultra_df.empty:
        return None, 0
    if not {"lat", "lng", "nome_unidade"} <= set(ultra_df.columns):
        return None, 0

    ultra = ultra_df.loc[ultra_df["lat"].notna() & ultra_df["lng"].notna()].copy()
    if ultra.empty:
        return None, 0

    if selected_ufs and "uf" in ultra.columns:
        ultra = ultra.loc[ultra["uf"].isin(selected_ufs)]
    if selected_cities and "cidade" in ultra.columns:
        ultra = ultra.loc[ultra["cidade"].isin(selected_cities)]
    if ultra.empty:
        return None, 0

    # Layer via helper compartilhado (atlas + payload enxuto + cap duro). O
    # center/zoom local da Visao Executiva e calculado a partir do frame filtrado
    # (preservado abaixo), independente do cap interno do payload.
    icon_layer = _ultra_icon_layer_from_frame(ultra.copy())
    if icon_layer is None:
        return None, 0

    if selected_cities or len(selected_ufs) == 1:
        center = {"lat": float(ultra["lat"].mean()), "lon": float(ultra["lng"].mean())}
        zoom = 7.2 if not selected_cities else 9.0
    elif selected_ufs:
        center = {"lat": float(ultra["lat"].mean()), "lon": float(ultra["lng"].mean())}
        zoom = 4.5
    else:
        center = BRASIL_CENTER
        zoom = 3.8

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
        layers=[icon_layer],
        tooltip=_shared_map_tooltip(),
    )
    return deck, len(ultra)


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
    color_col: str = "score_expansao_hibrido",
    competitors_df: pd.DataFrame | None = None,
    ultra_df: pd.DataFrame | None = None,
    search_pin: tuple[float, float] | None = None,
    search_hex_id: str | None = None,
    cluster_competitors: bool = False,
    show_discarded: bool = True,
):
    if "score_setor_2022_calibrado" not in hdf.columns:
        return None, 0

    present_columns = [column for column in MAP_SOURCE_COLUMNS_HYBRID if column in hdf.columns]

    # Scope relaxado (BLK-FIX-06-C): exige só geometria valida, NAO setor censitario.
    # A orla costeira (sem setor censitario, score_* NaN) deixa de sumir do mapa; o
    # guard de COLUNA ausente acima (return None, 0) e preservado.
    scope = (
        hdf["hex_id"].notna()
        & hdf["lat"].notna()
        & hdf["lng"].notna()
    )
    if selected_ufs:
        scope = scope & hdf["uf"].isin(selected_ufs)
    if selected_cities:
        city_col = "nome_municipio" if "nome_municipio" in hdf.columns else "uf"
        scope = scope & hdf[city_col].isin(selected_cities)
    if not bool(scope.any()):
        return None, 0

    # Projeção leve para o downsample antes do cap: ordena/filtra pela faixa nas
    # chaves e materializa as colunas completas só para os ≤MAP_POINT_LIMIT sobreviventes.
    _HYBRID_SORT = ["top_hex_intraurbano", "top_oportunidade_municipio", "score_expansao_hibrido", "score_setor_2022_calibrado"]
    key_columns = [
        column
        for column in ["hex_id", "uf", *_HYBRID_SORT]
        if column in hdf.columns
    ]
    key = hdf.loc[scope, key_columns].copy()

    if selected_faixas:
        _faixa_hibrida = _derivar_faixa_hibrida(key)
        key = key.loc[_faixa_hibrida.isin(selected_faixas)]
    if key.empty:
        return None, 0

    effective_limit = MAP_POINT_LIMIT_LARGE if len(key) > MAP_POINT_LIMIT else MAP_POINT_LIMIT
    survive_index = _downsample_map_index(
        key,
        sort_columns=_HYBRID_SORT,
        ascending=[False, False, False, False],
        limit=effective_limit,
    )

    map_df = hdf.loc[survive_index, present_columns].copy().reset_index(drop=True)

    _color_src = map_df[color_col] if color_col in map_df.columns else pd.Series(pd.NA, index=map_df.index)
    map_df["fill_color"] = _color_src.map(score_band_to_color)
    # Fallback de score NaN (BLK-FIX-06-C): hex sem setor censitario (score_* NaN)
    # recebe cor visivel distinta em vez do cinza alpha-70 de score_band_to_color.
    # Atribuicao linha-a-linha p/ preservar lista RGBA por celula (padrao de
    # _apply_pop_cut_colors). Roda ANTES de _apply_pop_cut_colors: um hex NaN+pop<5k
    # termina com a cor de "descartado <5k" (precedencia de produto).
    _nan_color_mask = _color_src.isna()
    if _nan_color_mask.any():
        map_df["fill_color"] = [
            list(_NAN_SCORE_FILL) if nan else c
            for nan, c in zip(_nan_color_mask, map_df["fill_color"], strict=False)
        ]
    _restrito = map_df["flag_join_uf_restrito"].fillna(False).astype(bool) if "flag_join_uf_restrito" in map_df.columns else pd.Series(False, index=map_df.index)
    _quality_c = _normalized_join_quality(map_df) == "C"
    _outlier = map_df["flag_outlier_espacial"].fillna(False).astype(bool) if "flag_outlier_espacial" in map_df.columns else pd.Series(False, index=map_df.index)
    _default_line = hex_to_rgba(COLORS["map_line"], 100)
    map_df["line_color"] = [
        [255, 90, 107, 220] if (r or q) else ([245, 158, 11, 220] if o else _default_line)
        for r, q, o in zip(_restrito, _quality_c, _outlier, strict=False)
    ]
    map_df["score_censo_fmt"] = map_df["score_setor_2022_calibrado"].map(format_score)
    map_df["score_hibrido_fmt"] = map_df["score_expansao_hibrido"].map(format_score)
    if "faixa_oportunidade" not in map_df.columns:
        map_df["faixa_oportunidade"] = pd.NA
    map_df["faixa_label"] = _compute_faixa_label(map_df["faixa_oportunidade"])
    _na_float_h = pd.Series(pd.NA, index=map_df.index, dtype="Float64")
    # Fallback municipal: preferir pop_total (população total) sobre populacao_proxy legado (18-45).
    pop_municipal_h = map_df.get("pop_total", map_df.get("populacao_proxy", _na_float_h))
    has_setor_pop_h = "pop_total_setor_2022" in map_df.columns and map_df["pop_total_setor_2022"].notna().any()
    if has_setor_pop_h:
        use_setor_pop_h = map_df["pop_total_setor_2022"].notna()
        pop_val_h = map_df["pop_total_setor_2022"].where(use_setor_pop_h, pop_municipal_h)
        pop_suffix_h = np.where(use_setor_pop_h, "", " (municipal)")
    else:
        pop_val_h = pop_municipal_h
        pop_suffix_h = np.full(len(map_df), " (municipal)")
    map_df["pop_fmt"] = pop_val_h.map(lambda v: format_int(v) if pd.notna(v) else "-") + pop_suffix_h
    has_setor_renda_h = "renda_per_capita_setor_2022_calibrada" in map_df.columns and map_df["renda_per_capita_setor_2022_calibrada"].notna().any()
    if has_setor_renda_h:
        use_setor_renda_h = map_df["renda_per_capita_setor_2022_calibrada"].notna()
        renda_val_h = map_df["renda_per_capita_setor_2022_calibrada"].where(use_setor_renda_h, map_df.get("renda_per_capita", _na_float_h))
        renda_suffix_h = np.where(use_setor_renda_h, "", " (municipal)")
    else:
        renda_val_h = map_df.get("renda_per_capita", _na_float_h)
        renda_suffix_h = np.full(len(map_df), " (municipal)")
    map_df["renda_fmt"] = renda_val_h.map(lambda v: format_int(v) if pd.notna(v) else "-") + renda_suffix_h
    map_df = _apply_pop_cut_colors(map_df, show_discarded=show_discarded)
    _active_mode = "censitario" if color_col == "score_setor_2022_calibrado" else "hibrido"
    map_df = _apply_hex_tooltip_fields(map_df, mode=_active_mode, show_discarded=show_discarded)
    search_tooltip_source = None
    if search_hex_id is not None:
        search_source = hdf.loc[
            hdf["hex_id"].astype(str) == str(search_hex_id),
            present_columns,
        ].copy()
        if not search_source.empty:
            search_source = search_source.drop_duplicates(subset=["hex_id"], keep="first")
            search_tooltip_source = _apply_hex_tooltip_fields(
                _prepare_hybrid_tooltip_fields(search_source),
                mode=_active_mode,
                show_discarded=show_discarded,
            )

    center, zoom = resolve_map_view(map_df, selected_ufs=selected_ufs, selected_cities=selected_cities)

    # Simplificacao enxuta SO no cap reduzido (UF grande); cor de fill inalterada.
    _stroked = effective_limit == MAP_POINT_LIMIT
    _auto_highlight = effective_limit == MAP_POINT_LIMIT
    layer_df = _deck_layer_frame(map_df)
    _hex_layer_kwargs: dict[str, Any] = dict(
        get_hexagon="hex_id",
        get_fill_color="fill_color",
        get_line_color="line_color",
        filled=True,
        stroked=_stroked,
        extruded=False,
        pickable=True,
        auto_highlight=_auto_highlight,
        highlight_color=[255, 255, 255, 60],
        opacity=0.85,
    )
    if _stroked:
        _hex_layer_kwargs["line_width_min_pixels"] = 1
    hex_layer = pdk.Layer("H3HexagonLayer", data=layer_df, **_hex_layer_kwargs)
    competitor_layer, _ = _competitor_layer_for_scope(
        competitors_df, map_df, cluster=cluster_competitors
    )
    ultra_layer = _build_ultra_icon_layer(ultra_df, map_df)
    layers = [hex_layer]
    if competitor_layer is not None:
        layers.append(competitor_layer)
    if ultra_layer is not None:
        layers.append(ultra_layer)
    if search_pin is not None:
        layers.append(_build_search_pin_layer(*search_pin))
        center = {"lat": search_pin[0], "lon": search_pin[1]}
        zoom = 10.0
    if search_hex_id is not None:
        layers.append(_build_search_hex_layer(search_hex_id, search_tooltip_source))

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
        layers=layers,
        tooltip=_hex_map_tooltip(),
    )
    # FU1: corte real do cap propagado para o caption honesto (vide build_map_figure).
    deck._ultra_capped = len(key) > effective_limit
    deck._ultra_effective_cap = effective_limit
    return deck, len(map_df)


def build_residual_heatmap_figure(
    hdf: pd.DataFrame,
    *,
    selected_ufs: list[str],
    selected_cities: list[str],
    competitors_df: pd.DataFrame | None = None,
    ultra_df: pd.DataFrame | None = None,
    search_pin: tuple[float, float] | None = None,
    search_hex_id: str | None = None,
    cluster_competitors: bool = False,
    show_discarded: bool = True,
):
    if "score_setor_2022_calibrado" not in hdf.columns:
        return None, 0

    present_columns = [column for column in MAP_SOURCE_COLUMNS_HYBRID if column in hdf.columns]

    # Scope relaxado (BLK-FIX-06-C): exige só geometria valida, NAO setor censitario.
    # A orla costeira (score_oportunidade_residual NaN) deixa de sumir do residual; o
    # guard de COLUNA ausente acima (return None, 0) e preservado.
    scope = (
        hdf["hex_id"].notna()
        & hdf["lat"].notna()
        & hdf["lng"].notna()
    )
    if selected_ufs:
        scope = scope & hdf["uf"].isin(selected_ufs)
    if selected_cities:
        city_col = "nome_municipio" if "nome_municipio" in hdf.columns else "uf"
        scope = scope & hdf[city_col].isin(selected_cities)
    if not bool(scope.any()):
        return None, 0

    # Downsample antes do cap: ordena pelo residual nas chaves leves e copia as
    # colunas completas só para os ≤MAP_POINT_LIMIT sobreviventes.
    key_columns = [
        column for column in ["hex_id", "uf", "score_oportunidade_residual"] if column in hdf.columns
    ]
    key = hdf.loc[scope, key_columns].copy()
    effective_limit = MAP_POINT_LIMIT_LARGE if len(key) > MAP_POINT_LIMIT else MAP_POINT_LIMIT
    survive_index = _downsample_map_index(
        key,
        sort_columns=["score_oportunidade_residual"],
        ascending=[False],
        limit=effective_limit,
    )
    map_df = hdf.loc[survive_index, present_columns].copy().reset_index(drop=True)

    # Fallback de score NaN (BLK-FIX-06-C): coluna ausente OU valor NaN (orla sem
    # residual) recebe a cor visivel _NAN_SCORE_FILL em vez do cinza alpha-70.
    # Atribuicao linha-a-linha p/ preservar lista RGBA por celula. Roda ANTES de
    # _apply_pop_cut_colors: um hex NaN+pop<5k termina com a cor de "descartado <5k".
    if "score_oportunidade_residual" in map_df.columns:
        _residual_src = map_df["score_oportunidade_residual"]
        map_df["fill_color"] = _residual_src.map(score_band_to_color)
        _nan_color_mask = _residual_src.isna()
        if _nan_color_mask.any():
            map_df["fill_color"] = [
                list(_NAN_SCORE_FILL) if nan else c
                for nan, c in zip(_nan_color_mask, map_df["fill_color"], strict=False)
            ]
    else:
        map_df["fill_color"] = [list(_NAN_SCORE_FILL) for _ in range(len(map_df))]
    _restrito = map_df["flag_join_uf_restrito"].fillna(False).astype(bool) if "flag_join_uf_restrito" in map_df.columns else pd.Series(False, index=map_df.index)
    _quality_c = _normalized_join_quality(map_df) == "C"
    _default_line = hex_to_rgba(COLORS["map_line"], 100)
    map_df["line_color"] = [
        [255, 90, 107, 220] if (r or q) else _default_line
        for r, q in zip(_restrito, _quality_c, strict=False)
    ]
    map_df = _prepare_hybrid_tooltip_fields(map_df)
    map_df = _apply_pop_cut_colors(map_df, show_discarded=show_discarded)
    map_df = _apply_hex_tooltip_fields(map_df, mode="residual", show_discarded=show_discarded)

    search_tooltip_source = None
    if search_hex_id is not None:
        search_source = hdf.loc[
            hdf["hex_id"].astype(str) == str(search_hex_id),
            present_columns,
        ].copy()
        if not search_source.empty:
            search_source = search_source.drop_duplicates(subset=["hex_id"], keep="first")
            search_tooltip_source = _apply_hex_tooltip_fields(
                _prepare_hybrid_tooltip_fields(search_source),
                mode="residual",
                show_discarded=show_discarded,
            )

    center, zoom = resolve_map_view(map_df, selected_ufs=selected_ufs, selected_cities=selected_cities)

    # Simplificacao enxuta SO no cap reduzido (UF grande); cor de fill inalterada.
    _stroked = effective_limit == MAP_POINT_LIMIT
    _auto_highlight = effective_limit == MAP_POINT_LIMIT
    layer_df = _deck_layer_frame(map_df)
    _hex_layer_kwargs: dict[str, Any] = dict(
        get_hexagon="hex_id",
        get_fill_color="fill_color",
        get_line_color="line_color",
        filled=True,
        stroked=_stroked,
        extruded=False,
        pickable=True,
        auto_highlight=_auto_highlight,
        highlight_color=[255, 255, 255, 60],
        opacity=0.85,
    )
    if _stroked:
        _hex_layer_kwargs["line_width_min_pixels"] = 1
    hex_layer = pdk.Layer("H3HexagonLayer", data=layer_df, **_hex_layer_kwargs)
    competitor_layer, _ = _competitor_layer_for_scope(
        competitors_df, map_df, cluster=cluster_competitors
    )
    ultra_layer = _build_ultra_icon_layer(ultra_df, map_df)
    layers = [hex_layer]
    if competitor_layer is not None:
        layers.append(competitor_layer)
    if ultra_layer is not None:
        layers.append(ultra_layer)
    if search_pin is not None:
        layers.append(_build_search_pin_layer(*search_pin))
        center = {"lat": search_pin[0], "lon": search_pin[1]}
        zoom = 10.0
    if search_hex_id is not None:
        layers.append(_build_search_hex_layer(search_hex_id, search_tooltip_source))

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
        layers=layers,
        tooltip=_hex_map_tooltip(),
    )
    # FU1: corte real do cap propagado para o caption honesto (vide build_map_figure).
    deck._ultra_capped = len(key) > effective_limit
    deck._ultra_effective_cap = effective_limit
    return deck, len(map_df)


_TESE_LINE_COLORS: dict[str, list[int]] = {
    "dominar_white_space": [34, 197, 94, 230],
    "abrir_com_disputa": [249, 115, 22, 230],
    "proteger_corredor_ultra": [59, 130, 246, 230],
    "adensar_cluster": [168, 85, 247, 230],
    "monitorar": [148, 163, 184, 180],
    "bloqueado_canibalizacao": [239, 68, 68, 230],
}

_TESE_LEGEND_COLORS: dict[str, str] = {
    "dominar_white_space": "#22C55E",
    "abrir_com_disputa": "#F97316",
    "proteger_corredor_ultra": "#3B82F6",
    "adensar_cluster": "#A855F7",
    "monitorar": "#94A3B8",
    "bloqueado_canibalizacao": "#EF4444",
}


def _dominio_fill_color(ordem) -> list[int]:
    """Gradient: ordem 1 = cyan brilhante, maior = azul mais escuro."""
    try:
        n = max(int(float(ordem)), 1)
    except (TypeError, ValueError):
        n = 5
    t = min(n - 1, 9) / 9.0
    return [int(t * 60), int(220 - t * 120), int(255 - t * 75), int(220 - t * 100)]


def build_dominio_map_figure(
    plano: pd.DataFrame,
    *,
    selected_ufs: list[str] | None = None,
    selected_cities: list[str] | None = None,
    competitors_df: pd.DataFrame | None = None,
    ultra_df: pd.DataFrame | None = None,
    cluster_competitors: bool = False,
):
    """Mapa de ancoras da Expansao de Dominio coloridas por ordem e tese."""
    if plano.empty or not {"hex_id", "lat", "lng"} <= set(plano.columns):
        return None, 0

    map_df = plano.loc[
        plano["hex_id"].notna() & plano["lat"].notna() & plano["lng"].notna()
    ].copy()
    if map_df.empty:
        return None, 0

    if selected_ufs:
        map_df = map_df.loc[map_df["uf"].isin(selected_ufs)].copy()
    if selected_cities and "nome_municipio" in map_df.columns:
        map_df = map_df.loc[map_df["nome_municipio"].isin(selected_cities)].copy()
    if map_df.empty:
        return None, 0

    map_df = map_df.drop_duplicates(subset=["hex_id"], keep="first").reset_index(drop=True)

    if "ordem_expansao_cidade" in map_df.columns:
        map_df["fill_color"] = map_df["ordem_expansao_cidade"].map(_dominio_fill_color)
    else:
        map_df["fill_color"] = [[0, 200, 240, 180]] * len(map_df)

    if "tese_dominio" in map_df.columns:
        map_df["line_color"] = map_df["tese_dominio"].map(
            lambda t: _TESE_LINE_COLORS.get(str(t), [120, 120, 140, 180])
        )
    else:
        map_df["line_color"] = [[120, 120, 140, 180]] * len(map_df)

    city_col = "nome_municipio" if "nome_municipio" in map_df.columns else "uf"
    map_df["tooltip_title"] = map_df[city_col].astype(str) + " / " + map_df["uf"].astype(str)
    if "cluster_id" in map_df.columns:
        map_df["tooltip_title"] = map_df["tooltip_title"] + " | " + map_df["cluster_id"].astype(str)

    map_df["tooltip_line_1"] = (
        "Abertura #" + map_df["ordem_expansao_cidade"].map(lambda v: str(int(v)) if pd.notna(v) else "-")
        if "ordem_expansao_cidade" in map_df.columns else ""
    )
    map_df["tooltip_line_2"] = (
        "Tese: " + map_df["tese_dominio"].astype(str)
        if "tese_dominio" in map_df.columns else ""
    )
    map_df["tooltip_line_3"] = (
        "Score residual: " + map_df["score_oportunidade_residual"].map(lambda v: f"{v:.1f}" if pd.notna(v) else "-")
        if "score_oportunidade_residual" in map_df.columns else ""
    )
    map_df["tooltip_line_4"] = (
        "Residual capturado: " + map_df["residual_incremental_capturado"].map(lambda v: format_int(v) if pd.notna(v) else "-")
        if "residual_incremental_capturado" in map_df.columns else ""
    )
    map_df["tooltip_line_5"] = (
        "Dist. Ultra: " + map_df["dist_ultra_mais_proxima_m"].map(lambda v: f"{int(v):,}".replace(",", ".") if pd.notna(v) else "-") + " m"
        if "dist_ultra_mais_proxima_m" in map_df.columns else ""
    )
    map_df["tooltip_line_6"] = (
        "Concorrentes 2km: " + map_df["n_concorrentes_mapeados_2km"].map(lambda v: str(int(v)) if pd.notna(v) else "-")
        if "n_concorrentes_mapeados_2km" in map_df.columns else ""
    )
    map_df["tooltip_line_7"] = (
        "Rank Brasil: " + map_df["rank_dominio_brasil"].map(lambda v: str(int(v)) if pd.notna(v) else "-")
        if "rank_dominio_brasil" in map_df.columns else ""
    )
    for _i in range(8, 15):
        map_df[f"tooltip_line_{_i}"] = ""

    center, zoom = resolve_map_view(
        map_df,
        selected_ufs=selected_ufs or [],
        selected_cities=selected_cities or [],
    )

    layer_df = _deck_layer_frame(map_df)
    hex_layer = pdk.Layer(
        "H3HexagonLayer",
        data=layer_df,
        get_hexagon="hex_id",
        get_fill_color="fill_color",
        get_line_color="line_color",
        filled=True,
        stroked=True,
        extruded=False,
        pickable=True,
        auto_highlight=True,
        highlight_color=[255, 255, 255, 80],
        opacity=0.88,
        line_width_min_pixels=2,
    )
    competitor_layer, _ = _competitor_layer_for_scope(
        competitors_df, map_df, cluster=cluster_competitors
    )
    ultra_layer = _build_ultra_icon_layer(ultra_df, map_df)
    layers = [hex_layer]
    if competitor_layer is not None:
        layers.append(competitor_layer)
    if ultra_layer is not None:
        layers.append(ultra_layer)

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
        layers=layers,
        tooltip=_shared_map_tooltip(),
    )
    # FU1: o mapa de dominio nao aplica cap dinamico (ancoras, volume baixo);
    # marca explicitamente nao-amostrado para o caption honesto.
    deck._ultra_capped = False
    deck._ultra_effective_cap = MAP_POINT_LIMIT
    return deck, len(map_df)


def render_dominio_tese_legend() -> None:
    chips = "".join(
        f"<span class='legend-chip'><span class='legend-dot' style='background:{color};'></span>{label.replace('_', ' ')}</span>"
        for label, color in _TESE_LEGEND_COLORS.items()
    )
    order_chip = (
        "<span class='legend-chip'>"
        "<span style='display:inline-flex;gap:3px;align-items:center;'>"
        "<span class='legend-dot' style='background:#00DCFF;'></span>"
        "<span class='legend-dot' style='background:#008BC8;'></span>"
        "<span class='legend-dot' style='background:#3C64B4;'></span>"
        "</span>"
        "Ordem de abertura (1=cyan, +tarde=azul)"
        "</span>"
    )
    st.markdown(f"<div class='legend-row'>{chips}{order_chip}</div>", unsafe_allow_html=True)


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
        labels={"score_medio": "Score médio", "cidade_label": "Cidade"},
        text="score_medio",
    )
    fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
    apply_exec_layout(fig, title="Top cidades por score médio", height=430)
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
        labels={"oportunidades_viaveis": "Oportunidades viáveis", "uf": "UF"},
        text="oportunidades_viaveis",
    )
    fig.update_traces(texttemplate="%{text:.0f}", textposition="outside")
    apply_exec_layout(fig, title="Top UFs por oportunidades viáveis", height=430)
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
            "populacao_proxy": "População",
            "score_medio": "Score médio",
        },
        color_continuous_scale="Blues",
    )
    apply_exec_layout(fig, title="Renda × população", height=520)
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
        labels={"score_priorizacao": "Score de priorização", "count": "Hexágonos"},
    )
    apply_exec_layout(fig, title="Distribuição de score", height=340)
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

    # Coluna de EXIBICAO acentuada (valor bruto de faixa_oportunidade INTOCADO). A ordem
    # categorica segue FAIXA_ORDEM mapeado pelos labels, para o eixo x nao desordenar; a cor
    # por faixa e preservada via FAIXA_COLORS_POR_LABEL (keyed pelo mesmo label).
    _faixa_label_order = [FAIXA_LABELS.get(f, f) for f in FAIXA_ORDEM]
    faixa_df["faixa_label"] = pd.Categorical(
        [FAIXA_LABELS.get(f, f) for f in faixa_df["faixa_oportunidade"].astype(str)],
        categories=_faixa_label_order,
        ordered=True,
    )
    fig = px.bar(
        faixa_df,
        x="faixa_label",
        y="score_medio",
        color="faixa_label",
        color_discrete_map=FAIXA_COLORS_POR_LABEL,
        category_orders={"faixa_label": _faixa_label_order},
        labels={"faixa_label": "Faixa", "score_medio": "Score médio"},
        text="score_medio",
    )
    fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
    apply_exec_layout(fig, title="Score médio por faixa de oportunidade", height=340)
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
        labels={"score_medio": "Score médio", "uf": "UF"},
        text="score_medio",
    )
    fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
    apply_exec_layout(fig, title="Melhores e piores UFs por score médio", height=620)
    return fig


def build_ultra_network_kpis(
    df: pd.DataFrame,
    ultra_df: pd.DataFrame | None,
    carteira_df: pd.DataFrame | None,
    plano_dominio_df: pd.DataFrame | None,
    *,
    selected_ufs: list[str],
    selected_cities: list[str],
) -> dict[str, str]:
    """KPIs da rede Ultra e mercado para a Visao Executiva."""
    ultra_units = 0
    cidades_com_ultra = 0
    if ultra_df is not None and not ultra_df.empty and {"lat", "lng"} <= set(ultra_df.columns):
        u = ultra_df.loc[ultra_df["lat"].notna() & ultra_df["lng"].notna()].copy()
        if selected_ufs and "uf" in u.columns:
            u = u.loc[u["uf"].isin(selected_ufs)]
        if selected_cities and "cidade" in u.columns:
            u = u.loc[u["cidade"].isin(selected_cities)]
        ultra_units = len(u)
        if "cidade" in u.columns:
            cidades_com_ultra = u["cidade"].nunique()

    score_medio_m1 = "-"
    if not df.empty and "score_priorizacao" in df.columns:
        score_medio_m1 = f"{df['score_priorizacao'].mean():.1f}"

    residual_total = "-"
    opps_sem_ultra = "-"
    if carteira_df is not None and not carteira_df.empty:
        cart = carteira_df
        if selected_ufs and "uf" in cart.columns:
            cart = cart.loc[cart["uf"].isin(selected_ufs)]
        if selected_cities:
            city_col = "nome_municipio" if "nome_municipio" in cart.columns else "cidade" if "cidade" in cart.columns else None
            if city_col:
                cart = cart.loc[cart[city_col].isin(selected_cities)]
        if "oferta_efetiva_disponivel" in cart.columns:
            total = cart["oferta_efetiva_disponivel"].sum(skipna=True)
            if pd.notna(total):
                residual_total = format_int(int(total))
        if "n_unidades_ultra_performance_hex" in cart.columns:
            sem_ultra = int((cart["n_unidades_ultra_performance_hex"].fillna(0) == 0).sum())
            opps_sem_ultra = format_int(sem_ultra)

    ancoras_dominio = "-"
    if plano_dominio_df is not None and not plano_dominio_df.empty:
        dom = plano_dominio_df
        if selected_ufs and "uf" in dom.columns:
            dom = dom.loc[dom["uf"].isin(selected_ufs)]
        if selected_cities:
            city_col = "nome_municipio" if "nome_municipio" in dom.columns else "cidade" if "cidade" in dom.columns else None
            if city_col:
                dom = dom.loc[dom[city_col].isin(selected_cities)]
        ancoras_dominio = format_int(len(dom))

    return {
        "ultra_units": format_int(ultra_units),
        "cidades_com_ultra": format_int(cidades_com_ultra),
        "residual_total": residual_total,
        "opps_sem_ultra": opps_sem_ultra,
        "ancoras_dominio": ancoras_dominio,
        "score_medio_m1": score_medio_m1,
    }


def build_residual_by_uf_figure(carteira_df: pd.DataFrame | None):
    """Residual potencial (oferta_efetiva_disponivel) agregado por UF."""
    if carteira_df is None or carteira_df.empty:
        return None
    if "oferta_efetiva_disponivel" not in carteira_df.columns or "uf" not in carteira_df.columns:
        return None
    grouped = (
        carteira_df.groupby("uf", as_index=False)["oferta_efetiva_disponivel"]
        .sum()
        .sort_values("oferta_efetiva_disponivel", ascending=True, kind="stable")
        .tail(15)
    )
    if grouped.empty:
        return None
    fig = px.bar(
        grouped,
        x="oferta_efetiva_disponivel",
        y="uf",
        orientation="h",
        color_discrete_sequence=[COLORS["brand_alt"]],
        labels={"oferta_efetiva_disponivel": "Residual (alunos)", "uf": "UF"},
        text="oferta_efetiva_disponivel",
    )
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    apply_exec_layout(fig, title="Residual potencial por UF (alunos)", height=430)
    return fig


def build_residual_score_dist_figure(carteira_df: pd.DataFrame | None):
    """Histograma de score_oportunidade_residual."""
    if carteira_df is None or carteira_df.empty:
        return None
    if "score_oportunidade_residual" not in carteira_df.columns:
        return None
    valid = carteira_df["score_oportunidade_residual"].dropna()
    if valid.empty:
        return None
    fig = px.histogram(
        carteira_df,
        x="score_oportunidade_residual",
        nbins=20,
        color_discrete_sequence=[COLORS["brand"]],
        labels={"score_oportunidade_residual": "Score residual"},
    )
    apply_exec_layout(fig, title="Distribuição do score residual", height=320)
    return fig


def build_top_cities_residual_figure(carteira_df: pd.DataFrame | None):
    """Top cidades com alto residual e baixa presenca Ultra."""
    if carteira_df is None or carteira_df.empty:
        return None
    city_col = "nome_municipio" if "nome_municipio" in carteira_df.columns else "cidade" if "cidade" in carteira_df.columns else None
    if city_col is None or "oferta_efetiva_disponivel" not in carteira_df.columns:
        return None

    agg: dict[str, object] = {"oferta_efetiva_disponivel": "sum", "uf": "first"}
    if "n_unidades_ultra_performance_hex" in carteira_df.columns:
        agg["n_unidades_ultra_performance_hex"] = "sum"

    grouped = carteira_df.groupby(city_col, as_index=False).agg(agg)

    if "n_unidades_ultra_performance_hex" in grouped.columns:
        low_ultra = grouped.loc[grouped["n_unidades_ultra_performance_hex"] == 0]
        if len(low_ultra) >= 5:
            grouped = low_ultra

    grouped = grouped.sort_values(
        "oferta_efetiva_disponivel", ascending=True, kind="stable"
    ).tail(10)
    if grouped.empty:
        return None

    grouped["label"] = grouped[city_col].astype(str) + " / " + grouped["uf"].astype(str)
    fig = px.bar(
        grouped,
        x="oferta_efetiva_disponivel",
        y="label",
        orientation="h",
        color_discrete_sequence=[COLORS["warning"]],
        labels={"oferta_efetiva_disponivel": "Residual (alunos)", "label": "Cidade"},
        text="oferta_efetiva_disponivel",
    )
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    apply_exec_layout(fig, title="Top cidades: alto residual, baixa presença Ultra", height=430)
    return fig


def build_indicator_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            {
                "Indicador": [
                    "Score médio",
                    "Renda per capita média",
                    "População proxy média",
                    "% viável",
                    "% priorizado",
                ],
                "Valor": ["-", "-", "-", "-", "-"],
            }
        )

    return pd.DataFrame(
        {
            "Indicador": [
                "Score médio",
                "Renda per capita média",
                "População proxy média",
                "% viável",
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
            "score_priorizacao": "Score Priorização",
            "rank_brasil": "Rank Brasil",
            "rank_uf": "Rank UF",
            "rank_cidade": "Rank Cidade",
            "faixa_oportunidade": "Faixa",
            "flag_prioridade": "Prioridade",
            "flag_viavel": "Viável",
            "nome_municipio": "Cidade",
        }
    )
    table_df["Prioridade"] = table_df["Prioridade"].map({True: "Sim", False: "Não"})
    table_df["Viável"] = table_df["Viável"].map({True: "Sim", False: "Não"})
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
        "nome_municipio": "Município",
        "hex_id": "Hex ID",
        "score_setor_2022_calibrado": "Score Censo 2022",
        "score_priorizacao": "Score M1",
        "score_expansao_hibrido": "Score Híbrido",
        "rank_hex_intraurbano": "Rank Intraurbano",
        "rank_hibrido_brasil": "Rank Híbrido Brasil",
        "top_hex_intraurbano": "Top Hex",
        "top_oportunidade_municipio": "Carteira Município",
        "qualidade_join_uf": "Qualidade Join",
        "coverage_pct_setor_2022": "Coverage %",
        "flag_join_uf_restrito": "Join Restrito",
        "flag_baixa_pop_setor": "Dens. < 5k",
        "flag_outlier_espacial": "Outlier Espacial",
        "causa_outlier_espacial": "Causa Outlier",
        "motivo_nao_elegivel_censo": "Status Editorial",
    }
    top = top.rename(columns={k: v for k, v in rename_map.items() if k in top.columns})
    for col in ["Top Hex", "Carteira Município", "Join Restrito", "Dens. < 5k", "Outlier Espacial"]:
        if col in top.columns:
            top[col] = top[col].map({True: "Sim", False: "Não"})
    return top


def build_hybrid_municipios_table(hdf: pd.DataFrame) -> pd.DataFrame:
    if "top_municipio" not in hdf.columns:
        return pd.DataFrame()

    mun = hdf[hdf["top_municipio"].eq(True)].copy()  # invariante a `== True`; evita E712 preservando semantica pandas/NaN
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
        "nome_municipio": "Município",
        "score_priorizacao": "Score M1",
        "rank_municipio_uf": "Rank Mun UF",
        "rank_municipio_brasil": "Rank Mun Brasil",
        "flag_censo_disponivel": "Censo Disponível",
        "top_municipio_hibrido": "Município Elegível Híbrido",
        "top_municipio": "Top M1",
        "melhor_hex_id": "Melhor Hex",
        "melhor_score_setor_2022_calibrado": "Melhor Score Censo",
        "melhor_score_expansao_hibrido": "Melhor Score Híbrido",
        "melhor_rank_hex_intraurbano": "Rank Melhor Hex",
        "melhor_top_oportunidade_municipio": "Carteira Município",
        "melhor_coverage_pct_setor_2022": "Coverage %",
        "melhor_qualidade_join_uf": "Qualidade Join",
        "melhor_flag_baixa_pop_setor": "Melhor Hex Dens. < 5k",
        "melhor_flag_outlier_espacial": "Melhor Hex Outlier",
    }
    mun = mun[
        [column for column in rename_map if column in mun.columns]
    ].rename(columns={k: v for k, v in rename_map.items() if k in mun.columns})
    for col in [
        "Censo Disponível",
        "Município Elegível Híbrido",
        "Top M1",
        "Carteira Município",
        "Melhor Hex Dens. < 5k",
        "Melhor Hex Outlier",
    ]:
        if col in mun.columns:
            mun[col] = mun[col].map({True: "Sim", False: "Não"})
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
        hdf[hdf["top_municipio_hibrido"].eq(True)][municipio_keys].drop_duplicates().shape[0]  # invariante a `== True`; evita E712
        if "top_municipio_hibrido" in hdf.columns and municipio_keys
        else 0
    )
    municipios_cobertos = (
        hdf[hdf["flag_censo_disponivel"].eq(True)][municipio_keys].drop_duplicates().shape[0]  # invariante a `== True`; evita E712
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
            "score_setor_2022_calibrado": "Score Censitário 2022 (intraurbano)",
            "uf_label": "UF",
        },
        opacity=0.55,
        title="M1 vs Censitário 2022 - cada ponto é um hex",
    )
    apply_exec_layout(fig, title="Comparativo M1 vs Censitário 2022 por hex", height=420)
    return fig


def build_hybrid_portfolio_table(hdf: pd.DataFrame) -> pd.DataFrame:
    if hdf.empty or "flag_hex_hibrido_elegivel" not in hdf.columns:
        return pd.DataFrame()

    portfolio = hdf[hdf["flag_hex_hibrido_elegivel"].eq(True)].copy()  # invariante a `== True`; evita E712
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
        "nome_municipio": "Município",
        "hex_id": "Hex ID",
        "rank_hibrido_brasil": "Rank Híbrido Brasil",
        "rank_hibrido_uf": "Rank Híbrido UF",
        "rank_hex_intraurbano": "Rank Intraurbano",
        "score_priorizacao": "Score M1",
        "score_setor_2022_calibrado": "Score Censo 2022",
        "score_expansao_hibrido": "Score Híbrido",
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
            portfolio[column] = portfolio[column].map({True: "Sim", False: "Não"})
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
            f"{format_int(join_restrito)} hexes no recorte estão com join restrito. Trate o Censitário como leitura exploratória e mantenha o M1 como evidência principal."
        )
    if coverage_baixa > 0:
        alerts.append(
            f"{format_int(coverage_baixa)} hexes estão abaixo do gate de 85% de coverage censitário. Evite usar esse sinal como evidência forte."
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

    score_min = float(table_df["Score Priorização"].min())
    score_max = float(table_df["Score Priorização"].max())

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
                "Score Priorização": "{:.2f}",
                "Rank Brasil": "{:.0f}",
                "Rank UF": "{:.0f}",
                "Rank Cidade": "{:.0f}",
            }
        )
        .map(score_style, subset=["Score Priorização"])
        .map(faixa_style, subset=["Faixa"])
        .map(flag_style, subset=["Prioridade", "Viável"])
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


def build_unified_map_figure(
    df: pd.DataFrame,
    *,
    color_mode: str = "m1",
    enabled_overlays: list[str] | None = None,
    selected_ufs: list[str],
    selected_cities: list[str],
    selected_faixas: list[str] | None = None,
    competitors_df: pd.DataFrame | None = None,
    ultra_df: pd.DataFrame | None = None,
    search_pin: tuple[float, float] | None = None,
    search_hex_id: str | None = None,
    dominio_df: pd.DataFrame | None = None,
    vazios_df: pd.DataFrame | None = None,
):
    """Dispatcher do Mapa Territorial Unificado.

    Retorna (deck, n_pontos) delegando ao builder correto conforme color_mode.
    Overlays sao controlados por enabled_overlays; None ativa todos.
    Nao altera score_priorizacao, carteira, plano nem artefatos oficiais do M1.
    """
    if enabled_overlays is None:
        enabled_overlays = list(OVERLAYS)

    _comp = competitors_df if "concorrentes" in enabled_overlays else None
    _ultra = ultra_df if "ultra" in enabled_overlays else None

    # BLK-FIX-11 (overlays mortos -> funcionais): gates centralizados no dispatcher.
    # hex_pesquisado controla pin + hex destacado; descartados_5k controla o cinza
    # _DISCARDED_FILL e o label de tooltip; ancoras_dominio injeta a camada ambar
    # pos-builder. DV-1..DV-5 aprovados por Felipe em 2026-06-10. READ-ONLY M1.
    _search_pin = search_pin if "hex_pesquisado" in enabled_overlays else None
    _search_hex_id = search_hex_id if "hex_pesquisado" in enabled_overlays else None
    _show_discarded = "descartados_5k" in enabled_overlays

    # BLK-FIX-07-B: cluster server-side dos concorrentes em recortes amplos (decidido
    # uma vez aqui e propagado a todos os builders, incl. dominio). Camada visual.
    cluster = competitor_cluster_mode(selected_ufs, selected_cities, selected_faixas)

    if color_mode == "dominio":
        # Modo dominio tem layout proprio; ancoras_dominio NAO sao injetadas aqui
        # (fora do escopo do BLK-FIX-11; follow-up). Retorna direto.
        plano = dominio_df if dominio_df is not None else pd.DataFrame()
        deck_dom, n_dom = build_dominio_map_figure(
            plano,
            selected_ufs=selected_ufs or None,
            selected_cities=selected_cities or None,
            competitors_df=_comp,
            ultra_df=_ultra,
            cluster_competitors=cluster,
        )
        _stabilize_layer_ids(deck_dom, prefix=f"{color_mode}")
        return deck_dom, n_dom

    if color_mode == "residual":
        deck, n_pontos = build_residual_heatmap_figure(
            df,
            selected_ufs=selected_ufs,
            selected_cities=selected_cities,
            competitors_df=_comp,
            ultra_df=_ultra,
            search_pin=_search_pin,
            search_hex_id=_search_hex_id,
            cluster_competitors=cluster,
            show_discarded=_show_discarded,
        )
    elif color_mode in ("hibrido", "censitario"):
        _color_col = "score_setor_2022_calibrado" if color_mode == "censitario" else "score_expansao_hibrido"
        deck, n_pontos = build_hybrid_map_figure(
            df,
            selected_ufs=selected_ufs,
            selected_cities=selected_cities,
            color_col=_color_col,
            competitors_df=_comp,
            ultra_df=_ultra,
            search_pin=_search_pin,
            search_hex_id=_search_hex_id,
            cluster_competitors=cluster,
            show_discarded=_show_discarded,
        )
    else:
        # Default: m1
        deck, n_pontos = build_map_figure(
            df,
            selected_ufs=selected_ufs,
            selected_cities=selected_cities,
            competitors_df=_comp,
            ultra_df=_ultra,
            search_pin=_search_pin,
            search_hex_id=_search_hex_id,
            cluster_competitors=cluster,
            show_discarded=_show_discarded,
        )

    if "ancoras_dominio" in enabled_overlays and deck is not None:
        ancora_layer = _build_ancoras_dominio_layer(dominio_df, selected_ufs, selected_cities)
        if ancora_layer is not None:
            deck.layers = [*deck.layers, ancora_layer]

    if "vazios_competitivos_lc" in enabled_overlays and deck is not None:
        vazios_layer = _build_vazios_competitivos_layer(vazios_df)
        if vazios_layer is not None:
            deck.layers = [*deck.layers, vazios_layer]

    _stabilize_layer_ids(deck, prefix=f"{color_mode}")
    return deck, n_pontos


def _stabilize_layer_ids(deck: pdk.Deck | None, *, prefix: str) -> None:
    """Atribui ids ESTÁVEIS e determinísticos às layers do deck (in-place).

    O pydeck gera `Layer.id` como uuid4 NOVO a cada construção; a doc do
    `st.pydeck_chart` exige que, com `on_select` ativo, "all layers must have a
    declared id to keep the chart stateful across reruns". Com ids mudando a cada
    rerun, o Streamlit >= 1.56 perde o vínculo de seleção e o CLIQUE no mapa morre
    silenciosamente (regressão observada em 2026-07-10; independe do cache do
    BLK-PERF-01b — reproduzida também no código pré-01b). Ordem das layers é
    determinística nos builders -> `{prefix}_layer_{i}` é estável entre reruns.
    Display-only; READ-ONLY M1.
    """
    if deck is None:
        return
    for i, layer in enumerate(getattr(deck, "layers", []) or []):
        layer.id = f"{prefix}_layer_{i}"


def build_analise_pontual_map(
    lat: float,
    lng: float,
    raio_km: float,
    hexes_entorno: pd.DataFrame,
    competitors_df: pd.DataFrame | None = None,
    ultra_df: pd.DataFrame | None = None,
) -> pdk.Deck | None:
    """Map with center point, radius circle and hexes within range for Analise Pontual.

    Does not recalculate or alter score_priorizacao or any official M1 artifact.
    """
    raio_m = raio_km * 1000
    layers: list[pdk.Layer] = []

    if not hexes_entorno.empty and "hex_id" in hexes_entorno.columns:
        layers.append(
            pdk.Layer(
                "H3HexagonLayer",
                data=hexes_entorno[["hex_id"]],
                get_hexagon="hex_id",
                filled=True,
                extruded=False,
                get_fill_color=[25, 183, 255, 90],
                get_line_color=[25, 183, 255, 200],
                line_width_min_pixels=1,
                pickable=False,
                opacity=0.65,
            )
        )

    layers.append(
        pdk.Layer(
            "ScatterplotLayer",
            data=[{"lat": lat, "lng": lng}],
            get_position=["lng", "lat"],
            get_radius=raio_m,
            get_fill_color=[255, 165, 0, 18],
            get_line_color=[255, 165, 0, 200],
            stroked=True,
            filled=True,
            line_width_min_pixels=2,
            pickable=False,
        )
    )

    layers.append(
        pdk.Layer(
            "ScatterplotLayer",
            data=[{"lat": lat, "lng": lng}],
            get_position=["lng", "lat"],
            get_radius=100,
            get_fill_color=[255, 77, 141, 240],
            get_line_color=[255, 255, 255, 210],
            stroked=True,
            filled=True,
            line_width_min_pixels=2,
            pickable=False,
        )
    )

    competitors_raio = filter_points_to_radius(
        competitors_df,
        lat,
        lng,
        raio_km,
        required_columns={"rede", "nome_unidade"},
    )
    competitor_layer, _ = _build_competitor_icon_layer(competitors_raio, competitors_raio)
    ultra_raio = filter_points_to_radius(
        ultra_df,
        lat,
        lng,
        raio_km,
        required_columns={"nome_unidade"},
    )
    ultra_layer = _build_ultra_icon_layer(ultra_raio, ultra_raio)

    if competitor_layer is not None:
        layers.append(competitor_layer)
    if ultra_layer is not None:
        layers.append(ultra_layer)

    return pdk.Deck(
        map_style=pdk.map_styles.CARTO_DARK,
        initial_view_state=pdk.ViewState(
            latitude=lat,
            longitude=lng,
            zoom=12,
            min_zoom=9,
            max_zoom=16,
            pitch=0,
            bearing=0,
        ),
        layers=layers,
    )


def _build_multihex_selection_layer(hex_ids: list[str]) -> pdk.Layer:
    """Layer de destaque (borda laranja) para hexes no cenario multi-hex.

    Nao interfere nas cores dos modos M1/Censitario/Hibrido/Residual/Dominio.
    Nao altera score_priorizacao nem artefatos oficiais do M1.
    """
    return pdk.Layer(
        "H3HexagonLayer",
        data=pd.DataFrame({"hex_id": hex_ids}),
        id="multihex_destaque",  # id ESTÁVEL (ver _stabilize_layer_ids)
        get_hexagon="hex_id",
        get_fill_color=[255, 165, 0, 50],
        get_line_color=[255, 165, 0, 255],
        filled=True,
        stroked=True,
        extruded=False,
        pickable=False,
        line_width_min_pixels=3,
        opacity=0.9,
    )


def build_multihex_analysis_map(
    hex_ids: list[str],
    lat: float | None = None,
    lng: float | None = None,
    raio_km: float = 1.6,
    competitors_df: pd.DataFrame | None = None,
    ultra_df: pd.DataFrame | None = None,
) -> pdk.Deck | None:
    """Map highlighting selected multi-hex hexagons with optional active-point radius.

    When lat/lng provided: adds radius circle, center pin and competitor/Ultra pins within range.
    Without lat/lng: centers view on the first hex centroid.
    Does not recalculate or alter score_priorizacao or any official M1 artifact.
    """
    if not hex_ids:
        return None

    layers: list[pdk.Layer] = []

    layers.append(
        pdk.Layer(
            "H3HexagonLayer",
            data=pd.DataFrame({"hex_id": hex_ids}),
            get_hexagon="hex_id",
            filled=True,
            extruded=False,
            get_fill_color=[255, 165, 0, 110],
            get_line_color=[255, 165, 0, 255],
            line_width_min_pixels=3,
            pickable=False,
            opacity=0.9,
        )
    )

    if lat is not None and lng is not None:
        raio_m = raio_km * 1000
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                data=[{"lat": lat, "lng": lng}],
                get_position=["lng", "lat"],
                get_radius=raio_m,
                get_fill_color=[255, 165, 0, 18],
                get_line_color=[255, 165, 0, 140],
                stroked=True,
                filled=True,
                line_width_min_pixels=2,
                pickable=False,
            )
        )
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                data=[{"lat": lat, "lng": lng}],
                get_position=["lng", "lat"],
                get_radius=100,
                get_fill_color=[255, 77, 141, 240],
                get_line_color=[255, 255, 255, 210],
                stroked=True,
                filled=True,
                line_width_min_pixels=2,
                pickable=False,
            )
        )
        competitors_raio = filter_points_to_radius(
            competitors_df, lat, lng, raio_km,
            required_columns={"rede", "nome_unidade"},
        )
        competitor_layer, _ = _build_competitor_icon_layer(competitors_raio, competitors_raio)
        ultra_raio = filter_points_to_radius(
            ultra_df, lat, lng, raio_km,
            required_columns={"nome_unidade"},
        )
        ultra_layer = _build_ultra_icon_layer(ultra_raio, ultra_raio)
        if competitor_layer is not None:
            layers.append(competitor_layer)
        if ultra_layer is not None:
            layers.append(ultra_layer)
        view_lat, view_lng, view_zoom = lat, lng, 12
    else:
        try:
            import h3
            cell_lat, cell_lng = h3.cell_to_latlng(hex_ids[0])
            view_lat, view_lng, view_zoom = cell_lat, cell_lng, 11
        except Exception:
            view_lat, view_lng, view_zoom = -15.77, -47.93, 4

    return pdk.Deck(
        map_style=pdk.map_styles.CARTO_DARK,
        initial_view_state=pdk.ViewState(
            latitude=view_lat,
            longitude=view_lng,
            zoom=view_zoom,
            min_zoom=4,
            max_zoom=16,
            pitch=0,
            bearing=0,
        ),
        layers=layers,
    )


def render_manifest_footer(manifest_path: Path) -> None:
    """Rodape read-only com a proveniencia dos outputs (BLK-OPS-03)."""
    if not manifest_path.exists():
        return  # ausencia nao quebra o app; nao renderiza
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    with st.expander("Proveniência dos outputs (read-only)", expanded=False):
        st.caption(
            f"IBGE: {data.get('ibge_vintage')} | H3 res {data.get('h3_resolution')} | "
            f"pesos renda {data.get('pesos', {}).get('renda')} / pop {data.get('pesos', {}).get('pop')} | "
            f"dist_min_ultra_km {data.get('dist_min_ultra_km')} | renda_min {data.get('renda_min')}"
        )
        st.caption(
            f"commit {data.get('code_commit')} | gerado em {data.get('generated_at')} | "
            f"Ultra.csv sha256 {data.get('ultra_csv_sha256')}"
        )
