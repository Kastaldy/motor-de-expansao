"""Testes unitários para imoveis_candidatos.py (BLK-VIAB-01).

Fixture sintética em memória — NÃO usa o xlsx real.
Cobertura: todos os casos-limite da limpeza + materialização + roundtrip.
"""

from __future__ import annotations

import pandas as pd
import pytest

from motor_expansao.dimensionamento.imoveis_candidatos import (
    COLUNAS_ESPERADAS,
    materializar,
    validar_e_limpar,
)

# ---------------------------------------------------------------------------
# Fixture base
# ---------------------------------------------------------------------------


def _df_bruto() -> pd.DataFrame:
    """Retorna DataFrame sintético com 7 linhas cobrindo todos os casos-limite.

    ID | ÁREA    | ALUGUEL   | LATITUDE | LONGITUDE | STATUS              | Resultado esperado
    1  | 1200.0  | 25000.0   | -23.5    | -46.6     | PROSPECÇÃO          | SOBREVIVE (flag_sem_coord=False)
    2  | 14.9    | 20000.0   | NaN      | NaN       | PROSPECÇÃO          | DESCARTA (área < 500)
    3  | 190.0   | 30000.0   | -22.9    | -43.1     | APROVADOS           | DESCARTA (área < 500)
    4  | 2100.0  | 11111.11  | NaN      | NaN       | PROSPECÇÃO          | DESCARTA (placeholder)
    5  | 1500.0  | 5000.0    | NaN      | NaN       | HISTÓRICO COMITÊ    | DESCARTA (aluguel < 10k)
    6  | 1800.0  | 151000.0  | NaN      | NaN       | APROVADOS           | SOBREVIVE (flag_sem_coord=True)
    7  | 999.0   | 600000.0  | NaN      | NaN       | PROSPECÇÃO          | DESCARTA (aluguel > 500k)
    """
    data = {
        "ID": [1, 2, 3, 4, 5, 6, 7],
        "NOME": ["Loja A", "Loja B", "Loja C", "Loja D", "Loja E", "Loja F", "Loja G"],
        "ÁREA": [1200.0, 14.9, 190.0, 2100.0, 1500.0, 1800.0, 999.0],
        "VAGAS": [None] * 7,
        "ALUGUEL": [25000.0, 20000.0, 30000.0, 11111.11, 5000.0, 151000.0, 600000.0],
        "LOGRADOURO": [None] * 7,
        "NÚMERO": [None] * 7,
        "COMPLEMENTO": [None] * 7,
        "BAIRRO": [None] * 7,
        "CIDADE": [None] * 7,
        "ESTADO": [None] * 7,
        "CEP": [None] * 7,
        "LATITUDE": [-23.5, None, -22.9, None, None, None, None],
        "LONGITUDE": [-46.6, None, -43.1, None, None, None, None],
        "DATA CADASTRO": [None] * 7,
        "DATA ATUALIZAÇÃO": [None] * 7,
        "STATUS": [
            "PROSPECÇÃO",
            "PROSPECÇÃO",
            "APROVADOS",
            "PROSPECÇÃO",
            "HISTÓRICO COMITÊ",
            "APROVADOS",
            "PROSPECÇÃO",
        ],
        "ATIVO": [None] * 7,
        "DESCRIÇÃO": [None] * 7,
    }
    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


def test_colunas_esperadas_ok() -> None:
    """validar_e_limpar não levanta exceção com fixture contendo COLUNAS_ESPERADAS."""
    df = _df_bruto()
    # Garante que a fixture tem todas as colunas esperadas
    assert set(COLUNAS_ESPERADAS).issubset(set(df.columns))
    # E que validar_e_limpar roda sem exceção
    df_limpo, resumo = validar_e_limpar(df)
    assert df_limpo is not None
    assert resumo is not None


