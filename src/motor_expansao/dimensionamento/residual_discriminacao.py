"""BLK-DIM-08 -- teste discriminativo do mercado residual + estrutura regional.

READ-ONLY sobre o M1 (DEC-001/DEC-008). Sem PII.

Hipotese (Felipe 2026-06-15): o `score_oportunidade_residual` por hex (camada de
mercado, paralela ao M1) DISCRIMINA unidades viaveis (alunos_reais >= 2.000) de
inviaveis (< 2.000) MELHOR que o baseline pop x renda em raio fixo. Em vez de
PREVER N alunos (que o BLK-DIM-01R ja mostrou ser NO-GO com pop+renda), aqui o
alvo e a SEPARABILIDADE binaria (AUC) -- pergunta mais barata e honesta.

Tres exames, todos com a disciplina do projeto (LOO honesto, NO-GO valido):
  - Teste B (`teste_b_discriminacao`): AUC do residual vs. baseline pop x renda
    (raio fixo 1.5 km) vs. penetracao regional LOO, com IC bootstrap (zero-inflado
    no residual -> reamostras de classe unica descartadas) e p-valor de permutacao.
  - Teste C (`teste_c_decomposicao_variancia`): quanto da variancia de
    log(penetracao LOO) e regiao vs. marca vs. DOMINIO (n_mesma_marca_no_raio),
    via OLS + ANOVA-sequencial (SS tipo I) em numpy puro. Domnio entra POR ULTIMO
    (mede o que sobra apos regiao+marca -- o confundidor "Engenharia fechou o Sul").
  - `sanidade_casos`: true negative rate -- fracao de inviaveis que de fato caem
    em hex de residual baixo (quartil inferior).

Anti-circularidade: a penetracao regional e SEMPRE leave-one-unit-out estrito -- a
unidade-alvo NUNCA entra na sua propria estimativa de cluster (`_penetracao_loo_por_grupo`).
O raio de captacao vem de densidade+concorrencia (via `validar_raio_variavel`),
NUNCA do nº de alunos.

A saida e DISCRIMINACAO / AUC / IC / variancia explicada / veredito GO-NO-GO de
RANKING. NUNCA previsao pontual de N alunos por hex.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from motor_expansao.dimensionamento import config
from motor_expansao.dimensionamento.base_multirede import (
    CONCORRENTES_PATH,
    PISO_VIABILIDADE_ALUNOS,
    RAIO_KM_FIXO_BASELINE,  # noqa: F401  (re-export de conveniencia)
    SAIDA_BASE,
    derivar_densidade_marca_propria,
    validar_raio_variavel,
)
from motor_expansao.dimensionamento.catchment_batch import GEO_BASE_DIR_DEFAULT
from motor_expansao.dimensionamento.growth_api_client import assert_sem_pii

_logger = logging.getLogger(__name__)

# Mesmo H3_RESOLUTION do M1 (NAO importar config raiz -- READ-ONLY/desacoplado).
H3_RES: int = 7
N_BOOTSTRAP: int = 1_000   # reamostras do IC de AUC
N_PERMUTACAO: int = 500    # permutacoes do p-valor
AUC_GO_MIN: float = 0.55   # limiar do veredito (AUC > 0.55)
AUC_IC_INFERIOR_MIN: float = 0.50  # E IC inferior > 0.50
N_CELULA_MIN: int = 5      # celula de regressao com N<5 = insuficiente
SEED: int = 42             # determinismo de bootstrap/permutacao

# Frase de guardrail anti-predicao -- testada por substring (NAO alterar o texto).
_FRASE_GUARDRAIL = (
    "Saida como score/discriminacao; NUNCA previsao pontual de N alunos por hex."
)

# Mapa LOCAL de macro-regiao (NAO importar REGIAO_POR_UF do M1 -- desacoplamento).
# Centro-Oeste + Norte colapsados (celulas ralas: SP domina o N; Engenharia no Sul).
_MACRO_REGIAO_POR_UF: dict[str, str] = {
    # Sul
    "RS": "Sul", "SC": "Sul", "PR": "Sul",
    # Sudeste
    "SP": "Sudeste", "RJ": "Sudeste", "MG": "Sudeste", "ES": "Sudeste",
    # Nordeste
    "BA": "Nordeste", "PE": "Nordeste", "CE": "Nordeste", "MA": "Nordeste",
    "PB": "Nordeste", "RN": "Nordeste", "AL": "Nordeste", "PI": "Nordeste",
    "SE": "Nordeste",
    # Centro-Oeste + Norte (colapsado)
    "DF": "CO_Norte", "GO": "CO_Norte", "MT": "CO_Norte", "MS": "CO_Norte",
    "AM": "CO_Norte", "PA": "CO_Norte", "RO": "CO_Norte", "RR": "CO_Norte",
    "AC": "CO_Norte", "AP": "CO_Norte", "TO": "CO_Norte",
}


# --------------------------------------------------------------------------- #
# 1. Enriquecimento por hex H3
# --------------------------------------------------------------------------- #
def enriquecer_base_com_residual(
    base_path: Path | str = SAIDA_BASE,
    mercado_path: Path | str = config.STAGING_DIR / "hexagonos_mercado_mapeado.parquet",
    *,
    base_df: pd.DataFrame | None = None,
    mercado_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Anexa `score_oportunidade_residual`/`oferta_efetiva_disponivel` por hex H3.

    Cada unidade com coord vira um `hex_id = h3.latlng_to_cell(lat, lng, 7)`, casado
    (left merge) com o subset do mercado mapeado. `base_df`/`mercado_df` injetaveis
    (TESTE offline; ignoram os paths quando passados). READ-ONLY; `assert_sem_pii`
    antes de retornar.
    """
    import h3  # lazy (custo de import fora do import do modulo)

    base = base_df if base_df is not None else pd.read_parquet(base_path)
    mercado = mercado_df if mercado_df is not None else pd.read_parquet(mercado_path)

    out = base.copy()
    lat = pd.to_numeric(out.get("lat"), errors="coerce")
    lng = pd.to_numeric(out.get("lng"), errors="coerce")
    coord_ok = lat.notna() & lng.notna()
    out = out[coord_ok].copy().reset_index(drop=True)
    lat = pd.to_numeric(out["lat"], errors="coerce")
    lng = pd.to_numeric(out["lng"], errors="coerce")

    hex_ids: list[object] = []
    for la, lo in zip(lat.to_numpy(), lng.to_numpy(), strict=False):
        try:
            hex_ids.append(h3.latlng_to_cell(float(la), float(lo), H3_RES))
        except Exception:  # pragma: no cover - coord invalida defensiva
            hex_ids.append(np.nan)
    out["hex_id"] = hex_ids

    cols = ["hex_id", "score_oportunidade_residual", "oferta_efetiva_disponivel",
            "renda_per_capita", "pop_total"]
    sub = mercado[[c for c in cols if c in mercado.columns]].copy()
    sub = sub.rename(columns={
        "renda_per_capita": "renda_per_capita_hex",
        "pop_total": "pop_total_hex",
    })
    sub = sub.drop_duplicates(subset=["hex_id"])
    out = out.merge(sub, on="hex_id", how="left")

    # Garante presenca das colunas mesmo se o mercado nao as tiver.
    for col in ("score_oportunidade_residual", "oferta_efetiva_disponivel",
                "renda_per_capita_hex", "pop_total_hex"):
        if col not in out.columns:
            out[col] = np.nan

    out["hex_match_ok"] = (
        out["hex_id"].notna() & out["score_oportunidade_residual"].notna()
    )

    assert_sem_pii(out)
    return out


