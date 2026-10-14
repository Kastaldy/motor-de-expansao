# -*- coding: utf-8 -*-
"""Multirede — etapa 1: universo de unidades (Ultra, Engenharia do Corpo, SkyFit) e caixas novas de grafo.

Entrada: data/staging/base_calibracao_multirede.parquet (426 unidades com alunos_reais; metragem so' Ultra/EdC).
Unidade a >= 6 km da borda de uma das 46 caixas existentes usa aquela caixa; as demais ganham caixas novas
(DBSCAN 35 km, margem 12 km), ids a partir de 100. Saidas em iso/multirede/:
  pontos.parquet  (ponto_id, marca, unidade, uf, cidade, lat, lng, alunos_reais, metragem, metro)
  metros_novos.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN

ISO = Path(r"C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\9259d0a1-7dda-49bd-a390-c88f3d4ac1a6\scratchpad\iso")
REPO = Path(r"C:\dev\motor-de-expansao")
OUT = ISO / "multirede"; OUT.mkdir(exist_ok=True)
RECUO_KM = 6.0


def main():
    d = pd.read_parquet(REPO / "data/staging/base_calibracao_multirede.parquet").dropna(subset=["lat", "lng"]).reset_index(drop=True)
    d["ponto_id"] = d["marca"] + "|" + d["unidade"].astype(str) + "|" + d.index.astype(str)
    metros = json.load(open(ISO / "metros.json", encoding="utf-8"))
    def caixa(r):
        for b in metros:
            dl = RECUO_KM / 110.54; dg = RECUO_KM / (111.32 * np.cos(np.radians(b["lat_c"])))
            if b["lat_min"] + dl <= r.lat <= b["lat_max"] - dl and b["lng_min"] + dg <= r.lng <= b["lng_max"] - dg:
                return b["id"]
        return -1
    d["metro"] = [caixa(r) for r in d.itertuples()]
    fora = d[d["metro"] == -1]
    lab = DBSCAN(eps=35 / 111.0, min_samples=1).fit(fora[["lat", "lng"]].values).labels_
    novos = []
    for cl in np.unique(lab):
        g = fora[lab == cl]; mid = 100 + int(cl)
        mlat = 12 / 111.0; mlng = 12 / (111.0 * np.cos(np.radians(g["lat"].mean())))
        novos.append({"id": mid, "n_pontos": int(len(g)), "lat_min": float(g["lat"].min() - mlat), "lat_max": float(g["lat"].max() + mlat),
                      "lng_min": float(g["lng"].min() - mlng), "lng_max": float(g["lng"].max() + mlng), "lat_c": float(g["lat"].mean()), "lng_c": float(g["lng"].mean())})
        d.loc[g.index, "metro"] = mid
    d.to_parquet(OUT / "pontos.parquet", index=False)
    json.dump(novos, open(OUT / "metros_novos.json", "w", encoding="utf-8"), indent=1)
    area = sum((m["lat_max"] - m["lat_min"]) * 111 * (m["lng_max"] - m["lng_min"]) * 111 * np.cos(np.radians(m["lat_c"])) for m in novos)
    print(d.assign(existente=d["metro"] < 100).groupby("marca")["existente"].agg(["size", "sum"]).rename(columns={"size": "n", "sum": "em_caixa_existente"}).to_string())
    print(f"caixas novas: {len(novos)} | area total {area:,.0f} km2 | maiores: {sorted([m['n_pontos'] for m in novos], reverse=True)[:10]}")


if __name__ == "__main__":
    main()
