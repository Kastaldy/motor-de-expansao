from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
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
    FATOR_TEMPORAL_RENDA,
    RENDA_MEDIA_DOMICILIAR_BANDS,
    RENDA_PER_CAPITA_BANDS,
    uplift_composicao_por_setor,
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
# Atribuicao exigida pela licenca CARTO/OSM (DEC-004); aparece no rodape do PNG quando ha tile.
_ATRIBUICAO_TILES = "(c) OpenStreetMap, (c) CARTO"
_BASEMAP_CONTRAST = 1.15
# Zoom extra dos tiles (alem do minimo p/ cobrir a bbox) -> ruas mais nitidas/detalhadas.
_BASEMAP_ZOOM_BUMP = 1

# Cores dos elementos desenhados DENTRO do mapa claro (precisam contrastar com fundo claro):
# circulo do raio (AZUL, pedido de Vini 2026-06-17) e barra de escala/labels em tinta ESCURA.
# _CIRCLE_RGBA: azul vivido, visivel sobre o fundo claro do basemap.
_CIRCLE_RGBA = (0, 102, 255, 235)
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

# Chaves canonicas das camadas combinadas (BLK-CENSO-03-FU5): `score` e o choropleth de
# score censitario COM legenda; `renda_domiciliar` e o choropleth de renda media domiciliar
# (renda_pc x moradores x uplift SETORIAL x fator temporal); `concorrentes` e o mapa SO de pins.
CAMADAS_CENSITARIAS = ("densidade", "renda", "score", "renda_domiciliar", "concorrentes")

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

# BLK-RELPON-06 (D4): tamanhos de fonte do mapa. Valem para dashboard, PDF e API (UM render
# so -- nao ha parametro `escala` por caminho, ver D4 da DEC). Ancorados no pior caso do PDF:
# o PNG de 1000px entra numa celula de ~298,67pt na tira 1x3 do slide "Mapas de calor"
# (`_map_grid_cells`: usable_w=896/3) -> ratio ~0,2987 -> a legenda-corpo (32px) sai a
# ~9,6pt, acima do alvo de 9-10pt de legibilidade no PDF.
_FS_TITULO = 44
_FS_VALOR_RAIO = 38
_FS_LEGENDA_TITULO = 34
_FS_LEGENDA_CORPO = 32
# Subtitulo da legenda ("Renda per capita (R$/pessoa)" etc.): fonte MENOR que o titulo --
# o subtitulo mais longo transbordava do canvas a `_FS_LEGENDA_TITULO` (34px -> ~448px,
# > budget de ~320px da coluna, `_LEGEND_COL_W - 10`). Texto secundario, como o rodape.
_FS_LEGENDA_SUBTITULO = 22
# Legenda de pins ("Ponto central"/"Pins: Ultra e concorrentes"): fonte MENOR que o corpo
# das faixas -- a essas duas linhas cabe em `_LEGEND_COL_W`, mas a frase e mais longa que
# o rotulo de faixa mais longo e transbordava do canvas a `_FS_LEGENDA_CORPO` (32px ->
# ~362px, > budget de ~252px da coluna). Texto secundario/anotacao, como rodape/escala.
_FS_LEGENDA_CAPTION = 20
_FS_BODY = 26  # mensagem "Sem setores intersectados no raio"
_FS_FOOTER = 22  # rodape (atribuicao CARTO)
_FS_ESCALA = 24  # label da barra de escala

# Coluna da legenda: alargada de 252 -> 330px porque o rotulo mais longo das faixas
# ("R$ 2.001-3.500", 14 chars) ocupa ~246px a 32px de fonte (ver teste de legibilidade).
_LEGEND_COL_W = 330
_MAP_TOP = 132  # era 92: abre espaco para titulo (44px) + linha de dado (38px)
_VALOR_Y = 78  # era 51: 22 (topo do titulo) + 44 (titulo) + 12 de respiro


