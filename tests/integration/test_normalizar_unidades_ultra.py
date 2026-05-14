"""
Teste minimo - Bloco 2: normalizacao das unidades Ultra.
"""

from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
PARQUET = ROOT / "data" / "staging" / "unidades_ultra_mapeadas.parquet"

SCHEMA_OBRIGATORIO = {
    "ultra_id", "unidade", "uf", "cidade", "lat", "lng",
    "flag_coord_valida", "hex_id_res7",
}

UFS_PRESENTES_ESPERADAS = {"SP", "DF", "RJ", "ES"}


@pytest.fixture(scope="module")
def df():
    assert PARQUET.exists(), f"Parquet nao encontrado: {PARQUET}"
    return pd.read_parquet(PARQUET)


def test_schema(df):
    assert SCHEMA_OBRIGATORIO <= set(df.columns), (
        f"Colunas faltando: {SCHEMA_OBRIGATORIO - set(df.columns)}"
    )


def test_total_linhas(df):
    assert len(df) == 150, f"Esperado 150 linhas, encontrado {len(df)}"


def test_todas_coords_validas(df):
    invalidas = (~df["flag_coord_valida"]).sum()
    assert invalidas == 0, f"{invalidas} linhas com coordenada invalida"


def test_hex_preenchido_em_validas(df):
    validas = df[df["flag_coord_valida"]]
    assert validas["hex_id_res7"].notna().all(), "Linhas validas com hex_id nulo"


def test_coordenadas_no_envelope_brasil(df):
    assert ((df["lat"] >= -34) & (df["lat"] <= 6)).all()
    assert ((df["lng"] >= -75) & (df["lng"] <= -28)).all()


def test_ultra_id_unico(df):
    assert not df["ultra_id"].duplicated().any(), "ultra_id duplicado encontrado"


def test_ufs_principais_presentes(df):
    ufs = set(df["uf"].unique())
    assert UFS_PRESENTES_ESPERADAS <= ufs, (
        f"UFs esperadas ausentes: {UFS_PRESENTES_ESPERADAS - ufs}"
    )


def test_uf_al_corrigida(df):
    """Linha 'Farol / AL' tem ESTADO corrompido no CSV; deve ser corrigido para AL."""
    al_rows = df[df["uf"] == "AL"]
    assert len(al_rows) >= 1, "Linha AL nao encontrada (correcao de UF falhou)"
    assert all(al_rows["flag_coord_valida"]), "Linha AL com coord invalida"


def test_uf_formato_valido(df):
    invalidas = df[~df["uf"].str.match(r"^[A-Z]{2}$", na=False)]
    assert len(invalidas) == 0, (
        f"UFs com formato invalido:\n{invalidas[['unidade','uf']]}"
    )
