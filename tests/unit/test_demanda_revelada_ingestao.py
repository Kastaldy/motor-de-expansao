"""Testes da camada de Demanda Revelada (BLK-TP-01).

Usa SEMPRE a fixture sintética SEM PII (`tests/fixtures/demanda_revelada_fake.html`),
NUNCA o dump real. Cobre: parquet legível, contrato de 9 colunas + dtypes, zero PII,
res-7, join por `hex_id`, reprodutibilidade e correção da agregação.
"""

from __future__ import annotations

from pathlib import Path

import h3
import pandas as pd
import pytest

from motor_expansao.demanda_revelada import (
    COLUNAS_PII_PROIBIDAS,
    CONTRATO_COLUNAS,
    VERSAO_CONTRATO,
    ingerir_demanda_revelada,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "demanda_revelada_fake.html"

# Hexes res-7 esperados (derivados das coords públicas da fixture).
HEX_SP = h3.latlng_to_cell(-23.5505, -46.6333, 7)  # 87a8100c0ffffff (SP-A1 + A2)
HEX_SP_B = h3.latlng_to_cell(-23.5680, -46.6450, 7)  # 87a8100c5ffffff
HEX_RJ = h3.latlng_to_cell(-22.9068, -43.1729, 7)  # 87a8a06a0ffffff


@pytest.fixture
def df_demanda(tmp_path: Path) -> pd.DataFrame:
    destino = tmp_path / "demanda_revelada_h3.parquet"
    return ingerir_demanda_revelada(fonte=FIXTURE, destino=destino)


def test_parquet_existe_e_legivel(tmp_path: Path) -> None:
    destino = tmp_path / "demanda_revelada_h3.parquet"
    ingerir_demanda_revelada(fonte=FIXTURE, destino=destino)
    assert destino.exists()
    lido = pd.read_parquet(destino)
    assert len(lido) == 3  # 3 hexes distintos na fixture


def test_contrato_colunas_e_dtypes(df_demanda: pd.DataFrame) -> None:
    assert list(df_demanda.columns) == list(CONTRATO_COLUNAS.keys())
    for col, dtype in CONTRATO_COLUNAS.items():
        assert str(df_demanda[col].dtype) == dtype, f"{col}: {df_demanda[col].dtype} != {dtype}"
    assert (df_demanda["versao_contrato"] == VERSAO_CONTRATO).all()


def test_zero_pii(df_demanda: pd.DataFrame) -> None:
    proibidas_presentes = set(df_demanda.columns) & COLUNAS_PII_PROIBIDAS
    assert proibidas_presentes == set(), f"PII vazou: {proibidas_presentes}"
    # Nenhuma coluna fora do contrato (ex.: 'sf_nome' da célula não deve sobreviver).
    assert set(df_demanda.columns) == set(CONTRATO_COLUNAS)


def test_hex_res7(df_demanda: pd.DataFrame) -> None:
    for hid in df_demanda["hex_id"]:
        assert h3.is_valid_cell(str(hid))
        assert h3.get_resolution(str(hid)) == 7


def test_join_hex_id(df_demanda: pd.DataFrame) -> None:
    # Frame de mercado sintético com hex_id (str) — casa por hex_id sem erro de tipo.
    mercado = pd.DataFrame(
        {
            "hex_id": pd.array([HEX_SP, HEX_RJ, "87a8100c1ffffff"], dtype="string"),
            "score_oportunidade_residual": [55.0, 30.0, 10.0],
        }
    )
    joined = mercado.merge(df_demanda, on="hex_id", how="left")
    casados = joined["membros"].notna().sum()
    assert casados >= 2  # HEX_SP e HEX_RJ casam
    assert joined.loc[joined["hex_id"] == HEX_SP, "membros"].iloc[0] == 140


def test_reprodutibilidade(tmp_path: Path) -> None:
    d1 = tmp_path / "a.parquet"
    d2 = tmp_path / "b.parquet"
    df1 = ingerir_demanda_revelada(fonte=FIXTURE, destino=d1)
    df2 = ingerir_demanda_revelada(fonte=FIXTURE, destino=d2)
    # Ordenado por hex_id → conteúdo idêntico entre execuções.
    pd.testing.assert_frame_equal(df1, df2)
    assert list(df1["hex_id"]) == sorted(df1["hex_id"])


def test_agregacao_correta(df_demanda: pd.DataFrame) -> None:
    idx = df_demanda.set_index("hex_id")

    # SP: duas células somam membros (100+40), banda gt5km só a de idx=5 (40),
    # dist mínima = 900, 2 células, 1 parceira (q=300), 1 unidade SF.
    sp = idx.loc[HEX_SP]
    assert sp["membros"] == 140
    assert sp["membros_gt5km_concorrente_lc"] == 40
    assert sp["dist_concorrente_lc_min_m"] == 900.0
    assert sp["n_celulas_agregadas"] == 2
    assert sp["n_acad_parceiras"] == 1
    assert sp["alunos_parceiras"] == 300
    assert sp["n_concorrente_lc"] == 1

    # SP-B: 1 célula, sem gt5km, sem parceira, sem SF.
    spb = idx.loc[HEX_SP_B]
    assert spb["membros"] == 70
    assert spb["membros_gt5km_concorrente_lc"] == 0
    assert spb["n_celulas_agregadas"] == 1
    assert spb["n_acad_parceiras"] == 0
    assert spb["n_concorrente_lc"] == 0

    # RJ: 1 célula gt5km, 1 parceira (q=80), sem SF.
    rj = idx.loc[HEX_RJ]
    assert rj["membros"] == 25
    assert rj["membros_gt5km_concorrente_lc"] == 25
    assert rj["dist_concorrente_lc_min_m"] == 8000.0
    assert rj["n_acad_parceiras"] == 1
    assert rj["alunos_parceiras"] == 80
    assert rj["n_concorrente_lc"] == 0


def test_nao_le_var_de_ruido(df_demanda: pd.DataFrame) -> None:
    # A var RAW_FAKE (com PII) existe no HTML mas NÃO é parseada → nada vaza.
    flat = df_demanda.to_csv(index=False)
    assert "cpf" not in flat.lower()
    assert "employee_id" not in flat.lower()
    assert "residencial" not in flat.lower()
