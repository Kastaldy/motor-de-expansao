"""Backtest do poder preditivo dos scores vs. desfecho (BLK-SCORE-02).

Mede, READ-ONLY, quanto cada um dos 4 scores do projeto
(M1 ``score_priorizacao``, censitario ``score_setor_2022_calibrado``,
residual ``score_oportunidade_residual``, dominio ``score_dominio_hibrido``)
correlaciona com o desfecho observado ``alunos_recorrentes`` no dataset rotulado
(``data/analysis/dataset_validacao.parquet``), por rede e no agregado; decompoe o
M1 em renda x pop (correlacao isolada de cada componente, via join read-only com
``data/staging/brasil_priorizados.parquet``); identifica casos score-alto x
desfecho-baixo (e o inverso); e gera ``data/analysis/relatorio_backtest.md``.

READ-ONLY sobre o M1: NAO recalcula nenhum score, NAO altera pesos/formula
(0.40/0.60), ``scoring.py``, ``constants.py`` ou qualquer artefato oficial /
``data/outputs/``. Saida SO em ``data/analysis/`` (gitignored). Analise
DESCRITIVA; nenhuma proposta de mudanca de peso/formula (isso e BLK-SCORE-03).

Execucao::

    python analysis/score_backtest.py

Gera:
    data/analysis/relatorio_backtest.md  (gitignored; apenas agregados, sem PII)
    data/analysis/fig_*.png              (OPCIONAIS; gitignored; sob try/except)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

# --------------------------------------------------------------------------- #
# Constantes / contrato de colunas
# --------------------------------------------------------------------------- #
REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET_PARQUET = REPO_ROOT / "data" / "analysis" / "dataset_validacao.parquet"
PRIORIZADOS_PARQUET = REPO_ROOT / "data" / "staging" / "brasil_priorizados.parquet"
OUT_REPORT = REPO_ROOT / "data" / "analysis" / "relatorio_backtest.md"
FIG_DIR = REPO_ROOT / "data" / "analysis"

OUTCOME = "alunos_recorrentes"

# scores oficiais/paralelos avaliados (ordem canonica) + rotulos legiveis.
SCORES: tuple[str, ...] = (
    "score_priorizacao",
    "score_setor_2022_calibrado",
    "score_oportunidade_residual",
    "score_dominio_hibrido",
)
SCORE_LABELS: dict[str, str] = {
    "score_priorizacao": "priorizacao (M1)",
    "score_setor_2022_calibrado": "setor_2022_calibrado (censitario)",
    "score_oportunidade_residual": "oportunidade_residual (residual)",
    "score_dominio_hibrido": "dominio_hibrido (dominio)",
}

# componentes do M1 — vem SO do join read-only com priorizados.
COMPONENTES: tuple[str, ...] = ("renda_pct_nacional", "pop_pct_nacional")

REDES: tuple[str, ...] = ("ultra", "skyfit", "engcorpo")

N_MIN = 10
SEED = 42
N_BOOT = 2000


# --------------------------------------------------------------------------- #
# Funcoes puras de calculo (testaveis; nao leem disco)
# --------------------------------------------------------------------------- #
def pairwise_valid(
    df: pd.DataFrame, score_col: str, outcome_col: str = OUTCOME
) -> pd.DataFrame:
    """Sub-DataFrame com linhas onde score E outcome sao ambos nao-nulos.

    Coerce numerico defensivo (``errors='coerce'``); nao muta a entrada.
    """
    out = df.copy()
    if score_col not in out.columns or outcome_col not in out.columns:
        return out.iloc[0:0]
    s = pd.to_numeric(out[score_col], errors="coerce")
    y = pd.to_numeric(out[outcome_col], errors="coerce")
    mask = s.notna() & y.notna()
    return out.loc[mask].copy()


def correlate(x: pd.Series, y: pd.Series, *, n_min: int = N_MIN) -> dict:
    """Spearman + Pearson de ``x`` vs ``y`` com tratamento de N pequeno / variancia zero.

    Retorna dict com chaves estaveis. Se ``n < n_min`` -> ``suficiente=False`` e
    coefs/p = None (nao chama scipy). Se ``n >= n_min`` mas alguma serie e
    constante (variancia zero) -> coefs = None com ``motivo='variancia_zero'``
    (scipy retornaria nan; tratado aqui sem quebrar).
    """
    xs = pd.to_numeric(pd.Series(x).reset_index(drop=True), errors="coerce")
    ys = pd.to_numeric(pd.Series(y).reset_index(drop=True), errors="coerce")
    mask = xs.notna() & ys.notna()
    xs = xs[mask]
    ys = ys[mask]
    n = int(len(xs))

    base: dict = {
        "n": n,
        "spearman_rho": None,
        "spearman_p": None,
        "pearson_r": None,
        "pearson_p": None,
        "suficiente": False,
        "motivo": None,
    }

    if n < n_min:
        base["motivo"] = f"N insuficiente (N={n} < {n_min})"
        return base

    if xs.nunique() < 2 or ys.nunique() < 2:
        base["suficiente"] = False
        base["motivo"] = "variancia_zero"
        return base

    sp = stats.spearmanr(xs, ys)
    pe = stats.pearsonr(xs, ys)
    sp_rho = float(sp.statistic) if hasattr(sp, "statistic") else float(sp[0])
    sp_p = float(sp.pvalue) if hasattr(sp, "pvalue") else float(sp[1])
    pe_r = float(pe.statistic) if hasattr(pe, "statistic") else float(pe[0])
    pe_p = float(pe.pvalue) if hasattr(pe, "pvalue") else float(pe[1])

    # defesa extra: scipy pode devolver nan em casos degenerados.
    if any(np.isnan(v) for v in (sp_rho, sp_p, pe_r, pe_p)):
        base["suficiente"] = False
        base["motivo"] = "variancia_zero"
        return base

    base.update(
        {
            "spearman_rho": sp_rho,
            "spearman_p": sp_p,
            "pearson_r": pe_r,
            "pearson_p": pe_p,
            "suficiente": True,
            "motivo": None,
        }
    )
    return base


def correlate_by_cell(
    df: pd.DataFrame,
    score_col: str,
    *,
    by: str | None = "rede",
    outcome_col: str = OUTCOME,
    n_min: int = N_MIN,
) -> list[dict]:
    """Aplica ``correlate`` no agregado (celula 'AGG') e por valor de ``by``.

    Cada item leva ``{'celula': <'AGG'|valor>, 'score': score_col}`` alem das
    chaves de ``correlate``. Usa apenas linhas com score E outcome validos
    (``pairwise_valid``). Para ``by`` ausente, so devolve a celula AGG.
    """
    valid = pairwise_valid(df, score_col, outcome_col)
    results: list[dict] = []

    agg = correlate(valid[score_col], valid[outcome_col], n_min=n_min)
    agg.update({"celula": "AGG", "score": score_col})
    results.append(agg)

    if by is not None and by in valid.columns:
        for cell in REDES:
            sub = valid[valid[by] == cell]
            res = correlate(sub[score_col], sub[outcome_col], n_min=n_min)
            res.update({"celula": cell, "score": score_col})
            results.append(res)
    return results


def bootstrap_ci_spearman(
    x: pd.Series,
    y: pd.Series,
    *,
    n_boot: int = N_BOOT,
    seed: int = SEED,
) -> tuple[float, float] | None:
    """IC percentil 2.5/97.5 do Spearman por reamostragem (seed 42).

    Retorna None se N < 30 (nao aplicar a celulas pequenas) ou se nao houver
    variancia suficiente. Deterministico pelo seed.
    """
    xs = pd.to_numeric(pd.Series(x).reset_index(drop=True), errors="coerce")
    ys = pd.to_numeric(pd.Series(y).reset_index(drop=True), errors="coerce")
    mask = xs.notna() & ys.notna()
    xs = xs[mask].to_numpy()
    ys = ys[mask].to_numpy()
    n = len(xs)
    if n < 30:
        return None
    if np.unique(xs).size < 2 or np.unique(ys).size < 2:
        return None

    rng = np.random.default_rng(seed)
    rhos: list[float] = []
    idx_all = np.arange(n)
    for _ in range(n_boot):
        idx = rng.choice(idx_all, size=n, replace=True)
        bx = xs[idx]
        by = ys[idx]
        if np.unique(bx).size < 2 or np.unique(by).size < 2:
            continue
        rho = stats.spearmanr(bx, by).statistic
        if not np.isnan(rho):
            rhos.append(float(rho))
    if len(rhos) < 2:
        return None
    lo = float(np.percentile(rhos, 2.5))
    hi = float(np.percentile(rhos, 97.5))
    return (lo, hi)


def join_componentes(
    dataset: pd.DataFrame, priorizados: pd.DataFrame
) -> tuple[pd.DataFrame, dict]:
    """Left-join read-only de ``renda_pct_nacional``/``pop_pct_nacional`` por ``hex_id``.

    Seleciona do priorizados SO ``['hex_id', *COMPONENTES]``; nunca sobrescreve
    colunas do dataset (componentes ja presentes no dataset, se houvesse, ficam
    sufixadas ``_prio``, mas o esquema oficial nao as traz). Retorna
    ``(df_merged, match_stats)`` com taxa de match das linhas que possuem hex_id.
    """
    cols = ["hex_id", *COMPONENTES]
    prio = priorizados[[c for c in cols if c in priorizados.columns]].copy()
    prio = prio.drop_duplicates(subset=["hex_id"], keep="first")

    left = dataset.copy()
    # Se algum componente ja existir no dataset, o do priorizados vira sufixado
    # ``_prio`` (o do join). O esquema oficial do dataset NAO traz estes componentes,
    # mas o guard mantem read-only sem sobrescrever a coluna original.
    overlap = [c for c in COMPONENTES if c in left.columns]
    suffixes = ("", "_prio") if overlap else ("", "")
    merged = left.merge(prio, on="hex_id", how="left", suffixes=suffixes)

    def _joined_col(col: str) -> str:
        suffixed = f"{col}_prio"
        if col in overlap and suffixed in merged.columns:
            return suffixed
        return col

    renda_col = _joined_col(COMPONENTES[0])
    pop_col = _joined_col(COMPONENTES[1])

    tem_hex = left["hex_id"].notna()
    n_com_hex = int(tem_hex.sum())
    # casadas = linhas com hex que receberam componente (renda) nao-nulo do join
    casadas = int(merged.loc[tem_hex.values, renda_col].notna().sum())
    match_rate = round(100.0 * casadas / n_com_hex, 1) if n_com_hex else 0.0

    match_stats = {
        "linhas_com_hex": n_com_hex,
        "casadas": casadas,
        "match_rate_pct": match_rate,
        "comp_renda_col": renda_col,
        "comp_pop_col": pop_col,
    }
    return merged, match_stats


def decompor_renda_pop(
    df_merged: pd.DataFrame,
    *,
    outcome_col: str = OUTCOME,
    n_min: int = N_MIN,
    renda_col: str = "renda_pct_nacional",
    pop_col: str = "pop_pct_nacional",
) -> dict:
    """Correlaciona ISOLADAMENTE renda_pct e pop_pct com o desfecho (agg + rede).

    ACHADO DESCRITIVO. Tambem correlaciona ``score_priorizacao`` nas MESMAS linhas
    casadas (com componente nao-nulo), para contextualizar. PROIBIDO derivar peso.
    """
    # restringe as linhas com componente disponivel (casadas no join)
    base = df_merged.copy()
    if renda_col not in base.columns or pop_col not in base.columns:
        return {"renda": [], "pop": [], "priorizacao_nas_casadas": []}
    casadas = base[base[renda_col].notna() & base[pop_col].notna()].copy()

    out: dict = {"renda": [], "pop": [], "priorizacao_nas_casadas": []}
    out["renda"] = correlate_by_cell(
        casadas.rename(columns={renda_col: "_renda"}), "_renda", outcome_col=outcome_col, n_min=n_min
    )
    out["pop"] = correlate_by_cell(
        casadas.rename(columns={pop_col: "_pop"}), "_pop", outcome_col=outcome_col, n_min=n_min
    )
    if "score_priorizacao" in casadas.columns:
        out["priorizacao_nas_casadas"] = correlate_by_cell(
            casadas, "score_priorizacao", outcome_col=outcome_col, n_min=n_min
        )
    return out


def find_outliers(
    df: pd.DataFrame,
    score_col: str,
    *,
    outcome_col: str = OUTCOME,
    k: int = 3,
    hi: float = 0.7,
    lo: float = 0.3,
) -> dict:
    """Casos score-alto x desfecho-baixo e o inverso, em percentis WITHIN-rede.

    Percentis (`rank(pct=True)`) calculados DENTRO de cada rede (heterogeneidade
    de desfecho). Saida AGREGADA/anonimizada: por linha expoe SO
    ``rede/uf/nome_municipio/hex_id/hex_precisao/rotulo_confiabilidade`` +
    percentis/valores + ``hipotese``. NUNCA expoe ``nome_unidade`` (PII).
    """
    valid = pairwise_valid(df, score_col, outcome_col)
    if valid.empty:
        return {"alto_score_baixo_outcome": [], "baixo_score_alto_outcome": []}

    valid = valid.copy()
    valid["_score_num"] = pd.to_numeric(valid[score_col], errors="coerce")
    valid["_outcome_num"] = pd.to_numeric(valid[outcome_col], errors="coerce")
    grp = valid.groupby("rede", dropna=False)
    valid["_score_pct"] = grp["_score_num"].rank(pct=True)
    valid["_outcome_pct"] = grp["_outcome_num"].rank(pct=True)
    valid["_disc"] = (valid["_score_pct"] - valid["_outcome_pct"]).abs()

    expose = [
        "rede",
        "uf",
        "nome_municipio",
        "hex_id",
        "hex_precisao",
        "rotulo_confiabilidade",
    ]

    def _row_to_case(row: pd.Series, direcao: str) -> dict:
        case = {col: (row[col] if col in row.index else None) for col in expose}
        case["score_pct_within_rede"] = round(float(row["_score_pct"]), 3)
        case["outcome_pct_within_rede"] = round(float(row["_outcome_pct"]), 3)
        case["score_valor"] = round(float(row["_score_num"]), 2)
        case["outcome_valor"] = round(float(row["_outcome_num"]), 2)
        case["hipotese"] = _hipotese(row, direcao)
        return case

    def _hipotese(row: pd.Series, direcao: str) -> str:
        prec = str(row.get("hex_precisao") or "")
        conf = str(row.get("rotulo_confiabilidade") or "")
        partes: list[str] = []
        if conf == "estimado":
            partes.append("rotulo estimado (EngCorpo: alunos/m2 x metragem)")
        if prec in ("cidade", "indisponivel"):
            partes.append(f"hex por precisao '{prec}' (centroide/baixa precisao)")
        if direcao == "alto_score_baixo_outcome":
            partes.append("maturacao nao observada (possivel unidade nova) e/ou saturacao de concorrente no entorno")
        else:
            partes.append("desempenho acima do esperado pelo score (execucao/posicionamento local nao capturado pelos componentes)")
        return "; ".join(partes)

    cond_hi = (valid["_score_pct"] >= hi) & (valid["_outcome_pct"] <= lo)
    cond_lo = (valid["_score_pct"] <= lo) & (valid["_outcome_pct"] >= hi)

    top_hi = valid[cond_hi].sort_values("_disc", ascending=False).head(k)
    top_lo = valid[cond_lo].sort_values("_disc", ascending=False).head(k)

    return {
        "alto_score_baixo_outcome": [
            _row_to_case(r, "alto_score_baixo_outcome") for _, r in top_hi.iterrows()
        ],
        "baixo_score_alto_outcome": [
            _row_to_case(r, "baixo_score_alto_outcome") for _, r in top_lo.iterrows()
        ],
    }


# --------------------------------------------------------------------------- #
# Relatorio (string; sem I/O)
# --------------------------------------------------------------------------- #
def _fmt_coef(v: float | None) -> str:
    return f"{v:+.3f}" if isinstance(v, (int, float)) else "—"


def _fmt_p(v: float | None) -> str:
    if not isinstance(v, (int, float)):
        return "—"
    if v < 0.001:
        return "<0.001"
    return f"{v:.3f}"


def _cell_row_md(res: dict) -> str:
    celula = res.get("celula", "?")
    n = res.get("n", 0)
    if not res.get("suficiente"):
        motivo = res.get("motivo") or "indisponivel"
        return f"| {celula} | {n} | — | — | — | — | {motivo} |"
    flag = "ok"
    if n < 30:
        flag = "N pequeno; IC largo"
    return (
        f"| {celula} | {n} | {_fmt_coef(res['spearman_rho'])} | "
        f"{_fmt_p(res['spearman_p'])} | {_fmt_coef(res['pearson_r'])} | "
        f"{_fmt_p(res['pearson_p'])} | {flag} |"
    )


def _ranking_agg(por_score: dict[str, list[dict]]) -> list[tuple[str, float]]:
    rank: list[tuple[str, float]] = []
    for score, results in por_score.items():
        agg = next((r for r in results if r.get("celula") == "AGG"), None)
        if agg and agg.get("suficiente") and agg.get("spearman_rho") is not None:
            rank.append((score, float(agg["spearman_rho"])))
    rank.sort(key=lambda t: t[1], reverse=True)
    return rank


def build_report(
    *,
    n_total: int,
    por_score: dict[str, list[dict]],
    decomposicao: dict,
    match_stats: dict,
    outliers_por_score: dict[str, dict],
    conf_counts: dict[str, int],
    boot_agg: dict[str, tuple[float, float] | None] | None = None,
) -> str:
    """Monta o markdown do relatorio de backtest (string, sem I/O)."""
    L: list[str] = []
    L.append("# Relatorio de backtest — poder preditivo dos scores (BLK-SCORE-02)")
    L.append("")
    L.append("> READ-ONLY sobre o M1. Artefato gitignored (`data/analysis/`). Apenas")
    L.append("> agregados/anonimizados (sem `nome_unidade`/PII).")
    L.append(">")
    L.append("> **Analise descritiva; nenhuma proposta de mudanca de peso/formula")
    L.append("> (isso e BLK-SCORE-03).**")
    L.append("")

    # 2. Dados e metodo
    L.append("## 1. Dados e metodo")
    L.append("")
    L.append(f"- Dataset: `data/analysis/dataset_validacao.parquet` — N total = **{n_total}** linhas (1 por unidade).")
    L.append(f"- Desfecho: `{OUTCOME}` (origem por rede em `alunos_origem`; redes: Ultra/Skyfit/EngCorpo).")
    medido = conf_counts.get("medido", 0)
    estimado = conf_counts.get("estimado", 0)
    sinal = conf_counts.get("sinal", 0)
    L.append(
        f"- Confiabilidade do rotulo: medido={medido}, estimado={estimado}, sinal={sinal} "
        "(`rotulo_confiabilidade`)."
    )
    L.append("- Metodo: `scipy.stats` Spearman (rho) + Pearson (r), com p-valor nativo como medida de incerteza primaria.")
    L.append(f"- Piso de N: N_MIN = {N_MIN} (celulas com N < {N_MIN} nao recebem correlacao calculada).")
    L.append(f"- Tratamento: pairwise por celula (score E desfecho ambos nao-nulos); coercao `to_numeric(errors='coerce')`. Seed = {SEED}.")
    L.append("- IC por bootstrap (percentil 2.5/97.5, n_boot=2000, seed 42) so para celulas com N>=30 (OPCIONAL).")
    L.append("")

    # 3. (a) Ranking de poder preditivo
    L.append("## 2. (a) Ranking de poder preditivo dos 4 scores")
    L.append("")
    for score in SCORES:
        results = por_score.get(score, [])
        L.append(f"### {SCORE_LABELS.get(score, score)} (`{score}`)")
        L.append("")
        L.append("| celula | N | Spearman rho | p | Pearson r | p | flag |")
        L.append("|---|---|---|---|---|---|---|")
        for res in results:
            L.append(_cell_row_md(res))
        if boot_agg and boot_agg.get(score) is not None:
            lo, hi = boot_agg[score]
            L.append("")
            L.append(f"IC95% bootstrap (Spearman, AGG): [{lo:+.3f}, {hi:+.3f}].")
        L.append("")

    rank = _ranking_agg(por_score)
    L.append("### Ranking agregado (Spearman rho, AGG)")
    L.append("")
    if rank:
        for i, (score, rho) in enumerate(rank, start=1):
            L.append(f"{i}. `{score}` — rho = {rho:+.3f} ({SCORE_LABELS.get(score, score)})")
    else:
        L.append("- (nenhum score com N suficiente no agregado)")
    L.append("")
    L.append(
        "> Nota: `score_dominio_hibrido` tem cobertura esparsa (poucos hexes com plano "
        "de dominio); por rede a celula EngCorpo cai no piso N_MIN. Ler com cautela."
    )
    L.append("")

    # 4. (b) Decomposicao renda x pop
    L.append("## 3. (b) Decomposicao renda x pop (componentes do M1)")
    L.append("")
    L.append(
        f"- Join read-only com `brasil_priorizados.parquet` por `hex_id`: "
        f"{match_stats.get('casadas', 0)}/{match_stats.get('linhas_com_hex', 0)} linhas com hex casaram "
        f"(**{match_stats.get('match_rate_pct', 0.0)}%**). Apenas linhas casadas entram na decomposicao."
    )
    L.append("")
    for comp_key, comp_label in (("renda", "renda_pct_nacional"), ("pop", "pop_pct_nacional")):
        L.append(f"### Componente `{comp_label}` vs `{OUTCOME}`")
        L.append("")
        L.append("| celula | N | Spearman rho | p | Pearson r | p | flag |")
        L.append("|---|---|---|---|---|---|---|")
        for res in decomposicao.get(comp_key, []):
            L.append(_cell_row_md(res))
        L.append("")
    if decomposicao.get("priorizacao_nas_casadas"):
        L.append("### Contexto: `score_priorizacao` nas MESMAS linhas casadas")
        L.append("")
        L.append("| celula | N | Spearman rho | p | Pearson r | p | flag |")
        L.append("|---|---|---|---|---|---|---|")
        for res in decomposicao["priorizacao_nas_casadas"]:
            L.append(_cell_row_md(res))
        L.append("")
    # achado descritivo: qual componente carrega o sinal (AGG)
    renda_agg = next((r for r in decomposicao.get("renda", []) if r.get("celula") == "AGG"), None)
    pop_agg = next((r for r in decomposicao.get("pop", []) if r.get("celula") == "AGG"), None)
    if renda_agg and pop_agg and renda_agg.get("suficiente") and pop_agg.get("suficiente"):
        rr = renda_agg["spearman_rho"]
        pp = pop_agg["spearman_rho"]
        carrega = "renda_pct_nacional" if abs(rr) >= abs(pp) else "pop_pct_nacional"
        L.append(
            f"**Achado descritivo (AGG):** rho(renda)= {rr:+.3f}, rho(pop)= {pp:+.3f}. "
            f"No agregado, o componente com maior magnitude de correlacao monotonica com o "
            f"desfecho e `{carrega}`."
        )
        L.append("")
    L.append(
        "> Este e um ACHADO DESCRITIVO sobre a correlacao isolada de cada componente com o "
        "desfecho observado nas unidades existentes. NAO implica e NAO sugere novo peso para o M1 "
        "(recalibracao = BLK-SCORE-03, fora deste bloco)."
    )
    L.append("")

    # 5. (c) Outliers
    L.append("## 4. (c) Casos score-alto x desfecho-baixo (e o inverso)")
    L.append("")
    L.append(
        "Percentis calculados DENTRO de cada rede (`rank(pct=True)` within-rede) por causa da "
        "heterogeneidade de desfecho. Casos anonimizados (sem `nome_unidade`)."
    )
    L.append("")
    any_case = False
    for score in SCORES:
        ol = outliers_por_score.get(score, {})
        hi_cases = ol.get("alto_score_baixo_outcome", [])
        lo_cases = ol.get("baixo_score_alto_outcome", [])
        if not hi_cases and not lo_cases:
            continue
        any_case = True
        L.append(f"### Score `{score}`")
        L.append("")
        L.append("**Score alto (>=0.7) x desfecho baixo (<=0.3):**")
        if hi_cases:
            for c in hi_cases:
                L.append(
                    f"- rede={c['rede']} | uf={c['uf']} | municipio={c['nome_municipio']} | "
                    f"hex={c['hex_id']} | precisao={c['hex_precisao']} | conf={c['rotulo_confiabilidade']} | "
                    f"score_pct={c['score_pct_within_rede']} (val={c['score_valor']}) | "
                    f"outcome_pct={c['outcome_pct_within_rede']} (val={c['outcome_valor']:.0f}) | "
                    f"hipotese: {c['hipotese']}"
                )
        else:
            L.append("- (nenhum caso na faixa)")
        L.append("")
        L.append("**Score baixo (<=0.3) x desfecho alto (>=0.7):**")
        if lo_cases:
            for c in lo_cases:
                L.append(
                    f"- rede={c['rede']} | uf={c['uf']} | municipio={c['nome_municipio']} | "
                    f"hex={c['hex_id']} | precisao={c['hex_precisao']} | conf={c['rotulo_confiabilidade']} | "
                    f"score_pct={c['score_pct_within_rede']} (val={c['score_valor']}) | "
                    f"outcome_pct={c['outcome_pct_within_rede']} (val={c['outcome_valor']:.0f}) | "
                    f"hipotese: {c['hipotese']}"
                )
        else:
            L.append("- (nenhum caso na faixa)")
        L.append("")
    if not any_case:
        L.append("- (nenhum caso de discrepancia extrema encontrado nas faixas definidas)")
        L.append("")

    # 6. Limitacoes
    L.append("## 5. Limitacoes")
    L.append("")
    L.append(
        "1. **Maturacao indisponivel.** `maturacao_status` e a constante unica "
        "`maturacao_indisponivel` — nao ha data de abertura confiavel, entao e impossivel "
        "separar unidade nova de unidade madura. Vies: scores podem parecer fracos onde a "
        "unidade ainda e imatura (e vice-versa). NAO foi inventado proxy de idade."
    )
    L.append(
        "2. **Heterogeneidade de desfecho entre redes** (Alunos EVO vs Alunos Totais vs "
        "alunos_total; medido vs estimado). Por isso a analise prioriza correlacao DENTRO de rede e ranks."
    )
    L.append(
        "3. **N pequeno** em EngCorpo e, sobretudo, no `score_dominio_hibrido` (cobertura esparsa) "
        "-> IC largo; significancia nao deve ser forcada."
    )
    L.append(
        "4. **Precisao de hex variavel** (`hex_precisao` = unidade / cidade_centroide / indisponivel): "
        "linhas por centroide de cidade carregam ruido de localizacao."
    )
    L.append(
        "5. **EngCorpo estimado** (`rotulo_confiabilidade='estimado'`): desfecho derivado de alunos/m2 x "
        "metragem, nao medido diretamente."
    )
    L.append("")

    # 7. Apendice
    L.append("## 6. Apendice — N por celula (consolidado)")
    L.append("")
    L.append("| score | AGG | ultra | skyfit | engcorpo |")
    L.append("|---|---|---|---|---|")
    for score in SCORES:
        results = por_score.get(score, [])
        by_cell = {r["celula"]: r["n"] for r in results}
        L.append(
            f"| `{score}` | {by_cell.get('AGG', 0)} | {by_cell.get('ultra', 0)} | "
            f"{by_cell.get('skyfit', 0)} | {by_cell.get('engcorpo', 0)} |"
        )
    L.append("")
    L.append("## 7. Reprodutibilidade")
    L.append("")
    L.append(f"- Seed fixo = {SEED} (bootstrap). scipy.stats determinístico. Gerado por `analysis/score_backtest.py`.")
    L.append("")
    return "\n".join(L)


# --------------------------------------------------------------------------- #
# I/O (unico ponto de leitura) + orquestracao
# --------------------------------------------------------------------------- #
def load_inputs(
    dataset_path: Path = DATASET_PARQUET,
    priorizados_path: Path = PRIORIZADOS_PARQUET,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Le o dataset rotulado e os componentes do priorizados (3 colunas). Read-only."""
    dataset = pd.read_parquet(dataset_path)
    priorizados = pd.read_parquet(
        priorizados_path, columns=["hex_id", *COMPONENTES]
    )
    return dataset, priorizados


