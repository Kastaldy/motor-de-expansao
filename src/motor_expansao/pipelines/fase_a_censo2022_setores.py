"""
Fase A — Ingestao do Censo 2022 por Setor Censitario (Piloto GO + SP + RJ).

Camada paralela ao M1 oficial. NAO altera score_priorizacao, hex_score_estrutural
nem nenhum artefato listado na secao 10 do CLAUDE.md.

Fluxo:
1. Leitura dos CSVs de agregados por setor (Basico + DomicilioRenda)
2. Leitura da malha de setores censitarios 2022 (shapefile)
3. Spatial join setor x hexagono H3-r7 com ponderacao por area de intersecao
4. Calculo do score experimental score_setor_2022_exp
5. Validacao (cobertura, amplitude, rastreabilidade)
6. Geracao de artefatos e relatorio
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import date
from pathlib import Path
from typing import Any

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
import structlog
from shapely.geometry import Polygon

try:
    from motor_expansao.pipelines.teste_setor_censitario_2010 import (
        _percentil_em_distribuicao_referencia,
    )
except ModuleNotFoundError:
    from teste_setor_censitario_2010 import (  # type: ignore[no-redef]
        _percentil_em_distribuicao_referencia,
    )

from motor_expansao.pipelines.m1.hex_enrichment import (
    _calcular_percentil_nacional,
    resumir_distribuicao_score,
)

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

UFS_PILOTO = {"GO": "52", "SP": "35", "RJ": "33"}

DATA_DOWNLOAD_DEFAULT = date.today().isoformat()

DEFAULT_RAW_DIR = Path("data/raw/censo2022_setores/ano=2022")
DEFAULT_STAGING_DIR = Path("data/staging")
DEFAULT_REPORT_PATH = Path("data/reports/fase_a_censo2022_piloto.md")
DEFAULT_BASE_OFICIAL_PATH = Path("data/staging/brasil_estrutural.parquet")
DEFAULT_HEX_ROOT = Path("data/staging/brasil")

OUTPUT_PARQUET = "censo2022_setores_h3_res7.parquet"

# Caminhos dos arquivos nacionais (Censo 2022 download completo)
NACIONAL_RAW_DIR = Path("data/raw/CENSO 2022")
NACIONAL_BASICO_PATH = (
    NACIONAL_RAW_DIR
    / "Agregados_por_setores_basico_BR_20250417"
    / "Agregados_por_setores_basico_BR_20250417.csv"
)
NACIONAL_RENDA_PATH = (
    NACIONAL_RAW_DIR
    / "Agregados_por_setores_renda_responsavel_BR_csv"
    / "Agregados_por_setores_renda_responsavel_BR.csv"
)
NACIONAL_SHAPEFILE_PATH = (
    NACIONAL_RAW_DIR / "BR_setores_CD2022" / "BR_setores_CD2022.shp"
)

# Colunas canonicas esperadas nos CSVs do IBGE Censo 2022
COD_SETOR_CANDIDATES = (
    "Cod_setor", "CD_SETOR", "cod_setor", "cd_setor",
    "GEOCODIGO", "geocodigo", "Codigo_do_setor",
)
# v0001 = Total de pessoas (populacao total do setor — dicionario IBGE 2022)
# v0002 = Total de Domicilios (nao populacao; era usado erroneamente como pop antes de 2026-05-15)
# Candidatas em ordem de preferencia: v0001 primeiro para arquivos nacionais 2022
POP_V002_CANDIDATES = ("v0001", "V0001", "V001", "v001", "V002", "v002", "v0002", "V0002")
# V06005 = renda total dos responsaveis; V06004 = media (arquivo renda_responsavel)
RENDA_V003_CANDIDATES = ("V003", "v003", "V06005", "v06005", "V06004", "v06004")

# Colunas canonicas na malha shapefile
SHP_COD_SETOR_CANDIDATES = (
    "CD_SETOR", "Cod_setor", "cod_setor", "cd_setor",
    "GEOCODIGO", "geocodigo",
)

# Referencia do experimento 2010 para comparacao
REF_2010 = {
    "GO": {"cobertura": 100.0, "amplitude_p95_p05": 71.47},
    "SP": {"cobertura": 100.0, "amplitude_p95_p05": 69.06},
    "RJ": {"cobertura": 97.88, "amplitude_p95_p05": 74.31},
}

# ---------------------------------------------------------------------------
# Passo 1 — Leitura e limpeza dos CSVs
# ---------------------------------------------------------------------------


def _resolve_column(df: pd.DataFrame, candidates: tuple[str, ...], descricao: str) -> str:
    """Resolve uma coluna pelo nome, tolerando variantes de case."""
    cols_lower = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand in df.columns:
            return cand
        found = cols_lower.get(cand.lower())
        if found:
            return found
    raise ValueError(
        f"Coluna de {descricao} nao encontrada. "
        f"Candidatas: {candidates}. Colunas disponiveis: {list(df.columns)}"
    )


def ler_csv_ibge(path: Path, encoding: str = "latin-1", sep: str = ";") -> pd.DataFrame:
    """Le CSV do IBGE com tratamento padrao de encoding e separador."""
    return pd.read_csv(path, encoding=encoding, sep=sep, low_memory=False)


def ler_basico_setor(path: Path) -> tuple[pd.DataFrame, dict]:
    """Le o CSV Basico com V002 (populacao total por setor)."""
    df = ler_csv_ibge(path)
    col_cod = _resolve_column(df, COD_SETOR_CANDIDATES, "codigo de setor (Basico)")
    col_pop = _resolve_column(df, POP_V002_CANDIDATES, "V002 populacao (Basico)")

    resultado = pd.DataFrame()
    resultado["cod_setor"] = df[col_cod].astype(str).str.strip()
    resultado["pop_total_setor_2022"] = pd.to_numeric(df[col_pop], errors="coerce")

    total_antes = len(resultado)
    resultado = resultado[
        resultado["pop_total_setor_2022"].notna()
        & (resultado["pop_total_setor_2022"] > 0)
    ].copy()
    descartados_pop = total_antes - len(resultado)

    info = {
        "arquivo": str(path),
        "total_linhas": total_antes,
        "validos": len(resultado),
        "descartados_pop_invalida": descartados_pop,
        "col_cod_setor": col_cod,
        "col_pop": col_pop,
    }
    log.info("basico_setor_lido", **info)
    return resultado.reset_index(drop=True), info


def ler_renda_setor(path: Path) -> tuple[pd.DataFrame, dict]:
    """Le o CSV DomicilioRenda com V003 (renda total do setor)."""
    df = ler_csv_ibge(path)
    col_cod = _resolve_column(df, COD_SETOR_CANDIDATES, "codigo de setor (Renda)")
    col_renda = _resolve_column(df, RENDA_V003_CANDIDATES, "V003 renda (DomicilioRenda)")

    resultado = pd.DataFrame()
    resultado["cod_setor"] = df[col_cod].astype(str).str.strip()
    resultado["renda_total_setor_2022"] = pd.to_numeric(df[col_renda], errors="coerce")

    total_antes = len(resultado)
    resultado = resultado[
        resultado["renda_total_setor_2022"].notna()
        & (resultado["renda_total_setor_2022"] >= 0)
    ].copy()
    descartados_renda = total_antes - len(resultado)

    info = {
        "arquivo": str(path),
        "total_linhas": total_antes,
        "validos": len(resultado),
        "descartados_renda_invalida": descartados_renda,
        "col_cod_setor": col_cod,
        "col_renda": col_renda,
    }
    log.info("renda_setor_lida", **info)
    return resultado.reset_index(drop=True), info


def preparar_atributos_setor(
    df_basico: pd.DataFrame, df_renda: pd.DataFrame
) -> pd.DataFrame:
    """Junta Basico + DomicilioRenda e calcula renda per capita."""
    df = df_basico.merge(df_renda, on="cod_setor", how="inner")
    df["renda_per_capita_setor_2022"] = np.where(
        df["pop_total_setor_2022"] > 0,
        df["renda_total_setor_2022"] / df["pop_total_setor_2022"],
        np.nan,
    )
    # Descartar setores sem renda per capita valida
    df = df[df["renda_per_capita_setor_2022"].notna()].copy()
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Passo 2 — Leitura da malha de setores (shapefile)
# ---------------------------------------------------------------------------


def ler_malha_setores(path: Path) -> gpd.GeoDataFrame:
    """Le shapefile de setores censitarios e reprojeta para EPSG:4326."""
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        log.warning("malha_sem_crs", path=str(path))
        gdf = gdf.set_crs("EPSG:4326")
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs("EPSG:4326")

    # Resolver coluna de codigo de setor
    col_cod = _resolve_column(gdf, SHP_COD_SETOR_CANDIDATES, "codigo de setor (shapefile)")
    gdf = gdf.rename(columns={col_cod: "cod_setor"})
    gdf["cod_setor"] = gdf["cod_setor"].astype(str).str.strip()

    # Corrigir geometrias invalidas
    invalid_mask = ~gdf.geometry.is_valid
    if invalid_mask.any():
        gdf.loc[invalid_mask, "geometry"] = gdf.loc[invalid_mask, "geometry"].buffer(0)
        log.info("geometrias_corrigidas", total=int(invalid_mask.sum()))

    gdf = gdf[gdf.geometry.notna() & gdf["cod_setor"].str.len().gt(0)].copy()
    log.info("malha_setores_lida", total_setores=len(gdf), path=str(path))
    return gdf[["cod_setor", "geometry"]].reset_index(drop=True)


def juntar_malha_com_atributos(
    gdf_malha: gpd.GeoDataFrame, df_atributos: pd.DataFrame
) -> gpd.GeoDataFrame:
    """Join da malha com atributos por cod_setor."""
    gdf = gdf_malha.merge(df_atributos, on="cod_setor", how="inner")
    if gdf.empty:
        raise ValueError("Join malha x atributos ficou vazio. Verifique cod_setor.")
    # Calcular area de cada setor (em graus^2, consistente com hexagonos)
    gdf["area_setor"] = gdf.geometry.area
    gdf = gdf[gdf["area_setor"] > 0].copy()
    log.info("malha_com_atributos", total=len(gdf))
    return gdf.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Passo 3 — Spatial join setor censitario x hexagono H3-r7
# ---------------------------------------------------------------------------


def _hex_polygon(hex_id: str) -> Polygon:
    boundary = h3.cell_to_boundary(hex_id)
    return Polygon([(lng, lat) for lat, lng in boundary])


def carregar_hexagonos_uf(hex_root: Path, uf: str) -> pd.DataFrame:
    """Carrega hexagonos H3-r7 de uma UF."""
    path = hex_root / f"uf={uf}" / "hexagonos.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Hexagonos nao encontrados: {path}")
    df = pd.read_parquet(path)
    log.info("hexagonos_carregados", uf=uf, total=len(df))
    return df


def spatial_join_area_weighted(
    df_hex: pd.DataFrame,
    gdf_setores: gpd.GeoDataFrame,
) -> pd.DataFrame:
    """Spatial join com ponderacao por area de intersecao via overlay.

    Para cada hexagono:
    - pop_total: soma ponderada (pop_setor * area_intersecao / area_setor)
    - renda_per_capita: media ponderada por area de intersecao
    - coverage_pct: area coberta por setores / area do hexagono
    """
    hex_geoms = [_hex_polygon(h) for h in df_hex["hex_id"]]
    gdf_hex = gpd.GeoDataFrame(
        df_hex[["hex_id"]].copy(),
        geometry=hex_geoms,
        crs="EPSG:4326",
    )
    gdf_hex["area_hex"] = gdf_hex.geometry.area

    gdf_s = gdf_setores[["cod_setor", "geometry", "area_setor",
                          "pop_total_setor_2022", "renda_total_setor_2022",
                          "renda_per_capita_setor_2022"]].copy()

    def _empty_result(df_hex_in: pd.DataFrame) -> pd.DataFrame:
        result = df_hex_in.copy()
        result["pop_total_setor_2022"] = np.nan
        result["renda_per_capita_setor_2022"] = np.nan
        result["renda_total_setor_2022"] = np.nan
        result["n_setores_contribuintes"] = 0
        result["coverage_pct_setor_2022"] = 0.0
        return result.reset_index(drop=True)

    # Overlay intersection: calcula geometria de intersecao diretamente
    try:
        overlay = gpd.overlay(gdf_hex, gdf_s, how="intersection", keep_geom_type=False)
    except Exception as e:
        log.warning("overlay_falhou", error=str(e))
        return _empty_result(df_hex)

    if overlay.empty:
        log.warning("overlay_vazio")
        return _empty_result(df_hex)

    overlay["area_intersecao"] = overlay.geometry.area
    overlay = overlay[overlay["area_intersecao"] > 0].copy()

    if overlay.empty:
        return _empty_result(df_hex)

    # Fator proporcional: fracao do setor que cai no hexagono
    overlay["frac_setor"] = (overlay["area_intersecao"] / overlay["area_setor"]).clip(0, 1)

    # Calcular contribuicoes ponderadas antes de agregar
    overlay["pop_contrib"] = overlay["pop_total_setor_2022"] * overlay["frac_setor"]
    overlay["renda_total_contrib"] = overlay["renda_total_setor_2022"] * overlay["frac_setor"]
    overlay["renda_pc_contrib"] = overlay["renda_per_capita_setor_2022"] * overlay["area_intersecao"]

    # Agregar por hexagono
    agg = overlay.groupby("hex_id").agg(
        pop_total_setor_2022=("pop_contrib", "sum"),
        renda_total_setor_2022=("renda_total_contrib", "sum"),
        renda_pc_num=("renda_pc_contrib", "sum"),
        renda_pc_den=("area_intersecao", "sum"),
        n_setores_contribuintes=("cod_setor", "count"),
        area_coberta=("area_intersecao", "sum"),
    ).reset_index()

    agg["renda_per_capita_setor_2022"] = np.where(
        agg["renda_pc_den"] > 0,
        agg["renda_pc_num"] / agg["renda_pc_den"],
        np.nan,
    )

    # Merge com hexagonos originais
    hex_area_map = dict(zip(gdf_hex["hex_id"], gdf_hex["area_hex"], strict=False))
    result = df_hex.copy()
    result = result.merge(
        agg[["hex_id", "pop_total_setor_2022", "renda_total_setor_2022",
             "renda_per_capita_setor_2022", "n_setores_contribuintes", "area_coberta"]],
        on="hex_id",
        how="left",
    )
    result["area_hex"] = result["hex_id"].map(hex_area_map)
    result["coverage_pct_setor_2022"] = np.where(
        result["area_hex"].fillna(0) > 0,
        (result["area_coberta"].fillna(0) / result["area_hex"] * 100).clip(0, 100),
        0.0,
    )
    result["n_setores_contribuintes"] = result["n_setores_contribuintes"].fillna(0).astype(int)
    result = result.drop(columns=["area_coberta", "area_hex"], errors="ignore")

    return result.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Passo 4 — Fallback
# ---------------------------------------------------------------------------


def aplicar_fallback(df: pd.DataFrame, threshold: float = 0.10) -> pd.DataFrame:
    """Marca hexagonos com cobertura insuficiente para fallback."""
    df = df.copy()
    coverage = df["coverage_pct_setor_2022"].fillna(0) / 100.0
    low_coverage = coverage < threshold

    df["fallback_setor_2022"] = low_coverage
    df["motivo_fallback_setor_2022"] = np.where(
        low_coverage, "cobertura_insuficiente", pd.NA
    )

    # Zerar valores de hexagonos com cobertura insuficiente
    cols_zerar = ["pop_total_setor_2022", "renda_per_capita_setor_2022", "renda_total_setor_2022"]
    for col in cols_zerar:
        if col in df.columns:
            df.loc[low_coverage, col] = np.nan

    n_fallback = int(low_coverage.sum())
    if n_fallback > 0:
        log.info("fallback_aplicado", total=n_fallback, pct=round(n_fallback / len(df) * 100, 2))
    return df


# ---------------------------------------------------------------------------
# Passo 5 — Score experimental
# ---------------------------------------------------------------------------


def calcular_score_setor_2022(
    df: pd.DataFrame,
    base_nacional: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Calcula score_setor_2022_exp usando percentis ancorados na distribuicao M1."""
    df = df.copy()

    pop = pd.to_numeric(df.get("pop_total_setor_2022", pd.Series(dtype=float)), errors="coerce")
    renda = pd.to_numeric(df.get("renda_per_capita_setor_2022", pd.Series(dtype=float)), errors="coerce")

    # Fonte de populacao: V002/v0002 do Censo 2022, agregada ao hexagono por area.
    df["fonte_populacao_setor"] = np.where(
        pop.notna(), "ibge_censo2022_v0002_pop_total_area_weighted", pd.NA
    )

    # Percentis ancorados na distribuicao nacional do M1
    if base_nacional is not None and not base_nacional.empty:
        ref_renda = pd.to_numeric(
            base_nacional.get("renda_per_capita", pd.Series(dtype=float)), errors="coerce"
        )
        ref_pop = pd.to_numeric(
            base_nacional.get("populacao_proxy", pd.Series(dtype=float)), errors="coerce"
        )
        df["renda_pct_setor"] = _percentil_em_distribuicao_referencia(renda, ref_renda)
        df["pop_pct_setor"] = _percentil_em_distribuicao_referencia(pop, ref_pop)
        df["percentil_escopo"] = "nacional_m1"
    else:
        df["renda_pct_setor"] = _calcular_percentil_nacional(renda)
        df["pop_pct_setor"] = _calcular_percentil_nacional(pop)
        df["percentil_escopo"] = "local_subconjunto"

    # Score experimental
    mask = renda.notna() & pop.notna() & ~df.get("fallback_setor_2022", False)
    df["score_setor_2022_exp"] = np.nan
    if mask.any():
        df.loc[mask, "score_setor_2022_exp"] = (
            100 * (
                0.60 * df.loc[mask, "renda_pct_setor"]
                + 0.40 * df.loc[mask, "pop_pct_setor"]
            )
        ).round(2)

    return df


