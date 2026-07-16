"""ui_spike_deckgl.py — SPIKE DESCARTÁVEL (BLK-REV-08).

Protótipo de teto de performance do mapa client-side com deck.gl
`H3HexagonLayer` servido por `st.components.v1.html`, escalado ao cap real
de produção (18–35k hexes). Objetivo: medir empiricamente o teto de FPS /
latência (render, recolor, cenário) para embasar o BLK-REV-12.

REMOVER APÓS A MEDIÇÃO — NÃO IMPORTAR EM PRODUÇÃO (`pages.py` não importa
este módulo). Opt-in via env var `ULTRA_SPIKE_DECKGL=1` ou
`st.session_state["show_ui_spike_deckgl"] = True`.

READ-ONLY sobre o M1 (CLAUDE.md §5): zero recálculo/alteração de
`score_priorizacao`/`hex_score_estrutural`/pesos/carteira/plano/artefatos
oficiais. Só LEITURA do parquet derivado por UF (não oficial M1).

Motor de render (WebGL) vs `ui_proto.py` (Leaflet + h3-js, DOM/SVG):
  - O payload carrega SÓ `hex_id` cru (sem geometria nem lat/lng por hex). A
    tesselação da célula acontece no CLIENTE via `h3.cellToBoundary(h, true)`
    (h3-js v4 por CDN) e desenha num `PolygonLayer` deck.gl (WebGL/GPU).
    Nota: a rota original usava `H3HexagonLayer` (`getHexagon`), mas o bundle
    standalone do deck.gl trazia um h3 interno incompatível (v3 x v4:
    `h3GetResolution`/`h3ToGeo is not a function`) — trocado por
    `PolygonLayer` + h3-js v4 explícito, que é robusto a versão e preserva a
    tese "payload só com hex_id".
  - Recolor (M1↔Residual) é update de atributo GPU via `updateTriggers`,
    sem re-serializar o payload (a geometria por hex fica cacheada em `d.__poly`).
  - Seleção/cenário é `pickable` + `onClick` no browser, sem rerun.

Dados consumidos (leitura):
  - data/outputs/hexagonos_dashboard_enriquecido/uf=<UF>/parte-0.parquet
    (o MESMO artefato derivado que o dashboard lazy-carrega por UF).

JSON de recorte (cache isolado, gitignored):
  - data/cache/ui_spike_deckgl/<UF>.json
"""
from __future__ import annotations

import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from motor_expansao.dashboard.constants import (
    MAP_POINT_LIMIT,
    MAP_POINT_LIMIT_LARGE,
    RESIDUAL_SCORE_BANDS,
)
from motor_expansao.dashboard.ui_theme import PROTO_PALETTE

# ──────────────────────────────────────────────────────────────
# Paths canônicos (nunca escrevem em artefatos M1 oficiais)
# ──────────────────────────────────────────────────────────────
# parents[3] = repo root (src/motor_expansao/dashboard/ui_spike_deckgl.py → repo).
# Correto no dev e na produção (/app/src/... → /app). Nota: ui_proto.py usa
# parents[4] (bug latente lá que só não quebra porque os testes sempre passam
# enriquecido_dir); aqui usamos o depth correto para a leitura real funcionar.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_ENRIQUECIDO_DIR = _REPO_ROOT / "data" / "outputs" / "hexagonos_dashboard_enriquecido"
# Cache ISOLADO — diretório novo, NÃO reusa data/cache/ui_proto/.
_CACHE_DIR = _REPO_ROOT / "data" / "cache" / "ui_spike_deckgl"

_SPIKE_VERSION = "ui_spike_deckgl_v1"

# Brasil default (fallback de view sem dados)
_BRASIL_VIEW = {"longitude": -51.9253, "latitude": -14.235, "zoom": 4.0}

# Colunas lidas do parquet (subset; fallback de leitura total como ui_proto).
_READ_COLUMNS = [
    "hex_id",
    "score_priorizacao",
    "score_oportunidade_residual",
    "pop_total",
    "populacao_proxy",
    "oferta_efetiva_disponivel",
    "lat",
    "lng",
]

