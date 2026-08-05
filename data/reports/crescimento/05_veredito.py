# -*- coding: utf-8 -*-
"""Junta as 5 dimensoes ao artefato da camada e monta o VEREDITO em linguagem de
decisao. A regra e simples e auditavel de proposito: conta quantas dimensoes estao
claramente acima da mediana nacional e cruza com o porte de mercado."""
import pandas as pd, numpy as np, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
API = r"C:\Users\Juan.lima\OneDrive - Grupo Ultra\Área de Trabalho\APIGeoEspacial"

d = pd.read_parquet("_dims.parquet")
d["cod6"] = d.cod6.astype(str).str.zfill(6)
DIMS = ["renda","pop","empresas","predios","emprego"]
ROT = {"renda":"renda","pop":"população","empresas":"empresas","predios":"prédios","emprego":"emprego"}

ALTA, BAIXA = 60.0, 40.0     # percentil nacional: acima de 60 = claramente acima da mediana
pos = d[[f"pos_{k}" for k in DIMS]]
d["v_n_alta"]  = (pos >= ALTA).sum(axis=1)
d["v_n_baixa"] = (pos <= BAIXA).sum(axis=1)

def quais(row, alto=True):
    ks = [ROT[k] for k in DIMS
          if pd.notna(row[f"pos_{k}"]) and ((row[f"pos_{k}"] >= ALTA) if alto else (row[f"pos_{k}"] <= BAIXA))]
    if not ks: return ""
    if len(ks) == 1: return ks[0]
    return ", ".join(ks[:-1]) + " e " + ks[-1]
d["v_quais_alta"]  = d.apply(lambda r: quais(r, True), axis=1)
d["v_quais_baixa"] = d.apply(lambda r: quais(r, False), axis=1)

madura = d.mat_label.eq("Já madura")
d["v_classe"] = np.select(
    [(d.v_n_alta >= 3) & madura,
     (d.v_n_alta >= 3) & ~madura,
     (d.v_n_baixa >= 3),
     (d.v_n_alta >= 2)],
    ["entrar", "acompanhar", "evitar", "observar"],
    default="estavel")

def frase(r):
    alta, baixa, cid = r.v_quais_alta, r.v_quais_baixa, r.cidade
    if r.v_classe == "entrar":
        return (f"{cid} cresceu em {alta}, e já tem porte de mercado para uma unidade. "
                "É praça para entrar.")
    if r.v_classe == "acompanhar":
        return (f"{cid} cresceu em {alta}, mas ainda não tem porte de mercado. "
                "Vale ficar de olho, não abrir agora.")
    if r.v_classe == "evitar":
        return (f"{cid} está abaixo da mediana nacional em {baixa}. "
                "A praça vem perdendo tração.")
    if r.v_classe == "observar":
        return f"{cid} cresceu em {alta}. Os demais indicadores estão na média do país."
    return f"{cid} está próxima da mediana nacional na maioria dos indicadores."
d["v_frase"] = d.apply(frase, axis=1)

print("=== distribuicao do veredito ===")
print(d.v_classe.value_counts().to_string())
print(f"\n'entrar' que ainda NAO tem Ultra: nao medido aqui (depende do artefato do Motor)")

art = pd.read_parquet(rf"{API}\staging\crescimento_municipal.parquet")
art["cod6"] = art.cod6.astype(str).str.zfill(6)
cols = (["cod6","dim_media","v_classe","v_frase","v_n_alta","v_n_baixa"]
        + [f"pos_{k}" for k in DIMS]
        + ["dim_renda_pct","dim_pop_pct","dim_empresas_por1k","dim_predios_pct",
           "dim_altura_pct","dim_emprego_pct"])
art = art.merge(d[cols], on="cod6", how="left")
art.to_parquet(rf"{API}\staging\crescimento_municipal.parquet", index=False)
print(f"\n-> artefato atualizado: {len(art):,} municipios, {len(art.columns)} colunas")

print("\n=== exemplos ===")
for c in ["Goianésia","Sorocaba","Extrema","Osasco"]:
    r = d[d.cidade.astype(str).str.contains(c, case=False, na=False)].nlargest(1,"pop_2024")
    if len(r):
        r = r.iloc[0]
        print(f"\n  {r.cidade}/{r.uf}  [{r.v_classe}]  media {r.dim_media:.0f}")
        print(f"    renda {r.dim_renda_pct:+.0f}% | pop {r.dim_pop_pct:+.1f}% | empresas {r.dim_empresas_por1k:.0f}/mil "
              f"| prédios {r.dim_predios_pct:+.0f}% | emprego {r.dim_emprego_pct:+.1f}%")
        print(f"    {r.v_frase}")
