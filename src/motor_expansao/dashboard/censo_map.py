from __future__ import annotations

from collections.abc import Callable, Iterable
from io import BytesIO
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageEnhance, ImageFont
from shapely.geometry import MultiPolygon, Point, Polygon, box
from shapely.geometry.base import BaseGeometry

from motor_expansao.dashboard.censo_point import (
    CRS_ORIGEM_CENSO,
    RAIO_CENSITARIO_DEFAULT_KM,
    _bbox_prefilter,
    _decode_geometry,
    _local_metric_crs,
    _project_geometry,
    _transformer,
    analisar_ponto_censitario_setores,
)
from motor_expansao.dashboard.competitors import _render_pin_tile
from motor_expansao.dashboard.constants import (
    DENSIDADE_POP_BANDS,
    RENDA_PER_CAPITA_BANDS,
)
from motor_expansao.dashboard.utils import score_band_to_color

# Cache local de tiles do basemap (DEC-004). Nunca versionado (.gitignore: data/cache/).
# Cada ponto cobre ~3 km de lado -> poucos tiles; dedup por-tile do contextily.
_BASEMAP_CACHE_DIR = Path("data/cache/basemap_tiles")

# Estilo do fundo de ruas: CartoDB **Voyager** COM labels (base CLARA estilo GeoFusion) —
# trocado da Dark Matter pelo gate BLK-CENSO-03 (Felipe, 2026-06-08) para o mapa de calor nao
# ficar escuro. No Voyager as ruas sao linhas ESCURAS finas e os nomes escuros sobre fundo
# claro — nitidos nativamente, sem nenhum realce/edge artificial. O choropleth translucido por
# cima fornece a cor; para a cor nao apagar o arruamento, recolocamos POR CIMA os PROPRIOS
# pixels ESCUROS do tile (ruas+nomes nativos — NAO e edge-detection; ver _STREET_*).
# O provedor e resolvido lazy em _fetch_basemap (ctx.providers.CartoDB.<_BASEMAP_PROVIDER_ATTR>).
_BASEMAP_PROVIDER_ATTR = "Voyager"
_BASEMAP_CONTRAST = 1.15
# Zoom extra dos tiles (alem do minimo p/ cobrir a bbox) -> ruas mais nitidas/detalhadas.
_BASEMAP_ZOOM_BUMP = 1

# Cores dos elementos desenhados DENTRO do mapa claro (precisam contrastar com fundo claro):
# circulo do raio (laranja, como o do dashboard) e barra de escala/labels em tinta ESCURA.
# _CIRCLE_RGBA: laranja, visivel sobre o fundo claro (decisao gate BLK-CENSO-03).
_CIRCLE_RGBA = (255, 176, 59, 235)
_DARK_MAP_INK = (31, 41, 55)

# Ruas/nomes do Voyager sao pixels ESCUROS sobre fundo claro. Para o choropleth nao apagar
# o arruamento, recolocamos POR CIMA do heat os PROPRIOS pixels escuros do basemap (ruas+nomes
# nativos do tile — NAO e edge-detection): luminancia < `_STREET_CEIL` vira opacidade (ganho
# `_STREET_GAIN`, teto `_STREET_CAP`). Resultado = ruas escuras nitidas sobre a cor, estilo
# GeoFusion. RENDER apenas (READ-ONLY M1).
_STREET_CEIL = 160
_STREET_GAIN = 2.2
_STREET_CAP = 210

# Margem do frame do mapa em torno do circulo de 1.5 km. O choropleth (display) cobre TODO
# o frame (setores recortados a este RETANGULO com a proporcao da area de mapa), nao so o
# circulo — estilo GeoFusion, sem letterbox. A analise (KPIs) segue circular/INTOCADA; e so RENDER.
_MAP_FRAME_MARGIN = 0.08

# Web Mercator (CRS nativo dos tiles). A composicao do mapa novo acontece em 3857;
# o motor (intersecao setor x circulo 1.5 km) segue intocado em aeqd local (censo_point).
CRS_WEB_MERCATOR = "EPSG:3857"

MAPA_CENSITARIO_METRICAS = {
    "pop_estimada_intersecao": "Pop. estimada",
    "renda_per_capita_setor_2022_calibrada": "Renda per capita",
    "score_setor_2022_calibrado": "Score censitario",
    "peso_area_setor": "Peso de area",
}

# Chaves canonicas das 4 camadas combinadas (BLK-CENSO-03-FU5): `score` e o choropleth de
# score censitario COM legenda; `concorrentes` e o mapa SO de pins (sem choropleth).
CAMADAS_CENSITARIAS = ("densidade", "renda", "score", "concorrentes")

_SECTOR_PALETTE = [
    (232, 242, 255, 225),
    (176, 211, 245, 225),
    (111, 166, 214, 225),
    (247, 196, 97, 225),
    (214, 93, 74, 225),
]