# Colunas de PII proibidas — NUNCA no payload (garantia estrutural + teste).
_PII_FORBIDDEN = {
    "endereco",
    "nome_propriedade",
    "owner",
    "email",
    "telefone",
    "cpf",
    "cnpj",
}
# Chaves de geometria proibidas — o payload usa hex_id cru, sem polígono.
_GEOMETRY_FORBIDDEN = {
    "geometry",
    "geometry_wkb",
    "boundary",
    "geometria",
    "lat",
    "lng",
}


def _safe_float(value: Any) -> float | None:
    """Converte valor para float, retornando None se NaN/infinito."""
    try:
        v = float(value)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    """Converte valor para int, retornando None se inválido."""
    v = _safe_float(value)
    if v is None:
        return None
    return int(v)


def _band_upper_edges() -> np.ndarray:
    """Bordas superiores das faixas RESIDUAL_SCORE_BANDS: [10, 20, ..., 100]."""
    return np.array(
        [float(band.split("-")[1]) for band, _color in RESIDUAL_SCORE_BANDS],
        dtype=float,
    )


def _band_index_vec(scores: pd.Series) -> np.ndarray:
    """Índice de faixa de cor (0–9) por score, vetorizado.

    Mapeia cada score às 10 faixas de RESIDUAL_SCORE_BANDS via searchsorted
    sobre as bordas superiores. NaN → faixa 0 (fillna 0). Clampeado a 0..9.
    """
    edges = _band_upper_edges()
    filled = scores.fillna(0.0).to_numpy(dtype=float)
    idx = np.searchsorted(edges, filled, side="left")
    return np.clip(idx, 0, len(edges) - 1).astype(int)


def _hex_to_rgb(color: str) -> list[int]:
    """Converte cor hexadecimal (#RRGGBB) para lista [r, g, b]."""
    h = color.lstrip("#")
    return [int(h[i : i + 2], 16) for i in (0, 2, 4)]


def _bands_rgb() -> list[list[int]]:
    """Paleta RESIDUAL_SCORE_BANDS como 10 triplas [r, g, b]."""
    return [_hex_to_rgb(color) for _band, color in RESIDUAL_SCORE_BANDS]


def _compute_view(lats: list[float], lngs: list[float]) -> dict[str, float]:
    """Pré-computa a viewport inicial (bbox → longitude/latitude/zoom).

    Calculado UMA vez em Python — o cliente não precisa de lat/lng por hex
    (a célula vem do hex_id). Heurística de zoom pelo maior span do bbox.
    """
    if not lats or not lngs:
        return dict(_BRASIL_VIEW)
    lat_min, lat_max = min(lats), max(lats)
    lng_min, lng_max = min(lngs), max(lngs)
    lat_c = (lat_min + lat_max) / 2.0
    lng_c = (lng_min + lng_max) / 2.0
    span = max(lat_max - lat_min, lng_max - lng_min, 0.02)
    zoom = math.log2(360.0 / span) - 1.0
    zoom = max(3.0, min(12.0, zoom))
    return {
        "longitude": round(lng_c, 5),
        "latitude": round(lat_c, 5),
        "zoom": round(zoom, 2),
    }


def _read_uf_parquet(uf_upper: str, enriquecido_dir: Path) -> pd.DataFrame | None:
    """Lê o parquet enriquecido da UF (subset de colunas; fallback total)."""
    uf_part = enriquecido_dir / f"uf={uf_upper}"
    if not uf_part.exists():
        return None
    parquet_file = uf_part / "parte-0.parquet"
    if not parquet_file.exists():
        candidates = sorted(uf_part.glob("*.parquet"))
        if not candidates:
            return None
        parquet_file = candidates[0]
    try:
        return pd.read_parquet(parquet_file, columns=_READ_COLUMNS)
    except Exception:
        try:
            return pd.read_parquet(parquet_file)
        except Exception:
            return None


