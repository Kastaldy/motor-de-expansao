# -*- coding: utf-8 -*-
"""Etapa 4 — atributos por isocrona: populacao, renda, domicilios (setores censitarios 2022, ponderados por
fracao de area), oferta (academias dentro do poligono, por tipo, e oferta ponderada cadeia=1 / independente=0,5),
unidades Ultra dentro, e os mesmos atributos para o CIRCULO de 1 km e o HEXAGONO res-7 do ponto (comparacao).

v2 (ISO_VERSAO=_v2), correcoes da lente de qualidade e dos verificadores:
  * a academia NAO conta a si mesma na oferta (auto-contagem: 99-100% dos poligonos continham o proprio ponto);
  * CIRCULOS DE AREA EQUIVALENTE a isocrona (carro 5 min e a pe' 15 min), raio = sqrt(area/pi): separam o efeito
    de TAMANHO do catchment do efeito de FORMA da rede (T6);
  * poligonos > 40 km2 (carro 10/15 min) usam o ponto representativo do setor (setor entra inteiro se o ponto
    cai dentro) em vez da intersecao exata — declarado; nos poligonos pequenos segue a fracao de area;
  * repassa r_max_m / dist_borda_m / truncada do 03;
  * --parte k/n processa so' os pontos com indice % n == k (execucoes curtas em primeiro plano).

Uso: venv-iso\\python 04_atributos.py <metro_id> [--parte k/n]
Saida: SCRATCH/iso/atributos{SUF}/metro_<id>[_p<k>].parquet
"""
import json
import math
import os
import sys
import time
from pathlib import Path

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from shapely import make_valid, wkb
from shapely.geometry import Point, Polygon
from shapely.strtree import STRtree

SCRATCH = Path(r"C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\9259d0a1-7dda-49bd-a390-c88f3d4ac1a6\scratchpad")
REPO = Path(r"C:\dev\motor-de-expansao")
ISO = SCRATCH / "iso"
GEO = REPO / "data/outputs/setores_censitarios_2022_geo"
SUF = os.environ.get("ISO_VERSAO", "")
OUT = ISO / f"atributos{SUF}"
OUT.mkdir(exist_ok=True)
# 'cadeia_agregador_com_pin' = unidade de rede do WellHub que JA' colapsa contra um ponto de concorrentes_mapeados
# (DEC-034/035): contar de novo seria dupla contagem -> peso 0 e fora de n_academias.
PESO = {"cadeia_mapeada": 1.0, "cadeia_agregador_sem_pin": 1.0, "cadeia_agregador_com_pin": 0.0, "independente_agregador": 0.5}
AREA_RAPIDA_M2 = 40e6
AUTO_M = 2.0  # academia a < 2 m do alvo = a propria


def setores_no_bbox(mtr):
    frames = []
    for ufdir in GEO.glob("uf=*"):
        for mdir in ufdir.glob("cod_municipio=*"):
            f = next(mdir.glob("*.parquet"), None)
            if f is None:
                continue
            try:
                bb = pq.read_table(f, columns=["bbox_minx", "bbox_miny", "bbox_maxx", "bbox_maxy"]).to_pandas()
            except Exception:
                continue
            if bb.empty:
                continue
            if bb["bbox_maxx"].max() < mtr["lng_min"] or bb["bbox_minx"].min() > mtr["lng_max"] or bb["bbox_maxy"].max() < mtr["lat_min"] or bb["bbox_miny"].min() > mtr["lat_max"]:
                continue
            df = pd.read_parquet(f, columns=["cod_setor", "geometry_wkb", "pop_total_setor_2022", "domicilios_particulares_ocupados_setor_2022",
                                             "renda_per_capita_setor_2022_calibrada", "renda_per_capita_setor_2022", "flag_geometria_valida", "bbox_minx", "bbox_miny", "bbox_maxx", "bbox_maxy"])
            df = df[(df["bbox_maxx"] >= mtr["lng_min"]) & (df["bbox_minx"] <= mtr["lng_max"]) & (df["bbox_maxy"] >= mtr["lat_min"]) & (df["bbox_miny"] <= mtr["lat_max"])]
            frames.append(df)
    if not frames:
        return None
    s = pd.concat(frames, ignore_index=True)
    s = s[s["flag_geometria_valida"].fillna(True)]
    g = gpd.GeoDataFrame(s.drop(columns=["geometry_wkb"]), geometry=[wkb.loads(b) for b in s["geometry_wkb"]], crs=4674).to_crs(5880)
    g["renda"] = g["renda_per_capita_setor_2022_calibrada"].fillna(g["renda_per_capita_setor_2022"])
    g["area"] = g.geometry.area
    g["rp"] = g.geometry.representative_point()
    return g.reset_index(drop=True)


