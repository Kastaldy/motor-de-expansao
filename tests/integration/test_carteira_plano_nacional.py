from pathlib import Path

import pandas as pd

from jobs.pipelines import (
    enriquecer_outputs_residual_mercado,
    gerar_carteira_acionavel,
    gerar_plano_expansao_curto_prazo,
)


def _local_test_dir(name: str):
    root = Path("fixtures") / "_tmp_carteira_plano_tests" / name
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_gerar_carteira_aplica_fallback_municipal_e_preserva_ordenacao_oficial(
    monkeypatch,
):
    root = _local_test_dir("carteira")
    input_path = root / "oportunidades_expansao_hibrido.parquet"

    pd.DataFrame(
        [
            {
                "hex_id": "sp_top1",
                "uf": "SP",
                "nome_municipio": "Sao Paulo",
                "cod_municipio": 3550308,
                "score_priorizacao": 95.0,
                "score_priorizacao_municipio": 95.0,
                "score_setor_2022_calibrado": 91.0,
                "score_expansao_hibrido": 95.00091,
                "rank_brasil": 30,
                "rank_uf": 1,
                "rank_municipio_uf": 1,
                "rank_municipio_brasil": 3,
                "rank_hex_intraurbano": 1,
                "top_municipio": True,
                "top_hex_intraurbano": True,
                "flag_hex_hibrido_elegivel": True,
                "qualidade_join_uf": "B",
                "flag_outlier_espacial": False,
                "flag_baixa_pop_setor": False,
                "flag_join_uf_restrito": False,
            },
            {
                "hex_id": "sp_top2",
                "uf": "SP",
                "nome_municipio": "Sao Paulo",
                "cod_municipio": 3550308,
                "score_priorizacao": 95.0,
                "score_priorizacao_municipio": 95.0,
                "score_setor_2022_calibrado": 88.0,
                "score_expansao_hibrido": 95.00088,
                "rank_brasil": 31,
                "rank_uf": 2,
                "rank_municipio_uf": 1,
                "rank_municipio_brasil": 3,
                "rank_hex_intraurbano": 2,
                "top_municipio": True,
                "top_hex_intraurbano": True,
                "flag_hex_hibrido_elegivel": True,
                "qualidade_join_uf": "B",
                "flag_outlier_espacial": False,
                "flag_baixa_pop_setor": False,
                "flag_join_uf_restrito": False,
            },
            {
                "hex_id": "sp_descartado_sem_top_hex",
                "uf": "SP",
                "nome_municipio": "Sao Paulo",
                "cod_municipio": 3550308,
                "score_priorizacao": 95.0,
                "score_priorizacao_municipio": 95.0,
                "score_setor_2022_calibrado": 99.0,
                "score_expansao_hibrido": 95.00099,
                "rank_brasil": 1,
                "rank_uf": 1,
                "rank_municipio_uf": 1,
                "rank_municipio_brasil": 3,
                "rank_hex_intraurbano": 99,
                "top_municipio": True,
                "top_hex_intraurbano": False,
                "flag_hex_hibrido_elegivel": True,
                "qualidade_join_uf": "B",
                "flag_outlier_espacial": False,
                "flag_baixa_pop_setor": False,
                "flag_join_uf_restrito": False,
            },
            {
                "hex_id": "ce_fallback1",
                "uf": "CE",
                "nome_municipio": "Fortaleza",
                "cod_municipio": 2304400,
                "score_priorizacao": 99.0,
                "score_priorizacao_municipio": 99.0,
                "score_setor_2022_calibrado": pd.NA,
                "score_expansao_hibrido": 99.0,
                "rank_brasil": 10,
                "rank_uf": 1,
                "rank_municipio_uf": 1,
                "rank_municipio_brasil": 10,
                "rank_hex_intraurbano": pd.NA,
                "top_municipio": True,
                "top_hex_intraurbano": False,
                "flag_hex_hibrido_elegivel": False,
                "qualidade_join_uf": "C",
                "flag_outlier_espacial": False,
                "flag_baixa_pop_setor": False,
                "flag_join_uf_restrito": True,
            },
            {
                "hex_id": "ce_fallback2",
                "uf": "CE",
                "nome_municipio": "Fortaleza",
                "cod_municipio": 2304400,
                "score_priorizacao": 99.0,
                "score_priorizacao_municipio": 99.0,
                "score_setor_2022_calibrado": pd.NA,
                "score_expansao_hibrido": 99.0,
                "rank_brasil": 11,
                "rank_uf": 2,
                "rank_municipio_uf": 1,
                "rank_municipio_brasil": 10,
                "rank_hex_intraurbano": pd.NA,
                "top_municipio": True,
                "top_hex_intraurbano": False,
                "flag_hex_hibrido_elegivel": False,
                "qualidade_join_uf": "C",
                "flag_outlier_espacial": False,
                "flag_baixa_pop_setor": False,
                "flag_join_uf_restrito": True,
            },
        ]
    ).to_parquet(input_path, index=False)
    mercado_path = root / "hexagonos_mercado_mapeado.parquet"
    pd.DataFrame(
        [
            {
                "hex_id": "sp_top1",
                "sam_fitness_potencial": 900.0,
                "oferta_consumida_mercado_estimada": 250.0,
                "oferta_consumida_ultra_real": 80.0,
                "oferta_efetiva_disponivel": 650.0,
                "share_ultra_estimado_hex": 0.24,
                "score_oportunidade_residual": 26.0,
            },
            {
                "hex_id": "sp_top2",
                "sam_fitness_potencial": 800.0,
                "oferta_consumida_mercado_estimada": 200.0,
                "oferta_consumida_ultra_real": 0.0,
                "oferta_efetiva_disponivel": 600.0,
                "share_ultra_estimado_hex": 0.0,
                "score_oportunidade_residual": 24.0,
            },
            {
                "hex_id": "ce_fallback1",
                "sam_fitness_potencial": 1200.0,
                "oferta_consumida_mercado_estimada": 100.0,
                "oferta_consumida_ultra_real": 0.0,
                "oferta_efetiva_disponivel": 1100.0,
                "share_ultra_estimado_hex": 0.0,
                "score_oportunidade_residual": 44.0,
            },
            {
                "hex_id": "ce_fallback2",
                "sam_fitness_potencial": 600.0,
                "oferta_consumida_mercado_estimada": 100.0,
                "oferta_consumida_ultra_real": 0.0,
                "oferta_efetiva_disponivel": 500.0,
                "share_ultra_estimado_hex": 0.0,
                "score_oportunidade_residual": 20.0,
            },
        ]
    ).to_parquet(mercado_path, index=False)

    monkeypatch.setattr(gerar_carteira_acionavel, "INPUT_PATH", input_path)
    monkeypatch.setattr(gerar_carteira_acionavel, "MERCADO_PATH", mercado_path)

    carteira = gerar_carteira_acionavel.gerar_carteira()

    assert carteira["hex_id"].tolist() == [
        "ce_fallback1",
        "ce_fallback2",
        "sp_top1",
        "sp_top2",
    ]
    assert carteira["uf"].nunique() == 2
    assert "sp_descartado_sem_top_hex" not in carteira["hex_id"].tolist()
    assert carteira.loc[carteira["uf"] == "CE", "modo_selecao_carteira"].eq(
        "fallback_municipal_m1"
    ).all()
    assert carteira.loc[carteira["uf"] == "SP", "modo_selecao_carteira"].eq(
        "granular_censitario"
    ).all()
    assert carteira["rank_carteira_brasil"].tolist() == [1, 2, 3, 4]
    assert "oferta_efetiva_disponivel" in carteira.columns
    assert carteira.loc[
        carteira["hex_id"] == "ce_fallback1", "oferta_efetiva_disponivel"
    ].iat[0] == 1100.0
    assert carteira.loc[
        carteira["hex_id"] == "ce_fallback1", "quartil_oportunidade_residual"
    ].iat[0] == "Q4_maior_residual"
    assert "Fallback municipal/M1" in carteira.loc[
        carteira["hex_id"] == "ce_fallback1", "motivo_priorizacao"
    ].iat[0]


