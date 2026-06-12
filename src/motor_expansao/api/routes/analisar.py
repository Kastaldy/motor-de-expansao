"""Rota ``POST /analisar`` (BLK-API-03) — saida JSON.

Negociacao JSON/PDF: a saida PDF chega no BLK-API-04; aqui ``formato=pdf``
responde ``501`` temporariamente. Auth por token->consumidor em todas as rotas.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, Response

from motor_expansao.api.auth import resolver_consumidor
from motor_expansao.api.coord import CoordenadaInvalidaError, resolver_coordenada
from motor_expansao.api.errors import APIError
from motor_expansao.api.schemas import AnalisarRequest, AnalisarResponseJSON, ErrorResponse
from motor_expansao.api.service import analisar_ponto, gerar_pdf_ponto
from motor_expansao.api.settings import Settings, get_settings

router = APIRouter(tags=["analise"])

_ERR: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse},
    401: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    500: {"model": ErrorResponse},
}


@router.post(
    "/analisar",
    response_model=AnalisarResponseJSON,
    responses=_ERR,
    summary="Analisa um ponto (Relatorio Pontual Censitario 1.5 km)",
)
async def analisar(
    payload: AnalisarRequest,
    request: Request,
    formato: str = Query("json", description="Atalho de negociacao (json|pdf)."),
    consumidor: str = Depends(resolver_consumidor),
    settings: Settings = Depends(get_settings),
) -> Response:
    # 1. Resolver e validar a coordenada (Decisao 4) -> 400 se invalida.
    try:
        lat, lng = resolver_coordenada(payload.lat, payload.lng, payload.maps_url)
    except CoordenadaInvalidaError as exc:
        raise APIError(400, str(exc), "coordenada_invalida") from exc

    # 2. Negociacao de conteudo (Decisao 1): ?formato=pdf, body.formato=pdf
    #    ou header Accept: application/pdf -> PDF; senao JSON.
    aceita_pdf = "application/pdf" in request.headers.get("accept", "")
    fmt = "pdf" if (aceita_pdf or "pdf" in (formato, payload.formato)) else "json"

    if fmt == "pdf":
        pdf_bytes = gerar_pdf_ponto(lat, lng, consumidor, settings, rotulo=payload.rotulo)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": 'inline; filename="relatorio_pontual_censitario.pdf"'},
        )

    # 3. Estudo do ponto (READ-ONLY) + carimbo de versao.
    dados = analisar_ponto(lat, lng, consumidor, settings)
    return JSONResponse(content=AnalisarResponseJSON(**dados).model_dump())
