"""Modelo de erro padrao da API (contrato §9): ``{detail, codigo}``.

FastAPI por padrao serializa erros como ``{"detail": ...}``. Aqui definimos uma
excecao propria (`APIError`) e um handler que devolve o corpo plano
``{"detail": "<mensagem>", "codigo": "<slug>"}`` exigido pelo contrato.
"""

from __future__ import annotations

import logging

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("motor_expansao.api")


class APIError(Exception):
    """Erro de dominio da API com mensagem e slug de codigo (contrato §9)."""

    def __init__(self, status_code: int, detail: str, codigo: str) -> None:
        self.status_code = status_code
        self.detail = detail
        self.codigo = codigo
        super().__init__(detail)


async def api_error_handler(_: Request, exc: APIError) -> JSONResponse:
    """Serializa `APIError` no formato padrao ``{detail, codigo}``."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "codigo": exc.codigo},
    )


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Captura qualquer excecao nao tratada e devolve o `500` padrao do contrato (§9).

    Sem este handler, uma falha inesperada (pandas/pyproj/render do PDF) vazaria o
    corpo default do FastAPI (``{"detail":"Internal Server Error"}``, SEM `codigo`),
    quebrando o modelo de erro ``{detail, codigo}``. Aqui devolvemos a mensagem
    generica do contrato e o slug `erro_interno`, sem expor detalhes internos.

    Observacao: `APIError` tem handler proprio (mais especifico) e `RequestValidationError`
    segue com o `422` default do FastAPI — este handler so pega o que sobra.
    """
    # Traceback no log do servidor: sem isto, a falha some (o cliente recebe o 500,
    # mas voce nao consegue investigar). `exc_info=exc` grava o stack completo.
    logger.error(
        "Excecao nao tratada em %s %s",
        request.method,
        request.url.path,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Erro interno ao gerar o estudo", "codigo": "erro_interno"},
    )
