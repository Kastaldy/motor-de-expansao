"""Modelo de erro padrao da API (contrato §9): ``{detail, codigo}``.

FastAPI por padrao serializa erros como ``{"detail": ...}``. Aqui definimos uma
excecao propria (`APIError`) e um handler que devolve o corpo plano
``{"detail": "<mensagem>", "codigo": "<slug>"}`` exigido pelo contrato.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


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