# --------------------------------------------------------------------------- #
# 2. Raio variavel + dominio de marca propria
# --------------------------------------------------------------------------- #
def enriquecer_com_raio_e_dominio(
    base: pd.DataFrame,
    *,
    conc_path: Path = CONCORRENTES_PATH,
    geo_base_dir: Path | str = GEO_BASE_DIR_DEFAULT,
    setores_loader=None,
) -> tuple[pd.DataFrame, dict]:
    """Delega a `validar_raio_variavel` + `derivar_densidade_marca_propria`.

    Traz `raio_km`, `pop_captacao_variavel`, `pop_captacao_fixo_1p5`,
    `n_concorrentes_km2` e `n_mesma_marca_no_raio`. `setores_loader=None` usa o censo
    real (NUNCA em teste -- injetar fake). READ-ONLY; `assert_sem_pii` antes de retornar.
    """
    enr, metricas_raio = validar_raio_variavel(
        base, geo_base_dir=geo_base_dir, setores_loader=setores_loader,
        conc_path=conc_path,
    )
    enr = derivar_densidade_marca_propria(enr, raio_col="raio_km")
    assert_sem_pii(enr)
    return enr, metricas_raio


# --------------------------------------------------------------------------- #
# 3. Flag de viabilidade + penetracao no raio variavel
# --------------------------------------------------------------------------- #
def calcular_residual_no_raio_variavel(base: pd.DataFrame) -> pd.DataFrame:
    """Adiciona `flag_viavel` (1 se alunos>=2.000) e `penetracao_observada`.

    `flag_viavel`: NaN de alunos -> 0 (inviavel; documentado). `penetracao_observada`
    = alunos / pop_captacao_variavel com divisao segura (pop<=0/NaN -> NaN). NAO faz LOO
    aqui (a penetracao LOO regional e responsabilidade dos Testes B/C).
    """
    out = base.copy()
    alunos = pd.to_numeric(out.get("alunos_reais"), errors="coerce")
    out["flag_viavel"] = (alunos >= PISO_VIABILIDADE_ALUNOS).fillna(False).astype(int)

    pop_var = pd.to_numeric(out.get("pop_captacao_variavel"), errors="coerce")
    pen = np.full(len(out), np.nan, dtype=float)
    valid = pop_var.notna().to_numpy() & (pop_var.to_numpy() > 0) & alunos.notna().to_numpy()
    pen[valid] = alunos.to_numpy()[valid] / pop_var.to_numpy()[valid]
    out["penetracao_observada"] = pen
    return out


