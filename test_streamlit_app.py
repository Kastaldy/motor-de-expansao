from pathlib import Path

import pandas as pd

import streamlit_app


def _write_outputs(root: Path, *, include_score_oficial: bool) -> None:
    parquet_base = {
        "hex_id": ["abc"],
        "lat": [-23.55],
        "lng": [-46.63],
        "uf": ["SP"],
        "cidade": ["Sao Paulo"],
        "regiao": ["SE"],
        "score_priorizacao": [81.0],
        "hex_score_estrutural": [77.0],
        "faixa_oportunidade": ["alta"],
        "flag_viavel": [True],
        "rank_brasil": [1],
        "rank_uf": [1],
        "rank_cidade": [1],
        "motivo_priorizacao": ["renda_alta"],
        "observacao_estrategica": ["Alta renda"],
    }
    if include_score_oficial:
        parquet_base["score_oficial"] = [88.0]

    df_parquet = pd.DataFrame(parquet_base)
    df_parquet.to_parquet(root / "hexagonos_mapa_sample.parquet", index=False)
    df_parquet.to_parquet(root / "hexagonos_brasil_dashboard.parquet", index=False)

    csv_base = {
        "rank_brasil": [1],
        "uf": ["SP"],
        "cidade": ["Sao Paulo"],
        "score_priorizacao": [81.0],
        "hex_score_estrutural": [77.0],
        "faixa_oportunidade": ["alta"],
        "motivo_priorizacao": ["renda_alta"],
        "observacao_estrategica": ["Alta renda"],
    }
    if include_score_oficial:
        csv_base["score_oficial"] = [88.0]

    pd.DataFrame(csv_base).to_csv(
        root / "top_oportunidades_resumo.csv",
        sep=";",
        encoding="utf-8-sig",
        index=False,
    )
    pd.DataFrame(
        {
            "uf": ["SP"],
            "total_hexagonos": [1],
            "total_viaveis": [1],
            "pct_viaveis": [100.0],
            "score_medio": [88.0 if include_score_oficial else 81.0],
            "score_p90": [88.0 if include_score_oficial else 81.0],
            "qtd_prioridade_maxima": [0],
            "qtd_alta": [1],
        }
    ).to_csv(
        root / "resumo_por_uf.csv",
        sep=";",
        encoding="utf-8-sig",
        index=False,
    )


def test_resolve_score_column_prefere_score_oficial():
    assert (
        streamlit_app._resolve_score_column(
            ["hex_score_estrutural", "score_priorizacao", "score_oficial"]
        )
        == "score_oficial"
    )


def test_load_data_consume_score_oficial_quando_disponivel(tmp_path, monkeypatch):
    _write_outputs(tmp_path, include_score_oficial=True)
    monkeypatch.setattr(streamlit_app, "DATA_DIR", tmp_path)
    streamlit_app.load_data.clear()

    df_mapa, df_dashboard, df_top, df_resumo = streamlit_app.load_data()

    assert df_mapa.loc[0, "score_exibicao"] == 88.0
    assert df_dashboard.loc[0, "score_exibicao"] == 88.0
    assert df_top.loc[0, "score_exibicao"] == 88.0
    assert df_resumo.loc[0, "score_medio"] == 88.0


def test_load_data_faz_fallback_para_score_priorizacao(tmp_path, monkeypatch):
    _write_outputs(tmp_path, include_score_oficial=False)
    monkeypatch.setattr(streamlit_app, "DATA_DIR", tmp_path)
    streamlit_app.load_data.clear()

    df_mapa, df_dashboard, df_top, _ = streamlit_app.load_data()

    assert df_mapa.loc[0, "score_exibicao"] == 81.0
    assert df_dashboard.loc[0, "score_exibicao"] == 81.0
    assert df_top.loc[0, "score_exibicao"] == 81.0
