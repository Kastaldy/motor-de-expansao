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
from urllib.parse import unquote, urljoin

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
# Forma alternativa de place SEM coordenada: `?q=<endereco>&ftid=0x...` (o Maps do Android
# devolve esta quando o link e' compartilhado pelo botao "Copiar link" de um pino salvo).
# Aceita tambem `query=`/`destination=` (Google) e `address=`/`daddr=` (Apple Maps do
# iPhone), que aparecem em links de navegacao e de place sem coordenada.
_Q_ENDERECO_RE = re.compile(r"[?&](?:q|query|destination|address|daddr)=([^&]+)")
# Par "lat,lng" ja e' tratado por `coord.parse_maps_url`; aqui so interessa TEXTO de endereco.
_COORD_PURA_RE = re.compile(r"^-?\d+\.\d+\s*,\s*-?\d+\.\d+$")


# Parametros que NUNCA sao endereco: identificadores, controles de camera e de UI. Sem esta
# lista o ultimo recurso abaixo devolveria coisas como "gps" (entry) ou "CAE" (shh) como se
# fossem logradouro.
_PARAMS_LIXO = frozenset({
    "ftid", "place-id", "placeid", "auid", "cid", "pb", "data", "entry", "shh", "lucs",
    "g_st", "gs_lcp", "hl", "gl", "ie", "oe", "output", "format", "source", "api", "t",
    "z", "zoom", "spn", "span", "layer", "view", "mode", "dirflg", "mapmode", "map_action",
    "basemap", "near", "sll", "ll", "coordinate", "center", "daddr", "saddr",
})
_PARAM_RE = re.compile(r"[?&]([A-Za-z_][\w.-]*)=([^&]+)")
# ID hexadecimal do Google (0x...:0x...) disfarcado de texto.
_ID_HEX_RE = re.compile(r"^0x[0-9a-f]+(:0x[0-9a-f]+)?$", re.I)


def _limpar_valor(valor: str) -> str:
    """Decodifica percent-encoding, troca `+` por espaco e normaliza espacos."""
    return " ".join(unquote(str(valor or "")).replace("+", " ").split())


def _parece_endereco(valor: str) -> bool:
    """Heuristica conservadora: texto com letras, comprido o bastante e que nao seja ID/coord.

    Prefere DEIXAR PASSAR pouco a arriscar geocodificar lixo: um valor errado aqui viraria um
    relatorio no lugar errado, que e' pior que o link falhar com mensagem clara.
    """
    if len(valor) < 8 or _COORD_PURA_RE.match(valor) or _ID_HEX_RE.match(valor):
        return False
    return any(c.isalpha() for c in valor) and (" " in valor or "," in valor)


def extrair_endereco_de_place_url(url: str) -> str:
    """Extrai o texto de endereco de uma URL `/maps/place/<NOME+ENDERECO>/...`.

    Alguns links de compartilhamento do Maps expandem para um place SEM coordenada
    na URL (so nome + endereco + place-id; a coord so viria via JS). Mas o endereco
    completo (com CEP) esta na propria URL -> extraimos para geocodificar.

    Duas formas cobertas: o path `/maps/place/<NOME+ENDERECO>/...` e o parametro
    `?q=<endereco>` (com `&ftid=0x...`), que e' o que o Maps do Android produz ao
    compartilhar um pino. Devolve "" quando nao ha endereco textual na URL.
    """
    texto = str(url or "")
    m = _PLACE_RE.search(texto)
    if m:
        seg = m.group(1).replace("+", " ")
        return " ".join(unquote(seg).split())

    # Fallback `?q=<endereco>`: link do Maps mobile que expande para
    # `google.com/maps?q=Av.+Santos+Dumont,+2915+-+Aldeota,+Fortaleza+-+CE,+60150-165&ftid=0x...`
    # -- nem `@lat,lng` nem `!3d!4d`, entao o parser puro falha e sem este ramo o link inteiro
    # morria em "Nao consegui localizar". O endereco vem completo, com CEP: geocodifica bem.
    m = _Q_ENDERECO_RE.search(texto)
    if m:
        seg = _limpar_valor(m.group(1))
        if _parece_endereco(seg):
            return seg

    # ULTIMO RECURSO: qualquer OUTRO parametro cujo valor pareca endereco. Mesma razao do
    # fallback generico de coordenada em `coord.py` -- a lista de nomes acima veio dos formatos
    # que conhecemos, e um app novo pode usar um nome que ninguem previu. Pega o valor mais
    # LONGO entre os candidatos: num link de place, o endereco completo e' quase sempre o campo
    # mais extenso, enquanto os curtos sao rotulo/ID.
    candidatos = [
        limpo
        for chave, bruto in _PARAM_RE.findall(texto)
        if chave.casefold() not in _PARAMS_LIXO
        and _parece_endereco(limpo := _limpar_valor(bruto))
    ]
    return max(candidatos, key=len) if candidatos else ""


def expandir_link_curto(texto: str) -> str:
    """Segue o redirect de um link e devolve a URL FINAL (para links compactados).

    Links curtos/compartilhaveis do Maps (`maps.app.goo.gl/...`, `goo.gl/maps/...`,
    `g.co/...`) NAO contem coordenada — sao um 30x para a URL completa (com
    `@lat,lng` / `!3d!4d`). Aqui seguimos o redirect e devolvemos a URL final, para o
    `parse_maps_url` (puro) extrair a coordenada.

    Guardrail SSRF (BLK-SEC-05): so seguimos links de dominio/encurtador do Google
    Maps (`url_maps_segura`), validando CADA salto de redirect. Um link para host
    interno da rede Docker (api:8077, authelia:9091), IP de metadata ou `file://` e
    recusado -> devolvemos o texto ORIGINAL (cai no geocoding, que so envia o texto
    como QUERY ao Nominatim, sem fetch da URL).

    Pensado para ser chamado SO quando o parse direto ja falhou — assim links
    completos (que ja parseiam) nao gastam rede. Sem URL valida no texto, ou falha de
    rede, devolve o texto ORIGINAL inalterado.
    """
    from motor_expansao.api.maps_geocoder import url_maps_segura

    m = _URL_RE.search(str(texto or ""))
    if not m:
        return texto
    url = m.group(0)
    if not url_maps_segura(url):
        return texto
    try:
        atual = url
        for _ in range(6):  # teto de saltos de redirect (evita loop/cadeia longa)
            resp = requests.get(
                atual, allow_redirects=False, timeout=10,
                headers={"User-Agent": _BROWSER_UA},
            )
            if resp.is_redirect or resp.is_permanent_redirect:
                destino = resp.headers.get("Location")
                if not destino:
                    return resp.url or texto
                destino = urljoin(atual, destino)
                # Re-valida cada salto: redirect para host interno e recusado.
                if not url_maps_segura(destino):
                    return texto
                atual = destino
                continue
            return resp.url or atual or texto
        return texto  # excesso de redirects
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
