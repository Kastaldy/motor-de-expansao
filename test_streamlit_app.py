from pathlib import Path

import pandas as pd
import pytest

import streamlit_app


def _write_dashboard_parquet(root: Path, rows: list[dict[str, object]]) -> Path:
    path = root / "hexagonos_brasil_dashboard.parquet"
    pd.DataFrame(rows).to_parquet(path, index=False)
    return path


@pytest.fixture
def local_tmp_dir():
    root = Path("fixtures") / "_tmp_codex_tests_streamlit"
    root.mkdir(parents=True, exist_ok=True)
    yield root


def test_load_data_prepara_aliases_e_score_oficial(local_tmp_dir, monkeypatch):
    path = _write_dashboard_parquet(
        local_tmp_dir,
        [
            {
                "hex_id": "a",
                "lat": -23.55,
                "lng": -46.63,
                "uf": "SP",
                "cidade": "Sao Paulo",
                "regiao": "SE",
                "score_priorizacao": 81.0,
                "hex_score_estrutural": 77.0,
                "ajuste_executivo": 4.0,
                "faixa_oportunidade": "alta",
                "flag_viavel": True,
                "flag_prioridade": True,
                "rank_brasil": 1,
                "rank_uf": 1,
                "rank_cidade": 1,
                "renda_per_capita": 5200.0,
                "populacao_proxy": 16000.0,
            }
        ],
    )
    monkeypatch.setattr(streamlit_app, "DATASET_PATH", path)
    streamlit_app.load_data.clear()

    df = streamlit_app.load_data()

    assert df.loc[0, "score_exibicao"] == 81.0
    assert df.loc[0, "UF"] == "SP"
    assert df.loc[0, "nome_municipio"] == "Sao Paulo"
    assert str(df.loc[0, "faixa_oportunidade"]) == "alta"


def test_load_data_falha_sem_colunas_obrigatorias(local_tmp_dir, monkeypatch):
    path = _write_dashboard_parquet(
        local_tmp_dir,
        [
            {
                "hex_id": "a",
                "lat": -23.55,
                "lng": -46.63,
                "uf": "SP",
            }
        ],
    )
    monkeypatch.setattr(streamlit_app, "DATASET_PATH", path)
    streamlit_app.load_data.clear()

    with pytest.raises(ValueError, match="colunas obrigatorias"):
        streamlit_app.load_data()


def test_apply_global_filters_respeita_uf_cidade_e_faixa():
    df = pd.DataFrame(
        [
            {"uf": "SP", "cidade": "Sao Paulo", "faixa_oportunidade": "alta"},
            {"uf": "SP", "cidade": "Campinas", "faixa_oportunidade": "media"},
            {"uf": "RJ", "cidade": "Rio de Janeiro", "faixa_oportunidade": "alta"},
        ]
    )

    filtered = streamlit_app.apply_global_filters(
        df,
        selected_ufs=["SP"],
        selected_cities=["Campinas"],
        selected_faixas=["media"],
    )

    assert len(filtered) == 1
    assert filtered.iloc[0]["cidade"] == "Campinas"


def test_apply_global_filters_respeita_campos_hibridos():
    df = pd.DataFrame(
        [
            {
                "uf": "DF",
                "nome_municipio": "Brasilia",
                "faixa_oportunidade": "alta",
                "elegibilidade_hibrida": "Elegivel",
                "cobertura_censitaria_bucket": "95-99,9%",
                "qualidade_camada": "A",
                "top_municipio": True,
                "top_hex_intraurbano": False,
            },
            {
                "uf": "SP",
                "nome_municipio": "Sao Paulo",
                "faixa_oportunidade": "alta",
                "elegibilidade_hibrida": "Nao elegivel",
                "cobertura_censitaria_bucket": "<85%",
                "qualidade_camada": "C",
                "top_municipio": True,
                "top_hex_intraurbano": True,
            },
        ]
    )

    filtered = streamlit_app.apply_global_filters(
        df,
        selected_ufs=[],
        selected_cities=[],
        selected_faixas=["alta"],
        selected_hybrid_eligibility=["Elegivel"],
        selected_coverage_buckets=["95-99,9%"],
        selected_join_quality=["A"],
        only_top_municipio=True,
        only_top_hex_intraurbano=False,
    )

    assert len(filtered) == 1
    assert filtered.iloc[0]["nome_municipio"] == "Brasilia"


