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
                "sam_fitness_potencial": 810.0,
                "oferta_consumida_mercado_estimada": 250.0,
                "oferta_consumida_ultra_real": 120.0,
                "oferta_efetiva_disponivel": 560.0,
                "share_ultra_estimado_hex": 0.324,
                "score_oportunidade_residual": 22.4,
                "quartil_oportunidade_residual": "Q4_maior_residual",
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
    assert float(enriched.loc[0, "oferta_efetiva_disponivel"]) == 560.0
    assert str(enriched.loc[0, "quartil_oportunidade_residual"]) == "Q4_maior_residual"


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


def test_load_competitors_ignora_skyfit(tmp_path):
    (tmp_path / "unidades_smart_fit.csv").write_text(
        "nome_unidade;latitude;longitude;data_coleta\n"
        "Augusta;-23.5572558791;-46.6591845018;2026-04-22\n",
        encoding="utf-8",
    )
    (tmp_path / "SkyFit_unidades_geocodificado.csv").write_text(
        "NOMENCLATURA UNIDADE;CIDADE;ESTADO;latitude;longitude;geocoding_status\n"
        "SKYFIT TAQUARA;RIO DE JANEIRO;RJ;-22.9236315;-43.3750906;OK\n",
        encoding="utf-8-sig",
    )
    competitors = streamlit_app.load_competitor_points(tmp_path)
    assert "skyfit" not in set(competitors["rede"])
    assert "smart_fit" in set(competitors["rede"])


def test_load_competitors_carrega_multiplas_planilhas(tmp_path):
    (tmp_path / "unidades_smart_fit.csv").write_text(
        "nome_unidade;latitude;longitude;data_coleta\n"
        "Augusta;-23.5572558791;-46.6591845018;2026-04-22\n",
        encoding="utf-8",
    )
    (tmp_path / "unidades_bluefit.csv").write_text(
        "nome_unidade;latitude;longitude;data_coleta\n"
        "Blue Rio;-22.90;-43.20;2026-04-22\n",
        encoding="utf-8",
    )
    (tmp_path / "unidades_26fit.csv").write_text(
        "nome_unidade;latitude;longitude;data_coleta\n"
        "Alegrete;-29.781996;-55.793823;2026-04-29\n",
        encoding="utf-8",
    )
    competitors = streamlit_app.load_competitor_points(tmp_path)
    assert set(competitors["rede"]) == {"smart_fit", "bluefit", "26fit"}
    assert len(competitors) == 3


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


def test_build_map_figure_adiciona_pins_de_concorrentes_no_recorte():
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
                "qualidade_join_uf": "A",
                "flag_censo_disponivel": True,
            }
        ]
    )
    competitors = pd.DataFrame(
        [
            {
                "rede": "smart_fit",
                "rede_label": "Smart Fit",
                "nome_unidade": "Smart Paulista",
                "lat": -23.551,
                "lng": -46.631,
                "cidade": "",
                "uf": "",
                "arquivo_origem": "unidades_smart_fit.csv",
            },
            {
                "rede": "bluefit",
                "rede_label": "Bluefit",
                "nome_unidade": "Blue Rio",
                "lat": -22.90,
                "lng": -43.20,
                "cidade": "",
                "uf": "",
                "arquivo_origem": "unidades_bluefit.csv",
            },
        ]
    )

    deck, points = streamlit_app.build_map_figure(
        df,
        selected_ufs=["SP"],
        selected_cities=[],
        competitors_df=competitors,
    )

    assert deck is not None
    assert points == 1
    assert len(deck.layers) == 2
    rendered_hex = pd.DataFrame(deck.layers[0].data)
    rendered_competitors = pd.DataFrame(deck.layers[1].data)
    assert "tooltip_title" in rendered_hex.columns
    assert rendered_competitors["nome_unidade"].tolist() == ["Smart Paulista"]
    assert rendered_competitors.loc[0, "icon_data"]["url"].startswith("data:image/")


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


