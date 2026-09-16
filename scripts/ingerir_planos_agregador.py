"""Ingere os CSVs de planos dos agregadores (TotalPass ou Wellhub) para o staging do piloto.

Uso:
    python scripts/ingerir_planos_agregador.py totalpass C:/caminho/unidades_totalpass.csv
    python scripts/ingerir_planos_agregador.py wellhub C:/caminho/unidades_wellhub_*.csv

Entrada: um ou mais CSVs do coletor, `sep=";"`, UTF-8, com as colunas de
`planos_agregador.colunas_obrigatorias(fonte)`. O Wellhub vem em um arquivo por UF; os
arquivos são concatenados antes de normalizar. Saída: `planos_<fonte>.parquet` no staging do
perfil ativo (`MOTOR_DATA_DIR`, ou o `data/` do repositório em dev).

READ-ONLY sobre o M1: grava um artefato NOVO e paralelo, não lê nem escreve artefato oficial.
"""

from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from motor_expansao.dashboard import planos_agregador  # noqa: E402


def _expandir(padroes: list[str]) -> list[Path]:
    """Aceita caminhos e padrões (o PowerShell não expande `*` para o Python)."""
    arquivos: list[Path] = []
    for padrao in padroes:
        achados = sorted(glob.glob(padrao))
        arquivos.extend(Path(a) for a in (achados or [padrao]))
    return arquivos


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("fonte", choices=sorted(planos_agregador.FONTES), help="agregador dos CSVs")
    parser.add_argument("csv", nargs="+", help="CSV(s) do coletor; aceita padrão com *")
    parser.add_argument("--saida", type=Path, default=None, help="parquet de destino")
    args = parser.parse_args(argv)

    arquivos = _expandir(args.csv)
    bruto = pd.concat(
        [pd.read_csv(a, sep=";", dtype=str, encoding="utf-8-sig") for a in arquivos], ignore_index=True
    )
    quadro = planos_agregador.normalizar(bruto, args.fonte)

    if args.saida is None:
        from motor_expansao.perfil import resolver_perfil

        args.saida = resolver_perfil().raiz / "staging" / planos_agregador.arquivo_staging(args.fonte)
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    quadro.to_parquet(args.saida, index=False)

    sem_preco = int(quadro["preco"].isna().sum())
    print(
        f"{args.fonte}: {len(quadro)} academias de {len(arquivos)} arquivo(s) gravadas em {args.saida} "
        f"({len(bruto) - len(quadro)} descartadas sem coordenada/duplicadas; {sem_preco} sem preço válido; "
        f"coleta {', '.join(sorted(quadro['data_coleta'].unique()))})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
