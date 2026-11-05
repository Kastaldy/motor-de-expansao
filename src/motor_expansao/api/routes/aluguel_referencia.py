"""Rota ``GET /aluguel-referencia`` — a régua de aluguel da DEC-080 no contrato público.

Por que existe (DEC-080, Emenda 1): a régua de aluguel por município × tipo de imóvel
(mediana do R$/m² dos anúncios da aba imobiliária) só existia no site, atrás do login. A
ponte do Forms gera os estudos pela API pública, e sem esta rota o estudo não consegue dizer
se o aluguel pedido está acima ou abaixo do mercado.

O que ela NÃO faz: não mexe no cenário de viabilidade. O `POST /analisar` segue exigindo o
aluguel e honrando o valor informado; esta rota só devolve a régua para quem quiser comparar.

Uma régua só: a consulta é `TabelaAluguel.consultar`, a MESMA que a rota do site chama
(`web/server/app.py`, `GET /api/aluguel-referencia`). A diferença é a entrada: o site manda
UF e município da ficha; aqui o consumidor manda o PONTO, e o município sai da malha
municipal (o mesmo `_carregar_malha` do `/analisar`) e do nome do censo.

READ-ONLY: lê o parquet do coletor e a malha; não toca M1, score nem artefato nenhum.
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from motor_expansao.api.auth import resolver_consumidor
from motor_expansao.api.coord import CoordenadaInvalidaError, validar_brasil
from motor_expansao.api.errors import APIError
from motor_expansao.api.schemas import AluguelReferenciaResponse, ErrorResponse
from motor_expansao.api.settings import Settings, get_settings
from motor_expansao.dimensionamento.aluguel_referencia import TabelaAluguel, carregar_tabela

router = APIRouter(tags=["analise"])

_ERR: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse},
    401: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
    500: {"model": ErrorResponse},
}


@router.get(
    "/aluguel-referencia",
    response_model=AluguelReferenciaResponse,
    responses=_ERR,
    summary="Aluguel de referencia por ponto e tipo de imovel (mercado anunciado)",
)
def aluguel_referencia(
    tipo: Literal["galpao", "comercial", "loja"] = Query(
        description=(
            "Tipo de imovel, valor bruto: galpao; comercial (laje corporativa: predio, "
            "conjunto, laje); loja (comercial: salao, ponto de rua)."
        ),
        examples=["galpao"],
    ),
    lat: float = Query(ge=-90, le=90, description="Latitude do ponto.", examples=[-22.9056]),
    lng: float = Query(ge=-180, le=180, description="Longitude do ponto.", examples=[-47.0608]),
    consumidor: str = Depends(resolver_consumidor),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    try:
        validar_brasil(lat, lng)
    except CoordenadaInvalidaError as exc:
        raise APIError(400, str(exc), "coordenada_invalida") from exc

    # Import tardio, como no site: o modulo do servico puxa shapely e a malha so' aqui.
    from motor_expansao.api.service import _carregar_malha

    resolvido = _carregar_malha(str(settings.ibge_dir)).resolver(lat, lng)
    if resolvido is None:
        # Mesmo status e codigo do `/analisar` para o mesmo ponto: o consumidor trata
        # "coordenada fora da malha" de um jeito so', qualquer que seja a rota.
        raise APIError(
            400,
            "Coordenada fora da malha municipal (mar aberto, fora do país ou a mais de 2 km"
            " de qualquer município).",
            "coordenada_invalida",
        )
    uf, cod_municipio = resolvido

    tabela = _tabela(str(settings.oportunidades_path)) if settings.oportunidades_path else None
    if tabela is None:
        # Sem a base nao ha regua, e devolver um numero qualquer seria pior que o erro: o
        # consumidor leria "sem regua" como "aluguel barato".
        raise APIError(
            503,
            "Base de imóveis indisponível nesta instância: sem a régua de aluguel.",
            "aluguel_referencia_indisponivel",
        )

    municipio = _nome_do_censo(settings.censo_geo_dir, uf, cod_municipio)
    ref = tabela.consultar(tipo, uf, municipio)
    if ref is None:
        raise APIError(404, "Sem referência de aluguel para esse tipo de imóvel.", "sem_referencia")
    return JSONResponse(content=AluguelReferenciaResponse.model_validate(ref.para_dict()).model_dump())


@lru_cache(maxsize=2)
def _tabela(caminho: str) -> TabelaAluguel | None:
    """Regua do parquet do coletor, cacheada por processo como no site (o arquivo muda com
    restart). `None` sem o arquivo ou com o arquivo ilegivel."""
    try:
        return carregar_tabela(Path(caminho))
    except Exception as erro:  # noqa: BLE001 -- sem regua, a rota responde 503
        print(f"[aluguel-referencia] base ilegível ({erro})", file=sys.stderr)
        return None


def _nome_do_censo(censo_geo_dir: Path, uf: str, cod_municipio: str) -> str | None:
    """`nome_municipio` da particao censitaria do municipio -- UMA coluna de UM arquivo.

    A regua casa o municipio pelo nome normalizado (sem acento, maiusculo), porque a base do
    coletor nao traz codigo. Sem nome, `consultar` cai para a UF -- nunca para outra cidade.
    """
    import pyarrow.parquet as pq

    pasta = Path(censo_geo_dir) / f"uf={uf.upper()}" / f"cod_municipio={cod_municipio}"
    for arq in sorted(pasta.glob("*.parquet")) if pasta.is_dir() else []:
        try:
            arquivo = pq.ParquetFile(arq)
            if "nome_municipio" not in arquivo.schema_arrow.names:
                return None
            valores = arquivo.read(columns=["nome_municipio"]).column(0).drop_null()
        except Exception:  # noqa: BLE001 -- particao ilegivel = sem nome, nunca 500
            return None
        if len(valores):
            return str(valores[0])
    return None
