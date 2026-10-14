# -*- coding: utf-8 -*-
"""T7 — calibracao de velocidade (descritivo): tempo de carro no nosso grafo x OSRM publico (perfil car, sem transito).

~40 pares origem Ultra (confianca alta) -> academia a 1-6 km, em 4 metros (DF, SP, RJ, BH). OSRM: 1 requisicao
por par com pausa de 1,1 s (servidor de demonstracao, uso leve). Coordenadas enviadas: unidades Ultra e academias
(enderecos publicos de estabelecimentos). Saida: testes_v2/calibracao_osrm.csv e resumo no stdout.
"""
import importlib.util
import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

ISO = Path(r"C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\9259d0a1-7dda-49bd-a390-c88f3d4ac1a6\scratchpad\iso")
spec = importlib.util.spec_from_file_location("iso03", ISO / "03_isocronas.py"); iso03 = importlib.util.module_from_spec(spec); spec.loader.exec_module(iso03)
OUT = ISO / "testes_v2"; OUT.mkdir(exist_ok=True)
METROS = {1: 10, 0: 12, 5: 10, 27: 8}  # metro -> n de pares
rng = np.random.default_rng(42)


def hav_km(la1, lo1, la2, lo2):
    p = np.pi / 180
    a = np.sin((la2 - la1) * p / 2) ** 2 + np.cos(la1 * p) * np.cos(la2 * p) * np.sin((lo2 - lo1) * p / 2) ** 2
    return 2 * 6371 * np.arcsin(np.sqrt(a))


def main():
    metros = {m["id"]: m for m in json.load(open(ISO / "metros.json", encoding="utf-8"))}
    u = pd.read_parquet(ISO / "ultra_pontos.parquet"); u = u[u["confianca"].eq("alta")]
    a = pd.read_parquet(ISO / "academias_pontos.parquet")
    linhas = []
    for mid, npar in METROS.items():
        mtr = metros[mid]
        nodes, csr, _ = iso03.montar(mid, "carro")
        x, y = iso03.proj(nodes["lat"].to_numpy(), nodes["lng"].to_numpy(), mtr["lat_c"], mtr["lng_c"])
        from scipy.sparse.csgraph import connected_components
        _, lab = connected_components(csr, directed=True, connection="weak")
        tam = np.bincount(lab); eleg = np.nonzero((np.diff(csr.indptr) > 0) & (tam[lab] >= 1000))[0]
        tree = cKDTree(np.c_[x[eleg], y[eleg]])
        um = u[u["lat"].between(mtr["lat_min"], mtr["lat_max"]) & u["lng"].between(mtr["lng_min"], mtr["lng_max"])]
        am = a[a["lat"].between(mtr["lat_min"], mtr["lat_max"]) & a["lng"].between(mtr["lng_min"], mtr["lng_max"])]
        pares = []
        for _, o in um.sample(frac=1, random_state=int(mid)).iterrows():
            d = hav_km(o["lat"], o["lng"], am["lat"].to_numpy(), am["lng"].to_numpy())
            cand = am[(d >= 1.0) & (d <= 6.0)]
            if len(cand):
                pares.append((o, cand.iloc[int(rng.integers(0, len(cand)))]))
            if len(pares) >= npar:
                break
        for o, dst in pares:
            ox, oy = iso03.proj(o["lat"], o["lng"], mtr["lat_c"], mtr["lng_c"]); dx, dy = iso03.proj(dst["lat"], dst["lng"], mtr["lat_c"], mtr["lng_c"])
            _, io = tree.query([ox, oy]); _, idd = tree.query([dx, dy])
            t_nosso = float(dijkstra(csr, directed=True, indices=eleg[io], limit=3600)[eleg[idd]])
            try:
                r = requests.get(f"https://router.project-osrm.org/route/v1/driving/{o['lng']:.6f},{o['lat']:.6f};{dst['lng']:.6f},{dst['lat']:.6f}",
                                 params={"overview": "false"}, headers={"User-Agent": "motor-expansao-ultra/calibracao (analise interna)"}, timeout=30)
                js = r.json(); rt = js["routes"][0]
                t_osrm, d_osrm = float(rt["duration"]), float(rt["distance"])
            except Exception as exc:  # noqa: BLE001
                t_osrm = d_osrm = np.nan; print("osrm falhou:", exc)
            time.sleep(1.1)
            linhas.append({"metro": mid, "origem": o["unidade_id"], "destino": dst["id"], "dist_reta_km": float(hav_km(o["lat"], o["lng"], dst["lat"], dst["lng"])),
                           "t_nosso_s": t_nosso, "t_osrm_s": t_osrm, "d_osrm_m": d_osrm})
            print(f"metro {mid} {o['unidade_id']:<24} reta {linhas[-1]['dist_reta_km']:.1f} km | nosso {t_nosso/60:5.1f} min | osrm {t_osrm/60:5.1f} min", flush=True)
    df = pd.DataFrame(linhas)
    df["razao_osrm_sobre_nosso"] = df["t_osrm_s"] / df["t_nosso_s"]
    df.to_csv(OUT / "calibracao_osrm.csv", sep=";", encoding="utf-8-sig", index=False)
    ok = df.dropna(subset=["razao_osrm_sobre_nosso"])
    ok = ok[np.isfinite(ok["razao_osrm_sobre_nosso"])]
    q = ok["razao_osrm_sobre_nosso"].quantile([0.25, 0.5, 0.75])
    print(f"\nN={len(ok)} pares | razao OSRM/nosso: mediana {q[0.5]:.2f} (IQR {q[0.25]:.2f}-{q[0.75]:.2f}) | por metro: {ok.groupby('metro')['razao_osrm_sobre_nosso'].median().round(2).to_dict()}")
    print(f"velocidade media implicita: nosso {(ok['d_osrm_m']/ok['t_nosso_s']*3.6).median():.1f} km/h | OSRM {(ok['d_osrm_m']/ok['t_osrm_s']*3.6).median():.1f} km/h (mesma distancia de rota do OSRM)")


if __name__ == "__main__":
    main()