def test_build_kpis_aplica_desempate_oficial_para_uf_e_cidade():
    df = pd.DataFrame(
        [
            {"flag_viavel": True, "flag_prioridade": True},
            {"flag_viavel": True, "flag_prioridade": False},
            {"flag_viavel": False, "flag_prioridade": True},
        ]
    )
    city_summary = pd.DataFrame(
        [
            {"uf": "RJ", "cidade": "Niteroi", "score_medio": 90.0, "melhor_rank_brasil": 3},
            {"uf": "SP", "cidade": "Campinas", "score_medio": 90.0, "melhor_rank_brasil": 1},
        ]
    )
    uf_summary = pd.DataFrame(
        [
            {"uf": "RJ", "oportunidades_viaveis": 2, "score_medio": 80.0},
            {"uf": "SP", "oportunidades_viaveis": 2, "score_medio": 82.0},
        ]
    )

    kpis = streamlit_app.build_kpis(df, city_summary, uf_summary)

    assert kpis["total_oportunidades_viaveis"] == "2"
    assert kpis["total_hexagonos_priorizados"] == "2"
    assert kpis["uf_lider_oportunidades"] == "SP"
    assert kpis["cidade_lider_score"] == "Campinas / SP"


def test_build_hybrid_kpis_conta_municipios_unicos():
    hdf = pd.DataFrame(
        [
            {
                "uf": "DF",
                "nome_municipio": "Brasilia",
                "top_municipio_hibrido": True,
                "flag_censo_disponivel": True,
                "flag_hex_hibrido_elegivel": True,
                "flag_monitoramento_prioritario": True,
                "flag_prioridade": True,
            },
            {
                "uf": "DF",
                "nome_municipio": "Brasilia",
                "top_municipio_hibrido": True,
                "flag_censo_disponivel": True,
                "flag_hex_hibrido_elegivel": True,
                "flag_monitoramento_prioritario": False,
                "flag_prioridade": False,
            },
            {
                "uf": "GO",
                "nome_municipio": "Goiania",
                "top_municipio_hibrido": False,
                "flag_censo_disponivel": True,
                "flag_hex_hibrido_elegivel": False,
                "flag_monitoramento_prioritario": True,
                "flag_prioridade": True,
            },
        ]
    )

    kpis = streamlit_app.build_hybrid_kpis(hdf)

    assert kpis["municipios_elegiveis"] == "1"
    assert kpis["hexes_elegiveis"] == "2"
    assert kpis["municipios_cobertos"] == "2"
    assert kpis["registros_monitoramento"] == "2"
    assert kpis["comparativo_m1_hibrido"] == "2 -> 2"