def gerar_recorte_spike_json(
    uf: str,
    enriquecido_dir: Path | None = None,
    *,
    limit: int = MAP_POINT_LIMIT,
    mode_stress: bool = False,
) -> dict[str, Any]:
    """Gera e cacheia o recorte JSON enxuto de uma UF para o spike deck.gl.

    Payload por hex (chaves curtas, SEM geometria, SEM lat/lng, SEM PII):
      h   = hex_id (str)
      bm1 = índice de faixa de cor M1 (int 0–9, sobre score_priorizacao)
      br  = índice de faixa de cor Residual (int 0–9, sobre score_oport._residual)
      s   = score_priorizacao (float|None)
      sr  = score_oportunidade_residual (float|None)
      p   = pop_total (int|None)
      o   = oferta_efetiva_disponivel (int|None)

    Cap (espelha produção `components.py:1552`): se `len(df) > MAP_POINT_LIMIT`
    (35000) → cap `MAP_POINT_LIMIT_LARGE` (18000); senão → `limit` (default
    35000). Ordena por `score_priorizacao` desc (estável) antes do `.head`.
    `mode_stress=True` DESLIGA o cap (renderiza o recorte cru — achar o teto).

    A geração é determinística: mesmos inputs → mesmos `hexagons`/`view`
    byte-a-byte (o `timestamp` é o único campo variável).

    Args:
        uf: Sigla da UF (ex.: "SP").
        enriquecido_dir: Override do diretório de enriquecido (para testes).
        limit: Cap base (default MAP_POINT_LIMIT = 35000).
        mode_stress: Se True, não aplica cap (renderiza o recorte inteiro).

    Returns:
        Dict {uf, version, timestamp, view, hexagons}.

    Raises:
        FileNotFoundError: Se a partição da UF não existir.
    """
    enriquecido_dir = enriquecido_dir or _ENRIQUECIDO_DIR
    uf_upper = uf.upper()

    df = _read_uf_parquet(uf_upper, enriquecido_dir)
    if df is None or df.empty:
        raise FileNotFoundError(
            f"Dados enriquecidos para UF={uf_upper} não encontrados em "
            f"{enriquecido_dir / f'uf={uf_upper}'}. Execute o pipeline de "
            "enriquecimento antes de gerar o recorte do spike."
        )

    df = df.copy()

    # PII/geometria nunca saem (garantia estrutural, mesmo em fallback total).
    for forbidden in _PII_FORBIDDEN | (_GEOMETRY_FORBIDDEN - {"lat", "lng"}):
        if forbidden in df.columns:
            df = df.drop(columns=[forbidden])

    # Normaliza população (pop_total ou populacao_proxy).
    if "pop_total" not in df.columns and "populacao_proxy" in df.columns:
        df["pop_total"] = df["populacao_proxy"]

    if "score_priorizacao" not in df.columns:
        raise FileNotFoundError(
            f"Coluna score_priorizacao ausente na partição UF={uf_upper}."
        )

    # Ordena por score desc (estável), depois aplica o cap.
    df = df.sort_values("score_priorizacao", ascending=False, kind="stable")

    if mode_stress:
        effective_limit = len(df)
    else:
        effective_limit = (
            MAP_POINT_LIMIT_LARGE if len(df) > MAP_POINT_LIMIT else limit
        )
    df = df.head(effective_limit).reset_index(drop=True)

    # Índices de faixa pré-computados (recolor client-side sem novo payload).
    bm1 = _band_index_vec(df["score_priorizacao"])
    if "score_oportunidade_residual" in df.columns:
        br = _band_index_vec(df["score_oportunidade_residual"])
        sr_series = df["score_oportunidade_residual"]
    else:
        br = np.zeros(len(df), dtype=int)
        sr_series = pd.Series([None] * len(df))

    pop_series = df["pop_total"] if "pop_total" in df.columns else pd.Series([None] * len(df))
    oferta_series = (
        df["oferta_efetiva_disponivel"]
        if "oferta_efetiva_disponivel" in df.columns
        else pd.Series([None] * len(df))
    )

    hex_ids = df["hex_id"].astype(str).tolist()
    s_vals = [_safe_float(v) for v in df["score_priorizacao"].tolist()]
    sr_vals = [_safe_float(v) for v in sr_series.tolist()]
    p_vals = [_safe_int(v) for v in pop_series.tolist()]
    o_vals = [_safe_int(v) for v in oferta_series.tolist()]

    hexagons: list[dict[str, Any]] = [
        {
            "h": h,
            "bm1": int(b1),
            "br": int(b2),
            "s": s,
            "sr": sr,
            "p": p,
            "o": o,
        }
        for h, b1, b2, s, sr, p, o in zip(
            hex_ids, bm1, br, s_vals, sr_vals, p_vals, o_vals, strict=True
        )
    ]

    # View pré-computada (bbox) — lat/lng NÃO vão por hex.
    lats = [_safe_float(v) for v in (df["lat"].tolist() if "lat" in df.columns else [])]
    lngs = [_safe_float(v) for v in (df["lng"].tolist() if "lng" in df.columns else [])]
    view = _compute_view(
        [v for v in lats if v is not None],
        [v for v in lngs if v is not None],
    )

    resultado: dict[str, Any] = {
        "uf": uf_upper,
        "version": _SPIKE_VERSION,
        "timestamp": datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "view": view,
        "hexagons": hexagons,
    }

    # Salva em cache isolado (gitignored).
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = _CACHE_DIR / f"{uf_upper}.json"
    json_str = json.dumps(
        resultado, separators=(",", ":"), sort_keys=True, ensure_ascii=False
    )
    cache_file.write_text(json_str, encoding="utf-8")

    return resultado


