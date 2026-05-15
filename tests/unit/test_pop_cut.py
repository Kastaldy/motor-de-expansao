from __future__ import annotations

import pandas as pd
import pytest

from motor_expansao.dashboard.data import build_pop_cut_lookup, derive_pop_cut_columns


def _df(**kwargs) -> pd.DataFrame:
    defaults = {
        "hex_id": ["h1"],
        "confianca_geografica": ["municipal"],
    }
    defaults.update(kwargs)
    return pd.DataFrame({k: v if isinstance(v, list) else [v] for k, v in defaults.items()})


def test_dado_censitario_granular_usa_setor_2022():
    df = _df(
        confianca_geografica="granular",
        pop_total_setor_2022=15_000.0,
        populacao_proxy=8_000.0,
    )
    result = derive_pop_cut_columns(df)

    assert result.loc[0, "fonte_populacao_corte"] == "setor_2022"
    assert float(result.loc[0, "populacao_corte_hex"]) == 15_000.0
    assert bool(result.loc[0, "flag_pop_min_5k"]) is True


def test_fallback_total_municipal_quando_nao_granular():
    df = _df(
        confianca_geografica="municipal",
        pop_total_setor_2022=15_000.0,
        populacao_proxy=12_000.0,
    )
    result = derive_pop_cut_columns(df)

    assert result.loc[0, "fonte_populacao_corte"] == "total_municipal"
    assert float(result.loc[0, "populacao_corte_hex"]) == 12_000.0
    assert bool(result.loc[0, "flag_pop_min_5k"]) is True


def test_sem_populacao_retorna_ausente_e_flag_false():
    df = _df()
    result = derive_pop_cut_columns(df)

    assert result.loc[0, "fonte_populacao_corte"] == "ausente"
    assert pd.isna(result.loc[0, "populacao_corte_hex"])
    assert bool(result.loc[0, "flag_pop_min_5k"]) is False


def test_abaixo_do_limiar_retorna_flag_false():
    df = _df(
        confianca_geografica="municipal",
        populacao_proxy=3_000.0,
    )
    result = derive_pop_cut_columns(df)

    assert result.loc[0, "fonte_populacao_corte"] == "total_municipal"
    assert bool(result.loc[0, "flag_pop_min_5k"]) is False


def test_exatamente_no_limiar_retorna_flag_true():
    df = _df(
        confianca_geografica="municipal",
        populacao_proxy=5_000.0,
    )
    result = derive_pop_cut_columns(df)

    assert bool(result.loc[0, "flag_pop_min_5k"]) is True


def test_granular_sem_setor_pop_cai_para_total_municipal():
    df = _df(
        confianca_geografica="granular",
        populacao_proxy=11_000.0,
    )
    result = derive_pop_cut_columns(df)

    assert result.loc[0, "fonte_populacao_corte"] == "total_municipal"
    assert bool(result.loc[0, "flag_pop_min_5k"]) is True


def test_pop_min_customizavel():
    df = _df(
        confianca_geografica="municipal",
        populacao_proxy=5_000.0,
    )
    result = derive_pop_cut_columns(df, pop_min=3_000)

    assert bool(result.loc[0, "flag_pop_min_5k"]) is True


def test_nao_altera_score_priorizacao():
    df = _df(
        confianca_geografica="municipal",
        populacao_proxy=20_000.0,
        score_priorizacao=88.0,
        hex_score_estrutural=82.0,
    )
    result = derive_pop_cut_columns(df)

    assert float(result.loc[0, "score_priorizacao"]) == 88.0
    assert float(result.loc[0, "hex_score_estrutural"]) == 82.0


def test_build_pop_cut_lookup_extrai_subset_por_hex_id():
    df = pd.DataFrame([
        {"hex_id": "a", "populacao_corte_hex": 15_000.0, "fonte_populacao_corte": "total_municipal", "flag_pop_min_5k": True, "score_priorizacao": 80.0},
        {"hex_id": "b", "populacao_corte_hex": 5_000.0, "fonte_populacao_corte": "total_municipal", "flag_pop_min_5k": False, "score_priorizacao": 70.0},
    ])
    lookup = build_pop_cut_lookup(df)

    assert set(lookup.columns) == {"hex_id", "populacao_corte_hex", "fonte_populacao_corte", "flag_pop_min_5k"}
    assert len(lookup) == 2
    assert "score_priorizacao" not in lookup.columns


def test_build_pop_cut_lookup_sem_hex_id_retorna_vazio():
    df = pd.DataFrame([{"populacao_corte_hex": 10_000.0}])
    lookup = build_pop_cut_lookup(df)

    assert lookup.empty