def test_enrich_dashboard_data_deriva_colunas_pop_cut():
    base_df = pd.DataFrame(
        [
            {
                "hex_id": "h1",
                "lat": -23.55,
                "lng": -46.63,
                "uf": "SP",
                "cidade": "Sao Paulo",
                "regiao": "SE",
                "score_priorizacao": 80.0,
                "hex_score_estrutural": 75.0,
                "ajuste_executivo": 5.0,
                "faixa_oportunidade": "alta",
                "flag_viavel": True,
                "flag_prioridade": True,
                "rank_brasil": 1,
                "rank_uf": 1,
                "rank_cidade": 1,
                "renda_per_capita": 5000.0,
                "populacao_proxy": 15_000.0,
            },
            {
                "hex_id": "h2",
                "lat": -23.56,
                "lng": -46.64,
                "uf": "SP",
                "cidade": "Sao Paulo",
                "regiao": "SE",
                "score_priorizacao": 70.0,
                "hex_score_estrutural": 65.0,
                "ajuste_executivo": 5.0,
                "faixa_oportunidade": "media",
                "flag_viavel": False,
                "flag_prioridade": False,
                "rank_brasil": 2,
                "rank_uf": 2,
                "rank_cidade": 2,
                "renda_per_capita": 4000.0,
                "populacao_proxy": 3_000.0,
            },
        ]
    )

    enriched = streamlit_app.enrich_dashboard_data(base_df)

    assert "populacao_corte_hex" in enriched.columns
    assert "fonte_populacao_corte" in enriched.columns
    assert "flag_pop_min_5k" in enriched.columns
    assert bool(enriched.loc[enriched["hex_id"] == "h1", "flag_pop_min_5k"].values[0]) is True
    assert bool(enriched.loc[enriched["hex_id"] == "h2", "flag_pop_min_5k"].values[0]) is False
    assert enriched.loc[enriched["hex_id"] == "h1", "score_priorizacao"].values[0] == 80.0


def test_enrich_dashboard_data_usa_setor_2022_quando_granular():
    base_df = pd.DataFrame(
        [
            {
                "hex_id": "g1",
                "lat": -15.0,
                "lng": -47.0,
                "uf": "DF",
                "cidade": "Brasilia",
                "regiao": "CO",
                "score_priorizacao": 95.0,
                "hex_score_estrutural": 90.0,
                "ajuste_executivo": 5.0,
                "faixa_oportunidade": "prioridade_maxima",
                "flag_viavel": True,
                "flag_prioridade": True,
                "rank_brasil": 1,
                "rank_uf": 1,
                "rank_cidade": 1,
                "renda_per_capita": 7000.0,
                "populacao_proxy": 5_000.0,
            }
        ]
    )
    hybrid_df = pd.DataFrame(
        [
            {
                "hex_id": "g1",
                "nome_municipio": "Brasilia",
                "qualidade_join_uf": "A",
                "flag_censo_disponivel": True,
                "pop_total_setor_2022": 20_000.0,
                "score_setor_2022_calibrado": 88.0,
                "flag_censo_elegivel": True,
                "flag_hex_hibrido_elegivel": True,
                "top_municipio": True,
                "top_municipio_hibrido": True,
                "top_hex_intraurbano": True,
                "rank_hex_intraurbano": 1,
                "rank_municipio_uf": 1,
                "coverage_pct_setor_2022": 99.0,
                "flag_join_uf_restrito": False,
                "flag_baixa_pop_setor": False,
                "flag_outlier_espacial": False,
                "motivo_nao_elegivel_censo": "elegivel",
                "top_oportunidade_municipio": True,
            }
        ]
    )

    enriched = streamlit_app.enrich_dashboard_data(base_df, hybrid_df)

    row = enriched.loc[enriched["hex_id"] == "g1"].iloc[0]
    assert row["fonte_populacao_corte"] == "setor_2022"
    assert float(row["populacao_corte_hex"]) == 20_000.0
    assert bool(row["flag_pop_min_5k"]) is True


def test_parse_coordinate_input_via_streamlit_app():
    assert streamlit_app.parse_coordinate_input("-23.55,-46.63") == pytest.approx((-23.55, -46.63))
    assert streamlit_app.parse_coordinate_input("-23,55; -46,63") == pytest.approx((-23.55, -46.63))
    assert streamlit_app.parse_coordinate_input("invalido") is None
    assert streamlit_app.parse_coordinate_input("20.0,-50.0") is None  # fora do Brasil


