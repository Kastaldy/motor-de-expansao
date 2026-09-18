"""Gate de igualdade do artefato geo: prova que o rerun so' mudou o que deveria.

Por que existe
--------------
O artefato `setores_censitarios_2022_geo` alimenta `score_setor_2022_calibrado`, a camada
PRIMARIA no uso operacional (CLAUDE.md §1). Regerar 468 mil linhas para acrescentar UMA coluna
e' seguro em tese -- o `k` de calibracao e' nacional e o percentil vem do `brasil_estrutural`,
entao o rerun e' deterministico --, mas "em tese" nao e' garantia. Sem medir, um desvio em
qualquer score entraria em producao sem ninguem ver.

Este script compara o artefato ANTIGO com o NOVO, particao por particao, e exige que a unica
diferenca seja a esperada.

Uso
---
    python scripts/comparar_artefato_geo.py --antigo <dir> --novo <dir>
    python scripts/comparar_artefato_geo.py --antigo <dir> --novo <dir> --uf SP

Codigo 1 na primeira divergencia inesperada.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

#: Colunas que PODEM diferir, e por que. Qualquer outra diferenca e' regressao.
ESPERADAS = {
    "cod_distrito": "coluna NOVA (F0.1) — o CD_DIST que o DBF sempre teve",
    "data_materializacao": "carimbo do rerun; muda por construcao",
}


def particoes(raiz: Path) -> dict[str, Path]:
    """`uf=XX/cod_municipio=NNN` -> caminho do parquet."""
    achadas: dict[str, Path] = {}
    for parquet in raiz.glob("uf=*/cod_municipio=*/*.parquet"):
        chave = f"{parquet.parent.parent.name}/{parquet.parent.name}"
        achadas[chave] = parquet
    return achadas


def comparar(antigo: Path, novo: Path, uf: str | None) -> int:
    a_part, n_part = particoes(antigo), particoes(novo)
    if uf:
        alvo = f"uf={uf.upper()}/"
        a_part = {k: v for k, v in a_part.items() if k.startswith(alvo)}
        n_part = {k: v for k, v in n_part.items() if k.startswith(alvo)}

    problemas: list[str] = []

    # A particao `000None` DEVE sumir: e' a correcao do baseline (5.571 -> 5.570).
    sumiram = sorted(set(a_part) - set(n_part))
    esperado_sumir = [p for p in sumiram if "cod_municipio=000None" in p]
    inesperado_sumir = [p for p in sumiram if p not in esperado_sumir]
    for p in esperado_sumir:
        print(f"  ok   particao espuria removida: {p}")
    for p in inesperado_sumir:
        problemas.append(f"particao SUMIU sem motivo: {p}")
    for p in sorted(set(n_part) - set(a_part)):
        problemas.append(f"particao NOVA inesperada: {p}")

    comuns = sorted(set(a_part) & set(n_part))
    print(f"  comparando {len(comuns)} particoes...")
    colunas_novas: set[str] = set()
    linhas_a = linhas_n = 0

    for chave in comuns:
        da = pd.read_parquet(a_part[chave])
        dn = pd.read_parquet(n_part[chave])
        linhas_a += len(da)
        linhas_n += len(dn)

        if len(da) != len(dn):
            problemas.append(f"{chave}: {len(da)} linhas -> {len(dn)}")
            continue

        colunas_novas |= set(dn.columns) - set(da.columns)
        sumidas = set(da.columns) - set(dn.columns)
        if sumidas:
            problemas.append(f"{chave}: colunas sumiram: {sorted(sumidas)}")

        # Compara SO' as colunas que existiam antes, ordenadas pela chave do setor: se
        # alguma delas mudou, o rerun nao foi neutro -- e e' isso que precisa nao acontecer.
        compartilhadas = [c for c in da.columns if c in dn.columns and c not in ESPERADAS]
        chave_ord = "cod_setor"
        va = da.sort_values(chave_ord)[compartilhadas].reset_index(drop=True)
        vn = dn.sort_values(chave_ord)[compartilhadas].reset_index(drop=True)
        if not va.equals(vn):
            diferentes = [c for c in compartilhadas if not va[c].equals(vn[c])]
            problemas.append(f"{chave}: colunas MUDARAM de valor: {diferentes}")

    print(f"  linhas: {linhas_a} -> {linhas_n}")
    inesperadas = colunas_novas - set(ESPERADAS)
    if colunas_novas:
        for c in sorted(colunas_novas):
            motivo = ESPERADAS.get(c, "SEM MOTIVO DECLARADO")
            print(f"  {'ok  ' if c in ESPERADAS else 'ERRO'} coluna nova `{c}`: {motivo}")
    if inesperadas:
        problemas.append(f"colunas novas nao declaradas: {sorted(inesperadas)}")

    print()
    if problemas:
        print(f"DIVERGENTE — {len(problemas)} problema(s):")
        for p in problemas:
            print(f"  - {p}")
        return 1
    print("OK: o rerun mudou apenas o declarado.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--antigo", required=True, help="artefato ANTES do rerun")
    parser.add_argument("--novo", required=True, help="artefato DEPOIS do rerun")
    parser.add_argument("--uf", default=None, help="comparar so' uma UF (mais rapido)")
    args = parser.parse_args()

    antigo, novo = Path(args.antigo), Path(args.novo)
    for caminho in (antigo, novo):
        if not caminho.is_dir():
            raise SystemExit(f"ERRO: nao encontrado: {caminho}")
    return comparar(antigo, novo, args.uf)


if __name__ == "__main__":
    sys.exit(main())
