"""Integracao end-to-end de POST /api/v1/analisar (BLK-API-03).

Usa os dados reais materializados (so SP: Aguas da Prata 3500402, Altinopolis
3501004). Pula se a base geo nao estiver presente.
"""

from __future__ import annotations

import pytest

pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from motor_expansao.api.main import create_app  # noqa: E402
from motor_expansao.api.settings import get_settings  # noqa: E402

AGUAS_DA_PRATA = {"lat": -21.9180, "lng": -46.6855}  # cod_municipio 3500402
AUTH = {"Authorization": "Bearer dev-token"}


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture(scope="module", autouse=True)
def _exige_base_geo() -> None:
    s = get_settings()
    part = s.censo_geo_dir / "uf=SP" / "cod_municipio=3500402"
    if not part.is_dir():
        pytest.skip(f"Base geo ausente em {part}")


def test_analisar_aguas_da_prata_ok(client: TestClient) -> None:
    resp = client.post("/api/v1/analisar", json=AGUAS_DA_PRATA, headers=AUTH)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["metodo"] == "setor_censitario_intersecao_area_1p5km"
    assert body["raio_km"] == 1.5
    assert body["versao_contrato"] == "api-geoespacial/v1"
    assert body["versao_score"] == "score_setor_2022_calibrado"
    assert body["consumidor"] == get_settings().tokens.get("dev-token")
    assert body["gerado_em"].endswith("Z")
    assert body["n_setores"] >= 1  # o ponto cai dentro do municipio


def test_analisar_sem_token_401(client: TestClient) -> None:
    resp = client.post("/api/v1/analisar", json=AGUAS_DA_PRATA)
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Token invalido", "codigo": "nao_autenticado"}


def test_analisar_fora_do_brasil_400(client: TestClient) -> None:
    resp = client.post("/api/v1/analisar", json={"lat": 48.85, "lng": 2.35}, headers=AUTH)
    assert resp.status_code == 400
    assert resp.json()["codigo"] == "coordenada_invalida"


def test_analisar_municipio_sem_base_404(client: TestClient, tmp_path) -> None:
    # Hermetico: aponta censo_geo_dir para um dir VAZIO, forcando "base geo ausente"
    # independente de quais municipios estao materializados no disco (a base completa
    # de 2026-06-12 cobre o Brasil todo -> nao ha mais municipio que de 404 pela base
    # real). O ponto ainda resolve o municipio pela malha IBGE real, mas a particao
    # nao existe no dir vazio -> 404 base_geo_ausente.
    vazio = tmp_path / "sem_base"
    vazio.mkdir()
    override = get_settings().model_copy(update={"censo_geo_dir": vazio})
    client.app.dependency_overrides[get_settings] = lambda: override
    try:
        resp = client.post("/api/v1/analisar", json=AGUAS_DA_PRATA, headers=AUTH)
    finally:
        client.app.dependency_overrides.pop(get_settings, None)
    assert resp.status_code == 404
    assert resp.json()["codigo"] == "base_geo_ausente"


def test_analisar_sem_coordenada_422(client: TestClient) -> None:
    resp = client.post("/api/v1/analisar", json={"formato": "json"}, headers=AUTH)
    assert resp.status_code == 422  # validacao Pydantic (nem lat/lng nem maps_url)


def test_analisar_maps_url(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/analisar",
        json={"maps_url": "https://maps.google.com/?q=-21.9180,-46.6855"},
        headers=AUTH,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["n_setores"] >= 1


def test_analisar_formato_pdf_query(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/analisar?formato=pdf", json=AGUAS_DA_PRATA, headers=AUTH
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"  # assinatura de arquivo PDF


def test_analisar_accept_pdf_header(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/analisar",
        json=AGUAS_DA_PRATA,
        headers={**AUTH, "Accept": "application/pdf"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"


def test_analisar_pdf_carimba_consumidor(client: TestClient, monkeypatch) -> None:
    # Wiring consumidor->solicitante (BLK-EST-03). Spy curto-circuita a geracao final
    # do PDF capturando o kwarg `solicitante`. O import em `gerar_pdf_ponto` e local
    # por-nome a partir de `censo_report`, entao o alvo do patch e o MODULO de origem.
    capturado: dict[str, object] = {}

    def _spy(*args, **kwargs) -> bytes:
        capturado["solicitante"] = kwargs.get("solicitante")
        return b"%PDF-1.4 fake"  # bytes sinteticos: nenhum PDF real em disco (anti-PII)

    monkeypatch.setattr(
        "motor_expansao.dashboard.censo_report.gerar_pdf_relatorio_pontual_censitario", _spy
    )
    resp = client.post("/api/v1/analisar?formato=pdf", json=AGUAS_DA_PRATA, headers=AUTH)
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    # consumidor resolvido pelo token (nome FICTICIO `dev-local`) chega como solicitante.
    assert capturado["solicitante"] == get_settings().tokens["dev-token"]


def test_analisar_pdf_solicitante_none_fallback(monkeypatch) -> None:
    # Fallback retrocompativel: consumidor=None -> solicitante=None (so "Ultra Academia"),
    # independente da rota. Chama gerar_pdf_ponto DIRETAMENTE com o mesmo spy.
    from motor_expansao.api import service

    capturado: dict[str, object] = {}

    def _spy(*args, **kwargs) -> bytes:
        capturado["solicitante"] = kwargs.get("solicitante")
        return b"%PDF-1.4 fake"

    monkeypatch.setattr(
        "motor_expansao.dashboard.censo_report.gerar_pdf_relatorio_pontual_censitario", _spy
    )
    out = service.gerar_pdf_ponto(
        AGUAS_DA_PRATA["lat"], AGUAS_DA_PRATA["lng"], None, get_settings(), rotulo=None
    )
    assert out == b"%PDF-1.4 fake"
    assert capturado["solicitante"] is None
