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


@pytest.fixture(autouse=True)
def _limpa_rate_state():
    """Isola o estado global do rate-limit entre testes."""
    from motor_expansao.api import main

    main._rate_state.clear()
    yield
    main._rate_state.clear()


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
        # Bypass por DIVERGENCIA DE PARSER (pentest 2026-08-19): o `urlsplit` (validacao)
        # ve `goo.gl` e liberava, mas `requests`/urllib3 conecta no host ANTES do
        # backslash (`api:8077`, `169.254.169.254`). Todos devem ser recusados.
        ("http://api:8077\\@goo.gl/", False),
        ("http://169.254.169.254\\@goo.gl/", False),
        ("https://goo.gl\\@api:8077/", False),
        ("https://goo.gl /maps", False),  # espaco: separa os dois parsers
        ("https://goo.gl\t/maps", False),  # tab: idem
    ],
)
def test_url_maps_segura(url: str, esperado: bool) -> None:
    assert url_maps_segura(url) is esperado


def test_url_maps_segura_fecha_parser_differential() -> None:
    """Regressao do pentest 2026-08-19: prova que o payload de backslash — que o
    `urlsplit` lia como `goo.gl` mas o urllib3 discava em host interno — e' recusado.

    O teste tambem DOCUMENTA a divergencia que sustentava o bypass, para que uma
    futura mudanca no guardrail que a reintroduza quebre aqui de forma legivel.
    """
    from urllib.parse import urlsplit

    from urllib3.util import parse_url

    payload = "http://api:8077\\@goo.gl/"
    # A divergencia REAL que o guardrail agora neutraliza:
    assert (urlsplit(payload).hostname or "").lower() == "goo.gl"  # o que a validacao via
    assert (parse_url(payload).host or "").lower() == "api"        # onde o requests discava
    # E, apesar da divergencia, o guardrail recusa:
    assert url_maps_segura(payload) is False
    # O caminho legitimo continua liberado:
    assert url_maps_segura("https://maps.app.goo.gl/abc123") is True


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


# ── Rate-limit da API publica (BLK-SEC-05) ──────────────────────────────────
def test_rate_limit_ok_respeita_o_teto(monkeypatch) -> None:
    from motor_expansao.api import main

    monkeypatch.setattr(main, "_RATE_LIMIT_MAX", 3)
    assert main._rate_limit_ok("tok-x") is True   # 1
    assert main._rate_limit_ok("tok-x") is True   # 2
    assert main._rate_limit_ok("tok-x") is True   # 3
    assert main._rate_limit_ok("tok-x") is False  # 4 -> estourou
    assert main._rate_limit_ok("tok-y") is True   # chave diferente tem janela propria


def test_rate_limit_middleware_429_e_health_livre(monkeypatch) -> None:
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from motor_expansao.api import main
    from motor_expansao.api.main import create_app

    monkeypatch.setattr(main, "_RATE_LIMIT_MAX", 2)
    client = TestClient(create_app())

    # /health NUNCA e limitado.
    for _ in range(5):
        assert client.get("/health").status_code == 200

    # Rota nao-livre: a 3a requisicao (max=2) recebe 429. O middleware roda antes do
    # routing, entao uma rota inexistente tambem conta (o alvo e a TAXA, nao a rota).
    main._rate_state.clear()
    assert client.get("/qualquer-rota").status_code != 429  # 1
    assert client.get("/qualquer-rota").status_code != 429  # 2
    resp = client.get("/qualquer-rota")                      # 3 -> estourou
    assert resp.status_code == 429
    assert resp.json()["codigo"] == "rate_limited"


