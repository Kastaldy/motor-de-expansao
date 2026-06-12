"""Testes do parser de coordenada / Google Maps (BLK-API-03, coord.py)."""

from __future__ import annotations

import pytest

from motor_expansao.api.coord import (
    CoordenadaInvalidaError,
    parse_maps_url,
    resolver_coordenada,
    validar_brasil,
)

AGUAS = (-21.9180, -46.6855)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.google.com/maps/@-21.9180,-46.6855,15z",
        "https://maps.google.com/?q=-21.9180,-46.6855",
        "https://www.google.com/maps/place/X/@-21.9,-46.6,17z/data=!3d-21.9180!4d-46.6855",
        "-21.9180,-46.6855",
    ],
)
def test_parse_maps_url_formatos(url: str) -> None:
    lat, lng = parse_maps_url(url)
    assert round(lat, 4) == AGUAS[0]
    assert round(lng, 4) == AGUAS[1]


def test_parse_maps_url_prioriza_3d4d_sobre_at() -> None:
    # @ aponta o viewport (-21.9,-46.6); !3d!4d aponta o pino exato.
    url = "https://www.google.com/maps/place/X/@-21.9,-46.6,17z/data=!3d-21.9180!4d-46.6855"
    assert parse_maps_url(url) == (-21.9180, -46.6855)


def test_parse_maps_url_invalido() -> None:
    with pytest.raises(CoordenadaInvalidaError):
        parse_maps_url("https://maps.google.com/sem-coordenada")


def test_validar_brasil_dentro_e_fora() -> None:
    assert validar_brasil(*AGUAS) == AGUAS
    with pytest.raises(CoordenadaInvalidaError):
        validar_brasil(48.85, 2.35)  # Paris


def test_resolver_coordenada_latlng_e_url() -> None:
    assert resolver_coordenada(AGUAS[0], AGUAS[1], None) == AGUAS
    assert resolver_coordenada(None, None, "?q=-21.9180,-46.6855") == AGUAS
    with pytest.raises(CoordenadaInvalidaError):
        resolver_coordenada(None, None, None)
