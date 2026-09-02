"""Utilitario PURO de coordenada (Decisao 4 / BLK-API-03).

Parser de link do Google Maps -> ``(lat, lng)`` por manipulacao de string (sem
rede, sem tocar o motor) + validacao do bounding box do Brasil. Sem dependencia
do motor ou de bibliotecas geoespaciais — so `re`.
"""

from __future__ import annotations

import re

from motor_expansao.perfil import resolver_perfil

# Bounding box do pais da INSTANCIA, nao mais do Brasil cravado (Bloco A / DEC-047). No
# perfil brasileiro sao os mesmos quatro numeros de sempre — `data/perfis/BR/perfil.json`
# os transcreve e `tests/contracts/test_perfil_br_reproduz_as_constantes.py` trava a
# igualdade —, entao o comportamento brasileiro nao muda um decimal. No perfil argentino
# sao os da Argentina, e e por isso que Buenos Aires (-34,60) deixa de ser recusada ANTES
# de qualquer leitura de disco.
#
# Resolvido no IMPORT porque um processo serve UM pais so (DEC-047). Os NOMES continuam
# `BRASIL_*` e a funcao continua `validar_brasil`: renomear custa 3 call sites em
# `web/server/app.py` mais o `test_api_coord.py`, e a spec §2.1 adia isso para o Bloco B
# de proposito — nesta onda muda o VALOR, nao a superficie.
_PERFIL = resolver_perfil()
_BBOX = _PERFIL.bbox
_NOME_DO_PAIS = _PERFIL.nome
BRASIL_LAT_MIN, BRASIL_LAT_MAX = _BBOX.lat_min, _BBOX.lat_max
BRASIL_LNG_MIN, BRASIL_LNG_MAX = _BBOX.lng_min, _BBOX.lng_max


class CoordenadaInvalidaError(ValueError):
    """Coordenada nao parseavel ou fora do pais da instancia (-> HTTP 400)."""


class ForaDoPaisError(CoordenadaInvalidaError):
    """A coordenada FOI lida, mas cai fora do bbox do pais da instancia.

    Subclasse para que quem precisa distinguir os dois casos o faca pelo TIPO, e nao
    pelo texto da mensagem. `web/server/app.py` (`/api/resolver-ponto`) fazia
    `if "fora do Brasil" in str(exc)` — controle de fluxo preso a uma string voltada ao
    usuario. Bastou a mensagem virar "fora de Brasil" no Bloco A para o ramo parar de
    casar e o operador passar a ver "nao reconheci esse link" para uma coordenada
    perfeitamente lida. Herda de `CoordenadaInvalidaError` de proposito: todo `except`
    que ja existia continua pegando esta, entao nenhum chamador precisa mudar.
    """


# Ordem de tentativa: !3dLAT!4dLNG (pino exato do place) tem prioridade sobre
# @lat,lng (centro do viewport), depois query params e "lat,lng" cru.
# Os query params cobrem Google Maps E Apple Maps (iPhone): o app nativo de Mapas do
# iOS compartilha com `ll=`, `coordinate=` ou `daddr=`, nunca com `@lat,lng`.
_PADROES = (
    re.compile(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)"),
    re.compile(r"@(-?\d+\.\d+),(-?\d+\.\d+)"),
    # `ll`/`sll` (Apple e Google), `coordinate` (Apple Maps place), `daddr`/`saddr`
    # (rota do Apple Maps -- destino/origem), `q`/`query`/`center`/`destination` (Google).
    re.compile(
        r"[?&](?:q|query|ll|sll|center|destination|coordinate|daddr|saddr)="
        r"(-?\d+\.\d+),\s*(-?\d+\.\d+)"
    ),
    re.compile(r"^\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\s*$"),
    # ULTIMO RECURSO: QUALQUER parametro cujo valor seja um par "lat,lng".
    #
    # Existe para o parser nao depender de conhecermos o nome do parametro. A lista acima foi
    # montada a partir dos formatos que sabemos existir (Google e Apple), mas um app novo -- ou
    # uma versao futura do proprio Maps -- pode usar um nome que ninguem previu, e hoje esse
    # caso e' perda TOTAL do link. Como este padrao so e' tentado depois de todos os
    # especificos falharem, ele nunca rouba a precedencia do pino (`!3d!4d`) sobre o centro do
    # viewport (`@lat,lng`): quando algum especifico casa, este nem chega a rodar.
    #
    # Risco contido por `validar_brasil`: um par espurio (ex.: uma versao "1.0,2.0") cai fora
    # do bounding box e vira erro claro, nao um relatorio no lugar errado.
    re.compile(r"[?&][A-Za-z_][\w.-]*=(-?\d+\.\d+),\s*(-?\d+\.\d+)(?:&|$)"),
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
    """Valida que ``(lat, lng)`` esta no bounding box do PAIS DA INSTANCIA.

    Levanta `CoordenadaInvalidaError` quando fora. Nao confirma municipio — isso
    e responsabilidade do ponto-em-poligono no `service.py`.

    O nome ficou `validar_brasil` de proposito nesta onda (spec §2.1): renomear custa
    3 call sites em `web/server/app.py` e o `test_api_coord.py`, e nao muda uma virgula
    de comportamento. O Bloco B renomeia.
    """
    if not _BBOX.contem(lat, lng):
        # "fora de X" e nao "fora do X": funciona em pt-BR para Brasil, Argentina,
        # Colombia, Mexico, Peru e Paraguai. `f"fora do {nome}"` sairia "fora do
        # Argentina". Deliberado, escrito aqui para nao ser "consertado" depois.
        raise ForaDoPaisError(f"Coordenada fora de {_NOME_DO_PAIS}")
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
