"""Testes da classificação anti-PII de rede das academias menores (BLK-TP-08-FU).

Usa SEMPRE a fixture sintética SEM PII (`tests/fixtures/rede_menor_fake.xlsx`) com nomes
FABRICADOS carregando tokens de rede, NUNCA o dump real. Cobre: classificação por token
com word-boundary (incl. falso-positivo EVITADO), colapso de rede N<3 em `independente`,
ZERO PII nos 2 artefatos, agregação hex×rede correta, média/mediana/`flag_confiavel`,
isolamento de import (ast) e determinismo.
"""

from __future__ import annotations

import ast
from pathlib import Path

import h3
import pandas as pd
import pytest

from motor_expansao.demanda_revelada import (
    CONTRATO_COLUNAS_CAP_REDE,
    CONTRATO_COLUNAS_OFERTA_MENORES_REDE,
    VERSAO_CONTRATO_CAP_REDE,
    VERSAO_CONTRATO_OFERTA_MENORES_REDE,
    classificar_rede,
    gerar_capacidade_media_por_rede,
    gerar_relatorio_classificacao,
    ingerir_oferta_menores_por_rede,
)
from motor_expansao.demanda_revelada.classificacao_rede_menor import (
    _COLUNAS_PII_LOCAIS,
    CATEGORIA_INDEPENDENTE,
    _ler_e_derivar_hex_rede,
)

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "rede_menor_fake.xlsx"
MODULO = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "motor_expansao"
    / "demanda_revelada"
    / "classificacao_rede_menor.py"
)

HEX_SP_A = h3.latlng_to_cell(-23.5505, -46.6333, 7)  # smart_fit x2 + falso 'live'
HEX_SP_B = h3.latlng_to_cell(-23.568, -46.645, 7)    # panobianco x3 + falso 'race'
HEX_RJ = h3.latlng_to_cell(-22.9068, -43.1729, 7)    # bluefit x1 (colapsa) + generic


@pytest.fixture
def df_oferta(tmp_path: Path) -> pd.DataFrame:
    destino = tmp_path / "oferta_academias_menores_rede_h3.parquet"
    return ingerir_oferta_menores_por_rede(fonte=FIXTURE, destino=destino)


@pytest.fixture
def df_cap(tmp_path: Path) -> pd.DataFrame:
    destino = tmp_path / "capacidade_media_por_rede.parquet"
    return gerar_capacidade_media_por_rede(fonte=FIXTURE, destino=destino)


# --------------------------------------------------------------------------------------
# Classificação por token (puro)
# --------------------------------------------------------------------------------------
def test_classificacao_por_token_boundary() -> None:
    assert classificar_rede("Academia Smart Fit Centro") == "smart_fit"
    assert classificar_rede("SMARTFIT Unidade 2") == "smart_fit"
    assert classificar_rede("Panobianco Vila X") == "panobianco"
    assert classificar_rede("Blue Fit Copacabana") == "bluefit"
    assert classificar_rede("PANOBIANCO Norte") == "panobianco"


def test_falso_positivo_evitado() -> None:
    # 'live' dentro de "Studio Live Well" NÃO deve casar rede 'live' (só marca composta).
    assert classificar_rede("Studio Live Well") == CATEGORIA_INDEPENDENTE
    # 'race' dentro de "Terrace Fit Club" NÃO casa 'race_bootcamp' (word-boundary).
    assert classificar_rede("Terrace Fit Club") == CATEGORIA_INDEPENDENTE
    # substrings genéricas viram independente.
    assert classificar_rede("Academia do Joao") == CATEGORIA_INDEPENDENTE
    assert classificar_rede("Grace Pilates") == CATEGORIA_INDEPENDENTE
    # 'phd' sozinho é ambíguo → só 'phd sports' casa.
    assert classificar_rede("PHD Consultoria") == CATEGORIA_INDEPENDENTE
    assert classificar_rede("PHD Sports Barra") == "phd_sports"
    assert classificar_rede("") == CATEGORIA_INDEPENDENTE
    assert classificar_rede(None) == CATEGORIA_INDEPENDENTE


