"""Mix recorrente x agregador editavel, e o cambio que leva o ticket em pesos a conta.

Duas coisas que a aba de Viabilidade argentina precisava e nao tinha:

1. **O mix.** `Premissas.share_balcao` ja existia no nucleo, mas o corpo da requisicao
   nao tinha como informa-lo: a fracao de balcao era sempre a constante brasileira
   (69% / 31%). `share_balcao` vira campo OPCIONAL do cenario; ausente, o payload e
   identico ao de antes.
2. **O cambio.** A conta e feita em reais (decisao 0.6). Para o operador digitar o
   ticket em pesos, a tela precisa de dois cambios: moeda local por dolar (ja estava no
   perfil AR, `moeda.cambio_base`) e reais por dolar (`moeda.cambio_viabilidade`, novo).
   O perfil declara, `/api/me` serve, a tela converte — sem `if pais` (DEC-047).

Medido contra os DOIS perfis reais versionados, sem dado local.
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from motor_expansao.dimensionamento.config import SIM_SHARE_BALCAO
from motor_expansao.dimensionamento.payload_viabilidade import (
    ViabilidadeIn,
    montar_payload_viabilidade,
    premissas_do_body,
)
from motor_expansao.perfil import PERFIL_BR_EMBARCADO, Perfil, carregar_perfil

_REPO = Path(__file__).resolve().parents[2]
_SERVIDOR = _REPO / "web" / "server"
if str(_SERVIDOR) not in sys.path:
    sys.path.insert(0, str(_SERVIDOR))

import app as pilot  # noqa: E402  (backend do piloto; web/server no sys.path acima)

_PERFIL_AR_JSON = PERFIL_BR_EMBARCADO.parents[1] / "AR" / "perfil.json"
_CENARIO = {"lat": -23.55, "lng": -46.63, "m2": 1500, "aluguel": 30000, "demanda": 1600}


@pytest.fixture(scope="module")
def br() -> Perfil:
    return carregar_perfil(PERFIL_BR_EMBARCADO)


@pytest.fixture(scope="module")
def ar() -> Perfil:
    return carregar_perfil(_PERFIL_AR_JSON)


def _payload(**extra: float) -> dict[str, Any]:
    return montar_payload_viabilidade(
        ViabilidadeIn(**_CENARIO, **extra), staging_dir=pilot.STAGING_DIR, setores_df=None
    )


# --------------------------------------------------------------------------------
# 1. O mix recorrente x agregador
# --------------------------------------------------------------------------------


def test_sem_share_o_cenario_usa_o_mix_do_motor() -> None:
    assert premissas_do_body(ViabilidadeIn(**_CENARIO)).share_balcao == SIM_SHARE_BALCAO


def test_share_informado_chega_as_premissas_e_ao_payload() -> None:
    padrao = _payload()
    so_balcao = _payload(share_balcao=1.0)
    metade = _payload(share_balcao=0.5)

    assert so_balcao["premissas"]["share_balcao"] == 1.0
    assert metade["premissas"]["share_balcao"] == 0.5
    # A reparticao de alunos acompanha o MESMO mix (1.600 de demanda no cenario): o
    # ticket medio com o mix informado e o `split` com o padrao seria meia mudanca.
    # A chave `studios` entrou no MESMO dict pela DEC-068 (#442), depois deste teste ser
    # escrito: a comparacao e' por igualdade ESTRITA, entao sem ela o teste falhava por
    # uma chave A MAIS, nao por valor errado (balcao e agregadores batiam). E' o padrao
    # "duas regras no mesmo payload que nao se viram" -- e `payload_viabilidade.py` nao
    # teve UMA linha de conflito textual no merge, o que torna isso invisivel ao git.
    assert so_balcao["split"] == {"balcao": 1600.0, "agregadores": 0.0, "studios": []}
    assert metade["split"] == {"balcao": 800.0, "agregadores": 800.0, "studios": []}
    # O agregador paga menos que o balcao: mais balcao, ticket medio maior.
    assert (
        metade["premissas"]["ticket_blended"]
        < padrao["premissas"]["ticket_blended"]
        < so_balcao["premissas"]["ticket_blended"]
    )


def test_share_igual_ao_padrao_nao_muda_o_payload() -> None:
    """Informar o proprio padrao tem de dar o MESMO payload de nao informar: prova de
    que o campo so atravessa, sem efeito colateral."""
    assert _payload(share_balcao=SIM_SHARE_BALCAO) == _payload()


@pytest.mark.parametrize("fora", [-0.01, 1.01, 69])
def test_share_fora_de_fracao_e_recusado(fora: float) -> None:
    """69 no lugar de 0,69 e o erro de unidade classico (percentual x fracao)."""
    with pytest.raises(ValidationError):
        ViabilidadeIn(**_CENARIO, share_balcao=fora)


# --------------------------------------------------------------------------------
# 2. O cambio do ticket
# --------------------------------------------------------------------------------


def test_perfil_ar_declara_os_dois_cambios_no_mesmo_mes_base(ar: Perfil) -> None:
    moeda = ar.moeda
    assert moeda.cambio_base is not None
    assert moeda.cambio_base.par == "ARS/USD"
    assert moeda.cambio_base.valor == 1397.71
    assert moeda.cambio_viabilidade is not None
    assert moeda.cambio_viabilidade.par == "BRL/USD"
    # PTAX de venda do Banco Central, media de maio/2026 (20 cotacoes). O MESMO mes do
    # cambio peso/dolar: cambios de meses diferentes fabricam uma conversao cruzada
    # que nunca existiu em dia nenhum.
    assert moeda.cambio_viabilidade.valor == 4.9837
    assert moeda.base_monetaria == "2026-05"


def test_perfil_br_nao_declara_cambio(br: Perfil) -> None:
    assert br.moeda.cambio_base is None
    assert br.moeda.cambio_viabilidade is None


def test_me_serve_a_moeda_da_viabilidade_na_instancia_ar(
    ar: Perfil, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pilot, "PERFIL", ar)
    assert pilot.me(remote_user=None)["viabilidade_moeda"] == {
        "codigo": "ARS",
        "simbolo": "$",
        "local_por_usd": 1397.71,
        "brl_por_usd": 4.9837,
        "base": "2026-05",
    }


def test_me_nao_serve_moeda_de_viabilidade_na_instancia_br(
    br: Perfil, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pilot, "PERFIL", br)
    assert "viabilidade_moeda" not in pilot.me(remote_user=None)


def test_sem_um_dos_cambios_a_moeda_nao_e_servida(
    ar: Perfil, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Meio cambio nao converte nada: a tela cairia em pesos sem ter como chegar aos
    reais da conta. Sem os DOIS, a chave some e a tela fica como a de hoje."""
    for moeda in (
        dataclasses.replace(ar.moeda, cambio_viabilidade=None),
        dataclasses.replace(ar.moeda, cambio_base=None),
    ):
        monkeypatch.setattr(pilot, "PERFIL", dataclasses.replace(ar, moeda=moeda))
        assert "viabilidade_moeda" not in pilot.me(remote_user=None)
