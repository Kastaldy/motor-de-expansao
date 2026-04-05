import pandas as pd

from fase1_bi_exports import (
    build_dashboard_dataset,
    build_hexagonos_mapa_sample,
    build_resumo_por_uf,
    build_top_oportunidades_resumo,
)


def _sample_source_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "hex_id": "h1",
                "lat": -23.55,
                "lng": -46.63,
                "uf": "SP",
                "regiao": "SE",
                "municipio_label": "Sao Paulo",
                "populacao_proxy": 12000.0,
                "hex_score_estrutural": 92.5,
                "faixa_oportunidade": "prioridade_maxima",
                "flag_viavel": True,
                "rank_brasil": 1,
                "rank_uf": 1,
                "rank_cidade": 1,
                "renda_per_capita": 3200.0,
                "motivo_priorizacao": "combinado",
                "motivo_alerta": "sem_alerta",
                "observacao_estrategica": "Alta renda e alta densidade",
            },
            {
                "hex_id": "h2",
                "lat": -23.56,
                "lng": -46.64,
                "uf": "SP",
                "regiao": "SE",
                "municipio_label": "Sao Paulo",
                "populacao_proxy": 8000.0,
                "hex_score_estrutural": 81.0,
                "faixa_oportunidade": "alta",
                "flag_viavel": True,
                "rank_brasil": 2,
                "rank_uf": 2,
                "rank_cidade": 2,
                "renda_per_capita": 2800.0,
                "motivo_priorizacao": "renda_alta",
                "motivo_alerta": "sem_alerta",
                "observacao_estrategica": "Alta renda, baixa densidade",
            },
            {
                "hex_id": "h3",
                "lat": -22.90,
                "lng": -43.20,
                "uf": "RJ",
                "regiao": "SE",
                "municipio_label": "Rio de Janeiro",
                "populacao_proxy": 9000.0,
                "hex_score_estrutural": 70.0,
                "faixa_oportunidade": "media",
                "flag_viavel": True,
                "rank_brasil": 3,
                "rank_uf": 1,
                "rank_cidade": 1,
                "renda_per_capita": 2500.0,
                "motivo_priorizacao": "alta_pop_jovem",
                "motivo_alerta": "sem_alerta",
                "observacao_estrategica": "Alta densidade, renda moderada",
            },
            {
                "hex_id": "h4",
                "lat": -22.91,
                "lng": -43.21,
                "uf": "RJ",
                "regiao": "SE",
                "municipio_label": "Rio de Janeiro",
                "populacao_proxy": 3000.0,
                "hex_score_estrutural": 40.0,
                "faixa_oportunidade": "descartado",
                "flag_viavel": False,
                "rank_brasil": 4,
                "rank_uf": 2,
                "rank_cidade": 2,
                "renda_per_capita": 1200.0,
                "motivo_priorizacao": "sem_destaque",
                "motivo_alerta": "renda_baixa | score_baixo",
                "observacao_estrategica": "Regiao fora do target ideal",
            },
        ]
    )


def test_build_dashboard_dataset_padroniza_colunas_obrigatorias():
    dashboard = build_dashboard_dataset(_sample_source_df())

    assert dashboard.columns.tolist() == [
        "hex_id",
        "lat",
        "lng",
        "uf",
        "cidade",
        "regiao",
        "hex_score_estrutural",
        "faixa_oportunidade",
        "flag_viavel",
        "rank_brasil",
        "rank_uf",
        "rank_cidade",
        "renda_per_capita",
        "proxy_populacao",
        "motivo_priorizacao",
        "motivo_alerta",
        "observacao_estrategica",
    ]
    assert dashboard.loc[0, "cidade"] == "Sao Paulo"
    assert dashboard.loc[0, "proxy_populacao"] == 12000.0
    assert str(dashboard["faixa_oportunidade"].dtype) == "category"


def test_build_dashboard_dataset_substitui_codigo_por_nome_quando_lookup_existe():
    source = _sample_source_df()
    source.loc[0, "cod_municipio"] = "3550308"
    source.loc[0, "municipio_label"] = "3550308"
    lookup = pd.DataFrame([{"cod_municipio": "3550308", "nome_municipio": "Sao Paulo"}])

    dashboard = build_dashboard_dataset(source, df_municipios_lookup=lookup)

    assert dashboard.loc[0, "cidade"] == "Sao Paulo"


def test_build_top_oportunidades_resumo_restringe_para_hexagonos_viaveis():
    dashboard = build_dashboard_dataset(_sample_source_df())

    resumo = build_top_oportunidades_resumo(dashboard, top_n=2)

    assert resumo["rank_brasil"].tolist() == [1, 2]
    assert resumo["cidade"].tolist() == ["Sao Paulo", "Sao Paulo"]
    assert resumo["faixa_oportunidade"].tolist() == ["prioridade_maxima", "alta"]


def test_build_resumo_por_uf_calcula_metricas_executivas():
    dashboard = build_dashboard_dataset(_sample_source_df())

    resumo = build_resumo_por_uf(dashboard)
    sp = resumo.loc[resumo["uf"] == "SP"].iloc[0]
    rj = resumo.loc[resumo["uf"] == "RJ"].iloc[0]

    assert sp["total_hexagonos"] == 2
    assert sp["total_viaveis"] == 2
    assert sp["pct_viaveis"] == 100.0
    assert sp["qtd_prioridade_maxima"] == 1
    assert sp["qtd_alta"] == 1
    assert rj["total_viaveis"] == 1


def test_build_hexagonos_mapa_sample_pega_top_30_por_cento_do_ranking():
    dashboard = build_dashboard_dataset(_sample_source_df())

    sample = build_hexagonos_mapa_sample(dashboard, top_pct=0.30)

    assert sample["hex_id"].tolist() == ["h1", "h2"]
