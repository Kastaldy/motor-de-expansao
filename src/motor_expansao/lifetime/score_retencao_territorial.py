"""BLK-LTV-04 — Score de retencao territorial (camada paralela M2, READ-ONLY M1).

Compoe um score de retencao territorial por hexagono ancorado no composto
`score_priorizacao` (eixo captacao, LIDO do M1) + um eixo de retencao territorial
calibrado FORA-DE-FOLD contra `LTV_PROSPECTIVO_12M_MEDIANO` (agregado por unidade,
N=56). Formula (DEC-014, decisao de produto 1: variante A 50/50):

    captacao_norm = score_priorizacao                              # 0-100, LIDO
    retencao_norm = 100 * percentil_nacional(retencao_prevista_territorial)
    score_retencao = clip(w_cap*captacao_norm + w_ret*retencao_norm, 0, 100)

Metodologia (DEC-008, honrada):
  - Eixo retencao calibrado por k-fold 5x5 (+ LOO fallback), Ridge em numpy PURO
    (DEC-014 decisao 3: SEM scikit-learn). Toda metrica e OUT-OF-FOLD:
    R2_oof + Spearman rho_oof, ambos com IC95 bootstrap (seed=42, >=1000).
  - Baseline obrigatorio = media do alvo fora-de-fold.
  - R2 in-sample e `fit(X,y)->predict(X)` BANIDOS.
  - Maturidade (de growth_api_historico.parquet, `inauguracao`) entra SO como
    COVARIAVEL de controle na validacao (variante com/sem); NUNCA feature do
    score por hex (maturidade e atributo de UNIDADE, nao de hex candidato).
  - Criterio de NO-GO honesto: o eixo retencao so se justifica se, no melhor
    modelo out-of-fold, `R2_oof>0` (IC nao cruza zero) E `rho_oof>=0.30` (IC nao
    cruza zero) E superar `score_priorizacao` sozinho. Caso contrario -> NO-GO
    -> ENCERRAR sem gerar o parquet de score (DEC-014 decisao 2). NO-GO e
    desfecho LEGITIMO e esperado (DEC-008); NAO forcar GO nem degradar para
    `score_priorizacao` como proxy.

GUARDRAILS (DEC-001/DEC-008/DEC-009; CLAUDE.md §5):
  - READ-ONLY sobre o M1: NAO recalcula `score_priorizacao`/`hex_score_estrutural`/
    pesos (renda=0.40/pop=0.60); NAO toca carteira/plano/artefatos oficiais. O
    `score_priorizacao` aqui e apenas uma FEATURE/eixo territorial LIDO. mtime
    dos 4 artefatos oficiais inalterado.
  - DEC-008: out-of-fold vs baseline; R2 in-sample banido; IC bootstrap; flag de
    extrapolacao; NO-GO e resultado VALIDO.
  - DEC-009: score de RETENCAO territorial, NAO preditor de magnitude de demanda;
    PROIBIDO usar qualquer coluna deste modulo como preditor geografico de
    demanda ou ajuste do `score_priorizacao`.
  - Pacote disjunto `lifetime/`: NAO importa de `pipelines/m1/`, `dashboard/`,
    `censo_*`, `api` (nem `sklearn`).
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

_logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Constantes (DEC-014)
# --------------------------------------------------------------------------- #
SEED: int = 42  # RNG fixo (np.random.default_rng); reprodutibilidade byte-estavel
N_BOOTSTRAP: int = 1000  # reamostras do IC95 (>=1000 p/ estabilidade em N pequeno)
PISO_RHO: float = 0.30  # rho_oof minimo p/ GO (relevancia material; espelha LTV-03)

# Pesos aprovados no gate humano (DEC-014, decisao 1 = variante A 50/50).
W_CAP: float = 0.50
W_RET: float = 0.50

# Validacao k-fold: 5 folds x 5 repeticoes; LOO fallback quando N < N_MIN_KFOLD.
K_FOLDS: int = 5
N_REPS: int = 5
N_MIN_KFOLD: int = 25  # abaixo disso, cai p/ LOO (N pequeno)

RIDGE_LAMBDA: float = 1.0  # regularizacao do Ridge (features padronizadas)

ALVO: str = "LTV_PROSPECTIVO_12M_MEDIANO"  # eixo ranking, N=56 (LTV-03)
SNAPSHOT: str = "2026-04-17"  # data de referencia p/ maturidade (meses)

# Envelope de maturidade em MESES: clip de outliers antes de usar como covariavel
# (ha valores negativos e >600 meses no dump; DEC-014 exige clip/winsorize).
MATURIDADE_MIN_MESES: float = 0.0
MATURIDADE_MAX_MESES: float = 300.0

# Eixo captacao = score_priorizacao (LIDO). Eixo retencao usa este preditor base
# + candidatos secundarios territoriais testados na validacao (nunca atributo de
# unidade: ticket/N_ALUNOS/maturidade ficam FORA do score por hex).
FEATURE_BASE: str = "score_priorizacao"
FEATURES_CANDIDATAS: tuple[str, ...] = (
    "score_priorizacao",
    "renda_per_capita",
    "n_concorrentes_mapeados_1km",
)

# Colunas territoriais minimas necessarias no universo de aplicacao do score.
COLS_APLICACAO: tuple[str, ...] = ("hex_id", *FEATURES_CANDIDATAS)

VERSAO_CONTRATO: str = "score_retencao_v1"

# Rotulo literal reservado (nunca usado; R2 in-sample e BANIDO como desempenho).
_ROTULO_INSAMPLE: str = "apenas auditoria -- NAO usar como desempenho"

# Normalizacao de nome de unidade (join com growth_api_historico.parquet).
# Implementada LOCALMENTE p/ manter `lifetime/` desacoplado (sem importar de
# `dimensionamento/`); espelha `normalizar_unidade` (maiuscula, sem acentos,
# espacos colapsados, sufixo " - XX" de UF removido). Casa 56/56 no dado real.
_UF_SUFFIX_RE = re.compile(r"\s*-\s*[A-Z]{2}$")


def _normalizar_unidade(value: object) -> str:
    """Normaliza o nome da unidade para join estavel com o historico de growth."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = "".join(
        c
        for c in unicodedata.normalize("NFKD", str(value))
        if not unicodedata.combining(c)
    )
    text = " ".join(text.upper().strip().split())
    return _UF_SUFFIX_RE.sub("", text).strip()


