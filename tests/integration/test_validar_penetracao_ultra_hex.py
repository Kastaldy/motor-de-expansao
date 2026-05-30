"""
Teste minimo - Bloco 4: padroes de penetracao Ultra por hex.
"""

from pathlib import Path

import pytest

from jobs.pipelines import validar_penetracao_ultra_hex as modulo

ROOT = Path(__file__).resolve().parents[2]
# gerar_analise() le este parquet (PERF_HEX_PATH em validar_penetracao_ultra_hex.py)
PERF_HEX_PATH = ROOT / "data" / "staging" / "unidades_ultra_performance_hex.parquet"

pytestmark = pytest.mark.skipif(
    not PERF_HEX_PATH.exists(),
    reason="unidades_ultra_performance_hex.parquet ausente (dados reais)",
)


def test_gerar_analise_schema_minimo():
    analise = modulo.gerar_analise()

    assert len(analise.base) == 54
    assert set(modulo.PERFORMANCE_METRICS) <= set(analise.base.columns)
    assert {"densidade_hex_km2", "densidade_geofusion_1km_calc"} <= set(analise.base.columns)
    assert {"metrica", "n_valido", "q33", "q67", "top_n", "bottom_n"} <= set(
        analise.regras_tercis.columns
    )
    assert {"pearson", "spearman", "n_valido", "status"} <= set(analise.correlacoes.columns)
    assert not analise.resumo_top_bottom.empty
    assert analise.achados


def test_classificacao_tercis_top_bottom_para_todas_metricas():
    analise = modulo.gerar_analise()

    for metric in modulo.PERFORMANCE_METRICS:
        faixa_col = f"faixa_desempenho_{metric}"
        valores = set(analise.base[faixa_col].dropna().unique())
        assert "top_tercil" in valores
        assert "bottom_tercil" in valores

        regra = analise.regras_tercis.loc[analise.regras_tercis["metrica"].eq(metric)].iloc[0]
        assert regra["n_valido"] > 0
        assert regra["top_n"] > 0
        assert regra["bottom_n"] > 0


def test_correlacoes_pearson_spearman_com_n_valido():
    analise = modulo.gerar_analise()
    corr_ok = analise.correlacoes[analise.correlacoes["status"].eq("ok")]

    assert not corr_ok.empty
    assert {"pearson", "spearman"} <= set(corr_ok.columns)
    assert corr_ok["n_valido"].ge(5).all()
    assert corr_ok["pearson"].notna().any()
    assert corr_ok["spearman"].notna().any()

    subset = corr_ok[
        corr_ok["metrica"].eq("penetracao_ultra_alunos_total")
        & corr_ok["variavel"].isin(
            {
                "pop_hex_base",
                "densidade_hex_km2",
                "renda_per_capita",
                "score_priorizacao",
                "score_expansao_hibrido",
                "n_concorrentes_mapeados_1km",
                "dist_concorrente_mais_proximo_m",
                "densidade_geofusion_1km_calc",
                "delta_densidade_hex_vs_geofusion",
            }
        )
    ]
    assert not subset.empty


def test_resumo_top_bottom_traz_padroes_operacionais():
    analise = modulo.gerar_analise()
    resumo = analise.resumo_top_bottom

    expected_vars = {
        "densidade_geofusion_1km_calc",
        "densidade_hex_km2",
        "renda_per_capita",
        "score_priorizacao",
        "n_concorrentes_mapeados_1km",
        "metragem",
        "agregadores",
    }
    subset = resumo[
        resumo["metrica"].eq("penetracao_ultra_alunos_total")
        & resumo["variavel"].isin(expected_vars)
    ]
    assert expected_vars & set(subset["variavel"])
    assert subset["top_n"].gt(0).any()
    assert subset["bottom_n"].gt(0).any()


def test_outliers_e_validacao_nao_falham():
    analise = modulo.gerar_analise()

    assert set(analise.outliers.columns) == {
        "metrica",
        "label_metrica",
        "unidade",
        "uf",
        "valor",
        "tipo",
        "limite_inferior",
        "limite_superior",
        "fonte_pop_hex_base",
    }
    modulo.validar(analise)


def test_relatorio_markdown_gerado(tmp_path: Path):
    analise = modulo.gerar_analise()
    report_path = tmp_path / "validacao_penetracao_ultra_hex.md"

    modulo.escrever_relatorio(analise, report_path)

    content = report_path.read_text(encoding="utf-8")
    assert "Validacao Penetracao Ultra por Hex" in content
    assert "Pearson" in content
    assert "Spearman" in content
    assert "Outliers" in content
    assert "baixa amostra" in content.lower() or "amostra pequena" in content.lower()
    assert "jobs/pipelines/validar_penetracao_ultra_hex.py" in content
