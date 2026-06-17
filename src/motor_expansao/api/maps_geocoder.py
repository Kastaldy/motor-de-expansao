"""Geocoder endereco+CEP -> coordenada via Google Maps (Selenium), vendorado.

Versao de pacote do `geocoder_maps.py` da raiz (mesma logica), restrita ao que a
API consome: resolve uma busca no Maps lendo a coordenada do PINO do place a partir
da URL final do navegador, ignorando o centro @ da camera (centroide do bairro).

O `selenium`/`webdriver-manager` sao importados SO em `MapsGeocoder.__init__`, de
modo que `import maps_geocoder` nao falha se as libs nao estiverem instaladas — o
chamador (geo.py) trata isso e cai no fallback Nominatim/Google.

Dependencias: selenium, webdriver-manager, Google Chrome instalado.
"""

from __future__ import annotations

import json
import re
import urllib.request
from urllib.parse import quote, unquote, urlencode

# Padroes de coordenada nas variantes de URL do Maps. ORDEM importa: !2d/!3d/!4d
# sao o PINO RESOLVIDO do place; @lat,lng e so o centro da camera (impreciso).
EMBED_PIN = re.compile(r"!2d(-?\d+(?:\.\d+)?)!3d(-?\d+(?:\.\d+)?)")      # !2d=lng !3d=lat
DETAIL_PIN = re.compile(r"!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)")     # !3d=lat !4d=lng
REVERSED_PIN = re.compile(r"!1d(-?\d+(?:\.\d+)?)!2d(-?\d+(?:\.\d+)?)")   # !1d=lng !2d=lat
CAMERA_AT = re.compile(r"@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)")          # centro da camera

# CEP brasileiro: 8 digitos, com ou sem hifen.
CEP_RE = re.compile(r"\b(\d{5})-?(\d{3})\b")


def normalize_cep(cep: str) -> str:
    """Normaliza um CEP para '00000-000'. Retorna '' se nao houver 8 digitos."""
    m = CEP_RE.search(str(cep or ""))
    return f"{m.group(1)}-{m.group(2)}" if m else ""


def split_address_cep(linha: str) -> tuple[str, str]:
    """Separa '(endereco, cep)' de um texto livre.

    Suporta 'endereco;CEP' e CEP embutido no proprio texto; em ambos remove o CEP
    do endereco para nao duplicar na busca.
    """
    bruto = str(linha or "").strip()
    if not bruto:
        return "", ""
    if ";" in bruto:
        endereco, _, cep = bruto.partition(";")
        return endereco.strip(), normalize_cep(cep)
    cep = normalize_cep(bruto)
    if cep:
        return CEP_RE.sub("", bruto).strip(" ,-").strip(), cep
    return bruto, ""


def extract_place_pin(url: str) -> tuple[float | None, float | None]:
    """Le SO o pino resolvido do place. (None, None) se a busca nao resolveu."""
    text = unquote(str(url or ""))
    m = EMBED_PIN.search(text)
    if m:
        return float(m.group(2)), float(m.group(1))
    m = DETAIL_PIN.search(text)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = REVERSED_PIN.search(text)
    if m:
        return float(m.group(2)), float(m.group(1))
    return None, None


def extract_any_coord(url: str) -> tuple[float | None, float | None]:
    """Pino do place OU, em ultimo caso, o centro @ (menos preciso)."""
    lat, lng = extract_place_pin(url)
    if lat is not None:
        return lat, lng
    m = CAMERA_AT.search(unquote(str(url or "")))
    if m:
        return float(m.group(1)), float(m.group(2))
    return None, None


def build_search_url(query: str) -> str:
    """URL de busca navegavel do Maps a partir de texto livre."""
    normalized = " ".join(str(query or "").split())
    return f"https://www.google.com/maps/search/?api=1&query={quote(normalized)}"


# Bounding box do Brasil (mesmos limites de data._validate_brazil_bbox; duplicados aqui
# para manter este modulo `api` sem depender da camada dashboard).
_BR_LAT_MIN, _BR_LAT_MAX = -33.75, 5.27
_BR_LNG_MIN, _BR_LNG_MAX = -73.99, -28.65


def _cache_key(query: str) -> str:
    """Chave de cache estavel (sha1 do texto normalizado) p/ nome de arquivo seguro."""
    import hashlib

    normalized = " ".join(str(query or "").split()).lower()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


# Endpoint de geocoding por HTTP puro (DEC-010, emenda 2026-06-17 — provedor = OSM):
# o fetch contra o Google Maps via urllib NAO resolve coordenada (a pagina e renderizada
# por JS; sem navegador a URL final nao traz o pino). O Nominatim/OpenStreetMap devolve
# lat/lon em JSON com um GET simples, sem navegador.
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Usage Policy do Nominatim exige User-Agent identificavel (max 1 req/s, sem uso em massa).
_GEOCODE_USER_AGENT = "motor-expansao-ultra/1.0 (+https://ultraacademia.com.br)"


