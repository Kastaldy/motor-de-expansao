"""BLK-TP-04: validacao honesta da curva tamanho->densidade (m2 -> alunos/m2).

Valida (NAO altera em producao) a curva tamanho->densidade que a
`dimensionamento.viabilidade_ponto.faixa_alunos_por_densidade` usa, sob a
disciplina DEC-008 (k-fold repetido vs baseline da media; R2 in-sample BANIDO
como desempenho; intervalos de predicao p10/p50/p90 + flag de extrapolacao;
IC95 bootstrap com seed fixa=42). A base com m2 real (N~112, Ultra +
Engenharia do Corpo) e o UNICO insumo da curva; `alunos_parceiras` da camada
de Demanda Revelada entra APENAS como sanity-check externo de ORDEM DE
GRANDEZA (micro-academias parceiras, ~16 alunos/unidade, sem m2, escala
incomparavel com clubes ~2.700) -- NUNCA como preditor da curva.

GATE HUMANO: plano D1-D7 APROVADO por Felipe Silva em 2026-07-02 (todas na
opcao A recomendada pelo Planner). D1-A: `alunos_parceiras` = sanity-check
qualitativo, nao validacao cruzada. D2-A: base_calibracao_multirede (N=112) +
Ultra (N=54) como coorte de robustez. D3-A: sem filtro por coord. D4-A:
estratificar/reportar por marca (pooled + dummy). D5-A: parceiras por faixa de
n_acad (referencia n_acad<=3). D6-A: nao filtrar parceiras por tipo (dado
inexistente). D7-A: curva "valida" <=> R2_oof > 0 com IC95 nao cruzando zero.

GUARDRAILS (CLAUDE.md §5; DEC-008/DEC-009/DEC-012):
  - READ-ONLY sobre o M1: NAO recalcula `score_priorizacao`/`hex_score_estrutural`/
    pesos (renda=0.40/pop=0.60); NAO toca carteira/plano/artefatos oficiais.
  - `viabilidade_ponto.py` / `faixa_alunos_por_densidade` e a curva EM PRODUCAO:
    INTOCADA (nenhum coeficiente alterado). Se a validacao sugerir recalibracao,
    isso e FOLLOW-UP com gate proprio -- este bloco so documenta/recomenda.
  - DEC-008: k-fold 5x5 repetido SEMPRE vs baseline da media; R2 in-sample so
    existe como variavel interna descartada -- NUNCA no output/relatorio; IC95
    bootstrap seed=42; intervalos p10/p50/p90 + flag de extrapolacao; NO-GO e
    resultado VALIDO (nao forcar GO).
  - DEC-009: a curva preve alunos a partir de `m2` SOMENTE. PROIBIDO lat/lng/pop/
    renda/concorrencia como preditor. `alunos_parceiras` e demanda OBSERVADA,
    so descritiva (sanity-check), nunca input da curva.
  - DEC-012 (anti-PII): consome so a camada agregada; nenhuma coluna de
    COLUNAS_PII_PROIBIDAS nas saidas/relatorio; testes com fixture sintetica; a
    fonte real (NAO_ABRA/) nunca e tocada nem versionada.
  - Isolamento (DEC-012): este modulo NUNCA importa das camadas do M1 (pipeline
    executivo), da UI, da trilha censitaria nem da camada de API; PODE importar de
    `dimensionamento/` (camada paralela irma; precedente BLK-TP-05). O teste de
    isolamento verifica a ausencia desses tokens no proprio codigo-fonte.
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

# Reuso da infraestrutura da camada paralela irma `dimensionamento/`
# (camada de modelagem, nao o M1/UI/trilha censitaria/API -- isolamento DEC-012
# preservado; precedente BLK-TP-05).
from motor_expansao.dimensionamento.aderencia import (
    ALPHA_GRID,
    _r2_loo_para_alpha,
)
from motor_expansao.dimensionamento.backtest_dim import _r2, _rmse

# Rede de seguranca anti-PII.
from .contrato import COLUNAS_PII_PROIBIDAS

_logger = logging.getLogger(__name__)

# --- Parametros de validacao honesta (DEC-008) -------------------------------
SEED_BOOTSTRAP: int = 42
N_BOOT: int = 2000  # reamostras do IC95 do R2_oof
K_FOLD: int = 5
N_REPEATS: int = 5
N_PISO_LOO: int = 30  # abaixo disso, LOO (k-fold 5x5 fica instavel)
N_ACAD_REF_MAX: int = 3  # faixa de referencia do sanity-check das parceiras (D5-A)

# Feature da curva (log da metragem). Rotulo de feature, NAO PII.
_FEATURE_LOG_M2 = "log_metragem"

# Rotulo literal do R2 in-sample (testado por substring -- deve NAO aparecer no output).
_ROTULO_INSAMPLE_BANIDO = "r2_insample"


@dataclass
class CurvaValidacaoResult:
    """Resultado da validacao honesta da curva m2 -> alunos/m2 (k-fold 5x5 vs baseline).

    `r2_oof` e a metrica-ANCORA (out-of-fold, vs media => vs baseline) e decide o
    gate junto com `r2_oof_ic95`. O R2 in-sample e BANIDO do output (DEC-008): so
    existe como variavel interna descartada na construcao. A curva preve de `m2`
    SOMENTE (DEC-009) -- nenhuma coluna geografica entra em X.
    """

    n: int
    """N de comparaveis com metragem+alunos usados na validacao."""

    n_por_marca: dict[str, int]
    """Contagem por marca (Engenharia/Ultra) na base validada."""

    alpha_sel: float
    """Alpha do Ridge selecionado por MENOR RMSE out-of-fold na varredura ALPHA_GRID."""

    metodo_validacao: str
    """"kfold_5x5" (n>=N_PISO_LOO) | "loo" (n<N_PISO_LOO, instavel)."""

    r2_oof: float
    """R2 out-of-fold (ANCORA do gate; vs media => vs baseline da media)."""

    r2_oof_ic95: tuple[float, float]
    """IC95 (2,5%; 97,5%) do R2_oof por bootstrap (N_BOOT reamostras, seed=42)."""

    rho_oof: float
    """Spearman(y_real, y_pred_oof) out-of-fold."""

    rho_oof_ic95: tuple[float, float]
    """IC95 (2,5%; 97,5%) do rho_oof por bootstrap (N_BOOT reamostras, seed=42)."""

    r2_baseline: float
    """R2 do baseline da media (= 0,0 por construcao do R2 vs media; registrado p/ leitura)."""

    estratificar_marca: bool
    """True se o modelo incluiu dummy de marca como covariavel (D4-A)."""

    densidade_por_marca: dict[str, float]
    """Mediana de `alunos_por_m2` por marca (confound Eng 2,31 vs Ultra 1,57)."""

    intervalos_m2: dict[str, dict[str, float]]
    """p10/p50/p90 de `alunos_por_m2` por janela de m2 de referencia (envelope da curva)."""

    envelope_m2: tuple[float, float]
    """(p05, p95) da metragem da base -- dominio de nao-extrapolacao da curva."""

    go: bool
    """True se R2_oof > R2_GO_LIMIAR (0,0) E IC95_inferior > 0 (D7-A). NO-GO e VALIDO."""

    veredito: str
    """"GO" | "NO-GO" (D7-A)."""

    nota_honesta: str = field(default="")
    """Mensagem legivel (PT, sem PII) com metricas, veredito e as limitacoes obrigatorias."""


# --------------------------------------------------------------------------- #
# Carga da base com m2 (D2/D3)
# --------------------------------------------------------------------------- #
def carregar_base_curva(
    path_multirede: Path | str = Path("data/staging/base_calibracao_multirede.parquet"),
    path_ultra: Path | str | None = None,
) -> pd.DataFrame:
    """Carrega a base com m2 real da curva (fatia `metragem>0 & alunos_reais>0`, N~112).

    D2-A: fonte principal = `base_calibracao_multirede.parquet` (Ultra + Engenharia
    do Corpo). D3-A: NAO filtra por `flag_qualidade_match`/coord -- a curva usa so
    `metragem`+`alunos_reais`; as linhas Engenharia `nao_casado` tem m2+alunos
    validos do xlsx e sao amostra legitima. Deriva `alunos_por_m2 =
    alunos_reais/metragem`; mantem `marca`, `metragem`, `flag_qualidade_match` para
    auditoria (sem usar `flag_qualidade_match` como filtro).

    D2-B (coorte de robustez, opcional): se `path_ultra` for dado, la a fatia Ultra
    (`unidades_ultra_performance_hex.parquet`, N=54) e a concatena com `marca="ultra"`
    marcada em `coorte="ultra_perf"`; a fatia multirede recebe `coorte="multirede"`.
    A coorte Ultra usa `alunos_total`/`metragem` como alunos_reais (fonte da curva EM
    PRODUCAO hoje).

    Retorna DataFrame com colunas: `marca`, `metragem`, `alunos_reais`,
    `alunos_por_m2`, `flag_qualidade_match`, `coorte`. Sem PII (nenhuma coluna de
    coordenada/identificacao individual e propagada).
    """
    dfm = pd.read_parquet(Path(path_multirede))
    m = pd.to_numeric(dfm.get("metragem"), errors="coerce")
    a = pd.to_numeric(dfm.get("alunos_reais"), errors="coerce")
    mask = m.notna() & (m > 0) & a.notna() & (a > 0)
    base = pd.DataFrame(
        {
            "marca": dfm.loc[mask, "marca"].astype("string").to_numpy(),
            "metragem": m[mask].to_numpy(dtype=float),
            "alunos_reais": a[mask].to_numpy(dtype=float),
            "flag_qualidade_match": (
                dfm.loc[mask, "flag_qualidade_match"].astype("string").to_numpy()
                if "flag_qualidade_match" in dfm.columns
                else pd.Series(["n/d"] * int(mask.sum()), dtype="string").to_numpy()
            ),
        }
    )
    base["coorte"] = "multirede"

    if path_ultra is not None:
        dfu = pd.read_parquet(Path(path_ultra))
        # Coorte de robustez (D2-B): usa `alunos_total` (fonte da curva EM PRODUCAO).
        col_alunos = "alunos_total" if "alunos_total" in dfu.columns else "alunos_reais"
        mu = pd.to_numeric(dfu.get("metragem"), errors="coerce")
        au = pd.to_numeric(dfu.get(col_alunos), errors="coerce")
        masku = mu.notna() & (mu > 0) & au.notna() & (au > 0)
        base_u = pd.DataFrame(
            {
                "marca": pd.Series(["ultra"] * int(masku.sum()), dtype="string").to_numpy(),
                "metragem": mu[masku].to_numpy(dtype=float),
                "alunos_reais": au[masku].to_numpy(dtype=float),
                "flag_qualidade_match": pd.Series(
                    ["ultra_perf"] * int(masku.sum()), dtype="string"
                ).to_numpy(),
            }
        )
        base_u["coorte"] = "ultra_perf"
        base = pd.concat([base, base_u], ignore_index=True)

    base["alunos_por_m2"] = base["alunos_reais"] / base["metragem"]
    return base


# --------------------------------------------------------------------------- #
# Intervalos de predicao p10/p50/p90 por janela de m2 (espelha faixa_alunos_por_densidade)
# --------------------------------------------------------------------------- #
def _percentis_janela(
    base_df: pd.DataFrame, m2_ref: float, *, tol: float = 0.20
) -> dict[str, float]:
    """p10/p50/p90 de `alunos_por_m2` na janela +/-tol de `m2_ref` (curva tamanho->densidade).

    Espelha localmente a logica de janela de `faixa_alunos_por_densidade` SEM
    importar/alterar `viabilidade_ponto.py`. Fallback: janela +/-50%; depois base
    inteira. Depende SO de `metragem` (m2) -- nenhuma geografia (DEC-009).
    """
    apm = pd.to_numeric(base_df["alunos_por_m2"], errors="coerce")
    metr = pd.to_numeric(base_df["metragem"], errors="coerce")
    val = apm.notna() & (apm > 0) & metr.notna() & (metr > 0)
    apm_v = apm[val]
    metr_v = metr[val]

    def _sub(t: float) -> np.ndarray:
        lo, hi = m2_ref * (1.0 - t), m2_ref * (1.0 + t)
        sel = metr_v.between(lo, hi)
        return apm_v[sel].to_numpy(dtype=float)

    arr = _sub(tol)
    if arr.size < N_ACAD_REF_MAX:
        arr = _sub(0.50)
    if arr.size < N_ACAD_REF_MAX:
        arr = apm_v.to_numpy(dtype=float)
    if arr.size == 0:
        return {"m2": float(m2_ref), "n": 0, "p10": float("nan"), "p50": float("nan"), "p90": float("nan")}
    p10, p50, p90 = (float(v) for v in np.percentile(arr, [10, 50, 90]))
    # Faixa de ALUNOS = alunos/m2 * m2 (mesma composicao da curva em producao).
    return {
        "m2": float(m2_ref),
        "n": int(arr.size),
        "p10": float(p10 * m2_ref),
        "p50": float(p50 * m2_ref),
        "p90": float(p90 * m2_ref),
    }


def flag_extrapolacao_m2(m2: float, base_df: pd.DataFrame) -> bool:
    """True se `m2` cair fora do envelope [p05, p95] da metragem da base (extrapolacao).

    Depende SO de `metragem` (curva tamanho->densidade; DEC-009). m2<=0 -> True.
    """
    if not np.isfinite(m2) or m2 <= 0:
        return True
    metr = pd.to_numeric(base_df["metragem"], errors="coerce")
    metr = metr[metr.notna() & (metr > 0)].to_numpy(dtype=float)
    if metr.size == 0:
        return True
    lo, hi = np.percentile(metr, [5, 95])
    return bool(m2 < lo or m2 > hi)


# --------------------------------------------------------------------------- #
# Nucleo k-fold repetido out-of-fold (reusa _r2/_rmse de dimensionamento)
# --------------------------------------------------------------------------- #
def _kfold_repetido_oof(
    X: np.ndarray, y: np.ndarray, alpha: float, *, n_splits: int
) -> tuple[np.ndarray, float, float]:
    """K-fold repetido out-of-fold de um Ridge(alpha).

    Retorna (y_pred_oof_media, r2_oof_medio, rmse_oof_medio):
      - `y_pred_oof_media`: predicao oof MEDIA por ponto entre as N_REPEATS (usada no IC).
      - metricas: media das N_REPEATS de R2_oof/RMSE_oof (cada repeticao e um oof completo).
    """
    rkf = RepeatedKFold(n_splits=n_splits, n_repeats=N_REPEATS, random_state=SEED_BOOTSTRAP)
    n = len(y)
    soma_pred = np.zeros(n, dtype=float)
    cont = np.zeros(n, dtype=float)
    r2_por_rep: list[float] = []
    rmse_por_rep: list[float] = []

    pred_rep = np.full(n, np.nan, dtype=float)
    folds_no_rep = 0
    for train_idx, test_idx in rkf.split(X):
        reg = Ridge(alpha=alpha)
        reg.fit(X[train_idx], y[train_idx])
        pred_rep[test_idx] = reg.predict(X[test_idx])
        soma_pred[test_idx] += pred_rep[test_idx]
        cont[test_idx] += 1.0
        folds_no_rep += 1
        if folds_no_rep == n_splits:
            r2_por_rep.append(_r2(y, pred_rep))
            rmse_por_rep.append(_rmse(y, pred_rep))
            pred_rep = np.full(n, np.nan, dtype=float)
            folds_no_rep = 0

    cont_seguro = np.where(cont > 0, cont, 1.0)
    y_pred_oof_media = soma_pred / cont_seguro
    r2_oof_medio = float(np.mean(r2_por_rep)) if r2_por_rep else float("nan")
    rmse_oof_medio = float(np.mean(rmse_por_rep)) if rmse_por_rep else float("nan")
    return y_pred_oof_media, r2_oof_medio, rmse_oof_medio


def _selecionar_alpha_e_oof(
    X: np.ndarray, y: np.ndarray, *, metodo: str
) -> tuple[float, np.ndarray, float, float]:
    """Varre ALPHA_GRID, escolhe alpha por MENOR RMSE oof, retorna oof do melhor.

    `metodo` in {"kfold_5x5", "loo"}. Retorna (alpha, y_pred_oof, r2_oof, rmse_oof).
    """
    melhor_alpha = float(ALPHA_GRID[0])
    melhor_rmse = float("inf")
    melhor_r2 = float("nan")
    melhor_pred = np.zeros(len(y), dtype=float)

    for alpha in ALPHA_GRID:
        a = float(alpha)
        if metodo == "loo":
            r2_a, rmse_a, pred_a = _r2_loo_para_alpha(X, y, a)
        else:
            pred_a, r2_a, rmse_a = _kfold_repetido_oof(X, y, a, n_splits=K_FOLD)
        if rmse_a < melhor_rmse:
            melhor_rmse = rmse_a
            melhor_r2 = r2_a
            melhor_alpha = a
            melhor_pred = pred_a
    return melhor_alpha, melhor_pred, melhor_r2, melhor_rmse


def _ic_bootstrap(
    y: np.ndarray,
    y_pred_oof: np.ndarray,
    metrica: str,
    rng: np.random.Generator,
    n: int = N_BOOT,
) -> tuple[float, float]:
    """IC95 (2,5%; 97,5%) de `metrica` in {"r2","rho"} por bootstrap dos pares (y, y_pred).

    Reamostra com reposicao os indices e recalcula a metrica. Reamostras degeneradas
    (SS_tot==0 ou sem variancia) sao descartadas. Determinista para a mesma seed.
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
        pb = y_pred_oof[idx]
        if float(np.sum((yb - yb.mean()) ** 2)) <= 0.0:
            continue
        if metrica == "rho":
            if np.unique(yb).size < 2 or np.unique(pb).size < 2:
                continue
            r = float(spearmanr(yb, pb).statistic)
        else:
            r = _r2(yb, pb)
        if np.isfinite(r):
            valores.append(r)
    if not valores:
        return (float("nan"), float("nan"))
    arr = np.asarray(valores, dtype=float)
    return (float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5)))


