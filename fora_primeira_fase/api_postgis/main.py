"""
api/main.py — Ponto de entrada da API FastAPI
"""

import sentry_sdk
import structlog
from api.config import settings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# --- Sentry ---
if settings.SENTRY_DSN:
    sentry_sdk.init(dsn=settings.SENTRY_DSN, environment=settings.ENVIRONMENT)

log = structlog.get_logger()

app = FastAPI(
    title="Motor de Expansão — Ultra Academia",
    description="API de inteligência territorial para expansão ativa",
    version="0.1.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.ENVIRONMENT == "development" else ["https://ultra.com.br"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "environment": settings.ENVIRONMENT}


# Importar rotas (descomentar à medida que os módulos forem criados)
# from api.routes import hexagonos, concorrentes, imoveis, oportunidades, pipeline
# app.include_router(hexagonos.router, prefix="/api/v1/hexagonos", tags=["Hexágonos"])
# app.include_router(concorrentes.router, prefix="/api/v1/concorrentes", tags=["Concorrentes"])
# app.include_router(imoveis.router, prefix="/api/v1/imoveis", tags=["Imóveis"])
# app.include_router(oportunidades.router, prefix="/api/v1/oportunidades", tags=["Oportunidades"])
# app.include_router(pipeline.router, prefix="/api/v1/pipeline", tags=["Pipeline"])


@app.on_event("startup")
async def startup():
    log.info("motor_expansao_api_started", environment=settings.ENVIRONMENT)
