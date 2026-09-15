"""Ingere o pacote de movimentação da concorrência para o staging do piloto.

Uso:
    python scripts/ingerir_movimentacao_concorrencia.py "C:/.../Movimentacao_Concorrencia"

Aceita a pasta do pacote ou a subpasta `movimentacao/`. Saída no staging do perfil ativo:
`movimentacao_concorrencia.parquet` e, se houver `series/`, `contagem_redes_concorrencia.parquet`. READ-ONLY sobre o M1.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from motor_expansao.dashboard import movimentacao_concorrencia as mov  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pasta", type=Path, help="pasta do pacote (ou a subpasta movimentacao/)")
    parser.add_argument("--saida", type=Path, default=None, help="parquet de destino")
    args = parser.parse_args(argv)

    if args.pasta.name == "movimentacao":
        args.pasta = args.pasta.parent
    pasta = args.pasta / "movimentacao" if (args.pasta / "movimentacao").is_dir() else args.pasta
    quadro = mov.montar(pasta)
    if args.saida is None:
        from motor_expansao.perfil import resolver_perfil

        args.saida = resolver_perfil().raiz / "staging" / mov.ARQUIVO_STAGING
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    quadro.to_parquet(args.saida, index=False)

    serie = args.pasta / "series" / mov.ARQUIVO_CONTAGEM
    if serie.is_file():
        import pandas as pd

        tabela = pd.read_csv(serie, sep=None, engine="python", encoding="utf-8-sig")
        contagem = mov.contagem_oficial(tabela, mov.fim_validado(quadro))
        destino = args.saida.parent / mov.ARQUIVO_CONTAGEM_STAGING
        contagem.to_parquet(destino, index=False)
        print(f"contagem oficial de {len(contagem)} redes em {contagem['data'].iloc[0] if len(contagem) else '-'} -> {destino}")
    else:
        print(f"sem {serie}: a coluna de total de unidades fica vazia")

    resumo = quadro.groupby(["fonte", "tipo", "confianca"]).size()
    print(f"{len(quadro)} eventos gravados em {args.saida}")
    print(resumo.to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
