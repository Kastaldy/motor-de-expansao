"""
Expansao de Dominio — Pipeline principal
=========================================
Bloco 2: candidatos elegiveis + clusters H3 intraurbanos.
Bloco 3: selecao greedy de hexes ancora.
Bloco 4: materializacao nacional com rankings.

Entrada : data/staging/hexagonos_mercado_mapeado.parquet
Saidas  : data/outputs/plano_expansao_dominio.parquet
          data/outputs/plano_expansao_dominio.csv
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
import unicodedata
from pathlib import Path
from typing import Optional

import h3
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
ENTRADA = ROOT / "data" / "staging" / "hexagonos_mercado_mapeado.parquet"
SAIDA_PARQUET = ROOT / "data" / "outputs" / "plano_expansao_dominio.parquet"
SAIDA_CSV = ROOT / "data" / "outputs" / "plano_expansao_dominio.csv"

# ── Parametros canonicos (alinhados a docs/expansao_dominio.md) ──────────────
H3_RESOLUTION = 7
RAIO_CAPTURA_KM = 2.0
DIST_MIN_NOVAS_ULTRAS_KM = 1.5
DIST_MIN_ULTRA_EXISTENTE_KM = 1.0
MAX_ANCORAS_POR_CIDADE = 10
MIN_SCORE_OPORTUNIDADE_RESIDUAL = 20.0
CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS = 2500

COLS_INPUT = [
    "hex_id", "uf", "cod_municipio", "nome_municipio",
    "lat", "lng",
    "score_oportunidade_residual", "oferta_efetiva_disponivel",
    "sam_fitness_potencial", "flag_sam_fitness",
    "dist_ultra_mais_proxima_m", "flag_canibalizacao_ultra_1km",
    "pressao_concorrencial_score_2km", "flag_white_space_2km",
    "n_concorrentes_mapeados_2km",
]

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)


# =============================================================================
# 1. Filtro de candidatos
# =============================================================================

def filtrar_candidatos(
    df: pd.DataFrame,
    min_score: float = MIN_SCORE_OPORTUNIDADE_RESIDUAL,
) -> pd.DataFrame:
    """Aplica os 6 gates de elegibilidade e retorna candidatos validos."""
    mask = (
        (df["flag_sam_fitness"] == True)  # noqa: E712
        & (df["oferta_efetiva_disponivel"] > 0)
        & (df["score_oportunidade_residual"] >= min_score)
        & df["lat"].notna()
        & df["lng"].notna()
        & (df["flag_canibalizacao_ultra_1km"] == False)  # noqa: E712
        & df["lat"].between(-90, 90)
        & df["lng"].between(-180, 180)
    )
    result = df[mask].copy().reset_index(drop=True)
    log.info("Candidatos elegiveis: %d / %d hexes", len(result), len(df))
    return result


# =============================================================================
# 2. Clusters por adjacencia H3
# =============================================================================

def construir_clusters(df: pd.DataFrame) -> pd.DataFrame:
    """
    Agrupa hexes candidatos em clusters por adjacencia H3 res7 dentro do mesmo
    cod_municipio (union-find). Adiciona coluna cluster_id = '{cod_municipio}_{seq}'.
    """
    if df.empty:
        return df.assign(cluster_id=pd.Series(dtype="str"))

    hex_ids = df["hex_id"].tolist()
    muni_map: dict[str, str] = dict(zip(df["hex_id"], df["cod_municipio"]))
    hex_set = set(hex_ids)

    parent: dict[str, str] = {h: h for h in hex_ids}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: str, y: str) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for h in hex_ids:
        neighbors = set(h3.grid_disk(h, 1)) - {h}
        for nb in neighbors:
            if nb in hex_set and muni_map.get(nb) == muni_map[h]:
                union(h, nb)

    # Atribui IDs sequenciais por municipio
    root_to_id: dict[str, str] = {}
    counters: dict[str, int] = {}
    cluster_ids: list[str] = []

    for h in hex_ids:
        root = find(h)
        if root not in root_to_id:
            muni = muni_map[h]
            seq = counters.get(muni, 0) + 1
            counters[muni] = seq
            root_to_id[root] = f"{muni}_{seq:03d}"
        cluster_ids.append(root_to_id[root])

    result = df.copy()
    result["cluster_id"] = cluster_ids
    log.info(
        "Clusters formados: %d em %d municipios",
        result["cluster_id"].nunique(),
        result["cod_municipio"].nunique(),
    )
    return result


# =============================================================================
# 3. Metricas por cluster
# =============================================================================

def calcular_metricas_cluster(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega metricas por cluster e faz join de volta ao DataFrame de candidatos."""
    if df.empty or "cluster_id" not in df.columns:
        for col in [
            "n_hex_cluster", "residual_total_cluster", "score_residual_max",
            "score_residual_medio", "sam_total_cluster",
            "pressao_concorrencial_media", "dist_ultra_min_cluster",
        ]:
            df[col] = pd.Series(dtype="float64")
        return df

    agg = df.groupby("cluster_id", sort=False).agg(
        n_hex_cluster=("hex_id", "count"),
        residual_total_cluster=("oferta_efetiva_disponivel", "sum"),
        score_residual_max=("score_oportunidade_residual", "max"),
        score_residual_medio=("score_oportunidade_residual", "mean"),
        sam_total_cluster=("sam_fitness_potencial", "sum"),
        pressao_concorrencial_media=("pressao_concorrencial_score_2km", "mean"),
        dist_ultra_min_cluster=("dist_ultra_mais_proxima_m", "min"),
    ).reset_index()

    return df.merge(agg, on="cluster_id", how="left")


