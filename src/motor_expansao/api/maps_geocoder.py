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

import ipaddress
import json
import re
import urllib.request
from urllib.parse import quote, unquote, urlencode, urlsplit

# Padroes de coordenada nas variantes de URL do Maps. ORDEM importa: !2d/!3d/!4d
# sao o PINO RESOLVIDO do place; @lat,lng e so o centro da camera (impreciso).
EMBED_PIN = re.compile(r"!2d(-?\d+(?:\.\d+)?)!3d(-?\d+(?:\.\d+)?)")      # !2d=lng !3d=lat
DETAIL_PIN = re.compile(r"!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)")     # !3d=lat !4d=lng
REVERSED_PIN = re.compile(r"!1d(-?\d+(?:\.\d+)?)!2d(-?\d+(?:\.\d+)?)")   # !1d=lng !2d=lat
CAMERA_AT = re.compile(r"@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)")          # centro da camera

# CEP brasileiro: 8 digitos, com ou sem hifen.
CEP_RE = re.compile(r"\b(\d{5})-?(\d{3})\b")

# Plus Code / Open Location Code. Alfabeto OLC = "23456789CFGHJMPQRVWX" (sem 0/1 e sem
# A/B/D/E/...). Codigo CURTO: 4 ou 6 chars antes do "+"; codigo COMPLETO: 8 antes. 2-3
# depois do "+". Ex.: "6M7J+GQ" (curto), "589R6M7J+GQ" (completo). Case-insensitive.
PLUS_CODE_RE = re.compile(r"\b([2-9CFGHJMPQRVWX]{2,8}\+[2-9CFGHJMPQRVWX]{2,3})\b", re.IGNORECASE)


# ── Guardrail SSRF (BLK-SEC-05) ─────────────────────────────────────────────
# `expandir_link_curto` (geo.py) e `resolve_short_link` seguem um link do usuario com
# uma requisicao HTTP no servidor. Sem trava, um usuario poderia fazer o container
# bater na REDE INTERNA do Docker (api:8077, authelia:9091, tileserver) ou em IP de
# metadata da nuvem. Por isso so aceitamos http(s) para um dominio/encurtador do
# proprio Google Maps (ou um IP publico); qualquer outro host e recusado ANTES do GET.
MAPS_HOST_ALLOWLIST: tuple[str, ...] = (
    "google.com",
    "google.com.br",
    "goo.gl",
    "maps.app.goo.gl",
    "g.co",
)


def host_de_maps_permitido(host: str) -> bool:
    """True se `host` e um dominio/encurtador do Google Maps, ou um IP PUBLICO.

    Recusa host interno/desconhecido e IP-literal privado/loopback/link-local
    (127.0.0.1, 10.x, 169.254.169.254, ::1, etc.) — o vetor de SSRF real.
    """
    h = (host or "").strip().lower().rstrip(".")
    if not h:
        return False
    try:
        ip = ipaddress.ip_address(h)
    except ValueError:
        # Nao e IP-literal: casa pelo sufixo de dominio permitido.
        return any(h == d or h.endswith("." + d) for d in MAPS_HOST_ALLOWLIST)
    # IP-literal: so publico global (bloqueia interno/metadata).
    return ip.is_global and not ip.is_multicast


def url_maps_segura(url: str) -> bool:
    """Guardrail SSRF: so http(s) para um host da allowlist do Maps (ou IP publico).

    Recusa `file://`/esquemas exoticos, host interno da rede Docker e IP privado.
    Usado antes de QUALQUER requisicao a um link fornecido pelo usuario.
    """
    try:
        parts = urlsplit(str(url or ""))
    except ValueError:
        return False
    if parts.scheme not in ("http", "https"):
        return False
    return host_de_maps_permitido(parts.hostname or "")


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


def extract_plus_code(text: str) -> tuple[str, str]:
    """Extrai o token Plus Code (OLC) e a LOCALIDADE que o segue. ('', '') se nao houver.

    Ex.: "6M7J+GQ Centro, Duque de Caxias - RJ" -> ("6M7J+GQ", "Centro, Duque de Caxias - RJ").
    O codigo e normalizado para maiusculas (o alfabeto OLC e maiusculo).
    """
    s = str(text or "")
    m = PLUS_CODE_RE.search(s)
    if not m:
        return "", ""
    code = m.group(1).upper()
    locality = s[m.end() :].strip(" ,;-\t").strip()
    return code, locality