class Contexto:
    def __init__(self, g, acad, ult):
        self.g = g
        self.tree = STRtree(g.geometry.values)
        self.tree_rp = STRtree(g["rp"].values)
        self.pop = g["pop_total_setor_2022"].clip(lower=0).to_numpy(float)
        self.dom = g["domicilios_particulares_ocupados_setor_2022"].clip(lower=0).to_numpy(float)
        self.renda = g["renda"].to_numpy(float)
        self.area = g["area"].to_numpy(float)
        ga = gpd.GeoSeries([Point(x, y) for x, y in zip(acad["lng"], acad["lat"])], crs=4326).to_crs(5880)
        self.ax = np.array([p.x for p in ga.values]); self.ay = np.array([p.y for p in ga.values])
        self.tree_acad = STRtree(ga.values) if len(ga) else None
        self.tipos = acad["tipo"].to_numpy()
        gu = gpd.GeoSeries([Point(x, y) for x, y in zip(ult["lng"], ult["lat"])], crs=4326).to_crs(5880)
        self.tree_ultra = STRtree(gu.values) if len(gu) else None


def atributos_poligono(poly, ctx, alvo_xy):
    if not poly.is_valid:
        poly = make_valid(poly)
        partes = [p for p in getattr(poly, "geoms", [poly]) if p.geom_type == "Polygon"]
        poly = max(partes, key=lambda p: p.area) if partes else poly.buffer(0)
    out = {"pop": 0.0, "domicilios": 0.0, "renda_pc": np.nan, "n_setores": 0, "metodo_setor": "fracao_area"}
    if poly.area > AREA_RAPIDA_M2:
        idx = ctx.tree_rp.query(poly, predicate="contains")
        frac = np.ones(len(idx))
        out["metodo_setor"] = "ponto_representativo"
    else:
        idx = ctx.tree.query(poly, predicate="intersects")
        if len(idx):
            cand = ctx.g.geometry.values[idx]
            try:
                inter = np.array([c.intersection(poly).area for c in cand])
            except Exception:  # noqa: BLE001
                inter = np.array([c.buffer(0).intersection(poly.buffer(0)).area for c in cand])
            frac = np.clip(inter / np.where(ctx.area[idx] > 0, ctx.area[idx], np.nan), 0, 1)
            frac = np.nan_to_num(frac)
        else:
            frac = np.array([])
    if len(idx):
        pop = ctx.pop[idx] * frac; dom = ctx.dom[idx] * frac; renda = ctx.renda[idx]
        w = np.where(np.isnan(renda), 0, pop)
        out.update({"pop": float(pop.sum()), "domicilios": float(dom.sum()),
                    "renda_pc": float((np.nan_to_num(renda) * w).sum() / w.sum()) if w.sum() > 0 else np.nan, "n_setores": int((frac > 0).sum())})
    ia = ctx.tree_acad.query(poly, predicate="contains") if ctx.tree_acad is not None else np.array([], int)
    if len(ia):
        auto = np.hypot(ctx.ax[ia] - alvo_xy[0], ctx.ay[ia] - alvo_xy[1]) < AUTO_M
        out["n_auto_excluida"] = int(auto.sum())
        ia = ia[~auto]
    else:
        out["n_auto_excluida"] = 0
    for t in PESO:
        out[f"n_{t}"] = int((ctx.tipos[ia] == t).sum()) if len(ia) else 0
    out["n_academias"] = int(len(ia)) - out["n_cadeia_agregador_com_pin"]
    out["oferta_ponderada"] = float(sum(PESO[t] * out[f"n_{t}"] for t in PESO))
    iu = ctx.tree_ultra.query(poly, predicate="contains") if ctx.tree_ultra is not None else np.array([], int)
    out["n_ultra"] = int(len(iu))
    return out


