"""Backtest read-only das features mercado/censitarias vs. desfecho (BLK-SCORE-04).

Continuacao analitica direta do BLK-SCORE-02: usa o MESMO metodo, estilo e
funcoes puras (importadas de ``analysis.score_backtest``) para MEDIR, READ-ONLY,
o poder preditivo INDIVIDUAL (Spearman/Pearson por rede + AGG, com IC bootstrap)
e CONJUNTO (regressao diagnostica OLS restrita) das features das camadas
mercado/competicao e censitaria, contra o desfecho ``alunos_recorrentes`` no
dataset rotulado de 441 unidades (``data/analysis/dataset_validacao.parquet``).

Responde a pergunta do BLK-SCORE-03: "outras variaveis alem de pop/renda
ajudam / sao significativas?". A saida e base de EVIDENCIA para o gate G4 da
DEC-001 — NAO e proposta de score, peso ou formula.

READ-ONLY ESTRITO sobre o M1: NAO recalcula nenhum score, NAO altera pesos/
formula (0.40/0.60), ``scoring.py``, ``constants.py`` ou qualquer artefato
oficial / ``data/outputs/``. Le do mercado SO ``hex_id`` + colunas candidatas.
Saida SO em ``data/analysis/`` (gitignored). Analise DESCRITIVA; nenhuma
proposta de mudanca de peso/formula. Sem PII (``nome_unidade`` jamais exposto).

Execucao::

    python analysis/feature_backtest_mercado.py

Gera:
    data/analysis/relatorio_backtest_mercado.md  (gitignored; agregados, sem PII)
    data/analysis/fig_*.png                       (OPCIONAIS; gitignored; try/except)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Permite ``python analysis/feature_backtest_mercado.py`` standalone: garante o
# repo root no sys.path para resolver o pacote ``analysis`` (sob pytest o
# pythonpath ja resolve). Read-only; nao toca M1.
_REPO_ROOT = str(Path(__file__).resolve().parents[1])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Reuso (NAO duplicacao) das funcoes puras do BLK-SCORE-02. NAO alterar
# ``score_backtest.py``; apenas importar dele.
from analysis.score_backtest import (  # noqa: E402
    N_BOOT,
    N_MIN,
    OUTCOME,
    SEED,
    _cell_row_md,
    bootstrap_ci_spearman,
    correlate_by_cell,
    pairwise_valid,
)

# --------------------------------------------------------------------------- #
# Constantes / contrato de colunas
# --------------------------------------------------------------------------- #
REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET_PARQUET = REPO_ROOT / "data" / "analysis" / "dataset_validacao.parquet"
MERCADO_PARQUET = REPO_ROOT / "data" / "staging" / "hexagonos_mercado_mapeado.parquet"
OUT_REPORT = REPO_ROOT / "data" / "analysis" / "relatorio_backtest_mercado.md"
FIG_DIR = REPO_ROOT / "data" / "analysis"

# Ancora censitaria: VEM DO DATASET (ja presente), nao do parquet mercado.
# Coerencia com o BLK-SCORE-02 (+0.148) e evita overlap.
ANCORA_CENSITARIA = "score_setor_2022_calibrado"

# Feature-pivo do match: existe para todo hex casado no mercado.
PIVO_MATCH = "n_concorrentes_mapeados_2km"

# Lista final de 12 features (poda 19->12 aprovada na revisao humana).
FEATURES: tuple[str, ...] = (
    ANCORA_CENSITARIA,  # 1. ancora censitaria (do DATASET)
    "densidade_pop_setor_hab_km2",  # 2. demanda/densidade intraurbana
    "pop_total_setor_2022",  # 3. volume populacional do setor
    "coverage_pct_setor_2022",  # 4. qualidade/cobertura censitaria (controle)
    "n_concorrentes_mapeados_2km",  # 5. contagem de concorrencia (ambiguo)
    "oferta_efetiva_mapeada_2km",  # 6. oferta ponderada (saturacao)
    "pressao_concorrencial_score_2km",  # 7. pressao competitiva 0-100
    "dist_concorrente_mais_proximo_m",  # 8. distancia (sentinela; ler Spearman)
    "n_unidades_ultra_2km",  # 9. presenca da propria rede (canibalizacao)
    "gap_rede_propria_1km",  # 10. folga da rede propria
    "share_smart_fit_2km",  # 11. dominancia do lider
    "residual_indice_mapeado",  # 12. indice residual demanda-vs-oferta
)

# Rotulo legivel + sinal esperado por feature.
FEATURE_LABELS: dict[str, str] = {
    "score_setor_2022_calibrado": "ancora censitaria — score_setor_2022_calibrado (sinal +)",
    "densidade_pop_setor_hab_km2": "densidade populacional do setor (sinal +)",
    "pop_total_setor_2022": "populacao total do setor (sinal +)",
    "coverage_pct_setor_2022": "cobertura censitaria do hex (controle; sinal incerto)",
    "n_concorrentes_mapeados_2km": "n. concorrentes em 2km (sinal ambiguo: demanda vs saturacao)",
    "oferta_efetiva_mapeada_2km": "oferta efetiva ponderada 2km (sinal -)",
    "pressao_concorrencial_score_2km": "pressao concorrencial 0-100 (sinal -)",
    "dist_concorrente_mais_proximo_m": "dist. ao concorrente mais proximo (sinal +; cauda longa)",
    "n_unidades_ultra_2km": "n. unidades Ultra em 2km (canibalizacao; sinal -; baixa variancia)",
    "gap_rede_propria_1km": "gap da rede propria 1km (sinal +; baixa variancia)",
    "share_smart_fit_2km": "share do lider Smart Fit 2km (sinal incerto)",
    "residual_indice_mapeado": "indice residual mapeado (sinal +; derivado)",
}

# Subconjunto NAO-colinear de 4 regressores para o OLS diagnostico
# (1 censitario + 1 competicao + 1 demanda + 1 distancia).
OLS_REGRESSORS: tuple[str, ...] = (
    "score_setor_2022_calibrado",
    "pressao_concorrencial_score_2km",
    "densidade_pop_setor_hab_km2",
    "dist_concorrente_mais_proximo_m",
)


# --------------------------------------------------------------------------- #
# I/O (unico ponto de leitura)
# --------------------------------------------------------------------------- #
def load_inputs(
    dataset_path: Path = DATASET_PARQUET,
    mercado_path: Path = MERCADO_PARQUET,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Le o dataset rotulado inteiro e o mercado SO com hex_id + features de mercado.

    A ancora censitaria vem do DATASET; do mercado lemos apenas as features de
    mercado (FEATURES menos a ancora), evitando carregar as 131 colunas / 1,5M
    linhas inteiras. Read-only.
    """
    dataset = pd.read_parquet(dataset_path)
    features_mercado = [f for f in FEATURES if f != ANCORA_CENSITARIA]
    mercado = pd.read_parquet(mercado_path, columns=["hex_id", *features_mercado])
    return dataset, mercado