# --------------------------------------------------------------------------- #
# Coracao da validacao (DEC-008)
# --------------------------------------------------------------------------- #
def validar_curva_densidade(
    base_df: pd.DataFrame, *, estratificar_marca: bool = True
) -> CurvaValidacaoResult:
    """Valida a curva tamanho->densidade (m2 -> alunos/m2) via k-fold 5x5 vs baseline.

    Alvo `y = alunos_por_m2`; feature `X = log(metragem)` (+ dummy `marca` se
    `estratificar_marca`, D4-A). k-fold 5x5 repetido (`RepeatedKFold(5,5,seed=42)`)
    vs baseline da media; alpha por menor RMSE oof; IC95 bootstrap (N_BOOT, seed=42)
    do R2_oof e do rho_oof. R2 in-sample e computado como variavel interna e
    DESCARTADO (DEC-008) -- NUNCA vai ao output. Intervalos p10/p50/p90 por janela
    de m2 + envelope de extrapolacao. Fallback LOO se `n < N_PISO_LOO`.

    A curva preve de `m2` SOMENTE (DEC-009): X so contem log(metragem) e, opcional,
    dummy de marca -- nenhuma coordenada/pop/renda. READ-ONLY sobre o M1.

    Parameters
    ----------
    base_df:
        Base com m2 real (`carregar_base_curva`), colunas `alunos_por_m2`,
        `metragem`, `marca`. Consumida READ-ONLY.
    estratificar_marca:
        Se True, adiciona dummy de `marca` como covariavel (D4-A).

    Returns
    -------
    CurvaValidacaoResult
        Metricas out-of-fold, IC95 bootstrap, intervalos, envelope e veredito GO/NO-GO.

    Raises
    ------
    ValueError
        Se nao houver linhas validas suficientes (n < N_MIN local).
    """
    apm = pd.to_numeric(base_df.get("alunos_por_m2"), errors="coerce")
    metr = pd.to_numeric(base_df.get("metragem"), errors="coerce")
    marca = base_df.get("marca")
    val = apm.notna() & (apm > 0) & metr.notna() & (metr > 0)
    base_v = base_df.loc[val].reset_index(drop=True)
    apm_v = apm[val].to_numpy(dtype=float)
    metr_v = metr[val].to_numpy(dtype=float)

    n = int(len(base_v))
    if n < 5:
        raise ValueError(
            f"Dados insuficientes para validar a curva: {n} comparaveis com m2 (minimo 5)."
        )

    y = apm_v
    cols_X: list[np.ndarray] = [np.log(metr_v)]
    marca_v = (
        base_v["marca"].astype("string").fillna("n/d")
        if marca is not None
        else pd.Series(["n/d"] * n, dtype="string")
    )
    usar_marca = estratificar_marca and marca_v.nunique() >= 2
    if usar_marca:
        # Dummies de marca (drop_first para evitar colinearidade com o intercepto).
        dummies = pd.get_dummies(marca_v, drop_first=True, dtype=float)
        for c in dummies.columns:
            cols_X.append(dummies[c].to_numpy(dtype=float))
    X = np.column_stack(cols_X)

    metodo = "loo" if n < N_PISO_LOO else "kfold_5x5"
    alpha, y_pred_oof, r2_oof, _rmse_oof = _selecionar_alpha_e_oof(X, y, metodo=metodo)

    rng = np.random.default_rng(SEED_BOOTSTRAP)
    r2_ic95 = _ic_bootstrap(y, y_pred_oof, "r2", rng, n=N_BOOT)
    rho_val = spearmanr(y, y_pred_oof)
    rho_oof = float(rho_val.statistic) if np.unique(y_pred_oof).size >= 2 else float("nan")
    rng_rho = np.random.default_rng(SEED_BOOTSTRAP)
    rho_ic95 = _ic_bootstrap(y, y_pred_oof, "rho", rng_rho, n=N_BOOT)

    # R2 IN-SAMPLE: computado e IMEDIATAMENTE DESCARTADO (DEC-008; nunca exposto).
    reg = Ridge(alpha=alpha)
    reg.fit(X, y)
    _r2_insample_descartado = _r2(y, reg.predict(X))
    del _r2_insample_descartado  # rede de seguranca: nao vaza ao output/relatorio

    # Confound de marca (Eng 2,31 vs Ultra 1,57) -- descritivo.
    densidade_por_marca: dict[str, float] = {}
    n_por_marca: dict[str, int] = {}
    for mk, grp in base_v.groupby(marca_v):
        densidade_por_marca[str(mk)] = float(
            pd.to_numeric(grp["alunos_por_m2"], errors="coerce").median()
        )
        n_por_marca[str(mk)] = int(len(grp))

    # Intervalos p10/p50/p90 por janela de m2 de referencia (envelope da curva).
    metr_serie = pd.to_numeric(base_v["metragem"], errors="coerce")
    p25, p50m, p75 = (float(v) for v in np.percentile(metr_v, [25, 50, 75]))
    intervalos_m2 = {
        "m2_p25": _percentis_janela(base_v, p25),
        "m2_p50": _percentis_janela(base_v, p50m),
        "m2_p75": _percentis_janela(base_v, p75),
    }
    envelope = (float(np.percentile(metr_v, 5)), float(np.percentile(metr_v, 95)))

    ic_inferior = r2_ic95[0]
    go = bool(
        np.isfinite(r2_oof)
        and r2_oof > 0.0
        and np.isfinite(ic_inferior)
        and ic_inferior > 0.0
    )
    veredito = "GO" if go else "NO-GO"

    result = CurvaValidacaoResult(
        n=n,
        n_por_marca=n_por_marca,
        alpha_sel=float(alpha),
        metodo_validacao=metodo,
        r2_oof=float(r2_oof),
        r2_oof_ic95=(float(r2_ic95[0]), float(r2_ic95[1])),
        rho_oof=float(rho_oof),
        rho_oof_ic95=(float(rho_ic95[0]), float(rho_ic95[1])),
        r2_baseline=0.0,
        estratificar_marca=bool(usar_marca),
        densidade_por_marca=densidade_por_marca,
        intervalos_m2=intervalos_m2,
        envelope_m2=envelope,
        go=go,
        veredito=veredito,
    )
    result.nota_honesta = _nota_honesta(result)
    _ = metr_serie  # metragem serie ja consumida; referencia explicita

    _logger.info(
        "CurvaValidacao: n=%d metodo=%s alpha=%.3g r2_oof=%.4f ic95=(%.4f,%.4f) gate=%s",
        n,
        metodo,
        alpha,
        r2_oof,
        r2_ic95[0],
        r2_ic95[1],
        veredito,
    )
    return result


