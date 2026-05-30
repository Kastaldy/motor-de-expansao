"""Pipeline censitario nacional para as 21 UFs restantes (Bloco 7).

Camada paralela ao M1 oficial.
Nao altera score_priorizacao, hex_score_estrutural nem artefatos oficiais.
UFs ja cobertas (GO, SP, RJ, MG, DF, RS) sao excluidas deste pipeline.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from motor_expansao.pipelines import fase_a_censo2022_setores as fase_a_module
from motor_expansao.pipelines.calibrar_renda_setor_2022 import (
    calcular_score_calibrado,
    percentile_in_distribution,
)
from motor_expansao.pipelines.fase_a_piloto_expandido import (
    parse_k_global,
    resumir_metricas_uf,
)
from motor_expansao.pipelines.validar_fase_a_censo2022 import (
    UFS_BRASIL,
    auditar_join_posicional,
    carregar_fontes_minimas,
    detectar_outliers_espaciais,
)

# UFs ja cobertas pelos pipelines anteriores
_UFS_JA_COBERTAS = {"GO", "SP", "RJ", "MG", "DF", "RS"}

TARGET_UFS: list[str] = sorted(
    [uf for uf in UFS_BRASIL if uf not in _UFS_JA_COBERTAS]
)

DEFAULT_BASE_OFICIAL_PATH = Path("data/staging/brasil_estrutural.parquet")
DEFAULT_REFERENCE_CALIBRATED_PATH = Path("data/staging/censo2022_setores_calibrado.parquet")
DEFAULT_OUTPUT_PATH = Path("data/staging/censo2022_setores_calibrado_nacional_completo.parquet")
DEFAULT_REPORT_PATH = Path("data/reports/fase_a_nacional_completo.md")
DEFAULT_METADATA_PATH = Path("data/staging/censo2022_setores_calibrado_nacional_completo_metadata.json")

DEFAULT_BASICO_PATH = fase_a_module.NACIONAL_BASICO_PATH
DEFAULT_RENDA_PATH = fase_a_module.NACIONAL_RENDA_PATH
DEFAULT_SHP_PATH = fase_a_module.NACIONAL_SHAPEFILE_PATH
DEFAULT_HEX_ROOT = fase_a_module.DEFAULT_HEX_ROOT

MIN_COVERAGE_PCT = 85.0
MIN_AMPLITUDE = 50.0
MIN_SPEARMAN = 0.6


def calcular_qualidade_join_uf(summary: dict[str, object]) -> str:
    """Retorna 'A'/'B' se todos os gates passaram, 'C' caso contrario."""
    return summary["classe_join"] if summary["status_tecnico"] == "GO" else "C"


def carregar_k_global(reference_path: Path) -> tuple[float, str]:
    ref = pd.read_parquet(reference_path, columns=["metodo_calibracao_renda"])
    metodos = sorted(set(ref["metodo_calibracao_renda"].dropna().astype(str).tolist()))
    if not metodos:
        raise ValueError(f"Arquivo de referencia sem metodo_calibracao_renda: {reference_path}")
    if len(metodos) != 1:
        raise ValueError(f"Arquivo de referencia tem mais de um metodo de calibracao: {metodos}")
    method = metodos[0]
    return parse_k_global(method), method


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
    # Registra UF no modulo piloto para que as funcoes de leitura a reconhecam
    fase_a_module.UFS_PILOTO[uf] = UFS_BRASIL[uf]

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
        .transform(lambda s: s.fillna(0).rank(pct=True, method="average"))
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
        "Pipeline nacional completo Bloco 7."
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
    k_global: float,
    output_path: Path,
) -> str:
    lines = [
        "# Fase A - Pipeline Nacional Completo (Bloco 7)",
        "",
        f"> Data: {date.today().isoformat()}",
        f"> UFs: {', '.join(sorted(r['uf'] for r in technical_rows))}",
        f"> k_global fixo da calibracao validada: {k_global:.4f}",
        "",
        "## 1. Validacao tecnica por UF",
        "",
        "| UF | Coverage % | Amp p95-p05 | Std | Mismatch % | Classe join | qualidade_join_uf | Status tecnico |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in sorted(technical_rows, key=lambda r: r["uf"]):
        lines.append(
            "| {uf} | {coverage_pct:.2f} | {amplitude:.2f} | {std:.2f} | "
            "{mismatch_pct:.2f} | {classe_join} | {qualidade_join_uf} | {status_tecnico} |".format(**row)
        )

    go_ufs = [r["uf"] for r in technical_rows if r["status_tecnico"] == "GO"]
    nogo_ufs = [r["uf"] for r in technical_rows if r["status_tecnico"] != "GO"]

    lines.extend(
        [
            "",
            "## 2. Resumo de cobertura",
            "",
            f"- UFs com gates aprovados (qualidade A/B): {len(go_ufs)} — {', '.join(sorted(go_ufs)) or 'nenhuma'}",
            f"- UFs com gate degradado (qualidade C): {len(nogo_ufs)} — {', '.join(sorted(nogo_ufs)) or 'nenhuma'}",
            "- Nota: gates sao informacionais. Todas as UFs foram incluidas no parquet de saida.",
            "",
            "## 3. Decisao consolidada",
            "",
            "**GO** para uso controlado como camada complementar.",
            "Nenhuma UF bloqueia a geracao do parquet; UFs com qualidade C ficam marcadas e",
            "sao filtradas automaticamente pelo modelo hibrido.",
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
    data_download: str | None = None,
) -> dict[str, object]:
    k_global, metodo_calibracao_renda = carregar_k_global(reference_calibrated_path)
    data_download = data_download or date.today().isoformat()

    base_oficial = pd.read_parquet(base_oficial_path)
    renda_m1_nacional = pd.to_numeric(
        base_oficial["renda_per_capita"], errors="coerce"
    ).dropna().to_numpy()

    basico_raw, renda_raw, shp_raw = carregar_fontes_minimas(basico_path, renda_path, shp_path)
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
        try:
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
        except Exception as exc:
            # Gate nao-bloqueante: registra falha mas continua
            technical_rows.append({
                "uf": uf,
                "coverage_pct": 0.0,
                "amplitude": 0.0,
                "std": 0.0,
                "distinct": 0,
                "mismatch_pct": 100.0,
                "classe_join": "C",
                "join_gate": False,
                "gate_cobertura": False,
                "gate_amplitude": False,
                "status_espacial": "ERRO",
                "critical_outliers": -1,
                "threshold_delta": float("nan"),
                "hex_avaliados": 0,
                "spearman_vs_m1": float("nan"),
                "m1_amplitude": float("nan"),
                "m1_std": float("nan"),
                "ganho_amplitude_vs_m1": float("nan"),
                "ganho_std_vs_m1": float("nan"),
                "status_tecnico": "NO-GO",
                "qualidade_join_uf": "C",
                "erro": str(exc),
            })
            continue

        outlier_result = detectar_outliers_espaciais(
            df_uf[["hex_id", "score_setor_2022_calibrado"]].copy(),
            score_col="score_setor_2022_calibrado",
        )

        audit_row = join_audit.loc[join_audit["uf"] == uf]
        mismatch_pct = (
            float(audit_row["mismatch_renda_total_pct"].iloc[0])
            if not audit_row.empty
            else 100.0
        )

        summary = resumir_metricas_uf(
            df_uf,
            uf=uf,
            mismatch_pct=mismatch_pct,
            outlier_result=outlier_result,
        )
        qualidade = calcular_qualidade_join_uf(summary)
        summary["qualidade_join_uf"] = qualidade

        df_uf["mismatch_renda_total_pct_uf"] = mismatch_pct
        df_uf["classe_join_uf"] = summary["classe_join"]
        df_uf["qualidade_join_uf"] = qualidade
        df_uf["status_tecnico_nacional_uf"] = summary["status_tecnico"]
        df_uf["status_espacial_nacional_uf"] = summary["status_espacial"]
        df_uf["critical_outliers_nacional_uf"] = summary["critical_outliers"]

        technical_rows.append(summary)
        all_frames.append(df_uf)

    if not all_frames:
        raise RuntimeError("Nenhuma UF foi processada com sucesso.")

    result = pd.concat(all_frames, ignore_index=True)
    report = gerar_relatorio(
        technical_rows=technical_rows,
        k_global=k_global,
        output_path=output_path,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    result.to_parquet(output_path, index=False)
    report_path.write_text(report, encoding="utf-8")

    contagem_por_uf = (
        result.groupby("uf")["hex_id"].count().rename("n_hexes").reset_index()
        .set_index("uf")["n_hexes"]
        .to_dict()
    )

    metadata = {
        "data_execucao": date.today().isoformat(),
        "ufs_processadas": TARGET_UFS,
        "k_global": k_global,
        "metodo_calibracao_renda": metodo_calibracao_renda,
        "technical_rows": technical_rows,
        "contagem_por_uf": contagem_por_uf,
        "output_path": str(output_path),
        "report_path": str(report_path),
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    return metadata


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Pipeline censitario nacional para as 21 UFs restantes (Bloco 7)."
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
        data_download=args.data_download,
    )
    go_count = sum(1 for r in metadata["technical_rows"] if r["status_tecnico"] == "GO")
    total = len(metadata["technical_rows"])
    print(f"PIPELINE NACIONAL COMPLETO: {go_count}/{total} UFs com gates aprovados")


if __name__ == "__main__":
    main()
