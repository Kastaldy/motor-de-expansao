"""BLK-TP-06-FU1: re-validacao do residual com CANDIDATOS de recalibracao.

Reproduz o baseline do BLK-TP-06 (`score_oportunidade_residual` vs demanda OBSERVADA,
+0,3119 out-of-fold) e valida OUT-OF-FOLD, com o MESMO harness/seed de `calibracao_residual.py`,
um residual CANDIDATO de recalibracao contra `log1p(membros)`, comparando por IC95 da DIFERENCA
PAREADA (bootstrap pareado, mesmos folds) e por recorte metropolitano (SP/MG/RJ x fora). Decide,
de forma honesta (DEC-008), SE e QUAL candidato alimenta o BLK-TP-09.

GATE HUMANO (APROVADO pelo usuario em 2026-07-02): rodar **baseline + Candidato A APENAS**.
  - Candidato C (capacidade POR REDE) e A+C: **ADIADOS** (NAO implementados neste ciclo). O
    Candidato C exigira capacidade de CLUBE real de `data/validacao/` (Sky Fit / Engenharia /
    Smart Fit KPIs), nao as medianas ~340 de bairro do BLK-TP-08-FU. Estrutura deixada EXTENSIVEL
    (dedup fino isolado em funcao propria) para o Candidato C futuro, mas SEM implementa-lo aqui.

Candidato A (oferta ENRIQUECIDA com dedup FINO por par (hex_id, rede_menor)):
  - Soma a oferta consumida os `alunos_academias_menores` das academias menores NAO ja cobertas
    pela mesma rede naquele hex (independentes sempre somam; ~91,7% somam, ~8,3% dedupados vs
    `concorrentes_mapeados[(hex_id_res7, rede)]`).
  - `residual_A = clip(100 * max(sam_fitness_potencial - oferta_consumida_ajustada, 0) / cap_ref,
    0, 100)`, com `oferta_consumida_ajustada = oferta_consumida_total_estimada + alunos_menores_add`
    e `cap_ref=2500` (denominador do clip INTOCADO).

GUARDRAILS (DEC-001/DEC-008/DEC-009/DEC-012/DEC-013; CLAUDE.md §5):
  - READ-ONLY sobre o M1: NAO recalcula `score_priorizacao`/`hex_score_estrutural`/pesos; NAO
    altera a formula de `score_oportunidade_residual` em producao nem regenera
    `hexagonos_mercado_mapeado.parquet`/derivados. Candidatos so EM MEMORIA / relatorio.
  - DEC-008: validacao out-of-fold vs baseline da media; R2 in-sample BANIDO do veredito; IC95
    bootstrap seed=42; comparacao de candidatos out-of-fold pelo IC95 do Delta PAREADO;
    NO-GO e resultado VALIDO.
  - DEC-009: `membros` e ALVO OBSERVADO; PROIBIDO usar como preditor geografico de magnitude.
  - DEC-012: pacote `demanda_revelada/` DISJUNTO -- este modulo NUNCA importa de `pipelines/m1/`,
    `censo_*`, `dashboard/`, `api`, `config.py` raiz, `pipelines.calcular_colunas_mercado` nem
    `pipelines.enriquecimento_espacial_hexagonos`; sem PII; fixtures sinteticas; `NAO_ABRA/`
    nunca tocado.
  - DEC-013: a oferta das academias menores entra so na camada de mercado/residual (candidata),
    COM DEDUP FINO por rede; READ-ONLY sobre o M1 e censitario.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

# Reuso do harness IRMAO da camada paralela (NAO e M1/censo/dashboard/api). API estavel: nao mutar.
from motor_expansao.demanda_revelada.calibracao_residual import (
    N_BOOTSTRAP,
    SEED,
    _ic_bootstrap_r2,
    _ic_bootstrap_rho,
    _metodo_validacao,
    _rho_oof,
    _selecionar_alpha_e_oof,
)
from motor_expansao.dimensionamento.backtest_dim import _r2

# Rede de seguranca anti-PII tambem neste modulo de analise.
from .contrato import COLUNAS_PII_PROIBIDAS

_logger = logging.getLogger(__name__)

# Constantes LOCAIS (nao arrastar dependencias de pipeline; espelham producao).
CAP_REF: float = 2500.0  # denominador do clip do residual (SCORE_RESIDUAL_CAPACIDADE_REFERENCIA).
UFS_METROPOLITANAS: tuple[str, ...] = ("SP", "MG", "RJ")
CATEGORIA_INDEPENDENTE: str = "independente"

# Piso minimo de observacoes para modelar (abaixo disso o oof e degenerado).
N_MIN_MODELO: int = 3

# Rotulo dos recortes (chaves canonicas do RevalidacaoResult).
RECORTE_COMPLETO: str = "completo"
RECORTE_METRO: str = "metropolitano_sp_mg_rj"
RECORTE_FORA: str = "fora_metropolitano"


# --------------------------------------------------------------------------- #
# Dataclasses de resultado
# --------------------------------------------------------------------------- #
@dataclass
class ResultadoCandidato:
    """Metricas out-of-fold de UM vetor de score-candidato vs `log1p(membros)`.

    `y_pred_oof` e guardado para a comparacao pareada (bootstrap pareado). `r2_insample` existe
    SO para auditoria -- NUNCA no veredito (DEC-008).
    """

    nome: str
    r2_oof_log: float
    ic95_r2_oof: tuple[float, float]
    rho_oof: float
    ic95_rho_oof: tuple[float, float]
    alpha: float
    n: int
    metodo: str
    y_oof: np.ndarray = field(repr=False)
    y_pred_oof: np.ndarray = field(repr=False)


@dataclass
class ComparacaoPareada:
    """IC95 do Delta pareado `R2(cand) - R2(baseline)` por bootstrap PAREADO (mesmos indices).

    `vence` <=> IC95 do Delta NAO cruza zero (inferior > 0).
    """

    nome_candidato: str
    delta_medio: float
    ic95_delta: tuple[float, float]
    vence: bool


@dataclass
class RevalidacaoRecorte:
    """Resultado de um recorte (completo / metropolitano / fora): candidatos + comparacoes."""

    recorte: str
    n: int
    baseline: ResultadoCandidato
    candidatos: dict[str, ResultadoCandidato]
    comparacoes: dict[str, ComparacaoPareada]


@dataclass
class RevalidacaoResult:
    """Resultado completo do BLK-TP-06-FU1: baseline + Candidato A, 3 recortes, veredito honesto.

    `dedup_add`/`dedup_dup` = alunos das academias menores somados/dedupados no join (auditoria).
    """

    recortes: dict[str, RevalidacaoRecorte]
    dedup_add: int
    dedup_dup: int
    concentracao_uf: dict[str, float]
    veredito: str
    nota_honesta: str = field(default="")

    @property
    def vence_candidato_a(self) -> bool:
        """True se o Candidato A vence (Delta pareado > 0) NO COMPLETO E FORA de SP/MG/RJ."""
        comp_completo = self.recortes[RECORTE_COMPLETO].comparacoes.get("cand_A")
        comp_fora = self.recortes[RECORTE_FORA].comparacoes.get("cand_A")
        return bool(comp_completo and comp_completo.vence and comp_fora and comp_fora.vence)


# --------------------------------------------------------------------------- #
# Dedup FINO por par (hex_id, rede_menor) -- isolado p/ o Candidato C futuro reusar
# --------------------------------------------------------------------------- #
def construir_pares_concorrentes(conc_df: pd.DataFrame) -> set[tuple[str, str]]:
    """Conjunto de pares `(hex_id_res7, rede)` de `concorrentes_mapeados` (agregado, sem PII).

    Filtra `status_registro == "valido"` quando a coluna existe (mantem paridade com a oferta
    consumida do Motor). Consome READ-ONLY.
    """
    df = conc_df
    if "status_registro" in df.columns:
        df = df[df["status_registro"].astype(str) == "valido"]
    hex_col = "hex_id_res7" if "hex_id_res7" in df.columns else "hex_id"
    return {
        (str(h), str(r))
        for h, r in zip(df[hex_col].astype(str), df["rede"].astype(str), strict=True)
    }


def alunos_menores_add_por_hex(
    of_menores_rede: pd.DataFrame,
    pares_concorrentes: set[tuple[str, str]],
    *,
    categoria_independente: str = CATEGORIA_INDEPENDENTE,
) -> pd.Series:
    """Alunos das academias menores a SOMAR por hex, apos o dedup FINO por par (hex, rede_menor).

    Regra (DEC-013 / gate 2026-07-02): um par `(hex, rede_conhecida)` que JA existe em
    `pares_concorrentes` NAO soma (assume-se a mesma rede ja contada na oferta consumida do
    Motor); todo o resto -- inclusive TODA a categoria `independente` -- SOMA integral (oferta
    real que o Motor ignora hoje). Retorna Series indexada por `hex_id` com a soma dos alunos NAO
    dedupados. Frame consumido READ-ONLY.
    """
    df = of_menores_rede[["hex_id", "rede_menor", "alunos_academias_menores"]].copy()
    df["hex_id"] = df["hex_id"].astype(str)
    df["rede_menor"] = df["rede_menor"].astype(str)
    df["alunos_academias_menores"] = pd.to_numeric(
        df["alunos_academias_menores"], errors="coerce"
    ).fillna(0.0)

    is_indep = df["rede_menor"] == categoria_independente
    # Um par de REDE CONHECIDA que ja existe nos concorrentes mapeados e duplicado -> nao soma.
    matched = (~is_indep) & df.apply(
        lambda r: (r["hex_id"], r["rede_menor"]) in pares_concorrentes, axis=1
    )
    somaveis = df.loc[~matched]
    if somaveis.empty:
        return pd.Series(dtype="float64")
    return somaveis.groupby("hex_id")["alunos_academias_menores"].sum()


# --------------------------------------------------------------------------- #
# Construcao dos vetores de residual (baseline + Candidato A) -- EM MEMORIA
# --------------------------------------------------------------------------- #
def construir_residuais_candidatos(
    df_join: pd.DataFrame,
    of_menores_rede: pd.DataFrame,
    pares_concorrentes: set[tuple[str, str]],
    *,
    cap_ref: float = CAP_REF,
) -> pd.DataFrame:
    """Devolve `df_join` + colunas EM MEMORIA: `residual_baseline`, `residual_cand_A`,
    `flag_metropolitano`. NUNCA escreve parquet.

    - `residual_baseline` = `score_oportunidade_residual` do parquet (reproduz o BLK-TP-06).
    - `residual_cand_A` = enriquecido com o dedup FINO por par (hex, rede_menor):
        `oferta_consumida_ajustada = oferta_consumida_total_estimada + alunos_menores_add`
        `oferta_efetiva_ajustada   = max(sam_fitness_potencial - oferta_consumida_ajustada, 0)`
        `residual_cand_A           = clip(100 * oferta_efetiva_ajustada / cap_ref, 0, 100)`
      (cap_ref = denominador do clip INTOCADO). O residual CAI onde ha academias menores nao
      mapeadas (a maior parte da oferta menor).

    Estrutura EXTENSIVEL para o Candidato C futuro (capacidade de clube real de data/validacao/):
    o dedup fino ja e uma funcao propria (`alunos_menores_add_por_hex`); o C somaria uma coluna
    `residual_cand_C` sem tocar esta.
    """
    df = df_join.copy()

    df["residual_baseline"] = pd.to_numeric(
        df["score_oportunidade_residual"], errors="coerce"
    ).astype(float)

    add = alunos_menores_add_por_hex(of_menores_rede, pares_concorrentes)
    df["_alunos_menores_add"] = (
        df["hex_id"].astype(str).map(add).fillna(0.0).astype(float)
    )

    sam = pd.to_numeric(df["sam_fitness_potencial"], errors="coerce").fillna(0.0).astype(float)
    consumida = (
        pd.to_numeric(df["oferta_consumida_total_estimada"], errors="coerce")
        .fillna(0.0)
        .astype(float)
    )
    consumida_ajustada = consumida + df["_alunos_menores_add"]
    efetiva_ajustada = np.clip(sam - consumida_ajustada, 0.0, None)
    df["residual_cand_A"] = np.clip(100.0 * efetiva_ajustada / cap_ref, 0.0, 100.0)

    uf = df["uf"].astype(str) if "uf" in df.columns else pd.Series("", index=df.index)
    df["flag_metropolitano"] = uf.isin(UFS_METROPOLITANAS)
    return df


# --------------------------------------------------------------------------- #
# Preparacao local (nao muta a API do harness -- `preparar_dados` fica intocada)
# --------------------------------------------------------------------------- #
def _preparar_candidato(df: pd.DataFrame, coluna: str) -> tuple[np.ndarray, np.ndarray]:
    """(X, y) de um candidato: `y=log1p(clip(membros,0,None))`, `X=coluna.reshape(-1,1)`.

    Limpeza NaN/inf identica a `preparar_dados` do harness. Nao lê `score_oportunidade_residual`
    fixo -- generico para qualquer coluna de score-candidato.
    """
    membros = pd.to_numeric(df.get("membros"), errors="coerce").to_numpy(dtype=float)
    y = np.log1p(np.clip(membros, 0.0, None))
    x = pd.to_numeric(df.get(coluna), errors="coerce").to_numpy(dtype=float)
    X = x.reshape(-1, 1)
    finito = np.isfinite(X).all(axis=1) & np.isfinite(y)
    return X[finito], y[finito]


# --------------------------------------------------------------------------- #
# Validacao out-of-fold de um candidato (reusa o harness)
# --------------------------------------------------------------------------- #
def validar_candidato(df_join: pd.DataFrame, coluna_score: str, *, nome: str) -> ResultadoCandidato:
    """Valida (out-of-fold, mesmo harness/seed) um vetor de score-candidato vs `log1p(membros)`.

    Roda `_preparar_candidato` + `_selecionar_alpha_e_oof` (alpha por menor RMSE oof) + IC95
    bootstrap (seed=42) do R2 e do rho. R2 in-sample NUNCA aqui (DEC-008).
    """
    X, y = _preparar_candidato(df_join, coluna_score)
    n = int(len(y))
    if n < N_MIN_MODELO:
        return ResultadoCandidato(
            nome=nome,
            r2_oof_log=float("nan"),
            ic95_r2_oof=(float("nan"), float("nan")),
            rho_oof=float("nan"),
            ic95_rho_oof=(float("nan"), float("nan")),
            alpha=float("nan"),
            n=n,
            metodo="degenerado",
            y_oof=y,
            y_pred_oof=np.full(n, np.nan, dtype=float),
        )
    metodo = _metodo_validacao(n)
    alpha, y_pred_oof, _base, r2_oof, _rmse_oof = _selecionar_alpha_e_oof(X, y, metodo=metodo)
    rng_r2 = np.random.default_rng(SEED)
    ic_r2 = _ic_bootstrap_r2(y, y_pred_oof, rng_r2)
    rng_rho = np.random.default_rng(SEED)
    ic_rho = _ic_bootstrap_rho(y, y_pred_oof, rng_rho)
    rho = _rho_oof(y, y_pred_oof)
    return ResultadoCandidato(
        nome=nome,
        r2_oof_log=float(r2_oof),
        ic95_r2_oof=(float(ic_r2[0]), float(ic_r2[1])),
        rho_oof=float(rho),
        ic95_rho_oof=(float(ic_rho[0]), float(ic_rho[1])),
        alpha=float(alpha),
        n=n,
        metodo=metodo,
        y_oof=y,
        y_pred_oof=y_pred_oof,
    )


# --------------------------------------------------------------------------- #
# Comparacao PAREADA (bootstrap pareado -- mesmos indices nos 2 vetores)
# --------------------------------------------------------------------------- #
def comparar_pareado(
    y: np.ndarray,
    pred_baseline_oof: np.ndarray,
    pred_cand_oof: np.ndarray,
    *,
    seed: int = SEED,
    n: int = N_BOOTSTRAP,
) -> tuple[float, tuple[float, float]]:
    """IC95 do Delta pareado `Delta = R2(y_b, cand_b) - R2(y_b, base_b)` por bootstrap PAREADO.

    Reamostra UMA vez os indices por iteracao e aplica os MESMOS indices aos DOIS vetores oof
    (pareamento). Reamostras com SS_tot==0 sao descartadas. Retorna (delta_medio, (p2.5, p97.5)).
    NaN/NaN se nenhuma valida.
    """
    y = np.asarray(y, dtype=float)
    pred_baseline_oof = np.asarray(pred_baseline_oof, dtype=float)
    pred_cand_oof = np.asarray(pred_cand_oof, dtype=float)
    m = len(y)
    if m < 2 or not (len(pred_baseline_oof) == len(pred_cand_oof) == m):
        return (float("nan"), (float("nan"), float("nan")))
    rng = np.random.default_rng(seed)
    valores: list[float] = []
    tentativas = 0
    teto = 10 * n
    while len(valores) < n and tentativas < teto:
        tentativas += 1
        idx = rng.integers(0, m, size=m)
        yb = y[idx]
        if float(np.sum((yb - yb.mean()) ** 2)) <= 0.0:
            continue
        delta = _r2(yb, pred_cand_oof[idx]) - _r2(yb, pred_baseline_oof[idx])
        if np.isfinite(delta):
            valores.append(float(delta))
    if not valores:
        return (float("nan"), (float("nan"), float("nan")))
    arr = np.asarray(valores, dtype=float)
    return (float(np.mean(arr)), (float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))))


def _comparacao_de(
    nome_candidato: str, baseline: ResultadoCandidato, cand: ResultadoCandidato
) -> ComparacaoPareada:
    """Monta a `ComparacaoPareada` (Delta pareado + IC95 + vence) de um candidato vs baseline.

    Exige alinhamento dos vetores oof (mesmo N e mesmo alvo -- garantido por construirmos ambos
    do MESMO df_join). "vence" <=> IC95 do Delta NAO cruza zero (inferior > 0).
    """
    if (
        baseline.n != cand.n
        or baseline.n < N_MIN_MODELO
        or not np.array_equal(baseline.y_oof, cand.y_oof, equal_nan=True)
    ):
        return ComparacaoPareada(
            nome_candidato=nome_candidato,
            delta_medio=float("nan"),
            ic95_delta=(float("nan"), float("nan")),
            vence=False,
        )
    delta, ic = comparar_pareado(baseline.y_oof, baseline.y_pred_oof, cand.y_pred_oof)
    vence = bool(np.isfinite(ic[0]) and ic[0] > 0.0)
    return ComparacaoPareada(
        nome_candidato=nome_candidato, delta_medio=delta, ic95_delta=ic, vence=vence
    )


# --------------------------------------------------------------------------- #
# Comparacao por recorte (completo / metropolitano / fora)
# --------------------------------------------------------------------------- #
def comparar_por_recorte(df_recorte: pd.DataFrame, *, recorte: str) -> RevalidacaoRecorte:
    """Valida baseline + Candidato A no recorte e compara cada candidato vs baseline (pareado).

    Consome o df com as colunas `residual_baseline`/`residual_cand_A`/`membros` ja construidas.
    """
    baseline = validar_candidato(df_recorte, "residual_baseline", nome="baseline")
    cand_a = validar_candidato(df_recorte, "residual_cand_A", nome="cand_A")
    candidatos = {"cand_A": cand_a}
    comparacoes = {"cand_A": _comparacao_de("cand_A", baseline, cand_a)}
    return RevalidacaoRecorte(
        recorte=recorte,
        n=baseline.n,
        baseline=baseline,
        candidatos=candidatos,
        comparacoes=comparacoes,
    )


# --------------------------------------------------------------------------- #
# Orquestrador
# --------------------------------------------------------------------------- #
def _concentracao_uf(df: pd.DataFrame, *, top: int = 3) -> dict[str, float]:
    """Top-N UF por % do join (caveat de vies). {} se `uf` ausente."""
    if "uf" not in df.columns or df.empty:
        return {}
    vc = (df["uf"].astype(str).value_counts(normalize=True) * 100.0).round(1)
    return {str(k): float(v) for k, v in vc.head(top).items()}


def revalidar_candidatos(
    df_join: pd.DataFrame,
    of_menores_rede: pd.DataFrame,
    pares_concorrentes: set[tuple[str, str]],
    *,
    cap_ref: float = CAP_REF,
) -> RevalidacaoResult:
    """Orquestra o BLK-TP-06-FU1: constroi baseline + Candidato A, valida nos 3 recortes,
    compara pareado e emite veredito honesto (DEC-008).

    READ-ONLY sobre o M1; nada escrito em disco aqui (o `__main__` escreve o relatorio).
    """
    df = construir_residuais_candidatos(
        df_join, of_menores_rede, pares_concorrentes, cap_ref=cap_ref
    )

    recortes: dict[str, RevalidacaoRecorte] = {
        RECORTE_COMPLETO: comparar_por_recorte(df, recorte=RECORTE_COMPLETO),
        RECORTE_METRO: comparar_por_recorte(
            df[df["flag_metropolitano"]], recorte=RECORTE_METRO
        ),
        RECORTE_FORA: comparar_por_recorte(
            df[~df["flag_metropolitano"]], recorte=RECORTE_FORA
        ),
    }

    # dedup_dup = alunos de academias menores dedupados (nao somados) no join.
    add_por_hex = alunos_menores_add_por_hex(of_menores_rede, pares_concorrentes)
    hexes_join = set(df["hex_id"].astype(str))
    of_join = of_menores_rede[of_menores_rede["hex_id"].astype(str).isin(hexes_join)]
    total_of_join = int(
        round(float(pd.to_numeric(of_join["alunos_academias_menores"], errors="coerce").fillna(0).sum()))
    )
    add_join = int(round(float(add_por_hex[add_por_hex.index.isin(hexes_join)].sum())))
    dedup_dup = max(total_of_join - add_join, 0)

    result = RevalidacaoResult(
        recortes=recortes,
        dedup_add=add_join,
        dedup_dup=dedup_dup,
        concentracao_uf=_concentracao_uf(df),
        veredito="",
    )
    result.veredito = "APLICAR_A" if result.vence_candidato_a else "NAO_APLICAR"
    result.nota_honesta = _nota_honesta(result)

    comp_completo = recortes[RECORTE_COMPLETO].comparacoes["cand_A"]
    comp_fora = recortes[RECORTE_FORA].comparacoes["cand_A"]
    _logger.info(
        "RevalidacaoResidual FU1: baseline_r2=%.4f cand_A_r2=%.4f delta_completo=%.4f "
        "ic=(%.4f,%.4f) vence_completo=%s vence_fora=%s veredito=%s",
        recortes[RECORTE_COMPLETO].baseline.r2_oof_log,
        recortes[RECORTE_COMPLETO].candidatos["cand_A"].r2_oof_log,
        comp_completo.delta_medio,
        comp_completo.ic95_delta[0],
        comp_completo.ic95_delta[1],
        comp_completo.vence,
        comp_fora.vence,
        result.veredito,
    )
    return result


# --------------------------------------------------------------------------- #
# Nota honesta + relatorio
# --------------------------------------------------------------------------- #
def _fmt(v: float, nd: int = 4) -> str:
    return f"{v:.{nd}f}" if np.isfinite(v) else "n/d"


def _nota_honesta(r: RevalidacaoResult) -> str:
    """Mensagem legivel (PT, sem PII) com o veredito honesto do Candidato A."""
    comp_c = r.recortes[RECORTE_COMPLETO].comparacoes["cand_A"]
    comp_f = r.recortes[RECORTE_FORA].comparacoes["cand_A"]
    base = r.recortes[RECORTE_COMPLETO].baseline
    cand = r.recortes[RECORTE_COMPLETO].candidatos["cand_A"]
    if r.vence_candidato_a:
        cab = (
            "APLICAR_A: o Candidato A (oferta enriquecida com dedup fino) SUPERA o baseline "
            "out-of-fold (Delta pareado > 0 no completo E fora de SP/MG/RJ). Recomendar ao "
            "BLK-TP-09 (DEC + gate) recalibrar a oferta consumida do residual incluindo as "
            "academias menores nao mapeadas."
        )
    else:
        cab = (
            "NAO_APLICAR (honesto, DEC-008): o Candidato A NAO supera o baseline de forma "
            "robusta out-of-fold (Delta pareado cruza zero no completo e/ou nao sobrevive fora "
            "de SP/MG/RJ). Nao recalibrar sobre sinal que nao generaliza seria sobreajuste."
        )
    return (
        "BLK-TP-06-FU1 -- re-validacao do residual (baseline + Candidato A; k-fold repetido, "
        "seed=42, vs baseline da media)\n"
        "GATE HUMANO 2026-07-02: rodar baseline + Candidato A APENAS. Candidato C e A+C ADIADOS "
        "(exigem capacidade de CLUBE real de data/validacao/, nao as medianas ~340 de bairro).\n"
        f"Veredito: {cab}\n"
        f"  Baseline: R2_oof_log={_fmt(base.r2_oof_log)} IC95="
        f"[{_fmt(base.ic95_r2_oof[0])}, {_fmt(base.ic95_r2_oof[1])}] | rho_oof={_fmt(base.rho_oof)} "
        f"| n={base.n}\n"
        f"  Candidato A: R2_oof_log={_fmt(cand.r2_oof_log)} IC95="
        f"[{_fmt(cand.ic95_r2_oof[0])}, {_fmt(cand.ic95_r2_oof[1])}] | rho_oof={_fmt(cand.rho_oof)}\n"
        f"  Delta pareado (A-baseline) COMPLETO = {_fmt(comp_c.delta_medio)} IC95="
        f"[{_fmt(comp_c.ic95_delta[0])}, {_fmt(comp_c.ic95_delta[1])}] -> vence={comp_c.vence}\n"
        f"  Delta pareado (A-baseline) FORA (nao-metro) = {_fmt(comp_f.delta_medio)} IC95="
        f"[{_fmt(comp_f.ic95_delta[0])}, {_fmt(comp_f.ic95_delta[1])}] -> vence={comp_f.vence}\n"
        f"  Dedup fino: +{r.dedup_add} alunos somados / -{r.dedup_dup} dedupados no join.\n"
        "Confounds (read-only, nao corrigidos):\n"
        "  1. Cobertura ~1% do universo de hexes do Motor (DEC-012) -> refino metropolitano, "
        "NAO validacao nacional.\n"
        "  2. Vies metropolitano do Sudeste (SP/MG/RJ concentram ~metade do join) -> qualquer "
        "ganho so vale se sobrevive FORA de SP/MG/RJ.\n"
        "  3. Dedup fino por par (hex, rede): independentes sempre somam; so rede conhecida ja "
        "mapeada e dedupada. Coords ~1 km atenuam o sinal no join res-7.\n"
        "  4. DEC-009: `membros` e ALVO OBSERVADO; nunca preditor geografico de magnitude.\n"
        "  5. Candidato C (capacidade de clube por rede) ADIADO -- fonte futura data/validacao/.\n"
    )


def relatorio_revalidacao(r: RevalidacaoResult) -> str:
    """String markdown legivel (PT, sem PII) com baseline, Candidato A, Delta pareado, recortes,
    veredito e o Candidato C ADIADO."""
    L: list[str] = []
    L.append("# Re-validacao do residual com candidatos -- BLK-TP-06-FU1")
    L.append("")
    L.append(
        "READ-ONLY sobre o M1 (DEC-001/DEC-008/DEC-009/DEC-012/DEC-013). Pacote disjunto. Sem PII. "
        "A demanda (`membros`) e ALVO OBSERVADO; os residuais (baseline e Candidato A) sao os "
        "PREDITORES. Este bloco VALIDA + RECOMENDA -- NAO altera a formula do residual em producao "
        "nem regenera `hexagonos_mercado_mapeado.parquet`."
    )
    L.append("")
    L.append(
        "**Gate humano APROVADO pelo usuario em 2026-07-02:** rodar **baseline + Candidato A "
        "APENAS**. Candidato C (capacidade POR REDE) e A+C: **ADIADOS** neste ciclo."
    )
    L.append("")
    base = r.recortes[RECORTE_COMPLETO].baseline
    cand = r.recortes[RECORTE_COMPLETO].candidatos["cand_A"]
    L.append("## 1. Baseline reproduzido (completo)")
    L.append("")
    L.append(f"- N do join = **{base.n}** (esperado 16.411)")
    L.append(f"- R2_oof_log = **{_fmt(base.r2_oof_log)}** (esperado ~+0,3119)")
    L.append(f"- rho_oof = **{_fmt(base.rho_oof)}** (esperado ~+0,4615)")
    top_uf = ", ".join(f"{k} {v:.1f}%" for k, v in r.concentracao_uf.items()) or "n/d"
    L.append(f"- Concentracao top-3 UF = {top_uf}")
    L.append("")
    L.append("## 2. Candidato A (oferta enriquecida com dedup FINO por (hex, rede))")
    L.append("")
    L.append(
        "Formula: `oferta_consumida_ajustada = oferta_consumida_total_estimada + "
        "alunos_menores_add`; `residual_cand_A = clip(100 * max(sam_fitness_potencial - "
        "oferta_consumida_ajustada, 0) / 2500, 0, 100)`. Dedup fino por par (hex, rede_menor): "
        "independentes sempre somam; so rede conhecida ja mapeada e dedupada."
    )
    L.append("")
    L.append(f"- Dedup fino no join: **+{r.dedup_add} alunos somados** / **-{r.dedup_dup} dedupados**")
    L.append(f"- R2_oof_log = **{_fmt(cand.r2_oof_log)}** | IC95 = "
             f"[{_fmt(cand.ic95_r2_oof[0])}, {_fmt(cand.ic95_r2_oof[1])}]")
    L.append(f"- rho_oof = {_fmt(cand.rho_oof)}")
    L.append("")
    L.append("## 3. Tabela comparativa (R2_oof / rho_oof / IC95) -- recorte completo")
    L.append("")
    L.append("| candidato | R2_oof_log | IC95 R2 | rho_oof | IC95 rho | n |")
    L.append("| --- | ---: | :---: | ---: | :---: | ---: |")
    for c in (base, cand):
        L.append(
            f"| {c.nome} | {_fmt(c.r2_oof_log)} | "
            f"[{_fmt(c.ic95_r2_oof[0])}, {_fmt(c.ic95_r2_oof[1])}] | {_fmt(c.rho_oof)} | "
            f"[{_fmt(c.ic95_rho_oof[0])}, {_fmt(c.ic95_rho_oof[1])}] | {c.n} |"
        )
    L.append("")
    L.append("## 4. Delta pareado (A - baseline) nos 3 recortes")
    L.append("")
    L.append("| recorte | n | Delta medio | IC95 Delta | vence? |")
    L.append("| --- | ---: | ---: | :---: | :---: |")
    for chave in (RECORTE_COMPLETO, RECORTE_METRO, RECORTE_FORA):
        rec = r.recortes[chave]
        comp = rec.comparacoes["cand_A"]
        L.append(
            f"| {chave} | {rec.n} | {_fmt(comp.delta_medio)} | "
            f"[{_fmt(comp.ic95_delta[0])}, {_fmt(comp.ic95_delta[1])}] | "
            f"{'SIM' if comp.vence else 'nao'} |"
        )
    L.append("")
    L.append("## 5. VEREDITO")
    L.append("")
    L.append(
        f"**{r.veredito}** -- Candidato A vence <=> IC95 do Delta pareado (mesmos folds, seed=42) "
        "nao cruza zero (inferior > 0) NO COMPLETO **E** FORA de SP/MG/RJ. "
        + (
            "O ganho generaliza fora do metropolitano -> recomendar ao BLK-TP-09 (DEC + gate)."
            if r.vence_candidato_a
            else "O ganho NAO sobrevive de forma robusta -> NAO recomendar aplicar (DEC-008: "
            "NO-GO e resultado valido)."
        )
    )
    L.append("")
    L.append("## 6. Candidato C -- ADIADO")
    L.append("")
    L.append(
        "O Candidato C (capacidade de consumo POR REDE, ponderando a oferta consumida pela "
        "capacidade real de cada rede via 2 km-decay) fica **ADIADO** neste ciclo por decisao do "
        "gate humano (2026-07-02). Motivo: a fonte de capacidade do BLK-TP-08-FU "
        "(`capacidade_media_por_rede.parquet`) traz medianas **~340 alunos** para 10 redes de "
        "**bairro** (panobianco/velocity/bio_ritmo/...), que sao **footprint de bairro, NAO "
        "capacidade de clube** -- e as grandes low-cost numerosas (smart_fit/selfit/bodytech/...) "
        "nem tem `flag_confiavel`. Usa-las como proxy de capacidade enviesaria fortemente o "
        "residual. A fonte CORRETA e futura para o Candidato C = capacidade de CLUBE real em "
        "`data/validacao/` (gitignored, dados reais, anti-PII): `Sky Fit dados.xlsx` (SkyFit), "
        "`academias_engenharia_do_corpo.xlsx` (Engenharia), `KPIs_Smart_2025_02 (1).xlsx` "
        "(Smart Fit KPIs). Retomar o Candidato C em bloco proprio quando essa capacidade de clube "
        "estiver disponivel na fronteira anti-PII."
    )
    L.append("")
    L.append("## 7. Nota honesta / confounds")
    L.append("")
    L.append("```")
    L.append(r.nota_honesta.rstrip("\n"))
    L.append("```")
    L.append("")
    return "\n".join(L)


def escrever_relatorio(r: RevalidacaoResult, *, path: Path) -> None:
    """Materializa o relatorio markdown (gitignored, sem PII). NAO chamada em teste."""
    path = Path(path)
    texto = relatorio_revalidacao(r)
    _assert_sem_pii_no_relatorio(texto)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(texto, encoding="utf-8")
    _logger.info("relatorio BLK-TP-06-FU1 escrito: %s", path)


def _assert_sem_pii_no_relatorio(texto: str) -> None:
    """Falha se qualquer coluna de COLUNAS_PII_PROIBIDAS aparecer como token isolado no texto.

    Word-boundary para nao casar substring de palavras PT legitimas (ex.: "id" em "medida").
    """
    baixo = texto.lower()
    presentes = {
        c for c in COLUNAS_PII_PROIBIDAS if re.search(rf"\b{re.escape(c.lower())}\b", baixo)
    }
    if presentes:  # pragma: no cover - rede de seguranca
        raise AssertionError(f"PII vazou no relatorio BLK-TP-06-FU1: {presentes}")


__all__ = [
    "CAP_REF",
    "ComparacaoPareada",
    "ResultadoCandidato",
    "RevalidacaoRecorte",
    "RevalidacaoResult",
    "alunos_menores_add_por_hex",
    "comparar_pareado",
    "comparar_por_recorte",
    "construir_pares_concorrentes",
    "construir_residuais_candidatos",
    "escrever_relatorio",
    "relatorio_revalidacao",
    "revalidar_candidatos",
    "validar_candidato",
]


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    _dem = pd.read_parquet(
        Path("data/staging/demanda_revelada_h3.parquet"), columns=["hex_id", "membros"]
    )
    _mkt = pd.read_parquet(
        Path("data/staging/hexagonos_mercado_mapeado.parquet"),
        columns=[
            "hex_id",
            "uf",
            "score_oportunidade_residual",
            "sam_fitness_potencial",
            "oferta_consumida_total_estimada",
        ],
    )
    _join = _dem.merge(_mkt, on="hex_id", how="inner")
    _of = pd.read_parquet(Path("data/staging/oferta_academias_menores_rede_h3.parquet"))
    _conc = pd.read_parquet(
        Path("data/staging/concorrentes_mapeados.parquet"),
        columns=["hex_id_res7", "rede", "status_registro"],
    )
    _pares = construir_pares_concorrentes(_conc)
    _res = revalidar_candidatos(_join, _of, _pares)
    escrever_relatorio(_res, path=Path("data/analysis/revalidacao_residual_candidatos.md"))
    print(_res.nota_honesta)
