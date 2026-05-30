"""
Teste minimo - Bloco 2: penetracao Ultra por hexagono.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from motor_expansao.pipelines import calcular_penetracao_ultra_hex as modulo

ROOT = Path(__file__).resolve().parents[2]
UNIDADES_PATH = ROOT / "data" / "staging" / "unidades_ultra_performance.parquet"

SCHEMA_OBRIGATORIO = {
    "unidade",
    "uf",
    "cidade",
    "lat",
    "lng",
    "hex_id_res7",
    "hex_id",
    "pop_hex_base",
    "fonte_pop_hex_base",
    "penetracao_ultra_alunos_total",
    "penetracao_ultra_pagantes",
    "receita_por_habitante_hex",
    "ticket_medio_aluno",
    "alunos_por_m2",
    "rank_penetracao_ultra_alunos_total",
}


@pytest.fixture(scope="module")
def df() -> pd.DataFrame:
    if not UNIDADES_PATH.exists():
        pytest.skip("unidades_ultra_performance.parquet ausente (dados reais)")
    return modulo.gerar_base()


def test_schema_minimo(df: pd.DataFrame):
    assert SCHEMA_OBRIGATORIO <= set(df.columns), (
        f"Colunas faltando: {SCHEMA_OBRIGATORIO - set(df.columns)}"
    )


def test_total_linhas_preserva_base_de_unidades(df: pd.DataFrame):
    unidades = pd.read_parquet(UNIDADES_PATH, columns=["performance_source_index"])
    assert len(df) == len(unidades) == 54
    assert not df["performance_source_index"].duplicated().any()


def test_fontes_de_populacao_e_formulas_reais(df: pd.DataFrame):
    assert set(df["fonte_pop_hex_base"].unique()) <= modulo.POP_SOURCE_VALUES
    assert {"censo_2022_hex", "m1_municipal_proxy"} <= set(df["fonte_pop_hex_base"].unique())

    censo = df["fonte_pop_hex_base"].eq("censo_2022_hex")
    censo_flags = df.loc[censo, "flag_censo_elegivel"].map(
        lambda value: bool(value) if pd.notna(value) else False
    )
    assert censo_flags.all()
    assert np.allclose(df.loc[censo, "pop_hex_base"], df.loc[censo, "pop_total_setor_2022"])

    proxy = df["fonte_pop_hex_base"].eq("m1_municipal_proxy")
    assert np.allclose(df.loc[proxy, "pop_hex_base"], df.loc[proxy, "populacao_proxy"])

    suzano = df.loc[df["unidade"].eq("SUZANO")].iloc[0]
    assert suzano["fonte_pop_hex_base"] == "censo_2022_hex"
    assert suzano["penetracao_ultra_alunos_total"] == pytest.approx(
        suzano["alunos_total"] / suzano["pop_hex_base"]
    )

    serra = df.loc[df["unidade"].eq("SERRA")].iloc[0]
    assert serra["fonte_pop_hex_base"] == "m1_municipal_proxy"
    assert serra["pop_hex_base"] == pytest.approx(serra["populacao_proxy"])


def test_divisoes_seguras_com_populacao_e_metragem_invalidas():
    base = pd.DataFrame(
        {
            "hex_id_res7": ["h1", "h2", "h3", pd.NA],
            "hex_id": ["h1", "h2", "h3", pd.NA],
            "flag_censo_elegivel": [True, False, True, False],
            "pop_total_setor_2022": [1000.0, 100.0, 0.0, np.nan],
            "populacao_proxy": [900.0, 2000.0, 0.0, np.nan],
            "faturamento": [10000.0, 5000.0, 4000.0, 3000.0],
            "alunos_total": [100.0, 50.0, 40.0, 30.0],
            "ativos_pag": [80.0, 25.0, 20.0, 15.0],
            "metragem": [1000.0, 0.0, np.nan, 500.0],
        }
    )

    result = modulo.calcular_metricas(base)

    assert result.loc[0, "fonte_pop_hex_base"] == "censo_2022_hex"
    assert result.loc[0, "penetracao_ultra_alunos_total"] == pytest.approx(0.10)
    assert result.loc[0, "penetracao_ultra_pagantes"] == pytest.approx(0.08)
    assert result.loc[0, "receita_por_habitante_hex"] == pytest.approx(10.0)
    assert result.loc[0, "alunos_por_m2"] == pytest.approx(0.10)

    assert result.loc[1, "fonte_pop_hex_base"] == "m1_municipal_proxy"
    assert result.loc[1, "penetracao_ultra_alunos_total"] == pytest.approx(0.025)
    assert pd.isna(result.loc[1, "alunos_por_m2"])

    assert result.loc[2, "fonte_pop_hex_base"] == "sem_populacao_valida"
    assert pd.isna(result.loc[2, "penetracao_ultra_alunos_total"])
    assert result.loc[3, "fonte_pop_hex_base"] == "sem_hex_id_res7"
    assert pd.isna(result.loc[3, "receita_por_habitante_hex"])


def test_ranking_de_penetracao(df: pd.DataFrame):
    validas = df["penetracao_ultra_alunos_total"].notna()
    assert validas.sum() >= 1
    assert int(df.loc[validas, "rank_penetracao_ultra_alunos_total"].min()) == 1

    top = df.sort_values("penetracao_ultra_alunos_total", ascending=False).iloc[0]
    assert int(top["rank_penetracao_ultra_alunos_total"]) == 1


def test_validar_base_nao_falha(df: pd.DataFrame):
    modulo.validar(df)
