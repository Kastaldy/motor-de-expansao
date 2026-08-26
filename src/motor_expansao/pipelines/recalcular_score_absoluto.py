"""Recalcula `score_setor_2022_calibrado` nos parquets censitarios com a regua ABSOLUTA.

POR QUE ESTE PIPELINE EXISTE
----------------------------
O score censitario nasce em tres pipelines `fase_a_*` que consomem o Censo bruto
(`data/raw/CENSO 2022/`). Esse insumo NAO vive na estacao de trabalho -- so' os parquets
derivados vivem. Quando a REGUA muda (e nao a fonte), reprocessar o Censo inteiro seria
desnecessario: a regua absoluta precisa apenas de `renda_per_capita_setor_2022_calibrada` e
`pop_total_setor_2022`, e as duas ja' estao materializadas nos tres parquets.

Este pipeline aplica `calcular_score_calibrado` -- a MESMA funcao que os `fase_a_*` usam, para
nao haver duas definicoes do score -- sobre os artefatos existentes, in-place.

NAO recalcula renda, nao recalibra o `k`, nao toca no M1. So' reescreve tres colunas derivadas:
`hex_score_estrutural_calibrado`, `ajuste_calibrado` e `score_setor_2022_calibrado`.

Os percentis (`renda_pct_nacional_calibrado`, `pop_pct_municipal`) sao PRESERVADOS como colunas
de auditoria -- eles deixaram de alimentar o score em 2026-08-26, mas continuam a explicar como
o artefato era antes.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from motor_expansao.pipelines.calibrar_renda_setor_2022 import calcular_score_calibrado

ALVOS = (
    Path("data/staging/censo2022_setores_calibrado.parquet"),
    Path("data/staging/censo2022_setores_calibrado_piloto_expandido.parquet"),
    Path("data/staging/censo2022_setores_calibrado_nacional_completo.parquet"),
)

COL_RENDA = "renda_per_capita_setor_2022_calibrada"
COL_POP = "pop_total_setor_2022"
COL_SCORE = "score_setor_2022_calibrado"
COL_HEX = "hex_score_estrutural_calibrado"
COL_AJUSTE = "ajuste_calibrado"


def recalcular(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Reescreve as tres colunas de score a partir de renda e populacao absolutas."""
    faltam = [c for c in (COL_RENDA, COL_POP) if c not in df.columns]
    if faltam:
        raise KeyError(f"colunas de insumo ausentes: {faltam}")

    renda = pd.to_numeric(df[COL_RENDA], errors="coerce")
    pop = pd.to_numeric(df[COL_POP], errors="coerce")
    mask = renda.notna() & pop.notna()

    antes = pd.to_numeric(df.get(COL_SCORE), errors="coerce") if COL_SCORE in df.columns else None

    for col in (COL_HEX, COL_AJUSTE, COL_SCORE):
        if col not in df.columns:
            df[col] = float("nan")
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if mask.any():
        hex_score, ajuste, score = calcular_score_calibrado(
            renda.loc[mask].to_numpy(),
            pop.loc[mask].to_numpy(),
        )
        df.loc[mask, COL_HEX] = hex_score
        df.loc[mask, COL_AJUSTE] = ajuste
        df.loc[mask, COL_SCORE] = score
    df.loc[~mask, [COL_HEX, COL_AJUSTE, COL_SCORE]] = float("nan")

    depois = pd.to_numeric(df[COL_SCORE], errors="coerce")
    resumo = {
        "linhas": int(len(df)),
        "recalculadas": int(mask.sum()),
        "sem_insumo": int((~mask).sum()),
        "score_mediana_depois": float(depois.median()) if depois.notna().any() else float("nan"),
        "saturam_em_100": int((depois >= 99.995).sum()),
    }
    if antes is not None and antes.notna().any():
        resumo["score_mediana_antes"] = float(antes.median())
    return df, resumo


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="mede sem gravar")
    args = ap.parse_args()

    print("Recalculo do score censitario pela regua ABSOLUTA")
    print("=" * 70)
    for alvo in ALVOS:
        if not alvo.exists():
            print(f"  PULADO (ausente): {alvo}")
            continue
        df = pd.read_parquet(alvo)
        df, r = recalcular(df)
        antes = r.get("score_mediana_antes")
        antes_txt = f"{antes:.1f}" if antes is not None else "n/d"
        print(f"  {alvo.name}")
        print(
            f"     linhas {r['linhas']:>9,} | recalculadas {r['recalculadas']:>9,} | "
            f"sem insumo {r['sem_insumo']:>9,}"
        )
        print(
            f"     mediana do score: {antes_txt} -> {r['score_mediana_depois']:.1f} | "
            f"saturam em 100: {r['saturam_em_100']:,}"
        )
        if not args.dry_run:
            df.to_parquet(alvo, index=False)
            print("     gravado")
    print("=" * 70)
    if args.dry_run:
        print("dry-run: nada foi gravado")


if __name__ == "__main__":
    main()