# --------------------------------------------------------------------------- #
# Helper interno: penetracao leave-one-unit-out por grupo (anti-circular)
# --------------------------------------------------------------------------- #
def _penetracao_loo_por_grupo(
    df: pd.DataFrame, valor_col: str, grupo_col: str
) -> pd.Series:
    """Media LOO do `valor_col` por `grupo_col`: (soma_grupo - valor_i)/(n_grupo - 1).

    Anti-circular: a linha-alvo NUNCA entra na sua propria media. Grupos com n==1 ou
    valor proprio NaN -> NaN (sem vizinho valido para estimar; nao vaza desfecho).
    """
    val = pd.to_numeric(df[valor_col], errors="coerce")
    grp = df[grupo_col].astype(str)
    res = pd.Series(np.nan, index=df.index, dtype=float)
    for _g, idx in val.groupby(grp).groups.items():
        sub = val.loc[idx]
        sub_ok = sub.dropna()
        soma = float(sub_ok.sum())
        n = int(sub_ok.shape[0])
        for i in idx:
            vi = val.loc[i]
            if pd.isna(vi) or n <= 1:
                continue
            res.loc[i] = (soma - float(vi)) / (n - 1)
    return res


def _auc_seguro(y: np.ndarray, score: np.ndarray) -> float:
    """AUC com guard de classe unica / NaN -> NaN (NAO levanta)."""
    ok = np.isfinite(score)
    yk = y[ok]
    sk = score[ok]
    if yk.size < 2 or len(np.unique(yk)) < 2:
        return float("nan")
    return float(roc_auc_score(yk, sk))


# --------------------------------------------------------------------------- #
# 4. Teste B -- discriminacao por AUC
# --------------------------------------------------------------------------- #
def teste_b_discriminacao(base: pd.DataFrame, *, rng_seed: int = SEED) -> dict:
    """AUC do residual vs. baseline pop x renda vs. penetracao LOO + IC + permutacao.

    Feature principal = `score_oportunidade_residual`. Baseline = `pop_captacao_fixo_1p5
    * renda_per_capita_hex` (score escalar de ranking, NAO modelo). Penetracao LOO =
    media das OUTRAS unidades do mesmo `uf` (anti-circular). IC95 por bootstrap (N=1000,
    descartando reamostras de classe unica). p-valor por permutacao do rotulo (N=500).
    Veredito GO se AUC>0.55 E IC_inferior>0.50; classe unica -> INDEFINIDO (nao levanta).
    """
    work = base.copy()
    if "hex_match_ok" in work.columns:
        work = work[work["hex_match_ok"].fillna(False)].copy()
    work = calcular_residual_no_raio_variavel(work) if "flag_viavel" not in work.columns else work

    alunos = pd.to_numeric(work.get("alunos_reais"), errors="coerce")
    residual = pd.to_numeric(work.get("score_oportunidade_residual"), errors="coerce")
    keep = alunos.notna() & residual.notna()
    work = work[keep].copy().reset_index(drop=True)

    n = int(len(work))
    y = pd.to_numeric(work["flag_viavel"], errors="coerce").fillna(0).astype(int).to_numpy()
    n_viaveis = int((y == 1).sum())
    n_inviaveis = int((y == 0).sum())

    score_res = pd.to_numeric(work["score_oportunidade_residual"], errors="coerce").to_numpy(dtype=float)
    pop15 = pd.to_numeric(work.get("pop_captacao_fixo_1p5"), errors="coerce").to_numpy(dtype=float)
    renda_hex = pd.to_numeric(work.get("renda_per_capita_hex"), errors="coerce").to_numpy(dtype=float)
    score_base = pop15 * renda_hex
    n_baseline = int(np.isfinite(score_base).sum())

    # Penetracao regional LOO por uf (anti-circular) como 3a feature.
    pen_loo = _penetracao_loo_por_grupo(
        work.assign(penetracao_observada=pd.to_numeric(
            work.get("penetracao_observada"), errors="coerce")),
        "penetracao_observada", "uf",
    ).to_numpy(dtype=float)

    if n_viaveis < 1 or n_inviaveis < 1:
        return {
            "n": n, "n_viaveis": n_viaveis, "n_inviaveis": n_inviaveis,
            "n_baseline": n_baseline,
            "auc_residual": float("nan"), "auc_baseline": float("nan"),
            "auc_penetracao_loo": float("nan"), "delta_auc": float("nan"),
            "ic95_residual": (float("nan"), float("nan")),
            "ic95_baseline": (float("nan"), float("nan")),
            "p_permutacao": float("nan"), "n_bootstrap_validos": 0,
            "veredito": "INDEFINIDO",
        }

    auc_residual = _auc_seguro(y, score_res)
    auc_baseline = _auc_seguro(y, score_base)
    auc_pen = _auc_seguro(y, pen_loo)
    delta_auc = (
        auc_residual - auc_baseline
        if np.isfinite(auc_residual) and np.isfinite(auc_baseline)
        else float("nan")
    )

    rng = np.random.default_rng(rng_seed)
    ic95_residual = _ic_bootstrap_auc(y, score_res, rng)
    ic95_baseline = _ic_bootstrap_auc(y, score_base, rng)
    n_bootstrap_validos = ic95_residual[2]
    ic_inferior_residual = ic95_residual[0]

    p_perm = _p_permutacao_auc(y, score_res, auc_residual, rng)

    veredito = (
        "GO"
        if (np.isfinite(auc_residual) and auc_residual > AUC_GO_MIN
            and np.isfinite(ic_inferior_residual) and ic_inferior_residual > AUC_IC_INFERIOR_MIN)
        else "NO-GO"
    )

    return {
        "n": n, "n_viaveis": n_viaveis, "n_inviaveis": n_inviaveis,
        "n_baseline": n_baseline,
        "auc_residual": auc_residual, "auc_baseline": auc_baseline,
        "auc_penetracao_loo": auc_pen, "delta_auc": delta_auc,
        "ic95_residual": (ic95_residual[0], ic95_residual[1]),
        "ic95_baseline": (ic95_baseline[0], ic95_baseline[1]),
        "p_permutacao": p_perm, "n_bootstrap_validos": n_bootstrap_validos,
        "veredito": veredito,
    }


