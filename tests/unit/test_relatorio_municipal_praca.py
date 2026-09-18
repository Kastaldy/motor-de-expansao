"""As quatro paginas da praca no Relatorio Municipal (pedido do Felipe, 2026-09-10).

Mapas de calor da cidade (renda domiciliar e densidade), pressao concorrencial da cidade inteira,
onde crescer (5 hexagonos) e como a cidade esta indo. So' entram com `praca=`; sem ela o PDF fica
igual. O preparo e' o de `service.montar_pdf_municipio`, que motor e bot compartilham. NENHUM
teste bate na rede.
"""

from __future__ import annotations

from io import BytesIO

import h3
import numpy as np
import pandas as pd
import pytest
from PIL import Image

from motor_expansao.dashboard import relatorio_praca as rp
from motor_expansao.dashboard import relatorio_praca_mapas as rpm
from motor_expansao.dashboard.relatorio_municipal import (
    PDF_SECTION_HEADERS,
    agregar_municipio,
    gerar_payloads_download_relatorio_municipal,
    gerar_pdf_relatorio_municipal,
)
from motor_expansao.dashboard.relatorio_praca import (
    TITULO_COMO_A_CIDADE_ESTA_INDO,
    TITULO_MAPAS_CALOR_CIDADE,
    TITULO_ONDE_CRESCER,
    TITULO_PRESSAO_CONCORRENCIAL,
    PracaDaCidade,
)

_LAT, _LNG = -23.55, -46.63  # Sao Paulo
_GRAU_LAT_M = 111_195.0
_TITULOS = (
    TITULO_MAPAS_CALOR_CIDADE,
    TITULO_PRESSAO_CONCORRENCIAL,
    TITULO_ONDE_CRESCER,
    TITULO_COMO_A_CIDADE_ESTA_INDO,
)


def _df_cidade(anel: int = 2) -> pd.DataFrame:
    centro = h3.latlng_to_cell(_LAT, _LNG, 7)
    celulas = sorted(h3.grid_disk(centro, anel))
    n = len(celulas)
    return pd.DataFrame(
        {
            "hex_id": celulas,
            "nome_municipio": "SAO PAULO",
            "uf": "SP",
            "oferta_efetiva_disponivel": [500.0 + 800.0 * i for i in range(n)],
            "score_setor_2022_calibrado": [20.0 + 3.0 * (i % 20) for i in range(n)],
            "pop_total_setor_2022": [1_000.0 + 100.0 * i for i in range(n)],
            "sam_fitness_potencial": 4000.0,
            "renda_per_capita": 3000.0,
            "pop_total": 2000.0,
            "score_oportunidade_residual": 50.0,
            "penetracao_fitness_mercado_estimada": 12.5,
            "oferta_consumida_mercado_estimada": 300.0,
        }
    )


def _png() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (1400, 1000), (0, 167, 157)).save(buf, format="PNG")
    return buf.getvalue()


def _praca(df: pd.DataFrame, **kw) -> PracaDaCidade:
    renda = {h: 1_000.0 + 250.0 * i for i, h in enumerate(df["hex_id"])}
    hexes = rp.preparar_hexes_da_cidade(df, renda)
    conc = pd.DataFrame({"rede": ["smart_fit", "smart_fit", None], "lat": [_LAT, _LAT + 0.003, _LAT - 0.02],
                         "lng": [_LNG, _LNG, _LNG]})
    base = dict(
        municipio="São Paulo",
        uf="SP",
        onde_crescer=rp.selecionar_onde_crescer(hexes),
        pressao=rp.pressao_na_cidade(hexes, conc, None),
        crescimento=rp.resumir_crescimento({"cres_tendencia": "Em alta", "v_frase": "Cidade em alta."}, uf="SP"),
        mapas={k: _png() for k in ("calor_cidade_renda_domiciliar", "calor_cidade_densidade", "pressao_cidade", "onde_crescer")},
        n_hexagonos_cidade=len(hexes),
    )
    base.update(kw)
    return PracaDaCidade(**base)


