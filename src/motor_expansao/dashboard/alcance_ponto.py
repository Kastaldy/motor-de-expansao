"""Alcance da analise de ponto: raio de 1 km, raio de 2 km, 5 e 10 min de carro (DEC-074).

O operador escolhe, NA FICHA do ponto, ate' onde a analise vai a partir do clique:

- ``raio_1km``   -- o estudo de sempre (DEC-021). Fator de regua EXATAMENTE 1.0.
- ``raio_2km``   -- o mesmo circulo, com o dobro do raio. Fator EXATAMENTE 4.0.
- ``carro_5min`` / ``carro_10min`` -- a ISOCRONA de 5 ou 10 min de carro sem transito,
  calculada por um Valhalla proprio (container na VPS, opcional pela env ``MOTOR_ROTAS_URL``).
  Os dois sao a MESMA isocrona com outro tempo: o tempo mora em `MINUTOS_DO_ALCANCE`, e
  quem consome (rota, motor, PDF, tela) le a tabela em vez de repetir o caso de 10 min. O de
  5 min entrou pela Emenda 1 da DEC-074 (20/10/2026, pedido do Vinicius, sem transito).

Identificadores CRUS, sem acento (CLAUDE.md secao 2): sao valor de payload e de query.

A REGUA (decisao do dono, 19/10/2026)
-------------------------------------
As reguas ABSOLUTAS de TOTAL (populacao minima, residual de destaque, teto de concorrentes,
metas do PDF, piso de populacao do gate do SAM) foram calibradas para o raio de 1 km
(pi km2). Num recorte maior elas aprovariam qualquer coisa so' por ele ser maior, entao
escalam pela AREA: ``fator_regua = area / (pi * 1^2)``. No raio o fator sai do RAIO
(``raio^2``) e nao da area medida, de proposito: a area de um circulo poligonizado nunca
da' pi exato (o de 256 vertices mede 3,1413), e um fator de 0,9999 moveria a meta de
10.000 habitantes do raio de 1 km para 9.999 -- regressao do estudo de sempre, que tem de
sair byte a byte igual. Reguas de MEDIA (renda, score, capacidade por academia) nao escalam.

O ISOCRONA E' DO SERVIDOR
-------------------------
O cliente manda so' (lat, lng, alcance); a geometria e' recalculada aqui, sempre. Aceitar
um poligono "de isocrona" vindo da tela reabriria a porta de corpo arbitrario que o teto
de 50 vertices do desenho a mao fecha (`geometria_desenhada`). Por isso o teto de vertices
deste modulo e' TECNICO (custo da intersecao setor a setor), aplicado DEPOIS da
simplificacao, e nao uma trava de entrada.

Travas de custo herdadas da DEC-071: area ate' 200 km2 e diagonal da caixa ate' 40 km.
A COMPACIDADE nao se aplica: ela existe contra ruido de desenho a mao, e uma isocrona
legitima tem forma de estrela (pontas ao longo das vias) -- recusa-la por isso recusaria
exatamente as pracas servidas por avenida. MultiPolygon (ilhas de alcance) e buracos
(lago, quadra sem acesso) sao REAIS e o motor ja' os le.

FALHA NUNCA VIRA RAIO EM SILENCIO
---------------------------------
Sem a env, com o servico fora, lento ou devolvendo 5xx: `RotasIndisponiveis` (a rota
responde 503 em portugues). Resposta que nao forma uma area analisavel: `AlcanceInvalido`
(400). Cair para o raio de 1 km sem dizer seria entregar um estudo diferente do pedido.

Modulo LEVE de proposito: so' shapely no import. `requests` e a projecao local (pyproj, via
`censo_point`) entram tardiamente, so' quando uma isocrona e' de fato calculada -- quem so'
quer o fator do raio (a rota de 1 km, o mercado) nao paga esse import.
"""

from __future__ import annotations

import logging
import math
import os
import time
from dataclasses import dataclass, replace
from functools import lru_cache
from typing import Any