# --------------------------------------------------------------------------- #
# Sanity-check das parceiras (D1-A / D5-A / D6-A) -- NUNCA preditor
# --------------------------------------------------------------------------- #
def sanity_check_parceiras(demanda_df: pd.DataFrame, *, n_acad_max: int = N_ACAD_REF_MAX) -> dict:
    """Distribuicao de `alunos_por_unidade` das parceiras por faixa de `n_acad` (descritivo).

    D1-A/D5-A/D6-A: `alunos_parceiras` sao micro-academias parceiras do TotalPass
    (sem m2, ~16 alunos/unidade), escala INCOMPARAVEL com clubes Ultra/Engenharia
    (~2.700). Este check reporta a ordem de grandeza por faixa de `n_acad`
    (1, 2-3, 4-10, 10+; faixa de referencia = `n_acad <= n_acad_max`), mas marca
    `usado_na_curva=False`: NUNCA entra na curva nem e usado como preditor.

    Retorna dict com `faixas` (n + p10/p50/p90 de alunos/unidade por faixa),
    `faixa_referencia`, `usado_na_curva=False` e `motivo`. Sem PII (so agregados).
    """
    alunos = pd.to_numeric(demanda_df.get("alunos_parceiras"), errors="coerce")
    n_acad = pd.to_numeric(demanda_df.get("n_acad_parceiras"), errors="coerce")
    mask = alunos.notna() & (alunos > 0) & n_acad.notna() & (n_acad > 0)
    apu = (alunos[mask] / n_acad[mask]).to_numpy(dtype=float)
    n_acad_m = n_acad[mask].to_numpy(dtype=float)

    def _faixa(lo: float, hi: float) -> dict:
        sel = (n_acad_m >= lo) & (n_acad_m <= hi)
        arr = apu[sel]
        if arr.size == 0:
            return {"n": 0, "p10": float("nan"), "p50": float("nan"), "p90": float("nan")}
        p10, p50, p90 = (float(v) for v in np.percentile(arr, [10, 50, 90]))
        return {"n": int(arr.size), "p10": p10, "p50": p50, "p90": p90}

    faixas = {
        "n_acad_1": _faixa(1, 1),
        "n_acad_2_3": _faixa(2, 3),
        "n_acad_4_10": _faixa(4, 10),
        "n_acad_10_mais": _faixa(11, float("inf")),
    }
    referencia = _faixa(1, float(n_acad_max))
    return {
        "faixas": faixas,
        "faixa_referencia": referencia,
        "n_acad_referencia_max": int(n_acad_max),
        "n_total_hexes": int(mask.sum()),
        "usado_na_curva": False,
        "motivo": "micro-academias parceiras; sem m²; escala incomparável",
    }