# --------------------------------------------------------------------------- #
# Funcoes puras de transformacao/calculo (testaveis; nao leem disco)
# --------------------------------------------------------------------------- #
def join_features(
    dataset: pd.DataFrame, mercado: pd.DataFrame
) -> tuple[pd.DataFrame, dict]:
    """Left-join read-only das features de mercado por ``hex_id``.

    - Dedup do mercado por ``hex_id`` (defensivo; ja e unico na fonte real).
    - ``suffixes=("", "_merc")`` preserva a ANCORA do DATASET intacta; uma even-
      tual coluna homonima do mercado vira ``*_merc`` e NAO entra nas features
      testadas.
    - ``match_stats`` reporta a taxa de match medida (linhas com hex que recebe-
      ram a feature-pivo nao-nula).
    """
    features_mercado = [
        f for f in FEATURES if f != ANCORA_CENSITARIA and f in mercado.columns
    ]
    merc = mercado[["hex_id", *features_mercado]].copy()
    merc = merc.drop_duplicates(subset=["hex_id"], keep="first")

    left = dataset.copy()
    merged = left.merge(merc, on="hex_id", how="left", suffixes=("", "_merc"))

    tem_hex = left["hex_id"].notna()
    n_com_hex = int(tem_hex.sum())
    pivo = PIVO_MATCH if PIVO_MATCH in merged.columns else None
    if pivo is not None:
        casadas = int(merged.loc[tem_hex.values, pivo].notna().sum())
    else:
        casadas = 0
    match_rate = round(100.0 * casadas / n_com_hex, 1) if n_com_hex else 0.0

    match_stats = {
        "linhas_com_hex": n_com_hex,
        "casadas": casadas,
        "match_rate_pct": match_rate,
        "pivo_match": pivo,
        "ancora_col": ANCORA_CENSITARIA,
        "ancora_origem": "dataset_validacao",
        "n_features": len(FEATURES),
    }
    return merged, match_stats


