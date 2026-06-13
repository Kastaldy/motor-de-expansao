"""Testes do catchment batch (mock do helper geometrico; sem cruzamento real)."""

from __future__ import annotations

import pandas as pd

import motor_expansao.dimensionamento.catchment_batch as cb
from motor_expansao.dimensionamento.catchment_batch import (
    CATCHMENT_COLUNAS,
    calcular_catchment_batch,
    calcular_catchment_unidade,
)


def _fake_setores():
    # so precisa ser nao-vazio; o helper e mockado.
    return pd.DataFrame({"geometry_wkb": [b"x"], "pop_total_setor_2022": [100.0]})


def test_calcular_catchment_unidade_usa_helper(monkeypatch):
    def fake_helper(lat, lng, setores_df, raio_km=1.5):
        return {
            "pop_total_raio": 1234.5,
            "renda_per_capita_media_raio": 5000.0,
            "n_setores": 7,
        }

    monkeypatch.setattr(cb, "analisar_ponto_censitario_setores", fake_helper)
    out = calcular_catchment_unidade(-23.0, -46.0, _fake_setores(), raio_km=1.5)
    assert out["pop_captacao"] == 1234.5
    assert out["renda_per_capita_captacao"] == 5000.0
    assert out["n_setores_captacao"] == 7
    assert out["raio_km"] == 1.5


def test_calcular_catchment_unidade_latlng_null(monkeypatch):
    chamado = {"n": 0}

    def fake_helper(*a, **k):
        chamado["n"] += 1
        return {}

    monkeypatch.setattr(cb, "analisar_ponto_censitario_setores", fake_helper)
    out = calcular_catchment_unidade(None, None, _fake_setores())
    assert pd.isna(out["pop_captacao"])
    assert pd.isna(out["renda_per_capita_captacao"])
    assert out["n_setores_captacao"] == 0
    # helper NAO deve ser chamado quando lat/lng e NULL
    assert chamado["n"] == 0


def test_calcular_catchment_unidade_setores_vazio(monkeypatch):
    monkeypatch.setattr(
        cb,
        "analisar_ponto_censitario_setores",
        lambda *a, **k: {"pop_total_raio": 1.0},
    )
    out = calcular_catchment_unidade(-23.0, -46.0, pd.DataFrame())
    assert pd.isna(out["pop_captacao"])


def test_calcular_catchment_batch_colunas_e_null(monkeypatch):
    def fake_helper(lat, lng, setores_df, raio_km=1.5):
        return {
            "pop_total_raio": 1000.0 + lat,
            "renda_per_capita_media_raio": 4000.0,
            "n_setores": 3,
        }

    monkeypatch.setattr(cb, "analisar_ponto_censitario_setores", fake_helper)

    def fake_loader(base_dir, uf):
        return _fake_setores()

    perf = pd.DataFrame(
        {
            "unidade": ["VILA MARIANA", "CAMPO LIMPO", "Aguas Lindas - GO"],
            "uf": ["SP", "SP", "GO"],
            "cidade": ["SP", None, "GO"],
            "lat": [-23.0, None, -15.7],
            "lng": [-46.6, None, -48.2],
        }
    )
    df = calcular_catchment_batch(perf, setores_loader=fake_loader)
    assert list(df.columns) == list(CATCHMENT_COLUNAS)
    assert len(df) == 3
    # unidade com lat/lng null -> pop_captacao NaN
    campo = df.loc[df["unidade"] == "CAMPO LIMPO"].iloc[0]
    assert pd.isna(campo["pop_captacao"])
    # normalizacao remove o sufixo de UF
    aguas = df.loc[df["unidade"] == "Aguas Lindas - GO"].iloc[0]
    assert aguas["unidade_norm"] == "AGUAS LINDAS"
    assert aguas["pop_captacao"] == 1000.0 + (-15.7)


def test_calcular_catchment_batch_cache_uf(monkeypatch):
    monkeypatch.setattr(
        cb,
        "analisar_ponto_censitario_setores",
        lambda *a, **k: {"pop_total_raio": 1.0, "renda_per_capita_media_raio": 2.0, "n_setores": 1},
    )
    chamadas = {"n": 0}

    def fake_loader(base_dir, uf):
        chamadas["n"] += 1
        return _fake_setores()

    perf = pd.DataFrame(
        {
            "unidade": ["A", "B", "C"],
            "uf": ["SP", "SP", "RJ"],
            "lat": [-23.0, -23.1, -22.9],
            "lng": [-46.0, -46.1, -43.2],
        }
    )
    calcular_catchment_batch(perf, setores_loader=fake_loader)
    # SP carregado 1x (cache), RJ 1x -> 2 chamadas, nao 3
    assert chamadas["n"] == 2


def test_batch_vazio_retorna_colunas():
    df = calcular_catchment_batch(
        pd.DataFrame(columns=["unidade", "uf", "lat", "lng"]),
        setores_loader=lambda b, u: pd.DataFrame(),
    )
    assert list(df.columns) == list(CATCHMENT_COLUNAS)
    assert df.empty
