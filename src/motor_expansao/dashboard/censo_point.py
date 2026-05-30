from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np
import pandas as pd
from pyproj import CRS, Transformer
from shapely import from_wkb, make_valid
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform

CRS_ORIGEM_CENSO = "EPSG:4674"
METODO_RELATORIO_PONTUAL_CENSITARIO = "setor_censitario_intersecao_area_1p5km"
RAIO_CENSITARIO_DEFAULT_KM = 1.5


def _haversine_km(
    lat1: float,
    lat2: np.ndarray | float,
    lng1: float,
    lng2: np.ndarray | float,
) -> np.ndarray:
    radius_km = 6371.0
    lat1_r = np.radians(lat1)
    lat2_r = np.radians(lat2)
    dlat = lat2_r - lat1_r
    dlng = np.radians(lng2) - np.radians(lng1)
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1_r) * np.cos(lat2_r) * np.sin(dlng / 2) ** 2
    return radius_km * 2 * np.arctan2(np.sqrt(a), np.sqrt(np.maximum(0.0, 1.0 - a)))


def _local_metric_crs(lat: float, lng: float) -> CRS:
    return CRS.from_proj4(
        f"+proj=aeqd +lat_0={lat} +lon_0={lng} +datum=WGS84 +units=m +no_defs"
    )


def _transformer(source: CRS | str, target: CRS | str) -> Transformer:
    return Transformer.from_crs(source, target, always_xy=True)


def _project_geometry(geom: BaseGeometry, transformer: Transformer) -> BaseGeometry:
    return transform(transformer.transform, geom)


def _decode_geometry(value: object) -> BaseGeometry | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, BaseGeometry):
        geom = value
    else:
        geom = from_wkb(value)
    if geom is None or geom.is_empty:
        return None
    if not geom.is_valid:
        geom = make_valid(geom)
    if geom is None or geom.is_empty:
        return None
    return geom


def _numeric(df: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in df.columns:
        return pd.Series(default, index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce")


def _weighted_average(values: pd.Series, weights: pd.Series) -> float | None:
    valid = values.notna() & weights.notna() & weights.gt(0)
    if valid.any():
        return round(float(np.average(values[valid], weights=weights[valid])), 2)
    valid_values = values.notna()
    if valid_values.any():
        return round(float(values[valid_values].mean()), 2)
    return None


def _empty_setores_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "cod_setor",
            "uf",
            "cod_municipio",
            "nome_municipio",
            "area_setor_m2",
            "area_intersecao_m2",
            "peso_area_setor",
            "pop_total_setor_2022",
            "pop_estimada_intersecao",
            "renda_per_capita_setor_2022_calibrada",
            "densidade_pop_setor_hab_km2",
            "score_setor_2022_calibrado",
            "flag_renda_disponivel",
            "flag_geometria_valida",
            "qualidade_join_uf",
        ]
    )


def _points_in_radius(
    lat: float,
    lng: float,
    points_df: pd.DataFrame | None,
    raio_km: float,
) -> pd.DataFrame:
    if points_df is None or points_df.empty or "lat" not in points_df.columns or "lng" not in points_df.columns:
        return pd.DataFrame()
    valid = points_df[["lat", "lng"]].apply(pd.to_numeric, errors="coerce").notna().all(axis=1)
    if not valid.any():
        return pd.DataFrame(columns=list(points_df.columns) + ["dist_km"])
    pts = points_df.loc[valid].copy()
    dists = _haversine_km(
        lat,
        pts["lat"].to_numpy(dtype=float),
        lng,
        pts["lng"].to_numpy(dtype=float),
    )
    pts["dist_km"] = np.round(dists, 4)
    return pts.loc[pts["dist_km"] <= raio_km].sort_values("dist_km", kind="stable").reset_index(drop=True)


def _bbox_prefilter(
    setores_df: pd.DataFrame,
    circle_wgs84: BaseGeometry,
) -> pd.DataFrame:
    bbox_cols = {"bbox_minx", "bbox_miny", "bbox_maxx", "bbox_maxy"}
    if not bbox_cols.issubset(set(setores_df.columns)):
        return setores_df
    minx, miny, maxx, maxy = circle_wgs84.bounds
    mask = (
        _numeric(setores_df, "bbox_maxx").ge(minx)
        & _numeric(setores_df, "bbox_minx").le(maxx)
        & _numeric(setores_df, "bbox_maxy").ge(miny)
        & _numeric(setores_df, "bbox_miny").le(maxy)
    )
    return setores_df.loc[mask]


def _available_columns(preferred: Iterable[str], df: pd.DataFrame) -> list[str]:
    return [column for column in preferred if column in df.columns]