import shapely
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import nearest_points, unary_union
from shapely.ops import transform as _shp_transform

_LOG = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Vocabulario                                                                  #
# --------------------------------------------------------------------------- #
ALCANCE_RAIO_1KM = "raio_1km"
ALCANCE_RAIO_2KM = "raio_2km"
ALCANCE_CARRO_5MIN = "carro_5min"
ALCANCE_CARRO_10MIN = "carro_10min"
RAIO_DO_ALCANCE = {ALCANCE_RAIO_1KM: 1.0, ALCANCE_RAIO_2KM: 2.0}
# A TABELA dos alcances de carro (DEC-074, Emenda 1): o tempo e' o unico parametro que muda
# entre eles. Um alcance novo de carro entra AQUI e no vocabulario da tela; o resto le daqui.
MINUTOS_DO_ALCANCE = {ALCANCE_CARRO_5MIN: 5, ALCANCE_CARRO_10MIN: 10}
# Ordem do seletor (decisao do dono): os raios, depois o carro do menor tempo ao maior.
ALCANCES = (ALCANCE_RAIO_1KM, ALCANCE_RAIO_2KM, *MINUTOS_DO_ALCANCE)
MINUTOS_ISOCRONA = 10  # o default de `isocrona_carro` (o alcance original da DEC-074)

# O raio em que as reguas absolutas foram calibradas (DEC-021). Literal, e NAO importado de
# `censo_point`, para o modulo seguir leve -- a igualdade e' travada por teste.
RAIO_REFERENCIA_KM = 1.0

# Travas de custo da DEC-071, repetidas como literal pelo mesmo motivo (`geometria_desenhada`
# importa `censo_point` e, com ele, pyproj). Igualdade travada por teste: se o teto do
# desenho mudar, este fica vermelho.
AREA_MAX_KM2 = 200.0
DIAGONAL_MAX_KM = 40.0

# Teto TECNICO de vertices depois da simplificacao: a intersecao setor a setor custa por
# vertice do recorte. Passou dele, a tolerancia dobra (ver `_simplificar_ate_o_teto`).
MAX_VERTICES_ISOCRONA = 2_000
TOLERANCIA_SIMPLIFICACAO_M = 25.0
# A origem tem de cair DENTRO do recorte: ela e' o centro da projecao local, o "setor do
# ponto" e o pin. O Valhalla parte da via mais proxima, entao um clique no meio de uma
# quadra grande pode ficar alguns metros fora do contorno -- une-se uma faixa de 75 m de
# meia largura ligando o clique ao contorno (perto, e' o disco de 75 m em volta dele).
BUFFER_ORIGEM_M = 75.0
# ...mas so' ate' aqui. Sem teto, o Valhalla procura a via mais proxima a ate' 35 km (o
# default dele): um clique no meio de um lago, de um parque grande ou de uma fazenda
# devolvia os 10 min a partir de OUTRO lugar, e a uniao com o disco escondia isso -- a tela
# e o PDF diziam "a partir do ponto" sobre uma area que nao parte dele. O mesmo valor vai
# no pedido (`search_cutoff`) e na checagem da resposta.
DIST_MAX_ORIGEM_M = 300.0

ENV_ROTAS = "MOTOR_ROTAS_URL"
TIMEOUT_ISOCRONA_S = (2, 15)  # (conexao, leitura)
# O status e' consultado ANTES da isocrona (a versao entra na chave do cache) e o carimbo
# e' opcional: leitura curta, para um Valhalla que aceita a conexao e nao responde nao
# segurar a vaga do semaforo das analises de area por mais 5 s a cada clique.
TIMEOUT_STATUS_S = (2, 2)
# Falha do status fica lembrada por este tempo (por URL): sem isso cada clique pagaria de
# novo o timeout do status antes mesmo de tentar a isocrona.
_ESPERA_APOS_FALHA_STATUS_S = 60.0
# A versao dos tiles entra no carimbo E na chave do cache: tiles reconstruidos mudam o
# resultado, e o cache em memoria nao pode servir a isocrona da malha viaria antiga.
# Reconsultada a cada hora para nao pagar um GET de status por clique.
_JANELA_VERSAO_S = 3600

