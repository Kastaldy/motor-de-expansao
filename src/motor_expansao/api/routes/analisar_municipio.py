"""Rotas do Relatorio Municipal (BLK-RELMUN).

- ``GET  /ufs``               -> UFs disponiveis (para o teclado do bot).
- ``GET  /municipios/{uf}``   -> municipios da UF (para validar o que o usuario digita).
- ``POST /analisar-municipio``-> PDF de 9 paginas do municipio.

READ-ONLY sobre o M1 (mesma premissa da rota /analisar). Auth por token->consumidor.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from motor_expansao.api.auth import resolver_consumidor
from motor_expansao.api.schemas import (
    AnalisarMunicipioRequest,
    ErrorResponse,
    MunicipiosResponse,
)
from motor_expansao.api.service import (
    gerar_pdf_municipio,
    listar_municipios,
    listar_ufs,
)
from motor_expansao.api.settings import Settings, get_settings

router = APIRouter(tags=["municipio"])

_ERR: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    500: {"model": ErrorResponse},
}


@router.get("/ufs", summary="UFs disponiveis no Relatorio Municipal")
async def ufs(
    consumidor: str = Depends(resolver_consumidor),
    settings: Settings = Depends(get_settings),
) -> dict[str, list[str]]:
    return {"ufs": listar_ufs(settings)}


@router.get(
    "/municipios/{uf}",
    response_model=MunicipiosResponse,
    responses=_ERR,
    summary="Municipios de uma UF",
)
async def municipios(
    uf: str,
    consumidor: str = Depends(resolver_consumidor),
    settings: Settings = Depends(get_settings),
) -> MunicipiosResponse:
    return MunicipiosResponse(uf=uf.upper(), municipios=listar_municipios(uf, settings))


@router.post(
    "/analisar-municipio",
    responses=_ERR,
    summary="Gera o Relatorio Municipal (PDF de 9 paginas)",
)
async def analisar_municipio(
    payload: AnalisarMunicipioRequest,
    consumidor: str = Depends(resolver_consumidor),
    settings: Settings = Depends(get_settings),
) -> Response:
    pdf_bytes = gerar_pdf_municipio(
        payload.uf, payload.municipio, consumidor, settings, solicitante=payload.solicitante
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="relatorio_municipal.pdf"'},
    )
