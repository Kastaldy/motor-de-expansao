"""Testes unitarios do backtest de scores (BLK-SCORE-02).

APENAS fixtures sinteticas em memoria (jamais o parquet real gitignored; o CI
nao tem as fontes). Cobre as funcoes puras de calculo do plano (secao 5 do
handoff). READ-ONLY: estes testes nao tocam nenhum artefato do M1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from analysis import score_backtest as sb


# --------------------------------------------------------------------------- #
# correlate
# --------------------------------------------------------------------------- #
def test_correlate_monotonica_positiva():
    x = pd.Series(range(20))
    y = pd.Series([v * 2 for v in range(20)])  # monotonica perfeita
    res = sb.correlate(x, y)
    assert res["suficiente"] is True
    assert res["n"] == 20
    assert res["spearman_rho"] == 1.0
    assert res["spearman_p"] < 0.05
    assert res["pearson_r"] > 0.99


def test_correlate_monotonica_inversa():
    x = pd.Series(range(20))
    y = pd.Series([-(v) for v in range(20)])
    res = sb.correlate(x, y)
    assert res["spearman_rho"] == -1.0
    assert res["suficiente"] is True


def test_correlate_n_abaixo_do_piso():
    x = pd.Series(range(5))
    y = pd.Series(range(5))
    res = sb.correlate(x, y)  # N=5 < N_MIN=10
    assert res["suficiente"] is False
    assert res["spearman_rho"] is None
    assert res["pearson_r"] is None
    assert res["n"] == 5
    assert "insuficiente" in (res["motivo"] or "")


def test_correlate_serie_constante_nao_quebra():
    x = pd.Series([5.0] * 15)  # variancia zero
    y = pd.Series(range(15))
    res = sb.correlate(x, y)
    assert res["suficiente"] is False
    assert res["spearman_rho"] is None
    assert res["motivo"] == "variancia_zero"


# --------------------------------------------------------------------------- #
# pairwise_valid
# --------------------------------------------------------------------------- #
def test_pairwise_valid_descarta_nulos():
    df = pd.DataFrame(
        {
            "score_x": [1.0, None, 3.0, 4.0],
            "alunos_recorrentes": [10.0, 20.0, None, 40.0],
        }
    )
    out = sb.pairwise_valid(df, "score_x")
    # so linhas 0 e 3 tem ambos nao-nulos
    assert len(out) == 2
    assert out["score_x"].tolist() == [1.0, 4.0]


def test_pairwise_valid_coluna_ausente():
    df = pd.DataFrame({"alunos_recorrentes": [1.0, 2.0]})
    out = sb.pairwise_valid(df, "inexistente")
    assert out.empty


# --------------------------------------------------------------------------- #
# correlate_by_cell
# --------------------------------------------------------------------------- #
def test_correlate_by_cell_agg_e_por_rede():
    rng = np.random.default_rng(0)
    n = 60
    df = pd.DataFrame(
        {
            "rede": (["ultra"] * 20 + ["skyfit"] * 35 + ["engcorpo"] * 5),
            "score_x": rng.normal(size=n),
            "alunos_recorrentes": rng.normal(size=n),
        }
    )
    results = sb.correlate_by_cell(df, "score_x")
    celulas = {r["celula"] for r in results}
    assert "AGG" in celulas
    assert "ultra" in celulas and "skyfit" in celulas and "engcorpo" in celulas
    # engcorpo N=5 < 10 -> insuficiente
    eng = next(r for r in results if r["celula"] == "engcorpo")
    assert eng["suficiente"] is False
    assert eng["n"] == 5
    # AGG marcado com o score
    agg = next(r for r in results if r["celula"] == "AGG")
    assert agg["score"] == "score_x"
    assert agg["n"] == 60


# --------------------------------------------------------------------------- #
# join_componentes
# --------------------------------------------------------------------------- #
def test_join_componentes_match_rate_e_nao_sobrescreve():
    dataset = pd.DataFrame(
        {
            "hex_id": ["HEXA", "HEXB", "HEXC", None],
            "alunos_recorrentes": [100.0, 200.0, 300.0, 400.0],
        }
    )
    prio = pd.DataFrame(
        {
            "hex_id": ["HEXA", "HEXC"],
            "renda_pct_nacional": [0.8, 0.5],
            "pop_pct_nacional": [0.9, 0.4],
        }
    )
    merged, stats = sb.join_componentes(dataset, prio)
    # 3 linhas tem hex; 2 casaram (HEXA, HEXC)
    assert stats["linhas_com_hex"] == 3
    assert stats["casadas"] == 2
    assert stats["match_rate_pct"] == round(100.0 * 2 / 3, 1)
    # componentes adicionados; HEXB (sem match) fica NaN
    by_hex = merged.set_index("hex_id")
    assert by_hex.loc["HEXA", "renda_pct_nacional"] == 0.8
    assert pd.isna(by_hex.loc["HEXB", "renda_pct_nacional"])
    # coluna de desfecho original intacta (nao sobrescrita)
    assert merged["alunos_recorrentes"].tolist() == [100.0, 200.0, 300.0, 400.0]


def test_join_componentes_nao_sobrescreve_coluna_existente():
    # se o dataset ja trouxesse o componente, o do join vem sufixado _prio
    dataset = pd.DataFrame(
        {
            "hex_id": ["HEXA"],
            "renda_pct_nacional": [0.1],  # valor original do dataset
            "pop_pct_nacional": [0.2],
            "alunos_recorrentes": [100.0],
        }
    )
    prio = pd.DataFrame(
        {"hex_id": ["HEXA"], "renda_pct_nacional": [0.9], "pop_pct_nacional": [0.8]}
    )
    merged, stats = sb.join_componentes(dataset, prio)
    # coluna original preservada
    assert merged["renda_pct_nacional"].iloc[0] == 0.1
    # o join aponta para a coluna sufixada
    assert stats["comp_renda_col"] == "renda_pct_nacional_prio"
    assert merged["renda_pct_nacional_prio"].iloc[0] == 0.9


# --------------------------------------------------------------------------- #
# decompor_renda_pop
# --------------------------------------------------------------------------- #
def test_decompor_renda_pop_estrutura():
    rng = np.random.default_rng(1)
    n = 40
    dataset = pd.DataFrame(
        {
            "hex_id": [f"HEX{i}" for i in range(n)],
            "rede": ["skyfit"] * n,
            "score_priorizacao": rng.normal(size=n),
            "alunos_recorrentes": rng.normal(size=n),
        }
    )
    prio = pd.DataFrame(
        {
            "hex_id": [f"HEX{i}" for i in range(n)],
            "renda_pct_nacional": rng.random(n),
            "pop_pct_nacional": rng.random(n),
        }
    )
    merged, stats = sb.join_componentes(dataset, prio)
    dec = sb.decompor_renda_pop(merged, renda_col=stats["comp_renda_col"], pop_col=stats["comp_pop_col"])
    assert "renda" in dec and "pop" in dec and "priorizacao_nas_casadas" in dec
    renda_agg = next(r for r in dec["renda"] if r["celula"] == "AGG")
    assert renda_agg["n"] == n
    assert renda_agg["suficiente"] is True


# --------------------------------------------------------------------------- #
# bootstrap_ci_spearman
# --------------------------------------------------------------------------- #
def test_bootstrap_ci_deterministico():
    rng = np.random.default_rng(7)
    x = pd.Series(rng.normal(size=50))
    y = pd.Series(rng.normal(size=50))
    ci1 = sb.bootstrap_ci_spearman(x, y)
    ci2 = sb.bootstrap_ci_spearman(x, y)
    assert ci1 is not None
    assert ci1 == ci2  # mesma seed -> mesmo IC
    assert ci1[0] <= ci1[1]


def test_bootstrap_ci_none_para_n_pequeno():
    x = pd.Series(range(20))  # N=20 < 30
    y = pd.Series(range(20))
    assert sb.bootstrap_ci_spearman(x, y) is None


# --------------------------------------------------------------------------- #
# find_outliers
# --------------------------------------------------------------------------- #
def test_find_outliers_caso_obvio_e_sem_pii():
    # 1 unidade com score altissimo e outcome baixissimo + base ruidosa
    n = 30
    df = pd.DataFrame(
        {
            "rede": ["skyfit"] * (n + 1),
            "uf": ["SP"] * (n + 1),
            "nome_municipio": ["Cidade"] * (n + 1),
            "nome_unidade": [f"Skyfit {i}" for i in range(n + 1)],  # PII — NAO deve vazar
            "hex_id": [f"HEX{i}" for i in range(n + 1)],
            "hex_precisao": ["unidade"] * (n + 1),
            "rotulo_confiabilidade": ["medido"] * (n + 1),
            # base: score == outcome (sem discrepancia); ultimo: score alto, outcome baixo
            "score_x": list(range(n)) + [999.0],
            "alunos_recorrentes": list(range(n)) + [0.0],
        }
    )
    out = sb.find_outliers(df, "score_x")
    hi = out["alto_score_baixo_outcome"]
    assert len(hi) >= 1
    caso = hi[0]
    # NUNCA expor nome_unidade (anti-PII)
    assert "nome_unidade" not in caso
    # chaves anonimizadas esperadas presentes
    for key in ("rede", "uf", "nome_municipio", "hex_id", "hex_precisao", "rotulo_confiabilidade", "hipotese"):
        assert key in caso
    assert caso["score_pct_within_rede"] >= 0.7
    assert caso["outcome_pct_within_rede"] <= 0.3


# --------------------------------------------------------------------------- #
# build_report (smoke)
# --------------------------------------------------------------------------- #
def test_build_report_contem_secoes_e_limitacoes():
    por_score = {s: sb.correlate_by_cell(
        pd.DataFrame(
            {
                "rede": ["skyfit"] * 20,
                s: list(range(20)),
                "alunos_recorrentes": list(range(20)),
            }
        ),
        s,
    ) for s in sb.SCORES}
    decomposicao = {"renda": [], "pop": [], "priorizacao_nas_casadas": []}
    match_stats = {"casadas": 10, "linhas_com_hex": 12, "match_rate_pct": 83.3,
                   "comp_renda_col": "renda_pct_nacional", "comp_pop_col": "pop_pct_nacional"}
    outliers = {s: {"alto_score_baixo_outcome": [], "baixo_score_alto_outcome": []} for s in sb.SCORES}
    report = sb.build_report(
        n_total=441,
        por_score=por_score,
        decomposicao=decomposicao,
        match_stats=match_stats,
        outliers_por_score=outliers,
        conf_counts={"medido": 380, "estimado": 61},
    )
    assert isinstance(report, str)
    assert "(a)" in report
    assert "(b)" in report
    assert "(c)" in report
    assert "Limitacoes" in report
    assert "maturacao" in report.lower()
    # sem proposta de peso
    assert "BLK-SCORE-03" in report


def test_build_report_nao_vaza_pii_de_outlier():
    outliers = {
        "score_priorizacao": {
            "alto_score_baixo_outcome": [
                {
                    "rede": "skyfit",
                    "uf": "SP",
                    "nome_municipio": "Cidade",
                    "hex_id": "HEXZ",
                    "hex_precisao": "unidade",
                    "rotulo_confiabilidade": "medido",
                    "score_pct_within_rede": 0.95,
                    "outcome_pct_within_rede": 0.05,
                    "score_valor": 99.0,
                    "outcome_valor": 10.0,
                    "hipotese": "teste",
                }
            ],
            "baixo_score_alto_outcome": [],
        }
    }
    outliers.update({s: {"alto_score_baixo_outcome": [], "baixo_score_alto_outcome": []} for s in sb.SCORES if s not in outliers})
    report = sb.build_report(
        n_total=10,
        por_score={s: [] for s in sb.SCORES},
        decomposicao={"renda": [], "pop": [], "priorizacao_nas_casadas": []},
        match_stats={"casadas": 0, "linhas_com_hex": 0, "match_rate_pct": 0.0,
                     "comp_renda_col": "renda_pct_nacional", "comp_pop_col": "pop_pct_nacional"},
        outliers_por_score=outliers,
        conf_counts={},
    )
    assert "HEXZ" in report  # o hex_id e exposto
    # o nome real da unidade (PII) NUNCA aparece no corpo do relatorio;
    # 'nome_unidade' como termo so e citado na nota de guardrail do cabecalho.
    assert "Skyfit Unidade Secreta" not in report