# =============================================================================
# 4. Distancia e decaimento residual
# =============================================================================

def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2.0 * R * math.asin(min(1.0, math.sqrt(a)))


def _haversine_array(lat0: float, lng0: float, lats: np.ndarray, lngs: np.ndarray) -> np.ndarray:
    R = 6_371_000.0
    phi0 = math.radians(lat0)
    phi = np.radians(lats)
    dphi = np.radians(lats - lat0)
    dlambda = np.radians(lngs - lng0)
    a = np.sin(dphi / 2) ** 2 + math.cos(phi0) * np.cos(phi) * np.sin(dlambda / 2) ** 2
    return 2.0 * R * np.arcsin(np.clip(np.sqrt(a), 0.0, 1.0))


# =============================================================================
# 5. Classificacao de tese de dominio
# =============================================================================

def classificar_tese_dominio(
    ordem: int,
    score_residual: float,
    n_concorrentes: int,
    dist_ultra_m: float,
    flag_white_space: bool,
) -> str:
    if 1000.0 <= dist_ultra_m < 2000.0:
        return "proteger_corredor_ultra"
    if flag_white_space and score_residual >= 50.0:
        return "dominar_white_space"
    if n_concorrentes > 0 and ordem == 1:
        return "abrir_com_disputa"
    if ordem >= 2:
        return "adensar_cluster"
    return "monitorar"


# =============================================================================
# 6. Selecao greedy de hexes ancora por cidade
# =============================================================================

def selecionar_ancoras_greedy(
    df_cidade: pd.DataFrame,
    max_ancoras: int = MAX_ANCORAS_POR_CIDADE,
    dist_min_km: float = DIST_MIN_NOVAS_ULTRAS_KM,
    raio_km: float = RAIO_CAPTURA_KM,
) -> pd.DataFrame:
    """
    Greedy por cidade: a cada passo escolhe o hex que maximiza residual incremental
    capturado (decaimento linear ate raio_km), respeitando distancia minima entre
    ancoras. Desempate por score_oportunidade_residual.
    Retorna apenas os hexes selecionados com colunas de auditoria.
    """
    if df_cidade.empty:
        return pd.DataFrame()

    raio_m = raio_km * 1000.0
    dist_min_m = dist_min_km * 1000.0

    df = df_cidade.reset_index(drop=True)
    n = len(df)
    lats = df["lat"].to_numpy(dtype=float)
    lngs = df["lng"].to_numpy(dtype=float)
    scores = df["score_oportunidade_residual"].to_numpy(dtype=float)

    # Distancias pairwise (n x n) — O(n²), aceitavel para granularidade hex
    dist_matrix = np.zeros((n, n), dtype=float)
    for i in range(n):
        dist_matrix[i] = _haversine_array(lats[i], lngs[i], lats, lngs)

    residual_rem = df["oferta_efetiva_disponivel"].to_numpy(dtype=float).copy()
    selected: list[int] = []
    records: list[dict] = []
    ordem = 0

    for _ in range(max_ancoras):
        eligible = np.ones(n, dtype=bool)
        for s in selected:
            eligible[s] = False
            eligible &= dist_matrix[s] >= dist_min_m

        if not eligible.any():
            break

        best_idx = -1
        best_capture = -1.0
        best_tiebreak = -1.0

        for i in range(n):
            if not eligible[i]:
                continue
            within = dist_matrix[i] < raio_m
            factors = np.maximum(0.0, 1.0 - dist_matrix[i][within] / raio_m)
            capture = float(np.dot(residual_rem[within], factors))

            if capture > best_capture or (capture == best_capture and scores[i] > best_tiebreak):
                best_idx = i
                best_capture = capture
                best_tiebreak = scores[i]

        if best_idx < 0:
            break

        ordem += 1

        dist_nearest = (
            float(min(dist_matrix[best_idx][s] for s in selected))
            if selected else float("nan")
        )

        # Consume residual com decaimento linear
        within = dist_matrix[best_idx] < raio_m
        factors = np.maximum(0.0, 1.0 - dist_matrix[best_idx][within] / raio_m)
        residual_rem[within] *= 1.0 - factors
        residual_pos = float(residual_rem.sum())

        row = df.iloc[best_idx]
        tese = classificar_tese_dominio(
            ordem=ordem,
            score_residual=float(scores[best_idx]),
            n_concorrentes=int(row.get("n_concorrentes_mapeados_2km") or 0),
            dist_ultra_m=float(row.get("dist_ultra_mais_proxima_m") or float("inf")),
            flag_white_space=bool(row.get("flag_white_space_2km", False)),
        )

        record = row.to_dict()
        record.update({
            "ordem_expansao_cidade": ordem,
            "residual_incremental_capturado": best_capture,
            "residual_cluster_pos_acao": residual_pos,
            "dist_nova_ancora_mais_proxima_m": dist_nearest,
            "tese_dominio": tese,
        })
        selected.append(best_idx)
        records.append(record)

    return pd.DataFrame(records) if records else pd.DataFrame()


