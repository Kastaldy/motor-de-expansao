"""Testes do esqueleto da API GeoEspacial (BLK-API-02).

Cobrem o liveness `/health` e a dependencia de auth por token->consumidor.
Sem dependencia de dados/motor — apenas a superficie minima do bloco.
"""

from __future__ import annotations

import pytest
from fastapi.security import HTTPAuthorizationCredentials

from motor_expansao.api import __version__
from motor_expansao.api.auth import resolver_consumidor
from motor_expansao.api.errors import APIError
from motor_expansao.api.settings import Settings


def _settings() -> Settings:
    return Settings(tokens={"tok-telegram": "bot-telegram"}, environment="test")


# --- auth: token -> consumidor (Decisao 2) ---------------------------------


def test_resolver_consumidor_token_valido() -> None:
    cred = HTTPAuthorizationCredentials(scheme="Bearer", credentials="tok-telegram")
    assert resolver_consumidor(credentials=cred, settings=_settings()) == "bot-telegram"


def test_resolver_consumidor_token_invalido() -> None:
    cred = HTTPAuthorizationCredentials(scheme="Bearer", credentials="errado")
    with pytest.raises(APIError) as exc:
        resolver_consumidor(credentials=cred, settings=_settings())
    assert exc.value.status_code == 401
    assert exc.value.codigo == "nao_autenticado"


def test_resolver_consumidor_token_ausente() -> None:
    with pytest.raises(APIError) as exc:
        resolver_consumidor(credentials=None, settings=_settings())
    assert exc.value.status_code == 401


# --- settings: parsing de tokens/origins via string -------------------------


def test_settings_tokens_via_json_string() -> None:
    s = Settings(tokens='{"a": "consumidor-a"}')
    assert s.tokens == {"a": "consumidor-a"}


def test_settings_cors_origins_via_csv_string() -> None:
    s = Settings(cors_origins="https://a.com, https://b.com")
    assert s.cors_origins == ["https://a.com", "https://b.com"]


# --- /health via TestClient (pula se httpx ausente) -------------------------


def test_health_endpoint() -> None:
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from motor_expansao.api.main import create_app

    client = TestClient(create_app())
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "environment" in body


def test_version_carimbo() -> None:
    assert __version__ == "api-geoespacial/v1"
