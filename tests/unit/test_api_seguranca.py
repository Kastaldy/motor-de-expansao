"""Testes das travas de seguranca da API GeoEspacial (BLK-SEC-05).

Cobrem:
  - guardrail SSRF de `url_maps_segura`/`host_de_maps_permitido` e a aplicacao dele
    em `expandir_link_curto` (geo.py) e `resolve_short_link` (maps_geocoder.py);
  - CORS sem `allow_credentials` (nao reflete origem);
  - recusa fail-closed de segredos default em producao.

Nenhum teste bate na rede: as travas rejeitam ANTES do GET, e o caminho permitido usa
mock de `requests.get`.
"""

from __future__ import annotations

import pytest

from motor_expansao.api import geo
from motor_expansao.api.maps_geocoder import host_de_maps_permitido, url_maps_segura


# ── SSRF: allowlist de host ─────────────────────────────────────────────────
@pytest.mark.parametrize(
    "host",
    [
        "maps.app.goo.gl",
        "goo.gl",
        "g.co",
        "www.google.com",
        "google.com",
        "maps.google.com.br",
        "GOOGLE.COM",  # case-insensitive
        "google.com.",  # trailing dot
    ],
)
def test_host_maps_permitido_aceita_dominios_do_google(host: str) -> None:
    assert host_de_maps_permitido(host) is True


@pytest.mark.parametrize(
    "host",
    [
        "api",  # servico interno do compose
        "authelia",
        "motor_expansao_tileserver",
        "localhost",
        "127.0.0.1",
        "10.0.0.5",
        "169.254.169.254",  # metadata da nuvem
        "::1",
        "8.8.8.8",  # IP publico tb e recusado: link do Maps e por dominio, nunca IP
        "1.1.1.1",
        "evil.com",
        "google.com.evil.com",  # sufixo falso
        "notgoogle.com",
        "",
    ],
)
def test_host_maps_permitido_recusa_interno_e_desconhecido(host: str) -> None:
    assert host_de_maps_permitido(host) is False


@pytest.mark.parametrize(
    "url,esperado",
    [
        ("https://maps.app.goo.gl/abc123", True),
        ("http://goo.gl/maps/x", True),
        ("https://www.google.com/maps/place/x", True),
        ("http://169.254.169.254/latest/meta-data", False),
        ("http://api:8077/api/health", False),
        ("http://8.8.8.8/x", False),  # IP publico: recusado (Maps e por dominio)
        ("file:///etc/passwd", False),
        ("ftp://google.com/x", False),
        ("https://evil.com/redir", False),
        ("", False),
        ("not-a-url", False),
    ],
)
def test_url_maps_segura(url: str, esperado: bool) -> None:
    assert url_maps_segura(url) is esperado


# ── expandir_link_curto: SSRF bloqueada + caminho permitido ─────────────────
def test_expandir_link_curto_bloqueia_url_interna_sem_tocar_a_rede(monkeypatch) -> None:
    """URL de host interno/metadata -> devolve o texto original e NAO faz request."""

    def _boom(*a, **k):
        raise AssertionError("requests.get NAO deveria ser chamado para URL insegura")

    monkeypatch.setattr(geo.requests, "get", _boom)
    texto = "veja http://169.254.169.254/latest/meta-data/"
    assert geo.expandir_link_curto(texto) == texto
    assert geo.expandir_link_curto("http://api:8077/segredo") == "http://api:8077/segredo"


def test_expandir_link_curto_sem_url_devolve_texto() -> None:
    assert geo.expandir_link_curto("Rua das Flores, 100") == "Rua das Flores, 100"


def test_expandir_link_curto_segue_link_do_maps(monkeypatch) -> None:
    """Link do Maps permitido -> segue e devolve a URL final (mock, sem rede)."""
    final = "https://www.google.com/maps/place/x/@-23.5,-46.6,17z/data=!3d-23.5!4d-46.6"

    class _Resp:
        url = final
        headers: dict = {}
        is_redirect = False
        is_permanent_redirect = False

    monkeypatch.setattr(geo.requests, "get", lambda *a, **k: _Resp())
    assert geo.expandir_link_curto("olha https://maps.app.goo.gl/abc123") == final