def prepare_features(merged: pd.DataFrame) -> pd.DataFrame:
    """Politica de sentinela/ausencia — explicita e idempotente (no-op de valores).

    Decisao fixada (revisao humana):
    - ``dist_concorrente_mais_proximo_m``: MANTER o valor real (inclui ~652 km
      para hexes sem concorrente proximo). Spearman trata como topo do rank
      ("sem concorrente proximo = mais distante"), interpretavel e honesto. NAO
      truncar, NAO winsorizar, NAO marcar ausente. Pearson dessa feature fica
      contaminado pela cauda -> a leitura primaria e Spearman.
    - Zeros em ``n_concorrentes_*``/``oferta_*``/``share_*`` sao ausencia REAL de
      concorrente (nao sentinela) -> mantidos.

    NAO aplica transformacao alguma sobre os valores (preserva honestidade);
    ``correlate_by_cell``/``bootstrap_ci_spearman`` ja fazem ``to_numeric(coerce)``
    + pairwise como defesa contra NaN. Idempotente: ``prepare_features`` e o
    proprio ``merged`` (copia defensiva).
    """
    return merged.copy()


def ranking_agg_abs(por_feature: dict[str, list[dict]]) -> list[tuple[str, float]]:
    """Ranking das features pela MAGNITUDE do Spearman rho no AGG (|rho| DESC).

    So inclui features com a celula AGG ``suficiente`` e ``spearman_rho`` nao-nulo.
    (Difere do ranking por rho cru do BLK-SCORE-02: o backlog deste bloco pede
    magnitude.)
    """
    rank: list[tuple[str, float]] = []
    for feat, results in por_feature.items():
        agg = next((r for r in results if r.get("celula") == "AGG"), None)
        if agg and agg.get("suficiente") and agg.get("spearman_rho") is not None:
            rank.append((feat, float(agg["spearman_rho"])))
    rank.sort(key=lambda t: abs(t[1]), reverse=True)
    return rank