def test_lookup_hex_by_coord_encontra_hex_na_base():
    import h3
    lat, lng = -23.55, -46.63
    hex_id = h3.latlng_to_cell(lat, lng, 7)
    df = pd.DataFrame([{
        "hex_id": hex_id,
        "lat": lat,
        "lng": lng,
        "uf": "SP",
        "cidade": "Sao Paulo",
        "score_priorizacao": 80.0,
        "rank_brasil": 100,
    }])
    result = streamlit_app.lookup_hex_by_coord(lat, lng, df)
    assert result is not None
    assert result["hex_id"] == hex_id
    assert result["_not_found"] is False


def test_build_map_figure_centraliza_no_search_pin_e_adiciona_layer():
    import h3
    lat, lng = -23.55, -46.63
    hex_id = h3.latlng_to_cell(lat, lng, 7)
    df = pd.DataFrame([{
        "hex_id": hex_id,
        "lat": lat,
        "lng": lng,
        "cidade": "Sao Paulo",
        "nome_municipio": "Sao Paulo",
        "uf": "SP",
        "faixa_oportunidade": "alta",
        "score_priorizacao": 80.0,
        "hex_score_estrutural": 75.0,
        "flag_viavel": True,
        "flag_prioridade": True,
        "score_setor_2022_calibrado": pd.NA,
        "coverage_pct_setor_2022": pd.NA,
        "qualidade_join_uf": "C",
        "flag_censo_disponivel": False,
    }])

    deck, points = streamlit_app.build_map_figure(
        df,
        selected_ufs=["SP"],
        selected_cities=[],
        search_pin=(-15.77, -47.93),
    )

    assert deck is not None
    assert len(deck.layers) == 2  # hex layer + pin layer
    view = deck.initial_view_state
    assert view.latitude == pytest.approx(-15.77)
    assert view.longitude == pytest.approx(-47.93)
    assert view.zoom == pytest.approx(10.0)


def _hex_row(hex_id: str, lat: float, lng: float, **kwargs) -> dict:
    base = {
        "hex_id": hex_id,
        "lat": lat,
        "lng": lng,
        "cidade": "Sao Paulo",
        "nome_municipio": "Sao Paulo",
        "uf": "SP",
        "faixa_oportunidade": "alta",
        "score_priorizacao": 80.0,
        "hex_score_estrutural": 75.0,
        "flag_viavel": True,
        "flag_prioridade": True,
        "score_setor_2022_calibrado": 85.0,
        "coverage_pct_setor_2022": 97.0,
        "qualidade_join_uf": "A",
        "flag_censo_disponivel": True,
        "populacao_proxy": 12_000,
        "renda_per_capita": 3_500,
        "pop_total_setor_2022": 12_345,
        "renda_per_capita_setor_2022_calibrada": 6_789,
        "flag_pop_min_5k": True,
        "sam_fitness_potencial": 540.0,
        "oferta_consumida_mercado_estimada": 200.0,
        "oferta_consumida_ultra_real": 25.0,
        "oferta_efetiva_disponivel": 300.0,
        "share_ultra_estimado_hex": 0.111,
        "score_oportunidade_residual": 12.0,
        "quartil_oportunidade_residual": "Q3",
    }
    base.update(kwargs)
    return base