def _load_cached_json(uf: str) -> dict[str, Any] | None:
    """Carrega o JSON cacheado de uma UF, ou None se inexistente."""
    cache_file = _CACHE_DIR / f"{uf.upper()}.json"
    if not cache_file.exists():
        return None
    try:
        return json.loads(cache_file.read_text(encoding="utf-8"))
    except Exception:
        return None


def _build_deckgl_html(data: dict[str, Any], height: int = 560) -> str:
    """Constrói o HTML do mapa deck.gl com dados embutidos inline.

    Motor: deck.gl UMD standalone por CDN (`H3HexagonLayer` + basemap raster
    CARTO dark via `TileLayer`). O payload embutido usa hex_id cru — a
    tesselação da célula acontece na GPU (sem geometria no JSON).

    Controles in-page (alvos do harness Playwright):
      - toggle M1↔Residual → recolor via `updateTriggers.getFillColor`
        (sem re-serializar o payload).
      - cenário múltiplo → add/remove client-side + sumário local.

    Marcadores de perf (lidos pelo Playwright, via performance.now()):
      window.__spikeFirstPaintMs  — trigger → 1º frame com dados.
      window.__spikeRecolorMs     — delta do toggle de cor.
      window.__spikeAddHexMs      — delta do último add ao cenário.

    Hooks programáticos (robustez do harness, sem depender de pixel-click):
      window.__spikeToggleColor()  window.__spikeAddHex(hexId?)

    Args:
        data: Resultado de gerar_recorte_spike_json (dict com hexagons/view).
        height: Altura do componente em pixels.

    Returns:
        String HTML completa para st.components.v1.html.
    """
    hexagons = data.get("hexagons", [])
    uf = str(data.get("uf", ""))
    view = data.get("view", _BRASIL_VIEW)

    hex_data_js = json.dumps(hexagons, separators=(",", ":"), ensure_ascii=False)
    bands_rgb_js = json.dumps(_bands_rgb(), separators=(",", ":"))
    view_js = json.dumps(view, separators=(",", ":"))

    palette = PROTO_PALETTE
    template = _DECKGL_TEMPLATE
    return (
        template.replace("__HEX_DATA__", hex_data_js)
        .replace("__BANDS_RGB__", bands_rgb_js)
        .replace("__VIEW__", view_js)
        .replace("__UF__", uf)
        .replace("__HEIGHT__", str(int(height)))
        .replace("__BG__", palette["bg"])
        .replace("__PANEL__", palette["panel"])
        .replace("__LINE__", palette["line"])
        .replace("__TEXT__", palette["text"])
        .replace("__MUTED__", palette["muted"])
        .replace("__ULTRA__", palette["ultra"])
    )


