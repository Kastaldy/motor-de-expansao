"""ui_proto.py — Página opt-in do PoC de repaginação do dashboard (BLK-UI-10).

Entregáveis:
  Fase A: Layout 3-painéis (header + sidebar KPIs + mapa central + detalhe)
          com tema visual Ultra (ui_theme.py).
  Fase B: Mapa Leaflet client-side via st.components.v1.html com dados embutidos,
          pan/zoom/clique sem round-trip ao servidor.

READ-ONLY sobre o M1: zero recálculo de score/pesos/artefatos oficiais.
Opt-in via env var `ULTRA_PROTO=1` ou session_state["show_ui_proto"] = True.

Dados consumidos (leitura):
  - data/outputs/hexagonos_dashboard_enriquecido/uf=<UF>/parte-0.parquet
  - data/staging/hexagonos_mercado_mapeado.parquet (fallback; join por hex_id)
  - data/staging/brasil_priorizados.parquet (context — top-20% por UF)

JSON de recorte: data/cache/ui_proto/<uf>.json (gitignored).
Relatório de comparação: data/reports/ui_poc_leaflet.md.
"""
from __future__ import annotations

import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from motor_expansao.dashboard.constants import RESIDUAL_SCORE_BANDS
from motor_expansao.dashboard.ui_theme import (
    PROTO_PALETTE,
    detail_panel_html,
    inject_ultra_theme,
    kpi_card_html,
)

# ──────────────────────────────────────────────────────────────
# Paths canônicos (nunca escrevem em artefatos M1 oficiais)
# ──────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parents[4]
_ENRIQUECIDO_DIR = _REPO_ROOT / "data" / "outputs" / "hexagonos_dashboard_enriquecido"
_MERCADO_PATH = _REPO_ROOT / "data" / "staging" / "hexagonos_mercado_mapeado.parquet"
_PRIORIZADOS_PATH = _REPO_ROOT / "data" / "staging" / "brasil_priorizados.parquet"
_CACHE_DIR = _REPO_ROOT / "data" / "cache" / "ui_proto"

# Colunas do recorte JSON (sem PII; sem endereço/nome_propriedade/owner)
_JSON_COLUMNS = [
    "hex_id",
    "lat",
    "lng",
    "score_priorizacao",
    "pop_total",
    "renda_per_capita",
    "score_oportunidade_residual",
    "oferta_efetiva_disponivel",
    "sam_fitness_potencial",
]

# Colunas obrigatórias do JSON (mínimo)
_JSON_REQUIRED = {"hex_id", "lat", "lng", "score_priorizacao"}

# Colunas de PII proibidas (nunca devem aparecer no JSON)
_PII_FORBIDDEN = {
    "endereco",
    "nome_propriedade",
    "owner",
    "email",
    "telefone",
    "cpf",
    "cnpj",
}

# Filtros opcionais para o recorte (reprodutíveis)
_RECORTE_POP_MIN = 5_000
_RECORTE_SCORE_MIN = 20.0

# Limite de hexes no recorte (evita JSON gigante no HTML)
_RECORTE_LIMIT = 500


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


