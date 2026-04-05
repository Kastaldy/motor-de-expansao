"""
api/config.py — Configurações centralizadas.

Usa pydantic-settings quando disponível. Em ambientes mínimos de teste, cai para um
loader simples baseado em variáveis de ambiente para manter o projeto importável.
"""

from __future__ import annotations

import os
from functools import lru_cache

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ModuleNotFoundError:  # pragma: no cover - fallback para ambientes sem a dependencia
    BaseSettings = None
    SettingsConfigDict = dict


def _coerce_env_value(raw: str, default):
    if isinstance(default, bool):
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(default, int) and not isinstance(default, bool):
        return int(raw)
    if isinstance(default, float):
        return float(raw)
    return raw


if BaseSettings is not None:

    class Settings(BaseSettings):
        model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

        # Banco
        DATABASE_URL: str = "postgresql+asyncpg://ultra:ultra123@localhost:5432/motor_expansao"
        DATABASE_URL_SYNC: str = "postgresql+psycopg2://ultra:ultra123@localhost:5432/motor_expansao"

        # App
        ENVIRONMENT: str = "development"
        SECRET_KEY: str = "dev-secret-key-change-in-production"
        ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

        # APIs externas
        GOOGLE_MAPS_API_KEY: str = ""
        GEOFUSION_API_KEY: str = ""
        MAPBOX_TOKEN: str = ""

        # Monitoramento
        SENTRY_DSN: str = ""

        # Scraping
        SCRAPER_DELAY_MIN: float = 2.0
        SCRAPER_DELAY_MAX: float = 5.0
        SCRAPER_MAX_RETRIES: int = 3
        SCRAPER_TIMEOUT: int = 30

        # Geoespacial
        H3_RESOLUTION: int = 7
        DIST_MIN_ULTRA_KM: float = 1.0
        RENDA_MIN: float = 4500.0

        # Fase 1 / M1 nacional
        M1_SCORE_OFICIAL: str = "score_priorizacao"
        M1_PRIORIZACAO_TOP_PCT_POR_UF: float = 0.20
        M1_OSM_ENABLED: bool = False
        M1_SETOR_CENSITARIO_OBRIGATORIO: bool = False

        # Alertas
        SLACK_WEBHOOK_URL: str = ""
        ALERT_EMAIL: str = ""

        # Constantes Ultra Academia
        AREA_MIN_M2: float = 1200.0
        AREA_IDEAL_MIN_M2: float = 1500.0
        AREA_IDEAL_MAX_M2: float = 2000.0
        PE_DIREITO_MIN: float = 3.5

        # Paleta de cores Ultra Academia
        @property
        def CORES(self) -> dict[str, str]:
            return {
                "purple": "#6B21A8",
                "cyan":   "#06B6D4",
                "red":    "#E63946",
                "green":  "#2A9D8F",
                "orange": "#F4A261",
                "blue":   "#457B9D",
                "pink":   "#EC4899",
                "white":  "#FFFFFF",
                "teal":   "#0D9488",
            }

else:

    class Settings:
        # Banco
        DATABASE_URL = "postgresql+asyncpg://ultra:ultra123@localhost:5432/motor_expansao"
        DATABASE_URL_SYNC = "postgresql+psycopg2://ultra:ultra123@localhost:5432/motor_expansao"

        # App
        ENVIRONMENT = "development"
        SECRET_KEY = "dev-secret-key-change-in-production"
        ACCESS_TOKEN_EXPIRE_MINUTES = 60

        # APIs externas
        GOOGLE_MAPS_API_KEY = ""
        GEOFUSION_API_KEY = ""
        MAPBOX_TOKEN = ""

        # Monitoramento
        SENTRY_DSN = ""

        # Scraping
        SCRAPER_DELAY_MIN = 2.0
        SCRAPER_DELAY_MAX = 5.0
        SCRAPER_MAX_RETRIES = 3
        SCRAPER_TIMEOUT = 30

        # Geoespacial
        H3_RESOLUTION = 7
        DIST_MIN_ULTRA_KM = 1.0
        RENDA_MIN = 4500.0

        # Fase 1 / M1 nacional
        M1_SCORE_OFICIAL = "score_priorizacao"
        M1_PRIORIZACAO_TOP_PCT_POR_UF = 0.20
        M1_OSM_ENABLED = False
        M1_SETOR_CENSITARIO_OBRIGATORIO = False

        # Alertas
        SLACK_WEBHOOK_URL = ""
        ALERT_EMAIL = ""

        # Constantes Ultra Academia
        AREA_MIN_M2 = 1200.0
        AREA_IDEAL_MIN_M2 = 1500.0
        AREA_IDEAL_MAX_M2 = 2000.0
        PE_DIREITO_MIN = 3.5

        def __init__(self) -> None:
            for name, default in self.__class__.__dict__.items():
                if not name.isupper():
                    continue
                raw = os.getenv(name)
                setattr(self, name, _coerce_env_value(raw, default) if raw is not None else default)

        @property
        def CORES(self) -> dict[str, str]:
            return {
                "purple": "#6B21A8",
                "cyan":   "#06B6D4",
                "red":    "#E63946",
                "green":  "#2A9D8F",
                "orange": "#F4A261",
                "blue":   "#457B9D",
                "pink":   "#EC4899",
                "white":  "#FFFFFF",
                "teal":   "#0D9488",
            }


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