def looks_like_plus_code(text: str) -> bool:
    """True se o texto contem um token com cara de Plus Code (roteia a cascata de busca)."""
    return bool(PLUS_CODE_RE.search(str(text or "")))


def resolve_plus_code(
    text: str, *, timeout: float = 6.0, cache_dir: object | None = None
) -> tuple[float, float] | None:
    """Plus Code (Open Location Code) -> (lat, lng), validado no bounding box do Brasil.

    BLK-UI-09-FU2: usa a biblioteca oficial `openlocationcode` (pura, sem deps
    transitivas), importada de forma LAZY (o modulo segue importavel sem ela).
    - Codigo COMPLETO (ex.: "589R6M7J+GQ"): decodifica OFFLINE (sem rede).
    - Codigo CURTO (ex.: "6M7J+GQ Duque de Caxias - RJ"): usa a LOCALIDADE que segue o
      codigo como referencia, resolvida por `resolve_endereco_http` (Nominatim, DEC-010);
      recupera o codigo completo (`recoverNearest`) e decodifica.

    Qualquer falha / sem rede / fora do Brasil -> None (o chamador cai no fallback).
    """
    try:
        from openlocationcode import openlocationcode as olc
    except Exception:
        return None

    code, locality = extract_plus_code(text)
    if not code or not olc.isValid(code):
        return None

    full = code
    if olc.isShort(code):
        # Codigo curto precisa de uma referencia: geocodifica a localidade (Nominatim).
        if not locality:
            return None
        ref = resolve_endereco_http(locality, timeout=timeout, cache_dir=cache_dir)
        if ref is None:
            return None
        try:
            full = olc.recoverNearest(code, ref[0], ref[1])
        except Exception:
            return None
    elif not olc.isFull(code):
        return None

    try:
        area = olc.decode(full)
        lat = float(area.latitudeCenter)
        lng = float(area.longitudeCenter)
    except Exception:
        return None

    if not (_BR_LAT_MIN <= lat <= _BR_LAT_MAX and _BR_LNG_MIN <= lng <= _BR_LNG_MAX):
        return None
    return lat, lng


def resolve_short_link(url: str, *, timeout: float = 6.0) -> str | None:
    """Segue o redirect HTTP de um link CURTO do Maps -> URL longa final (ou None).

    BLK-UI-09 / DEC-010 (emenda 2026-06-19, Opcao B): links curtos do Google Maps
    (`maps.app.goo.gl`, `goo.gl/maps`) NAO trazem a coordenada na propria string. Este
    helper faz UMA requisicao HTTP PURA (`urllib.request`, sem Selenium/navegador) so
    para seguir o(s) redirect(s) e ler a URL final (`resp.geturl()`), que costuma trazer
    o pino `!3d/!4d` ou `@lat,lng` — o chamador extrai a coordenada com `extract_any_coord`.

    GUARDRAIL (DEC-010): I/O de rede isolado nesta camada `api` (o import no dashboard e
    lazy; a rede so ocorre quando ESTA funcao e chamada, no sub-caminho de link curto da
    busca). `try/except` amplo + timeout curto: qualquer falha/ausencia de rede retorna
    `None` (o chamador cai no fallback gracioso). Enviamos um User-Agent identificavel
    (mesmo de `resolve_endereco_http`); a URL curta e enviada ao Google SO para seguir o
    redirect — nada e persistido (nota anti-PII da DEC-010).

    Retorna a URL longa final (str) ou `None` se faltar rede/falhar/timeout/URL vazia.
    """
    normalized = " ".join(str(url or "").split())
    if not normalized:
        return None
    # Guardrail SSRF (BLK-SEC-05): so seguimos links de dominio/encurtador do Maps.
    # Um host interno (api:8077, 169.254.169.254, file://) e recusado ANTES do GET.
    if not url_maps_segura(normalized):
        return None
    try:
        req = urllib.request.Request(
            normalized,
            headers={
                "User-Agent": _GEOCODE_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "pt-BR",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - URL validada por url_maps_segura
            final_url = resp.geturl() or getattr(resp, "url", None)
    except Exception:
        return None
    final_url = str(final_url or "").strip()
    # O redirect pode, em tese, apontar para fora do Maps -> so devolvemos destino seguro.
    if final_url and not url_maps_segura(final_url):
        return None
    return final_url or None


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
