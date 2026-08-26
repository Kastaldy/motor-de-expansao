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

from motor_expansao.pipelines.calibrar_renda_setor_2022 import (
    ajuste_executivo,
    calcular_score_calibrado,
)

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
COL_RENDA_PCT = "renda_pct_nacional_calibrado"
COL_POP_PCT = "pop_pct_municipal"


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


def reverter(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Reconstitui o score ANTIGO (percentil) a partir das colunas de auditoria.

    A reversao NAO depende de backup: `renda_pct_nacional_calibrado` e `pop_pct_municipal`
    sao preservados por `recalcular`, e a formula antiga era
    `clip(100*(0,60*renda_pct + 0,40*pop_pct) + ajuste_executivo, 0, 100)`.
    Verificado contra o backup do artefato nacional em 2026-08-26: erro maximo 0,0 exato.

    Existe para que voltar atras seja um comando, e nao uma arqueologia.
    """
    faltam = [c for c in (COL_RENDA_PCT, COL_POP_PCT) if c not in df.columns]
    if faltam:
        raise KeyError(f"colunas de auditoria ausentes, reversao impossivel: {faltam}")

    r = pd.to_numeric(df[COL_RENDA_PCT], errors="coerce")
    p = pd.to_numeric(df[COL_POP_PCT], errors="coerce")
    mask = r.notna() & p.notna()

    for col in (COL_HEX, COL_AJUSTE, COL_SCORE):
        if col not in df.columns:
            df[col] = float("nan")
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if mask.any():
        rv = r.loc[mask].to_numpy()
        pv = p.loc[mask].to_numpy()
        hex_score = 100.0 * (0.60 * rv + 0.40 * pv)
        adj = ajuste_executivo(rv, pv)
        df.loc[mask, COL_HEX] = hex_score
        df.loc[mask, COL_AJUSTE] = adj
        df.loc[mask, COL_SCORE] = (hex_score + adj).clip(0.0, 100.0)
    df.loc[~mask, [COL_HEX, COL_AJUSTE, COL_SCORE]] = float("nan")

    depois = pd.to_numeric(df[COL_SCORE], errors="coerce")
    return df, {
        "linhas": int(len(df)),
        "revertidas": int(mask.sum()),
        "sem_insumo": int((~mask).sum()),
        "score_mediana_depois": float(depois.median()) if depois.notna().any() else float("nan"),
        "saturam_em_100": int((depois >= 99.995).sum()),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="mede sem gravar")
    ap.add_argument(
        "--reverter",
        action="store_true",
        help="volta ao score de PERCENTIL usando as colunas de auditoria (nao precisa de backup)",
    )
    args = ap.parse_args()

    modo = "REVERSAO para a regua de PERCENTIL" if args.reverter else "regua ABSOLUTA"
    print(f"Score censitario -- {modo}")
    print("=" * 70)
    for alvo in ALVOS:
        if not alvo.exists():
            print(f"  PULADO (ausente): {alvo}")
            continue
        df = pd.read_parquet(alvo)
        df, r = reverter(df) if args.reverter else recalcular(df)
        antes = r.get("score_mediana_antes")
        antes_txt = f"{antes:.1f}" if antes is not None else "n/d"
        print(f"  {alvo.name}")
        print(
            f"     linhas {r['linhas']:>9,} | "
            f"aplicadas {r.get('recalculadas', r.get('revertidas', 0)):>9,} | "
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
