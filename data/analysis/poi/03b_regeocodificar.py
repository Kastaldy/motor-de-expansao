# -*- coding: utf-8 -*-
"""Corrige a geocodificacao do CNPJ (03_cnpj.py) apontada pela revisao de 2026-09-25, sem baixar nada:

  1. numero vazio (S/N) casava com o endereco "0" do CNEFE e era rotulado exato -> passa a nivel CEP
  2. CEP de AREA (mais de CEP_AREA_MIN enderecos no CNEFE: CEP de cidade inteira ou de bairro grande):
     o mesmo numero existe em varias ruas, entao nem o casamento (CEP, numero) localiza -> nivel cnpj_cep_area
  3. CEP que nao existe no CNEFE (grande usuario, CEP novo): antes ficava sem coordenada -> centroide dos
     enderecos com o mesmo prefixo de 5 digitos (cnpj_cep5), se houver
Niveis finais (geo_nivel): cnpj_cep_numero | cnpj_cep | cnpj_cep_area | cnpj_cep5 | cnpj_sem_coordenada
(o prefixo "cnpj_" e' posto no 04; aqui os valores sao cep_numero | cep | cep_area | cep5 | sem_coordenada).
Reescreve data/staging/poi/cnpj_ativos_<UF>.parquet no lugar. Uso: venv-iso\\python 03b_regeocodificar.py <UF ...>|--todas
"""
import sys
import time
from pathlib import Path

import pandas as pd

POI = Path(r"C:\dev\motor-de-expansao\data\staging\poi")
CEP_AREA_MIN = 2000  # fixado antes de olhar desfecho (p99 de enderecos por CEP em SP = 668)


def regeo(uf):
    t0 = time.time()
    f = POI / f"cnpj_ativos_{uf}.parquet"
    d = pd.read_parquet(f).drop(columns=["lat", "lng", "geo_nivel"], errors="ignore")
    cn = pd.read_parquet(POI / f"cnefe_cep_numero_{uf}.parquet")
    cn["numero"] = cn["numero"].astype(str).str.lstrip("0")
    cn = cn[cn.numero != ""]  # endereco sem numero no CNEFE nao serve de casamento exato
    cn = cn.sort_values("n", ascending=False).drop_duplicates(["cep", "numero"])  # "010" e "10" colapsam
    ce = pd.read_parquet(POI / f"cnefe_cep_{uf}.parquet")
    area = set(ce.loc[ce.n > CEP_AREA_MIN, "cep"])
    d["numero"] = d["numero"].fillna("").astype(str).str.strip().str.lstrip("0")
    # 1) exato: numero nao vazio, CEP nao-area
    m = d.merge(cn[["cep", "numero", "lat", "lng"]], on=["cep", "numero"], how="left")
    assert len(m) == len(d)
    exato = m.lat.notna() & (d.numero != "") & ~d.cep.isin(area)
    d["lat"] = m.lat.where(exato); d["lng"] = m.lng.where(exato)
    d["geo_nivel"] = pd.Series("sem_coordenada", index=d.index).mask(exato, "cep_numero")
    # 2) centroide do CEP (rotulado cep_area quando o CEP e' de area)
    sem = d.lat.isna()
    m2 = d.loc[sem, ["cep"]].merge(ce[["cep", "lat", "lng"]], on="cep", how="left")
    d.loc[sem, "lat"] = m2.lat.to_numpy(); d.loc[sem, "lng"] = m2.lng.to_numpy()
    tem = sem & d.lat.notna()
    d.loc[tem, "geo_nivel"] = "cep"
    d.loc[tem & d.cep.isin(area), "geo_nivel"] = "cep_area"
    # 3) prefixo de 5 digitos
    ce["cep5"] = ce.cep.str[:5]
    c5 = ce.assign(_la=ce.lat * ce.n, _lo=ce.lng * ce.n).groupby("cep5")[["_la", "_lo", "n"]].sum()
    c5 = pd.DataFrame({"lat5": c5._la / c5.n, "lng5": c5._lo / c5.n})
    sem = d.lat.isna()
    m3 = d.loc[sem, ["cep"]].assign(cep5=lambda x: x.cep.str[:5]).merge(c5, left_on="cep5", right_index=True, how="left")
    d.loc[sem, "lat"] = m3.lat5.to_numpy(); d.loc[sem, "lng"] = m3.lng5.to_numpy()
    d.loc[sem & d.lat.notna(), "geo_nivel"] = "cep5"
    d.to_parquet(f, index=False)
    print(f"[{uf}] {len(d):,} | {d.geo_nivel.value_counts(normalize=True).round(3).to_dict()} | {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    ufs = sys.argv[1:]
    if ufs == ["--todas"]:
        ufs = sorted(p.stem.split("_")[-1] for p in POI.glob("cnpj_ativos_*.parquet"))
    for u in ufs:
        regeo(u)
