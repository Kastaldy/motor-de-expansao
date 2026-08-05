# -*- coding: utf-8 -*-
"""Enriquece a camada de crescimento municipal com quatro leituras que um percentual
sozinho nao da:
  1. serie do saldo CAGED (acumulado 12 meses) -> a FORMA do crescimento
  2. salario medio de admissao e sua variacao   -> QUALIDADE do emprego que entra
  3. setor que puxa a abertura de empresas      -> DE ONDE vem o crescimento
  4. mediana da UF                              -> ESCALA (o numero sozinho nao diz nada)
"""
import pandas as pd, numpy as np, unicodedata, zipfile, sys, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from _raizes import raiz, trabalho  # noqa: E402
C = str(raiz("TEC"))
D = str(raiz("SOCIO"))

def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper().strip()
    return " ".join(s.split())

base = pd.read_csv(rf"{C}\indices_crescimento_municipal.csv", low_memory=False,
                   usecols=["cod6","cidade","uf"])
base["cod6"] = base.cod6.astype(str).str.zfill(6)
base["chave"] = base.uf.map(norm) + "|" + base.cidade.map(norm)

# ---------- 1 e 2: CAGED mensal ---------------------------------------------
cg = pd.read_csv(rf"{D}\caged\caged_municipio_mensal_2020_2026.csv",
                 dtype={"competencia": str, "cod_municipio": str})
cg["cod6"] = cg.cod_municipio.str.zfill(6).str[:6]
cg = cg[cg.cod6 != "999999"]
cg["saldo"] = pd.to_numeric(cg.saldo, errors="coerce").fillna(0)
piv = cg.pivot_table(index="cod6", columns="competencia", values="saldo", aggfunc="sum").fillna(0)
comps = sorted(piv.columns)
# acumulado movel de 12 meses: e assim que se le CAGED no Brasil
rol = piv[comps].T.rolling(12).sum().T
JAN = comps[11:]                      # meses com 12 de historico
USAR = JAN[-30:]                      # ultimos 30 pontos -> ~2,5 anos de sparkline
serie = rol[USAR].round(0)
print(f"serie CAGED: {len(USAR)} pontos, {USAR[0]} .. {USAR[-1]}")

sal = cg[["cod6","competencia","salario_medio_adm","admissoes"]].copy()
sal["salario_medio_adm"] = pd.to_numeric(sal.salario_medio_adm, errors="coerce")
sal["admissoes"] = pd.to_numeric(sal.admissoes, errors="coerce").fillna(0)
# MEDIANA dos meses, nao media ponderada: o salario_medio_adm do CAGED tem
# outliers grosseiros no microdado (Sorocaba 202505 = R$ 129.957; o maximo
# nacional de 2025 passa de R$ 709 milhoes). Uma media absorve o outlier e
# produz variacoes impossiveis (-81%); a mediana de 12 meses ignora o mes ruim.
ULT12, ANT12 = comps[-12:], comps[-24:-12]
s_now = sal[sal.competencia.isin(ULT12)].groupby("cod6")["salario_medio_adm"].median()
s_old = sal[sal.competencia.isin(ANT12)].groupby("cod6")["salario_medio_adm"].median()
sal_df = pd.DataFrame({"cres_salario": s_now, "cres_salario_ant": s_old})
sal_df["cres_salario_var"] = 100 * (sal_df.cres_salario / sal_df.cres_salario_ant - 1)
print(f"salario de admissao: {sal_df.cres_salario.notna().sum():,} municipios | "
      f"mediana R$ {sal_df.cres_salario.median():,.0f} | var mediana {sal_df.cres_salario_var.median():+.1f}%")

# ---------- 3: setor que puxa a abertura de empresas -------------------------
SEC = [(1,3,"Agropecuária"),(5,9,"Extrativa"),(10,33,"Indústria"),(35,35,"Energia"),
       (36,39,"Saneamento"),(41,43,"Construção"),(45,47,"Comércio"),(49,53,"Transporte e logística"),
       (55,56,"Alojamento e alimentação"),(58,63,"Informação e TI"),(64,66,"Finanças"),
       (68,68,"Imobiliário"),(69,75,"Serviços profissionais"),(77,82,"Serviços administrativos"),
       (84,84,"Administração pública"),(85,85,"Educação"),(86,88,"Saúde"),
       (90,93,"Cultura e esporte"),(94,97,"Outros serviços")]
def secao(div):
    try: d = int(div)
    except (TypeError, ValueError): return None
    for lo, hi, nome in SEC:
        if lo <= d <= hi: return nome
    return None