def gerar_plano_dominio(
    df: pd.DataFrame,
    max_ancoras: int = MAX_ANCORAS_POR_CIDADE,
    dist_min_km: float = DIST_MIN_NOVAS_ULTRAS_KM,
) -> pd.DataFrame:
    """Executa selecao greedy por cidade e retorna plano consolidado."""
    partes: list[pd.DataFrame] = []
    cidades = df["cod_municipio"].unique()
    log.info("Executando greedy em %d cidades...", len(cidades))

    for cod in cidades:
        ancoras = selecionar_ancoras_greedy(
            df[df["cod_municipio"] == cod],
            max_ancoras=max_ancoras,
            dist_min_km=dist_min_km,
        )
        if not ancoras.empty:
            partes.append(ancoras)

    if not partes:
        log.warning("Nenhuma ancora selecionada.")
        return pd.DataFrame()

    plano = pd.concat(partes, ignore_index=True)
    log.info(
        "Plano gerado: %d ancoras em %d cidades",
        len(plano), plano["cod_municipio"].nunique(),
    )
    return plano


# =============================================================================
# 7. Pipeline completa de candidatos
# =============================================================================

def carregar_candidatos(
    cidade: Optional[str] = None,
    uf: Optional[str] = None,
    min_score: float = MIN_SCORE_OPORTUNIDADE_RESIDUAL,
) -> pd.DataFrame:
    if not ENTRADA.exists():
        log.error("Parquet de mercado nao encontrado: %s", ENTRADA)
        sys.exit(1)

    df = pd.read_parquet(ENTRADA, columns=COLS_INPUT)
    log.info(
        "Base carregada: %d hexes | %d municipios | %d UFs",
        len(df), df["cod_municipio"].nunique(), df["uf"].nunique(),
    )

    if uf:
        df = df[df["uf"].str.upper() == uf.upper()]
        log.info("Filtro UF=%s: %d hexes", uf.upper(), len(df))

    if cidade:
        def _asc(s: str) -> str:
            return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().casefold()

        cidade_norm = _asc(cidade)
        mask = df["nome_municipio"].map(lambda v: _asc(str(v)) == cidade_norm if pd.notna(v) else False)
        df = df[mask]
        log.info("Filtro cidade=%s: %d hexes", cidade, len(df))

    df = filtrar_candidatos(df, min_score=min_score)
    df = construir_clusters(df)
    df = calcular_metricas_cluster(df)

    return df


# =============================================================================
# 7b. Filtro top-N cidades por residual
# =============================================================================

def _top_cidades_por_residual(df: pd.DataFrame, top_n: int) -> pd.DataFrame:
    """Mantém apenas as top_n cidades com maior residual total disponivel."""
    top_cods = (
        df.groupby("cod_municipio")["oferta_efetiva_disponivel"]
        .sum()
        .sort_values(ascending=False)
        .head(top_n)
        .index
    )
    result = df[df["cod_municipio"].isin(top_cods)].copy()
    log.info(
        "Top %d cidades por residual: %d candidatos selecionados",
        top_n, len(result),
    )
    return result


