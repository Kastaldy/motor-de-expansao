from __future__ import annotations

from io import BytesIO

import pandas as pd
from PIL import Image
from pyproj import Transformer
from shapely.geometry import box
from shapely.ops import transform

from motor_expansao.dashboard.censo_map import render_mapa_censitario_estatico_png
from motor_expansao.dashboard.censo_point import CRS_ORIGEM_CENSO, _local_metric_crs

LAT_C = -23.55
LNG_C = -46.63


def _to_wgs_geometry(local_geom):
    transformer = Transformer.from_crs(_local_metric_crs(LAT_C, LNG_C), CRS_ORIGEM_CENSO, always_xy=True)
    return transform(transformer.transform, local_geom)


def _sector_record(
    cod_setor: str,
    local_geom,
    *,
    pop: float = 1000.0,
    renda: float = 2000.0,
    score: float = 70.0,
) -> dict[str, object]:
    geom_wgs = _to_wgs_geometry(local_geom)
    minx, miny, maxx, maxy = geom_wgs.bounds
    return {
        "cod_setor": cod_setor,
        "uf": "SP",
        "cod_municipio": "3550308",
        "nome_municipio": "SAO PAULO",
        "area_setor_m2": float(local_geom.area),
        "geometry_wkb": geom_wgs.wkb,
        "bbox_minx": minx,
        "bbox_miny": miny,
        "bbox_maxx": maxx,
        "bbox_maxy": maxy,
        "pop_total_setor_2022": pop,
        "renda_per_capita_setor_2022_calibrada": renda,
        "densidade_pop_setor_hab_km2": pop / (local_geom.area / 1_000_000.0),
        "score_setor_2022_calibrado": score,
        "flag_renda_disponivel": True,
        "flag_geometria_valida": True,
        "qualidade_join_uf": "A",
    }


def test_mapa_censitario_estatico_gera_png_com_setores_pins_legenda_e_escala(tmp_path):
    setores = pd.DataFrame(
        [
            _sector_record("355030801000001", box(-700, -700, 0, 700), pop=800, score=40),
            _sector_record("355030801000002", box(0, -700, 700, 700), pop=1400, score=85),
        ]
    )
    competitors = pd.DataFrame([{"nome_unidade": "Concorrente", "lat": LAT_C, "lng": LNG_C + 0.004}])
    ultra = pd.DataFrame([{"nome_unidade": "Ultra", "lat": LAT_C + 0.003, "lng": LNG_C}])

    png = render_mapa_censitario_estatico_png(
        LAT_C,
        LNG_C,
        setores,
        metric_column="score_setor_2022_calibrado",
        competitors_df=competitors,
        ultra_df=ultra,
        width=900,
        height=680,
    )
    output = tmp_path / "mapa_censitario.png"
    output.write_bytes(png)

    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert output.stat().st_size > 10_000
    image = Image.open(BytesIO(png))
    assert image.size == (900, 680)
    assert len(image.getcolors(maxcolors=1_000_000) or []) > 20


def test_mapa_censitario_estatico_trata_estado_vazio_sem_concorrentes():
    png = render_mapa_censitario_estatico_png(
        LAT_C,
        LNG_C,
        pd.DataFrame(),
        width=720,
        height=520,
    )

    image = Image.open(BytesIO(png))
    assert image.format == "PNG"
    assert image.size == (720, 520)