def test_area_descartada() -> None:
    """IDs 2 e 3 (área < 500) devem ser descartados; resumo reflete contagem."""
    df_limpo, resumo = validar_e_limpar(_df_bruto())
    ids_limpos = set(df_limpo["ID"].tolist())
    assert 2 not in ids_limpos, "ID 2 (área 14.9) deveria ter sido descartado"
    assert 3 not in ids_limpos, "ID 3 (área 190.0) deveria ter sido descartado"
    assert resumo["descartados_area"] == 2


def test_placeholder_descartado() -> None:
    """ID 4 (aluguel 11111.11) deve ser descartado; resumo reflete contagem."""
    df_limpo, resumo = validar_e_limpar(_df_bruto())
    ids_limpos = set(df_limpo["ID"].tolist())
    assert 4 not in ids_limpos, "ID 4 (aluguel placeholder) deveria ter sido descartado"
    assert resumo["descartados_placeholder"] == 1


def test_aluguel_fora_range_descartado() -> None:
    """IDs 5 (5k < 10k) e 7 (600k > 500k) devem ser descartados."""
    df_limpo, resumo = validar_e_limpar(_df_bruto())
    ids_limpos = set(df_limpo["ID"].tolist())
    assert 5 not in ids_limpos, "ID 5 (aluguel 5000 < 10k) deveria ter sido descartado"
    assert 7 not in ids_limpos, "ID 7 (aluguel 600k > 500k) deveria ter sido descartado"
    assert resumo["descartados_aluguel_fora_range"] == 2


def test_sobreviventes_corretos() -> None:
    """df_limpo deve conter exatamente IDs 1 e 6; len == 2."""
    df_limpo, resumo = validar_e_limpar(_df_bruto())
    ids_limpos = sorted(df_limpo["ID"].tolist())
    assert ids_limpos == [1, 6], f"Esperado [1, 6], obtido {ids_limpos}"
    assert len(df_limpo) == 2
    assert resumo["total_limpo"] == 2


def test_flag_sem_coord_adicionada() -> None:
    """Coluna flag_sem_coord deve existir; ID 1 = False; ID 6 = True."""
    df_limpo, _ = validar_e_limpar(_df_bruto())
    assert "flag_sem_coord" in df_limpo.columns, "Coluna flag_sem_coord ausente"
    assert df_limpo["flag_sem_coord"].dtype == bool or df_limpo["flag_sem_coord"].dtype == "bool"

    row_id1 = df_limpo.loc[df_limpo["ID"] == 1, "flag_sem_coord"].iloc[0]
    row_id6 = df_limpo.loc[df_limpo["ID"] == 6, "flag_sem_coord"].iloc[0]
    assert row_id1 is False or row_id1 == False, f"ID 1 deveria ter flag_sem_coord=False, obtido {row_id1}"  # noqa: E712
    assert row_id6 is True or row_id6 == True, f"ID 6 deveria ter flag_sem_coord=True, obtido {row_id6}"  # noqa: E712


def test_status_preservado() -> None:
    """Coluna STATUS deve estar presente com valores corretos para IDs 1 e 6."""
    df_limpo, _ = validar_e_limpar(_df_bruto())
    assert "STATUS" in df_limpo.columns, "Coluna STATUS ausente no df_limpo"
    status_id1 = df_limpo.loc[df_limpo["ID"] == 1, "STATUS"].iloc[0]
    status_id6 = df_limpo.loc[df_limpo["ID"] == 6, "STATUS"].iloc[0]
    assert status_id1 == "PROSPECÇÃO", f"STATUS do ID 1 esperado PROSPECÇÃO, obtido {status_id1}"
    assert status_id6 == "APROVADOS", f"STATUS do ID 6 esperado APROVADOS, obtido {status_id6}"


def test_resumo_totais() -> None:
    """total_entrada == 7; sem_coord == 1 (só ID 6 sobrevive sem coordenada)."""
    _, resumo = validar_e_limpar(_df_bruto())
    assert resumo["total_entrada"] == 7
    assert resumo["sem_coord"] == 1, f"Esperado sem_coord=1, obtido {resumo['sem_coord']}"


