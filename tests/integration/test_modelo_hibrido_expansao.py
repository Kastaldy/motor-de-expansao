from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from motor_expansao.pipelines.modelo_hibrido_expansao import (
    TOP_HEX_INTRAURBANO_PCT,
    _load_censo,
    calcular_corte_top,
    calcular_score_expansao_hibrido,
    classificar_motivo_nao_elegivel,
    construir_base_monitoramento,
    construir_dataset_hibrido,
)


@pytest.fixture
def local_tmp_dir():
    root = Path("fixtures") / "_tmp_codex_tests_modelo_hibrido"
    root.mkdir(parents=True, exist_ok=True)
    yield root


def test_calcular_corte_top_respeita_minimo():
    assert calcular_corte_top(4, 0.20) == 1
    assert calcular_corte_top(10, 0.20) == 2
    assert calcular_corte_top(0, 0.20) == 0


@pytest.mark.parametrize(
    ("kwargs", "esperado"),
    [
        (
            {
                "score_setor_2022_calibrado": None,
                "coverage_pct_setor_2022": 99.0,
                "qualidade_join_uf": "A",
                "flag_join_uf_restrito": False,
                "flag_baixa_pop_setor": False,
                "densidade_pop_setor_hab_km2": 6000.0,
                "score_priorizacao": 80.0,
            },
            "sem_score_censitario",
        ),
        (
            {
                "score_setor_2022_calibrado": 90.0,
                "coverage_pct_setor_2022": 70.0,
                "qualidade_join_uf": "A",
                "flag_join_uf_restrito": False,
                "flag_baixa_pop_setor": False,
                "densidade_pop_setor_hab_km2": 6000.0,
                "score_priorizacao": 80.0,
            },
            "coverage_baixa",
        ),
        (
            {
                "score_setor_2022_calibrado": 90.0,
                "coverage_pct_setor_2022": 90.0,
                "qualidade_join_uf": "C",
                "flag_join_uf_restrito": False,
                "flag_baixa_pop_setor": False,
                "densidade_pop_setor_hab_km2": 6000.0,
                "score_priorizacao": 80.0,
            },
            "join_uf_fora_regra",
        ),
        (
            {
                "score_setor_2022_calibrado": 90.0,
                "coverage_pct_setor_2022": 90.0,
                "qualidade_join_uf": "A",
                "flag_join_uf_restrito": False,
                "flag_baixa_pop_setor": True,
                "densidade_pop_setor_hab_km2": 4200.0,
                "score_priorizacao": 75.0,
            },
            "densidade_abaixo_piso",
        ),
        (
            {
                "score_setor_2022_calibrado": 90.0,
                "coverage_pct_setor_2022": 90.0,
                "qualidade_join_uf": "A",
                "flag_join_uf_restrito": False,
                "flag_baixa_pop_setor": False,
                "densidade_pop_setor_hab_km2": None,
                "score_priorizacao": 75.0,
            },
            "densidade_indisponivel",
        ),
        (
            {
                "score_setor_2022_calibrado": 90.0,
                "coverage_pct_setor_2022": 90.0,
                "qualidade_join_uf": "A",
                "flag_join_uf_restrito": False,
                "flag_baixa_pop_setor": False,
                "densidade_pop_setor_hab_km2": 6100.0,
                "score_priorizacao": 75.0,
            },
            "elegivel",
        ),
    ],
)
def test_classificar_motivo_nao_elegivel(kwargs: dict, esperado: str):
    assert classificar_motivo_nao_elegivel(**kwargs) == esperado


def test_calcular_score_expansao_hibrido_mantem_m1_como_camanda_primaria():
    score_m1 = pd.Series([90.00, 89.99, 90.00])
    score_censo = pd.Series([10.0, 99.0, 90.0])
    elegivel = pd.Series([True, True, False])

    result = calcular_score_expansao_hibrido(score_m1, score_censo, elegivel)

    assert result.iloc[0] > result.iloc[1]
    assert result.iloc[0] > result.iloc[2]
    assert result.iloc[2] == pytest.approx(90.0)


