"""Validacao e consolidacao da Fase A do Censo 2022 por setor censitario."""

from __future__ import annotations

import argparse
import json
import threading
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
import psutil

try:
    from jobs.pipelines.fase_a_censo2022_setores import (
        DEFAULT_BASE_OFICIAL_PATH,
        DEFAULT_HEX_ROOT,
        NACIONAL_BASICO_PATH,
        NACIONAL_RENDA_PATH,
        NACIONAL_SHAPEFILE_PATH,
        carregar_hexagonos_uf,
        ler_basico_nacional_uf,
        ler_malha_nacional_uf,
        ler_renda_nacional_uf_preservando_suprimidos,
        montar_gdf_setores_nacional,
        spatial_join_area_weighted,
    )
except ModuleNotFoundError:
    from fase_a_censo2022_setores import (
        DEFAULT_BASE_OFICIAL_PATH,
        DEFAULT_HEX_ROOT,
        NACIONAL_BASICO_PATH,
        NACIONAL_RENDA_PATH,
        NACIONAL_SHAPEFILE_PATH,
        carregar_hexagonos_uf,
        ler_basico_nacional_uf,
        ler_malha_nacional_uf,
        ler_renda_nacional_uf_preservando_suprimidos,
        montar_gdf_setores_nacional,
        spatial_join_area_weighted,
    )


UFS_BRASIL = {
    "RO": "11",
    "AC": "12",
    "AM": "13",
    "RR": "14",
    "PA": "15",
    "AP": "16",
    "TO": "17",
    "MA": "21",
    "PI": "22",
    "CE": "23",
    "RN": "24",
    "PB": "25",
    "PE": "26",
    "AL": "27",
    "SE": "28",
    "BA": "29",
    "MG": "31",
    "ES": "32",
    "RJ": "33",
    "SP": "35",
    "PR": "41",
    "SC": "42",
    "RS": "43",
    "MS": "50",
    "MT": "51",
    "GO": "52",
    "DF": "53",
}

TARGET_CITIES = {
    "GO": {"cod_municipio": "5208707", "nome": "Goiania"},
    "SP": {"cod_municipio": "3550308", "nome": "Sao Paulo"},
    "RJ": {"cod_municipio": "3304557", "nome": "Rio de Janeiro"},
}

DEFAULT_CENSO_PATH = Path("data/staging/censo2022_setores_h3_res7.parquet")
DEFAULT_OUTPUT_PATH = Path("data/staging/censo2022_setores_validado.parquet")
DEFAULT_REPORT_PATH = Path("data/reports/fase_a_censo2022_validacao.md")
DEFAULT_METADATA_PATH = Path("data/staging/censo2022_setores_validado_metadata.json")


@dataclass
class ProfileSample:
    uf: str
    hex_count: int
    setor_count: int
    time_s: float
    peak_rss_mb: float


def _markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(str(v) for v in row) + " |" for row in rows]
    return "\n".join([header, sep] + body)


def _stats(series: pd.Series) -> dict[str, float]:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return {
            "count": 0,
            "mean": np.nan,
            "median": np.nan,
            "std": np.nan,
            "skew": np.nan,
            "p05": np.nan,
            "p95": np.nan,
            "p99": np.nan,
            "p95_p05": np.nan,
            "outlier_3iqr_pct": np.nan,
            "zeros_pct": np.nan,
        }
    q1 = float(s.quantile(0.25))
    q3 = float(s.quantile(0.75))
    iqr = q3 - q1
    outlier_pct = float(((s < (q1 - 3 * iqr)) | (s > (q3 + 3 * iqr))).mean() * 100)
    zeros_pct = float((s <= 0).mean() * 100)
    return {
        "count": int(s.size),
        "mean": float(s.mean()),
        "median": float(s.median()),
        "std": float(s.std(ddof=0)),
        "skew": float(s.skew()),
        "p05": float(s.quantile(0.05)),
        "p95": float(s.quantile(0.95)),
        "p99": float(s.quantile(0.99)),
        "p95_p05": float(s.quantile(0.95) - s.quantile(0.05)),
        "outlier_3iqr_pct": outlier_pct,
        "zeros_pct": zeros_pct,
    }


def _safe_corr(a: pd.Series, b: pd.Series) -> float:
    aa = pd.to_numeric(a, errors="coerce")
    bb = pd.to_numeric(b, errors="coerce")
    if aa.nunique(dropna=True) <= 1 or bb.nunique(dropna=True) <= 1:
        return np.nan
    return float(aa.corr(bb))


def _weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    mask = values.notna() & weights.notna()
    if not mask.any():
        return np.nan
    return float(np.average(values.loc[mask], weights=weights.loc[mask]))


