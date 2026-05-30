from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import streamlit_app
from motor_expansao.dashboard.data import agregar_cenario_multihex

# ── helpers ──────────────────────────────────────────────────────────────────

def _df_base(**overrides) -> pd.DataFrame:
    """DataFrame minimal com dois hexes para testes."""
    data = {
        "hex_id": ["h1", "h2"],
        "populacao_proxy": [10_000.0, 5_000.0],
        "renda_per_capita": [6_000.0, 4_000.0],
        "score_priorizacao": [80.0, 60.0],
    }
    data.update(overrides)
    return pd.DataFrame(data)


# ── lista vazia e df vazio ──────────────────────────────────────────────────

def test_lista_vazia_retorna_qtd_zero():
    df = _df_base()
    result = agregar_cenario_multihex(df, [])
    assert result["qtd_hexes"] == 0
    assert result["hexes_selecionados"].empty


def test_df_vazio_retorna_qtd_zero():
    result = agregar_cenario_multihex(pd.DataFrame(), ["h1"])
    assert result["qtd_hexes"] == 0


def test_df_none_retorna_qtd_zero():
    result = agregar_cenario_multihex(None, ["h1"])
    assert result["qtd_hexes"] == 0


# ── hexes ausentes ────────────────────────────────────────────────────────────

def test_hex_inexistente_vai_para_ausentes():
    df = _df_base()
    result = agregar_cenario_multihex(df, ["h1", "h_nao_existe"])
    assert "h_nao_existe" in result["hex_ids_ausentes"]
    assert "h1" in result["hex_ids_existentes"]
    assert result["qtd_hexes"] == 1


def test_todos_ausentes_retorna_qtd_zero_e_lista_ausentes():
    df = _df_base()
    result = agregar_cenario_multihex(df, ["x1", "x2"])
    assert result["qtd_hexes"] == 0
    assert result["hex_ids_ausentes"] == ["x1", "x2"]
    assert result["hex_ids_existentes"] == []


# ── populacao ─────────────────────────────────────────────────────────────────

def test_pop_total_soma_populacao_proxy():
    df = _df_base()
    result = agregar_cenario_multihex(df, ["h1", "h2"])
    assert result["pop_total"] == pytest.approx(15_000.0)


def test_pop_prefere_setor_2022_sobre_proxy():
    df = _df_base(
        pop_total_setor_2022=[8_000.0, 3_000.0],
    )
    result = agregar_cenario_multihex(df, ["h1", "h2"])
    assert result["pop_total"] == pytest.approx(11_000.0)


def test_pop_fallback_para_proxy_quando_setor_ausente():
    df = pd.DataFrame({
        "hex_id": ["h1", "h2"],
        "populacao_proxy": [10_000.0, 5_000.0],
        "renda_per_capita": [6_000.0, 4_000.0],
        "score_priorizacao": [80.0, 60.0],
        "pop_total_setor_2022": [np.nan, np.nan],
    })
    result = agregar_cenario_multihex(df, ["h1", "h2"])
    assert result["pop_total"] == pytest.approx(15_000.0)


# ── renda ─────────────────────────────────────────────────────────────────────

def test_renda_media_ponderada_por_populacao():
    df = _df_base()
    # (10000*6000 + 5000*4000) / 15000 = 80000000/15000 = 5333.33...
    result = agregar_cenario_multihex(df, ["h1", "h2"])
    assert result["renda_per_capita_media"] == pytest.approx(5333.33, abs=1.0)
    assert result["metodo_renda"] == "ponderada_populacao"


def test_renda_media_simples_sem_populacao():
    df = pd.DataFrame({
        "hex_id": ["h1", "h2"],
        "renda_per_capita": [6_000.0, 4_000.0],
        "score_priorizacao": [80.0, 60.0],
    })
    result = agregar_cenario_multihex(df, ["h1", "h2"])
    assert result["renda_per_capita_media"] == pytest.approx(5_000.0)
    assert result["metodo_renda"] == "media_simples"


def test_renda_ausente_retorna_none_e_metodo_ausente():
    df = pd.DataFrame({
        "hex_id": ["h1"],
        "populacao_proxy": [10_000.0],
        "score_priorizacao": [80.0],
    })
    result = agregar_cenario_multihex(df, ["h1"])
    assert result["renda_per_capita_media"] is None
    assert result["metodo_renda"] == "ausente"


# ── colunas opcionais ausentes ────────────────────────────────────────────────

def test_colunas_fitness_ausentes_retornam_none():
    df = _df_base()
    result = agregar_cenario_multihex(df, ["h1", "h2"])
    assert result["residual_total"] is None
    assert result["sam_fitness_total"] is None
    assert result["consumo_concorrentes_total"] is None
    assert result["consumo_ultra_total"] is None
    assert result["consumo_total_instalado"] is None


def test_scores_opcionais_ausentes_retornam_none():
    df = _df_base()
    result = agregar_cenario_multihex(df, ["h1", "h2"])
    assert result["score_censo_medio"] is None
    assert result["score_residual_medio"] is None
    assert result["score_hibrido_medio"] is None
    assert result["score_dominio_hibrido_medio"] is None


# ── scores ────────────────────────────────────────────────────────────────────

