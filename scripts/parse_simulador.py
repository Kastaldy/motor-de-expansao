"""Parse OFFLINE do simulador -> data/staging/simulador_estrutura.json (COMMITABLE, D2).

Le o `.xlsx` real (gitignored, local) e serializa SO a estrutura parametrica
(metadado, sem PII nem dado financeiro real de unidade). NAO entra no CI (testes
usam fixture sintetica). READ-ONLY sobre o M1.
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from motor_expansao.dimensionamento import config
from motor_expansao.dimensionamento.simulador_parser import XLSX_DEFAULT, parse_simulador

OUT_JSON = config.STAGING_DIR / "simulador_estrutura.json"


@click.command()
@click.option("--xlsx", default=str(XLSX_DEFAULT), show_default=True)
def main(xlsx: str) -> None:
    if not Path(xlsx).is_file():
        raise click.ClickException(f"Simulador .xlsx ausente: {xlsx}")
    estrutura = parse_simulador(xlsx)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUT_JSON.open("w", encoding="utf-8") as fh:
        json.dump(estrutura, fh, ensure_ascii=False, indent=2)
    click.echo(f"Escrito: {OUT_JSON}")
    click.echo(f"drivers: {len(estrutura['drivers'])}")
    click.echo(f"ratios_dre: {len(estrutura['ratios_dre'])}")
    click.echo(f"impostos_presumido: {len(estrutura['impostos_presumido'])}")
    # amostra de conferencia
    for k in ("mensalidade", "capex_total", "royalties_pct"):
        click.echo(f"  {k}: {estrutura['drivers'][k]}")


if __name__ == "__main__":
    main()
