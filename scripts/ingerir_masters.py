"""Ingestão da planilha dos masters -> data/staging/masters_*.parquet (DEC-089).

O piloto (tela Masters) lê estes parquets, e não a planilha, que é CONFIDENCIAL: daqui sai só o
que a tela mostra, com o nome do master (o titular sem o território) e sem o texto livre da área
(ver `motor_expansao.masters.ingestao`).

Fluxo (quando a planilha de levantamento muda):

  1. A planilha nova fica em `data/ultra/masters/Masters_Ultra_Territorios_e_Unidades.xlsx` e a
     config em `data/ultra/masters/territorios.json` (os dois gitignored).
  2. Este script lê, valida e grava os três parquets + o manifesto em `data/staging/`. Qualquer
     falta (aba, coluna, master fora da config) ABORTA sem escrever.
  3. O Felipe leva os quatro arquivos à staging da VPS (scp, um comando por vez, com a confirmação
     dele) e o piloto passa a mostrá-los no próximo `limpar_caches` ou restart.

As datas de inauguração NÃO vêm daqui: o piloto as tira da base do Growth, que o motor atualiza
todo dia.

Uso:
    python scripts/ingerir_masters.py
    python scripts/ingerir_masters.py --planilha <xlsx> --territorios <json> --saida <pasta>
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from motor_expansao.masters.ingestao import IngestaoRecusada, gravar, montar_tabelas

PLANILHA = Path("data/ultra/masters/Masters_Ultra_Territorios_e_Unidades.xlsx")
TERRITORIOS = Path("data/ultra/masters/territorios.json")
SAIDA = Path("data/staging")


@click.command()
@click.option("--planilha", type=click.Path(path_type=Path), default=PLANILHA, show_default=True)
@click.option(
    "--territorios", type=click.Path(path_type=Path), default=TERRITORIOS, show_default=True
)
@click.option("--saida", type=click.Path(path_type=Path), default=SAIDA, show_default=True)
def main(planilha: Path, territorios: Path, saida: Path) -> None:
    for caminho in (planilha, territorios):
        if not caminho.exists():
            click.echo(f"ERRO: {caminho} não existe", err=True)
            sys.exit(2)
    try:
        tabelas = montar_tabelas(planilha, territorios)
    except IngestaoRecusada as erro:
        click.echo(f"ERRO: ingestão recusada, nada foi gravado: {erro}", err=True)
        sys.exit(1)
    for arquivo in gravar(tabelas, saida):
        click.echo(f"gravado: {arquivo}")
    c = tabelas.manifesto["contagens"]
    click.echo(
        f"{c['masters']} masters, {c['inauguradas']} inauguradas e {c['pipeline']} assinadas "
        f"(planilha de {tabelas.manifesto['planilha']['modificada_em']})"
    )


if __name__ == "__main__":
    main()
