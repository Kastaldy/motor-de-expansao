# -*- coding: utf-8 -*-
"""Etapa 3 — isocronas (carro 5/10/15 min; a pe' 10/15 min) para todos os pontos-alvo de cada metro.

Uso: venv-iso\\python 03_isocronas.py [metro_id ...] [--procs N] [--so-ultra]

Pontos-alvo por metro (dentro do bbox):
  ultra        : unidades Ultra da Growth (ultra_pontos.parquet)
  academia     : concorrentes/independentes (academias_pontos.parquet)
  controle     : pontos aleatorios SOBRE a malha viaria (uniforme no bbox, mantidos se ha' no' a <= 120 m) — 2x academias, teto 4.000
  hex_carteira : centroides dos hexagonos de carteira_expansao_acionavel.parquet (funil)
Grafo de carro: classes de veiculo, DIRECIONADO (oneway), velocidade = maxspeed (teto 80) ou default por classe.
Grafo a pe': todas as classes menos motorway/trunk, nao direcionado, 4,5 km/h (escadas 2 km/h).
Snap: no' mais proximo (KD-tree) a <= 250 m (carro) / 150 m (pe'); senao 'sem_rede'.
Poligono: concave hull (shapely, ratio 0,3) dos nos alcancados (amostra de ate' 2.500 nos), WKB em WGS84.
Saida: SCRATCH/iso/isocronas/metro_<id>.parquet (uma linha por ponto x cenario).
"""
import json
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree
from shapely import concave_hull
from shapely.geometry import MultiPoint, Point

SCRATCH = Path(r"C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\9259d0a1-7dda-49bd-a390-c88f3d4ac1a6\scratchpad")
REPO = Path(r"C:\dev\motor-de-expansao")
ISO = SCRATCH / "iso"
SUF = os.environ.get("ISO_VERSAO", "")  # "" = v1; "_v2" = pipeline corrigido
OUT = ISO / f"isocronas{SUF}"
OUT.mkdir(exist_ok=True)

VEL = {"motorway": 80, "motorway_link": 50, "trunk": 60, "trunk_link": 40, "primary": 40, "primary_link": 30, "secondary": 35,
       "secondary_link": 30, "tertiary": 30, "tertiary_link": 25, "unclassified": 25, "residential": 20, "living_street": 10,
       "service": 15, "road": 25}
HW_CARRO = set(VEL)
HW_PE_EXCL = {"motorway", "motorway_link", "trunk", "trunk_link"}
CENARIOS = {"carro": [300, 600, 900], "pe": [600, 900]}
SEED = 42
RECUO_KM = 6.0 if os.environ.get("ISO_VERSAO", "") else 0.0
MIN_COMP = 1000  # v2: componente conexo com >= 1.000 nos (antes: so' o maior; partia Niteroi, Guaruja, Aguas Lindas a pe')
SNAP_HEX_M = 700.0  # v2: centroide de hexagono res-7 (aresta ~1,4 km) pode cair longe de rua


def proj(lat, lng, lat_c, lng_c):
    return (np.asarray(lng) - lng_c) * 111320.0 * math.cos(math.radians(lat_c)), (np.asarray(lat) - lat_c) * 110540.0


def montar(mid, modo):
    d = ISO / "grafo" / f"metro_{mid}"
    nodes = pd.read_parquet(d / "nodes.parquet")
    edges = pd.read_parquet(d / "edges.parquet")
    if modo == "carro":
        e = edges[edges["hw"].isin(HW_CARRO)].copy()
        vel = e["hw"].map(VEL).astype(float)
        ms = e["maxspeed_kmh"].clip(upper=80)
        vel = np.where(ms.notna(), np.minimum(ms.fillna(0), np.maximum(vel * 1.5, 30)), vel)  # maxspeed vale, mas nao infla via local
        t = e["length_m"].to_numpy() / (vel / 3.6)
        back = e["oneway"].to_numpy() == 0
    else:
        e = edges[~edges["hw"].isin(HW_PE_EXCL)].copy()
        vel = np.where(e["hw"] == "steps", 2.0, 4.5)
        t = e["length_m"].to_numpy() / (vel / 3.6)
        back = np.ones(len(e), bool)
    used = pd.unique(np.concatenate([e["u"].to_numpy(), e["v"].to_numpy()]))
    nodes = nodes[nodes["node_id"].isin(used)].reset_index(drop=True)
    idx = pd.Series(np.arange(len(nodes)), index=nodes["node_id"].to_numpy())
    u = idx.reindex(e["u"].to_numpy()).to_numpy(); v = idx.reindex(e["v"].to_numpy()).to_numpy()
    rows = np.concatenate([u, v[back]]); cols = np.concatenate([v, u[back]]); vals = np.concatenate([t, t[back]])
    n = len(nodes)
    csr = coo_matrix((vals, (rows, cols)), shape=(n, n)).tocsr()
    csr.sum_duplicates()
    # comprimento por aresta (para km de rua alcancada): usa a menor aresta por par
    L = coo_matrix((np.concatenate([e["length_m"].to_numpy(), e["length_m"].to_numpy()[back]]), (rows, cols)), shape=(n, n)).tocsr()
    return nodes, csr, L