def _try_figures(por_score: dict[str, list[dict]], dataset: pd.DataFrame) -> None:
    """Figuras matplotlib OPCIONAIS. Toda falha e engolida; nunca derruba o script."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # Barras de Spearman AGG por score.
        labels: list[str] = []
        rhos: list[float] = []
        for score in SCORES:
            agg = next(
                (r for r in por_score.get(score, []) if r.get("celula") == "AGG"), None
            )
            if agg and agg.get("suficiente") and agg.get("spearman_rho") is not None:
                labels.append(score.replace("score_", ""))
                rhos.append(float(agg["spearman_rho"]))
        if labels:
            fig, ax = plt.subplots(figsize=(7, 4))
            ax.bar(labels, rhos, color="#3b6ea5")
            ax.axhline(0, color="black", linewidth=0.8)
            ax.set_ylabel("Spearman rho (AGG)")
            ax.set_title("Correlacao score x alunos_recorrentes (agregado)")
            plt.xticks(rotation=20, ha="right")
            fig.tight_layout()
            fig.savefig(FIG_DIR / "fig_ranking_spearman_agg.png", dpi=120)
            plt.close(fig)
    except Exception:
        # ImportError, backend headless, qualquer erro -> ignora.
        return


def main(argv: list[str] | None = None) -> int:
    """Orquestra: load -> join -> correlacoes -> decomposicao -> outliers -> report."""
    dataset, priorizados = load_inputs()

    # correlacoes por score (AGG + por rede)
    por_score: dict[str, list[dict]] = {}
    boot_agg: dict[str, tuple[float, float] | None] = {}
    for score in SCORES:
        por_score[score] = correlate_by_cell(dataset, score)
        valid = pairwise_valid(dataset, score)
        boot_agg[score] = bootstrap_ci_spearman(valid[score], valid[OUTCOME])

    # decomposicao renda x pop (join read-only)
    merged, match_stats = join_componentes(dataset, priorizados)
    renda_col = match_stats["comp_renda_col"]
    pop_col = match_stats["comp_pop_col"]
    decomposicao = decompor_renda_pop(merged, renda_col=renda_col, pop_col=pop_col)

    # outliers por score
    outliers_por_score: dict[str, dict] = {
        score: find_outliers(dataset, score) for score in SCORES
    }

    # contagens de confiabilidade
    conf_counts: dict[str, int] = {}
    if "rotulo_confiabilidade" in dataset.columns:
        conf_counts = dataset["rotulo_confiabilidade"].value_counts(dropna=False).to_dict()
        conf_counts = {str(k): int(v) for k, v in conf_counts.items()}

    # figuras opcionais (nunca derrubam)
    _try_figures(por_score, dataset)

    report = build_report(
        n_total=int(len(dataset)),
        por_score=por_score,
        decomposicao=decomposicao,
        match_stats=match_stats,
        outliers_por_score=outliers_por_score,
        conf_counts=conf_counts,
        boot_agg=boot_agg,
    )

    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(report, encoding="utf-8")

    # stdout: SO agregados (sem PII)
    print(f"[score_backtest] dataset: {len(dataset)} linhas; relatorio -> {OUT_REPORT}")
    print(
        f"[score_backtest] decomposicao match: {match_stats['casadas']}/{match_stats['linhas_com_hex']} "
        f"({match_stats['match_rate_pct']}%)"
    )
    rank = _ranking_agg(por_score)
    for i, (score, rho) in enumerate(rank, start=1):
        print(f"  ranking AGG #{i}: {score} rho={rho:+.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