st = pd.read_parquet(rf"{D}\cnpj\agg\municipio_ano_setor_dinamismo.parquet")
st["ano_i"] = pd.to_numeric(st.ano, errors="coerce")
st = st[(st.ano_i >= 2020) & (st.ano_i <= 2026)]
st["secao"] = st.cnae_div.map(secao)
st = st[st.secao.notna()]
st["sinal"] = np.where(st.tipo.eq("abertura"), 1, -1)
st["liq"] = st.n * st.sinal
agg = st.groupby(["uf","municipio","secao"])["liq"].sum().reset_index()

with zipfile.ZipFile(rf"{D}\cnpj\Municipios.zip") as z:
    mref = pd.read_csv(z.open(z.namelist()[0]), sep=";", header=None,
                       names=["cod_receita","nome"], dtype=str, encoding="latin1")
mref["cod_receita"] = mref.cod_receita.str.zfill(4)
mref["nome_norm"] = mref.nome.map(norm)
agg["cod_receita"] = agg.municipio.astype(str).str.zfill(4)
agg = agg.merge(mref[["cod_receita","nome_norm"]], on="cod_receita", how="left")
agg["chave"] = agg.uf.map(norm) + "|" + agg.nome_norm.fillna("")
agg = agg.merge(base[["chave","cod6"]], on="chave", how="left")
casou = agg.cod6.notna().mean()
print(f"setor: de-para TOM->IBGE casou {casou:.1%} das linhas")

pos = agg[(agg.cod6.notna()) & (agg.liq > 0)]
tot = pos.groupby("cod6")["liq"].sum().rename("tot")
pos = pos.merge(tot, on="cod6")
pos = pos[pos.tot >= 30]                       # volume minimo para a fracao significar algo
pos["share"] = 100 * pos.liq / pos.tot
# "Comercio" e o maior setor em 78% das cidades — dizer isso nao informa nada.
# O que informa e o DESVIO: qual setor esta acima do normal NESTA cidade.
norma = pos.groupby("secao")["share"].median().rename("norma")
pos = pos.merge(norma, on="secao")
pos["desvio"] = pos.share - pos.norma
top = pos.sort_values("desvio", ascending=False).drop_duplicates("cod6").set_index("cod6")
setor_df = pd.DataFrame({"cres_setor": top.secao, "cres_setor_pct": top.share.round(0),
                         "cres_setor_norma": top.norma.round(0)})
print(f"setor definido para {len(setor_df):,} municipios")
print(setor_df.cres_setor.value_counts().head(8).to_string())

# ---------- 4: mediana da UF -------------------------------------------------
cm = pd.read_csv(rf"{C}\crescimento_municipio.csv", dtype={"cod6": str})
cm["cod6"] = cm.cod6.astype(str).str.zfill(6)
cm = cm.merge(base[["cod6","uf"]], on="cod6", how="left")
med_uf = cm.groupby("uf")["emp_cresc_pct"].median().rename("cres_uf_mediana").round(1)
print(f"\nmediana de emprego por UF: {med_uf.min():.1f}% a {med_uf.max():.1f}%")

out = (base[["cod6","uf"]]
       .join(serie.apply(lambda r: ";".join(f"{int(v)}" for v in r), axis=1).rename("cres_serie"), on="cod6")
       .join(sal_df[["cres_salario","cres_salario_var"]], on="cod6")
       .join(setor_df[["cres_setor","cres_setor_pct"]], on="cod6")
       .merge(med_uf.reset_index(), on="uf", how="left"))
out["cres_salario"] = out.cres_salario.round(0)
out["cres_salario_var"] = out.cres_salario_var.round(1)
# Chave de nome para o fallback do join: o M1 deixa cod_municipio 100% NULO em
# ES, PR, SC, BA, PE e CE (6 das 12 UFs, ~204 mil hexes). nome_municipio esta
# completo em todas, entao (uf, nome normalizado) recupera o que o codigo perde.
out = out.merge(base[["cod6","cidade"]], on="cod6", how="left")
out["cres_chave_nome"] = out.uf.map(norm) + "|" + out.cidade.map(norm)
out.drop(columns=["uf","cidade"]).to_parquet(trabalho("_cres_extra.parquet"), index=False)
print(f"\n-> _cres_extra.parquet  ({len(out):,} municipios)")
print("\ncobertura:", {c: f"{out[c].notna().mean():.0%}" for c in
      ["cres_serie","cres_salario","cres_setor","cres_uf_mediana"]})
