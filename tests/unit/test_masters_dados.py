"""Os leitores das entradas do relatório dos masters (`masters/dados.py`), contra parquets mínimos.

Achado da revisão automática do #567 (média, "lógica nova sem teste"): os leitores do mercado, dos
concorrentes, das Ultras e do painel de unidades não tinham teste. Cada um FILTRA alguma coisa (UF,
coordenada válida, duplicado, unidade excluída da rede), e o filtro errado não quebra nada à vista:
só muda os números do relatório. É isso que se trava aqui, com o mínimo de colunas de cada artefato.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from motor_expansao.masters import dados
from motor_expansao.masters.territorios import normalizar


def _parquet(tmp_path: Path, nome: str, df: pd.DataFrame) -> Path:
    caminho = tmp_path / nome
    df.to_parquet(caminho, index=False)
    return caminho


def _mercado(ufs: list[str], *, opcionais: bool) -> pd.DataFrame:
    n = len(ufs)
    df = pd.DataFrame({c: [0.0] * n for c in dados.COLUNAS_MERCADO})
    df["hex_id"] = [f"h{i}" for i in range(n)]
    df["uf"] = ufs
    df["nome_municipio"] = [f"M{i}" for i in range(n)]
    df["data_snapshot_mercado"] = "2026-07-14"
    df["coluna_que_o_relatorio_nao_usa"] = 1
    if opcionais:
        df["n_concorrentes_influencia_1km"] = list(range(n))
    return df


# --------------------------------------------------------------------------------------
# Mercado
# --------------------------------------------------------------------------------------


def test_o_mercado_vem_so_das_ufs_pedidas_e_so_com_as_colunas_do_relatorio(tmp_path: Path) -> None:
    caminho = _parquet(tmp_path, "m.parquet", _mercado(["DF", "GO", "SP", "DF"], opcionais=False))
    df = dados.ler_mercado(caminho, frozenset({"DF", "GO"}))
    assert sorted(df["uf"]) == ["DF", "DF", "GO"]
    assert list(df.columns) == list(dados.COLUNAS_MERCADO)


def test_a_coluna_opcional_entra_so_quando_o_artefato_a_tem(tmp_path: Path) -> None:
    """A contagem de concorrentes da DEC-057 é opcional: artefato antigo sem ela ainda é lido."""
    caminho = _parquet(tmp_path, "m.parquet", _mercado(["DF", "GO"], opcionais=True))
    df = dados.ler_mercado(caminho, {"DF"})
    assert list(df.columns) == [*dados.COLUNAS_MERCADO, "n_concorrentes_influencia_1km"]
    assert "n_concorrentes_mapeados_1km" not in df.columns
    assert "coluna_que_o_relatorio_nao_usa" not in df.columns


def test_o_mercado_do_brasil_vem_inteiro_e_so_com_a_regua_da_ocupacao(tmp_path: Path) -> None:
    caminho = _parquet(tmp_path, "m.parquet", _mercado(["DF", "GO", "SP"], opcionais=True))
    df = dados.ler_mercado_brasil(caminho)
    assert sorted(df["uf"]) == ["DF", "GO", "SP"]
    assert list(df.columns) == [
        "uf",
        "nome_municipio",
        "sam_fitness_potencial",
        "oferta_consumida_mercado_estimada",
        "oferta_consumida_ultra_estimada",
    ]


# --------------------------------------------------------------------------------------
# Concorrentes e Ultras
# --------------------------------------------------------------------------------------


def test_concorrente_sem_coordenada_valida_ou_duplicado_fica_de_fora(tmp_path: Path) -> None:
    """Coordenada desconhecida (nula) conta como inválida; duplicado desconhecido, como não
    duplicado: na dúvida, o concorrente só entra se o motor sabe onde ele está."""
    df = pd.DataFrame(
        {
            "concorrente_id": ["ok", "sem_coord", "coord_nula", "duplicado", "dup_nulo"],
            "rede": ["A", "A", "B", "B", "C"],
            "hex_id_res7": ["h1", "h2", "h3", "h4", "h5"],
            "flag_coord_valida": [True, False, None, True, True],
            "flag_duplicado_rede_coord": [False, False, False, True, None],
            "outra": [1, 2, 3, 4, 5],
        }
    )
    lidos = dados.ler_concorrentes(_parquet(tmp_path, "c.parquet", df))
    assert list(lidos["concorrente_id"]) == ["ok", "dup_nulo"]
    assert list(lidos.columns) == ["concorrente_id", "rede", "hex_id_res7"]


def test_sem_as_colunas_de_flag_os_concorrentes_entram_todos(tmp_path: Path) -> None:
    df = pd.DataFrame(
        {"concorrente_id": ["a", "b"], "rede": ["A", "B"], "hex_id_res7": ["h1", "h2"]}
    )
    assert list(dados.ler_concorrentes(_parquet(tmp_path, "c.parquet", df))["concorrente_id"]) == [
        "a",
        "b",
    ]


def test_a_ultra_sem_coordenada_valida_fica_de_fora_e_a_flag_sai(tmp_path: Path) -> None:
    df = pd.DataFrame(
        {
            "ultra_id": [1, 2, 3],
            "unidade": ["Asa Sul", "Sem Coord", "Nula"],
            "uf": ["DF", "DF", "GO"],
            "lat": [-15.8, 0.0, 0.0],
            "lng": [-47.9, 0.0, 0.0],
            "hex_id_res7": ["h1", "h2", "h3"],
            "flag_coord_valida": [True, False, None],
        }
    )
    lidas = dados.ler_ultra(_parquet(tmp_path, "u.parquet", df))
    assert list(lidas["unidade"]) == ["Asa Sul"]
    assert "flag_coord_valida" not in lidas.columns
    assert list(lidas.index) == [0]


# --------------------------------------------------------------------------------------
# Painel de unidades (BLK-UNI)
# --------------------------------------------------------------------------------------


@pytest.fixture
def painel(tmp_path: Path) -> tuple[Path, Path]:
    dim = pd.DataFrame(
        {
            "unidade_id": ["u1", "u2", "u3"],
            "nome": ["São Gonçalo  Centro", "Fechada", "Sem Data"],
            "excluida_rede": [False, True, None],
            "inauguracao": ["2024-03-01", "2023-01-01", "não é data"],
        }
    )
    n = 4
    fato = pd.DataFrame({c: [0] * n for c in dados.COLUNAS_FATO})
    fato["unidade_id"] = ["u1", "u2", "u3", "u_fora_do_cadastro"]
    fato["mes_completo"] = pd.array([True, True, None, True], dtype="boolean")
    fato["pre_inauguracao"] = pd.array([None, False, True, False], dtype="boolean")
    fato["coluna_que_o_relatorio_nao_usa"] = 1
    return _parquet(tmp_path, "dim.parquet", dim), _parquet(tmp_path, "fato.parquet", fato)


def test_a_unidade_excluida_da_rede_sai_do_cadastro_e_da_serie(painel: tuple[Path, Path]) -> None:
    """Exclusão desconhecida (nula) não exclui; e a série só traz unidade que está no cadastro."""
    dim, fato = dados.ler_unidades(*painel)
    assert list(dim["unidade_id"]) == ["u1", "u3"]
    assert list(fato["unidade_id"]) == ["u1", "u3"]
    assert list(dim.index) == [0, 1] and list(fato.index) == [0, 1]


def test_o_cadastro_ganha_a_data_e_a_chave_do_nome(painel: tuple[Path, Path]) -> None:
    dim, _ = dados.ler_unidades(*painel)
    assert dim.loc[0, "inauguracao"] == pd.Timestamp("2024-03-01")
    assert pd.isna(dim.loc[1, "inauguracao"])  # data ilegível vira NaT, e não erro
    assert list(dim["chave_nome"]) == [normalizar("São Gonçalo  Centro"), normalizar("Sem Data")]
    assert dim.loc[0, "chave_nome"] == "sao goncalo centro"


def test_a_serie_traz_so_as_colunas_do_relatorio_e_os_flags_sem_nulo(
    painel: tuple[Path, Path],
) -> None:
    _, fato = dados.ler_unidades(*painel)
    assert list(fato.columns) == list(dados.COLUNAS_FATO)
    assert list(fato["mes_completo"]) == [True, False]
    assert list(fato["pre_inauguracao"]) == [False, True]
    assert fato["mes_completo"].dtype == bool and fato["pre_inauguracao"].dtype == bool