def rodar_metro(mid, metros, parte=None):
    mtr = next(m for m in metros if m["id"] == mid)
    f = ISO / f"isocronas{SUF}" / f"metro_{mid}.parquet"
    if not f.exists():
        print("metro", mid, "sem isocronas"); return
    t0 = time.time()
    iso = pd.read_parquet(f)
    pontos = iso["ponto_id"].drop_duplicates().reset_index(drop=True)
    if parte is not None:
        k, n = parte
        pontos = pontos[pontos.index % n == k]
        iso = iso[iso["ponto_id"].isin(set(pontos))]
    g = setores_no_bbox(mtr)
    if g is None:
        print("metro", mid, "sem setores"); return
    acad = pd.read_parquet(ISO / "academias_pontos.parquet")
    acad = acad[(acad["lat"].between(mtr["lat_min"], mtr["lat_max"])) & (acad["lng"].between(mtr["lng_min"], mtr["lng_max"]))].reset_index(drop=True)
    ult = pd.read_parquet(ISO / "ultra_pontos.parquet").dropna(subset=["lat"])
    ult = ult[(ult["lat"].between(mtr["lat_min"], mtr["lat_max"])) & (ult["lng"].between(mtr["lng_min"], mtr["lng_max"]))]
    ctx = Contexto(g, acad, ult)
    print(f"metro {mid}{'' if parte is None else f' parte {parte[0]}/{parte[1]}'}: {len(g):,} setores | {len(acad):,} academias | {len(ult)} ultra | {len(iso):,} isocronas ({time.time()-t0:.0f}s)", flush=True)
    pts = iso.drop_duplicates("ponto_id")[["ponto_id", "tipo", "subtipo", "lat", "lng"]].reset_index(drop=True)
    gp = gpd.GeoSeries([Point(x, y) for x, y in zip(pts["lng"], pts["lat"])], crs=4326).to_crs(5880)
    xy = {pid: (p.x, p.y) for pid, p in zip(pts["ponto_id"], gp.values)}
    linhas = []
    polys5880 = gpd.GeoSeries([wkb.loads(b) if b is not None else None for b in iso["poligono_wkb"]], crs=4326).to_crs(5880)
    area_iso = {}
    extra = [c for c in ("r_max_m", "dist_borda_m", "truncada") if c in iso.columns]
    for i, (r, p) in enumerate(zip(iso.itertuples(index=False), polys5880.values)):
        cen = f"{r.modo}_{int(r.limite_s)//60}min"
        base = {"ponto_id": r.ponto_id, "tipo": r.tipo, "subtipo": r.subtipo, "lat": r.lat, "lng": r.lng, "metro": mid, "cenario": cen,
                "snap_dist_m": r.snap_dist_m, "n_nos": r.n_nos, "km_rua": r.km_rua, "area_km2": r.area_km2, **{c: getattr(r, c) for c in extra}}
        if p is None or p.is_empty:
            linhas.append({**base, "pop": np.nan, "domicilios": np.nan, "renda_pc": np.nan, "n_setores": 0, "n_academias": np.nan, "oferta_ponderada": np.nan, "n_ultra": np.nan})
            continue
        if cen in ("carro_5min", "pe_15min"):
            area_iso[(r.ponto_id, cen)] = p.area
        linhas.append({**base, **atributos_poligono(p, ctx, xy[r.ponto_id])})
        if i % 5000 == 0 and i:
            print(f"   {i:,}/{len(iso):,} ({time.time()-t0:.0f}s)", flush=True)
    for r, p in zip(pts.itertuples(index=False), gp.values):
        comum = {"ponto_id": r.ponto_id, "tipo": r.tipo, "subtipo": r.subtipo, "lat": r.lat, "lng": r.lng, "metro": mid, "snap_dist_m": np.nan, "n_nos": np.nan, "km_rua": np.nan}
        linhas.append({**comum, "cenario": "circulo_1km", "area_km2": math.pi, **atributos_poligono(p.buffer(1000.0), ctx, (p.x, p.y))})
        for cen in ("carro_5min", "pe_15min"):
            a = area_iso.get((r.ponto_id, cen))
            if a:
                rad = math.sqrt(a / math.pi)
                linhas.append({**comum, "cenario": f"circeq_{cen}", "area_km2": a / 1e6, "raio_eq_m": rad, **atributos_poligono(p.buffer(rad), ctx, (p.x, p.y))})
        try:
            cell = h3.latlng_to_cell(r.lat, r.lng, 7)
            b = h3.cell_to_boundary(cell)
            hexp = gpd.GeoSeries([Polygon([(lng, lat) for lat, lng in b])], crs=4326).to_crs(5880).iloc[0]
            linhas.append({**comum, "cenario": "hex_r7", "area_km2": hexp.area / 1e6, **atributos_poligono(hexp, ctx, (p.x, p.y))})
        except Exception as exc:  # noqa: BLE001
            print("hex falhou", r.ponto_id, exc)
    res = pd.DataFrame(linhas)
    nome = f"metro_{mid}.parquet" if parte is None else f"metro_{mid}_p{parte[0]}.parquet"
    res.to_parquet(OUT / nome, index=False)
    print(f"metro {mid}: {len(res):,} linhas de atributos em {time.time()-t0:.0f}s", flush=True)


def main(argv):
    metros = json.load(open(ISO / "metros.json", encoding="utf-8"))
    parte = None; ids = []
    it = iter(argv)
    for a in it:
        if a == "--parte":
            k, n = next(it).split("/"); parte = (int(k), int(n))
        else:
            ids.append(int(a))
    ids = ids or [m["id"] for m in metros if (ISO / f"isocronas{SUF}" / f"metro_{m['id']}.parquet").exists()]
    for mid in ids:
        rodar_metro(mid, metros, parte)


if __name__ == "__main__":
    main(sys.argv[1:])
