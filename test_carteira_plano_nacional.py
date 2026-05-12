from pathlib import Path

import pandas as pd

from jobs.pipelines import gerar_carteira_acionavel, gerar_plano_expansao_curto_prazo


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

    monkeypatch.setattr(gerar_carteira_acionavel, "INPUT_PATH", input_path)

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
    assert saida_parquet.exists()
    assert saida_csv.exists()
