# -*- coding: utf-8 -*-
"""Artefato do passo 4: COMO A CIDADE ESTA INDO.
So repassa o que o Crescimento Regional TEC ja apura. Nao reconstroi, nao prediz,
nao ranqueia oportunidade. Cobertura nacional."""
import pandas as pd, numpy as np, sys, glob
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from _raizes import artefato_municipal, outputs, trabalho  # noqa: E402
ART = artefato_municipal()

d = pd.read_parquet(trabalho("_mun_cresc_bruto.parquet"))

# --- confiabilidade nas cidades que o piloto realmente mostra ----------------
cart = pd.read_parquet(outputs("carteira_expansao_acionavel.parquet"),
                       columns=["cod_municipio","nome_municipio","uf"])
cart["cod6"] = cart.cod_municipio.astype(str).str[:6]
cc = d[d.cod6.isin(set(cart.cod6))]
print("=== confiabilidade: pais inteiro x cidades da CARTEIRA ===")
comp = pd.DataFrame({
    "pais": d.confiabilidade.value_counts(normalize=True),
    "carteira": cc.confiabilidade.value_counts(normalize=True)}).fillna(0).round(3) * 100
print(comp.round(1).to_string())
print(f"\ncidades da carteira: {len(cc):,} de {cart.cod6.nunique():,}")
print(f"  com confiabilidade alta ou media: {cc.confiabilidade.isin(['alta','media']).mean():.1%}")

# --- classes de tendencia, mapeadas na paleta do piloto ---------------------
# faixas da SCORE_BANDS_HEX: 8 = verde, 5 = amarelo neutro, 1 = vermelho
RAMPA = {"Em alta": 85.0, "Estavel": 55.0, "Em queda": 15.0}
d["cres_tendencia"] = d.tendencia
d["cres_ramp"] = d.tendencia.map(RAMPA)
# confiabilidade fraca -> sem cor (o proprio projeto diz que o dado nao sustenta)
fraco = d.confiabilidade.isin(["muito_baixa"])
d.loc[fraco, "cres_ramp"] = np.nan
d.loc[fraco, "cres_tendencia"] = None
print(f"\nsem leitura por confiabilidade muito baixa: {int(fraco.sum()):,} municipios ({fraco.mean():.1%})")
print(f"  destes, quantos estao na carteira: {int(fraco[d.cod6.isin(set(cart.cod6))].sum()):,}")

art = d[["cod6","cres_tendencia","cres_ramp","emp_cresc_pct","saldo","confiabilidade",
         "vinculos_2024","pop_2024"]].copy()
art.columns = ["cod6","cres_tendencia","cres_ramp","cres_emp_pct","cres_saldo_empresas",
               "cres_confiab","cres_vinculos","cres_pop"]
# as quatro leituras que um percentual sozinho nao da (ver t2_enriquecer.py)
extra = pd.read_parquet(trabalho("_cres_extra.parquet"))
extra["cod6"] = extra.cod6.astype(str).str.zfill(6)
art["cod6"] = art.cod6.astype(str).str.zfill(6)
art = art.merge(extra, on="cod6", how="left")
art["cres_emp_pct"] = art.cres_emp_pct.round(1)
art["cod6"] = art.cod6.astype(str).str.zfill(6)
p = ART
art.to_parquet(p, index=False)
import os; print(f"\n-> crescimento_municipal.parquet  ({len(art):,} municipios, {os.path.getsize(p)/1024:.0f} KB)")

print("\n=== distribuicao final das classes ===")
print(art.cres_tendencia.value_counts(dropna=False).to_string())
print("\n=== como fica a leitura ===")
for c in ["Sorocaba","Goiânia","Extrema","Indaiatuba","Uberlândia","Osasco"]:
    r = art.merge(d[["cod6","cidade","uf"]], on="cod6")
    r = r[r.cidade.astype(str).str.contains(c, case=False, na=False)].nlargest(1,"cres_pop")
    if len(r):
        r = r.iloc[0]
        t = r.cres_tendencia if pd.notna(r.cres_tendencia) else "sem leitura"
        print(f"  {str(r.cidade)[:18]:<18}{r.uf}  {t:<9} emprego {r.cres_emp_pct:>+6.1f}%  "
              f"empresas {r.cres_saldo_empresas:>+9,.0f}  conf. {r.cres_confiab}")
