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


# --- settings: competitors_logos_dir None-safe e logos carregados ----------------

# PNG mínimo válido (1×1 px transparente) para fixture de logo
_MINIMAL_PNG_LOGOS = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_settings_competitors_logos_dir_default_e_none() -> None:
    """O default de competitors_logos_dir deve ser None, nunca site-packages/data/Logos."""
    s = Settings()
    assert s.competitors_logos_dir is None


def test_settings_competitors_logos_dir_via_env(tmp_path) -> None:
    """Quando API_COMPETITORS_LOGOS_DIR aponta para dir existente, o campo é Path."""
    logos_dir = tmp_path / "logos"
    logos_dir.mkdir()
    s = Settings(competitors_logos_dir=logos_dir)
    assert s.competitors_logos_dir == logos_dir


def test_preload_logos_com_dir_valido_popula_icon_cache(tmp_path) -> None:
    """logos_dir válido com logo_smart_fit.png popula _ICON_CACHE['smart_fit']."""
    from motor_expansao.dashboard.competitors import _ICON_CACHE, preload_logos

    logos_dir = tmp_path / "logos"
    logos_dir.mkdir()
    (logos_dir / "logo_smart_fit.png").write_bytes(_MINIMAL_PNG_LOGOS)
    _ICON_CACHE.pop("smart_fit", None)
    try:
        preload_logos(logos_dir)
        assert "smart_fit" in _ICON_CACHE
    finally:
        _ICON_CACHE.pop("smart_fit", None)


def test_service_guard_logos_dir_none_resulta_em_none() -> None:
    """Quando competitors_logos_dir=None, o guard de service.py deve resolver para None
    sem lançar TypeError (Path(None).is_dir() lançaria TypeError sem o guard is not None)."""
    from pathlib import Path

    s = Settings(competitors_logos_dir=None)
    # Replica exatamente o guard de service.py (gerar_pdf_ponto)
    logos_dir = (
        s.competitors_logos_dir
        if s.competitors_logos_dir is not None
        and Path(s.competitors_logos_dir).is_dir()
        else None
    )
    assert logos_dir is None  # deve ser None sem exceção


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


# --- handler catch-all de 500 (contrato §9): {detail, codigo:"erro_interno"} ---


def test_500_inesperado_usa_corpo_padrao_e_loga_traceback() -> None:
    """Qualquer excecao nao tratada vira {detail, codigo:"erro_interno"} (nunca o
    corpo cru do FastAPI) E gera um log de ERROR com o traceback no servidor."""
    import logging

    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from motor_expansao.api.main import create_app

    app = create_app()

    @app.get("/api/v1/_boom", include_in_schema=False)
    async def _boom() -> dict:
        raise RuntimeError("falha inesperada interna")

    # Captura direta no logger da API (propagate=False quebraria o caplog do pytest).
    registros: list[logging.LogRecord] = []

    class _Captura(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            registros.append(record)

    api_logger = logging.getLogger("motor_expansao.api")
    captura = _Captura()
    api_logger.addHandler(captura)
    try:
        # raise_server_exceptions=False: queremos a RESPOSTA 500, nao a excecao propagada.
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/_boom")
    finally:
        api_logger.removeHandler(captura)

    assert resp.status_code == 500
    assert resp.json() == {"detail": "Erro interno ao gerar o estudo", "codigo": "erro_interno"}
    # Ha um ERROR com traceback (exc_info) do nosso handler.
    assert any(r.levelno == logging.ERROR and r.exc_info for r in registros)


def test_hexes_vizinhos_serve_score_setor_para_socioeconomia_do_hero(tmp_path):
    """Regressao BLK-RELPON-13: o painel Socioeconomia do slide-hero passou a ser desenhado
    por HEXAGONO e depende de `score_setor_2022_calibrado` no `hexes_df`. O caminho da API/bot
    (`_hexes_vizinhos_do_ponto`) servia so `oferta_efetiva_disponivel` -> o painel caia no
    fallback textual em TODO PDF do bot. Este teste trava as duas colunas no retorno.
    """
    import h3
    import pandas as pd

    from motor_expansao.api.service import _hexes_vizinhos_do_ponto

    lat, lng = -23.55, -46.63
    centro = h3.latlng_to_cell(lat, lng, 7)
    hexes = list(h3.grid_disk(centro, 5))
    df = pd.DataFrame(
        {
            "hex_id": hexes,
            "oferta_efetiva_disponivel": [1200.0] * len(hexes),
            "score_setor_2022_calibrado": [64.0] * len(hexes),
            "coluna_irrelevante": [0] * len(hexes),  # nao deve ser puxada
        }
    )
    staging = tmp_path / "staging"
    staging.mkdir()
    df.to_parquet(staging / "hexagonos_mercado_mapeado.parquet")

    settings = Settings(staging_dir=staging)
    out = _hexes_vizinhos_do_ponto(lat, lng, settings)

    assert out is not None
    assert "score_setor_2022_calibrado" in out.columns  # a regressao
    assert "oferta_efetiva_disponivel" in out.columns
    assert "coluna_irrelevante" not in out.columns       # segue lendo so o necessario
    assert (out["score_setor_2022_calibrado"] == 64.0).all()


def test_hexes_vizinhos_sem_a_coluna_score_nao_crasha(tmp_path):
    """Parquet antigo sem `score_setor_2022_calibrado`: a leitura e tolerante (nao pede a
    coluna) e devolve o que houver -> a Socioeconomia cai no fallback textual, sem crashar."""
    import h3
    import pandas as pd

    from motor_expansao.api.service import _hexes_vizinhos_do_ponto

    lat, lng = -23.55, -46.63
    centro = h3.latlng_to_cell(lat, lng, 7)
    hexes = list(h3.grid_disk(centro, 5))
    df = pd.DataFrame(
        {"hex_id": hexes, "oferta_efetiva_disponivel": [1200.0] * len(hexes)}
    )
    staging = tmp_path / "staging"
    staging.mkdir()
    df.to_parquet(staging / "hexagonos_mercado_mapeado.parquet")

    out = _hexes_vizinhos_do_ponto(lat, lng, Settings(staging_dir=staging))
    assert out is not None
    assert "score_setor_2022_calibrado" not in out.columns
    assert "oferta_efetiva_disponivel" in out.columns
