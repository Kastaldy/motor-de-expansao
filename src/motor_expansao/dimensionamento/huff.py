"""BLK-DIM-02R -- modelo gravitacional de Huff (share de mercado) com validacao real.

READ-ONLY sobre o M1 (DEC-001/DEC-008): nao recalcula `score_priorizacao`/pesos nem
toca artefatos oficiais. Camada PARALELA de Dimensionamento (Camada 2 do spec
`modelo_dimensionamento_expansao.md` §4: share gravitacional + saturacao por capacidade
propria + canibalizacao por unidades proprias no catchment).

Anti-PII: o modulo so le `lat`/`lng` (+ `rede` para dedup opcional) dos concorrentes; o
`nome_unidade` NUNCA e lido para saida nem persistido. `assert_sem_pii` antes de qualquer
escrita em disco.

Anti-vazamento (a regra mais importante deste bloco): a funcao-nucleo `share_huff` e PURA
e GEOMETRICA -- NAO recebe nem usa `alunos_reais` (o alvo). PROIBIDO qualquer
`pot = where(isnan(pot), y, pot)` ou variante que injete o alvo no previsor. O vazamento do
spike (que matou o BLK-DIM-01R) fica estruturalmente impossivel porque o nucleo nao tem
acesso ao alvo.

LOO honesto (anti-circular): para cada unidade-alvo deixada de fora, o expoente de
decaimento beta e re-otimizado SO nas DEMAIS unidades e aplicado a unidade excluida. O
alvo da unidade-alvo nunca entra no beta usado nela.

Metodologia (DEC-008 §7): LOO-CV vs baseline, BANIR R2 in-sample, IC obrigatorio, flag de
extrapolacao. A saida quantitativa e beta + IC + correlacao/AUC de RANKING do share LOO vs
alunos reais -- NUNCA "este hex tera N alunos". NO-GO e resultado VALIDO (nao forcar GO).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score

from motor_expansao.dimensionamento.base_multirede import (
    CONCORRENTES_PATH,
    PISO_VIABILIDADE_ALUNOS,
    SAIDA_BASE,
    haversine_km,  # noqa: F401  (re-export usado em teste/comparacao da haversine vetorizada)
)
from motor_expansao.dimensionamento.growth_api_client import assert_sem_pii

_logger = logging.getLogger(__name__)

# Grade e limites de busca do expoente de decaimento gravitacional beta.
BETA_GRID: tuple[float, ...] = (0.5, 1.0, 1.5, 2.0, 3.0)  # auditoria/sanity
BETA_BOUNDS: tuple[float, float] = (0.1, 5.0)  # busca continua (minimize_scalar)
# Distancia de referencia (raio mediano observado no BLK-DIM-07).
DIST_BASE_KM: float = 1.66
# Piso de distancia p/ evitar divisao por zero (unidade ~coincidente com concorrente).
DIST_MIN_KM: float = 0.05
# Janela de catchment para concorrentes considerados no share (multiplo do raio base).
JANELA_CATCHMENT_KM: float = DIST_BASE_KM * 2.0
# Capacidade-padrao de concorrente (atratividade). concorrentes_mapeados NAO tem
# capacidade -> atratividade unitaria (1.0) por concorrente. Documentado (D3).
ATRATIVIDADE_CONCORRENTE: float = 1.0
# Atratividade da PROPRIA unidade-alvo no numerador do share (auto-share = 1 ref).
ATRATIVIDADE_PROPRIA: float = 1.0
# Bootstrap do IC de beta e da metrica LOO.
N_BOOTSTRAP: int = 1_000
SEED: int = 42
# Gate: share LOO precisa correlacionar com alunos reais E o IC da correlacao nao cruzar 0.
CORR_GO_MIN: float = 0.15  # |correlacao Spearman| LOO minima p/ GO honesto
N_MIN_CALIBRACAO: int = 30  # abaixo disso flag_extrapolacao_padrao=True

# Frase de guardrail anti-predicao -- testada por substring (NAO alterar o texto).
_FRASE_GUARDRAIL = "Saida como beta/share de ranking; NUNCA previsao pontual de N alunos por hex."


@dataclass
class HuffModel:
    """Resultado da calibracao Huff. Sem PII; campos agregados/numericos apenas."""

    beta: float  # expoente de decaimento calibrado (LOO-agregado)
    beta_ic95: tuple[float, float]  # IC95 bootstrap de beta
    beta_indistinguivel_de_zero: bool  # True se IC de corr cruza 0 OU beta colado no piso
    corr_loo_share_alunos: float  # Spearman(share_loo, alunos_reais) -- metrica honesta
    corr_loo_ic95: tuple[float, float]
    auc_loo_viavel: float  # AUC share_loo discrimina viavel(>=2000) vs inviavel
    auc_loo_ic95: tuple[float, float]
    baseline_corr: float  # baseline: -log1p(n_conc_no_raio) ~ alunos (sem beta)
    n_treinamento: int
    n_outliers_removidos: int
    flag_extrapolacao_padrao: bool  # n < N_MIN_CALIBRACAO
    veredito: str  # "GO" | "NO-GO"
    nota_honesta: str
    betas_por_fold: list[float] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Geometria vetorizada
# --------------------------------------------------------------------------- #
def _haversine_vec(lat0: float, lng0: float, lats: np.ndarray, lngs: np.ndarray) -> np.ndarray:
    """Haversine de 1 ponto a N pontos (km). Padrao numpy de `_conc_por_km2`."""
    lats = np.asarray(lats, dtype=float)
    lngs = np.asarray(lngs, dtype=float)
    if lats.size == 0:
        return np.array([], dtype=float)
    r = 6371.0088
    p1 = math.radians(lat0)
    p2 = np.radians(lats)
    dphi = np.radians(lats - lat0)
    dlmb = np.radians(lngs - lng0)
    h = np.sin(dphi / 2) ** 2 + math.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(h))


# --------------------------------------------------------------------------- #
# Carga de concorrentes (so lat/lng -- NUNCA nome_unidade)
# --------------------------------------------------------------------------- #
def _carregar_concorrentes(
    conc_path: Path = CONCORRENTES_PATH, *, conc_df: pd.DataFrame | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """Retorna `(conc_lat, conc_lng)` de concorrentes_mapeados (so coords validas).

    `conc_df` injetavel em teste (IGNORA `conc_path` quando passado). Filtra
    `flag_coord_valida` quando a coluna existe; coage e descarta NaN. NUNCA retorna
    nem persiste `nome_unidade`.
    """
    conc = conc_df if conc_df is not None else pd.read_parquet(conc_path)
    if "flag_coord_valida" in conc.columns:
        conc = conc[conc["flag_coord_valida"].fillna(False).astype(bool)]
    lat = pd.to_numeric(conc.get("lat"), errors="coerce").to_numpy(dtype=float)
    lng = pd.to_numeric(conc.get("lng"), errors="coerce").to_numpy(dtype=float)
    ok = np.isfinite(lat) & np.isfinite(lng)
    return lat[ok], lng[ok]


# --------------------------------------------------------------------------- #
# Nucleo PURO: share gravitacional (sem alvo)
# --------------------------------------------------------------------------- #
def share_huff(
    dist_propria_km: float,
    dist_concorrentes_km: np.ndarray,
    beta: float,
    *,
    atr_propria: float = ATRATIVIDADE_PROPRIA,
    atr_concorrente: float = ATRATIVIDADE_CONCORRENTE,
) -> float:
    """Share gravitacional de Huff de UMA unidade dado beta. PURA e geometrica.

    `share = (atr_propria / d_propria^beta) / (atr_propria/d_propria^beta +
    sum_j atr_conc/d_j^beta)`. Distancias clampadas a `>= DIST_MIN_KM`. Sem
    concorrentes -> share = 1.0 (monopolio local). Retorna float em [0, 1].

    NAO recebe nem usa `alunos_reais` (o alvo) -- vazamento estruturalmente impossivel.
    """
    d_propria = max(float(dist_propria_km), DIST_MIN_KM)
    num = float(atr_propria) / (d_propria**beta)

    dconc = np.asarray(dist_concorrentes_km, dtype=float)
    dconc = dconc[np.isfinite(dconc)]
    if dconc.size == 0:
        return 1.0
    dconc = np.maximum(dconc, DIST_MIN_KM)
    denom_conc = float(np.sum(float(atr_concorrente) / (dconc**beta)))

    denom = num + denom_conc
    if denom <= 0:
        return 0.0
    return float(num / denom)


def _share_loo_para_unidade(
    i: int,
    lats: np.ndarray,
    lngs: np.ndarray,
    marcas: np.ndarray,
    conc_lat: np.ndarray,
    conc_lng: np.ndarray,
    beta: float,
) -> float:
    """Share da unidade i: concorrentes OSM + canibalizacao da MESMA marca, sem o alvo.

    Concorrentes = TODOS os OSM dentro de `JANELA_CATCHMENT_KM` + outras unidades-alvo da
    MESMA `marca` dentro da janela (canibalizacao propria, spec §4). A unidade i NUNCA
    entra como seu proprio concorrente (anti-circular). `alunos_reais` jamais usado.
    """
    lat_i, lng_i = float(lats[i]), float(lngs[i])
    if not (np.isfinite(lat_i) and np.isfinite(lng_i)):
        return float("nan")

    # Concorrentes OSM dentro da janela de catchment.
    dist_osm = _haversine_vec(lat_i, lng_i, conc_lat, conc_lng)
    dist_osm = dist_osm[np.isfinite(dist_osm) & (dist_osm <= JANELA_CATCHMENT_KM)]

    # Canibalizacao: outras unidades da MESMA marca (i nunca e seu proprio concorrente).
    same_marca = marcas == marcas[i]
    same_marca[i] = False
    outras_lat = lats[same_marca]
    outras_lng = lngs[same_marca]
    dist_propria_rede = _haversine_vec(lat_i, lng_i, outras_lat, outras_lng)
    dist_propria_rede = dist_propria_rede[
        np.isfinite(dist_propria_rede) & (dist_propria_rede <= JANELA_CATCHMENT_KM)
    ]

    dist_concorrentes = np.concatenate([dist_osm, dist_propria_rede])
    return share_huff(DIST_BASE_KM, dist_concorrentes, beta)


# --------------------------------------------------------------------------- #
# Objetivo de calibracao + LOO honesto
# --------------------------------------------------------------------------- #
def _objetivo_beta(
    beta: float,
    idxs: np.ndarray,
    lats: np.ndarray,
    lngs: np.ndarray,
    marcas: np.ndarray,
    alunos: np.ndarray,
    conc_lat: np.ndarray,
    conc_lng: np.ndarray,
) -> float:
    """-|Spearman(share, alunos)| sobre o conjunto `idxs` (a minimizar)."""
    shares = np.array(
        [
            _share_loo_para_unidade(int(i), lats, lngs, marcas, conc_lat, conc_lng, beta)
            for i in idxs
        ],
        dtype=float,
    )
    y = alunos[idxs]
    ok = np.isfinite(shares) & np.isfinite(y)
    if int(ok.sum()) < 3 or len(np.unique(shares[ok])) < 2:
        return 0.0
    rho, _p = spearmanr(shares[ok], y[ok])
    if not np.isfinite(rho):
        return 0.0
    return -abs(float(rho))


def _otimizar_beta(
    idxs: np.ndarray,
    lats: np.ndarray,
    lngs: np.ndarray,
    marcas: np.ndarray,
    alunos: np.ndarray,
    conc_lat: np.ndarray,
    conc_lng: np.ndarray,
    *,
    beta_bounds: tuple[float, float] = BETA_BOUNDS,
) -> float:
    """Otimiza beta no conjunto `idxs` (maximiza |Spearman|) via minimize_scalar bounded."""
    res = minimize_scalar(
        _objetivo_beta,
        bounds=beta_bounds,
        method="bounded",
        args=(idxs, lats, lngs, marcas, alunos, conc_lat, conc_lng),
    )
    beta = float(res.x)
    return float(min(max(beta, beta_bounds[0]), beta_bounds[1]))


def _calibrar_beta_loo(
    lats: np.ndarray,
    lngs: np.ndarray,
    marcas: np.ndarray,
    alunos: np.ndarray,
    conc_lat: np.ndarray,
    conc_lng: np.ndarray,
    *,
    beta_bounds: tuple[float, float] = BETA_BOUNDS,
) -> tuple[float, np.ndarray, list[float]]:
    """LOO honesto: para cada i, beta otimizado nas DEMAIS e aplicado SO a i.

    Retorna `(beta_mediano_loo, share_loo, betas_por_fold)`. Anti-vazamento: o alvo
    (alunos) da unidade i NUNCA entra na otimizacao do beta usado nela. Grupo de treino
    com <3 unidades validas -> `share_loo[i] = nan`.
    """
    n = len(lats)
    todos = np.arange(n)
    share_loo = np.full(n, np.nan, dtype=float)
    betas: list[float] = []
    for i in range(n):
        treino = todos[todos != i]
        # Apenas indices de treino com alunos finitos contam para o objetivo.
        treino_ok = treino[np.isfinite(alunos[treino])]
        if treino_ok.size < 3:
            continue
        beta_i = _otimizar_beta(
            treino_ok,
            lats,
            lngs,
            marcas,
            alunos,
            conc_lat,
            conc_lng,
            beta_bounds=beta_bounds,
        )
        betas.append(beta_i)
        share_loo[i] = _share_loo_para_unidade(i, lats, lngs, marcas, conc_lat, conc_lng, beta_i)
    beta_mediano = float(np.median(betas)) if betas else float("nan")
    return beta_mediano, share_loo, betas


# --------------------------------------------------------------------------- #
# Baseline + IC bootstrap
# --------------------------------------------------------------------------- #
def _n_conc_no_raio(
    lats: np.ndarray,
    lngs: np.ndarray,
    conc_lat: np.ndarray,
    conc_lng: np.ndarray,
    *,
    raio_km: float = DIST_BASE_KM,
) -> np.ndarray:
    """Numero de concorrentes OSM dentro de `raio_km` por unidade (baseline sem beta)."""
    out = np.zeros(len(lats), dtype=float)
    for i in range(len(lats)):
        lat_i, lng_i = float(lats[i]), float(lngs[i])
        if not (np.isfinite(lat_i) and np.isfinite(lng_i)):
            out[i] = np.nan
            continue
        d = _haversine_vec(lat_i, lng_i, conc_lat, conc_lng)
        out[i] = float(np.sum(np.isfinite(d) & (d <= raio_km)))
    return out


def _ic_bootstrap(
    valores: np.ndarray, *, rng: np.random.Generator, n: int = N_BOOTSTRAP
) -> tuple[float, float]:
    """IC95 (2.5/97.5) por bootstrap percentil de uma amostra de valores finitos."""
    v = np.asarray(valores, dtype=float)
    v = v[np.isfinite(v)]
    if v.size < 2:
        return (float("nan"), float("nan"))
    amostras = np.empty(n, dtype=float)
    for k in range(n):
        idx = rng.integers(0, v.size, size=v.size)
        amostras[k] = float(np.mean(v[idx]))
    return (float(np.percentile(amostras, 2.5)), float(np.percentile(amostras, 97.5)))


def _ic_bootstrap_corr(
    share: np.ndarray,
    alunos: np.ndarray,
    *,
    rng: np.random.Generator,
    n: int = N_BOOTSTRAP,
) -> tuple[float, float]:
    """IC95 da Spearman(share, alunos) por bootstrap de pares (descarta degenerados)."""
    s = np.asarray(share, dtype=float)
    y = np.asarray(alunos, dtype=float)
    ok = np.isfinite(s) & np.isfinite(y)
    s, y = s[ok], y[ok]
    if s.size < 3:
        return (float("nan"), float("nan"))
    rhos: list[float] = []
    teto = 10 * n
    tentativas = 0
    while len(rhos) < n and tentativas < teto:
        tentativas += 1
        idx = rng.integers(0, s.size, size=s.size)
        sb, yb = s[idx], y[idx]
        if len(np.unique(sb)) < 2 or len(np.unique(yb)) < 2:
            continue
        rho, _p = spearmanr(sb, yb)
        if np.isfinite(rho):
            rhos.append(float(rho))
    if not rhos:
        return (float("nan"), float("nan"))
    arr = np.asarray(rhos, dtype=float)
    return (float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5)))


def _auc_seguro(y: np.ndarray, score: np.ndarray) -> float:
    """AUC com guard de classe unica / NaN -> NaN (NAO levanta)."""
    ok = np.isfinite(score)
    yk, sk = y[ok], score[ok]
    if yk.size < 2 or len(np.unique(yk)) < 2:
        return float("nan")
    return float(roc_auc_score(yk, sk))


def _ic_bootstrap_auc(
    y: np.ndarray,
    score: np.ndarray,
    *,
    rng: np.random.Generator,
    n: int = N_BOOTSTRAP,
) -> tuple[float, float]:
    """IC95 de AUC por bootstrap; descarta reamostra de classe unica."""
    aucs: list[float] = []
    teto = 10 * n
    tentativas = 0
    while len(aucs) < n and tentativas < teto:
        tentativas += 1
        idx = rng.integers(0, y.size, size=y.size)
        yb = y[idx]
        if len(np.unique(yb)) < 2:
            continue
        a = _auc_seguro(yb, score[idx])
        if np.isfinite(a):
            aucs.append(a)
    if not aucs:
        return (float("nan"), float("nan"))
    arr = np.asarray(aucs, dtype=float)
    return (float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5)))


# --------------------------------------------------------------------------- #
# Orquestrador de calibracao
# --------------------------------------------------------------------------- #
def calibrar_huff(
    base: pd.DataFrame,
    *,
    conc_path: Path = CONCORRENTES_PATH,
    conc_df: pd.DataFrame | None = None,
    rng_seed: int = SEED,
) -> HuffModel:
    """Calibra beta por LOO honesto e devolve um `HuffModel` com IC e veredito GO/NO-GO.

    Valida colunas `{lat, lng, alunos_reais, marca}`; remove linhas sem coord/alunos
    (conta `n_outliers_removidos`); levanta `ValueError` se N < 5. A saida quantitativa e
    beta + IC + Spearman/AUC do share LOO vs alunos -- NUNCA previsao pontual de alunos.
    """
    obrig = {"lat", "lng", "alunos_reais", "marca"}
    faltando = obrig - set(base.columns)
    if faltando:
        raise ValueError(f"Colunas obrigatorias ausentes: {sorted(faltando)}")

    n_inicial = int(len(base))
    lat = pd.to_numeric(base["lat"], errors="coerce")
    lng = pd.to_numeric(base["lng"], errors="coerce")
    alunos_s = pd.to_numeric(base["alunos_reais"], errors="coerce")
    keep = lat.notna() & lng.notna() & alunos_s.notna()
    work = base[keep].copy().reset_index(drop=True)
    n_outliers = n_inicial - int(len(work))

    if int(len(work)) < 5:
        raise ValueError(
            f"N insuficiente para calibrar Huff: {len(work)} (< 5) unidades com coord+alunos."
        )

    lats = pd.to_numeric(work["lat"], errors="coerce").to_numpy(dtype=float)
    lngs = pd.to_numeric(work["lng"], errors="coerce").to_numpy(dtype=float)
    marcas = work["marca"].astype(str).to_numpy()
    alunos = pd.to_numeric(work["alunos_reais"], errors="coerce").to_numpy(dtype=float)

    conc_lat, conc_lng = _carregar_concorrentes(conc_path, conc_df=conc_df)

    beta, share_loo, betas = _calibrar_beta_loo(lats, lngs, marcas, alunos, conc_lat, conc_lng)

    rng = np.random.default_rng(rng_seed)

    # Correlacao honesta share_loo vs alunos.
    ok = np.isfinite(share_loo) & np.isfinite(alunos)
    n_treino = int(ok.sum())
    if n_treino >= 3 and len(np.unique(share_loo[ok])) >= 2:
        corr_loo, _p = spearmanr(share_loo[ok], alunos[ok])
        corr_loo = float(corr_loo) if np.isfinite(corr_loo) else float("nan")
    else:
        corr_loo = float("nan")
    corr_ic = _ic_bootstrap_corr(share_loo, alunos, rng=rng)

    # AUC: share_loo discrimina viavel(>=PISO) vs inviavel.
    y_viavel = (alunos >= PISO_VIABILIDADE_ALUNOS).astype(int)
    auc_viavel = _auc_seguro(y_viavel, share_loo)
    auc_ic = _ic_bootstrap_auc(y_viavel, share_loo, rng=rng)

    # Baseline SEM beta: -log1p(n_conc_no_raio) ~ alunos.
    n_conc = _n_conc_no_raio(lats, lngs, conc_lat, conc_lng)
    base_proxy = -np.log1p(n_conc)
    okb = np.isfinite(base_proxy) & np.isfinite(alunos)
    if int(okb.sum()) >= 3 and len(np.unique(base_proxy[okb])) >= 2:
        baseline_corr, _pb = spearmanr(base_proxy[okb], alunos[okb])
        baseline_corr = float(baseline_corr) if np.isfinite(baseline_corr) else float("nan")
    else:
        baseline_corr = float("nan")

    # IC de beta por bootstrap dos betas-por-fold.
    beta_ic = _ic_bootstrap(np.asarray(betas, dtype=float), rng=rng)

    flag_extrap = n_treino < N_MIN_CALIBRACAO

    # Indistinguivel de zero: IC da correlacao cruza 0 OU beta colado no piso de busca.
    corr_cruza_zero = not (np.isfinite(corr_ic[0]) and np.isfinite(corr_ic[1])) or (
        corr_ic[0] <= 0.0 <= corr_ic[1]
    )
    beta_no_piso = np.isfinite(beta) and abs(beta - BETA_BOUNDS[0]) < 1e-3
    beta_indist = bool(corr_cruza_zero or beta_no_piso)

    veredito = (
        "GO"
        if (
            np.isfinite(corr_loo)
            and abs(corr_loo) >= CORR_GO_MIN
            and np.isfinite(corr_ic[0])
            and np.isfinite(corr_ic[1])
            and not (corr_ic[0] <= 0.0 <= corr_ic[1])
        )
        else "NO-GO"
    )

    nota = (
        f"beta={beta:.3f} IC95=[{beta_ic[0]:.3f},{beta_ic[1]:.3f}]; "
        f"Spearman(share_loo, alunos)={corr_loo:.3f} "
        f"IC95=[{corr_ic[0]:.3f},{corr_ic[1]:.3f}]; "
        f"baseline_corr={baseline_corr:.3f}; "
        f"AUC viavel={auc_viavel:.3f}; n_treino={n_treino}; veredito={veredito}. "
        f"{_FRASE_GUARDRAIL}"
    )

    _logger.info(
        "Huff calibrado: beta=%.3f corr_loo=%.3f auc=%.3f n=%d veredito=%s",
        beta,
        corr_loo,
        auc_viavel,
        n_treino,
        veredito,
    )

    return HuffModel(
        beta=beta,
        beta_ic95=beta_ic,
        beta_indistinguivel_de_zero=beta_indist,
        corr_loo_share_alunos=corr_loo,
        corr_loo_ic95=corr_ic,
        auc_loo_viavel=auc_viavel,
        auc_loo_ic95=auc_ic,
        baseline_corr=baseline_corr,
        n_treinamento=n_treino,
        n_outliers_removidos=n_outliers,
        flag_extrapolacao_padrao=flag_extrap,
        veredito=veredito,
        nota_honesta=nota,
        betas_por_fold=betas,
    )


# --------------------------------------------------------------------------- #
# Relatorio
# --------------------------------------------------------------------------- #
def _f(v: object, nd: int = 4) -> str:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return f"{float(v):.{nd}f}" if np.isfinite(float(v)) else "n/d"
    return str(v)


def _ic(t: object) -> str:
    if isinstance(t, (tuple, list)) and len(t) == 2:
        return f"[{_f(t[0])}, {_f(t[1])}]"
    return "n/d"


def relatorio_huff(modelo: HuffModel) -> str:
    """String markdown legivel (PT, sem PII) com beta/IC/validacao/veredito/confounds."""
    L: list[str] = []
    L.append("# Calibracao Huff gravitacional -- BLK-DIM-02R")
    L.append("")
    L.append("READ-ONLY sobre o M1 (DEC-001/DEC-008). Sem PII (so contagens/metricas agregadas).")
    L.append("")
    L.append(_FRASE_GUARDRAIL)
    L.append("")

    L.append("## 1. Setup")
    L.append("")
    L.append(f"- N de treinamento (coord + alunos): {modelo.n_treinamento}")
    L.append(f"- N linhas removidas (sem coord/alunos): {modelo.n_outliers_removidos}")
    L.append(
        f"- flag_extrapolacao_padrao (N < {N_MIN_CALIBRACAO}): {modelo.flag_extrapolacao_padrao}"
    )
    L.append(
        f"- Distancia propria de referencia: {DIST_BASE_KM} km "
        f"(raio mediano BLK-DIM-07); janela catchment {JANELA_CATCHMENT_KM:.2f} km"
    )
    L.append(
        f"- Atratividade por concorrente: {ATRATIVIDADE_CONCORRENTE} "
        "(concorrentes_mapeados NAO tem capacidade -> unitaria; D3)"
    )
    L.append("")

    L.append("## 2. Calibracao de beta (LOO honesto)")
    L.append("")
    L.append(
        "Para cada unidade deixada de fora, beta e re-otimizado SO nas demais "
        "(maximiza |Spearman(share, alunos)|) e aplicado a unidade excluida. O alvo "
        "da unidade-alvo nunca entra no beta usado nela (anti-vazamento)."
    )
    L.append("")
    L.append(f"- beta (mediano LOO): {_f(modelo.beta, 3)}")
    L.append(f"- IC95 de beta (bootstrap dos betas-por-fold): {_ic(modelo.beta_ic95)}")
    L.append(
        f"- limites de busca: [{BETA_BOUNDS[0]}, {BETA_BOUNDS[1]}]; grade de sanity: {BETA_GRID}"
    )
    L.append("")

    L.append("## 3. Validacao honesta (LOO vs baseline)")
    L.append("")
    L.append("| metrica | valor | IC95 |")
    L.append("| --- | ---: | --- |")
    L.append(
        f"| Spearman(share_loo, alunos) | {_f(modelo.corr_loo_share_alunos)} | "
        f"{_ic(modelo.corr_loo_ic95)} |"
    )
    L.append(
        f"| AUC share_loo (viavel >= {PISO_VIABILIDADE_ALUNOS}) | "
        f"{_f(modelo.auc_loo_viavel)} | {_ic(modelo.auc_loo_ic95)} |"
    )
    L.append(f"| baseline -log1p(n_conc) ~ alunos | {_f(modelo.baseline_corr)} | n/d |")
    L.append("")
    L.append(
        "O baseline NAO usa distancia/beta (so contagem de concorrentes no raio). "
        "Se o Huff nao supera o baseline, a geometria de distancia nao agrega."
    )
    L.append("")

    L.append("## 4. Veredito GO/NO-GO de beta")
    L.append("")
    L.append(
        f"**Veredito:** `{modelo.veredito}` "
        f"(GO se |Spearman| >= {CORR_GO_MIN} E IC da correlacao NAO cruza zero)."
    )
    L.append(f"- beta_indistinguivel_de_zero: {modelo.beta_indistinguivel_de_zero}")
    L.append("")
    L.append(modelo.nota_honesta)
    L.append("")

    L.append("## 5. Confounds e ressalvas")
    L.append("")
    L.append(
        "- Atratividade unitaria por concorrente (sem capacidade observavel): o share "
        "ignora porte do concorrente -- simplificacao consciente (D3)."
    )
    L.append(
        "- Distancia propria fixa (DIST_BASE_KM): proxy do catchment, nao derivada de "
        "alunos (anti-circular)."
    )
    L.append(
        "- metragem propria NAO usada como atratividade (esparsa por marca -> viesaria "
        "por cobertura)."
    )
    L.append("- Vies de selecao entre redes: taxas de match de coord diferentes por marca.")
    L.append(
        "- NO-GO e resultado VALIDO: significa que distancia a concorrentes nao explica "
        "o ranking de alunos -- nao se forca GO."
    )
    L.append("")
    L.append(_FRASE_GUARDRAIL)
    L.append("")
    return "\n".join(L)


def escrever_relatorio_huff(
    modelo: HuffModel, *, path: Path = Path("data/analysis/huff_calibracao.md")
) -> None:
    """Materializa o relatorio markdown (gitignored, sem PII). Nunca lista unidades."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(relatorio_huff(modelo), encoding="utf-8")
    _logger.info("relatorio BLK-DIM-02R escrito: %s", path)


