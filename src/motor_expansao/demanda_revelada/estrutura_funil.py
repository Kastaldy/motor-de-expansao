"""BLK-ATR-03: testar a ESTRUTURA de leitura da atratividade -- matriz vs score composto.

Testa OUT-OF-FOLD (DEC-008: k-fold 5x5 repetido vs baseline da media; IC95 bootstrap seed=42;
R2 in-sample BANIDO do veredito) se um SCORE COMPOSTO dos 3 eixos de atratividade prevê a
demanda paga OBSERVADA (`membros`, camada de Demanda Revelada / BLK-TP-01) MELHOR que cada
eixo isolado e melhor que a MATRIZ (default = 3 eixos separados). Emite veredito honesto:
GO-composto SOMENTE se o composto bate o baseline (IC>0) E vence o melhor eixo isolado
materialmente (> LIMIAR_GANHO_MATERIAL) E nao e redundante (< LIMIAR_REDUNDANCIA); caso
contrario -> default = MATRIZ. NO-GO (matriz) e resultado VALIDO (DEC-008).

Os 3 eixos (mapa `EIXOS`):
  - sociodemo -> `score_priorizacao`     (composto do M1 renda 0.40 + pop 0.60; LIDO, nunca alterado)
  - mercado   -> `score_oportunidade_residual`
  - disputa   -> `share_captura_huff`     (INVERTIDO: 1 - share; mais share => menos oportunidade)
Eixo de AUDITORIA (fora do composto): `score_setor_2022_calibrado` (censitario).

GUARDRAILS (DEC-001/DEC-008/DEC-009/DEC-012; CLAUDE.md §5):
  - READ-ONLY sobre o M1: NAO recalcula `score_priorizacao`/`hex_score_estrutural`/pesos
    (renda=0.40/pop=0.60); NAO toca carteira/plano/artefatos oficiais; NAO altera a formula do
    residual/atratividade nem regenera `hexagonos_mercado_mapeado.parquet`/derivados.
  - DEC-008: k-fold repetido SEMPRE vs baseline da media; R2 in-sample so campo de auditoria
    rotulado (nunca no veredito); IC95 + flag de extrapolacao; NO-GO/matriz e resultado VALIDO.
  - DEC-009: a demanda (`membros`) e ALVO OBSERVADO; PROIBIDO usar `membros`/qualquer coluna da
    demanda como preditor geografico de magnitude ou ajuste do score.
  - DEC-012: pacote `demanda_revelada/` DISJUNTO -- este modulo NUNCA importa de `pipelines/`,
    `pipelines/m1/`, `censo_*`, `dashboard/`, `api` nem `config.py` raiz; sem PII (zero coluna
    de COLUNAS_PII_PROIBIDAS em frame/saida/relatorio); fonte real (NAO_ABRA/) nunca tocada;
    testes so com fixture sintetica. O gate ATR-02 e REPLICADO inline (constantes locais),
    NAO importado de `pipelines/pop_corte.py`/`calcular_colunas_mercado.py`.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import Ridge
from sklearn.model_selection import RepeatedKFold

# Reuso de infraestrutura das camadas paralelas irmas `dimensionamento/` e `demanda_revelada/`
# (NAO e M1/censo/dashboard/api/config raiz -- precedente de backtest_tp05.py/calibracao_residual.py).
from motor_expansao.dimensionamento.aderencia import (
    ALPHA_GRID,
    LIMIAR_R2_GO,
    _r2_loo_para_alpha,
)
from motor_expansao.dimensionamento.backtest_dim import _r2, _rmse

# Rede de seguranca anti-PII tambem neste modulo de analise.
from .contrato import COLUNAS_PII_PROIBIDAS

_logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Parametros de validacao honesta (mesma seed dos precedentes BLK-TP-05/06)
# --------------------------------------------------------------------------- #
N_SPLITS_PADRAO: int = 5
N_SPLITS_PEQUENO: int = 10  # fallback quando n < N_PISO_KFOLD
N_REPEATS: int = 5
N_PISO_KFOLD: int = 200  # abaixo disso, k=10
N_PISO_LOO: int = 30  # abaixo disso, LOO + flag_extrapolacao_padrao_global
N_BOOTSTRAP: int = 2000  # reamostras do IC (seed fixa)
SEED: int = 42
N_MIN_MODELO: int = 3
# Universo de hexes do Motor (DEC-003; usado so para a % de cobertura do join, nao e M1).
_UNIVERSO_MOTOR: int = 1_542_531

# --------------------------------------------------------------------------- #
# Constantes do veredito (item 1 do plano)
# --------------------------------------------------------------------------- #
# O composto so e GO-material se R2_oof_composto > max(R2_oof_eixo_isolado) + esta margem.
LIMIAR_GANHO_MATERIAL: float = 0.01
# O composto e REDUNDANTE (nao agrega) se pearson(pred_composto, pred_melhor_eixo) >= isto.
LIMIAR_REDUNDANCIA: float = 0.95

# Replica LOCAL dos limiares do gate de atratividade ATR-02. Fonte: `POP_MIN_SAM_GATE` (=5000) e
# `RENDA_PER_CAPITA_MIN_ATR` (=1500) de `pipelines/calcular_colunas_mercado.py`. NAO importado
# (mantem o pacote `demanda_revelada/` disjunto de `pipelines/`); valores estaveis vivem numa DEC.
POP_MIN_GATE_ATR: int = 5000
RENDA_PC_MIN_GATE_ATR: float = 1500.0

# Mapa nome_do_eixo -> coluna. Os 3 eixos QUE COMPOEM o composto.
EIXOS: dict[str, str] = {
    "sociodemo": "score_priorizacao",
    "mercado": "score_oportunidade_residual",
    "disputa": "share_captura_huff",  # INVERTIDO (1 - share) antes de normalizar
}
# Eixo de auditoria (censitario): entra SO como eixo isolado, FORA do composto.
EIXO_AUDITORIA: str = "score_setor_2022_calibrado"

# Nomes de feature normalizada (rotulos, nao PII). Ordem fixa do composto.
FEAT_SOCIODEMO = "eixo_sociodemo_norm"
FEAT_MERCADO = "eixo_mercado_norm"
FEAT_DISPUTA = "eixo_disputa_norm"
FEAT_AUDITORIA = "eixo_censitario_norm"
FEATURES_COMPOSTO: tuple[str, ...] = (FEAT_SOCIODEMO, FEAT_MERCADO, FEAT_DISPUTA)

# Rotulo literal exigido para o R2 in-sample (testado por substring -- NAO alterar o texto).
_ROTULO_INSAMPLE = "apenas auditoria -- NAO usar como desempenho"


# --------------------------------------------------------------------------- #
# Dataclasses de resultado
# --------------------------------------------------------------------------- #
@dataclass
class ModeloOOF:
    """Metricas out-of-fold de UM modelo (baseline, eixo isolado ou composto)."""

    nome: str
    features: tuple[str, ...]
    n: int
    r2_oof: float
    ic95_r2: tuple[float, float]
    rho_oof: float
    ic95_rho: tuple[float, float]
    rmse_oof: float
    r2_insample: float  # SO auditoria (DEC-008); nunca no veredito
    alpha: float
    y_pred_oof: np.ndarray = field(repr=False, default_factory=lambda: np.empty(0))
    coefs: dict[str, float] = field(default_factory=dict)


@dataclass
class EstruturaFunilResult:
    """Veredito honesto matriz vs composto + metricas de todos os modelos."""

    modelos: dict[str, ModeloOOF]
    """nome -> ModeloOOF (baseline, sociodemo, mercado, disputa, censitario, composto, pesos_iguais)."""

    nome_melhor_eixo: str
    r2_melhor_eixo: float
    ganho_material: float
    redundante: bool
    veredito: str  # "GO-composto" | "matriz"
    motivo_veredito: str
    coefs_composto: dict[str, float]

    spearman_bruta: dict[str, tuple[float, float]]
    correlacoes_cruzadas: dict[str, float]
    subanalise_competitivos: dict[str, float]

    n_join: int
    n_pos_gate: int
    pct_retido_gate: float
    pct_cobertura_universo: float
    pct_huff_disponivel: float

    metodo_validacao: str
    flag_extrapolacao_padrao_global: bool
    concentracao_uf: dict[str, float]

    nota_honesta: str = field(default="")

    @property
    def go(self) -> bool:
        """True se o veredito recomenda o SCORE COMPOSTO (default operacional = matriz)."""
        return self.veredito == "GO-composto"


# --------------------------------------------------------------------------- #
# Gate ATR-02 replicado inline (pop >= 5000 AND renda_per_capita >= 1500)
# --------------------------------------------------------------------------- #
def _normalized_join_quality(df: pd.DataFrame) -> pd.Series:
    """Replica de `pop_corte.normalized_join_quality` (puro, sem import de pipelines)."""
    if "qualidade_join_uf" not in df.columns:
        return pd.Series("", index=df.index, dtype="object")
    return (
        df["qualidade_join_uf"]
        .astype(object)
        .where(df["qualidade_join_uf"].notna(), "")
        .astype(str)
        .str.upper()
    )


def _has_censo_signal(df: pd.DataFrame) -> pd.Series:
    """Replica de `pop_corte.has_censo_signal`."""
    signal = pd.Series(False, index=df.index)
    if "flag_censo_disponivel" in df.columns:
        signal |= df["flag_censo_disponivel"].fillna(False).astype(bool)
    if "score_setor_2022_calibrado" in df.columns:
        signal |= df["score_setor_2022_calibrado"].notna()
    return signal


def _derive_confianca_geografica(df: pd.DataFrame) -> pd.Series:
    """Replica de `pop_corte.derive_confianca_geografica` (granular vs municipal)."""
    if "confianca_geografica" in df.columns:
        base = (
            df["confianca_geografica"]
            .astype(object)
            .where(df["confianca_geografica"].notna(), "municipal")
            .astype(str)
            .str.lower()
        )
        base = base.where(base.isin(["granular", "municipal"]), "municipal")
    else:
        base = pd.Series("municipal", index=df.index, dtype="object")
    granular_mask = _normalized_join_quality(df).isin(["A", "B"]) & _has_censo_signal(df)
    return pd.Series(
        np.where(granular_mask, "granular", base), index=df.index, dtype="object"
    )


def _derive_populacao_corte(df: pd.DataFrame) -> pd.Series:
    """Replica da regua de `pop_corte.derive_pop_cut_columns` (so a coluna de corte).

    populacao_corte_hex = pop_total_setor_2022 quando o hex e `granular` e tem setor;
    fallback = pop_total (ou populacao_proxy legado). Coercao numerica.
    """
    if "populacao_corte_hex" in df.columns:
        return pd.to_numeric(df["populacao_corte_hex"], errors="coerce")

    confianca = _derive_confianca_geografica(df)
    is_granular = confianca.eq("granular")
    has_setor = "pop_total_setor_2022" in df.columns
    has_pop_total = "pop_total" in df.columns
    has_proxy = "populacao_proxy" in df.columns

    if has_pop_total:
        pop_municipal = df["pop_total"]
    elif has_proxy:
        pop_municipal = df["populacao_proxy"]
    else:
        pop_municipal = pd.Series(pd.NA, index=df.index, dtype="Float64")

    if has_setor:
        use_setor = is_granular & df["pop_total_setor_2022"].notna()
        pop_val = df["pop_total_setor_2022"].where(use_setor, pop_municipal)
    else:
        pop_val = pop_municipal
    return pd.to_numeric(pop_val, errors="coerce")


def aplicar_gate_atratividade(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    """Aplica o gate ATR-02 INLINE e FILTRA para os viaveis.

    `flag_gate_atratividade = populacao_corte_hex >= 5000 AND renda_per_capita >= 1500`.
    Retorna (df_pos_gate, meta_gate) com n_pre_gate/n_pos_gate/pct_retido.
    """
    n_pre = int(len(df))
    pop_corte = _derive_populacao_corte(df)
    renda_pc = pd.to_numeric(df.get("renda_per_capita"), errors="coerce")
    flag = (pop_corte >= POP_MIN_GATE_ATR) & (renda_pc >= RENDA_PC_MIN_GATE_ATR)
    flag = flag.fillna(False)
    df_pos = df.loc[flag].copy()
    n_pos = int(len(df_pos))
    meta: dict[str, object] = {
        "n_pre_gate": n_pre,
        "n_pos_gate": n_pos,
        "pct_retido": float(100.0 * n_pos / n_pre) if n_pre else float("nan"),
    }
    return df_pos, meta


# --------------------------------------------------------------------------- #
# Normalizacao dos eixos (percentil nacional 0-100)
# --------------------------------------------------------------------------- #
def _percentil_0_100(serie: pd.Series) -> np.ndarray:
    """Percentil nacional 0-100 (rank fracionario) sobre a serie. NaN preservado."""
    valores = pd.to_numeric(serie, errors="coerce")
    return (valores.rank(pct=True) * 100.0).to_numpy(dtype=float)


def normalizar_eixos(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona os eixos normalizados 0-100 + a inversao do share e a flag de disputa.

    Percentil nacional (dentro do conjunto passado; coerente com "nacional" restrito ao universo
    modelado -- documentado no relatorio). O eixo `disputa` = percentil de (1 - share_captura_huff):
    mais share => menos oportunidade de disputa. `flag_huff_disponivel` = share < 1.0 (ha
    concorrente na janela). `membros` NUNCA e tocado (e o ALVO).
    """
    out = df.copy()

    if "score_priorizacao" in out.columns:
        out[FEAT_SOCIODEMO] = _percentil_0_100(out["score_priorizacao"])
    if "score_oportunidade_residual" in out.columns:
        out[FEAT_MERCADO] = _percentil_0_100(out["score_oportunidade_residual"])

    if "share_captura_huff" in out.columns:
        share = pd.to_numeric(out["share_captura_huff"], errors="coerce")
        out["flag_huff_disponivel"] = (share < 1.0).fillna(False)
        disputa_bruta = 1.0 - share
        out[FEAT_DISPUTA] = _percentil_0_100(disputa_bruta)
    else:
        out["flag_huff_disponivel"] = pd.Series(False, index=out.index)

    if EIXO_AUDITORIA in out.columns:
        out[FEAT_AUDITORIA] = _percentil_0_100(out[EIXO_AUDITORIA])

    return out


