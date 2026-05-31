"""Testes unitarios do backtest de features mercado/censitarias (BLK-SCORE-04).

APENAS fixtures sinteticas em memoria (jamais o parquet real gitignored; o CI
nao tem as fontes). Cobre as funcoes puras do plano. READ-ONLY: estes testes
nao tocam nenhum artefato do M1 nem leem os parquets reais.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from analysis import feature_backtest_mercado as fb


# --------------------------------------------------------------------------- #
# join_features — taxa de match
# --------------------------------------------------------------------------- #
def test_join_features_match_rate():
    dataset = pd.DataFrame(
        {
            "hex_id": ["HEXA", "HEXB", "HEXC", None],
            "rede": ["ultra", "skyfit", "ultra", "skyfit"],
            "score_setor_2022_calibrado": [50.0, 60.0, 70.0, 80.0],
            "alunos_recorrentes": [100.0, 200.0, 300.0, 400.0],
        }
    )
    # mercado casa HEXA e HEXC; HEXB fica sem match.
    mercado = pd.DataFrame(
        {
            "hex_id": ["HEXA", "HEXC", "HEXZ"],
            "n_concorrentes_mapeados_2km": [3.0, 1.0, 9.0],
            "densidade_pop_setor_hab_km2": [1000.0, 2000.0, 3000.0],
        }
    )
    merged, stats = fb.join_features(dataset, mercado)
    # 3 linhas com hex; 2 casaram (HEXA, HEXC) via pivo
    assert stats["linhas_com_hex"] == 3
    assert stats["casadas"] == 2
    assert stats["match_rate_pct"] == round(100.0 * 2 / 3, 1)
    assert stats["pivo_match"] == "n_concorrentes_mapeados_2km"
    # HEXB sem match -> feature NaN
    by_hex = merged.set_index("hex_id")
    assert by_hex.loc["HEXA", "n_concorrentes_mapeados_2km"] == 3.0
    assert pd.isna(by_hex.loc["HEXB", "n_concorrentes_mapeados_2km"])


# --------------------------------------------------------------------------- #
# join_features — ancora do dataset nao sobrescrita
# --------------------------------------------------------------------------- #
def test_join_features_ancora_do_dataset_nao_sobrescrita():
    dataset = pd.DataFrame(
        {
            "hex_id": ["HEXA"],
            "rede": ["ultra"],
            "score_setor_2022_calibrado": [11.0],  # valor do DATASET (ancora)
            "alunos_recorrentes": [100.0],
        }
    )
    # mercado traz a MESMA coluna com OUTRO valor -> deve virar *_merc.
    mercado = pd.DataFrame(
        {
            "hex_id": ["HEXA"],
            "score_setor_2022_calibrado": [99.0],
            "n_concorrentes_mapeados_2km": [2.0],
        }
    )
    merged, stats = fb.join_features(dataset, mercado)
    # ancora (sem sufixo) mantem o valor do DATASET
    assert merged["score_setor_2022_calibrado"].iloc[0] == 11.0
    # match_stats aponta a ancora correta e a origem
    assert stats["ancora_col"] == "score_setor_2022_calibrado"
    assert stats["ancora_origem"] == "dataset_validacao"
    # join_features so traz features de mercado != ancora -> nao ha _merc
    # (a ancora do mercado e excluida da selecao de colunas, por design).
    assert "score_setor_2022_calibrado_merc" not in merged.columns


# --------------------------------------------------------------------------- #
# variancia-zero -> indefinido
# --------------------------------------------------------------------------- #
def test_feature_variancia_zero_marca_indefinido():
    n = 15
    df = pd.DataFrame(
        {
            "rede": ["skyfit"] * n,
            "n_unidades_ultra_2km": [4.0] * n,  # constante -> variancia zero
            "alunos_recorrentes": list(range(n)),
        }
    )
    results = fb.correlate_by_cell(df, "n_unidades_ultra_2km")
    agg = next(r for r in results if r["celula"] == "AGG")
    assert agg["suficiente"] is False
    assert agg["motivo"] == "variancia_zero"
    # e o markdown da linha mostra o motivo (nao inventa rho)
    row = fb._cell_row_md(agg)
    assert "variancia_zero" in row


# --------------------------------------------------------------------------- #
# ranking por |rho|
# --------------------------------------------------------------------------- #
def test_ranking_agg_abs_ordena_por_magnitude():
    def _agg(rho: float | None, *, suf: bool = True) -> list[dict]:
        return [
            {
                "celula": "AGG",
                "n": 100,
                "spearman_rho": rho,
                "suficiente": suf,
                "motivo": None,
            }
        ]

    por_feature = {
        "feat_pos_pequeno": _agg(0.10),
        "feat_neg_grande": _agg(-0.40),
        "feat_pos_medio": _agg(0.20),
        "feat_indef": _agg(None, suf=False),
    }
    ranking = fb.ranking_agg_abs(por_feature)
    # ordem por |rho| DESC: 0.40, 0.20, 0.10; indefinida fora.
    assert [f for f, _ in ranking] == [
        "feat_neg_grande",
        "feat_pos_medio",
        "feat_pos_pequeno",
    ]
    assert ranking[0][1] == -0.40  # mantem o sinal cru, ordena por magnitude


# --------------------------------------------------------------------------- #
# OLS — estrutura e pureza
# --------------------------------------------------------------------------- #
def test_ols_diagnostico_estrutura_e_nao_persiste(tmp_path):
    rng = np.random.default_rng(3)
    n = 120
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    x3 = rng.normal(size=n)
    x4 = rng.normal(size=n)
    # outcome dirigido por +x1 forte (sinal conhecido) + ruido
    y = 3.0 * x1 - 1.0 * x2 + 0.2 * rng.normal(size=n)
    df = pd.DataFrame(
        {
            "score_setor_2022_calibrado": x1,
            "pressao_concorrencial_score_2km": x2,
            "densidade_pop_setor_hab_km2": x3,
            "dist_concorrente_mais_proximo_m": x4,
            "alunos_recorrentes": y,
        }
    )
    res = fb.ols_diagnostico(df)
    assert res["n"] == n
    assert res["r2"] is not None and 0.0 <= res["r2"] <= 1.0
    # um beta por regressor presente
    assert set(res["coefs"]) == set(fb.OLS_REGRESSORS)
    # sinal conhecido: x1 (+) maior que x2 (-)
    assert res["coefs"]["score_setor_2022_calibrado"] > 0
    assert res["coefs"]["pressao_concorrencial_score_2km"] < 0
    # pureza: a funcao nao escreve arquivo algum
    before = set(p.name for p in tmp_path.iterdir())
    fb.ols_diagnostico(df)
    after = set(p.name for p in tmp_path.iterdir())
    assert before == after


# --------------------------------------------------------------------------- #
# build_feature_report — secoes + anti-PII
# --------------------------------------------------------------------------- #
def test_build_feature_report_secoes_e_sem_pii():
    n = 30
    df = pd.DataFrame(
        {
            "rede": ["skyfit"] * n,
            "score_setor_2022_calibrado": list(range(n)),
            "alunos_recorrentes": list(range(n)),
            # PII ficticia: NUNCA deve vazar para o relatorio
            "nome_unidade": [f"Academia Secreta {i}" for i in range(n)],
        }
    )
    por_feature = {f: fb.correlate_by_cell(df, f) for f in fb.FEATURES if f in df.columns}
    # completar features ausentes com listas vazias (smoke)
    for f in fb.FEATURES:
        por_feature.setdefault(f, [])
    boot_agg = {f: None for f in fb.FEATURES}
    match_stats = {
        "linhas_com_hex": 30,
        "casadas": 29,
        "match_rate_pct": 96.7,
        "pivo_match": "n_concorrentes_mapeados_2km",
        "ancora_col": "score_setor_2022_calibrado",
        "ancora_origem": "dataset_validacao",
        "n_features": 12,
    }
    ranking = fb.ranking_agg_abs(por_feature)
    ols = {
        "n": 30,
        "r2": 0.42,
        "coefs": {"score_setor_2022_calibrado": 0.5},
        "intercepto": 0.0,
        "cond": 1.2,
        "nota_instabilidade": "ok",
        "regressors": list(fb.OLS_REGRESSORS),
    }
    report = fb.build_feature_report(
        n_total=441,
        por_feature=por_feature,
        boot_agg=boot_agg,
        match_stats=match_stats,
        ranking=ranking,
        ols=ols,
    )
    assert isinstance(report, str)
    assert "match" in report.lower()
    assert "Ranking" in report
    assert "Limitacoes" in report
    assert "BLK-SCORE-02" in report  # heranca das limitacoes
    # anti-PII: o VALOR do nome de unidade (PII) nunca vaza para o corpo do
    # relatorio. O termo 'nome_unidade' so e citado na nota de guardrail do
    # cabecalho (mesma convencao do teste do BLK-SCORE-02).
    assert "Academia Secreta" not in report


# --------------------------------------------------------------------------- #
# build_feature_report — marca indefinido
# --------------------------------------------------------------------------- #
def test_build_feature_report_marca_indefinido():
    # uma feature com motivo variancia_zero deve aparecer como indefinido no md.
    por_feature = {f: [] for f in fb.FEATURES}
    por_feature["n_unidades_ultra_2km"] = [
        {
            "celula": "AGG",
            "n": 50,
            "spearman_rho": None,
            "spearman_p": None,
            "pearson_r": None,
            "pearson_p": None,
            "suficiente": False,
            "motivo": "variancia_zero",
            "score": "n_unidades_ultra_2km",
        }
    ]
    boot_agg = {f: None for f in fb.FEATURES}
    match_stats = {
        "linhas_com_hex": 1,
        "casadas": 1,
        "match_rate_pct": 100.0,
        "pivo_match": "n_concorrentes_mapeados_2km",
        "ancora_col": "score_setor_2022_calibrado",
        "ancora_origem": "dataset_validacao",
        "n_features": 12,
    }
    ols = {
        "n": 0,
        "r2": None,
        "coefs": {},
        "intercepto": None,
        "cond": None,
        "nota_instabilidade": "regressores/outcome ausentes",
        "regressors": [],
    }
    report = fb.build_feature_report(
        n_total=441,
        por_feature=por_feature,
        boot_agg=boot_agg,
        match_stats=match_stats,
        ranking=[],
        ols=ols,
    )
    # a feature constante aparece marcada com o motivo (nao inventa rho)
    assert "variancia_zero" in report
    # R2 indefinido nao quebra a renderizacao
    assert "indefinido" in report.lower()