# --------------------------------------------------------------------------- #
# Dataclass de resultado da validacao
# --------------------------------------------------------------------------- #
@dataclass
class ResultadoModelo:
    """Metricas OUT-OF-FOLD de um modelo territorial (uma variante de features)."""

    nome: str  # rotulo da variante (ex.: "score_priorizacao")
    features: tuple[str, ...]
    n: int  # N efetivo (unidades sem NaN nas features + alvo)
    r2_oof: float  # R2 fora-de-fold vs baseline da media (nan se degenerado)
    r2_ci_low: float
    r2_ci_high: float
    rho_oof: float  # Spearman rho_oof (predito x observado)
    rho_ci_low: float
    rho_ci_high: float
    protocolo: str  # "kfold_5x5" | "loo"
    com_maturidade: bool  # True se maturidade entrou como covariavel de controle


@dataclass
class ResultadoValidacao:
    """Agrega as variantes validadas + o modelo escolhido p/ aplicar o score."""

    modelos: list[ResultadoModelo] = field(default_factory=list)
    n_calibracao: int = 0
    protocolo: str = ""
    seed: int = SEED

    def melhor(self) -> ResultadoModelo | None:
        """Modelo territorial (sem maturidade) com maior R2_oof; None se vazio."""
        candidatos = [m for m in self.modelos if not m.com_maturidade]
        if not candidatos:
            return None
        return max(candidatos, key=lambda m: (m.r2_oof if np.isfinite(m.r2_oof) else -np.inf))

    def base_sozinho(self) -> ResultadoModelo | None:
        """Modelo `score_priorizacao` sozinho (sem maturidade) p/ comparacao."""
        for m in self.modelos:
            if (not m.com_maturidade) and m.features == (FEATURE_BASE,):
                return m
        return None


# --------------------------------------------------------------------------- #
# Loaders privados (READ-ONLY)
# --------------------------------------------------------------------------- #
def _carregar_dataset(path: Path) -> pd.DataFrame:
    """Le unidade_territorio_retencao.parquet (calibracao). READ-ONLY."""
    return pd.read_parquet(path)


def _carregar_universo_aplicacao(path: Path) -> pd.DataFrame:
    """Le o universo de hexes p/ aplicar o score (hexagonos_mercado_mapeado).

    READ-ONLY; carrega apenas as colunas necessarias (`COLS_APLICACAO`). NAO e
    artefato oficial do M1 (camada paralela de mercado).
    """
    cols = [c for c in COLS_APLICACAO]
    return pd.read_parquet(path, columns=cols)