def resolve_endereco_http(
    query: str,
    *,
    timeout: float = 6.0,
    cache_dir: object | None = None,
) -> tuple[float, float] | None:
    """Resolve texto livre (endereco) -> (lat, lng) por fetch HTTP PURO (urllib).

    Usa o Nominatim/OpenStreetMap (DEC-010, emenda 2026-06-17): UMA requisicao GET leve
    ao endpoint de busca, que devolve lat/lon em JSON. SEM Selenium, SEM navegador (o
    fetch contra o Google Maps NAO resolve coordenada sem JS — por isso a troca de
    provedor).

    GUARDRAIL (DEC-010): I/O de rede isolado neste helper da camada `api` (NAO no
    dashboard); o import de `resolve_endereco_http` no dashboard e lazy e a rede so
    ocorre quando ESTA funcao e chamada (caminho de busca por endereco). `try/except`
    amplo + timeout curto garantem que qualquer falha/ausencia de rede retorne `None`
    (o chamador cai no fallback offline). O texto da consulta e enviado ao
    OpenStreetMap/Nominatim (nota anti-PII na DEC-010); enviamos um User-Agent
    identificavel conforme a Usage Policy (max 1 req/s, sem uso em massa) e cacheamos
    localmente para nao repetir requisicoes.

    Valida o resultado contra o bounding box do Brasil; fora dele -> `None`.
    `cache_dir` (opcional, ex.: `data/cache/geocode/`): cacheia o par lat,lng resolvido
    em arquivo texto por consulta, minimizando requisicoes repetidas.
    """
    normalized = " ".join(str(query or "").split())
    if not normalized:
        return None

    # 1) Cache local (gitignored). Leitura tolerante a falha.
    cache_path = None
    if cache_dir is not None:
        try:
            from pathlib import Path

            cache_path = Path(str(cache_dir)) / f"{_cache_key(normalized)}.txt"
            if cache_path.exists():
                raw = cache_path.read_text(encoding="utf-8").strip()
                lat_s, _, lng_s = raw.partition(",")
                c_lat, c_lng = float(lat_s), float(lng_s)
                if _BR_LAT_MIN <= c_lat <= _BR_LAT_MAX and _BR_LNG_MIN <= c_lng <= _BR_LNG_MAX:
                    return c_lat, c_lng
        except Exception:
            pass  # cache ausente/ilegivel -> ignora e refaz o fetch (cache_path segue valido p/ regravar)

    # 2) Fetch HTTP puro (urllib) ao Nominatim, lendo lat/lon do JSON.
    #    `urllib.request` e importado no topo do modulo (stdlib, sem rede no import) para
    #    ser facilmente mockavel em teste; a rede so ocorre no urlopen abaixo.
    url = f"{_NOMINATIM_URL}?" + urlencode(
        {
            "q": normalized,
            "format": "jsonv2",
            "limit": "1",
            "countrycodes": "br",
            "addressdetails": "0",
        }
    )
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": _GEOCODE_USER_AGENT,
                "Accept": "application/json",
                "Accept-Language": "pt-BR",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - URL fixa do Nominatim
            payload = resp.read(200_000).decode("utf-8", errors="ignore")
        data = json.loads(payload)
    except Exception:
        return None

    if not isinstance(data, list) or not data:
        return None
    try:
        lat = float(data[0]["lat"])
        lng = float(data[0]["lon"])
    except (KeyError, ValueError, TypeError, IndexError):
        return None
    if not (_BR_LAT_MIN <= lat <= _BR_LAT_MAX and _BR_LNG_MIN <= lng <= _BR_LNG_MAX):
        return None

    # 3) Persiste no cache (best-effort).
    if cache_path is not None:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(f"{lat},{lng}", encoding="utf-8")
        except Exception:
            pass
    return lat, lng


class MapsGeocoder:
    """Abre um Chrome headless e resolve endereco+CEP. Reutilize a MESMA instancia."""

    def __init__(
        self,
        *,
        headless: bool = True,
        timeout: int = 20,
        require_place_pin: bool = False,
        bounds: dict | None = None,
    ):
        # Imports tardios: so falham se MapsGeocoder for realmente instanciado.
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager

        self.timeout = timeout
        self.require_place_pin = require_place_pin
        self.bounds = bounds
        self._extract = extract_place_pin if require_place_pin else extract_any_coord

        options = Options()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.set_page_load_timeout(timeout + 10)

    def __enter__(self) -> MapsGeocoder:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        try:
            self.driver.quit()
        except Exception:
            pass

    def _within_bounds(self, lat: float, lng: float) -> bool:
        if not self.bounds:
            return True
        b = self.bounds
        return b["min_lat"] <= lat <= b["max_lat"] and b["min_lng"] <= lng <= b["max_lng"]

    def _resolve_url(self, query: str) -> tuple[float | None, float | None]:
        from selenium.webdriver.support.ui import WebDriverWait

        self.driver.get(build_search_url(query))
        try:
            WebDriverWait(self.driver, self.timeout).until(
                lambda d: "maps/place" in d.current_url or "@" in d.current_url
            )
        except Exception:
            pass
        lat, lng = self._extract(self.driver.current_url)
        if lat is None or lng is None or not self._within_bounds(lat, lng):
            return None, None
        return lat, lng

    def geocode(
        self, address: str, *, brand: str = "", cep: str = ""
    ) -> tuple[float | None, float | None]:
        """endereco (+CEP/brand) -> (lat, lng). Cadeia de fallback, mais preciso 1o."""
        address = " ".join(str(address or "").split())
        cep = normalize_cep(cep)
        if not address and not cep:
            return None, None

        tentativas: list[str] = []

        def add(q: str) -> None:
            q = " ".join(str(q or "").split())
            if q and q not in tentativas:
                tentativas.append(q)

        if brand and cep:
            add(f"{brand}, {address}, {cep}")
        if brand:
            add(f"{brand}, {address}")
        if cep:
            add(f"{address}, {cep}")   # endereco escrito + CEP
        add(address)
        if cep:
            add(cep)

        for query in tentativas:
            lat, lng = self._resolve_url(query)
            if lat is not None:
                return lat, lng
        return None, None