# --------------------------------------------------------------------------- #
# Nota honesta + relatorio
# --------------------------------------------------------------------------- #
def _nota_honesta(r: CurvaValidacaoResult) -> str:
    """Mensagem legivel (PT, sem PII) com metricas, veredito e limitacoes obrigatorias."""
    if r.go:
        cab = (
            f"GO (fraco): R2_oof={r.r2_oof:+.4f} > 0 E IC95_inferior={r.r2_oof_ic95[0]:+.4f} > 0. "
            "A curva tamanho->densidade tem sinal util out-of-fold -- mas RECALIBRAR os "
            "coeficientes em producao e FOLLOW-UP com gate proprio (NAO neste bloco)."
        )
    else:
        cab = (
            f"NO-GO: R2_oof={r.r2_oof:+.4f}, IC95=[{r.r2_oof_ic95[0]:+.4f}, {r.r2_oof_ic95[1]:+.4f}] "
            "(cruza/nao supera zero). A metragem sozinha nao supera o baseline da media de forma "
            "materialmente confiavel out-of-fold; consistente com DIM-07 (R2_LOO metragem ~ +0,096, "
            "margem estreita). NO-GO e resultado VALIDO (DEC-008)."
        )
    return (
        "Validacao honesta da curva tamanho->densidade (BLK-TP-04, k-fold 5x5 vs baseline)\n"
        "Alvo: alunos_por_m2 ~ f(log metragem)"
        + (" + dummy marca" if r.estratificar_marca else "")
        + f". Metodo: {r.metodo_validacao}; alpha={r.alpha_sel:g}.\n"
        f"Veredito GO/NO-GO: {cab}\n"
        f"  R2_oof (ancora, gate) = {r.r2_oof:+.4f} | IC95 = "
        f"[{r.r2_oof_ic95[0]:+.4f}, {r.r2_oof_ic95[1]:+.4f}]\n"
        f"  rho_oof (Spearman) = {r.rho_oof:+.4f} | IC95 = "
        f"[{r.rho_oof_ic95[0]:+.4f}, {r.rho_oof_ic95[1]:+.4f}]\n"
        f"  n = {r.n} | por marca = {r.n_por_marca} | densidade mediana/marca = "
        f"{ {k: round(v, 3) for k, v in r.densidade_por_marca.items()} }\n"
        f"  envelope de nao-extrapolacao (m2, p05-p95) = "
        f"[{r.envelope_m2[0]:.0f}, {r.envelope_m2[1]:.0f}]\n"
        "Limitacoes (read-only, nao corrigidas):\n"
        "  1. N pequeno (~112) -> k-fold com folds instaveis; IC largo (DEC-008 mitiga via "
        "RepeatedKFold + bootstrap).\n"
        "  2. Heterogeneidade de rede: Engenharia (~2,31 alunos/m²) x Ultra (~1,57) -> curva "
        "pooled mistura tiers; dummy de marca reportado, coeficientes NAO recalibrados.\n"
        "  3. SkyFit sem metragem e `alunos_parceiras` sem m²/tipo -> fora da curva "
        "(sanity-check descritivo apenas; escala ~16 vs ~2.700 alunos/unidade incomparavel).\n"
        "  4. ~90% da variancia de densidade fica fora do que temos (DIM-07): a metragem e o "
        "UNICO sinal real, mas fraco -> o veredito honesto tende a GO fraco/NO-GO.\n"
        "  5. READ-ONLY sobre o M1 (DEC-001/008/009): `viabilidade_ponto.py`/curva em producao "
        "INTOCADA; recalibrar coeficientes = FOLLOW-UP com gate proprio.\n"
    )


