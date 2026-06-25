"""Testes unitários da camada de Validação: Demanda Revelada × Residual Fitness (BLK-TP-02).

NUNCA usa dados reais. Todas as fixtures são sintéticas (geradas em tmp_path).
Cobre: join, arquivo ausente, Spearman IC, quadrantes, divergências,
relatório Markdown, parquet de quadrantes sem PII e smoke de integração.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from motor_expansao.demanda_revelada import COLUNAS_PII_PROIBIDAS
from motor_expansao.demanda_revelada.validacao import (
    calcular_divergencias,
    calcular_spearman_ic,
    carregar_par_validacao,
    executar_validacao_completa,
    gerar_relatorio_validacao,
    mapear_quadrantes,
    salvar_quadrantes_parquet,
)

# ---------------------------------------------------------------------------
# Hexes sintéticos (mesmos do teste de ingestão)
# ---------------------------------------------------------------------------
import h3

HEX_SP = h3.latlng_to_cell(-23.5505, -46.6333, 7)   # 87a8100c0ffffff
HEX_SP_B = h3.latlng_to_cell(-23.5680, -46.6450, 7)  # 87a8100c5ffffff
HEX_RJ = h3.latlng_to_cell(-22.9068, -43.1729, 7)    # 87a8a06a0ffffff

# Dois hexes extras presentes só no mercado (sem demanda)
HEX_MKT_ONLY_A = h3.latlng_to_cell(-23.6000, -46.7000, 7)
HEX_MKT_ONLY_B = h3.latlng_to_cell(-22.8000, -43.2000, 7)


# ---------------------------------------------------------------------------
# Fixtures sintéticas
# ---------------------------------------------------------------------------


@pytest.fixture
def demanda_path(tmp_path: Path) -> Path:
    """Parquet de demanda sintético com 3 hexes."""
    df = pd.DataFrame(
        {
            "hex_id": pd.array([HEX_SP, HEX_SP_B, HEX_RJ], dtype="string"),
            "membros": pd.array([140, 70, 25], dtype="int64"),
        }
    )
    p = tmp_path / "demanda_revelada_h3.parquet"
    df.to_parquet(p, index=False)
    return p


@pytest.fixture
def mercado_path(tmp_path: Path) -> Path:
    """Parquet de mercado sintético com 5 hexes (3 casam com demanda + 2 extras)."""
    df = pd.DataFrame(
        {
            "hex_id": pd.array(
                [HEX_SP, HEX_SP_B, HEX_RJ, HEX_MKT_ONLY_A, HEX_MKT_ONLY_B],
                dtype="string",
            ),
            "score_oportunidade_residual": [80.0, 40.0, 60.0, 90.0, 20.0],
            "oferta_efetiva_disponivel": [2000.0, 1000.0, 1500.0, 2250.0, 500.0],
            "uf": pd.array(["SP", "SP", "RJ", "SP", "RJ"], dtype="string"),
        }
    )
    p = tmp_path / "hexagonos_mercado_mapeado.parquet"
    df.to_parquet(p, index=False)
    return p


@pytest.fixture
def priorizados_path(tmp_path: Path) -> Path:
    """Parquet de priorizados sintético com HEX_SP + um hex ausente na demanda."""
    df = pd.DataFrame(
        {
            "hex_id": pd.array([HEX_SP, HEX_MKT_ONLY_A], dtype="string"),
            "uf": pd.array(["SP", "SP"], dtype="string"),
            "score_priorizacao": [85.0, 92.0],
        }
    )
    p = tmp_path / "brasil_priorizados.parquet"
    df.to_parquet(p, index=False)
    return p


@pytest.fixture
def df_validacao(
    demanda_path: Path, mercado_path: Path, priorizados_path: Path
) -> pd.DataFrame:
    """DataFrame de validação carregado via fixture sintética."""
    return carregar_par_validacao(
        demanda_path=demanda_path,
        mercado_path=mercado_path,
        priorizados_path=priorizados_path,
    )


@pytest.fixture
def df_quad(df_validacao: pd.DataFrame) -> pd.DataFrame:
    """DataFrame com quadrantes mapeados."""
    return mapear_quadrantes(df_validacao)


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


def test_carregar_par_validacao_inner_join(
    demanda_path: Path, mercado_path: Path, priorizados_path: Path
) -> None:
    """Apenas hexes presentes em ambos (demanda E mercado) devem aparecer."""
    df = carregar_par_validacao(
        demanda_path=demanda_path,
        mercado_path=mercado_path,
        priorizados_path=priorizados_path,
    )
    # Inner join: só os 3 hexes comuns
    assert len(df) == 3
    hex_ids = set(df["hex_id"].tolist())
    assert HEX_SP in hex_ids
    assert HEX_SP_B in hex_ids
    assert HEX_RJ in hex_ids
    # Hexes só-mercado NÃO devem aparecer
    assert HEX_MKT_ONLY_A not in hex_ids
    assert HEX_MKT_ONLY_B not in hex_ids
    # Colunas esperadas
    esperadas = {
        "hex_id", "membros", "score_oportunidade_residual",
        "oferta_efetiva_disponivel", "uf", "top_m1_20pct",
    }
    assert set(df.columns) == esperadas


def test_carregar_par_validacao_arquivo_ausente(
    demanda_path: Path, tmp_path: Path, priorizados_path: Path
) -> None:
    """FileNotFoundError com mensagem útil quando mercado_path não existe."""
    inexistente = tmp_path / "nao_existe.parquet"
    with pytest.raises(FileNotFoundError, match="hexagonos_mercado_mapeado|mercado"):
        carregar_par_validacao(
            demanda_path=demanda_path,
            mercado_path=inexistente,
            priorizados_path=priorizados_path,
        )


def test_calcular_spearman_ic_positivo(tmp_path: Path) -> None:
    """Correlação positiva forte: rho > 0, p < 0.05, IC low > 0, IC high <= 1."""
    n = 20
    x = np.arange(n, dtype=float)
    df = pd.DataFrame({"x": x, "y": x + np.random.default_rng(0).normal(0, 0.01, n)})
    res = calcular_spearman_ic(df, "x", "y", n_boot=99, seed=42)
    assert res["rho"] > 0
    assert res["pvalor"] < 0.05
    assert res["ic_low"] > 0
    assert res["ic_high"] <= 1.0
    assert res["n"] >= 3


def test_calcular_spearman_ic_negativo(tmp_path: Path) -> None:
    """Correlação negativa perfeita: rho < 0."""
    n = 10
    x = np.arange(n, dtype=float)
    df = pd.DataFrame({"x": x, "y": -x})
    res = calcular_spearman_ic(df, "x", "y", n_boot=99, seed=42)
    assert res["rho"] < 0


def test_mapear_quadrantes_particao(df_validacao: pd.DataFrame) -> None:
    """Todo hex recebe um quadrante em {Q1,Q2,Q3,Q4} sem NaN; soma = len(df)."""
    df = mapear_quadrantes(df_validacao)
    assert "quadrante" in df.columns
    assert df["quadrante"].notna().all()
    assert set(df["quadrante"].unique()).issubset({"Q1", "Q2", "Q3", "Q4"})
    assert len(df) == len(df_validacao)


def test_mapear_quadrantes_q1_maior_mediana(tmp_path: Path) -> None:
    """Hexes acima da mediana em ambas as colunas devem ser Q1."""
    # Dados controlados: membros 100,200; residual 50,80; medianas = 150 e 65
    df = pd.DataFrame(
        {
            "hex_id": pd.array(["hex_a", "hex_b"], dtype="string"),
            "membros": [100, 200],
            "score_oportunidade_residual": [50.0, 80.0],
            "oferta_efetiva_disponivel": [1000.0, 2000.0],
            "uf": pd.array(["SP", "SP"], dtype="string"),
            "top_m1_20pct": [False, True],
        }
    )
    df_q = mapear_quadrantes(df)
    # hex_b: membros=200 ≥ mediana(150) e residual=80 ≥ mediana(65) → Q1
    row_b = df_q[df_q["hex_id"] == "hex_b"].iloc[0]
    assert row_b["quadrante"] == "Q1"
    # hex_a: membros=100 < mediana(150) e residual=50 < mediana(65) → Q4
    row_a = df_q[df_q["hex_id"] == "hex_a"].iloc[0]
    assert row_a["quadrante"] == "Q4"


def test_calcular_divergencias_shape(df_quad: pd.DataFrame) -> None:
    """q1_fora_top20 tem só hexes Q1 com top_m1_20pct=False; top20_fora_q1 o inverso."""
    div = calcular_divergencias(df_quad)
    q1_fora = div["q1_fora_top20"]
    top20_fora = div["top20_fora_q1"]

    # q1_fora: todos são Q1 e top_m1_20pct=False
    if not q1_fora.empty:
        assert (q1_fora["quadrante"] == "Q1").all()
        assert (~q1_fora["top_m1_20pct"]).all()

    # top20_fora: todos são top_m1_20pct=True e quadrante ≠ Q1
    if not top20_fora.empty:
        assert top20_fora["top_m1_20pct"].all()
        assert (top20_fora["quadrante"] != "Q1").all()


def test_gerar_relatorio_contem_secoes(
    df_quad: pd.DataFrame, tmp_path: Path
) -> None:
    """Markdown gerado deve conter as strings-chave de cada uma das 7 seções."""
    sp = calcular_spearman_ic(df_quad, "membros", "score_oportunidade_residual")
    ss = calcular_spearman_ic(df_quad, "membros", "oferta_efetiva_disponivel")
    div = calcular_divergencias(df_quad)
    lim_r = float(df_quad["score_oportunidade_residual"].median())
    lim_d = float(df_quad["membros"].median())

    destino = tmp_path / "relatorio.md"
    conteudo = gerar_relatorio_validacao(
        df=df_quad,
        spearman_primario=sp,
        spearman_secundario=ss,
        limiar_residual=lim_r,
        limiar_demanda=lim_d,
        divergencias=div,
        destino=destino,
    )

    # Verifica que o arquivo foi gerado
    assert destino.exists()
    assert len(conteudo) > 100

    # Seções obrigatórias
    assert "## 1. Resumo Executivo" in conteudo
    assert "## 2. Metodologia" in conteudo
    assert "## 3. Resultados Spearman Primário" in conteudo
    assert "## 4. Resultados Spearman Secundário" in conteudo
    assert "## 5. Mapa de Quadrantes" in conteudo
    assert "## 6. Divergências vs. M1" in conteudo
    assert "## 7. Guardrails e Proibições" in conteudo

    # Conteúdo mínimo
    assert "rho" in conteudo
    assert "Q1" in conteudo
    assert "DEC-009" in conteudo


def test_salvar_quadrantes_zero_pii(df_quad: pd.DataFrame, tmp_path: Path) -> None:
    """Parquet de quadrantes não pode conter nenhuma coluna de COLUNAS_PII_PROIBIDAS."""
    destino = tmp_path / "quadrantes.parquet"
    salvar_quadrantes_parquet(df_quad, destino=destino)
    assert destino.exists()
    lido = pd.read_parquet(destino)
    pii_presentes = set(lido.columns) & COLUNAS_PII_PROIBIDAS
    assert pii_presentes == set(), f"PII no parquet de quadrantes: {pii_presentes}"


def test_salvar_quadrantes_colunas(df_quad: pd.DataFrame, tmp_path: Path) -> None:
    """Parquet de quadrantes deve ter exatamente as 7 colunas canônicas."""
    destino = tmp_path / "quadrantes.parquet"
    salvar_quadrantes_parquet(df_quad, destino=destino)
    lido = pd.read_parquet(destino)
    esperadas = {
        "hex_id",
        "membros",
        "score_oportunidade_residual",
        "oferta_efetiva_disponivel",
        "uf",
        "quadrante",
        "top_m1_20pct",
    }
    assert set(lido.columns) == esperadas


def test_executar_validacao_completa_integracao(
    demanda_path: Path,
    mercado_path: Path,
    priorizados_path: Path,
    tmp_path: Path,
) -> None:
    """Smoke: executar_validacao_completa retorna dict com todas as chaves esperadas
    e gera relatório Markdown e parquet em tmp_path."""
    relatorio_path = tmp_path / "relatorio.md"
    quadrantes_path = tmp_path / "quadrantes.parquet"

    resultado = executar_validacao_completa(
        demanda_path=demanda_path,
        mercado_path=mercado_path,
        priorizados_path=priorizados_path,
        relatorio_path=relatorio_path,
        quadrantes_path=quadrantes_path,
        salvar_quadrantes=True,
    )

    # Chaves obrigatórias no retorno
    chaves_esperadas = {
        "n_hexes_join",
        "spearman_primario",
        "spearman_secundario",
        "contagem_quadrantes",
        "n_q1_fora_top20",
        "n_top20_fora_q1",
    }
    assert chaves_esperadas == set(resultado.keys())

    # Valores básicos
    assert resultado["n_hexes_join"] == 3  # inner join de 3 hexes sintéticos
    assert isinstance(resultado["spearman_primario"], dict)
    assert "rho" in resultado["spearman_primario"]
    assert isinstance(resultado["spearman_secundario"], dict)
    assert isinstance(resultado["contagem_quadrantes"], dict)
    assert isinstance(resultado["n_q1_fora_top20"], int)
    assert isinstance(resultado["n_top20_fora_q1"], int)

    # Arquivos gerados
    assert relatorio_path.exists(), "Relatório Markdown não foi gerado"
    assert quadrantes_path.exists(), "Parquet de quadrantes não foi gerado"

    # Parquet de quadrantes sem PII
    lido = pd.read_parquet(quadrantes_path)
    pii = set(lido.columns) & COLUNAS_PII_PROIBIDAS
    assert pii == set(), f"PII no parquet: {pii}"
