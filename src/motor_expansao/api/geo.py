"""Geocoding para o bot.

Combina a funcao de limpeza de endereco do Juan (`endereco_para_link_maps`) com
um geocoder (Nominatim/geopy) para resolver endereco+CEP -> coordenada:
  1. `endereco_para_link_maps` limpa o texto (remove CEP, complementos, ancora no
     pais) e devolve um link de busca do Maps;
  2. extraimos o texto limpo do parametro `query=` e geocodificamos -> (lat,lng,nome).

Mantido fora do `coord.py` porque AQUI ha acesso a rede; o `coord.py` segue puro.
Para geocoding mais preciso, trocar `_nominatim_geocode` pela Google Geocoding API
(exige `GOOGLE_MAPS_API_KEY`).
"""

from __future__ import annotations

import atexit
import re
import threading
from urllib.parse import unquote

import requests

from motor_expansao.api.settings import Settings

_USER_AGENT = "motor_expansao_ultra_academia_bot"
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_GOOGLE_GEOCODE = "https://maps.googleapis.com/maps/api/geocode/json"

_URL_RE = re.compile(r"https?://\S+")
# Segmento de endereco em URLs /maps/place/<NOME+ENDERECO>/... (sem coordenada).
_PLACE_RE = re.compile(r"/maps/place/([^/]+)")


def extrair_endereco_de_place_url(url: str) -> str:
    """Extrai o texto de endereco de uma URL `/maps/place/<NOME+ENDERECO>/...`.

    Alguns links de compartilhamento do Maps expandem para um place SEM coordenada
    na URL (so nome + endereco + place-id; a coord so viria via JS). Mas o endereco
    completo (com CEP) esta no proprio path -> extraimos para geocodificar. Devolve
    "" se a URL nao for um link de place.
    """
    m = _PLACE_RE.search(str(url or ""))
    if not m:
        return ""
    seg = m.group(1).replace("+", " ")
    return " ".join(unquote(seg).split())


def expandir_link_curto(texto: str) -> str:
    """Segue o redirect de um link e devolve a URL FINAL (para links compactados).

    Links curtos/compartilhaveis do Maps (`maps.app.goo.gl/...`, `goo.gl/maps/...`,
    `g.co/...`, encurtadores em geral) NAO contem coordenada — sao um 30x para a URL
    completa (com `@lat,lng` / `!3d!4d`). Aqui seguimos o redirect de QUALQUER URL
    encontrada no texto e devolvemos a URL final, para o `parse_maps_url` (puro)
    extrair a coordenada. Sem lista fixa de hosts: aceita qualquer encurtador.

    Pensado para ser chamado SO quando o parse direto ja falhou — assim links
    completos (que ja parseiam) nao gastam rede. Sem URL no texto, ou falha de rede,
    devolve o texto ORIGINAL inalterado (cai no geocoding).
    """
    m = _URL_RE.search(str(texto or ""))
    if not m:
        return texto
    try:
        resp = requests.get(
            m.group(0), allow_redirects=True, timeout=10,
            headers={"User-Agent": _BROWSER_UA},
        )
        return resp.url or texto
    except requests.RequestException:
        return texto