def _with_choropleth_alpha(rgba: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """Aplica o alpha canonico do choropleth (mantem RGB da faixa)."""
    return (int(rgba[0]), int(rgba[1]), int(rgba[2]), _CHOROPLETH_ALPHA)


def _map_box(width: int, height: int) -> tuple[int, int, int, int]:
    """Retangulo (left, top, right, bottom) da area de mapa dentro da figura.

    BLK-RELPON-06 (D4): `_MAP_TOP` abre espaco para o titulo+linha-de-dado maiores; o `-33`
    preserva o mesmo respiro (~33px) entre a borda direita do mapa e a coluna da legenda que
    existia antes (`(width-252) - (width-285) = 33`), agora com `_LEGEND_COL_W` mais larga.
    """
    return (28, _MAP_TOP, width - (_LEGEND_COL_W + 33), height - 54)


def _map_inner_dims(width: int, height: int) -> tuple[float, float]:
    """Dimensoes uteis (inner_w, inner_h) onde o frame e desenhado (sem o padding de 12px)."""
    left, top, right, bottom = _map_box(width, height)
    return (float(right - left - 24), float(bottom - top - 24))


def _font(size: int = 12) -> ImageFont.ImageFont:
    # BLK-RELPON-06 (D3): fonte TrueType EMBUTIDA do Pillow (>=10.1), via load_default(size=).
    # Deliberadamente NAO usa TTF do sistema: `arial.ttf` so existe no Windows e a imagem de
    # producao (python:3.11-slim) nao tem fonte alguma -> o fallback load_default() SEM size
    # caia num bitmap FIXO ~10px que IGNORAVA o tamanho pedido, quebrando o texto do mapa no
    # PDF *e* no dashboard (title_font(20) e title_font(60) renderizavam IGUAL em producao).
    # Com load_default(size=N) a fonte escala de fato -> o PNG/PDF fica IDENTICO em Windows
    # e na VPS (auditavel). truetype()/arial.ttf NAO devem ser reintroduzidos.
    # truetype() devolve FreeTypeFont (nao subclasse de ImageFont nos stubs Pillow);
    # cast preserva runtime e mantem a assinatura aceita por _draw_text/_text_width.
    return cast(ImageFont.ImageFont, ImageFont.load_default(size=size))


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


# ── Faixa superior "<variavel> no raio" por camada (BLK-RELPON-05, faixa REVERTIDA p/ o
# raio pelo BLK-RELPON-06/D1) ──────────────────────────────────────────────────────────
# Formata o valor AGREGADO do raio de 1.5 km (densidade sobre area valida, renda e score
# medios ponderados) -- NAO mais o valor bruto do setor que contem o ponto (BLK-RELPON-05
# original). "n/d" para None/NaN (sem setores intersectados). Texto so com pontuacao ASCII
# por consistencia com o restante do relatorio.


def _format_valor_ponto_renda(value: float | None) -> str:
    """Renda per capita media do raio: moeda, separador de milhar '.', sem centavos."""
    if value is None or pd.isna(value):
        return "n/d"
    return f"R$ {float(value):,.0f}".replace(",", ".")


def _format_valor_ponto_densidade(value: float | None) -> str:
    """Densidade populacional do raio (sobre area valida): inteiro, unidade ASCII 'hab/km2'."""
    if value is None or pd.isna(value):
        return "n/d"
    return f"{float(value):,.0f}".replace(",", ".") + " hab/km2"


def _format_valor_ponto_score(value: float | None) -> str:
    """Score censitario medio do raio: inteiro 0-100."""
    if value is None or pd.isna(value):
        return "n/d"
    return f"{float(value):.0f}"


def _legenda_valor_ponto(rotulo: str, texto: str) -> str:
    """Monta o texto da faixa superior do mapa: "<Rotulo> no raio: <texto>" (BLK-RELPON-06/D1)."""
    return f"{rotulo} no raio: {texto}"


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
    # D8=B (BLK-EST-02): linha mais grossa (width 5) e box branco semi-translucido atras do
    # label, para legibilidade sobre qualquer cor do choropleth.
    draw.line([(x0, y0), (x0 + px_len, y0)], fill=_DARK_MAP_INK, width=5)
    draw.line([(x0, y0 - 5), (x0, y0 + 5)], fill=_DARK_MAP_INK, width=2)
    draw.line([(x0 + px_len, y0 - 5), (x0 + px_len, y0 + 5)], fill=_DARK_MAP_INK, width=2)
    label = f"{scale_m // 1000} km" if scale_m >= 1000 else f"{scale_m} m"
    # BLK-RELPON-06 (D4): box branco atras do label acompanha a fonte maior (_FS_ESCALA).
    draw.rectangle([x0 - 2, y0 + 5, x0 + px_len, y0 + 34], fill=(255, 255, 255, 180))
    _draw_text(draw, (x0, y0 + 8), label, font=_font(_FS_ESCALA), fill=_DARK_MAP_INK)


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
    """Legenda por camada: faixas fixas (label + amostra de cor) + pins de referencia.

    BLK-RELPON-06 (D4): fontes/layout ampliados (`_FS_LEGENDA_TITULO`/`_FS_LEGENDA_CORPO`,
    linhas/swatch maiores) para o texto ficar legivel no PDF (celula ~299pt na tira 1x3).
    """
    title_font = _font(_FS_LEGENDA_TITULO)
    body_font = _font(_FS_LEGENDA_CORPO)
    caption_font = _font(_FS_LEGENDA_CAPTION)
    subtitle_font = _font(_FS_LEGENDA_SUBTITULO)
    _draw_text(draw, (x, y), "Legenda", font=title_font)
    # Subtitulo com fonte dedicada MENOR que o corpo (ver `_FS_LEGENDA_SUBTITULO`): o mais
    # longo ("Renda per capita (R$/pessoa)") transbordaria do canvas a `_FS_LEGENDA_CORPO`.
    _draw_text(draw, (x, y + 44), titulo, font=subtitle_font)

    base_y = y + 96
    row_h = 48
    for idx, (label, color) in enumerate(entries):
        yy = base_y + idx * row_h
        # D7=C subset seguro (BLK-EST-02): amostras arredondadas (radius 5).
        draw.rounded_rectangle(
            [x, yy, x + 56, yy + 38], radius=5, fill=color[:3], outline=(148, 163, 184)
        )
        _draw_text(draw, (x + 68, yy + 6), label, font=body_font)

    # D7=C subset seguro: linha separadora fina antes do bloco de pins.
    sep_y = base_y + len(entries) * row_h + 8
    draw.line([(x, sep_y), (x + 210, sep_y)], fill=(210, 214, 222), width=1)

    yy = base_y + len(entries) * row_h + 24
    _draw_center_pin(draw, x + 12, yy + 20, scale=0.8)
    # Fonte MENOR (`_FS_LEGENDA_CAPTION`) que o corpo das faixas: a frase "Pins: Ultra e
    # concorrentes" e mais longa que o rotulo de faixa mais longo e transbordaria do
    # canvas a `_FS_LEGENDA_CORPO` (ver constante acima).
    _draw_text(draw, (x + 68, yy), "Ponto central", font=caption_font)
    _draw_text(draw, (x + 68, yy + 30), "Pins: Ultra e concorrentes", font=caption_font)


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
                # Insumos da renda media domiciliar por setor (uplift SETORIAL, formula do #124).
                "avg_moradores_domicilio_setor_2022": row.get("avg_moradores_domicilio_setor_2022"),
                "renda_responsavel_media_setor_2022": row.get("renda_responsavel_media_setor_2022"),
                "uf": row.get("uf"),
                "cod_municipio": row.get("cod_municipio"),
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
    valor_ponto: str | None = None,
) -> bytes:
    """Desenha UMA camada (mesmos bbox/projecao/basemap/pins; varia fill + legenda).

    Quando `pins_only=True` (camada Concorrentes): pula o choropleth de faixas E o overlay
    de ruas de pixel; mantem basemap + circulo + ponto central + pins de concorrentes/Ultra +
    escala + footer + legenda so de pins. BLK-CENSO-03.

    `valor_ponto` (BLK-RELPON-05, faixa REVERTIDA p/ os agregados do raio pelo
    BLK-RELPON-06/D1): texto opcional da faixa superior ("<Variavel> no raio: <valor>"),
    desenhado numa 2a linha entre o titulo e o `map_box`. Default `None` preserva o render
    IDENTICO desta funcao para qualquer chamador que nao passe o parametro.

    BLK-RELPON-06 (D4): fontes ampliadas na BASE (`_FS_*`) -- vale para dashboard, PDF e
    API com UM UNICO render (sem parametro de escala por-caminho).
    """
    # Base RGBA TRANSPARENTE-branco: as margens (fora do map_box) ficam transparentes -> no
    # PDF o fundo da pagina aparece (sem retangulo branco). O choropleth/pins sao clipados ao
    # map_box (sobre basemap/fill OPACO), entao as cores nao mudam; e, achatado sobre branco
    # (convert("RGB")), fica identico ao RGB antigo -> compat com os testes de cor das faixas.
    image = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image, "RGBA")
    title_font = _font(_FS_TITULO)
    body_font = _font(_FS_BODY)
    small_font = _font(_FS_FOOTER)

    _draw_text(draw, (28, 22), titulo, font=title_font)
    if valor_ponto is not None:
        # BLK-RELPON-06 (D4): `_VALOR_Y`/`_FS_VALOR_RAIO`/`_MAP_TOP` tem que fechar:
        # _VALOR_Y (78) + _FS_VALOR_RAIO (38) + 16 de respiro = _MAP_TOP (132). Mudar um
        # tamanho no gate visual exige recalcular os outros dois junto.
        _draw_text(draw, (28, _VALOR_Y), valor_ponto, font=_font(_FS_VALOR_RAIO), fill=_DARK_MAP_INK)

    map_box = _map_box(width, height)
    legend_x = width - _LEGEND_COL_W
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
        # Circulo do raio em AZUL (pedido de Vini 2026-06-17), visivel sobre o fundo claro.
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

    # D8=B (BLK-EST-02): rodape enxuto. Atribuicao CARTO (exigida pela licenca DEC-004)
    # permanece quando ha basemap; some no fallback offline (sem tile, sem atribuicao).
    if drew_basemap:
        footer = f"Raio 1,5 km - EPSG:3857 - {_ATRIBUICAO_TILES}"
    else:
        footer = "Raio 1,5 km - EPSG:3857 - fundo de ruas offline"
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
    """Gera as 5 camadas do Relatorio Pontual Censitario numa unica chamada.

    Retorna `{"densidade": png, "renda": png, "score": png, "renda_domiciliar": png,
    "concorrentes": png}` (chaves canonicas). `renda_domiciliar` e o choropleth de renda media
    domiciliar (renda_pc x moradores x uplift SETORIAL x fator temporal); `concorrentes` e o mapa SO
    de pins (basemap + pins, sem choropleth). As 4 camadas de choropleth (densidade/renda/score/
    renda_domiciliar) e a de pins compartilham basemap, bbox, projecao (EPSG:3857) e pins; variam
    so o fill dos setores + a legenda/titulo.

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

    BLK-RELPON-05: os 3 choropleths (densidade/renda/score) recebem uma faixa superior,
    computada a partir do PROPRIO `result` interno desta funcao (mesma chamada de
    `analisar_ponto_censitario_setores` que ja existia antes desta mudanca) -- nenhum
    caller em `pages.py` precisa mudar para o recurso aparecer, tanto no PNG interativo do
    dashboard quanto no PDF (que embute os mesmos PNGs). A camada `concorrentes` NAO
    recebe a faixa (fica byte-a-byte igual): e um mapa so-pins, sem variavel continua por
    setor. BLK-RELPON-06 (D1) REVERTEU a fonte da faixa: era o valor BRUTO do setor que
    CONTEM o ponto, agora sao os agregados do RAIO de 1.5 km (densidade sobre area valida,
    renda e score medios ponderados) -- rotulo "no raio". Os 5 campos `*_setor_ponto`
    continuam no `result` para CSV/auditoria.
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

    # Transformer compartilhado: criado UMA vez para todos os setores e geometrias
    # do mesmo render (mesmo lat/lng -> mesmo CRS aeqd local -> mesmo 3857). Fix 1 BLK-PERF-01a.
    _crs_local = _local_metric_crs(lat, lng)
    _to_3857 = _transformer(_crs_local, CRS_WEB_MERCATOR)

    # Reprojeta setores + circulo + centro + frame do aeqd local -> 3857 (SO para render).
    circle_3857 = _project_geometry(circle_metric, _to_3857)
    center_3857 = _to_3857.transform(0.0, 0.0)
    frame_3857 = _project_geometry(frame_box_metric, _to_3857)

    sector_records_3857: list[tuple[BaseGeometry, int]] = []
    densidade_vals: list[float] = []
    renda_vals: list[float] = []
    score_vals: list[float] = []
    renda_domiciliar_vals: list[float] = []
    for idx, record in enumerate(sector_records):
        geom = record.get("geometry_metric")
        if not isinstance(geom, BaseGeometry) or geom.is_empty:
            densidade_vals.append(float("nan"))
            renda_vals.append(float("nan"))
            score_vals.append(float("nan"))
            renda_domiciliar_vals.append(float("nan"))
            continue
        sector_records_3857.append((_project_geometry(geom, _to_3857), idx))
        densidade_vals.append(
            float(pd.to_numeric(record.get("densidade_pop_setor_hab_km2"), errors="coerce"))
        )
        renda_calibrada = pd.to_numeric(
            record.get("renda_per_capita_setor_2022_calibrada"), errors="coerce"
        )
        renda_raw = renda_calibrada
        if pd.isna(renda_raw):
            renda_raw = pd.to_numeric(record.get("renda_per_capita_setor_2022"), errors="coerce")
        renda_vals.append(float(renda_raw))
        score_vals.append(
            float(pd.to_numeric(record.get("score_setor_2022_calibrado"), errors="coerce"))
        )
        # Renda media domiciliar por setor (formula setorial do #124, censo_point.py:328-352):
        # renda_pc(CALIBRADA) x moradores x uplift_SETORIAL(cod_setor) x fator_temporal, com fallback
        # POR SETOR para renda_responsavel_media_setor_2022 quando calibrada x moradores e' NaN
        # (`.where(notna, _resp)` do #124). Usa a CALIBRADA (nao a bruta do renda_per_capita), para o
        # setor entrar na cor com o MESMO valor com que entra no agregado `renda_domiciliar_total_raio`.
        moradores = pd.to_numeric(
            record.get("avg_moradores_domicilio_setor_2022"), errors="coerce"
        )
        renda_domiciliar = renda_calibrada * moradores
        if pd.isna(renda_domiciliar):
            renda_domiciliar = pd.to_numeric(
                record.get("renda_responsavel_media_setor_2022"), errors="coerce"
            )
        uf_val = record.get("uf")
        mun_val = record.get("cod_municipio")
        uplift_setor = uplift_composicao_por_setor(
            str(record.get("cod_setor") or ""),
            str(uf_val) if pd.notna(uf_val) else None,
            str(mun_val) if pd.notna(mun_val) else None,
        )
        renda_domiciliar_vals.append(
            float(renda_domiciliar * uplift_setor * float(FATOR_TEMPORAL_RENDA))
        )

    densidade_series = pd.Series(densidade_vals, dtype="float64")
    renda_series = pd.Series(renda_vals, dtype="float64")
    score_series = pd.Series(score_vals, dtype="float64")
    renda_domiciliar_series = pd.Series(renda_domiciliar_vals, dtype="float64")

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

    def _renda_dom_fn(value: float) -> tuple[int, int, int, int]:
        if pd.isna(value):
            return sem_dado
        r, g, b, _a = _color_for_bands(value, RENDA_MEDIA_DOMICILIAR_BANDS)
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

    # BLK-RELPON-06 (D1): faixa superior por camada, com os agregados do RAIO de 1.5 km
    # (ja expostos por `result`, computados no proprio `analisar_ponto_censitario_setores`
    # acima) -- REVERTE a fonte do BLK-RELPON-05, que usava o valor BRUTO do setor que
    # CONTEM o ponto. "n/d" quando nao ha setores intersectados (sem area valida).
    valor_raio_densidade = _legenda_valor_ponto(
        "Densidade", _format_valor_ponto_densidade(result.get("densidade_pop_raio_valida_hab_km2"))
    )
    valor_raio_renda = _legenda_valor_ponto(
        "Renda", _format_valor_ponto_renda(result.get("renda_per_capita_media_raio"))
    )
    valor_raio_score = _legenda_valor_ponto(
        "Score", _format_valor_ponto_score(result.get("score_setor_medio"))
    )
    # Faixa da renda domiciliar: usa o agregado do raio COM uplift+temporal (mesma escala das
    # bandas), NAO o pre-uplift `renda_media_domiciliar_raio` (cairia sempre na faixa mais baixa).
    valor_raio_renda_dom = _legenda_valor_ponto(
        "Renda dom.", _format_valor_ponto_renda(result.get("renda_domiciliar_total_raio"))
    )

    densidade_png = _render_camada(
        titulo="Densidade populacional",
        legenda_titulo="Densidade (hab/km2)",
        legenda_entries=_bands_legend_entries(DENSIDADE_POP_BANDS),
        color_fn=_dens_fn,
        source_values=densidade_series,
        valor_ponto=valor_raio_densidade,
        **common,
    )
    renda_png = _render_camada(
        titulo="Renda per capita",
        legenda_titulo="Renda per capita (R$/pessoa)",
        legenda_entries=_bands_legend_entries(RENDA_PER_CAPITA_BANDS),
        color_fn=_renda_fn,
        source_values=renda_series,
        valor_ponto=valor_raio_renda,
        **common,
    )
    # Camada Score censitario: choropleth COM legenda (modo de cor ativo) — restaurada no
    # BLK-CENSO-03-FU5 (Felipe, 2026-06-08). Distinta da camada Concorrentes (so-pins).
    score_png = _render_camada(
        titulo="Score censitario",
        legenda_titulo="Score censitario (0-100)",
        legenda_entries=_score_legend_entries(),
        color_fn=_score_fn,
        source_values=score_series,
        valor_ponto=valor_raio_score,
        **common,
    )
    renda_domiciliar_png = _render_camada(
        titulo="Renda media domiciliar",
        legenda_titulo="Renda domiciliar (R$/domicilio)",
        legenda_entries=_bands_legend_entries(RENDA_MEDIA_DOMICILIAR_BANDS),
        color_fn=_renda_dom_fn,
        source_values=renda_domiciliar_series,
        valor_ponto=valor_raio_renda_dom,
        **common,
    )
    concorrentes_png = _render_camada(
        titulo="Concorrentes e Ultra",
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
        "renda_domiciliar": renda_domiciliar_png,
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


# ===========================================================================
# TESTE (ainda NAO definitivo) — FOTO DE SATELITE do ponto.
#
# Fonte: Esri World Imagery + Reference/World_Transportation (rotulos) — a MESMA
# composicao do "World Imagery Hybrid" da Esri e do sat-overlay do
# openmaptiles-infra. Aditivo: nenhuma funcao existente foi tocada.
#
# Zoom: tenta z19 e cai p/ z18 conforme a disponibilidade REAL no ponto (a Esri
# devolve placeholder de ~2,5 KB onde nao ha imagem). Medido em 22 pontos do
# Brasil: z17 existe em todo lugar, z18 em cidade media/grande, z19 so em capital.
#
# LICENCA (REGULARIZADA — DEC-018): a imagem vem do ArcGIS Location Platform
# (`ibasemaps-api.arcgis.com`), autenticada por CHAVE lida de env
# (`MOTOR_ARCGIS_API_KEY`; a chave precisa do privilegio `premium:user:basemaps`;
# faixa gratuita de 2M tiles/mes). A chave NUNCA e commitada. SEM chave, a pagina
# de satelite e simplesmente OMITIDA (render devolve None) -- nunca se cai no
# endpoint anonimo `server.arcgisonline.com`, cujo uso os termos da Esri consideram
# irregular. A imagem e SEMPRE externa (nao se self-hospeda) e o credito da Esri e
# obrigatorio -- por isso `_SAT_ATRIBUICAO` e desenhado no canto da foto.
# ===========================================================================

# Nome da env var com a chave do ArcGIS Location Platform (regularizacao da licenca).
_SAT_API_KEY_ENV = "MOTOR_ARCGIS_API_KEY"
_SAT_TILE_URL = (
    "https://ibasemaps-api.arcgis.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
)
_SAT_ROTULOS_URL = (
    "https://ibasemaps-api.arcgis.com/arcgis/rest/services/Reference/World_Transportation"
    "/MapServer/tile/{z}/{y}/{x}"
)
_SAT_ATRIBUICAO = "Esri, Vantor, Earthstar Geographics"
_SAT_ZOOM_MIN, _SAT_ZOOM_MAX = 18, 19
_SAT_PLACEHOLDER_MAX_BYTES = 3000
_SAT_COBERTURA_M = 400          # largura do enquadramento no chao
# Proporcao = a MESMA da celula de foto do PDF (`_FOTO_ASPECT`, paisagem 3:2). Se gerar
# em outra proporcao, `_recortar_cover` corta as laterais p/ encaixar na celula -- e o
# corte come o credito da Esri no canto, que a licenca exige visivel. Medido no teste:
# em 1,667 o PDF cortou 141 px e a atribuicao saiu pela metade.
_SAT_RATIO = 3.0 / 2.0
_SAT_RAIO_CANTO_PCT = 0.025
_SAT_TILE_PX = 256
_SAT_UA = {"User-Agent": "motor_expansao_ultra_academia_bot"}


def _sat_deg2num(lat: float, lng: float, z: int) -> tuple[float, float]:
    """lat/lng -> coordenada de tile FRACIONARIA (a parte decimal centraliza o recorte)."""
    n = 2.0**z
    x = (lng + 180.0) / 360.0 * n
    y = (
        1.0 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi
    ) / 2.0 * n
    return x, y


def _sat_api_key() -> str | None:
    """Chave do ArcGIS Location Platform, lida de env. Sem ela, a vista aerea e omitida."""
    import os

    return os.environ.get(_SAT_API_KEY_ENV) or None


def _sat_url(base: str, z: int, x: int, y: int, token: str) -> str:
    """URL do tile ja autenticada com o token do ArcGIS Location Platform (`?token=`)."""
    from urllib.parse import quote

    return f"{base.format(z=z, x=x, y=y)}?token={quote(token, safe='')}"


def _sat_baixar_tile(url: str, z: int, x: int, y: int, timeout: float, token: str) -> Image.Image:
    import urllib.request

    req = urllib.request.Request(_sat_url(url, z, x, y, token), headers=_SAT_UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return Image.open(BytesIO(resp.read())).convert("RGBA")


def _sat_melhor_zoom(lat: float, lng: float, timeout: float, token: str) -> int:
    """Maior zoom com imagem REAL neste ponto (1 tile de sonda, nao o mosaico todo)."""
    import urllib.request

    for z in range(_SAT_ZOOM_MAX, _SAT_ZOOM_MIN - 1, -1):
        fx, fy = _sat_deg2num(lat, lng, z)
        try:
            req = urllib.request.Request(
                _sat_url(_SAT_TILE_URL, z, int(fx), int(fy), token), headers=_SAT_UA
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if len(resp.read()) > _SAT_PLACEHOLDER_MAX_BYTES:
                    return z
        except Exception:
            continue
    return _SAT_ZOOM_MIN


def _sat_desenhar_pin(img: Image.Image, escala: float) -> None:
    """Pin vermelho com a PONTA no centro — mesma geometria de `_draw_center_pin`."""
    cx, cy = img.width // 2, img.height // 2
    vermelho = (218, 32, 32)
    r = max(6, int(round(9 * escala)))
    topo = cy - int(round(24 * escala))

    camada = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    sr = int(r * 1.2)
    d.ellipse([cx - sr, cy - int(sr * 0.34), cx + sr, cy + int(sr * 0.34)], fill=(0, 0, 0, 115))
    # gota: o pescoco sai TANGENTE a cabeca, senao circulo+triangulo viram um borrao
    bx, by = r * 0.72, topo + r * 0.70
    d.polygon([(cx, cy), (cx - bx, by), (cx + bx, by)], fill=vermelho)
    d.ellipse([cx - r, topo - r, cx + r, topo + r], fill=vermelho)
    furo = max(3, int(round(r * 0.38)))
    d.ellipse([cx - furo, topo - furo, cx + furo, topo + furo], fill=(255, 255, 255))
    img.paste(Image.alpha_composite(img.convert("RGBA"), camada).convert("RGB"), (0, 0))


def render_foto_satelite_ponto(
    lat: float,
    lng: float,
    *,
    cobertura_m: int = _SAT_COBERTURA_M,
    zoom: int | None = None,
    rotulos: bool = True,
    timeout: float = 20.0,
) -> bytes | None:
    """PNG da foto de satelite do ponto, com pin no centro. `None` se a rede falhar
    OU se nao houver chave do ArcGIS Location Platform.

    Devolver `None` (em vez de levantar) e proposital: o chamador segue gerando o
    relatorio sem a pagina de foto, igual ao fallback offline do `_fetch_basemap`.
    Sem chave, a pagina e omitida — nunca se busca tile no endpoint anonimo (licenca).
    """
    try:
        token = _sat_api_key()
        if not token:
            return None
        z = zoom if zoom is not None else _sat_melhor_zoom(lat, lng, timeout, token)
        m_px = 156543.03392 * math.cos(math.radians(lat)) / (2**z)
        larg = int(round(cobertura_m / m_px))
        alt = int(round(larg / _SAT_RATIO))

        fx, fy = _sat_deg2num(lat, lng, z)
        x0, y0 = fx * _SAT_TILE_PX - larg / 2, fy * _SAT_TILE_PX - alt / 2
        tx0, ty0 = math.floor(x0 / _SAT_TILE_PX), math.floor(y0 / _SAT_TILE_PX)
        tx1 = math.floor((x0 + larg) / _SAT_TILE_PX)
        ty1 = math.floor((y0 + alt) / _SAT_TILE_PX)
        coords = [(tx, ty) for ty in range(ty0, ty1 + 1) for tx in range(tx0, tx1 + 1)]

        tam = ((tx1 - tx0 + 1) * _SAT_TILE_PX, (ty1 - ty0 + 1) * _SAT_TILE_PX)
        canvas = Image.new("RGBA", tam, (20, 24, 34, 255))
        urls = [_SAT_TILE_URL] + ([_SAT_ROTULOS_URL] if rotulos else [])
        with ThreadPoolExecutor(max_workers=8) as ex:
            for url in urls:                       # ordem importa: foto, depois rotulo
                futs = {
                    (tx, ty): ex.submit(_sat_baixar_tile, url, z, tx, ty, timeout, token)
                    for tx, ty in coords
                }
                for (tx, ty), fut in futs.items():
                    try:
                        canvas.alpha_composite(
                            fut.result(),
                            ((tx - tx0) * _SAT_TILE_PX, (ty - ty0) * _SAT_TILE_PX),
                        )
                    except Exception:
                        continue                   # tile faltando nao invalida a foto
        ox, oy = int(round(x0 - tx0 * _SAT_TILE_PX)), int(round(y0 - ty0 * _SAT_TILE_PX))
        img = canvas.crop((ox, oy, ox + larg, oy + alt)).convert("RGB")

        _sat_desenhar_pin(img, escala=larg / 520)

        # credito da Esri: exigido pela licenca. Texto com sombra, sem caixa.
        d = ImageDraw.Draw(img, "RGBA")
        f = _font(max(11, int(14 * (img.width / 1100))))
        bb = d.textbbox((0, 0), _SAT_ATRIBUICAO, font=f)
        # nome proprio: `tx`/`ty` acima sao coordenadas INTEIRAS de tile no laco do
        # mosaico; reusar os nomes aqui (float) quebra o mypy.
        cred_x = img.width - (bb[2] - bb[0]) - 10
        cred_y = img.height - (bb[3] - bb[1]) - 10
        for dx, dy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
            d.text((cred_x + dx, cred_y + dy), _SAT_ATRIBUICAO, font=f, fill=(0, 0, 0, 150))
        d.text((cred_x, cred_y), _SAT_ATRIBUICAO, font=f, fill=(255, 255, 255, 225))

        raio = int(round(larg * _SAT_RAIO_CANTO_PCT))
        if raio > 0:
            mask = Image.new("L", img.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle(
                [0, 0, img.width - 1, img.height - 1], raio, fill=255
            )
            arredondado = Image.new("RGBA", img.size, (255, 255, 255, 0))
            arredondado.paste(img, (0, 0), mask)
            img = arredondado

        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None
