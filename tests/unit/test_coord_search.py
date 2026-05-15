from __future__ import annotations

import pandas as pd
import pytest

from motor_expansao.dashboard.data import lookup_hex_by_coord, parse_coordinate_input


# ── parse_coordinate_input ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text,expected",
    [
        ("-23.55,-46.63", (-23.55, -46.63)),
        ("-23.55, -46.63", (-23.55, -46.63)),
        ("-23.55 -46.63", (-23.55, -46.63)),
        ("-23,55;-46,63", (-23.55, -46.63)),
        ("-23,55; -46,63", (-23.55, -46.63)),
        ("-23,55 -46,63", (-23.55, -46.63)),
        ("-23,55,-46,63", (-23.55, -46.63)),
        ("  -15.77 , -47.93  ", (-15.77, -47.93)),
    ],
)
def test_parse_formatos_validos(text, expected):
    result = parse_coordinate_input(text)
    assert result is not None
    assert result == pytest.approx(expected, abs=1e-5)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "ABC",
        "nao_e_numero",
        "-23.55",          # apenas uma coordenada
        "20.0,-50.0",      # lat fora do Brasil (norte demais)
        "-23.55,-5.0",     # lng fora do Brasil (leste demais)
        "-40.0,-46.63",    # lat fora do Brasil (sul demais)
        "-23.55,-80.0",    # lng fora do Brasil (oeste demais)
    ],
)
def test_parse_entrada_invalida_retorna_none(text):
    assert parse_coordinate_input(text) is None


def test_parse_none_retorna_none():
    assert parse_coordinate_input(None) is None  # type: ignore[arg-type]


def test_parse_limites_brasil():
    # ponto extremo norte (RR)
    assert parse_coordinate_input("5.0,-60.0") is not None
    # ponto extremo sul (RS)
    assert parse_coordinate_input("-33.0,-53.0") is not None
    # fora do norte
    assert parse_coordinate_input("6.0,-60.0") is None
    # fora do sul
    assert parse_coordinate_input("-34.0,-53.0") is None


# ── lookup_hex_by_coord ───────────────────────────────────────────────────────


def _base_df(hex_id: str, lat: float = -23.55, lng: float = -46.63) -> pd.DataFrame:
    return pd.DataFrame([{
        "hex_id": hex_id,
        "lat": lat,
        "lng": lng,
        "uf": "SP",
        "cidade": "Sao Paulo",
        "score_priorizacao": 80.0,
        "rank_brasil": 100,
    }])


def test_lookup_encontra_hex_quando_coordenada_pertence_ao_hex():
    import h3
    lat, lng = -23.55, -46.63
    hex_id = h3.latlng_to_cell(lat, lng, 7)
    df = _base_df(hex_id, lat, lng)
    result = lookup_hex_by_coord(lat, lng, df)
    assert result is not None
    assert result["hex_id"] == hex_id
    assert result["_not_found"] is False
    assert result["_searched_lat"] == pytest.approx(lat)
    assert result["_searched_lng"] == pytest.approx(lng)


def test_lookup_retorna_not_found_quando_hex_nao_esta_na_base():
    lat, lng = -15.77, -47.93  # Brasilia, diferente de SP
    df = _base_df("hex_sp_qualquer", -23.55, -46.63)
    result = lookup_hex_by_coord(lat, lng, df)
    assert result is not None
    assert result["_not_found"] is True
    assert "hex_id" in result


def test_lookup_nao_altera_score_priorizacao():
    import h3
    lat, lng = -23.55, -46.63
    hex_id = h3.latlng_to_cell(lat, lng, 7)
    df = _base_df(hex_id, lat, lng)
    result = lookup_hex_by_coord(lat, lng, df)
    assert result is not None
    assert result.get("score_priorizacao") == 80.0