def test_gerar_plano_mantem_cobertura_uf_via_top10_por_uf(monkeypatch):
    root = _local_test_dir("plano")
    entrada = root / "carteira_expansao_acionavel.parquet"
    saida_parquet = root / "plano_expansao_curto_prazo.parquet"
    saida_csv = root / "plano_expansao_curto_prazo.csv"

    rows = []
    rank = 1
    for uf, total in [("SP", 25), ("RJ", 25), ("CE", 10)]:
        for rank_uf in range(1, total + 1):
            rows.append(
                {
                    "hex_id": f"{uf.lower()}_{rank_uf}",
                    "uf": uf,
                    "nome_municipio": f"Municipio {uf}",
                    "cod_municipio": 100000 + rank,
                    "rank_carteira_brasil": rank,
                    "rank_carteira_uf": rank_uf,
                    "score_expansao_hibrido": 100.0 - rank_uf / 100,
                    "score_priorizacao": 100.0 - rank / 100,
                    "score_setor_2022_calibrado": 80.0 if uf != "CE" else pd.NA,
                    "qualidade_join_uf": "A" if uf != "CE" else "C",
                    "modo_selecao_carteira": "granular_censitario"
                    if uf != "CE"
                    else "fallback_municipal_m1",
                    "flag_outlier_espacial": False,
                    "flag_baixa_pop_setor": False,
                    "sam_fitness_potencial": 1000.0 + rank,
                    "oferta_efetiva_disponivel": 500.0 + rank,
                    "score_oportunidade_residual": 20.0,
                    "share_ultra_estimado_hex": 0.1,
                    "oferta_consumida_mercado_estimada": 100.0,
                    "oferta_consumida_ultra_real": 10.0,
                }
            )
            rank += 1

    pd.DataFrame(rows).to_parquet(entrada, index=False)

    monkeypatch.setattr(gerar_plano_expansao_curto_prazo, "ENTRADA", entrada)
    monkeypatch.setattr(gerar_plano_expansao_curto_prazo, "SAIDA_PARQUET", saida_parquet)
    monkeypatch.setattr(gerar_plano_expansao_curto_prazo, "SAIDA_CSV", saida_csv)

    plano = gerar_plano_expansao_curto_prazo.gerar_plano()

    assert len(plano) == 60
    assert plano["hex_id"].is_unique
    assert plano["uf"].nunique() == 3
    assert set(plano["uf"]) == {"SP", "RJ", "CE"}
    assert (plano.loc[plano["uf"] == "CE", "nivel_prioridade_final"] == "Tatica").all()
    assert "Fallback M1" in plano.loc[plano["uf"] == "CE", "motivo_priorizacao"].iat[0]
    assert "oferta_efetiva_disponivel" in plano.columns
    assert plano["score_priorizacao"].notna().all()
    assert saida_parquet.exists()
    assert saida_csv.exists()


