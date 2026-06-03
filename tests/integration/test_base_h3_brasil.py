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

_CAND = "motor_expansao.pipelines.m1.base_h3_brasil._gerar_candidatos_uf"
_LATLNG = "motor_expansao.pipelines.m1.base_h3_brasil.h3.cell_to_latlng"
_BOUNDARY = "motor_expansao.pipelines.m1.base_h3_brasil.h3.cell_to_boundary"


def _box_geojson(lng0: float, lat0: float, lng1: float, lat1: float) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [[[lng0, lat0], [lng1, lat0], [lng1, lat1], [lng0, lat1], [lng0, lat0]]],
    }


# Convencao dos testes:
#   - Brasil = box (lng/lat) 0..10
#   - UF "SP" = metade esquerda (lng 0..5); a metade direita (lng 5..10) e "UF vizinha"
#   - Mar = fora do box 0..10
_BRASIL = box(0, 0, 10, 10)
_UF_GEOJSON = _box_geojson(0, 0, 5, 10)


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


def test_normalizar_features_uf_mapeia_todas_as_ufs():
    geometry = {
        "type": "Polygon",
        "coordinates": [[[-49.5, -16.9], [-49.4, -16.9], [-49.4, -16.8], [-49.5, -16.8], [-49.5, -16.9]]],
    }
    payload = {
        "features": [
            {"properties": {"codarea": codarea}, "geometry": geometry}
            for codarea in (
                "11", "12", "13", "14", "15", "16", "17", "21", "22", "23",
                "24", "25", "26", "27", "28", "29", "31", "32", "33", "35",
                "41", "42", "43", "50", "51", "52", "53",
            )
        ]
    }

    features = normalizar_features_uf(payload)

    assert len(features) == 27
    assert features[0]["uf"] == "AC"
    assert features[-1]["uf"] == "TO"
    assert {feature["regiao"] for feature in features} == set(REGIAO_POR_UF.values())


def test_gerar_hexagonos_fast_path_centroide_na_uf():
    # hex_uf: centroide (lat 5, lng 2) DENTRO da UF -> mantido pelo fast path, sem
    # avaliar poligono (custo zero no interior).
    feature_uf = {"uf": "SP", "geometry": _UF_GEOJSON}

    with patch(_CAND, return_value=["hex_uf"]):
        with patch(_LATLNG, side_effect=[(5, 2)]):
            with patch(_BOUNDARY) as mock_boundary:
                validos, removidos, recuperados, vec = gerar_hexagonos_validos_uf(
                    feature_uf=feature_uf, brasil_geom=_BRASIL, resolucao=7, coletar_fracao_terra=True
                )

    assert validos == ["hex_uf"]
    assert removidos == 0
    assert recuperados == 0
    assert vec == []
    mock_boundary.assert_not_called()


def test_gerar_hexagonos_centroide_uf_vizinha_ignorado_sem_duplicar():
    # hex_vizinho: centroide (lat 5, lng 7) em terra do Brasil mas FORA desta UF
    # (metade direita = UF vizinha). Deve ser IGNORADO aqui (a UF vizinha o reivindica
    # pelo proprio centro) -> nao entra em validos, nem conta como removido/recuperado.
    # Esta e a correcao do BLK-FIX-06-B: sem isso, candidatos overlap duplicavam hexes
    # de borda entre UFs.
    feature_uf = {"uf": "SP", "geometry": _UF_GEOJSON}

    with patch(_CAND, return_value=["hex_vizinho"]):
        with patch(_LATLNG, side_effect=[(5, 7)]):
            with patch(_BOUNDARY) as mock_boundary:
                validos, removidos, recuperados, vec = gerar_hexagonos_validos_uf(
                    feature_uf=feature_uf, brasil_geom=_BRASIL, resolucao=7, coletar_fracao_terra=True
                )

    assert validos == []
    assert removidos == 0
    assert recuperados == 0
    assert vec == []
    mock_boundary.assert_not_called()  # nao e mar: nem avalia poligono


def test_gerar_hexagonos_costeiro_mantido_pelo_limiar():
    # hex_costeiro: centroide (lat -0.5, lng 2) NO MAR (fora da UF e do Brasil), mas o
    # poligono sobrepoe terra com fracao >= 0.20 -> recuperado.
    # Quadrado lat[-1.5,0.5] x lng[1,3]: parte sobre o Brasil (lat[0,0.5]) = 0.5 de 2.0
    # de altura => fracao = 0.25 >= 0.20 => MANTIDO.
    feature_uf = {"uf": "SP", "geometry": _UF_GEOJSON}

    with patch(_CAND, return_value=["hex_costeiro"]):
        with patch(_LATLNG, side_effect=[(-0.5, 2)]):
            with patch(_BOUNDARY, return_value=_boundary_quadrado(-0.5, 2.0, meia_aresta=1.0)):
                validos, removidos, recuperados, vec = gerar_hexagonos_validos_uf(
                    feature_uf=feature_uf,
                    brasil_geom=_BRASIL,
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


def test_gerar_hexagonos_mar_aberto_descartado():
    # hex_mar: centroide no mar e poligono com fracao ~0 (<0.20) -> descartado.
    feature_uf = {"uf": "SP", "geometry": _UF_GEOJSON}

    with patch(_CAND, return_value=["hex_mar"]):
        with patch(_LATLNG, side_effect=[(-5, 2)]):
            with patch(_BOUNDARY, return_value=_boundary_quadrado(-5.0, 2.0)):
                validos, removidos, recuperados, vec = gerar_hexagonos_validos_uf(
                    feature_uf=feature_uf,
                    brasil_geom=_BRASIL,
                    resolucao=7,
                    land_fraction_min=0.20,
                    coletar_fracao_terra=True,
                )

    assert validos == []
    assert removidos == 1
    assert recuperados == 0
    assert vec == []  # fracao_terra == 0 nao entra no vetor


def test_gerar_hexagonos_borda_no_limiar_usa_maior_ou_igual():
    # hex_borda: centroide no mar (lat 5, lng 5 — fora da UF lng[0,3] e do brasil_geom
    # fino) com fracao de terra exatamente == limiar (0.20) -> MANTIDO (regra >=).
    feature_uf = {"uf": "SP", "geometry": _box_geojson(0, 0, 3, 10)}
    # quadrado do hex: lng in [4,6], lat in [4,6] (area 4); brasil_geom cobre
    # lng[4,6] x lat[4,4.4] => intersecao area = 2 * 0.4 = 0.8; fracao = 0.8/4 = 0.20.
    brasil_geom = Polygon([(4, 4), (6, 4), (6, 4.4), (4, 4.4)])

    with patch(_CAND, return_value=["hex_borda"]):
        with patch(_LATLNG, side_effect=[(5, 5)]):
            with patch(_BOUNDARY, return_value=_boundary_quadrado(5.0, 5.0, meia_aresta=1.0)):
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
