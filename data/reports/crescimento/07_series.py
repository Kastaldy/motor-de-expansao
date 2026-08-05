# -*- coding: utf-8 -*-
"""Uma serie temporal por dimensao, para o grafico trocar conforme o botao clicado.
Formato por dimensao: nome|unidade|rotulo_ini|rotulo_fim|v1,v2,...   unidas por ';'."""
import pandas as pd, numpy as np, glob, zipfile, unicodedata, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from _raizes import TRABALHO, artefato_municipal, entrada, raiz, trabalho  # noqa: E402
ART = artefato_municipal()
D = str(raiz("SOCIO"))
C = str(raiz("TEC"))
c6 = lambda s: s.astype(str).str.replace(r"\D", "", regex=True).str.zfill(6).str[:6]
def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii","ignore").decode().upper().strip()
    return " ".join(s.split())

base = pd.read_csv(rf"{C}\indices_crescimento_municipal.csv", low_memory=False,
                   usecols=["cod6","cidade","uf"])
base["cod6"] = base.cod6.astype(str).str.zfill(6)
S = {}

# --- RENDA: remuneracao media RAIS 2020..2024 -------------------------------
anos_r = list(range(2020, 2025)); part = []
for a in anos_r:
    d = pd.read_csv(rf"{D}\rais\rais_municipio_{a}.csv", dtype={"cod_municipio": str})
    d["cod6"] = c6(d.cod_municipio)
    g = d.groupby("cod6").agg(v=("vinculos_ativos","sum"), m=("massa_salarial_mensal","sum"))
    part.append((g.m / g.v).rename(a))
renda = pd.concat(part, axis=1).dropna()
S["renda"] = ("Renda", "R$", str(anos_r[0]), str(anos_r[-1]), renda.round(0))
print(f"renda: {len(renda):,} municipios x {len(anos_r)} anos")

# --- POPULACAO --------------------------------------------------------------
po = pd.read_csv(rf"{D}\pib\populacao_6579_serie.csv", dtype={"cod6": str})
po["cod6"] = po.cod6.astype(str).str.zfill(6)
pv = po.pivot_table(index="cod6", columns="ano", values="populacao", aggfunc="first")
anos_p = [a for a in sorted(pv.columns) if a >= 2016]
pop = pv[anos_p].dropna()
S["pop"] = ("População", "hab", str(anos_p[0]), str(anos_p[-1]), pop.round(0))
print(f"populacao: {len(pop):,} x {len(anos_p)} anos {anos_p}")

# --- EMPRESAS: saldo CNPJ por ano ------------------------------------------
cj = pd.read_parquet(rf"{D}\cnpj\agg\municipio_ano_dinamismo.parquet")
cj["ano_i"] = pd.to_numeric(cj.ano, errors="coerce")
cj = cj[(cj.ano_i >= 2018) & (cj.ano_i <= 2025)]
cj["sinal"] = np.where(cj.tipo.eq("abertura"), 1, -1)
cj["liq"] = cj.n * cj.sinal
with zipfile.ZipFile(rf"{D}\cnpj\Municipios.zip") as z:
    mref = pd.read_csv(z.open(z.namelist()[0]), sep=";", header=None,
                       names=["cod_receita","nome"], dtype=str, encoding="latin1")
mref["cod_receita"] = mref.cod_receita.str.zfill(4); mref["nn"] = mref.nome.map(norm)
cj["cod_receita"] = cj.municipio.astype(str).str.zfill(4)
cj = cj.merge(mref[["cod_receita","nn"]], on="cod_receita", how="left")
cj["chave"] = cj.uf.map(norm) + "|" + cj.nn.fillna("")
base["chave"] = base.uf.map(norm) + "|" + base.cidade.map(norm)
cj = cj.merge(base[["chave","cod6"]], on="chave", how="left")
emp = cj[cj.cod6.notna()].pivot_table(index="cod6", columns="ano_i", values="liq", aggfunc="sum").fillna(0)
anos_e = sorted(emp.columns)
S["empresas"] = ("Empresas", "saldo", str(int(anos_e[0])), str(int(anos_e[-1])), emp[anos_e].round(0))
print(f"empresas: {len(emp):,} x {len(anos_e)} anos")

# --- PREDIOS: area construida municipal 2016..2023 (satelite) --------------
ex = pd.read_parquet(entrada(TRABALHO, "_eixo_trajetoria.parquet"),
      columns=["cod_municipio","n_pixels","mascara_urbana"] + [f"p{a}" for a in range(2016,2024)])
ex = ex[ex.mascara_urbana]
for a in range(2016, 2024): ex[f"a{a}"] = ex[f"p{a}"] * ex.n_pixels * 400
pr = ex.groupby("cod_municipio")[[f"a{a}" for a in range(2016,2024)]].sum()
pr.index = c6(pd.Series(pr.index.astype(str)))
pr = pr[~pr.index.duplicated()]
pr.columns = list(range(2016, 2024))
S["predios"] = ("Prédios", "m²", "2016", "2023", (pr/1000).round(0))   # milhares de m2
print(f"predios: {len(pr):,} x 8 anos")

# --- EMPREGO: saldo CAGED acumulado 12m (mensal) ---------------------------
cg = pd.read_csv(rf"{D}\caged\caged_municipio_mensal_2020_2026.csv",
                 dtype={"competencia": str, "cod_municipio": str})
cg["cod6"] = c6(cg.cod_municipio); cg = cg[cg.cod6 != "999999"]
cg["saldo"] = pd.to_numeric(cg.saldo, errors="coerce").fillna(0)
piv = cg.pivot_table(index="cod6", columns="competencia", values="saldo", aggfunc="sum").fillna(0)
comps = sorted(piv.columns)
rol = piv[comps].T.rolling(12).sum().T
usar = comps[11:][-30:]
S["emprego"] = ("Emprego", "vagas", "jan/2024", "jun/2026", rol[usar].round(0))
print(f"emprego: {len(rol):,} x {len(usar)} meses")

# --- codifica ---------------------------------------------------------------
def enc(cod6):
    out = []
    for k, (nome, un, ri, rf, df) in S.items():
        if cod6 not in df.index: continue
        v = df.loc[cod6]
        if v.isna().any(): continue
        out.append(f"{nome}|{un}|{ri}|{rf}|" + ",".join(f"{x:.0f}" for x in v))
    return ";".join(out) if out else None

art = pd.read_parquet(ART)
art["cod6"] = art.cod6.astype(str).str.zfill(6)
art["cres_series"] = [enc(c) for c in art.cod6]
art.to_parquet(ART, index=False)
n = art.cres_series.fillna("").str.count(";") + 1
print(f"\n-> cres_series | com >=1 serie {art.cres_series.notna().mean():.1%} | com as 5 {(n==5).mean():.1%}")
ex1 = art[art.cres_series.fillna('').str.count(';').eq(4)].iloc[0]
print(f"\nexemplo cod6={ex1.cod6}:")
for p in str(ex1.cres_series).split(";"):
    c = p.split("|"); print(f"   {c[0]:<10} {c[2]}..{c[3]}  {len(c[4].split(','))} pontos  [{c[4][:46]}...]")