MSG_ROTAS_INDISPONIVEIS = (
    "O cálculo de tempo de deslocamento está indisponível agora. "
    "Tente de novo em instantes ou use o raio."
)
# As frases levam o TEMPO como campo (`{minutos}`): a mesma recusa vale para 5 e 10 min, e
# dizer "10 min" a quem pediu 5 seria nomear outro recorte.
MSG_SEM_VIA = (
    "Não foi possível calcular os {minutos} min de carro a partir deste ponto (nenhuma rua "
    "alcançável por perto). Use o raio."
)
MSG_AREA_GRANDE = (
    "A área de {minutos} min de carro a partir deste ponto passa de {teto:.0f} km², o teto "
    "da análise. Use o raio de 2 km."
)
MSG_DIAGONAL_GRANDE = (
    "A área de {minutos} min de carro a partir deste ponto se estende por mais de "
    "{teto:.0f} km, o teto da análise. Use o raio de 2 km."
)
MSG_ORIGEM_FORA = (
    "O ponto clicado fica a mais de {dist:.0f} m de qualquer rua alcançável, então os "
    "{minutos} min de carro partiriam de outro lugar. Use o raio."
)


class RotasIndisponiveis(RuntimeError):
    """Servico de rotas ausente (env vazia), fora do ar, lento ou com 5xx -> 503.

    `str(exc)` e' SEMPRE a mensagem ao usuario; o detalhe tecnico vai em `detalhe` (log).
    """

    def __init__(self, detalhe: str = "") -> None:
        super().__init__(MSG_ROTAS_INDISPONIVEIS)
        self.detalhe = detalhe


class AlcanceInvalido(ValueError):
    """O servico respondeu, mas o recorte nao e' analisavel -> 400 com a mensagem."""


# --------------------------------------------------------------------------- #
# Fator de regua                                                               #
# --------------------------------------------------------------------------- #
def _positivo_finito(valor: float, nome: str) -> float:
    try:
        v = float(valor)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{nome} invalido: {valor!r}") from exc
    if not math.isfinite(v) or v <= 0:
        raise ValueError(f"{nome} tem de ser positivo e finito: {valor!r}")
    return v


def fator_regua_do_raio(raio_km: float) -> float:
    """``(raio / 1 km)^2``: 1 km -> EXATAMENTE 1.0, 2 km -> EXATAMENTE 4.0.

    Do raio, e nao da area: ver a docstring do modulo (a area poligonizada nao da' pi).
    """
    r = _positivo_finito(raio_km, "raio_km")
    return (r / RAIO_REFERENCIA_KM) ** 2


def fator_regua_da_area(area_km2: float) -> float:
    """``area / (pi * 1^2)``. Recebe a area EXATA -- nunca a arredondada do dict do motor
    (3,14 em vez de pi daria 0,9995 e moveria as metas)."""
    a = _positivo_finito(area_km2, "area_km2")
    return a / (math.pi * RAIO_REFERENCIA_KM**2)


# --------------------------------------------------------------------------- #
# Servico de rotas                                                             #
# --------------------------------------------------------------------------- #
def url_rotas() -> str | None:
    """URL base do Valhalla (sem barra final), ou `None` sem a env. Lida a cada chamada:
    a env e' do deploy, e um teste que a liga/desliga nao pode ficar preso num cache."""
    bruto = (os.environ.get(ENV_ROTAS) or "").strip().rstrip("/")
    return bruto or None


def rotas_configuradas() -> bool:
    """As opcoes de carro (5 e 10 min) existem neste deploy? (So' a env; nao consulta o
    servico.)"""
    return url_rotas() is not None