def test_construir_dataset_hibrido_aplica_duas_etapas(local_tmp_dir):
    dashboard = pd.DataFrame(
        {
            "hex_id": ["h1", "h2", "h3", "h4", "h5", "h6"],
            "uf": ["GO", "GO", "GO", "GO", "GO", "GO"],
            "cidade": ["A", "A", "B", "B", "C", "C"],
            "score_priorizacao": [95.0, 95.0, 90.0, 90.0, 80.0, 80.0],
            "score_oficial": [95.0, 95.0, 90.0, 90.0, 80.0, 80.0],
            "rank_brasil": [1, 2, 3, 4, 5, 6],
            "rank_uf": [1, 2, 3, 4, 5, 6],
            "rank_cidade": [1, 2, 1, 2, 1, 2],
            "hex_score_estrutural": [90.0, 90.0, 85.0, 85.0, 75.0, 75.0],
            "renda_per_capita": [3000.0, 3000.0, 2500.0, 2500.0, 1800.0, 1800.0],
            "populacao_proxy": [10000.0, 10000.0, 8000.0, 8000.0, 5000.0, 5000.0],
            "faixa_oportunidade": ["alta"] * 6,
            "flag_viavel": [True] * 6,
            "flag_prioridade": [True, True, False, False, False, False],
        }
    )
    structural = pd.DataFrame(
        {
            "hex_id": ["h1", "h2", "h3", "h4", "h5", "h6"],
            "cod_municipio": ["001", "001", "002", "002", "003", "003"],
            "nome_municipio": ["A", "A", "B", "B", "C", "C"],
        }
    )
    censo = pd.DataFrame(
        {
            "hex_id": ["h1", "h2", "h3", "h4"],
            "uf": ["GO", "GO", "GO", "GO"],
            "cod_municipio": ["001", "001", "002", "002"],
            "nome_municipio": ["A", "A", "B", "B"],
            "score_setor_2022_calibrado": [70.0, 90.0, 80.0, 20.0],
            "pop_total_setor_2022": [15000.0, 42000.0, 35000.0, 1000.0],
            "coverage_pct_setor_2022": [100.0, 100.0, 100.0, 100.0],
            "qualidade_join_uf": ["A", "A", "A", "A"],
            "flag_join_uf_restrito": [False, False, False, False],
            "flag_baixa_pop_setor": [False, False, False, False],
            "flag_outlier_espacial": [False, False, False, False],
            "status_espacial_uf": ["GO", "GO", "GO", "GO"],
        }
    )

    dashboard_path = local_tmp_dir / "dashboard.parquet"
    structural_path = local_tmp_dir / "structural.parquet"
    censo_path = local_tmp_dir / "censo.parquet"
    censo_expanded_path = local_tmp_dir / "censo_expanded.parquet"

    dashboard.to_parquet(dashboard_path, index=False)
    structural.to_parquet(structural_path, index=False)
    censo.to_parquet(censo_path, index=False)
    censo.iloc[0:0].to_parquet(censo_expanded_path, index=False)

    result = construir_dataset_hibrido(
        dashboard_path=dashboard_path,
        structural_path=structural_path,
        censo_core_path=censo_path,
        censo_expanded_path=censo_expanded_path,
        censo_nacional_path=None,
    )

    top_rows = result[result["top_municipio"]]
    assert set(top_rows["cod_municipio"]) == {"001"}

    municipio_a = result[result["cod_municipio"] == "001"].sort_values("rank_hex_intraurbano")
    assert list(municipio_a["hex_id"]) == ["h2", "h1"]
    assert municipio_a["top_hex_intraurbano"].sum() == calcular_corte_top(
        2,
        TOP_HEX_INTRAURBANO_PCT,
    )

    assert bool(result.loc[result["hex_id"] == "h2", "flag_hex_hibrido_elegivel"].iloc[0]) is True
    assert bool(result.loc[result["hex_id"] == "h1", "flag_hex_hibrido_elegivel"].iloc[0]) is False
    assert result.loc[result["hex_id"] == "h1", "motivo_nao_elegivel_censo"].iloc[0] == "densidade_abaixo_piso"
    assert bool(result.loc[result["hex_id"] == "h3", "flag_hex_hibrido_elegivel"].iloc[0]) is False


