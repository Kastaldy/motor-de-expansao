"""Constantes LOCAIS do modulo de Dimensionamento (BLK-DIM).

NAO mexer no `config.py` raiz do M1. Estes valores sao da camada paralela de
Dimensionamento e Viabilidade e foram aprovados no gate humano (2026-06-13,
decisoes D1-D7 do BLK-DIM-00).
"""

from __future__ import annotations

from pathlib import Path

# --- Growth API -------------------------------------------------------------
GROWTH_API_BASE_URL = "https://services.ultraacademia.com.br/growth_api_ultra"

# Rate limit documentado (doc Growth API v1.0.0 §6): 10 req / 5 min por IP -> HTTP 429.
RATE_LIMIT_REQS = 10
RATE_LIMIT_WINDOW_S = 300
# Em 429 o doc manda aguardar >= 30 s + backoff exponencial.
BACKOFF_MIN_S = 30
# Token expira em 1 h (§5.4) -> relogin em 401.
TOKEN_TTL_S = 3600

# --- Diretorios -------------------------------------------------------------
CACHE_DIR = Path("data/cache/growth_api")
STAGING_DIR = Path("data/staging")

# --- Anti-PII (LGPD §10.3) --------------------------------------------------
# Nenhuma destas colunas pode existir em disco. `assert_sem_pii` levanta antes de
# qualquer `to_parquet`. Comparacao case-insensitive.
PII_COLUNAS_PROIBIDAS = frozenset(
    {
        "nome",
        "cpf",
        "email",
        "celular",
        "data_nascimento",
        "cod_aluno",
        "nome_usuario",
        "usuario",
        "cod_usuario",
        "tel",
        "cel",
        "sexo",
        "situacao",
        "plano",
        "motivo",
        "cargo",
    }
)

# --- Parametros de consolidacao (decisoes D1/D3/D4/D6 do gate humano) -------
# D1: inicio da serie historica (janela mensal ate hoje).
DATA_INICIO_HISTORICO = "2022-04-01"
# D6: mediana dos ultimos N meses maduros para steady-state.
N_MESES_STEADY = 6
# D4: limiar de maturacao em meses (flag_madura = meses_desde_inauguracao >= MESES_MADURA).
MESES_MADURA = 8
# D3: raio do catchment censitario (km). Parametrizavel 1.0-2.0 sem tocar o helper.
RAIO_CATCHMENT_KM = 1.5

# --- Endpoint (decisao D7) --------------------------------------------------
# Ingerir SO `/historico-dash-view` (superset de `/historico-dash`).
ENDPOINT_HISTORICO_VIEW = "/historico-dash-view"
ENDPOINT_HISTORICO = "/historico-dash"
ENDPOINT_LOGIN = "/auth/login"
