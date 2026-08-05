# -*- coding: utf-8 -*-
"""O que o projeto Crescimento Regional TEC ja apura por municipio, pronto para exibir.
Nada de reconstruir, nada de validar: so ver o que existe e como ler facil."""
import pandas as pd, numpy as np, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
C = r"C:\Users\Juan.lima\OneDrive - Grupo Ultra\Área de Trabalho\Crescimento Regional TEC\output"

b  = pd.read_csv(rf"{C}\indices_crescimento_municipal.csv", low_memory=False)
cm = pd.read_csv(rf"{C}\crescimento_municipio.csv", low_memory=False)
cn = pd.read_csv(rf"{C}\indices_desenvolvimento_municipal.csv", low_memory=False)
for d in (b, cm, cn): d["cod6"] = d.cod6.astype(str).str.zfill(6)

d = (b[["cod6","cidade","uf","confiabilidade","pop_2024","vinculos_2024","rem_media_2024",
        "massa_cresc","vinculos_cresc","pib_cresc","rem_cresc","pop_cresc","emprego_momentum"]]
     .merge(cm[["cod6","tendencia","emp_cresc_pct","pib_cresc_pct","cempre_cresc_pct","mat_label"]], on="cod6", how="left")
     .merge(cn[["cod6","saldo","aberturas","fechamentos","idx_dinamismo"]], on="cod6", how="left"))
print(f"municipios: {len(d):,}  (cobertura NACIONAL)\n")

print("=== TENDENCIA — o resumo que o projeto ja calcula ===")
print(d.tendencia.value_counts(dropna=False).to_string())
print()
print("=== os numeros CRUS que dao para mostrar (ja sao percentuais reais) ===")
COLS = [("emp_cresc_pct","emprego formal, % 2020->2026"),
        ("pib_cresc_pct","PIB, % 2019->2023"),
        ("cempre_cresc_pct","empresas CEMPRE, %"),
        ("pop_cresc","populacao, fracao 2019->2021"),
        ("massa_cresc","massa salarial, fracao 2020->2024"),
        ("vinculos_cresc","vinculos, fracao 2020->2024"),
        ("saldo","saldo de empresas CNPJ 2020-2025, unidades")]
q = [.10,.25,.50,.75,.90]
print(f"{'coluna':<20}{'rotulo':<36}" + "".join(f"{f'p{int(x*100)}':>10}" for x in q) + f"{'nulos':>8}")
for c, rot in COLS:
    if c not in d: continue
    v = d[c].quantile(q)
    print(f"{c:<20}{rot:<36}" + "".join(f"{v[x]:>10,.1f}" for x in q) + f"{d[c].isna().mean():>7.1%}")

print("\n=== tendencia x numeros (a tendencia bate com o que ela promete?) ===")
print(d.groupby("tendencia", observed=True).agg(
    municipios=("cod6","size"),
    emprego_pct=("emp_cresc_pct","median"),
    pib_pct=("pib_cresc_pct","median"),
    saldo_empresas=("saldo","median"),
    pop_2024=("pop_2024","median")).round(1).to_string())

print("\n=== confiabilidade (o proprio projeto marca onde o dado e fraco) ===")
print(d.confiabilidade.value_counts(dropna=False).to_string())

print("\n=== exemplos de leitura ===")
for c in ["Sorocaba","Goiânia","Extrema","Indaiatuba","Juazeiro"]:
    r = d[d.cidade.astype(str).str.contains(c, case=False, na=False)].nlargest(1,"pop_2024")
    if len(r):
        r = r.iloc[0]
        print(f"  {str(r.cidade)[:20]:<20}{r.uf}  {str(r.tendencia):<9} | emprego {r.emp_cresc_pct:>6.1f}% | "
              f"PIB {r.pib_cresc_pct:>6.1f}% | empresas {r.saldo:>+7,.0f} | conf. {r.confiabilidade}")
d.to_parquet("_mun_cresc_bruto.parquet", index=False)
print("\n-> _mun_cresc_bruto.parquet")