def endereco_para_link_maps(endereco: str, pais: str = "Brasil") -> str:
    """Limpa um endereco livre e devolve um link navegavel de busca do Google Maps.

    (Funcao do Juan.) Independente: nao usa imports, regex nem urllib. Faz limpeza
    textual e percent-encoding (UTF-8) manualmente, preservando apenas chars nao
    reservados.
    """
    # 1) Normaliza espacos em branco.
    texto = " ".join(str(endereco or "").split())

    # 2) Remove o sufixo de CEP ("... - CEP 80000-000 ...") em diante.
    baixo = texto.lower()
    i = baixo.find("cep")
    while i != -1:
        antes = texto[i - 1] if i > 0 else " "
        fim = i + 3
        depois = texto[fim] if fim < len(texto) else " "
        if antes in " -,;" and depois in " :0123456789":
            texto = texto[:i]
            break
        i = baixo.find("cep", i + 1)

    # 3) Remove complementos (sala/bloco/loja/...) do primeiro separador em diante.
    baixo = texto.lower()
    chaves = ("sala", "bloco", "loja", "andar", "piso", "conjunto",
              "quadra", "lote", "apto", "apt")
    n = len(texto)
    for sep in range(n):
        if texto[sep] in ",;-":
            j = sep + 1
            while j < n and texto[j] == " ":
                j += 1
            achou = False
            for chave in chaves:
                if baixo.startswith(chave, j):
                    fim = j + len(chave)
                    seguinte = texto[fim] if fim < n else " "
                    if seguinte in " .":
                        texto = texto[:sep]
                        achou = True
                        break
            if achou:
                break

    # 4) Limpa lixo de pontuacao nas bordas e colapsa espacos.
    texto = " ".join(texto.split()).strip(" ,-")
    if not texto:
        return ""

    # 5) Garante o pais para ancorar a busca.
    if pais and pais.lower() not in texto.lower():
        texto = texto + ", " + pais

    # 6) Percent-encoding manual (UTF-8): mantem apenas chars nao reservados.
    seguros = ("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
               "0123456789-_.~")
    partes = []
    for byte in texto.encode("utf-8"):
        c = chr(byte)
        partes.append(c if c in seguros else f"%{byte:02X}")

    return "https://www.google.com/maps/search/?api=1&query=" + "".join(partes)


def endereco_limpo(texto: str) -> str:
    """Reusa a limpeza do Juan e devolve o ENDERECO limpo (texto, nao o link)."""
    link = endereco_para_link_maps(texto)
    if not link or "query=" not in link:
        return ""
    return unquote(link.split("query=", 1)[1])


def geocodificar_endereco(texto: str, settings: Settings) -> tuple[float, float, str] | None:
    """Endereco + CEP -> (lat, lng, nome). Retorna None se nao resolver.

    Cadeia: (1) geocoder do Google MAPS via Selenium (`maps_geocoder`) — primario,
    o mais preciso para endereco+CEP no Brasil (le o pino do place na URL do Maps);
    (2) fallback Google Geocoding API (se `google_maps_api_key`) ou Nominatim, sobre
    o texto LIMPO (funcao do Juan) e, se falhar, o BRUTO — a limpeza pode cortar a
    cidade quando o complemento ("Sala 3") vem antes dela. A API ainda valida o
    ponto (404 se fora da base).
    """
    # (1) Primario: Google Maps (Selenium). Mais lento (~5-15s, abre Chrome), mas
    # resolve endereco+CEP com a precisao do proprio Maps.
    resultado = _maps_geocode(texto)
    if resultado is not None:
        return resultado

    # (2) Fallback: Google Geocoding API (se chave) senao Nominatim.
    chave = settings.google_maps_api_key
    geocode = (lambda q: _google_geocode(q, chave)) if chave else _nominatim_geocode

    candidatos: list[str] = []
    limpo = endereco_limpo(texto)
    if limpo:
        candidatos.append(limpo)
    if texto and texto not in candidatos:
        candidatos.append(texto)  # fallback: endereco bruto
    for candidato in candidatos:
        resultado = geocode(candidato)
        if resultado is not None:
            return resultado
    return None


# --- geocoder Google MAPS via Selenium (primario; preciso p/ endereco+CEP) ----

# Singleton: um unico Chrome reutilizado por todas as chamadas (abrir/fechar por
# request seria lento demais). Protegido por lock porque os endpoints sync da API
# rodam num threadpool — o WebDriver nao e thread-safe.
_maps_lock = threading.Lock()
_maps_geocoder: object | None = None
_maps_indisponivel = False  # vira True se selenium/Chrome faltarem (nao retenta)