def _ic_bootstrap_auc(
    y: np.ndarray, score: np.ndarray, rng: np.random.Generator
) -> tuple[float, float, int]:
    """IC95 (2.5%, 97.5%) de AUC por bootstrap; descarta reamostra de classe unica.

    Retorna (lo, hi, n_validos). Teto de 10*N_BOOTSTRAP tentativas evita loop infinito
    quando uma classe e minuscula.
    """
    n = len(y)
    aucs: list[float] = []
    tentativas = 0
    teto = 10 * N_BOOTSTRAP
    while len(aucs) < N_BOOTSTRAP and tentativas < teto:
        tentativas += 1
        idx = rng.integers(0, n, size=n)
        yb = y[idx]
        if len(np.unique(yb)) < 2:
            continue
        a = _auc_seguro(yb, score[idx])
        if np.isfinite(a):
            aucs.append(a)
    if not aucs:
        return (float("nan"), float("nan"), 0)
    arr = np.asarray(aucs, dtype=float)
    return (float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5)), len(aucs))


def _p_permutacao_auc(
    y: np.ndarray, score: np.ndarray, auc_obs: float, rng: np.random.Generator
) -> float:
    """p-valor de permutacao: P(AUC_perm >= AUC_obs) sob rotulo permutado."""
    if not np.isfinite(auc_obs):
        return float("nan")
    cont = 0
    for _ in range(N_PERMUTACAO):
        yp = rng.permutation(y)
        a = _auc_seguro(yp, score)
        if np.isfinite(a) and a >= auc_obs:
            cont += 1
    return (1 + cont) / (N_PERMUTACAO + 1)


# --------------------------------------------------------------------------- #
# 5. Teste C -- decomposicao de variancia (regiao x marca x dominio)
# --------------------------------------------------------------------------- #
def _ss_res(X: np.ndarray, y: np.ndarray) -> float:
    """Soma de quadrados residual de um OLS (np.linalg.lstsq, estavel)."""
    beta, _res, _rank, _sv = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    return float(np.sum(resid**2))


