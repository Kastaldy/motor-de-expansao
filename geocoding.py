"""
jobs/pipelines/geocoding.py — Geocodificação centralizada

Converte endereços em (lat, lng) com:
- Cache em memória para evitar chamadas repetidas
- Validação de coordenadas dentro do Brasil
- Fallback: Nominatim (gratuito) → Google Maps (pago, mais preciso)
- Rate limiting respeitoso

Uso:
    from jobs.pipelines.geocoding import geocodificar, geocodificar_lote
"""

import time
import functools
from typing import Optional

import structlog
from geopy.geocoders import Nominatim, GoogleV3
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

from api.config import settings

log = structlog.get_logger()

# Bounds do Brasil
BRASIL = {
    "lat_min": -33.75, "lat_max": 5.27,
    "lng_min": -73.98, "lng_max": -28.85,
}

# Cache simples em memória (persiste durante a sessão)
_cache: dict[str, tuple[float, float] | None] = {}


def _dentro_do_brasil(lat: float, lng: float) -> bool:
    return (
        BRASIL["lat_min"] <= lat <= BRASIL["lat_max"] and
        BRASIL["lng_min"] <= lng <= BRASIL["lng_max"]
    )


def geocodificar(
    endereco: str,
    cidade: str = "",
    uf: str = "",
    usar_google: bool = False,
) -> Optional[tuple[float, float]]:
    """
    Geocodifica um endereço e retorna (lat, lng).

    Estratégia:
    1. Verifica cache
    2. Tenta Nominatim (gratuito, rate limit: 1 req/s)
    3. Fallback para Google Maps se `usar_google=True` e API key configurada
    4. Valida que resultado está dentro do Brasil

    Returns: (lat, lng) ou None se falhar
    """
    # Normalizar chave do cache
    chave = f"{endereco}|{cidade}|{uf}".lower().strip()
    if chave in _cache:
        return _cache[chave]

    # Montar query completa
    partes = [p for p in [endereco, cidade, uf, "Brasil"] if p]
    query = ", ".join(partes)

    resultado = None

    # --- Tentativa 1: Nominatim ---
    try:
        geolocator = Nominatim(user_agent="motor_expansao_ultra_academia", timeout=10)
        time.sleep(1.1)  # Rate limit Nominatim: 1 req/s
        location = geolocator.geocode(query)

        if location and _dentro_do_brasil(location.latitude, location.longitude):
            resultado = (location.latitude, location.longitude)
            log.debug("geocodificado_nominatim", query=query, lat=resultado[0], lng=resultado[1])
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        log.warning("nominatim_erro", query=query, erro=str(e))

    # --- Tentativa 2: Google Maps (fallback) ---
    if resultado is None and usar_google and settings.GOOGLE_MAPS_API_KEY:
        try:
            geolocator_google = GoogleV3(api_key=settings.GOOGLE_MAPS_API_KEY)
            location = geolocator_google.geocode(query)
            if location and _dentro_do_brasil(location.latitude, location.longitude):
                resultado = (location.latitude, location.longitude)
                log.debug("geocodificado_google", query=query, lat=resultado[0], lng=resultado[1])
        except Exception as e:
            log.warning("google_geocoding_erro", query=query, erro=str(e))

    if resultado is None:
        log.warning("geocodificacao_falhou", query=query)

    _cache[chave] = resultado
    return resultado


def geocodificar_lote(
    registros: list[dict],
    campo_endereco: str = "endereco",
    campo_cidade: str = "cidade",
    campo_uf: str = "uf",
    usar_google: bool = False,
) -> list[dict]:
    """
    Geocodifica uma lista de registros em lote.
    Adiciona campos `lat` e `lng` nos registros que não os têm.

    Args:
        registros: Lista de dicts com campos de endereço
        campo_endereco: Nome do campo de endereço
        campo_cidade: Nome do campo de cidade
        campo_uf: Nome do campo de UF

    Returns: Lista de registros com lat/lng preenchidos
    """
    total = len(registros)
    geocodificados = 0
    falhas = 0

    for reg in registros:
        # Pular se já tem coordenadas válidas
        if reg.get("lat") and reg.get("lng"):
            continue

        endereco = reg.get(campo_endereco, "")
        cidade = reg.get(campo_cidade, "")
        uf = reg.get(campo_uf, "")

        if not endereco and not cidade:
            falhas += 1
            continue

        coords = geocodificar(endereco, cidade, uf, usar_google)
        if coords:
            reg["lat"], reg["lng"] = coords
            geocodificados += 1
        else:
            falhas += 1

    taxa = geocodificados / total * 100 if total > 0 else 0
    log.info(
        "geocodificacao_lote_concluida",
        total=total,
        geocodificados=geocodificados,
        falhas=falhas,
        taxa_sucesso=f"{taxa:.1f}%",
    )

    # Alerta se taxa de sucesso < 90%
    if taxa < 90.0 and total > 10:
        log.warning("geocodificacao_taxa_baixa", taxa=f"{taxa:.1f}%", threshold="90%")

    return registros


def limpar_cache() -> None:
    """Limpa o cache de geocodificação (útil em testes)."""
    _cache.clear()
