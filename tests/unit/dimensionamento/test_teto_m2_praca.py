"""Teto de metragem do modelo de praca (DEC-086): o modelo conta ate' `V2_TETO_M2`.

O teto vale DENTRO de `prever_faturamento_v2`, e por isso para toda superficie que usa o
modelo: a sugestao da Viabilidade, a conferencia do token (PDF e planilha) e a lista de
oportunidades imobiliarias. Acima dele o p50 e' o do teto; a metragem digitada segue no
token e no resto da conta.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from motor_expansao.dimensionamento import viabilidade_v2 as v2
from motor_expansao.dimensionamento.config import V2_TETO_M2
from motor_expansao.dimensionamento.demanda_v2 import EntradasV2, prever_faturamento_v2
from motor_expansao.dimensionamento.payload_viabilidade import ViabilidadeIn

from .test_viabilidade_v2 import COEF_FICTICIO, GOLDEN, _gravar

# Entradas dentro do envelope dos coeficientes REAIS (renda domiciliar ~R$ 4.286, pop 200 mil).
_PRACA = {"studios": 0, "pop_c10": 200_000.0, "dom_c10": 70_000.0, "renda_pc_c10": 1_500.0}


@pytest.fixture
def coef(tmp_path, monkeypatch):
    monkeypatch.delenv("MOTOR_VIABILIDADE_V2", raising=False)
    caminho = _gravar(tmp_path, COEF_FICTICIO)
    monkeypatch.setattr(v2, "caminho_coeficientes", lambda: caminho)
    v2.limpar_cache()
    yield v2.carregar_coeficientes()
    v2.limpar_cache()


@pytest.fixture
def coef_reais(monkeypatch):
    """Os coeficientes que vao para producao (`dimensionamento/v2_coeficientes.json`)."""
    monkeypatch.delenv("MOTOR_VIABILIDADE_V2", raising=False)
    v2.limpar_cache()
    yield v2.carregar_coeficientes()
    v2.limpar_cache()


def _p(m2: float, coef):
    return prever_faturamento_v2(EntradasV2(m2=m2, **_PRACA), coef)


def test_acima_do_teto_o_p50_e_o_do_teto(coef):
    no_teto, acima, muito_acima = _p(V2_TETO_M2, coef), _p(3_500.0, coef), _p(20_000.0, coef)
    assert acima.fat_p50 == pytest.approx(no_teto.fat_p50, rel=1e-12)
    assert muito_acima.fat_p50 == pytest.approx(no_teto.fat_p50, rel=1e-12)
    assert acima.fat_p10 == pytest.approx(no_teto.fat_p10, rel=1e-12)
    assert acima.fat_p90 == pytest.approx(no_teto.fat_p90, rel=1e-12)
    assert acima.teto_m2_aplicado is True and acima.m2_modelo == V2_TETO_M2
    assert acima.ln_x["ln_m2"] == math.log(V2_TETO_M2)


def test_ate_o_teto_nada_muda(coef):
    """Na borda e abaixo dela, a conta e' a de antes do teto (exp de X.beta + cal)."""
    for m2 in (1_500.0, V2_TETO_M2):
        prev = _p(m2, coef)
        assert prev.teto_m2_aplicado is False and prev.m2_modelo == m2
        assert prev.ln_x["ln_m2"] == math.log(m2)
    razao = _p(V2_TETO_M2, coef).fat_p50 / _p(1_400.0, coef).fat_p50
    assert razao == pytest.approx(2.0 ** COEF_FICTICIO["beta"]["ln_m2"], rel=1e-12)


def test_teto_e_o_topo_do_envelope_dos_coeficientes_reais(coef_reais):
    """O teto e' a MAIOR unidade do treino. Se os coeficientes forem reestimados com outra
    metragem maxima, este teste cai e o teto tem de ser revisto (DEC-086)."""
    _lo, hi = coef_reais.envelope["ln_m2"]
    assert math.log(V2_TETO_M2) == hi
    assert math.exp(hi) == pytest.approx(V2_TETO_M2, rel=1e-12)


@pytest.mark.parametrize("m2", [V2_TETO_M2, 3_000.0, 12_000.0])
def test_no_teto_e_acima_dele_a_metragem_nao_vira_extrapolacao(coef_reais, m2):
    prev = _p(m2, coef_reais)
    assert "ln_m2" not in prev.fora_do_envelope
    assert prev.flag_extrapolacao is False


def test_sugestao_declara_o_teto_e_o_token_guarda_a_metragem_digitada(coef):
    corpo = v2.DemandaV2In(lat=GOLDEN["lat"], lng=GOLDEN["lng"], m2=3_200.0, ticket=GOLDEN["ticket"])
    sug = v2.montar_sugestao_v2(corpo, pop_c10=3e5, dom_c10=1e5, renda_pc_c10=1800, coef=coef)
    assert sug["teto_m2_aplicado"] is True and sug["m2_modelo"] == V2_TETO_M2
    assert sug["entradas"]["m2"] == 3_200.0, "o token e o corpo seguem a metragem digitada"
    abaixo = v2.montar_sugestao_v2(
        corpo.model_copy(update={"m2": 1_500.0}), pop_c10=3e5, dom_c10=1e5, renda_pc_c10=1800,
        coef=coef,
    )
    assert abaixo["teto_m2_aplicado"] is False and abaixo["m2_modelo"] == 1_500.0


def test_token_tirado_acima_do_teto_confere_na_viabilidade(coef):
    """A conferencia (PDF e planilha) refaz a conta pela MESMA funcao: com o teto dentro
    do modelo, a sugestao acima dele confere sem nova chamada externa."""
    corpo = v2.DemandaV2In(lat=GOLDEN["lat"], lng=GOLDEN["lng"], m2=3_200.0, ticket=GOLDEN["ticket"])
    sug = v2.montar_sugestao_v2(corpo, pop_c10=3e5, dom_c10=1e5, renda_pc_c10=1800, coef=coef)
    ref = {k: sug["entradas"][k] for k in ("pop_c10", "dom_c10", "renda_pc_c10")}
    body = ViabilidadeIn(**{
        **GOLDEN, "m2": 3_200.0, "demanda": round(sug["alunos"]["p50"]), "modelo_demanda": "v2",
        "demanda_v2": {"token": sug["token"], **ref},
    })
    from motor_expansao.dimensionamento.payload_viabilidade import premissas_do_body

    conferida = v2.conferir_demanda_v2(body, premissas_do_body(body))
    assert conferida.demanda_fonte == v2.DEMANDA_FONTE_V2
    assert conferida.bloco["teto_m2_aplicado"] is True


def test_o_json_real_nao_ganhou_chave_de_teto():
    """O teto mora no config, nao no JSON de coeficientes (schema estrito: chave nova
    deixaria a v2 indisponivel)."""
    bruto = json.loads(
        (Path(v2.__file__).with_name("v2_coeficientes.json")).read_text(encoding="utf-8")
    )
    assert "teto_m2" not in bruto and "teto" not in json.dumps(bruto)
