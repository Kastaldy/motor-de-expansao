"""Testes unitários para scripts/movimentacao_concorrencial.py.

Todos os testes usam fixtures sintéticas em memória —
nenhum parquet real de staging é lido.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from scripts.movimentacao_concorrencial import (
    gerar_relatorio,
    impacto_residual,
    join_uf_cidade,
    rede_dominante_por_uf,
    resumo_densos,
    resumo_por_rede,
    resumo_por_uf,
    run,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def df_conc_fake() -> pd.DataFrame:
    """5 linhas: 3 válidas (2 redes, 2 UF via hex + 1 sem match), 1 descartado_duplicado, 1 descartado_coord.

    c1: hex 87a8c2090ffffff → SP (encontra no mercado)
    c2: hex 87a9d46cbffffff → RJ (encontra no mercado)
    c3: hex 87000000dffffff → não existe no mercado → uf=NaN
    c4: descartado_duplicado (não entra no join)
    c5: descartado_coord (não entra no join)
    """
    return pd.DataFrame(
        {
            "concorrente_id": ["c1", "c2", "c3", "c4", "c5"],
            "rede": ["smart_fit", "bluefit", "smart_fit", "smart_fit", "bluefit"],
            "nome_unidade": ["SF SP", "BF RJ", "SF SP2", "SF dup", "BF inval"],
            "lat": [-23.5, -22.9, -23.6, -23.5, -99.0],
            "lng": [-46.6, -43.1, -46.7, -46.6, 0.0],
            "hex_id_res7": [
                "87a8c2090ffffff",
                "87a9d46cbffffff",
                "87000000dffffff",   # hex sem match no mercado → uf=NaN
                "87a8c2090ffffff",
                "87000000dffffff",
            ],
            "flag_coord_valida": [True, True, True, True, False],
            "flag_duplicado_rede_coord": [False, False, False, True, False],
            "status_registro": [
                "valido",
                "valido",
                "valido",
                "descartado_duplicado",
                "descartado_coord",
            ],
            "data_coleta": pd.to_datetime(["2026-04-22"] * 5),
            "arquivo_origem": ["x"] * 5,
        }
    )


@pytest.fixture()
def df_mkt_fake() -> pd.DataFrame:
    """3 hexes com uf/nome_municipio/oferta."""
    return pd.DataFrame(
        {
            "hex_id": [
                "87a8c2090ffffff",
                "87a9d46cbffffff",
                "87aaaaaaaaffffff",
            ],
            "uf": ["SP", "RJ", "MG"],
            "nome_municipio": ["São Paulo", "Rio de Janeiro", "Belo Horizonte"],
            "oferta_consumida_mercado_estimada": [1000.0, 500.0, 200.0],
            "oferta_efetiva_disponivel": [5000.0, 3000.0, 2000.0],
            "rede_dominante_2km": ["smart_fit", "bluefit", None],
        }
    )


@pytest.fixture()
def df_denso_fake() -> pd.DataFrame:
    """6 linhas: base_atual, totalpass, wellhub."""
    return pd.DataFrame(
        {
            "hex_id_res7": ["87a8c2090ffffff"] * 3 + ["87a9d46cbffffff"] * 3,
            "lat": [-23.5, -23.5, -23.5, -22.9, -22.9, -22.9],
            "lng": [-46.6, -46.6, -46.6, -43.1, -43.1, -43.1],
            "rede_normalizada": [
                "smart_fit",
                "independente",
                "independente",
                "bluefit",
                "independente",
                "independente",
            ],
            "fonte": [
                "base_atual",
                "totalpass",
                "wellhub",
                "base_atual",
                "totalpass",
                "wellhub",
            ],
            "flag_da_base_atual": [True, False, False, True, False, False],
            "n_unidades_no_hex": [1, 5, 3, 1, 4, 2],
            "versao_contrato": ["concorrentes_densos_v1"] * 6,
        }
    )


@pytest.fixture()
def resultados_fake(
    df_conc_fake: pd.DataFrame,
    df_mkt_fake: pd.DataFrame,
    df_denso_fake: pd.DataFrame,
) -> dict:
    """Monta o dict de resultados a partir das fixtures."""
    df_geo = join_uf_cidade(df_conc_fake, df_mkt_fake)
    por_rede = resumo_por_rede(df_geo)
    por_uf = resumo_por_uf(df_geo)
    dom_uf = rede_dominante_por_uf(df_mkt_fake)
    residual = impacto_residual(df_mkt_fake)
    densos = resumo_densos(df_denso_fake)
    return {
        "por_rede": por_rede,
        "por_uf": por_uf,
        "dom_uf": dom_uf,
        "residual": residual,
        "densos": densos,
        "df_geo": df_geo,
    }


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


def test_join_uf_cidade_matches(
    df_conc_fake: pd.DataFrame, df_mkt_fake: pd.DataFrame
) -> None:
    """join_uf_cidade retorna só as 3 linhas válidas; 2 com UF, 1 sem UF."""
    result = join_uf_cidade(df_conc_fake, df_mkt_fake)
    # Apenas os 3 válidos são retornados
    assert len(result) == 3
    # Hex "87a8c2090ffffff" → SP, "87a9d46cbffffff" → RJ; "87000000dffffff" → não existe
    assert result["uf"].notna().sum() == 2


def test_join_uf_cidade_left_preserva_sem_match(
    df_conc_fake: pd.DataFrame, df_mkt_fake: pd.DataFrame
) -> None:
    """join_uf_cidade é LEFT: unidades sem hex no mercado não são descartadas."""
    result = join_uf_cidade(df_conc_fake, df_mkt_fake)
    # 1 válida com hex "87000000dffffff" (não existe no mercado) → NaN, mas presente
    assert result["uf"].isna().sum() == 1


def test_resumo_por_rede_n_unidades(
    df_conc_fake: pd.DataFrame, df_mkt_fake: pd.DataFrame
) -> None:
    """resumo_por_rede retorna 2 redes com contagem correta.

    Com a fixture: c1=smart_fit, c2=bluefit, c3=smart_fit → smart_fit=2, bluefit=1.
    """
    df_geo = join_uf_cidade(df_conc_fake, df_mkt_fake)
    result = resumo_por_rede(df_geo)
    assert len(result) == 2
    assert result.iloc[0]["rede"] == "smart_fit"
    assert result.iloc[0]["n_unidades"] == 2
    assert result.iloc[1]["rede"] == "bluefit"
    assert result.iloc[1]["n_unidades"] == 1


def test_resumo_por_rede_top3_cidades(
    df_conc_fake: pd.DataFrame, df_mkt_fake: pd.DataFrame
) -> None:
    """top3_cidades de smart_fit contém 'São Paulo'."""
    df_geo = join_uf_cidade(df_conc_fake, df_mkt_fake)
    result = resumo_por_rede(df_geo)
    sf_row = result[result["rede"] == "smart_fit"].iloc[0]
    assert "São Paulo" in sf_row["top3_cidades"]


def test_resumo_por_uf_n_redes(
    df_conc_fake: pd.DataFrame, df_mkt_fake: pd.DataFrame
) -> None:
    """resumo_por_uf retorna n_unidades e n_redes corretos.

    Com a fixture: c1=SP/smart_fit, c2=RJ/bluefit, c3=NaN (sem UF).
    resumo_por_uf exclui linhas sem UF → SP=1, RJ=1.
    """
    df_geo = join_uf_cidade(df_conc_fake, df_mkt_fake)
    result = resumo_por_uf(df_geo)
    sp = result[result["uf"] == "SP"].iloc[0]
    rj = result[result["uf"] == "RJ"].iloc[0]
    assert sp["n_unidades"] == 1
    assert sp["n_redes"] == 1
    assert rj["n_unidades"] == 1
    assert rj["n_redes"] == 1


def test_rede_dominante_exclui_nula(df_mkt_fake: pd.DataFrame) -> None:
    """rede_dominante_por_uf exclui hexes com rede_dominante_2km nula (MG)."""
    result = rede_dominante_por_uf(df_mkt_fake)
    # MG tem rede_dominante_2km=None → não aparece
    assert "MG" not in result["uf"].values
    assert len(result) == 2
    assert set(result["uf"].tolist()) == {"SP", "RJ"}


def test_impacto_residual_totais(df_mkt_fake: pd.DataFrame) -> None:
    """impacto_residual retorna as somas corretas de oferta consumida e disponível."""
    result = impacto_residual(df_mkt_fake)
    # 1000 + 500 + 200 = 1700
    assert result["oferta_consumida_total"] == pytest.approx(1700.0)
    # 5000 + 3000 + 2000 = 10000
    assert result["oferta_disponivel_total"] == pytest.approx(10000.0)


def test_resumo_densos_fontes(df_denso_fake: pd.DataFrame) -> None:
    """resumo_densos retorna por_fonte com contagens corretas."""
    result = resumo_densos(df_denso_fake)
    assert result["por_fonte"]["base_atual"] == 2
    assert result["por_fonte"]["totalpass"] == 2
    assert result["por_fonte"]["wellhub"] == 2
    # TotalPass + Wellhub
    assert result["totalpass_wellhub"] == 4


def test_gerar_relatorio_conteudo(
    resultados_fake: dict, tmp_path: Path
) -> None:
    """gerar_relatorio escreve arquivo com seções esperadas."""
    output = tmp_path / "test.md"
    conteudo = gerar_relatorio(resultados_fake, output)
    assert output.exists()
    assert len(conteudo) > 0
    # Deve conter "Snapshot único" (seção de notas)
    assert "Snapshot único" in conteudo or "snapshot único" in conteudo
    # Deve mencionar uma rede mapeada
    assert "smart_fit" in conteudo
    # Deve mencionar a base complementar
    assert "TotalPass" in conteudo or "Wellhub" in conteudo
    # Deve mencionar READ-ONLY
    assert "READ-ONLY" in conteudo


def test_run_escreve_arquivo(
    df_conc_fake: pd.DataFrame,
    df_mkt_fake: pd.DataFrame,
    df_denso_fake: pd.DataFrame,
    tmp_path: Path,
) -> None:
    """run() escreve movimentacao_concorrencial.md em analysis_dir."""
    tmp_staging = tmp_path / "staging"
    tmp_staging.mkdir()
    tmp_analysis = tmp_path / "analysis"

    # Escreve parquets sintéticos no tmp_staging
    df_conc_fake.to_parquet(tmp_staging / "concorrentes_mapeados.parquet", index=False)
    df_mkt_fake.to_parquet(tmp_staging / "hexagonos_mercado_mapeado.parquet", index=False)
    df_denso_fake.to_parquet(tmp_staging / "concorrentes_densos.parquet", index=False)

    out = run(staging_dir=tmp_staging, analysis_dir=tmp_analysis)
    assert out == tmp_analysis / "movimentacao_concorrencial.md"
    assert out.exists()
    assert out.stat().st_size > 0


def test_idempotente(
    df_conc_fake: pd.DataFrame,
    df_mkt_fake: pd.DataFrame,
    df_denso_fake: pd.DataFrame,
    tmp_path: Path,
) -> None:
    """Duas execuções de run() no mesmo diretório produzem conteúdo idêntico."""
    tmp_staging = tmp_path / "staging"
    tmp_staging.mkdir()
    tmp_analysis = tmp_path / "analysis"

    df_conc_fake.to_parquet(tmp_staging / "concorrentes_mapeados.parquet", index=False)
    df_mkt_fake.to_parquet(tmp_staging / "hexagonos_mercado_mapeado.parquet", index=False)
    df_denso_fake.to_parquet(tmp_staging / "concorrentes_densos.parquet", index=False)

    out1 = run(staging_dir=tmp_staging, analysis_dir=tmp_analysis)
    conteudo1 = out1.read_text(encoding="utf-8")

    out2 = run(staging_dir=tmp_staging, analysis_dir=tmp_analysis)
    conteudo2 = out2.read_text(encoding="utf-8")

    assert conteudo1 == conteudo2