def test_enrich_dashboard_data_preserva_base_oficial_e_sobrepoe_rastreabilidade():
    base_df = pd.DataFrame(
        [
            {
                "hex_id": "abc",
                "lat": -15.0,
                "lng": -47.0,
                "uf": "DF",
                "cidade": "Brasilia",
                "regiao": "CO",
                "score_priorizacao": 98.0,
                "hex_score_estrutural": 95.0,
                "ajuste_executivo": 3.0,
                "faixa_oportunidade": "alta",
                "flag_viavel": True,
                "flag_prioridade": True,
                "rank_brasil": 1,
                "rank_uf": 1,
                "rank_cidade": 1,
                "renda_per_capita": 6500.0,
                "populacao_proxy": 18000.0,
            }
        ]
    )
    hybrid_df = pd.DataFrame(
        [
            {
                "hex_id": "abc",
                "nome_municipio": "Brasilia",
                "score_setor_2022_calibrado": 87.5,
                "score_expansao_hibrido": 98.000875,
                "top_municipio": True,
                "top_hex_intraurbano": True,
                "flag_censo_elegivel": True,
                "flag_censo_disponivel": True,
                "flag_hex_hibrido_elegivel": True,
                "top_municipio_hibrido": True,
                "rank_municipio_uf": 1,
                "rank_hex_intraurbano": 1,
                "top_oportunidade_municipio": True,
                "coverage_pct_setor_2022": 99.2,
                "qualidade_join_uf": "B",
                "flag_join_uf_restrito": False,
                "flag_baixa_pop_setor": False,
                "flag_outlier_espacial": False,
                "motivo_nao_elegivel_censo": "elegivel",
            }
        ]
    )
    censo_df = pd.DataFrame(
        [
            {
                "hex_id": "abc",
                "nome_municipio": "Brasilia",
                "score_setor_2022_calibrado": 88.1,
                "coverage_pct_setor_2022": 100.0,
                "qualidade_join_uf": "A",
                "flag_join_uf_restrito": False,
                "flag_baixa_pop_setor": True,
                "flag_outlier_espacial": True,
                "causa_outlier_espacial": "limiar_de_zona",
                "delta_vs_vizinhos": 36.0,
                "metodo_join_setor_2022": "posicional",
                "motivo_fallback_setor_2022": pd.NA,
                "renda_per_capita_setor_2022_calibrada": 7000.0,
            }
        ]
    )

    enriched = streamlit_app.enrich_dashboard_data(base_df, hybrid_df, censo_df)

    assert enriched.loc[0, "score_priorizacao"] == 98.0
    assert enriched.loc[0, "score_setor_2022_calibrado"] == 87.5
    assert enriched.loc[0, "coverage_pct_setor_2022"] == 99.2
    assert bool(enriched.loc[0, "flag_outlier_espacial"]) is False
    assert enriched.loc[0, "causa_outlier_espacial"] == "limiar_de_zona"
    assert enriched.loc[0, "metodo_join_setor_2022"] == "posicional"
    assert enriched.loc[0, "confianca_geografica"] == "granular"
    assert str(enriched.loc[0, "elegibilidade_hibrida"]) == "Elegivel"
    assert str(enriched.loc[0, "cobertura_censitaria_bucket"]) == "95-99,9%"
    assert str(enriched.loc[0, "qualidade_camada"]) == "B"


def test_build_map_scope_caption_reflete_todos_os_hexes_da_uf():
    caption = streamlit_app.build_map_scope_caption(1234, selected_ufs=["SP"])

    assert "todos os hexagonos validos da UF selecionada" in caption
    assert "100 melhores" not in caption
    assert "1.234" in caption


def test_censo_score_to_color_usa_amarelo_na_faixa_50_a_75():
    assert streamlit_app._censo_score_to_color(60) == [245, 158, 11, 140]


def test_faixa_alta_usa_amarelo_no_mapa_e_na_legenda():
    assert streamlit_app.FAIXA_COLORS["alta"] == "#F59E0B"
    assert streamlit_app.hex_to_rgba(streamlit_app.FAIXA_COLORS["alta"], 140) == [245, 158, 11, 140]


