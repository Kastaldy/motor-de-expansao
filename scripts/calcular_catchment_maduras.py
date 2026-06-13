"""Catchment OFFLINE das unidades -> data/staging/unidades_ultra_catchment.parquet.

Roda local (cruzamento geometrico real, ~54 unidades x setores por UF). NAO entra
no CI (testes usam mock de `analisar_ponto_censitario_setores`). READ-ONLY sobre
o M1; raio 1,5 km e metodo de intersecao INTOCADOS.
"""

from __future__ import annotations

from pathlib import Path

import click
import pandas as pd

from motor_expansao.dimensionamento import config
from motor_expansao.dimensionamento.catchment_batch import (
    GEO_BASE_DIR_DEFAULT,
    calcular_catchment_batch,
)
from motor_expansao.dimensionamento.growth_api_client import assert_sem_pii

PERF_PARQUET = Path("data/staging/unidades_ultra_performance_hex.parquet")
OUT_PARQUET = config.STAGING_DIR / "unidades_ultra_catchment.parquet"


@click.command()
@click.option("--raio-km", default=config.RAIO_CATCHMENT_KM, show_default=True, type=float)
@click.option("--geo-base-dir", default=str(GEO_BASE_DIR_DEFAULT), show_default=True)
def main(raio_km: float, geo_base_dir: str) -> None:
    if not PERF_PARQUET.is_file():
        raise click.ClickException(f"Performance parquet ausente: {PERF_PARQUET}")
    perf = pd.read_parquet(
        PERF_PARQUET, columns=["unidade", "uf", "cidade", "lat", "lng"]
    )
    click.echo(f"Calculando catchment de {len(perf)} unidades (raio {raio_km} km)...")
    df = calcular_catchment_batch(perf, geo_base_dir=Path(geo_base_dir), raio_km=raio_km)

    assert_sem_pii(df)
    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PARQUET, index=False)

    n_null = int(df["pop_captacao"].isna().sum())
    click.echo("\n=== AUDITORIA unidades_ultra_catchment.parquet ===")
    click.echo(f"arquivo: {OUT_PARQUET}")
    click.echo(f"unidades: {len(df)}")
    click.echo(f"com catchment valido: {len(df) - n_null}")
    click.echo(f"sem catchment (lat/lng NULL ou sem setor): {n_null}")
    if n_null:
        faltantes = df.loc[df["pop_captacao"].isna(), "unidade"].tolist()
        click.echo(f"unidades sem catchment: {faltantes}")
    validos = df.loc[df["pop_captacao"].notna()]
    if not validos.empty:
        click.echo(
            f"pop_captacao: min={validos['pop_captacao'].min():.0f} "
            f"mediana={validos['pop_captacao'].median():.0f} "
            f"max={validos['pop_captacao'].max():.0f}"
        )


if __name__ == "__main__":
    main()