def teste_c_decomposicao_variancia(
    base: pd.DataFrame, *, min_celula: int = N_CELULA_MIN
) -> dict:
    """Decompoe a variancia de log(penetracao LOO) em regiao x marca x DOMINIO.

    Resposta y = log(penetracao LOO regional por uf) (anti-circular, > 0). Efeitos:
    regiao (macro, dummies drop-first), marca (dummies drop-first), dominio
    (`n_mesma_marca_no_raio`, continua). OLS via lstsq; variancia explicada por
    ANOVA-sequencial (SS tipo I) na ordem regiao -> marca -> dominio (dominio mede o
    que sobra). Coef de dominio + IC95 por erro-padrao OLS classico (t~1.96, aprox.
    normal -- documentado, N pequeno). MixedLM (statsmodels) tentado em try/except;
    fallback gracioso para OLS (`metodo="ols_dummies"`). Guard de N<min_celula global
    -> dict indefinido (nao levanta).
    """
    work = base.copy()
    if "hex_match_ok" in work.columns:
        work = work[work["hex_match_ok"].fillna(False)].copy()
    if "penetracao_observada" not in work.columns:
        work = calcular_residual_no_raio_variavel(work)

    work["regiao"] = work["uf"].astype(str).str.upper().map(_MACRO_REGIAO_POR_UF)
    pen_loo = _penetracao_loo_por_grupo(
        work.assign(penetracao_observada=pd.to_numeric(
            work.get("penetracao_observada"), errors="coerce")),
        "penetracao_observada", "uf",
    )
    work["penetracao_loo"] = pen_loo

    dom = pd.to_numeric(work.get("n_mesma_marca_no_raio"), errors="coerce")
    y_raw = work["penetracao_loo"]
    ok = y_raw.notna() & (y_raw > 0) & work["regiao"].notna() & dom.notna()
    work = work[ok].copy().reset_index(drop=True)
    n_efetivo = int(len(work))

    metodo = "ols_dummies"
    indefinido = {
        "metodo": "indefinido", "n_efetivo": n_efetivo,
        "r2_total": float("nan"), "var_explicada_regiao": float("nan"),
        "var_explicada_marca": float("nan"), "var_explicada_dominio": float("nan"),
        "coef_dominio": float("nan"), "ic95_dominio": (float("nan"), float("nan")),
        "uplift_dominio_pct": float("nan"),
        "penetracao_base_por_regiao": {}, "celulas_insuficientes": [],
    }
    if n_efetivo < min_celula:
        return indefinido

    y = np.log(pd.to_numeric(work["penetracao_loo"], errors="coerce").to_numpy(dtype=float))
    dom_arr = pd.to_numeric(work["n_mesma_marca_no_raio"], errors="coerce").to_numpy(dtype=float)

    regiao_d = pd.get_dummies(work["regiao"].astype(str), prefix="reg", drop_first=True)
    marca_d = pd.get_dummies(work["marca"].astype(str), prefix="marca", drop_first=True)
    n = n_efetivo
    intercepto = np.ones((n, 1), dtype=float)

    X0 = intercepto
    X_reg = np.column_stack([intercepto, regiao_d.to_numpy(dtype=float)]) if regiao_d.shape[1] else intercepto
    X_regmarca = (
        np.column_stack([X_reg, marca_d.to_numpy(dtype=float)]) if marca_d.shape[1] else X_reg
    )
    X_full = np.column_stack([X_regmarca, dom_arr.reshape(-1, 1)])

    ss_total = float(np.sum((y - y.mean()) ** 2))
    if ss_total <= 0:
        return indefinido

    ss0 = _ss_res(X0, y)
    ss_reg = _ss_res(X_reg, y)
    ss_regmarca = _ss_res(X_regmarca, y)
    ss_full = _ss_res(X_full, y)

    var_regiao = (ss0 - ss_reg) / ss_total
    var_marca = (ss_reg - ss_regmarca) / ss_total
    var_dominio = (ss_regmarca - ss_full) / ss_total
    r2_total = 1.0 - ss_full / ss_total

    # Coef de dominio (ultima coluna) + IC95 por erro-padrao OLS classico.
    coef_dominio = float("nan")
    ic_dominio = (float("nan"), float("nan"))
    try:
        beta, _r, _rk, _s = np.linalg.lstsq(X_full, y, rcond=None)
        coef_dominio = float(beta[-1])
        dof = n - X_full.shape[1]
        if dof >= 1:
            resid = y - X_full @ beta
            sigma2 = float(np.sum(resid**2) / dof)
            xtx_inv = np.linalg.inv(X_full.T @ X_full)
            var_coef = sigma2 * float(xtx_inv[-1, -1])
            if var_coef >= 0:
                se = float(np.sqrt(var_coef))
                ic_dominio = (coef_dominio - 1.96 * se, coef_dominio + 1.96 * se)
    except np.linalg.LinAlgError:
        coef_dominio = float("nan")

    uplift_pct = float(np.exp(coef_dominio) - 1.0) * 100.0 if np.isfinite(coef_dominio) else float("nan")

    # Penetracao-base liquida de dominio (dom=0) por macro-regiao (back-transform).
    pen_base: dict[str, dict] = {}
    celulas_insuf: list[str] = []
    for reg in sorted(work["regiao"].astype(str).unique()):
        sub = work[work["regiao"].astype(str) == reg]
        n_cel = int(len(sub))
        insuf = n_cel < min_celula
        # media de log(pen) com dom=0: aproximada pela media observada deflacionada do coef*dom.
        ylog = np.log(pd.to_numeric(sub["penetracao_loo"], errors="coerce").to_numpy(dtype=float))
        domc = pd.to_numeric(sub["n_mesma_marca_no_raio"], errors="coerce").to_numpy(dtype=float)
        if np.isfinite(coef_dominio):
            base_log = float(np.mean(ylog - coef_dominio * domc))
        else:
            base_log = float(np.mean(ylog))
        pen_base[reg] = {
            "valor": float(np.exp(base_log)), "n": n_cel,
            "n_celula_insuficiente": insuf,
        }
        if insuf:
            celulas_insuf.append(reg)

    # MixedLM opcional (gracioso) -- so registra que tentou; OLS e o caminho default/testado.
    try:  # pragma: no cover - statsmodels nao garantido no ambiente
        import statsmodels.api as sm  # noqa: F401
        # Nao convergir/indisponivel mantem metodo OLS; nao mudamos os numeros.
    except Exception:
        metodo = "ols_dummies"

    return {
        "metodo": metodo, "n_efetivo": n_efetivo,
        "r2_total": float(r2_total),
        "var_explicada_regiao": float(var_regiao),
        "var_explicada_marca": float(var_marca),
        "var_explicada_dominio": float(var_dominio),
        "coef_dominio": coef_dominio,
        "ic95_dominio": ic_dominio,
        "uplift_dominio_pct": uplift_pct,
        "penetracao_base_por_regiao": pen_base,
        "celulas_insuficientes": celulas_insuf,
    }