def _carregar_maturidade(path: Path) -> pd.DataFrame:
    """Deriva maturidade_meses por unidade de growth_api_historico.parquet.

    Dedup `groupby('unidade').first()`, parse de `inauguracao` (DD/MM/YYYY),
    meses ate `SNAPSHOT` e CLIP de outliers (negativos e >600 meses). Chave de
    join = `_chave_unidade` (nome normalizado). READ-ONLY; nunca escreve.
    """
    g = pd.read_parquet(path, columns=["unidade", "inauguracao"])
    g = g.groupby("unidade", as_index=False).first()
    inaug = pd.to_datetime(g["inauguracao"], format="%d/%m/%Y", errors="coerce")
    snap = pd.Timestamp(SNAPSHOT)
    meses = (snap - inaug).dt.days / 30.44
    meses = meses.clip(lower=MATURIDADE_MIN_MESES, upper=MATURIDADE_MAX_MESES)
    out = pd.DataFrame(
        {
            "_chave_unidade": g["unidade"].map(_normalizar_unidade),
            "maturidade_meses": meses.astype(float),
        }
    )
    out = out[out["_chave_unidade"] != ""].drop_duplicates("_chave_unidade")
    return out.reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Ridge em numpy PURO (DEC-014 decisao 3: sem scikit-learn)
# --------------------------------------------------------------------------- #
def _ridge_fit(x: np.ndarray, y: np.ndarray, lam: float = RIDGE_LAMBDA) -> np.ndarray:
    """Minimos quadrados regularizados (Ridge) com intercepto NAO penalizado.

    `x` ja padronizado (media 0, desvio 1) no fold de treino. Resolve o sistema
    normal `(XtX + lam*R) beta = Xt y` via `np.linalg.solve` (fallback lstsq se
    singular). R zera a penalizacao do intercepto.
    """
    xb = np.column_stack([np.ones(len(x)), x])
    p = xb.shape[1]
    reg = lam * np.eye(p)
    reg[0, 0] = 0.0
    a = xb.T @ xb + reg
    b = xb.T @ y
    try:
        beta = np.linalg.solve(a, b)
    except np.linalg.LinAlgError:  # pragma: no cover - fallback numerico
        beta, *_ = np.linalg.lstsq(a, b, rcond=None)
    return beta


def _ridge_pred(beta: np.ndarray, x: np.ndarray) -> np.ndarray:
    """Predicao do Ridge para features `x` ja padronizadas com o mesmo pipeline."""
    return np.column_stack([np.ones(len(x)), x]) @ beta


def _oof_predictions(
    x: np.ndarray, y: np.ndarray, *, seed: int = SEED
) -> tuple[np.ndarray, str]:
    """Predicoes OUT-OF-FOLD do Ridge (k-fold 5x5 media das reps, ou LOO).

    Padronizacao ajustada SO no treino de cada fold (sem vazamento). Retorna
    `(oof, protocolo)`. `fit(X,y)->predict(X)` NUNCA ocorre (cada ponto so e
    predito por modelos que NAO o viram).
    """
    n = len(y)
    if n < N_MIN_KFOLD:
        # LOO: cada ponto predito por modelo treinado nos outros n-1.
        oof = np.empty(n, dtype=float)
        for i in range(n):
            tr = np.delete(np.arange(n), i)
            mu = x[tr].mean(axis=0)
            sd = x[tr].std(axis=0)
            sd[sd == 0.0] = 1.0
            xtr = (x[tr] - mu) / sd
            xte = (x[i : i + 1] - mu) / sd
            beta = _ridge_fit(xtr, y[tr])
            oof[i] = _ridge_pred(beta, xte)[0]
        return oof, "loo"

    rng = np.random.default_rng(seed)
    acc = np.zeros(n, dtype=float)
    cnt = np.zeros(n, dtype=float)
    for _rep in range(N_REPS):
        idx = rng.permutation(n)
        folds = np.array_split(idx, K_FOLDS)
        for f in folds:
            if f.size == 0:
                continue
            tr = np.setdiff1d(np.arange(n), f)
            mu = x[tr].mean(axis=0)
            sd = x[tr].std(axis=0)
            sd[sd == 0.0] = 1.0
            xtr = (x[tr] - mu) / sd
            xte = (x[f] - mu) / sd
            beta = _ridge_fit(xtr, y[tr])
            acc[f] += _ridge_pred(beta, xte)
            cnt[f] += 1.0
    cnt[cnt == 0.0] = 1.0
    return acc / cnt, "kfold_5x5"


def _r2_oof(y: np.ndarray, oof: np.ndarray) -> float:
    """R2 out-of-fold vs baseline da MEDIA (ss_res/ss_tot). nan se ss_tot=0."""
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    if ss_tot == 0.0:
        return float("nan")
    ss_res = float(np.sum((y - oof) ** 2))
    return 1.0 - ss_res / ss_tot