@lru_cache(maxsize=4)
def _versao_cacheada(url: str, _janela: int) -> str:
    """`GET {url}/status` -> carimbo da malha viaria. Levanta em qualquer falha: o
    `lru_cache` nao memoiza excecao, entao uma falha e' tentada de novo na proxima vez."""
    import requests

    resp = requests.get(f"{url}/status", timeout=TIMEOUT_STATUS_S)
    resp.raise_for_status()
    corpo = resp.json()
    modificado = corpo.get("tileset_last_modified")
    if isinstance(modificado, (int, float)) and math.isfinite(modificado) and modificado > 0:
        from datetime import UTC, datetime

        return datetime.fromtimestamp(float(modificado), UTC).isoformat(timespec="seconds")
    versao = corpo.get("version")
    if versao:
        return str(versao)
    raise ValueError("status sem tileset_last_modified nem version")


# url -> instante (monotonic) ate' o qual o status nao e' reconsultado depois de uma falha.
_STATUS_FALHOU_ATE: dict[str, float] = {}


def versao_rotas() -> str | None:
    """Carimbo da malha viaria em uso (data dos tiles; senao a versao do Valhalla).

    `None` quando o servico nao responde ao status -- a isocrona ainda pode sair, so' sem o
    carimbo. Uma falha fica lembrada por `_ESPERA_APOS_FALHA_STATUS_S` (o `lru_cache` nao
    memoiza excecao, e sem isso cada clique esperaria o timeout do status). NUNCA levanta.
    """
    url = url_rotas()
    if url is None:
        return None
    if time.monotonic() < _STATUS_FALHOU_ATE.get(url, 0.0):
        return None
    try:
        return _versao_cacheada(url, int(time.time() // _JANELA_VERSAO_S))
    except Exception as exc:  # noqa: BLE001 - carimbo e' opcional, nunca derruba a analise
        _LOG.warning("Status do servico de rotas indisponivel: %s", exc)
        _STATUS_FALHOU_ATE[url] = time.monotonic() + _ESPERA_APOS_FALHA_STATUS_S
        return None


def estado_rotas() -> dict[str, Any]:
    """Saude do servico de rotas para o painel de artefatos. NUNCA levanta.

    `configurado` = env setada; `responde` = o status respondeu; `versao` = carimbo.
    """
    url = url_rotas()
    if url is None:
        return {"configurado": False, "responde": None, "versao": None}
    versao = versao_rotas()
    return {"configurado": True, "responde": versao is not None, "versao": versao}


# --------------------------------------------------------------------------- #
# Isocrona                                                                     #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Isocrona:
    """Isocrona pronta para o motor.

    `geometria` em graus (x=lng, y=lat), Polygon ou MultiPolygon, possivelmente com buracos,
    e garantidamente contendo (`lat`, `lng`) -- a origem que o motor usa como centro da
    projecao local e "ponto". `area_km2` e' a EXATA (fonte do `fator_regua`); arredondar e'
    so' para exibicao.
    """

    lat: float
    lng: float
    minutos: int
    geometria: BaseGeometry
    area_km2: float
    diagonal_km: float
    n_vertices: int
    versao: str | None

    @property
    def fator_regua(self) -> float:
        return fator_regua_da_area(self.area_km2)

    @property
    def parametros(self) -> dict[str, Any]:
        """Carimbo do calculo (vai ao payload e ao PDF). Copia nova a cada leitura: o objeto
        mora num cache compartilhado entre requisicoes."""
        return {
            "motor": "valhalla",
            "perfil": "auto",
            "minutos": int(self.minutos),
            "trafego": False,
            "versao": self.versao,
        }


def _projecoes(lat: float, lng: float):
    """(graus -> metros, metros -> graus) na AEQD local centrada na origem.

    A MESMA projecao que `analisar_ponto_censitario_setores` usa para medir a area do
    recorte: o `fator_regua` daqui e a `area_km2_exata` do motor saem da mesma regua de
    metros. Import tardio: e' o que puxa pyproj.
    """
    from motor_expansao.dashboard.censo_point import (
        CRS_ORIGEM_CENSO,
        _local_metric_crs,
        _transformer,
    )

    crs = _local_metric_crs(lat, lng)
    return _transformer(CRS_ORIGEM_CENSO, crs), _transformer(crs, CRS_ORIGEM_CENSO)


def _so_poligonos(geom: BaseGeometry) -> BaseGeometry:
    """Partes de area de `geom` (descarta linhas/pontos que um `make_valid` pode gerar)."""
    if isinstance(geom, (Polygon, MultiPolygon)):
        return geom
    partes = [g for g in getattr(geom, "geoms", []) if isinstance(g, (Polygon, MultiPolygon))]
    return unary_union(partes) if partes else Polygon()


def _geometria_da_resposta(corpo: Any, minutos: int = MINUTOS_ISOCRONA) -> BaseGeometry:
    """FeatureCollection do Valhalla -> uma geometria de area (uniao das features)."""
    features = corpo.get("features") if isinstance(corpo, dict) else None
    if not isinstance(features, list):
        raise RotasIndisponiveis("resposta sem 'features'")
    partes: list[BaseGeometry] = []
    for feat in features:
        geom = (feat or {}).get("geometry") if isinstance(feat, dict) else None
        if not isinstance(geom, dict) or geom.get("type") not in ("Polygon", "MultiPolygon"):
            continue
        try:
            partes.append(shape(geom))
        except Exception as exc:  # noqa: BLE001 - coordenada malformada vinda do servico
            raise RotasIndisponiveis(f"geometria malformada: {exc}") from exc
    if not partes:
        raise AlcanceInvalido(MSG_SEM_VIA.format(minutos=minutos))
    unida = unary_union(partes)
    if not unida.is_valid:
        # So' para artefato NUMERICO do contorno (anel que se toca num vertice). Aqui nao
        # ha' "intencao do operador" a preservar, ao contrario do desenho a mao.
        unida = shapely.make_valid(unida)
    unida = _so_poligonos(unida)
    if unida.is_empty or unida.area <= 0:
        raise AlcanceInvalido(MSG_SEM_VIA.format(minutos=minutos))
    return unida


def _simplificar_ate_o_teto(geom_m: BaseGeometry) -> BaseGeometry:
    """Simplifica em METROS com `preserve_topology`; dobra a tolerancia ate' caber no teto."""
    tolerancia = TOLERANCIA_SIMPLIFICACAO_M
    simples = geom_m.simplify(tolerancia, preserve_topology=True)
    for _ in range(8):
        if shapely.get_num_coordinates(simples) <= MAX_VERTICES_ISOCRONA:
            break
        tolerancia *= 2.0
        simples = geom_m.simplify(tolerancia, preserve_topology=True)
    return _so_poligonos(simples)


def _construir_isocrona(lat: float, lng: float, minutos: int, url: str, versao: str | None):
    """A chamada ao Valhalla e todo o tratamento. Sem cache (ver `_isocrona_cacheada`)."""
    import requests

    corpo_req = {
        "locations": [{"lat": lat, "lon": lng, "search_cutoff": int(DIST_MAX_ORIGEM_M)}],
        "costing": "auto",
        "contours": [{"time": minutos}],
        "polygons": True,
        "denoise": 0.5,
        "generalize": 25,
    }
    try:
        resp = requests.post(f"{url}/isochrone", json=corpo_req, timeout=TIMEOUT_ISOCRONA_S)
    except requests.exceptions.RequestException as exc:
        raise RotasIndisponiveis(f"falha de conexao/timeout: {exc}") from exc
    if resp.status_code >= 500:
        raise RotasIndisponiveis(f"HTTP {resp.status_code}: {resp.text[:300]}")
    if resp.status_code == 400:
        # 400 do Valhalla = o pedido nao tem resposta (tipicamente "No suitable edges near
        # location", ponto longe de qualquer via). O servico esta' de pe'; o recorte e' que
        # nao existe -> 400, nao 503.
        _LOG.info("Isocrona recusada pelo servico (HTTP 400): %s", resp.text[:300])
        raise AlcanceInvalido(MSG_SEM_VIA.format(minutos=minutos))
    if resp.status_code >= 400:
        # Qualquer OUTRO 4xx (404/405 de URL errada, 401/403 de proxy, 429) e' defeito de
        # CONFIGURACAO ou de capacidade, nao do ponto: dizer "nenhuma rua por perto" a cada
        # clique esconderia um `MOTOR_ROTAS_URL` errado atras de um problema do lugar.
        raise RotasIndisponiveis(f"HTTP {resp.status_code}: {resp.text[:300]}")
    try:
        corpo = resp.json()
    except ValueError as exc:
        raise RotasIndisponiveis(f"resposta nao-JSON: {exc}") from exc

    geom_wgs = _geometria_da_resposta(corpo, minutos)
    para_m, para_graus = _projecoes(lat, lng)
    geom_m = _shp_transform(para_m.transform, geom_wgs)
    geom_m = _simplificar_ate_o_teto(geom_m)

    origem_m = Point(0.0, 0.0)  # a origem da AEQD local e' o proprio ponto
    if not geom_m.covers(origem_m):
        distancia = float(geom_m.distance(origem_m))
        if distancia > DIST_MAX_ORIGEM_M:
            # A area alcancada comeca longe do clique: os minutos partem de outro lugar.
            raise AlcanceInvalido(
                MSG_ORIGEM_FORA.format(dist=DIST_MAX_ORIGEM_M, minutos=minutos)
            )
        # Faixa do clique ao contorno: o recorte continua UMA area ligada ao ponto, e nao
        # o contorno com um disco solto ao lado.
        _, perto = nearest_points(origem_m, geom_m)
        ligacao = LineString([origem_m, perto]).buffer(BUFFER_ORIGEM_M)
        geom_m = _so_poligonos(unary_union([geom_m, ligacao]))
    if not geom_m.covers(origem_m):  # defensivo: a uniao acima sempre cobre
        raise AlcanceInvalido(MSG_ORIGEM_FORA.format(dist=DIST_MAX_ORIGEM_M, minutos=minutos))

    area_km2 = float(geom_m.area) / 1_000_000.0
    minx, miny, maxx, maxy = geom_m.bounds
    diagonal_km = math.hypot(maxx - minx, maxy - miny) / 1000.0
    if area_km2 > AREA_MAX_KM2:
        raise AlcanceInvalido(MSG_AREA_GRANDE.format(teto=AREA_MAX_KM2, minutos=minutos))
    if diagonal_km > DIAGONAL_MAX_KM:
        raise AlcanceInvalido(
            MSG_DIAGONAL_GRANDE.format(teto=DIAGONAL_MAX_KM, minutos=minutos)
        )

    geom_graus = _shp_transform(para_graus.transform, geom_m)
    return Isocrona(
        lat=lat,
        lng=lng,
        minutos=int(minutos),
        geometria=geom_graus,
        area_km2=area_km2,
        diagonal_km=diagonal_km,
        n_vertices=int(shapely.get_num_coordinates(geom_graus)),
        versao=versao,
    )


@lru_cache(maxsize=256)
def _isocrona_cacheada(
    lat: float, lng: float, minutos: int, url: str, versao: str | None
) -> Isocrona:
    # Excecoes NAO sao memoizadas pelo `lru_cache`: servico fora agora nao vira "fora para
    # sempre" neste processo. A chave inclui a URL e a versao dos tiles.
    return _construir_isocrona(lat, lng, minutos, url, versao)


def isocrona_carro(lat: float, lng: float, minutos: int = MINUTOS_ISOCRONA) -> Isocrona:
    """Area alcancavel em `minutos` de carro sem transito a partir de (lat, lng).

    Cache em memoria por ``(round(lat, 5), round(lng, 5), minutos)`` (~1 m): o MESMO ponto
    clicado de novo, na ficha e depois no PDF, nao paga outra chamada -- e o PDF analisa a
    mesma area que a tela mostrou. A conta roda na coordenada ARREDONDADA, entao o
    contorno nao depende de quem chamou primeiro; mas `Isocrona.lat/lng` devolvem a
    coordenada DO CHAMADOR. Devolver a arredondada movia o ponto ate' ~0,5 m: a tela grava
    a origem do payload, e voltar ao raio de 1 km relia o ponto ali, nao no clique -- perto
    de uma divisa de setor ou de hexagono, outra ficha.

    Levanta `RotasIndisponiveis` (sem env, conexao, timeout, 5xx, resposta ilegivel) ou
    `AlcanceInvalido` (sem via por perto, acima de 200 km2 ou de 40 km de diagonal).
    """
    url = url_rotas()
    if url is None:
        raise RotasIndisponiveis(f"env {ENV_ROTAS} vazia")
    minutos_i = int(minutos)
    if minutos_i <= 0:
        raise ValueError(f"minutos tem de ser positivo: {minutos!r}")
    iso = _isocrona_cacheada(
        round(float(lat), 5), round(float(lng), 5), minutos_i, url, versao_rotas()
    )
    lat_f, lng_f = float(lat), float(lng)
    if (lat_f, lng_f) == (iso.lat, iso.lng):
        return iso
    # O contorno ja' cobre a origem arredondada; o clique esta' a menos de 1 m dela. So' no
    # caso degenerado de a borda passar entre os dois a origem arredondada e' mantida -- o
    # motor exige a origem dentro do recorte.
    if not iso.geometria.covers(Point(lng_f, lat_f)):
        return iso
    return replace(iso, lat=lat_f, lng=lng_f)


def limpar_cache() -> None:
    """Esvazia os caches (testes; e depois de reconstruir os tiles sem reiniciar o web)."""
    _isocrona_cacheada.cache_clear()
    _versao_cacheada.cache_clear()
    _STATUS_FALHOU_ATE.clear()


# --------------------------------------------------------------------------- #
# Contorno para a tela                                                         #
# --------------------------------------------------------------------------- #
def _anel(coords) -> list[list[float]]:
    return [[round(float(x), 6), round(float(y), 6)] for x, y, *_ in coords]


def _poligono_geojson(p: Polygon) -> list[list[list[float]]]:
    return [_anel(p.exterior.coords), *(_anel(i.coords) for i in p.interiors)]


def contorno_geojson(geom: BaseGeometry) -> dict[str, Any]:
    """Polygon/MultiPolygon em GeoJSON (lng, lat; 6 casas, ~0,1 m), buracos inclusos.

    E' o contorno que a tela desenha. O formato de anel unico do desenho a mao
    (`geometria`) nao cabe uma isocrona com ilhas, por isso o GeoJSON completo.
    """
    if isinstance(geom, Polygon):
        return {"type": "Polygon", "coordinates": _poligono_geojson(geom)}
    if isinstance(geom, MultiPolygon):
        return {
            "type": "MultiPolygon",
            "coordinates": [_poligono_geojson(p) for p in geom.geoms],
        }
    raise ValueError(f"contorno so' de Polygon/MultiPolygon, recebido {geom.geom_type}")


__all__ = [
    "ALCANCES",
    "ALCANCE_CARRO_10MIN",
    "ALCANCE_CARRO_5MIN",
    "ALCANCE_RAIO_1KM",
    "ALCANCE_RAIO_2KM",
    "AREA_MAX_KM2",
    "DIAGONAL_MAX_KM",
    "DIST_MAX_ORIGEM_M",
    "ENV_ROTAS",
    "MINUTOS_DO_ALCANCE",
    "MINUTOS_ISOCRONA",
    "RAIO_DO_ALCANCE",
    "AlcanceInvalido",
    "Isocrona",
    "RotasIndisponiveis",
    "contorno_geojson",
    "estado_rotas",
    "fator_regua_da_area",
    "fator_regua_do_raio",
    "isocrona_carro",
    "limpar_cache",
    "rotas_configuradas",
    "url_rotas",
    "versao_rotas",
]