def test_determinismo() -> None:
    """Duas chamadas com a mesma fixture devem produzir df_limpos idênticos."""
    df_limpo_1, _ = validar_e_limpar(_df_bruto())
    df_limpo_2, _ = validar_e_limpar(_df_bruto())
    pd.testing.assert_frame_equal(df_limpo_1, df_limpo_2)


def test_placeholder_tolerancia() -> None:
    """11111.109 (diff < 0.01) deve ser descartado; 11111.12 (diff > 0.01) sobrevive."""
    # Linha com placeholder na tolerância
    df_dentro = pd.DataFrame(
        {col: [None] for col in COLUNAS_ESPERADAS},
    )
    df_dentro["ÁREA"] = [1000.0]
    df_dentro["ALUGUEL"] = [11111.109]  # |11111.109 - 11111.11| = 0.001 < 0.01
    df_limpo_dentro, resumo_dentro = validar_e_limpar(df_dentro)
    assert resumo_dentro["descartados_placeholder"] == 1
    assert len(df_limpo_dentro) == 0

    # Linha fora da tolerância do placeholder (mas dentro do range válido)
    df_fora = pd.DataFrame(
        {col: [None] for col in COLUNAS_ESPERADAS},
    )
    df_fora["ÁREA"] = [1000.0]
    df_fora["ALUGUEL"] = [11111.12]  # |11111.12 - 11111.11| = 0.01 = tolerância (não descarta)
    df_limpo_fora, resumo_fora = validar_e_limpar(df_fora)
    # 11111.12 >= 10k e <= 500k → deve sobreviver ao placeholder e ao range
    assert resumo_fora["descartados_placeholder"] == 0
    assert len(df_limpo_fora) == 1


def test_materializar_cria_parquet(tmp_path: pytest.TempPathFactory) -> None:
    """materializar deve criar o parquet no diretório de staging."""
    df_limpo, resumo = validar_e_limpar(_df_bruto())
    staging = tmp_path / "staging"  # type: ignore[operator]
    analysis = tmp_path / "analysis"  # type: ignore[operator]
    path_parquet, _ = materializar(df_limpo, resumo, staging, analysis)
    assert path_parquet.exists(), f"Parquet não foi criado em {path_parquet}"
    assert path_parquet.name == "imoveis_candidatos_limpos.parquet"


def test_materializar_cria_relatorio_md(tmp_path: pytest.TempPathFactory) -> None:
    """materializar deve criar o relatório .md com conteúdo esperado."""
    df_limpo, resumo = validar_e_limpar(_df_bruto())
    staging = tmp_path / "staging"  # type: ignore[operator]
    analysis = tmp_path / "analysis"  # type: ignore[operator]
    _, path_relatorio = materializar(df_limpo, resumo, staging, analysis)
    assert path_relatorio.exists(), f"Relatório .md não foi criado em {path_relatorio}"
    conteudo = path_relatorio.read_text(encoding="utf-8")
    assert "Total limpo" in conteudo, "Relatório não contém 'Total limpo'"


def test_parquet_roundtrip(tmp_path: pytest.TempPathFactory) -> None:
    """Parquet gerado deve ser legível e conter flag_sem_coord e todas as linhas limpas."""
    df_limpo, resumo = validar_e_limpar(_df_bruto())
    staging = tmp_path / "staging"  # type: ignore[operator]
    analysis = tmp_path / "analysis"  # type: ignore[operator]
    path_parquet, _ = materializar(df_limpo, resumo, staging, analysis)
    df_lido = pd.read_parquet(path_parquet)
    assert len(df_lido) == resumo["total_limpo"], (
        f"Parquet tem {len(df_lido)} linhas, esperado {resumo['total_limpo']}"
    )
    assert "flag_sem_coord" in df_lido.columns, "Coluna flag_sem_coord ausente no parquet lido"
