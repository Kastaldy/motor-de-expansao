"""Composicao do investimento (obra x equipamentos) na pagina de Viabilidade.

O payload da API sempre trouxe `investimento.obra` e `investimento.equipamentos` -- sao
os dois valores que o operador DIGITA na tela --, mas `_viab_normalizado` nao os lia e o
PDF nunca os imprimia: o relatorio afirmava "investimento total X" sem dizer de que ele
e' feito. Estes testes travam a linha nova e a degradacao graciosa dela.
"""

from __future__ import annotations

from motor_expansao.dashboard.censo_report import (
    _viab_linha_composicao_investimento,
    _viab_linhas_detalhe,
    _viab_normalizado,
)

_PAYLOAD = {
    "investimento": {
        "obra": 850_000.0,
        "parcelas_obra": 4,
        "equipamentos": 620_000.0,
        "prazo_equipamentos": 48,
        "juros_equipamentos_am": 0.0149,
        "investimento_total": 1_470_000.0,
    }
}


def test_normalizado_passa_a_carregar_a_composicao():
    dados = _viab_normalizado(_PAYLOAD)
    assert dados["obra"] == 850_000.0
    assert dados["equipamentos"] == 620_000.0
    assert dados["parcelas_obra"] == 4
    assert dados["prazo_equipamentos"] == 48
    assert dados["juros_equipamentos_am"] == 0.0149


def test_linha_nomeia_as_duas_naturezas():
    linha = _viab_linha_composicao_investimento(_viab_normalizado(_PAYLOAD))
    assert linha == (
        "Investimento: obra R$ 850.000,00 (4x sem juros) + "
        "equipamentos R$ 620.000,00 (financiados em 48x a 1,5% a.m.)."
    )


def test_a_linha_entra_no_slide():
    linhas = _viab_linhas_detalhe(_viab_normalizado(_PAYLOAD))
    assert any(linha.startswith("Investimento: obra") for linha in linhas)


def test_so_obra_nao_afirma_equipamentos():
    dados = _viab_normalizado({"investimento": {"obra": 400_000.0, "parcelas_obra": 4}})
    assert _viab_linha_composicao_investimento(dados) == (
        "Investimento: obra R$ 400.000,00 (4x sem juros)."
    )


def test_equipamentos_sem_prazo_nem_juros_nao_inventa_numero():
    dados = _viab_normalizado({"investimento": {"equipamentos": 300_000.0}})
    assert _viab_linha_composicao_investimento(dados) == (
        "Investimento: equipamentos R$ 300.000,00 (financiados)."
    )


def test_parcela_unica_de_obra_nao_diz_parcelamento():
    dados = _viab_normalizado({"investimento": {"obra": 400_000.0, "parcelas_obra": 1}})
    assert _viab_linha_composicao_investimento(dados) == "Investimento: obra R$ 400.000,00."


def test_sem_composicao_no_payload_a_linha_nao_existe():
    # Payload legado (so' CAPEX agregado): a pagina fica como era, sem linha nova.
    dados = _viab_normalizado({"investimento": {"investimento_total": 1_000_000.0}})
    assert _viab_linha_composicao_investimento(dados) is None
    assert not any(
        linha.startswith("Investimento: obra") for linha in _viab_linhas_detalhe(dados)
    )