# --------------------------------------------------------------------------- #
# Bootstrap dos IC95 (reusa o padrao do LTV-03: default_rng determinista)
# --------------------------------------------------------------------------- #
def _bootstrap_ci_r2_rho(
    y: np.ndarray,
    oof: np.ndarray,
    *,
    n_boot: int = N_BOOTSTRAP,
    seed: int = SEED,
) -> tuple[float, float, float, float]:
    """IC95 (2.5%, 97.5%) de R2_oof e Spearman rho_oof por bootstrap dos pares.

    Reamostra com reposicao os pares `(y_i, oof_i)` ja calculados fora-de-fold
    (o IC quantifica a incerteza amostral das metricas OOF, sem re-treinar).
    Determinista: mesmo `(y, oof, seed)` -> mesmo IC. Retorna
    `(r2_low, r2_high, rho_low, rho_high)`; nan se degenerado.
    """
    m = len(y)
    if m < 3:
        return (float("nan"),) * 4  # type: ignore[return-value]
    rng = np.random.default_rng(seed)
    r2s: list[float] = []
    rhos: list[float] = []
    for _ in range(n_boot):
        idx = rng.integers(0, m, size=m)
        yb = y[idx]
        ob = oof[idx]
        if np.unique(yb).size < 2 or np.unique(ob).size < 2:
            continue
        r2s.append(_r2_oof(yb, ob))
        rho, _p = spearmanr(ob, yb)
        if np.isfinite(rho):
            rhos.append(float(rho))
    if not r2s or not rhos:
        return (float("nan"),) * 4  # type: ignore[return-value]
    r2a = np.asarray(r2s, dtype=float)
    rhoa = np.asarray(rhos, dtype=float)
    return (
        float(np.percentile(r2a, 2.5)),
        float(np.percentile(r2a, 97.5)),
        float(np.percentile(rhoa, 2.5)),
        float(np.percentile(rhoa, 97.5)),
    )


# --------------------------------------------------------------------------- #
# Validacao do eixo retencao
# --------------------------------------------------------------------------- #
def _validar_variante(
    df: pd.DataFrame,
    features: tuple[str, ...],
    *,
    nome: str,
    maturidade: pd.DataFrame | None = None,
) -> ResultadoModelo:
    """Valida uma variante de features OUT-OF-FOLD (Ridge numpy) + IC bootstrap."""
    com_mat = maturidade is not None
    cols = list(features)
    work = df.copy()
    if com_mat:
        assert maturidade is not None
        work = work.merge(maturidade, on="_chave_unidade", how="left")
        cols = [*cols, "maturidade_meses"]
    sub = work.dropna(subset=[*cols, ALVO])
    n = len(sub)
    if n < 3 or n <= len(cols) + 1:
        return ResultadoModelo(
            nome=nome,
            features=features,
            n=n,
            r2_oof=float("nan"),
            r2_ci_low=float("nan"),
            r2_ci_high=float("nan"),
            rho_oof=float("nan"),
            rho_ci_low=float("nan"),
            rho_ci_high=float("nan"),
            protocolo="n/d",
            com_maturidade=com_mat,
        )
    x = sub[cols].to_numpy(dtype=float)
    y = sub[ALVO].to_numpy(dtype=float)
    oof, protocolo = _oof_predictions(x, y)
    r2 = _r2_oof(y, oof)
    rho, _p = spearmanr(oof, y)
    r2_lo, r2_hi, rho_lo, rho_hi = _bootstrap_ci_r2_rho(y, oof)
    return ResultadoModelo(
        nome=nome,
        features=features,
        n=n,
        r2_oof=float(r2),
        r2_ci_low=float(r2_lo),
        r2_ci_high=float(r2_hi),
        rho_oof=float(rho) if np.isfinite(rho) else float("nan"),
        rho_ci_low=float(rho_lo),
        rho_ci_high=float(rho_hi),
        protocolo=protocolo,
        com_maturidade=com_mat,
    )


