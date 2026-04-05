"""
api/config.py — Configurações centralizadas via pydantic-settings
Lê variáveis do .env automaticamente.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    DIST_MIN_ULTRA_KM: float = 2.0
    RENDA_MIN: float = 3000.0

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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
