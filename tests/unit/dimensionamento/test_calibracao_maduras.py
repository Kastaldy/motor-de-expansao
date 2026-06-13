"""Testes da consolidacao da base de calibracao (fixtures sinteticas; sem rede)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from motor_expansao.dimensionamento.calibracao_maduras import (
    consolidar_base_calibracao,
    normalizar_unidade,
    resumo_consolidacao,
)


def _perf():
    return pd.DataFrame(
        {
            "unidade": ["VILA MARIANA", "CAMPO LIMPO"],
            "uf": ["SP", "SP"],
            "cidade": ["SP", None],
            "metragem": [1500.0, 1800.0],
            "faturamento": [500000.0, 400000.0],
            "alunos_por_m2": [1.5, 1.2],
            "ticket_medio_aluno": [150.0, 140.0],
        }
    )


def _historico():
    # serie diaria; VILA MARIANA inaugurada 2021, com 2 datas recentes + 1 antiga.
    return pd.DataFrame(
        {
            "unidade": [
                "VILA MARIANA - SP",
                "VILA MARIANA - SP",
                "VILA MARIANA - SP",
            ],
            "data": ["01/06/2026", "02/06/2026", "01/01/2024"],
            "inauguracao": ["23/08/2021", "23/08/2021", "23/08/2021"],
            "pagantes": [2000, 2100, 1000],
            "churn": [0.05, 0.07, 0.20],
            "ticket_medio": [200.0, 210.0, 100.0],
            "cancelados": [10, 12, 5],
            "ativos_total": [2000, 2100, 1000],
            "inadimplente": [50, 60, 30],
            "uf": ["SP", "SP", "SP"],
        }
    )


def _catchment():
    return pd.DataFrame(
        {
            "unidade_norm": ["VILA MARIANA", "CAMPO LIMPO"],
            "pop_captacao": [50000.0, np.nan],
            "renda_per_capita_captacao": [4000.0, np.nan],
            "n_setores_captacao": [30, 0],
            "raio_km": [1.5, 1.5],
        }
    )


def test_consolida_steady_state_dos_ultimos_meses():
    base = consolidar_base_calibracao(_perf(), _historico(), _catchment(), n_meses_steady=6)
    vm = base.loc[base["unidade_norm"] == "VILA MARIANA"].iloc[0]
    # mediana dos ultimos 6 meses (so 01/06 e 02/06; a de 2024 fica fora) -> [2000,2100]
    assert vm["pagantes_steady_state"] == 2050.0
    assert vm["churn_steady"] == pytest.approx(0.06)  # mediana de 0.05, 0.07
    assert vm["ticket_steady"] == 205.0


def test_maturacao_real_e_flag_madura():
    base = consolidar_base_calibracao(_perf(), _historico(), _catchment(), meses_madura=8)
    vm = base.loc[base["unidade_norm"] == "VILA MARIANA"].iloc[0]
    # data_ref = 02/06/2026; inaug = 23/08/2021 -> ~57 meses
    assert vm["meses_desde_inauguracao"] > 8
    assert vm["flag_madura"] is True or vm["flag_madura"] == True  # noqa: E712
    assert vm["inauguracao"] == "2021-08-23"


def test_unidade_sem_historico_tem_lacunas():
    base = consolidar_base_calibracao(_perf(), _historico(), _catchment())
    cl = base.loc[base["unidade_norm"] == "CAMPO LIMPO"].iloc[0]
    # sem serie historica -> steady NaN; sem inauguracao -> flag_madura False
    assert pd.isna(cl["pagantes_steady_state"])
    assert cl["flag_madura"] == False  # noqa: E712
    assert "pagantes_steady_state" in cl["lacunas"]
    assert "pop_captacao" in cl["lacunas"]  # catchment NaN


def test_join_catchment():
    base = consolidar_base_calibracao(_perf(), _historico(), _catchment())
    vm = base.loc[base["unidade_norm"] == "VILA MARIANA"].iloc[0]
    assert vm["pop_captacao"] == 50000.0
    assert vm["renda_per_capita_captacao"] == 4000.0


def test_normalizar_unidade_reexport():
    assert normalizar_unidade("Vila Mariana - SP") == "VILA MARIANA"


def test_resumo_consolidacao():
    base = consolidar_base_calibracao(_perf(), _historico(), _catchment())
    res = resumo_consolidacao(base)
    assert res["n_unidades"] == 2
    # 1 de 2 com inauguracao real
    assert res["pct_inauguracao_real"] == 50.0
    assert res["meses_desde_inauguracao_nunique"] >= 1
    assert res["n_com_lacunas"] >= 1


def test_historico_vazio_nao_quebra():
    base = consolidar_base_calibracao(_perf(), pd.DataFrame(), _catchment())
    assert len(base) == 2
    assert base["pagantes_steady_state"].isna().all()


def test_meses_desde_inauguracao_nao_constante():
    # 2 unidades com inauguracoes diferentes -> meses variam (fecha parte do G1).
    perf = pd.DataFrame(
        {"unidade": ["A", "B"], "uf": ["SP", "SP"], "metragem": [1500.0, 1500.0]}
    )
    hist = pd.DataFrame(
        {
            "unidade": ["A", "B"],
            "data": ["01/06/2026", "01/06/2026"],
            "inauguracao": ["01/01/2020", "01/01/2024"],
            "pagantes": [1000, 500],
            "churn": [0.05, 0.05],
            "ticket_medio": [150, 150],
        }
    )
    catch = pd.DataFrame({"unidade_norm": ["A", "B"], "pop_captacao": [1.0, 2.0]})
    base = consolidar_base_calibracao(perf, hist, catch)
    meses = base["meses_desde_inauguracao"].dropna().unique()
    assert len(meses) == 2  # nao constante