def test_enriquecer_outputs_residual_preserva_score_e_ranks():
    base = pd.DataFrame(
        {
            "hex_id": ["h1", "h2"],
            "score_priorizacao": [95.0, 80.0],
            "rank_brasil": [1, 2],
            "rank_carteira_brasil": [1, 2],
        }
    )
    mercado = pd.DataFrame(
        {
            "hex_id": ["h1", "h2"],
            "sam_fitness_potencial": [1000.0, 900.0],
            "oferta_consumida_mercado_estimada": [250.0, 500.0],
            "oferta_consumida_ultra_real": [100.0, 0.0],
            "oferta_efetiva_disponivel": [750.0, 400.0],
            "share_ultra_estimado_hex": [0.29, 0.0],
            "score_oportunidade_residual": [30.0, 16.0],
            "quartil_oportunidade_residual": ["Q4_maior_residual", "Q1_menor_residual"],
        }
    )

    enriched = enriquecer_outputs_residual_mercado.enriquecer_dataframe_com_residual(base, mercado)

    assert enriched["score_priorizacao"].tolist() == [95.0, 80.0]
    assert enriched["rank_brasil"].tolist() == [1, 2]
    assert enriched["rank_carteira_brasil"].tolist() == [1, 2]
    assert enriched["oferta_efetiva_disponivel"].tolist() == [750.0, 400.0]