def test_build_map_figure_mostra_todos_os_hexes_validos_da_uf_sem_cap_editorial():
    df = pd.DataFrame(
        [
            {
                "hex_id": "sp_granular_1",
                "lat": -23.55,
                "lng": -46.63,
                "cidade": "Sao Paulo",
                "nome_municipio": "Sao Paulo",
                "uf": "SP",
                "faixa_oportunidade": "alta",
                "score_priorizacao": 98.0,
                "hex_score_estrutural": 92.0,
                "flag_viavel": True,
                "flag_prioridade": True,
                "score_setor_2022_calibrado": 88.0,
                "coverage_pct_setor_2022": 97.0,
                "qualidade_join_uf": "A",
                "flag_censo_disponivel": True,
            },
            {
                "hex_id": "sp_granular_1",
                "lat": -23.55,
                "lng": -46.63,
                "cidade": "Sao Paulo",
                "nome_municipio": "Sao Paulo",
                "uf": "SP",
                "faixa_oportunidade": "alta",
                "score_priorizacao": 98.0,
                "hex_score_estrutural": 92.0,
                "flag_viavel": True,
                "flag_prioridade": True,
                "score_setor_2022_calibrado": 88.0,
                "coverage_pct_setor_2022": 97.0,
                "qualidade_join_uf": "A",
                "flag_censo_disponivel": True,
            },
            {
                "hex_id": "sp_granular_2",
                "lat": -23.56,
                "lng": -46.62,
                "cidade": "Sao Paulo",
                "nome_municipio": "Sao Paulo",
                "uf": "SP",
                "faixa_oportunidade": "alta",
                "score_priorizacao": 97.0,
                "hex_score_estrutural": 91.0,
                "flag_viavel": True,
                "flag_prioridade": True,
                "score_setor_2022_calibrado": 86.0,
                "coverage_pct_setor_2022": 96.0,
                "qualidade_join_uf": "A",
                "flag_censo_disponivel": True,
            },
            {
                "hex_id": "sp_granular_3",
                "lat": -23.57,
                "lng": -46.61,
                "cidade": "Sao Paulo",
                "nome_municipio": "Sao Paulo",
                "uf": "SP",
                "faixa_oportunidade": "media",
                "score_priorizacao": 96.0,
                "hex_score_estrutural": 89.0,
                "flag_viavel": True,
                "flag_prioridade": False,
                "score_setor_2022_calibrado": 82.0,
                "coverage_pct_setor_2022": 94.0,
                "qualidade_join_uf": "B",
                "flag_censo_disponivel": True,
            },
            {
                "hex_id": "sp_municipal_descartado",
                "lat": -23.58,
                "lng": -46.60,
                "cidade": "Sao Paulo",
                "nome_municipio": "Sao Paulo",
                "uf": "SP",
                "faixa_oportunidade": "media",
                "score_priorizacao": 95.0,
                "hex_score_estrutural": 87.0,
                "flag_viavel": True,
                "flag_prioridade": False,
                "score_setor_2022_calibrado": pd.NA,
                "coverage_pct_setor_2022": pd.NA,
                "qualidade_join_uf": "A",
                "flag_censo_disponivel": False,
            },
            {
                "hex_id": "ce_municipal",
                "lat": -3.73,
                "lng": -38.52,
                "cidade": "Fortaleza",
                "nome_municipio": "Fortaleza",
                "uf": "CE",
                "faixa_oportunidade": "alta",
                "score_priorizacao": 99.0,
                "hex_score_estrutural": 93.0,
                "flag_viavel": True,
                "flag_prioridade": True,
                "score_setor_2022_calibrado": pd.NA,
                "coverage_pct_setor_2022": pd.NA,
                "qualidade_join_uf": "C",
                "flag_censo_disponivel": False,
            },
        ]
    )

    deck, points = streamlit_app.build_map_figure(
        df,
        selected_ufs=["SP"],
        selected_cities=[],
    )

    assert deck is not None
    assert points == 3
    rendered = pd.DataFrame(deck.layers[0].data)
    assert set(rendered["hex_id"]) == {"sp_granular_1", "sp_granular_2", "sp_granular_3"}
    assert rendered["hex_id"].nunique() == len(rendered)
    assert rendered["confianca_geografica"].tolist() == ["granular", "granular", "granular"]


def test_build_map_figure_usa_geometria_granular_em_uf_ab_e_fallback_municipal_em_uf_c():
    df = pd.DataFrame(
        [
            {
                "hex_id": "sp_granular",
                "lat": -23.55,
                "lng": -46.63,
                "cidade": "Sao Paulo",
                "nome_municipio": "Sao Paulo",
                "uf": "SP",
                "faixa_oportunidade": "alta",
                "score_priorizacao": 98.0,
                "hex_score_estrutural": 92.0,
                "flag_viavel": True,
                "flag_prioridade": True,
                "score_setor_2022_calibrado": 88.0,
                "coverage_pct_setor_2022": 97.0,
                "qualidade_join_uf": "B",
                "flag_censo_disponivel": True,
            },
            {
                "hex_id": "sp_municipal_descartado",
                "lat": -23.57,
                "lng": -46.61,
                "cidade": "Sao Paulo",
                "nome_municipio": "Sao Paulo",
                "uf": "SP",
                "faixa_oportunidade": "media",
                "score_priorizacao": 91.0,
                "hex_score_estrutural": 86.0,
                "flag_viavel": True,
                "flag_prioridade": False,
                "score_setor_2022_calibrado": pd.NA,
                "coverage_pct_setor_2022": pd.NA,
                "qualidade_join_uf": "B",
                "flag_censo_disponivel": False,
            },
            {
                "hex_id": "ce_municipal",
                "lat": -3.73,
                "lng": -38.52,
                "cidade": "Fortaleza",
                "nome_municipio": "Fortaleza",
                "uf": "CE",
                "faixa_oportunidade": "alta",
                "score_priorizacao": 84.0,
                "hex_score_estrutural": 79.0,
                "flag_viavel": True,
                "flag_prioridade": True,
                "score_setor_2022_calibrado": pd.NA,
                "coverage_pct_setor_2022": pd.NA,
                "qualidade_join_uf": "C",
                "flag_censo_disponivel": False,
            },
        ]
    )

    deck, points = streamlit_app.build_map_figure(
        df,
        selected_ufs=["SP", "CE"],
        selected_cities=[],
    )

    assert deck is not None
    assert points == 2
    rendered = pd.DataFrame(deck.layers[0].data)
    assert set(rendered["hex_id"]) == {"sp_granular", "ce_municipal"}
    assert rendered.set_index("hex_id").loc["sp_granular", "confianca_geografica"] == "granular"
    assert rendered.set_index("hex_id").loc["ce_municipal", "confianca_geografica"] == "municipal"