def render_mapa_deckgl(data: dict[str, Any], height: int = 560) -> None:
    """Renderiza o mapa deck.gl client-side no Streamlit.

    Usa st.components.v1.html com HTML embutido; pan/zoom/clique/recolor/
    cenário sem round-trip ao servidor.
    """
    html_str = _build_deckgl_html(data, height=height)
    components.html(html_str, height=height + 60, scrolling=False)


def is_spike_enabled() -> bool:
    """Verifica se o spike está habilitado via env var ou session_state.

    Returns:
        True se ULTRA_SPIKE_DECKGL=1 ou session_state["show_ui_spike_deckgl"].
    """
    if os.environ.get("ULTRA_SPIKE_DECKGL", "").strip() == "1":
        return True
    return bool(st.session_state.get("show_ui_spike_deckgl", False))


def render_spike_page() -> None:
    """Renderiza a página opt-in do spike (seletor de UF + mapa deck.gl).

    Deve ser chamado APENAS sob is_spike_enabled(). NÃO é importado por
    pages.py — é rota descartável de medição.
    """
    st.markdown(
        "### ULTRA SPIKE — deck.gl H3HexagonLayer (BLK-REV-08)\n\n"
        "Protótipo **descartável** de teto de performance client-side. "
        "READ-ONLY sobre o M1; produção não é afetada."
    )

    all_ufs = sorted(
        p.name.replace("uf=", "")
        for p in _ENRIQUECIDO_DIR.glob("uf=*")
        if p.is_dir()
    )
    if not all_ufs:
        st.warning(
            "Nenhuma partição de UF encontrada em "
            f"`{_ENRIQUECIDO_DIR}`. Execute o pipeline de enriquecimento."
        )
        return

    col_uf, col_stress, col_btn = st.columns([2, 1, 1])
    with col_uf:
        selected_uf = st.selectbox(
            "UF", all_ufs, index=0, key="ui_spike_deckgl_uf"
        )
    with col_stress:
        mode_stress = st.checkbox(
            "Modo stress",
            key="ui_spike_deckgl_stress",
            help="Desliga o cap e renderiza o recorte inteiro (achar o teto).",
        )
    with col_btn:
        gerar = st.button("Gerar recorte", key="ui_spike_deckgl_gerar")

    data: dict[str, Any] | None = None
    erro: str | None = None
    if gerar:
        with st.spinner(f"Gerando recorte para {selected_uf}..."):
            try:
                data = gerar_recorte_spike_json(
                    selected_uf or "SP", mode_stress=bool(mode_stress)
                )
            except FileNotFoundError as exc:
                erro = str(exc)
    else:
        data = _load_cached_json(selected_uf or "")

    if erro:
        st.error(f"Erro ao gerar recorte: {erro}")
        return
    if not data:
        st.info(
            "Selecione uma UF e clique em **Gerar recorte** para ver o mapa."
        )
        return

    n_hexes = len(data.get("hexagons", []))
    st.caption(
        f"UF: **{data.get('uf')}** | {n_hexes} hexágonos | "
        f"versão: {data.get('version')} | deck.gl H3HexagonLayer (CDN)"
    )
    render_mapa_deckgl(data, height=560)


