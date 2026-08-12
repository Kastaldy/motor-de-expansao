"""Ingestao MENSAL da planilha do Financeiro -> data/staging/faturamento_financeiro.parquet.

A planilha e' a base sobre a qual os royalties sao cobrados e e' a fonte correta do
faturamento da rede; a Growth subdimensiona em ~20% e nao carrega mais a receita de
agregador (ver `motor_expansao.dashboard.rede_faturamento_financeiro`).

Fluxo (roda uma vez por mes, depois que o mes virou):

  1. Felipe baixa a planilha do SharePoint e solta em `data/raw/financeiro/`.
     O download NAO e' automatizado de proposito: o arquivo mora no OneDrive PESSOAL de
     outra pessoa e chega por link compartilhado -- um alvo que quebra sozinho quando ele
     renomeia, move ou revoga. Este script trata o arquivo como entrada, nao como fonte.
  2. Pega o .xlsx mais RECENTE da pasta (ou o caminho passado em `--planilha`).
  3. Le so' as abas `Faturamento & Alunos` e `Unidades_UX`. As abas de cadastro tem CNPJ,
     razao social e nome de franqueado: NADA disso e' lido, e nada disso vai para o disco.
  4. Valida. Qualquer achado de nivel `erro` ABORTA sem escrever -- em especial o mes
     ainda ABERTO, que gravaria uma competencia pela metade como se fosse definitiva.
  5. Compara com o parquet anterior e denuncia reescrita de mes ja fechado.
  6. Grava o parquet + um manifesto JSON com a procedencia (arquivo, sha256, competencias).

Uso:
    python scripts/ingerir_faturamento_financeiro.py
    python scripts/ingerir_faturamento_financeiro.py --planilha ~/Downloads/ULTRA\\ -\\ ....xlsx
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import click
import pandas as pd

from motor_expansao.dashboard import rede_faturamento_financeiro as fin

ENTRADA_DIR = Path("data/raw/financeiro")
OUT_PARQUET = Path("data/staging/faturamento_financeiro.parquet")


def manifesto_de(saida: Path) -> Path:
    """O manifesto anda SEMPRE colado ao parquet que ele descreve.

    Era um caminho fixo: rodar com `--saida` apontando para outro arquivo gravava o parquet
    no destino pedido e sobrescrevia o manifesto de PRODUCAO com a procedencia (sha256,
    competencias) de um arquivo que nao era o que estava la'. Parquet e manifesto
    dessincronizados sao piores que manifesto nenhum -- ele existe justamente para dizer de
    qual planilha aquele parquet saiu.
    """
    return saida.with_suffix(".json")


def achar_planilha(pasta: Path) -> Path:
    """O .xlsx mais recente da pasta. Ignora os temporarios do Excel (`~$...`)."""
    if not pasta.exists():
        raise SystemExit(
            f"pasta {pasta} nao existe.\n"
            f"  crie-a e solte ali a planilha do Financeiro:  mkdir -p {pasta}"
        )
    candidatos = [p for p in pasta.glob("*.xlsx") if not p.name.startswith("~$")]
    if not candidatos:
        raise SystemExit(f"nenhum .xlsx em {pasta} -- baixe a planilha do Financeiro e solte ali.")
    return max(candidatos, key=lambda p: p.stat().st_mtime)


def sha256_de(caminho: Path) -> str:
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1 << 20), b""):
            digest.update(bloco)
    return digest.hexdigest()


@click.command()
@click.option("--planilha", type=click.Path(exists=True, dir_okay=False, path_type=Path), default=None,
              help="Caminho do .xlsx. Sem isto, pega o mais recente de data/raw/financeiro/.")
@click.option("--saida", type=click.Path(dir_okay=False, path_type=Path), default=OUT_PARQUET, show_default=True)
@click.option("--hoje", type=click.DateTime(formats=["%Y-%m-%d"]), default=None,
              help="Data de referencia do gate de mes fechado (para teste).")
@click.option("--permitir-mes-aberto", is_flag=True,
              help="NAO use em producao: grava mesmo com a ultima competencia em curso.")
@click.option("--simular", is_flag=True, help="Valida e relata, sem escrever nada.")
def main(planilha: Path | None, saida: Path, hoje: datetime | None,
         permitir_mes_aberto: bool, simular: bool) -> None:
    """Le a planilha do Financeiro, valida e grava o parquet de faturamento oficial."""
    origem = planilha or achar_planilha(ENTRADA_DIR)
    idade_dias = (datetime.now().timestamp() - origem.stat().st_mtime) / 86400
    click.echo(f"planilha : {origem}")
    click.echo(f"           {origem.stat().st_size / 1e6:.2f} MB, baixada ha {idade_dias:.1f} dia(s)")

    fat = fin.ler_planilha(origem)
    meses = sorted(fat["competencia"].dropna().unique())
    click.echo(
        f"lido     : {len(fat):,} linhas | {fat['unidade_planilha'].nunique()} unidades | "
        f"{len(meses)} competencias ({meses[0]} .. {meses[-1]})"
    )

    anterior = fin.carregar(saida)
    referencia: date | None = hoje.date() if hoje else None
    achados = fin.validar(fat, hoje=referencia, anterior=anterior if len(anterior) else None)

    erros = [a for a in achados if a.eh_erro]
    if permitir_mes_aberto:
        erros = [a for a in erros if a.codigo != "mes_aberto"]
    click.echo("")
    for achado in achados:
        cor = "red" if achado.eh_erro else "yellow"
        click.secho(f"  {achado}", fg=cor)
    if not achados:
        click.secho("  sem achados", fg="green")

    if erros:
        click.secho(f"\nABORTADO: {len(erros)} erro(s). Nada foi escrito.", fg="red", bold=True)
        sys.exit(1)

    ultima = meses[-1]
    do_mes = fat[fat["competencia"] == ultima]

    def zerado(coluna: str) -> pd.Series:
        """`to_numeric` antes do `fillna`: componente inteiramente vazia chega como coluna
        de objeto, e somar objeto com float dispara downcast silencioso no pandas."""
        return pd.to_numeric(do_mes[coluna], errors="coerce").fillna(0.0)

    agregador = zerado("gympass") + zerado("totalpass") - zerado("tem_saude")
    click.echo(
        f"\n{ultima}: R$ {do_mes['faturamento'].sum():,.2f} em "
        f"{int((zerado('faturamento') > 0).sum())} unidades "
        f"(agregador R$ {agregador.sum():,.2f})"
    )

    if simular:
        click.secho("\n--simular: nada gravado.", fg="cyan")
        return

    saida.parent.mkdir(parents=True, exist_ok=True)
    fat.to_parquet(saida, index=False)
    manifesto = {
        "gerado_em": datetime.now(UTC).isoformat(timespec="seconds"),
        "planilha": origem.name,
        "sha256": sha256_de(origem),
        "linhas": int(len(fat)),
        "unidades": int(fat["unidade_planilha"].nunique()),
        "competencia_inicio": meses[0],
        "competencia_fim": ultima,
        "avisos": [str(a) for a in achados],
    }
    destino_manifesto = manifesto_de(saida)
    destino_manifesto.parent.mkdir(parents=True, exist_ok=True)
    destino_manifesto.write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    click.secho(f"\ngravado: {saida}  ({len(fat):,} linhas)", fg="green")
    click.echo(f"manifesto: {destino_manifesto}")


if __name__ == "__main__":
    main()
