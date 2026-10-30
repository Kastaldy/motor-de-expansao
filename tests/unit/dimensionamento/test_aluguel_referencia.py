"""DEC-080: régua de aluguel por município × tipo, com fallback UF e Brasil."""

from __future__ import annotations

import pandas as pd

from motor_expansao.dimensionamento.aluguel_referencia import (
    MIN_ANUNCIOS,
    TabelaAluguel,
    normalizar_nome,
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
