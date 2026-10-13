# -*- coding: utf-8 -*-
"""Multirede — etapa 2: isocronas (carro 5/10, a pe' 10/15) e atributos para as unidades Ultra/EdC/SkyFit.

Reusa 03 (processar_lote, regras v2: componente >= 1.000 nos) e 04 (Contexto, atributos_poligono).
Auto-exclusao da oferta: academias a < 75 m da unidade (a propria unidade aparece no cadastro de concorrentes
com coordenada ligeiramente diferente). Um processo, metro por metro; pula metros ja' feitos.
Uso: venv-iso\\python 11_iso_multirede.py [metro ...]
Saida: iso/multirede/atributos/metro_<id>.parquet
"""
import importlib.util
import json
import math
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("ISO_VERSAO", "_v2")
import geopandas as gpd  # noqa: E402
import h3  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from shapely import wkb  # noqa: E402
from shapely.geometry import Point, Polygon  # noqa: E402

ISO = Path(r"C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\9259d0a1-7dda-49bd-a390-c88f3d4ac1a6\scratchpad\iso")
def carregar(nome, arq):
    spec = importlib.util.spec_from_file_location(nome, ISO / arq); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
i03 = carregar("i03", "03_isocronas.py"); i04 = carregar("i04", "04_atributos.py")
i03.CENARIOS = {"carro": [300, 600], "pe": [600, 900]}
i04.AUTO_M = 75.0
MR = ISO / "multirede"; OUT = MR / "atributos"; OUT.mkdir(exist_ok=True)


def main(argv):
    pts = pd.read_parquet(MR / "pontos.parquet")
    metros = {m["id"]: m for m in json.load(open(ISO / "metros.json", encoding="utf-8")) + json.load(open(MR / "metros_novos.json", encoding="utf-8"))}
    ids = [int(a) for a in argv] or sorted(pts["metro"].unique())
    for mid in ids:
        if (OUT / f"metro_{mid}.parquet").exists():
            continue
        if not (ISO / "grafo" / f"metro_{mid}" / "edges.parquet").exists():
            print(f"metro {mid}: sem grafo ({(pts.metro == mid).sum()} pontos)"); continue
        t0 = time.time(); mtr = metros[mid]
        alvos = pts[pts["metro"] == mid][["ponto_id", "lat", "lng", "marca"]].rename(columns={"marca": "subtipo"}).reset_index(drop=True)
        alvos["tipo"] = "multirede"
        iso = pd.concat([i03.processar_lote((mid, modo, 0, alvos, mtr["lat_c"], mtr["lng_c"], mtr)) for modo in ("carro", "pe")], ignore_index=True)
        g = i04.setores_no_bbox(mtr)
        acad = pd.read_parquet(ISO / "academias_pontos.parquet")
        acad = acad[acad["lat"].between(mtr["lat_min"], mtr["lat_max"]) & acad["lng"].between(mtr["lng_min"], mtr["lng_max"])].reset_index(drop=True)
        ult = pd.read_parquet(ISO / "ultra_pontos.parquet").dropna(subset=["lat"])
        ult = ult[ult["lat"].between(mtr["lat_min"], mtr["lat_max"]) & ult["lng"].between(mtr["lng_min"], mtr["lng_max"])]
        ctx = i04.Contexto(g, acad, ult)
        gp = gpd.GeoSeries([Point(x, y) for x, y in zip(alvos["lng"], alvos["lat"])], crs=4326).to_crs(5880)
        xy = {pid: (p.x, p.y) for pid, p in zip(alvos["ponto_id"], gp.values)}
        polys = gpd.GeoSeries([wkb.loads(b) if b is not None else None for b in iso["poligono_wkb"]], crs=4326).to_crs(5880)
        linhas, area_iso = [], {}
        for r, p in zip(iso.itertuples(index=False), polys.values):
            cen = f"{r.modo}_{int(r.limite_s)//60}min"
            base = {"ponto_id": r.ponto_id, "subtipo": r.subtipo, "metro": mid, "cenario": cen, "snap_dist_m": r.snap_dist_m, "n_nos": r.n_nos,
                    "km_rua": r.km_rua, "area_km2": r.area_km2, "truncada": r.truncada}
            if p is None or p.is_empty:
                linhas.append(base); continue
            if cen in ("carro_5min", "pe_15min"):
                area_iso[(r.ponto_id, cen)] = p.area
            linhas.append({**base, **i04.atributos_poligono(p, ctx, xy[r.ponto_id])})
        for pid, p in zip(alvos["ponto_id"], gp.values):
            linhas.append({"ponto_id": pid, "metro": mid, "cenario": "circulo_1km", "area_km2": math.pi, **i04.atributos_poligono(p.buffer(1000.0), ctx, (p.x, p.y))})
            for cen in ("carro_5min", "pe_15min"):
                a = area_iso.get((pid, cen))
                if a:
                    linhas.append({"ponto_id": pid, "metro": mid, "cenario": f"circeq_{cen}", "area_km2": a / 1e6, **i04.atributos_poligono(p.buffer(math.sqrt(a / math.pi)), ctx, (p.x, p.y))})
            r0 = alvos[alvos.ponto_id == pid].iloc[0]
            hexp = gpd.GeoSeries([Polygon([(lng, lat) for lat, lng in h3.cell_to_boundary(h3.latlng_to_cell(r0.lat, r0.lng, 7))])], crs=4326).to_crs(5880).iloc[0]
            linhas.append({"ponto_id": pid, "metro": mid, "cenario": "hex_r7", "area_km2": hexp.area / 1e6, **i04.atributos_poligono(hexp, ctx, (p.x, p.y))})
        pd.DataFrame(linhas).to_parquet(OUT / f"metro_{mid}.parquet", index=False)
        iso.drop(columns=["poligono_wkb"]).to_parquet(OUT / f"iso_metro_{mid}.parquet", index=False)
        iso[["ponto_id", "modo", "limite_s", "poligono_wkb"]].to_parquet(OUT / f"poligonos_metro_{mid}.parquet", index=False)
        print(f"metro {mid}: {len(alvos)} pontos em {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
