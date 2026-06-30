"""BLK-TP-05: re-teste honesto do elo demanda OBSERVADA -> captura (k-fold vs baseline).

Re-testa, com validacao honesta (k-fold repetido vs baseline da media; R2 in-sample BANIDO
como desempenho), se a demanda OBSERVADA por hex (`membros`, camada de Demanda Revelada /
BLK-TP-01) + distancia/contagem do concorrente low-cost predizem `alunos_parceiras` FORA da
amostra. E o re-teste do que a DEC-009 marcou NO-GO com demanda IMPUTADA -- agora com sinal
observado. Emite veredito GO/NO-GO honesto.

Modelagem (decisoes A1-A8 aprovadas por Felipe Silva em 2026-06-30):
  - Alvo: `y = log1p(alunos_parceiras)` SO no subset `alunos_parceiras > 0` (regressao de
    magnitude condicional a presenca; os zeros descartados sao contados). [A1/A8]
  - Features principais: `[log1p(membros), log1p(dist_concorrente_lc_min_m), n_concorrente_lc]`.
    `n_acad_parceiras` EXCLUIDO (circular: soma<->contagem, rho +0,94 -> GO espurio) e usado
    SO num modelo de auditoria rotulado; `membros_gt5km_concorrente_lc` EXCLUIDO (colinear). [A2/A3]
  - Validacao: `RepeatedKFold(n_splits=5, n_repeats=5, random_state=42)` + `Ridge`, alpha por
    MENOR RMSE medio out-of-fold sobre `ALPHA_GRID` (reuso de `aderencia.py`). R2_oof e a
    metrica-ancora (R2 ja e vs a media => comparacao contra baseline). Fallback k=10 (n<200)
    e LOO (n<30). [A4]
  - IC95 do R2_oof por bootstrap (>=500 reamostras dos pares (y, y_pred_oof); seed 42). [A5]
  - GO se `R2_oof > LIMIAR_R2_GO` (0,05, herdado) E `IC95_inferior > 0`. NO-GO e VALIDO. [A6]

GUARDRAILS (DEC-001/DEC-008/DEC-009/DEC-012; CLAUDE.md §5):
  - READ-ONLY sobre o M1: NAO recalcula `score_priorizacao`/`hex_score_estrutural`/pesos
    (renda=0.40/pop=0.60); NAO toca carteira/plano/artefatos oficiais.
  - DEC-008: k-fold repetido SEMPRE vs baseline da media; R2 in-sample BANIDO como desempenho
    (so campo de auditoria rotulado); NO-GO e resultado VALIDO -- nao forcar GO.
  - DEC-009: a demanda e insumo OBSERVADO, NUNCA preditor geografico de magnitude para ajustar
    o score; `membros` aqui e variavel de uma analise read-only, nao input do M1.
  - DEC-012: pacote `demanda_revelada/` DISJUNTO -- este modulo NUNCA importa de `pipelines/m1/`,
    `censo_*`, `dashboard/` nem `config.py` raiz; sem PII (zero coluna de COLUNAS_PII_PROIBIDAS
    em qualquer frame/saida/relatorio); fonte real (NAO_ABRA/) nunca tocada; testes so com
    fixture sintetica.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import Ridge
from sklearn.model_selection import RepeatedKFold

# Reuso de infraestrutura da camada paralela irma `dimensionamento/` (NAO e M1/censo/dashboard).
from motor_expansao.dimensionamento.aderencia import (
    ALPHA_GRID,
    LIMIAR_R2_GO,
    _r2_loo_para_alpha,
)
from motor_expansao.dimensionamento.backtest_dim import _r2, _rmse

# Rede de seguranca anti-PII tambem neste modulo de analise.
from .contrato import COLUNAS_PII_PROIBIDAS

_logger = logging.getLogger(__name__)

# Parametros de validacao honesta.
N_SPLITS_PADRAO: int = 5
N_SPLITS_PEQUENO: int = 10  # fallback quando n < N_PISO_KFOLD
N_REPEATS: int = 5
N_PISO_KFOLD: int = 200  # abaixo disso, k=10
N_PISO_LOO: int = 30  # abaixo disso, LOO + flag_extrapolacao_padrao_global
N_BOOTSTRAP: int = 500  # reamostras do IC do R2_oof
SEED: int = 42

# Features do modelo PRINCIPAL (ordem fixa). Rotulos de feature, nao PII.
FEATURES_PRINCIPAIS: tuple[str, ...] = (
    "log1p_membros",
    "log1p_dist_concorrente_lc_min_m",
    "n_concorrente_lc",
)

# Rotulo literal exigido para o R2 in-sample (testado por substring -- NAO alterar o texto).
_ROTULO_INSAMPLE = "apenas auditoria -- NAO usar como desempenho"
# Rotulo literal do modelo secundario com `n_acad_parceiras` (testado por substring).
_ROTULO_AUDITORIA = "auditoria -- vazamento estrutural"


@dataclass
class BacktestTP05Result:
    """Resultado do re-teste honesto demanda OBSERVADA -> captura (k-fold repetido).

    `r2_oof_log` e a metrica-ANCORA (out-of-fold, espaco log, vs media => vs baseline) e
    decide o gate junto com `ic95_r2_oof`. `r2_oof_alunos` e auditoria/interpretabilidade
    (back-transform `expm1`). `r2_insample` existe SO para auditoria -- nunca no veredito (DEC-008).
    """

    alpha_selecionado: float
    """Alpha selecionado por MENOR RMSE medio out-of-fold na varredura do ALPHA_GRID."""

    coefs: dict[str, float]
    """Coeficientes do modelo final por feature (espaco log)."""

    intercepto: float
    """Intercepto do modelo final (espaco log)."""

    r2_oof_log: float
    """R2 out-of-fold no espaco log. METRICA-ANCORA do gate (vs media => vs baseline)."""

    r2_oof_alunos: float
    """R2 out-of-fold no espaco de alunos (expm1 das predicoes oof). Auditoria; NAO decide gate."""

    rmse_oof_log: float
    """RMSE out-of-fold no espaco log."""

    rmse_oof_alunos: float
    """RMSE out-of-fold no espaco de alunos."""

    rmse_oof_baseline_log: float
    """RMSE out-of-fold do baseline (media do treino de cada fold), espaco log."""

    rmse_oof_baseline_alunos: float
    """RMSE out-of-fold do baseline (media do treino de cada fold), espaco de alunos."""

    r2_oof_baseline: float
    """R2 do baseline (= 0,0 por construcao do R2 vs media; registrado p/ leitura)."""

    ic95_r2_oof: tuple[float, float]
    """IC95 (2,5%; 97,5%) do R2_oof_log por bootstrap dos pares (y, y_pred_oof)."""

    r2_insample: float
    """R2 in-sample (espaco log). APENAS auditoria -- NAO usar como desempenho (DEC-008)."""

    n_treinamento: int
    """N de hexes usados (subset alunos_parceiras > 0 e features finitas)."""

    n_descartado_zeros: int
    """N de hexes descartados por `alunos_parceiras == 0` (zero-inflacao)."""

    n_descartado_invalidos: int
    """N de hexes descartados por NaN/inf em alguma feature/alvo (alem dos zeros)."""

    range_alunos: tuple[float, float]
    """(min, max) de `alunos_parceiras` no subset modelado."""

    spearman: dict[str, tuple[float, float]]
    """Correlacao bivariada de Spearman feature_bruta -> (rho, p) vs alunos_parceiras (subset>0)."""

    pct_extrapolacao: float
    """% de pontos cujas features caem fora do envelope min-max das features de treino (0-100)."""

    flag_extrapolacao_padrao_global: bool
    """True se n_treinamento < N_PISO_LOO (modelo globalmente instavel; degradou p/ LOO)."""

    metodo_validacao: str
    """"kfold_5x5" | "kfold_10x5" | "loo" -- caminho de validacao efetivo (A4)."""

    auditoria_vazamento: dict[str, float]
    """Modelo SECUNDARIO com `n_acad_parceiras` (rotulado vazamento estrutural). NAO no veredito."""

    veredito: str
    """"GO" se r2_oof_log > LIMIAR_R2_GO E ic95_inferior > 0; "NO-GO" caso contrario."""

    nota_honesta: str = field(default="")
    """Mensagem legivel (PT, sem PII) com metricas, veredito e os 6 confounds obrigatorios."""

    @property
    def go(self) -> bool:
        """True se o gate honesto deu GO."""
        return self.veredito == "GO"


# --------------------------------------------------------------------------- #
# Correlacoes bivariadas (ANTES do modelo)
# --------------------------------------------------------------------------- #
def correlacoes_bivariadas(df: pd.DataFrame) -> dict[str, tuple[float, float]]:
    """Spearman de cada feature bruta vs `alunos_parceiras` no subset `alunos_parceiras > 0`.

    Reporta a colinearidade ANTES do modelo (confound de mesma origem de medicao no dump).
    Retorna dict feature_bruta -> (rho, p). NaN/NaN se nao houver variancia.
    """
    cols = (
        "membros",
        "dist_concorrente_lc_min_m",
        "n_concorrente_lc",
        "n_acad_parceiras",
        "membros_gt5km_concorrente_lc",
    )
    alvo = pd.to_numeric(df.get("alunos_parceiras"), errors="coerce")
    mask = alvo.notna() & (alvo > 0)
    out: dict[str, tuple[float, float]] = {}
    y = alvo[mask].to_numpy(dtype=float)
    for c in cols:
        if c not in df.columns:
            out[c] = (float("nan"), float("nan"))
            continue
        x = pd.to_numeric(df[c], errors="coerce")[mask].to_numpy(dtype=float)
        ok = np.isfinite(x) & np.isfinite(y)
        if ok.sum() < 3 or np.unique(x[ok]).size < 2:
            out[c] = (float("nan"), float("nan"))
            continue
        rho, p = spearmanr(x[ok], y[ok])
        out[c] = (float(rho), float(p))
    return out


# --------------------------------------------------------------------------- #
# Preparacao dos dados (itens 1.1-1.5)
# --------------------------------------------------------------------------- #
def preparar_dados(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, dict[str, object]]:
    """Prepara (X, y, meta) do modelo PRINCIPAL.

    Alvo = log1p(alunos_parceiras) no subset `alunos_parceiras > 0`. Features =
    [log1p(membros), log1p(dist_concorrente_lc_min_m), n_concorrente_lc]. Limpa NaN/inf.
    `meta` traz n_descartado_zeros, n_descartado_invalidos, range_alunos e os nomes de feature.
    """
    alvo_bruto = pd.to_numeric(df.get("alunos_parceiras"), errors="coerce")
    membros = pd.to_numeric(df.get("membros"), errors="coerce")
    dist = pd.to_numeric(df.get("dist_concorrente_lc_min_m"), errors="coerce")
    n_conc = pd.to_numeric(df.get("n_concorrente_lc"), errors="coerce")

    n_total = int(len(df))
    # Zeros (e <0/NaN) sao descartados ANTES (zero-inflacao -> regressao de magnitude condicional).
    mask_positivo = alvo_bruto.notna() & (alvo_bruto > 0)
    n_descartado_zeros = int((alvo_bruto.notna() & (alvo_bruto <= 0)).sum())

    sub = pd.DataFrame(
        {
            "alunos_parceiras": alvo_bruto[mask_positivo],
            "membros": membros[mask_positivo],
            "dist_concorrente_lc_min_m": dist[mask_positivo],
            "n_concorrente_lc": n_conc[mask_positivo],
        }
    )

    # log1p exige >= 0; membros/dist sao sempre > 0 na fonte, mas guardamos o invalido.
    log_membros = np.log1p(sub["membros"].to_numpy(dtype=float))
    log_dist = np.log1p(sub["dist_concorrente_lc_min_m"].to_numpy(dtype=float))
    n_conc_arr = sub["n_concorrente_lc"].to_numpy(dtype=float)
    y = np.log1p(sub["alunos_parceiras"].to_numpy(dtype=float))

    X = np.column_stack([log_membros, log_dist, n_conc_arr])
    finito = np.isfinite(X).all(axis=1) & np.isfinite(y)
    n_descartado_invalidos = int((~finito).sum())

    X_ok = X[finito]
    y_ok = y[finito]
    alunos_ok = sub["alunos_parceiras"].to_numpy(dtype=float)[finito]
    range_alunos = (
        (float(np.min(alunos_ok)), float(np.max(alunos_ok)))
        if alunos_ok.size
        else (float("nan"), float("nan"))
    )

    meta: dict[str, object] = {
        "n_total": n_total,
        "n_descartado_zeros": n_descartado_zeros,
        "n_descartado_invalidos": n_descartado_invalidos,
        "range_alunos": range_alunos,
        "features": list(FEATURES_PRINCIPAIS),
    }
    return X_ok, y_ok, meta


# --------------------------------------------------------------------------- #
# Nucleo k-fold repetido out-of-fold
# --------------------------------------------------------------------------- #
def _kfold_repetido_oof(
    X: np.ndarray, y: np.ndarray, alpha: float, *, n_splits: int
) -> tuple[np.ndarray, np.ndarray, float, float]:
    """K-fold repetido (out-of-fold) de um Ridge(alpha).

    Para cada repeticao, concatena as predicoes oof e computa R2/RMSE vs a media (baseline).
    Retorna (y_pred_oof_media, y_pred_baseline_oof_media, r2_oof_medio, rmse_oof_medio):
      - `y_pred_oof_media`: predicao oof MEDIA por ponto entre as N_REPEATS (cada ponto e
        retido exatamente 1x por repeticao) -> usada no IC bootstrap.
      - `y_pred_baseline_oof_media`: media do treino do fold (baseline da media) por ponto.
      - metricas: media das N_REPEATS de R2_oof/RMSE_oof (cada repeticao e um oof completo).
    """
    rkf = RepeatedKFold(n_splits=n_splits, n_repeats=N_REPEATS, random_state=SEED)
    n = len(y)
    soma_pred = np.zeros(n, dtype=float)
    soma_base = np.zeros(n, dtype=float)
    cont = np.zeros(n, dtype=float)

    r2_por_rep: list[float] = []
    rmse_por_rep: list[float] = []

    pred_rep = np.full(n, np.nan, dtype=float)
    base_rep = np.full(n, np.nan, dtype=float)
    folds_no_rep = 0
    for train_idx, test_idx in rkf.split(X):
        reg = Ridge(alpha=alpha)
        reg.fit(X[train_idx], y[train_idx])
        pred_rep[test_idx] = reg.predict(X[test_idx])
        base_rep[test_idx] = float(np.mean(y[train_idx]))
        soma_pred[test_idx] += pred_rep[test_idx]
        soma_base[test_idx] += base_rep[test_idx]
        cont[test_idx] += 1.0
        folds_no_rep += 1
        if folds_no_rep == n_splits:
            # fim de uma repeticao completa (oof cobrindo todos os pontos)
            r2_por_rep.append(_r2(y, pred_rep))
            rmse_por_rep.append(_rmse(y, pred_rep))
            pred_rep = np.full(n, np.nan, dtype=float)
            base_rep = np.full(n, np.nan, dtype=float)
            folds_no_rep = 0

    cont_seguro = np.where(cont > 0, cont, 1.0)
    y_pred_oof_media = soma_pred / cont_seguro
    y_pred_baseline_oof_media = soma_base / cont_seguro
    r2_oof_medio = float(np.mean(r2_por_rep)) if r2_por_rep else float("nan")
    rmse_oof_medio = float(np.mean(rmse_por_rep)) if rmse_por_rep else float("nan")
    return y_pred_oof_media, y_pred_baseline_oof_media, r2_oof_medio, rmse_oof_medio


def _ic_bootstrap_r2(
    y: np.ndarray, y_pred_oof: np.ndarray, rng: np.random.Generator, n: int = N_BOOTSTRAP
) -> tuple[float, float]:
    """IC95 (2,5%; 97,5%) do R2(y, y_pred_oof) por bootstrap dos pares.

    Espelha `_ic_bootstrap_auc` de `residual_discriminacao.py`, adaptado a R2: reamostra com
    reposicao os indices, recalcula R2 (vs media da reamostra). Reamostras com SS_tot==0 sao
    descartadas. NaN/NaN se nenhuma valida.
    """
    m = len(y)
    if m < 2:
        return (float("nan"), float("nan"))
    valores: list[float] = []
    tentativas = 0
    teto = 10 * n
    while len(valores) < n and tentativas < teto:
        tentativas += 1
        idx = rng.integers(0, m, size=m)
        yb = y[idx]
        if float(np.sum((yb - yb.mean()) ** 2)) <= 0.0:
            continue
        r = _r2(yb, y_pred_oof[idx])
        if np.isfinite(r):
            valores.append(r)
    if not valores:
        return (float("nan"), float("nan"))
    arr = np.asarray(valores, dtype=float)
    return (float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5)))


def _pct_extrapolacao(X: np.ndarray) -> float:
    """% de pontos fora do envelope min-max das features de treino.

    Treino e teste vem do mesmo dump aqui -> esperado ~0%. O campo existe para o contrato
    honesto e reuso futuro (envelope min-max, padrao de `AderenciaModel.flag_extrapolacao`).
    """
    if X.size == 0:
        return float("nan")
    mn = X.min(axis=0)
    mx = X.max(axis=0)
    fora = ((X < mn) | (X > mx)).any(axis=1)
    return float(100.0 * fora.sum() / len(X))


def _selecionar_alpha_e_oof(
    X: np.ndarray, y: np.ndarray, *, metodo: str
) -> tuple[float, np.ndarray, np.ndarray, float, float]:
    """Varre ALPHA_GRID, escolhe alpha por MENOR RMSE oof, retorna oof do melhor.

    `metodo` in {"kfold_5x5","kfold_10x5","loo"}. Retorna
    (alpha, y_pred_oof, y_pred_baseline_oof, r2_oof_log, rmse_oof_log).
    """
    melhor_alpha = float(ALPHA_GRID[0])
    melhor_rmse = float("inf")
    melhor_r2 = float("nan")
    melhor_pred = np.zeros(len(y), dtype=float)
    melhor_base = np.full(len(y), float(np.mean(y)), dtype=float)

    for alpha in ALPHA_GRID:
        a = float(alpha)
        if metodo == "loo":
            r2_loo, rmse_loo, y_pred = _r2_loo_para_alpha(X, y, a)
            # baseline LOO por ponto: media dos N-1 restantes.
            total = float(np.sum(y))
            base = (total - y) / (len(y) - 1) if len(y) > 1 else np.full(len(y), float(np.mean(y)))
            r2_a, rmse_a, pred_a, base_a = r2_loo, rmse_loo, y_pred, base
        else:
            n_splits = N_SPLITS_PEQUENO if metodo == "kfold_10x5" else N_SPLITS_PADRAO
            pred_a, base_a, r2_a, rmse_a = _kfold_repetido_oof(X, y, a, n_splits=n_splits)
        if rmse_a < melhor_rmse:
            melhor_rmse = rmse_a
            melhor_r2 = r2_a
            melhor_alpha = a
            melhor_pred = pred_a
            melhor_base = base_a

    return melhor_alpha, melhor_pred, melhor_base, melhor_r2, melhor_rmse


def _auditoria_vazamento(df: pd.DataFrame) -> dict[str, float]:
    """Modelo SECUNDARIO COM `n_acad_parceiras` -- AUDITORIA, vazamento estrutural.

    `alunos_parceiras` e a SOMA dos alunos das `n_acad_parceiras` parceiras do hex -> relacao
    quase mecanica (rho +0,94). Mede o salto de R2_oof atribuivel a circularidade. NUNCA entra
    no veredito (item 1.3 do plano). Retorna R2_oof do modelo principal + a feature circular vs
    do principal isolado.
    """
    alvo = pd.to_numeric(df.get("alunos_parceiras"), errors="coerce")
    mask = alvo.notna() & (alvo > 0)
    if int(mask.sum()) < N_PISO_LOO:
        return {"r2_oof_com_circular": float("nan"), "n": int(mask.sum())}

    membros = np.log1p(pd.to_numeric(df.get("membros"), errors="coerce")[mask].to_numpy(float))
    dist = np.log1p(
        pd.to_numeric(df.get("dist_concorrente_lc_min_m"), errors="coerce")[mask].to_numpy(float)
    )
    n_conc = pd.to_numeric(df.get("n_concorrente_lc"), errors="coerce")[mask].to_numpy(float)
    n_acad = pd.to_numeric(df.get("n_acad_parceiras"), errors="coerce")[mask].to_numpy(float)
    y = np.log1p(alvo[mask].to_numpy(float))

    X_circ = np.column_stack([membros, dist, n_conc, n_acad])
    finito = np.isfinite(X_circ).all(axis=1) & np.isfinite(y)
    X_circ = X_circ[finito]
    y = y[finito]
    n = len(y)
    if n < N_PISO_LOO:
        return {"r2_oof_com_circular": float("nan"), "n": n}

    metodo = "kfold_5x5" if n >= N_PISO_KFOLD else "kfold_10x5"
    _alpha, _pred, _base, r2_oof, _rmse_oof = _selecionar_alpha_e_oof(X_circ, y, metodo=metodo)
    return {"r2_oof_com_circular": float(r2_oof), "n": float(n)}


# --------------------------------------------------------------------------- #
# Orquestrador
# --------------------------------------------------------------------------- #
def backtest_demanda_captura(
    df: pd.DataFrame, limiar_r2: float = LIMIAR_R2_GO
) -> BacktestTP05Result:
    """Re-teste honesto demanda OBSERVADA -> captura (k-fold repetido vs baseline da media).

    Modelo Ridge log-log: y=log1p(alunos_parceiras) ~ [log1p(membros),
    log1p(dist_concorrente_lc_min_m), n_concorrente_lc], so no subset alunos_parceiras>0.
    Alpha por menor RMSE oof; R2_oof e a metrica-ancora (vs media => vs baseline). GO se
    R2_oof > limiar_r2 E IC95_inferior > 0. NO-GO NAO levanta (resultado VALIDO, DEC-008).

    READ-ONLY sobre o M1 (DEC-001/009); pacote disjunto (DEC-012); sem PII.

    Parameters
    ----------
    df:
        DataFrame da camada de Demanda Revelada (contrato de 9 colunas). Consumido READ-ONLY.
    limiar_r2:
        Limiar do gate GO (default LIMIAR_R2_GO=0,05, herdado de aderencia.py).

    Returns
    -------
    BacktestTP05Result
        Metricas honestas (k-fold), IC95 bootstrap, flag de extrapolacao, veredito e nota honesta.

    Raises
    ------
    ValueError
        Se nao houver nenhum hex com `alunos_parceiras > 0` apos a limpeza.
    """
    spearman = correlacoes_bivariadas(df)
    X, y, meta = preparar_dados(df)
    n = int(len(y))
    if n == 0:
        raise ValueError(
            "Nenhum hex com alunos_parceiras > 0 apos a limpeza -- nada a modelar."
        )

    # Caminho de validacao (A4): k=5x5 normal; k=10 (n<200); LOO (n<30, instavel).
    flag_extrapolacao_padrao_global = n < N_PISO_LOO
    if n < N_PISO_LOO:
        metodo = "loo"
    elif n < N_PISO_KFOLD:
        metodo = "kfold_10x5"
    else:
        metodo = "kfold_5x5"

    alpha, y_pred_oof, y_pred_base_oof, r2_oof_log, rmse_oof_log = _selecionar_alpha_e_oof(
        X, y, metodo=metodo
    )

    # Espaco de alunos (back-transform expm1 das predicoes oof).
    alunos_real = np.expm1(y)
    alunos_pred = np.expm1(y_pred_oof)
    alunos_base = np.expm1(y_pred_base_oof)
    r2_oof_alunos = _r2(alunos_real, alunos_pred)
    rmse_oof_alunos = _rmse(alunos_real, alunos_pred)
    rmse_oof_baseline_log = _rmse(y, y_pred_base_oof)
    rmse_oof_baseline_alunos = _rmse(alunos_real, alunos_base)

    # IC95 do R2_oof por bootstrap dos pares.
    rng = np.random.default_rng(SEED)
    ic95 = _ic_bootstrap_r2(y, y_pred_oof, rng)

    # Modelo final no conjunto completo (coeficientes definitivos + R2 in-sample AUDITORIA).
    reg = Ridge(alpha=alpha)
    reg.fit(X, y)
    coefs = {nome: float(c) for nome, c in zip(FEATURES_PRINCIPAIS, reg.coef_, strict=True)}
    intercepto = float(reg.intercept_)
    r2_insample = _r2(y, reg.predict(X))

    pct_extra = _pct_extrapolacao(X)
    auditoria = _auditoria_vazamento(df)

    ic_inferior = ic95[0]
    veredito = (
        "GO"
        if (
            np.isfinite(r2_oof_log)
            and r2_oof_log > limiar_r2
            and np.isfinite(ic_inferior)
            and ic_inferior > 0.0
        )
        else "NO-GO"
    )

    result = BacktestTP05Result(
        alpha_selecionado=float(alpha),
        coefs=coefs,
        intercepto=intercepto,
        r2_oof_log=float(r2_oof_log),
        r2_oof_alunos=float(r2_oof_alunos),
        rmse_oof_log=float(rmse_oof_log),
        rmse_oof_alunos=float(rmse_oof_alunos),
        rmse_oof_baseline_log=float(rmse_oof_baseline_log),
        rmse_oof_baseline_alunos=float(rmse_oof_baseline_alunos),
        r2_oof_baseline=0.0,
        ic95_r2_oof=(float(ic95[0]), float(ic95[1])),
        r2_insample=float(r2_insample),
        n_treinamento=n,
        n_descartado_zeros=int(cast(int, meta["n_descartado_zeros"])),
        n_descartado_invalidos=int(cast(int, meta["n_descartado_invalidos"])),
        range_alunos=cast("tuple[float, float]", meta["range_alunos"]),
        spearman=spearman,
        pct_extrapolacao=float(pct_extra),
        flag_extrapolacao_padrao_global=flag_extrapolacao_padrao_global,
        metodo_validacao=metodo,
        auditoria_vazamento=auditoria,
        veredito=veredito,
    )
    result.nota_honesta = _nota_honesta(result)

    _logger.info(
        "BacktestTP05: n=%d metodo=%s alpha=%.3g r2_oof_log=%.4f ic95=(%.4f,%.4f) gate=%s",
        n,
        metodo,
        alpha,
        r2_oof_log,
        ic95[0],
        ic95[1],
        veredito,
    )
    return result


# --------------------------------------------------------------------------- #
# Nota honesta + relatorio
# --------------------------------------------------------------------------- #
def _nota_honesta(r: BacktestTP05Result) -> str:
    """Mensagem legivel (PT, sem PII) com metricas, veredito e os 6 confounds obrigatorios."""
    if r.go:
        cab = (
            f"GO honesto: R2_oof_log={r.r2_oof_log:+.4f} > {LIMIAR_R2_GO} E IC95_inferior="
            f"{r.ic95_r2_oof[0]:+.4f} > 0. A demanda OBSERVADA tem sinal util out-of-fold sobre "
            "a captura -- mas a REABERTURA da Camada 2 (Huff) e gate humano (Felipe), fora deste bloco."
        )
    else:
        cab = (
            f"NO-GO honesto: R2_oof_log={r.r2_oof_log:+.4f} (limiar {LIMIAR_R2_GO}), IC95="
            f"[{r.ic95_r2_oof[0]:+.4f}, {r.ic95_r2_oof[1]:+.4f}]. O sinal nao supera o baseline da "
            "media de forma materialmente confiavel out-of-fold; consistente com a DEC-009 "
            "(demanda nao prevista pela geografia). NO-GO e resultado VALIDO (DEC-008)."
        )
    return (
        "Re-teste honesto demanda OBSERVADA -> captura (BLK-TP-05, k-fold repetido vs baseline)\n"
        "Alvo: log1p(alunos_parceiras) no subset > 0; features: "
        "[log1p(membros), log1p(dist_concorrente_lc_min_m), n_concorrente_lc].\n"
        f"Veredito GO/NO-GO: {cab}\n"
        f"  R2_oof_log (ancora, gate) = {r.r2_oof_log:+.4f} | IC95 = "
        f"[{r.ic95_r2_oof[0]:+.4f}, {r.ic95_r2_oof[1]:+.4f}]\n"
        f"  R2_oof_alunos (auditoria) = {r.r2_oof_alunos:+.4f}\n"
        f"  R2_insample = {r.r2_insample:+.4f} ({_ROTULO_INSAMPLE})\n"
        f"  RMSE_oof_log = {r.rmse_oof_log:.4f} (baseline {r.rmse_oof_baseline_log:.4f}) | "
        f"RMSE_oof_alunos = {r.rmse_oof_alunos:.1f} (baseline {r.rmse_oof_baseline_alunos:.1f})\n"
        f"  n_treinamento = {r.n_treinamento} | descartados: zeros={r.n_descartado_zeros}, "
        f"invalidos={r.n_descartado_invalidos} | range alunos = "
        f"[{r.range_alunos[0]:.0f}, {r.range_alunos[1]:.0f}]\n"
        f"  metodo_validacao = {r.metodo_validacao} | alpha = {r.alpha_selecionado:g} | "
        f"pct_extrapolacao = {r.pct_extrapolacao:.1f}% | flag_global = "
        f"{r.flag_extrapolacao_padrao_global}\n"
        "Confounds obrigatorios (read-only, nao corrigidos):\n"
        "  1. Cobertura ~1% do universo de hexes do Motor (16.575 de ~1,54 M; DEC-012) -> camada "
        "de refino sobre metropoles, NAO nacional.\n"
        "  2. Concentracao em SP (DEC-012) -> amostra nao representativa do Brasil.\n"
        "  3. Ruido de coords ~1 km na fonte -> dist_concorrente_lc_min_m / n_concorrente_lc sao "
        "proxy de ordem de grandeza no join res-7 (~5,16 km2).\n"
        "  4. Vies de selecao das academias parceiras -> alunos_parceiras so existe onde academias "
        "aderiram a plataforma (selecao nao aleatoria); documentado, nao corrigido.\n"
        "  5. Multicolinearidade membros<->alunos_parceiras (ambos do mesmo dump): correlacao "
        "bivariada reportada ANTES do modelo; membros e insumo OBSERVADO, nao prova de causalidade "
        "demanda->captura (DEC-009).\n"
        "  6. n_acad_parceiras quase deterministico (rho +0,94, soma<->contagem) -> EXCLUIDO do "
        f"modelo principal por circularidade; usado SO no modelo de {_ROTULO_AUDITORIA}.\n"
    )


def relatorio_tp05(result: BacktestTP05Result) -> str:
    """String markdown legivel (PT, sem PII) com N, Spearman, metricas, veredito e confounds."""

    def _f(v: float, nd: int = 4) -> str:
        return f"{v:.{nd}f}" if np.isfinite(v) else "n/d"

    L: list[str] = []
    L.append("# Re-teste honesto demanda OBSERVADA -> captura -- BLK-TP-05")
    L.append("")
    L.append(
        "READ-ONLY sobre o M1 (DEC-001/DEC-008/DEC-009). Pacote disjunto (DEC-012). Sem PII "
        "(so contagens/metricas agregadas). A demanda e insumo OBSERVADO, NUNCA preditor "
        "geografico de magnitude para ajustar o score."
    )
    L.append("")
    L.append(
        "Re-teste do elo que a DEC-009 marcou NO-GO com demanda IMPUTADA, agora com demanda "
        "OBSERVADA (`membros`, BLK-TP-01). Alvo = `log1p(alunos_parceiras)` no subset > 0; "
        "features = `[log1p(membros), log1p(dist_concorrente_lc_min_m), n_concorrente_lc]`; "
        "Ridge + k-fold repetido (vs baseline da media)."
    )
    L.append("")
    L.append("## 1. Amostra")
    L.append("")
    L.append(f"- N usados (alunos_parceiras > 0, features finitas): **{result.n_treinamento}**")
    L.append(f"- N descartado por alunos_parceiras == 0 (zero-inflacao): {result.n_descartado_zeros}")
    L.append(f"- N descartado por NaN/inf em feature/alvo: {result.n_descartado_invalidos}")
    L.append(
        f"- Range de alunos_parceiras no subset: "
        f"[{result.range_alunos[0]:.0f}, {result.range_alunos[1]:.0f}]"
    )
    L.append(f"- Metodo de validacao: `{result.metodo_validacao}`")
    L.append("")
    L.append("## 2. Correlacoes bivariadas (Spearman, ANTES do modelo)")
    L.append("")
    L.append("| feature bruta | rho | p |")
    L.append("| --- | ---: | ---: |")
    for feat, (rho, p) in result.spearman.items():
        L.append(f"| {feat} | {_f(rho, 3)} | {_f(p, 4)} |")
    L.append("")
    L.append("## 3. Metricas honestas (k-fold repetido out-of-fold)")
    L.append("")
    L.append("| metrica | valor |")
    L.append("| --- | ---: |")
    L.append(f"| R2_oof_log (ANCORA, gate) | {_f(result.r2_oof_log)} |")
    L.append(f"| IC95 R2_oof (bootstrap >={N_BOOTSTRAP}) | [{_f(result.ic95_r2_oof[0])}, {_f(result.ic95_r2_oof[1])}] |")
    L.append(f"| R2_oof_alunos (auditoria) | {_f(result.r2_oof_alunos)} |")
    L.append(f"| R2_insample ({_ROTULO_INSAMPLE}) | {_f(result.r2_insample)} |")
    L.append(f"| RMSE_oof_log (modelo) | {_f(result.rmse_oof_log)} |")
    L.append(f"| RMSE_oof_log (baseline media) | {_f(result.rmse_oof_baseline_log)} |")
    L.append(f"| RMSE_oof_alunos (modelo) | {_f(result.rmse_oof_alunos, 1)} |")
    L.append(f"| RMSE_oof_alunos (baseline media) | {_f(result.rmse_oof_baseline_alunos, 1)} |")
    L.append(f"| alpha selecionado | {result.alpha_selecionado:g} |")
    L.append(f"| pct_extrapolacao (envelope min-max) | {_f(result.pct_extrapolacao, 1)}% |")
    L.append(f"| flag_extrapolacao_padrao_global (n<{N_PISO_LOO}) | {result.flag_extrapolacao_padrao_global} |")
    L.append("")
    L.append("Coeficientes do modelo final (espaco log):")
    L.append("")
    L.append("| feature | coef |")
    L.append("| --- | ---: |")
    for feat, c in result.coefs.items():
        L.append(f"| {feat} | {c:+.4f} |")
    L.append(f"| (intercepto) | {result.intercepto:+.4f} |")
    L.append("")
    L.append("## 4. Veredito")
    L.append("")
    L.append(
        f"**{result.veredito}** -- GO se `R2_oof_log > {LIMIAR_R2_GO}` E `IC95_inferior > 0`. "
        "NO-GO e resultado VALIDO e esperado (DEC-008)."
    )
    L.append("")
    L.append("## 5. Modelo de auditoria (vazamento estrutural) -- NAO entra no veredito")
    L.append("")
    L.append(
        f"Modelo SECUNDARIO COM `n_acad_parceiras` ({_ROTULO_AUDITORIA}): `alunos_parceiras` e a "
        "SOMA dos alunos das parceiras do hex (rho +0,94, soma<->contagem). So evidencia o salto "
        "de R2 atribuivel a circularidade -- por isso `n_acad_parceiras` foi EXCLUIDO do principal."
    )
    L.append("")
    L.append("| modelo | R2_oof_log | n |")
    L.append("| --- | ---: | ---: |")
    r2c = result.auditoria_vazamento.get("r2_oof_com_circular", float("nan"))
    nc = result.auditoria_vazamento.get("n", float("nan"))
    L.append(f"| principal (sem n_acad_parceiras) | {_f(result.r2_oof_log)} | {result.n_treinamento} |")
    L.append(f"| auditoria (COM n_acad_parceiras) | {_f(float(r2c))} | {int(nc) if np.isfinite(nc) else 'n/d'} |")
    L.append("")
    L.append("## 6. Nota honesta + confounds")
    L.append("")
    L.append("```")
    L.append(result.nota_honesta.rstrip("\n"))
    L.append("```")
    L.append("")
    return "\n".join(L)


def escrever_relatorio_tp05(result: BacktestTP05Result, *, path: Path) -> None:
    """Materializa o relatorio markdown (gitignored, sem PII). NAO chamada em teste."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(relatorio_tp05(result), encoding="utf-8")
    _logger.info("relatorio BLK-TP-05 escrito: %s", path)


# Rede de seguranca anti-PII: nenhum nome de coluna proibida deve aparecer nas saidas.
def _assert_sem_pii_no_relatorio(texto: str) -> None:
    """Falha se qualquer coluna de COLUNAS_PII_PROIBIDAS aparecer no relatorio/saida."""
    baixo = texto.lower()
    presentes = {c for c in COLUNAS_PII_PROIBIDAS if c.lower() in baixo}
    if presentes:  # pragma: no cover - rede de seguranca
        raise AssertionError(f"PII vazou no relatorio TP-05: {presentes}")


__all__ = [
    "BacktestTP05Result",
    "backtest_demanda_captura",
    "correlacoes_bivariadas",
    "preparar_dados",
    "relatorio_tp05",
    "escrever_relatorio_tp05",
    "FEATURES_PRINCIPAIS",
    "N_BOOTSTRAP",
]


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    _df_real = pd.read_parquet(Path("data/staging/demanda_revelada_h3.parquet"))
    _res = backtest_demanda_captura(_df_real)
    escrever_relatorio_tp05(_res, path=Path("data/analysis/backtest_tp05.md"))
    print(_res.nota_honesta)
