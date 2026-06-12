"""Utilitario PURO de coordenada (Decisao 4 / BLK-API-03).

Parser de link do Google Maps -> ``(lat, lng)`` por manipulacao de string (sem
rede, sem tocar o motor) + validacao do bounding box do Brasil. Sem dependencia
do motor ou de bibliotecas geoespaciais — so `re`.
"""

from __future__ import annotations

import re

# Bounding box aproximado do Brasil (inclui ilhas oceanicas: Noronha, Trindade).
BRASIL_LAT_MIN, BRASIL_LAT_MAX = -34.0, 5.5
BRASIL_LNG_MIN, BRASIL_LNG_MAX = -74.0, -28.0


class CoordenadaInvalidaError(ValueError):
    """Coordenada nao parseavel ou fora do Brasil (-> HTTP 400)."""


# Ordem de tentativa: !3dLAT!4dLNG (pino exato do place) tem prioridade sobre
# @lat,lng (centro do viewport), depois query params e "lat,lng" cru.
_PADROES = (
    re.compile(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)"),
    re.compile(r"@(-?\d+\.\d+),(-?\d+\.\d+)"),
    re.compile(r"[?&](?:q|query|ll|sll|center|destination)=(-?\d+\.\d+),\s*(-?\d+\.\d+)"),
    re.compile(r"^\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\s*$"),
)


def parse_maps_url(url: str) -> tuple[float, float]:
    """Extrai ``(lat, lng)`` de um link do Google Maps ou de ``"lat,lng"`` cru.

    Levanta `CoordenadaInvalidaError` se nenhum formato conhecido casar.
    """
    if not isinstance(url, str) or not url.strip():
        raise CoordenadaInvalidaError("maps_url vazio ou invalido")
    for padrao in _PADROES:
        m = padrao.search(url)
        if m:
            return float(m.group(1)), float(m.group(2))
    raise CoordenadaInvalidaError("Nao foi possivel extrair coordenada do maps_url")


def validar_brasil(lat: float, lng: float) -> tuple[float, float]:
    """Valida que ``(lat, lng)`` esta no bounding box do Brasil.

    Levanta `CoordenadaInvalidaError` quando fora. Nao confirma municipio — isso
    e responsabilidade do ponto-em-poligono no `service.py`.
    """
    dentro = (
        BRASIL_LAT_MIN <= lat <= BRASIL_LAT_MAX
        and BRASIL_LNG_MIN <= lng <= BRASIL_LNG_MAX
    )
    if not dentro:
        raise CoordenadaInvalidaError("Coordenada fora do Brasil")
    return lat, lng


def resolver_coordenada(
    lat: float | None,
    lng: float | None,
    maps_url: str | None,
) -> tuple[float, float]:
    """Resolve a coordenada a partir de ``{lat,lng}`` OU ``maps_url`` e valida Brasil."""
    if lat is not None and lng is not None:
        coord = (float(lat), float(lng))
    elif maps_url:
        coord = parse_maps_url(maps_url)
    else:
        raise CoordenadaInvalidaError("Forneca {lat,lng} ou maps_url")
    return validar_brasil(*coord)