# --------------------------------------------------------------------------- #
# Preparo                                                                     #
# --------------------------------------------------------------------------- #
def test_preparo_usa_renda_domiciliar_densidade_do_hexagono_e_indice_do_funil():
    from motor_expansao.dashboard import praca_indice

    df = _df_cidade(1)
    renda = {df["hex_id"].iloc[0]: 4_321.0}
    hexes = rp.preparar_hexes_da_cidade(df, renda)

    assert "renda_domiciliar" not in df.columns  # frame novo: o de entrada nao muda
    assert hexes["renda_domiciliar"].iloc[0] == 4_321.0
    assert hexes["renda_domiciliar"].iloc[1:].isna().all()  # sem renda no mapa = nula, nunca per capita

    area = h3.cell_area(df["hex_id"].iloc[0], unit="km^2")
    assert hexes["densidade_hab_km2"].iloc[0] == pytest.approx(1_000.0 / area)

    esperado = praca_indice.indice_praca(
        df["score_setor_2022_calibrado"], praca_indice.nota_demanda(df["oferta_efetiva_disponivel"])
    )
    np.testing.assert_allclose(hexes["indice_praca"].to_numpy(), esperado.to_numpy())

    sem_mapa = rp.preparar_hexes_da_cidade(df, None)
    assert sem_mapa["renda_domiciliar"].isna().all()
    assert rp.selecionar_onde_crescer(sem_mapa).aviso


def test_indice_do_web_e_o_mesmo_modulo():
    """O alias de `web/server` devolve o modulo de `src`: uma regua so' para funil e relatorio."""
    import importlib
    import sys
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[2] / "web" / "server"
    sys.path.insert(0, str(raiz))
    try:
        sys.modules.pop("praca_indice", None)
        web = importlib.import_module("praca_indice")
    finally:
        sys.path.remove(str(raiz))
    from motor_expansao.dashboard import praca_indice

    assert web is praca_indice


def test_linha_de_crescimento_casa_por_codigo_e_por_nome():
    cres = pd.DataFrame(
        {
            "cod6": ["355030", "330455"],
            "cres_chave_nome": ["SP|SAO PAULO", "RJ|RIO DE JANEIRO"],
            "cres_tendencia": ["Em alta", "Estavel"],
        }
    )
    assert rp.linha_crescimento_municipal(cres, uf="SP", cod_municipio="3550308", nome_municipio=None)["cres_tendencia"] == "Em alta"
    por_nome = rp.linha_crescimento_municipal(cres, uf="rj", cod_municipio=None, nome_municipio="Rio de Janeiro")
    assert por_nome["cres_tendencia"] == "Estavel"
    assert rp.linha_crescimento_municipal(cres, uf="SP", cod_municipio="9999999", nome_municipio="Nenhuma") is None
    assert rp.linha_crescimento_municipal(None, uf="SP", cod_municipio="3550308", nome_municipio=None) is None


# --------------------------------------------------------------------------- #
# Pressao da cidade                                                           #
# --------------------------------------------------------------------------- #
def test_pressao_da_cidade_conta_cobertura_e_sobreposicao():
    df = _df_cidade(3)
    centro = h3.latlng_to_cell(_LAT, _LNG, 7)
    lat_c, lng_c = h3.cell_to_latlng(centro)
    # tres academias a <= 200 m do centro do hexagono central: ele fica com 3 discos
    conc = pd.DataFrame(
        {
            "rede": ["smart_fit", "bio_ritmo", None],
            "lat": [lat_c, lat_c + 150 / _GRAU_LAT_M, lat_c - 150 / _GRAU_LAT_M],
            "lng": [lng_c, lng_c, lng_c],
        }
    )
    ultra = pd.DataFrame({"lat": [lat_c + 50 / _GRAU_LAT_M], "lng": [lng_c]})
    p = rp.pressao_na_cidade(df, conc, ultra)

    assert p.raio_m == rp.RAIO_INFLUENCIA_M
    assert (p.n_concorrentes, p.n_ultra, p.n_independentes) == (3, 1, 1)
    assert p.redes == [("bio_ritmo", 1), ("smart_fit", 1)]
    assert p.n_hexagonos == len(df)
    discos = rp.discos_por_hexagono(df, pd.concat([conc, ultra]))
    assert discos[df["hex_id"].tolist().index(centro)] == 4
    assert p.max_discos_no_hex == 4
    assert p.n_hex_disputados >= 1
    # res-7 tem ~1,2 km entre centros: 1 km alcanca o centro vizinho so' em parte dos casos, e
    # nunca os hexagonos do anel 3
    assert 1 <= p.n_hex_cobertos < len(df)
    assert p.pct_coberto == pytest.approx(100.0 * p.n_hex_cobertos / len(df))


