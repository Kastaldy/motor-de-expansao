"""Padrao POR CAMPO do investimento (decisao de Felipe, 2026-10-28).

Campo vazio vale o padrao do config -- os mesmos numeros que a tela da Viabilidade
mostra em cinza. Antes, obra e equipamentos vazios caiam num CAPEX unico de 2.340.000
sem financiamento, preencher um zerava o outro e o juros vazio era 0%: digitar o numero
cinza mudava o payback (Campinas: 52 -> 39 meses so' de confirmar a obra).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from motor_expansao.dimensionamento.config import (
    SIM_CAPEX_DEFAULT,
    SIM_EQUIPAMENTOS_DEFAULT,
    SIM_JUROS_EQUIPAMENTOS_AM_DEFAULT,
    SIM_OBRA_DEFAULT,
    SIM_PRAZO_EQUIPAMENTOS_DEFAULT,
)
from motor_expansao.dimensionamento.payload_viabilidade import (
    ViabilidadeIn,
    investimento_do_body,
)

_BASE = {"lat": -22.9056, "lng": -47.0608, "m2": 1500, "aluguel": 60_000, "demanda": 2500}
_TELA = Path(__file__).resolve().parents[3] / "web" / "src" / "screens" / "ViabilityScreen.tsx"


def _inv(**campos):
    return investimento_do_body(ViabilidadeIn(**_BASE, **campos))


def test_os_padroes_sao_os_numeros_decididos():
    assert SIM_OBRA_DEFAULT == 1_500_000
    assert SIM_EQUIPAMENTOS_DEFAULT == 1_200_000
    assert SIM_PRAZO_EQUIPAMENTOS_DEFAULT == 36
    assert SIM_JUROS_EQUIPAMENTOS_AM_DEFAULT == pytest.approx(0.018)


def test_tudo_vazio_usa_os_quatro_padroes():
    inv = _inv()
    assert inv["obra"] == SIM_OBRA_DEFAULT
    assert inv["equipamentos"] == SIM_EQUIPAMENTOS_DEFAULT
    assert inv["prazo_equipamentos"] == SIM_PRAZO_EQUIPAMENTOS_DEFAULT
    assert inv["juros_equipamentos_am"] == pytest.approx(SIM_JUROS_EQUIPAMENTOS_AM_DEFAULT)


@pytest.mark.parametrize(
    "digitado",
    [
        {"obra": 1_500_000},
        {"equipamentos": 1_200_000},
        {"prazo_equipamentos": 36},
        {"juros_equipamentos_am": 0.018},
        {
            "obra": 1_500_000,
            "equipamentos": 1_200_000,
            "prazo_equipamentos": 36,
            "juros_equipamentos_am": 0.018,
        },
    ],
)
def test_digitar_o_numero_cinza_nao_muda_o_investimento(digitado):
    """O defeito de origem: confirmar o padrao tem de ser o mesmo que deixar vazio."""
    assert _inv(**digitado) == _inv()


def test_preencher_um_campo_nao_zera_o_outro():
    assert _inv(obra=900_000)["equipamentos"] == SIM_EQUIPAMENTOS_DEFAULT
    assert _inv(equipamentos=500_000)["obra"] == SIM_OBRA_DEFAULT


def test_zero_digitado_e_honrado():
    inv = _inv(equipamentos=0, juros_equipamentos_am=0)
    assert inv["equipamentos"] == 0
    assert inv["prazo_equipamentos"] == 0  # sem equipamento nao ha financiamento
    assert inv["juros_equipamentos_am"] == 0
    assert _inv(obra=0)["obra"] == 0


def test_corpo_legado_com_capex_segue_a_regra_antiga():
    """Quem integrou pela API antiga (`capex` + fracao financiada) nao muda."""
    inv = _inv(capex=2_000_000, capex_financiado_pct=0.25)
    assert inv["obra"] == 1_500_000
    assert inv["equipamentos"] == 500_000
    assert inv["juros_equipamentos_am"] == 0.0
    assert inv["prazo_equipamentos"] == 36
    so_pct = _inv(capex_financiado_pct=0.5)
    assert so_pct["obra"] + so_pct["equipamentos"] == SIM_CAPEX_DEFAULT


def test_a_tela_anuncia_os_mesmos_padroes_do_motor():
    """O cinza da caixa e' o padrao: se o config mudar sem a tela, o defeito volta."""
    tela = _TELA.read_text(encoding="utf-8")

    def const(nome: str) -> str:
        m = re.search(rf"const {nome} = ([^\n]+)", tela)
        assert m, nome
        return m.group(1).strip().strip("'").replace("_", "")

    assert const("PADRAO_OBRA") == "1.500.000"
    assert const("PADRAO_OBRA_REAIS") == str(SIM_OBRA_DEFAULT)
    assert const("PADRAO_EQUIPAMENTOS") == "1.200.000"
    assert const("PADRAO_EQUIPAMENTOS_REAIS") == str(SIM_EQUIPAMENTOS_DEFAULT)
    assert const("PADRAO_PRAZO_EQUIP") == str(SIM_PRAZO_EQUIPAMENTOS_DEFAULT)
    assert const("PADRAO_JUROS_EQUIP") == "1,8"
    assert "SUGESTÃO" not in tela.split("PADRAO_OBRA = ")[1].split("function ")[0]