# Alpha do choropleth (heat) sobre o basemap CLARO Voyager. Mais opaco que no fundo escuro para
# a cor de faixa ser legivel sobre o claro; as ruas escuras do Voyager sao RECOLOCADAS por cima
# depois (_STREET_*), entao o arruamento nao se perde. A legenda usa RGB solido (ignora este
# alpha), entao as faixas seguem nitidas na legenda.
_CHOROPLETH_ALPHA = 140

# Cor de fill para setor sem dado na faixa nova (cinza translucido).
_FILL_SEM_DADO = (218, 222, 229, _CHOROPLETH_ALPHA)


def _with_choropleth_alpha(rgba: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """Aplica o alpha canonico do choropleth (mantem RGB da faixa)."""
    return (int(rgba[0]), int(rgba[1]), int(rgba[2]), _CHOROPLETH_ALPHA)


def _map_box(width: int, height: int) -> tuple[int, int, int, int]:
    """Retangulo (left, top, right, bottom) da area de mapa dentro da figura."""
    return (28, 92, width - 285, height - 54)


def _map_inner_dims(width: int, height: int) -> tuple[float, float]:
    """Dimensoes uteis (inner_w, inner_h) onde o frame e desenhado (sem o padding de 12px)."""
    left, top, right, bottom = _map_box(width, height)
    return (float(right - left - 24), float(bottom - top - 24))


def _font(size: int = 12) -> ImageFont.ImageFont:
    # truetype() devolve FreeTypeFont (nao subclasse de ImageFont nos stubs Pillow);
    # cast preserva runtime e mantem a assinatura aceita por _draw_text/_text_width.
    try:
        return cast(ImageFont.ImageFont, ImageFont.truetype("arial.ttf", size))
    except OSError:
        return cast(ImageFont.ImageFont, ImageFont.load_default())


def _iter_polygons(geom: BaseGeometry) -> Iterable[Polygon]:
    if isinstance(geom, Polygon):
        yield geom
    elif isinstance(geom, MultiPolygon):
        yield from geom.geoms
    elif hasattr(geom, "geoms"):
        for item in geom.geoms:
            yield from _iter_polygons(item)


def _metric_values(df: pd.DataFrame, metric_column: str) -> pd.Series:
    if metric_column not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype="float64")
    return pd.to_numeric(df[metric_column], errors="coerce")


def _color_for_value(value: float, breaks: list[float]) -> tuple[int, int, int, int]:
    if pd.isna(value):
        return (218, 222, 229, 210)
    if not breaks:
        return _SECTOR_PALETTE[2]
    idx = int(np.searchsorted(breaks, float(value), side="right"))
    idx = max(0, min(idx, len(_SECTOR_PALETTE) - 1))
    return _SECTOR_PALETTE[idx]


def _build_breaks(values: pd.Series) -> list[float]:
    valid = values.dropna()
    if valid.empty or valid.nunique() <= 1:
        return []
    quantiles = valid.quantile([0.2, 0.4, 0.6, 0.8]).to_numpy(dtype=float)
    return sorted({round(float(value), 6) for value in quantiles})


# ── Cores por faixa absoluta fixa (substitui o quartil no caminho novo) ──────────


def _color_for_bands(
    value: float,
    bands: list[tuple[float, str, tuple[int, int, int, int]]],
) -> tuple[int, int, int, int]:
    if pd.isna(value):
        return _FILL_SEM_DADO
    val = float(value)
    for upper, _label, color in bands:
        if val <= upper:
            return color
    return bands[-1][2]


def _color_for_densidade(value: float) -> tuple[int, int, int, int]:
    return _with_choropleth_alpha(_color_for_bands(value, DENSIDADE_POP_BANDS))


def _color_for_renda(value: float) -> tuple[int, int, int, int]:
    return _with_choropleth_alpha(_color_for_bands(value, RENDA_PER_CAPITA_BANDS))


def _color_for_score(value: float) -> tuple[int, int, int, int]:
    rgba = score_band_to_color(value, alpha=_CHOROPLETH_ALPHA)
    return (int(rgba[0]), int(rgba[1]), int(rgba[2]), int(rgba[3]))


def _format_value(value: float) -> str:
    if pd.isna(value):
        return "-"
    abs_value = abs(float(value))
    if abs_value >= 1000:
        return f"{value:,.0f}".replace(",", ".")
    if abs_value >= 10:
        return f"{value:.1f}"
    return f"{value:.2f}"


def _metric_label(metric_column: str) -> str:
    return MAPA_CENSITARIO_METRICAS.get(metric_column, metric_column)


def _draw_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    *,
    fill: tuple[int, int, int] = (31, 41, 55),
    font: ImageFont.ImageFont | None = None,
) -> None:
    draw.text(xy, text, fill=fill, font=font or _font())


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    left, _, right, _ = draw.textbbox((0, 0), text, font=font)
    return int(right - left)


def _polygon_to_pixels(
    polygon: Polygon,
    project: Callable[[float, float], tuple[float, float]],
) -> list[tuple[int, int]]:
    coords = [project(x, y) for x, y in polygon.exterior.coords]
    return [(int(round(x)), int(round(y))) for x, y in coords]