def ols_diagnostico(
    merged: pd.DataFrame,
    *,
    regressors: tuple[str, ...] = OLS_REGRESSORS,
    outcome_col: str = OUTCOME,
) -> dict:
    """OLS diagnostico via ``numpy.linalg.lstsq`` (zero dep nova). NAO persiste nada.

    - Listwise: so linhas com TODOS os regressores + outcome nao-nulos.
    - z-score de cada regressor e do outcome SO em memoria (coeficientes
      comparaveis), intercepto adicionado.
    - Retorna ``{n, r2, coefs: {feat: beta_z}, intercepto, cond, nota_instabilidade}``.
    - Marca instabilidade quando ``n < 50`` ou ``cond(X) > 30`` ou variancia-zero
      em algum regressor.

    REPORTADO SO COMO DIAGNOSTICO. NAO cria score, NAO persiste coeficientes.
    """
    cols = list(regressors)
    base = merged.copy()
    presentes = [c for c in cols if c in base.columns]
    if outcome_col not in base.columns or len(presentes) < 1:
        return {
            "n": 0,
            "r2": None,
            "coefs": {},
            "intercepto": None,
            "cond": None,
            "nota_instabilidade": "regressores/outcome ausentes",
            "regressors": presentes,
        }

    num = base[[*presentes, outcome_col]].apply(pd.to_numeric, errors="coerce")
    num = num.dropna(axis=0, how="any")
    n = int(len(num))

    notas: list[str] = []
    if n < 50:
        notas.append(f"N pequeno (N={n} < 50) -> coeficientes instaveis")

    # variancia-zero em algum regressor -> nao da pra padronizar.
    stds = {c: float(num[c].std(ddof=0)) for c in presentes}
    const_cols = [c for c in presentes if stds[c] == 0.0]
    if const_cols or n < 3:
        notas.append(
            "variancia-zero em regressor(es) "
            + (", ".join(const_cols) if const_cols else "(N muito baixo)")
            + " -> OLS indefinido"
        )
        return {
            "n": n,
            "r2": None,
            "coefs": {},
            "intercepto": None,
            "cond": None,
            "nota_instabilidade": "; ".join(notas),
            "regressors": presentes,
        }

    # z-score (media/desvio da subamostra) em memoria.
    Xz = np.column_stack(
        [(num[c].to_numpy() - num[c].mean()) / stds[c] for c in presentes]
    )
    y = num[outcome_col].to_numpy()
    y_std = float(num[outcome_col].std(ddof=0))
    yz = (y - y.mean()) / y_std if y_std > 0 else y - y.mean()

    X = np.column_stack([np.ones(n), Xz])  # intercepto
    cond = float(np.linalg.cond(X))
    if cond > 30:
        notas.append(f"condicao alta (cond={cond:.1f} > 30) -> colinearidade residual")

    coef, *_ = np.linalg.lstsq(X, yz, rcond=None)
    resid = yz - X @ coef
    sse = float(resid @ resid)
    sst = float(((yz - yz.mean()) ** 2).sum())
    r2 = float(1.0 - sse / sst) if sst > 0 else None

    coefs = {feat: float(b) for feat, b in zip(presentes, coef[1:], strict=False)}

    return {
        "n": n,
        "r2": r2,
        "coefs": coefs,
        "intercepto": float(coef[0]),
        "cond": cond,
        "nota_instabilidade": "; ".join(notas) if notas else "ok",
        "regressors": presentes,
    }


