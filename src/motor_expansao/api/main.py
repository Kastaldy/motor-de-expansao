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

import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from motor_expansao.api import __version__
from motor_expansao.api.errors import APIError, api_error_handler, unexpected_error_handler
from motor_expansao.api.settings import get_settings

_log = logging.getLogger("motor_expansao.api")


def _garantir_log_handler() -> None:
    """Anexa um StreamHandler ao logger da API uma vez (idempotente).

    Garante que os logs de acesso/erro aparecam mesmo rodando standalone
    (`uvicorn motor_expansao.api.main:app`), sem depender de config externa.
    `propagate=False` evita linha duplicada quando o root ja tem handler (uvicorn).
    """
    if _log.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    _log.addHandler(handler)
    _log.setLevel(logging.INFO)
    _log.propagate = False


# Segredos default do settings.py — inertes em dev/teste, PROIBIDOS em producao.
_DEFAULTS_INSEGUROS = frozenset({"dev-token", "dev-local", "trocar-esta-senha", "changeme"})


def _garantir_producao_sem_defaults(settings) -> None:  # type: ignore[no-untyped-def]
    """Fail-closed (BLK-SEC-05): em producao, recusa subir com TOKEN de auth default.

    A API GeoEspacial e internet-facing (api.ultra-expansao.tech, so Bearer); um
    `API_TOKENS` default (ex.: 'dev-token') daria acesso total. Fora de producao
    (environment != 'production') os defaults seguem valendo — nao atrapalha dev/teste.

    So checa `tokens` (o que a API usa para AUTENTICAR consumidores). `api_call_token`
    (token que o BOT usa p/ chamar a API) e `bot_senha` (senha do BOT) sao config do
    servico `telegram-bot`; o compose NAO os passa ao servico `api`, entao no processo
    da API ficam no default de forma INOFENSIVA (a API nao os usa) — inclui-los aqui
    fazia a API abortar o boot em producao por falso-positivo.
    """
    if settings.environment != "production":
        return
    if any(token in _DEFAULTS_INSEGUROS for token in settings.tokens):
        raise RuntimeError(
            "API em producao com token default inseguro em API_TOKENS (ex.: 'dev-token'). "
            "Defina tokens fortes no .env (ver .env.example)."
        )


# ── Rate-limit da API publica (BLK-SEC-05) ─────────────────────────────────────
# Teto por TOKEN (ou IP, se anonimo) numa janela fixa, em memoria (1 worker uvicorn).
# Complementa o `--limit-concurrency` do compose: aquele limita CONCORRENCIA; este
# limita TAXA — barra um flood sustentado de baixa concorrencia contra o gerador de
# PDF. Generoso p/ nao atrapalhar o bot/parceiro (uso esporadico).
_RATE_LIMIT_MAX = 120           # requisicoes por janela
_RATE_LIMIT_JANELA_S = 60.0     # 1 minuto
_rate_state: dict[str, tuple[float, int]] = {}


def _rate_limit_ok(chave: str) -> bool:
    """Fixed-window por `chave`. True = dentro do teto; False = estourou a janela."""
    agora = time.monotonic()
    # Limpeza defensiva contra crescimento por muitos IPs distintos.
    if len(_rate_state) > 10000:
        for k in [k for k, (ini, _) in _rate_state.items() if agora - ini >= _RATE_LIMIT_JANELA_S]:
            _rate_state.pop(k, None)
    inicio, cont = _rate_state.get(chave, (agora, 0))
    if agora - inicio >= _RATE_LIMIT_JANELA_S:
        inicio, cont = agora, 0  # nova janela
    cont += 1
    _rate_state[chave] = (inicio, cont)
    return cont <= _RATE_LIMIT_MAX


def create_app() -> FastAPI:
    """Factory do app — facilita testes e overrides de settings."""
    settings = get_settings()
    _garantir_producao_sem_defaults(settings)
    _garantir_log_handler()

    app = FastAPI(
        title="API GeoEspacial — Motor de Expansao Ultra Academia",
        description=(
            "API complementar on-demand para o Relatorio Pontual Censitario "
            "1.0 km. READ-ONLY sobre o M1; importa, nao edita, a camada censo_*."
        ),
        version=__version__,
        # Docs interativa so fora de producao. O schema OpenAPI tambem fecha em producao
        # (pentest 2026-08-19): com so' docs_url/redoc_url off, /openapi.json continuava
        # 200 anonimo e entregava toda a superficie da API — o /docs desligado sem o
        # /openapi.json fechado e' meia trava.
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url="/redoc" if settings.environment != "production" else None,
        openapi_url="/openapi.json" if settings.environment != "production" else None,
    )

    # allow_credentials=False (BLK-SEC-05): a auth desta API e por Bearer token, nao por
    # cookie de sessao. Com credentials=True + allow_origins=["*"], o Starlette REFLETE
    # qualquer Origin com Access-Control-Allow-Credentials: true (misconfig classica).
    # Como nao ha cookie a proteger, desligar credentials mantem o CORS seguro (com "*"
    # o navegador recebe Allow-Origin: * e NAO reflete origem) sem afetar consumidores
    # server-to-server (bot, parceiro), que nem passam por CORS.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Starlette tipa o handler como Callable[[Request, Exception], ...]; o nosso e
    # preciso (APIError). Limitacao conhecida do stub -> ignore localizado.
    app.add_exception_handler(APIError, api_error_handler)  # type: ignore[arg-type]
    # Catch-all: garante o corpo {detail, codigo: "erro_interno"} no 500 (contrato §9).
    app.add_exception_handler(Exception, unexpected_error_handler)

    _rotas_livres_rl = {"/health", f"{settings.api_prefix}/health"}

    @app.middleware("http")
    async def _rate_limit(request: Request, call_next):
        """Barra o excedente (429) por token/IP antes do trabalho pesado (BLK-SEC-05)."""
        if request.url.path not in _rotas_livres_rl:
            auth = request.headers.get("Authorization", "")
            token = auth[7:].strip() if auth[:7].lower() == "bearer " else ""
            xff = request.headers.get("X-Forwarded-For", "")
            ip = xff.split(",")[0].strip() if xff else (request.client.host if request.client else "")
            if not _rate_limit_ok(token or ip or "anon"):
                return JSONResponse(
                    {"detail": "Muitas requisicoes. Tente novamente em instantes.", "codigo": "rate_limited"},
                    status_code=429,
                )
        return await call_next(request)

    @app.middleware("http")
    async def _registrar_acesso(request: Request, call_next):
        """Uma linha de log por request: metodo, rota, status e duracao."""
        inicio = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # Excecao nao tratada: o traceback e logado pelo unexpected_error_handler
            # (no ServerErrorMiddleware, acima deste middleware). Aqui so a linha de acesso.
            dur_ms = (time.perf_counter() - inicio) * 1000
            _log.warning("%s %s -> 500 (%.0f ms)", request.method, request.url.path, dur_ms)
            raise
        dur_ms = (time.perf_counter() - inicio) * 1000
        _log.info(
            "%s %s -> %d (%.0f ms)",
            request.method,
            request.url.path,
            response.status_code,
            dur_ms,
        )
        return response

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

    # BLK-RELMUN: GET /ufs, GET /municipios/{uf}, POST /analisar-municipio
    from motor_expansao.api.routes import analisar_municipio

    app.include_router(analisar_municipio.router, prefix=settings.api_prefix)

    return app


app = create_app()
