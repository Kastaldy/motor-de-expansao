"""Gera o relatório trimestral dos masters (PDF por master + `_manifest.json`).

Uso local (teste com um master):
    python scripts/gerar_relatorio_masters.py --master gempro

No servidor (cron trimestral), todos os masters:
    python scripts/gerar_relatorio_masters.py --todos --oficial

Os caminhos têm padrão no layout do repo e podem vir por opção ou variável de ambiente.
Camada paralela, READ-ONLY sobre o M1.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import click

from motor_expansao.masters.gerar import Entradas, gerar
from motor_expansao.masters.territorios import carregar_territorios

ROOT = Path(__file__).resolve().parents[1]


def _p(envvar: str, padrao: str) -> dict:
    return {
        "type": click.Path(path_type=Path),
        "envvar": envvar,
        "default": ROOT / padrao,
        "show_default": True,
    }


@click.command()
@click.option(
    "--master",
    "ids",
    multiple=True,
    help="id do master (repetível). Sem --master nem --todos: sorteia um.",
)
@click.option("--todos", is_flag=True, help="Gera para todos os masters da config.")
@click.option(
    "--por-regiao",
    is_flag=True,
    help="Um relatório por região dos masters com mais de uma (ex.: RJ/SP 01 sai em RJ e em SP).",
)
@click.option("--oficial", is_flag=True, help="Tira o selo 'versão de teste' da capa.")
@click.option(
    "--modelo",
    type=click.Choice(["antigo", "novo", "so_novos"]),
    default="antigo",
    show_default=True,
    help="antigo = 10 slides; novo = + slides de funcionamento da região; so_novos = só os slides a mais (teste).",
)
@click.option(
    "--planilha",
    **_p("MASTERS_PLANILHA", "data/ultra/masters/Masters_Ultra_Territorios_e_Unidades.xlsx"),
)
@click.option("--territorios", **_p("MASTERS_TERRITORIOS", "data/ultra/masters/territorios.json"))
@click.option(
    "--mercado", **_p("MASTERS_MERCADO", "data/staging/hexagonos_mercado_mapeado.parquet")
)
@click.option(
    "--concorrentes", **_p("MASTERS_CONCORRENTES", "data/staging/concorrentes_mapeados.parquet")
)
@click.option("--dim-unidade", **_p("MASTERS_DIM_UNIDADE", "data/staging/dim_unidade.parquet"))
@click.option(
    "--fato-unidade-mes", **_p("MASTERS_FATO_UNIDADE_MES", "data/staging/fato_unidade_mes.parquet")
)
@click.option("--ultra", **_p("MASTERS_ULTRA", "data/staging/unidades_ultra_mapeadas.parquet"))
@click.option(
    "--censo-geo-dir", **_p("MASTERS_CENSO_GEO_DIR", "data/outputs/setores_censitarios_2022_geo")
)
@click.option("--staging-dir", **_p("MASTERS_STAGING_DIR", "data/staging"))
@click.option("--assets-dir", **_p("MASTERS_ASSETS_DIR", "data/ultra"))
@click.option("--saida", **_p("MASTERS_SAIDA", "data/ultra/masters/relatorios"))
def main(
    ids: tuple[str, ...],
    todos: bool,
    por_regiao: bool,
    oficial: bool,
    modelo: str,
    planilha: Path,
    territorios: Path,
    mercado: Path,
    concorrentes: Path,
    dim_unidade: Path,
    fato_unidade_mes: Path,
    ultra: Path,
    censo_geo_dir: Path,
    staging_dir: Path,
    assets_dir: Path,
    saida: Path,
) -> None:
    masters = carregar_territorios(territorios)
    if todos:
        escolhidos = list(masters.values())
    elif ids:
        faltando = [i for i in ids if i not in masters]
        if faltando:
            raise click.BadParameter(f"master desconhecido: {faltando}; opções: {sorted(masters)}")
        escolhidos = [masters[i] for i in ids]
    else:
        escolhidos = [random.choice([m for m in masters.values() if m.regioes])]
        click.echo(f"Master sorteado: {escolhidos[0].id}")
    e = Entradas(
        planilha,
        territorios,
        mercado,
        concorrentes,
        dim_unidade,
        fato_unidade_mes,
        ultra=ultra,
        censo_geo_dir=censo_geo_dir,
        staging_dir=staging_dir,
        assets_dir=assets_dir,
    )
    manifesto = gerar(e, escolhidos, saida, teste=not oficial, modelo=modelo, por_regiao=por_regiao)
    click.echo(json.dumps(manifesto, ensure_ascii=False, indent=2, default=str))
    if any(r["status"] == "erro" for r in manifesto["relatorios"]):
        sys.exit(1)


if __name__ == "__main__":
    main()
