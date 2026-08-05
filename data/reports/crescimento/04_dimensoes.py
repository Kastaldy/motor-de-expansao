# -*- coding: utf-8 -*-
"""Cinco dimensoes do crescimento municipal, cada uma com NUMERO REAL + posicao.
Nada de nota solta: todo percentil vem acompanhado do valor que ele resume.
Renda e nominal de proposito — a comparacao com a mediana nacional faz o papel do
deflator, e evita inventar um indice de inflacao que ninguem pode auditar aqui."""
import pandas as pd, numpy as np, glob, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
D = r"C:\dados\socioeconomico"
C = r"C:\Users\Juan.lima\OneDrive - Grupo Ultra\Área de Trabalho\Crescimento Regional TEC\output"
POC = r"C:\Users\Juan.lima\OneDrive - Grupo Ultra\Área de Trabalho\Google Engine\poc_satelite"
UFS = ["SP","MG","RJ","ES","PR","SC","RS","BA","PE","CE","GO","DF"]
# Serve para codigo de 6 OU 7 digitos: a RAIS usa 6, a ponte do CRESCIMENTO usa 7.
# zfill(7)+[:6] quebrava o de 6 ("110001" virava "011000").
c6 = lambda s: s.astype(str).str.replace(r"\D", "", regex=True).str.zfill(6).str[:6]

base = pd.read_csv(rf"{C}\indices_crescimento_municipal.csv", low_memory=False,
                   usecols=["cod6","cidade","uf","pop_2024","confiabilidade"])
base["cod6"] = base.cod6.astype(str).str.zfill(6)

# ---- 1. RENDA: remuneracao media RAIS 2020 -> 2024 --------------------------
r20 = pd.read_csv(rf"{D}\rais\rais_municipio_2020.csv", dtype={"cod_municipio": str})
r24 = pd.read_csv(rf"{D}\rais\rais_municipio_2024.csv", dtype={"cod_municipio": str})
for r in (r20, r24): r["cod6"] = c6(r.cod_municipio)
a = r20.groupby("cod6").agg(v0=("vinculos_ativos","sum"), m0=("massa_salarial_mensal","sum"))
b = r24.groupby("cod6").agg(v1=("vinculos_ativos","sum"), m1=("massa_salarial_mensal","sum"))
rn = a.join(b, how="inner")
rn = rn[(rn.v0 > 30) & (rn.v1 > 30)]
rn["rem0"] = rn.m0 / rn.v0; rn["rem1"] = rn.m1 / rn.v1
rn["dim_renda_pct"] = (100 * (rn.rem1 / rn.rem0 - 1)).round(1)
rn["dim_renda_valor"] = rn.rem1.round(0)
print(f"renda: {len(rn):,} municipios | mediana {rn.dim_renda_pct.median():+.1f}% nominal 2020->2024")

# ---- 2. POPULACAO: serie longa ---------------------------------------------
po = pd.read_csv(rf"{D}\pib\populacao_6579_serie.csv", dtype={"cod6": str})
po["cod6"] = po.cod6.astype(str).str.zfill(6)
pv = po.pivot_table(index="cod6", columns="ano", values="populacao", aggfunc="first")
A0, A1 = 2016, int(max(pv.columns))
pop = pd.DataFrame({"p0": pv[A0], "p1": pv[A1]}).dropna()
pop = pop[pop.p0 > 0]
pop["dim_pop_pct"] = (100 * (pop.p1 / pop.p0 - 1)).round(1)
pop["dim_pop_valor"] = pop.p1.round(0)
print(f"populacao: {len(pop):,} municipios | {A0}->{A1} | mediana {pop.dim_pop_pct.median():+.1f}%")

# ---- 3. EMPRESAS: saldo CNPJ por 1.000 habitantes ---------------------------
cn = pd.read_csv(rf"{C}\indices_desenvolvimento_municipal.csv", low_memory=False,
                 usecols=["cod6","saldo","pop"])
cn["cod6"] = cn.cod6.astype(str).str.zfill(6)
cn = cn[cn["pop"] > 0].set_index("cod6")
cn["dim_empresas_por1k"] = (1000 * cn.saldo / cn["pop"]).round(1)
cn["dim_empresas_valor"] = cn.saldo
print(f"empresas: {len(cn):,} municipios | mediana {cn.dim_empresas_por1k.median():.1f} por 1.000 hab")