# --------------------------------------------------------------------------- #
# Orquestrador real (caminho de disco -- NAO chamado em teste)
# --------------------------------------------------------------------------- #
def executar(
    base_path: Path | str = SAIDA_BASE,
    conc_path: Path | str = CONCORRENTES_PATH,
    out_path: Path | str = Path("data/analysis/huff_calibracao.md"),
) -> HuffModel:
    """Le base + concorrentes reais, calibra Huff e materializa o relatorio."""
    base = pd.read_parquet(base_path)
    assert_sem_pii(base)
    modelo = calibrar_huff(base, conc_path=Path(conc_path))
    escrever_relatorio_huff(modelo, path=Path(out_path))
    return modelo


__all__ = [
    "HuffModel",
    "share_huff",
    "calibrar_huff",
    "relatorio_huff",
    "escrever_relatorio_huff",
    "executar",
    "BETA_GRID",
    "BETA_BOUNDS",
    "DIST_BASE_KM",
    "CORR_GO_MIN",
    "PISO_VIABILIDADE_ALUNOS",
]


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    _m = executar()
    print("Huff veredito:", _m.veredito)
    print("beta:", _m.beta, "IC95:", _m.beta_ic95)
    print("corr_loo:", _m.corr_loo_share_alunos, "IC95:", _m.corr_loo_ic95)