def test_normalizacao_acentos() -> None:
    # Acento/pontuação não devem quebrar o match.
    assert classificar_rede("Bio-Ritmo!") == "bio_ritmo"
    assert classificar_rede("Cia Athlética") == "cia_athletica"


# --------------------------------------------------------------------------------------
# Colapso anti-reidentificação
# --------------------------------------------------------------------------------------
def test_colapso_baixa_cardinalidade(df_oferta: pd.DataFrame) -> None:
    # Com limiar 3: bluefit(1) e smart_fit(2) colapsam em independente; panobianco(3) sobrevive.
    redes = set(df_oferta["rede_menor"].astype(str))
    assert "bluefit" not in redes
    assert "smart_fit" not in redes
    assert "panobianco" in redes
    assert CATEGORIA_INDEPENDENTE in redes


def test_colapso_detalhado() -> None:
    # panobianco=3 (sobrevive), smart_fit=2 e bluefit=1 (colapsam com limiar 3).
    df = _ler_e_derivar_hex_rede(FIXTURE, n_min_anti_reid=3)
    contagem = df["rede_menor"].value_counts()
    assert "panobianco" in contagem.index
    assert "smart_fit" not in contagem.index
    assert "bluefit" not in contagem.index
    # com limiar 2, smart_fit(2) sobrevive, bluefit(1) colapsa.
    df2 = _ler_e_derivar_hex_rede(FIXTURE, n_min_anti_reid=2)
    contagem2 = df2["rede_menor"].value_counts()
    assert "smart_fit" in contagem2.index
    assert "bluefit" not in contagem2.index


# --------------------------------------------------------------------------------------
# ZERO PII nos 2 artefatos + relatório
# --------------------------------------------------------------------------------------
def test_zero_pii(df_oferta: pd.DataFrame, df_cap: pd.DataFrame) -> None:
    for df in (df_oferta, df_cap):
        presentes = {c for c in df.columns if c.lower() in _COLUNAS_PII_LOCAIS}
        assert presentes == set(), f"PII vazou: {presentes}"
    assert set(df_oferta.columns) == set(CONTRATO_COLUNAS_OFERTA_MENORES_REDE)
    assert set(df_cap.columns) == set(CONTRATO_COLUNAS_CAP_REDE)
    for pii in ("nome_academia", "latitude", "longitude", "cluster_id", "total_alunos_cluster"):
        assert pii not in {c.lower() for c in df_oferta.columns}
        assert pii not in {c.lower() for c in df_cap.columns}


def test_contrato_colunas_e_dtypes(df_oferta: pd.DataFrame, df_cap: pd.DataFrame) -> None:
    assert list(df_oferta.columns) == list(CONTRATO_COLUNAS_OFERTA_MENORES_REDE.keys())
    for col, dtype in CONTRATO_COLUNAS_OFERTA_MENORES_REDE.items():
        assert str(df_oferta[col].dtype) == dtype, f"{col}: {df_oferta[col].dtype} != {dtype}"
    assert list(df_cap.columns) == list(CONTRATO_COLUNAS_CAP_REDE.keys())
    for col, dtype in CONTRATO_COLUNAS_CAP_REDE.items():
        assert str(df_cap[col].dtype) == dtype, f"{col}: {df_cap[col].dtype} != {dtype}"
    assert (df_oferta["versao_contrato"] == VERSAO_CONTRATO_OFERTA_MENORES_REDE).all()
    assert (df_cap["versao_contrato"] == VERSAO_CONTRATO_CAP_REDE).all()


