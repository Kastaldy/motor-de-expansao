"""Validacao do poligono DESENHADO no mapa -- "Analisar geometria", fase 1 (DEC-071, PROPOSTA).

O operador desenha um poligono a mao no Mapa Territorial e ele SUBSTITUI o raio de 1,0 km
na analise de ponto: censo (setor a setor), concorrentes e mercado passam a ser lidos DENTRO
dele. Este modulo e' a porta de entrada: recebe o GeoJSON cru do corpo da requisicao e
devolve o poligono pronto para o motor, ou levanta `GeometriaDesenhadaInvalida` com a
mensagem em portugues que a rota devolve como 400.

OS LIMITES (decisao do dono, 2026-10-14) e o porque de cada um:

- AREA entre 0,1 e 200 km2. O piso tira o clique duplo acidental (um "poligono" de tres
  vertices colados) e o recorte menor que um quarteirao, em que a intersecao setor a setor
  vira ruido. O teto e' de CUSTO: a intersecao e' um laco Python por setor, e cada
  municipio alcancado e' uma particao a mais lida do disco. Era 25 km2 (~8x o raio de
  1 km) e foi a 200 km2 a pedido do Vinicius (2026-10-16), para caber uma regiao inteira
  de cidade (varios bairros) -- o custo foi medido antes de subir (ver DEC-071).
- ATE 50 vertices. Desenho a mao nao precisa de mais, e o teto fecha a porta para um
  corpo de requisicao arbitrariamente grande.
- SEM autointersecao. Um "oito" nao tem area bem definida (o shapely o declara invalido e
  a intersecao com setor daria lixo), e consertar em silencio (`make_valid`) analisaria
  uma area que o operador nao desenhou.
- SEM buraco. A fase 1 desenha so' o contorno externo; aceitar aneis internos seria
  contrato que a tela nao tem como produzir.
- TODO vertice no pais. Quem decide o que e' "no pais" e' o chamador (`validar_coordenada`),
  pela mesma regua do `/api/ponto` -- este modulo nao conhece o perfil do deploy (DEC-047).

O PONTO DE REFERENCIA e' o `representative_point`, e NAO o centroide: num poligono concavo
(um "L", um "U") o centroide pode cair FORA da area, e ele vira a origem da projecao local,
o "setor do ponto" e o municipio que resolve a particao. O `representative_point` e'
garantidamente interno.

Funcao pura: nao le disco, nao muta entrada, nao toca o M1.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

from motor_expansao.dashboard.censo_point import (
    CRS_ORIGEM_CENSO,
    _local_metric_crs,
    _project_geometry,
    _transformer,
)

AREA_MIN_KM2 = 0.1
AREA_MAX_KM2 = 200.0
MAX_VERTICES = 50
MIN_VERTICES = 3


class GeometriaDesenhadaInvalida(ValueError):
    """O poligono nao serve para a analise. A mensagem vai ao usuario, em portugues."""


@dataclass(frozen=True)
class GeometriaDesenhada:
    """O poligono validado, pronto para o motor."""

    poligono: BaseGeometry
    """Em graus, convencao GeoJSON (x=lng, y=lat)."""
    lat: float
    """Latitude do `representative_point` -- o ponto de referencia da analise."""
    lng: float
    area_km2: float
    n_vertices: int
    coordenadas: list[list[list[float]]]
    """`coordinates` do Polygon GeoJSON normalizado: um anel, fechado, em [lng, lat]."""


def _km2(valor: float) -> str:
    """Area com virgula decimal ("0,05"), sem depender do locale do servidor."""
    casas = 2 if valor < 10 else 1
    return f"{valor:.{casas}f}".replace(".", ",")


def _limite(valor: float) -> str:
    return f"{valor:g}".replace(".", ",")


def _anel_da_entrada(geojson: Any) -> list[Any]:
    """O anel externo do Polygon GeoJSON (aceita tambem um Feature que o embrulhe)."""
    if isinstance(geojson, dict) and geojson.get("type") == "Feature":
        geojson = geojson.get("geometry")
    if not isinstance(geojson, dict) or geojson.get("type") != "Polygon":
        raise GeometriaDesenhadaInvalida(
            "A geometria precisa ser um polígono GeoJSON (type \"Polygon\")."
        )
    aneis = geojson.get("coordinates")
    if not isinstance(aneis, list) or not aneis or not isinstance(aneis[0], list):
        raise GeometriaDesenhadaInvalida("O polígono veio sem coordenadas.")
    if len(aneis) > 1:
        raise GeometriaDesenhadaInvalida(
            "O polígono não pode ter buracos: desenhe só o contorno externo da área."
        )
    return aneis[0]


def _vertices(anel: list[Any]) -> list[tuple[float, float]]:
    """Vertices (lng, lat) DISTINTOS, sem o fechamento e sem repeticao consecutiva."""
    pontos: list[tuple[float, float]] = []
    for i, pos in enumerate(anel, start=1):
        if not isinstance(pos, (list, tuple)) or len(pos) < 2:
            raise GeometriaDesenhadaInvalida(f"Coordenada inválida no vértice {i}.")
        try:
            lng, lat = float(pos[0]), float(pos[1])
        except (TypeError, ValueError):
            raise GeometriaDesenhadaInvalida(f"Coordenada inválida no vértice {i}.") from None
        if not (math.isfinite(lng) and math.isfinite(lat)):
            raise GeometriaDesenhadaInvalida(f"Coordenada inválida no vértice {i}.")
        # Clique duplo no mesmo lugar deixa o vertice repetido: nao e' vertice novo, e
        # conta-lo faria um triangulo de 3 cliques parecer um poligono de 4 lados.
        if not pontos or pontos[-1] != (lng, lat):
            pontos.append((lng, lat))
    # O anel GeoJSON repete o 1o vertice no fim. Aceita-se tambem o anel aberto (a tela
    # manda fechado, mas um cliente de API pode nao saber da regra) -- o que importa e'
    # nao contar o fechamento como vertice.
    if len(pontos) > 1 and pontos[0] == pontos[-1]:
        pontos.pop()
    return pontos


def validar_geometria_desenhada(
    geojson: Any,
    *,
    validar_coordenada: Callable[[float, float], None] | None = None,
) -> GeometriaDesenhada:
    """Valida o GeoJSON do poligono desenhado e devolve o que o motor precisa.

    `validar_coordenada(lat, lng)` levanta (qualquer excecao, com mensagem ao usuario)
    quando o vertice esta fora do pais -- a rota passa a mesma regua do `/api/ponto`.
    Levanta `GeometriaDesenhadaInvalida` com a mensagem em portugues em qualquer recusa.
    """
    vertices = _vertices(_anel_da_entrada(geojson))
    n = len(vertices)
    if n < MIN_VERTICES:
        raise GeometriaDesenhadaInvalida(
            f"O polígono precisa de pelo menos {MIN_VERTICES} vértices distintos."
        )
    if n > MAX_VERTICES:
        raise GeometriaDesenhadaInvalida(
            f"O polígono tem {n} vértices; o máximo é {MAX_VERTICES}."
        )
    if validar_coordenada is not None:
        for i, (lng, lat) in enumerate(vertices, start=1):
            try:
                validar_coordenada(lat, lng)
            except Exception as exc:  # noqa: BLE001 -- a regua e' do chamador
                raise GeometriaDesenhadaInvalida(f"Vértice {i} fora da área atendida: {exc}") from exc

    poligono = Polygon(vertices)
    # Pelo FECHO convexo, e nao pela area do proprio anel: um "oito" simetrico tem area
    # assinada ZERO (os dois lobulos se cancelam) e seria anunciado como "alinhado" --
    # o motivo errado para quem desenhou arestas que se cruzam.
    if poligono.convex_hull.area <= 0:
        raise GeometriaDesenhadaInvalida(
            "O polígono não tem área: os vértices estão alinhados."
        )
    if not poligono.is_valid:
        raise GeometriaDesenhadaInvalida(
            "O polígono cruza a si mesmo. Redesenhe a área sem que as arestas se cruzem."
        )

    referencia = poligono.representative_point()
    lat, lng = float(referencia.y), float(referencia.x)
    # Area na MESMA projecao local (AEQD no ponto de referencia) que o motor censitario usa
    # para a intersecao: o limite aceito aqui e a area que a analise reporta saem da mesma
    # regua de metros, e nunca divergem na borda dos 0,1 / 200 km2.
    crs = _local_metric_crs(lat, lng)
    area_km2 = float(
        _project_geometry(poligono, _transformer(CRS_ORIGEM_CENSO, crs)).area
    ) / 1_000_000.0
    if area_km2 < AREA_MIN_KM2:
        raise GeometriaDesenhadaInvalida(
            f"A área desenhada tem {_km2(area_km2)} km²; o mínimo é {_limite(AREA_MIN_KM2)} km²."
        )
    if area_km2 > AREA_MAX_KM2:
        raise GeometriaDesenhadaInvalida(
            f"A área desenhada tem {_km2(area_km2)} km²; o máximo é {_limite(AREA_MAX_KM2)} km²."
        )

    anel = [[lng_v, lat_v] for lng_v, lat_v in vertices]
    anel.append(list(anel[0]))
    return GeometriaDesenhada(
        poligono=poligono,
        lat=lat,
        lng=lng,
        area_km2=area_km2,
        n_vertices=n,
        coordenadas=[anel],
    )