# =============================================================================
# 8. Rankings nacionais e sub-nacionais
# =============================================================================

def adicionar_rankings(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona rank_dominio_brasil, rank_dominio_uf e rank_dominio_cidade."""
    df = df.copy()
    df["rank_dominio_brasil"] = (
        df["residual_incremental_capturado"]
        .rank(method="first", ascending=False)
        .astype(int)
    )
    df["rank_dominio_uf"] = (
        df.groupby("uf")["residual_incremental_capturado"]
        .rank(method="first", ascending=False)
        .astype(int)
    )
    df["rank_dominio_cidade"] = (
        df.groupby("cod_municipio")["residual_incremental_capturado"]
        .rank(method="first", ascending=False)
        .astype(int)
    )
    return df


# =============================================================================
# 9. Smoke de schema e materializacao
# =============================================================================

SCHEMA_DOMINIO_OBRIGATORIO: frozenset[str] = frozenset({
    "hex_id", "uf", "cod_municipio", "nome_municipio", "lat", "lng",
    "cluster_id", "tese_dominio",
    "ordem_expansao_cidade", "residual_incremental_capturado",
    "residual_cluster_pos_acao", "dist_nova_ancora_mais_proxima_m",
    "rank_dominio_brasil", "rank_dominio_uf", "rank_dominio_cidade",
})


def validate_dominio_schema(df: pd.DataFrame) -> None:
    """Smoke check: garante que o plano contem as colunas obrigatorias."""
    ausentes = SCHEMA_DOMINIO_OBRIGATORIO - set(df.columns)
    assert not ausentes, f"colunas ausentes no plano de dominio: {sorted(ausentes)}"


def materializar(df: pd.DataFrame) -> None:
    """Valida e persiste o plano em parquet e csv."""
    assert df["hex_id"].notna().all(), "hex_id nulo detectado no plano"
    assert not df["hex_id"].duplicated().any(), "hex_id duplicado detectado no plano"
    validate_dominio_schema(df)
    SAIDA_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(SAIDA_PARQUET, index=False)
    df.to_csv(SAIDA_CSV, sep=";", encoding="utf-8-sig", index=False)
    log.info("Salvo: %s (%d linhas)", SAIDA_PARQUET.name, len(df))
    log.info("Salvo: %s", SAIDA_CSV.name)


# =============================================================================
# 5. CLI
# =============================================================================

def _parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Expansao de Dominio — pipeline")
    p.add_argument("--dry-run", action="store_true", help="Preview sem salvar")
    p.add_argument("--cidade", type=str, default=None)
    p.add_argument("--uf", type=str, default=None)
    p.add_argument("--min-score-residual", type=float, default=MIN_SCORE_OPORTUNIDADE_RESIDUAL)
    p.add_argument("--max-ancoras-cidade", type=int, default=MAX_ANCORAS_POR_CIDADE)
    p.add_argument("--top-cidades", type=int, default=None)
    p.add_argument("--min-dist-novas-ultras-km", type=float, default=DIST_MIN_NOVAS_ULTRAS_KM)
    return p.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()

    df = carregar_candidatos(
        cidade=args.cidade,
        uf=args.uf,
        min_score=args.min_score_residual,
    )

    if args.top_cidades and not args.cidade:
        df = _top_cidades_por_residual(df, args.top_cidades)

    plano = gerar_plano_dominio(
        df,
        max_ancoras=args.max_ancoras_cidade,
        dist_min_km=args.min_dist_novas_ultras_km,
    )

    if args.dry_run:
        log.info("=== DRY-RUN ===")
        log.info("Candidatos : %d hexes", len(df))
        log.info("Ancoras    : %d", len(plano))
        if not plano.empty:
            log.info("Cidades    : %d", plano["cod_municipio"].nunique())
            top = (
                plano.groupby("nome_municipio", sort=False)
                .agg(
                    n_ancoras=("hex_id", "count"),
                    residual_cap=("residual_incremental_capturado", "sum"),
                    tese=("tese_dominio", lambda x: x.value_counts().index[0]),
                )
                .sort_values("residual_cap", ascending=False)
                .head(10)
            )
            log.info("\nTop cidades:\n%s", top.to_string())
        log.info("Dry-run concluido. Nenhum arquivo salvo.")
        sys.exit(0)

    if plano.empty:
        log.warning("Plano vazio. Nenhum arquivo salvo.")
        sys.exit(0)

    plano = adicionar_rankings(plano)
    materializar(plano)
    log.info(
        "Bloco 4 concluido: %d ancoras em %d cidades.",
        len(plano),
        plano["cod_municipio"].nunique(),
    )