def test_build_map_figure_pinta_hex_descartado_por_pop_com_cor_neutra():
    import h3
    lat_ok, lng_ok = -23.55, -46.63
    lat_bad, lng_bad = -23.65, -46.50  # coords diferentes o suficiente para hex distinto
    hex_ok = h3.latlng_to_cell(lat_ok, lng_ok, 7)
    hex_bad = h3.latlng_to_cell(lat_bad, lng_bad, 7)
    assert hex_ok != hex_bad, "sanity: coords devem mapear para hexes distintos"

    df = pd.DataFrame([
        _hex_row(hex_ok, lat_ok, lng_ok, flag_pop_min_5k=True),
        _hex_row(hex_bad, lat_bad, lng_bad, flag_pop_min_5k=False),
    ])

    deck, points = streamlit_app.build_map_figure(df, selected_ufs=["SP"], selected_cities=[])

    assert deck is not None
    assert points == 2
    rendered = pd.DataFrame(deck.layers[0].data).set_index("hex_id")
    # hex descartado deve ter cor cinza neutra
    assert rendered.loc[hex_bad, "fill_color"] == [120, 120, 140, 70]
    # hex nao descartado nao deve ter cor cinza
    assert rendered.loc[hex_ok, "fill_color"] != [120, 120, 140, 70]
    # tooltip do descartado deve mencionar descarte
    assert "Descartado" in rendered.loc[hex_bad, "tooltip_title"]
    # tooltip do nao descartado nao deve mencionar descarte
    assert "Descartado" not in rendered.loc[hex_ok, "tooltip_title"]


def test_build_map_figure_adiciona_layer_de_destaque_do_hex_pesquisado():
    import h3
    lat, lng = -23.55, -46.63
    hex_id = h3.latlng_to_cell(lat, lng, 7)
    lat_bsb, lng_bsb = -15.77, -47.93
    hex_brasilia = h3.latlng_to_cell(lat_bsb, lng_bsb, 7)
    df = pd.DataFrame([
        _hex_row(hex_id, lat, lng),
        _hex_row(
            hex_brasilia,
            lat_bsb,
            lng_bsb,
            cidade="Brasilia",
            nome_municipio="Brasilia",
            uf="DF",
            score_priorizacao=91.0,
            hex_score_estrutural=89.0,
            populacao_proxy=20_000,
            renda_per_capita=4_200,
            pop_total_setor_2022=21_000,
            renda_per_capita_setor_2022_calibrada=4_500,
        ),
    ])

    # sem search_hex_id: apenas 1 layer (sem competidores)
    deck_sem, _ = streamlit_app.build_map_figure(df, selected_ufs=["SP"], selected_cities=[])
    assert deck_sem is not None
    assert len(deck_sem.layers) == 1

    # com search_hex_id: 2 layers (hex + destaque)
    deck_com, _ = streamlit_app.build_map_figure(
        df, selected_ufs=["SP"], selected_cities=[], search_hex_id=hex_id
    )
    assert deck_com is not None
    assert len(deck_com.layers) == 2
    highlight_data = pd.DataFrame(deck_com.layers[-1].data)
    assert hex_id in highlight_data["hex_id"].values
    highlight = highlight_data.iloc[0]
    assert highlight["tooltip_title"] == "Sao Paulo / SP"
    assert highlight["tooltip_line_3"] == "Score M1: 80.00"
    assert highlight["tooltip_line_10"] == "Habitantes: 12.345"
    assert highlight["tooltip_line_11"] == "Renda per capita: R$ 6.789"
    assert highlight["tooltip_line_12"] == "Residual fitness: 300 | Score residual: 12.00 | Q3"
    assert highlight["tooltip_line_13"] == "SAM fitness: 540 | Consumo mercado: 200"
    assert highlight["tooltip_line_14"] == "Ultra real: 25 | Share Ultra: 11.1%"


def test_build_map_figure_destaque_hex_aparece_mesmo_fora_dos_filtros():
    """Hex pesquisado deve ser destacado mesmo se estiver fora do recorte filtrado."""
    import h3
    lat, lng = -23.55, -46.63
    hex_id = h3.latlng_to_cell(lat, lng, 7)
    lat_bsb, lng_bsb = -15.77, -47.93
    hex_brasilia = h3.latlng_to_cell(lat_bsb, lng_bsb, 7)
    df = pd.DataFrame([
        _hex_row(hex_id, lat, lng),
        _hex_row(
            hex_brasilia,
            lat_bsb,
            lng_bsb,
            cidade="Brasilia",
            nome_municipio="Brasilia",
            uf="DF",
            score_priorizacao=91.0,
            hex_score_estrutural=89.0,
            populacao_proxy=20_000,
            renda_per_capita=4_200,
            pop_total_setor_2022=21_000,
            renda_per_capita_setor_2022_calibrada=4_500,
        ),
    ])
    deck, _ = streamlit_app.build_map_figure(
        df, selected_ufs=["SP"], selected_cities=[], search_hex_id=hex_brasilia
    )
    assert deck is not None
    # deve ter o hex layer (SP) + destaque (Brasilia fora do filtro)
    assert len(deck.layers) == 2
    highlight_data = pd.DataFrame(deck.layers[-1].data)
    assert hex_brasilia in highlight_data["hex_id"].values
    highlight = highlight_data.iloc[0]
    assert highlight["tooltip_title"] == "Brasilia / DF"
    assert highlight["tooltip_line_3"] == "Score M1: 91.00"
    assert highlight["tooltip_line_10"] == "Habitantes: 21.000"