def gerar_recorte_json(
    uf: str,
    enriquecido_dir: Path | None = None,
    mercado_path: Path | None = None,
    *,
    pop_min: int = _RECORTE_POP_MIN,
    score_min: float = _RECORTE_SCORE_MIN,
    limit: int = _RECORTE_LIMIT,
) -> dict[str, Any]:
    """Gera e salva em cache o recorte JSON enxuto de uma UF.

    Lê os parquets existentes (READ-ONLY M1) e produz um dict com a estrutura:
    {
        "uf": str,
        "version": "ui_proto_v1",
        "timestamp": ISO-8601 UTC,
        "hexagons": [ { hex_id, lat, lng, score_priorizacao, ... }, ... ]
    }

    A geração é determinística: mesmos inputs → mesmo JSON byte-a-byte
    (json.dumps com sort_keys=True e separators compactos).

    Args:
        uf: Sigla da UF (ex.: "SP").
        enriquecido_dir: Override do diretório de enriquecido (para testes).
        mercado_path: Override do path do mercado (para testes).
        pop_min: Filtro mínimo de população (default 5.000).
        score_min: Filtro mínimo de score_priorizacao (default 20).
        limit: Máximo de hexes no recorte (ordena por score desc).

    Returns:
        Dict com estrutura do recorte JSON.

    Raises:
        FileNotFoundError: Se nem o enriquecido nem o dashboard parquet existir.
    """
    enriquecido_dir = enriquecido_dir or _ENRIQUECIDO_DIR
    mercado_path = mercado_path or _MERCADO_PATH

    uf_upper = uf.upper()
    uf_part = enriquecido_dir / f"uf={uf_upper}"

    # Lê parquet da UF (enriquecido particionado)
    df: pd.DataFrame | None = None
    if uf_part.exists():
        parquet_file = uf_part / "parte-0.parquet"
        if not parquet_file.exists():
            # Tenta qualquer parquet na pasta
            candidates = sorted(uf_part.glob("*.parquet"))
            if candidates:
                parquet_file = candidates[0]
        if parquet_file.exists():
            cols_to_read = list(
                {*_JSON_COLUMNS, "populacao_proxy", "nome_municipio", "uf", "UF"}
            )
            try:
                df = pd.read_parquet(
                    parquet_file,
                    columns=[
                        c
                        for c in cols_to_read
                        # read only columns that exist; parquet.schema handles missing
                    ],
                )
            except Exception:
                # Se leitura de subset falhar, lê tudo
                df = pd.read_parquet(parquet_file)

    if df is None or df.empty:
        raise FileNotFoundError(
            f"Dados enriquecidos para UF={uf_upper} não encontrados em {uf_part}. "
            "Execute o pipeline de enriquecimento antes de gerar o recorte."
        )

    # Normaliza coluna de população (pode ser pop_total ou populacao_proxy)
    if "pop_total" not in df.columns and "populacao_proxy" in df.columns:
        df = df.copy()
        df["pop_total"] = df["populacao_proxy"]

    # Filtra: PII nunca sai (garantia estrutural)
    for pii_col in _PII_FORBIDDEN:
        if pii_col in df.columns:
            df = df.drop(columns=[pii_col])

    # Filtros de recorte (reprodutíveis com os mesmos defaults)
    if "pop_total" in df.columns:
        df = df[df["pop_total"].fillna(0) >= pop_min]
    if "score_priorizacao" in df.columns:
        df = df[df["score_priorizacao"].fillna(0) >= score_min]

    # Ordena por score descendente e limita
    if "score_priorizacao" in df.columns:
        df = df.sort_values("score_priorizacao", ascending=False, kind="stable")
    df = df.head(limit)

    # Constrói lista de hexes (somente campos do recorte JSON)
    hexagons: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        hex_entry: dict[str, Any] = {}
        for col in _JSON_COLUMNS:
            val = row.get(col)
            if col in ("lat", "lng", "score_priorizacao", "renda_per_capita",
                        "score_oportunidade_residual"):
                hex_entry[col] = _safe_float(val)
            elif col in ("pop_total", "oferta_efetiva_disponivel", "sam_fitness_potencial"):
                hex_entry[col] = _safe_int(val)
            else:
                hex_entry[col] = str(val) if val is not None and not (
                    isinstance(val, float) and math.isnan(val)
                ) else None
        hexagons.append(hex_entry)

    resultado: dict[str, Any] = {
        "uf": uf_upper,
        "version": "ui_proto_v1",
        "timestamp": datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "hexagons": hexagons,
    }

    # Salva em cache (gitignored)
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = _CACHE_DIR / f"{uf_upper}.json"
    json_str = json.dumps(resultado, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
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


def _score_to_color(score: float | None) -> str:
    """Converte score para cor hexadecimal da paleta RESIDUAL_SCORE_BANDS."""
    if score is None:
        return "#4a5568"
    for band_label, color in RESIDUAL_SCORE_BANDS:
        low, high = (int(x) for x in band_label.split("-"))
        if low <= score <= high:
            return color
    return RESIDUAL_SCORE_BANDS[-1][1]


def _build_leaflet_html(data: dict[str, Any], height: int = 560) -> str:
    """Constrói o HTML do mapa Leaflet com dados embutidos.

    Usa Leaflet e h3-js por CDN (sem dep nova no pyproject.toml).
    Padrão do totalpass: dados como arrays JS inline.
    Pan/zoom/clique sem round-trip ao servidor.

    Args:
        data: Resultado de gerar_recorte_json (dict com "hexagons").
        height: Altura do mapa em pixels.

    Returns:
        String HTML completa para st.components.v1.html.
    """
    hexagons = data.get("hexagons", [])
    uf = data.get("uf", "")

    # Paleta para colorir hexes por score
    color_map = json.dumps(
        {
            band: color
            for band, color in RESIDUAL_SCORE_BANDS
        },
        separators=(",", ":"),
    )

    # Dados JS compactos
    hex_data_js = json.dumps(hexagons, separators=(",", ":"), ensure_ascii=False)

    ultra_color = PROTO_PALETTE["ultra"]
    bg_color = PROTO_PALETTE["bg"]
    panel_color = PROTO_PALETTE["panel"]
    text_color = PROTO_PALETTE["text"]
    muted_color = PROTO_PALETTE["muted"]
    line_color = PROTO_PALETTE["line"]

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ultra PoC Leaflet — {uf}</title>
<link rel="stylesheet"
  href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
  integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
  crossorigin="anonymous">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{ height: {height}px; background: {bg_color}; }}
  #map {{ position: absolute; inset: 0; }}
  /* Painel de detalhe (canto inferior direito) */
  #detail {{
    position: absolute; bottom: 16px; right: 16px; z-index: 1000;
    background: {panel_color}; border: 1px solid {line_color};
    border-radius: 8px; padding: 12px 14px; min-width: 220px;
    max-width: 260px; color: {text_color};
    font-family: 'IBM Plex Sans', system-ui, sans-serif;
    font-size: 12px; display: none;
    box-shadow: 0 4px 16px rgba(0,0,0,0.4);
  }}
  #detail .title {{
    font-size: 11px; font-weight: 600; letter-spacing: 0.06em;
    text-transform: uppercase; color: {ultra_color}; margin-bottom: 8px;
    padding-bottom: 6px; border-bottom: 1px solid {line_color};
  }}
  #detail .row {{
    display: flex; justify-content: space-between;
    gap: 6px; padding: 3px 0;
  }}
  #detail .key {{ color: {muted_color}; }}
  #detail .val {{
    font-family: 'IBM Plex Mono', monospace;
    color: {text_color}; text-align: right;
  }}
  /* Legenda (canto superior direito) */
  #legend {{
    position: absolute; top: 10px; right: 10px; z-index: 1000;
    background: {panel_color}; border: 1px solid {line_color};
    border-radius: 8px; padding: 8px 10px;
    font-family: 'IBM Plex Sans', system-ui, sans-serif;
    font-size: 11px; color: {muted_color};
  }}
  #legend .leg-title {{
    font-weight: 600; color: {text_color};
    margin-bottom: 5px; font-size: 11px; letter-spacing: 0.04em;
    text-transform: uppercase;
  }}
  .leg-row {{ display: flex; align-items: center; gap: 5px; margin: 2px 0; }}
  .leg-dot {{
    width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0;
  }}
  /* Info do clique */
  #click-info {{
    position: absolute; top: 10px; left: 10px; z-index: 1000;
    background: {panel_color}; border: 1px solid {line_color};
    border-radius: 8px; padding: 6px 10px;
    font-family: 'IBM Plex Sans', system-ui, sans-serif;
    font-size: 11px; color: {muted_color};
    pointer-events: none;
  }}
  /* Atribuição Leaflet — mantém contraste */
  .leaflet-control-attribution {{
    background: rgba(0,0,0,0.6) !important;
    color: #aaa !important; font-size: 10px !important;
  }}
  .leaflet-control-attribution a {{ color: #7d97ad !important; }}
</style>
</head>
<body>
<div id="map"></div>
<div id="legend">
  <div class="leg-title">Score M1</div>
  <div id="leg-items"></div>
</div>
<div id="detail"><div class="title" id="detail-title">Hexágono</div><div id="detail-rows"></div></div>
<div id="click-info">Clique em um hexágono para detalhes</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
  integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV/XN/WLs="
  crossorigin="anonymous"></script>
<script src="https://unpkg.com/h3-js@4.1.0/dist/h3-js.umd.js"></script>
<script>
// ── Dados embutidos (sem round-trip) ──────────────────────────
var HEX_DATA = {hex_data_js};
var COLOR_MAP = {color_map};
var UF_LABEL = "{uf}";

// ── Mapa base (CartoDB DarkMatter — tema escuro do PoC) ────────
var map = L.map('map', {{
  zoomControl: true,
  attributionControl: true,
}});

L.tileLayer(
  'https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png',
  {{
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: 'abcd',
    maxZoom: 19,
  }}
).addTo(map);

// ── Helpers ───────────────────────────────────────────────────
function scoreToColor(score) {{
  if (score === null || score === undefined) return '#4a5568';
  var bands = Object.keys(COLOR_MAP);
  for (var i = 0; i < bands.length; i++) {{
    var parts = bands[i].split('-');
    var lo = parseInt(parts[0]);
    var hi = parseInt(parts[1]);
    if (score >= lo && score <= hi) return COLOR_MAP[bands[i]];
  }}
  return '#4a5568';
}}

function fmtVal(v) {{
  if (v === null || v === undefined) return '—';
  if (typeof v === 'number') return v.toLocaleString('pt-BR');
  return String(v);
}}

// ── Legenda ───────────────────────────────────────────────────
var legItems = document.getElementById('leg-items');
var bands = Object.keys(COLOR_MAP);
// Mostra apenas bands alternadas para compactar
[0, 2, 4, 6, 8].forEach(function(i) {{
  if (i >= bands.length) return;
  var div = document.createElement('div');
  div.className = 'leg-row';
  div.innerHTML = '<span class="leg-dot" style="background:' + COLOR_MAP[bands[i]] + '"></span>' + bands[i];
  legItems.appendChild(div);
}});

// ── Painel de detalhe ─────────────────────────────────────────
var detailEl = document.getElementById('detail');
var detailRows = document.getElementById('detail-rows');
var detailTitle = document.getElementById('detail-title');

function showDetail(hex) {{
  detailEl.style.display = 'block';
  detailTitle.textContent = (hex.hex_id || '').substring(0, 12) + '...';
  var fields = [
    ['Score M1', hex.score_priorizacao !== null ? (hex.score_priorizacao || 0).toFixed(1) : '—'],
    ['Score Residual', hex.score_oportunidade_residual !== null ? (hex.score_oportunidade_residual || 0).toFixed(1) : '—'],
    ['Pop. Total', fmtVal(hex.pop_total)],
    ['Renda per capita', hex.renda_per_capita !== null ? 'R$ ' + (hex.renda_per_capita || 0).toLocaleString('pt-BR', {{maximumFractionDigits: 0}}) : '—'],
    ['Oferta Residual', fmtVal(hex.oferta_efetiva_disponivel)],
    ['SAM Fitness', fmtVal(hex.sam_fitness_potencial)],
    ['Lat/Lng', (hex.lat || 0).toFixed(4) + ', ' + (hex.lng || 0).toFixed(4)],
  ];
  detailRows.innerHTML = fields.map(function(f) {{
    return '<div class="row"><span class="key">' + f[0] + '</span><span class="val">' + f[1] + '</span></div>';
  }}).join('');
}}

// ── Hexágonos (h3-js → Leaflet polygons) ─────────────────────
var bounds = [];
var activeLayer = null;

HEX_DATA.forEach(function(hex) {{
  if (!hex.hex_id || hex.lat === null || hex.lng === null) return;
  var boundary;
  try {{
    // h3-js: cellToBoundary retorna [[lat,lng], ...]
    boundary = h3.cellToBoundary(hex.hex_id);
  }} catch(e) {{
    return;
  }}
  var latlngs = boundary.map(function(p) {{ return [p[0], p[1]]; }});
  var color = scoreToColor(hex.score_priorizacao);
  var poly = L.polygon(latlngs, {{
    color: color,
    weight: 1,
    opacity: 0.9,
    fillColor: color,
    fillOpacity: 0.55,
  }});
  poly.hexData = hex;
  poly.on('click', function(e) {{
    // Destaca hex clicado
    if (activeLayer) activeLayer.setStyle({{ weight: 1, opacity: 0.9 }});
    e.target.setStyle({{ weight: 2.5, opacity: 1 }});
    activeLayer = e.target;
    showDetail(hex);
    document.getElementById('click-info').textContent = 'Hex: ' + (hex.hex_id || '');
    L.DomEvent.stopPropagation(e);
  }});
  poly.addTo(map);
  bounds.push([hex.lat, hex.lng]);
}});

// Centraliza o mapa nos dados
if (bounds.length > 0) {{
  map.fitBounds(bounds, {{ padding: [20, 20] }});
}} else {{
  // Brasil default se sem dados
  map.setView([-15.78, -47.93], 4);
}}

// Clique no mapa vazio fecha detalhe
map.on('click', function() {{
  detailEl.style.display = 'none';
  if (activeLayer) {{
    activeLayer.setStyle({{ weight: 1, opacity: 0.9 }});
    activeLayer = null;
  }}
  document.getElementById('click-info').textContent = 'Clique em um hexágono para detalhes';
}});
</script>
</body>
</html>"""


def render_mapa_leaflet(data: dict[str, Any], height: int = 560) -> None:
    """Renderiza o mapa Leaflet client-side no Streamlit.

    Usa st.components.v1.html com HTML embutido.
    Pan/zoom/clique sem round-trip ao servidor.

    Args:
        data: Resultado de gerar_recorte_json.
        height: Altura do componente em pixels.
    """
    html_str = _build_leaflet_html(data, height=height)
    components.html(html_str, height=height + 10, scrolling=False)


def _build_kpis_from_data(data: dict[str, Any]) -> dict[str, str]:
    """Calcula KPIs sumários a partir do recorte JSON."""
    hexagons = data.get("hexagons", [])
    n = len(hexagons)
    if n == 0:
        return {
            "hexágonos": "0",
            "score médio": "—",
            "pop. total": "—",
            "residual médio": "—",
        }

    scores = [h["score_priorizacao"] for h in hexagons if h.get("score_priorizacao") is not None]
    pops = [h["pop_total"] for h in hexagons if h.get("pop_total") is not None]
    residuais = [h["score_oportunidade_residual"] for h in hexagons
                 if h.get("score_oportunidade_residual") is not None]

    score_med = sum(scores) / len(scores) if scores else None
    pop_total = sum(pops) if pops else None
    residual_med = sum(residuais) / len(residuais) if residuais else None

    return {
        "hexágonos": f"{n:,}".replace(",", "."),
        "score médio": f"{score_med:.1f}" if score_med is not None else "—",
        "pop. total": f"{pop_total:,.0f}".replace(",", ".") if pop_total else "—",
        "residual médio": f"{residual_med:.1f}" if residual_med is not None else "—",
    }


def render_proto_page() -> None:
    """Renderiza a página opt-in do PoC (Fases A + B).

    Deve ser chamado APENAS quando ULTRA_PROTO=1 ou
    session_state["show_ui_proto"] == True.

    Layout:
      [header strip]
      [col_left: KPIs/filtros] | [col_center: mapa Leaflet] | [col_right: detalhe]
    """
    inject_ultra_theme()

    # ── Banner de opt-in ──────────────────────────────────────
    st.markdown(
        '<div class="ui-proto-root">'
        '<div class="ui-proto-banner">'
        '<strong>ULTRA PROTO</strong> '
        "— PoC de repaginação (BLK-UI-10). Produção em outra aba."
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    # ── Header strip ─────────────────────────────────────────
    st.markdown(
        '<div class="ui-proto-root">'
        '<div class="ui-proto-header">'
        "Ultra Academia"
        ' <span class="ui-proto-badge">PROTO</span>'
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    # ── Seletor de UF (para gerar recorte) ───────────────────
    all_ufs = sorted(
        p.name.replace("uf=", "")
        for p in _ENRIQUECIDO_DIR.glob("uf=*")
        if p.is_dir()
    )
    if not all_ufs:
        st.warning(
            "Nenhuma partição de UF encontrada em "
            f"`{_ENRIQUECIDO_DIR.relative_to(_REPO_ROOT)}`. "
            "Execute o pipeline de enriquecimento."
        )
        return

    col_uf, col_btn = st.columns([2, 1])
    with col_uf:
        selected_uf = st.selectbox(
            "UF",
            all_ufs,
            index=0,
            key="ui_proto_uf",
            label_visibility="collapsed",
        )
    with col_btn:
        gerar = st.button("Gerar recorte", key="ui_proto_gerar")

    # ── Layout 3 painéis ─────────────────────────────────────
    col_left, col_center, col_right = st.columns([1, 3, 1])

    # Carrega ou gera o recorte JSON
    data: dict[str, Any] | None = None
    erro: str | None = None

    if gerar or _load_cached_json(selected_uf or "") is not None:
        if gerar:
            with st.spinner(f"Gerando recorte para {selected_uf}..."):
                try:
                    data = gerar_recorte_json(selected_uf or "SP")
                    st.success(
                        f"{len(data.get('hexagons', []))} hexágonos gerados para {selected_uf}."
                    )
                except FileNotFoundError as exc:
                    erro = str(exc)
        else:
            data = _load_cached_json(selected_uf or "")

    # ── Coluna esquerda: KPIs ─────────────────────────────────
    with col_left:
        st.markdown(
            '<div class="ui-proto-root"><div class="ui-proto-sidebar">'
            "<h3>Sumário</h3>",
            unsafe_allow_html=True,
        )
        if data:
            kpis = _build_kpis_from_data(data)
            for label, value in kpis.items():
                st.markdown(kpi_card_html(label, value), unsafe_allow_html=True)
        else:
            st.markdown(
                '<p style="color:#7d97ad;font-size:0.8rem;">Gere um recorte para ver KPIs.</p>',
                unsafe_allow_html=True,
            )
        st.markdown("</div></div>", unsafe_allow_html=True)

        # Legenda de score
        st.markdown('<div class="ui-proto-root">', unsafe_allow_html=True)
        st.markdown(
            '<div class="ui-proto-legend">'
            + "".join(
                f'<span class="ui-proto-legend-chip">'
                f'<span class="ui-proto-legend-dot" style="background:{color}"></span>'
                f"{band}"
                f"</span>"
                for band, color in RESIDUAL_SCORE_BANDS[::2]  # alternado para compactar
            )
            + "</div>",
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Coluna central: mapa Leaflet ──────────────────────────
    with col_center:
        if erro:
            st.error(f"Erro ao gerar recorte: {erro}")
        elif data:
            n_hexes = len(data.get("hexagons", []))
            st.caption(
                f"UF: **{data.get('uf')}** | "
                f"{n_hexes} hexágonos | "
                f"versão: {data.get('version')} | "
                f"Leaflet + h3-js (CDN)"
            )
            render_mapa_leaflet(data, height=520)
        else:
            # Estado vazio — instrução clara sem crashar
            st.markdown(
                '<div class="ui-proto-root">'
                '<div class="ui-proto-map-panel" style="height:520px;display:flex;'
                'align-items:center;justify-content:center;">'
                f'<span style="color:{PROTO_PALETTE["muted"]};font-size:0.9rem;">'
                "Selecione uma UF e clique em <strong>Gerar recorte</strong> para ver o mapa."
                "</span>"
                "</div></div>",
                unsafe_allow_html=True,
            )

    # ── Coluna direita: detalhe (placeholder) ─────────────────
    with col_right:
        st.markdown(
            '<div class="ui-proto-root"><div class="ui-proto-sidebar">',
            unsafe_allow_html=True,
        )
        st.markdown("<h3>Detalhe</h3>", unsafe_allow_html=True)
        if data and data.get("hexagons"):
            # Exibe o hex de score mais alto como exemplo
            top_hex = data["hexagons"][0]
            fields = {
                "hex_id": (top_hex.get("hex_id") or "")[:14] + "…",
                "score M1": (
                    f"{top_hex['score_priorizacao']:.1f}"
                    if top_hex.get("score_priorizacao") is not None
                    else "—"
                ),
                "score residual": (
                    f"{top_hex['score_oportunidade_residual']:.1f}"
                    if top_hex.get("score_oportunidade_residual") is not None
                    else "—"
                ),
                "pop. total": (
                    f"{top_hex['pop_total']:,}".replace(",", ".")
                    if top_hex.get("pop_total") is not None
                    else "—"
                ),
                "oferta": (
                    f"{top_hex['oferta_efetiva_disponivel']:,}".replace(",", ".")
                    if top_hex.get("oferta_efetiva_disponivel") is not None
                    else "—"
                ),
            }
            st.markdown(
                detail_panel_html(fields, title="Top hex do recorte"),
                unsafe_allow_html=True,
            )
            st.caption("Clique em hexágono no mapa para detalhes em tempo real.")
        else:
            st.markdown(
                f'<p style="color:{PROTO_PALETTE["muted"]};font-size:0.8rem;">'
                "Clique em um hexágono no mapa."
                "</p>",
                unsafe_allow_html=True,
            )
        st.markdown("</div></div>", unsafe_allow_html=True)


def is_proto_enabled() -> bool:
    """Verifica se o PoC está habilitado via env var ou session_state.

    Returns:
        True se ULTRA_PROTO=1 ou session_state["show_ui_proto"] == True.
    """
    if os.environ.get("ULTRA_PROTO", "").strip() == "1":
        return True
    return bool(st.session_state.get("show_ui_proto", False))