def test_pressao_da_cidade_sem_academia():
    p = rp.pressao_na_cidade(_df_cidade(1), None, None)
    assert (p.n_concorrentes, p.n_hex_cobertos, p.max_discos_no_hex) == (0, 0, 0)
    vazio = rp.pressao_na_cidade(None, None, None)
    assert vazio.pct_coberto is None


# --------------------------------------------------------------------------- #
# Mapas                                                                       #
# --------------------------------------------------------------------------- #
def test_mapas_da_cidade_saem_sem_ponto():
    df = _df_cidade(2)
    hexes = rp.preparar_hexes_da_cidade(df, {h: 1_000.0 * (i + 1) for i, h in enumerate(df["hex_id"])})
    png = rpm.render_calor_cidade(
        hexes, "renda_domiciliar", titulo="Renda", legenda_titulo="R$", formatar=str,
        paleta=rpm.PALETA_RENDA, basemap=False,
    )
    assert png and Image.open(BytesIO(png)).size == (1400, 1000)
    top = rp.selecionar_onde_crescer(hexes).hexagonos
    assert rpm.render_onde_crescer(hexes, top, basemap=False)

    conc = pd.DataFrame({"rede": ["smart_fit", None], "lat": [_LAT, _LAT + 0.004], "lng": [_LNG, _LNG]})
    assert rpm.render_pressao_cidade(hexes, conc, None, basemap=False)
    assert rpm.render_pressao_cidade(None, conc, None, basemap=False) is None


def test_pressao_da_cidade_troca_logo_por_ponto_quando_ha_academia_demais():
    from unittest import mock

    df = _df_cidade(2)
    poucas = pd.DataFrame({"rede": ["smart_fit"] * 3, "lat": [_LAT] * 3, "lng": [_LNG] * 3})
    muitas = pd.DataFrame(
        {"rede": ["smart_fit"] * (rpm.LOGOS_MAX_CIDADE + 1), "lat": _LAT, "lng": _LNG}
    )
    with mock.patch.object(rpm, "_paste_logo_pin") as colar:
        rpm.render_pressao_cidade(df, poucas, None, basemap=False)
        assert colar.call_count == 3
        colar.reset_mock()
        rpm.render_pressao_cidade(df, muitas, None, basemap=False)
        assert colar.call_count == 0


# --------------------------------------------------------------------------- #
# PDF                                                                         #
# --------------------------------------------------------------------------- #
def _resultado(df: pd.DataFrame) -> dict:
    return agregar_municipio(df, nome_municipio="SAO PAULO", uf="SP")


def test_pdf_municipal_ganha_as_quatro_paginas():
    df = _df_cidade(2)
    res = _resultado(df)
    sem = gerar_pdf_relatorio_municipal(res, None)
    com = gerar_pdf_relatorio_municipal(res, None, praca=_praca(df))

    n_sem = int(sem.split(b"/Count ")[1].split(maxsplit=1)[0])
    assert f"/Count {n_sem + 4}".encode() in com
    for titulo in _TITULOS:
        assert titulo.encode("latin-1") in com, titulo
        assert titulo.encode("latin-1") not in sem, titulo
        # condicionais: fora da tupla canonica
        assert titulo not in PDF_SECTION_HEADERS

    # mesma ordem das paginas que o docstring promete: cada titulo aparece DEPOIS do anterior
    # (busca encadeada -- "Score Censitário" tambem e' citado antes da propria pagina)
    pos = 0
    for t in ("Score Censitário", TITULO_MAPAS_CALOR_CIDADE, "Residual Fitness", TITULO_PRESSAO_CONCORRENCIAL,
              "Expansão de Domínio", TITULO_ONDE_CRESCER, TITULO_COMO_A_CIDADE_ESTA_INDO, "Síntese"):
        pos = com.index(t.encode("latin-1"), pos) + 1