def analisar_ponto_censitario_setores(
    lat: float,
    lng: float,
    setores_df: pd.DataFrame,
    raio_km: float = RAIO_CENSITARIO_DEFAULT_KM,
    competitors_df: pd.DataFrame | None = None,
    ultra_df: pd.DataFrame | None = None,
) -> dict:
    """Analisa um ponto por intersecao real entre setores censitarios e circulo.

    A entrada esperada e uma base setorial ja recortada/carregada com `geometry_wkb`
    em EPSG:4674. A funcao e pura: nao muta os DataFrames recebidos e nao recalcula
    nenhum artefato oficial do M1.
    """
    area_km2 = math.pi * raio_km**2
    concorrentes_raio = _points_in_radius(lat, lng, competitors_df, raio_km)
    ultra_raio = _points_in_radius(lat, lng, ultra_df, raio_km)
    result: dict = {
        "lat": lat,
        "lng": lng,
        "raio_km": raio_km,
        "area_km2": round(area_km2, 2),
        "metodo": METODO_RELATORIO_PONTUAL_CENSITARIO,
        "n_setores": 0,
        "area_intersecao_total_m2": 0.0,
        "pop_total_raio": None,
        "renda_per_capita_media_raio": None,
        "metodo_renda_raio": "ausente",
        "densidade_pop_raio_hab_km2": None,
        "score_setor_medio": None,
        "score_setor_max": None,
        "n_concorrentes": len(concorrentes_raio),
        "n_ultra": len(ultra_raio),
        "concorrentes_raio": concorrentes_raio,
        "ultra_raio": ultra_raio,
        "setores_intersectados": _empty_setores_frame(),
    }

    if setores_df is None or setores_df.empty:
        return result
    if "geometry_wkb" not in setores_df.columns and "geometry" not in setores_df.columns:
        return result

    metric_crs = _local_metric_crs(lat, lng)
    to_metric = _transformer(CRS_ORIGEM_CENSO, metric_crs)
    to_wgs84 = _transformer(metric_crs, CRS_ORIGEM_CENSO)
    center_metric = Point(0, 0)
    circle_metric = center_metric.buffer(raio_km * 1000.0, quad_segs=64)
    circle_wgs84 = _project_geometry(circle_metric, to_wgs84)

    candidates = _bbox_prefilter(setores_df, circle_wgs84)
    if "flag_geometria_valida" in candidates.columns:
        candidates = candidates.loc[candidates["flag_geometria_valida"].fillna(False).astype(bool)]
    if candidates.empty:
        return result

    geometry_col = "geometry_wkb" if "geometry_wkb" in candidates.columns else "geometry"
    records: list[dict[str, object]] = []
    for _idx, row in candidates.iterrows():
        geom_wgs84 = _decode_geometry(row[geometry_col])
        if geom_wgs84 is None:
            continue
        geom_metric = _project_geometry(geom_wgs84, to_metric)
        if geom_metric.is_empty:
            continue
        intersection = geom_metric.intersection(circle_metric)
        if intersection.is_empty:
            continue
        area_intersecao_m2 = float(intersection.area)
        if area_intersecao_m2 <= 0:
            continue
        area_setor_m2 = pd.to_numeric(row.get("area_setor_m2", np.nan), errors="coerce")
        if pd.isna(area_setor_m2) or float(area_setor_m2) <= 0:
            area_setor_m2 = float(geom_metric.area)
        peso_area = max(0.0, min(1.0, area_intersecao_m2 / float(area_setor_m2)))
        record = row.to_dict()
        record["area_setor_m2"] = float(area_setor_m2)
        record["area_intersecao_m2"] = area_intersecao_m2
        record["peso_area_setor"] = peso_area
        records.append(record)

    if not records:
        return result

    intersectados = pd.DataFrame(records).reset_index(drop=True)
    pop_setor = _numeric(intersectados, "pop_total_setor_2022").clip(lower=0)
    intersectados["pop_estimada_intersecao"] = pop_setor * intersectados["peso_area_setor"]

    renda = _numeric(intersectados, "renda_per_capita_setor_2022_calibrada")
    if renda.isna().all() and "renda_per_capita_setor_2022" in intersectados.columns:
        renda = _numeric(intersectados, "renda_per_capita_setor_2022")
        intersectados["renda_per_capita_setor_2022_calibrada"] = renda

    score = _numeric(intersectados, "score_setor_2022_calibrado")
    area_weights = _numeric(intersectados, "area_intersecao_m2").clip(lower=0)
    pop_weights = _numeric(intersectados, "pop_estimada_intersecao").clip(lower=0)
    renda_weight = pop_weights.where(pop_weights.gt(0), area_weights)
    score_weight = pop_weights.where(pop_weights.gt(0), area_weights)

    display_cols = _available_columns(_empty_setores_frame().columns, intersectados)
    result["setores_intersectados"] = intersectados[display_cols].copy()
    result["n_setores"] = len(intersectados)
    result["area_intersecao_total_m2"] = round(float(area_weights.sum()), 2)

    if pop_weights.notna().any():
        pop_total = float(pop_weights.fillna(0).sum())
        result["pop_total_raio"] = round(pop_total, 2)
        result["densidade_pop_raio_hab_km2"] = round(pop_total / area_km2, 2)

    result["renda_per_capita_media_raio"] = _weighted_average(renda, renda_weight)
    if result["renda_per_capita_media_raio"] is not None:
        result["metodo_renda_raio"] = (
            "ponderada_populacao_estimada"
            if pop_weights.gt(0).any()
            else "ponderada_area_intersecao"
        )

    result["score_setor_medio"] = _weighted_average(score, score_weight)
    if score.notna().any():
        result["score_setor_max"] = round(float(score.max()), 2)

    return result