def carregar_fontes_minimas(
    basico_path: Path,
    renda_path: Path,
    shp_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    basico = pd.read_csv(
        basico_path,
        sep=";",
        encoding="latin-1",
        usecols=["CD_UF", "CD_MUN", "v0002", "v0005"],
        dtype=str,
        low_memory=False,
    )
    renda = pd.read_csv(
        renda_path,
        sep=";",
        encoding="latin-1",
        usecols=["CD_SETOR", "V06004"],
        dtype=str,
        low_memory=False,
    )
    renda["cd_uf_approx"] = (
        pd.to_numeric(
            renda["CD_SETOR"].str.replace(",", ".", regex=False),
            errors="coerce",
        )
        // 10**13
    ).astype("Int64")
    renda["V06004_num"] = pd.to_numeric(
        renda["V06004"].str.replace(",", ".", regex=False),
        errors="coerce",
    )

    shp = gpd.read_file(shp_path, columns=["CD_SETOR", "CD_UF", "CD_MUN"])
    shp["CD_UF"] = shp["CD_UF"].astype(str).str.zfill(2)
    shp["CD_SETOR"] = shp["CD_SETOR"].astype(str).str.zfill(15)
    return basico, renda, pd.DataFrame(shp)


def auditar_join_posicional(
    basico: pd.DataFrame,
    renda: pd.DataFrame,
    shp: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for uf, code in UFS_BRASIL.items():
        basico_uf = basico[basico["CD_UF"] == code].reset_index(drop=True)
        renda_uf = renda[renda["cd_uf_approx"] == int(code)].reset_index(drop=True)
        shp_uf = (
            shp[shp["CD_UF"] == code]
            .sort_values("CD_SETOR")
            .reset_index(drop=True)
        )

        mismatch_basico_vs_shp = (
            abs(len(basico_uf) - len(shp_uf)) / max(len(shp_uf), 1) * 100
        )
        mismatch_renda_total = (
            abs(len(basico_uf) - len(renda_uf)) / max(len(basico_uf), 1) * 100
        )
        renda_validos = int(renda_uf["V06004_num"].notna().sum())
        mismatch_renda_validos = (
            abs(len(basico_uf) - renda_validos) / max(len(basico_uf), 1) * 100
        )
        mun_seq_match_pct = np.nan
        if len(basico_uf) == len(shp_uf):
            mun_seq_match_pct = float(
                (
                    basico_uf["CD_MUN"].astype(str).to_numpy()
                    == shp_uf["CD_MUN"].astype(str).to_numpy()
                ).mean()
                * 100
            )

        join_consistente = (
            mismatch_basico_vs_shp == 0.0
            and mismatch_renda_total <= 5.0
            and mun_seq_match_pct >= 99.9
        )
        rows.append(
            {
                "uf": uf,
                "setores_shapefile": int(len(shp_uf)),
                "setores_basico": int(len(basico_uf)),
                "setores_renda_total": int(len(renda_uf)),
                "setores_renda_validos": renda_validos,
                "mismatch_basico_vs_shapefile_pct": round(mismatch_basico_vs_shp, 4),
                "mismatch_renda_total_pct": round(mismatch_renda_total, 4),
                "mismatch_renda_validos_pct": round(mismatch_renda_validos, 4),
                "renda_suprimida_pct": round(
                    (len(renda_uf) - renda_validos) / max(len(basico_uf), 1) * 100,
                    4,
                ),
                "mun_seq_match_pct": round(mun_seq_match_pct, 4),
                "alerta_join_gt_5pct": bool(mismatch_renda_total > 5.0),
                "join_consistente": bool(join_consistente),
            }
        )
    return pd.DataFrame(rows).sort_values("uf").reset_index(drop=True)


def construir_setores_proxy_uf(
    basico: pd.DataFrame,
    renda: pd.DataFrame,
    uf: str,
) -> pd.DataFrame:
    code = UFS_BRASIL[uf]
    basico_uf = basico[basico["CD_UF"] == code].reset_index(drop=True)
    renda_uf = renda[renda["cd_uf_approx"] == int(code)].reset_index(drop=True)

    n = len(basico_uf)
    renda_vals = np.full(n, np.nan)
    renda_vals[: len(renda_uf)] = renda_uf["V06004_num"].to_numpy()

    pop = pd.to_numeric(basico_uf["v0002"], errors="coerce")
    hh_size = pd.to_numeric(
        basico_uf["v0005"].str.replace(",", ".", regex=False),
        errors="coerce",
    ).clip(lower=1.0, upper=15.0)

    setor = pd.DataFrame(
        {
            "uf": uf,
            "cod_municipio": basico_uf["CD_MUN"].astype(str),
            "pop_total_setor_2022": pop,
            "avg_household_size": hh_size,
            "V06004": renda_vals,
        }
    )
    setor["renda_per_capita_setor_2022"] = setor["V06004"] / setor["avg_household_size"]
    return setor[setor["pop_total_setor_2022"].fillna(0) > 0].reset_index(drop=True)


def auditar_renda_proxy(
    basico: pd.DataFrame,
    renda: pd.DataFrame,
    base_oficial: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    ref = base_oficial.drop_duplicates(["uf", "cod_municipio"])[
        ["uf", "cod_municipio", "nome_municipio", "renda_per_capita"]
    ]

    uf_rows: list[dict[str, object]] = []
    city_rows: list[dict[str, object]] = []

    for uf, meta in TARGET_CITIES.items():
        setor = construir_setores_proxy_uf(basico, renda, uf)

        agg_rows = []
        for cod_municipio, group in setor.groupby("cod_municipio", sort=False):
            agg_rows.append(
                {
                    "cod_municipio": cod_municipio,
                    "renda_pc_proxy_mun": _weighted_mean(
                        group["renda_per_capita_setor_2022"],
                        group["pop_total_setor_2022"],
                    ),
                    "v06004_mun": _weighted_mean(
                        group["V06004"],
                        group["pop_total_setor_2022"],
                    ),
                    "coverage_valid_renda_pct": float(
                        group["renda_per_capita_setor_2022"].notna().mean() * 100
                    ),
                }
            )
        agg = pd.DataFrame(agg_rows)
        merged = agg.merge(ref[ref["uf"] == uf], on="cod_municipio", how="inner")
        merged = merged.dropna(subset=["renda_pc_proxy_mun", "renda_per_capita"])

        corr_proxy = _safe_corr(merged["renda_pc_proxy_mun"], merged["renda_per_capita"])
        corr_raw = _safe_corr(merged["v06004_mun"], merged["renda_per_capita"])
        mae_proxy = float(
            (merged["renda_pc_proxy_mun"] - merged["renda_per_capita"]).abs().mean()
        )
        mae_raw = float(
            (merged["v06004_mun"] - merged["renda_per_capita"]).abs().mean()
        )
        ratio_proxy = float(
            (merged["renda_pc_proxy_mun"] / merged["renda_per_capita"]).median()
        )
        ratio_raw = float((merged["v06004_mun"] / merged["renda_per_capita"]).median())

        uf_rows.append(
            {
                "uf": uf,
                "municipios_comp": int(len(merged)),
                "corr_proxy_vs_m1": round(corr_proxy, 4),
                "corr_v06004_vs_m1": round(corr_raw, 4),
                "mae_proxy_vs_m1": round(mae_proxy, 2),
                "mae_v06004_vs_m1": round(mae_raw, 2),
                "median_ratio_proxy_vs_m1": round(ratio_proxy, 4),
                "median_ratio_v06004_vs_m1": round(ratio_raw, 4),
                "coverage_valid_renda_avg_pct": round(
                    float(merged["coverage_valid_renda_pct"].mean()),
                    2,
                ),
                "transformacao_v0005_melhor_que_bruta": bool(
                    mae_proxy < mae_raw
                    and abs(1 - ratio_proxy) < abs(1 - ratio_raw)
                ),
            }
        )

        city = merged[merged["cod_municipio"] == meta["cod_municipio"]]
        if not city.empty:
            city_rows.append(
                {
                    "uf": uf,
                    "cidade": meta["nome"],
                    "cod_municipio": meta["cod_municipio"],
                    "renda_pc_proxy_mun": round(
                        float(city["renda_pc_proxy_mun"].iloc[0]),
                        2,
                    ),
                    "v06004_mun": round(float(city["v06004_mun"].iloc[0]), 2),
                    "renda_per_capita_m1": round(
                        float(city["renda_per_capita"].iloc[0]),
                        2,
                    ),
                    "coverage_valid_renda_pct": round(
                        float(city["coverage_valid_renda_pct"].iloc[0]),
                        2,
                    ),
                }
            )

    return (
        pd.DataFrame(uf_rows).sort_values("uf").reset_index(drop=True),
        pd.DataFrame(city_rows).sort_values("uf").reset_index(drop=True),
    )


def construir_base_validada(
    censo_path: Path,
    base_oficial_path: Path,
) -> pd.DataFrame:
    censo = pd.read_parquet(censo_path)
    base = pd.read_parquet(
        base_oficial_path,
        columns=[
            "hex_id",
            "uf",
            "cod_municipio",
            "nome_municipio",
            "renda_per_capita",
            "hex_score_estrutural",
            "score_priorizacao",
        ],
    )
    validado = censo.merge(base, on=["hex_id", "uf"], how="left")
    validado["metodo_join_setor_2022"] = "posicional_uf_preservando_suprimidos"
    validado["transformacao_renda_setor_2022"] = "V06004_div_v0005"
    validado["data_validacao_fase_a"] = date.today().isoformat()
    return validado


def auditar_distribuicao_renda(validado: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for uf in TARGET_CITIES:
        setor_stats = _stats(validado.loc[validado["uf"] == uf, "renda_per_capita_setor_2022"])
        m1_stats = _stats(validado.loc[validado["uf"] == uf, "renda_per_capita"])
        rows.append(
            {
                "uf": uf,
                "setor_mean": round(setor_stats["mean"], 2),
                "setor_median": round(setor_stats["median"], 2),
                "setor_std": round(setor_stats["std"], 2),
                "setor_skew": round(setor_stats["skew"], 2),
                "setor_p95_p05": round(setor_stats["p95_p05"], 2),
                "setor_outlier_3iqr_pct": round(setor_stats["outlier_3iqr_pct"], 2),
                "setor_zeros_pct": round(setor_stats["zeros_pct"], 2),
                "m1_mean": round(m1_stats["mean"], 2),
                "m1_median": round(m1_stats["median"], 2),
                "m1_std": round(m1_stats["std"], 2),
                "m1_skew": round(m1_stats["skew"], 2),
                "m1_p95_p05": round(m1_stats["p95_p05"], 2),
                "distribuicao_coerente": bool(
                    setor_stats["skew"] <= 5.0
                    and setor_stats["outlier_3iqr_pct"] <= 5.0
                    and setor_stats["zeros_pct"] <= 10.0
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("uf").reset_index(drop=True)


def medir_intraurbano(validado: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for uf, meta in TARGET_CITIES.items():
        city = validado[
            (validado["uf"] == uf)
            & (validado["cod_municipio"].astype(str) == meta["cod_municipio"])
        ].copy()
        municipal_score = pd.to_numeric(city["score_priorizacao"], errors="coerce")
        setor_score = pd.to_numeric(city["score_setor_2022_exp"], errors="coerce")
        municipal_stats = _stats(municipal_score)
        setor_stats = _stats(setor_score)
        corr = _safe_corr(municipal_score, setor_score)
        rows.append(
            {
                "uf": uf,
                "cidade": meta["nome"],
                "hex_cidade": int(len(city)),
                "municipal_std": round(municipal_stats["std"], 2),
                "setor_std": round(setor_stats["std"], 2),
                "ganho_std": round(setor_stats["std"] - municipal_stats["std"], 2),
                "municipal_p95_p05": round(municipal_stats["p95_p05"], 2),
                "setor_p95_p05": round(setor_stats["p95_p05"], 2),
                "ganho_amplitude": round(
                    setor_stats["p95_p05"] - municipal_stats["p95_p05"],
                    2,
                ),
                "correlacao_modelos": (
                    round(corr, 4) if pd.notna(corr) else "NA_baseline_uniforme"
                ),
                "ganho_intraurbano_confirmado": bool(setor_stats["p95_p05"] > 50.0),
            }
        )
    return pd.DataFrame(rows).sort_values("uf").reset_index(drop=True)


def detectar_outliers_espaciais(
    df_city: pd.DataFrame,
    *,
    score_col: str = "score_setor_2022_exp",
    min_neighbors: int = 5,
    absolute_floor: float = 35.0,
    quantile_cut: float = 0.995,
    mad_multiplier: float = 4.0,
) -> dict[str, object]:
    score_map = dict(
        zip(
            df_city["hex_id"],
            pd.to_numeric(df_city[score_col], errors="coerce"),
            strict=False,
        )
    )

    stats = []
    for hex_id, score in score_map.items():
        if pd.isna(score):
            continue
        neighbors = [
            n
            for n in h3.grid_disk(hex_id, 1)
            if n != hex_id and n in score_map and pd.notna(score_map[n])
        ]
        if len(neighbors) < min_neighbors:
            continue
        neigh_scores = np.array([score_map[n] for n in neighbors], dtype=float)
        neigh_median = float(np.median(neigh_scores))
        delta = float(score - neigh_median)
        similar_neighbors = int(np.sum(np.abs(neigh_scores - score) <= 10))
        stats.append(
            {
                "hex_id": hex_id,
                "score": float(score),
                "neighbor_median": neigh_median,
                "delta": delta,
                "neighbors": int(len(neighbors)),
                "similar_neighbors": similar_neighbors,
            }
        )

    if not stats:
        return {
            "avaliados": 0,
            "threshold": absolute_floor,
            "critical_outliers": 0,
            "critical_examples": [],
        }

    delta_abs = np.abs(np.array([row["delta"] for row in stats], dtype=float))
    median_abs = float(np.median(delta_abs))
    mad_abs = float(np.median(np.abs(delta_abs - median_abs)))
    threshold = max(
        absolute_floor,
        float(np.quantile(delta_abs, quantile_cut)),
        median_abs + mad_multiplier * mad_abs,
    )

    critical = [
        row
        for row in stats
        if abs(row["delta"]) > threshold and row["similar_neighbors"] <= 1
    ]
    return {
        "avaliados": int(len(stats)),
        "threshold": round(threshold, 2),
        "critical_outliers": int(len(critical)),
        "critical_examples": critical[:5],
    }


def auditar_continuidade_espacial(validado: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for uf, meta in TARGET_CITIES.items():
        city = validado[
            (validado["uf"] == uf)
            & (validado["cod_municipio"].astype(str) == meta["cod_municipio"])
        ].copy()
        result = detectar_outliers_espaciais(city)
        rows.append(
            {
                "uf": uf,
                "cidade": meta["nome"],
                "hex_avaliados": result["avaliados"],
                "threshold_delta": result["threshold"],
                "critical_outliers": result["critical_outliers"],
                "spatial_status": "GO" if result["critical_outliers"] == 0 else "REVIEW",
                "critical_examples": result["critical_examples"],
            }
        )
    return pd.DataFrame(rows).sort_values("uf").reset_index(drop=True)


def perfilar_spatial_join_piloto(
    *,
    hex_root: Path,
    basico_path: Path,
    renda_path: Path,
    shp_path: Path,
) -> pd.DataFrame:
    process = psutil.Process()
    rows: list[ProfileSample] = []

    for uf in TARGET_CITIES:
        gdf_malha = ler_malha_nacional_uf(shp_path, uf)
        df_basico = ler_basico_nacional_uf(basico_path, uf)
        df_renda = ler_renda_nacional_uf_preservando_suprimidos(renda_path, uf)
        gdf_setores = montar_gdf_setores_nacional(gdf_malha, df_basico, df_renda, uf)
        gdf_setores = gdf_setores[gdf_setores["pop_total_setor_2022"].fillna(0) > 0].copy()
        df_hex = carregar_hexagonos_uf(hex_root, uf)

        stop_flag = False
        peak_rss_mb = process.memory_info().rss / (1024**2)

        def _sampler() -> None:
            nonlocal peak_rss_mb, stop_flag
            while not stop_flag:  # noqa: B023 - closure usa `nonlocal` p/ escrever de volta; thread criada/join na mesma iteracao (default-arg quebraria o write-back)
                peak_rss_mb = max(
                    peak_rss_mb,
                    process.memory_info().rss / (1024**2),
                )
                time.sleep(0.05)

        thread = threading.Thread(target=_sampler, daemon=True)
        thread.start()
        t0 = time.perf_counter()
        _ = spatial_join_area_weighted(df_hex, gdf_setores)
        elapsed = time.perf_counter() - t0
        stop_flag = True
        thread.join(timeout=1.0)

        rows.append(
            ProfileSample(
                uf=uf,
                hex_count=int(len(df_hex)),
                setor_count=int(len(gdf_setores)),
                time_s=round(elapsed, 2),
                peak_rss_mb=round(float(peak_rss_mb), 2),
            )
        )

    return pd.DataFrame([row.__dict__ for row in rows]).sort_values("uf").reset_index(drop=True)


def estimar_stress_test(
    base_oficial: pd.DataFrame,
    join_audit: pd.DataFrame,
    profiling: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, object]]:
    hex_por_uf = (
        base_oficial.groupby("uf")["hex_id"].size().rename("hex_count").reset_index()
    )
    setores_por_uf = join_audit[["uf", "setores_basico"]].rename(
        columns={"setores_basico": "setor_count"}
    )
    df = hex_por_uf.merge(setores_por_uf, on="uf", how="left")

    if profiling.empty:
        sec_per_hex = 0.0020
        peak_rss_ref = np.nan
        ref_hex = np.nan
    else:
        sec_per_hex = float(
            profiling["time_s"].sum() / max(profiling["hex_count"].sum(), 1)
        )
        peak_rss_ref = float(profiling["peak_rss_mb"].max())
        ref_hex = float(profiling["hex_count"].max())

    df["tempo_spatial_join_estimado_s"] = (
        df["hex_count"].astype(float) * sec_per_hex
    ).round(2)

    if pd.notna(peak_rss_ref) and pd.notna(ref_hex) and ref_hex > 0:
        df["peak_rss_estimado_mb"] = (
            peak_rss_ref * (df["hex_count"].astype(float) / ref_hex)
        ).round(2)
    else:
        df["peak_rss_estimado_mb"] = np.nan

    nacional_summary = {
        "tempo_nacional_estimado_min": round(
            float(df["tempo_spatial_join_estimado_s"].sum() / 60),
            2,
        ),
        "peak_rss_estimado_maior_uf_mb": (
            round(float(df["peak_rss_estimado_mb"].max()), 2)
            if df["peak_rss_estimado_mb"].notna().any()
            else None
        ),
        "maiores_gargalos_hex": df.nlargest(5, "hex_count")[
            ["uf", "hex_count"]
        ].to_dict(orient="records"),
        "maiores_gargalos_setor": df.nlargest(5, "setor_count")[
            ["uf", "setor_count"]
        ].to_dict(orient="records"),
        "ufs_join_alerta_gt_5pct": join_audit.loc[
            join_audit["alerta_join_gt_5pct"], "uf"
        ].tolist(),
        "observacao": (
            "Overlay geopandas/shapely e o principal gargalo; o pico de memoria "
            "fica concentrado na maior UF processada sequencialmente."
        ),
    }
    return df.sort_values("uf").reset_index(drop=True), nacional_summary


def aplicar_flags_validacao(
    validado: pd.DataFrame,
    join_audit: pd.DataFrame,
    renda_proxy: pd.DataFrame,
    renda_dist: pd.DataFrame,
    intraurbano: pd.DataFrame,
    spatial: pd.DataFrame,
) -> pd.DataFrame:
    df = validado.copy()
    join_flags = join_audit[["uf", "mismatch_renda_total_pct", "join_consistente"]].rename(
        columns={
            "mismatch_renda_total_pct": "join_mismatch_pct_uf",
            "join_consistente": "status_validacao_join_uf",
        }
    )
    mismatch = pd.to_numeric(join_flags["join_mismatch_pct_uf"], errors="coerce")
    join_flags["qualidade_join_uf"] = np.select(
        [mismatch < 2.0, mismatch <= 5.0],
        ["A", "B"],
        default="C",
    )
    join_flags.loc[mismatch.isna(), "qualidade_join_uf"] = pd.NA
    renda_flags = renda_proxy[
        ["uf", "corr_proxy_vs_m1", "transformacao_v0005_melhor_que_bruta"]
    ].rename(
        columns={
            "corr_proxy_vs_m1": "corr_renda_proxy_vs_m1_uf",
            "transformacao_v0005_melhor_que_bruta": "transformacao_renda_aprovada_uf",
        }
    )
    dist_flags = renda_dist[["uf", "distribuicao_coerente"]].rename(
        columns={"distribuicao_coerente": "status_distribuicao_renda_uf"}
    )
    intra_flags = intraurbano[["uf", "ganho_amplitude", "ganho_intraurbano_confirmado"]].rename(
        columns={
            "ganho_amplitude": "ganho_amplitude_intraurbano_uf",
            "ganho_intraurbano_confirmado": "status_intraurbano_uf",
        }
    )
    spatial_flags = spatial[["uf", "critical_outliers", "spatial_status"]].rename(
        columns={
            "critical_outliers": "critical_outliers_uf",
            "spatial_status": "status_espacial_uf",
        }
    )

    for extra in [join_flags, renda_flags, dist_flags, intra_flags, spatial_flags]:
        df = df.merge(extra, on="uf", how="left")

    df["status_validacao_join_uf"] = np.where(
        df["status_validacao_join_uf"].fillna(False),
        "GO",
        "REVIEW",
    )
    df["status_distribuicao_renda_uf"] = np.where(
        df["status_distribuicao_renda_uf"].fillna(False),
        "GO",
        "REVIEW",
    )
    df["status_intraurbano_uf"] = np.where(
        df["status_intraurbano_uf"].fillna(False),
        "GO",
        "REVIEW",
    )
    df["status_validacao_fase_a_uf"] = np.where(
        (df["status_validacao_join_uf"] == "GO")
        & (df["status_distribuicao_renda_uf"] == "GO")
        & (df["status_intraurbano_uf"] == "GO")
        & (df["status_espacial_uf"].isin(["GO", np.nan])),
        "GO",
        "REVIEW",
    )
    return df


def gerar_relatorio_validacao(
    *,
    join_audit: pd.DataFrame,
    renda_proxy: pd.DataFrame,
    renda_cidades: pd.DataFrame,
    renda_dist: pd.DataFrame,
    intraurbano: pd.DataFrame,
    spatial: pd.DataFrame,
    profiling: pd.DataFrame,
    stress_df: pd.DataFrame,
    stress_summary: dict[str, object],
    recomendacao_nacional: str,
    motivos_nacionais: list[str],
) -> str:
    lines = [
        "# Fase A - Validacao consolidada do Censo 2022",
        "",
        f"> Data da validacao: {date.today().isoformat()}",
        "",
        "## 1. Auditoria do join posicional por UF",
        "",
        _markdown_table(
            [
                "UF",
                "Shapefile",
                "Basico",
                "Renda total",
                "Renda valida",
                "Mismatch total %",
                "Seq municipio %",
                "Alerta >5%",
            ],
            [
                [
                    row.uf,
                    row.setores_shapefile,
                    row.setores_basico,
                    row.setores_renda_total,
                    row.setores_renda_validos,
                    f"{row.mismatch_renda_total_pct:.2f}",
                    f"{row.mun_seq_match_pct:.4f}",
                    "SIM" if row.alerta_join_gt_5pct else "NAO",
                ]
                for row in join_audit.itertuples()
            ],
        ),
        "",
        "## 2. Validacao da renda proxy",
        "",
        _markdown_table(
            [
                "UF",
                "Corr proxy vs M1",
                "Corr V06004 vs M1",
                "MAE proxy",
                "MAE V06004",
                "Ratio proxy",
                "Ratio V06004",
                "V06004/v0005 melhor?",
            ],
            [
                [
                    row.uf,
                    f"{row.corr_proxy_vs_m1:.4f}",
                    f"{row.corr_v06004_vs_m1:.4f}",
                    f"{row.mae_proxy_vs_m1:.2f}",
                    f"{row.mae_v06004_vs_m1:.2f}",
                    f"{row.median_ratio_proxy_vs_m1:.4f}",
                    f"{row.median_ratio_v06004_vs_m1:.4f}",
                    "SIM" if row.transformacao_v0005_melhor_que_bruta else "NAO",
                ]
                for row in renda_proxy.itertuples()
            ],
        ),
        "",
        _markdown_table(
            [
                "UF",
                "Setor mean",
                "Setor median",
                "Setor skew",
                "Outlier %",
                "Zeros %",
                "M1 mean",
                "M1 median",
                "Distribuicao coerente?",
            ],
            [
                [
                    row.uf,
                    f"{row.setor_mean:.2f}",
                    f"{row.setor_median:.2f}",
                    f"{row.setor_skew:.2f}",
                    f"{row.setor_outlier_3iqr_pct:.2f}",
                    f"{row.setor_zeros_pct:.2f}",
                    f"{row.m1_mean:.2f}",
                    f"{row.m1_median:.2f}",
                    "SIM" if row.distribuicao_coerente else "NAO",
                ]
                for row in renda_dist.itertuples()
            ],
        ),
        "",
        "### Capitais piloto",
        "",
        _markdown_table(
            ["UF", "Cidade", "Proxy mun", "V06004 mun", "M1 mun", "Cobertura %"],
            [
                [
                    row.uf,
                    row.cidade,
                    f"{row.renda_pc_proxy_mun:.2f}",
                    f"{row.v06004_mun:.2f}",
                    f"{row.renda_per_capita_m1:.2f}",
                    f"{row.coverage_valid_renda_pct:.2f}",
                ]
                for row in renda_cidades.itertuples()
            ],
        ),
        "",
        "## 3. Validacao intraurbana",
        "",
        _markdown_table(
            [
                "UF",
                "Cidade",
                "Hex",
                "Std municipal",
                "Std setor",
                "Ganho std",
                "Amp municipal",
                "Amp setor",
                "Ganho amplitude",
                "Correlacao",
            ],
            [
                [
                    row.uf,
                    row.cidade,
                    row.hex_cidade,
                    f"{row.municipal_std:.2f}",
                    f"{row.setor_std:.2f}",
                    f"{row.ganho_std:.2f}",
                    f"{row.municipal_p95_p05:.2f}",
                    f"{row.setor_p95_p05:.2f}",
                    f"{row.ganho_amplitude:.2f}",
                    row.correlacao_modelos,
                ]
                for row in intraurbano.itertuples()
            ],
        ),
        "",
        "## 4. Consistencia espacial intraurbana",
        "",
        _markdown_table(
            ["UF", "Cidade", "Hex avaliados", "Threshold", "Outliers criticos", "Status"],
            [
                [
                    row.uf,
                    row.cidade,
                    row.hex_avaliados,
                    f"{row.threshold_delta:.2f}",
                    row.critical_outliers,
                    row.spatial_status,
                ]
                for row in spatial.itertuples()
            ],
        ),
        "",
        "## 5. Stress test tecnico",
        "",
    ]

    if not profiling.empty:
        lines.extend(
            [
                "### Perfil medido nas UFs piloto",
                "",
                _markdown_table(
                    ["UF", "Hex", "Setores", "Tempo s", "Peak RSS MB"],
                    [
                        [
                            row.uf,
                            row.hex_count,
                            row.setor_count,
                            f"{row.time_s:.2f}",
                            f"{row.peak_rss_mb:.2f}",
                        ]
                        for row in profiling.itertuples()
                    ],
                ),
                "",
            ]
        )

    lines.extend(
        [
            _markdown_table(
                ["UF", "Hex", "Setores", "Tempo est. s", "Peak RSS est. MB"],
                [
                    [
                        row.uf,
                        row.hex_count,
                        row.setor_count,
                        f"{row.tempo_spatial_join_estimado_s:.2f}",
                        (
                            f"{row.peak_rss_estimado_mb:.2f}"
                            if pd.notna(row.peak_rss_estimado_mb)
                            else "N/A"
                        ),
                    ]
                    for row in stress_df.itertuples()
                ],
            ),
            "",
            f"- Tempo nacional estimado (sequencial): {stress_summary['tempo_nacional_estimado_min']:.2f} min",
            f"- Pico de memoria estimado na maior UF: {stress_summary['peak_rss_estimado_maior_uf_mb']} MB"
            if stress_summary["peak_rss_estimado_maior_uf_mb"] is not None
            else "- Pico de memoria estimado na maior UF: N/A",
            f"- UFs com alerta de join >5%: {', '.join(stress_summary['ufs_join_alerta_gt_5pct']) or 'nenhuma'}",
            f"- Gargalo principal: {stress_summary['observacao']}",
            "",
            "## 6. Recomendacao",
            "",
            f"**{recomendacao_nacional}** para escala nacional imediata.",
            "",
            "Motivos principais:",
        ]
    )
    for motivo in motivos_nacionais:
        lines.append(f"- {motivo}")
    lines.extend(
        [
            "",
            "## 7. Dados reais Ultra",
            "",
            "- Dados de faturamento/alunos/churn nao foram encontrados no repositorio; a validacao com performance real permanece pendente.",
        ]
    )
    return "\n".join(lines) + "\n"


def executar_validacao(
    *,
    censo_path: Path,
    base_oficial_path: Path,
    basico_path: Path,
    renda_path: Path,
    shp_path: Path,
    hex_root: Path,
    output_path: Path,
    report_path: Path,
    metadata_path: Path,
    profile_spatial_join: bool,
) -> dict[str, object]:
    basico, renda, shp = carregar_fontes_minimas(basico_path, renda_path, shp_path)
    join_audit = auditar_join_posicional(basico, renda, shp)

    validado = construir_base_validada(censo_path, base_oficial_path)
    base_oficial = pd.read_parquet(
        base_oficial_path,
        columns=["hex_id", "uf", "cod_municipio", "nome_municipio", "renda_per_capita"],
    )
    renda_proxy, renda_cidades = auditar_renda_proxy(basico, renda, base_oficial)
    renda_dist = auditar_distribuicao_renda(validado)
    intraurbano = medir_intraurbano(validado)
    spatial = auditar_continuidade_espacial(validado)
    profiling = (
        perfilar_spatial_join_piloto(
            hex_root=hex_root,
            basico_path=basico_path,
            renda_path=renda_path,
            shp_path=shp_path,
        )
        if profile_spatial_join
        else pd.DataFrame()
    )
    stress_df, stress_summary = estimar_stress_test(base_oficial, join_audit, profiling)
    validado = aplicar_flags_validacao(
        validado,
        join_audit=join_audit,
        renda_proxy=renda_proxy,
        renda_dist=renda_dist,
        intraurbano=intraurbano,
        spatial=spatial,
    )

    go_join_ok = bool(join_audit.loc[join_audit["uf"] == "GO", "join_consistente"].iloc[0])
    go_renda_ok = bool(
        renda_dist.loc[renda_dist["uf"] == "GO", "distribuicao_coerente"].iloc[0]
        and renda_proxy.loc[
            renda_proxy["uf"] == "GO", "transformacao_v0005_melhor_que_bruta"
        ].iloc[0]
    )
    go_intra_ok = bool(
        intraurbano.loc[
            intraurbano["uf"] == "GO", "ganho_intraurbano_confirmado"
        ].iloc[0]
    )
    go_spatial_ok = bool(
        spatial.loc[spatial["uf"] == "GO", "critical_outliers"].iloc[0] == 0
    )

    motivos_nacionais = []
    if join_audit["alerta_join_gt_5pct"].any():
        motivos_nacionais.append("join posicional ainda tem alerta estrutural >5% em AM e RR")
    if (renda_proxy["corr_proxy_vs_m1"] < 0.40).any():
        motivos_nacionais.append("a calibracao municipal da renda proxy segue fraca frente ao M1 nas UFs piloto")
    motivos_nacionais.append("nao ha validacao com performance real das unidades Ultra no repositorio atual")
    recomendacao_nacional = "NO-GO"

    report = gerar_relatorio_validacao(
        join_audit=join_audit,
        renda_proxy=renda_proxy,
        renda_cidades=renda_cidades,
        renda_dist=renda_dist,
        intraurbano=intraurbano,
        spatial=spatial,
        profiling=profiling,
        stress_df=stress_df,
        stress_summary=stress_summary,
        recomendacao_nacional=recomendacao_nacional,
        motivos_nacionais=motivos_nacionais,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    validado.to_parquet(output_path, index=False)
    report_path.write_text(report, encoding="utf-8")

    metadata = {
        "data_validacao": date.today().isoformat(),
        "output_path": str(output_path),
        "report_path": str(report_path),
        "go_validacoes_obrigatorias": {
            "join_consistente": go_join_ok,
            "renda_distribuicao_coerente": go_renda_ok,
            "ganho_intraurbano_confirmado": go_intra_ok,
            "ausencia_outliers_espaciais_criticos": go_spatial_ok,
        },
        "recomendacao_nacional": recomendacao_nacional,
        "ufs_join_alerta_gt_5pct": join_audit.loc[
            join_audit["alerta_join_gt_5pct"], "uf"
        ].tolist(),
        "renda_proxy_corr_vs_m1": renda_proxy.set_index("uf")[
            "corr_proxy_vs_m1"
        ].to_dict(),
        "ganho_amplitude_capitais": intraurbano.set_index("uf")[
            "ganho_amplitude"
        ].to_dict(),
        "critical_outliers_capitais": spatial.set_index("uf")[
            "critical_outliers"
        ].to_dict(),
        "stress_summary": stress_summary,
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return metadata


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Valida e consolida a Fase A do Censo 2022.")
    parser.add_argument("--censo-path", default=str(DEFAULT_CENSO_PATH))
    parser.add_argument("--base-oficial-path", default=str(DEFAULT_BASE_OFICIAL_PATH))
    parser.add_argument("--basico-path", default=str(NACIONAL_BASICO_PATH))
    parser.add_argument("--renda-path", default=str(NACIONAL_RENDA_PATH))
    parser.add_argument("--shp-path", default=str(NACIONAL_SHAPEFILE_PATH))
    parser.add_argument("--hex-root", default=str(DEFAULT_HEX_ROOT))
    parser.add_argument("--output-path", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--metadata-path", default=str(DEFAULT_METADATA_PATH))
    parser.add_argument(
        "--profile-spatial-join",
        action="store_true",
        help="Reroda o spatial join piloto para estimar tempo e pico de memoria.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    executar_validacao(
        censo_path=Path(args.censo_path),
        base_oficial_path=Path(args.base_oficial_path),
        basico_path=Path(args.basico_path),
        renda_path=Path(args.renda_path),
        shp_path=Path(args.shp_path),
        hex_root=Path(args.hex_root),
        output_path=Path(args.output_path),
        report_path=Path(args.report_path),
        metadata_path=Path(args.metadata_path),
        profile_spatial_join=args.profile_spatial_join,
    )


if __name__ == "__main__":
    main()
