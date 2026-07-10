from __future__ import annotations

import pandas as pd
import pytest
from pyproj import Transformer
from shapely.geometry import box
from shapely.ops import transform

from motor_expansao.dashboard.censo_point import (
    CRS_ORIGEM_CENSO,
    METODO_RELATORIO_PONTUAL_CENSITARIO,
    _local_metric_crs,
    analisar_ponto_censitario_setores,
)

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


def test_motor_censitario_setor_totalmente_dentro_do_raio():
    setor = box(-100, -100, 100, 100)
    df = pd.DataFrame([_sector_record("355030801000001", setor, pop=500, renda=1800, score=82)])

    result = analisar_ponto_censitario_setores(LAT_C, LNG_C, df)

    assert result["metodo"] == METODO_RELATORIO_PONTUAL_CENSITARIO
    assert result["raio_km"] == pytest.approx(1.5)
    assert result["area_km2"] == pytest.approx(7.07)
    assert result["n_setores"] == 1
    assert result["pop_total_raio"] == pytest.approx(500)
    assert result["renda_per_capita_media_raio"] == pytest.approx(1800)
    assert result["score_setor_medio"] == pytest.approx(82)
    setores = result["setores_intersectados"]
    assert setores.loc[0, "peso_area_setor"] == pytest.approx(1.0)
    assert setores.loc[0, "area_intersecao_m2"] == pytest.approx(setor.area)


def test_motor_censitario_setor_parcialmente_dentro_do_raio():
    from shapely.geometry import Point

    setor = box(1000, -500, 2500, 500)
    df = pd.DataFrame([_sector_record("355030801000002", setor, pop=1500, renda=2400, score=60)])
    expected_intersection_area = setor.intersection(Point(0, 0).buffer(1500, quad_segs=64)).area
    expected_weight = expected_intersection_area / setor.area

    result = analisar_ponto_censitario_setores(LAT_C, LNG_C, df)

    assert result["n_setores"] == 1
    assert result["setores_intersectados"].loc[0, "area_intersecao_m2"] == pytest.approx(
        expected_intersection_area,
        rel=0.01,
    )
    assert result["setores_intersectados"].loc[0, "peso_area_setor"] == pytest.approx(
        expected_weight,
        rel=0.01,
    )
    assert result["pop_total_raio"] == pytest.approx(1500 * expected_weight, rel=0.01)


def test_motor_censitario_exclui_setor_fora_do_raio():
    setor = box(3000, 3000, 3500, 3500)
    df = pd.DataFrame([_sector_record("355030801000003", setor)])

    result = analisar_ponto_censitario_setores(LAT_C, LNG_C, df)

    assert result["n_setores"] == 0
    assert result["pop_total_raio"] is None
    assert result["setores_intersectados"].empty


def test_motor_censitario_entrada_vazia_conta_pontos_por_distancia_real():
    competitors = pd.DataFrame(
        [
            {"nome_unidade": "Concorrente perto", "lat": LAT_C, "lng": LNG_C + 0.004},
            {"nome_unidade": "Concorrente longe", "lat": LAT_C + 0.1, "lng": LNG_C},
        ]
    )
    ultra = pd.DataFrame([{"nome_unidade": "Ultra perto", "lat": LAT_C, "lng": LNG_C}])

    result = analisar_ponto_censitario_setores(
        LAT_C,
        LNG_C,
        pd.DataFrame(),
        competitors_df=competitors,
        ultra_df=ultra,
    )

    assert result["n_setores"] == 0
    assert result["n_concorrentes"] == 1
    assert result["n_ultra"] == 1
    assert result["concorrentes_raio"]["nome_unidade"].tolist() == ["Concorrente perto"]


def test_motor_censitario_nao_muta_dataframe_de_entrada():
    setor = box(-100, -100, 100, 100)
    df = pd.DataFrame([_sector_record("355030801000004", setor)])
    original = df.copy(deep=True)

    analisar_ponto_censitario_setores(LAT_C, LNG_C, df)

    pd.testing.assert_frame_equal(df, original)


# ── BLK-RELPON-05: lookup do setor que CONTEM o ponto ────────────────────────────


def test_lookup_setor_do_ponto_dentro_da_malha():
    # Setor A cobre o ponto (0,0 no CRS metrico local) por completo. Setor B fica fora do
    # ambito de A (nao compartilha fronteira com o ponto) mas ainda dentro do raio de
    # 1.5 km, com renda/score bem diferentes -- serve para provar que o valor do ponto
    # NAO e reciclagem do agregado ponderado do raio (que combina A+B).
    setor_a = box(-700, -700, 700, 700)
    setor_b = box(1000, -200, 1400, 200)
    df = pd.DataFrame(
        [
            _sector_record("355030801000010", setor_a, pop=800, renda=1900, score=55),
            _sector_record("355030801000011", setor_b, pop=1400, renda=4200, score=95),
        ]
    )

    result = analisar_ponto_censitario_setores(LAT_C, LNG_C, df)

    assert result["flag_setor_ponto_encontrado"] is True
    assert result["cod_setor_ponto"] == "355030801000010"
    assert result["renda_per_capita_setor_ponto"] == pytest.approx(1900)
    assert result["score_setor_2022_calibrado_ponto"] == pytest.approx(55)
    assert result["densidade_pop_setor_ponto"] == pytest.approx(
        round(800 / (setor_a.area / 1_000_000.0), 2)
    )
    # Difere do agregado ponderado do raio (A+B combinados) -- prova que nao e reciclagem.
    assert result["renda_per_capita_setor_ponto"] != result["renda_per_capita_media_raio"]
    assert result["score_setor_2022_calibrado_ponto"] != result["score_setor_medio"]


def test_lookup_setor_do_ponto_fora_da_malha():
    # Setor que intersecta o raio mas NAO cobre o ponto (0,0): geometria de
    # test_motor_censitario_setor_parcialmente_dentro_do_raio.
    setor = box(1000, -500, 2500, 500)
    df = pd.DataFrame([_sector_record("355030801000012", setor)])

    result = analisar_ponto_censitario_setores(LAT_C, LNG_C, df)

    assert result["flag_setor_ponto_encontrado"] is False
    assert result["cod_setor_ponto"] is None
    assert result["renda_per_capita_setor_ponto"] is None
    assert result["densidade_pop_setor_ponto"] is None
    assert result["score_setor_2022_calibrado_ponto"] is None


def test_lookup_setor_ponto_setor_geometria_invalida_fica_ausente():
    # Setor cobre o ponto mas tem flag_geometria_valida=False -> ja excluido de
    # `candidates` antes do laco de intersecao (linha 196-197): nunca chega a ser
    # avaliado para conter o ponto, caindo em "n/d" por design (mesmo padrao do resto
    # da funcao).
    setor = box(-700, -700, 700, 700)
    record = _sector_record("355030801000013", setor)
    record["flag_geometria_valida"] = False
    df = pd.DataFrame([record])

    result = analisar_ponto_censitario_setores(LAT_C, LNG_C, df)

    assert result["n_setores"] == 0
    assert result["flag_setor_ponto_encontrado"] is False
    assert result["cod_setor_ponto"] is None
    assert result["renda_per_capita_setor_ponto"] is None
    assert result["densidade_pop_setor_ponto"] is None
    assert result["score_setor_2022_calibrado_ponto"] is None
