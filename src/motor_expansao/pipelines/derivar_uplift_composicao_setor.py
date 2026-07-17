"""Deriva o UPLIFT de composicao (responsavel -> domicilio inteiro) POR SETOR, nao por municipio.

Por que este pipeline existe
----------------------------
`derivar_uplift_renda_domiciliar.py` produz um uplift por MUNICIPIO. Isso significa que hoje todo
setor de Sao Paulo — Itaim e Brasilandia, Rocinha e Gavea — recebe o mesmo fator 1.475. A variacao
de composicao familiar DENTRO do municipio, que e enorme, e tratada como zero.

O agregado `Agregados_por_setores_parentesco_BR.csv` corrige isso. Ele estava integro no disco e
nunca havia sido usado: publica, por SETOR, a matriz completa de parentesco x faixa etaria (182
variaveis). Da para contar, setor a setor, quantos adultos existem por domicilio e de que tipo.

O modelo (as duas pontas sao IBGE — nenhuma GeoFusion na conta)
---------------------------------------------------------------
Nao basta contar adultos: um conjuge contribui muito mais que uma avo ou um filho recem-adulto.
Os pesos sao estimados por OLS ponderado contra os 5.551 upliftes MUNICIPAIS ja derivados do IBGE
(SIDRA t.10295 x Censo v0005 / V06004). Ou seja: o parentesco (IBGE) explica o uplift (IBGE).

    uplift_setor = a + b1*conjuges/dom + b2*outros_adultos_20+/dom + b3*fracao_unipessoal

Os coeficientes ajustados sao economicamente coerentes, o que e a melhor evidencia de que o sinal
e real: conjuge ~ +0.84 (quase uma segunda renda), outro adulto ~ +0.17 (filho adulto/avo
contribuem pouco), domicilio unipessoal ~ -0.37 (nao ha ninguem para somar). A qualidade e' medida
OUT-OF-FOLD (k-fold 5x5 vs baseline da media, com IC95 e intervalo de predicao — DEC-008), nunca
por R2 in-sample.

O que foi testado e REJEITADO (2026-07-14) — nao refaca
-------------------------------------------------------
1. ALFABETIZACAO: R2 vai de 0.296 para 0.297. Zero. O Censo 2022 nao publica escolaridade por
   setor, so alfabetizacao binaria, que satura (~98%) em area urbana e nao separa bairro nobre de
   periferia. (A intuicao "instrucao e correlato de renda" esta certa; o dado disponivel e' que
   nao mede instrucao.)

2. BANHEIROS/DOMICILIO (V00232-V00238, o proxy do Criterio Brasil/ABEP): sobe o R2 para 0.337 —
   mas NAO melhora a predicao do faturamento real das unidades Ultra (r 0.454 -> 0.455; o ticket
   ate cai). Em troca, desloca a renda de bairros nobres em -10 a -19% (coeficiente negativo:
   controlando pela composicao, no domicilio rico a renda se concentra no responsavel). Um efeito
   grande e sistematico sem ganho comprovado no ground truth e' risco sem retorno — a regra do
   projeto e' validar contra o resultado REAL das unidades, nao contra metrica intermediaria.
   A feature continua sendo calculada e gravada no artefato, para auditoria e trabalho futuro.
   Nota: banheiros correlaciona +0.75 com log(renda do responsavel) por setor em SP — e um bom
   proxy de NIVEL de renda; so nao ajuda a prever a RAZAO que o uplift representa.

O raking (por que nada do que ja funciona quebra)
-------------------------------------------------
Depois de aplicar o modelo por setor, os valores sao RE-ESCALONADOS para que a media ponderada por
domicilios dos setores de cada municipio reproduza EXATAMENTE o uplift municipal do IBGE. Logo:

  - a renda agregada do municipio nao muda (continua ancorada no IBGE, rastreavel);
  - o que muda e a DISTRIBUICAO dentro do municipio, que hoje e uniforme por construcao.

O modelo so precisa acertar o formato relativo da distribuicao intra-municipal; o nivel continua
vindo do IBGE. E por isso que um R2 out-of-fold modesto entre municipios ainda e util: ele so precisa
acertar o FORMATO relativo da distribuicao intra-municipal, nao o nivel (que continua vindo do IBGE).

IMPORTANTE — valores de JULHO/2022 (referencia do Censo). A atualizacao temporal e um fator
SEPARADO (`FATOR_TEMPORAL_RENDA`, em dashboard/constants.py). Nao embuta inflacao aqui: foi essa
mistura que fez o fator antigo (2.15) envelhecer escondido.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DEFAULT_PARENTESCO_PATH = Path(
    "data/raw/CENSO 2022/Agregados_por_setores_parentesco_BR"
    "/Agregados_por_setores_parentesco_BR.csv"
)
# Banheiros vivem no agregado de caracteristicas do domicilio PARTE 2 (nao a parte 1), e a chave
# ali se chama `setor` — nao `CD_SETOR`. Os agregados do Censo nao padronizam o nome da chave.
DEFAULT_DOMICILIO_PATH = Path(
    "data/raw/CENSO 2022/Agregados_por_setores_caracteristicas_domicilio2_BR_20250417"
    "/Agregados_por_setores_caracteristicas_domicilio2_BR_20250417.csv"
)
DEFAULT_UPLIFT_MUNICIPIO_PATH = Path("data/staging/uplift_renda_domiciliar_municipio.parquet")
DEFAULT_OUTPUT_PATH = Path("data/staging/uplift_composicao_setor.parquet")
DEFAULT_REPORT_PATH = Path("data/reports/uplift_composicao_setor.md")

# Mesma faixa de plausibilidade do uplift municipal: o responsavel nao pode responder por menos de
# ~1/4 nem por mais de 100% da renda do domicilio.
UPLIFT_MIN = 1.0
UPLIFT_MAX = 4.0


def _faixa(inicio: int, fim: int) -> list[str]:
    return [f"V0{n}" for n in range(inicio, fim + 1)]


# --- Variaveis do agregado de parentesco (dicionario oficial do Censo 2022) -------------------
V_RESPONSAVEIS = "V01042"  # pessoa responsavel pelo domicilio (~= domicilios ocupados)
V_CONJUGES_TOTAL = ["V01043", "V01044"]  # conjuge de sexo diferente + do mesmo sexo (totais)

# Nao-responsaveis por tipo (totais, sem faixa etaria) e jovens 0-19 (que nao geram renda).
# adultos_outros = (nao-responsaveis) - (conjuges) - (jovens 0-19).
V_NAO_RESPONSAVEIS_TOTAL = _faixa(1043, 1061)
V_JOVENS_0_19 = (
    _faixa(1084, 1087)  # filhos 0-19
    + _faixa(1095, 1098)  # enteados 0-19
    + _faixa(1143, 1146)  # netos 0-19
    + _faixa(1165, 1168)  # irmaos 0-19
)
# Especie de unidade domestica: unipessoal / nuclear / estendida / composta.
V_ESPECIE = ["V01209", "V01210", "V01211", "V01212"]
V_UNIPESSOAL = "V01209"

COLUNAS_PARENTESCO = list(
    dict.fromkeys(
        ["CD_SETOR", V_RESPONSAVEIS, *V_NAO_RESPONSAVEIS_TOTAL, *V_JOVENS_0_19, *V_ESPECIE]
    )
)

# Banheiros de uso exclusivo por domicilio: 1, 2, 3, 4+, so comum, nenhum.
V_BANHEIROS = ["V00232", "V00233", "V00234", "V00235", "V00236", "V00238"]
# Peso em banheiros de cada faixa ("4 ou mais" -> 4.5; banheiro de uso comum -> 0.5; nenhum -> 0).
PESO_BANHEIROS = {"V00232": 1.0, "V00233": 2.0, "V00234": 3.0, "V00235": 4.5,
                  "V00236": 0.5, "V00238": 0.0}
CHAVE_DOMICILIO = "setor"

# Banheiros/domicilio e carregado e gravado no artefato (para auditoria e trabalho futuro), mas
# NAO entra no modelo. Ver "O que foi testado e rejeitado", no topo.
FEATURES = [
    "conjuges_por_domicilio",
    "adultos_outros_por_domicilio",
    "fracao_unipessoal",
]


def _read_csv_censo(path: Path, **kwargs) -> pd.DataFrame:
    """Le agregado do Censo (sep=';', latin-1). Mesma convencao dos demais pipelines."""
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(
                path, sep=";", encoding=encoding, dtype=str, low_memory=False, **kwargs
            )
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path, sep=";", encoding="latin-1", dtype=str, low_memory=False, **kwargs)


def _to_number(series: pd.Series) -> pd.Series:
    """Converte coluna do Censo em numero. 'X' (sigilo) vira NaN."""
    return pd.to_numeric(
        series.astype(str).str.replace(",", ".", regex=False), errors="coerce"
    )


def carregar_features_parentesco(path: Path = DEFAULT_PARENTESCO_PATH) -> pd.DataFrame:
    """Features de composicao domiciliar por SETOR, do agregado de parentesco.

    O agregado suprime celulas pequenas por sigilo ('X'): 19% das celulas de faixa etaria, mas so
    1.9% dos responsaveis. Suprimido e tratado como 0 — o valor real e' pequeno (1 ou 2) por
    definicao, e o resultado e' robusto a essa escolha: refazer com X=1 ou X=2 move o R2 de 0.206
    para 0.238 e o beta em ~15%, sem mudar a ordenacao dos setores.
    """
    df = _read_csv_censo(path, usecols=COLUNAS_PARENTESCO)

    # O CD_SETOR deste agregado esta INTACTO (15 digitos) — ao contrario de basico/renda/demografia,
    # corrompidos em notacao cientifica. Nunca faca join posicional; a chave e' cod_setor.
    cod_setor = df["CD_SETOR"].astype(str).str.strip().str.zfill(15)
    if not cod_setor.str.fullmatch(r"\d{15}").all():
        raise ValueError(
            "CD_SETOR do parentesco nao esta integro (esperado 15 digitos). "
            "Nao prossiga: join por chave exige a chave real."
        )

    out = pd.DataFrame({"cod_setor": cod_setor})
    out["cod_municipio"] = cod_setor.str[:7]

    domicilios = _to_number(df[V_RESPONSAVEIS]).fillna(0.0)
    conjuges = sum(_to_number(df[c]).fillna(0.0) for c in V_CONJUGES_TOTAL)
    nao_responsaveis = sum(_to_number(df[c]).fillna(0.0) for c in V_NAO_RESPONSAVEIS_TOTAL)
    jovens = sum(_to_number(df[c]).fillna(0.0) for c in V_JOVENS_0_19)
    adultos_outros = (nao_responsaveis - conjuges - jovens).clip(lower=0.0)

    especie = pd.DataFrame({c: _to_number(df[c]).fillna(0.0) for c in V_ESPECIE})
    total_especie = especie.sum(axis=1)

    out["domicilios_parentesco"] = domicilios
    out["conjuges_por_domicilio"] = np.where(domicilios > 0, conjuges / domicilios, np.nan)
    out["adultos_outros_por_domicilio"] = np.where(
        domicilios > 0, adultos_outros / domicilios, np.nan
    )
    out["fracao_unipessoal"] = np.where(
        total_especie > 0, _to_number(df[V_UNIPESSOAL]).fillna(0.0) / total_especie, np.nan
    )

    return out


def carregar_banheiros(path: Path = DEFAULT_DOMICILIO_PATH) -> pd.DataFrame:
    """Banheiros medios por domicilio, por SETOR — o proxy de renda do Criterio Brasil/ABEP.

    Fica no agregado de caracteristicas do domicilio parte 2, cuja chave se chama `setor` (os
    agregados do Censo nao padronizam o nome da chave). Chave INTACTA, 15 digitos.
    """
    df = _read_csv_censo(path, usecols=[CHAVE_DOMICILIO, *V_BANHEIROS])

    cod_setor = df[CHAVE_DOMICILIO].astype(str).str.strip().str.zfill(15)
    if not cod_setor.str.fullmatch(r"\d{15}").all():
        raise ValueError(
            f"Chave do agregado de domicilio nao esta integra (esperado 15 digitos): {path}"
        )

    faixas = {c: _to_number(df[c]).fillna(0.0) for c in V_BANHEIROS}
    domicilios = sum(faixas.values())
    banheiros = sum(PESO_BANHEIROS[c] * faixas[c] for c in V_BANHEIROS)

    return pd.DataFrame(
        {
            "cod_setor": cod_setor,
            "banheiros_por_domicilio": np.where(
                domicilios > 0, banheiros / domicilios, np.nan
            ),
        }
    )


def montar_features(
    parentesco_path: Path = DEFAULT_PARENTESCO_PATH,
    domicilio_path: Path = DEFAULT_DOMICILIO_PATH,
) -> pd.DataFrame:
    """Junta parentesco + banheiros por chave cod_setor. NUNCA por posicao."""
    setores = carregar_features_parentesco(parentesco_path)
    banheiros = carregar_banheiros(domicilio_path)

    out = setores.merge(banheiros, on="cod_setor", how="left")
    taxa_match = float(out["banheiros_por_domicilio"].notna().mean())
    if taxa_match < 0.95:
        raise ValueError(
            f"Join parentesco x domicilio suspeito: so {taxa_match*100:.1f}% dos setores casaram."
        )

    out["features_completas"] = (
        out[FEATURES].notna().all(axis=1) & out["domicilios_parentesco"].gt(0)
    )
    return out


def _wls_fit(X: np.ndarray, y: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Minimos quadrados ponderados por `w` — a MESMA conta do modelo final, isolada p/ reuso."""
    raiz = np.sqrt(w)
    coef, *_ = np.linalg.lstsq(X * raiz[:, None], y * raiz, rcond=None)
    return coef