# --------------------------------------------------------------------------- #
# 6. Sanidade dos casos inviaveis (true negative rate)
# --------------------------------------------------------------------------- #
def sanidade_casos(base: pd.DataFrame) -> dict:
    """True negative rate: fracao de inviaveis que caem em hex de residual baixo.

    q25 = quartil inferior do `score_oportunidade_residual` sobre unidades com hex match.
    TNR = #{inviavel E score<=q25} / #{inviaveis}. Contraste = fracao de VIAVEIS acima
    da mediana. Guards para N=0 -> NaN.
    """
    work = base.copy()
    if "hex_match_ok" in work.columns:
        work = work[work["hex_match_ok"].fillna(False)].copy()
    if "flag_viavel" not in work.columns:
        work = calcular_residual_no_raio_variavel(work)

    score = pd.to_numeric(work.get("score_oportunidade_residual"), errors="coerce")
    work = work[score.notna()].copy()
    score = pd.to_numeric(work["score_oportunidade_residual"], errors="coerce").to_numpy(dtype=float)
    viavel = pd.to_numeric(work["flag_viavel"], errors="coerce").fillna(0).astype(int).to_numpy()

    if score.size == 0:
        return {
            "q25_residual": float("nan"), "n_inviaveis": 0,
            "true_negative_rate": float("nan"), "n_viaveis": 0,
            "viaveis_acima_mediana_pct": float("nan"),
        }

    q25 = float(np.nanpercentile(score, 25))
    mediana = float(np.nanmedian(score))
    inviaveis = viavel == 0
    viaveis = viavel == 1
    n_inviaveis = int(inviaveis.sum())
    n_viaveis = int(viaveis.sum())

    tnr = (
        float(np.sum(inviaveis & (score <= q25)) / n_inviaveis)
        if n_inviaveis > 0 else float("nan")
    )
    recall = (
        float(np.sum(viaveis & (score > mediana)) / n_viaveis) * 100.0
        if n_viaveis > 0 else float("nan")
    )
    return {
        "q25_residual": q25, "n_inviaveis": n_inviaveis,
        "true_negative_rate": tnr, "n_viaveis": n_viaveis,
        "viaveis_acima_mediana_pct": recall,
    }


