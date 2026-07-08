"""Testes unitarios para demanda_premissa.py (BLK-VIAB-02).

Regra absoluta: ZERO leitura de arquivos reais. Todas as fixtures sao sinteticas,
construidas em memoria com pd.DataFrame ou gravadas em tmpdir pelo pytest.
"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from motor_expansao.dimensionamento.demanda_premissa import (
    N_EXTRAPOLACAO_MIN,
    TIERS,
    VERSAO_CONTRATO,
    _assign_tier,
    calcular_tiers,
    carregar_eng_corpo,
    carregar_ultra,
    combinar_bases,
    materializar,
    run,
)

# ---------------------------------------------------------------------------
# Fixtures e helpers sinteticos
# ---------------------------------------------------------------------------

_COLUNAS_SAIDA = [
    "tier_label",
    "metragem_min",
    "metragem_max",
    "n",
    "p10",
    "p50",
    "p90",
    "flag_extrapolacao",
    "versao_contrato",
]

_COLUNAS_PII = ["nome", "lat", "lng", "hex_id", "endereco", "unidade"]


def _df_sintetico() -> pd.DataFrame:
    """22 unidades sinteticas cobrindo todos os tiers.

    - 5 unidades < 1000 m²,   alunos 500-900     (n>=5 -> flag=False)
    - 6 unidades 1000-1499,   alunos 1500-2500   (n>=5 -> flag=False)
    - 5 unidades 1500-1999,   alunos 2000-3500   (n>=5 -> flag=False)
    - 5 unidades 2000-2999,   alunos 3000-4500   (n>=5 -> flag=False)
    - 1 unidade  >= 3000,     alunos 5000         (n=1  -> flag=True)
    """
    metragens = (
        [500.0, 600.0, 700.0, 800.0, 900.0]
        + [1000.0, 1100.0, 1200.0, 1300.0, 1400.0, 1499.0]
        + [1500.0, 1600.0, 1700.0, 1800.0, 1999.0]
        + [2000.0, 2200.0, 2500.0, 2800.0, 2950.0]
        + [3000.0]
    )
    alunos = (
        [500.0, 600.0, 700.0, 800.0, 900.0]
        + [1500.0, 1700.0, 1900.0, 2100.0, 2300.0, 2500.0]
        + [2000.0, 2500.0, 3000.0, 3200.0, 3500.0]
        + [3000.0, 3300.0, 3700.0, 4000.0, 4500.0]
        + [5000.0]
    )
    return pd.DataFrame({"metragem": metragens, "alunos": alunos})


def _parquet_ultra_sintetico(tmp_path: Path) -> Path:
    """Grava um parquet sintetico de Ultra no tmpdir."""
    df = pd.DataFrame(
        {
            "metragem": [800.0, 1200.0, 1700.0, 2300.0, 3200.0],
            "alunos_total": [900.0, 2000.0, 2800.0, 3500.0, 5000.0],
            # Coluna extra que NAO deve ser propagada
            "hex_id": ["h1", "h2", "h3", "h4", "h5"],
        }
    )
    path = tmp_path / "ultra.parquet"
    df.to_parquet(path, index=False)
    return path


def _xlsx_eng_sintetico(tmp_path: Path) -> Path:
    """Grava um xlsx sintetico de Eng Corpo no tmpdir."""
    df = pd.DataFrame(
        {
            "Metragem M²": [750.0, 1100.0, 1600.0, 2500.0, 3500.0],
            "Alunos Totais": [800.0, 1800.0, 2600.0, 3800.0, 6000.0],
            # Coluna extra que NAO deve ser propagada
            "Nome": ["A", "B", "C", "D", "E"],
        }
    )
    path = tmp_path / "eng.xlsx"
    df.to_excel(path, index=False)
    return path


# ---------------------------------------------------------------------------
# Testes de carregar_ultra
# ---------------------------------------------------------------------------


def test_carregar_ultra_sintetico(tmp_path: Path) -> None:
    """carregar_ultra lê parquet sintetico e retorna colunas ['metragem', 'alunos']."""
    path = _parquet_ultra_sintetico(tmp_path)
    df = carregar_ultra(path)
    assert list(df.columns) == ["metragem", "alunos"]
    assert len(df) == 5
    # Sem PII
    for col in _COLUNAS_PII:
        assert col not in df.columns


def test_carregar_ultra_sem_pii(tmp_path: Path) -> None:
    """carregar_ultra nao propaga colunas de PII (lat, lng, hex_id, etc.)."""
    path = _parquet_ultra_sintetico(tmp_path)
    df = carregar_ultra(path)
    for col in _COLUNAS_PII:
        assert col not in df.columns


def test_carregar_ultra_dropa_nan(tmp_path: Path) -> None:
    """carregar_ultra dropa linhas com NaN ou valores <= 0."""
    df_raw = pd.DataFrame(
        {
            "metragem": [1000.0, None, 1200.0, -100.0, 1500.0],
            "alunos_total": [2000.0, 1800.0, None, 3000.0, 0.0],
        }
    )
    path = tmp_path / "ultra_nan.parquet"
    df_raw.to_parquet(path, index=False)
    df = carregar_ultra(path)
    assert len(df) == 1
    assert df["metragem"].iloc[0] == 1000.0


# ---------------------------------------------------------------------------
# Testes de carregar_eng_corpo
# ---------------------------------------------------------------------------


def test_carregar_eng_corpo_sintetico(tmp_path: Path) -> None:
    """carregar_eng_corpo lê xlsx sintetico e retorna colunas ['metragem', 'alunos']."""
    path = _xlsx_eng_sintetico(tmp_path)
    df = carregar_eng_corpo(path)
    assert list(df.columns) == ["metragem", "alunos"]
    assert len(df) == 5
    for col in _COLUNAS_PII:
        assert col not in df.columns


def test_carregar_eng_corpo_sem_pii(tmp_path: Path) -> None:
    """carregar_eng_corpo nao propaga colunas de PII."""
    path = _xlsx_eng_sintetico(tmp_path)
    df = carregar_eng_corpo(path)
    for col in _COLUNAS_PII:
        assert col not in df.columns


# ---------------------------------------------------------------------------
# Testes de combinar_bases
# ---------------------------------------------------------------------------


def test_combinar_bases(tmp_path: Path) -> None:
    """combinar_bases concatena dois DataFrames; resultado tem linhas corretas e so ['metragem','alunos']."""
    ultra_df = carregar_ultra(_parquet_ultra_sintetico(tmp_path))
    eng_df = carregar_eng_corpo(_xlsx_eng_sintetico(tmp_path))
    combined = combinar_bases(ultra_df, eng_df)
    assert list(combined.columns) == ["metragem", "alunos"]
    assert len(combined) == len(ultra_df) + len(eng_df)


def test_combinar_bases_dropa_nan() -> None:
    """combinar_bases dropa linhas invalidas apos concatenacao."""
    ultra_df = pd.DataFrame({"metragem": [1000.0, -1.0], "alunos": [2000.0, 3000.0]})
    eng_df = pd.DataFrame({"metragem": [1500.0], "alunos": [float("nan")]})
    combined = combinar_bases(ultra_df, eng_df)
    assert len(combined) == 1
    assert combined["metragem"].iloc[0] == 1000.0


def test_combinar_bases_sem_pii() -> None:
    """combinar_bases retorna apenas ['metragem', 'alunos'] mesmo se entradas tivessem extras."""
    ultra_df = pd.DataFrame({"metragem": [1000.0], "alunos": [2000.0]})
    eng_df = pd.DataFrame({"metragem": [1500.0], "alunos": [2500.0]})
    combined = combinar_bases(ultra_df, eng_df)
    assert set(combined.columns) == {"metragem", "alunos"}


# ---------------------------------------------------------------------------
# Testes de calcular_tiers
# ---------------------------------------------------------------------------


def test_calcular_tiers_cinco_linhas() -> None:
    """calcular_tiers retorna exatamente 5 linhas."""
    df = _df_sintetico()
    result = calcular_tiers(df)
    assert len(result) == 5


def test_calcular_tiers_ordem() -> None:
    """Os tier_label estao na ordem correta dos TIERS."""
    df = _df_sintetico()
    result = calcular_tiers(df)
    expected = ["<1000", "1000-1499", "1500-1999", "2000-2999", ">=3000"]
    assert list(result["tier_label"]) == expected


def test_calcular_tiers_n_correto() -> None:
    """n por tier bate com o df sintetico injetado."""
    df = _df_sintetico()
    result = calcular_tiers(df)
    ns = dict(zip(result["tier_label"], result["n"], strict=True))
    assert ns["<1000"] == 5
    assert ns["1000-1499"] == 6
    assert ns["1500-1999"] == 5
    assert ns["2000-2999"] == 5
    assert ns[">=3000"] == 1


def test_calcular_tiers_percentis_monotonos() -> None:
    """p10 <= p50 <= p90 em todos os tiers com n >= 1."""
    df = _df_sintetico()
    result = calcular_tiers(df)
    for _, row in result.iterrows():
        if row["n"] >= 1:
            assert row["p10"] <= row["p50"], f"p10>p50 em {row['tier_label']}"
            assert row["p50"] <= row["p90"], f"p50>p90 em {row['tier_label']}"


def test_calcular_tiers_percentis_positivos() -> None:
    """p50 > 0 em todos os tiers com n >= 1."""
    df = _df_sintetico()
    result = calcular_tiers(df)
    for _, row in result.iterrows():
        if row["n"] >= 1:
            assert row["p50"] > 0, f"p50<=0 em {row['tier_label']}"


def test_flag_extrapolacao_true() -> None:
    """Tier com n < N_EXTRAPOLACAO_MIN tem flag_extrapolacao=True."""
    df = _df_sintetico()
    result = calcular_tiers(df)
    # tier >=3000 tem n=1 < 5
    row = result[result["tier_label"] == ">=3000"].iloc[0]
    assert row["flag_extrapolacao"] is True or bool(row["flag_extrapolacao"]) is True


def test_flag_extrapolacao_false() -> None:
    """Tier com n >= N_EXTRAPOLACAO_MIN tem flag_extrapolacao=False."""
    df = _df_sintetico()
    result = calcular_tiers(df)
    for label in ["<1000", "1000-1499", "1500-1999", "2000-2999"]:
        row = result[result["tier_label"] == label].iloc[0]
        assert not bool(row["flag_extrapolacao"]), f"flag True inesperado em {label}"


def test_tier_n_zero_nan_percentis() -> None:
    """Tier sem observacoes tem n=0 e p10/p50/p90 sao NaN."""
    # Cria df sem observacoes no tier >=3000
    df = pd.DataFrame(
        {
            "metragem": [500.0, 1200.0, 1700.0, 2500.0],
            "alunos": [800.0, 2000.0, 2800.0, 3500.0],
        }
    )
    result = calcular_tiers(df)
    row = result[result["tier_label"] == ">=3000"].iloc[0]
    assert int(row["n"]) == 0
    assert math.isnan(float(row["p10"]))
    assert math.isnan(float(row["p50"]))
    assert math.isnan(float(row["p90"]))


def test_versao_contrato() -> None:
    """versao_contrato == 'demanda_premissa_v1' em todas as linhas."""
    df = _df_sintetico()
    result = calcular_tiers(df)
    assert (result["versao_contrato"] == "demanda_premissa_v1").all()
    assert VERSAO_CONTRATO == "demanda_premissa_v1"


def test_colunas_parquet() -> None:
    """DataFrame de tiers tem exatamente as colunas do contrato."""
    df = _df_sintetico()
    result = calcular_tiers(df)
    assert list(result.columns) == _COLUNAS_SAIDA


def test_sem_pii() -> None:
    """Resultado de calcular_tiers nao tem colunas de PII."""
    df = _df_sintetico()
    result = calcular_tiers(df)
    for col in _COLUNAS_PII:
        assert col not in result.columns


def test_determinismo() -> None:
    """calcular_tiers chamada 2x com mesmo df retorna DataFrames identicos."""
    df = _df_sintetico()
    r1 = calcular_tiers(df)
    r2 = calcular_tiers(df)
    pd.testing.assert_frame_equal(r1, r2)


def test_metragem_min_max() -> None:
    """metragem_min/metragem_max batem com as constantes de TIERS; >=3000 tem max=inf."""
    df = _df_sintetico()
    result = calcular_tiers(df)
    for tier in TIERS:
        row = result[result["tier_label"] == tier["tier_label"]].iloc[0]
        assert row["metragem_min"] == tier["metragem_min"]
        if tier["tier_label"] == ">=3000":
            assert math.isinf(float(row["metragem_max"]))
        else:
            assert row["metragem_max"] == tier["metragem_max"]


def test_assign_tier_fronteiras() -> None:
    """Valores exatos de fronteira vao para o tier correto."""
    assert _assign_tier(999.9) == "<1000"
    assert _assign_tier(1000.0) == "1000-1499"
    assert _assign_tier(1499.9) == "1000-1499"
    assert _assign_tier(1500.0) == "1500-1999"
    assert _assign_tier(1999.9) == "1500-1999"
    assert _assign_tier(2000.0) == "2000-2999"
    assert _assign_tier(2999.9) == "2000-2999"
    assert _assign_tier(3000.0) == ">=3000"
    assert _assign_tier(5000.0) == ">=3000"


def test_materializar_cria_arquivos(tmp_path: Path) -> None:
    """materializar em tmpdir cria parquet e md; parquet lê 5 linhas."""
    df = _df_sintetico()
    df_tiers = calcular_tiers(df)
    parquet_path, md_path = materializar(df_tiers, tmp_path, tmp_path)
    assert parquet_path.exists()
    assert md_path.exists()
    df_lido = pd.read_parquet(parquet_path)
    assert len(df_lido) == 5
    assert list(df_lido.columns) == _COLUNAS_SAIDA


def test_run_end_to_end(tmp_path: Path) -> None:
    """run(ultra_path, eng_path, tmpdir, tmpdir) cria parquet com 5 linhas."""
    ultra_path = _parquet_ultra_sintetico(tmp_path)
    eng_path = _xlsx_eng_sintetico(tmp_path)
    parquet_path, md_path = run(ultra_path, eng_path, tmp_path, tmp_path)
    assert parquet_path.exists()
    assert md_path.exists()
    df_lido = pd.read_parquet(parquet_path)
    assert len(df_lido) == 5
    assert "versao_contrato" in df_lido.columns
    assert (df_lido["versao_contrato"] == "demanda_premissa_v1").all()


def test_dec009_sem_geografico() -> None:
    """DEC-009: resultado de calcular_tiers nao tem lat/lng/hex_id como coluna."""
    df = _df_sintetico()
    result = calcular_tiers(df)
    proibidas = ["lat", "lng", "hex_id", "membros"]
    for col in proibidas:
        assert col not in result.columns, f"Coluna proibida encontrada: {col}"


def test_n_extrapolacao_min_constante() -> None:
    """N_EXTRAPOLACAO_MIN == 5 conforme especificado."""
    assert N_EXTRAPOLACAO_MIN == 5


def test_tiers_cinco_entradas() -> None:
    """TIERS deve ter exatamente 5 entradas."""
    assert len(TIERS) == 5


def test_calcular_tiers_n_total_correto() -> None:
    """n total dos tiers bate com o tamanho do df sintetico."""
    df = _df_sintetico()
    result = calcular_tiers(df)
    assert result["n"].sum() == len(df)