def _get_maps_geocoder() -> object | None:
    """Cria (1x) e devolve o MapsGeocoder singleton, ou None se indisponivel."""
    global _maps_geocoder, _maps_indisponivel
    if _maps_geocoder is not None:
        return _maps_geocoder
    if _maps_indisponivel:
        return None
    try:
        from motor_expansao.api.maps_geocoder import MapsGeocoder

        # require_place_pin=True: so aceita o PINO EXATO do place. Medicao 2026-06-12
        # mostrou que o centro @ da camera (fallback) gerava pontos ate 161 km errados;
        # com pino-exato, o CEP resolve o endereco com precisao e, quando nao ha pino,
        # retorna None -> cai no fallback Nominatim (melhor None do que ponto errado).
        _maps_geocoder = MapsGeocoder(headless=True, require_place_pin=True, timeout=20)
        atexit.register(lambda: getattr(_maps_geocoder, "close", lambda: None)())
        return _maps_geocoder
    except Exception:
        # selenium/webdriver/Chrome ausentes ou falha ao subir o navegador.
        _maps_indisponivel = True
        return None


def _maps_geocode(texto: str) -> tuple[float, float, str] | None:
    """Resolve endereco+CEP pelo Google Maps (Selenium). None se nao der."""
    from motor_expansao.api.maps_geocoder import split_address_cep

    endereco, cep = split_address_cep(texto)
    if not endereco and not cep:
        return None
    try:
        with _maps_lock:
            geocoder = _get_maps_geocoder()
            if geocoder is None:
                return None
            lat, lng = geocoder.geocode(endereco, cep=cep)  # type: ignore[attr-defined]
    except Exception:
        return None
    if lat is None:
        return None
    nome = endereco or texto.strip()
    return float(lat), float(lng), nome


def nome_do_local(lat: float, lng: float, settings: Settings) -> str:
    """Reverse geocode (coord -> nome do endereco). Usa Google (RAPIDO) se houver
    chave; senao devolve a coordenada na hora — NAO chama Nominatim reverse, que e
    lento (timeout ~10s) e instavel, deixando o bot travado. Nunca falha."""
    chave = settings.google_maps_api_key
    if chave:
        nome = _google_reverse(lat, lng, chave)
        if nome:
            return nome
    return f"{lat:.5f}, {lng:.5f}"


# --- geocoder Google (preciso; exige API key) ------------------------------


def _google_geocode(texto: str, key: str) -> tuple[float, float, str] | None:
    try:
        resp = requests.get(
            _GOOGLE_GEOCODE,
            params={"address": texto, "key": key, "region": "br", "language": "pt-BR"},
            timeout=15,
        )
        data = resp.json()
        if data.get("status") != "OK" or not data.get("results"):
            return None
        top = data["results"][0]
        loc = top["geometry"]["location"]
        return float(loc["lat"]), float(loc["lng"]), str(top.get("formatted_address", texto))
    except (requests.RequestException, ValueError, KeyError):
        return None


def _google_reverse(lat: float, lng: float, key: str) -> str | None:
    try:
        resp = requests.get(
            _GOOGLE_GEOCODE,
            params={"latlng": f"{lat},{lng}", "key": key, "language": "pt-BR"},
            timeout=15,
        )
        data = resp.json()
        if data.get("status") != "OK" or not data.get("results"):
            return None
        return str(data["results"][0].get("formatted_address")) or None
    except (requests.RequestException, ValueError, KeyError):
        return None


# --- geocoder Nominatim/geopy (fallback gratuito) --------------------------


def _nominatim_geocode(texto: str) -> tuple[float, float, str] | None:
    try:
        from geopy.geocoders import Nominatim

        geo = Nominatim(user_agent=_USER_AGENT, timeout=10)
        loc = geo.geocode(texto)
        if loc is None:
            return None
        return float(loc.latitude), float(loc.longitude), str(loc.address)
    except Exception:
        return None


def _nominatim_reverse(lat: float, lng: float) -> str | None:
    try:
        from geopy.geocoders import Nominatim

        geo = Nominatim(user_agent=_USER_AGENT, timeout=10)
        loc = geo.reverse((lat, lng), language="pt")
        return str(loc.address) if loc is not None else None
    except Exception:
        return None