def alvos_do_metro(mtr, so_ultra=False):
    b = mtr
    def dentro(df, recuo_km=0.0):
        # v2: alvos que nao sao Ultra ficam a >= RECUO_KM da borda da caixa, senao a isocrona de
        # carro e' truncada pelo fim do grafo (achado D2 da lente de qualidade)
        dlat = recuo_km / 110.54; dlng = recuo_km / (111.32 * math.cos(math.radians(b["lat_c"])))
        return df[(df["lat"] >= b["lat_min"] + dlat) & (df["lat"] <= b["lat_max"] - dlat) & (df["lng"] >= b["lng_min"] + dlng) & (df["lng"] <= b["lng_max"] - dlng)]
    u = pd.read_parquet(ISO / "ultra_pontos.parquet").dropna(subset=["lat"])
    u = dentro(u)[["unidade_id", "lat", "lng", "confianca"]].rename(columns={"unidade_id": "ponto_id"}); u["tipo"] = "ultra"
    if so_ultra:
        return u
    a = pd.read_parquet(ISO / "academias_pontos.parquet")
    a = dentro(a, RECUO_KM)[["id", "lat", "lng", "tipo"]].rename(columns={"id": "ponto_id", "tipo": "subtipo"}); a["tipo"] = "academia"
    import h3
    cart = pd.read_parquet(REPO / "data/outputs/carteira_expansao_acionavel.parquet", columns=["hex_id", "uf", "nome_municipio", "faixa_oportunidade", "n_concorrentes_influencia_1km"])
    ll = np.array([h3.cell_to_latlng(h) if hasattr(h3, "cell_to_latlng") else h3.h3_to_geo(h) for h in cart["hex_id"]])
    cart["lat"], cart["lng"] = ll[:, 0], ll[:, 1]
    hx = dentro(cart, RECUO_KM)[["hex_id", "lat", "lng"]].rename(columns={"hex_id": "ponto_id"}); hx["tipo"] = "hex_carteira"
    # controles = NOS da malha de carro sorteados uniformemente ("esquina aleatoria"): a densidade de
    # controles acompanha a densidade de ruas, entao a comparacao academia x controle e' "ponto de
    # academia x ponto urbano tipico", e nao "cidade x mato" (uniforme no bbox cai em area rural)
    rng = np.random.default_rng(SEED + int(mtr["id"]))
    n_ctrl = int(min(4000, max(300, 2 * len(a))))
    d = ISO / "grafo" / f"metro_{mtr['id']}"
    ed = pd.read_parquet(d / "edges.parquet", columns=["u", "v", "hw"])
    ed = ed[ed["hw"].isin(HW_CARRO) & ~ed["hw"].isin({"service"})]
    nid = pd.unique(np.concatenate([ed["u"].to_numpy(), ed["v"].to_numpy()]))
    nd = pd.read_parquet(d / "nodes.parquet").set_index("node_id").loc[nid]
    nd = dentro(nd.reset_index(), RECUO_KM)
    sel = rng.choice(len(nd), size=min(n_ctrl, len(nd)), replace=False)
    ctrl = nd.iloc[sel][["lat", "lng"]].reset_index(drop=True)
    ctrl["ponto_id"] = [f"ctrl_{mtr['id']}_{i}" for i in range(len(ctrl))]; ctrl["tipo"] = "controle"
    return pd.concat([u, a, hx, ctrl], ignore_index=True)


