import numpy as np
import pandas as pd

from dashboard.constants import REQUIRED_COLUMNS
from fase1_bi_exports import (
    build_dashboard_dataset,
    build_hexagonos_mapa_sample,
    build_resumo_por_uf,
    build_top_oportunidades_resumo,
    read_enriched_dashboard,
    write_enriched_dashboard_partitioned,
)
from motor_expansao.dashboard.data import _prepare_dataframe, enrich_dashboard_data


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
                "renda_pct_nacional": 0.95,
                "pop_pct_nacional": 0.90,
                "hex_score_estrutural": 92.5,
                "ajuste_executivo": 5.0,
                "score_priorizacao": 97.5,
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
                "renda_pct_nacional": 0.82,
                "pop_pct_nacional": 0.62,
                "hex_score_estrutural": 81.0,
                "ajuste_executivo": 2.0,
                "score_priorizacao": 83.0,
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
                "renda_pct_nacional": 0.55,
                "pop_pct_nacional": 0.83,
                "hex_score_estrutural": 70.0,
                "ajuste_executivo": 1.0,
                "score_priorizacao": 71.0,
                "faixa_oportunidade": "media",
                "flag_viavel": True,
                "rank_brasil": 3,
                "rank_uf": 1,
                "rank_cidade": 1,
                "renda_per_capita": 2500.0,
                "motivo_priorizacao": "alta_populacao",
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
                "renda_pct_nacional": 0.18,
                "pop_pct_nacional": 0.12,
                "hex_score_estrutural": 40.0,
                "ajuste_executivo": -8.0,
                "score_priorizacao": 32.0,
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
        "score_oficial",
        "score_oficial_nome",
        "score_percentil_nacional",
        "faixa_oportunidade",
        "flag_viavel",
        "flag_prioridade",
        "rank_brasil",
        "rank_uf",
        "rank_cidade",
        "renda_per_capita",
        "renda_target_proxy",
        "populacao_proxy",
        "proxy_populacao",
        "renda_pct_nacional",
        "pop_pct_nacional",
        "ajuste_executivo",
        "score_priorizacao",
        "criterio_prioridade",
        "threshold_prioridade_uf",
        "osm_status",
        "fonte_demografica",
        "fonte_renda",
        "fonte_populacao",
        "nivel_geografico_ibge",
        "fallback_setor_censitario",
        "motivo_fallback_setor",
        "fonte_geometria_ibge",
        "metodo_atribuicao_municipio",
        "data_referencia_ibge",
        "motivo_priorizacao",
        "motivo_alerta",
        "observacao_estrategica",
    ]
    assert dashboard.loc[0, "cidade"] == "Sao Paulo"
    assert dashboard.loc[0, "populacao_proxy"] == 12000.0
    assert dashboard.loc[0, "proxy_populacao"] == 12000.0
    assert dashboard.loc[0, "score_priorizacao"] == 97.5
    assert dashboard.loc[0, "ajuste_executivo"] == 5.0
    assert dashboard.loc[0, "score_oficial"] == 97.5
    assert dashboard.loc[0, "score_oficial_nome"] == "score_priorizacao"
    assert dashboard.loc[0, "osm_status"] == "nao_aplicado_mvp_nacional"
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
    assert resumo["score_oficial_nome"].tolist() == ["score_priorizacao", "score_priorizacao"]
    assert resumo["score_priorizacao"].tolist() == [97.5, 83.0]


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


def _sample_m1_base_df() -> pd.DataFrame:
    rows = [
        ("hSP1", "SP", "Sao Paulo", "prioridade_maxima", True, True, 1),
        ("hSP2", "SP", "Campinas", "alta", True, False, 2),
        ("hRJ1", "RJ", "Rio de Janeiro", "media", True, False, 3),
        ("hRJ2", "RJ", "Niteroi", "descartado", False, False, 4),
    ]
    records = []
    for i, (hex_id, uf, cidade, faixa, viavel, prioridade, rank) in enumerate(rows):
        records.append(
            {
                "hex_id": hex_id,
                "lat": -23.5 - i,
                "lng": -46.6 - i,
                "uf": uf,
                "cidade": cidade,
                "regiao": "SE",
                "score_priorizacao": 95.0 - i * 5,
                "hex_score_estrutural": 90.0 - i * 5,
                "ajuste_executivo": 2.0,
                "faixa_oportunidade": faixa,
                "flag_viavel": viavel,
                "flag_prioridade": prioridade,
                "rank_brasil": rank,
                "rank_uf": rank,
                "rank_cidade": 1,
                "renda_per_capita": 3000.0 + i,
                "populacao_proxy": 12000.0 - i * 100,
            }
        )
    return pd.DataFrame(records)[REQUIRED_COLUMNS]


def test_dataset_enriquecido_particionado_bate_com_runtime_para_uf(tmp_path):
    base = _prepare_dataframe(_sample_m1_base_df())
    runtime = enrich_dashboard_data(base, pd.DataFrame(), pd.DataFrame())

    out_dir = write_enriched_dashboard_partitioned(runtime, base_dir=tmp_path / "enriquecido")
    assert (out_dir / "uf=SP").exists()
    assert (out_dir / "uf=RJ").exists()

    materializado = read_enriched_dashboard(out_dir, uf="SP")
    runtime_sp = runtime[runtime["uf"].astype(str) == "SP"]

    # contagem de linhas por particao
    assert len(materializado) == len(runtime_sp)

    mat = materializado.sort_values("hex_id").reset_index(drop=True)
    rt = runtime_sp.sort_values("hex_id").reset_index(drop=True)

    assert mat["hex_id"].tolist() == rt["hex_id"].tolist()
    assert mat["uf"].astype(str).tolist() == ["SP"] * len(mat)
    assert mat["faixa_oportunidade"].astype(str).tolist() == rt["faixa_oportunidade"].astype(str).tolist()
    for col in ["score_priorizacao", "rank_brasil", "populacao_proxy"]:
        np.testing.assert_allclose(
            pd.to_numeric(mat[col]).to_numpy(),
            pd.to_numeric(rt[col]).to_numpy(),
        )
    # nenhuma coluna do frame de runtime se perde no round-trip (uf reconstruida da particao)
    assert set(runtime.columns) <= set(materializado.columns)