def test_score_m1_medio_ponderado_e_max():
    df = _df_base()
    result = agregar_cenario_multihex(df, ["h1", "h2"])
    # ponderado: (10000*80 + 5000*60) / 15000 = 1100000/15000 ≈ 73.33
    assert result["score_m1_medio"] == pytest.approx(73.33, abs=0.1)
    assert result["score_m1_max"] == pytest.approx(80.0)


def test_score_m1_media_simples_sem_populacao():
    df = pd.DataFrame({
        "hex_id": ["h1", "h2"],
        "score_priorizacao": [80.0, 60.0],
    })
    result = agregar_cenario_multihex(df, ["h1", "h2"])
    assert result["score_m1_medio"] == pytest.approx(70.0)
    assert result["score_m1_max"] == pytest.approx(80.0)


# ── dominio hibrido ───────────────────────────────────────────────────────────

def test_dominio_hibrido_calcula_com_ambos_componentes():
    df = pd.DataFrame({
        "hex_id": ["h1"],
        "populacao_proxy": [10_000.0],
        "score_setor_2022_calibrado": [80.0],
        "score_oportunidade_residual": [60.0],
    })
    result = agregar_cenario_multihex(df, ["h1"])
    # 0.60*80 + 0.40*60 = 48 + 24 = 72
    assert result["score_dominio_hibrido_medio"] == pytest.approx(72.0)
    assert result["score_dominio_hibrido_max"] == pytest.approx(72.0)


def test_dominio_hibrido_fallback_apenas_censo():
    df = pd.DataFrame({
        "hex_id": ["h1"],
        "populacao_proxy": [10_000.0],
        "score_setor_2022_calibrado": [90.0],
    })
    result = agregar_cenario_multihex(df, ["h1"])
    assert result["score_dominio_hibrido_medio"] == pytest.approx(90.0)


def test_dominio_hibrido_fallback_apenas_residual():
    df = pd.DataFrame({
        "hex_id": ["h1"],
        "populacao_proxy": [10_000.0],
        "score_oportunidade_residual": [55.0],
    })
    result = agregar_cenario_multihex(df, ["h1"])
    assert result["score_dominio_hibrido_medio"] == pytest.approx(55.0)


def test_dominio_hibrido_clipa_em_100():
    df = pd.DataFrame({
        "hex_id": ["h1"],
        "populacao_proxy": [10_000.0],
        "score_setor_2022_calibrado": [110.0],
        "score_oportunidade_residual": [110.0],
    })
    result = agregar_cenario_multihex(df, ["h1"])
    assert result["score_dominio_hibrido_max"] == pytest.approx(100.0)


# ── consumo fitness ───────────────────────────────────────────────────────────

def test_consumo_total_soma_concorrentes_e_ultra():
    df = pd.DataFrame({
        "hex_id": ["h1", "h2"],
        "populacao_proxy": [10_000.0, 5_000.0],
        "oferta_consumida_mercado_estimada": [2_000.0, 1_000.0],
        "oferta_consumida_ultra_real": [500.0, 200.0],
    })
    result = agregar_cenario_multihex(df, ["h1", "h2"])
    assert result["consumo_concorrentes_total"] == pytest.approx(3_000.0)
    assert result["consumo_ultra_total"] == pytest.approx(700.0)
    assert result["consumo_total_instalado"] == pytest.approx(3_700.0)


def test_consumo_total_com_apenas_concorrentes():
    df = pd.DataFrame({
        "hex_id": ["h1"],
        "oferta_consumida_mercado_estimada": [1_500.0],
    })
    result = agregar_cenario_multihex(df, ["h1"])
    assert result["consumo_total_instalado"] == pytest.approx(1_500.0)
    assert result["consumo_ultra_total"] is None


def test_presenca_ultra_verdadeiro_quando_ha_unidades():
    df = pd.DataFrame({
        "hex_id": ["h1", "h2"],
        "n_unidades_ultra_performance_hex": [1.0, 0.0],
    })
    result = agregar_cenario_multihex(df, ["h1", "h2"])
    assert result["presenca_ultra"] is True
    assert result["n_unidades_ultra"] == pytest.approx(1.0)


def test_presenca_ultra_falso_sem_unidades():
    df = pd.DataFrame({
        "hex_id": ["h1"],
        "n_unidades_ultra_performance_hex": [0.0],
    })
    result = agregar_cenario_multihex(df, ["h1"])
    assert result["presenca_ultra"] is False


# ── imutabilidade do dataframe de entrada ────────────────────────────────────

def test_nao_muta_dataframe_de_entrada():
    df = _df_base()
    cols_antes = list(df.columns)
    shape_antes = df.shape
    agregar_cenario_multihex(df, ["h1", "h2"])
    assert list(df.columns) == cols_antes
    assert df.shape == shape_antes


# ── hexes_selecionados ────────────────────────────────────────────────────────

def test_hexes_selecionados_contem_apenas_hexes_pedidos():
    df = _df_base()
    result = agregar_cenario_multihex(df, ["h1"])
    assert list(result["hexes_selecionados"]["hex_id"]) == ["h1"]


def test_exportado_via_streamlit_app():
    assert hasattr(streamlit_app, "agregar_cenario_multihex")
    assert callable(streamlit_app.agregar_cenario_multihex)