def hull_wkb(pts_xy, rng):
    if len(pts_xy) < 4:
        return None, 0.0
    if len(pts_xy) > 2500:
        pts_xy = pts_xy[rng.choice(len(pts_xy), 2500, replace=False)]
    try:
        poly = concave_hull(MultiPoint(pts_xy), ratio=0.3)
        if poly.is_empty or poly.geom_type != "Polygon":
            poly = MultiPoint(pts_xy).convex_hull
    except Exception:  # noqa: BLE001
        poly = MultiPoint(pts_xy).convex_hull
    if not poly.is_valid:
        from shapely import make_valid
        poly = make_valid(poly)
        partes = [p for p in getattr(poly, "geoms", [poly]) if p.geom_type == "Polygon"]
        poly = max(partes, key=lambda p: p.area) if partes else None
        if poly is None:
            return None, 0.0
    if poly.geom_type != "Polygon":
        return None, 0.0
    return poly, poly.area / 1e6


def processar_lote(args):
    mid, modo, lote_idx, alvos_lote, lat_c, lng_c, bb = args
    nodes, csr, L = montar(mid, modo)
    x, y = proj(nodes["lat"].to_numpy(), nodes["lng"].to_numpy(), lat_c, lng_c)
    # snap so' em no' com SAIDA (fim de mao unica nao serve como origem) e no maior componente
    # conexo (fragmento isolado de via de servico devolveria isocrona de 1 no')
    from scipy.sparse.csgraph import connected_components
    deg_out = np.diff(csr.indptr)
    _, lab = connected_components(csr, directed=True, connection="weak")
    if SUF:
        tam = np.bincount(lab)
        elegivel = np.nonzero((deg_out > 0) & (tam[lab] >= MIN_COMP))[0]
    else:
        maior = np.bincount(lab).argmax()
        elegivel = np.nonzero((deg_out > 0) & (lab == maior))[0]
    tree = cKDTree(np.c_[x[elegivel], y[elegivel]])
    px, py = proj(alvos_lote["lat"].to_numpy(), alvos_lote["lng"].to_numpy(), lat_c, lng_c)
    dist, src_el = tree.query(np.c_[px, py])
    src = elegivel[src_el]
    lim_base = 250.0 if modo == "carro" else 150.0
    lim_vec = np.where((alvos_lote["tipo"] == "hex_carteira").to_numpy() & bool(SUF), SNAP_HEX_M, lim_base)
    # distancia do ponto a borda do grafo (caixa do metro), para marcar truncamento
    bx0, by0 = proj(bb["lat_min"], bb["lng_min"], lat_c, lng_c); bx1, by1 = proj(bb["lat_max"], bb["lng_max"], lat_c, lng_c)
    d_borda = np.minimum.reduce([px - bx0, bx1 - px, py - by0, by1 - py])
    rng = np.random.default_rng(SEED + lote_idx)
    from shapely.ops import transform as shp_transform
    def to_wgs(poly):
        return shp_transform(lambda X, Y: (X / (111320.0 * math.cos(math.radians(lat_c))) + lng_c, Y / 110540.0 + lat_c), poly)
    saida = []
    limites = CENARIOS[modo]
    Lcoo = L.tocoo()
    ok = np.nonzero(dist <= lim_vec)[0]
    for k0 in range(0, len(ok), 25):
        ks = ok[k0:k0 + 25]
        D = dijkstra(csr, directed=True, indices=src[ks], limit=max(limites))
        for j, k in enumerate(ks):
            d = D[j]
            for lim in limites:
                alc = np.nonzero(d <= lim)[0]
                # km de rua: arestas com os dois extremos alcancados
                m = np.zeros(len(d), bool); m[alc] = True
                km = float(Lcoo.data[m[Lcoo.row] & m[Lcoo.col]].sum() / 2000.0)
                poly, area = hull_wkb(np.c_[x[alc], y[alc]], rng)
                r_max = float(np.hypot(x[alc] - px[k], y[alc] - py[k]).max()) if len(alc) else 0.0
                saida.append({"ponto_id": alvos_lote["ponto_id"].iloc[k], "tipo": alvos_lote["tipo"].iloc[k], "subtipo": alvos_lote.get("subtipo", pd.Series([None] * len(alvos_lote))).iloc[k],
                              "lat": alvos_lote["lat"].iloc[k], "lng": alvos_lote["lng"].iloc[k], "metro": mid, "modo": modo, "limite_s": lim,
                              "snap_dist_m": float(dist[k]), "n_nos": int(len(alc)), "km_rua": km, "area_km2": area,
                              "r_max_m": r_max, "dist_borda_m": float(d_borda[k]), "truncada": bool(r_max >= d_borda[k] - 500.0),
                              "poligono_wkb": to_wgs(poly).wkb if poly is not None else None})
    for k in np.nonzero(dist > lim_vec)[0]:
        for lim in limites:
            saida.append({"ponto_id": alvos_lote["ponto_id"].iloc[k], "tipo": alvos_lote["tipo"].iloc[k], "subtipo": alvos_lote.get("subtipo", pd.Series([None] * len(alvos_lote))).iloc[k],
                          "lat": alvos_lote["lat"].iloc[k], "lng": alvos_lote["lng"].iloc[k], "metro": mid, "modo": modo, "limite_s": lim,
                          "snap_dist_m": float(dist[k]), "n_nos": 0, "km_rua": 0.0, "area_km2": 0.0,
                          "r_max_m": 0.0, "dist_borda_m": float(d_borda[k]), "truncada": False, "poligono_wkb": None})
    return pd.DataFrame(saida)


