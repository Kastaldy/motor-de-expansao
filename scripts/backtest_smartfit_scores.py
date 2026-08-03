"""Backtest de validacao (READ-ONLY M1): os scores correlacionam com a
demanda observada (alunos/acessos) da rede Smart Fit?

Junta a KPI Smart Fit (alunos/acessos 2023, por nome de unidade) com as
coordenadas de concorrentes/Unidades/unidades_smart_fit.csv (match por nome),
atribui cada unidade ao hex H3 res7 e cruza com os scores oficiais/paralelos
em data/staging/hexagonos_mercado_mapeado.parquet.

NAO recalcula score nem toca artefato M1. Saida: relatorio impresso + parquet
em data/analysis/ (gitignored).
"""
from __future__ import annotations

import unicodedata
from pathlib import Path

import h3
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
KPI = ROOT / "data/validacao/KPIs_Smart_2025_02 (1).xlsx"
COORDS = ROOT / "concorrentes/Unidades/unidades_smart_fit.csv"
SCORES = ROOT / "data/staging/hexagonos_mercado_mapeado.parquet"
OUT = ROOT / "data/analysis"


def norm(s: str) -> str:
    s = str(s).strip().lower()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return "".join(ch for ch in s if ch.isalnum() or ch == " ").strip()


def main() -> None:
    # 1. KPI: agrega por unidade (media 2023 = steady-state aprox.)
    kpi = pd.read_excel(KPI, sheet_name="Base")
    kpi_agg = (
        kpi.groupby("Nome", as_index=False)
        .agg(
            alunos=("Alunos Totais SF", "mean"),
            acessos=("Acessos SF", "mean"),
            freq=("Frequencia", "mean"),
            meses=("Data_Ref", "nunique"),
        )
    )
    kpi_agg["key"] = kpi_agg["Nome"].map(norm)
    print(f"KPI: {len(kpi)} linhas-mes -> {len(kpi_agg)} unidades unicas")

    # 2. Coordenadas
    coords = pd.read_csv(COORDS, sep=None, engine="python")
    coords["key"] = coords["nome_unidade"].map(norm)
    coords = coords.dropna(subset=["latitude", "longitude"]).drop_duplicates("key")
    print(f"Coords: {len(coords)} unidades com lat/lng unicas (por nome)")

    # 3. Match por nome normalizado
    m = kpi_agg.merge(coords[["key", "latitude", "longitude"]], on="key", how="inner")
    print(
        f"MATCH exato por nome: {len(m)} / {len(kpi_agg)} "
        f"({100*len(m)/len(kpi_agg):.0f}% das unidades KPI)"
    )

    # 4. hex H3 res7
    m["hex_id"] = [
        h3.latlng_to_cell(float(la), float(lo), 7)
        for la, lo in zip(m["latitude"], m["longitude"], strict=True)
    ]

    # 5. scores por hex
    sc = pd.read_parquet(
        SCORES,
        columns=[
            "hex_id",
            "score_priorizacao",
            "score_setor_2022_calibrado",
            "score_oportunidade_residual",
            "score_expansao_hibrido",
        ],
    )
    j = m.merge(sc, on="hex_id", how="left")
    j["alunos_por_acesso"] = j["acessos"] / j["alunos"].replace(0, np.nan)
    print(f"Join scores: {j['score_priorizacao'].notna().sum()} / {len(j)} hexes com score M1\n")

    # 6. Spearman score x desfecho
    outcomes = {"alunos": "Alunos Totais (media 2023)", "acessos": "Acessos (media 2023)"}
    scores = {
        "score_priorizacao": "M1 (executivo)",
        "score_setor_2022_calibrado": "Censitario (operacional)",
        "score_oportunidade_residual": "Residual (mercado)",
        "score_expansao_hibrido": "Hibrido",
    }
    print("=" * 78)
    print("CORRELACAO DE SPEARMAN — score (preditor) x demanda observada (desfecho)")
    print("=" * 78)
    for oc, oc_lbl in outcomes.items():
        print(f"\n### Desfecho: {oc_lbl}")
        for scn, scl in scores.items():
            sub = j[[scn, oc]].dropna()
            n = len(sub)
            if n < 10 or sub[scn].nunique() < 3:
                print(f"  {scl:28s}  n={n:4d}  (insuficiente / sem variacao)")
                continue
            rho, p = stats.spearmanr(sub[scn], sub[oc])
            # IC95% de Fisher para rho de Spearman
            stderr = 1.0 / np.sqrt(n - 3)
            z = np.arctanh(rho)
            lo, hi = np.tanh(z - 1.96 * stderr), np.tanh(z + 1.96 * stderr)
            flag = "" if (lo > 0 or hi < 0) else "  <- IC cruza zero (n.s.)"
            print(f"  {scl:28s}  n={n:4d}  rho={rho:+.3f}  IC95[{lo:+.3f},{hi:+.3f}]  p={p:.3f}{flag}")

    OUT.mkdir(parents=True, exist_ok=True)
    cols = [
        "Nome", "alunos", "acessos", "freq", "hex_id",
        "score_priorizacao", "score_setor_2022_calibrado",
        "score_oportunidade_residual", "score_expansao_hibrido",
    ]
    j[cols].to_parquet(OUT / "backtest_smartfit.parquet", index=False)
    print(f"\nArtefato: {OUT / 'backtest_smartfit.parquet'} (gitignored, READ-ONLY M1)")


if __name__ == "__main__":
    main()
