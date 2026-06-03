from unittest.mock import patch

import pandas as pd
import pytest
from shapely.geometry import Polygon, box

from motor_expansao.pipelines.m1.base_h3_brasil import (
    REGIAO_POR_UF,
    gerar_hexagonos_validos_uf,
    montar_dataframe_hexagonos,
    normalizar_features_uf,
    validar_dataframe_hexagonos,
)


def test_normalizar_features_uf_mapeia_todas_as_ufs():
    geometry = {
        "type": "Polygon",
        "coordinates": [[[-49.5, -16.9], [-49.4, -16.9], [-49.4, -16.8], [-49.5, -16.8], [-49.5, -16.9]]],
    }
    payload = {
        "features": [
            {"properties": {"codarea": codarea}, "geometry": geometry}
            for codarea in (
                "11",
                "12",
                "13",
                "14",
                "15",
                "16",
                "17",
                "21",
                "22",
                "23",
                "24",
                "25",
                "26",
                "27",
                "28",
                "29",
                "31",
                "32",
                "33",
                "35",
                "41",
                "42",
                "43",
                "50",
                "51",
                "52",
                "53",
            )
        ]
    }

    features = normalizar_features_uf(payload)

    assert len(features) == 27
    assert features[0]["uf"] == "AC"
    assert features[-1]["uf"] == "TO"
    assert {feature["regiao"] for feature in features} == set(REGIAO_POR_UF.values())


def _boundary_quadrado(lat_c: float, lng_c: float, meia_aresta: float = 0.5):
    """Boundary H3 sintetico (lat, lng) de um quadrado centrado em (lat_c, lng_c).

    `_hex_polygon` consome como `(lat, lng)` e converte para `(lng, lat)`.
    """
    return [
        (lat_c - meia_aresta, lng_c - meia_aresta),
        (lat_c - meia_aresta, lng_c + meia_aresta),
        (lat_c + meia_aresta, lng_c + meia_aresta),
        (lat_c + meia_aresta, lng_c - meia_aresta),
    ]


def test_gerar_hexagonos_validos_uf_remove_hexagonos_fora_do_brasil():
    # brasil_geom cobre (0,0)-(10,10); hex_in tem centroide em (5,5), hex_out em (11,11)
    # hex_out: centroide e poligono inteiramente fora -> fracao_terra 0 -> descartado.
    feature_uf = {"uf": "RJ", "geometry": {"type": "Polygon", "coordinates": []}}
    brasil_geom = box(0, 0, 10, 10)

    with patch("motor_expansao.pipelines.m1.base_h3_brasil.h3.geo_to_cells", return_value=["hex_in", "hex_out"]):
        with patch(
            "motor_expansao.pipelines.m1.base_h3_brasil.h3.cell_to_latlng",
            side_effect=[(5, 5), (11, 11)],  # (lat, lng): hex_in dentro, hex_out fora
        ):
            with patch(
                "motor_expansao.pipelines.m1.base_h3_brasil.h3.cell_to_boundary",
                return_value=_boundary_quadrado(11.0, 11.0),  # mar aberto, longe do box
            ):
                validos, removidos, recuperados, vec = gerar_hexagonos_validos_uf(
                    feature_uf=feature_uf,
                    brasil_geom=brasil_geom,
                    resolucao=7,
                    chunk_size=10,
                )

    assert validos == ["hex_in"]
    assert removidos == 1
    assert recuperados == 0
    assert vec == []


def test_gerar_hexagonos_hex_costeiro_mantido_pelo_limiar():
    # hex_costeiro: centroide FORA (lat -0.5, fora do box que exige lat>=0) mas
    # poligono com fracao de area dentro do box(0,0,10,10) >= 0.20.
    # Quadrado lat[-1.5,0.5] x lng[4,6]: parte interna lat[0,0.5] = 0.5 de 2.0 de
    # altura => fracao = 0.25 >= 0.20 => MANTIDO.
    feature_uf = {"uf": "SP", "geometry": {"type": "Polygon", "coordinates": []}}
    brasil_geom = box(0, 0, 10, 10)

    with patch("motor_expansao.pipelines.m1.base_h3_brasil.h3.geo_to_cells", return_value=["hex_costeiro"]):
        with patch(
            "motor_expansao.pipelines.m1.base_h3_brasil.h3.cell_to_latlng",
            side_effect=[(-0.5, 5)],  # (lat, lng): centroide fora do box
        ):
            with patch(
                "motor_expansao.pipelines.m1.base_h3_brasil.h3.cell_to_boundary",
                return_value=_boundary_quadrado(-0.5, 5.0, meia_aresta=1.0),
            ):
                validos, removidos, recuperados, vec = gerar_hexagonos_validos_uf(
                    feature_uf=feature_uf,
                    brasil_geom=brasil_geom,
                    resolucao=7,
                    land_fraction_min=0.20,
                    coletar_fracao_terra=True,
                )

    assert validos == ["hex_costeiro"]
    assert removidos == 0
    assert recuperados == 1
    assert len(vec) == 1
    assert vec[0][0] == "hex_costeiro"
    assert vec[0][1] == pytest.approx(0.25, abs=1e-6)