# ──────────────────────────────────────────────────────────────
# Template HTML deck.gl (placeholders substituídos em _build_deckgl_html).
# Mantido como string plana (não f-string) para evitar escape de chaves no JS.
# ──────────────────────────────────────────────────────────────
_DECKGL_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ultra Spike deck.gl - __UF__</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; background: __BG__; overflow: hidden;
    font-family: 'IBM Plex Sans', system-ui, sans-serif; color: __TEXT__; }
  #container { position: absolute; inset: 0; }
  #container canvas { width: 100% !important; height: 100% !important; }
  #controls {
    position: absolute; top: 10px; left: 10px; z-index: 1000;
    background: __PANEL__; border: 1px solid __LINE__; border-radius: 8px;
    padding: 8px 10px; display: flex; gap: 8px; align-items: center;
    font-size: 12px;
  }
  #controls button {
    background: __BG__; color: __TEXT__; border: 1px solid __LINE__;
    border-radius: 6px; padding: 5px 10px; font-size: 12px; cursor: pointer;
  }
  #controls button:hover { border-color: __ULTRA__; }
  #scenario-summary { color: __MUTED__; }
  #detail {
    position: absolute; bottom: 16px; right: 16px; z-index: 1000;
    background: __PANEL__; border: 1px solid __LINE__; border-radius: 8px;
    padding: 12px 14px; min-width: 220px; max-width: 260px;
    font-size: 12px; display: none;
    box-shadow: 0 4px 16px rgba(0,0,0,0.4);
  }
  #detail .title {
    font-size: 11px; font-weight: 600; letter-spacing: 0.06em;
    text-transform: uppercase; color: __ULTRA__; margin-bottom: 8px;
    padding-bottom: 6px; border-bottom: 1px solid __LINE__;
  }
  #detail .row { display: flex; justify-content: space-between; gap: 6px; padding: 3px 0; }
  #detail .key { color: __MUTED__; }
  #detail .val { font-family: 'IBM Plex Mono', monospace; text-align: right; }
  #legend {
    position: absolute; top: 10px; right: 10px; z-index: 1000;
    background: __PANEL__; border: 1px solid __LINE__; border-radius: 8px;
    padding: 8px 10px; font-size: 11px; color: __MUTED__;
  }
  #legend .leg-title {
    font-weight: 600; color: __TEXT__; margin-bottom: 5px;
    letter-spacing: 0.04em; text-transform: uppercase;
  }
  .leg-row { display: flex; align-items: center; gap: 5px; margin: 2px 0; }
  .leg-dot { width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0; }
</style>
</head>
<body>
<div id="container"></div>
<div id="controls">
  <button id="toggle-mode" onclick="window.__spikeToggleColor()">Cor: M1</button>
  <button id="add-hex" onclick="window.__spikeAddHex()">Adicionar hex ao cenário</button>
  <button id="clear-scenario" onclick="window.__spikeClearScenario()">Limpar cenário</button>
  <span id="scenario-summary">Cenário: 0 hexes</span>
</div>
<div id="legend"><div class="leg-title" id="legend-title">Score M1</div><div id="legend-items"></div></div>
<div id="detail"><div class="title" id="detail-title">Hexágono</div><div id="detail-rows"></div></div>

<script src="https://unpkg.com/h3-js@4.1.0/dist/h3-js.umd.js"></script>
<script src="https://unpkg.com/deck.gl@8.9.36/dist.min.js"></script>
<script>
// ── Dados embutidos (sem round-trip) ──────────────────────────
var HEX_DATA = __HEX_DATA__;
var BANDS_RGB = __BANDS_RGB__;
var VIEW = __VIEW__;
var UF_LABEL = "__UF__";

// ── Estado client-side ────────────────────────────────────────
var colorMode = 'm1';            // 'm1' | 'residual'
var scenario = {};               // set de hex_id no cenário
var scenarioVersion = 0;         // trigger de recolor da borda
var __tStart = performance.now();
var __pendingRecolor = false, __pendingRecolorStart = 0;
var __pendingAdd = false, __pendingAddStart = 0;

// Marcadores de perf lidos pelo Playwright.
window.__spikeFirstPaintMs = null;
window.__spikeRecolorMs = null;
window.__spikeAddHexMs = null;
window.__spikeError = null;
window.__spikeHexCount = (HEX_DATA && HEX_DATA.length) || 0;

