# -*- coding: utf-8 -*-
"""Receita Federal, dados abertos do CNPJ (set/2026), tabela Estabelecimentos -> data/staging/poi/cnpj_ativos_<UF>.parquet

So' estabelecimentos ATIVOS (situacao cadastral 02). PRIVACIDADE: nome fantasia, telefones, e-mail e o proprio CNPJ
sao descartados na leitura (empresas individuais/MEI identificam pessoas). Guarda: CNAE principal, CNAE secundario
(texto), matriz/filial, data de inicio, CEP, numero, bairro, UF, municipio (codigo Receita).
Geocodificacao pelo CNEFE 2022 (02_cnefe.py): (CEP, numero) exato -> senao centroide do CEP -> senao sem coordenada.
Uso: venv-iso\\python 03_cnpj.py <arquivo Estabelecimentos N> | --geocodificar <UF ...>
"""
import io
import sys
import time
import zipfile
from pathlib import Path

import pandas as pd

RAW = Path(r"C:\dev\motor-de-expansao\data\raw\receita_cnpj\2026-09")
OUT = Path(r"C:\dev\motor-de-expansao\data\staging\poi"); OUT.mkdir(parents=True, exist_ok=True)
TMP = OUT / "_cnpj_tmp"; TMP.mkdir(exist_ok=True)
COLS = {3: "matriz_filial", 5: "situacao", 10: "data_inicio", 11: "cnae_principal", 12: "cnae_secundario", 15: "numero", 17: "bairro", 18: "cep", 19: "uf", 20: "municipio_rf"}


def ler(n):
    t0 = time.time(); tot = 0
    with zipfile.ZipFile(RAW / f"Estabelecimentos{n}.zip") as z:
        nome = z.namelist()[0]
        with z.open(nome) as f:
            for i, b in enumerate(pd.read_csv(io.TextIOWrapper(f, encoding="latin-1"), sep=";", header=None, usecols=list(COLS), dtype=str, chunksize=1_000_000)):
                b = b.rename(columns=COLS)
                b = b[b["situacao"] == "02"].drop(columns=["situacao"])
                tot += len(b)
                for uf, g in b.groupby("uf"):
                    g.to_parquet(TMP / f"{uf}_{n}_{i}.parquet", index=False)
    print(f"Estabelecimentos{n}: {tot:,} ativos em {time.time()-t0:.0f}s", flush=True)


def geocodificar(uf):
    t0 = time.time()
    fs = sorted(TMP.glob(f"{uf}_*.parquet"))
    if not fs:
        print(uf, "sem arquivos"); return
    d = pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True)
    d["numero"] = d["numero"].fillna("").str.strip().str.lstrip("0").replace({"S/N": "", "SN": ""})
    cn = pd.read_parquet(OUT / f"cnefe_cep_numero_{uf}.parquet"); cn["numero"] = cn["numero"].astype(str).str.lstrip("0")
    ce = pd.read_parquet(OUT / f"cnefe_cep_{uf}.parquet")
    d = d.merge(cn[["cep", "numero", "lat", "lng"]], on=["cep", "numero"], how="left")
    sem = d["lat"].isna()
    m2 = d.loc[sem, ["cep"]].merge(ce[["cep", "lat", "lng"]], on="cep", how="left")
    d.loc[sem, "lat"] = m2["lat"].to_numpy(); d.loc[sem, "lng"] = m2["lng"].to_numpy()
    d["geo_nivel"] = "cep_numero"; d.loc[sem, "geo_nivel"] = "cep"; d.loc[d["lat"].isna(), "geo_nivel"] = "sem_coordenada"
    d["cnae_divisao"] = d["cnae_principal"].str[:2]
    d.to_parquet(OUT / f"cnpj_ativos_{uf}.parquet", index=False)
    for f in fs:
        f.unlink()
    print(f"[{uf}] {len(d):,} ativos | geo: {d.geo_nivel.value_counts(normalize=True).round(3).to_dict()} | {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "--geocodificar":
        for u in sys.argv[2:]:
            geocodificar(u)
    else:
        for n in sys.argv[1:]:
            ler(n)
