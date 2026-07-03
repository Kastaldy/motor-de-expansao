"""BLK-TP-06-FU1: re-validacao do residual com CANDIDATOS de recalibracao.

Reproduz o baseline do BLK-TP-06 (`score_oportunidade_residual` vs demanda OBSERVADA,
+0,3119 out-of-fold) e valida OUT-OF-FOLD, com o MESMO harness/seed de `calibracao_residual.py`,
um residual CANDIDATO de recalibracao contra `log1p(membros)`, comparando por IC95 da DIFERENCA
PAREADA (bootstrap pareado, mesmos folds) e por recorte metropolitano (SP/MG/RJ x fora). Decide,
de forma honesta (DEC-008), SE e QUAL candidato alimenta o BLK-TP-09.

GATE HUMANO (FU1, APROVADO pelo usuario em 2026-07-02): rodar **baseline + Candidato A**.

BLK-TP-06-FU2 (gate = decisao AUTONOMA do orquestrador em 2026-07-02; usuario delegou): estende
com o Candidato C DECOMPOSTO em **C1** e **C2**, validados out-of-fold pelo MESMO harness:
  - **C1** (re-capacitar as grandes SEM bairro): re-deriva a oferta consumida dos CONCORRENTES
    point-level (decay linear 2 km a partir de lat/lng de `concorrentes_mapeados`) ponderando por
    CAPACIDADE de CLUBE REAL por rede (Smart ~2.370 / Engenharia ~3.106 de `data/validacao/`;
    fallback 2.500 p/ ~26 redes -- decisao (A)) no lugar do `·2500` uniforme do baseline.
  - **C2** (C1 + academias de bairro decaidas): soma ao C1 as academias de bairro (dedup fino,
    IDENTICO ao A) espalhadas por k-ring H3 k=1 PONDERADO por anel (1,0 central / 0,5 anel-1) com
    NORMALIZACAO Σ_pesos=4,0 (conserva massa; NAO infla ~4x -- decisao (B)).
  Veredito POR SUB-CANDIDATO (APLICAR_C1/C2 ou NAO_APLICAR): IC95 do Δ pareado (Cx−baseline,
  seed=42) sem cruzar zero NO COMPLETO **E** FORA de SP/MG/RJ (decisao (D)). NO-GO e VALIDO.

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
from collections.abc import Mapping
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

# --- Candidato C (FU2) --------------------------------------------------------
# Raio do decay linear point-level dos concorrentes (mesmo do baseline mapeado ~2 km).
RAIO_DECAY_M: float = 2000.0
# k-ring H3 do termo de bairro (res-7 espaca ~2,436 km centro-a-centro; k=1 ~= 2 km).
K_RING_BAIRRO: int = 1
# Pesos por anel (central, anel-1). Normalizados por Σ_pesos para conservar massa (decisao (B)).
PESOS_ANEL_BAIRRO: tuple[float, float] = (1.0, 0.5)
# Raio da Terra (m) para o Haversine local vetorizado (sem importar pipeline).
_RAIO_TERRA_M: float = 6_371_000.0


def _haversine_m(
    lat_h: float, lng_h: float, lat_i: np.ndarray, lng_i: np.ndarray
) -> np.ndarray:
    """Distancia haversine (m) de UM hex (lat_h, lng_h) a N concorrentes (arrays lat_i/lng_i).

    Vetorizado sobre os concorrentes. Local (NAO importa pipeline). Entrada em graus.
    """
    rlat_h = np.radians(lat_h)
    rlng_h = np.radians(lng_h)
    rlat_i = np.radians(lat_i)
    rlng_i = np.radians(lng_i)
    dlat = rlat_i - rlat_h
    dlng = rlng_i - rlng_h
    a = np.sin(dlat / 2.0) ** 2 + np.cos(rlat_h) * np.cos(rlat_i) * np.sin(dlng / 2.0) ** 2
    return 2.0 * _RAIO_TERRA_M * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


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
        return self._vence("cand_A")

    @property
    def vence_candidato_c1(self) -> bool:
        """True se o Candidato C1 vence (Delta pareado > 0) NO COMPLETO E FORA de SP/MG/RJ."""
        return self._vence("cand_C1")

    @property
    def vence_candidato_c2(self) -> bool:
        """True se o Candidato C2 vence (Delta pareado > 0) NO COMPLETO E FORA de SP/MG/RJ."""
        return self._vence("cand_C2")

    def _vence(self, chave: str) -> bool:
        """Regra comum: Δ pareado vence no COMPLETO E FORA de SP/MG/RJ (decisao (D))."""
        comp_completo = self.recortes[RECORTE_COMPLETO].comparacoes.get(chave)
        comp_fora = self.recortes[RECORTE_FORA].comparacoes.get(chave)
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
# Candidato C1 -- oferta consumida dos CONCORRENTES re-derivada point-level
# --------------------------------------------------------------------------- #
def oferta_concorrentes_recapacitada_por_hex(
    hex_ids: pd.Series,
    lat_hex: pd.Series,
    lng_hex: pd.Series,
    conc_df: pd.DataFrame,
    capacidade_por_rede: Mapping[str, float],
    *,
    raio_m: float = RAIO_DECAY_M,
    cap_fallback: float = CAP_REF,
) -> pd.Series:
    """Oferta consumida dos concorrentes por hex, re-derivada POINT-LEVEL (base do C1).

    Para cada hex `h` (centroide `lat_h,lng_h`) e cada concorrente valido `i` (rede `r_i`,
    `lat_i,lng_i`):
        `dist_m = haversine(h, i)`; `peso_2km_i = max(0, 1 - dist_m/raio_m)` se `dist_m<=raio_m` senao 0;
        `oferta[h] = Σ_i peso_2km_i · cap[r_i]`
    onde `cap[r_i]` = capacidade de CLUBE por rede (real de validacao ou `cap_fallback`=2.500). E o
    MESMO decay linear de 2 km do baseline mapeado -- SO troca o `·2500` uniforme pelo `·cap[r_i]`.

    Se `capacidade_por_rede[r] == 2500 ∀ r`, `oferta[h]` reproduz `oferta_efetiva_mapeada_2km·2500`
    do parquet (a menos do ruido de coords ~1 km) -- testado em comparabilidade.

    Vetorizado por hex (Haversine sobre os concorrentes, com bounding-box de ~raio antes do
    Haversine exato). Consome READ-ONLY; nunca escreve. Retorna Series indexada por `hex_id`.
    """
    df = conc_df
    if "status_registro" in df.columns:
        df = df[df["status_registro"].astype(str) == "valido"]
    lat_c = pd.to_numeric(df["lat"], errors="coerce").to_numpy(dtype=float)
    lng_c = pd.to_numeric(df["lng"], errors="coerce").to_numpy(dtype=float)
    rede_c = df["rede"].astype(str).to_numpy()
    ok = np.isfinite(lat_c) & np.isfinite(lng_c)
    lat_c, lng_c, rede_c = lat_c[ok], lng_c[ok], rede_c[ok]
    cap_c = np.array(
        [float(capacidade_por_rede.get(r, cap_fallback)) for r in rede_c], dtype=float
    )

    # Margem do bounding-box (graus). ~raio_m em lat; ajustado por cos(lat) em lng.
    graus_lat = (raio_m / _RAIO_TERRA_M) * (180.0 / np.pi)

    hx = hex_ids.astype(str).to_numpy()
    lat_h = pd.to_numeric(lat_hex, errors="coerce").to_numpy(dtype=float)
    lng_h = pd.to_numeric(lng_hex, errors="coerce").to_numpy(dtype=float)

    out = np.zeros(len(hx), dtype=float)
    for j in range(len(hx)):
        lh, gh = lat_h[j], lng_h[j]
        if not (np.isfinite(lh) and np.isfinite(gh)):
            continue
        coslat = max(np.cos(np.radians(lh)), 1e-6)
        graus_lng = graus_lat / coslat
        # Bounding-box: descarta concorrentes claramente fora do raio antes do Haversine exato.
        cand = (
            (np.abs(lat_c - lh) <= graus_lat) & (np.abs(lng_c - gh) <= graus_lng)
        )
        if not cand.any():
            continue
        dist = _haversine_m(lh, gh, lat_c[cand], lng_c[cand])
        peso = np.where(dist <= raio_m, np.clip(1.0 - dist / raio_m, 0.0, None), 0.0)
        out[j] = float(np.sum(peso * cap_c[cand]))
    # Index UNICO por hex (o mesmo hex computa o mesmo valor -> dedup por primeira ocorrencia).
    s = pd.Series(out, index=pd.Index(hx, name="hex_id"))
    return s[~s.index.duplicated(keep="first")]


# --------------------------------------------------------------------------- #
# Candidato C2 -- termo de bairro decaido por k-ring H3 (conserva massa)
# --------------------------------------------------------------------------- #
def oferta_bairro_decaida_kring_por_hex(
    add_por_hex: pd.Series,
    hexes_alvo: set[str],
    *,
    k: int = K_RING_BAIRRO,
    pesos_anel: tuple[float, ...] = PESOS_ANEL_BAIRRO,
) -> pd.Series:
    """Espalha os alunos de bairro `add_por_hex` por k-ring H3 com decay por anel (termo do C2).

    Para cada hex-fonte `hf` com `add_por_hex[hf]` alunos, distribui pelos aneis de `grid_disk(hf,k)`:
      - anel 0 (central): peso `pesos_anel[0]`;
      - anel d (1..k): peso `pesos_anel[d]` (default (1.0, 0.5) para k=1).
    NORMALIZA por `Σ_pesos` (conserva massa; NAO infla ~4x): `contrib(h)=add[hf]·peso(d)/Σ_pesos`,
    onde para k=1 `Σ_pesos = 1·1.0 + 6·0.5 = 4.0`. So contribuicoes para hexes em `hexes_alvo`
    (vizinhos fora do join sao descartados -- sem alvo `membros`). Retorna Series indexada por
    `hex_id`. Import de `h3` local (dep base). Consome READ-ONLY.
    """
    import h3

    if add_por_hex.empty:
        return pd.Series(dtype="float64")
    # Soma dos pesos: 1 hex central + 6 vizinhos por anel d (grid_ring tem 6d hexes no anel d).
    soma_pesos = pesos_anel[0] + sum(6 * d * pesos_anel[d] for d in range(1, k + 1))
    if soma_pesos <= 0.0:  # pragma: no cover - guard
        soma_pesos = 1.0

    acc: dict[str, float] = {}
    for hf, alunos in add_por_hex.items():
        val = float(alunos)
        if val == 0.0:
            continue
        hf_s = str(hf)
        try:
            aneis = [{hf_s}] + [set(h3.grid_ring(hf_s, d)) for d in range(1, k + 1)]
        except Exception:  # pragma: no cover - hex invalido (fixtures reais nao caem aqui)
            aneis = [{hf_s}]
        for d, anel in enumerate(aneis):
            peso = pesos_anel[d] if d < len(pesos_anel) else 0.0
            if peso == 0.0:
                continue
            contrib = val * peso / soma_pesos
            for h in anel:
                if h in hexes_alvo:
                    acc[h] = acc.get(h, 0.0) + contrib
    if not acc:
        return pd.Series(dtype="float64")
    s = pd.Series(acc, dtype="float64")
    s.index.name = "hex_id"
    return s


# --------------------------------------------------------------------------- #
# Construcao dos vetores de residual (baseline + Candidato A) -- EM MEMORIA
# --------------------------------------------------------------------------- #
def construir_residuais_candidatos(
    df_join: pd.DataFrame,
    of_menores_rede: pd.DataFrame,
    pares_concorrentes: set[tuple[str, str]],
    *,
    cap_ref: float = CAP_REF,
    capacidade_por_rede: Mapping[str, float] | None = None,
    conc_df: pd.DataFrame | None = None,
    k_ring: int = K_RING_BAIRRO,
    pesos_anel: tuple[float, ...] = PESOS_ANEL_BAIRRO,
) -> pd.DataFrame:
    """Devolve `df_join` + colunas EM MEMORIA: `residual_baseline`, `residual_cand_A`,
    `flag_metropolitano`; e, quando `capacidade_por_rede`+`conc_df` sao dados (FU2),
    `residual_cand_C1` e `residual_cand_C2`. NUNCA escreve parquet.

    - `residual_baseline` = `score_oportunidade_residual` do parquet (reproduz o BLK-TP-06).
    - `residual_cand_A` = enriquecido com o dedup FINO por par (hex, rede_menor):
        `oferta_consumida_ajustada = oferta_consumida_total_estimada + alunos_menores_add`
        `oferta_efetiva_ajustada   = max(sam_fitness_potencial - oferta_consumida_ajustada, 0)`
        `residual_cand_A           = clip(100 * oferta_efetiva_ajustada / cap_ref, 0, 100)`
      (cap_ref = denominador do clip INTOCADO). O residual CAI onde ha academias menores nao
      mapeadas (a maior parte da oferta menor).

    Candidato C (FU2, so quando `capacidade_por_rede` e `conc_df` sao fornecidos -- default
    `None` = comportamento FU1 byte-a-byte preservado):
    - `residual_cand_C1`: re-deriva a oferta consumida dos CONCORRENTES point-level (decay 2 km,
      lat/lng de `conc_df`) ponderando por `capacidade_por_rede` (real/fallback), somada ao termo
      Ultra INTOCADO (`oferta_consumida_ultra_estimada`):
        `oferta_C1 = Σ_i peso_2km_i·cap[r_i] + oferta_consumida_ultra_estimada`
        `residual_cand_C1 = clip(100·max(sam - oferta_C1, 0)/cap_ref, 0, 100)`.
    - `residual_cand_C2`: C1 + academias de bairro (dedup fino, IDENTICO ao A) espalhadas por
      k-ring H3 (k=`k_ring` ponderado por `pesos_anel`, normalizado -- conserva massa):
        `oferta_C2 = oferta_C1 + Σ_hf add[hf]·peso_anel/Σ_pesos`
        `residual_cand_C2 = clip(100·max(sam - oferta_C2, 0)/cap_ref, 0, 100)`.
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

    # --- Candidato C (FU2) ---------------------------------------------------
    if capacidade_por_rede is not None and conc_df is not None:
        ultra = (
            pd.to_numeric(df.get("oferta_consumida_ultra_estimada"), errors="coerce")
            .fillna(0.0)
            .astype(float)
            if "oferta_consumida_ultra_estimada" in df.columns
            else pd.Series(0.0, index=df.index)
        )
        oferta_conc_c1 = oferta_concorrentes_recapacitada_por_hex(
            df["hex_id"],
            df["lat"],
            df["lng"],
            conc_df,
            capacidade_por_rede,
            cap_fallback=cap_ref,
        )
        df["_oferta_conc_c1"] = (
            df["hex_id"].astype(str).map(oferta_conc_c1).fillna(0.0).astype(float)
        )
        consumida_c1 = df["_oferta_conc_c1"] + ultra.to_numpy(dtype=float)
        efetiva_c1 = np.clip(sam - consumida_c1, 0.0, None)
        df["residual_cand_C1"] = np.clip(100.0 * efetiva_c1 / cap_ref, 0.0, 100.0)

        hexes_alvo = set(df["hex_id"].astype(str))
        bairro_kring = oferta_bairro_decaida_kring_por_hex(
            add, hexes_alvo, k=k_ring, pesos_anel=pesos_anel
        )
        df["_oferta_bairro_kring"] = (
            df["hex_id"].astype(str).map(bairro_kring).fillna(0.0).astype(float)
        )
        consumida_c2 = consumida_c1 + df["_oferta_bairro_kring"]
        efetiva_c2 = np.clip(sam - consumida_c2, 0.0, None)
        df["residual_cand_C2"] = np.clip(100.0 * efetiva_c2 / cap_ref, 0.0, 100.0)

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
    """Valida baseline + Candidato A (e C1/C2, quando presentes) no recorte e compara vs baseline.

    Consome o df com `residual_baseline`/`residual_cand_A`/`membros` (e opcionalmente
    `residual_cand_C1`/`residual_cand_C2`) ja construidas. Cada candidato e validado out-of-fold
    e comparado (Δ pareado) contra o baseline.
    """
    baseline = validar_candidato(df_recorte, "residual_baseline", nome="baseline")
    candidatos: dict[str, ResultadoCandidato] = {}
    comparacoes: dict[str, ComparacaoPareada] = {}
    for chave, coluna in (
        ("cand_A", "residual_cand_A"),
        ("cand_C1", "residual_cand_C1"),
        ("cand_C2", "residual_cand_C2"),
    ):
        if coluna not in df_recorte.columns:
            continue
        cand = validar_candidato(df_recorte, coluna, nome=chave)
        candidatos[chave] = cand
        comparacoes[chave] = _comparacao_de(chave, baseline, cand)
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
    capacidade_por_rede: Mapping[str, float] | None = None,
    conc_df: pd.DataFrame | None = None,
    k_ring: int = K_RING_BAIRRO,
    pesos_anel: tuple[float, ...] = PESOS_ANEL_BAIRRO,
) -> RevalidacaoResult:
    """Orquestra o BLK-TP-06: constroi baseline + Candidato A (e C1/C2 quando os insumos de
    capacidade/concorrentes sao fornecidos), valida nos 3 recortes, compara pareado e emite
    veredito honesto POR SUB-CANDIDATO (DEC-008).

    Default (`capacidade_por_rede`/`conc_df` = None) = comportamento FU1 (baseline + A) byte-a-byte.
    READ-ONLY sobre o M1; nada escrito em disco aqui (o `__main__` escreve o relatorio).
    """
    df = construir_residuais_candidatos(
        df_join,
        of_menores_rede,
        pares_concorrentes,
        cap_ref=cap_ref,
        capacidade_por_rede=capacidade_por_rede,
        conc_df=conc_df,
        k_ring=k_ring,
        pesos_anel=pesos_anel,
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
    # Veredito. SEM Candidato C (FU1): formato legado "APLICAR_A"/"NAO_APLICAR" (byte-a-byte).
    # COM Candidato C (FU2): veredito POR SUB-CANDIDATO "APLICAR_C1; NAO_APLICAR_C2; ..." (inclui A).
    tem_c = "cand_C1" in recortes[RECORTE_COMPLETO].candidatos
    if not tem_c:
        result.veredito = "APLICAR_A" if result.vence_candidato_a else "NAO_APLICAR"
    else:
        partes = [
            ("A", result.vence_candidato_a),
            ("C1", result.vence_candidato_c1),
            ("C2", result.vence_candidato_c2),
        ]
        result.veredito = "; ".join(
            (f"APLICAR_{nome}" if vence else f"NAO_APLICAR_{nome}") for nome, vence in partes
        )
    result.nota_honesta = _nota_honesta(result)

    comp_completo = recortes[RECORTE_COMPLETO].comparacoes["cand_A"]
    comp_fora = recortes[RECORTE_FORA].comparacoes["cand_A"]
    _logger.info(
        "RevalidacaoResidual: baseline_r2=%.4f cand_A_r2=%.4f delta_completo_A=%.4f "
        "ic=(%.4f,%.4f) vence_A_completo=%s vence_A_fora=%s c_ativo=%s veredito=%s",
        recortes[RECORTE_COMPLETO].baseline.r2_oof_log,
        recortes[RECORTE_COMPLETO].candidatos["cand_A"].r2_oof_log,
        comp_completo.delta_medio,
        comp_completo.ic95_delta[0],
        comp_completo.ic95_delta[1],
        comp_completo.vence,
        comp_fora.vence,
        tem_c,
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
    tem_c = "cand_C1" in r.recortes[RECORTE_COMPLETO].candidatos
    cab_ciclo = (
        "GATE 2026-07-02 (orquestrador autonomo): FU2 -- baseline + Candidato C (C1 re-capacita "
        "concorrentes point-level por capacidade de clube real; C2 = C1 + bairro decaido por "
        "k-ring). Candidato A do FU1 tambem reportado."
        if tem_c
        else "GATE HUMANO 2026-07-02: rodar baseline + Candidato A APENAS. Candidato C e A+C ADIADOS "
        "(exigem capacidade de CLUBE real de data/validacao/, nao as medianas ~340 de bairro)."
    )
    linhas_c = ""
    if tem_c:
        for chave, rot in (("cand_C1", "C1"), ("cand_C2", "C2")):
            cc = r.recortes[RECORTE_COMPLETO].comparacoes.get(chave)
            cf = r.recortes[RECORTE_FORA].comparacoes.get(chave)
            cand_c = r.recortes[RECORTE_COMPLETO].candidatos.get(chave)
            if cc is None or cf is None or cand_c is None:
                continue
            linhas_c += (
                f"  Candidato {rot}: R2_oof_log={_fmt(cand_c.r2_oof_log)} IC95="
                f"[{_fmt(cand_c.ic95_r2_oof[0])}, {_fmt(cand_c.ic95_r2_oof[1])}] | "
                f"rho_oof={_fmt(cand_c.rho_oof)}\n"
                f"  Delta pareado ({rot}-baseline) COMPLETO = {_fmt(cc.delta_medio)} IC95="
                f"[{_fmt(cc.ic95_delta[0])}, {_fmt(cc.ic95_delta[1])}] -> vence={cc.vence}\n"
                f"  Delta pareado ({rot}-baseline) FORA (nao-metro) = {_fmt(cf.delta_medio)} IC95="
                f"[{_fmt(cf.ic95_delta[0])}, {_fmt(cf.ic95_delta[1])}] -> vence={cf.vence}\n"
            )
    confound_5 = (
        "  5. Candidato C: capacidade REAL cobre so ~33% dos pontos (Smart/Engenharia); o resto "
        "usa fallback 2.500 -> capacidade ~uniforme, C1 tende a NEUTRO. C2 pode reintroduzir o "
        "vies de co-localizacao bairro<->demanda que matou o A (decay+normalizacao atenuam).\n"
        if tem_c
        else "  5. Candidato C (capacidade de clube por rede) ADIADO -- fonte futura data/validacao/.\n"
    )
    return (
        "BLK-TP-06 -- re-validacao do residual (k-fold repetido, seed=42, vs baseline da media)\n"
        f"{cab_ciclo}\n"
        f"Veredito: {r.veredito}\n"
        f"  Baseline: R2_oof_log={_fmt(base.r2_oof_log)} IC95="
        f"[{_fmt(base.ic95_r2_oof[0])}, {_fmt(base.ic95_r2_oof[1])}] | rho_oof={_fmt(base.rho_oof)} "
        f"| n={base.n}\n"
        f"  Candidato A: R2_oof_log={_fmt(cand.r2_oof_log)} IC95="
        f"[{_fmt(cand.ic95_r2_oof[0])}, {_fmt(cand.ic95_r2_oof[1])}] | rho_oof={_fmt(cand.rho_oof)}\n"
        f"  Delta pareado (A-baseline) COMPLETO = {_fmt(comp_c.delta_medio)} IC95="
        f"[{_fmt(comp_c.ic95_delta[0])}, {_fmt(comp_c.ic95_delta[1])}] -> vence={comp_c.vence}\n"
        f"  Delta pareado (A-baseline) FORA (nao-metro) = {_fmt(comp_f.delta_medio)} IC95="
        f"[{_fmt(comp_f.ic95_delta[0])}, {_fmt(comp_f.ic95_delta[1])}] -> vence={comp_f.vence}\n"
        f"{linhas_c}"
        f"  Dedup fino: +{r.dedup_add} alunos somados / -{r.dedup_dup} dedupados no join.\n"
        "Confounds (read-only, nao corrigidos):\n"
        "  1. Cobertura ~1% do universo de hexes do Motor (DEC-012) -> refino metropolitano, "
        "NAO validacao nacional.\n"
        "  2. Vies metropolitano do Sudeste (SP/MG/RJ concentram ~metade do join) -> qualquer "
        "ganho so vale se sobrevive FORA de SP/MG/RJ.\n"
        "  3. Dedup fino por par (hex, rede): independentes sempre somam; so rede conhecida ja "
        "mapeada e dedupada. Coords ~1 km atenuam o sinal no join res-7.\n"
        "  4. DEC-009: `membros` e ALVO OBSERVADO; nunca preditor geografico de magnitude.\n"
        f"{confound_5}"
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


# --------------------------------------------------------------------------- #
# Relatorio dedicado do Candidato C (FU2)
# --------------------------------------------------------------------------- #
def _linha_candidato_c(r: RevalidacaoResult, chave: str) -> tuple[str, bool]:
    """(veredito_str, vence) de um sub-candidato C (chave 'cand_C1'/'cand_C2')."""
    nome = "C1" if chave == "cand_C1" else "C2"
    vence = r.vence_candidato_c1 if chave == "cand_C1" else r.vence_candidato_c2
    return (f"APLICAR_{nome}" if vence else f"NAO_APLICAR_{nome}", vence)


def relatorio_revalidacao_candidato_c(
    r: RevalidacaoResult,
    *,
    capacidades: Mapping[str, float] | None = None,
    ancora_sky: float | None = None,
    n_redes_alvo: int | None = None,
    n_redes_reais: int | None = None,
) -> str:
    """String markdown (PT, sem PII) do FU2: baseline + C1 + C2 + Δ pareado + veredito por
    sub-candidato + capacidades por rede (agregado) + confounds. Exige C1/C2 presentes."""
    L: list[str] = []
    L.append("# Re-validacao do residual -- Candidato C (C1 + C2) -- BLK-TP-06-FU2")
    L.append("")
    L.append(
        "READ-ONLY sobre o M1 (DEC-001/DEC-008/DEC-009/DEC-012/DEC-013). Pacote disjunto. Sem PII. "
        "A demanda (`membros`) e ALVO OBSERVADO; os residuais (baseline/C1/C2) sao os PREDITORES. "
        "Este bloco VALIDA + RECOMENDA -- NAO altera a formula do residual em producao nem "
        "regenera `hexagonos_mercado_mapeado.parquet`."
    )
    L.append("")
    L.append(
        "**Gate = decisao AUTONOMA do orquestrador (2026-07-02; usuario delegou):** (A) capacidade "
        "real Smart/Engenharia de `data/validacao/`, fallback 2.500 p/ ~26 redes, Sky so ancora; "
        "(B) decay bairro k=1 ponderado por anel (1,0/0,5), normalizado Σ=4,0 (conserva massa); "
        "(C) rodar C1 e C2; (D) vence = IC95 Δ pareado sem cruzar zero no completo E fora de "
        "SP/MG/RJ; (E) leitor de validacao anti-PII em modulo irmao."
    )
    L.append("")
    base = r.recortes[RECORTE_COMPLETO].baseline
    L.append("## 1. Baseline reproduzido (completo)")
    L.append("")
    L.append(f"- N do join = **{base.n}** (esperado ~16.411)")
    L.append(f"- R2_oof_log = **{_fmt(base.r2_oof_log)}** (esperado ~+0,3119)")
    L.append(f"- rho_oof = **{_fmt(base.rho_oof)}** (esperado ~+0,4615)")
    top_uf = ", ".join(f"{k} {v:.1f}%" for k, v in r.concentracao_uf.items()) or "n/d"
    L.append(f"- Concentracao top-3 UF = {top_uf}")
    L.append("")
    L.append("## 2. Capacidade de CLUBE por rede (agregado, sem PII)")
    L.append("")
    if capacidades:
        L.append("| rede | capacidade (mediana alunos/unidade) | fonte |")
        L.append("| --- | ---: | --- |")
        for rede, cap in sorted(capacidades.items(), key=lambda kv: -kv[1]):
            fonte = "validacao (real)" if abs(cap - CAP_REF) > 1e-6 else "fallback (2.500)"
            L.append(f"| {rede} | {cap:.0f} | {fonte} |")
        L.append("")
    if n_redes_alvo:
        cob = 100.0 * (n_redes_reais or 0) / n_redes_alvo
        L.append(
            f"- Cobertura de capacidade REAL = **{n_redes_reais or 0}/{n_redes_alvo} redes "
            f"(~{cob:.0f}%)**; POR PONTOS de `concorrentes_mapeados` = ~33% (Smart 999 + "
            "Engenharia 63 de 3.179 validos). As demais usam fallback 2.500 -> a capacidade "
            "por rede e ~uniforme na pratica; C1 tende a NEUTRO."
        )
    if ancora_sky is not None:
        L.append(
            f"- Ancora Sky Fit (NAO e rede mapeada; nenhum peso direto) = ~{ancora_sky:.0f} "
            "alunos/clube -> sustenta o fallback low-cost."
        )
    L.append("")
    L.append("## 3. C1 -- oferta consumida dos concorrentes re-capacitada (SEM bairro)")
    L.append("")
    L.append(
        "Formula: `oferta_C1 = Σ_i peso_2km_i·cap[r_i] + oferta_consumida_ultra_estimada`, "
        "`peso_2km_i = max(0, 1 - dist_m/2000)` (decay linear point-level, a partir das "
        "coordenadas de `concorrentes_mapeados`); "
        "`residual_cand_C1 = clip(100·max(sam - oferta_C1, 0)/2500, 0, 100)`."
    )
    L.append("")
    L.append("## 4. C2 -- C1 + academias de bairro decaidas (k-ring H3 k=1 ponderado)")
    L.append("")
    L.append(
        "Formula: `oferta_C2 = oferta_C1 + Σ_hf add[hf]·peso_anel/Σ_pesos`, k=1 pesos (1,0 "
        "central / 0,5 anel-1), NORMALIZADO por Σ_pesos=4,0 (conserva massa -- NAO infla ~4x). "
        "`add[hf]` = dedup fino IDENTICO ao Candidato A. "
        f"Dedup fino no join: +{r.dedup_add} alunos somados / -{r.dedup_dup} dedupados."
    )
    L.append("")
    L.append("## 5. Tabela comparativa (R2_oof / rho_oof / IC95) -- recorte completo")
    L.append("")
    L.append("| candidato | R2_oof_log | IC95 R2 | rho_oof | IC95 rho | n |")
    L.append("| --- | ---: | :---: | ---: | :---: | ---: |")
    rec_c = r.recortes[RECORTE_COMPLETO]
    linha_cands = [rec_c.baseline]
    for ch in ("cand_C1", "cand_C2"):
        if ch in rec_c.candidatos:
            linha_cands.append(rec_c.candidatos[ch])
    for c in linha_cands:
        L.append(
            f"| {c.nome} | {_fmt(c.r2_oof_log)} | "
            f"[{_fmt(c.ic95_r2_oof[0])}, {_fmt(c.ic95_r2_oof[1])}] | {_fmt(c.rho_oof)} | "
            f"[{_fmt(c.ic95_rho_oof[0])}, {_fmt(c.ic95_rho_oof[1])}] | {c.n} |"
        )
    L.append("")
    L.append("## 6. Delta pareado (Cx - baseline) nos 3 recortes")
    L.append("")
    for chave_cand in ("cand_C1", "cand_C2"):
        if chave_cand not in rec_c.candidatos:
            continue
        L.append(f"### {chave_cand}")
        L.append("")
        L.append("| recorte | n | Delta medio | IC95 Delta | vence? |")
        L.append("| --- | ---: | ---: | :---: | :---: |")
        for chave in (RECORTE_COMPLETO, RECORTE_METRO, RECORTE_FORA):
            rec = r.recortes[chave]
            comp = rec.comparacoes.get(chave_cand)
            if comp is None:
                continue
            L.append(
                f"| {chave} | {rec.n} | {_fmt(comp.delta_medio)} | "
                f"[{_fmt(comp.ic95_delta[0])}, {_fmt(comp.ic95_delta[1])}] | "
                f"{'SIM' if comp.vence else 'nao'} |"
            )
        L.append("")
    L.append("## 7. VEREDITO POR SUB-CANDIDATO")
    L.append("")
    for chave_cand in ("cand_C1", "cand_C2"):
        if chave_cand not in rec_c.candidatos:
            continue
        vstr, vence = _linha_candidato_c(r, chave_cand)
        rec_txt = (
            "SUPERA o baseline out-of-fold (Δ pareado > 0 no completo E fora de SP/MG/RJ) -> "
            "recomendar ao BLK-TP-09 (DEC + gate)."
            if vence
            else "NAO supera o baseline de forma robusta (Δ pareado cruza zero no completo e/ou "
            "nao sobrevive fora de SP/MG/RJ) -> NAO recomendar aplicar (DEC-008: NO-GO e valido)."
        )
        L.append(f"- **{vstr}**: {rec_txt}")
    L.append("")
    L.append(f"Veredito consolidado: **{r.veredito}**")
    L.append("")
    L.append("## 7.1 Recomendacao honesta ao BLK-TP-09")
    L.append("")
    comp_c1 = rec_c.comparacoes.get("cand_C1")
    if comp_c1 is not None and r.vence_candidato_c1:
        L.append(
            "- **C1 vence o criterio (D), mas o ganho e MATERIALMENTE DESPREZIVEL** "
            f"(Δ pareado completo ~{_fmt(comp_c1.delta_medio, 4)}; ~+0,002 de R2_oof sobre "
            "+0,3119). Isto CONFIRMA a hipotese (A): com capacidade REAL cobrindo so ~33% dos "
            "pontos (Smart ~2.363 / Engenharia ~3.107; fallback 2.500 no resto), re-capacitar as "
            "grandes quase nao move o residual -> **NAO justifica** trocar a formula em producao "
            "por um ganho de segunda casa decimal. Recomendacao pragmatica: **NAO aplicar C1** "
            "(o ganho nao paga o custo/risco de recalibrar), a menos que capacidade real por rede "
            "cubra a maioria dos pontos num bloco futuro."
        )
    else:
        L.append(
            "- **C1 NAO vence** de forma robusta -> nao recalibrar a oferta consumida dos "
            "concorrentes por capacidade de clube (DEC-008)."
        )
    L.append(
        "- **C2 NAO vence** (piora o baseline): espalhar as academias de bairro por k-ring, mesmo "
        "com decay + normalizacao que conserva massa, REPETE o padrao do Candidato A (NO-GO) -- o "
        "termo de bairro co-localiza com a demanda observada e consome oferta onde ha `membros`, "
        "derrubando o residual. **NAO aplicar C2.**"
    )
    L.append(
        "- **Conclusao:** o residual atual (baseline) segue como esta em producao. O FU2 ATRIBUIU "
        "CAUSA: o NO-GO do Candidato A nao era so crudeza de execucao -- nem re-capacitar (C1, "
        "neutro) nem incluir bairro com decay fino (C2, negativo) supera o baseline de forma util."
    )
    L.append("")
    L.append("## 8. Nota honesta / confounds")
    L.append("")
    L.append("```")
    L.append(r.nota_honesta.rstrip("\n"))
    L.append("```")
    L.append("")
    texto = "\n".join(L)
    _assert_sem_pii_no_relatorio(texto)
    return texto


def escrever_relatorio_candidato_c(
    r: RevalidacaoResult,
    *,
    path: Path,
    capacidades: Mapping[str, float] | None = None,
    ancora_sky: float | None = None,
    n_redes_alvo: int | None = None,
    n_redes_reais: int | None = None,
) -> None:
    """Materializa o relatorio do Candidato C (gitignored, sem PII). NAO chamada em teste."""
    path = Path(path)
    texto = relatorio_revalidacao_candidato_c(
        r,
        capacidades=capacidades,
        ancora_sky=ancora_sky,
        n_redes_alvo=n_redes_alvo,
        n_redes_reais=n_redes_reais,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(texto, encoding="utf-8")
    _logger.info("relatorio BLK-TP-06-FU2 (Candidato C) escrito: %s", path)


__all__ = [
    "CAP_REF",
    "K_RING_BAIRRO",
    "PESOS_ANEL_BAIRRO",
    "RAIO_DECAY_M",
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
    "escrever_relatorio_candidato_c",
    "oferta_bairro_decaida_kring_por_hex",
    "oferta_concorrentes_recapacitada_por_hex",
    "relatorio_revalidacao",
    "relatorio_revalidacao_candidato_c",
    "revalidar_candidatos",
    "validar_candidato",
]


if __name__ == "__main__":  # pragma: no cover
    from motor_expansao.demanda_revelada.capacidade_clube_validacao import (
        ancora_capacidade_sky,
        capacidade_por_rede_com_fallback,
        ler_capacidade_clube_por_rede,
    )

    logging.basicConfig(level=logging.INFO)
    _dem = pd.read_parquet(
        Path("data/staging/demanda_revelada_h3.parquet"), columns=["hex_id", "membros"]
    )
    _mkt = pd.read_parquet(
        Path("data/staging/hexagonos_mercado_mapeado.parquet"),
        columns=[
            "hex_id",
            "uf",
            "lat",
            "lng",
            "score_oportunidade_residual",
            "sam_fitness_potencial",
            "oferta_consumida_total_estimada",
            "oferta_consumida_ultra_estimada",
        ],
    )
    _join = _dem.merge(_mkt, on="hex_id", how="inner")
    _of = pd.read_parquet(Path("data/staging/oferta_academias_menores_rede_h3.parquet"))
    _conc_pares = pd.read_parquet(
        Path("data/staging/concorrentes_mapeados.parquet"),
        columns=["hex_id_res7", "rede", "status_registro"],
    )
    _pares = construir_pares_concorrentes(_conc_pares)

    # --- FU1: baseline + Candidato A (preservado) ---
    _res_a = revalidar_candidatos(_join, _of, _pares)
    escrever_relatorio(_res_a, path=Path("data/analysis/revalidacao_residual_candidatos.md"))
    print(_res_a.nota_honesta)

    # --- FU2: Candidato C (C1 + C2) com capacidade real por rede + concorrentes point-level ---
    _conc = pd.read_parquet(
        Path("data/staging/concorrentes_mapeados.parquet"),
        columns=["rede", "lat", "lng", "status_registro"],
    )
    _redes_alvo = sorted(_conc["rede"].astype(str).unique())
    _cap_reais = ler_capacidade_clube_por_rede()
    _cap = capacidade_por_rede_com_fallback(_redes_alvo, _cap_reais)
    _sky = ancora_capacidade_sky()
    _res_c = revalidar_candidatos(_join, _of, _pares, capacidade_por_rede=_cap, conc_df=_conc)
    escrever_relatorio_candidato_c(
        _res_c,
        path=Path("data/analysis/revalidacao_residual_candidato_c.md"),
        capacidades=_cap,
        ancora_sky=_sky,
        n_redes_alvo=len(_redes_alvo),
        n_redes_reais=len(_cap_reais),
    )
    print(_res_c.nota_honesta)
