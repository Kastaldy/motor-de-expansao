from __future__ import annotations

from collections.abc import Iterable
from io import BytesIO
from typing import cast

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import MultiPolygon, Point, Polygon
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

MAPA_CENSITARIO_METRICAS = {
    "pop_estimada_intersecao": "Pop. estimada",
    "renda_per_capita_setor_2022_calibrada": "Renda per capita",
    "score_setor_2022_calibrado": "Score censitario",
    "peso_area_setor": "Peso de area",
}

_SECTOR_PALETTE = [
    (232, 242, 255, 225),
    (176, 211, 245, 225),
    (111, 166, 214, 225),
    (247, 196, 97, 225),
    (214, 93, 74, 225),
]


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
    project,
) -> list[tuple[int, int]]:
    coords = [project(x, y) for x, y in polygon.exterior.coords]
    return [(int(round(x)), int(round(y))) for x, y in coords]


def _draw_scale_bar(
    draw: ImageDraw.ImageDraw,
    project,
    map_box: tuple[int, int, int, int],
    meters_per_px: float,
) -> None:
    left, _, _, bottom = map_box
    candidates = [1000, 750, 500, 250, 100]
    scale_m = next((value for value in candidates if value / meters_per_px <= 140), 100)
    px_len = max(20, int(round(scale_m / meters_per_px)))
    x0 = left + 18
    y0 = bottom - 28
    draw.line([(x0, y0), (x0 + px_len, y0)], fill=(31, 41, 55), width=4)
    draw.line([(x0, y0 - 5), (x0, y0 + 5)], fill=(31, 41, 55), width=2)
    draw.line([(x0 + px_len, y0 - 5), (x0 + px_len, y0 + 5)], fill=(31, 41, 55), width=2)
    label = f"{scale_m // 1000} km" if scale_m >= 1000 else f"{scale_m} m"
    _draw_text(draw, (x0, y0 + 7), label, font=_font(11))


def _draw_legend(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    metric_column: str,
    values: pd.Series,
    breaks: list[float],
) -> None:
    title_font = _font(14)
    body_font = _font(11)
    _draw_text(draw, (x, y), "Legenda", font=title_font)
    _draw_text(draw, (x, y + 24), _metric_label(metric_column), font=body_font)
    if values.dropna().empty:
        draw.rectangle([x, y + 54, x + 24, y + 74], fill=(218, 222, 229), outline=(148, 163, 184))
        _draw_text(draw, (x + 34, y + 55), "Sem dados", font=body_font)
        return

    valid = values.dropna()
    min_value = float(valid.min())
    max_value = float(valid.max())
    ranges: list[str] = []
    if not breaks:
        ranges = [_format_value(min_value)]
        colors = [_SECTOR_PALETTE[2]]
    else:
        limits = [min_value, *breaks, max_value]
        ranges = [
            f"{_format_value(limits[i])} a {_format_value(limits[i + 1])}"
            for i in range(len(limits) - 1)
        ]
        colors = _SECTOR_PALETTE[: len(ranges)]

    for idx, (label, color) in enumerate(zip(ranges, colors, strict=False)):
        yy = y + 54 + idx * 26
        draw.rectangle([x, yy, x + 24, yy + 18], fill=color[:3], outline=(148, 163, 184))
        _draw_text(draw, (x + 34, yy + 1), label, font=body_font)

    yy = y + 68 + len(ranges) * 26
    draw.ellipse([x + 2, yy, x + 18, yy + 16], fill=(20, 96, 181), outline=(255, 255, 255), width=2)
    _draw_text(draw, (x + 34, yy), "Ponto central", font=body_font)
    draw.ellipse([x + 2, yy + 28, x + 18, yy + 44], fill=(245, 158, 11), outline=(31, 41, 55))
    _draw_text(draw, (x + 34, yy + 28), "Concorrente", font=body_font)
    draw.rectangle([x + 3, yy + 57, x + 17, yy + 71], fill=(200, 0, 30), outline=(31, 41, 55))
    _draw_text(draw, (x + 34, yy + 55), "Ultra", font=body_font)