# ---------------------------------------------------------------------------
# Rastreabilidade
# ---------------------------------------------------------------------------


def adicionar_rastreabilidade(
    df: pd.DataFrame, data_download: str
) -> pd.DataFrame:
    """Adiciona colunas de rastreabilidade canonica."""
    df = df.copy()
    has_data = df.get("n_setores_contribuintes", pd.Series(0, index=df.index)).fillna(0) > 0

    df["fonte_setor_2022"] = np.where(has_data, "IBGE_Censo2022_Setores", pd.NA)
    df["data_referencia_setor_2022"] = np.where(has_data, data_download, pd.NA)
    df["metodo_agregacao_setor_2022"] = np.where(has_data, "area_weighted", pd.NA)
    df["qualidade_setor_2022"] = np.where(has_data, "gold", pd.NA)
    df["domicilios_setor_2022"] = np.nan  # nao disponivel separadamente nesta versao

    return df


# ---------------------------------------------------------------------------
# Validacao
# ---------------------------------------------------------------------------


def validar_uf(
    df: pd.DataFrame, uf: str
) -> dict:
    """Valida metricas de uma UF contra os gates de qualidade."""
    total_hex = len(df)
    if total_hex == 0:
        return {"uf": uf, "status": "NO-GO", "motivo": "sem hexagonos"}

    has_match = df["n_setores_contribuintes"].fillna(0) > 0
    hex_com_match = int(has_match.sum())
    cobertura_pct = round(hex_com_match / total_hex * 100, 2)

    score = pd.to_numeric(df["score_setor_2022_exp"], errors="coerce").dropna()
    if len(score) > 1:
        p95 = float(score.quantile(0.95))
        p05 = float(score.quantile(0.05))
        amplitude = round(p95 - p05, 2)
        std = round(float(score.std(ddof=0)), 2)
        distintos = int(score.nunique())
    else:
        amplitude = 0.0
        std = 0.0
        distintos = 0

    # Rastreabilidade nulos
    rastreio_cols = ["fonte_setor_2022", "data_referencia_setor_2022"]
    nulos_rastreio = 0
    total_rastreio = 0
    for col in rastreio_cols:
        if col in df.columns:
            subset = df[has_match]
            nulos_rastreio += int(subset[col].isna().sum())
            total_rastreio += len(subset)
    pct_nulos_rastreio = round(nulos_rastreio / max(total_rastreio, 1) * 100, 2)

    # Gates
    gate_cobertura = cobertura_pct >= 85.0
    gate_amplitude = amplitude > 50.0
    gate_nulos = pct_nulos_rastreio <= 2.0

    status = "GO" if (gate_cobertura and gate_amplitude and gate_nulos) else "NO-GO"

    ref = REF_2010.get(uf, {})

    resultado = {
        "uf": uf,
        "total_hex": total_hex,
        "hex_com_match": hex_com_match,
        "cobertura_pct": cobertura_pct,
        "amplitude_p95_p05": amplitude,
        "std_score": std,
        "valores_distintos": distintos,
        "pct_nulos_rastreio": pct_nulos_rastreio,
        "gate_cobertura": gate_cobertura,
        "gate_amplitude": gate_amplitude,
        "gate_nulos": gate_nulos,
        "status": status,
        "ref_2010_cobertura": ref.get("cobertura"),
        "ref_2010_amplitude": ref.get("amplitude_p95_p05"),
    }
    return resultado