def validar_eixo_retencao(
    df: pd.DataFrame, *, maturidade: pd.DataFrame | None = None
) -> ResultadoValidacao:
    """Valida o eixo retencao out-of-fold (variantes de features + covariavel).

    Roda: (a) `score_priorizacao` sozinho; (b) multivariadas territoriais; e,
    quando `maturidade` e passada, uma variante COM maturidade como covariavel
    de CONTROLE (nunca feature do score por hex). READ-ONLY: nao muta `df`.
    Determinista (SEED). `df` deve ter `_chave_unidade` (nome normalizado) p/ o
    merge de maturidade.
    """
    variantes: list[tuple[str, tuple[str, ...]]] = [
        (FEATURE_BASE, (FEATURE_BASE,)),
        ("score+renda", ("score_priorizacao", "renda_per_capita")),
        ("score+conc", ("score_priorizacao", "n_concorrentes_mapeados_1km")),
        (
            "score+renda+conc",
            ("score_priorizacao", "renda_per_capita", "n_concorrentes_mapeados_1km"),
        ),
    ]
    modelos: list[ResultadoModelo] = []
    for nome, feats in variantes:
        modelos.append(_validar_variante(df, feats, nome=nome))
    if maturidade is not None:
        # Variante de CONTROLE: score_priorizacao + maturidade (covariavel).
        modelos.append(
            _validar_variante(
                df,
                (FEATURE_BASE,),
                nome=f"{FEATURE_BASE}+maturidade",
                maturidade=maturidade,
            )
        )
    n_cal = max((m.n for m in modelos), default=0)
    protocolo = next((m.protocolo for m in modelos if m.protocolo != "n/d"), "n/d")
    return ResultadoValidacao(
        modelos=modelos, n_calibracao=n_cal, protocolo=protocolo, seed=SEED
    )


# --------------------------------------------------------------------------- #
# Veredito mecanico (NUNCA levanta excecao; NO-GO e desfecho valido)
# --------------------------------------------------------------------------- #
def _veredito_no_go(res: ResultadoValidacao) -> tuple[str, str]:
    """Veredito GO/NO-GO mecanico do eixo retencao (DEC-014 criterio de NO-GO).

    GO se e somente se o MELHOR modelo territorial (por R2_oof) satisfaz TODOS:
      1. R2_oof > 0 E IC95 nao cruza zero (supera o baseline da media);
      2. rho_oof >= PISO_RHO (0.30) E IC95 nao cruza zero (relevancia material);
      3. supera `score_priorizacao` sozinho (R2_oof do melhor > R2_oof do base).
    Caso contrario -> NO-GO (ENCERRAR sem score; DEC-014 decisao 2). NUNCA
    levanta excecao.
    """
    melhor = res.melhor()
    base = res.base_sozinho()
    if melhor is None or base is None:
        return (
            "NO-GO",
            "NO-GO: sem modelo territorial valido (N insuficiente ou features "
            "ausentes). Encerrar sem score (DEC-014 decisao 2).",
        )

    r2_ok = (
        np.isfinite(melhor.r2_oof)
        and melhor.r2_oof > 0.0
        and np.isfinite(melhor.r2_ci_low)
        and melhor.r2_ci_low > 0.0
    )
    rho_ok = (
        np.isfinite(melhor.rho_oof)
        and melhor.rho_oof >= PISO_RHO
        and np.isfinite(melhor.rho_ci_low)
        and melhor.rho_ci_low > 0.0
    )
    # "supera score_priorizacao sozinho": melhor multivariado > base; se o proprio
    # melhor JA e o base, exige que o base atinja os pisos absolutos (nao ha o que
    # superar). Comparacao por R2_oof.
    supera_base = (
        melhor.features == (FEATURE_BASE,)
        or (
            np.isfinite(melhor.r2_oof)
            and np.isfinite(base.r2_oof)
            and melhor.r2_oof > base.r2_oof
        )
    )

    if r2_ok and rho_ok and supera_base:
        just = (
            f"GO: melhor modelo '{melhor.nome}' (features={melhor.features}) com "
            f"R2_oof={melhor.r2_oof:+.4f} (IC95=[{melhor.r2_ci_low:+.4f}, "
            f"{melhor.r2_ci_high:+.4f}]) E rho_oof={melhor.rho_oof:+.4f} "
            f"(IC95=[{melhor.rho_ci_low:+.4f}, {melhor.rho_ci_high:+.4f}]) >= "
            f"{PISO_RHO:.2f}, ambos IC sem cruzar zero, superando "
            f"'{FEATURE_BASE}' sozinho (R2_oof={base.r2_oof:+.4f}). Gera o score "
            "de retencao territorial."
        )
        return "GO", just

    motivos: list[str] = []
    if not r2_ok:
        motivos.append(
            f"R2_oof={melhor.r2_oof:+.4f} (IC95=[{melhor.r2_ci_low:+.4f}, "
            f"{melhor.r2_ci_high:+.4f}]) nao supera o baseline da media com IC "
            "sem cruzar zero"
        )
    if not rho_ok:
        motivos.append(
            f"rho_oof={melhor.rho_oof:+.4f} (IC95=[{melhor.rho_ci_low:+.4f}, "
            f"{melhor.rho_ci_high:+.4f}]) < {PISO_RHO:.2f} ou IC cruza zero"
        )
    if not supera_base:
        motivos.append(
            f"melhor modelo nao supera '{FEATURE_BASE}' sozinho "
            f"(R2_oof melhor={melhor.r2_oof:+.4f} vs base={base.r2_oof:+.4f})"
        )
    just = (
        "NO-GO: o eixo retencao territorial nao satisfaz o criterio honesto — "
        + "; ".join(motivos)
        + ". Consistente com N pequeno (56) + confound de maturidade + "
        "colinearidade captacao<->retencao. NO-GO e desfecho LEGITIMO (DEC-008): "
        "ENCERRAR sem gerar score (DEC-014 decisao 2); NAO degradar para "
        "`score_priorizacao` como proxy."
    )
    return "NO-GO", just


