# -*- coding: utf-8 -*-
"""1) Populacao: usa SO a base pre-Censo (2016-2021). Cruzar 2021->2024 mistura
   metodologias — a dispersao ano a ano salta de [0,974;1,026] para [0,697;1,425].
2) Taxa de crescimento POR HEXAGONO, para as faixas do mapa."""
import pandas as pd, numpy as np, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from _raizes import TRABALHO, artefato_hex, artefato_municipal, entrada, raiz, trabalho  # noqa: E402
ART = artefato_municipal()
D = str(raiz("SOCIO"))

# ---------- 1. populacao na base consistente --------------------------------
po = pd.read_csv(rf"{D}\pib\populacao_6579_serie.csv", dtype={"cod6": str})
po["cod6"] = po.cod6.astype(str).str.zfill(6)
pv = po.pivot_table(index="cod6", columns="ano", values="populacao", aggfunc="first")
ANOS_P = [2016, 2017, 2018, 2019, 2020, 2021]          # base pre-Censo 2022
pop = pv[ANOS_P].dropna()
pop = pop[pop[2016] > 0]
novo_pct = (100 * (pop[2021] / pop[2016] - 1)).round(1)
print(f"populacao 2016-2021: {len(pop):,} municipios | mediana {novo_pct.median():+.2f}%")

art = pd.read_parquet(ART)
art["cod6"] = art.cod6.astype(str).str.zfill(6)
art["dim_pop_pct"] = art.cod6.map(novo_pct)
art["pos_pop"] = (art.dim_pop_pct.rank(pct=True) * 100).round(0)

# refaz a serie de populacao e o campo cres_dims / cres_series
def _sub(s, alvo, novo):
    if not isinstance(s, str): return s
    ps = [p for p in s.split(";") if not p.startswith(alvo)]
    if novo: ps.append(novo)
    return ";".join(ps) if ps else None
serie_pop = {c: "População|hab|2016|2021|" + ",".join(f"{v:.0f}" for v in pop.loc[c]) for c in pop.index}
art["cres_series"] = [_sub(s, "População|", serie_pop.get(c)) for s, c in zip(art.cres_series, art.cod6)]
dim_pop = {c: f"População:{v:.1f}:%:{p:.0f}" for c, v, p in
           zip(art.cod6, art.dim_pop_pct, art.pos_pop) if pd.notna(v) and pd.notna(p)}
art["cres_dims"] = [_sub(s, "População:", dim_pop.get(c)) for s, c in zip(art.cres_dims, art.cod6)]

DIMS = ["renda","pop","empresas","predios","emprego"]
art["dim_media"] = art[[f"pos_{k}" for k in DIMS]].mean(axis=1, skipna=True).round(0)
art.to_parquet(ART, index=False)
print("-> artefato: populacao corrigida para a base 2016-2021")

# ---------- 2. taxa de crescimento por HEXAGONO -----------------------------
ex = pd.read_parquet(entrada(TRABALHO, "_eixo_trajetoria.parquet"),
                     columns=["hex_id","p2016","p2023","n_pixels","mascara_urbana"])
ex = ex[ex.mascara_urbana].copy()
ex["a16"] = ex.p2016 * ex.n_pixels * 400
ex["a23"] = ex.p2023 * ex.n_pixels * 400
ex = ex[ex.a16 > 0]
ex["hex_taxa"] = (100 * (ex.a23 / ex.a16 - 1)).round(1)
q = [.01,.05,.10,.25,.50,.75,.90,.95,.99]
print("\n=== taxa de crescimento da area construida por hexagono (mascara urbana) ===")
print(ex.hex_taxa.quantile(q).round(1).to_string())

# faixas: cortes na distribuicao real, nao em palpite
# Cortes ancorados na distribuicao real: p50 = +19,2% e p75 = +30,6%. Com 15% o
# rotulo "Em alta" cairia em 64% dos hexes e deixaria de significar alguma coisa.
#
# IDENTIFICADOR SEM ACENTO (regra do CLAUDE.md §2): "Estavel", nao "Estável". O
# valor gravado aqui e chave de comparacao no backend (`_ROTULO_CLASSE` em
# web/server/app.py), e o irmao `cres_tendencia` ja seguia essa regra — as duas
# colunas saiam do mesmo balao de tooltip escritas de formas diferentes. O texto
# acentuado que o usuario le e montado na exibicao, nunca guardado no parquet.
CORTES = [(-1e9, 0, "Sem obra nova"), (0, 30, "Estavel"), (30, 1e9, "Em alta")]
ex["hex_classe"] = None
for lo, hi, nome in CORTES:
    ex.loc[(ex.hex_taxa >= lo) & (ex.hex_taxa < hi), "hex_classe"] = nome
print("\n=== faixas ===")
print(ex.hex_classe.value_counts().reindex([c[2] for c in CORTES]).to_string())
out = ex[["hex_id","hex_taxa","hex_classe"]].copy()
out["hex_id"] = out.hex_id.astype(str)
out.columns = ["hex_id","cres_hex_taxa","cres_hex_classe"]
out.to_parquet(artefato_hex(), index=False)
print(f"\n-> crescimento_hex.parquet ({len(out):,} hexes)")
