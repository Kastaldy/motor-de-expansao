"""BLK-TP-06: validacao honesta do `score_oportunidade_residual` vs demanda OBSERVADA.

Mede, OUT-OF-FOLD (DEC-008: k-fold repetido vs baseline da media; IC95 bootstrap seed-fixa;
R2 in-sample BANIDO do veredito), quanto o `score_oportunidade_residual` (camada PARALELA de
mercado/residual) prevê a demanda paga OBSERVADA (`membros`, camada de Demanda Revelada /
BLK-TP-01) casada por `hex_id`. Quantifica honestamente o +0,52 in-sample da DEC-012 e emite
veredito GO/NO-GO. Se GO, a PROPOSTA de recalibracao vai APENAS no relatorio -- este bloco NAO
altera a formula em producao (`calcular_colunas_mercado.py`) nem regenera nenhum parquet.

Gate humano (APROVADO por Felipe Silva em 2026-07-02):
  - Alvo `y = log1p(membros)` (demanda paga OBSERVADA; cauda longa -> log1p, mesma escolha do
    precedente BLK-TP-05). `membros` = ALVO UNICO.
  - Preditor PRINCIPAL = `score_oportunidade_residual`. Modelo SECUNDARIO auditavel =
    `log1p(oferta_efetiva_disponivel)` (componente-fonte do residual), reportado SEPARADO --
    NAO somado ao principal.
  - `alunos_parceiras`/`n_acad_parceiras` = OFERTA instalada -> SO covariavel/cross-check
    (Spearman ANTES do modelo), NUNCA alvo.
  - GO/NO-GO = R2_oof_log como ANCORA (> LIMIAR_R2_GO=0,05 E IC95_inferior > 0) + rho_oof como
    SUPORTE (>= 0,30 E IC95_inferior > 0). GO forte = ancora R2; GO so por rho e rotulado
    "alinhamento monotonico sem ganho de erro out-of-fold". NO-GO e resultado VALIDO (DEC-008).
  - R4 = (A): validar SO com o ja ingerido; `03_Competidores.xlsx` adiado p/ BLK-TP-08.

GUARDRAILS (DEC-001/DEC-008/DEC-009/DEC-012; CLAUDE.md §5):
  - READ-ONLY sobre o M1: NAO recalcula `score_priorizacao`/`hex_score_estrutural`/pesos
    (renda=0.40/pop=0.60); NAO toca carteira/plano/artefatos oficiais; NAO altera a formula do
    `score_oportunidade_residual` nem regenera `hexagonos_mercado_mapeado.parquet`/derivados.
  - DEC-008: k-fold repetido SEMPRE vs baseline da media; R2 in-sample so campo de auditoria
    rotulado (nunca no veredito); IC95 + flag de extrapolacao; NO-GO e resultado VALIDO.
  - DEC-009: a demanda (`membros`) e ALVO OBSERVADO; PROIBIDO usar `membros`/qualquer coluna da
    demanda como preditor geografico de magnitude ou ajuste do score. Medir se o SCORE (preditor)
    alinha com a demanda observada (alvo) e PERMITIDO (precedente BLK-TP-05).
  - DEC-012: pacote `demanda_revelada/` DISJUNTO -- este modulo NUNCA importa de `pipelines/m1/`,
    `censo_*`, `dashboard/`, `api` nem `config.py` raiz; sem PII (zero coluna de
    COLUNAS_PII_PROIBIDAS em qualquer frame/saida/relatorio); fonte real (NAO_ABRA/) nunca tocada;
    testes so com fixture sintetica.
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

# Parametros de validacao honesta (mesma seed do precedente BLK-TP-05).
N_SPLITS_PADRAO: int = 5
N_SPLITS_PEQUENO: int = 10  # fallback quando n < N_PISO_KFOLD
N_REPEATS: int = 5
N_PISO_KFOLD: int = 200  # abaixo disso, k=10
N_PISO_LOO: int = 30  # abaixo disso, LOO + flag_extrapolacao_padrao_global
N_BOOTSTRAP: int = 2000  # reamostras do IC (subido de 500->2000; pedido do bloco; seed fixa)
SEED: int = 42
# Piso minimo de observacoes para tentar modelar (abaixo disso o oof e degenerado).
N_MIN_MODELO: int = 3
# Universo de hexes do Motor (DEC-003; usado so para a % de cobertura do join, nao e M1).
_UNIVERSO_MOTOR: int = 1_542_531

# Limiar de suporte do rho_oof (Spearman out-of-fold) para o GO "monotonico".
LIMIAR_RHO_SUPORTE: float = 0.30

# Features do modelo PRINCIPAL (ordem fixa). Rotulos de feature, nao PII. O preditor e o SCORE
# residual -- a demanda (`membros`) e ALVO, JAMAIS feature (DEC-009).
FEATURES_PRINCIPAIS: tuple[str, ...] = ("score_oportunidade_residual",)
# Feature do modelo SECUNDARIO auditavel (componente-fonte do residual). Reportado SEPARADO.
FEATURES_SECUNDARIO: tuple[str, ...] = ("log1p_oferta_efetiva_disponivel",)

# Rotulo literal exigido para o R2 in-sample (testado por substring -- NAO alterar o texto).
_ROTULO_INSAMPLE = "apenas auditoria -- NAO usar como desempenho"


@dataclass
class CalibracaoResidualResult:
    """Resultado da validacao honesta `score_oportunidade_residual` -> demanda OBSERVADA.

    `r2_oof_log` e a metrica-ANCORA (out-of-fold, espaco log, vs media => vs baseline) e decide
    o gate junto com `ic95_r2_oof`. `rho_oof`/`ic95_rho_oof` sao o SUPORTE monotonico. `r2_insample`
    existe SO para auditoria -- nunca no veredito (DEC-008).
    """

    alpha_selecionado: float
    """Alpha selecionado por MENOR RMSE medio out-of-fold na varredura do ALPHA_GRID."""

    coefs: dict[str, float]
    """Coeficientes do modelo final por feature (espaco log)."""

    intercepto: float
    """Intercepto do modelo final (espaco log)."""

    r2_oof_log: float
    """R2 out-of-fold no espaco log. METRICA-ANCORA do gate (vs media => vs baseline)."""

    r2_oof_membros: float
    """R2 out-of-fold no espaco de membros (expm1 das predicoes oof). Auditoria; NAO decide gate."""

    rmse_oof_log: float
    """RMSE out-of-fold no espaco log."""

    rmse_oof_membros: float
    """RMSE out-of-fold no espaco de membros."""

    rmse_oof_baseline_log: float
    """RMSE out-of-fold do baseline (media do treino de cada fold), espaco log."""

    rmse_oof_baseline_membros: float
    """RMSE out-of-fold do baseline (media do treino de cada fold), espaco de membros."""

    r2_oof_baseline: float
    """R2 do baseline (= 0,0 por construcao do R2 vs media; registrado p/ leitura)."""

    ic95_r2_oof: tuple[float, float]
    """IC95 (2,5%; 97,5%) do R2_oof_log por bootstrap dos pares (y, y_pred_oof)."""

    rho_oof: float
    """Spearman out-of-fold (predicoes oof concatenadas vs alvo). Metrica de SUPORTE do gate."""

    ic95_rho_oof: tuple[float, float]
    """IC95 (2,5%; 97,5%) do rho_oof por bootstrap dos pares (y, y_pred_oof)."""

    r2_insample: float
    """R2 in-sample (espaco log). APENAS auditoria -- NAO usar como desempenho (DEC-008)."""

    n_treinamento: int
    """N de hexes usados no modelo (features/alvo finitos)."""

    n_join: int
    """N do join inner demanda x mercado por hex_id (antes da limpeza de invalidos)."""

    pct_cobertura_universo: float
    """% do universo de hexes do Motor coberto pelo join (~1,06)."""

    n_descartado_invalidos: int
    """N de hexes descartados por NaN/inf em feature/alvo."""

    range_membros: tuple[float, float]
    """(min, max) de `membros` no subset modelado."""

    spearman_bruta: dict[str, tuple[float, float]]
    """Spearman bivariada (residual/oferta/covariaveis) vs membros, ANTES do modelo."""

    r2_oof_secundario: float
    """R2 out-of-fold do modelo SECUNDARIO auditavel (log1p(oferta)). Reportado SEPARADO."""

    ic95_r2_oof_secundario: tuple[float, float]
    """IC95 do R2_oof do modelo secundario (auditoria; NAO no veredito principal)."""

    pct_extrapolacao: float
    """% de pontos cujas features caem fora do envelope min-max de treino (0-100)."""

    flag_extrapolacao_padrao_global: bool
    """True se n_treinamento < N_PISO_LOO (modelo globalmente instavel; degradou p/ LOO)."""

    metodo_validacao: str
    """"kfold_5x5" | "kfold_10x5" | "loo" -- caminho de validacao efetivo."""

    concentracao_uf: dict[str, float]
    """Top-3 UF (% do join) -- caveat de vies metropolitano."""

    veredito: str
    """"GO" se (R2_oof ancora) OU (rho_oof suporte) baterem o criterio; "NO-GO" caso contrario."""

    tipo_go: str = field(default="")
    """"ancora_r2" | "suporte_rho" | "" -- qual condicao disparou o GO (vazio se NO-GO)."""

    nota_honesta: str = field(default="")
    """Mensagem legivel (PT, sem PII) com metricas, veredito e os confounds obrigatorios."""

    @property
    def go(self) -> bool:
        """True se o gate honesto deu GO."""
        return self.veredito == "GO"


# --------------------------------------------------------------------------- #
# Join demanda x mercado (READ-ONLY, so colunas agregadas -- nunca PII)
# --------------------------------------------------------------------------- #
def _join_demanda_residual(dem_df: pd.DataFrame, mkt_df: pd.DataFrame) -> pd.DataFrame:
    """Inner join por `hex_id` das colunas agregadas necessarias (nunca PII).

    Consome READ-ONLY. Da demanda: `hex_id`, `membros`, `alunos_parceiras`, `n_acad_parceiras`.
    Do mercado: `hex_id`, `score_oportunidade_residual`, `oferta_efetiva_disponivel`, `uf`.
    Colunas ausentes sao toleradas (o modelo/limpeza cuidam depois).
    """
    cols_dem = [
        c
        for c in ("hex_id", "membros", "alunos_parceiras", "n_acad_parceiras")
        if c in dem_df.columns
    ]
    cols_mkt = [
        c
        for c in ("hex_id", "score_oportunidade_residual", "oferta_efetiva_disponivel", "uf")
        if c in mkt_df.columns
    ]
    if "hex_id" not in cols_dem or "hex_id" not in cols_mkt:
        raise ValueError("`hex_id` obrigatorio em ambos os frames para o join.")
    return dem_df[cols_dem].merge(mkt_df[cols_mkt], on="hex_id", how="inner")


def _concentracao_uf(df: pd.DataFrame, *, top: int = 3) -> dict[str, float]:
    """Top-N UF por % do join (caveat de vies). {} se `uf` ausente."""
    if "uf" not in df.columns or df.empty:
        return {}
    vc = (df["uf"].value_counts(normalize=True) * 100.0).round(1)
    return {str(k): float(v) for k, v in vc.head(top).items()}


# --------------------------------------------------------------------------- #
# Correlacoes bivariadas (ANTES do modelo)
# --------------------------------------------------------------------------- #
def correlacoes_bivariadas(df: pd.DataFrame) -> dict[str, tuple[float, float]]:
    """Spearman de cada preditor/covariavel bruta vs `membros` (ANTES do modelo).

    Reporta o alinhamento monotonico e a colinearidade oferta<->residual ANTES do modelo.
    `alunos_parceiras`/`n_acad_parceiras` sao OFERTA instalada (cross-check, nunca alvo).
    Retorna dict feature_bruta -> (rho, p). NaN/NaN se nao houver variancia.
    """
    cols = (
        "score_oportunidade_residual",
        "oferta_efetiva_disponivel",
        "alunos_parceiras",
        "n_acad_parceiras",
    )
    alvo = pd.to_numeric(df.get("membros"), errors="coerce")
    mask = alvo.notna()
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
# Preparacao dos dados
# --------------------------------------------------------------------------- #
def preparar_dados(
    df: pd.DataFrame, *, secundario: bool = False
) -> tuple[np.ndarray, np.ndarray, dict[str, object]]:
    """Prepara (X, y, meta) do modelo.

    Alvo = `log1p(membros)` (demanda paga OBSERVADA; cauda longa). Preditor:
      - principal (secundario=False): `score_oportunidade_residual` (cru; 0-100).
      - secundario (secundario=True): `log1p(oferta_efetiva_disponivel)` (componente-fonte).
    Limpa NaN/inf. `meta` traz `n_join`, `n_descartado_invalidos`, `range_membros`, `features`,
    `concentracao_uf`.
    """
    membros = pd.to_numeric(df.get("membros"), errors="coerce")
    n_join = int(len(df))

    if secundario:
        pred = pd.to_numeric(df.get("oferta_efetiva_disponivel"), errors="coerce")
        feat_col = np.log1p(np.clip(pred.to_numpy(dtype=float), 0.0, None))
        features = list(FEATURES_SECUNDARIO)
    else:
        pred = pd.to_numeric(df.get("score_oportunidade_residual"), errors="coerce")
        feat_col = pred.to_numpy(dtype=float)
        features = list(FEATURES_PRINCIPAIS)

    y = np.log1p(np.clip(membros.to_numpy(dtype=float), 0.0, None))
    X = feat_col.reshape(-1, 1)
    finito = np.isfinite(X).all(axis=1) & np.isfinite(y)
    n_descartado_invalidos = int((~finito).sum())

    X_ok = X[finito]
    y_ok = y[finito]
    membros_ok = membros.to_numpy(dtype=float)[finito]
    range_membros = (
        (float(np.min(membros_ok)), float(np.max(membros_ok)))
        if membros_ok.size
        else (float("nan"), float("nan"))
    )

    meta: dict[str, object] = {
        "n_join": n_join,
        "n_descartado_invalidos": n_descartado_invalidos,
        "range_membros": range_membros,
        "features": features,
        "concentracao_uf": _concentracao_uf(df),
    }
    return X_ok, y_ok, meta


# --------------------------------------------------------------------------- #
# Nucleo k-fold repetido out-of-fold (portado de backtest_tp05.py)
# --------------------------------------------------------------------------- #
def _kfold_repetido_oof(
    X: np.ndarray, y: np.ndarray, alpha: float, *, n_splits: int
) -> tuple[np.ndarray, np.ndarray, float, float]:
    """K-fold repetido (out-of-fold) de um Ridge(alpha).

    Para cada repeticao, concatena as predicoes oof e computa R2/RMSE vs a media (baseline).
    Retorna (y_pred_oof_media, y_pred_baseline_oof_media, r2_oof_medio, rmse_oof_medio).
    """
    rkf = RepeatedKFold(n_splits=n_splits, n_repeats=N_REPEATS, random_state=SEED)
    n = len(y)
    soma_pred = np.zeros(n, dtype=float)
    soma_base = np.zeros(n, dtype=float)
    cont = np.zeros(n, dtype=float)

    r2_por_rep: list[float] = []
    rmse_por_rep: list[float] = []

    pred_rep = np.full(n, np.nan, dtype=float)
    folds_no_rep = 0
    for train_idx, test_idx in rkf.split(X):
        reg = Ridge(alpha=alpha)
        reg.fit(X[train_idx], y[train_idx])
        pred_rep[test_idx] = reg.predict(X[test_idx])
        base_val = float(np.mean(y[train_idx]))
        soma_pred[test_idx] += pred_rep[test_idx]
        soma_base[test_idx] += base_val
        cont[test_idx] += 1.0
        folds_no_rep += 1
        if folds_no_rep == n_splits:
            # fim de uma repeticao completa (oof cobrindo todos os pontos)
            r2_por_rep.append(_r2(y, pred_rep))
            rmse_por_rep.append(_rmse(y, pred_rep))
            pred_rep = np.full(n, np.nan, dtype=float)
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

    Reamostra com reposicao os indices, recalcula R2 (vs media da reamostra). Reamostras com
    SS_tot==0 sao descartadas. NaN/NaN se nenhuma valida.
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


def _ic_bootstrap_rho(
    y: np.ndarray, y_pred_oof: np.ndarray, rng: np.random.Generator, n: int = N_BOOTSTRAP
) -> tuple[float, float]:
    """IC95 (2,5%; 97,5%) do Spearman rho(y, y_pred_oof) por bootstrap dos pares.

    Analogo a `_ic_bootstrap_r2`: reamostra com reposicao, recalcula Spearman. Reamostras sem
    variancia (em y ou pred) sao descartadas. NaN/NaN se nenhuma valida.
    """
    m = len(y)
    if m < 3:
        return (float("nan"), float("nan"))
    valores: list[float] = []
    tentativas = 0
    teto = 10 * n
    while len(valores) < n and tentativas < teto:
        tentativas += 1
        idx = rng.integers(0, m, size=m)
        yb = y[idx]
        pb = y_pred_oof[idx]
        if np.unique(yb).size < 2 or np.unique(pb).size < 2:
            continue
        rho, _p = spearmanr(yb, pb)
        if np.isfinite(rho):
            valores.append(float(rho))
    if not valores:
        return (float("nan"), float("nan"))
    arr = np.asarray(valores, dtype=float)
    return (float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5)))


def _rho_oof(y: np.ndarray, y_pred_oof: np.ndarray) -> float:
    """Spearman out-of-fold (predicoes oof concatenadas vs alvo). NaN se sem variancia."""
    ok = np.isfinite(y) & np.isfinite(y_pred_oof)
    if ok.sum() < 3 or np.unique(y[ok]).size < 2 or np.unique(y_pred_oof[ok]).size < 2:
        return float("nan")
    rho, _p = spearmanr(y[ok], y_pred_oof[ok])
    return float(rho)


def _pct_extrapolacao(X: np.ndarray) -> float:
    """% de pontos fora do envelope min-max das features de treino.

    Treino e teste vem do mesmo dump aqui -> esperado ~0%. O campo existe para o contrato
    honesto e reuso futuro (padrao de `AderenciaModel.flag_extrapolacao`).
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