// Erro visivel na propria pagina (sem precisar de DevTools).
function __spikeReport(msg, isError) {
  var el = document.getElementById('scenario-summary');
  if (el) {
    el.textContent = msg;
    el.style.color = isError ? '#ff6b6b' : '';
  }
}
window.onerror = function(msg) {
  window.__spikeError = String(msg);
  __spikeReport('ERRO JS: ' + msg, true);
  return false;
};

var deckgl = null;

function fillColor(d) {
  var idx = colorMode === 'm1' ? d.bm1 : d.br;
  var c = BANDS_RGB[idx] || [120, 120, 120];
  return [c[0], c[1], c[2], 180];
}

function lineColor(d) {
  return scenario[d.h] ? [255, 255, 255, 255] : [12, 16, 22, 90];
}

function lineWidth(d) {
  return scenario[d.h] ? 3 : 0;
}

// Tesselação da célula H3 no CLIENTE, a partir do hex_id cru (sem geometria
// no payload). Cacheado por hex (d.__poly) — recolor/seleção não recomputam.
// h3.cellToBoundary(h, true) → anel [lng, lat] (ordem GeoJSON), que o
// PolygonLayer consome direto. Preserva a tese "payload só com hex_id".
function hexPoly(d) {
  if (d.__poly) return d.__poly;
  try {
    d.__poly = h3.cellToBoundary(d.h, true);
  } catch (e) {
    d.__poly = [];
  }
  return d.__poly;
}

function makeLayers() {
  var glo = (typeof deck !== 'undefined') ? deck : {};
  var TileLayer = glo.TileLayer;
  var BitmapLayer = glo.BitmapLayer;
  var PolygonLayer = glo.PolygonLayer;
  var layers = [];
  if (TileLayer && BitmapLayer) {
    layers.push(new TileLayer({
      id: 'basemap',
      data: 'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
      minZoom: 0, maxZoom: 19, tileSize: 256,
      renderSubLayers: function(props) {
        var b = props.tile.bbox;
        return new BitmapLayer(props, {
          data: null, image: props.data,
          bounds: [b.west, b.south, b.east, b.north]
        });
      }
    }));
  }
  layers.push(new PolygonLayer({
    id: 'hexes',
    data: HEX_DATA,
    pickable: true,
    filled: true,
    stroked: true,
    extruded: false,
    getPolygon: hexPoly,
    getFillColor: fillColor,
    getLineColor: lineColor,
    getLineWidth: lineWidth,
    lineWidthUnits: 'pixels',
    updateTriggers: {
      getFillColor: [colorMode],
      getLineColor: [scenarioVersion],
      getLineWidth: [scenarioVersion]
    },
    onClick: function(info) {
      if (info && info.object) {
        showDetail(info.object);
        window.__spikeAddHex(info.object.h);
      }
    }
  }));
  return layers;
}

function updateLayers() {
  if (deckgl) { deckgl.setProps({ layers: makeLayers() }); }
}

function fmtVal(v) {
  if (v === null || v === undefined) return '-';
  if (typeof v === 'number') return v.toLocaleString('pt-BR');
  return String(v);
}

// ── Painel de detalhe ─────────────────────────────────────────
function showDetail(hex) {
  var detailEl = document.getElementById('detail');
  var detailTitle = document.getElementById('detail-title');
  var detailRows = document.getElementById('detail-rows');
  detailEl.style.display = 'block';
  detailTitle.textContent = (hex.h || '').substring(0, 12) + '...';
  var fields = [
    ['Score M1', hex.s !== null && hex.s !== undefined ? hex.s.toFixed(1) : '-'],
    ['Score Residual', hex.sr !== null && hex.sr !== undefined ? hex.sr.toFixed(1) : '-'],
    ['Pop. Total', fmtVal(hex.p)],
    ['Oferta Residual', fmtVal(hex.o)]
  ];
  detailRows.innerHTML = fields.map(function(f) {
    return '<div class="row"><span class="key">' + f[0] +
      '</span><span class="val">' + f[1] + '</span></div>';
  }).join('');
}

