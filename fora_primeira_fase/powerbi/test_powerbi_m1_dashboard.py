import pandas as pd
import powerbi_m1_dashboard as dashboard


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "hex_id": ["a", "b", "c"],
            "lat": [-10.0, -10.1, -19.9],
            "lng": [-48.0, -48.2, -43.9],
            "uf": ["GO", "GO", "RJ"],
            "cidade": ["Goiania", "Goiania", "Rio de Janeiro"],
            "regiao": ["CO", "CO", "SE"],
            "score_priorizacao": [90.0, 70.0, 80.0],
            "hex_score_estrutural": [85.0, 68.0, 78.0],
            "ajuste_executivo": [5.0, 2.0, 2.0],
            "faixa_oportunidade": ["prioridade_maxima", "alta", "alta"],
            "flag_viavel": [True, True, False],
            "flag_prioridade": [True, False, False],
            "rank_brasil": [1, 2, 3],
            "rank_uf": [1, 2, 1],
            "rank_cidade": [1, 2, 1],
            "renda_per_capita": [2500.0, 2000.0, 2200.0],
            "populacao_proxy": [100000.0, 80000.0, 150000.0],
        }
    )


def test_validate_schema_matches_expected_model_columns():
    schema = dashboard.validate_schema(_sample_df())

    assert schema.missing_source_columns == []
    assert set(schema.model_mapping) == set(dashboard.EXPECTED_MODEL_COLUMNS)
    assert schema.model_mapping["UF"] == "uf"
    assert schema.model_mapping["nome_municipio"] == "cidade"


def test_build_page_spec_has_four_required_pages():
    pages = dashboard.build_page_spec()

    assert len(pages) == 4
    assert [page["titulo"] for page in pages] == [
        "Visao Executiva",
        "Analise Territorial",
        "Ranking e Priorizacao",
        "Comparacao por UF",
    ]


def test_build_kpis_uses_official_fields():
    df = _sample_df()
    city_summary = dashboard.build_city_summary(df)
    uf_summary = dashboard.build_uf_summary(df)

    kpis = dashboard.build_kpis(df, city_summary, uf_summary)

    assert kpis["total_oportunidades_viaveis"] == "2"
    assert kpis["total_hexagonos_priorizados"] == "1"
    assert kpis["uf_lider_oportunidades"].startswith("GO")
    assert "Goiania" in kpis["cidade_lider_score"]
