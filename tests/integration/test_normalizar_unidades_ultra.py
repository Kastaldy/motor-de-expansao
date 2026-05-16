"""
Teste minimo - Bloco 1: unidades Ultra com performance e coordenadas.
"""

from pathlib import Path

import pandas as pd
import pytest

from jobs.pipelines import normalizar_unidades_ultra as modulo

ROOT = Path(__file__).resolve().parents[2]
ULTRA_RAW_PATH = ROOT / "data" / "ultra" / "Ultra.csv"

SCHEMA_OBRIGATORIO = {
    "unidade",
    "uf",
    "cidade",
    "lat",
    "lng",
    "hex_id_res7",
    "pop_geofusion_1km",
    "densidade_geofusion_1km_km2",
    "faturamento",
    "ativos_pag",
    "alunos_gympass",
    "alunos_totalpass",
    "agregadores",
    "alunos_total",
    "ticket_medio_aluno",
    "status_match_coord",
}


@pytest.fixture(scope="module")
def df() -> pd.DataFrame:
    return modulo.gerar_base()


def test_schema_minimo(df: pd.DataFrame):
    assert SCHEMA_OBRIGATORIO <= set(df.columns), (
        f"Colunas faltando: {SCHEMA_OBRIGATORIO - set(df.columns)}"
    )


def test_total_linhas_preserva_planilha_performance(df: pd.DataFrame):
    assert len(df) == 54
    assert not df["performance_source_index"].duplicated().any()


def test_taxa_match_coord_e_status_explicito(df: pd.DataFrame):
    matched = df["status_match_coord"].str.startswith("casado", na=False)
    assert int(matched.sum()) >= 53
    assert set(df.loc[~matched, "status_match_coord"]) <= {"sem_coord"}


def test_coordenadas_e_h3_em_linhas_casadas(df: pd.DataFrame):
    matched = df["status_match_coord"].str.startswith("casado", na=False)
    validas = df.loc[matched]
    assert validas["lat"].between(-34, 6).all()
    assert validas["lng"].between(-75, -28).all()
    assert validas["hex_id_res7"].notna().all()

    sem_coord = df.loc[~matched]
    assert sem_coord["lat"].isna().all()
    assert sem_coord["lng"].isna().all()
    assert sem_coord["hex_id_res7"].isna().all()


def test_sem_duplicidade_critica_por_unidade_uf(df: pd.DataFrame):
    assert not df.duplicated(subset=["unidade", "uf"]).any()


def test_metricas_performance_convertidas(df: pd.DataFrame):
    assert df["alunos_total"].notna().all()
    assert (df["faturamento"] > 0).all()
    assert (df["ticket_medio_aluno"].dropna() > 0).all()

    praia_grande = df.loc[df["localizacao_raw"].eq("PRAIA GRANDE - SP")].iloc[0]
    assert praia_grande["ticket_medio_aluno"] == pytest.approx(454048 / 6251)


def test_loader_ultra_lida_com_metadado_encoding_e_uf_corrompida():
    assert ULTRA_RAW_PATH.exists(), f"CSV nao encontrado: {ULTRA_RAW_PATH}"
    raw = modulo.carregar_ultra(ULTRA_RAW_PATH)

    assert len(raw) == 150
    assert {"unidade", "uf", "cidade", "lat_raw", "lng_raw", "lat", "lng"} <= set(raw.columns)
    assert raw["lat"].notna().all()
    assert raw["lng"].notna().all()

    al_rows = raw[raw["unidade"].str.contains(r"/\s*AL\s*$", regex=True, na=False)]
    assert not al_rows.empty, "Linha AL nao encontrada no CSV bruto"
    assert set(al_rows["uf"].unique()) == {"AL"}


def test_validar_base_nao_falha(df: pd.DataFrame):
    modulo.validar(df)