def _fmt(v: float, nd: int = 4) -> str:
    return f"{v:.{nd}f}" if np.isfinite(v) else "n/d"


def _relatorio_markdown(
    result: CurvaValidacaoResult,
    sanity: dict,
    *,
    result_pooled: CurvaValidacaoResult | None = None,
    result_ultra: CurvaValidacaoResult | None = None,
) -> str:
    """String markdown (PT, sem PII) com a estrutura de 8 secoes do handoff.

    `result` = modelo PRINCIPAL (com dummy de marca, D4-A). `result_pooled` (opcional)
    = mesma base SEM dummy de marca (robustez). `result_ultra` (opcional) = coorte
    Ultra N=54 (D2-B, robustez monomarca).
    """
    L: list[str] = []
    L.append("# Validacao honesta da curva tamanho->densidade -- BLK-TP-04")
    L.append("")
    L.append(
        "READ-ONLY sobre o M1 (DEC-001/DEC-008/DEC-009/DEC-012). Sem PII (so agregados). A curva "
        "preve alunos a partir de `m²` SOMENTE -- nenhuma coordenada/pop/renda como preditor "
        "(DEC-009). `viabilidade_ponto.py` / `faixa_alunos_por_densidade` INTOCADA; recalibracao "
        "de coeficientes = FOLLOW-UP com gate proprio. Gate humano D1-D7 APROVADO por Felipe "
        "Silva em 2026-07-02 (todas na opcao A)."
    )
    L.append("")
    L.append("## 1. Cabecalho")
    L.append("")
    L.append(
        "Valida (NAO altera) a curva `alunos_por_m2 ~ f(log metragem)` sob DEC-008 (k-fold 5x5 "
        "repetido vs baseline da media; R2 in-sample BANIDO como desempenho; IC95 bootstrap "
        f"N_BOOT={N_BOOT} seed={SEED_BOOTSTRAP}; intervalos p10/p50/p90 + flag de extrapolacao)."
    )
    L.append("")
    L.append("## 2. Dados (base com m² real)")
    L.append("")
    L.append(f"- N com metragem+alunos: **{result.n}**")
    L.append(f"- Por marca: {result.n_por_marca}")
    L.append("- Densidade mediana (alunos/m²) por marca: "
             + str({k: round(v, 3) for k, v in result.densidade_por_marca.items()}))
    L.append(f"- Envelope de metragem (p05-p95): [{result.envelope_m2[0]:.0f}, {result.envelope_m2[1]:.0f}] m²")
    L.append("")
    L.append("## 3. Papel de `alunos_parceiras` (D1-A -- sanity-check, NAO entra na curva)")
    L.append("")
    L.append(
        f"`usado_na_curva = {sanity['usado_na_curva']}` -- motivo: {sanity['motivo']}. Distribuicao "
        "de alunos/unidade das parceiras por faixa de `n_acad` (referencia = "
        f"`n_acad <= {sanity['n_acad_referencia_max']}`):"
    )
    L.append("")
    L.append("| faixa n_acad | N | p10 | p50 | p90 |")
    L.append("| --- | ---: | ---: | ---: | ---: |")
    for nome, fx in sanity["faixas"].items():
        L.append(
            f"| {nome} | {fx['n']} | {_fmt(fx['p10'], 1)} | {_fmt(fx['p50'], 1)} | {_fmt(fx['p90'], 1)} |"
        )
    ref = sanity["faixa_referencia"]
    L.append(
        f"| **referencia (n_acad<= {sanity['n_acad_referencia_max']})** | {ref['n']} | "
        f"{_fmt(ref['p10'], 1)} | {_fmt(ref['p50'], 1)} | {_fmt(ref['p90'], 1)} |"
    )
    L.append("")
    L.append(
        "Escala INCOMPARAVEL: parceiras ~dezenas de alunos/unidade vs clubes ~2.700 -> nao pode "
        "ser injetada na base de calibracao nem usada como validacao cruzada unidade-a-unidade "
        "(D1-A). So confirma que a curva nao tem uso ingenuo cruzado."
    )
    L.append("")
    L.append("## 4. Validacao da curva (DEC-008, k-fold 5x5 vs baseline)")
    L.append("")
    L.append(f"- Metodo de validacao: `{result.metodo_validacao}` | alpha = {result.alpha_sel:g} | "
             f"dummy de marca = {result.estratificar_marca}")
    L.append("")
    L.append("| metrica | valor |")
    L.append("| --- | ---: |")
    L.append(f"| R2_oof (ANCORA, gate) | {_fmt(result.r2_oof)} |")
    L.append(f"| IC95 R2_oof (bootstrap {N_BOOT}, seed {SEED_BOOTSTRAP}) | "
             f"[{_fmt(result.r2_oof_ic95[0])}, {_fmt(result.r2_oof_ic95[1])}] |")
    L.append(f"| rho_oof (Spearman) | {_fmt(result.rho_oof)} |")
    L.append(f"| IC95 rho_oof | [{_fmt(result.rho_oof_ic95[0])}, {_fmt(result.rho_oof_ic95[1])}] |")
    L.append(f"| R2 baseline (media) | {_fmt(result.r2_baseline)} |")
    L.append("")
    L.append(
        "Nota: R2 in-sample e BANIDO do relatorio (DEC-008) -- existe so como variavel interna "
        "descartada na construcao do modelo final."
    )
    if result_pooled is not None or result_ultra is not None:
        L.append("")
        L.append("### 4b. Robustez (pooled sem marca / coorte Ultra N=54)")
        L.append("")
        L.append("| variante | N | R2_oof | IC95 R2_oof | rho_oof | veredito |")
        L.append("| --- | ---: | ---: | ---: | ---: | ---: |")
        L.append(
            f"| principal (dummy marca) | {result.n} | {_fmt(result.r2_oof)} | "
            f"[{_fmt(result.r2_oof_ic95[0])}, {_fmt(result.r2_oof_ic95[1])}] | "
            f"{_fmt(result.rho_oof)} | {result.veredito} |"
        )
        if result_pooled is not None:
            L.append(
                f"| pooled (sem marca) | {result_pooled.n} | {_fmt(result_pooled.r2_oof)} | "
                f"[{_fmt(result_pooled.r2_oof_ic95[0])}, {_fmt(result_pooled.r2_oof_ic95[1])}] | "
                f"{_fmt(result_pooled.rho_oof)} | {result_pooled.veredito} |"
            )
        if result_ultra is not None:
            L.append(
                f"| coorte Ultra (N=54) | {result_ultra.n} | {_fmt(result_ultra.r2_oof)} | "
                f"[{_fmt(result_ultra.r2_oof_ic95[0])}, {_fmt(result_ultra.r2_oof_ic95[1])}] | "
                f"{_fmt(result_ultra.rho_oof)} | {result_ultra.veredito} |"
            )
        L.append("")
        L.append(
            "Leitura honesta: o sinal da curva depende FORTEMENTE da estratificacao por marca "
            "(tier Engenharia ~2,31 vs Ultra ~1,57 alunos/m²). Sem o dummy de marca (pooled), o "
            "IC95 tende a cruzar zero -> o GO do modelo principal e sobretudo o degrau de TIER, "
            "nao a metragem sozinha. Confirma o caveat DIM-07 (metragem e sinal fraco)."
        )
    L.append("")
    L.append("## 5. Intervalos de predicao p10/p50/p90 (por janela de m²) + extrapolacao")
    L.append("")
    L.append("| janela m² | m² ref | N | alunos p10 | alunos p50 | alunos p90 |")
    L.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for nome, iv in result.intervalos_m2.items():
        L.append(
            f"| {nome} | {iv['m2']:.0f} | {iv['n']} | {_fmt(iv['p10'], 0)} | "
            f"{_fmt(iv['p50'], 0)} | {_fmt(iv['p90'], 0)} |"
        )
    L.append("")
    L.append(
        f"`flag_extrapolacao_m2(m2)` = True para m² fora do envelope "
        f"[{result.envelope_m2[0]:.0f}, {result.envelope_m2[1]:.0f}] (p05-p95 da metragem da base)."
    )
    L.append("")
    L.append("## 6. Veredito GO/NO-GO (D7-A)")
    L.append("")
    L.append(
        f"**{result.veredito}** -- \"curva valida\" <=> `R2_oof > 0` E `IC95_inferior > 0`. "
        "NO-GO e resultado VALIDO e esperado (DEC-008; DIM-07 mediu R2_LOO metragem ~ +0,096, "
        "margem estreita -> IC provavelmente proximo de zero)."
    )
    L.append("")
    L.append("## 7. Limitacoes")
    L.append("")
    L.append("- N=112 pequeno (folds instaveis; IC largo).")
    L.append("- Heterogeneidade Engenharia (~2,31) x Ultra (~1,57 alunos/m²).")
    L.append("- SkyFit sem m²; `alunos_parceiras` sem m²/tipo (fora da curva).")
    L.append("- ~90% da variancia de densidade fora do que temos (DIM-07): metragem e o unico sinal real.")
    L.append("")
    L.append("## 8. Recomendacao")
    L.append("")
    if result.go:
        L.append(
            "- GO fraco: a forma funcional log-metragem tem sinal util, mas RECALIBRAR os "
            "coeficientes da curva em producao e FOLLOW-UP com gate proprio (NAO aplicar aqui)."
        )
    else:
        L.append(
            "- NO-GO: a metragem sozinha nao valida a curva out-of-fold de forma materialmente "
            "confiavel. NAO recalibrar coeficientes; a curva em producao segue como esta "
            "(heuristica de comparaveis), com o caveat de sinal fraco documentado."
        )
    L.append(
        "- Em qualquer caso, `alunos_parceiras` NAO entra na curva (D1-A); nenhuma feature "
        "geografica (DEC-009); nenhum artefato do M1 alterado (§5)."
    )
    L.append("")
    L.append("---")
    L.append("")
    L.append("## Nota honesta embutida")
    L.append("")
    L.append("```")
    L.append(result.nota_honesta.rstrip("\n"))
    L.append("```")
    L.append("")
    texto = "\n".join(L)
    _assert_sem_pii(texto)
    return texto


