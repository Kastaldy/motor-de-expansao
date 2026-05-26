from unittest.mock import patch

import pandas as pd
from shapely.geometry import box

from base_h3_brasil import (
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


def test_gerar_hexagonos_validos_uf_remove_hexagonos_fora_do_brasil():
    # brasil_geom cobre (0,0)-(10,10); hex_in tem centroide em (5,5), hex_out em (11,11)
    feature_uf = {"uf": "RJ", "geometry": {"type": "Polygon", "coordinates": []}}
    brasil_geom = box(0, 0, 10, 10)

    with patch("base_h3_brasil.h3.geo_to_cells", return_value=["hex_in", "hex_out"]):
        with patch(
            "base_h3_brasil.h3.cell_to_latlng",
            side_effect=[(5, 5), (11, 11)],  # (lat, lng): hex_in dentro, hex_out fora
        ):
            validos, removidos = gerar_hexagonos_validos_uf(
                feature_uf=feature_uf,
                brasil_geom=brasil_geom,
                resolucao=7,
                chunk_size=10,
            )

    assert validos == ["hex_in"]
    assert removidos == 1

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
