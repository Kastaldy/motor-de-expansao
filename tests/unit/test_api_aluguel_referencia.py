"""`GET /api/v1/aluguel-referencia` — a régua de aluguel da DEC-080 no contrato público.

Por que existe (DEC-080, Emenda 1): a ponte do Forms gera os estudos pela API pública, e a
régua de aluguel por município × tipo só existia no site. Sem esta rota, o estudo que sai
pela API não consegue dizer se o aluguel pedido está acima ou abaixo do mercado.

O que estes testes protegem:

1. **Uma régua só.** Para o mesmo tipo e município, a rota pública devolve o MESMO dict que
   a rota do site (`GET /api/aluguel-referencia`). As duas chamam `TabelaAluguel.consultar`;
   se alguém recopiar a mediana numa delas, as duas divergem em silêncio.
2. **O ponto decide o município.** A API recebe lat/lng, resolve o município pela malha e
   pelo nome do censo, e só então consulta a régua — com o fallback UF e Brasil da DEC-080.
3. **A ausência da base é dita.** Sem o arquivo de anúncios, 503 com código próprio, nunca
   um número qualquer: o consumidor não pode confundir "sem régua" com "régua barata".

Sem dado real: malha, censo e anúncios são fixtures sintéticas em `tmp_path`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from motor_expansao.api.main import create_app  # noqa: E402
from motor_expansao.api.settings import Settings, get_settings  # noqa: E402

AUTH = {"Authorization": "Bearer dev-token"}
ROTA = "/api/v1/aluguel-referencia"

# Dois municípios do ES, quadrados vizinhos: Vitória em volta de (-20.30, -40.30) e
# Cariacica logo a oeste. Os códigos são os do IBGE, mas a geometria é inventada.
VITORIA = {"lat": -20.30, "lng": -40.30}
CARIACICA = {"lat": -20.30, "lng": -40.40}
NO_MAR = {"lat": -20.30, "lng": -39.50}  # dentro do Brasil, a ~80 km da malha sintética


def _quadrado(lng0: float, lat0: float, meio: float = 0.05) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [[
            [lng0 - meio, lat0 - meio], [lng0 + meio, lat0 - meio],
            [lng0 + meio, lat0 + meio], [lng0 - meio, lat0 + meio],
            [lng0 - meio, lat0 - meio],
        ]],
    }


def _anuncios(uf: str, municipio: str, tipo: str, rs_m2: list[float]) -> list[dict]:
    return [
        {"uf": uf, "municipio": municipio, "tipo": tipo, "status": "ativo",
         "area_relevante_m2": 1000.0, "preco_aluguel": v * 1000.0}
        for v in rs_m2
    ]


@pytest.fixture
def dados(tmp_path: Path) -> dict[str, Path]:
    ibge = tmp_path / "ibge"
    ibge.mkdir()
    (ibge / "municipios_ES.geojson").write_text(
        json.dumps({
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "properties": {"codarea": "3205309"},
                 "geometry": _quadrado(-40.30, -20.30)},
                {"type": "Feature", "properties": {"codarea": "3201308"},
                 "geometry": _quadrado(-40.40, -20.30)},
            ],
        }),
        encoding="utf-8",
    )
    censo = tmp_path / "censo"
    for cod, nome in (("3205309", "Vitória"), ("3201308", "Cariacica")):
        pasta = censo / "uf=ES" / f"cod_municipio={cod}"
        pasta.mkdir(parents=True)
        pd.DataFrame({"nome_municipio": [nome, nome]}).to_parquet(pasta / "part-0.parquet")
    anuncios = tmp_path / "viaveis.parquet"
    pd.DataFrame(
        _anuncios("ES", "Vitória", "galpao", [10, 20, 30, 40, 50])     # cidade: 5, mediana 30
        + _anuncios("ES", "Cariacica", "galpao", [60, 70])             # cidade: 2 -> UF
        + _anuncios("ES", "Vitória", "loja", [5, 6, 7])                # UF < 5 -> Brasil
        + _anuncios("SP", "Campinas", "loja", [40, 40, 40])
    ).to_parquet(anuncios)
    return {"ibge": ibge, "censo": censo, "anuncios": anuncios}


def _cliente(dados: dict[str, Path], *, base: Path | None) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        ibge_dir=dados["ibge"], censo_geo_dir=dados["censo"], oportunidades_path=base
    )
    return TestClient(app)


@pytest.fixture
def client(dados: dict[str, Path]) -> TestClient:
    return _cliente(dados, base=dados["anuncios"])


def test_sem_token_401(client: TestClient) -> None:
    resp = client.get(ROTA, params={"tipo": "galpao", **VITORIA})
    assert resp.status_code == 401
    assert resp.json()["codigo"] == "nao_autenticado"


def test_ponto_resolve_o_municipio_e_usa_a_mediana_da_cidade(client: TestClient) -> None:
    resp = client.get(ROTA, params={"tipo": "galpao", **VITORIA}, headers=AUTH)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "tipo": "galpao", "rs_m2": 30.0, "n_anuncios": 5, "nivel": "municipio",
        "uf": "ES", "municipio": "Vitória", "rs_m2_p25": 20.0, "rs_m2_p75": 40.0,
    }


def test_cidade_com_menos_de_cinco_cai_para_a_uf(client: TestClient) -> None:
    corpo = client.get(ROTA, params={"tipo": "galpao", **CARIACICA}, headers=AUTH).json()
    assert (corpo["nivel"], corpo["n_anuncios"], corpo["uf"], corpo["municipio"]) == (
        "uf", 7, "ES", None
    )
    assert corpo["rs_m2"] == 40.0


def test_uf_com_menos_de_cinco_cai_para_o_brasil(client: TestClient) -> None:
    corpo = client.get(ROTA, params={"tipo": "loja", **VITORIA}, headers=AUTH).json()
    assert (corpo["nivel"], corpo["n_anuncios"], corpo["uf"]) == ("brasil", 6, None)


@pytest.mark.parametrize("tipo", ["terreno", "Galpão", ""])
def test_tipo_fora_dos_tres_422(client: TestClient, tipo: str) -> None:
    resp = client.get(ROTA, params={"tipo": tipo, **VITORIA}, headers=AUTH)
    assert resp.status_code == 422


def test_sem_base_503_com_codigo(dados: dict[str, Path]) -> None:
    for base in (None, dados["anuncios"].with_name("nao-existe.parquet")):
        resp = _cliente(dados, base=base).get(ROTA, params={"tipo": "galpao", **VITORIA}, headers=AUTH)
        assert resp.status_code == 503, base
        assert resp.json()["codigo"] == "aluguel_referencia_indisponivel"


def test_ponto_fora_da_malha_400_como_o_analisar(client: TestClient) -> None:
    resp = client.get(ROTA, params={"tipo": "galpao", **NO_MAR}, headers=AUTH)
    assert resp.status_code == 400
    assert resp.json()["codigo"] == "coordenada_invalida"


def test_mesma_regua_que_a_rota_do_site(
    client: TestClient, dados: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    servidor = Path(__file__).resolve().parents[2] / "web" / "server"
    if str(servidor) not in sys.path:
        sys.path.insert(0, str(servidor))
    import app as site  # backend do piloto (web/server)

    from motor_expansao.dimensionamento.aluguel_referencia import carregar_tabela

    tabela = carregar_tabela(dados["anuncios"])
    monkeypatch.setattr(site, "_tabela_aluguel", lambda: tabela)
    for tipo, ponto, municipio in (
        ("galpao", VITORIA, "Vitória"),
        ("galpao", CARIACICA, "Cariacica"),
        ("loja", VITORIA, "Vitória"),
    ):
        publico = client.get(ROTA, params={"tipo": tipo, **ponto}, headers=AUTH).json()
        assert publico == site.aluguel_referencia(tipo=tipo, uf="ES", municipio=municipio)
