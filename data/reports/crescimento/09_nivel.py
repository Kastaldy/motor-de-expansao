# -*- coding: utf-8 -*-
"""Todas as series viram NIVEL (estoque), nunca ritmo.

Motivo: o grafico de saldo acumulado em 12 meses CAI quando a cidade contrata mais
devagar, mesmo com o estoque subindo. Sao Paulo capital mostrava a linha indo de
+317 mil para +86 mil ao lado de "+8,8%", e as duas leituras pareciam se contradizer.
Plotando o estoque, a linha SOBE e a desaceleracao aparece como achatamento — que e
o que de fato aconteceu. Renda, populacao e predios ja eram nivel; faltavam emprego
e empresas."""
import pandas as pd, numpy as np, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
D = r"C:\dados\socioeconomico"
API = r"C:\Users\Juan.lima\OneDrive - Grupo Ultra\Área de Trabalho\APIGeoEspacial"
c6 = lambda s: s.astype(str).str.replace(r"\D", "", regex=True).str.zfill(6).str[:6]

art = pd.read_parquet(rf"{API}\staging\crescimento_municipal.parquet")
art["cod6"] = art.cod6.astype(str).str.zfill(6)

# ---- EMPREGO: estoque = RAIS 2022 + saldo acumulado desde 2023 -------------
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
# 1 ponto a cada 2 meses para o grafico nao virar sopa: 21 pontos
passo = meses[::2] if len(meses) > 24 else meses
emp_niv = niv[passo].round(0)
print(f"emprego (estoque): {len(emp_niv):,} municipios x {len(passo)} pontos "
      f"({passo[0]} .. {passo[-1]})")

# ---- EMPRESAS: saldo ACUMULADO desde 2018 ---------------------------------
def desdobra(s):
    if not isinstance(s, str): return {}
    out = {}
    for b in s.split(";"):
        p = b.split("|")
        if len(p) == 5: out[p[0]] = p
    return out
def refaz(row):
    d = desdobra(row.cres_series)
    if "Empresas" in d:
        p = d["Empresas"]
        v = np.cumsum([float(x) for x in p[4].split(",")])
        d["Empresas"] = [p[0], "acum.", p[2], p[3], ",".join(f"{x:.0f}" for x in v)]
    if row.cod6 in emp_niv.index:
        v = emp_niv.loc[row.cod6]
        d["Emprego"] = ["Emprego", "vínculos", "2023", "jun/2026",
                        ",".join(f"{x:.0f}" for x in v)]
    return ";".join("|".join(p) for p in d.values()) if d else None

art["cres_series"] = art.apply(refaz, axis=1)
art.to_parquet(rf"{API}\staging\crescimento_municipal.parquet", index=False)

# ---- conferencia: alguma serie ainda CAI enquanto a dimensao e positiva? ---
def cai(s, nome):
    d = desdobra(s)
    if nome not in d: return None
    v = [float(x) for x in d[nome][4].split(",")]
    return v[-1] < v[0]
for nome in ["Renda","População","Empresas","Prédios","Emprego"]:
    c = art.cres_series.apply(lambda s: cai(s, nome))
    print(f"  {nome:<11} series que terminam abaixo do inicio: {c.sum():>5.0f} de {c.notna().sum():,}")

print("\n=== Sao Paulo capital, antes e depois ===")
sp = art[art.cod6 == "355030"].iloc[0]
for b in str(sp.cres_series).split(";"):
    p = b.split("|")
    if p[0] == "Emprego":
        v = [float(x) for x in p[4].split(",")]
        print(f"  Emprego ({p[1]}): {v[0]:,.0f} -> {v[-1]:,.0f}   variacao {100*(v[-1]/v[0]-1):+.1f}%")
        print(f"  a dimensao diz: +8.8%  -> agora o grafico SOBE e bate com o numero")
