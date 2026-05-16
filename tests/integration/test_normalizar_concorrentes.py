"""
Teste minimo - Bloco 1: normalizacao dos concorrentes mapeados.
"""

from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
PARQUET = ROOT / "data" / "staging" / "concorrentes_mapeados.parquet"

SCHEMA_OBRIGATORIO = {
    "concorrente_id", "rede", "nome_unidade", "lat", "lng",
    "data_coleta", "arquivo_origem", "flag_coord_valida",
    "flag_duplicado_rede_coord", "status_registro", "hex_id_res7",
}

REDES_MINIMAS = {"smart_fit", "bluefit", "panobianco"}


@pytest.fixture(scope="module")
def df():
    assert PARQUET.exists(), f"Parquet nao encontrado: {PARQUET}"
    return pd.read_parquet(PARQUET)


def test_schema(df):
    assert SCHEMA_OBRIGATORIO <= set(df.columns), f"Colunas faltando: {SCHEMA_OBRIGATORIO - set(df.columns)}"


def test_redes_presentes(df):
    redes = set(df["rede"].unique())
    assert REDES_MINIMAS <= redes, f"Redes obrigatorias ausentes: {REDES_MINIMAS - redes}"
    assert len(redes) >= len(REDES_MINIMAS), f"Esperado >= {len(REDES_MINIMAS)} redes, encontrado {len(redes)}"


def test_registros_validos_existem(df):
    validos = df[df["status_registro"] == "valido"]
    assert len(validos) > 0


def test_hex_valido_somente_em_validos(df):
    validos = df[df["status_registro"] == "valido"]
    invalidos = df[df["status_registro"] != "valido"]
    assert validos["hex_id_res7"].notna().all(), "Validos com hex_id nulo"
    assert invalidos["hex_id_res7"].isna().all(), "Invalidos com hex_id preenchido"


def test_coordenadas_no_envelope_brasil(df):
    validos = df[df["status_registro"] == "valido"]
    assert ((validos["lat"] >= -34) & (validos["lat"] <= 6)).all()
    assert ((validos["lng"] >= -75) & (validos["lng"] <= -28)).all()


def test_sem_duplicatas_validas(df):
    validos = df[df["status_registro"] == "valido"]
    dup = validos.duplicated(subset=["rede", "lat", "lng"])
    assert not dup.any(), f"Duplicatas validas encontradas: {dup.sum()}"


def test_concorrente_id_unico_nos_validos(df):
    validos = df[df["status_registro"] == "valido"]
    assert not validos["concorrente_id"].duplicated().any()


def test_contagem_por_rede(df):
    contagem = df[df["status_registro"] == "valido"].groupby("rede").size()
    assert contagem["smart_fit"] > 900
    assert contagem["bluefit"] > 200
    assert contagem["panobianco"] > 400