def test_build_hybrid_map_figure_destaque_hex_usa_tooltip_completo():
    import h3

    def hybrid_row(hex_id: str, lat: float, lng: float, uf: str, cidade: str, score_m1: float) -> dict:
        return {
            "hex_id": hex_id,
            "lat": lat,
            "lng": lng,
            "uf": uf,
            "nome_municipio": cidade,
            "score_setor_2022_calibrado": 88.0,
            "score_priorizacao": score_m1,
            "score_expansao_hibrido": 93.0,
            "densidade_pop_setor_hab_km2": 8_500,
            "qualidade_join_uf": "A",
            "flag_join_uf_restrito": False,
            "flag_baixa_pop_setor": False,
            "flag_outlier_espacial": False,
            "causa_outlier_espacial": pd.NA,
            "coverage_pct_setor_2022": 96.0,
            "motivo_nao_elegivel_censo": pd.NA,
            "elegibilidade_hibrida": "Elegivel",
            "rank_hex_intraurbano": 1,
            "top_hex_intraurbano": True,
            "top_oportunidade_municipio": True,
            "populacao_proxy": 20_000,
            "renda_per_capita": 4_200,
            "pop_total_setor_2022": 21_000,
            "renda_per_capita_setor_2022_calibrada": 4_500,
            "flag_pop_min_5k": True,
            "sam_fitness_potencial": 1000.0,
            "oferta_consumida_mercado_estimada": 350.0,
            "oferta_consumida_ultra_real": 150.0,
            "oferta_efetiva_disponivel": 650.0,
            "share_ultra_estimado_hex": 0.3,
            "score_oportunidade_residual": 26.0,
            "quartil_oportunidade_residual": "Q4_maior_residual",
        }

    hex_sp = h3.latlng_to_cell(-23.55, -46.63, 7)
    hex_brasilia = h3.latlng_to_cell(-15.77, -47.93, 7)
    hdf = pd.DataFrame([
        hybrid_row(hex_sp, -23.55, -46.63, "SP", "Sao Paulo", 80.0),
        hybrid_row(hex_brasilia, -15.77, -47.93, "DF", "Brasilia", 91.0),
    ])

    deck, _ = streamlit_app.build_hybrid_map_figure(
        hdf,
        selected_ufs=["SP"],
        selected_cities=[],
        search_hex_id=hex_brasilia,
    )

    assert deck is not None
    assert len(deck.layers) == 2
    highlight = pd.DataFrame(deck.layers[-1].data).iloc[0]
    assert highlight["tooltip_title"] == "Brasilia / DF"
    assert highlight["tooltip_line_1"] == "Score Censitario 2022: 88.00"
    assert highlight["tooltip_line_2"] == "Score M1: 91.00"
    assert highlight["tooltip_line_3"] == "Score Hibrido: 93.00"
    assert highlight["tooltip_line_11"] == "Habitantes: 21.000"
    assert highlight["tooltip_line_12"] == "Renda per capita: R$ 4.500"
    assert highlight["tooltip_line_13"] == "Residual fitness: 650 | Score residual: 26.00 | Q4_maior_residual"
    assert highlight["tooltip_line_14"] == "SAM fitness: 1.000 | Consumo mercado: 350 | Ultra real: 150 | Share Ultra: 30.0%"