def test_construir_base_monitoramento_filtra_lista_curta():
    df = pd.DataFrame(
        {
            "flag_monitoramento_prioritario": [True, False, True],
            "uf": ["GO", "GO", "SP"],
            "cod_municipio": ["001", "001", "3550308"],
            "hex_id": ["h1", "h2", "h3"],
            "top_oportunidade_brasil": [True, False, False],
            "top_oportunidade_uf": [True, False, True],
            "top_oportunidade_municipio": [True, False, True],
            "score_expansao_hibrido": [95.0009, 95.0001, 90.0008],
            "score_setor_2022_calibrado": [90.0, 10.0, 80.0],
            "score_priorizacao": [95.0, 95.0, 90.0],
        }
    )

    out = construir_base_monitoramento(df)

    assert len(out) == 2
    assert "monitoramento_id" in out.columns
    assert set(out["status_monitoramento"]) == {"pronto_para_registro"}


def test_load_censo_deduplicacao_prioridade_core_sobre_nacional(local_tmp_dir):
    """core deve vencer nacional quando hex_id coincide; nacional adiciona hexes novos."""
    core = pd.DataFrame(
        {
            "hex_id": ["h1"],
            "uf": ["GO"],
            "cod_municipio": ["001"],
            "nome_municipio": ["A"],
            "score_setor_2022_calibrado": [80.0],
            "coverage_pct_setor_2022": [95.0],
            "qualidade_join_uf": ["A"],
            "flag_join_uf_restrito": [False],
            "flag_baixa_pop_setor": [False],
            "flag_outlier_espacial": [False],
            "status_espacial_uf": ["GO"],
        }
    )
    nacional = pd.DataFrame(
        {
            "hex_id": ["h1", "h2"],
            "uf": ["GO", "BA"],
            "cod_municipio": ["001", "099"],
            "nome_municipio": ["A", "Salvador"],
            "score_setor_2022_calibrado": [50.0, 70.0],  # h1 deve ser ignorado
            "coverage_pct_setor_2022": [90.0, 90.0],
            "qualidade_join_uf": ["A", "B"],
            "flag_join_uf_restrito": [False, False],
            "flag_baixa_pop_setor": [False, False],
            "flag_outlier_espacial": [False, False],
            "status_espacial_uf": ["GO", "GO"],
        }
    )
    core_path = local_tmp_dir / "core_dedup.parquet"
    expanded_path = local_tmp_dir / "expanded_dedup.parquet"
    nacional_path = local_tmp_dir / "nacional_dedup.parquet"

    core.to_parquet(core_path, index=False)
    core.iloc[0:0].to_parquet(expanded_path, index=False)
    nacional.to_parquet(nacional_path, index=False)

    resultado = _load_censo(core_path, expanded_path, nacional_path)

    assert len(resultado) == 2, "deve ter h1 (core) + h2 (nacional)"
    h1_score = resultado.loc[resultado["hex_id"] == "h1", "score_setor_2022_calibrado"].iloc[0]
    assert h1_score == 80.0, "core deve vencer nacional na deduplicacao"
    assert "h2" in resultado["hex_id"].values
    fontes = set(resultado["fonte_camada_censitaria"].tolist())
    assert "fase_a_calibrada" in fontes
    assert "fase_a_calibrada_nacional" in fontes


def test_load_censo_deriva_qualidade_join_quando_validado_traz_mismatch(local_tmp_dir):
    core = pd.DataFrame(
        {
            "hex_id": ["h1", "h2", "h3"],
            "uf": ["GO", "GO", "GO"],
            "score_setor_2022_calibrado": [80.0, 70.0, 60.0],
            "coverage_pct_setor_2022": [95.0, 95.0, 95.0],
            "join_mismatch_pct_uf": [0.5, 3.0, 8.0],
            "status_validacao_join_uf": ["GO", "GO", "REVIEW"],
        }
    )
    core_path = local_tmp_dir / "core_mismatch.parquet"
    expanded_path = local_tmp_dir / "expanded_mismatch.parquet"
    core.to_parquet(core_path, index=False)
    core.iloc[0:0].to_parquet(expanded_path, index=False)

    resultado = _load_censo(core_path, expanded_path, None).sort_values("hex_id")

    assert resultado["qualidade_join_uf"].tolist() == ["A", "B", "C"]