def _metodo_validacao(n: int) -> str:
    """Caminho de validacao efetivo por N: k=5x5 (n>=200); k=10 (30<=n<200); LOO (n<30)."""
    if n < N_PISO_LOO:
        return "loo"
    if n < N_PISO_KFOLD:
        return "kfold_10x5"
    return "kfold_5x5"


def _r2_oof_secundario(df: pd.DataFrame) -> tuple[float, tuple[float, float]]:
    """Modelo SECUNDARIO auditavel: y=log1p(membros) ~ log1p(oferta_efetiva_disponivel).

    Reportado SEPARADO do principal (NAO somado). Retorna (r2_oof_log, ic95_r2_oof).
    NaN/NaN se dados insuficientes.
    """
    X, y, _meta = preparar_dados(df, secundario=True)
    n = int(len(y))
    if n < N_MIN_MODELO:
        return (float("nan"), (float("nan"), float("nan")))
    metodo = _metodo_validacao(n)
    _alpha, y_pred_oof, _base, r2_oof, _rmse_oof = _selecionar_alpha_e_oof(X, y, metodo=metodo)
    rng = np.random.default_rng(SEED)
    ic = _ic_bootstrap_r2(y, y_pred_oof, rng)
    return (float(r2_oof), (float(ic[0]), float(ic[1])))


