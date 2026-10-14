# -*- coding: utf-8 -*-
"""Etapa 2 — extrai a malha viaria do OSM (PBF regional Geofabrik) para cada metro-alvo.

Uso: venv-iso\\python 02_grafo.py <regiao> [<regiao> ...]   (centro-oeste, sudeste, sul, nordeste, norte)

Para cada regiao, UMA passada com pyosmium (locations em memoria, flex_mem): so' ways com tag highway
chegam ao Python; a way entra no metro cujo bbox contem seu PRIMEIRO no' (grade de 0,1 graus para o
teste ser O(1)). Saida por metro em SCRATCH/iso/grafo/metro_<id>/:
  nodes.parquet : node_id, lat, lng
  edges.parquet : u, v, length_m, hw, oneway (0 = duplo, 1 = so' u->v), maxspeed_kmh (NaN se ausente), way_id
Cada segmento consecutivo (n_i, n_{i+1}) da way vira UMA aresta (grafo NAO simplificado: o snap do ponto
ao no' mais proximo fica a poucos metros).
"""
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import osmium
import pandas as pd

SCRATCH = Path(r"C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\9259d0a1-7dda-49bd-a390-c88f3d4ac1a6\scratchpad")
PBF_DIR = Path(r"C:\dev\motor-de-expansao\data\osm_cache\pbf")
OUT = SCRATCH / "iso" / "grafo"
OUT.mkdir(parents=True, exist_ok=True)

HW_OK = {
    "motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link",
    "tertiary", "tertiary_link", "unclassified", "residential", "living_street", "service", "road",
    "pedestrian", "footway", "path", "steps", "cycleway", "track",
}
ONEWAY_YES = {"yes", "true", "1"}
ONEWAY_REV = {"-1", "reverse"}


def parse_maxspeed(v):
    if not v:
        return float("nan")
    m = "".join(ch for ch in v.split(";")[0] if ch.isdigit() or ch == ".")
    try:
        x = float(m)
    except ValueError:
        return float("nan")
    if "mph" in v:
        x *= 1.609
    return x if 5 <= x <= 120 else float("nan")


class Extrator(osmium.SimpleHandler):
    def __init__(self, metros):
        super().__init__()
        self.metros = metros
        self.grade = {}
        for mtr in metros:
            for la in range(int(math.floor(mtr["lat_min"] * 10)), int(math.floor(mtr["lat_max"] * 10)) + 1):
                for lo in range(int(math.floor(mtr["lng_min"] * 10)), int(math.floor(mtr["lng_max"] * 10)) + 1):
                    self.grade.setdefault((la, lo), []).append(mtr)
        self.buf = {mtr["id"]: {"nodes": {}, "edges": []} for mtr in metros}
        self.n_ways = 0
        self.n_in = 0

    def _metro_de(self, lat, lon):
        cands = self.grade.get((int(math.floor(lat * 10)), int(math.floor(lon * 10))))
        if not cands:
            return None
        for mtr in cands:
            if mtr["lat_min"] <= lat <= mtr["lat_max"] and mtr["lng_min"] <= lon <= mtr["lng_max"]:
                return mtr["id"]
        return None

    def way(self, w):
        tags = w.tags
        hw = tags.get("highway")
        if hw not in HW_OK:
            return
        self.n_ways += 1
        if tags.get("area") == "yes":
            return
        if tags.get("access") in ("private", "no") and hw != "service":
            return
        if hw == "service" and tags.get("service") in ("parking_aisle", "driveway", "drive-through", "emergency_access"):
            return
        nodes = w.nodes
        if len(nodes) < 2:
            return
        try:
            loc0 = nodes[0].location
            if not loc0.valid():
                return
            mid = self._metro_de(loc0.lat, loc0.lon)
        except osmium.InvalidLocationError:
            return
        if mid is None:
            return
        self.n_in += 1
        ow = tags.get("oneway", "")
        if ow in ONEWAY_YES or tags.get("junction") in ("roundabout", "circular") or (hw in ("motorway", "motorway_link") and ow != "no"):
            oneway = 1
        elif ow in ONEWAY_REV:
            oneway = -1
        else:
            oneway = 0
        ms = parse_maxspeed(tags.get("maxspeed", ""))
        b = self.buf[mid]
        prev = None
        for n in nodes:
            try:
                loc = n.location
                if not loc.valid():
                    prev = None
                    continue
            except osmium.InvalidLocationError:
                prev = None
                continue
            nid = n.ref
            b["nodes"][nid] = (loc.lat, loc.lon)
            if prev is not None:
                plat, plon = b["nodes"][prev]
                dx = (loc.lon - plon) * 111320.0 * math.cos(math.radians((loc.lat + plat) / 2))
                dy = (loc.lat - plat) * 110540.0
                L = math.hypot(dx, dy)
                if oneway == -1:
                    b["edges"].append((nid, prev, L, hw, 1, ms, w.id))
                else:
                    b["edges"].append((prev, nid, L, hw, oneway, ms, w.id))
            prev = nid


def main(regioes):
    import os
    metros = json.load(open(os.environ.get("METROS_FILE", str(SCRATCH / "iso" / "metros.json")), encoding="utf-8"))
    if os.environ.get("METROS_IDS"):
        ids = {int(x) for x in os.environ["METROS_IDS"].split(",")}
        metros = [m for m in metros if m["id"] in ids]
    for reg in regioes:
        pbf = PBF_DIR / f"{reg}-latest.osm.pbf"
        if not pbf.exists():
            print("PBF ausente:", pbf); continue
        t0 = time.time()
        h = Extrator(metros)
        h.apply_file(str(pbf), locations=True, idx="flex_mem")
        print(f"[{reg}] ways highway={h.n_ways:,} | nos metros={h.n_in:,} | {time.time()-t0:.0f}s", flush=True)
        for mid, b in h.buf.items():
            if not b["edges"]:
                continue
            d = OUT / f"metro_{mid}"
            d.mkdir(exist_ok=True)
            nodes = pd.DataFrame([(k, v[0], v[1]) for k, v in b["nodes"].items()], columns=["node_id", "lat", "lng"])
            edges = pd.DataFrame(b["edges"], columns=["u", "v", "length_m", "hw", "oneway", "maxspeed_kmh", "way_id"])
            # uma regiao pode complementar outra (metro na fronteira): acumula e dedup por (way_id,u,v)
            fn, fe = d / "nodes.parquet", d / "edges.parquet"
            if fn.exists():
                nodes = pd.concat([pd.read_parquet(fn), nodes]).drop_duplicates("node_id")
                edges = pd.concat([pd.read_parquet(fe), edges]).drop_duplicates(["way_id", "u", "v"])
            nodes.to_parquet(fn, index=False); edges.to_parquet(fe, index=False)
            print(f"   metro {mid}: {len(nodes):,} nos, {len(edges):,} arestas", flush=True)
        del h


if __name__ == "__main__":
    main(sys.argv[1:] or ["centro-oeste"])