def test_sort_carteira_by_m1_preserva_ranking_oficial_antes_do_hibrido():
    carteira = pd.DataFrame(
        [
            {
                "hex_id": "hex_b",
                "rank_brasil": 2,
                "rank_uf": 2,
                "score_priorizacao": 99.0,
                "rank_hex_intraurbano": 3,
                "score_setor_2022_calibrado": 92.0,
                "score_expansao_hibrido": 105.0,
            },
            {
                "hex_id": "hex_a",
                "rank_brasil": 1,
                "rank_uf": 1,
                "score_priorizacao": 88.0,
                "rank_hex_intraurbano": 1,
                "score_setor_2022_calibrado": 70.0,
                "score_expansao_hibrido": 80.0,
            },
        ]
    )

    sorted_df = streamlit_app._sort_carteira_by_m1(carteira)

    assert sorted_df["hex_id"].tolist() == ["hex_a", "hex_b"]


def test_tabelas_hibridas_expoem_flags_de_rastreabilidade():
    hdf = pd.DataFrame(
        [
            {
                "uf": "RJ",
                "nome_municipio": "Rio de Janeiro",
                "hex_id": "hex1",
                "score_setor_2022_calibrado": 91.0,
                "score_priorizacao": 97.0,
                "score_expansao_hibrido": 97.00091,
                "rank_hex_intraurbano": 1,
                "rank_hibrido_brasil": 3,
                "rank_hibrido_uf": 1,
                "top_hex_intraurbano": True,
                "top_oportunidade_municipio": True,
                "qualidade_join_uf": "B",
                "coverage_pct_setor_2022": 90.0,
                "flag_join_uf_restrito": False,
                "flag_baixa_pop_setor": True,
                "flag_outlier_espacial": True,
                "causa_outlier_espacial": "setor_baixa_pop_area_nobre",
                "motivo_nao_elegivel_censo": "elegivel",
                "top_municipio": True,
                "top_municipio_hibrido": True,
                "flag_censo_disponivel": True,
                "flag_monitoramento_prioritario": True,
                "flag_hex_hibrido_elegivel": True,
                "rank_municipio_uf": 1,
                "rank_municipio_brasil": 10,
            }
        ]
    )

    top_hexes = streamlit_app.build_hybrid_top_hexes_table(hdf)
    municipios = streamlit_app.build_hybrid_municipios_table(hdf)
    portfolio = streamlit_app.build_hybrid_portfolio_table(hdf)

    assert "Dens. < 5k" in top_hexes.columns
    assert "Causa Outlier" in top_hexes.columns
    assert top_hexes.loc[0, "Outlier Espacial"] == "Sim"
    assert "Melhor Hex Outlier" in municipios.columns
    assert municipios.loc[0, "Melhor Hex Dens. < 5k"] == "Sim"
    assert "Outlier" in portfolio.columns
    assert portfolio.loc[0, "Dens. < 5k"] == "Sim"
