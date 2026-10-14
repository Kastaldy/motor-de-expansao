# -*- coding: utf-8 -*-
"""IBGE CNEFE 2022 (enderecos geocodificados do Censo) -> por UF, em data/staging/poi/:
  cnefe_estab_<UF>.parquet  : enderecos NAO residenciais (especie 4 agropecuario, 5 ensino, 6 saude,
                              7 outras finalidades) com lat/lng, CEP, setor censitario
  cnefe_cep_<UF>.parquet    : geocodificador por CEP (+ numero): mediana de lat/lng por (CEP, numero) e por CEP
Le o CSV em blocos (um UF por execucao). Uso: venv-iso\\python 02_cnefe.py <UF> [<UF> ...]
"""
import io
import sys
import time
import zipfile
from pathlib import Path

import pandas as pd

RAW = Path(r"C:\dev\motor-de-expansao\data\raw\ibge_cnefe_2022\UF")
OUT = Path(r"C:\dev\motor-de-expansao\data\staging\poi"); OUT.mkdir(parents=True, exist_ok=True)
ESPECIE = {1: "domicilio_particular", 2: "domicilio_coletivo", 3: "agropecuario", 4: "ensino", 5: "saude", 6: "outras_finalidades", 7: "em_construcao", 8: "religioso"}
COLS = ["COD_SETOR", "CEP", "NUM_ENDERECO", "LATITUDE", "LONGITUDE", "NV_GEO_COORD", "COD_ESPECIE", "COD_INDICADOR_ESTAB_ENDERECO"]


def processar(uf):
    t0 = time.time()
    arq = next(RAW.glob(f"*_{uf}.zip"))
    estab, cep_num = [], []
    with zipfile.ZipFile(arq) as z:
        nome = [n for n in z.namelist() if n.lower().endswith(".csv")][0]
        with z.open(nome) as f:
            cab = f.readline().decode("latin-1").strip().split(";")
            usar = [c for c in COLS if c in cab]
            f.seek(0) if f.seekable() else None
        with z.open(nome) as f:
            for bloco in pd.read_csv(io.TextIOWrapper(f, encoding="latin-1"), sep=";", usecols=usar, dtype=str, chunksize=1_000_000):
                bloco["lat"] = pd.to_numeric(bloco["LATITUDE"].str.replace(",", "."), errors="coerce")
                bloco["lng"] = pd.to_numeric(bloco["LONGITUDE"].str.replace(",", "."), errors="coerce")
                bloco = bloco.dropna(subset=["lat", "lng"])
                esp = pd.to_numeric(bloco["COD_ESPECIE"], errors="coerce")
                e = bloco[esp.isin([3, 4, 5, 6, 8])]
                estab.append(pd.DataFrame({"cod_setor": e["COD_SETOR"], "cep": e["CEP"], "lat": e["lat"], "lng": e["lng"],
                                           "especie": esp[esp.isin([3, 4, 5, 6, 8])].map(ESPECIE), "nv_geo": e.get("NV_GEO_COORD"), "multi_estab": e.get("COD_INDICADOR_ESTAB_ENDERECO")}))
                g = bloco.groupby(["CEP", "NUM_ENDERECO"], observed=True).agg(lat=("lat", "median"), lng=("lng", "median"), n=("lat", "size")).reset_index()
                cep_num.append(g)
    es = pd.concat(estab, ignore_index=True); es["uf"] = uf
    es.to_parquet(OUT / f"cnefe_estab_{uf}.parquet", index=False)
    cn = pd.concat(cep_num, ignore_index=True)
    def media_ponderada(df, chaves):
        df = df.assign(_la=df.lat * df.n, _lo=df.lng * df.n)
        g = df.groupby(chaves, observed=True)[["_la", "_lo", "n"]].sum().reset_index()
        g["lat"] = g._la / g.n; g["lng"] = g._lo / g.n
        return g.drop(columns=["_la", "_lo"])
    cn = media_ponderada(cn, ["CEP", "NUM_ENDERECO"])
    cep = media_ponderada(cn, ["CEP"])
    cn.rename(columns={"CEP": "cep", "NUM_ENDERECO": "numero"}).assign(nivel="cep_numero").to_parquet(OUT / f"cnefe_cep_numero_{uf}.parquet", index=False)
    cep.rename(columns={"CEP": "cep"}).assign(nivel="cep").to_parquet(OUT / f"cnefe_cep_{uf}.parquet", index=False)
    print(f"[{uf}] {len(es):,} enderecos nao residenciais | {len(cn):,} (CEP, numero) | {len(cep):,} CEPs | {time.time()-t0:.0f}s | {es.especie.value_counts().to_dict()}", flush=True)


if __name__ == "__main__":
    for u in sys.argv[1:]:
        processar(u)