def test_gerar_hexagonos_hex_mar_aberto_descartado():
    # hex_mar: centroide fora e poligono com fracao ~0 (<0.20) -> descartado.
    feature_uf = {"uf": "RJ", "geometry": {"type": "Polygon", "coordinates": []}}
    brasil_geom = box(0, 0, 10, 10)

    with patch("motor_expansao.pipelines.m1.base_h3_brasil.h3.geo_to_cells", return_value=["hex_mar"]):
        with patch(
            "motor_expansao.pipelines.m1.base_h3_brasil.h3.cell_to_latlng",
            side_effect=[(-5, 5)],
        ):
            with patch(
                "motor_expansao.pipelines.m1.base_h3_brasil.h3.cell_to_boundary",
                return_value=_boundary_quadrado(-5.0, 5.0),  # totalmente fora do box
            ):
                validos, removidos, recuperados, vec = gerar_hexagonos_validos_uf(
                    feature_uf=feature_uf,
                    brasil_geom=brasil_geom,
                    resolucao=7,
                    land_fraction_min=0.20,
                    coletar_fracao_terra=True,
                )

    assert validos == []
    assert removidos == 1
    assert recuperados == 0
    assert vec == []  # fracao_terra == 0 nao entra no vetor


def test_gerar_hexagonos_hex_interior_nao_avalia_poligono():
    # hex_interior: centroide dentro -> mantido pelo fast path SEM chamar cell_to_boundary.
    feature_uf = {"uf": "GO", "geometry": {"type": "Polygon", "coordinates": []}}
    brasil_geom = box(0, 0, 10, 10)

    with patch("motor_expansao.pipelines.m1.base_h3_brasil.h3.geo_to_cells", return_value=["hex_interior"]):
        with patch(
            "motor_expansao.pipelines.m1.base_h3_brasil.h3.cell_to_latlng",
            side_effect=[(5, 5)],
        ):
            with patch(
                "motor_expansao.pipelines.m1.base_h3_brasil.h3.cell_to_boundary",
            ) as mock_boundary:
                validos, removidos, recuperados, vec = gerar_hexagonos_validos_uf(
                    feature_uf=feature_uf,
                    brasil_geom=brasil_geom,
                    resolucao=7,
                    land_fraction_min=0.20,
                    coletar_fracao_terra=True,
                )

    assert validos == ["hex_interior"]
    assert removidos == 0
    assert recuperados == 0
    mock_boundary.assert_not_called()  # custo zero no interior


def test_gerar_hexagonos_borda_no_limiar_usa_maior_ou_igual():
    # hex com fracao_terra exatamente == limiar (0.20) -> MANTIDO (regra >=).
    # Quadrado [4,6]x[4,6] (area 4); box recortado para deixar exatamente 20% (area 0.8).
    # Usamos um brasil_geom retangular fino que cobre 20% do quadrado do hex.
    feature_uf = {"uf": "SP", "geometry": {"type": "Polygon", "coordinates": []}}
    # quadrado do hex: x in [4,6], y in [4,6]; brasil_geom cobre x in [4,6], y in [4, 4.4]
    # => intersecao area = 2 * 0.4 = 0.8; fracao = 0.8/4 = 0.20 exato.
    brasil_geom = Polygon([(4, 4), (6, 4), (6, 4.4), (4, 4.4)])

    with patch("motor_expansao.pipelines.m1.base_h3_brasil.h3.geo_to_cells", return_value=["hex_borda"]):
        with patch(
            "motor_expansao.pipelines.m1.base_h3_brasil.h3.cell_to_latlng",
            side_effect=[(5, 5)],  # centroide em (5,5) fora do brasil_geom fino -> 2o teste
        ):
            with patch(
                "motor_expansao.pipelines.m1.base_h3_brasil.h3.cell_to_boundary",
                return_value=_boundary_quadrado(5.0, 5.0, meia_aresta=1.0),
            ):
                validos, removidos, recuperados, vec = gerar_hexagonos_validos_uf(
                    feature_uf=feature_uf,
                    brasil_geom=brasil_geom,
                    resolucao=7,
                    land_fraction_min=0.20,
                    coletar_fracao_terra=True,
                )

    assert vec[0][1] == pytest.approx(0.20, abs=1e-9)
    assert validos == ["hex_borda"]  # fracao == limiar -> mantido pela regra >=
    assert recuperados == 1


def test_leque_refiltra_vetor_de_fracao_terra():
    # Re-filtragem do vetor de fracao_terra por limiar (logica do leque do script):
    # um hex com fracao_terra=0.22 entra em 0.15/0.20 e sai em 0.25/0.30.
    vec = [("hex_a", 0.22), ("hex_b", 0.05), ("hex_c", 0.40)]

    def entram(limiar: float) -> set[str]:
        return {hid for hid, frac in vec if frac >= limiar}

    assert entram(0.15) == {"hex_a", "hex_c"}
    assert entram(0.20) == {"hex_a", "hex_c"}
    assert entram(0.25) == {"hex_c"}
    assert entram(0.30) == {"hex_c"}
    # hex_a (0.22): dentro em 0.15/0.20, fora em 0.25/0.30
    assert "hex_a" in entram(0.20) and "hex_a" not in entram(0.25)

def test_montar_dataframe_hexagonos_e_validar_nulls():
    df = montar_dataframe_hexagonos(["87a8c0ce3ffffff"], uf="GO", regiao="CO")

    assert list(df.columns) == ["hex_id", "lat", "lng", "uf", "regiao"]
    assert df.loc[0, "uf"] == "GO"
    assert df.loc[0, "regiao"] == "CO"
    assert validar_dataframe_hexagonos(df) == {
        "null_hex_id": 0,
        "null_lat": 0,
        "null_lng": 0,
        "null_uf": 0,
    }

    df_com_null = pd.DataFrame(
        [{"hex_id": None, "lat": None, "lng": -49.2, "uf": None, "regiao": "CO"}]
    )
    assert validar_dataframe_hexagonos(df_com_null) == {
        "null_hex_id": 1,
        "null_lat": 1,
        "null_lng": 0,
        "null_uf": 1,
    }