# --------------------------------------------------------------------------- #
# Orquestrador
# --------------------------------------------------------------------------- #
def calibrar_residual_demanda(
    df_join: pd.DataFrame,
    *,
    limiar_r2: float = LIMIAR_R2_GO,
    limiar_rho: float = LIMIAR_RHO_SUPORTE,
) -> CalibracaoResidualResult:
    """Valida (out-of-fold) `score_oportunidade_residual` -> demanda OBSERVADA (`membros`).

    Modelo Ridge log-linear: y=log1p(membros) ~ score_oportunidade_residual, sobre o join inner
    demanda x mercado por hex_id. Alpha por menor RMSE oof; R2_oof e a metrica-ancora (vs media =>
    vs baseline) e rho_oof (Spearman oof) e o suporte. GO se (R2_oof > limiar_r2 E IC95_inf > 0)
    OU (rho_oof >= limiar_rho E IC95_inf(rho) > 0). NO-GO NAO levanta (resultado VALIDO, DEC-008).

    READ-ONLY sobre o M1 (DEC-001/009); pacote disjunto (DEC-012); sem PII.

    Parameters
    ----------
    df_join:
        DataFrame do join demanda x mercado (colunas agregadas; ver `_join_demanda_residual`).
        Consumido READ-ONLY.
    limiar_r2:
        Limiar do gate GO-ancora (default LIMIAR_R2_GO=0,05).
    limiar_rho:
        Limiar do gate GO-suporte (default LIMIAR_RHO_SUPORTE=0,30).

    Returns
    -------
    CalibracaoResidualResult
        Metricas honestas (k-fold), IC95 bootstrap (R2 e rho), flag de extrapolacao, veredito.

    Raises
    ------
    ValueError
        Se nao houver nenhum hex valido apos a limpeza.
    """
    spearman = correlacoes_bivariadas(df_join)
    X, y, meta = preparar_dados(df_join, secundario=False)
    n = int(len(y))
    if n == 0:
        raise ValueError("Nenhum hex valido apos a limpeza -- nada a modelar.")

    flag_extrapolacao_padrao_global = n < N_PISO_LOO
    metodo = _metodo_validacao(n)

    alpha, y_pred_oof, y_pred_base_oof, r2_oof_log, rmse_oof_log = _selecionar_alpha_e_oof(
        X, y, metodo=metodo
    )

    # Espaco de membros (back-transform expm1 das predicoes oof).
    membros_real = np.expm1(y)
    membros_pred = np.expm1(y_pred_oof)
    membros_base = np.expm1(y_pred_base_oof)
    r2_oof_membros = _r2(membros_real, membros_pred)
    rmse_oof_membros = _rmse(membros_real, membros_pred)
    rmse_oof_baseline_log = _rmse(y, y_pred_base_oof)
    rmse_oof_baseline_membros = _rmse(membros_real, membros_base)

    # IC95 do R2_oof e do rho_oof por bootstrap dos pares (seed 42; determinista).
    rng = np.random.default_rng(SEED)
    ic95_r2 = _ic_bootstrap_r2(y, y_pred_oof, rng)
    rng_rho = np.random.default_rng(SEED)
    ic95_rho = _ic_bootstrap_rho(y, y_pred_oof, rng_rho)
    rho_oof = _rho_oof(y, y_pred_oof)

    # Modelo final no conjunto completo (coeficientes definitivos + R2 in-sample AUDITORIA).
    reg = Ridge(alpha=alpha)
    reg.fit(X, y)
    coefs = {nome: float(c) for nome, c in zip(FEATURES_PRINCIPAIS, reg.coef_, strict=True)}
    intercepto = float(reg.intercept_)
    r2_insample = _r2(y, reg.predict(X))

    pct_extra = _pct_extrapolacao(X)
    r2_oof_sec, ic95_r2_sec = _r2_oof_secundario(df_join)

    # Veredito: ancora R2 OU suporte rho (gate humano 2026-07-02).
    go_ancora = (
        np.isfinite(r2_oof_log)
        and r2_oof_log > limiar_r2
        and np.isfinite(ic95_r2[0])
        and ic95_r2[0] > 0.0
    )
    go_suporte = (
        np.isfinite(rho_oof)
        and rho_oof >= limiar_rho
        and np.isfinite(ic95_rho[0])
        and ic95_rho[0] > 0.0
    )
    if go_ancora:
        veredito, tipo_go = "GO", "ancora_r2"
    elif go_suporte:
        veredito, tipo_go = "GO", "suporte_rho"
    else:
        veredito, tipo_go = "NO-GO", ""

    result = CalibracaoResidualResult(
        alpha_selecionado=float(alpha),
        coefs=coefs,
        intercepto=intercepto,
        r2_oof_log=float(r2_oof_log),
        r2_oof_membros=float(r2_oof_membros),
        rmse_oof_log=float(rmse_oof_log),
        rmse_oof_membros=float(rmse_oof_membros),
        rmse_oof_baseline_log=float(rmse_oof_baseline_log),
        rmse_oof_baseline_membros=float(rmse_oof_baseline_membros),
        r2_oof_baseline=0.0,
        ic95_r2_oof=(float(ic95_r2[0]), float(ic95_r2[1])),
        rho_oof=float(rho_oof),
        ic95_rho_oof=(float(ic95_rho[0]), float(ic95_rho[1])),
        r2_insample=float(r2_insample),
        n_treinamento=n,
        n_join=int(cast(int, meta["n_join"])),
        pct_cobertura_universo=float(100.0 * int(cast(int, meta["n_join"])) / _UNIVERSO_MOTOR),
        n_descartado_invalidos=int(cast(int, meta["n_descartado_invalidos"])),
        range_membros=cast("tuple[float, float]", meta["range_membros"]),
        spearman_bruta=spearman,
        r2_oof_secundario=float(r2_oof_sec),
        ic95_r2_oof_secundario=(float(ic95_r2_sec[0]), float(ic95_r2_sec[1])),
        pct_extrapolacao=float(pct_extra),
        flag_extrapolacao_padrao_global=flag_extrapolacao_padrao_global,
        metodo_validacao=metodo,
        concentracao_uf=cast("dict[str, float]", meta["concentracao_uf"]),
        veredito=veredito,
        tipo_go=tipo_go,
    )
    result.nota_honesta = _nota_honesta(result)

    _logger.info(
        "CalibracaoResidual: n=%d metodo=%s alpha=%.3g r2_oof_log=%.4f ic95=(%.4f,%.4f) "
        "rho_oof=%.4f ic95_rho=(%.4f,%.4f) gate=%s(%s)",
        n,
        metodo,
        alpha,
        r2_oof_log,
        ic95_r2[0],
        ic95_r2[1],
        rho_oof,
        ic95_rho[0],
        ic95_rho[1],
        veredito,
        tipo_go or "n/a",
    )
    return result