def test_rate_limit_token_INVENTADO_cai_no_balde_do_IP(monkeypatch) -> None:
    """Trocar o Bearer a cada requisicao nao abre janela nova no rate-limit.

    Antes a chave era o token cru, ainda nao validado: cada token inventado ganhava 120
    requisicoes proprias, e adivinhar `API_TOKENS` nao tinha teto nenhum.
    """
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from motor_expansao.api import main
    from motor_expansao.api.settings import Settings

    dev = Settings(
        environment="development",
        tokens={"tok-forte-abc": "bot"},
        api_call_token="tok-forte-abc",
        bot_senha="uma-senha-forte-123",
    )
    monkeypatch.setattr(main, "get_settings", lambda: dev)
    monkeypatch.setattr(main, "_RATE_LIMIT_MAX", 2)
    client = TestClient(main.create_app())
    main._rate_state.clear()

    def com(token: str) -> int:
        return client.get("/qualquer-rota", headers={"Authorization": f"Bearer {token}"}).status_code

    assert com("chute-1") != 429
    assert com("chute-2") != 429
    assert com("chute-3") == 429, "token inventado ganhou janela propria e evadiu o teto do IP"
    assert not any(k.startswith("tok:chute") for k in main._rate_state), (
        "token inventado virou chave no estado do rate-limit"
    )
    # O consumidor legitimo segue com a janela DELE, mesmo com o IP ja' estourado.
    assert com("tok-forte-abc") != 429


def test_rate_limit_da_API_agrega_IPv6_pelo_MIDDLEWARE(monkeypatch) -> None:
    """Revisao de 09/11/2026: girar o IPv6 dentro do bloco do assinante nao abre balde novo.

    Pelo middleware de verdade, e nao pela funcao auxiliar: a 2a revisao mostrou que o teste
    da auxiliar seguia verde com o `chave_de_origem` arrancado do `_rate_limit`."""
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from motor_expansao.api import main

    monkeypatch.setattr(main, "_RATE_LIMIT_MAX", 2)
    client = TestClient(main.create_app())
    main._rate_state.clear()

    codigos = [
        client.get("/qualquer-rota", headers={"X-Forwarded-For": f"2001:db8:0:{i:x}::1"}).status_code
        for i in range(3)
    ]
    assert codigos[-1] == 429, f"cada rede /64 do mesmo /56 ganhou balde proprio: {codigos}"


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


# ── OpenAPI/schema fechado em producao (pentest 2026-08-19) ─────────────────
def test_api_openapi_e_docs_desligados_em_producao(monkeypatch) -> None:
    """Em producao a API nao pode servir /openapi.json|/docs|/redoc: o probe de prod
    achou /openapi.json=200 mesmo com /docs off (meia trava). Fecha o schema junto."""
    from motor_expansao.api import main
    from motor_expansao.api.settings import Settings

    prod = Settings(
        environment="production",
        tokens={"tok-forte-abc": "bot"},
        api_call_token="tok-forte-abc",
        bot_senha="uma-senha-forte-123",
    )
    monkeypatch.setattr(main, "get_settings", lambda: prod)
    app = main.create_app()
    assert app.openapi_url is None
    assert app.docs_url is None
    assert app.redoc_url is None


def test_api_openapi_ligado_fora_de_producao(monkeypatch) -> None:
    """Fora de producao a docs interativa segue disponivel (conveniencia de dev)."""
    from motor_expansao.api import main
    from motor_expansao.api.settings import Settings

    dev = Settings(
        environment="development",
        tokens={"tok-forte-abc": "bot"},
        api_call_token="tok-forte-abc",
        bot_senha="uma-senha-forte-123",
    )
    monkeypatch.setattr(main, "get_settings", lambda: dev)
    app = main.create_app()
    assert app.openapi_url == "/openapi.json"
    assert app.docs_url == "/docs"


def test_cors_default_e_restritivo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Solidificacao #5: o default do CORS deixou de ser `["*"]`. Vazio = nenhuma origem
    cross-origin; a API e' Bearer server-to-server e nenhum navegador a chama."""
    monkeypatch.delenv("API_CORS_ORIGINS", raising=False)
    from motor_expansao.api.settings import Settings

    assert Settings().cors_origins == []


def test_rate_limit_ip_sai_do_ULTIMO_xff_nao_do_primeiro() -> None:
    """Solidificacao #7: o IP do rate-limit anonimo sai do ULTIMO token do X-Forwarded-For
    (o que o Caddy anexa), nao do 1o (que o cliente forja); token nao-IP cai no peer TCP."""
    from motor_expansao.api import main

    assert main._ip_do_edge("1.2.3.4, 203.0.113.9", "10.0.0.1") == "203.0.113.9"
    assert main._ip_do_edge("lixo-nao-ip", "10.0.0.1") == "10.0.0.1"
    assert main._ip_do_edge("", "10.0.0.1") == "10.0.0.1"