def test_expandir_link_curto_recusa_redirect_para_host_interno(monkeypatch) -> None:
    """Um redirect (302) apontando para host interno e recusado -> texto original."""

    class _Redir:
        url = "https://maps.app.goo.gl/abc"
        # Redirect para um host INTERNO (nao-allowlisted). Sem porta no valor de proposito:
        # `host:porta` faz o gitleaks confundir com `chave:segredo` (falso-positivo).
        headers = {"Location": "http://servico-interno-do-compose/api/verify"}
        is_redirect = True
        is_permanent_redirect = False

    monkeypatch.setattr(geo.requests, "get", lambda *a, **k: _Redir())
    texto = "https://maps.app.goo.gl/abc"
    assert geo.expandir_link_curto(texto) == texto


# ── resolve_short_link: recusa antes do GET ─────────────────────────────────
def test_resolve_short_link_recusa_url_insegura_sem_rede(monkeypatch) -> None:
    from motor_expansao.api import maps_geocoder

    def _boom(*a, **k):
        raise AssertionError("requests.get NAO deveria ser chamado para URL insegura")

    monkeypatch.setattr(maps_geocoder.requests, "get", _boom)
    assert maps_geocoder.resolve_short_link("http://169.254.169.254/") is None
    assert maps_geocoder.resolve_short_link("http://api:8077/") is None
    assert maps_geocoder.resolve_short_link("file:///etc/passwd") is None
    assert maps_geocoder.resolve_short_link("http://8.8.8.8/x") is None  # IP publico tb recusado


# ── CORS: sem allow_credentials (nao reflete origem) ────────────────────────
def test_cors_nao_habilita_credentials() -> None:
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from motor_expansao.api.main import create_app

    client = TestClient(create_app())
    resp = client.get("/health", headers={"Origin": "https://qualquer-site.example"})
    assert resp.status_code == 200
    # Sem credentials, o header de credentials NAO pode aparecer.
    assert resp.headers.get("access-control-allow-credentials") is None


# ── Fail-closed: producao recusa segredos default ───────────────────────────
def test_producao_recusa_token_default() -> None:
    from motor_expansao.api.main import _garantir_producao_sem_defaults
    from motor_expansao.api.settings import Settings

    s = Settings(
        environment="production",
        tokens={"dev-token": "dev-local"},
        api_call_token="dev-token",
        bot_senha="uma-senha-forte-123",
    )
    with pytest.raises(RuntimeError):
        _garantir_producao_sem_defaults(s)


def test_producao_ignora_bot_senha_e_api_call_token_default() -> None:
    """O servico `api` NAO recebe api_call_token/bot_senha (sao do bot) -> ficam no
    default de forma inofensiva. Com API_TOKENS forte, a API NAO deve abortar o boot
    (regressao que derrubou o deploy: o guard checava esses dois por engano)."""
    from motor_expansao.api.main import _garantir_producao_sem_defaults
    from motor_expansao.api.settings import Settings

    s = Settings(
        environment="production",
        tokens={"tok-forte-abc": "bot"},
        api_call_token="dev-token",      # default do BOT — irrelevante para a API
        bot_senha="trocar-esta-senha",   # default do BOT — irrelevante para a API
    )
    _garantir_producao_sem_defaults(s)  # nao levanta: so `tokens` importa


def test_producao_aceita_segredos_fortes() -> None:
    from motor_expansao.api.main import _garantir_producao_sem_defaults
    from motor_expansao.api.settings import Settings

    s = Settings(
        environment="production",
        tokens={"tok-forte-abc": "bot"},
        api_call_token="tok-forte-abc",
        bot_senha="uma-senha-forte-123",
    )
    _garantir_producao_sem_defaults(s)  # nao levanta


def test_dev_ignora_segredos_default() -> None:
    from motor_expansao.api.main import _garantir_producao_sem_defaults
    from motor_expansao.api.settings import Settings

    s = Settings(
        environment="development",
        tokens={"dev-token": "dev-local"},
        api_call_token="dev-token",
        bot_senha="trocar-esta-senha",
    )
    _garantir_producao_sem_defaults(s)  # nao levanta em dev
