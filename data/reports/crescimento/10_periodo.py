# -*- coding: utf-8 -*-
"""1) A serie de emprego passa a comecar no ESTOQUE da RAIS 2022, para a variacao
   do grafico bater EXATAMENTE com o numero da dimensao (era 8,5% vs 8,8%).
2) Cada dimensao carrega o PERIODO, para a tela poder responder "em relacao a que?".
   Formato: nome:valor:unidade:posicao:periodo"""
import pandas as pd, numpy as np, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from _raizes import artefato_municipal, raiz  # noqa: E402
ART = artefato_municipal()
D = str(raiz("SOCIO"))
c6 = lambda s: s.astype(str).str.replace(r"\D", "", regex=True).str.zfill(6).str[:6]

art = pd.read_parquet(ART)
art["cod6"] = art.cod6.astype(str).str.zfill(6)

rais = pd.read_csv(rf"{D}\rais\rais_municipio_2022.csv", dtype={"cod_municipio": str})
rais["cod6"] = c6(rais.cod_municipio)
estoque = rais.groupby("cod6").vinculos_ativos.sum()

cg = pd.read_csv(rf"{D}\caged\caged_municipio_mensal_2020_2026.csv",
                 dtype={"competencia": str, "cod_municipio": str})
cg["cod6"] = c6(cg.cod_municipio); cg = cg[cg.cod6 != "999999"]
cg["saldo"] = pd.to_numeric(cg.saldo, errors="coerce").fillna(0)
piv = cg.pivot_table(index="cod6", columns="competencia", values="saldo", aggfunc="sum").fillna(0)
meses = [c for c in sorted(piv.columns) if c >= "202301"]
acum = piv[meses].cumsum(axis=1)
niv = acum.add(estoque.reindex(acum.index), axis=0).dropna()
# ponto ZERO = estoque de dez/2022, para o primeiro ponto do grafico ser a base
# do percentual. Sem ele o grafico media 8,5% e a dimensao 8,8%.
niv.insert(0, "202212", estoque.reindex(niv.index))
passo = ["202212"] + meses[1::2]
emp_niv = niv[passo].round(0)

PERIODO = {"Renda": "2020→2024", "População": "2016→2021", "Empresas": "2020–2025",
           "Prédios": "2016→2023", "Emprego": "2022→jun/2026"}

def des(s, sep):
    if not isinstance(s, str): return {}
    out = {}
    for b in s.split(";"):
        p = b.split(sep)
        if p: out[p[0]] = p
    return out

def refaz_series(row):
    d = des(row.cres_series, "|")
    if row.cod6 in emp_niv.index:
        v = emp_niv.loc[row.cod6]
        d["Emprego"] = ["Emprego", "vínculos", "dez/2022", "jun/2026",
                        ",".join(f"{x:.0f}" for x in v)]
    return ";".join("|".join(p) for p in d.values()) if d else None

def refaz_dims(s):
    d = des(s, ":")
    out = []
    for nome, p in d.items():
        if len(p) < 4: continue
        out.append(":".join(p[:4] + [PERIODO.get(nome, "")]))
    return ";".join(out) if out else None

art["cres_series"] = art.apply(refaz_series, axis=1)
art["cres_dims"] = art.cres_dims.apply(refaz_dims)
art.to_parquet(ART, index=False)

sp = art[art.cod6 == "355030"].iloc[0]
for b in str(sp.cres_series).split(";"):
    p = b.split("|")
    if p[0] == "Emprego":
        v = [float(x) for x in p[4].split(",")]
        print(f"Sao Paulo capital, emprego: {v[0]:,.0f} -> {v[-1]:,.0f} = {100*(v[-1]/v[0]-1):+.1f}%")
emp = [x for x in str(sp.cres_dims).split(";") if x.startswith("Emprego")][0]
print(f"a dimensao diz: {emp}")
print("\n=== dims com periodo ===")
for x in str(sp.cres_dims).split(";"): print("   ", x)