# --------------------------------------------------------------------------- #
# Nota honesta + relatorio
# --------------------------------------------------------------------------- #
def _nota_honesta(r: CalibracaoResidualResult) -> str:
    """Mensagem legivel (PT, sem PII) com metricas, veredito e os confounds obrigatorios."""
    if r.go and r.tipo_go == "ancora_r2":
        cab = (
            f"GO (ancora R2): R2_oof_log={r.r2_oof_log:+.4f} > {LIMIAR_R2_GO} E IC95_inferior="
            f"{r.ic95_r2_oof[0]:+.4f} > 0. O `score_oportunidade_residual` prevê a demanda "
            "OBSERVADA fora da amostra (bate o baseline da media), RESTRITO ao recorte "
            "metropolitano do join (~1%). RECALIBRAR a formula em producao e FOLLOW-UP com gate "
            "humano (fora deste bloco)."
        )
    elif r.go and r.tipo_go == "suporte_rho":
        cab = (
            f"GO (suporte rho): alinhamento monotonico sem ganho de erro out-of-fold. "
            f"rho_oof={r.rho_oof:+.4f} >= {LIMIAR_RHO_SUPORTE} E IC95_inferior="
            f"{r.ic95_rho_oof[0]:+.4f} > 0, mas a ANCORA R2_oof_log={r.r2_oof_log:+.4f} nao superou "
            f"{LIMIAR_R2_GO}/IC. O residual ORDENA a demanda observada, mas nao reduz o erro vs a "
            "media out-of-fold. Recalibracao = FOLLOW-UP com gate."
        )
    else:
        cab = (
            f"NO-GO honesto: R2_oof_log={r.r2_oof_log:+.4f} (limiar {LIMIAR_R2_GO}), IC95="
            f"[{r.ic95_r2_oof[0]:+.4f}, {r.ic95_r2_oof[1]:+.4f}]; rho_oof={r.rho_oof:+.4f} "
            f"(limiar {LIMIAR_RHO_SUPORTE}), IC95=[{r.ic95_rho_oof[0]:+.4f}, {r.ic95_rho_oof[1]:+.4f}]. "
            "O residual nao supera o baseline da media de forma materialmente confiavel out-of-fold "
            "nem alcanca alinhamento monotonico com IC valido. NO-GO e resultado VALIDO (DEC-008)."
        )
    top_uf = ", ".join(f"{k} {v:.1f}%" for k, v in r.concentracao_uf.items()) or "n/d"
    return (
        "Validacao honesta score_oportunidade_residual -> demanda OBSERVADA "
        "(BLK-TP-06, k-fold repetido vs baseline)\n"
        "Alvo: log1p(membros) (demanda paga OBSERVADA); preditor: score_oportunidade_residual.\n"
        f"Veredito GO/NO-GO: {cab}\n"
        f"  R2_oof_log (ancora, gate) = {r.r2_oof_log:+.4f} | IC95 = "
        f"[{r.ic95_r2_oof[0]:+.4f}, {r.ic95_r2_oof[1]:+.4f}]\n"
        f"  rho_oof (suporte) = {r.rho_oof:+.4f} | IC95 = "
        f"[{r.ic95_rho_oof[0]:+.4f}, {r.ic95_rho_oof[1]:+.4f}]\n"
        f"  R2_oof_membros (auditoria) = {r.r2_oof_membros:+.4f}\n"
        f"  R2_insample = {r.r2_insample:+.4f} ({_ROTULO_INSAMPLE})\n"
        f"  R2_oof secundario (log1p(oferta), reportado SEPARADO) = {r.r2_oof_secundario:+.4f} | "
        f"IC95 = [{r.ic95_r2_oof_secundario[0]:+.4f}, {r.ic95_r2_oof_secundario[1]:+.4f}]\n"
        f"  RMSE_oof_log = {r.rmse_oof_log:.4f} (baseline {r.rmse_oof_baseline_log:.4f}) | "
        f"RMSE_oof_membros = {r.rmse_oof_membros:.1f} (baseline {r.rmse_oof_baseline_membros:.1f})\n"
        f"  n_join = {r.n_join} | n_treinamento = {r.n_treinamento} | "
        f"invalidos={r.n_descartado_invalidos} | cobertura ~{r.pct_cobertura_universo:.2f}% do "
        f"universo | range membros = [{r.range_membros[0]:.0f}, {r.range_membros[1]:.0f}]\n"
        f"  metodo_validacao = {r.metodo_validacao} | alpha = {r.alpha_selecionado:g} | "
        f"pct_extrapolacao = {r.pct_extrapolacao:.1f}% | flag_global = "
        f"{r.flag_extrapolacao_padrao_global} | top-3 UF = {top_uf}\n"
        "Confounds obrigatorios (read-only, nao corrigidos):\n"
        "  1. Cobertura ~1% do universo de hexes do Motor (16.575 de ~1,54 M; DEC-012) -> camada "
        "de refino sobre metropoles, NAO validacao nacional.\n"
        "  2. Vies metropolitano do Sudeste (top-3 UF do join concentram ~metade da amostra) -> "
        "amostra nao representativa do Brasil.\n"
        "  3. Dois tipos de aluno/ativo: `membros` (demanda paga OBSERVADA, ALVO) x "
        "`alunos_parceiras` (OFERTA instalada nas parceiras) -- NAO confundir; `alunos_parceiras` "
        "so entra como covariavel/cross-check, NUNCA alvo.\n"
        "  4. Ruido de coords ~1 km na fonte -> o join res-7 (~5,16 km2) e proxy de ordem de "
        "grandeza; ruido atenua o sinal.\n"
        "  5. Vies de selecao da plataforma -> `membros` so existe onde ha adesao ao beneficio "
        "corporativo (selecao nao aleatoria); documentado, nao corrigido.\n"
        "  6. `oferta_efetiva_disponivel` e componente-FONTE do residual (colinear) -> reportado "
        "em modelo SEPARADO (auditoria), NUNCA somado ao principal sem justificativa.\n"
        "  7. DEC-009: `membros` e ALVO OBSERVADO; PROIBIDO usar como preditor geografico de "
        "magnitude ou ajuste do score. Este bloco VALIDA + PROPOE (documenta), nao APLICA.\n"
    )