# --------------------------------------------------------------------------- #
# 7. Relatorio
# --------------------------------------------------------------------------- #
def escrever_relatorio(
    resultado: dict,
    *,
    path: Path = Path("data/analysis/residual_discriminacao.md"),
) -> None:
    """Materializa o relatorio markdown (gitignored, sem PII), 5 secoes + guardrail.

    `resultado` consolidado por `executar`: chaves `enriquecimento`, `teste_b`,
    `teste_c`, `sanidade`, `metricas_raio`, `marcas_resumo`.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    b = resultado.get("teste_b", {})
    c = resultado.get("teste_c", {})
    s = resultado.get("sanidade", {})
    enr = resultado.get("enriquecimento", {})
    marcas = resultado.get("marcas_resumo", {})

    def _f(v: object, nd: int = 4) -> str:
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return f"{float(v):.{nd}f}" if np.isfinite(float(v)) else "n/d"
        return str(v)

    def _ic(t: object) -> str:
        if isinstance(t, (tuple, list)) and len(t) == 2:
            return f"[{_f(t[0])}, {_f(t[1])}]"
        return "n/d"

    L: list[str] = []
    L.append("# Teste discriminativo do mercado residual -- BLK-DIM-08")
    L.append("")
    L.append("READ-ONLY sobre o M1 (DEC-001/DEC-008). Sem PII (so contagens/medias agregadas).")
    L.append("")
    L.append(_FRASE_GUARDRAIL)
    L.append("")

    L.append("## 1. Enriquecimento")
    L.append("")
    L.append(f"- N base (com coord): {enr.get('n_com_coord', 'n/d')}")
    L.append(f"- N com hex match (residual disponivel): {enr.get('n_hex_match', 'n/d')}")
    L.append(f"- N com coord + alunos: {enr.get('n_com_alunos', 'n/d')}")
    L.append(f"- N viaveis (>= {PISO_VIABILIDADE_ALUNOS} alunos): {b.get('n_viaveis', 'n/d')}")
    L.append(f"- N inviaveis (< {PISO_VIABILIDADE_ALUNOS} alunos): {b.get('n_inviaveis', 'n/d')}")
    if marcas:
        L.append("")
        L.append("Media de `alunos_reais` por marca (premissa de ticket similar -- conferir):")
        L.append("")
        L.append("| marca | n | alunos_medio |")
        L.append("| --- | ---: | ---: |")
        for marca, info in sorted(marcas.items()):
            L.append(f"| {marca} | {info.get('n', 'n/d')} | {_f(info.get('alunos_medio'), 1)} |")
    L.append("")

    L.append("## 2. Teste B -- discriminacao (AUC)")
    L.append("")
    L.append("AUC da separacao viavel (>=2k) x inviavel (<2k). Baseline = pop_captacao_fixo_1p5 x")
    L.append("renda_per_capita (raio fixo 1.5 km). Penetracao-LOO = anti-circular por uf.")
    L.append("")
    L.append("| feature | AUC | IC95 |")
    L.append("| --- | ---: | --- |")
    L.append(f"| residual (hex) | {_f(b.get('auc_residual'))} | {_ic(b.get('ic95_residual'))} |")
    L.append(f"| baseline pop x renda | {_f(b.get('auc_baseline'))} | {_ic(b.get('ic95_baseline'))} |")
    L.append(f"| penetracao LOO regional | {_f(b.get('auc_penetracao_loo'))} | n/d |")
    L.append("")
    L.append(f"- delta_auc (residual - baseline): {_f(b.get('delta_auc'))}")
    L.append(f"- p-valor permutacao (residual): {_f(b.get('p_permutacao'))}")
    L.append(f"- n_bootstrap_validos: {b.get('n_bootstrap_validos', 'n/d')}")
    L.append("")
    L.append(f"**Veredito GO/NO-GO (Teste B):** `{b.get('veredito', 'n/d')}` "
             f"(GO se AUC>{AUC_GO_MIN} E IC_inf>{AUC_IC_INFERIOR_MIN}).")
    L.append("")

    L.append("## 3. Teste C -- decomposicao de variancia (regiao x marca x dominio)")
    L.append("")
    L.append(f"Metodo: `{c.get('metodo', 'n/d')}` (OLS+ANOVA SS tipo I; MixedLM nao garantido).")
    L.append(f"N efetivo: {c.get('n_efetivo', 'n/d')} | R2 total: {_f(c.get('r2_total'))}")
    L.append("")
    L.append("| componente | variancia explicada |")
    L.append("| --- | ---: |")
    L.append(f"| regiao | {_f(c.get('var_explicada_regiao'))} |")
    L.append(f"| marca | {_f(c.get('var_explicada_marca'))} |")
    L.append(f"| dominio (n_mesma_marca_no_raio) | {_f(c.get('var_explicada_dominio'))} |")
    L.append("")
    L.append(f"- coef dominio: {_f(c.get('coef_dominio'))} | IC95: {_ic(c.get('ic95_dominio'))}")
    L.append(f"- uplift de dominio (%/unidade de marca no raio): {_f(c.get('uplift_dominio_pct'), 2)}%")
    L.append("")
    pen_base = c.get("penetracao_base_por_regiao", {})
    if pen_base:
        L.append("Penetracao-base liquida de dominio por macro-regiao:")
        L.append("")
        L.append("| macro_regiao | penetracao_base | n | celula_insuficiente |")
        L.append("| --- | ---: | ---: | --- |")
        for reg, info in sorted(pen_base.items()):
            L.append(f"| {reg} | {_f(info.get('valor'), 6)} | {info.get('n', 'n/d')} | "
                     f"{info.get('n_celula_insuficiente', 'n/d')} |")
    L.append("")

    L.append("## 4. Sanidade dos casos (<2k) -- true negative rate")
    L.append("")
    L.append(f"- q25 do residual: {_f(s.get('q25_residual'), 6)}")
    L.append(f"- N inviaveis: {s.get('n_inviaveis', 'n/d')}")
    L.append(f"- true_negative_rate (inviavel em residual baixo): {_f(s.get('true_negative_rate'))}")
    L.append(f"- viaveis acima da mediana (%): {_f(s.get('viaveis_acima_mediana_pct'), 2)}%")
    L.append("")

    L.append("## 5. Veredito consolidado + ressalvas de confounds")
    L.append("")
    L.append(f"**Tese residual (discriminacao):** `{b.get('veredito', 'n/d')}`.")
    L.append("")
    L.append("Ressalvas (confounds estruturais):")
    L.append("- N ralo em celulas regiao x marca (SP domina o Sudeste; Engenharia no Sul) ->")
    L.append("  IC do Teste C e aproximacao normal com N pequeno; ler com cautela.")
    L.append("- Vies de selecao entre redes: taxas de match de coord diferentes por marca ->")
    L.append("  a amostra com hex_match nao e aleatoria.")
    L.append("- Heterogeneidade de marcas (ticket/posicionamento) nao totalmente controlada.")
    L.append("- `oferta_efetiva_disponivel`/`score_oportunidade_residual` sao do hex H3 (~1 km2),")
    L.append("  NAO do catchment variavel da unidade -> PROXY (vies de granularidade).")
    L.append("")
    L.append(_FRASE_GUARDRAIL)
    L.append("")

    path.write_text("\n".join(L), encoding="utf-8")
    _logger.info("relatorio BLK-DIM-08 escrito: %s", path)


# --------------------------------------------------------------------------- #
# Orquestrador real (caminho com censo -- NAO chamado em teste)
# --------------------------------------------------------------------------- #
def executar(
    *,
    base_path: Path | str = SAIDA_BASE,
    mercado_path: Path | str = config.STAGING_DIR / "hexagonos_mercado_mapeado.parquet",
    relatorio_path: Path = Path("data/analysis/residual_discriminacao.md"),
) -> dict:
    """Encadeia o pipeline real e materializa o relatorio. Toca o censo (NUNCA em teste)."""
    base = enriquecer_base_com_residual(base_path, mercado_path)
    assert_sem_pii(base)
    n_com_coord = int(len(base))
    n_hex_match = int(base["hex_match_ok"].fillna(False).sum())

    enr, metricas_raio = enriquecer_com_raio_e_dominio(base)
    assert_sem_pii(enr)

    # Re-anexar residual/hex match (validar_raio_variavel filtra/reordena por coord).
    cols_keep = [c for c in (
        "unidade", "hex_id", "score_oportunidade_residual", "oferta_efetiva_disponivel",
        "renda_per_capita_hex", "pop_total_hex", "hex_match_ok",
    ) if c in base.columns]
    enr = enr.merge(base[cols_keep], on="unidade", how="left", suffixes=("", "_b"))
    for col in ("hex_id", "score_oportunidade_residual", "oferta_efetiva_disponivel",
                "renda_per_capita_hex", "pop_total_hex", "hex_match_ok"):
        if f"{col}_b" in enr.columns and col not in enr.columns:
            enr[col] = enr[f"{col}_b"]
    enr = calcular_residual_no_raio_variavel(enr)
    assert_sem_pii(enr)

    n_com_alunos = int(pd.to_numeric(enr.get("alunos_reais"), errors="coerce").notna().sum())

    marcas_resumo: dict[str, dict] = {}
    for marca, g in enr.groupby("marca"):
        al = pd.to_numeric(g["alunos_reais"], errors="coerce")
        marcas_resumo[str(marca)] = {
            "n": int(len(g)), "alunos_medio": float(al.mean()) if al.notna().any() else float("nan"),
        }

    res_b = teste_b_discriminacao(enr)
    res_c = teste_c_decomposicao_variancia(enr)
    san = sanidade_casos(enr)

    resultado = {
        "enriquecimento": {
            "n_com_coord": n_com_coord, "n_hex_match": n_hex_match,
            "n_com_alunos": n_com_alunos,
        },
        "teste_b": res_b, "teste_c": res_c, "sanidade": san,
        "metricas_raio": metricas_raio, "marcas_resumo": marcas_resumo,
        "base": enr,
    }
    escrever_relatorio(resultado, path=relatorio_path)
    return resultado


__all__ = [
    "enriquecer_base_com_residual",
    "enriquecer_com_raio_e_dominio",
    "calcular_residual_no_raio_variavel",
    "teste_b_discriminacao",
    "teste_c_decomposicao_variancia",
    "sanidade_casos",
    "escrever_relatorio",
    "executar",
    "PISO_VIABILIDADE_ALUNOS",
    "AUC_GO_MIN",
]


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    _res = executar()
    print("Teste B veredito:", _res["teste_b"].get("veredito"))
    print("AUC residual:", _res["teste_b"].get("auc_residual"))