# --------------------------------------------------------------------------- #
# Relatorio (string; sem I/O)
# --------------------------------------------------------------------------- #
def build_feature_report(
    *,
    n_total: int,
    por_feature: dict[str, list[dict]],
    boot_agg: dict[str, tuple[float, float] | None],
    match_stats: dict,
    ranking: list[tuple[str, float]],
    ols: dict,
) -> str:
    """Monta o markdown do relatorio de backtest de features (string, sem I/O)."""
    L: list[str] = []
    L.append(
        "# Relatorio de backtest — features mercado/censitarias (BLK-SCORE-04)"
    )
    L.append("")
    L.append("> READ-ONLY sobre o M1. Artefato gitignored (`data/analysis/`). Apenas")
    L.append("> agregados/anonimizados (sem `nome_unidade`/PII).")
    L.append(">")
    L.append("> **Evidencia para o gate G4 da DEC-001; NAO e proposta de score/peso/")
    L.append("> formula.** Analise descritiva; nenhuma recalibracao do M1.")
    L.append("")

    # §1 Dados e metodo
    L.append("## 1. Dados e metodo")
    L.append("")
    L.append(
        f"- Dataset: `data/analysis/dataset_validacao.parquet` — N total = "
        f"**{n_total}** linhas (1 por unidade)."
    )
    L.append(f"- Desfecho: `{OUTCOME}` (redes: Ultra/Skyfit/EngCorpo).")
    L.append(
        "- Fonte de features: `data/staging/hexagonos_mercado_mapeado.parquet` "
        "(lendo SO `hex_id` + colunas candidatas; dedup por `hex_id`)."
    )
    L.append(
        f"- Ancora censitaria `{match_stats.get('ancora_col')}` vem do "
        f"`{match_stats.get('ancora_origem')}` (coerencia com BLK-SCORE-02); a "
        "coluna homonima do mercado (`_merc`) NAO entra nas features testadas."
    )
    L.append(
        f"- Metodo: Spearman (rho, leitura primaria) + Pearson (r) por celula "
        f"(AGG + por rede); piso N_MIN = {N_MIN}; seed = {SEED}; n_boot = "
        f"{N_BOOT}; bootstrap so para N>=30."
    )
    L.append(
        "- Tratamento: pairwise por celula (feature E desfecho nao-nulos); "
        "`to_numeric(errors='coerce')`. Sentinela de distancia preservada (ver §6)."
    )
    L.append("")

    # §2 Match
    L.append("## 2. Taxa de match do join `hex_id`")
    L.append("")
    L.append(
        f"- {match_stats.get('casadas', 0)}/{match_stats.get('linhas_com_hex', 0)} "
        f"linhas com hex casaram com o mercado "
        f"(**{match_stats.get('match_rate_pct', 0.0)}%**), via feature-pivo "
        f"`{match_stats.get('pivo_match')}`. Linhas sem match ficam NaN e sao "
        "descartadas por feature no pairwise."
    )
    L.append("")

    # §3 Tabela por feature × celula
    L.append("## 3. Poder preditivo individual (feature x celula)")
    L.append("")
    for feat in FEATURES:
        results = por_feature.get(feat, [])
        L.append(f"### `{feat}`")
        L.append(f"_{FEATURE_LABELS.get(feat, feat)}_")
        L.append("")
        L.append("| celula | N | Spearman rho | p | Pearson r | p | flag |")
        L.append("|---|---|---|---|---|---|---|")
        for res in results:
            L.append(_cell_row_md(res))
        bo = boot_agg.get(feat)
        if bo is not None:
            lo, hi = bo
            L.append("")
            L.append(f"IC95% bootstrap (Spearman, AGG): [{lo:+.3f}, {hi:+.3f}].")
        L.append("")

    # §4 Ranking por |rho|
    L.append("## 4. Ranking por |rho| (Spearman, AGG)")
    L.append("")
    if ranking:
        for i, (feat, rho) in enumerate(ranking, start=1):
            L.append(
                f"{i}. `{feat}` — rho = {rho:+.3f} (|rho| = {abs(rho):.3f}) — "
                f"{FEATURE_LABELS.get(feat, feat)}"
            )
    else:
        L.append("- (nenhuma feature com N suficiente no agregado)")
    L.append("")
    L.append(
        "> Magnitude (|rho|) e IC importam mais que p isolado: ha multiplicidade "
        "de testes (12 features) — ver §5."
    )
    L.append("")
    L.append(
        "> **CAUTELA DE ENDOGENEIDADE (ler antes de usar o ranking):** as features "
        "de REDE PROPRIA (`n_unidades_ultra_2km`, `gap_rede_propria_1km`) tendem a "
        "liderar o |rho|, mas a correlacao e potencialmente CIRCULAR: a presenca/folga "
        "da propria Ultra no entorno reflete onde a rede JA escolheu operar (e onde ja "
        "teve sucesso), nao um atributo estrutural exogeno do local. NAO sao features "
        "preditivas acionaveis para decidir NOVA expansao — sao espelho da carteira "
        "atual. Para o gate G4 da DEC-001, considerar apenas features EXOGENAS "
        "(censitario/demanda/competicao de terceiros), nunca as de rede propria. "
        "Ver §6 (limitacao 8)."
    )
    L.append("")

    # §5 Sinal conjunto (OLS diagnostico)
    L.append("## 5. Sinal conjunto — OLS diagnostico (NAO e score)")
    L.append("")
    L.append(
        "- Regressores (z-scored, intercepto): "
        + ", ".join(f"`{c}`" for c in ols.get("regressors", []))
        + "."
    )
    L.append(
        f"- N (listwise) = **{ols.get('n', 0)}**; "
        f"R2 = **{ols.get('r2'):+.3f}**"
        if ols.get("r2") is not None
        else f"- N (listwise) = **{ols.get('n', 0)}**; R2 = indefinido"
    )
    if ols.get("coefs"):
        L.append("")
        L.append("| regressor | beta padronizado |")
        L.append("|---|---|")
        for feat, b in ols["coefs"].items():
            L.append(f"| `{feat}` | {b:+.3f} |")
    if ols.get("cond") is not None:
        L.append("")
        L.append(f"Numero de condicao da matriz de regressao: {ols['cond']:.1f}.")
    L.append("")
    L.append(f"- Nota de instabilidade: {ols.get('nota_instabilidade', '—')}.")
    L.append("")
    L.append("**Avisos obrigatorios (ler antes de interpretar):**")
    L.append(
        "1. **Colinearidade residual:** varias features de mercado derivam da "
        "mesma base de concorrentes; o subconjunto de 4 regressores reduz, mas "
        "nao elimina, a redundancia. Betas devem ser lidos com cautela."
    )
    L.append(
        "2. **Multiplicidade de testes:** 12 features x celulas, p-valores NAO "
        "corrigidos -> risco de falso-positivo. Ler magnitude/IC, nao p<0.05 cru."
    )
    L.append(
        "3. **N pequeno:** com N moderado e features correlacionadas o OLS e "
        "instavel; coeficientes sao DIAGNOSTICO, nao base para peso/formula."
    )
    L.append("")
    L.append(
        "> NENHUM coeficiente foi persistido em artefato. Este OLS NAO cria score "
        "nem propoe peso (recalibracao = fora deste bloco / DEC-001)."
    )
    L.append("")

    # §6 Limitacoes
    L.append("## 6. Limitacoes")
    L.append("")
    L.append("**Herdadas do BLK-SCORE-02 (§5):**")
    L.append(
        "1. **Maturacao indisponivel** (`maturacao_status` constante): impossivel "
        "separar unidade nova de madura; scores podem parecer fracos onde a "
        "unidade ainda e imatura. Sem proxy de idade inventado."
    )
    L.append(
        "2. **Heterogeneidade de desfecho entre redes** (Alunos EVO vs Totais; "
        "medido vs estimado) -> priorizar correlacao DENTRO de rede e ranks."
    )
    L.append(
        "3. **N pequeno** em EngCorpo (e por rede em geral) -> IC largo; "
        "significancia nao deve ser forcada."
    )
    L.append(
        "4. **Precisao de hex variavel** (`hex_precisao` = unidade / "
        "cidade_centroide / indisponivel): linhas por centroide carregam ruido."
    )
    L.append(
        "5. **EngCorpo estimado** (`rotulo_confiabilidade='estimado'`): desfecho "
        "derivado de alunos/m2 x metragem, nao medido diretamente."
    )
    L.append("")
    L.append("**Especificas deste bloco:**")
    L.append(
        "6. **Colinearidade entre features de mercado:** varias derivam da mesma "
        "base de concorrentes/oferta (ex.: `pressao_concorrencial_score_2km` e "
        "complemento de `oferta_efetiva_mapeada_2km`; `residual_indice_mapeado` "
        "deriva de gap competitivo) -> correlacoes individuais sao parcialmente "
        "redundantes. Poda 19->12 mitiga, nao elimina."
    )
    L.append(
        "7. **Sentinela de `dist_concorrente_mais_proximo_m`:** hexes sem "
        "concorrente proximo recebem distancia enorme (cauda longa, ~652 km no "
        "maximo observado). Pearson dessa feature e CONTAMINADO pela cauda; a "
        "leitura primaria e Spearman (rank-robusto: 'sem concorrente = topo')."
    )
    L.append(
        "8. **Endogeneidade das features de rede propria:** "
        "`n_unidades_ultra_2km` e `gap_rede_propria_1km` medem a presenca/folga da "
        "PROPRIA Ultra no entorno. Sua correlacao com o desfecho e potencialmente "
        "CIRCULAR (a rede ja se instalou onde via viabilidade/sucesso), nao um sinal "
        "estrutural exogeno. Lideram o |rho| no ranking, mas NAO sao acionaveis para "
        "decidir nova expansao e NAO devem entrar no gate G4 da DEC-001. Tratar como "
        "espelho da carteira atual, nao como preditor de localizacao."
    )
    L.append("")

    # §7 Apendice N por celula
    L.append("## 7. Apendice — N por celula por feature")
    L.append("")
    L.append("| feature | AGG | ultra | skyfit | engcorpo |")
    L.append("|---|---|---|---|---|")
    for feat in FEATURES:
        results = por_feature.get(feat, [])
        by_cell = {r["celula"]: r["n"] for r in results}
        L.append(
            f"| `{feat}` | {by_cell.get('AGG', 0)} | {by_cell.get('ultra', 0)} | "
            f"{by_cell.get('skyfit', 0)} | {by_cell.get('engcorpo', 0)} |"
        )
    L.append("")

    # §8 Reprodutibilidade
    L.append("## 8. Reprodutibilidade")
    L.append("")
    L.append(
        f"- Seed fixo = {SEED}; n_boot = {N_BOOT}; N_MIN = {N_MIN}. "
        "scipy.stats / numpy deterministicos. Gerado por "
        "`analysis/feature_backtest_mercado.py`."
    )
    L.append("")
    return "\n".join(L)


