"""Testes da ingestão anti-PII da oferta de academias menores (BLK-TP-08).

Usa SEMPRE a fixture sintética SEM PII (`tests/fixtures/oferta_academias_menores_fake.xlsx`),
NUNCA o dump real. Cobre: contrato + dtypes, ZERO PII (parquet/relatório),
agregação correta (`Alunos_Academia` somado; `Total_Alunos_Cluster` NUNCA), res-7,
determinismo, DEDUP por hex e isolamento de import (ast).
"""

from __future__ import annotations

import ast
from pathlib import Path

import h3
import pandas as pd
import pytest

from motor_expansao.demanda_revelada import (
    CONTRATO_COLUNAS_OFERTA_MENORES,
    VERSAO_CONTRATO_OFERTA_MENORES,
    gerar_relatorio_qualidade,
    ingerir_oferta_academias_menores,
)
from motor_expansao.demanda_revelada.oferta_academias_menores import _COLUNAS_PII_LOCAIS

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "oferta_academias_menores_fake.xlsx"
MODULO = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "motor_expansao"
    / "demanda_revelada"
    / "oferta_academias_menores.py"
)

# Hexes res-7 esperados (derivados das coords públicas da fixture).
HEX_SP = h3.latlng_to_cell(-23.5505, -46.6333, 7)  # 87a8100c0ffffff (SP-A + SP-B próximas)
HEX_SP_B = h3.latlng_to_cell(-23.5680, -46.6450, 7)  # 87a8100c5ffffff
HEX_RJ = h3.latlng_to_cell(-22.9068, -43.1729, 7)  # 87a8a06a0ffffff


@pytest.fixture
def df_oferta(tmp_path: Path) -> pd.DataFrame:
    destino = tmp_path / "oferta_academias_menores_h3.parquet"
    return ingerir_oferta_academias_menores(fonte=FIXTURE, destino=destino)


def test_parquet_existe_e_legivel(tmp_path: Path) -> None:
    destino = tmp_path / "oferta_academias_menores_h3.parquet"
    ingerir_oferta_academias_menores(fonte=FIXTURE, destino=destino)
    assert destino.exists()
    lido = pd.read_parquet(destino)
    assert len(lido) == 3  # 3 hexes distintos (linha sem coord é dropada)


def test_contrato_colunas_e_dtypes(df_oferta: pd.DataFrame) -> None:
    assert list(df_oferta.columns) == list(CONTRATO_COLUNAS_OFERTA_MENORES.keys())
    for col, dtype in CONTRATO_COLUNAS_OFERTA_MENORES.items():
        assert str(df_oferta[col].dtype) == dtype, f"{col}: {df_oferta[col].dtype} != {dtype}"
    assert (df_oferta["versao_contrato"] == VERSAO_CONTRATO_OFERTA_MENORES).all()


def test_zero_pii(df_oferta: pd.DataFrame) -> None:
    # Nenhuma coluna PII local (Lat/Lng/Nome/Cluster + total_alunos_cluster) no parquet.
    presentes = {c for c in df_oferta.columns if c.lower() in _COLUNAS_PII_LOCAIS}
    assert presentes == set(), f"PII vazou: {presentes}"
    assert set(df_oferta.columns) == set(CONTRATO_COLUNAS_OFERTA_MENORES)
    # Blindagem explícita: coluna de cluster nunca existe.
    assert "total_alunos_cluster" not in {c.lower() for c in df_oferta.columns}
    assert "n_academias_menores" in df_oferta.columns


def test_hex_res7(df_oferta: pd.DataFrame) -> None:
    for hid in df_oferta["hex_id"]:
        assert h3.is_valid_cell(str(hid))
        assert h3.get_resolution(str(hid)) == 7


