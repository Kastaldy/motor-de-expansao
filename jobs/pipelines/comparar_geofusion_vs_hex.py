"""
Bloco 3 - Comparar GeoFusion 1km vs populacao do hex.

Compara a leitura de raio 1km do GeoFusion com a populacao do hexagono H3 res7
onde a unidade Ultra esta localizada. O KPI principal e a densidade (hab/km2),
pois as areas cobertas sao distintas: GeoFusion cobre circulo de ~3.14 km2 e
o hex H3 res7 cobre ~5.16 km2. A diferenca bruta de populacao e registrada
apenas como diagnostico secundario.

Saida: data/reports/validacao_geofusion_vs_hex.md

Nao altera nenhum artefato oficial do M1.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

PERF_HEX_PATH = ROOT / "data" / "staging" / "unidades_ultra_performance_hex.parquet"
REPORT_PATH = ROOT / "data" / "reports" / "validacao_geofusion_vs_hex.md"

GEOFUSION_AREA_KM2 = 3.14  # pi * r^2, r=1km

REQUIRED_INPUT_COLS = {
    "unidade",
    "uf",
    "hex_id_res7",
    "pop_geofusion_1km",
    "densidade_geofusion_1km_km2",
    "pop_hex_base",
    "fonte_pop_hex_base",
}

OUTPUT_COLS = [
    "unidade",
    "uf",
    "hex_id_res7",
    "area_geofusion_km2",
    "pop_geofusion_1km",
    "densidade_geofusion_1km_km2",
    "densidade_geofusion_1km_calc",
    "area_hex_km2",
    "pop_hex_base",
    "fonte_pop_hex_base",
    "densidade_hex_km2",
    "delta_densidade_hex_vs_geofusion",
    "ratio_densidade_hex_geofusion",
    "delta_pop_hex_vs_geofusion",
    "flag_sem_geofusion",
    "flag_sem_coord",
    "flag_sem_pop_hex",
]


def _cell_area_km2(hex_id: object) -> float | None:
    if pd.isna(hex_id):
        return None
    import h3
    try:
        return h3.cell_area(str(hex_id), unit="km^2")
    except Exception:
        return None


def _safe_div(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    num = pd.to_numeric(numerator, errors="coerce")
    den = pd.to_numeric(denominator, errors="coerce")
    valid_den = den.where(den > 0)
    return num / valid_den


def calcular_comparacao(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    out["flag_sem_geofusion"] = pd.to_numeric(out["pop_geofusion_1km"], errors="coerce").isna()
    out["flag_sem_coord"] = out["hex_id_res7"].isna() | out["fonte_pop_hex_base"].eq("sem_hex_id_res7")
    pop_num = pd.to_numeric(out["pop_hex_base"], errors="coerce")
    out["flag_sem_pop_hex"] = pop_num.isna() | (pop_num <= 0)

    out["area_geofusion_km2"] = GEOFUSION_AREA_KM2
    out["densidade_geofusion_1km_calc"] = (
        pd.to_numeric(out["pop_geofusion_1km"], errors="coerce") / GEOFUSION_AREA_KM2
    )

    out["area_hex_km2"] = out["hex_id_res7"].map(_cell_area_km2)
    out["densidade_hex_km2"] = _safe_div(out["pop_hex_base"], out["area_hex_km2"])

    out["delta_densidade_hex_vs_geofusion"] = (
        pd.to_numeric(out["densidade_hex_km2"], errors="coerce")
        - pd.to_numeric(out["densidade_geofusion_1km_calc"], errors="coerce")
    )
    out["ratio_densidade_hex_geofusion"] = _safe_div(
        out["densidade_hex_km2"], out["densidade_geofusion_1km_calc"]
    )

    # diagnostico secundario: diferenca bruta de populacao
    out["delta_pop_hex_vs_geofusion"] = (
        pd.to_numeric(out["pop_hex_base"], errors="coerce")
        - pd.to_numeric(out["pop_geofusion_1km"], errors="coerce")
    )

    for col in ["flag_sem_geofusion", "flag_sem_coord", "flag_sem_pop_hex"]:
        out[col] = out[col].astype(bool)

    return out


def gerar_comparacao(path: Path = PERF_HEX_PATH) -> pd.DataFrame:
    df = pd.read_parquet(path)
    faltam = REQUIRED_INPUT_COLS - set(df.columns)
    if faltam:
        raise AssertionError(f"Colunas obrigatorias ausentes: {sorted(faltam)}")
    return calcular_comparacao(df)


def _fmt(value: object, decimals: int = 1) -> str:
    if pd.isna(value):
        return "—"
    return f"{float(value):,.{decimals}f}"


def escrever_relatorio(df: pd.DataFrame, path: Path = REPORT_PATH) -> None:
    lines: list[str] = []
    a = lines.append

    a("# Validacao GeoFusion 1km vs Populacao do Hex")
    a("")
    a(f"**Data:** 2026-05-15  ")
    a(f"**Unidades analisadas:** {len(df)}")
    a("")

    a("## Coberturas")
    a("")
    n_geo = int((~df["flag_sem_geofusion"]).sum())
    n_coord = int((~df["flag_sem_coord"]).sum())
    n_pop = int((~df["flag_sem_pop_hex"]).sum())
    n_comp = int((~df["flag_sem_geofusion"] & ~df["flag_sem_pop_hex"]).sum())
    a("| Indicador | n |")
    a("| --- | --- |")
    a(f"| Com dado GeoFusion | {n_geo} |")
    a(f"| Com hex_id_res7 valido | {n_coord} |")
    a(f"| Com pop_hex_base valida | {n_pop} |")
    a(f"| Base comparavel (ambos) | {n_comp} |")
    a("")

    a("## Contexto metodologico")
    a("")
    a("As areas cobertas sao intrinsecamente distintas — nao e esperado que populacao GeoFusion")
    a("e populacao do hex sejam iguais. O KPI de comparacao e a densidade (hab/km2).")
    a("")
    a("| Fonte | Area coberta |")
    a("| --- | --- |")
    a(f"| GeoFusion raio 1 km | pi x 1^2 = {GEOFUSION_AREA_KM2} km2 (constante) |")
    a("| H3 resolucao 7 | ~5.16 km2 (varia por hex; calculado via h3.cell_area) |")
    a("")
    a("Interpretacao do ratio `densidade_hex / densidade_geofusion`:")
    a("- Ratio > 1: hex mais denso que raio 1 km GeoFusion (hex captura area menos densa ao redor).")
    a("- Ratio < 1: nucleo urbano de 1 km GeoFusion mais denso que o hex como um todo.")
    a("")

    comp = df[~df["flag_sem_geofusion"] & ~df["flag_sem_pop_hex"]].copy()

    if not comp.empty:
        a("## Comparacao de densidades — base comparavel")
        a("")
        a("| Unidade | UF | Fonte pop hex | Area hex km2 | Dens GeoFusion (hab/km2) | Dens hex (hab/km2) | Delta | Ratio |")
        a("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for _, row in comp.sort_values("unidade").iterrows():
            a(
                f"| {row['unidade']} | {row['uf']} | {row['fonte_pop_hex_base']} "
                f"| {_fmt(row.get('area_hex_km2'), 3)} "
                f"| {_fmt(row.get('densidade_geofusion_1km_calc'))} "
                f"| {_fmt(row.get('densidade_hex_km2'))} "
                f"| {_fmt(row.get('delta_densidade_hex_vs_geofusion'))} "
                f"| {_fmt(row.get('ratio_densidade_hex_geofusion'), 2)} |"
            )
        a("")

        valid_ratio = pd.to_numeric(comp["ratio_densidade_hex_geofusion"], errors="coerce").dropna()
        if not valid_ratio.empty:
            a("## Estatisticas do ratio")
            a("")
            a("| Estatistica | Valor |")
            a("| --- | --- |")
            a(f"| Mediana | {_fmt(float(valid_ratio.median()), 2)} |")
            a(f"| Media | {_fmt(float(valid_ratio.mean()), 2)} |")
            a(f"| Min | {_fmt(float(valid_ratio.min()), 2)} |")
            a(f"| Max | {_fmt(float(valid_ratio.max()), 2)} |")
            a(f"| P25 | {_fmt(float(valid_ratio.quantile(0.25)), 2)} |")
            a(f"| P75 | {_fmt(float(valid_ratio.quantile(0.75)), 2)} |")
            a("")

    a("## Diagnostico secundario — diferenca bruta de populacao")
    a("")
    a("Registrado apenas para rastreabilidade. Nao usar como KPI de comparacao pois as areas sao distintas.")
    a("")
    if not comp.empty:
        valid_delta_pop = pd.to_numeric(comp["delta_pop_hex_vs_geofusion"], errors="coerce").dropna()
        if not valid_delta_pop.empty:
            a(f"- Mediana delta pop: {_fmt(float(valid_delta_pop.median()))} hab")
            a(f"- Media delta pop: {_fmt(float(valid_delta_pop.mean()))} hab")
            a("")

    sem_geo = df[df["flag_sem_geofusion"]]
    if not sem_geo.empty:
        a("## Unidades sem dado GeoFusion")
        a("")
        for _, row in sem_geo.iterrows():
            a(f"- **{row['unidade']}** ({row['uf']}): `pop_geofusion_1km` ausente")
        a("")

    sem_coord = df[df["flag_sem_coord"]]
    if not sem_coord.empty:
        a("## Unidades sem coordenada (sem hex_id_res7)")
        a("")
        for _, row in sem_coord.iterrows():
            a(f"- **{row['unidade']}** ({row['uf']}): `{row['fonte_pop_hex_base']}`")
        a("")

    sem_pop_com_coord = df[df["flag_sem_pop_hex"] & ~df["flag_sem_coord"]]
    if not sem_pop_com_coord.empty:
        a("## Unidades com coordenada mas sem populacao de hex")
        a("")
        a("Coordenada existe mas hex nao foi encontrado na camada de mercado.")
        a("")
        for _, row in sem_pop_com_coord.iterrows():
            a(f"- **{row['unidade']}** ({row['uf']}): `{row['fonte_pop_hex_base']}`")
        a("")

    a("## Areas registradas no output")
    a("")
    a(f"- `area_geofusion_km2`: {GEOFUSION_AREA_KM2} km2 (constante; pi x r^2 com r=1km)")
    area_vals = pd.to_numeric(df["area_hex_km2"], errors="coerce").dropna()
    if not area_vals.empty:
        a(
            f"- `area_hex_km2`: min={_fmt(float(area_vals.min()), 3)}, "
            f"max={_fmt(float(area_vals.max()), 3)}, "
            f"mediana={_fmt(float(area_vals.median()), 3)} km2"
        )
    a("")
    a("_Gerado por `jobs/pipelines/comparar_geofusion_vs_hex.py`_")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Relatorio salvo: {path}")


def validar(df: pd.DataFrame) -> None:
    print("\n=== Validacao: comparacao GeoFusion vs hex ===")
    print(f"Total de linhas: {len(df)}")

    faltam = set(OUTPUT_COLS) - set(df.columns)
    assert not faltam, f"Colunas ausentes: {sorted(faltam)}"
    print("Schema OK")

    dens_hex = pd.to_numeric(df["densidade_hex_km2"], errors="coerce")
    dens_geo = pd.to_numeric(df["densidade_geofusion_1km_calc"], errors="coerce")
    assert (dens_hex.dropna() >= 0).all(), "densidade_hex_km2 negativa"
    assert (dens_geo.dropna() >= 0).all(), "densidade_geofusion_1km_calc negativa"
    print("Densidades nao negativas OK")

    assert (df["area_geofusion_km2"] == GEOFUSION_AREA_KM2).all(), "area_geofusion_km2 inconsistente"
    com_hex = df["hex_id_res7"].notna()
    assert df.loc[com_hex, "area_hex_km2"].notna().all(), "area_hex_km2 ausente para hex valido"
    print("Areas registradas OK")

    n_sem_geo = int(df["flag_sem_geofusion"].sum())
    n_sem_coord = int(df["flag_sem_coord"].sum())
    n_sem_pop = int(df["flag_sem_pop_hex"].sum())
    n_comp = int((~df["flag_sem_geofusion"] & ~df["flag_sem_pop_hex"]).sum())
    print(f"Sem GeoFusion: {n_sem_geo} | Sem coord: {n_sem_coord} | Sem pop hex: {n_sem_pop} | Comparaveis: {n_comp}")
    print("Validacao OK")


def main() -> None:
    print("Bloco 3 - Comparar GeoFusion 1km vs populacao do hex")
    print("=" * 55)

    df = gerar_comparacao(PERF_HEX_PATH)
    validar(df)
    escrever_relatorio(df, REPORT_PATH)
    print("Bloco 3 concluido.")


if __name__ == "__main__":
    main()