def test_payload_repassa_a_praca():
    df = _df_cidade(1)
    payload = gerar_payloads_download_relatorio_municipal(_resultado(df), None, praca=_praca(df))
    assert TITULO_ONDE_CRESCER.encode("latin-1") in payload.pdf_bytes


def test_pdf_onde_crescer_mostra_bairro_criterio_e_rede_pelo_rotulo():
    df = _df_cidade(2)
    res = _resultado(df)
    praca = _praca(df)
    primeiro = praca.onde_crescer.hexagonos["hex_id"].iloc[0]
    res = {**res, "bairros_por_hex": {primeiro: "Pinheiros"}}
    pdf = gerar_pdf_relatorio_municipal(res, None, praca=praca)
    assert b"Pinheiros" in pdf
    assert "índice de praça".encode("latin-1") in pdf
    assert b"Smart Fit" in pdf  # a pagina de pressao lista a rede pelo rotulo, nao pelo slug


def test_pdf_municipal_sem_crescimento_e_sem_elegivel_explica():
    df = _df_cidade(1)
    hexes = rp.preparar_hexes_da_cidade(df, None)
    praca = _praca(
        df,
        onde_crescer=rp.selecionar_onde_crescer(hexes),
        crescimento=rp.resumir_crescimento(None),
        mapas={},
    )
    pdf = gerar_pdf_relatorio_municipal(_resultado(df), None, praca=praca)
    assert rp.TEXTO_SEM_CRESCIMENTO.encode("latin-1") in pdf
    assert "Nenhum hexágono passou".encode("latin-1") in pdf
    assert "Mapa indisponível".encode("latin-1") in pdf


# --------------------------------------------------------------------------- #
# Preparo unico (service)                                                     #
# --------------------------------------------------------------------------- #
def test_service_monta_a_praca_com_crescimento_da_staging(tmp_path, monkeypatch):
    from motor_expansao.api import service
    from motor_expansao.api.settings import Settings

    df = _df_cidade(1).assign(cod_municipio="3550308")
    pd.DataFrame(
        {"cod6": ["355030"], "cres_chave_nome": ["SP|SAO PAULO"], "cres_tendencia": ["Em alta"],
         "v_frase": ["Cidade em alta."]}
    ).to_parquet(tmp_path / "crescimento_municipal.parquet")
    settings = Settings(staging_dir=tmp_path)
    conc = pd.DataFrame({"rede": ["smart_fit", "smart_fit"], "lat": [_LAT, -10.0], "lng": [_LNG, -40.0]})

    praca = service._praca_da_cidade(
        df, uf="SP", nome_municipio="São Paulo", cod="3550308", comp_df=conc, ultra_df=None,
        poligono=None, renda_dom={h: 2_000.0 + i for i, h in enumerate(df["hex_id"])},
        settings=settings, basemap=False,
    )
    assert praca.crescimento.disponivel
    assert dict(praca.crescimento.linhas)["Tendência do emprego formal"] == "Em alta"
    assert praca.pressao.n_concorrentes == 1  # a academia de fora do municipio nao entra
    assert set(praca.mapas) == {"calor_cidade_renda_domiciliar", "calor_cidade_densidade", "pressao_cidade", "onde_crescer"}
    assert len(praca.onde_crescer.hexagonos) >= 1


