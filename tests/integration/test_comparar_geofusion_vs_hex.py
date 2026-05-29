"""
Teste minimo - Bloco 3: comparar GeoFusion 1km vs populacao do hex.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from jobs.pipelines import comparar_geofusion_vs_hex as modulo

ROOT = Path(__file__).resolve().parents[2]
# gerar_comparacao() le este parquet (PERF_HEX_PATH em comparar_geofusion_vs_hex.py)
PERF_HEX_PATH = ROOT / "data" / "staging" / "unidades_ultra_performance_hex.parquet"

SCHEMA_OBRIGATORIO = {
    "unidade",
    "uf",
    "hex_id_res7",
    "area_geofusion_km2",
    "pop_geofusion_1km",
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
}


@pytest.fixture(scope="module")
def df() -> pd.DataFrame:
    if not PERF_HEX_PATH.exists():
        pytest.skip("unidades_ultra_performance_hex.parquet ausente (dados reais)")
    return modulo.gerar_comparacao()


def test_schema_minimo(df: pd.DataFrame):
    assert SCHEMA_OBRIGATORIO <= set(df.columns), f"Colunas faltando: {SCHEMA_OBRIGATORIO - set(df.columns)}"


def test_preserva_total_de_unidades(df: pd.DataFrame):
    assert len(df) == 54


def test_densidades_nao_negativas(df: pd.DataFrame):
    assert (pd.to_numeric(df["densidade_hex_km2"], errors="coerce").dropna() >= 0).all()
    assert (pd.to_numeric(df["densidade_geofusion_1km_calc"], errors="coerce").dropna() >= 0).all()


def test_area_geofusion_constante_registrada(df: pd.DataFrame):
    assert (df["area_geofusion_km2"] == modulo.GEOFUSION_AREA_KM2).all()


def test_area_hex_presente_para_hexes_validos(df: pd.DataFrame):
    com_hex = df["hex_id_res7"].notna()
    assert df.loc[com_hex, "area_hex_km2"].notna().all()
    assert (pd.to_numeric(df.loc[com_hex, "area_hex_km2"], errors="coerce") > 0).all()


def test_flags_dtype_bool(df: pd.DataFrame):
    assert df["flag_sem_geofusion"].dtype == bool
    assert df["flag_sem_coord"].dtype == bool
    assert df["flag_sem_pop_hex"].dtype == bool


def test_densidade_hex_formula(df: pd.DataFrame):
    comp = df[~df["flag_sem_coord"] & ~df["flag_sem_pop_hex"]].copy()
    assert not comp.empty
    expected = pd.to_numeric(comp["pop_hex_base"], errors="coerce") / pd.to_numeric(comp["area_hex_km2"], errors="coerce")
    pd.testing.assert_series_equal(
        pd.to_numeric(comp["densidade_hex_km2"], errors="coerce").reset_index(drop=True),
        expected.reset_index(drop=True),
        check_names=False,
        rtol=1e-5,
    )


def test_densidade_geofusion_formula(df: pd.DataFrame):
    comp = df[~df["flag_sem_geofusion"]].copy()
    expected = pd.to_numeric(comp["pop_geofusion_1km"], errors="coerce") / modulo.GEOFUSION_AREA_KM2
    pd.testing.assert_series_equal(
        pd.to_numeric(comp["densidade_geofusion_1km_calc"], errors="coerce").reset_index(drop=True),
        expected.reset_index(drop=True),
        check_names=False,
        rtol=1e-5,
    )


def test_comparaveis_existem(df: pd.DataFrame):
    n_comp = int((~df["flag_sem_geofusion"] & ~df["flag_sem_pop_hex"]).sum())
    assert n_comp > 0, "Nenhuma unidade comparavel (com GeoFusion e pop hex)"


def test_calcular_comparacao_unit():
    base = pd.DataFrame({
        "unidade": ["A", "B", "C"],
        "uf": ["SP", "SP", "RJ"],
        "hex_id_res7": ["87a8100e3ffffff", None, "87a8952a6ffffff"],
        "pop_geofusion_1km": [10000.0, np.nan, 5000.0],
        "densidade_geofusion_1km_km2": [3185.0, np.nan, 1592.0],
        "pop_hex_base": [30000.0, np.nan, np.nan],
        "fonte_pop_hex_base": ["censo_2022_hex", "sem_hex_id_res7", "hex_nao_encontrado"],
    })
    result = modulo.calcular_comparacao(base)

    # A: tem GeoFusion e pop hex — comparavel
    assert not result.loc[0, "flag_sem_geofusion"]
    assert not result.loc[0, "flag_sem_coord"]
    assert not result.loc[0, "flag_sem_pop_hex"]
    assert result.loc[0, "area_geofusion_km2"] == modulo.GEOFUSION_AREA_KM2
    assert pd.notna(result.loc[0, "area_hex_km2"])
    assert pd.notna(result.loc[0, "densidade_hex_km2"])
    assert pd.notna(result.loc[0, "ratio_densidade_hex_geofusion"])
    assert result.loc[0, "densidade_geofusion_1km_calc"] == pytest.approx(10000.0 / modulo.GEOFUSION_AREA_KM2, rel=1e-5)

    # B: sem coord (hex_id_res7=None), sem GeoFusion, sem pop hex
    assert result.loc[1, "flag_sem_geofusion"]
    assert result.loc[1, "flag_sem_coord"]
    assert result.loc[1, "flag_sem_pop_hex"]
    assert pd.isna(result.loc[1, "area_hex_km2"])
    assert pd.isna(result.loc[1, "densidade_geofusion_1km_calc"])
    assert pd.isna(result.loc[1, "densidade_hex_km2"])

    # C: tem GeoFusion e coord, mas sem pop hex (hex_nao_encontrado)
    assert not result.loc[2, "flag_sem_geofusion"]
    assert not result.loc[2, "flag_sem_coord"]
    assert result.loc[2, "flag_sem_pop_hex"]
    assert pd.notna(result.loc[2, "area_hex_km2"])
    assert pd.notna(result.loc[2, "densidade_geofusion_1km_calc"])
    assert pd.isna(result.loc[2, "densidade_hex_km2"])
    assert pd.isna(result.loc[2, "ratio_densidade_hex_geofusion"])


def test_relatorio_gerado(df: pd.DataFrame, tmp_path: Path):
    report_path = tmp_path / "validacao_geofusion_vs_hex.md"
    modulo.escrever_relatorio(df, report_path)
    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")
    assert "densidade" in content.lower()
    assert "area_geofusion_km2" in content
    assert "area_hex_km2" in content
    assert str(modulo.GEOFUSION_AREA_KM2) in content


def test_validar_nao_falha(df: pd.DataFrame):
    modulo.validar(df)
