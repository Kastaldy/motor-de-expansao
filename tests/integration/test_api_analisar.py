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


def test_analisar_municipio_sem_base_404(client: TestClient) -> None:
    # Sao Paulo capital (3550308) nao esta materializado -> 404 base_geo_ausente.
    resp = client.post("/api/v1/analisar", json={"lat": -23.5505, "lng": -46.6333}, headers=AUTH)
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
