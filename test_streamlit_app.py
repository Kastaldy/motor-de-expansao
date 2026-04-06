from pathlib import Path

import pandas as pd
import pytest

import streamlit_app


def _write_dashboard_parquet(root: Path, rows: list[dict[str, object]]) -> Path:
    path = root / "hexagonos_brasil_dashboard.parquet"
    pd.DataFrame(rows).to_parquet(path, index=False)
    return path


def test_load_data_prepara_aliases_e_score_oficial(tmp_path, monkeypatch):
    path = _write_dashboard_parquet(
        tmp_path,
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


def test_load_data_falha_sem_colunas_obrigatorias(tmp_path, monkeypatch):
    path = _write_dashboard_parquet(
        tmp_path,
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