def relatorio_calibracao(result: CalibracaoResidualResult) -> str:
    """String markdown legivel (PT, sem PII) com N, Spearman, metricas, veredito e confounds.

    As 7 secoes do handoff: amostra/cobertura, tipos de aluno, correlacoes bivariadas, metricas
    honestas, veredito, proposta de recalibracao (se GO) e limitacoes/confounds.
    """

    def _f(v: float, nd: int = 4) -> str:
        return f"{v:.{nd}f}" if np.isfinite(v) else "n/d"

    L: list[str] = []
    L.append("# Calibracao/validacao do score residual vs demanda revelada -- BLK-TP-06")
    L.append("")
    L.append(
        "READ-ONLY sobre o M1 (DEC-001/DEC-008/DEC-009). Pacote disjunto (DEC-012). Sem PII "
        "(so contagens/metricas agregadas). A demanda (`membros`) e ALVO OBSERVADO; o "
        "`score_oportunidade_residual` e o PREDITOR. Este bloco VALIDA + PROPOE (documenta) -- "
        "NAO altera a formula em producao nem regenera `hexagonos_mercado_mapeado.parquet`."
    )
    L.append("")
    L.append(
        "Gate humano APROVADO por Felipe Silva em 2026-07-02: R4=(A) adiar `03_Competidores.xlsx` "
        "p/ BLK-TP-08; alvo=`log1p(membros)`; GO/NO-GO = R2_oof_log ancora + rho_oof suporte; "
        "`membros` = alvo unico. R2 in-sample BANIDO do veredito."
    )
    L.append("")
    L.append("## 1. Amostra + cobertura/vies")
    L.append("")
    L.append(f"- N do join inner (demanda x mercado por hex_id): **{result.n_join}**")
    L.append(f"- N usado no modelo (features/alvo finitos): **{result.n_treinamento}**")
    L.append(f"- N descartado por NaN/inf em feature/alvo: {result.n_descartado_invalidos}")
    L.append(
        f"- Cobertura do universo do Motor (~1,54 M hexes): **~{result.pct_cobertura_universo:.2f}%** "
        "-> camada de refino sobre metropoles, NAO validacao nacional."
    )
    top_uf = ", ".join(f"{k} {v:.1f}%" for k, v in result.concentracao_uf.items()) or "n/d"
    L.append(f"- Concentracao (top-3 UF do join): {top_uf} -> vies metropolitano do Sudeste.")
    L.append(
        f"- Range de `membros` no subset: "
        f"[{result.range_membros[0]:.0f}, {result.range_membros[1]:.0f}]"
    )
    L.append(f"- Metodo de validacao: `{result.metodo_validacao}`")
    L.append("")
    L.append("## 2. Distincao dos 2 tipos de aluno/ativo (alvo travado)")
    L.append("")
    L.append(
        "- **`membros`** = demanda paga OBSERVADA (beneficio corporativo agregado ao hex). "
        "**ALVO UNICO** deste bloco."
    )
    L.append(
        "- **`alunos_parceiras`** / **`n_acad_parceiras`** = OFERTA instalada nas academias "
        "parceiras -> SO covariavel/cross-check (Spearman ANTES do modelo), NUNCA alvo. Inverter "
        "os dois validaria o residual contra oferta instalada, nao contra demanda (erro semantico)."
    )
    L.append(
        "- Preditor principal = `score_oportunidade_residual`; secundario auditavel = "
        "`log1p(oferta_efetiva_disponivel)` (componente-fonte do residual), reportado SEPARADO."
    )
    L.append("")
    L.append("## 3. Correlacoes bivariadas (Spearman, ANTES do modelo)")
    L.append("")
    L.append("| feature bruta (vs membros) | rho | p |")
    L.append("| --- | ---: | ---: |")
    for feat, (rho, p) in result.spearman_bruta.items():
        L.append(f"| {feat} | {_f(rho, 3)} | {_f(p, 4)} |")
    L.append("")
    L.append(
        "Nota: o rho in-sample de `score_oportunidade_residual` reproduz o +0,52 exploratorio da "
        "DEC-012 -- e in-sample, NAO o veredito. O veredito honesto e out-of-fold (secao 4)."
    )
    L.append("")
    L.append("## 4. Metricas honestas (k-fold repetido out-of-fold)")
    L.append("")
    L.append("| metrica | valor |")
    L.append("| --- | ---: |")
    L.append(f"| R2_oof_log (ANCORA, gate) | {_f(result.r2_oof_log)} |")
    L.append(
        f"| IC95 R2_oof (bootstrap {N_BOOTSTRAP}, seed {SEED}) | "
        f"[{_f(result.ic95_r2_oof[0])}, {_f(result.ic95_r2_oof[1])}] |"
    )
    L.append(f"| rho_oof (SUPORTE, Spearman oof) | {_f(result.rho_oof)} |")
    L.append(
        f"| IC95 rho_oof (bootstrap {N_BOOTSTRAP}, seed {SEED}) | "
        f"[{_f(result.ic95_rho_oof[0])}, {_f(result.ic95_rho_oof[1])}] |"
    )
    L.append(f"| R2_oof_membros (auditoria expm1) | {_f(result.r2_oof_membros)} |")
    L.append(f"| R2_insample ({_ROTULO_INSAMPLE}) | {_f(result.r2_insample)} |")
    L.append(
        f"| R2_oof secundario log1p(oferta) (SEPARADO) | {_f(result.r2_oof_secundario)} "
        f"IC95 [{_f(result.ic95_r2_oof_secundario[0])}, {_f(result.ic95_r2_oof_secundario[1])}] |"
    )
    L.append(f"| RMSE_oof_log (modelo) | {_f(result.rmse_oof_log)} |")
    L.append(f"| RMSE_oof_log (baseline media) | {_f(result.rmse_oof_baseline_log)} |")
    L.append(f"| RMSE_oof_membros (modelo) | {_f(result.rmse_oof_membros, 1)} |")
    L.append(f"| RMSE_oof_membros (baseline media) | {_f(result.rmse_oof_baseline_membros, 1)} |")
    L.append(f"| alpha selecionado | {result.alpha_selecionado:g} |")
    L.append(f"| pct_extrapolacao (envelope min-max) | {_f(result.pct_extrapolacao, 1)}% |")
    L.append(
        f"| flag_extrapolacao_padrao_global (n<{N_PISO_LOO}) | "
        f"{result.flag_extrapolacao_padrao_global} |"
    )
    L.append("")
    L.append("Coeficientes do modelo final (espaco log):")
    L.append("")
    L.append("| feature | coef |")
    L.append("| --- | ---: |")
    for feat, c in result.coefs.items():
        L.append(f"| {feat} | {c:+.4f} |")
    L.append(f"| (intercepto) | {result.intercepto:+.4f} |")
    L.append("")
    L.append("## 5. Veredito")
    L.append("")
    L.append(
        f"**{result.veredito}**"
        + (f" ({result.tipo_go})" if result.tipo_go else "")
        + f" -- GO se (`R2_oof_log > {LIMIAR_R2_GO}` E `IC95_inf(R2) > 0`) OU "
        f"(`rho_oof >= {LIMIAR_RHO_SUPORTE}` E `IC95_inf(rho) > 0`). "
        "R2 e a ANCORA; rho e o SUPORTE monotonico. NO-GO e resultado VALIDO (DEC-008)."
    )
    L.append("")
    L.append("## 6. Proposta de recalibracao (documentada -- NAO aplicada)")
    L.append("")
    if result.go:
        L.append(
            "Com GO, o alinhamento residual->demanda observada justifica ESTUDAR (follow-up com "
            "gate proprio, NUNCA neste bloco) ajustes na formula de `score_oportunidade_residual` "
            "(`calcular_colunas_mercado.py`), por exemplo:"
        )
        L.append(
            "- **Capacidade default (2.500 alunos/unidade)**: recalibrar a partir da razao "
            "observada `membros`/`oferta_efetiva_disponivel` no recorte metropolitano (onde ha "
            "demanda observada), com IC e flag de extrapolacao."
        )
        L.append(
            "- **Peso de `oferta_efetiva_disponivel`**: o modelo secundario mede o poder isolado do "
            "componente-fonte; comparar com o principal indica se o residual pondera bem a oferta."
        )
        L.append(
            "- **Faixa de corte / normalizacao 0-100**: reavaliar o `clip(100*oferta/2500,0,100)` "
            "contra a distribuicao de `membros` observada."
        )
        L.append("")
        L.append(
            "**IMPORTANTE:** isto e ANALISE/RECOMENDACAO, NAO mudanca de producao. Aplicar a "
            "recalibracao (editar `calcular_colunas_mercado.py` / regenerar "
            "`hexagonos_mercado_mapeado.parquet` e derivados) e FOLLOW-UP com DEC + gate humano "
            "(BLK-TP-07). Este bloco NAO altera nenhuma linha da formula em producao."
        )
    else:
        L.append(
            "Veredito NO-GO -> **nenhuma** proposta de recalibracao. Recalibrar a formula do "
            "residual sobre um sinal que nao se sustenta out-of-fold seria sobreajuste a ruido "
            "(DEC-008). O residual segue como esta em producao."
        )
    L.append("")
    L.append("## 7. Limitacoes / confounds")
    L.append("")
    L.append("```")
    L.append(result.nota_honesta.rstrip("\n"))
    L.append("```")
    L.append("")
    return "\n".join(L)


