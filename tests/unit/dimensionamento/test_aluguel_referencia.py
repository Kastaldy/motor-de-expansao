"""DEC-080: régua de aluguel por município × tipo, com fallback UF e Brasil."""

from __future__ import annotations

import pandas as pd

from motor_expansao.dimensionamento.aluguel_referencia import (
    MIN_ANUNCIOS,
    TabelaAluguel,
    bloco_do_pdf,
    diferenca_da_faixa_pct,
    normalizar_nome,
    texto_da_diferenca,
)


def _anuncios(uf: str, municipio: str, tipo: str, rs_m2: list[float]) -> list[dict]:
    return [
        {"uf": uf, "municipio": municipio, "tipo": tipo, "area_relevante_m2": 1000.0,
         "preco_aluguel": v * 1000.0, "status": "ativo"}
        for v in rs_m2
    ]


def _tabela(*grupos: list[dict]) -> TabelaAluguel:
    return TabelaAluguel(pd.DataFrame([linha for g in grupos for linha in g]))


def test_corte_e_cinco_anuncios():
    assert MIN_ANUNCIOS == 5


def test_municipio_com_cinco_anuncios_usa_a_mediana_da_cidade():
    t = _tabela(
        _anuncios("ES", "Vitória", "comercial", [10, 20, 30, 40, 50]),
        _anuncios("ES", "Serra", "comercial", [100] * 10),
    )
    r = t.consultar("comercial", "ES", "vitoria")
    assert (r.nivel, r.rs_m2, r.n_anuncios, r.municipio) == ("municipio", 30.0, 5, "Vitória")


def test_cidade_com_quatro_cai_para_a_uf_do_mesmo_tipo():
    t = _tabela(
        _anuncios("ES", "Vitória", "galpao", [10, 20, 30, 40]),
        _anuncios("ES", "Serra", "galpao", [50] * 3),
        _anuncios("ES", "Vitória", "comercial", [999] * 9),
    )
    r = t.consultar("galpao", "ES", "Vitória")
    assert (r.nivel, r.n_anuncios, r.uf, r.municipio) == ("uf", 7, "ES", None)
    assert r.rs_m2 == 40.0


def test_uf_sem_cinco_cai_para_o_brasil():
    t = _tabela(
        _anuncios("AC", "Rio Branco", "loja", [10, 20]),
        _anuncios("SP", "Campinas", "loja", [30, 30, 30, 30]),
    )
    r = t.consultar("loja", "AC", "Rio Branco")
    assert (r.nivel, r.n_anuncios, r.uf) == ("brasil", 6, None)


def test_mediana_e_nao_media_e_descarta_fora_de_3_a_400():
    t = _tabela(_anuncios("SP", "Campinas", "loja", [10, 11, 12, 13, 300, 1.0, 900]))
    r = t.consultar("loja", "SP", "Campinas")
    assert r.n_anuncios == 5
    assert r.rs_m2 == 12.0


def test_tipo_desconhecido_ou_base_vazia_devolve_none():
    t = _tabela(_anuncios("SP", "Campinas", "loja", [10] * 5))
    assert t.consultar("terreno", "SP", "Campinas") is None
    assert TabelaAluguel(pd.DataFrame()).consultar("loja", "SP", "Campinas") is None


def test_normalizar_nome_casa_sem_acento_e_caixa():
    assert normalizar_nome("  São   Paulo ") == normalizar_nome("SAO PAULO") == "SAO PAULO"


def test_faixa_e_o_p25_e_o_p75_do_mesmo_recorte():
    t = _tabela(_anuncios("ES", "Vitória", "comercial", [10, 20, 30, 40, 50]))
    r = t.consultar("comercial", "ES", "Vitória")
    assert (r.rs_m2_p25, r.rs_m2, r.rs_m2_p75) == (20.0, 30.0, 40.0)
    assert r.para_dict()["rs_m2_p25"] == 20.0 and r.para_dict()["rs_m2_p75"] == 40.0


def test_comparacao_contra_a_faixa_espelha_o_front():
    # Os mesmos casos de `aluguel-referencia.test.ts`: tela e PDF dizem a mesma frase.
    faixa = (27600, 43700)
    assert diferenca_da_faixa_pct(48000, faixa) == 10
    assert diferenca_da_faixa_pct(22000, faixa) == -20
    assert diferenca_da_faixa_pct(30000, faixa) == 0
    assert diferenca_da_faixa_pct(43700, faixa) == 0
    assert diferenca_da_faixa_pct(43800, faixa) == 1
    assert diferenca_da_faixa_pct(27500, faixa) == -1
    assert texto_da_diferenca(10) == "10% acima da faixa"
    assert texto_da_diferenca(-20) == "20% abaixo da faixa"
    assert texto_da_diferenca(0) == "dentro da faixa"


def test_bloco_do_pdf_so_compara_com_aluguel_digitado():
    t = _tabela(_anuncios("ES", "Vitória", "comercial", [10, 20, 30, 40, 50]))
    sem = bloco_do_pdf(t, "comercial", "ES", "Vitória", 1500, None)
    assert (sem["faixa_min"], sem["faixa_max"]) == (30000, 60000)
    assert sem["base"] == "Base: 5 anúncios de laje corporativa em Vitória/ES"
    assert sem["comparacao"] is None and sem["diferenca_pct"] is None
    assert sem["mediana"] == 45000 and sem["diferenca_mediana_pct"] is None
    com = bloco_do_pdf(t, "comercial", "ES", "Vitória", 1500, 66000)
    assert com["comparacao"] == "47% acima da mediana · 10% acima da faixa"
    assert (com["diferenca_pct"], com["diferenca_mediana_pct"]) == (10, 47)
    dentro = bloco_do_pdf(t, "comercial", "ES", "Vitória", 1500, 45000)
    assert dentro["comparacao"] == "na mediana · dentro da faixa"


def test_bloco_do_pdf_sem_tabela_tipo_ou_metragem_e_none():
    t = _tabela(_anuncios("ES", "Vitória", "comercial", [10] * 5))
    assert bloco_do_pdf(None, "comercial", "ES", "Vitória", 1500, None) is None
    assert bloco_do_pdf(t, None, "ES", "Vitória", 1500, None) is None
    assert bloco_do_pdf(t, "comercial", "ES", "Vitória", 0, None) is None


def test_faixa_do_pdf_parte_do_rs_m2_que_a_tela_recebe():
    # p25 = 53,3651 x 1.500 m²: cru dá R$ 80.000; a tela, com 53,37, dá R$ 80.100.
    from motor_expansao.dimensionamento.aluguel_referencia import Referencia, faixa_mensal

    ref = Referencia("loja", 60.0, 9, "uf", "SP", None, 53.3651, 70.0)
    assert faixa_mensal(ref, 1500) == (80100, 105000)


def test_comparacao_contra_a_mediana_espelha_o_front():
    from motor_expansao.dimensionamento.aluguel_referencia import (
        diferenca_da_mediana_pct,
        texto_da_diferenca_mediana,
    )

    assert diferenca_da_mediana_pct(48000, 33800) == 42
    assert diferenca_da_mediana_pct(30000, 33800) == -11
    assert diferenca_da_mediana_pct(33800, 33800) == 0
    assert texto_da_diferenca_mediana(42) == "42% acima da mediana"
    assert texto_da_diferenca_mediana(-11) == "11% abaixo da mediana"
    assert texto_da_diferenca_mediana(0) == "na mediana"