def rodar_metro(mid, metros, procs, so_ultra, parte=None):
    mtr = next(m for m in metros if m["id"] == mid)
    d = ISO / "grafo" / f"metro_{mid}"
    if not (d / "edges.parquet").exists():
        print(f"metro {mid}: sem grafo"); return
    t0 = time.time()
    alvos = alvos_do_metro(mtr, so_ultra)
    # controles: mantem so' os que caem sobre a malha (no' a <= 120 m), ate' o teto
    nodes = pd.read_parquet(d / "nodes.parquet")
    x, y = proj(nodes["lat"].to_numpy(), nodes["lng"].to_numpy(), mtr["lat_c"], mtr["lng_c"])
    tree = cKDTree(np.c_[x, y])
    px, py = proj(alvos["lat"].to_numpy(), alvos["lng"].to_numpy(), mtr["lat_c"], mtr["lng_c"])
    dist, _ = tree.query(np.c_[px, py])
    ctrl = (alvos["tipo"] == "controle").to_numpy()
    n_ctrl_alvo = int(min(4000, max(300, 2 * int((alvos["tipo"] == "academia").sum()))))
    keep = ~ctrl | (dist <= 120.0)
    alvos = alvos[keep].reset_index(drop=True)
    ctrl_idx = alvos.index[alvos["tipo"] == "controle"]
    if len(ctrl_idx) > n_ctrl_alvo:
        alvos = alvos.drop(ctrl_idx[n_ctrl_alvo:]).reset_index(drop=True)
    if parte is not None:
        alvos = alvos[alvos.index % parte[1] == parte[0]].reset_index(drop=True)
    del nodes, tree, x, y
    nodes = pd.read_parquet(d / "nodes.parquet", columns=["node_id"])
    print(f"metro {mid}: {len(nodes):,} nos | alvos {alvos['tipo'].value_counts().to_dict()}", flush=True)
    frames = []
    for modo in ("carro", "pe"):
        n_lotes = max(1, min(procs * 3, math.ceil(len(alvos) / 150)))
        lotes = np.array_split(np.arange(len(alvos)), n_lotes)
        tarefas = [(mid, modo, i, alvos.iloc[l].reset_index(drop=True), mtr["lat_c"], mtr["lng_c"], mtr) for i, l in enumerate(lotes) if len(l)]
        if procs > 1 and len(tarefas) > 1:
            with ProcessPoolExecutor(max_workers=procs) as ex:
                for r in ex.map(processar_lote, tarefas):
                    frames.append(r)
        else:
            for tr in tarefas:
                frames.append(processar_lote(tr))
        print(f"   {modo}: ok ({time.time()-t0:.0f}s)", flush=True)
    res = pd.concat(frames, ignore_index=True)
    res.to_parquet(OUT / (f"metro_{mid}.parquet" if parte is None else f"metro_{mid}_p{parte[0]}.parquet"), index=False)
    print(f"metro {mid}: {len(res):,} linhas em {time.time()-t0:.0f}s | sem_rede carro: {(res[(res.modo=='carro')&(res.limite_s==300)]['n_nos']==0).sum()}", flush=True)


def main(argv):
    procs = 6; so_ultra = False; ids = []; parte = None
    it = iter(argv)
    for a in it:
        if a == "--procs": procs = int(next(it))
        elif a == "--so-ultra": so_ultra = True
        elif a == "--parte": k, n = next(it).split("/"); parte = (int(k), int(n))
        else: ids.append(int(a))
    metros = json.load(open(ISO / "metros.json", encoding="utf-8"))
    if not ids:
        ids = [m["id"] for m in metros if (ISO / "grafo" / f"metro_{m['id']}" / "edges.parquet").exists()]
    for mid in ids:
        rodar_metro(mid, metros, procs, so_ultra, parte)


if __name__ == "__main__":
    main(sys.argv[1:])