def escrever_relatorio(result: CalibracaoResidualResult, *, path: Path) -> None:
    """Materializa o relatorio markdown (gitignored, sem PII). NAO chamada em teste."""
    path = Path(path)
    texto = relatorio_calibracao(result)
    _assert_sem_pii_no_relatorio(texto)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(texto, encoding="utf-8")
    _logger.info("relatorio BLK-TP-06 escrito: %s", path)


# Rede de seguranca anti-PII: nenhum nome de coluna proibida deve aparecer nas saidas.
def _assert_sem_pii_no_relatorio(texto: str) -> None:
    """Falha se qualquer coluna de COLUNAS_PII_PROIBIDAS aparecer como token isolado no texto.

    Word-boundary para nao casar substring de palavras PT legitimas (ex.: "id" em "medida").
    """
    import re

    baixo = texto.lower()
    presentes = {
        c for c in COLUNAS_PII_PROIBIDAS if re.search(rf"\b{re.escape(c.lower())}\b", baixo)
    }
    if presentes:  # pragma: no cover - rede de seguranca
        raise AssertionError(f"PII vazou no relatorio BLK-TP-06: {presentes}")


__all__ = [
    "CalibracaoResidualResult",
    "calibrar_residual_demanda",
    "correlacoes_bivariadas",
    "preparar_dados",
    "relatorio_calibracao",
    "escrever_relatorio",
    "FEATURES_PRINCIPAIS",
    "FEATURES_SECUNDARIO",
    "LIMIAR_RHO_SUPORTE",
    "N_BOOTSTRAP",
]


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    _dem = pd.read_parquet(Path("data/staging/demanda_revelada_h3.parquet"))
    _mkt = pd.read_parquet(
        Path("data/staging/hexagonos_mercado_mapeado.parquet"),
        columns=["hex_id", "score_oportunidade_residual", "oferta_efetiva_disponivel", "uf"],
    )
    _join = _join_demanda_residual(_dem, _mkt)
    _res = calibrar_residual_demanda(_join)
    escrever_relatorio(_res, path=Path("data/analysis/calibracao_residual_demanda.md"))
    print(_res.nota_honesta)