// ── Legenda ───────────────────────────────────────────────────
function updateLegend() {
  document.getElementById('legend-title').textContent =
    colorMode === 'm1' ? 'Score M1' : 'Score Residual';
  var items = document.getElementById('legend-items');
  var rows = [];
  for (var i = 0; i < BANDS_RGB.length; i += 2) {
    var c = BANDS_RGB[i];
    rows.push('<div class="leg-row"><span class="leg-dot" style="background:rgb(' +
      c[0] + ',' + c[1] + ',' + c[2] + ')"></span>' + (i * 10) + '-' + ((i + 1) * 10) + '</div>');
  }
  items.innerHTML = rows.join('');
}

function updateSummary() {
  var n = Object.keys(scenario).length;
  document.getElementById('scenario-summary').textContent = 'Cenário: ' + n + ' hexes';
}

// ── Hooks programáticos (também acionados pelos botões) ───────
window.__spikeToggleColor = function() {
  __pendingRecolorStart = performance.now();
  __pendingRecolor = true;
  colorMode = colorMode === 'm1' ? 'residual' : 'm1';
  document.getElementById('toggle-mode').textContent =
    'Cor: ' + (colorMode === 'm1' ? 'M1' : 'Residual');
  updateLegend();
  updateLayers();
};

window.__spikeAddHex = function(hexId) {
  if (!hexId) {
    for (var i = 0; i < HEX_DATA.length; i++) {
      if (!scenario[HEX_DATA[i].h]) { hexId = HEX_DATA[i].h; break; }
    }
  }
  if (!hexId) return;
  __pendingAddStart = performance.now();
  __pendingAdd = true;
  scenario[hexId] = true;
  scenarioVersion++;
  updateSummary();
  updateLayers();
};

window.__spikeClearScenario = function() {
  scenario = {};
  scenarioVersion++;
  updateSummary();
  updateLayers();
};

// ── Boot ──────────────────────────────────────────────────────
function boot() {
  var glo = (typeof deck !== 'undefined') ? deck : null;
  if (!glo || !glo.DeckGL) {
    __spikeReport('deck.gl indisponível (CDN offline)', true);
    window.__spikeError = 'deckgl-unavailable';
    return;
  }
  // Diagnóstico: quais classes o bundle expõe (falha silenciosa vira visível).
  var missing = [];
  if (!glo.PolygonLayer) missing.push('PolygonLayer');
  if (!glo.TileLayer) missing.push('TileLayer');
  if (!glo.BitmapLayer) missing.push('BitmapLayer');
  if (typeof h3 === 'undefined' || !h3.cellToBoundary) missing.push('h3-js');
  if (missing.length) {
    __spikeReport('Classes ausentes no bundle: ' + missing.join(', '), true);
    window.__spikeError = 'missing:' + missing.join(',');
  }
  updateLegend();
  updateSummary();
  try {
  deckgl = new glo.DeckGL({
    container: 'container',
    initialViewState: {
      longitude: VIEW.longitude, latitude: VIEW.latitude,
      zoom: VIEW.zoom, pitch: 0, bearing: 0
    },
    controller: true,
    layers: makeLayers(),
    onAfterRender: function() {
      if (window.__spikeFirstPaintMs === null && HEX_DATA.length > 0) {
        window.__spikeFirstPaintMs = performance.now() - __tStart;
      }
      if (__pendingRecolor) {
        window.__spikeRecolorMs = performance.now() - __pendingRecolorStart;
        __pendingRecolor = false;
      }
      if (__pendingAdd) {
        window.__spikeAddHexMs = performance.now() - __pendingAddStart;
        __pendingAdd = false;
      }
    }
  });
  } catch (e) {
    window.__spikeError = String((e && e.message) || e);
    __spikeReport('ERRO ao criar deck.gl: ' + window.__spikeError, true);
  }
}

if (document.readyState === 'complete' || document.readyState === 'interactive') {
  boot();
} else {
  window.addEventListener('DOMContentLoaded', boot);
}
</script>
</body>
</html>"""
