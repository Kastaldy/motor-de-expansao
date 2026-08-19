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


# --- Apple Maps / iPhone (BLK-FIX-MAPSQ) ---------------------------------------------
# O app nativo de Mapas do iOS NUNCA compartilha com `@lat,lng`: usa `ll=`, `coordinate=`
# ou `daddr=`. Sem estes parametros o link do iPhone morria em "Nao consegui localizar".


def test_apple_maps_coordinate():
    from motor_expansao.api.coord import parse_maps_url

    lat, lng = parse_maps_url(
        "https://maps.apple.com/place?coordinate=-3.7361,-38.4975&name=AYO+Gym"
    )
    assert (round(lat, 4), round(lng, 4)) == (-3.7361, -38.4975)


def test_apple_maps_daddr_e_saddr():
    """Rota do Apple Maps: destino (`daddr`) e origem (`saddr`)."""
    from motor_expansao.api.coord import parse_maps_url

    assert parse_maps_url("https://maps.apple.com/?daddr=-3.7361,-38.4975")[0] == -3.7361
    assert parse_maps_url("https://maps.apple.com/?saddr=-23.55,-46.63")[1] == -46.63


def test_apple_maps_ll_continua_valendo():
    from motor_expansao.api.coord import parse_maps_url

    lat, lng = parse_maps_url("https://maps.apple.com/?ll=-3.7327,-38.4869&q=Marcado")
    assert (round(lat, 4), round(lng, 4)) == (-3.7327, -38.4869)


def test_pino_exato_tem_prioridade_sobre_viewport():
    """`!3d!4d` (pino) vence `@lat,lng` (centro da camera) -- a ordem dos padroes importa:
    o centro do viewport pode estar a centenas de metros do ponto pedido."""
    from motor_expansao.api.coord import parse_maps_url

    url = ("https://www.google.com/maps/place/X/@-3.7000,-38.4000,17z/"
           "data=!3m1!4b1!4m5!3d-3.7673!4d-38.4867")
    assert parse_maps_url(url) == (-3.7673, -38.4867)