# ---- 4. PREDIOS: area construida e altura media (satelite, 12 UFs) ----------
eixo = pd.read_parquet("_eixo_trajetoria.parquet",
                       columns=["hex_id","cod_municipio","p2016","p2023","n_pixels","mascara_urbana"])
eixo = eixo[eixo.mascara_urbana].copy()
eixo["a16"] = eixo.p2016 * eixo.n_pixels; eixo["a23"] = eixo.p2023 * eixo.n_pixels
alt = []
for uf in UFS:
    for ano in (2016, 2023):
        f = rf"{POC}\data\uf={uf}\hex_google_temporal_{ano}.parquet"
        d = pd.read_parquet(f, columns=["hex_id","altura_media","presenca_media","n_pixels"])
        d["ano"] = ano; alt.append(d)
alt = pd.concat(alt, ignore_index=True)
alt["hex_id"] = alt.hex_id.astype(str)
alt["peso"] = alt.presenca_media * alt.n_pixels
alt = alt[alt.hex_id.isin(set(eixo.hex_id.astype(str)))]
alt = alt.merge(eixo[["hex_id","cod_municipio"]].assign(hex_id=lambda x: x.hex_id.astype(str)), on="hex_id")
def hpond(g):
    w = g.peso.sum()
    return (g.altura_media * g.peso).sum() / w if w > 0 else np.nan
h = alt.groupby(["cod_municipio","ano"]).apply(hpond, include_groups=False).unstack()
pred = eixo.groupby("cod_municipio").agg(a16=("a16","sum"), a23=("a23","sum")).join(h)
pred = pred[pred.a16 > 0]
pred["dim_predios_pct"] = (100 * (pred.a23 / pred.a16 - 1)).round(1)
pred["dim_altura_pct"] = (100 * (pred[2023] / pred[2016] - 1)).round(1)
pred["dim_altura_valor"] = pred[2023].round(2)
pred.index = pred.index.astype(str).str.zfill(7).str[:6]
pred = pred[~pred.index.duplicated()]
print(f"predios: {len(pred):,} municipios (12 UFs) | area mediana {pred.dim_predios_pct.median():+.1f}% | "
      f"altura mediana {pred.dim_altura_pct.median():+.1f}%")

# ---- junta e calcula posicao NACIONAL de cada dimensao ----------------------
d = (base.set_index("cod6")
     .join(rn[["dim_renda_pct","dim_renda_valor"]])
     .join(pop[["dim_pop_pct","dim_pop_valor"]])
     .join(cn[["dim_empresas_por1k","dim_empresas_valor"]])
     .join(pred[["dim_predios_pct","dim_altura_pct","dim_altura_valor"]]))
cm = pd.read_csv(rf"{C}\crescimento_municipio.csv", dtype={"cod6": str})
cm["cod6"] = cm.cod6.astype(str).str.zfill(6)
d = d.join(cm.set_index("cod6")[["emp_cresc_pct","mat_label"]])
d = d.rename(columns={"emp_cresc_pct": "dim_emprego_pct"})

DIMS = ["renda","pop","empresas","predios","emprego"]
COLPCT = {"renda":"dim_renda_pct","pop":"dim_pop_pct","empresas":"dim_empresas_por1k",
          "predios":"dim_predios_pct","emprego":"dim_emprego_pct"}
for k, c in COLPCT.items():
    d[f"pos_{k}"] = (d[c].rank(pct=True) * 100).round(0)
d["dim_media"] = d[[f"pos_{k}" for k in DIMS]].mean(axis=1, skipna=True).round(0)
d["dim_n"] = d[[f"pos_{k}" for k in DIMS]].notna().sum(axis=1)
print("\n=== cobertura por dimensao ===")
for k in DIMS: print(f"  {k:<10} {d['pos_'+k].notna().mean():>6.1%}")
print(f"\n  media com >=4 dimensoes: {(d.dim_n>=4).mean():.1%} dos municipios")
d.reset_index().to_parquet("_dims.parquet", index=False)
print("\n-> _dims.parquet")
print("\n=== exemplo: Goianesia GO ===")
g = d[d.cidade.astype(str).str.upper().str.startswith("GOIAN")].head(3)
print(g[["cidade","uf","dim_renda_pct","dim_pop_pct","dim_empresas_por1k","dim_predios_pct",
         "dim_altura_pct","dim_emprego_pct","dim_media"]].to_string())