def _draw_scale_bar(
    draw: ImageDraw.ImageDraw,
    map_box: tuple[int, int, int, int],
    meters_per_px: float,
) -> None:
    left, _, _, bottom = map_box
    candidates = [1000, 750, 500, 250, 100]
    scale_m = next((value for value in candidates if value / meters_per_px <= 140), 100)
    px_len = max(20, int(round(scale_m / meters_per_px)))
    x0 = left + 18
    y0 = bottom - 28
    # Barra de escala em tinta ESCURA (dentro do mapa claro Voyager).
    draw.line([(x0, y0), (x0 + px_len, y0)], fill=_DARK_MAP_INK, width=4)
    draw.line([(x0, y0 - 5), (x0, y0 + 5)], fill=_DARK_MAP_INK, width=2)
    draw.line([(x0 + px_len, y0 - 5), (x0 + px_len, y0 + 5)], fill=_DARK_MAP_INK, width=2)
    label = f"{scale_m // 1000} km" if scale_m >= 1000 else f"{scale_m} m"
    _draw_text(draw, (x0, y0 + 7), label, font=_font(11), fill=_DARK_MAP_INK)


def _paste_logo_pin(
    image: Image.Image,
    px: int,
    py: int,
    key: str,
    *,
    size: int = 40,
) -> None:
    """Cola o pin (balao + logo OU sigla) de `competitors._render_pin_tile` no mapa.

    Ancora a PONTA do balao (anchorY do tile 128x128) no ponto (px, py): o tile e
    desenhado com a ponta na base, entao posicionamos `(px - w//2, py - h)`. Reusa a
    mascara alpha do tile RGBA. Logo real quando ha PNG no _ICON_CACHE; sigla no fallback.
    """
    tile = cast(Image.Image, _render_pin_tile(key))
    tile = tile.resize((size, size), Image.Resampling.LANCZOS)
    image.paste(tile, (int(px) - size // 2, int(py) - size), tile)


def _draw_legend_camada(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    titulo: str,
    entries: list[tuple[str, tuple[int, int, int, int]]],
) -> None:
    """Legenda por camada: faixas fixas (label + amostra de cor) + pins de referencia."""
    title_font = _font(14)
    body_font = _font(11)
    _draw_text(draw, (x, y), "Legenda", font=title_font)
    _draw_text(draw, (x, y + 22), titulo, font=body_font)

    base_y = y + 50
    for idx, (label, color) in enumerate(entries):
        yy = base_y + idx * 24
        draw.rectangle([x, yy, x + 22, yy + 16], fill=color[:3], outline=(148, 163, 184))
        _draw_text(draw, (x + 32, yy), label, font=body_font)

    yy = base_y + len(entries) * 24 + 12
    _draw_center_pin(draw, x + 10, yy + 18, scale=0.7)
    _draw_text(draw, (x + 32, yy), "Ponto central", font=body_font)
    _draw_text(draw, (x + 32, yy + 24), "Pins: Ultra e concorrentes", font=body_font)


def _draw_center_pin(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    *,
    scale: float = 1.0,
) -> None:
    """Pin VERMELHO de mapa com a PONTA ancorada no ponto central (cx, cy)."""
    red = (220, 38, 38)
    white = (255, 255, 255)
    r = max(4, int(round(9 * scale)))
    head_cy = cy - int(round(22 * scale))
    # corpo: triangulo da base da cabeca ate a ponta no ponto
    draw.polygon([(cx, cy), (cx - r, head_cy), (cx + r, head_cy)], fill=red)
    # cabeca do pin
    draw.ellipse([cx - r, head_cy - r, cx + r, head_cy + r], fill=red, outline=white, width=2)
    # furo central branco
    hole = max(2, int(round(3 * scale)))
    draw.ellipse([cx - hole, head_cy - hole, cx + hole, head_cy + hole], fill=white)


def _decode_intersections(
    lat: float,
    lng: float,
    setores_df: pd.DataFrame,
    raio_km: float,
    clip_box_metric: BaseGeometry,
) -> tuple[list[dict[str, object]], BaseGeometry]:
    """Decodifica os setores que cobrem o FRAME do mapa (quadrado em torno do circulo),
    recortados ao `clip_box_metric` — NAO ao circulo — p/ o choropleth cobrir o frame todo
    (estilo GeoFusion). Os valores (densidade/renda/score) vem da PROPRIA linha do setor em
    `setores_df`, entao setores fora do circulo tambem saem coloridos. Display-only; a analise
    (KPIs por `analisar_ponto_censitario_setores`) segue circular e INTOCADA.
    """
    metric_crs = _local_metric_crs(lat, lng)
    to_metric = _transformer(CRS_ORIGEM_CENSO, metric_crs)
    to_wgs84 = _transformer(metric_crs, CRS_ORIGEM_CENSO)
    circle_metric = Point(0, 0).buffer(raio_km * 1000.0, quad_segs=96)
    clip_wgs84 = _project_geometry(clip_box_metric, to_wgs84)

    if setores_df is None or setores_df.empty:
        return [], circle_metric

    geometry_col = "geometry_wkb" if "geometry_wkb" in setores_df.columns else "geometry"
    if geometry_col not in setores_df.columns:
        return [], circle_metric

    candidates = _bbox_prefilter(setores_df, clip_wgs84)
    records: list[dict[str, object]] = []
    for _, row in candidates.iterrows():
        geom_wgs84 = _decode_geometry(row[geometry_col])
        if geom_wgs84 is None:
            continue
        clipped = _project_geometry(geom_wgs84, to_metric).intersection(clip_box_metric)
        if clipped.is_empty:
            continue
        records.append(
            {
                "cod_setor": str(row.get("cod_setor", "")),
                "geometry_metric": clipped,
                "densidade_pop_setor_hab_km2": row.get("densidade_pop_setor_hab_km2"),
                "renda_per_capita_setor_2022_calibrada": row.get("renda_per_capita_setor_2022_calibrada"),
                "renda_per_capita_setor_2022": row.get("renda_per_capita_setor_2022"),
                "score_setor_2022_calibrado": row.get("score_setor_2022_calibrado"),
            }
        )
    return records, circle_metric


def _to_mercator(geom: BaseGeometry, lat: float, lng: float) -> BaseGeometry:
    """Reprojeta uma geometria do aeqd local (CRS do motor) -> EPSG:3857, SO para render."""
    to_3857 = _transformer(_local_metric_crs(lat, lng), CRS_WEB_MERCATOR)
    return _project_geometry(geom, to_3857)


def _point_to_mercator(x_local: float, y_local: float, lat: float, lng: float) -> tuple[float, float]:
    to_3857 = _transformer(_local_metric_crs(lat, lng), CRS_WEB_MERCATOR)
    return to_3857.transform(x_local, y_local)


def _project_points(
    points_df: pd.DataFrame,
    lat: float,
    lng: float,
) -> list[tuple[float, float, str]]:
    """Reprojeta pontos (lat/lng) -> aeqd local. Devolve (x, y, key) para o pin.

    `key` e a rede (concorrente) ou "__ultra__"; resolvido a partir da coluna `rede`.
    """
    if points_df is None or points_df.empty or not {"lat", "lng"}.issubset(points_df.columns):
        return []
    to_metric = _transformer(CRS_ORIGEM_CENSO, _local_metric_crs(lat, lng))
    coords: list[tuple[float, float, str]] = []
    for _, row in points_df.iterrows():
        point_lat = pd.to_numeric(row.get("lat"), errors="coerce")
        point_lng = pd.to_numeric(row.get("lng"), errors="coerce")
        if pd.isna(point_lat) or pd.isna(point_lng):
            continue
        x, y = to_metric.transform(float(point_lng), float(point_lat))
        rede = row.get("rede")
        key = str(rede) if rede is not None and not pd.isna(rede) and str(rede).strip() else ""
        coords.append((x, y, key))
    return coords


def _zoom_for_bounds(minx: float, maxx: float, target_px: int) -> int:
    """Escolhe o menor zoom cujo grid de tiles (256 px) cubra a bbox 3857 com >= target_px.

    A resolucao 3857 no zoom z e (2*pi*R)/(256*2^z) m/px; queremos span/res >= target_px.
    """
    earth_circumference = 2.0 * np.pi * 6378137.0
    span_m = max(maxx - minx, 1.0)
    for zoom in range(0, 20):
        res = earth_circumference / (256.0 * (2**zoom))
        if span_m / res >= target_px:
            return max(0, min(zoom, 19))
    return 19


def _fetch_basemap(
    bounds_3857: tuple[float, float, float, float],
    width: int,
) -> tuple[object, tuple[float, float, float, float]] | None:
    """Busca tiles de basemap claro (CartoDB Voyager No-Labels) via contextily.

    Import LAZY sob try/except: se o extra `[basemap]` nao estiver instalado OU o fetch
    falhar (sem internet/timeout), devolve None e o chamador cai no fallback offline.
    Aplica realce de contraste `_BASEMAP_CONTRAST` p/ as ruas aparecerem sob o choropleth.
    Cache local em data/cache/basemap_tiles/. Retorna (img_array, extent_3857) ou None.
    """
    try:
        import contextily as ctx  # lazy: so existe com o extra [basemap]
    except ImportError:
        return None
    try:
        _BASEMAP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            ctx.set_cache_dir(str(_BASEMAP_CACHE_DIR))
        except Exception:
            pass
        minx, miny, maxx, maxy = bounds_3857
        zoom = min(19, _zoom_for_bounds(minx, maxx, width) + _BASEMAP_ZOOM_BUMP)
        source = getattr(ctx.providers.CartoDB, _BASEMAP_PROVIDER_ATTR)
        img, extent = ctx.bounds2img(minx, miny, maxx, maxy, zoom=zoom, source=source, ll=False)
        if _BASEMAP_CONTRAST != 1.0:
            base = Image.fromarray(np.asarray(img)).convert("RGB")
            base = ImageEnhance.Contrast(base).enhance(_BASEMAP_CONTRAST)
            arr = np.asarray(base)
            alpha = np.full((arr.shape[0], arr.shape[1], 1), 255, dtype=np.uint8)
            img = np.concatenate([arr, alpha], axis=2)
        return img, extent
    except Exception:
        return None


def _render_camada(
    *,
    titulo: str,
    legenda_titulo: str,
    legenda_entries: list[tuple[str, tuple[int, int, int, int]]],
    color_fn: Callable[[float], tuple[int, int, int, int]],
    source_values: pd.Series,
    sector_records_3857: list[tuple[BaseGeometry, int]],
    circle_3857: BaseGeometry,
    center_3857: tuple[float, float],
    pins: list[tuple[float, float, str]],
    ultra_pins: list[tuple[float, float, str]],
    basemap: tuple[object, tuple[float, float, float, float]] | None,
    bounds: tuple[float, float, float, float],
    lat: float,
    lng: float,
    raio_km: float,
    n_setores: int,
    width: int,
    height: int,
    pins_only: bool = False,
    street_ceil: int | None = None,
    street_gain: float | None = None,
    street_cap: int | None = None,
) -> bytes:
    """Desenha UMA camada (mesmos bbox/projecao/basemap/pins; varia fill + legenda).

    Quando `pins_only=True` (camada Concorrentes): pula o choropleth de faixas E o overlay
    de ruas de pixel; mantem basemap + circulo + ponto central + pins de concorrentes/Ultra +
    escala + footer + legenda so de pins. BLK-CENSO-03.
    """
    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image, "RGBA")
    title_font = _font(20)
    body_font = _font(12)
    small_font = _font(11)

    _draw_text(draw, (28, 22), titulo, font=title_font)
    subtitle = f"Centro: {lat:.6f}, {lng:.6f} | raio {raio_km:.1f} km | setores: {n_setores}"
    _draw_text(draw, (28, 52), subtitle, font=body_font, fill=(71, 85, 105))

    map_box = _map_box(width, height)
    legend_x = width - 252
    left, top, right, bottom = map_box

    minx, miny, maxx, maxy = bounds
    span_x = max(maxx - minx, 1.0)
    span_y = max(maxy - miny, 1.0)
    inner_w = right - left - 24
    inner_h = bottom - top - 24
    scale = min(inner_w / span_x, inner_h / span_y)
    offset_x = left + 12 + (inner_w - span_x * scale) / 2
    offset_y = top + 12 + (inner_h - span_y * scale) / 2

    def project(x: float, y: float) -> tuple[float, float]:
        px = offset_x + (x - minx) * scale
        py = offset_y + (maxy - y) * scale
        return px, py

    # Fundo: basemap Voyager (3857) quando disponivel; senao canvas claro (fallback offline).
    # As ruas/nomes vem NATIVOS do tile (linhas escuras finas sobre fundo claro) — sem realce
    # artificial: base clara estilo GeoFusion.
    drew_basemap = False
    basemap_patch: Image.Image | None = None  # ruas/nomes claros p/ recolocar por cima da cor
    if basemap is not None:
        try:
            img_array, extent = basemap
            bm = Image.fromarray(np.asarray(img_array)).convert("RGB")
            ex_minx, ex_maxx, ex_miny, ex_maxy = extent
            # mapeia o extent dos tiles (3857) para pixels e cola
            tx0, ty0 = project(ex_minx, ex_maxy)  # canto superior-esquerdo
            tx1, ty1 = project(ex_maxx, ex_miny)  # canto inferior-direito
            box_w = max(1, int(round(tx1 - tx0)))
            box_h = max(1, int(round(ty1 - ty0)))
            bm = bm.resize((box_w, box_h), Image.Resampling.LANCZOS)
            crop = Image.new("RGB", (width, height), (245, 245, 245))
            crop.paste(bm, (int(round(tx0)), int(round(ty0))))
            # recorta a area do map_box e cola so ela (mantem moldura)
            patch = crop.crop((left, top, right, bottom))
            image.paste(patch, (left, top))
            draw.rounded_rectangle(map_box, radius=6, outline=(71, 85, 105))
            basemap_patch = patch
            drew_basemap = True
        except Exception:
            drew_basemap = False
            basemap_patch = None
    if not drew_basemap:
        # Fallback offline: canvas claro (sem ruas), coerente com o tema claro do mapa.
        draw.rounded_rectangle(map_box, radius=6, fill=(245, 245, 245), outline=(71, 85, 105))

    # choropleth por faixa fixa (alpha translucido -> ruas ESCURAS do basemap claro aparecem por
    # cima depois). SEM borda nos setores: transicao suave entre faixas (estilo GeoFusion).
    # Pulado quando pins_only=True (camada Concorrentes = so basemap + pins).
    if not pins_only:
        for geom_3857, idx in sector_records_3857:
            color = color_fn(source_values.iloc[idx])
            for polygon in _iter_polygons(geom_3857):
                points = _polygon_to_pixels(polygon, project)
                if len(points) >= 3:
                    draw.polygon(points, fill=color)
                    for interior in polygon.interiors:
                        hole = [
                            (int(round(px)), int(round(py)))
                            for px, py in (project(a, b) for a, b in interior.coords)
                        ]
                        if len(hole) >= 3:
                            draw.polygon(hole, fill=(200, 200, 200, 80))

    # Ruas/nomes do Voyager (pixels ESCUROS) recolocados POR CIMA da cor, com os PROPRIOS
    # pixels do tile (nao edge-detection): luminancia baixa -> opacidade -> arruamento nitido
    # sobre o choropleth, estilo GeoFusion. Antes do circulo/pins/escala (que ficam no topo).
    # Pulado quando pins_only=True (sem choropleth -> nao precisa recolocar ruas). RENDER apenas.
    if basemap_patch is not None and not pins_only:
        ceil = _STREET_CEIL if street_ceil is None else street_ceil
        gain = _STREET_GAIN if street_gain is None else street_gain
        cap = _STREET_CAP if street_cap is None else street_cap
        lum = basemap_patch.convert("L")
        street_mask = lum.point(
            lambda v: 0 if v >= ceil else min(cap, int((ceil - v) * gain))
        )
        region = image.crop((left, top, right, bottom))
        region.paste(basemap_patch, (0, 0), street_mask)
        image.paste(region, (left, top))

    circle_points = [
        (int(round(px)), int(round(py)))
        for px, py in (project(x, y) for x, y in circle_3857.exterior.coords)
    ]
    if len(circle_points) >= 3:
        # Circulo do raio em LARANJA (como o do mapa do dashboard), visivel sobre o fundo escuro.
        draw.line(circle_points + [circle_points[0]], fill=_CIRCLE_RGBA, width=3)

    cx, cy = project(*center_3857)
    _draw_center_pin(draw, int(round(cx)), int(round(cy)))

    for x_local, y_local, key in pins:
        mx, my = _point_to_mercator(x_local, y_local, lat, lng)
        px, py = project(mx, my)
        _paste_logo_pin(image, int(round(px)), int(round(py)), key or "")
    for x_local, y_local, _key in ultra_pins:
        mx, my = _point_to_mercator(x_local, y_local, lat, lng)
        px, py = project(mx, my)
        _paste_logo_pin(image, int(round(px)), int(round(py)), "__ultra__")

    if not sector_records_3857 and not pins_only:
        message = "Sem setores intersectados no raio"
        msg_w = _text_width(draw, message, body_font)
        _draw_text(
            draw,
            (int((left + right - msg_w) / 2), int((top + bottom) / 2)),
            message,
            font=body_font,
            fill=_DARK_MAP_INK,
        )

    meters_per_px = 1 / scale
    _draw_scale_bar(draw, map_box, meters_per_px)
    _draw_legend_camada(draw, legend_x, 96, legenda_titulo, legenda_entries)

    if drew_basemap:
        fundo = "Fundo de ruas: CartoDB Voyager. (c) OpenStreetMap, (c) CARTO."
    else:
        fundo = "Fundo de ruas indisponivel offline (instale o extra [basemap] p/ ruas)."
    footer = (
        "Metodo: intersecao geometrica setor x circulo em CRS metrico local (raio 1.5 km). "
        f"Render em EPSG:3857. {fundo}"
    )
    _draw_text(draw, (28, height - 34), footer, font=small_font, fill=(71, 85, 105))

    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def _bands_legend_entries(
    bands: list[tuple[float, str, tuple[int, int, int, int]]],
) -> list[tuple[str, tuple[int, int, int, int]]]:
    return [(label, color) for _upper, label, color in bands]


def _score_legend_entries() -> list[tuple[str, tuple[int, int, int, int]]]:
    entries: list[tuple[str, tuple[int, int, int, int]]] = []
    for band in range(0, 100, 20):
        rgba = score_band_to_color(float(band) + 5.0, alpha=150)
        entries.append((f"{band}-{band + 20}", (int(rgba[0]), int(rgba[1]), int(rgba[2]), int(rgba[3]))))
    return entries


def render_mapas_censitarios_combinados(
    lat: float,
    lng: float,
    setores_df: pd.DataFrame,
    *,
    raio_km: float = RAIO_CENSITARIO_DEFAULT_KM,
    competitors_df: pd.DataFrame | None = None,
    ultra_df: pd.DataFrame | None = None,
    width: int = 1000,
    height: int = 760,
    basemap: bool = True,
    logos_dir: Path | None = None,
    ultra_logo_dir: Path | None = None,
    street_ceil: int | None = None,
    street_gain: float | None = None,
    street_cap: int | None = None,
    choropleth_alpha: int | None = None,
) -> dict[str, bytes]:
    """Gera as 4 camadas do Relatorio Pontual Censitario numa unica chamada.

    Retorna `{"densidade": png, "renda": png, "score": png, "concorrentes": png}` (chaves
    canonicas). `score` e o choropleth de score censitario COM legenda (modo de cor ativo);
    `concorrentes` e o mapa SO de pins (basemap + pins, sem choropleth). As 3 camadas de
    choropleth (densidade/renda/score) e a de pins compartilham basemap, bbox, projecao
    (EPSG:3857) e pins; variam so o fill dos setores + a legenda/titulo.

    READ-ONLY sobre o M1: o motor (`analisar_ponto_censitario_setores`,
    `setor_censitario_intersecao_area_1p5km`, raio 1.5 km) e INTOCADO; toda a mudanca e
    de RENDER. `basemap=False` forca o caminho offline (canvas branco sem ruas) — default
    seguro em CI/teste. `import contextily` e lazy: sem o extra `[basemap]` cai no offline.

    Ajuste fino do arruamento (todos `None` = constantes do modulo, render IDENTICO ao
    dashboard; so a API os sobrescreve): `street_ceil`/`street_gain`/`street_cap` controlam
    o resgate das ruas sobre o choropleth (luminancia abaixo de `street_ceil` -> opacidade);
    subir o `ceil` recupera as vias residenciais CINZA-CLARAS do Voyager (lum ~200) que com o
    teto baixo (160) sumiam sob a cor. `choropleth_alpha` e a opacidade do preenchimento das
    faixas — menor = ruas aparecem mais. A legenda usa RGB solido, entao nao muda com o alpha.
    """
    if logos_dir is not None:
        from motor_expansao.dashboard.competitors import preload_logos

        preload_logos(logos_dir, ultra_dir=ultra_logo_dir)

    result = analisar_ponto_censitario_setores(
        lat,
        lng,
        setores_df,
        raio_km=raio_km,
        competitors_df=competitors_df,
        ultra_df=ultra_df,
    )
    # Frame do mapa: RETANGULO com a proporcao da area de mapa (nao mais quadrado), para o
    # choropleth preencher a figura inteira sem letterbox. O lado MENOR = raio*(1+margem) (o
    # circulo de 1.5 km cabe e fica redondo, pois x/y tem o mesmo scale). Os setores sao
    # recortados a este retangulo (nao ao circulo) -> figura toda preenchida. RENDER apenas.
    base_half = raio_km * 1000.0 * (1.0 + _MAP_FRAME_MARGIN)
    inner_w, inner_h = _map_inner_dims(width, height)
    aspect = inner_w / inner_h if inner_h > 0 else 1.0
    if aspect >= 1.0:
        frame_half_x, frame_half_y = base_half * aspect, base_half
    else:
        frame_half_x, frame_half_y = base_half, base_half / aspect
    frame_box_metric = box(-frame_half_x, -frame_half_y, frame_half_x, frame_half_y)
    sector_records, circle_metric = _decode_intersections(
        lat,
        lng,
        setores_df,
        raio_km,
        frame_box_metric,
    )

    # Reprojeta setores + circulo + centro + frame do aeqd local -> 3857 (SO para render).
    circle_3857 = _to_mercator(circle_metric, lat, lng)
    center_3857 = _point_to_mercator(0.0, 0.0, lat, lng)
    frame_3857 = _to_mercator(frame_box_metric, lat, lng)

    sector_records_3857: list[tuple[BaseGeometry, int]] = []
    densidade_vals: list[float] = []
    renda_vals: list[float] = []
    score_vals: list[float] = []
    for idx, record in enumerate(sector_records):
        geom = record.get("geometry_metric")
        if not isinstance(geom, BaseGeometry) or geom.is_empty:
            densidade_vals.append(float("nan"))
            renda_vals.append(float("nan"))
            score_vals.append(float("nan"))
            continue
        sector_records_3857.append((_to_mercator(geom, lat, lng), idx))
        densidade_vals.append(
            float(pd.to_numeric(record.get("densidade_pop_setor_hab_km2"), errors="coerce"))
        )
        renda_raw = pd.to_numeric(record.get("renda_per_capita_setor_2022_calibrada"), errors="coerce")
        if pd.isna(renda_raw):
            renda_raw = pd.to_numeric(record.get("renda_per_capita_setor_2022"), errors="coerce")
        renda_vals.append(float(renda_raw))
        score_vals.append(
            float(pd.to_numeric(record.get("score_setor_2022_calibrado"), errors="coerce"))
        )

    densidade_series = pd.Series(densidade_vals, dtype="float64")
    renda_series = pd.Series(renda_vals, dtype="float64")
    score_series = pd.Series(score_vals, dtype="float64")

    # bbox do mapa = o FRAME (quadrado em 3857). Os setores ja foram recortados a ele, entao
    # preenchem o frame todo (corners inclusos), sem sobra de margem nem spill na legenda.
    bounds_t = frame_3857.bounds

    basemap_tiles = None
    if basemap:
        basemap_tiles = _fetch_basemap(bounds_t, width)

    pins = _project_points(result["concorrentes_raio"], lat, lng)
    ultra_pins = _project_points(result["ultra_raio"], lat, lng)
    n_setores = result["n_setores"]

    # Alpha efetivo do choropleth: None -> constante do modulo (identico ao dashboard). As
    # color_fn locais reproduzem `_color_for_densidade/renda/score` exatamente quando
    # eff_alpha == _CHOROPLETH_ALPHA; so a API passa um alpha menor p/ as ruas aparecerem.
    eff_alpha = _CHOROPLETH_ALPHA if choropleth_alpha is None else int(choropleth_alpha)
    sem_dado = (_FILL_SEM_DADO[0], _FILL_SEM_DADO[1], _FILL_SEM_DADO[2], eff_alpha)

    def _dens_fn(value: float) -> tuple[int, int, int, int]:
        if pd.isna(value):
            return sem_dado
        r, g, b, _a = _color_for_bands(value, DENSIDADE_POP_BANDS)
        return (int(r), int(g), int(b), eff_alpha)

    def _renda_fn(value: float) -> tuple[int, int, int, int]:
        if pd.isna(value):
            return sem_dado
        r, g, b, _a = _color_for_bands(value, RENDA_PER_CAPITA_BANDS)
        return (int(r), int(g), int(b), eff_alpha)

    def _score_fn(value: float) -> tuple[int, int, int, int]:
        rgba = score_band_to_color(value, alpha=eff_alpha)
        return (int(rgba[0]), int(rgba[1]), int(rgba[2]), int(rgba[3]))

    common = dict(
        sector_records_3857=sector_records_3857,
        circle_3857=circle_3857,
        center_3857=center_3857,
        pins=pins,
        ultra_pins=ultra_pins,
        basemap=basemap_tiles,
        bounds=bounds_t,
        lat=lat,
        lng=lng,
        raio_km=raio_km,
        n_setores=n_setores,
        width=width,
        height=height,
        street_ceil=street_ceil,
        street_gain=street_gain,
        street_cap=street_cap,
    )

    densidade_png = _render_camada(
        titulo="Relatorio Pontual Censitario - Densidade populacional",
        legenda_titulo="Densidade (hab/km2)",
        legenda_entries=_bands_legend_entries(DENSIDADE_POP_BANDS),
        color_fn=_dens_fn,
        source_values=densidade_series,
        **common,
    )
    renda_png = _render_camada(
        titulo="Relatorio Pontual Censitario - Renda per capita",
        legenda_titulo="Renda per capita (R$/pessoa)",
        legenda_entries=_bands_legend_entries(RENDA_PER_CAPITA_BANDS),
        color_fn=_renda_fn,
        source_values=renda_series,
        **common,
    )
    # Camada Score censitario: choropleth COM legenda (modo de cor ativo) — restaurada no
    # BLK-CENSO-03-FU5 (Felipe, 2026-06-08). Distinta da camada Concorrentes (so-pins).
    score_png = _render_camada(
        titulo="Relatorio Pontual Censitario - Score censitario",
        legenda_titulo="Score censitario (0-100)",
        legenda_entries=_score_legend_entries(),
        color_fn=_score_fn,
        source_values=score_series,
        **common,
    )
    concorrentes_png = _render_camada(
        titulo="Relatorio Pontual Censitario - Concorrentes e Ultra",
        legenda_titulo="Pins: Ultra e concorrentes",
        legenda_entries=[],  # sem faixas de choropleth (camada so-pins)
        color_fn=_color_for_score,  # irrelevante quando pins_only=True
        source_values=score_series,  # irrelevante quando pins_only=True
        pins_only=True,
        **common,
    )

    return {
        "densidade": densidade_png,
        "renda": renda_png,
        "score": score_png,
        "concorrentes": concorrentes_png,
    }


def render_mapa_censitario_estatico_png(
    lat: float,
    lng: float,
    setores_df: pd.DataFrame,
    *,
    raio_km: float = RAIO_CENSITARIO_DEFAULT_KM,
    metric_column: str = "pop_estimada_intersecao",
    competitors_df: pd.DataFrame | None = None,
    ultra_df: pd.DataFrame | None = None,
    width: int = 1000,
    height: int = 760,
    basemap: bool = False,
) -> bytes:
    """LEGADO: wrapper fino sobre `render_mapas_censitarios_combinados`.

    Mantido para imports externos durante a migracao. Devolve UMA das camadas combinadas,
    mapeando o antigo `metric_column` para a chave canonica mais proxima (renda->"renda",
    score->"score", demais->"densidade"). `basemap=False` por padrao (offline) p/
    nao depender de internet em chamadas legadas. Prefira a orquestradora combinada.
    """
    mapas = render_mapas_censitarios_combinados(
        lat,
        lng,
        setores_df,
        raio_km=raio_km,
        competitors_df=competitors_df,
        ultra_df=ultra_df,
        width=width,
        height=height,
        basemap=basemap,
    )
    if metric_column == "renda_per_capita_setor_2022_calibrada":
        return mapas["renda"]
    if metric_column == "score_setor_2022_calibrado":
        return mapas["score"]
    return mapas["densidade"]
