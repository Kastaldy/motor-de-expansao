"""Consolidacao OFFLINE -> data/staging/base_calibracao_maduras.parquet.

Le os 3 parquets de staging (performance READ-ONLY, historico, catchment) e grava
a base de calibracao por unidade. NAO entra no CI (testes usam fixtures sinteticas).
ZERO PII em disco; READ-ONLY sobre o M1.
"""

from __future__ import annotations

from pathlib import Path

import click
import pandas as pd

from motor_expansao.dimensionamento import config
from motor_expansao.dimensionamento.calibracao_maduras import (
    consolidar_base_calibracao,
    resumo_consolidacao,
)
from motor_expansao.dimensionamento.growth_api_client import assert_sem_pii

PERF_PARQUET = Path("data/staging/unidades_ultra_performance_hex.parquet")
HIST_PARQUET = config.STAGING_DIR / "growth_api_historico.parquet"
CATCH_PARQUET = config.STAGING_DIR / "unidades_ultra_catchment.parquet"
OUT_PARQUET = config.STAGING_DIR / "base_calibracao_maduras.parquet"


@click.command()
@click.option("--n-meses-steady", default=config.N_MESES_STEADY, show_default=True, type=int)
@click.option("--meses-madura", default=config.MESES_MADURA, show_default=True, type=int)
def main(n_meses_steady: int, meses_madura: int) -> None:
    for nome, caminho in (
        ("performance", PERF_PARQUET),
        ("historico", HIST_PARQUET),
        ("catchment", CATCH_PARQUET),
    ):
        if not caminho.is_file():
            raise click.ClickException(f"Parquet {nome} ausente: {caminho}")

    perf = pd.read_parquet(PERF_PARQUET)
    hist = pd.read_parquet(HIST_PARQUET)
    catch = pd.read_parquet(CATCH_PARQUET)

    base = consolidar_base_calibracao(
        perf, hist, catch, n_meses_steady=n_meses_steady, meses_madura=meses_madura
    )

    assert_sem_pii(base)
    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    base.to_parquet(OUT_PARQUET, index=False)

    res = resumo_consolidacao(base)
    click.echo("\n=== AUDITORIA base_calibracao_maduras.parquet ===")
    click.echo(f"arquivo: {OUT_PARQUET}")
    click.echo(f"unidades: {res['n_unidades']}")
    click.echo(f"% inauguracao real: {res['pct_inauguracao_real']}%")
    click.echo(f"unidades maduras (>= {meses_madura} meses): {res['n_maduras']}")
    click.echo(
        f"meses_desde_inauguracao: nunique={res['meses_desde_inauguracao_nunique']} "
        f"min={res['meses_min']} max={res['meses_max']}"
    )
    click.echo(f"unidades com lacunas: {res['n_com_lacunas']}")


if __name__ == "__main__":
    main()