# --------------------------------------------------------------------------- #
# Figuras opcionais
# --------------------------------------------------------------------------- #
def _try_figures(ranking: list[tuple[str, float]]) -> None:
    """Figura matplotlib OPCIONAL (barras de |rho| AGG). Toda falha e engolida."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        if not ranking:
            return
        top = ranking[:10]
        labels = [f.replace("score_", "").replace("_mapeado", "") for f, _ in top]
        vals = [abs(r) for _, r in top]
        fig, ax = plt.subplots(figsize=(8, 4.5))
        ax.barh(labels[::-1], vals[::-1], color="#3b6ea5")
        ax.set_xlabel("|Spearman rho| (AGG)")
        ax.set_title("Poder preditivo individual das features (|rho| AGG)")
        fig.tight_layout()
        fig.savefig(FIG_DIR / "fig_feature_rho_agg.png", dpi=120)
        plt.close(fig)
    except Exception:
        return


# --------------------------------------------------------------------------- #
# Orquestracao
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    """Orquestra: load -> join -> prepare -> correlacao -> ranking -> OLS -> report."""
    dataset, mercado = load_inputs()
    merged, match_stats = join_features(dataset, mercado)
    merged = prepare_features(merged)

    por_feature: dict[str, list[dict]] = {}
    boot_agg: dict[str, tuple[float, float] | None] = {}
    for feat in FEATURES:
        por_feature[feat] = correlate_by_cell(merged, feat)
        valid = pairwise_valid(merged, feat)
        if feat in valid.columns and OUTCOME in valid.columns:
            boot_agg[feat] = bootstrap_ci_spearman(valid[feat], valid[OUTCOME])
        else:
            boot_agg[feat] = None

    ranking = ranking_agg_abs(por_feature)
    ols = ols_diagnostico(merged)

    _try_figures(ranking)

    report = build_feature_report(
        n_total=int(len(dataset)),
        por_feature=por_feature,
        boot_agg=boot_agg,
        match_stats=match_stats,
        ranking=ranking,
        ols=ols,
    )

    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(report, encoding="utf-8")

    # stdout: SO agregados (sem PII)
    print(
        f"[feature_backtest] dataset: {len(dataset)} linhas; relatorio -> {OUT_REPORT}"
    )
    print(
        f"[feature_backtest] match: {match_stats['casadas']}/"
        f"{match_stats['linhas_com_hex']} ({match_stats['match_rate_pct']}%)"
    )
    print("[feature_backtest] top-5 |rho| (AGG):")
    for i, (feat, rho) in enumerate(ranking[:5], start=1):
        print(f"  #{i}: {feat} rho={rho:+.3f} (|rho|={abs(rho):.3f})")
    r2 = ols.get("r2")
    r2_str = f"{r2:+.3f}" if r2 is not None else "indefinido"
    print(f"[feature_backtest] OLS diagnostico: N={ols.get('n', 0)}, R2={r2_str}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