def _decode_intersections(
    lat: float,
    lng: float,
    setores_df: pd.DataFrame,
    setores_intersectados: pd.DataFrame,
    raio_km: float,
) -> tuple[list[dict[str, object]], BaseGeometry]:
    metric_crs = _local_metric_crs(lat, lng)
    to_metric = _transformer(CRS_ORIGEM_CENSO, metric_crs)
    to_wgs84 = _transformer(metric_crs, CRS_ORIGEM_CENSO)
    circle_metric = Point(0, 0).buffer(raio_km * 1000.0, quad_segs=96)
    circle_wgs84 = _project_geometry(circle_metric, to_wgs84)

    if setores_df is None or setores_df.empty or setores_intersectados.empty:
        return [], circle_metric

    geometry_col = "geometry_wkb" if "geometry_wkb" in setores_df.columns else "geometry"
    if geometry_col not in setores_df.columns:
        return [], circle_metric

    codigos = set(setores_intersectados.get("cod_setor", pd.Series(dtype=str)).astype(str))
    candidates = _bbox_prefilter(setores_df, circle_wgs84)
    if codigos and "cod_setor" in candidates.columns:
        candidates = candidates.loc[candidates["cod_setor"].astype(str).isin(codigos)]

    metrics = setores_intersectados.set_index(setores_intersectados["cod_setor"].astype(str), drop=False)
    records: list[dict[str, object]] = []
    for _, row in candidates.iterrows():
        geom_wgs84 = _decode_geometry(row[geometry_col])
        if geom_wgs84 is None:
            continue
        intersection = _project_geometry(geom_wgs84, to_metric).intersection(circle_metric)
        if intersection.is_empty:
            continue
        cod_setor = str(row.get("cod_setor", ""))
        metric_row = metrics.loc[cod_setor].to_dict() if cod_setor in metrics.index else {}
        records.append({"cod_setor": cod_setor, "geometry_metric": intersection, **metric_row})
    return records, circle_metric


