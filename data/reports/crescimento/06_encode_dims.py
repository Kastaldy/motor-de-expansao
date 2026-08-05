# -*- coding: utf-8 -*-
"""Codifica as 5 dimensoes num campo unico para o front: nome:valor:unidade:posicao,
separados por ';'. Evita 10 colunas novas no contrato da API para a mesma informacao."""
import pandas as pd, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
API = r"C:\Users\Juan.lima\OneDrive - Grupo Ultra\Área de Trabalho\APIGeoEspacial"
a = pd.read_parquet(rf"{API}\staging\crescimento_municipal.parquet")

SPEC = [("Renda",      "dim_renda_pct",       "%",   "pos_renda"),
        ("População",  "dim_pop_pct",         "%",   "pos_pop"),
        ("Empresas",   "dim_empresas_por1k",  "/mil","pos_empresas"),
        ("Prédios",    "dim_predios_pct",     "%",   "pos_predios"),
        ("Emprego",    "dim_emprego_pct",     "%",   "pos_emprego")]

def linha(r):
    out = []
    for nome, cv, un, cp in SPEC:
        v, p = r.get(cv), r.get(cp)
        if pd.isna(v) or pd.isna(p):
            continue
        out.append(f"{nome}:{v:.1f}:{un}:{p:.0f}")
    return ";".join(out) if out else None

a["cres_dims"] = a.apply(linha, axis=1)
a.to_parquet(rf"{API}\staging\crescimento_municipal.parquet", index=False)
print(f"-> cres_dims gravado | preenchido em {a.cres_dims.notna().mean():.1%} dos municipios")
print(f"   com as 5 dimensoes: {a.cres_dims.fillna('').str.count(';').eq(4).mean():.1%}")
ex = a[a.cres_dims.notna()].iloc[0]
print(f"\nexemplo cod6={ex.cod6}:")
for p in str(ex.cres_dims).split(";"): print("   ", p)
