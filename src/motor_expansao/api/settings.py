"""Configuracoes da API GeoEspacial (BLK-API-02).

`pydantic-settings` com prefixo de env `API_` para nao colidir com o `.env`
legado do projeto. Define ambiente, prefixo de versao `/api/v1`, os diretorios
de dados (READ-ONLY) e o mapa estatico `token -> consumidor` (Decisao 2).

Sem IdP no MVP: a lista de tokens e estatica e evoluivel para Authelia/JWT
depois. Nenhum parametro canonico do M1 e definido aqui.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# .../src/motor_expansao/api/settings.py -> parents[3] = raiz do repo
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DATA_DIR = _REPO_ROOT / "data"


class Settings(BaseSettings):
    """Configuracao da API. Sobrescrevivel por env (prefixo `API_`) ou `.env`."""

    model_config = SettingsConfigDict(
        env_prefix="API_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    api_prefix: str = "/api/v1"

    # Diretorios de dados — READ-ONLY. Defaults relativos a raiz do repo.
    # `censo_geo_dir` e o base_dir de `read_censo_geo_partition`.
    censo_geo_dir: Path = _DATA_DIR / "outputs" / "setores_censitarios_2022_geo"
    ibge_dir: Path = _DATA_DIR / "ibge"
    ultra_dir: Path = _DATA_DIR / "ultra"  # assets de branding do PDF (opcional)
    # Logos das redes concorrentes (logo_<rede>.png) para os pins do mapa de Concorrentes.
    # None = sem logos (fallback de sigla). Em produção VPS definir via env:
    # API_COMPETITORS_LOGOS_DIR=/app/concorrentes
    competitors_logos_dir: Path | None = None
    # Camada de mercado/SAM + concorrentes + unidades Ultra (opcional; enriquece o PDF).
    staging_dir: Path = _DATA_DIR / "staging"

    # CORS. Em producao, restringir via env API_CORS_ORIGINS.
    cors_origins: list[str] = ["*"]

    # Mapa estatico token -> consumidor (Decisao 2). Rastreio do solicitante.
    # Em producao defina via env: API_TOKENS='{"tok-real":"bot-telegram"}'.
    tokens: dict[str, str] = Field(default_factory=lambda: {"dev-token": "dev-local"})

    # --- Bot Telegram (BLK-API-07) ---
    # Token do @BotFather. NUNCA commitar; definir via env API_TELEGRAM_TOKEN ou .env.
    telegram_token: str = ""
    # Base da API que o bot consome (desacoplado, via HTTP).
    api_base_url: str = "http://127.0.0.1:8077"
    # Token que o bot usa para se autenticar na propria API (deve existir em `tokens`).
    api_call_token: str = "dev-token"
    # Senha compartilhada de acesso ao bot (Decisao do usuario). Definir em
    # .env: API_BOT_SENHA=... . Quem acertar a senha fica autorizado naquele chat.
    bot_senha: str = "trocar-esta-senha"
    # Chave da Google Geocoding API (opcional). Se vazia, o geocoding de
    # endereco+CEP usa Nominatim. Definir em .env: API_GOOGLE_MAPS_API_KEY=...
    google_maps_api_key: str = ""
    # Chave do ArcGIS Location Platform p/ a VISTA AEREA (satelite Esri) do
    # Relatorio Pontual — BLK-SAT-01/DEC-018. Se vazia, a pagina de satelite e
    # OMITIDA (o resto do PDF sai igual). Definir em .env: API_ARCGIS_API_KEY=...
    arcgis_api_key: str = ""
    # Onde persistir as sessoes do bot (quem ja esta logado), para que um restart
    # do bot NAO deslogue todo mundo. Default no repo; override via env.
    bot_sessoes_path: Path = _REPO_ROOT / "bot_sessoes.json"
    # --- Relatorio de acessos do piloto (2026-08-18, trilha DEC-027) ---
    # Diretorio da trilha de acesso, montado :ro no container do bot (compose).
    # None = comando /acessos indisponivel. Env: API_ACESSO_LOG_DIR=/app/logs/acesso
    acesso_log_dir: Path | None = None
    # Chat AUTORIZADO a puxar o /acessos (o grupo de ops/alertas — mesmo id do
    # MONITOR_TELEGRAM_CHAT_ID; o compose repassa). O relatorio lista atividade do
    # time, entao NAO e' liberado pela senha compartilhada do bot: so este chat.
    # Vazio = comando desligado. Env: API_ACESSOS_ADMIN_CHAT_ID=...
    acessos_admin_chat_id: str = ""

    @field_validator("acesso_log_dir", mode="before")
    @classmethod
    def _acesso_log_dir_vazio_e_none(cls, value: object) -> object:
        # Env vazia ("API_ACESSO_LOG_DIR=") viraria Path(".") — truthy, e o guard
        # "None = indisponivel" do bot nunca dispararia (revisao de 2026-08-18).
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("tokens", mode="before")
    @classmethod
    def _parse_tokens(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return json.loads(value) if value else {}
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("["):
                return json.loads(value)
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Singleton das settings (cacheado por processo)."""
    return Settings()