def test_agregacao_correta(df_oferta: pd.DataFrame) -> None:
    idx = df_oferta.set_index("hex_id")

    # SP: 2 academias (100+40 alunos), plano tp1 + tp2_plus.
    sp = idx.loc[HEX_SP]
    assert sp["n_academias_menores"] == 2
    assert sp["alunos_academias_menores"] == 140  # Alunos_Academia somado
    assert sp["n_plano_tp1"] == 1
    assert sp["n_plano_tp2_plus"] == 1
    assert sp["n_plano_tp0"] == 0

    # SP-B: 1 academia, 70 alunos, plano tp0.
    spb = idx.loc[HEX_SP_B]
    assert spb["n_academias_menores"] == 1
    assert spb["alunos_academias_menores"] == 70
    assert spb["n_plano_tp0"] == 1

    # RJ: 1 academia, 25 alunos, plano tp7.
    rj = idx.loc[HEX_RJ]
    assert rj["n_academias_menores"] == 1
    assert rj["alunos_academias_menores"] == 25
    assert rj["n_plano_tp7"] == 1


def test_total_alunos_cluster_nunca_somado(df_oferta: pd.DataFrame) -> None:
    # Total_Alunos_Cluster do SP hex é 500 (por cluster) — se fosse somado apareceria
    # 500+500=1000; a soma correta de Alunos_Academia é 140.
    idx = df_oferta.set_index("hex_id")
    assert idx.loc[HEX_SP, "alunos_academias_menores"] == 140
    # Nenhuma coluna carrega o valor do cluster.
    for col in df_oferta.columns:
        if col.startswith(("n_", "alunos_")):
            assert 500 not in df_oferta[col].values or col == "alunos_academias_menores"


def test_reprodutibilidade(tmp_path: Path) -> None:
    d1 = tmp_path / "a.parquet"
    d2 = tmp_path / "b.parquet"
    df1 = ingerir_oferta_academias_menores(fonte=FIXTURE, destino=d1)
    df2 = ingerir_oferta_academias_menores(fonte=FIXTURE, destino=d2)
    pd.testing.assert_frame_equal(df1, df2)
    assert list(df1["hex_id"]) == sorted(df1["hex_id"])


def test_dedup_por_hex(df_oferta: pd.DataFrame, tmp_path: Path) -> None:
    # Concorrente sintético cobre só o hex de SP → overlap = 1 hex, 2 academias / 140 alunos.
    conc = pd.DataFrame({"hex_id_res7": [HEX_SP, "87a0000000fffff"]})
    conc_path = tmp_path / "concorrentes_mapeados.parquet"
    conc.to_parquet(conc_path, index=False)
    md = gerar_relatorio_qualidade(
        df_oferta,
        concorrentes_path=conc_path,
        universo_path=tmp_path / "inexistente.parquet",
        destino_md=tmp_path / "rel.md",
    )
    assert "Hexes em SOBREPOSIÇÃO" in md
    assert "**1**" in md  # 1 hex overlap
    # 2 academias / 140 alunos em hex coberto (SP).
    assert "**2**" in md
    assert "**140**" in md


def test_relatorio_sem_pii(df_oferta: pd.DataFrame, tmp_path: Path) -> None:
    md = gerar_relatorio_qualidade(
        df_oferta,
        concorrentes_path=tmp_path / "inexistente_conc.parquet",
        universo_path=tmp_path / "inexistente_univ.parquet",
        destino_md=tmp_path / "rel.md",
        escrever=False,
    )
    low = md.lower()
    # Nenhum nome de academia da fixture nem token PII na string do relatório.
    for token in ("fake gym", "latitude", "longitude", "nome_academia", "cluster_id", "cpf"):
        assert token not in low, f"token PII no relatório: {token}"


def test_isolamento_import() -> None:
    # O módulo novo NÃO importa de pipelines/m1, dashboard, censo, api.
    src = MODULO.read_text(encoding="utf-8")
    tree = ast.parse(src)
    proibidos = ("pipelines.m1", "dashboard", "censo", "motor_expansao.api")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not any(p in alias.name for p in proibidos), alias.name
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert not any(p in mod for p in proibidos), mod