def test_load_censo_sem_nacional_nao_falha(local_tmp_dir):
    """Se censo_nacional_path=None, _load_censo deve funcionar normalmente."""
    core = pd.DataFrame(
        {
            "hex_id": ["h1"],
            "uf": ["GO"],
            "score_setor_2022_calibrado": [80.0],
            "coverage_pct_setor_2022": [95.0],
            "qualidade_join_uf": ["A"],
        }
    )
    core_path = local_tmp_dir / "core_sem_nac.parquet"
    expanded_path = local_tmp_dir / "expanded_sem_nac.parquet"
    core.to_parquet(core_path, index=False)
    core.iloc[0:0].to_parquet(expanded_path, index=False)

    resultado = _load_censo(core_path, expanded_path, None)
    assert len(resultado) == 1
    assert "h1" in resultado["hex_id"].values


def test_load_censo_propaga_renda_setorial_das_tres_fontes(local_tmp_dir):
    """Regressao: a renda setorial NAO pode ser descartada por _padronizar_censo.

    Ate 2026-08-25 a coluna `renda_per_capita_setor_2022_calibrada` faltava em
    `keep_cols`. As tres fontes (core/expandido/nacional) tem a coluna, mas ela era
    filtrada aqui e, a jusante, `calcular_colunas_mercado.anexar_colunas_censo` a
    repreenchia SO com o parquet core (GO/RJ/SP). Resultado: a renda intraurbana caia
    de ~85% para 7,4% dos hexagonos, em silencio -- a coluna existia, so estava nula.
    Sem renda por setor nao ha gate socioeconomico nem quadrante fora de 3 UFs.
    """
    base = {
        "coverage_pct_setor_2022": 95.0,
        "qualidade_join_uf": "A",
        "flag_join_uf_restrito": False,
        "flag_baixa_pop_setor": False,
        "flag_outlier_espacial": False,
        "status_espacial_uf": "GO",
    }
    core = pd.DataFrame(
        {
            "hex_id": ["h_core"],
            "uf": ["SP"],
            "pop_total_setor_2022": [1200.0],
            "renda_per_capita_setor_2022_calibrada": [3100.0],
            "score_setor_2022_calibrado": [80.0],
            **{k: [v] for k, v in base.items()},
        }
    )
    expandido = pd.DataFrame(
        {
            "hex_id": ["h_exp"],
            "uf": ["MG"],
            "pop_total_setor_2022": [900.0],
            "renda_per_capita_setor_2022_calibrada": [1700.0],
            "score_setor_2022_calibrado": [65.0],
            **{k: [v] for k, v in base.items()},
        }
    )
    nacional = pd.DataFrame(
        {
            "hex_id": ["h_nac"],
            "uf": ["BA"],
            "pop_total_setor_2022": [800.0],
            "renda_per_capita_setor_2022_calibrada": [950.0],
            "score_setor_2022_calibrado": [55.0],
            **{k: [v] for k, v in base.items()},
        }
    )

    core_path = local_tmp_dir / "core_renda.parquet"
    expandido_path = local_tmp_dir / "expandido_renda.parquet"
    nacional_path = local_tmp_dir / "nacional_renda.parquet"
    core.to_parquet(core_path, index=False)
    expandido.to_parquet(expandido_path, index=False)
    nacional.to_parquet(nacional_path, index=False)

    resultado = _load_censo(core_path, expandido_path, nacional_path)

    assert "renda_per_capita_setor_2022_calibrada" in resultado.columns, (
        "renda setorial sumiu de _load_censo -- provavelmente caiu de keep_cols"
    )
    renda = resultado.set_index("hex_id")["renda_per_capita_setor_2022_calibrada"]
    assert renda.notna().all(), (
        "renda setorial nula em alguma fonte: "
        f"{renda[renda.isna()].index.tolist()} -- o expandido e o nacional tambem "
        "precisam propagar a coluna, senao a cobertura cai para as UFs do core"
    )
    assert renda["h_core"] == 3100.0
    assert renda["h_exp"] == 1700.0
    assert renda["h_nac"] == 950.0
