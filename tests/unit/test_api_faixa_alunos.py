"""`GET /api/v1/faixa-alunos` — a faixa por metragem no contrato publico.

Ela existe porque `demanda` e campo OBRIGATORIO do cenario de viabilidade e e PREMISSA de
quem pede (DEC-009). Sem a faixa, o consumidor da API precisa cravar um numero fixo — o
mesmo para 600 m2 e para 10.000 m2.

O que estes testes protegem:

1. **Uma regua so'.** A rota publica e a do piloto tem que devolver os MESMOS numeros para
   a mesma metragem. Se alguem recopiar a conversao em vez de chamar a funcao do nucleo,
   as duas divergem no primeiro ajuste — e divergem em silencio.
2. **A ausencia de base e' resposta, nao erro** — e ela vem com a `fonte` dizendo o porque.
   Sem isso, o consumidor leria faixa nula como "faixa estreita" em vez de "nao calculada".
3. **A faixa nao e' previsao.** A rota nao aceita lat/lng; aceitar abriria a porta para
   lerem o numero como previsao de demanda daquele ponto.

Sem dado real: a base de comparaveis e uma fixture sintetica de 30 linhas.
"""

from __future__ import annotations

import pandas as pd
import pytest

pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from motor_expansao.api.main import create_app  # noqa: E402

AUTH = {"Authorization": "Bearer dev-token"}


def _base_sintetica() -> pd.DataFrame:
    """Comparaveis plausiveis: 30 unidades de 900 a 2.350 m2, densidade decrescente com
    o tamanho (unidade grande ocupa menos aluno por m2, que e o formato da curva real)."""
    metragens = [900 + 50 * i for i in range(30)]
    return pd.DataFrame(
        {
            "metragem": metragens,
            "alunos_por_m2": [1.2 - 0.012 * i for i in range(30)],
        }
    )


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    import motor_expansao.api.routes.faixa_alunos as rota

    monkeypatch.setattr(
        rota, "base_calibracao", lambda _dir: (_base_sintetica(), "fixture-sintetica.parquet")
    )
    return TestClient(create_app())


@pytest.fixture
def client_sem_base(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    import motor_expansao.api.routes.faixa_alunos as rota

    monkeypatch.setattr(
        rota,
        "base_calibracao",
        lambda _dir: (None, "indisponivel (faixa de alunos nao calculada)"),
    )
    return TestClient(create_app())


def test_sem_token_401(client: TestClient) -> None:
    resp = client.get("/api/v1/faixa-alunos", params={"m2": 1500})
    assert resp.status_code == 401
    assert resp.json()["codigo"] == "nao_autenticado"


def test_faixa_ordenada_e_com_procedencia(client: TestClient) -> None:
    resp = client.get("/api/v1/faixa-alunos", params={"m2": 1500}, headers=AUTH)
    assert resp.status_code == 200, resp.text
    corpo = resp.json()

    assert corpo["m2"] == 1500
    assert corpo["p10"] <= corpo["p50"] <= corpo["p90"], corpo
    assert corpo["n_comparaveis"] > 0
    # A procedencia viaja junto com o numero: a MESMA faixa significa outra coisa quando
    # vem do fallback, e quem for usar isso como premissa precisa saber disso.
    assert corpo["fonte"] == "fixture-sintetica.parquet"
    # Alunos e' unidade contavel — nada de 412,7.
    assert all(float(corpo[k]).is_integer() for k in ("p10", "p50", "p90"))


def test_sem_base_devolve_faixa_nula_e_diz_o_motivo(client_sem_base: TestClient) -> None:
    resp = client_sem_base.get("/api/v1/faixa-alunos", params={"m2": 1500}, headers=AUTH)
    assert resp.status_code == 200, resp.text
    corpo = resp.json()

    assert corpo["p10"] is None and corpo["p50"] is None and corpo["p90"] is None
    assert corpo["n_comparaveis"] == 0
    assert "indisponivel" in corpo["fonte"]


@pytest.mark.parametrize("m2", [0, -100])
def test_metragem_invalida_422(client: TestClient, m2: float) -> None:
    resp = client.get("/api/v1/faixa-alunos", params={"m2": m2}, headers=AUTH)
    assert resp.status_code == 422


def test_metragem_ausente_422(client: TestClient) -> None:
    assert client.get("/api/v1/faixa-alunos", headers=AUTH).status_code == 422


def test_a_rota_publica_e_a_do_piloto_dao_o_mesmo_numero(monkeypatch: pytest.MonkeyPatch) -> None:
    """A prova da regua unica.

    Nao basta as duas "parecerem certas": elas tem que sair da MESMA funcao. Este teste
    compara os tres percentis para a mesma metragem e a mesma base — se alguem recopiar a
    montagem na rota publica, ele falha antes do merge.
    """
    import sys
    from pathlib import Path

    servidor = Path(__file__).resolve().parents[2] / "web" / "server"
    if str(servidor) not in sys.path:
        sys.path.insert(0, str(servidor))
    import app as pilot  # noqa: E402

    import motor_expansao.api.routes.faixa_alunos as rota

    base = _base_sintetica()
    monkeypatch.setattr(rota, "base_calibracao", lambda _dir: (base, "fixture-sintetica.parquet"))
    monkeypatch.setattr(pilot, "_base_calibracao", lambda: (base, "fixture-sintetica.parquet"))

    da_api = TestClient(create_app()).get(
        "/api/v1/faixa-alunos", params={"m2": 1500}, headers=AUTH
    ).json()
    do_piloto = pilot.faixa_alunos(m2=1500)

    for chave in ("p10", "p50", "p90"):
        assert da_api[chave] == do_piloto[chave], f"{chave} divergiu entre as duas rotas"
    assert da_api["n_comparaveis"] == do_piloto["n_comparaveis"]


def test_rota_nao_aceita_coordenada(client: TestClient) -> None:
    """A faixa depende SO do tamanho. Aceitar lat/lng aqui — mesmo ignorando — faria o
    consumidor ler o numero como previsao de demanda daquele ponto (DEC-009)."""
    resp = client.get(
        "/api/v1/faixa-alunos",
        params={"m2": 1500, "lat": -23.55, "lng": -46.63},
        headers=AUTH,
    )
    assert resp.status_code == 200
    assert "lat" not in resp.json() and "lng" not in resp.json()