# --------------------------------------------------------------------------- #
# Pins nos mapas tematicos                                                    #
# --------------------------------------------------------------------------- #
def test_score_e_residual_saem_sem_pins(monkeypatch):
    """Em capital as logos cobriam os hexagonos: score e residual ficam so' com a cor."""
    from motor_expansao.dashboard import relatorio_municipal as relmun

    recebidos: dict[str, object] = {}

    def _render(df, *, camada, competitors_df=None, ultra_df=None, **k):
        recebidos[camada] = (competitors_df, ultra_df)
        return b"PNG"

    monkeypatch.setattr(relmun, "_render_mapa_municipio", _render)
    monkeypatch.setattr(relmun, "_render_mapa_bairros", lambda *a, **k: b"PNG")
    df = _df_cidade(1)
    conc = pd.DataFrame({"rede": ["smart_fit"], "lat": [_LAT], "lng": [_LNG]})
    ultra = pd.DataFrame({"lat": [_LAT], "lng": [_LNG]})
    relmun.render_mapas_municipio(df, {"zonas": []}, competitors_df=conc, ultra_df=ultra)

    assert recebidos["score"] == (None, None)
    assert recebidos["residual"] == (None, None)
    assert recebidos["cobertura"] == (None, None)
    for camada in ("resumo", "dominio"):
        c, u = recebidos[camada]
        assert c is not None and len(c) == 1 and u is not None and len(u) == 1


def test_mapas_tematicos_so_desenham_ultra_e_as_maiores_redes(monkeypatch):
    """Sao Paulo tem 491 concorrentes: os mapas ficam com a Ultra e as 5 maiores redes, e o
    rodape do PNG diz quais sao."""
    from motor_expansao.dashboard import relatorio_municipal as relmun

    recebidos: dict[str, tuple] = {}

    def _render(df, *, camada, competitors_df=None, ultra_df=None, nota_pins=None, **k):
        recebidos[camada] = (competitors_df, nota_pins, k.get("hexes_rotulados"))
        return b"PNG"

    monkeypatch.setattr(relmun, "_render_mapa_municipio", _render)
    monkeypatch.setattr(relmun, "_render_mapa_bairros", lambda *a, **k: b"PNG")
    redes = ["smart_fit"] * 9 + ["bluefit"] * 7 + ["selfit"] * 5 + ["panobianco"] * 4 + ["gavioes"] * 3 + ["pequena"] * 2
    conc = pd.DataFrame({"rede": redes + [None], "lat": _LAT, "lng": _LNG})
    ultra = pd.DataFrame({"lat": [_LAT], "lng": [_LNG]})
    top5 = {"h_a", "h_b"}

    relmun.render_mapas_municipio(
        _df_cidade(1), {"zonas": []}, competitors_df=conc, ultra_df=ultra, hexes_rotulados=top5
    )

    assert relmun.principais_redes(conc) == ["smart_fit", "bluefit", "selfit", "panobianco", "gavioes"]
    pins, nota, rotulados = recebidos["resumo"]
    assert len(pins) == 28  # 9+7+5+4+3; a rede pequena e a independente ficam de fora
    assert set(pins["rede"]) == {"smart_fit", "bluefit", "selfit", "panobianco", "gavioes"}
    assert nota is not None and "5 maiores redes" in nota and "29 de 32" in nota  # 28 concorrentes das 5 redes + 1 Ultra, de 31 + 1 and "Smart Fit" in nota and "pequena" not in nota
    assert rotulados == top5
    # mapa sem pins nao promete recorte de academia nenhum
    assert recebidos["score"][0] is None and recebidos["score"][1] is None
    assert recebidos["score"][2] == top5

    # municipio so' com independentes: nao ha o que recortar, o frame passa inteiro
    so_indep = pd.DataFrame({"rede": [None, None], "lat": _LAT, "lng": _LNG})
    assert relmun.principais_redes(so_indep) == []
    assert len(relmun._so_as_principais(so_indep, [])) == 2


def test_mapa_do_resumo_sai_sem_o_numero_em_cada_hexagono(monkeypatch):
    """Sao Paulo tinha 154 plaquinhas de Residual sobre os hexagonos. O relatorio passa a pedir
    o mapa sem elas; quem chama o render direto continua com o de antes."""
    from motor_expansao.dashboard import relatorio_municipal as relmun

    vistos: dict[str, object] = {}

    def _render(df, *, camada, rotular_valores=True, **k):
        vistos[camada] = rotular_valores
        return b"PNG"

    monkeypatch.setattr(relmun, "_render_mapa_municipio", _render)
    monkeypatch.setattr(relmun, "_render_mapa_bairros", lambda *a, **k: b"PNG")
    relmun.render_mapas_municipio(_df_cidade(1), {"zonas": []})
    assert vistos["resumo"] is False