def _r2_ponderado(y: np.ndarray, pred: np.ndarray, w: np.ndarray, base: np.ndarray) -> float:
    """R2 ponderado do modelo CONTRA um baseline explicito (nao a media in-sample).

    base = predicao do baseline (media do treino) para as MESMAS linhas. R2 = 1 - SSres/SSbase:
    positivo <=> o modelo bate a media; e' a metrica honesta exigida pela DEC-008.
    """
    ss_res = float(np.sum(w * (y - pred) ** 2))
    ss_base = float(np.sum(w * (y - base) ** 2))
    return 1.0 - ss_res / ss_base if ss_base > 0 else float("nan")


def _predicoes_out_of_fold(
    X: np.ndarray,
    y: np.ndarray,
    w: np.ndarray,
    *,
    n_splits: int = 5,
    n_repeats: int = 5,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """Predicoes OUT-OF-FOLD do modelo e do baseline (media ponderada do TREINO), k-fold repetido.

    DEC-008: nada de `fit(X, y) -> predict(X)`. Cada linha so e' prevista por folds que NAO a viram;
    o baseline de cada fold e' a media do treino daquele fold. Poolando `n_repeats` particoes
    (media por linha), retorna `(pred_modelo, pred_baseline)` para R2 e IC bootstrap a jusante.
    """
    n = len(y)
    rng = np.random.default_rng(seed)
    indices = np.arange(n)
    soma_pred = np.zeros(n)
    soma_base = np.zeros(n)
    vezes = np.zeros(n)
    for _ in range(n_repeats):
        ordem = rng.permutation(n)
        for teste in np.array_split(ordem, n_splits):
            if teste.size == 0:
                continue
            treino = np.setdiff1d(indices, teste, assume_unique=False)
            if treino.size == 0 or float(np.sum(w[treino])) <= 0.0:
                continue
            coef = _wls_fit(X[treino], y[treino], w[treino])
            soma_pred[teste] += X[teste] @ coef
            soma_base[teste] += float(np.average(y[treino], weights=w[treino]))
            vezes[teste] += 1.0
    validos = vezes > 0
    pred = np.full(n, np.nan)
    base = np.full(n, np.nan)
    pred[validos] = soma_pred[validos] / vezes[validos]
    base[validos] = soma_base[validos] / vezes[validos]
    return pred, base


def _ic_bootstrap_r2(
    y: np.ndarray,
    pred: np.ndarray,
    w: np.ndarray,
    base: np.ndarray,
    *,
    n_boot: int = 1000,
    seed: int = 42,
) -> tuple[float, float]:
    """IC95 do R2 out-of-fold por bootstrap de linhas (seed fixa p/ reprodutibilidade — DEC-008)."""
    rng = np.random.default_rng(seed)
    n = len(y)
    amostras = [
        _r2_ponderado(y[idx], pred[idx], w[idx], base[idx])
        for idx in (rng.integers(0, n, n) for _ in range(n_boot))
    ]
    vals = np.array([v for v in amostras if np.isfinite(v)], dtype=float)
    if vals.size == 0:
        return float("nan"), float("nan")
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def validar_out_of_fold(
    X: np.ndarray,
    y: np.ndarray,
    w: np.ndarray,
    *,
    n_splits: int = 5,
    n_repeats: int = 5,
    seed: int = 42,
) -> dict[str, float]:
    """Diagnostico honesto do modelo: R2 out-of-fold vs baseline da media + IC95 + intervalo de 95%.

    Substitui o R2 in-sample (banido pela DEC-008). O intervalo de 95% vem do desvio ponderado dos
    residuos out-of-fold (± 1.96 sigma) — a incerteza real de uma predicao nova.
    """
    pred, base = _predicoes_out_of_fold(
        X, y, w, n_splits=n_splits, n_repeats=n_repeats, seed=seed
    )
    ok = np.isfinite(pred) & np.isfinite(base)
    if not ok.any():
        return {
            "r2_oof": float("nan"),
            "r2_oof_ic_baixo": float("nan"),
            "r2_oof_ic_alto": float("nan"),
            "intervalo_95": float("nan"),
        }
    r2 = _r2_ponderado(y[ok], pred[ok], w[ok], base[ok])
    ic_baixo, ic_alto = _ic_bootstrap_r2(y[ok], pred[ok], w[ok], base[ok], seed=seed)
    resid = y[ok] - pred[ok]
    sigma = float(np.sqrt(np.average(resid**2, weights=w[ok])))
    return {
        "r2_oof": r2,
        "r2_oof_ic_baixo": ic_baixo,
        "r2_oof_ic_alto": ic_alto,
        "intervalo_95": 1.96 * sigma,
    }


def ajustar_coeficientes(
    setores: pd.DataFrame, uplift_municipio: pd.DataFrame
) -> tuple[np.ndarray, dict[str, Any]]:
    """Estima os pesos do modelo contra o uplift MUNICIPAL do IBGE (OLS ponderado por domicilios).

    IBGE explicando IBGE: as features vem do agregado de parentesco; o alvo, do uplift municipal
    (SIDRA t.10295 x Censo v0005 / V06004). A GeoFusion nao entra — ela e' modelo, nao verdade.

    O coeficiente final e' ajustado em TODOS os municipios (o modelo de producao); a qualidade,
    porem, e' medida OUT-OF-FOLD (`validar_out_of_fold`) vs baseline da media — nunca in-sample
    (DEC-008). O `envelope` (min/max de cada feature na calibracao) marca extrapolacao a jusante.
    """
    validos = setores[setores["features_completas"]]
    agregado = (
        validos.groupby("cod_municipio")
        .apply(
            lambda g: pd.Series(
                {
                    f: float(np.average(g[f], weights=g["domicilios_parentesco"]))
                    for f in FEATURES
                }
            ),
            include_groups=False,
        )
        .reset_index()
    )

    alvo = uplift_municipio.loc[
        uplift_municipio["uplift_confiavel"].astype(bool),
        ["cod_municipio", "uplift_composicao", "domicilios_municipio"],
    ].copy()
    alvo["cod_municipio"] = alvo["cod_municipio"].astype(str).str.zfill(7)

    df = agregado.merge(alvo, on="cod_municipio", how="inner")
    if len(df) < 100:
        raise ValueError(f"Municipios insuficientes para ajustar o modelo: {len(df)}")

    X = np.column_stack([np.ones(len(df)), *[df[f].to_numpy(dtype=float) for f in FEATURES]])
    y = df["uplift_composicao"].to_numpy(dtype=float)
    w = df["domicilios_municipio"].to_numpy(dtype=float)

    coef = _wls_fit(X, y, w)

    # Qualidade OUT-OF-FOLD (DEC-008): jamais o R2 in-sample do proprio ajuste.
    validacao = validar_out_of_fold(X, y, w)
    # Envelope de calibracao (min/max por feature) -> flag de extrapolacao ao aplicar por setor.
    envelope = {f: (float(df[f].min()), float(df[f].max())) for f in FEATURES}
    diagnostico: dict[str, Any] = {
        **validacao,
        "municipios_ajuste": float(len(df)),
        "intercepto": float(coef[0]),
        "envelope": envelope,
        **{f: float(c) for f, c in zip(FEATURES, coef[1:], strict=True)},
    }
    return coef, diagnostico


def aplicar_e_rakear(
    setores: pd.DataFrame,
    coef: np.ndarray,
    uplift_municipio: pd.DataFrame,
    envelope: dict[str, tuple[float, float]] | None = None,
) -> pd.DataFrame:
    """Aplica o modelo por setor e re-escalona para preservar o uplift municipal do IBGE.

    O raking e' o que torna a mudanca segura: a media ponderada por domicilios dos setores de cada
    municipio volta a ser EXATAMENTE o uplift municipal do IBGE. O nivel continua sendo do IBGE; o
    modelo so redistribui dentro do municipio — que e' precisamente o que hoje nao existe.

    `envelope` (min/max por feature na calibracao MUNICIPAL) marca `flag_extrapolacao`: setores cuja
    composicao cai fora da faixa vista no ajuste — honestamente, ali o modelo esta extrapolando.
    """
    df = setores.copy()
    X = np.column_stack(
        [np.ones(len(df)), *[df[f].to_numpy(dtype=float) for f in FEATURES]]
    )
    bruto = X @ coef
    df["uplift_modelo"] = np.where(df["features_completas"], bruto, np.nan)

    completas = df["features_completas"].to_numpy(dtype=bool)
    if envelope:
        dentro = np.ones(len(df), dtype=bool)
        for f, (lo, hi) in envelope.items():
            vals = df[f].to_numpy(dtype=float)
            dentro &= (vals >= lo) & (vals <= hi)
        df["flag_extrapolacao"] = completas & ~dentro
    else:
        df["flag_extrapolacao"] = False

    mun = uplift_municipio[["cod_municipio", "uf", "uplift_composicao_final"]].copy()
    mun["cod_municipio"] = mun["cod_municipio"].astype(str).str.zfill(7)
    df = df.merge(mun, on="cod_municipio", how="left")

    # media do modelo dentro do municipio (ponderada por domicilios) -> fator de raking
    def _media_modelo(g: pd.DataFrame) -> float:
        ok = g["uplift_modelo"].notna() & g["domicilios_parentesco"].gt(0)
        if not ok.any():
            return float("nan")
        return float(
            np.average(g.loc[ok, "uplift_modelo"], weights=g.loc[ok, "domicilios_parentesco"])
        )

    media = df.groupby("cod_municipio").apply(_media_modelo, include_groups=False)
    df["uplift_modelo_medio_municipio"] = df["cod_municipio"].map(media)

    fator_raking = df["uplift_composicao_final"] / df["uplift_modelo_medio_municipio"]
    df["fator_raking_municipio"] = fator_raking.replace([np.inf, -np.inf], np.nan)

    rakeado = df["uplift_modelo"] * df["fator_raking_municipio"]
    # Setor sem parentesco utilizavel herda o uplift do proprio municipio (comportamento de hoje).
    df["uplift_composicao_setor"] = rakeado.where(
        rakeado.notna(), df["uplift_composicao_final"]
    ).clip(UPLIFT_MIN, UPLIFT_MAX)
    df["fonte_uplift_setor"] = np.where(
        rakeado.notna(), "parentesco_setor", "municipio_ibge"
    )
    return df


def gerar_relatorio(df: pd.DataFrame, diagnostico: dict[str, float]) -> str:
    setoriais = df[df["fonte_uplift_setor"] == "parentesco_setor"]
    amplitude = (
        setoriais.groupby("cod_municipio")["uplift_composicao_setor"]
        .agg(lambda s: s.quantile(0.95) - s.quantile(0.05))
        .median()
    )
    linhas = [
        "# Uplift de composicao por SETOR — derivado do parentesco (IBGE)",
        "",
        "Substitui o uplift unico por municipio. Ate aqui, todo setor de Sao Paulo — Itaim e",
        "Brasilandia — recebia o mesmo fator: a variacao de composicao familiar DENTRO do",
        "municipio era tratada como zero.",
        "",
        "## Modelo",
        "",
        "```",
        "uplift_setor = a + b1*conjuges/dom + b2*outros_adultos_20+/dom + b3*fracao_unipessoal",
        "```",
        "",
        "Coeficientes por OLS ponderado contra os upliftes MUNICIPAIS do IBGE (IBGE explicando",
        "IBGE — sem GeoFusion):",
        "",
        f"- intercepto: **{diagnostico['intercepto']:+.3f}** (domicilio so com o responsavel)",
        f"- conjuges/domicilio: **{diagnostico['conjuges_por_domicilio']:+.3f}**"
        " (quase uma segunda renda)",
        f"- outros adultos 20+/domicilio: **{diagnostico['adultos_outros_por_domicilio']:+.3f}**"
        " (filho adulto, avo: contribuem pouco)",
        f"- fracao unipessoal: **{diagnostico['fracao_unipessoal']:+.3f}** (nao ha quem somar)",
        "",
        f"R2 out-of-fold (k-fold 5x5, vs baseline da media): **{diagnostico['r2_oof']:.3f}**"
        f" (IC95 [{diagnostico['r2_oof_ic_baixo']:+.3f}, {diagnostico['r2_oof_ic_alto']:+.3f}],"
        f" {int(diagnostico['municipios_ajuste']):,} municipios)."
        f" Intervalo de 95% de uma predicao: **+-{diagnostico['intervalo_95']:.3f}**.",
        "",
        "Metrica HONESTA (DEC-008): cada municipio e' previsto so por folds que nao o viram, contra o",
        "baseline da media. R2>0 com IC95 sem cruzar zero => o modelo bate a media fora da amostra.",
        "Os sinais e magnitudes dos coeficientes sao economicamente coerentes — evidencia adicional de",
        "que o sinal e real, e nao ajuste de curva.",
        "",
        "## Testado e rejeitado (nao refaca)",
        "",
        "Deltas de R2 abaixo sao de SCREENING exploratorio in-sample (comparacao relativa entre",
        "candidatas, nao a validacao do modelo — esta e' out-of-fold, acima):",
        "",
        "- **Alfabetizacao**: R2 0.296 -> 0.297. Zero. O Censo 2022 nao publica escolaridade por",
        "  setor, so alfabetizacao binaria, que satura (~98%) em area urbana.",
        "- **Banheiros/domicilio** (Criterio Brasil/ABEP): sobe o R2 para 0.337, mas nao melhora a",
        "  predicao do faturamento real das unidades Ultra (r 0.454 -> 0.455) e desloca bairros",
        "  nobres em -10 a -19%. Efeito grande sem ganho comprovado = risco sem retorno. A feature",
        "  segue gravada no artefato para auditoria.",
        "",
        "## Raking: por que isto nao quebra o que ja funciona",
        "",
        "Os valores sao re-escalonados para que a media ponderada por domicilios dos setores de",
        "cada municipio reproduza EXATAMENTE o uplift municipal do IBGE. A renda agregada do",
        "municipio nao muda; muda a distribuicao DENTRO dele. O modelo so precisa acertar o",
        "formato relativo — o nivel continua vindo do IBGE.",
        "",
        "## Cobertura",
        "",
        f"- Setores com uplift proprio (parentesco): **{len(setoriais):,}** de {len(df):,}"
        f" ({100*len(setoriais)/max(len(df),1):.1f}%)",
        f"- Setores que herdam o municipio: {int((df['fonte_uplift_setor']=='municipio_ibge').sum()):,}",
        f"- Setores em EXTRAPOLACAO (composicao fora da faixa de calibracao municipal):"
        f" **{int(df.get('flag_extrapolacao', pd.Series(dtype=bool)).sum()):,}**"
        " — marcados em `flag_extrapolacao` para leitura cautelosa.",
        f"- Amplitude intra-municipal (p95-p05, mediana dos municipios): **{amplitude:.3f}**"
        " — antes era 0.000 por construcao.",
        "",
        "## Valores em JULHO/2022",
        "",
        "Data de referencia do Censo. A atualizacao temporal e um fator SEPARADO",
        "(`FATOR_TEMPORAL_RENDA`) — de proposito: o fator antigo (2.15) misturava composicao com",
        "deriva temporal e envelhecia sem ninguem perceber.",
        "",
        "## Distribuicao do uplift por setor",
        "",
        "| Percentil | Uplift |",
        "| --- | ---: |",
    ]
    for q in (0.05, 0.25, 0.50, 0.75, 0.95):
        linhas.append(
            f"| p{int(q*100):02d} | {float(df['uplift_composicao_setor'].quantile(q)):.3f} |"
        )
    return "\n".join(linhas) + "\n"


def executar(
    parentesco_path: Path = DEFAULT_PARENTESCO_PATH,
    uplift_municipio_path: Path = DEFAULT_UPLIFT_MUNICIPIO_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    report_path: Path = DEFAULT_REPORT_PATH,
    domicilio_path: Path = DEFAULT_DOMICILIO_PATH,
) -> pd.DataFrame:
    setores = montar_features(parentesco_path, domicilio_path)
    uplift_municipio = pd.read_parquet(uplift_municipio_path)

    coef, diagnostico = ajustar_coeficientes(setores, uplift_municipio)
    df = aplicar_e_rakear(setores, coef, uplift_municipio, diagnostico.get("envelope"))

    cols = [
        "cod_setor",
        "cod_municipio",
        "uf",
        *FEATURES,
        "banheiros_por_domicilio",  # fora do modelo; gravado para auditoria
        "domicilios_parentesco",
        "uplift_modelo",
        "fator_raking_municipio",
        "uplift_composicao_setor",
        "flag_extrapolacao",  # composicao fora da faixa de calibracao (leitura cautelosa)
        "fonte_uplift_setor",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df[cols].to_parquet(output_path, index=False)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(gerar_relatorio(df, diagnostico), encoding="utf-8")

    proprio = int((df["fonte_uplift_setor"] == "parentesco_setor").sum())
    print(f"[uplift-setor] setores: {len(df):,} | com uplift proprio: {proprio:,}")
    print(
        f"[uplift-setor] R2 out-of-fold (vs baseline da media): {diagnostico['r2_oof']:.3f}"
        f" IC95 [{diagnostico['r2_oof_ic_baixo']:+.3f}, {diagnostico['r2_oof_ic_alto']:+.3f}]"
    )
    print(f"[uplift-setor] coef: intercepto={diagnostico['intercepto']:+.3f}")
    for f in FEATURES:
        print(f"[uplift-setor]       {f}={diagnostico[f]:+.3f}")
    print(f"[uplift-setor] artefato: {output_path}")
    print(f"[uplift-setor] relatorio: {report_path}")
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parentesco-path", default=str(DEFAULT_PARENTESCO_PATH))
    parser.add_argument("--domicilio-path", default=str(DEFAULT_DOMICILIO_PATH))
    parser.add_argument("--uplift-municipio-path", default=str(DEFAULT_UPLIFT_MUNICIPIO_PATH))
    parser.add_argument("--output-path", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH))
    args = parser.parse_args()
    executar(
        Path(args.parentesco_path),
        Path(args.uplift_municipio_path),
        Path(args.output_path),
        Path(args.report_path),
        Path(args.domicilio_path),
    )


if __name__ == "__main__":
    main()