def _project_points(
    points_df: pd.DataFrame,
    lat: float,
    lng: float,
) -> list[tuple[float, float]]:
    if points_df is None or points_df.empty or not {"lat", "lng"}.issubset(points_df.columns):
        return []
    to_metric = _transformer(CRS_ORIGEM_CENSO, _local_metric_crs(lat, lng))
    coords: list[tuple[float, float]] = []
    for _, row in points_df.iterrows():
        point_lat = pd.to_numeric(row.get("lat"), errors="coerce")
        point_lng = pd.to_numeric(row.get("lng"), errors="coerce")
        if pd.isna(point_lat) or pd.isna(point_lng):
            continue
        coords.append(to_metric.transform(float(point_lng), float(point_lat)))
    return coords


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
) -> bytes:
    """Renderiza PNG offline do relatorio pontual censitario.

    O mapa e estatico para uso em PDF/export. Ele usa setores reais intersectados,
    circulo metrico de 1.5 km, ponto central e pins opcionais ja filtrados por
    distancia real pelo motor censitario.
    """
    result = analisar_ponto_censitario_setores(
        lat,
        lng,
        setores_df,
        raio_km=raio_km,
        competitors_df=competitors_df,
        ultra_df=ultra_df,
    )
    setores_intersectados = result["setores_intersectados"]
    sector_records, circle_metric = _decode_intersections(
        lat,
        lng,
        setores_df,
        setores_intersectados,
        raio_km,
    )

    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image, "RGBA")
    title_font = _font(20)
    body_font = _font(12)
    small_font = _font(11)

    _draw_text(draw, (28, 22), "Relatorio Pontual Censitario - mapa estatico", font=title_font)
    subtitle = f"Centro: {lat:.6f}, {lng:.6f} | raio {raio_km:.1f} km | setores: {result['n_setores']}"
    _draw_text(draw, (28, 52), subtitle, font=body_font, fill=(71, 85, 105))

    map_box = (28, 92, width - 285, height - 54)
    legend_x = width - 252
    draw.rounded_rectangle(map_box, radius=6, fill=(248, 250, 252), outline=(203, 213, 225))

    bounds = list(circle_metric.bounds)
    for record in sector_records:
        geom = record["geometry_metric"]
        if isinstance(geom, BaseGeometry) and not geom.is_empty:
            minx, miny, maxx, maxy = geom.bounds
            bounds[0] = min(bounds[0], minx)
            bounds[1] = min(bounds[1], miny)
            bounds[2] = max(bounds[2], maxx)
            bounds[3] = max(bounds[3], maxy)

    minx, miny, maxx, maxy = bounds
    span_x = max(maxx - minx, 1.0)
    span_y = max(maxy - miny, 1.0)
    margin_x = span_x * 0.08
    margin_y = span_y * 0.08
    minx -= margin_x
    maxx += margin_x
    miny -= margin_y
    maxy += margin_y
    span_x = max(maxx - minx, 1.0)
    span_y = max(maxy - miny, 1.0)

    left, top, right, bottom = map_box
    inner_w = right - left - 24
    inner_h = bottom - top - 24
    scale = min(inner_w / span_x, inner_h / span_y)
    offset_x = left + 12 + (inner_w - span_x * scale) / 2
    offset_y = top + 12 + (inner_h - span_y * scale) / 2

    def project(x: float, y: float) -> tuple[float, float]:
        px = offset_x + (x - minx) * scale
        py = offset_y + (maxy - y) * scale
        return px, py

    metric_values = pd.Series(
        [pd.to_numeric(record.get(metric_column), errors="coerce") for record in sector_records],
        dtype="float64",
    )
    breaks = _build_breaks(metric_values)

    for idx, record in enumerate(sector_records):
        geom = record["geometry_metric"]
        color = _color_for_value(metric_values.iloc[idx], breaks)
        for polygon in _iter_polygons(geom):
            points = _polygon_to_pixels(polygon, project)
            if len(points) >= 3:
                draw.polygon(points, fill=color, outline=(71, 85, 105, 180))
                for interior in polygon.interiors:
                    hole = [(int(round(x)), int(round(y))) for x, y in (project(a, b) for a, b in interior.coords)]
                    if len(hole) >= 3:
                        draw.polygon(hole, fill=(248, 250, 252, 255))

    circle_points = [
        (int(round(x)), int(round(y)))
        for x, y in (project(x, y) for x, y in circle_metric.exterior.coords)
    ]
    if len(circle_points) >= 3:
        draw.line(circle_points + [circle_points[0]], fill=(15, 23, 42, 215), width=3)

    cx, cy = project(0, 0)
    draw.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=(20, 96, 181), outline=(255, 255, 255), width=2)
    draw.line([(cx - 11, cy), (cx + 11, cy)], fill=(20, 96, 181), width=2)
    draw.line([(cx, cy - 11), (cx, cy + 11)], fill=(20, 96, 181), width=2)

    for x, y in _project_points(result["concorrentes_raio"], lat, lng):
        px, py = project(x, y)
        draw.ellipse([px - 6, py - 6, px + 6, py + 6], fill=(245, 158, 11), outline=(31, 41, 55))

    for x, y in _project_points(result["ultra_raio"], lat, lng):
        px, py = project(x, y)
        draw.rectangle([px - 6, py - 6, px + 6, py + 6], fill=(200, 0, 30), outline=(31, 41, 55))

    if not sector_records:
        message = "Sem setores intersectados no raio"
        msg_w = _text_width(draw, message, body_font)
        _draw_text(
            draw,
            (int((left + right - msg_w) / 2), int((top + bottom) / 2)),
            message,
            font=body_font,
            fill=(71, 85, 105),
        )

    meters_per_px = 1 / scale
    _draw_scale_bar(draw, project, map_box, meters_per_px)
    _draw_legend(draw, legend_x, 96, metric_column, metric_values, breaks)

    footer = (
        "Metodo: intersecao geometrica setor x circulo em CRS metrico local. "
        "Distribuicao intrassetor aproximada por area."
    )
    _draw_text(draw, (28, height - 34), footer, font=small_font, fill=(71, 85, 105))

    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()