# ---------------------------------------------------------------------------
# Relatorio
# ---------------------------------------------------------------------------


def _markdown_table(headers: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        lines.append("| " + " | ".join(str(v) for v in row) + " |")
    return "\n".join(lines)


def gerar_relatorio(
    validacoes: list[dict],
    info_processamento: dict,
    df_consolidado: pd.DataFrame,
) -> str:
    """Gera relatorio Markdown da Fase A."""
    linhas = [
        "# Fase A — Censo 2022 por Setor Censitario (Piloto GO + SP + RJ)",
        "",
        f"> Data de execucao: {date.today().isoformat()}",
        "> Fonte: IBGE Censo Demografico 2022 — Agregados por Setores Censitarios",
        "",
        "## 1. Setores processados por UF",
        "",
    ]

    for uf, info in info_processamento.get("por_uf", {}).items():
        linhas.append(f"### {uf}")
        linhas.append(f"- Setores no Basico: {info.get('setores_basico', 'N/A')}")
        linhas.append(f"- Setores no DomicilioRenda (linhas totais): {info.get('setores_renda', 'N/A')}")
        if "setores_renda_validos" in info:
            linhas.append(f"- Setores no DomicilioRenda (renda valida): {info.get('setores_renda_validos', 'N/A')}")
        linhas.append(f"- Setores com match (apos join): {info.get('setores_join', 'N/A')}")
        linhas.append(f"- Setores descartados (pop invalida): {info.get('descartados_pop', 0)}")
        linhas.append(f"- Setores descartados (renda invalida): {info.get('descartados_renda', 0)}")
        if "join_mismatch_pct" in info:
            linhas.append(f"- Mismatch estrutural do join (%): {info.get('join_mismatch_pct', 'N/A')}")
        linhas.append("")

    linhas += [
        "## 2. Cobertura espacial por UF",
        "",
    ]

    headers_cob = ["UF", "Hex total", "Hex com match", "Cobertura %",
                    "Ref 2010 %", "Gate (>=85%)"]
    rows_cob = []
    for v in validacoes:
        rows_cob.append([
            v["uf"], v["total_hex"], v["hex_com_match"],
            f"{v['cobertura_pct']:.2f}",
            f"{v.get('ref_2010_cobertura', 'N/A')}",
            "PASS" if v["gate_cobertura"] else "FAIL",
        ])
    linhas.append(_markdown_table(headers_cob, rows_cob))
    linhas.append("")

    linhas += [
        "## 3. Amplitude intraurbana (score_setor_2022_exp)",
        "",
    ]
    headers_amp = ["UF", "Amplitude p95-p05", "Ref 2010", "Std", "Distintos", "Gate (>50)"]
    rows_amp = []
    for v in validacoes:
        rows_amp.append([
            v["uf"],
            f"{v['amplitude_p95_p05']:.2f}",
            f"{v.get('ref_2010_amplitude', 'N/A')}",
            f"{v['std_score']:.2f}",
            v["valores_distintos"],
            "PASS" if v["gate_amplitude"] else "FAIL",
        ])
    linhas.append(_markdown_table(headers_amp, rows_amp))
    linhas.append("")

    linhas += [
        "## 4. Rastreabilidade",
        "",
    ]
    headers_r = ["UF", "% nulos rastreio", "Gate (<=2%)"]
    rows_r = []
    for v in validacoes:
        rows_r.append([
            v["uf"],
            f"{v['pct_nulos_rastreio']:.2f}",
            "PASS" if v["gate_nulos"] else "FAIL",
        ])
    linhas.append(_markdown_table(headers_r, rows_r))
    linhas.append("")

    linhas += [
        "## 5. Comparacao com experimento 2010",
        "",
    ]
    headers_comp = ["UF", "Cobertura 2022", "Cobertura 2010", "Ampl. 2022", "Ampl. 2010"]
    rows_comp = []
    for v in validacoes:
        rows_comp.append([
            v["uf"],
            f"{v['cobertura_pct']:.2f}%",
            f"{v.get('ref_2010_cobertura', 'N/A')}%",
            f"{v['amplitude_p95_p05']:.2f}",
            f"{v.get('ref_2010_amplitude', 'N/A')}",
        ])
    linhas.append(_markdown_table(headers_comp, rows_comp))
    linhas.append("")

    # Distribuicao de score
    score_col = pd.to_numeric(df_consolidado["score_setor_2022_exp"], errors="coerce")
    dist = resumir_distribuicao_score(score_col)
    linhas += [
        "## 6. Distribuicao do score experimental",
        "",
        f"- count: {dist.get('count', 0)}",
        f"- min: {dist.get('min', 'N/A')}",
        f"- max: {dist.get('max', 'N/A')}",
        f"- media: {dist.get('media', 'N/A')}",
        f"- mediana: {dist.get('mediana', 'N/A')}",
        f"- std: {dist.get('std', 'N/A')}",
        f"- p90: {dist.get('p90', 'N/A')}",
        "",
    ]

    # Status consolidado
    all_go = all(v["status"] == "GO" for v in validacoes)
    linhas += [
        "## 7. Status do gate de qualidade",
        "",
    ]
    headers_gate = ["UF", "Cobertura", "Amplitude", "Rastreio", "Status"]
    rows_gate = []
    for v in validacoes:
        rows_gate.append([
            v["uf"],
            "PASS" if v["gate_cobertura"] else "FAIL",
            "PASS" if v["gate_amplitude"] else "FAIL",
            "PASS" if v["gate_nulos"] else "FAIL",
            f"**{v['status']}**",
        ])
    linhas.append(_markdown_table(headers_gate, rows_gate))
    linhas.append("")

    linhas += [
        "## 8. Recomendacao",
        "",
    ]
    if all_go:
        linhas += [
            "**GO** — Todas as UFs piloto passaram nos gates de qualidade.",
            "Recomendacao: avancar para escala nacional.",
        ]
    else:
        falhas = [v["uf"] for v in validacoes if v["status"] != "GO"]
        linhas += [
            f"**NO-GO** — UFs com falha: {', '.join(falhas)}.",
            "Recomendacao: revisar metodologia antes de escalar.",
        ]

    linhas += [
        "",
        "## 9. Observacoes",
        "",
        "- `score_setor_2022_exp` e experimental — NAO substitui `score_priorizacao` oficial.",
        "- Nenhum artefato do M1 oficial foi alterado.",
        "- Percentis ancorados na distribuicao nacional do M1 via `_percentil_em_distribuicao_referencia()`.",
        "- Hexagonos com cobertura < 10% foram marcados como fallback e nao receberam score.",
        "- `domicilios_setor_2022` nao disponivel nesta versao (coluna nula).",
    ]

    return "\n".join(linhas) + "\n"


# ---------------------------------------------------------------------------
# Descoberta automatica de arquivos
# ---------------------------------------------------------------------------


def descobrir_arquivos_uf(raw_dir: Path, uf: str) -> dict:
    """Descobre automaticamente os arquivos de uma UF no diretorio raw."""
    cod = UFS_PILOTO[uf]
    resultado: dict[str, Path | None] = {"basico": None, "renda": None, "shapefile": None}

    # Procurar CSVs
    csvs = list(raw_dir.rglob("*.csv")) + list(raw_dir.rglob("*.CSV"))
    uf_lower = uf.lower()

    for csv_path in csvs:
        nome = csv_path.name.lower()
        # Basico
        if ("basico" in nome or "básico" in nome) and (uf_lower in nome or cod in nome):
            resultado["basico"] = csv_path
        # DomicilioRenda
        elif ("renda" in nome or "domicilio" in nome) and (uf_lower in nome or cod in nome):
            resultado["renda"] = csv_path

    # Procurar shapefile
    shps = list(raw_dir.rglob("*.shp")) + list(raw_dir.rglob("*.SHP"))
    for shp_path in shps:
        nome = shp_path.name.lower()
        if uf_lower in nome or cod in nome or f"_{uf_lower}" in nome:
            resultado["shapefile"] = shp_path

    # Tambem aceitar GeoPackage ou GeoJSON
    if resultado["shapefile"] is None:
        for ext in ("*.gpkg", "*.geojson"):
            for geo_path in raw_dir.rglob(ext):
                nome = geo_path.name.lower()
                if uf_lower in nome or cod in nome:
                    resultado["shapefile"] = geo_path
                    break

    return resultado


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------


def executar_fase_a(
    *,
    ufs: list[str] | None = None,
    raw_dir: Path = DEFAULT_RAW_DIR,
    hex_root: Path = DEFAULT_HEX_ROOT,
    base_oficial_path: Path = DEFAULT_BASE_OFICIAL_PATH,
    staging_dir: Path = DEFAULT_STAGING_DIR,
    report_path: Path = DEFAULT_REPORT_PATH,
    data_download: str = DATA_DOWNLOAD_DEFAULT,
    basico_paths: dict[str, Path] | None = None,
    renda_paths: dict[str, Path] | None = None,
    shapefile_paths: dict[str, Path] | None = None,
) -> dict:
    """Executa pipeline completo da Fase A."""
    if ufs is None:
        ufs = list(UFS_PILOTO.keys())

    basico_paths = basico_paths or {}
    renda_paths = renda_paths or {}
    shapefile_paths = shapefile_paths or {}

    log.info("fase_a_inicio", ufs=ufs, raw_dir=str(raw_dir))

    # Carregar base oficial para ancoragem de percentis
    base_oficial = pd.read_parquet(base_oficial_path)
    log.info("base_oficial_carregada", total=len(base_oficial))

    all_results = []
    validacoes = []
    info_processamento: dict[str, Any] = {"por_uf": {}}

    for uf in ufs:
        log.info("processando_uf", uf=uf)

        # Descobrir ou usar caminhos explicitos
        if uf in basico_paths and uf in renda_paths and uf in shapefile_paths:
            arquivos = {
                "basico": basico_paths[uf],
                "renda": renda_paths[uf],
                "shapefile": shapefile_paths[uf],
            }
        else:
            arquivos = descobrir_arquivos_uf(raw_dir, uf)

        for tipo, path in arquivos.items():
            if path is None:
                raise FileNotFoundError(
                    f"Arquivo {tipo} nao encontrado para UF {uf} em {raw_dir}. "
                    f"Baixe os dados do IBGE e coloque em {raw_dir}."
                )
            if not path.exists():
                raise FileNotFoundError(f"Arquivo nao existe: {path}")

        # Passo 1: Ler CSVs
        df_basico, info_basico = ler_basico_setor(arquivos["basico"])
        df_renda, info_renda = ler_renda_setor(arquivos["renda"])
        df_atributos = preparar_atributos_setor(df_basico, df_renda)

        info_processamento["por_uf"][uf] = {
            "setores_basico": info_basico["validos"],
            "setores_renda": info_renda["validos"],
            "setores_join": len(df_atributos),
            "descartados_pop": info_basico["descartados_pop_invalida"],
            "descartados_renda": info_renda["descartados_renda_invalida"],
        }

        # Passo 2: Ler malha
        gdf_malha = ler_malha_setores(arquivos["shapefile"])
        gdf_setores = juntar_malha_com_atributos(gdf_malha, df_atributos)

        # Passo 3: Carregar hexagonos e spatial join
        df_hex = carregar_hexagonos_uf(hex_root, uf)
        t0 = time.perf_counter()
        df_result = spatial_join_area_weighted(df_hex, gdf_setores)
        tempo_join = round(time.perf_counter() - t0, 2)
        log.info("spatial_join_completo", uf=uf, tempo_s=tempo_join, total_hex=len(df_result))

        # Passo 4: Fallback
        df_result = aplicar_fallback(df_result)

        # Passo 5: Score experimental
        df_result = calcular_score_setor_2022(df_result, base_nacional=base_oficial)

        # Rastreabilidade
        df_result = adicionar_rastreabilidade(df_result, data_download)

        # Adicionar UF para consolidacao
        if "uf" not in df_result.columns:
            df_result["uf"] = uf

        # Validacao
        validacao = validar_uf(df_result, uf)
        validacao["tempo_spatial_join_s"] = tempo_join
        validacoes.append(validacao)
        log.info("validacao_uf", **validacao)

        all_results.append(df_result)

    # Consolidar
    df_consolidado = pd.concat(all_results, ignore_index=True)
    df_consolidado = df_consolidado.reset_index(drop=True)

    # Salvar parquet
    staging_dir.mkdir(parents=True, exist_ok=True)
    output_path = staging_dir / OUTPUT_PARQUET
    colunas_salvar = [
        "hex_id", "lat", "lng", "uf", "regiao",
        "pop_total_setor_2022", "renda_per_capita_setor_2022",
        "renda_total_setor_2022", "domicilios_setor_2022",
        "n_setores_contribuintes", "coverage_pct_setor_2022",
        "fallback_setor_2022", "motivo_fallback_setor_2022",
        "renda_pct_setor", "pop_pct_setor",
        "score_setor_2022_exp", "percentil_escopo",
        "fonte_populacao_setor",
        "fonte_setor_2022", "data_referencia_setor_2022",
        "metodo_agregacao_setor_2022", "qualidade_setor_2022",
    ]
    colunas_existentes = [c for c in colunas_salvar if c in df_consolidado.columns]
    df_consolidado[colunas_existentes].to_parquet(output_path, index=False)
    log.info("parquet_salvo", path=str(output_path), linhas=len(df_consolidado))

    # Salvar CSVs raw individuais (copia de referencia)
    raw_dir.mkdir(parents=True, exist_ok=True)

    # Relatorio
    report_path.parent.mkdir(parents=True, exist_ok=True)
    relatorio = gerar_relatorio(validacoes, info_processamento, df_consolidado)
    report_path.write_text(relatorio, encoding="utf-8")
    log.info("relatorio_salvo", path=str(report_path))

    # Metadata
    metadata = {
        "data_execucao": date.today().isoformat(),
        "ufs_processadas": ufs,
        "total_hexagonos": len(df_consolidado),
        "validacoes": validacoes,
        "output_parquet": str(output_path),
        "report_path": str(report_path),
        "all_go": all(v["status"] == "GO" for v in validacoes),
    }

    # Salvar metadata
    meta_path = staging_dir / "censo2022_setores_h3_res7_metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    return metadata


# ---------------------------------------------------------------------------
# Suporte a arquivos nacionais do Censo 2022
# ---------------------------------------------------------------------------
# Os arquivos nacionais (download completo do IBGE 2022) nao possuem CD_SETOR
# com precisao suficiente nos CSVs (6 sig figs no Basico, 3 no Renda).
# A estrategia adotada e:
#   - Basico x Shapefile: join posicional por UF (mesma qtd de linhas, mesma ordem)
#   - Renda x Basico:     join posicional por UF (renda tem ~1-3% de linhas a menos;
#                          setores faltantes na renda sao marcados como NaN / fallback)
# ---------------------------------------------------------------------------


def ler_malha_nacional_uf(shp_path: Path, uf: str) -> gpd.GeoDataFrame:
    """Le shapefile nacional e filtra por UF.

    Retorna GeoDataFrame com cod_setor (15 digitos) + geometry, ordenado por
    CD_SETOR (mesma ordem que Basico_BR_nacional filtrado por CD_UF).
    """
    cod_uf = UFS_PILOTO[uf]
    gdf = gpd.read_file(shp_path, where=f"CD_UF='{cod_uf}'")
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs("EPSG:4326")

    # Resolver coluna de sector
    col_cod = _resolve_column(gdf, SHP_COD_SETOR_CANDIDATES, "codigo de setor (shapefile nacional)")
    gdf = gdf.rename(columns={col_cod: "cod_setor"})
    gdf["cod_setor"] = gdf["cod_setor"].astype(str).str.strip().str.zfill(15)

    # Corrigir geometrias invalidas
    invalid_mask = ~gdf.geometry.is_valid
    if invalid_mask.any():
        gdf.loc[invalid_mask, "geometry"] = gdf.loc[invalid_mask, "geometry"].buffer(0)

    gdf = gdf[gdf.geometry.notna() & gdf["cod_setor"].str.len().eq(15)].copy()
    gdf = gdf.sort_values("cod_setor").reset_index(drop=True)
    log.info("malha_nacional_uf_lida", uf=uf, total=len(gdf))
    return gdf[["cod_setor", "geometry"]]


def ler_basico_nacional_uf(basico_path: Path, uf: str) -> pd.DataFrame:
    """Le CSV Basico nacional e filtra por CD_UF.

    Preserva a ordem original (igual ao shapefile filtrado por UF).
    Colunas carregadas (dicionario IBGE Censo 2022):
    - v0001: Total de pessoas (populacao total do setor)
    - v0002: Total de Domicilios (nao populacao — usado apenas como fallback de domicilios)
    - v0005: Media de moradores em Domicilios Particulares Ocupados (household size, '2,8')
    - v0007: Total de Domicilios Particulares Ocupados (DPPO + DPIO)
    """
    cod_uf = int(UFS_PILOTO[uf])
    df = pd.read_csv(basico_path, sep=";", encoding="latin-1", low_memory=False,
                     usecols=["CD_UF", "v0001", "v0002", "v0005", "v0007"], dtype=str)
    df = df[df["CD_UF"].astype(int) == cod_uf].copy()

    # v0001 = Total de pessoas (populacao total) — corrigido em 2026-05-15
    df["pop_total_setor_2022"] = pd.to_numeric(df["v0001"], errors="coerce")
    df["pop_total_setor_2022"] = df["pop_total_setor_2022"].where(
        df["pop_total_setor_2022"] >= 0, np.nan
    )
    # v0007 = Domicilios Particulares Ocupados (referencia para household size)
    df["domicilios_setor"] = pd.to_numeric(df["v0007"], errors="coerce")
    # v0005 = media de moradores por domicilio (comma decimal, e.g. '2,8')
    v0005_str = df["v0005"].str.replace(",", ".", regex=False)
    df["avg_household_size"] = pd.to_numeric(v0005_str, errors="coerce")
    # Fallback: v0001/v0007 = pessoas / domicilios particulares ocupados
    fallback_size = np.where(
        df["domicilios_setor"] > 0,
        df["pop_total_setor_2022"] / df["domicilios_setor"],
        np.nan,
    )
    df["avg_household_size"] = df["avg_household_size"].fillna(pd.Series(fallback_size, index=df.index))
    # Limitar entre 1 e 15 (valores biologicamente razoaveis)
    df["avg_household_size"] = df["avg_household_size"].clip(lower=1.0, upper=15.0)

    df = df.reset_index(drop=True)
    log.info("basico_nacional_uf_lido", uf=uf, total=len(df),
             avg_size_median=float(df["avg_household_size"].median()))
    return df[["pop_total_setor_2022", "avg_household_size"]]


def ler_renda_nacional_uf(renda_path: Path, uf: str) -> pd.DataFrame:
    """Le CSV Renda nacional e filtra por UF via prefixo do CD_SETOR.

    O CD_SETOR no arquivo renda tem apenas 3 sig figs; a filtragem por UF
    e feita convertendo para int64 e extraindo os 2 primeiros digitos.
    Coluna usada: V06005 (renda total dos responsaveis no setor).
    AVISO: join posicional por UF — erro esperado de ~0.35-2.8% de setores.
    """
    cod_uf = int(UFS_PILOTO[uf])
    # Leitura sem decimal=',' pois as colunas de renda sao object (strings com virgula)
    df = pd.read_csv(renda_path, sep=";", encoding="latin-1", dtype=str,
                     low_memory=False)

    # CD_SETOR: converter string '1,10E+14' → float → int64 → UF prefix
    # Substituir virgula decimal antes de converter
    cd_setor_str = df["CD_SETOR"].str.replace(",", ".", regex=False)
    cd_setor_float = pd.to_numeric(cd_setor_str, errors="coerce")
    df["cd_uf_approx"] = (cd_setor_float // 10 ** 13).astype("Int64")
    df_uf = df[df["cd_uf_approx"] == cod_uf].copy()

    # V06004 = rendimento medio mensal do responsavel (media por domicilio).
    # Usado diretamente como proxy de renda_per_capita_setor (R$/mes).
    # V06005 descartado: seus valores sao anomalamente grandes e inconsistentes
    # com V06004 x V06001, possivelmente refletindo renda anualizada ou outra metrica.
    renda_col = None
    for cand in ("V06004", "v06004", "V06005", "v06005", "V003", "v003"):
        if cand in df_uf.columns:
            renda_col = cand
            break
    if renda_col is None:
        raise ValueError(
            f"Coluna de renda nao encontrada no arquivo renda nacional. "
            f"Colunas disponíveis: {list(df_uf.columns)}"
        )

    # Valores com ',' decimal (ex: '2453,03') — substituir antes de converter
    renda_str = df_uf[renda_col].str.replace(",", ".", regex=False)
    # V06004 e rendimento medio (per responsible) — usado como renda_per_capita proxy
    df_uf["renda_per_capita_setor_2022"] = pd.to_numeric(renda_str, errors="coerce")
    # renda_total: V06001 (domicilios com renda) × V06004 = total income dos responsaveis
    if "V06001" in df_uf.columns:
        v06001_str = df_uf["V06001"].str.replace(",", ".", regex=False)
        v06001 = pd.to_numeric(v06001_str, errors="coerce")
        df_uf["renda_total_setor_2022"] = df_uf["renda_per_capita_setor_2022"] * v06001
    else:
        df_uf["renda_total_setor_2022"] = np.nan

    n_antes = len(df_uf)
    df_uf = df_uf[df_uf["renda_per_capita_setor_2022"].notna()].copy()
    df_uf = df_uf.reset_index(drop=True)
    log.info("renda_nacional_uf_lida", uf=uf, total=len(df_uf),
             col_renda=renda_col, suprimidos_x=n_antes - len(df_uf))
    return df_uf[["renda_per_capita_setor_2022", "renda_total_setor_2022"]]


def ler_renda_nacional_uf_preservando_suprimidos(
    renda_path: Path, uf: str
) -> pd.DataFrame:
    """Le renda nacional preservando linhas suprimidas como NaN.

    Esta funcao existe para manter a reprodutibilidade do join posicional
    entre Basico e Renda dentro da UF: valores 'X' em V06004 continuam na
    serie como NaN, em vez de deslocar todas as linhas subsequentes.
    """
    cod_uf = int(UFS_PILOTO[uf])
    df = pd.read_csv(
        renda_path,
        sep=";",
        encoding="latin-1",
        dtype=str,
        low_memory=False,
    )

    cd_setor_str = df["CD_SETOR"].str.replace(",", ".", regex=False)
    cd_setor_float = pd.to_numeric(cd_setor_str, errors="coerce")
    df["cd_uf_approx"] = (cd_setor_float // 10 ** 13).astype("Int64")
    df_uf = df[df["cd_uf_approx"] == cod_uf].copy()

    renda_col = None
    for cand in ("V06004", "v06004", "V06005", "v06005", "V003", "v003"):
        if cand in df_uf.columns:
            renda_col = cand
            break
    if renda_col is None:
        raise ValueError(
            f"Coluna de renda nao encontrada no arquivo renda nacional. "
            f"Colunas disponiveis: {list(df_uf.columns)}"
        )

    renda_str = df_uf[renda_col].str.replace(",", ".", regex=False)
    df_uf["renda_per_capita_setor_2022"] = pd.to_numeric(renda_str, errors="coerce")

    if "V06001" in df_uf.columns:
        v06001_str = df_uf["V06001"].str.replace(",", ".", regex=False)
        v06001 = pd.to_numeric(v06001_str, errors="coerce")
        df_uf["renda_total_setor_2022"] = (
            df_uf["renda_per_capita_setor_2022"] * v06001
        )
    else:
        df_uf["renda_total_setor_2022"] = np.nan

    df_uf = df_uf.reset_index(drop=True)
    n_validos = int(df_uf["renda_per_capita_setor_2022"].notna().sum())
    log.info(
        "renda_nacional_uf_lida_preservando_suprimidos",
        uf=uf,
        total_linhas=len(df_uf),
        validos=n_validos,
        suprimidos_x=len(df_uf) - n_validos,
        col_renda=renda_col,
    )
    return df_uf[["renda_per_capita_setor_2022", "renda_total_setor_2022"]]


def montar_gdf_setores_nacional(
    gdf_malha: gpd.GeoDataFrame,
    df_basico: pd.DataFrame,
    df_renda: pd.DataFrame,
    uf: str,
) -> gpd.GeoDataFrame:
    """Monta GeoDataFrame de setores por join posicional (malha x basico x renda).

    - malha (shapefile) e basico tem EXATAMENTE o mesmo numero de linhas por UF
      e estao na mesma ordem de sector code → join por posicao e exato.
    - renda pode ter ate ~3% de linhas a menos; linhas excedentes em basico
      ficam com renda NaN e sao marcadas como fallback.
    """
    n_malha = len(gdf_malha)
    n_basico = len(df_basico)
    n_renda = len(df_renda)

    if n_malha != n_basico:
        raise ValueError(
            f"UF {uf}: malha ({n_malha} linhas) e basico ({n_basico} linhas) "
            f"nao tem o mesmo numero de setores. Verifique os arquivos."
        )

    log.info(
        "join_posicional",
        uf=uf,
        n_malha=n_malha,
        n_basico=n_basico,
        n_renda=n_renda,
        renda_validos=int(df_renda["renda_per_capita_setor_2022"].notna().sum()),
        delta_renda=n_basico - n_renda,
    )

    # Join posicional malha x basico (exato)
    gdf = gdf_malha.copy()
    gdf["pop_total_setor_2022"] = df_basico["pop_total_setor_2022"].values
    gdf["avg_household_size"] = df_basico["avg_household_size"].values

    # Join posicional basico x renda (aproximado — renda pode ter menos linhas)
    # V06004 = rendimento medio mensal do responsavel (per household head).
    # Para tornar comparavel ao M1 renda_per_capita (per capita domiciliar),
    # dividimos pelo tamanho medio do domicilio (v0005 do basico).
    renda_pc_v06004 = df_renda["renda_per_capita_setor_2022"].values
    renda_pc_padded_v06004 = np.full(n_malha, np.nan)
    renda_pc_padded_v06004[:len(renda_pc_v06004)] = renda_pc_v06004
    # Ajuste: V06004 / avg_household_size → proxy de renda per capita domiciliar
    gdf["renda_per_capita_setor_2022"] = np.where(
        (gdf["avg_household_size"] > 0) & ~np.isnan(renda_pc_padded_v06004),
        renda_pc_padded_v06004 / gdf["avg_household_size"],
        np.nan,
    )

    renda_tot_vals = df_renda["renda_total_setor_2022"].values
    renda_tot_padded = np.full(n_malha, np.nan)
    renda_tot_padded[:len(renda_tot_vals)] = renda_tot_vals
    gdf["renda_total_setor_2022"] = renda_tot_padded

    # Area do setor (em graus^2, consistente com hexagonos)
    gdf["area_setor"] = gdf.geometry.area
    gdf = gdf[gdf["area_setor"] > 0].copy()

    return gdf.reset_index(drop=True)


def executar_fase_a_nacional(
    *,
    ufs: list[str] | None = None,
    basico_path: Path = NACIONAL_BASICO_PATH,
    renda_path: Path = NACIONAL_RENDA_PATH,
    shp_path: Path = NACIONAL_SHAPEFILE_PATH,
    hex_root: Path = DEFAULT_HEX_ROOT,
    base_oficial_path: Path = DEFAULT_BASE_OFICIAL_PATH,
    staging_dir: Path = DEFAULT_STAGING_DIR,
    report_path: Path = DEFAULT_REPORT_PATH,
    data_download: str = DATA_DOWNLOAD_DEFAULT,
) -> dict:
    """Executa pipeline Fase A usando arquivos nacionais do Censo 2022.

    Alternativa a `executar_fase_a` para o caso em que os dados estao nos
    arquivos nacionais (nao segmentados por UF) em `data/raw/CENSO 2022/`.
    """
    if ufs is None:
        ufs = list(UFS_PILOTO.keys())

    for p in (basico_path, renda_path, shp_path):
        if not p.exists():
            raise FileNotFoundError(
                f"Arquivo nacional nao encontrado: {p}\n"
                f"Baixe os dados do IBGE Censo 2022 e coloque em {NACIONAL_RAW_DIR}."
            )

    log.info("fase_a_nacional_inicio", ufs=ufs)

    # Carregar base oficial para ancoragem de percentis
    base_oficial = pd.read_parquet(base_oficial_path)
    log.info("base_oficial_carregada", total=len(base_oficial))

    all_results = []
    validacoes = []
    info_processamento: dict[str, Any] = {"por_uf": {}}

    for uf in ufs:
        log.info("processando_uf_nacional", uf=uf)

        # Passo 1: Ler arquivos nacionais filtrados por UF
        gdf_malha = ler_malha_nacional_uf(shp_path, uf)
        df_basico = ler_basico_nacional_uf(basico_path, uf)
        df_renda = ler_renda_nacional_uf_preservando_suprimidos(renda_path, uf)
        renda_validos = int(df_renda["renda_per_capita_setor_2022"].notna().sum())

        info_processamento["por_uf"][uf] = {
            "setores_basico": len(df_basico),
            "setores_renda": len(df_renda),
            "setores_renda_validos": renda_validos,
            "setores_join": len(gdf_malha),
            "descartados_pop": 0,
            "descartados_renda": len(df_renda) - renda_validos,
            "join_mismatch_pct": round(abs(len(df_basico) - len(df_renda)) / max(len(df_basico), 1) * 100, 2),
        }

        # Passo 2: Montar GeoDataFrame de setores por join posicional
        gdf_setores = montar_gdf_setores_nacional(gdf_malha, df_basico, df_renda, uf)
        # Filtrar setores sem populacao (pop_total=0 ou NaN) para o spatial join
        gdf_setores_validos = gdf_setores[
            gdf_setores["pop_total_setor_2022"].fillna(0) > 0
        ].copy()
        log.info("setores_validos_para_join", uf=uf, total=len(gdf_setores_validos))

        # Passo 3: Carregar hexagonos e spatial join
        df_hex = carregar_hexagonos_uf(hex_root, uf)
        t0 = time.perf_counter()
        df_result = spatial_join_area_weighted(df_hex, gdf_setores_validos)
        tempo_join = round(time.perf_counter() - t0, 2)
        log.info("spatial_join_completo", uf=uf, tempo_s=tempo_join,
                 total_hex=len(df_result))

        # Passo 4: Fallback
        df_result = aplicar_fallback(df_result)

        # Passo 5: Score experimental
        df_result = calcular_score_setor_2022(df_result, base_nacional=base_oficial)

        # Rastreabilidade
        df_result = adicionar_rastreabilidade(df_result, data_download)
        if "uf" not in df_result.columns:
            df_result["uf"] = uf

        # Validacao
        validacao = validar_uf(df_result, uf)
        validacao["tempo_spatial_join_s"] = tempo_join
        validacoes.append(validacao)
        log.info("validacao_uf", **validacao)

        all_results.append(df_result)

    # Consolidar
    df_consolidado = pd.concat(all_results, ignore_index=True)
    df_consolidado = df_consolidado.reset_index(drop=True)

    # Salvar parquet
    staging_dir.mkdir(parents=True, exist_ok=True)
    output_path = staging_dir / OUTPUT_PARQUET
    colunas_salvar = [
        "hex_id", "lat", "lng", "uf", "regiao",
        "pop_total_setor_2022", "renda_per_capita_setor_2022",
        "renda_total_setor_2022", "domicilios_setor_2022",
        "n_setores_contribuintes", "coverage_pct_setor_2022",
        "fallback_setor_2022", "motivo_fallback_setor_2022",
        "renda_pct_setor", "pop_pct_setor",
        "score_setor_2022_exp", "percentil_escopo",
        "fonte_populacao_setor",
        "fonte_setor_2022", "data_referencia_setor_2022",
        "metodo_agregacao_setor_2022", "qualidade_setor_2022",
    ]
    colunas_existentes = [c for c in colunas_salvar if c in df_consolidado.columns]
    df_consolidado[colunas_existentes].to_parquet(output_path, index=False)
    log.info("parquet_salvo", path=str(output_path), linhas=len(df_consolidado))

    # Relatorio
    report_path.parent.mkdir(parents=True, exist_ok=True)
    relatorio = gerar_relatorio(validacoes, info_processamento, df_consolidado)
    report_path.write_text(relatorio, encoding="utf-8")
    log.info("relatorio_salvo", path=str(report_path))

    metadata = {
        "data_execucao": date.today().isoformat(),
        "ufs_processadas": ufs,
        "total_hexagonos": len(df_consolidado),
        "validacoes": validacoes,
        "output_parquet": str(output_path),
        "report_path": str(report_path),
        "all_go": all(v["status"] == "GO" for v in validacoes),
        "modo": "nacional",
    }
    meta_path = staging_dir / "censo2022_setores_h3_res7_metadata.json"
    meta_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    return metadata


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fase A — Ingestao do Censo 2022 por Setor Censitario (Piloto GO + SP + RJ)."
    )
    parser.add_argument(
        "--uf", action="append", default=[],
        help="UF a processar (GO, SP, RJ). Repetir para varias. Default: todas as piloto.",
    )
    parser.add_argument(
        "--raw-dir", default=str(DEFAULT_RAW_DIR),
        help="Diretorio com dados brutos do Censo 2022.",
    )
    parser.add_argument(
        "--hex-root", default=str(DEFAULT_HEX_ROOT),
        help="Raiz dos hexagonos H3-r7 por UF.",
    )
    parser.add_argument(
        "--base-oficial-path", default=str(DEFAULT_BASE_OFICIAL_PATH),
        help="Parquet oficial brasil_estrutural.parquet.",
    )
    parser.add_argument(
        "--staging-dir", default=str(DEFAULT_STAGING_DIR),
        help="Diretorio de staging para output.",
    )
    parser.add_argument(
        "--report-path", default=str(DEFAULT_REPORT_PATH),
        help="Caminho do relatorio Markdown.",
    )
    parser.add_argument(
        "--data-download", default=DATA_DOWNLOAD_DEFAULT,
        help="Data de download dos dados (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--nacional", action="store_true",
        help="Usar arquivos nacionais do Censo 2022 em data/raw/CENSO 2022/.",
    )
    parser.add_argument(
        "--basico-path", default=str(NACIONAL_BASICO_PATH),
        help="Caminho do CSV Basico nacional (modo --nacional).",
    )
    parser.add_argument(
        "--renda-path", default=str(NACIONAL_RENDA_PATH),
        help="Caminho do CSV Renda nacional (modo --nacional).",
    )
    parser.add_argument(
        "--shp-path", default=str(NACIONAL_SHAPEFILE_PATH),
        help="Caminho do shapefile nacional (modo --nacional).",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    ufs = [u.upper() for u in args.uf] if args.uf else None
    if ufs:
        for uf in ufs:
            if uf not in UFS_PILOTO:
                parser.error(f"UF {uf} nao e piloto. Validas: {list(UFS_PILOTO.keys())}")

    if args.nacional:
        resultado = executar_fase_a_nacional(
            ufs=ufs,
            basico_path=Path(args.basico_path),
            renda_path=Path(args.renda_path),
            shp_path=Path(args.shp_path),
            hex_root=Path(args.hex_root),
            base_oficial_path=Path(args.base_oficial_path),
            staging_dir=Path(args.staging_dir),
            report_path=Path(args.report_path),
            data_download=args.data_download,
        )
    else:
        resultado = executar_fase_a(
            ufs=ufs,
            raw_dir=Path(args.raw_dir),
            hex_root=Path(args.hex_root),
            base_oficial_path=Path(args.base_oficial_path),
            staging_dir=Path(args.staging_dir),
            report_path=Path(args.report_path),
            data_download=args.data_download,
        )

    if resultado["all_go"]:
        print("FASE A: GO — Todas as UFs piloto passaram.")
    else:
        falhas = [v["uf"] for v in resultado["validacoes"] if v["status"] != "GO"]
        print(f"FASE A: NO-GO — UFs com falha: {', '.join(falhas)}")


if __name__ == "__main__":
    main()
