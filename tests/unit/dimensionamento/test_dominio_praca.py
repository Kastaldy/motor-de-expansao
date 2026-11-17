"""Dominio do modelo de praca (DEC-086, emenda 1): onde ele NAO estima a demanda.

Duas regras medidas: a isocrona presa (abaixo de `V2_AREA_MIN_KM2`) e a zona morta da
Viabilidade (DEC-042). Captacao indisponivel e' indecidivel e nunca veta.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from motor_expansao.dimensionamento import dominio_praca as dom
from motor_expansao.dimensionamento.config import RAIO_CATCHMENT_KM, V2_AREA_MIN_KM2
from motor_expansao.dimensionamento.viabilidade_ponto import (
    POP_ZONA_MORTA_MIN,
    RENDA_ZONA_MORTA_MIN,
)


def test_o_piso_da_area_e_1_km2_e_a_borda_nao_corta():
    assert V2_AREA_MIN_KM2 == 1.0
    assert dom.area_pequena(0.03) and dom.area_pequena(0.999)
    assert not dom.area_pequena(1.0), "na borda o ponto segue no dominio"
    assert not dom.area_pequena(15.0)
    for vazio in (None, float("nan"), math.inf, "x"):
        assert not dom.area_pequena(vazio), "sem area medida nao ha o que recusar"


def test_zona_morta_e_a_regua_da_viabilidade():
    assert dom.zona_morta(POP_ZONA_MORTA_MIN - 1, 2_000.0) == f"pop<{int(POP_ZONA_MORTA_MIN)}"
    assert dom.zona_morta(50_000.0, RENDA_ZONA_MORTA_MIN - 1) == f"renda<{int(RENDA_ZONA_MORTA_MIN)}"
    assert dom.zona_morta(POP_ZONA_MORTA_MIN, 2_000.0) is None, "no limiar nao dispara (estrito)"
    assert dom.zona_morta(50_000.0, 2_000.0) is None


@pytest.mark.parametrize("pop, renda", [(None, None), (float("nan"), None), (None, float("nan"))])
def test_captacao_indisponivel_nunca_veta(pop, renda):
    assert dom.zona_morta(pop, renda) is None
    assert dom.motivo_fora_do_dominio(area_km2=12.0, pop_captacao=pop, renda_pc_captacao=renda) is None


def test_a_area_vem_antes_da_zona_morta_nas_duas_superficies():
    assert dom.motivo_fora_do_dominio(area_km2=0.4, pop_captacao=300.0, renda_pc_captacao=900.0) == (
        dom.MOTIVO_AREA_PEQUENA
    )
    assert dom.motivo_fora_do_dominio(area_km2=12.0, pop_captacao=300.0, renda_pc_captacao=900.0) == (
        dom.MOTIVO_ZONA_MORTA
    )
    assert dom.motivo_fora_do_dominio(area_km2=12.0, pop_captacao=40_000.0, renda_pc_captacao=900.0) is None
    # Cada argumento ausente nao conta: o simulador confere a area antes de ler setor.
    assert dom.motivo_fora_do_dominio(area_km2=0.4) == dom.MOTIVO_AREA_PEQUENA
    assert dom.motivo_fora_do_dominio(pop_captacao=300.0, renda_pc_captacao=900.0) == dom.MOTIVO_ZONA_MORTA


def test_captacao_e_a_conta_da_viabilidade_no_raio_de_1_5_km(monkeypatch):
    from motor_expansao.dimensionamento import catchment_batch

    chamadas = {}

    def _catch(lat, lng, setores, raio_km):
        chamadas["raio"] = raio_km
        return {"pop_captacao": 4_321.0, "renda_per_capita_captacao": float("nan")}

    monkeypatch.setattr(catchment_batch, "calcular_catchment_unidade", _catch)
    assert dom.captacao(-23.5, -46.6, pd.DataFrame()) == (4_321.0, None)
    assert chamadas["raio"] == RAIO_CATCHMENT_KM == 1.5
    assert dom.captacao(-23.5, -46.6, None) == (None, None)


def test_captacao_que_falha_vira_indecidivel(monkeypatch):
    from motor_expansao.dimensionamento import catchment_batch

    def _quebra(*_a, **_k):
        raise ValueError("geometria estranha")

    monkeypatch.setattr(catchment_batch, "calcular_catchment_unidade", _quebra)
    assert dom.captacao(-23.5, -46.6, pd.DataFrame()) == (None, None)


def test_textos_sao_acentuados_e_citam_a_regua_da_zona_morta():
    zm = dom.texto_sem_projecao(dom.MOTIVO_ZONA_MORTA, pop_captacao=1_200.0, renda_pc_captacao=2_000.0)
    assert zm == "Sem projeção: zona morta (população de captação abaixo de 5.000)."
    assert "via interna" in dom.texto_sem_projecao(dom.MOTIVO_AREA_PEQUENA)
    assert "madrugada" in dom.texto_sem_projecao(dom.MOTIVO_AGUARDANDO)
    assert "área" in dom.texto_sem_projecao(dom.MOTIVO_SEM_AREA)
    assert "não pôde ser calculado" in dom.texto_sem_projecao(dom.MOTIVO_SEM_CALCULO)
    assert "não pôde ser calculado" in dom.texto_sem_projecao("motivo_novo_desconhecido")
    for motivo in dom.MOTIVOS:
        texto = dom.texto_sem_projecao(motivo)
        assert texto.startswith("Sem projeção") and "_" not in texto, "token cru nunca vai a tela"


def test_frase_do_simulador_pede_a_demanda():
    area = dom.mensagem_sugestao_recusada(dom.MOTIVO_AREA_PEQUENA)
    zm = dom.mensagem_sugestao_recusada(
        dom.MOTIVO_ZONA_MORTA, pop_captacao=50_000.0, renda_pc_captacao=RENDA_ZONA_MORTA_MIN - 1
    )
    assert area.startswith("O modelo de praça não estima a demanda deste ponto") and "via interna" in area
    assert "renda per capita de captação abaixo de R$ 500" in zm
    for frase in (area, zm):
        assert frase.endswith("Informe a demanda.")
