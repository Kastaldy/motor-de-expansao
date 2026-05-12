"""Piloto expandido da Fase A calibrada para MG, DF e RS.

Camada paralela ao M1 oficial.
Nao altera score_priorizacao, hex_score_estrutural nem artefatos oficiais.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import date
from pathlib import Path

import h3
import numpy as np
import pandas as pd

from jobs.pipelines import fase_a_censo2022_setores as fase_a_module
from jobs.pipelines.calibrar_renda_setor_2022 import (
    calcular_score_calibrado,
    percentile_in_distribution,
)
from jobs.pipelines.validar_fase_a_censo2022 import (
    UFS_BRASIL,
    auditar_join_posicional,
    carregar_fontes_minimas,
    detectar_outliers_espaciais,
)

TARGET_UFS = ["MG", "DF", "RS"]
CAPITAIS = {
    "MG": {"cod_municipio": "3106200", "nome": "Belo Horizonte"},
    "DF": {"cod_municipio": "5300108", "nome": "Brasilia"},
    "RS": {"cod_municipio": "4314902", "nome": "Porto Alegre"},
}

DEFAULT_BASE_OFICIAL_PATH = Path("data/staging/brasil_estrutural.parquet")
DEFAULT_REFERENCE_CALIBRATED_PATH = Path("data/staging/censo2022_setores_calibrado.parquet")
DEFAULT_OUTPUT_PATH = Path("data/staging/censo2022_setores_calibrado_piloto_expandido.parquet")
DEFAULT_REPORT_PATH = Path("data/reports/fase_a_piloto_expandido.md")
DEFAULT_METADATA_PATH = Path("data/staging/censo2022_setores_calibrado_piloto_expandido_metadata.json")

DEFAULT_BASICO_PATH = fase_a_module.NACIONAL_BASICO_PATH
DEFAULT_RENDA_PATH = fase_a_module.NACIONAL_RENDA_PATH
DEFAULT_SHP_PATH = fase_a_module.NACIONAL_SHAPEFILE_PATH
DEFAULT_HEX_ROOT = fase_a_module.DEFAULT_HEX_ROOT

MIN_COVERAGE_PCT = 85.0
MIN_AMPLITUDE = 50.0


def parse_k_global(method: str) -> float:
    match = re.search(r"k=([0-9]+(?:\.[0-9]+)?)", str(method))
    if not match:
        raise ValueError(f"Metodo de calibracao sem k global: {method}")
    return float(match.group(1))


def classificar_qualidade_join(mismatch_pct: float) -> str:
    if mismatch_pct < 2.0:
        return "A"
    if mismatch_pct <= 5.0:
        return "B"
    return "C"


def ensure_supported_ufs(ufs: list[str]) -> None:
    for uf in ufs:
        if uf not in UFS_BRASIL:
            raise ValueError(f"UF nao suportada: {uf}")
        fase_a_module.UFS_PILOTO[uf] = UFS_BRASIL[uf]


def carregar_k_global(reference_path: Path) -> tuple[float, str]:
    ref = pd.read_parquet(reference_path, columns=["metodo_calibracao_renda"])
    metodos = sorted(
        set(ref["metodo_calibracao_renda"].dropna().astype(str).tolist())
    )
    if not metodos:
        raise ValueError(
            f"Arquivo de referencia sem metodo_calibracao_renda: {reference_path}"
        )
    if len(metodos) != 1:
        raise ValueError(
            f"Arquivo de referencia tem mais de um metodo de calibracao: {metodos}"
        )
    method = metodos[0]
    return parse_k_global(method), method


def resumir_distribuicao(series: pd.Series) -> dict[str, float]:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return {
            "coverage_pct": 0.0,
            "amplitude": 0.0,
            "std": 0.0,
            "distinct": 0,
        }
    return {
        "coverage_pct": round(float(numeric.size), 2),
        "amplitude": round(float(numeric.quantile(0.95) - numeric.quantile(0.05)), 2),
        "std": round(float(numeric.std(ddof=0)), 2),
        "distinct": int(numeric.nunique()),
    }


def resumir_metricas_uf(
    df_uf: pd.DataFrame,
    *,
    uf: str,
    mismatch_pct: float,
    outlier_result: dict[str, object],
) -> dict[str, object]:
    score_cal = pd.to_numeric(df_uf["score_setor_2022_calibrado"], errors="coerce")
    score_m1 = pd.to_numeric(df_uf["score_priorizacao"], errors="coerce")

    coverage_pct = round(float(score_cal.notna().mean() * 100), 2)
    cal_stats = resumir_distribuicao(score_cal)
    m1_stats = resumir_distribuicao(score_m1)

    both = df_uf[["score_setor_2022_calibrado", "score_priorizacao"]].dropna()
    spearman_modelos = (
        round(
            float(
                both["score_setor_2022_calibrado"].corr(
                    both["score_priorizacao"], method="spearman"
                )
            ),
            4,
        )
        if len(both) > 1
        else np.nan
    )

    classe_join = classificar_qualidade_join(mismatch_pct)
    gate_cobertura = coverage_pct >= MIN_COVERAGE_PCT
    gate_amplitude = cal_stats["amplitude"] > MIN_AMPLITUDE
    join_gate = classe_join in {"A", "B"}
    spatial_status = "GO" if int(outlier_result["critical_outliers"]) == 0 else "REVIEW"
    status_tecnico = "GO" if (gate_cobertura and gate_amplitude and join_gate) else "NO-GO"

    return {
        "uf": uf,
        "coverage_pct": coverage_pct,
        "amplitude": cal_stats["amplitude"],
        "std": cal_stats["std"],
        "distinct": cal_stats["distinct"],
        "mismatch_pct": round(float(mismatch_pct), 2),
        "classe_join": classe_join,
        "join_gate": join_gate,
        "gate_cobertura": gate_cobertura,
        "gate_amplitude": gate_amplitude,
        "status_espacial": spatial_status,
        "critical_outliers": int(outlier_result["critical_outliers"]),
        "threshold_delta": outlier_result["threshold"],
        "hex_avaliados": int(outlier_result["avaliados"]),
        "spearman_vs_m1": spearman_modelos,
        "m1_amplitude": m1_stats["amplitude"],
        "m1_std": m1_stats["std"],
        "ganho_amplitude_vs_m1": round(cal_stats["amplitude"] - m1_stats["amplitude"], 2),
        "ganho_std_vs_m1": round(cal_stats["std"] - m1_stats["std"], 2),
        "status_tecnico": status_tecnico,
    }


def _normalizar_coluna(name: str) -> str:
    text = unicodedata.normalize("NFKD", str(name))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_")
    return text


def _find_column(columns: list[str], candidates: list[str]) -> str | None:
    normalized = {_normalizar_coluna(col): col for col in columns}
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    return None


def _load_tabular(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    raise ValueError(f"Formato de snapshot Ultra nao suportado: {path}")


def localizar_snapshot_ultra(explicit_path: Path | None = None) -> Path | None:
    if explicit_path is not None and explicit_path.exists():
        return explicit_path

    search_roots = [Path("data/staging"), Path("data/raw"), Path("data/outputs")]
    metric_tokens = ("fatur", "alun", "churn", "conver", "perform", "ltv")
    for root in search_roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".parquet", ".csv", ".xlsx", ".xls"}:
                continue
            normalized_name = _normalizar_coluna(path.stem)
            if "ultra" not in normalized_name:
                continue
            if not any(token in normalized_name for token in metric_tokens):
                continue
            return path
    return None


def avaliar_snapshot_ultra(
    expanded: pd.DataFrame,
    *,
    ultra_path: Path | None = None,
) -> dict[str, object]:
    path = localizar_snapshot_ultra(ultra_path)
    if path is None:
        return {
            "status": "SNAPSHOT_NAO_ENCONTRADO",
            "path": None,
            "unit_rows": [],
            "correlacoes": [],
            "comparacao_m1": [],
            "outliers": [],
            "mensagem": (
                "Snapshot real de unidades Ultra nao encontrado no workspace; "
                "correlacao de negocio e ganho vs M1 permanecem pendentes."
            ),
        }

    units = _load_tabular(path).copy()
    if units.empty:
        return {
            "status": "SNAPSHOT_VAZIO",
            "path": str(path),
            "unit_rows": [],
            "correlacoes": [],
            "comparacao_m1": [],
            "outliers": [],
            "mensagem": "Snapshot real de unidades Ultra existe, mas esta vazio.",
        }

    units.columns = [str(col) for col in units.columns]
    hex_col = _find_column(list(units.columns), ["hex_id", "hex", "h3", "h3_id"])
    lat_col = _find_column(list(units.columns), ["lat", "latitude"])
    lng_col = _find_column(list(units.columns), ["lng", "lon", "longitude", "long"])

    if hex_col is None and (lat_col is None or lng_col is None):
        return {
            "status": "SNAPSHOT_SEM_LOCALIZACAO",
            "path": str(path),
            "unit_rows": [],
            "correlacoes": [],
            "comparacao_m1": [],
            "outliers": [],
            "mensagem": (
                "Snapshot real de unidades Ultra foi encontrado, mas nao tem "
                "hex_id nem coordenadas lat/lng para cruzamento."
            ),
        }

    if hex_col is None:
        units["hex_id"] = [
            h3.latlng_to_cell(float(lat), float(lng), 7)
            if pd.notna(lat) and pd.notna(lng)
            else pd.NA
            for lat, lng in zip(units[lat_col], units[lng_col])
        ]
    else:
        units["hex_id"] = units[hex_col].astype("string")

    unit_name_col = _find_column(
        list(units.columns),
        ["nome_unidade", "unidade", "nome", "unit_name", "loja"],
    )
    metric_cols = {
        "faturamento": _find_column(
            list(units.columns), ["faturamento", "receita", "revenue"]
        ),
        "total_alunos": _find_column(
            list(units.columns), ["total_alunos", "alunos", "students"]
        ),
        "churn": _find_column(list(units.columns), ["churn", "cancelamento"]),
        "conversao": _find_column(
            list(units.columns), ["conversao", "conversion", "taxa_conversao"]
        ),
    }

    merged = units.merge(
        expanded[
            [
                "hex_id",
                "uf",
                "cod_municipio",
                "nome_municipio",
                "score_setor_2022_calibrado",
                "score_priorizacao",
            ]
        ],
        on="hex_id",
        how="inner",
        suffixes=("_source", ""),
    )
    if merged.empty:
        return {
            "status": "SNAPSHOT_SEM_MATCH",
            "path": str(path),
            "unit_rows": [],
            "correlacoes": [],
            "comparacao_m1": [],
            "outliers": [],
            "mensagem": (
                "Snapshot real de unidades Ultra foi encontrado, mas nenhum hex "
                "fez match com MG/DF/RS no piloto expandido."
            ),
        }

    merged["nome_unidade"] = (
        merged[unit_name_col].astype("string")
        if unit_name_col is not None
        else pd.Series(
            [f"unidade_{idx+1}" for idx in range(len(merged))], index=merged.index
        ).astype("string")
        )

    uf_col = "uf" if "uf" in merged.columns else "uf_source"
    unit_rows = []
    for row in merged.itertuples():
        unit_rows.append(
            {
                "uf": getattr(row, uf_col),
                "nome_unidade": row.nome_unidade,
                "hex_id": row.hex_id,
                "score_setor_2022_calibrado": round(float(row.score_setor_2022_calibrado), 2),
                "score_priorizacao": round(float(row.score_priorizacao), 2),
            }
        )

    correlation_rows: list[dict[str, object]] = []
    comparison_rows: list[dict[str, object]] = []
    outlier_rows: list[dict[str, object]] = []

    metric_expectation = {
        "faturamento": 1.0,
        "total_alunos": 1.0,
        "conversao": 1.0,
        "churn": -1.0,
    }

    for metric_name, source_col in metric_cols.items():
        if source_col is None:
            continue
        values = pd.to_numeric(merged[source_col], errors="coerce")
        if metric_name == "churn":
            adjusted = -values
        else:
            adjusted = values
        merged[f"{metric_name}_score"] = adjusted

        for uf in TARGET_UFS:
            subset = merged.loc[merged["uf"] == uf].copy()
            subset = subset.dropna(
                subset=["score_setor_2022_calibrado", "score_priorizacao", f"{metric_name}_score"]
            )
            if len(subset) < 3:
                continue

            corr_cal = subset["score_setor_2022_calibrado"].corr(
                subset[f"{metric_name}_score"], method="spearman"
            )
            corr_m1 = subset["score_priorizacao"].corr(
                subset[f"{metric_name}_score"], method="spearman"
            )
            abs_cal = abs(float(corr_cal)) if pd.notna(corr_cal) else float("-inf")
            abs_m1 = abs(float(corr_m1)) if pd.notna(corr_m1) else float("-inf")
            correlation_rows.append(
                {
                    "uf": uf,
                    "metrica": metric_name,
                    "correlacao_spearman_calibrado": round(float(corr_cal), 4),
                    "correlacao_spearman_m1": round(float(corr_m1), 4),
                    "direcao_esperada": "positiva" if metric_expectation[metric_name] > 0 else "negativa",
                }
            )
            comparison_rows.append(
                {
                    "uf": uf,
                    "metrica": metric_name,
                    "vencedor": (
                        "score_setor_2022_calibrado"
                        if abs_cal > abs_m1
                        else "score_priorizacao"
                    ),
                    "delta_abs": round(abs_cal - abs_m1, 4),
                }
            )

            high_score = subset["score_setor_2022_calibrado"].quantile(0.75)
            low_score = subset["score_setor_2022_calibrado"].quantile(0.25)
            high_perf = subset[f"{metric_name}_score"].quantile(0.75)
            low_perf = subset[f"{metric_name}_score"].quantile(0.25)

            mismatch = subset[
                (
                    (subset["score_setor_2022_calibrado"] >= high_score)
                    & (subset[f"{metric_name}_score"] <= low_perf)
                )
                | (
                    (subset["score_setor_2022_calibrado"] <= low_score)
                    & (subset[f"{metric_name}_score"] >= high_perf)
                )
            ].copy()
            for _, row in mismatch.head(10).iterrows():
                outlier_rows.append(
                    {
                        "uf": uf,
                        "metrica": metric_name,
                        "nome_unidade": row["nome_unidade"],
                        "score_setor_2022_calibrado": round(
                            float(row["score_setor_2022_calibrado"]), 2
                        ),
                        "score_priorizacao": round(float(row["score_priorizacao"]), 2),
                        "valor_metrica": round(float(row[source_col]), 4),
                    }
                )

    status = "GO" if correlation_rows else "PENDENTE"
    mensagem = (
        "Snapshot real de unidades Ultra carregado e cruzado com o piloto expandido."
        if correlation_rows
        else "Snapshot real encontrado, mas sem densidade minima para correlacoes confiaveis."
    )
    return {
        "status": status,
        "path": str(path),
        "unit_rows": unit_rows,
        "correlacoes": correlation_rows,
        "comparacao_m1": comparison_rows,
        "outliers": outlier_rows,
        "mensagem": mensagem,
    }


def processar_uf(
    uf: str,
    *,
    base_oficial: pd.DataFrame,
    renda_m1_nacional: np.ndarray,
    k_global: float,
    data_download: str,
    basico_path: Path,
    renda_path: Path,
    shp_path: Path,
    hex_root: Path,
) -> pd.DataFrame:
    gdf_malha = fase_a_module.ler_malha_nacional_uf(shp_path, uf)
    df_basico = fase_a_module.ler_basico_nacional_uf(basico_path, uf)
    df_renda = fase_a_module.ler_renda_nacional_uf_preservando_suprimidos(renda_path, uf)
    gdf_setores = fase_a_module.montar_gdf_setores_nacional(gdf_malha, df_basico, df_renda, uf)
    gdf_setores = gdf_setores[gdf_setores["pop_total_setor_2022"].fillna(0) > 0].copy()

    df_hex = fase_a_module.carregar_hexagonos_uf(hex_root, uf)
    df_result = fase_a_module.spatial_join_area_weighted(df_hex, gdf_setores)
    df_result = fase_a_module.aplicar_fallback(df_result)
    df_result = fase_a_module.calcular_score_setor_2022(df_result, base_nacional=base_oficial)
    df_result = fase_a_module.adicionar_rastreabilidade(df_result, data_download)
    df_result["uf"] = uf

    df_result = df_result.merge(
        base_oficial[
            [
                "hex_id",
                "uf",
                "cod_municipio",
                "nome_municipio",
                "renda_per_capita",
                "hex_score_estrutural",
                "score_priorizacao",
                "pop_pct_nacional",
            ]
        ],
        on=["hex_id", "uf"],
        how="left",
    )

    valid_mask = df_result["renda_per_capita_setor_2022"].notna()
    df_result.loc[valid_mask, "renda_per_capita_setor_2022_calibrada"] = (
        df_result.loc[valid_mask, "renda_per_capita_setor_2022"] * k_global
    )
    df_result.loc[~valid_mask, "renda_per_capita_setor_2022_calibrada"] = np.nan

    renda_cal = df_result.loc[valid_mask, "renda_per_capita_setor_2022_calibrada"].to_numpy()
    if renda_cal.size > 0:
        df_result.loc[valid_mask, "renda_pct_nacional_calibrado"] = percentile_in_distribution(
            renda_cal,
            renda_m1_nacional,
        )
    df_result.loc[~valid_mask, "renda_pct_nacional_calibrado"] = np.nan

    df_result["pop_pct_municipal"] = (
        df_result.groupby("cod_municipio")["pop_total_setor_2022"]
        .transform(lambda series: series.fillna(0).rank(pct=True, method="average"))
    )
    df_result["pop_pct_nacional_m1"] = df_result["pop_pct_nacional"]

    cal_mask = (
        df_result["renda_pct_nacional_calibrado"].notna()
        & df_result["pop_pct_municipal"].notna()
        & ~df_result["fallback_setor_2022"].fillna(False)
    )
    if cal_mask.any():
        hex_score, ajuste, score = calcular_score_calibrado(
            df_result.loc[cal_mask, "renda_pct_nacional_calibrado"].to_numpy(),
            df_result.loc[cal_mask, "pop_pct_municipal"].to_numpy(),
        )
        df_result.loc[cal_mask, "hex_score_estrutural_calibrado"] = hex_score
        df_result.loc[cal_mask, "ajuste_calibrado"] = ajuste
        df_result.loc[cal_mask, "score_setor_2022_calibrado"] = score

    df_result["metodo_join_setor_2022"] = "posicional_uf_preservando_suprimidos"
    df_result["transformacao_renda_setor_2022"] = "V06004_div_v0005"
    df_result["data_validacao_fase_a"] = date.today().isoformat()
    df_result["metodo_calibracao_renda"] = f"multiplicativo_global_k={k_global:.4f}"
    df_result["metodo_calibracao_pop"] = "pop_pct_municipal_within_municipio"
    df_result["referencia_calibracao"] = "m1_nacional_mediana_piloto_go_sp_rj"
    df_result["data_calibracao"] = date.today().isoformat()
    df_result["score_oficial_nome_calibrado"] = "score_setor_2022_calibrado"
    df_result["score_experimental_nota"] = (
        "Experimental. Nao substitui score_priorizacao M1. "
        "Piloto expandido da Fase A calibrada."
    )
    return df_result.reset_index(drop=True)


def _format_metric(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "N/D"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def gerar_relatorio(
    *,
    technical_rows: list[dict[str, object]],
    ultra_validation: dict[str, object],
    k_global: float,
    output_path: Path,
) -> str:
    lines = [
        "# Fase A - Piloto expandido calibrado",
        "",
        f"> Data: {date.today().isoformat()}",
        f"> UFs: {', '.join(TARGET_UFS)}",
        f"> k_global fixo da calibracao validada: {k_global:.4f}",
        "",
        "## 1. Validacao tecnica por UF",
        "",
        "| UF | Coverage % | Amp p95-p05 | Std | Distintos | Mismatch % | Classe join | Outliers criticos | Status espacial | Status tecnico |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in technical_rows:
        lines.append(
            "| {uf} | {coverage_pct:.2f} | {amplitude:.2f} | {std:.2f} | {distinct} | "
            "{mismatch_pct:.2f} | {classe_join} | {critical_outliers} | {status_espacial} | "
            "{status_tecnico} |".format(**row)
        )

    lines.extend(
        [
            "",
            "## 2. Comparativo tecnico com o M1",
            "",
            "| UF | Amp calibrado | Amp M1 | Ganho amp | Std calibrado | Std M1 | Ganho std | Spearman calibrado vs M1 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in technical_rows:
        lines.append(
            f"| {row['uf']} | {row['amplitude']:.2f} | {row['m1_amplitude']:.2f} | "
            f"{row['ganho_amplitude_vs_m1']:.2f} | {row['std']:.2f} | {row['m1_std']:.2f} | "
            f"{row['ganho_std_vs_m1']:.2f} | {_format_metric(row['spearman_vs_m1'])} |"
        )

    lines.extend(
        [
            "",
            "## 3. Dados reais Ultra",
            "",
            f"- Status: `{ultra_validation['status']}`",
            f"- Fonte: `{ultra_validation['path'] or 'nao encontrada'}`",
            f"- Observacao: {ultra_validation['mensagem']}",
        ]
    )

    if ultra_validation["correlacoes"]:
        lines.extend(
            [
                "",
                "| UF | Metrica | Spearman calibrado | Spearman M1 | Direcao esperada |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for row in ultra_validation["correlacoes"]:
            lines.append(
                f"| {row['uf']} | {row['metrica']} | {row['correlacao_spearman_calibrado']:.4f} | "
                f"{row['correlacao_spearman_m1']:.4f} | {row['direcao_esperada']} |"
            )
    else:
        lines.extend(
            [
                "",
                "- Correlacoes com metricas reais: N/D.",
                "- Comparacao de explicacao de performance vs M1: pendente pelo mesmo motivo.",
            ]
        )

    decision = "GO"
    motivos = []
    if not all(row["status_tecnico"] == "GO" for row in technical_rows):
        decision = "NO-GO"
        motivos.append("nem todas as UFs passaram nos gates tecnicos minimos")
    if ultra_validation["status"] != "GO":
        decision = "NO-GO"
        motivos.append("validacao com dados reais da Ultra nao foi concluida")

    lines.extend(
        [
            "",
            "## 4. Decisao consolidada",
            "",
            f"**{decision}** para escala nacional imediata.",
            "",
            "Motivos principais:",
        ]
    )
    for motivo in motivos or ["todos os gates tecnicos e de negocio passaram"]:
        lines.append(f"- {motivo}")
    lines.extend(
        [
            "",
            f"- Output final: `{output_path}`",
            "- M1 oficial permaneceu intocado durante toda a execucao.",
        ]
    )
    return "\n".join(lines) + "\n"


def executar(
    *,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    report_path: Path = DEFAULT_REPORT_PATH,
    metadata_path: Path = DEFAULT_METADATA_PATH,
    base_oficial_path: Path = DEFAULT_BASE_OFICIAL_PATH,
    basico_path: Path = DEFAULT_BASICO_PATH,
    renda_path: Path = DEFAULT_RENDA_PATH,
    shp_path: Path = DEFAULT_SHP_PATH,
    hex_root: Path = DEFAULT_HEX_ROOT,
    reference_calibrated_path: Path = DEFAULT_REFERENCE_CALIBRATED_PATH,
    ultra_path: Path | None = None,
    data_download: str | None = None,
) -> dict[str, object]:
    ensure_supported_ufs(TARGET_UFS)
    k_global, metodo_calibracao_renda = carregar_k_global(reference_calibrated_path)
    data_download = data_download or date.today().isoformat()

    base_oficial = pd.read_parquet(base_oficial_path)
    renda_m1_nacional = pd.to_numeric(
        base_oficial["renda_per_capita"], errors="coerce"
    ).dropna().to_numpy()

    basico_raw, renda_raw, shp_raw = carregar_fontes_minimas(
        basico_path,
        renda_path,
        shp_path,
    )
    join_audit = auditar_join_posicional(basico_raw, renda_raw, shp_raw)
    join_audit = (
        join_audit[join_audit["uf"].isin(TARGET_UFS)]
        .copy()
        .sort_values("uf")
        .reset_index(drop=True)
    )

    all_frames: list[pd.DataFrame] = []
    technical_rows: list[dict[str, object]] = []
    for uf in TARGET_UFS:
        df_uf = processar_uf(
            uf,
            base_oficial=base_oficial,
            renda_m1_nacional=renda_m1_nacional,
            k_global=k_global,
            data_download=data_download,
            basico_path=basico_path,
            renda_path=renda_path,
            shp_path=shp_path,
            hex_root=hex_root,
        )

        outlier_result = detectar_outliers_espaciais(
            df_uf[["hex_id", "score_setor_2022_calibrado"]].copy(),
            score_col="score_setor_2022_calibrado",
        )
        mismatch_pct = float(
            join_audit.loc[join_audit["uf"] == uf, "mismatch_renda_total_pct"].iloc[0]
        )
        summary = resumir_metricas_uf(
            df_uf,
            uf=uf,
            mismatch_pct=mismatch_pct,
            outlier_result=outlier_result,
        )
        technical_rows.append(summary)

        df_uf["mismatch_renda_total_pct_uf"] = mismatch_pct
        df_uf["classe_join_uf"] = summary["classe_join"]
        df_uf["status_tecnico_piloto_expandido_uf"] = summary["status_tecnico"]
        df_uf["status_espacial_piloto_expandido_uf"] = summary["status_espacial"]
        df_uf["critical_outliers_piloto_expandido_uf"] = summary["critical_outliers"]
        all_frames.append(df_uf)

    expanded = pd.concat(all_frames, ignore_index=True)
    ultra_validation = avaliar_snapshot_ultra(expanded, ultra_path=ultra_path)

    report = gerar_relatorio(
        technical_rows=technical_rows,
        ultra_validation=ultra_validation,
        k_global=k_global,
        output_path=output_path,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    expanded.to_parquet(output_path, index=False)
    report_path.write_text(report, encoding="utf-8")

    metadata = {
        "data_execucao": date.today().isoformat(),
        "ufs_processadas": TARGET_UFS,
        "k_global": k_global,
        "metodo_calibracao_renda": metodo_calibracao_renda,
        "technical_rows": technical_rows,
        "ultra_validation": ultra_validation,
        "output_path": str(output_path),
        "report_path": str(report_path),
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return metadata


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Executa o piloto expandido da Fase A calibrada para MG, DF e RS."
    )
    parser.add_argument("--output-path", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--metadata-path", default=str(DEFAULT_METADATA_PATH))
    parser.add_argument("--base-oficial-path", default=str(DEFAULT_BASE_OFICIAL_PATH))
    parser.add_argument("--basico-path", default=str(DEFAULT_BASICO_PATH))
    parser.add_argument("--renda-path", default=str(DEFAULT_RENDA_PATH))
    parser.add_argument("--shp-path", default=str(DEFAULT_SHP_PATH))
    parser.add_argument("--hex-root", default=str(DEFAULT_HEX_ROOT))
    parser.add_argument(
        "--reference-calibrated-path",
        default=str(DEFAULT_REFERENCE_CALIBRATED_PATH),
    )
    parser.add_argument(
        "--ultra-unidades-path",
        default=None,
        help="Snapshot offline opcional com unidades Ultra e metricas reais.",
    )
    parser.add_argument("--data-download", default=date.today().isoformat())
    return parser


def main() -> None:
    args = build_parser().parse_args()
    metadata = executar(
        output_path=Path(args.output_path),
        report_path=Path(args.report_path),
        metadata_path=Path(args.metadata_path),
        base_oficial_path=Path(args.base_oficial_path),
        basico_path=Path(args.basico_path),
        renda_path=Path(args.renda_path),
        shp_path=Path(args.shp_path),
        hex_root=Path(args.hex_root),
        reference_calibrated_path=Path(args.reference_calibrated_path),
        ultra_path=Path(args.ultra_unidades_path) if args.ultra_unidades_path else None,
        data_download=args.data_download,
    )
    status = "GO"
    if not all(row["status_tecnico"] == "GO" for row in metadata["technical_rows"]):
        status = "NO-GO"
    if metadata["ultra_validation"]["status"] != "GO":
        status = "NO-GO"
    print(f"PILOTO EXPANDIDO FASE A: {status}")


if __name__ == "__main__":
    main()
