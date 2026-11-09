"""Paginas da praca no PDF Pontual da API (`paginas_praca`, emenda de 2026-11-09 da DEC-005).

O site gera "Pressao concorrencial" e "Como a cidade esta indo" desde 2026-09-17; a API passa a
gerar as duas so' a pedido, pela MESMA montagem (`praca_do_ponto.montar_praca_do_ponto`). O bot
do Telegram chama a mesma rota sem o campo e segue com o PDF de sempre.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from motor_expansao import recomendacao
from motor_expansao.api import service
from motor_expansao.api.schemas import AnalisarRequest
from motor_expansao.api.settings import Settings
from motor_expansao.dashboard import relatorio_praca as rp
from motor_expansao.dashboard import relatorio_praca_mapas as rpm

# A montagem da suite do piloto: `pilot` (o app com web/server no sys.path) e as fixtures de
# dado sintetico do passo 4 (enriquecido de SP + os dois artefatos de crescimento).
from tests.unit.test_piloto_web_crescimento import com_crescimento  # noqa: F401
from tests.unit.test_piloto_web_endpoints import pilot, synth_data  # noqa: F401

_LAT, _LNG = -23.55, -46.63
_SENTINELA = object()


# --------------------------------------------------------------------------- #
# Contrato: o campo e' opt-in                                                 #
# --------------------------------------------------------------------------- #
def test_campo_e_opt_in() -> None:
    assert AnalisarRequest(lat=_LAT, lng=_LNG).paginas_praca is False
    assert AnalisarRequest(lat=_LAT, lng=_LNG, paginas_praca=True).paginas_praca is True


def test_rota_repassa_o_campo(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from motor_expansao.api.main import create_app
    from motor_expansao.api.routes import analisar as rota

    vistos: list[dict] = []

    def _pdf(lat, lng, consumidor, settings, **kw):
        vistos.append(kw)
        return b"%PDF-1.4 stub"

    monkeypatch.setattr(rota, "gerar_pdf_ponto", _pdf)
    cliente = TestClient(create_app())
    auth = {"Authorization": "Bearer dev-token"}
    for corpo, esperado in (({}, False), ({"paginas_praca": True}, True)):
        resp = cliente.post(
            "/api/v1/analisar", json={"lat": _LAT, "lng": _LNG, "formato": "pdf", **corpo}, headers=auth
        )
        assert resp.status_code == 200, resp.text
        assert vistos[-1]["paginas_praca"] is esperado


# --------------------------------------------------------------------------- #
# gerar_pdf_ponto: sem o campo o gerador nem recebe `praca`                   #
# --------------------------------------------------------------------------- #
@pytest.fixture
def gerador(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    """Carga, motor, mapas, mercado e gerador trocados por stubs; guarda os kwargs do gerador."""
    from motor_expansao.dashboard import censo_map, censo_point, censo_report

    visto: dict = {"gerador": [], "praca": []}
    setores = pd.DataFrame({"cod_setor": ["355030801000001"], "nome_municipio": ["São Paulo"]})

    def _gerar(result, mapas, **kw):
        visto["gerador"].append(kw)
        return b"%PDF-1.4 stub"

    monkeypatch.setattr(service, "_resolver_e_carregar", lambda lat, lng, cfg, **kw: ("SP", "3550308", setores))
    monkeypatch.setattr(service, "_competitors_ultra", lambda cfg: ("conc", "ultra"))
    monkeypatch.setattr(service, "_mercado_do_ponto", lambda *a, **k: {})
    monkeypatch.setattr(service, "_hexes_vizinhos_do_ponto", lambda *a, **k: None)
    monkeypatch.setattr(service, "_reuse_contextily_session", lambda: None)
    monkeypatch.setattr(censo_point, "analisar_ponto_censitario_setores", lambda *a, **k: {"pop_total_raio": 1000})
    monkeypatch.setattr(censo_point, "agregar_perfil_bairro_distrito", lambda *a, **k: None)
    monkeypatch.setattr(censo_map, "render_mapas_censitarios_combinados", lambda *a, **k: {"m": b""})
    monkeypatch.setattr(censo_map, "render_foto_satelite_ponto", lambda *a, **k: None)
    monkeypatch.setattr(censo_report, "gerar_pdf_relatorio_pontual_classico", _gerar)
    visto["settings"] = Settings(
        censo_geo_dir=tmp_path / "geo", ibge_dir=tmp_path / "ibge",
        ultra_dir=tmp_path / "ultra", staging_dir=tmp_path / "staging",
    )
    return visto


def test_sem_o_campo_o_gerador_nem_recebe_praca(gerador: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "_praca_do_ponto", lambda *a, **k: pytest.fail("montou a praca sem pedido"))
    service.gerar_pdf_ponto(_LAT, _LNG, "teste", gerador["settings"])
    assert "praca" not in gerador["gerador"][-1]


def test_com_o_campo_a_praca_chega_ao_gerador(gerador: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    def _praca(lat, lng, **kw):
        gerador["praca"].append(kw)
        return _SENTINELA

    monkeypatch.setattr(service, "_praca_do_ponto", _praca)
    service.gerar_pdf_ponto(_LAT, _LNG, "teste", gerador["settings"], paginas_praca=True)
    assert gerador["gerador"][-1]["praca"] is _SENTINELA
    kw = gerador["praca"][-1]
    assert (kw["uf"], kw["cod_municipio"], kw["nome_municipio"]) == ("SP", "3550308", "São Paulo")
    assert (kw["comp_df"], kw["ultra_df"]) == ("conc", "ultra"), "os pins tem de ser os do slide Concorrentes"
    assert kw["basemap"] is True


@pytest.mark.parametrize("falha", ["excecao", "sem_base"])
def test_falha_na_praca_nao_derruba_o_pdf(gerador: dict, monkeypatch: pytest.MonkeyPatch, falha: str) -> None:
    def _praca(*a, **k):
        if falha == "excecao":
            raise RuntimeError("parquet ilegivel")
        return None

    monkeypatch.setattr(service, "_praca_do_ponto", _praca)
    assert service.gerar_pdf_ponto(_LAT, _LNG, "teste", gerador["settings"], paginas_praca=True)
    assert "praca" not in gerador["gerador"][-1]


def test_sem_base_da_uf_a_api_omite_as_paginas(tmp_path: Path) -> None:
    cfg = Settings(censo_geo_dir=tmp_path / "outputs" / "geo", staging_dir=tmp_path / "staging")
    assert service._praca_do_ponto(
        _LAT, _LNG, uf="SP", cod_municipio=None, nome_municipio="São Paulo",
        comp_df=None, ultra_df=None, settings=cfg, basemap=False,
    ) is None


# --------------------------------------------------------------------------- #
# Paridade: o site e a API montam a MESMA praca com os mesmos dados           #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("com_regua", [True, False])
@pytest.mark.parametrize("municipio", ["Sao Paulo", "Campinas"])
@pytest.mark.parametrize("pelo_codigo", [False, True])
def test_site_e_api_montam_a_mesma_praca(
    com_crescimento: Path,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    com_regua: bool,
    municipio: str,
    pelo_codigo: bool,
) -> None:
    import h3

    regra = object() if com_regua else None
    monkeypatch.setattr(pilot, "_regra_recomendacao", lambda: regra)
    monkeypatch.setattr(recomendacao, "carregar_regra", lambda *a, **k: regra)
    monkeypatch.setattr(rpm, "render_pressao_raios", lambda *a, **k: b"png")
    for cache in (service._hexes_da_uf_para_praca, service._crescimento_hex_df, service._carregar_parquet_full):
        cache.cache_clear()

    df = pilot.carregar_uf("SP")
    linha = df[df["nome_municipio"] == municipio].iloc[1]
    lat, lng = float(linha["lat"]), float(linha["lng"])
    # Os hex_id da fixture nao sao celulas H3 de verdade: o ponto cai no hexagono da linha.
    monkeypatch.setattr(h3, "latlng_to_cell", lambda *a, **k: str(linha["hex_id"]))
    cod = str(linha["cod_municipio"]) if pelo_codigo else None
    conc = pd.DataFrame({"lat": [lat + 0.003, lat + 0.02], "lng": [lng, lng], "rede": ["Smart Fit", None]})
    ultra = pd.DataFrame({"lat": [lat - 0.004], "lng": [lng]})

    site = pilot._praca_para_pdf(lat, lng, "SP", cod, municipio, conc, ultra, basemap=False)
    api = service._praca_do_ponto(
        lat, lng, uf="SP", cod_municipio=cod, nome_municipio=municipio, comp_df=conc, ultra_df=ultra,
        settings=Settings(
            censo_geo_dir=com_crescimento / "outputs" / "setores_censitarios_2022_geo",
            staging_dir=com_crescimento / "staging",
        ),
        basemap=False,
    )
    for cache in (service._hexes_da_uf_para_praca, service._crescimento_hex_df, service._carregar_parquet_full):
        cache.cache_clear()

    assert site is not None and api is not None
    assert api == site
    # Nao e' paridade de dois vazios: os dois blocos sairam com dado. Excecao conhecida, a mesma
    # no site: Campinas nao tem tendencia na fixture, e com a regua (sem veredito) a cidade sai
    # "sem dado" -- o caso dos 39% do pais.
    if not (municipio == "Campinas" and com_regua):
        assert api.crescimento.disponivel and api.crescimento.frase
    assert api.crescimento_hex.disponivel and api.crescimento_hex.mediana_cidade_texto
    assert api.pressao.n_concorrentes_sobre_ponto == 1 and api.pressao.n_ultra_sobre_ponto == 1


# --------------------------------------------------------------------------- #
# A frase e' a do site, letra por letra                                       #
# --------------------------------------------------------------------------- #
def test_frase_da_mooca_e_a_do_pdf_do_site() -> None:
    """Pagina "Como a cidade esta indo" do PDF do site para a Mooca (09/11/2026)."""
    linha = {
        "cres_tendencia": "Estavel", "cres_emp_pct": 8.8, "cres_uf_mediana": 9.0,
        "cres_setor": "Serviços administrativos", "cres_salario": 3005.0, "cres_salario_var": 1.0,
        "cres_confiab": "alta", "v_frase": "São Paulo é praça para entrar.",
    }
    frase = rp.narrativa_crescimento(
        linha, "São Paulo", uf="SP", rotulo_tendencia=service._ROTULO_TENDENCIA, leitura=True
    )
    assert rp.texto_pdf(frase) == (
        "O emprego formal em São Paulo está estável: variou +8,8% desde dez/2022, abaixo da "
        "mediana de SP (+9,0%). O que mais puxa a abertura de empresas aqui é serviços "
        "administrativos. Quem é admitido entra ganhando R$ 3.005, +1,0% em relação ao ano "
        "anterior. CAGED e Receita Federal, até junho de 2026 - contexto sobre a praça."
    )


def test_site_e_api_leem_a_mesma_frase(com_crescimento: Path) -> None:  # noqa: F811
    """A tela do passo 4 (`app._narrativa_crescimento`) e a montagem do PDF leem a mesma redacao."""
    df = pilot.carregar_uf("SP")
    sp = df[df["nome_municipio"] == "Sao Paulo"]
    linha = {c: pilot._mun_val(sp, c) for c in rp.COLS_CRESCIMENTO_MUNICIPAL}
    for leitura in (True, False):
        assert pilot._narrativa_crescimento(sp, "Sao Paulo", leitura=leitura) == rp.narrativa_crescimento(
            linha, "Sao Paulo", uf="SP", rotulo_tendencia=service._ROTULO_TENDENCIA, leitura=leitura
        )