# --------------------------------------------------------------------------- #
# Calculo do score (aplicado ao universo de hexes)
# --------------------------------------------------------------------------- #
def _fit_final(df_cal: pd.DataFrame, features: tuple[str, ...]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Ajuste FINAL do Ridge sobre TODA a calibracao (so p/ APLICAR aos hexes).

    NAO e usado como desempenho (proibido; DEC-008) — o desempenho ja foi medido
    OUT-OF-FOLD em `validar_eixo_retencao`. Este ajuste existe unicamente para
    projetar a predicao aos hexes candidatos (a magnitude bruta e depois
    re-escalada por percentil nacional). Retorna `(beta, mu, sd)` do padronizador.
    """
    sub = df_cal.dropna(subset=[*features, ALVO])
    x = sub[list(features)].to_numpy(dtype=float)
    y = sub[ALVO].to_numpy(dtype=float)
    mu = x.mean(axis=0)
    sd = x.std(axis=0)
    sd[sd == 0.0] = 1.0
    beta = _ridge_fit((x - mu) / sd, y)
    return beta, mu, sd


def calcular_score_retencao(
    df_hexes: pd.DataFrame,
    df_cal: pd.DataFrame,
    features: tuple[str, ...],
    *,
    w_cap: float = W_CAP,
    w_ret: float = W_RET,
) -> pd.DataFrame:
    """Calcula o score_retencao por hex (schema DEC-014). NAO muta os inputs.

    - `captacao_norm` = `score_priorizacao` LIDO (0-100).
    - `retencao_prevista_territorial` = predicao do Ridge (ajuste final sobre a
      calibracao) aplicada aos hexes com as features disponiveis.
    - `retencao_norm` = 100 * percentil nacional (rank) da predicao (0-100).
    - `score_retencao` = clip(w_cap*captacao_norm + w_ret*retencao_norm, 0, 100).
    - `flag_extrapolacao` = True se ALGUMA feature do hex cai fora do envelope
      [q05, q95] das unidades de calibracao (extrapolacao sinalizada).
    NUNCA escreve em disco nem em path do M1.
    """
    feats = list(features)
    hexes = df_hexes.dropna(subset=feats).copy()

    beta, mu, sd = _fit_final(df_cal, features)
    xh = hexes[feats].to_numpy(dtype=float)
    pred = _ridge_pred(beta, (xh - mu) / sd)

    # Percentil nacional (rank medio, 0-1) -> 0-100. `rank(pct=True)` e determinista.
    retencao_norm = pd.Series(pred, index=hexes.index).rank(pct=True) * 100.0

    captacao_norm = pd.to_numeric(hexes[FEATURE_BASE], errors="coerce").astype(float)
    score = (w_cap * captacao_norm + w_ret * retencao_norm).clip(0.0, 100.0)

    # Envelope de calibracao [q05, q95] por feature -> flag_extrapolacao.
    cal = df_cal.dropna(subset=feats)
    lows = {f: float(cal[f].quantile(0.05)) for f in feats}
    highs = {f: float(cal[f].quantile(0.95)) for f in feats}
    fora = pd.Series(False, index=hexes.index)
    for f in feats:
        col = pd.to_numeric(hexes[f], errors="coerce")
        fora = fora | (col < lows[f]) | (col > highs[f])

    out = pd.DataFrame(
        {
            "hex_id": hexes["hex_id"].astype(str).to_numpy(),
            "captacao_norm": captacao_norm.astype("float64").to_numpy(),
            "retencao_prevista_territorial": np.asarray(pred, dtype="float64"),
            "retencao_norm": retencao_norm.astype("float64").to_numpy(),
            "w_cap": np.full(len(hexes), float(w_cap), dtype="float64"),
            "w_ret": np.full(len(hexes), float(w_ret), dtype="float64"),
            "score_retencao": score.astype("float64").to_numpy(),
            "flag_extrapolacao": fora.astype(bool).to_numpy(),
            "versao_contrato": np.full(len(hexes), VERSAO_CONTRATO, dtype=object),
        }
    )
    return out.reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Relatorio (funcao pura de string, byte-estavel + writer)
# --------------------------------------------------------------------------- #
def _fmt(v: float, nd: int = 4) -> str:
    return f"{v:+.{nd}f}" if np.isfinite(v) else "n/d"


def _linha_modelo(m: ResultadoModelo) -> str:
    ic_r2 = f"[{_fmt(m.r2_ci_low)}, {_fmt(m.r2_ci_high)}]" if np.isfinite(m.r2_ci_low) else "n/d"
    ic_rho = (
        f"[{_fmt(m.rho_ci_low)}, {_fmt(m.rho_ci_high)}]" if np.isfinite(m.rho_ci_low) else "n/d"
    )
    return (
        f"| {m.nome} | {m.n} | {m.protocolo} | {_fmt(m.r2_oof)} | {ic_r2} | "
        f"{_fmt(m.rho_oof)} | {ic_rho} |"
    )


def _montar_relatorio(
    res: ResultadoValidacao, veredito: str, justificativa: str
) -> str:
    """Monta a string markdown do relatorio (funcao PURA; nao toca disco)."""
    L: list[str] = []
    L.append("# Score de retencao territorial (M2) -- BLK-LTV-04")
    L.append("")
    L.append(
        "READ-ONLY sobre o M1 (DEC-001/DEC-008/DEC-009; DEC-014). NAO recalcula "
        "`score_priorizacao`/`hex_score_estrutural`/pesos (renda=0.40/pop=0.60), "
        "carteira, plano nem artefatos oficiais. `score_priorizacao` e apenas o "
        "eixo captacao LIDO."
    )
    L.append("")
    L.append(
        f"Formula (DEC-014, variante A): score_retencao = clip({W_CAP:.2f}*"
        f"captacao_norm + {W_RET:.2f}*retencao_norm, 0, 100). captacao_norm = "
        "score_priorizacao (LIDO); retencao_norm = 100*percentil_nacional("
        "retencao_prevista_territorial)."
    )
    L.append("")
    L.append(
        f"Metodo (DEC-008): eixo retencao calibrado OUT-OF-FOLD (k-fold 5x5 + LOO "
        f"fallback), Ridge em numpy PURO (sem scikit-learn), seed={SEED}, "
        f"IC95 bootstrap ({N_BOOTSTRAP} reamostras). Baseline = media do alvo "
        "fora-de-fold. R2 in-sample e fit(X,y)->predict(X) BANIDOS. Maturidade so "
        "como COVARIAVEL de controle (nunca feature do score por hex)."
    )
    L.append("")
    L.append("## 1. Amostra / calibracao")
    L.append("")
    L.append(
        f"- Alvo: `{ALVO}` (agregado por unidade, eixo ranking do LTV-03)."
    )
    L.append(f"- N de calibracao: **{res.n_calibracao}** unidades (hex_id notna).")
    L.append(f"- Protocolo out-of-fold: **{res.protocolo}** (LOO se N<{N_MIN_KFOLD}).")
    L.append("")
    L.append("## 2. Modelos out-of-fold (Ridge numpy; metricas OOF)")
    L.append("")
    L.append("| variante | N | protocolo | R2_oof | IC95 R2 | rho_oof | IC95 rho |")
    L.append("| --- | ---: | --- | ---: | ---: | ---: | ---: |")
    for m in res.modelos:
        L.append(_linha_modelo(m))
    L.append("")
    L.append("## 3. Confounds (obrigatorios; declarados)")
    L.append("")
    L.append(
        "1. **N pequeno (56)** — variancia alta; R2_oof fraco/negativo e desfecho "
        "honesto, NAO evidencia de ausencia de efeito."
    )
    L.append(
        "2. **Colinearidade captacao<->retencao** — ambos os eixos derivam de "
        "`score_priorizacao`; o eixo retencao pode nao AGREGAR alem do composto "
        "(por isso o criterio exige superar `score_priorizacao` sozinho)."
    )
    L.append(
        "3. **Maturidade nao-controlavel no score** — atributo de UNIDADE; entra "
        "SO como covariavel de validacao, nunca feature do score por hex."
    )
    L.append(
        "4. **Selecao de sobreviventes + 32 sem hex_id (36%)** — universo N=56 "
        "pode nao representar a rede; caveat declarado."
    )
    L.append(
        "5. **TICKET_MEDIO_UNIDADE x LTV +0.626** — mais forte que territorio, mas "
        "atributo de UNIDADE (nao territorial) -> PROIBIDO como feature (DEC-014)."
    )
    L.append("")
    L.append("## 4. Veredito GO/NO-GO (mecanico; DEC-014)")
    L.append("")
    L.append(
        "Regra: **GO** se e somente se o melhor modelo territorial tem R2_oof>0 "
        f"(IC sem cruzar zero) E rho_oof>={PISO_RHO:.2f} (IC sem cruzar zero) E "
        "supera `score_priorizacao` sozinho. Senao **NO-GO** -> ENCERRAR sem "
        "score (DEC-014 decisao 2). NO-GO e resultado VALIDO (DEC-008)."
    )
    L.append("")
    L.append(f"**VEREDITO: {veredito}**")
    L.append("")
    L.append(justificativa)
    L.append("")
    L.append("## 5. Nota de escopo")
    L.append("")
    L.append(
        "PROIBIDO usar qualquer coluna deste modulo como preditor geografico de "
        "magnitude de demanda ou ajuste do `score_priorizacao` (DEC-009). Nenhum "
        f"R2 in-sample reportado como desempenho (DEC-008; rotulo reservado: "
        f'"{_ROTULO_INSAMPLE}"). Output NAO oficial, gitignored.'
    )
    L.append("")
    return "\n".join(L)


def _escrever_relatorio(texto: str, *, path: Path) -> None:
    """Materializa o relatorio markdown (gitignored). NAO chamada em teste de conteudo."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(texto, encoding="utf-8")
    _logger.info("relatorio BLK-LTV-04 escrito: %s", path)


# --------------------------------------------------------------------------- #
# Orquestrador
# --------------------------------------------------------------------------- #
def run(root: Path | None = None) -> tuple[str, ResultadoValidacao]:
    """Le parquets, valida o eixo retencao, e SO em GO grava o parquet de score.

    READ-ONLY sobre o M1: le apenas parquets de staging (calibracao, universo de
    aplicacao, maturidade) e escreve, no maximo, o `.md` gitignored + o parquet
    NAO oficial de score (so em GO). Nenhuma escrita em artefato oficial do M1.

    Em NO-GO (DEC-014 decisao 2): grava o relatorio documentando o NO-GO e
    RETORNA o veredito sem gerar o parquet de score, sem levantar excecao.
    """
    if root is None:
        # src/motor_expansao/lifetime/score_retencao_territorial.py -> parents[3] = raiz
        root = Path(__file__).resolve().parents[3]
    root = Path(root)
    staging = root / "data" / "staging"

    df = _carregar_dataset(staging / "unidade_territorio_retencao.parquet")
    df56 = df[df["hex_id"].notna()].copy()
    df56["_chave_unidade"] = df56["UNIDADE"].map(_normalizar_unidade)

    maturidade = _carregar_maturidade(staging / "growth_api_historico.parquet")
    res = validar_eixo_retencao(df56, maturidade=maturidade)
    veredito, justificativa = _veredito_no_go(res)

    texto = _montar_relatorio(res, veredito, justificativa)
    _escrever_relatorio(texto, path=root / "data" / "analysis" / "relatorio_score_retencao.md")

    if veredito == "GO":
        melhor = res.melhor()
        assert melhor is not None  # GO garante melhor != None
        universo = _carregar_universo_aplicacao(
            staging / "hexagonos_mercado_mapeado.parquet"
        )
        score_df = calcular_score_retencao(universo, df56, melhor.features)
        out_path = staging / "score_retencao_territorial.parquet"
        score_df.to_parquet(out_path, index=False)
        _logger.info("BLK-LTV-04 GO: score gravado (%d hexes) em %s", len(score_df), out_path)
    else:
        _logger.info("BLK-LTV-04 NO-GO: score NAO gerado (DEC-014 decisao 2).")

    return veredito, res


def main() -> None:
    """Entry point para execucao direta."""
    veredito, _res = run()
    _logger.info("BLK-LTV-04 veredito=%s", veredito)


__all__ = [
    "ResultadoModelo",
    "ResultadoValidacao",
    "validar_eixo_retencao",
    "calcular_score_retencao",
    "_veredito_no_go",
    "_bootstrap_ci_r2_rho",
    "_oof_predictions",
    "_carregar_maturidade",
    "_montar_relatorio",
    "W_CAP",
    "W_RET",
    "PISO_RHO",
    "SEED",
    "N_BOOTSTRAP",
    "ALVO",
    "VERSAO_CONTRATO",
    "FEATURE_BASE",
    "FEATURES_CANDIDATAS",
    "run",
    "main",
]


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    main()
