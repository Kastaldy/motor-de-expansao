"""App FastAPI da API GeoEspacial — BLK-API-02.

MVP minimo deste bloco: `GET /health` (liveness, sem auth) + esqueleto pronto
para montar `POST /analisar` (BLK-API-03) sob o prefixo `/api/v1`.

Reaproveita do scaffold legado (`fora_primeira_fase/api_postgis/main.py`) apenas
o `FastAPI(...)`, o `CORSMiddleware` e o `/health`. Descarta Sentry, structlog,
routers PostGIS e `@app.on_event("startup")` (deprecado) — §12 do contrato.

Rodar localmente:
    uvicorn motor_expansao.api.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from motor_expansao.api import __version__
from motor_expansao.api.errors import APIError, api_error_handler
from motor_expansao.api.settings import get_settings


def create_app() -> FastAPI:
    """Factory do app — facilita testes e overrides de settings."""
    settings = get_settings()

    app = FastAPI(
        title="API GeoEspacial — Motor de Expansao Ultra Academia",
        description=(
            "API complementar on-demand para o Relatorio Pontual Censitario "
            "1.5 km. READ-ONLY sobre o M1; importa, nao edita, a camada censo_*."
        ),
        version=__version__,
        # Docs interativa so fora de producao.
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url="/redoc" if settings.environment != "production" else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Starlette tipa o handler como Callable[[Request, Exception], ...]; o nosso e
    # preciso (APIError). Limitacao conhecida do stub -> ignore localizado.
    app.add_exception_handler(APIError, api_error_handler)  # type: ignore[arg-type]

    @app.get("/health", tags=["infra"], summary="Liveness do servico")
    async def health() -> dict[str, str]:
        return {"status": "ok", "environment": settings.environment}

    # Espelha o /health sob o prefixo de versao (contrato §10).
    @app.get(f"{settings.api_prefix}/health", tags=["infra"], include_in_schema=False)
    async def health_v1() -> dict[str, str]:
        return {"status": "ok", "environment": settings.environment}

    # BLK-API-03: POST /api/v1/analisar
    from motor_expansao.api.routes import analisar

    app.include_router(analisar.router, prefix=settings.api_prefix)

    return app


app = create_app()