def _preparar_alvo(df: pd.DataFrame) -> np.ndarray:
    """y = log1p(membros) (cauda longa). `membros` e o ALVO (DEC-009)."""
    membros = pd.to_numeric(df.get("membros"), errors="coerce").to_numpy(dtype=float)
    return np.log1p(np.clip(membros, 0.0, None))


# --------------------------------------------------------------------------- #
# Nucleo k-fold repetido out-of-fold (portado de backtest_tp05.py)
# --------------------------------------------------------------------------- #
def _kfold_repetido_oof(
    X: np.ndarray, y: np.ndarray, alpha: float, *, n_splits: int
) -> tuple[np.ndarray, np.ndarray, float, float]:
    """K-fold repetido (out-of-fold) de um Ridge(alpha) vs baseline da media.

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
    """IC95 (2,5%; 97,5%) do R2(y, y_pred_oof) por bootstrap dos pares (reamostras sem var. descartadas)."""
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
    """IC95 (2,5%; 97,5%) do Spearman rho(y, y_pred_oof) por bootstrap dos pares."""
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
    """Spearman out-of-fold (predicoes oof vs alvo). NaN se sem variancia."""
    ok = np.isfinite(y) & np.isfinite(y_pred_oof)
    if ok.sum() < 3 or np.unique(y[ok]).size < 2 or np.unique(y_pred_oof[ok]).size < 2:
        return float("nan")
    rho, _p = spearmanr(y[ok], y_pred_oof[ok])
    return float(rho)


def _selecionar_alpha_e_oof(
    X: np.ndarray, y: np.ndarray, *, metodo: str
) -> tuple[float, np.ndarray, np.ndarray, float, float]:
    """Varre ALPHA_GRID, escolhe alpha por MENOR RMSE oof, retorna oof do melhor.

    `metodo` in {"kfold_5x5","kfold_10x5","loo"}. Retorna
    (alpha, y_pred_oof, y_pred_baseline_oof, r2_oof, rmse_oof).
    """
    melhor_alpha = float(ALPHA_GRID[0])
    melhor_rmse = float("inf")
    melhor_r2 = float("nan")
    melhor_pred = np.zeros(len(y), dtype=float)
    melhor_base = np.full(len(y), float(np.mean(y)) if len(y) else 0.0, dtype=float)

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


# --------------------------------------------------------------------------- #
# Avaliacao de um modelo out-of-fold
# --------------------------------------------------------------------------- #
def _avaliar_modelo(
    df: pd.DataFrame, y: np.ndarray, features: tuple[str, ...], *, nome: str
) -> ModeloOOF:
    """Avalia UM modelo (features -> log1p(membros)) out-of-fold.

    Limpa NaN/inf ANTES; N efetivo por modelo pode variar (censitario tem NaN). Retorna ModeloOOF
    com R2_oof/IC95, rho_oof/IC95, RMSE_oof, R2_insample (auditoria) e coefs finais.
    """
    cols = [df[f].to_numpy(dtype=float) for f in features]
    X_full = np.column_stack(cols) if cols else np.empty((len(y), 0))
    finito = np.isfinite(X_full).all(axis=1) & np.isfinite(y)
    X = X_full[finito]
    yy = y[finito]
    n = int(len(yy))

    vazio = (float("nan"), float("nan"))
    if n < N_MIN_MODELO or np.unique(yy).size < 2:
        return ModeloOOF(
            nome=nome, features=features, n=n, r2_oof=float("nan"), ic95_r2=vazio,
            rho_oof=float("nan"), ic95_rho=vazio, rmse_oof=float("nan"),
            r2_insample=float("nan"), alpha=float("nan"),
            y_pred_oof=np.full(n, np.nan), coefs={},
        )

    metodo = _metodo_validacao(n)
    alpha, y_pred_oof, _base, r2_oof, rmse_oof = _selecionar_alpha_e_oof(X, yy, metodo=metodo)

    rng = np.random.default_rng(SEED)
    ic95_r2 = _ic_bootstrap_r2(yy, y_pred_oof, rng)
    rng_rho = np.random.default_rng(SEED)
    ic95_rho = _ic_bootstrap_rho(yy, y_pred_oof, rng_rho)
    rho = _rho_oof(yy, y_pred_oof)

    reg = Ridge(alpha=alpha)
    reg.fit(X, yy)
    coefs = {f: float(c) for f, c in zip(features, reg.coef_, strict=True)}
    r2_insample = _r2(yy, reg.predict(X))  # SO auditoria (DEC-008)

    return ModeloOOF(
        nome=nome, features=features, n=n, r2_oof=float(r2_oof),
        ic95_r2=(float(ic95_r2[0]), float(ic95_r2[1])), rho_oof=float(rho),
        ic95_rho=(float(ic95_rho[0]), float(ic95_rho[1])), rmse_oof=float(rmse_oof),
        r2_insample=float(r2_insample), alpha=float(alpha), y_pred_oof=y_pred_oof, coefs=coefs,
    )


# --------------------------------------------------------------------------- #
# Correlacoes bivariadas + cruzadas
# --------------------------------------------------------------------------- #
def correlacoes(df: pd.DataFrame) -> tuple[dict[str, tuple[float, float]], dict[str, float]]:
    """Spearman bruto de cada eixo vs `membros` + correlacoes cruzadas entre eixos normalizados.

    Retorna (spearman_bruta, correlacoes_cruzadas). Reproduz os rhos do BO (sanity check).
    """
    alvo = pd.to_numeric(df.get("membros"), errors="coerce")
    mask = alvo.notna()
    y = alvo[mask].to_numpy(dtype=float)

    spearman: dict[str, tuple[float, float]] = {}
    for col in ("share_captura_huff", "score_priorizacao", "score_oportunidade_residual", EIXO_AUDITORIA):
        if col not in df.columns:
            spearman[col] = (float("nan"), float("nan"))
            continue
        x = pd.to_numeric(df[col], errors="coerce")[mask].to_numpy(dtype=float)
        ok = np.isfinite(x) & np.isfinite(y)
        if ok.sum() < 3 or np.unique(x[ok]).size < 2:
            spearman[col] = (float("nan"), float("nan"))
            continue
        rho, p = spearmanr(x[ok], y[ok])
        spearman[col] = (float(rho), float(p))

    cruzadas: dict[str, float] = {}
    pares = (
        ("mercado_x_disputa", FEAT_MERCADO, FEAT_DISPUTA),
        ("sociodemo_x_mercado", FEAT_SOCIODEMO, FEAT_MERCADO),
        ("sociodemo_x_disputa", FEAT_SOCIODEMO, FEAT_DISPUTA),
    )
    for rotulo, a, b in pares:
        if a not in df.columns or b not in df.columns:
            cruzadas[rotulo] = float("nan")
            continue
        xa = pd.to_numeric(df[a], errors="coerce").to_numpy(dtype=float)
        xb = pd.to_numeric(df[b], errors="coerce").to_numpy(dtype=float)
        ok = np.isfinite(xa) & np.isfinite(xb)
        if ok.sum() < 3 or np.unique(xa[ok]).size < 2 or np.unique(xb[ok]).size < 2:
            cruzadas[rotulo] = float("nan")
            continue
        rho, _p = spearmanr(xa[ok], xb[ok])
        cruzadas[rotulo] = float(rho)
    return spearman, cruzadas


def _concentracao_uf(df: pd.DataFrame, *, top: int = 3) -> dict[str, float]:
    """Top-N UF por % do df (caveat de vies). {} se `uf` ausente."""
    if "uf" not in df.columns or df.empty:
        return {}
    vc = (df["uf"].value_counts(normalize=True) * 100.0).round(1)
    return {str(k): float(v) for k, v in vc.head(top).items()}


def _subanalise_competitivos(df_pos_gate: pd.DataFrame, y: np.ndarray) -> dict[str, float]:
    """Roda eixo disputa isolado + composto SO onde `flag_huff_disponivel` (concorrente na janela)."""
    if "flag_huff_disponivel" not in df_pos_gate.columns:
        return {"n_competitivos": 0.0, "pct_competitivos": 0.0}
    mask = df_pos_gate["flag_huff_disponivel"].to_numpy(dtype=bool)
    n_comp = int(mask.sum())
    pct = float(100.0 * n_comp / len(df_pos_gate)) if len(df_pos_gate) else float("nan")
    out: dict[str, float] = {"n_competitivos": float(n_comp), "pct_competitivos": pct}
    if n_comp < N_MIN_MODELO:
        out["r2_oof_disputa_competitivos"] = float("nan")
        out["r2_oof_composto_competitivos"] = float("nan")
        return out
    sub = df_pos_gate.loc[mask]
    y_sub = y[mask]
    m_disp = _avaliar_modelo(sub, y_sub, (FEAT_DISPUTA,), nome="disputa_competitivos")
    m_comp = _avaliar_modelo(sub, y_sub, FEATURES_COMPOSTO, nome="composto_competitivos")
    out["r2_oof_disputa_competitivos"] = m_disp.r2_oof
    out["r2_oof_composto_competitivos"] = m_comp.r2_oof
    return out


# --------------------------------------------------------------------------- #
# Veredito honesto matriz vs composto
# --------------------------------------------------------------------------- #
def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    """Pearson entre duas predicoes oof (pontos finitos comuns). NaN se sem variancia."""
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 3 or np.unique(a[ok]).size < 2 or np.unique(b[ok]).size < 2:
        return float("nan")
    return float(np.corrcoef(a[ok], b[ok])[0, 1])


def _decidir_veredito(
    modelos: dict[str, ModeloOOF],
) -> tuple[str, str, float, str, float, bool]:
    """Decide GO-composto vs matriz (default).

    Retorna (veredito, nome_melhor_eixo, r2_melhor_eixo, motivo, ganho_material, redundante).
    GO-composto SOMENTE se: R2_oof_composto > LIMIAR_R2_GO E IC95_inf(R2) > 0 E
    ganho_material > LIMIAR_GANHO_MATERIAL E NOT redundante. Caso contrario -> matriz (VALIDO).
    """
    eixos_composto = ("sociodemo", "mercado", "disputa")
    candidatos = [
        (nome, modelos[nome].r2_oof)
        for nome in eixos_composto
        if nome in modelos and np.isfinite(modelos[nome].r2_oof)
    ]
    if candidatos:
        nome_melhor, r2_melhor = max(candidatos, key=lambda kv: kv[1])
    else:
        nome_melhor, r2_melhor = ("", float("nan"))

    comp = modelos.get("composto")
    if comp is None or not np.isfinite(comp.r2_oof):
        return ("matriz", nome_melhor, r2_melhor, "composto sem metricas validas", float("nan"), False)

    ganho = comp.r2_oof - r2_melhor if np.isfinite(r2_melhor) else float("nan")

    redundante = False
    if nome_melhor and nome_melhor in modelos:
        pred_melhor = modelos[nome_melhor].y_pred_oof
        if pred_melhor.shape == comp.y_pred_oof.shape and pred_melhor.size:
            corr = _pearson(comp.y_pred_oof, pred_melhor)
            redundante = bool(np.isfinite(corr) and corr >= LIMIAR_REDUNDANCIA)

    bate_baseline = comp.r2_oof > LIMIAR_R2_GO and np.isfinite(comp.ic95_r2[0]) and comp.ic95_r2[0] > 0.0
    vence_material = np.isfinite(ganho) and ganho > LIMIAR_GANHO_MATERIAL

    if bate_baseline and vence_material and not redundante:
        motivo = (
            f"composto bate baseline (R2_oof={comp.r2_oof:+.4f} > {LIMIAR_R2_GO}, IC95_inf="
            f"{comp.ic95_r2[0]:+.4f} > 0), vence o melhor eixo `{nome_melhor}` "
            f"(ganho={ganho:+.4f} > {LIMIAR_GANHO_MATERIAL}) e nao e redundante."
        )
        return ("GO-composto", nome_melhor, r2_melhor, motivo, float(ganho), redundante)

    faltas: list[str] = []
    if not bate_baseline:
        faltas.append(
            f"nao bate baseline (R2_oof={comp.r2_oof:+.4f}, limiar {LIMIAR_R2_GO}, IC95_inf="
            f"{comp.ic95_r2[0]:+.4f})"
        )
    if not vence_material:
        faltas.append(
            f"nao vence o melhor eixo `{nome_melhor}` materialmente (ganho={ganho:+.4f} <= "
            f"{LIMIAR_GANHO_MATERIAL})"
        )
    if redundante:
        faltas.append(f"redundante com `{nome_melhor}` (pearson pred >= {LIMIAR_REDUNDANCIA})")
    motivo = "default = MATRIZ: " + "; ".join(faltas) + ". NO-GO (matriz) e resultado VALIDO (DEC-008)."
    return ("matriz", nome_melhor, r2_melhor, motivo, float(ganho), redundante)


# --------------------------------------------------------------------------- #
# Orquestrador PURO (testavel com fixtures sinteticas)
# --------------------------------------------------------------------------- #
def avaliar_estrutura_funil(df_join: pd.DataFrame) -> EstruturaFunilResult:
    """Aplica gate ATR-02, normaliza eixos, roda modelos oof e decide matriz vs composto.

    Funcao PURA (sem I/O) exercida pelos testes. Recebe o frame ja joinado (demanda x mercado por
    hex_id). READ-ONLY sobre o M1 (DEC-001/009); pacote disjunto (DEC-012); sem PII.

    Raises
    ------
    ValueError
        Se nao houver hex viavel apos o gate, ou faltarem colunas obrigatorias.
    """
    obrig = ("hex_id", "membros", "share_captura_huff", "score_priorizacao", "score_oportunidade_residual")
    faltando = [c for c in obrig if c not in df_join.columns]
    if faltando:
        raise ValueError(f"Colunas obrigatorias ausentes no join: {faltando}")

    n_join = int(len(df_join))
    df_pos, meta_gate = aplicar_gate_atratividade(df_join)
    n_pos = int(meta_gate["n_pos_gate"])  # type: ignore[call-overload]
    if n_pos == 0:
        raise ValueError("Nenhum hex viavel apos o gate de atratividade -- nada a modelar.")

    df_norm = normalizar_eixos(df_pos)
    y = _preparar_alvo(df_norm)

    spearman, cruzadas = correlacoes(df_norm)

    modelos: dict[str, ModeloOOF] = {}
    modelos["baseline"] = ModeloOOF(
        nome="baseline", features=(), n=int(np.isfinite(y).sum()), r2_oof=0.0,
        ic95_r2=(0.0, 0.0), rho_oof=float("nan"), ic95_rho=(float("nan"), float("nan")),
        rmse_oof=float("nan"), r2_insample=0.0, alpha=float("nan"),
        y_pred_oof=np.full(len(y), float(np.nanmean(y)) if np.isfinite(y).any() else np.nan),
    )
    modelos["sociodemo"] = _avaliar_modelo(df_norm, y, (FEAT_SOCIODEMO,), nome="sociodemo")
    modelos["mercado"] = _avaliar_modelo(df_norm, y, (FEAT_MERCADO,), nome="mercado")
    modelos["disputa"] = _avaliar_modelo(df_norm, y, (FEAT_DISPUTA,), nome="disputa")
    if FEAT_AUDITORIA in df_norm.columns:
        modelos["censitario"] = _avaliar_modelo(df_norm, y, (FEAT_AUDITORIA,), nome="censitario_auditoria")
    modelos["composto"] = _avaliar_modelo(df_norm, y, FEATURES_COMPOSTO, nome="composto_ridge")

    # Composto pesos-iguais (auditoria): media simples dos 3 eixos normalizados como 1 feature.
    df_pi = df_norm.copy()
    df_pi["eixo_pesos_iguais"] = df_pi[list(FEATURES_COMPOSTO)].mean(axis=1)
    modelos["pesos_iguais"] = _avaliar_modelo(
        df_pi, y, ("eixo_pesos_iguais",), nome="composto_pesos_iguais_auditoria"
    )

    veredito, nome_melhor, r2_melhor, motivo, ganho, redundante = _decidir_veredito(modelos)

    pct_huff = (
        float(100.0 * df_norm["flag_huff_disponivel"].mean())
        if "flag_huff_disponivel" in df_norm.columns and len(df_norm)
        else float("nan")
    )
    subanalise = _subanalise_competitivos(df_norm, y)

    n_modelo = modelos["composto"].n
    result = EstruturaFunilResult(
        modelos=modelos,
        nome_melhor_eixo=nome_melhor,
        r2_melhor_eixo=float(r2_melhor),
        ganho_material=float(ganho),
        redundante=bool(redundante),
        veredito=veredito,
        motivo_veredito=motivo,
        coefs_composto=dict(modelos["composto"].coefs),
        spearman_bruta=spearman,
        correlacoes_cruzadas=cruzadas,
        subanalise_competitivos=subanalise,
        n_join=n_join,
        n_pos_gate=n_pos,
        pct_retido_gate=float(meta_gate["pct_retido"]),  # type: ignore[arg-type]
        pct_cobertura_universo=float(100.0 * n_join / _UNIVERSO_MOTOR),
        pct_huff_disponivel=pct_huff,
        metodo_validacao=_metodo_validacao(n_modelo),
        flag_extrapolacao_padrao_global=n_modelo < N_PISO_LOO,
        concentracao_uf=_concentracao_uf(df_norm),
    )
    result.nota_honesta = _nota_honesta(result)

    _logger.info(
        "EstruturaFunil: n_join=%d n_pos_gate=%d metodo=%s composto_r2=%.4f melhor_eixo=%s(%.4f) "
        "ganho=%.4f redundante=%s veredito=%s",
        n_join, n_pos, result.metodo_validacao, modelos["composto"].r2_oof, nome_melhor,
        r2_melhor, ganho, redundante, veredito,
    )
    return result


# --------------------------------------------------------------------------- #
# Nota honesta + relatorio
# --------------------------------------------------------------------------- #
def _nota_honesta(r: EstruturaFunilResult) -> str:
    """Mensagem legivel (PT, sem PII) com metricas, veredito e os confounds obrigatorios."""
    comp = r.modelos["composto"]
    if r.go:
        cab = (
            f"GO-composto: o score composto Ridge bate o baseline (R2_oof={comp.r2_oof:+.4f}, "
            f"IC95_inf={comp.ic95_r2[0]:+.4f} > 0), vence o melhor eixo isolado `{r.nome_melhor_eixo}` "
            f"(R2_oof={r.r2_melhor_eixo:+.4f}; ganho={r.ganho_material:+.4f} > {LIMIAR_GANHO_MATERIAL}) "
            "e nao e redundante. Adotar o composto e FOLLOW-UP com gate humano (fora deste bloco)."
        )
    else:
        cab = (
            f"MATRIZ (default honesto): {r.motivo_veredito} O composto NAO substitui a leitura "
            f"multi-eixo (matriz). composto R2_oof={comp.r2_oof:+.4f} IC95="
            f"[{comp.ic95_r2[0]:+.4f}, {comp.ic95_r2[1]:+.4f}]; melhor eixo `{r.nome_melhor_eixo}` "
            f"R2_oof={r.r2_melhor_eixo:+.4f}."
        )
    top_uf = ", ".join(f"{k} {v:.1f}%" for k, v in r.concentracao_uf.items()) or "n/d"
    return (
        "Estrutura de leitura da atratividade: MATRIZ vs SCORE COMPOSTO "
        "(BLK-ATR-03, k-fold repetido vs baseline)\n"
        "Alvo: log1p(membros) (demanda paga OBSERVADA); eixos: sociodemo(score_priorizacao), "
        "mercado(score_oportunidade_residual), disputa(1 - share_captura_huff).\n"
        f"Veredito: {cab}\n"
        f"  composto R2_oof = {comp.r2_oof:+.4f} | IC95 = [{comp.ic95_r2[0]:+.4f}, {comp.ic95_r2[1]:+.4f}]"
        f" | rho_oof = {comp.rho_oof:+.4f}\n"
        f"  melhor eixo isolado = {r.nome_melhor_eixo} (R2_oof = {r.r2_melhor_eixo:+.4f}) | "
        f"ganho_material = {r.ganho_material:+.4f} | redundante = {r.redundante}\n"
        f"  R2_insample do composto = {comp.r2_insample:+.4f} ({_ROTULO_INSAMPLE})\n"
        f"  n_join = {r.n_join} | n_pos_gate = {r.n_pos_gate} | % retido gate = {r.pct_retido_gate:.1f}% | "
        f"cobertura ~{r.pct_cobertura_universo:.2f}% do universo\n"
        f"  metodo_validacao = {r.metodo_validacao} | flag_global = {r.flag_extrapolacao_padrao_global} | "
        f"% huff disponivel = {r.pct_huff_disponivel:.1f}% | top-3 UF = {top_uf}\n"
        "Confounds obrigatorios (read-only, nao corrigidos):\n"
        "  1. Cobertura ~1% do universo de hexes do Motor (16.575 de ~1,54 M; DEC-012) -> camada "
        "de refino sobre metropoles, NAO validacao nacional.\n"
        "  2. Vies metropolitano do Sudeste (top-3 UF do join concentram ~metade da amostra) -> "
        "amostra nao representativa do Brasil.\n"
        "  3. Ruido de coords ~1 km na fonte -> o join res-7 (~5,16 km2) e proxy de ordem de "
        "grandeza; ruido atenua o sinal.\n"
        "  4. Vies de selecao da plataforma -> `membros` so existe onde ha adesao ao beneficio "
        "corporativo (selecao nao aleatoria); documentado, nao corrigido.\n"
        "  5. Multicolinearidade dos eixos (residual x disputa) -> Ridge trata; correlacoes "
        "cruzadas reportadas ANTES do modelo; teste de redundancia evita GO espurio.\n"
        "  6. share_captura_huff == 1.0 (monopolio local) na maioria dos hexes -> o eixo disputa "
        "vira percentil baixo (2 eixos efetivos no composto); sub-analise separada dos competitivos.\n"
        "  7. DEC-009: `membros` e ALVO OBSERVADO; PROIBIDO usar como preditor geografico de "
        "magnitude ou ajuste do score. Este bloco TESTA a ESTRUTURA de leitura, nao aplica nada.\n"
        "  8. Matriz e o DEFAULT honesto: o composto so e recomendado se vence material E nao e "
        "redundante E bate baseline; caso contrario, os 3 eixos seguem lidos separados.\n"
    )


def relatorio_estrutura_funil(result: EstruturaFunilResult) -> str:
    """String markdown legivel (PT, sem PII) com amostra, correlacoes, tabela de modelos e veredito."""

    def _f(v: float, nd: int = 4) -> str:
        return f"{v:.{nd}f}" if np.isfinite(v) else "n/d"

    def _ic(t: tuple[float, float]) -> str:
        return f"[{_f(t[0])}, {_f(t[1])}]"

    L: list[str] = []
    L.append("# Estrutura de leitura da atratividade: matriz vs score composto -- BLK-ATR-03")
    L.append("")
    L.append(
        "READ-ONLY sobre o M1 (DEC-001/DEC-008/DEC-009). Pacote disjunto (DEC-012). Sem PII "
        "(so contagens/metricas agregadas). A demanda (`membros`) e ALVO OBSERVADO; os 3 eixos "
        "sao PREDITORES. Este bloco TESTA a ESTRUTURA -- NAO altera formula/artefatos em producao. "
        "Default operacional = MATRIZ (3 eixos separados); composto so se vencer materialmente."
    )
    L.append("")
    L.append("## 1. Amostra + cobertura/vies + gate ATR-02")
    L.append("")
    L.append(f"- N do join inner (demanda x mercado por hex_id): **{result.n_join}**")
    L.append(
        f"- Gate ATR-02 (`populacao_corte_hex >= {POP_MIN_GATE_ATR}` E "
        f"`renda_per_capita >= {RENDA_PC_MIN_GATE_ATR:.0f}`): N pos-gate = **{result.n_pos_gate}** "
        f"(retido {result.pct_retido_gate:.1f}%)"
    )
    L.append(
        f"- Cobertura do universo do Motor (~1,54 M hexes): **~{result.pct_cobertura_universo:.2f}%** "
        "-> camada de refino sobre metropoles, NAO validacao nacional."
    )
    top_uf = ", ".join(f"{k} {v:.1f}%" for k, v in result.concentracao_uf.items()) or "n/d"
    L.append(f"- Concentracao (top-3 UF pos-gate): {top_uf} -> vies metropolitano do Sudeste.")
    L.append(f"- Metodo de validacao: `{result.metodo_validacao}` | flag_global = "
             f"{result.flag_extrapolacao_padrao_global}")
    L.append("")
    L.append("## 2. Normalizacao dos eixos + inversao do share + degradacao graciosa")
    L.append("")
    L.append(
        "- Cada eixo -> percentil nacional 0-100 (rank fracionario) DENTRO do conjunto viavel "
        "(percentil restrito ao universo modelado; documentado)."
    )
    L.append(
        "- Eixo `disputa` = percentil de `1 - share_captura_huff` (mais share => menos oportunidade "
        "de disputa; alinha com o rho negativo observado)."
    )
    L.append(
        f"- Degradacao graciosa: `flag_huff_disponivel` (share < 1.0) em **{_f(result.pct_huff_disponivel, 1)}%** "
        "dos hexes viaveis. Onde share=1.0 (monopolio local), o eixo disputa vira percentil baixo "
        "-> o composto opera com 2 eixos efetivos (documentado; sem perder linhas)."
    )
    L.append("")
    L.append("## 3. Correlacoes bivariadas (Spearman vs membros) + cruzadas")
    L.append("")
    L.append("| eixo bruto (vs membros) | rho | p |")
    L.append("| --- | ---: | ---: |")
    for feat, (rho, p) in result.spearman_bruta.items():
        L.append(f"| {feat} | {_f(rho, 3)} | {_f(p, 4)} |")
    L.append("")
    L.append("Correlacoes cruzadas entre eixos normalizados (multicolinearidade, ANTES do modelo):")
    L.append("")
    L.append("| par | rho |")
    L.append("| --- | ---: |")
    for par, rho in result.correlacoes_cruzadas.items():
        L.append(f"| {par} | {_f(rho, 3)} |")
    L.append("")
    L.append("## 4. Tabela comparativa dos modelos (out-of-fold)")
    L.append("")
    L.append("A MATRIZ = os 3 eixos isolados lidos separados (default). Vencer a matriz = o composto "
             "vencer o melhor eixo isolado materialmente.")
    L.append("")
    L.append("| modelo | n | R2_oof | IC95 R2 | rho_oof | IC95 rho | RMSE_oof | R2_insample (auditoria) |")
    L.append("| --- | ---: | ---: | :--- | ---: | :--- | ---: | ---: |")
    ordem = ["baseline", "sociodemo", "mercado", "disputa", "censitario", "composto", "pesos_iguais"]
    for chave in ordem:
        m = result.modelos.get(chave)
        if m is None:
            continue
        L.append(
            f"| {m.nome} | {m.n} | {_f(m.r2_oof)} | {_ic(m.ic95_r2)} | {_f(m.rho_oof)} | "
            f"{_ic(m.ic95_rho)} | {_f(m.rmse_oof)} | {_f(m.r2_insample)} |"
        )
    L.append("")
    L.append(f"R2 in-sample e {_ROTULO_INSAMPLE} (DEC-008): NUNCA entra no veredito.")
    L.append("")
    L.append("Coeficientes do composto Ridge (auditoria dos pesos aprendidos):")
    L.append("")
    L.append("| feature | coef |")
    L.append("| --- | ---: |")
    for feat, c in result.coefs_composto.items():
        L.append(f"| {feat} | {c:+.4f} |")
    L.append("")
    L.append("## 5. Sub-analise dos competitivos (share < 1.0)")
    L.append("")
    sc = result.subanalise_competitivos
    L.append(
        f"- N competitivos (concorrente na janela): {int(sc.get('n_competitivos', 0))} "
        f"({_f(sc.get('pct_competitivos', float('nan')), 1)}% dos viaveis)"
    )
    L.append(f"- R2_oof eixo disputa (so competitivos): {_f(sc.get('r2_oof_disputa_competitivos', float('nan')))}")
    L.append(f"- R2_oof composto (so competitivos): {_f(sc.get('r2_oof_composto_competitivos', float('nan')))}")
    L.append("")
    L.append("Nota: o eixo Huff/disputa e informativo APENAS onde ha concorrentes na janela.")
    L.append("")
    L.append("## 6. Veredito GO/NO-GO (matriz vs composto)")
    L.append("")
    L.append(f"**{result.veredito}** -- {result.motivo_veredito}")
    L.append("")
    L.append(
        f"Regra: GO-composto SOMENTE se `R2_oof_composto > {LIMIAR_R2_GO}` E `IC95_inf(R2) > 0` E "
        f"`ganho sobre o melhor eixo > {LIMIAR_GANHO_MATERIAL}` E `NOT redundante "
        f"(pearson pred < {LIMIAR_REDUNDANCIA})`. Caso contrario -> MATRIZ (default). NO-GO e "
        "resultado VALIDO (DEC-008)."
    )
    L.append("")
    L.append("## 7. Limitacoes / confounds")
    L.append("")
    L.append("```")
    L.append(result.nota_honesta.rstrip("\n"))
    L.append("```")
    L.append("")
    return "\n".join(L)


# Rede de seguranca anti-PII: nenhum nome de coluna proibida deve aparecer nas saidas.
def _assert_sem_pii_no_relatorio(texto: str) -> None:
    """Falha se qualquer coluna de COLUNAS_PII_PROIBIDAS aparecer como token isolado no texto.

    Word-boundary para nao casar substring de palavras PT legitimas (ex.: "id" em "medida").
    """
    baixo = texto.lower()
    presentes = {
        c for c in COLUNAS_PII_PROIBIDAS if re.search(rf"\b{re.escape(c.lower())}\b", baixo)
    }
    if presentes:  # pragma: no cover - rede de seguranca
        raise AssertionError(f"PII vazou no relatorio BLK-ATR-03: {presentes}")


def escrever_relatorio(result: EstruturaFunilResult, *, path: Path) -> None:
    """Materializa o relatorio markdown (gitignored, sem PII). NAO chamada em teste."""
    path = Path(path)
    texto = relatorio_estrutura_funil(result)
    _assert_sem_pii_no_relatorio(texto)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(texto, encoding="utf-8")
    _logger.info("relatorio BLK-ATR-03 escrito: %s", path)


# --------------------------------------------------------------------------- #
# Caminho de disco (NAO chamado em teste)
# --------------------------------------------------------------------------- #
def _carregar_join(dem_path: Path, mkt_path: Path) -> pd.DataFrame:  # pragma: no cover
    """Inner join por `hex_id` de demanda x mercado (so colunas agregadas; nunca PII)."""
    dem = pd.read_parquet(Path(dem_path), columns=["hex_id", "membros"])
    cols_mkt = [
        "hex_id", "score_priorizacao", "score_oportunidade_residual", "share_captura_huff",
        "score_setor_2022_calibrado", "renda_per_capita", "uf", "populacao_corte_hex",
        "confianca_geografica", "pop_total_setor_2022", "pop_total", "populacao_proxy",
        "qualidade_join_uf", "flag_censo_disponivel",
    ]
    import pyarrow.parquet as pq

    disponiveis = set(pq.ParquetFile(Path(mkt_path)).schema.names)
    mkt = pd.read_parquet(Path(mkt_path), columns=[c for c in cols_mkt if c in disponiveis])
    return dem.merge(mkt, on="hex_id", how="inner")


def executar(dem_path: Path, mkt_path: Path, out_path: Path) -> EstruturaFunilResult:  # pragma: no cover
    """Carrega, avalia e escreve o relatorio. Operacao CARA -- NAO rodar em teste/building."""
    df = _carregar_join(dem_path, mkt_path)
    result = avaliar_estrutura_funil(df)
    escrever_relatorio(result, path=Path(out_path))
    return result


__all__ = [
    "EstruturaFunilResult",
    "ModeloOOF",
    "avaliar_estrutura_funil",
    "aplicar_gate_atratividade",
    "normalizar_eixos",
    "correlacoes",
    "relatorio_estrutura_funil",
    "escrever_relatorio",
    "executar",
    "EIXOS",
    "EIXO_AUDITORIA",
    "LIMIAR_GANHO_MATERIAL",
    "LIMIAR_REDUNDANCIA",
    "POP_MIN_GATE_ATR",
    "RENDA_PC_MIN_GATE_ATR",
    "N_BOOTSTRAP",
    "SEED",
]


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    _res = executar(
        Path("data/staging/demanda_revelada_h3.parquet"),
        Path("data/staging/hexagonos_mercado_mapeado.parquet"),
        Path("data/analysis/estrutura_funil.md"),
    )
    print(_res.nota_honesta)
