"""Ingere a tabela de comodidades das concorrentes para o staging do piloto.

Uso:
    python scripts/ingerir_comodidades_concorrentes.py C:/caminho/comodidades_concorrentes.csv

Entrada: o CSV do coletor (repositório GymScraping, `Comodidades/comodidades_concorrentes.csv`),
`sep=";"`, UTF-8, com as colunas de `comodidades_concorrentes.COLUNAS_OBRIGATORIAS`. Saída:
`comodidades_concorrentes.parquet` no staging do perfil ativo (`MOTOR_DATA_DIR`, ou o `data/` do
repositório em dev).

READ-ONLY sobre o M1: grava um artefato NOVO e paralelo, não lê nem escreve artefato oficial.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from motor_expansao.dashboard import comodidades_concorrentes  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("csv", type=Path, help="CSV de comodidades do coletor")
    parser.add_argument("--saida", type=Path, default=None, help="parquet de destino")
    args = parser.parse_args(argv)

    bruto = pd.read_csv(args.csv, sep=";", dtype=str, encoding="utf-8-sig")
    quadro = comodidades_concorrentes.normalizar(bruto)

    if args.saida is None:
        from motor_expansao.perfil import resolver_perfil

        args.saida = resolver_perfil().raiz / "staging" / comodidades_concorrentes.ARQUIVO_STAGING
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    quadro.to_parquet(args.saida, index=False)

    por_canal = ", ".join(f"{canal} {n}" for canal, n in quadro["canal"].value_counts().items())
    print(
        f"comodidades: {len(quadro)} linhas gravadas em {args.saida} ({por_canal}; "
        f"{len(bruto) - len(quadro)} descartadas por coordenada ausente ou reprovada; "
        f"coleta {', '.join(sorted(quadro['data_coleta'].unique()))})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