def test_relatorio_sem_pii(df_oferta: pd.DataFrame, df_cap: pd.DataFrame, tmp_path: Path) -> None:
    df_front = _ler_e_derivar_hex_rede(FIXTURE)
    md = gerar_relatorio_classificacao(
        df_front,
        df_oferta,
        df_cap,
        concorrentes_path=tmp_path / "inexistente.parquet",
        destino_md=tmp_path / "rel.md",
        escrever=False,
    )
    low = md.lower()
    for token in ("smart fit centro", "copacabana", "latitude", "longitude", "cluster_id", "cpf"):
        assert token not in low, f"token PII no relatório: {token}"


# --------------------------------------------------------------------------------------
# Agregação hex×rede
# --------------------------------------------------------------------------------------
def test_agregacao_hex_rede(df_oferta: pd.DataFrame) -> None:
    idx = df_oferta.set_index(["hex_id", "rede_menor"])
    # SP-A smart_fit colapsa (N=2<3) → vira independente: 100+200=300 alunos + o 'live' fp (30).
    assert (HEX_SP_A, "independente") in idx.index
    assert int(idx.loc[(HEX_SP_A, "independente"), "alunos_academias_menores"]) == 330
    assert int(idx.loc[(HEX_SP_A, "independente"), "n_academias_menores"]) == 3
    # SP-B panobianco sobrevive (N=3): 300+320+280=900; terrace fp vira independente (50).
    assert int(idx.loc[(HEX_SP_B, "panobianco"), "alunos_academias_menores"]) == 900
    assert int(idx.loc[(HEX_SP_B, "panobianco"), "n_academias_menores"]) == 3
    assert int(idx.loc[(HEX_SP_B, "independente"), "alunos_academias_menores"]) == 50
    # Total_Alunos_Cluster (999/888/77) nunca somado.
    assert 999 not in df_oferta["alunos_academias_menores"].to_numpy()
    assert 888 not in df_oferta["alunos_academias_menores"].to_numpy()


def test_hex_res7(df_oferta: pd.DataFrame) -> None:
    for hid in df_oferta["hex_id"]:
        assert h3.is_valid_cell(str(hid))
        assert h3.get_resolution(str(hid)) == 7


# --------------------------------------------------------------------------------------
# Capacidade média/mediana por rede
# --------------------------------------------------------------------------------------
def test_capacidade_media_mediana(df_cap: pd.DataFrame) -> None:
    # `independente` nunca aparece na tabela de capacidade.
    assert CATEGORIA_INDEPENDENTE not in set(df_cap["rede_menor"].astype(str))
    # panobianco: 3 filiais (300,320,280) → média 300, mediana 300; N<10 → não confiável.
    pano = df_cap.set_index("rede_menor").loc["panobianco"]
    assert int(pano["n_filiais"]) == 3
    assert pano["media_alunos"] == pytest.approx(300.0)
    assert pano["mediana_alunos"] == pytest.approx(300.0)
    assert bool(pano["flag_confiavel"]) is False  # 3 < 10


# --------------------------------------------------------------------------------------
# Isolamento de import (ast)
# --------------------------------------------------------------------------------------
def test_isolamento_import() -> None:
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


# --------------------------------------------------------------------------------------
# Determinismo
# --------------------------------------------------------------------------------------
def test_determinismo(tmp_path: Path) -> None:
    d1 = tmp_path / "a.parquet"
    d2 = tmp_path / "b.parquet"
    df1 = ingerir_oferta_menores_por_rede(fonte=FIXTURE, destino=d1)
    df2 = ingerir_oferta_menores_por_rede(fonte=FIXTURE, destino=d2)
    pd.testing.assert_frame_equal(df1, df2)
    assert list(df1[["hex_id", "rede_menor"]].itertuples(index=False)) == sorted(
        df1[["hex_id", "rede_menor"]].itertuples(index=False)
    )
    c1 = gerar_capacidade_media_por_rede(fonte=FIXTURE, destino=tmp_path / "c1.parquet")
    c2 = gerar_capacidade_media_por_rede(fonte=FIXTURE, destino=tmp_path / "c2.parquet")
    pd.testing.assert_frame_equal(c1, c2)
