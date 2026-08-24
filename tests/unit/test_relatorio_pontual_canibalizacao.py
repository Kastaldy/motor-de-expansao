"""Alerta de CANIBALIZACAO no parecer do Relatorio Pontual.

A rede propria dentro do raio do estudo precisa aparecer no parecer. O dado ja existe --
`censo_point` devolve `n_ultra` e `ultra_raio` (com `dist_km`, ordenado) --, entao nada
de pipeline muda aqui.

ENTRA COMO RESSALVA, nao como eliminatorio (decisao de Juan, 2026-08-21): rebaixa para
"Aprovado com ressalvas" e nomeia a distancia, sem reprovar o ponto sozinho. Coerente com
a DEC-007, que tirou a canibalizacao do gate do SAM -- o projeto ja decidiu uma vez que
proximidade da rede propria informa, nao bloqueia.
"""

from __future__ import annotations

import pandas as pd

from motor_expansao.dashboard.censo_report import (
    CONCLUSAO_APROVADO,
    CONCLUSAO_RESSALVAS,
    _avaliar_conclusao,
    _conclusao_canibalizacao,
)

_RESULT_OK = {
    "pop_total_raio": 20_000,
    "renda_per_capita_media_raio": 3_000.0,
    "domicilios_total_raio": 8_000,
    "renda_domiciliar_total_raio": 9_000.0,
    "n_concorrentes": 2,
}
_RESIDUAL_OK = {
    "sam_fitness_potencial": 12_000,
    "oferta_efetiva_disponivel": 9_000,
    "oferta_consumida_mercado_estimada": 3_000,
}


def _parecer(result_extra: dict) -> object:
    return _avaliar_conclusao(
        {**_RESULT_OK, **result_extra}, _RESIDUAL_OK, None, {}, somente_estudo=True
    )


def test_sem_ultra_no_raio_nao_ha_alerta():
    assert _conclusao_canibalizacao({"n_ultra": 0}) is None
    assert _parecer({"n_ultra": 0}).demografico.status == CONCLUSAO_APROVADO


def test_uma_ultra_no_raio_diz_a_distancia():
    texto = _conclusao_canibalizacao(
        {"n_ultra": 1, "ultra_raio": pd.DataFrame({"dist_km": [0.42]})}
    )
    assert texto == (
        "Canibalização da rede: 1 unidade Ultra dentro do raio do estudo; "
        "a unidade está a 420 m do ponto."
    )


def test_varias_ultra_reportam_a_mais_proxima():
    texto = _conclusao_canibalizacao(
        {"n_ultra": 3, "ultra_raio": pd.DataFrame({"dist_km": [0.18, 0.55, 0.91]})}
    )
    assert texto == (
        "Canibalização da rede: 3 unidades Ultra dentro do raio do estudo; "
        "a mais próxima está a 180 m do ponto."
    )


def test_sem_distancia_o_alerta_ainda_sai_pela_contagem():
    # `ultra_raio` ausente (chamada antiga, ou parquet sem a coluna): o alerta nao pode
    # sumir por causa disso -- perde a distancia, nao o aviso.
    assert _conclusao_canibalizacao({"n_ultra": 2}) == (
        "Canibalização da rede: 2 unidades Ultra dentro do raio do estudo."
    )


def test_alerta_rebaixa_o_selo_para_ressalvas():
    parecer = _parecer({"n_ultra": 1, "ultra_raio": pd.DataFrame({"dist_km": [0.42]})})
    assert parecer.demografico.status == CONCLUSAO_RESSALVAS
    assert any("Canibalização" in item for item in parecer.demografico.ressalvas)


def test_alerta_vai_para_a_pagina_do_imovel(monkeypatch):
    """A faixa vermelha no pe da pagina "Imovel - Informacoes" (pedido de Juan)."""
    from motor_expansao.dashboard import censo_report

    capturado: dict[str, object] = {}
    original = censo_report._info_imovel_page

    def _espiao(pdf, info_imovel, assets, **kwargs):
        capturado.update(kwargs)
        return original(pdf, info_imovel, assets, **kwargs)

    monkeypatch.setattr(censo_report, "_info_imovel_page", _espiao)
    censo_report.gerar_pdf_relatorio_pontual_classico(
        {
            "lat": -23.55,
            "lng": -46.63,
            "nome_municipio": "SAO PAULO",
            "uf": "SP",
            "raio_km": 1.0,
            "n_ultra": 2,
            "ultra_raio": pd.DataFrame({"dist_km": [0.38, 0.72]}),
        },
        None,
        info_imovel={"metragem_m2": 1_800},
    )
    assert capturado["alerta_canibalizacao"] == (
        "Canibalização da rede: 2 unidades Ultra dentro do raio do estudo; "
        "a mais próxima está a 380 m do ponto."
    )


def test_sem_ultra_a_pagina_do_imovel_nao_ganha_faixa(monkeypatch):
    from motor_expansao.dashboard import censo_report

    capturado: dict[str, object] = {}
    original = censo_report._info_imovel_page

    def _espiao(pdf, info_imovel, assets, **kwargs):
        capturado.update(kwargs)
        return original(pdf, info_imovel, assets, **kwargs)

    monkeypatch.setattr(censo_report, "_info_imovel_page", _espiao)
    censo_report.gerar_pdf_relatorio_pontual_classico(
        {
            "lat": -23.55,
            "lng": -46.63,
            "nome_municipio": "SAO PAULO",
            "uf": "SP",
            "raio_km": 1.0,
            "n_ultra": 0,
        },
        None,
        info_imovel={"metragem_m2": 1_800},
    )
    assert capturado["alerta_canibalizacao"] is None