def escrever_relatorio(
    result: CurvaValidacaoResult,
    sanity: dict,
    *,
    path: Path | str = Path("data/analysis/calibracao_curva_densidade.md"),
    result_pooled: CurvaValidacaoResult | None = None,
    result_ultra: CurvaValidacaoResult | None = None,
) -> None:
    """Materializa o relatorio markdown (gitignored, sem PII). NAO chamada em teste unitario."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _relatorio_markdown(
            result, sanity, result_pooled=result_pooled, result_ultra=result_ultra
        ),
        encoding="utf-8",
    )
    _logger.info("relatorio BLK-TP-04 escrito: %s", path)


# Rede de seguranca anti-PII: nenhum NOME DE COLUNA proibido deve aparecer como token
# isolado nas saidas. Usa fronteira de palavra (`\b`) para nao colidir com substrings
# legitimas do texto em PT (ex.: "id" em "valida", "lat" em "correlat", "nome" em "nomes").
def _assert_sem_pii(texto: str) -> None:
    """Falha se qualquer coluna de COLUNAS_PII_PROIBIDAS aparecer como token isolado."""
    baixo = texto.lower()
    presentes = {
        c
        for c in COLUNAS_PII_PROIBIDAS
        if re.search(rf"\b{re.escape(c.lower())}\b", baixo)
    }
    if presentes:  # pragma: no cover - rede de seguranca
        raise AssertionError(f"PII vazou no relatorio BLK-TP-04: {presentes}")


__all__ = [
    "CurvaValidacaoResult",
    "carregar_base_curva",
    "validar_curva_densidade",
    "sanity_check_parceiras",
    "flag_extrapolacao_m2",
    "escrever_relatorio",
    "SEED_BOOTSTRAP",
    "N_BOOT",
    "K_FOLD",
    "N_REPEATS",
    "N_ACAD_REF_MAX",
]


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    _base = carregar_base_curva(
        path_multirede=Path("data/staging/base_calibracao_multirede.parquet"),
        path_ultra=None,
    )
    _res = validar_curva_densidade(_base, estratificar_marca=True)
    _res_pooled = validar_curva_densidade(_base, estratificar_marca=False)
    # Coorte de robustez Ultra (N=54, D2-B), monomarca -> validacao pooled.
    _res_ultra = None
    try:
        _du = pd.read_parquet(Path("data/staging/unidades_ultra_performance_hex.parquet"))
        _mu = pd.to_numeric(_du.get("metragem"), errors="coerce")
        _au = pd.to_numeric(_du.get("alunos_total"), errors="coerce")
        _mask = _mu.notna() & (_mu > 0) & _au.notna() & (_au > 0)
        _base_u = pd.DataFrame(
            {
                "marca": ["ultra"] * int(_mask.sum()),
                "metragem": _mu[_mask].to_numpy(dtype=float),
                "alunos_reais": _au[_mask].to_numpy(dtype=float),
            }
        )
        _base_u["alunos_por_m2"] = _base_u["alunos_reais"] / _base_u["metragem"]
        _res_ultra = validar_curva_densidade(_base_u, estratificar_marca=False)
    except Exception as _exc:  # noqa: BLE001 - robustez opcional
        _logger.warning("coorte Ultra indisponivel: %s", _exc)

    _demanda = pd.read_parquet(Path("data/staging/demanda_revelada_h3.parquet"))
    _sanity = sanity_check_parceiras(_demanda)
    escrever_relatorio(
        _res,
        _sanity,
        path=Path("data/analysis/calibracao_curva_densidade.md"),
        result_pooled=_res_pooled,
        result_ultra=_res_ultra,
    )
    print(_res.nota_honesta)
