# -*- coding: utf-8 -*-
"""BLK-UNI-10, item 4 (protocolo_bateria.md §7 + §9.9 + §18 + §19): PREPARO das vias ao redor das unidades. Sem desfecho.
Le' o grafo viario do pipeline de isocronas (scratchpad da sessao, 136 caixas; 02_grafo.py: cada way entra INTEIRA na UMA
caixa que contem o seu PRIMEIRO no'), junta as caixas e grava, de forma permanente e congelavel:
  insumos_item4/vias_entorno.parquet : segmentos de via de carro a <= RAIO de alguma unidade (EPSG:5880), com hw, way_id, u, v
  insumos_item4/cobertura.parquet    : por unidade (lab = sigla; Ultra = unidade_id): pino (lat/lng) e margem ate a borda da
                                       melhor caixa, medida em GRAUS com escala local (a mesma regra de pertenca do 02_grafo)
  insumos_item4/meta.json            : raio, data e distribuicao do comprimento das ways arteriais (sem desfecho)
  insumos_item4/grafo_sha.txt        : SHA-256 dos arquivos de grafo lidos
Pontos: Smart Fit = amostra_lab do item 2 (crosswalk do termometro); Ultra = pinos corrigidos (poligonos_ultra).
Uso: item4_prep_vias.py  (.venv, PYTHONPATH=src). Um script por vez."""
import hashlib
import importlib.util
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import shapely
from pyproj import Transformer

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
ISO = UNI.parent / "isocronas"
GRAFO = Path(r"C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\9259d0a1-7dda-49bd-a390-c88f3d4ac1a6\scratchpad\iso\grafo")
OUT = AQUI / "insumos_item4"
CARRO = {"motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link",
         "tertiary", "tertiary_link", "unclassified", "residential", "living_street", "service", "road"}
ART = {"primary", "secondary", "trunk"}
RAIO = 300.0
JANELA = 6000.0
CAIXAS = {m["id"]: m for m in json.load(open(ISO / "metros.json", encoding="utf-8")) + json.load(open(ISO / "multirede" / "metros_novos.json", encoding="utf-8"))}
TF = Transformer.from_crs(4326, 5880, always_xy=True)


def mod(nome, p):
    s = importlib.util.spec_from_file_location(nome, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def margem_graus(lat, lng, la0, la1, lo0, lo1):
    """Distancia (m) ate a borda de uma caixa lat/lng, com a escala local (negativa = fora). E' a regra do 02_grafo."""
    c = np.cos(np.radians(lat))
    return np.minimum.reduce([(lat - la0) * 110540.0, (la1 - lat) * 110540.0, (lng - lo0) * 111320.0 * c, (lo1 - lng) * 111320.0 * c])


def main():
    OUT.mkdir(exist_ok=True)
    i5 = mod("i5", AQUI / "item5_faculdades.py")  # so' para reaproveitar it2 / tm / ex (nao roda o item 5)
    it2, tm, ex, op = i5.it2, i5.tm, i5.ex, i5.op
    S, _ = it2.amostra_lab(it2.ler_comodidades())
    f, d = ex.carregar(); tr, te, *_ = tm.bases(f, d)
    pv = pd.read_csv(op.PV, sep=";", encoding="utf-8-sig", index_col=0)
    PU = it2.poligonos_ultra(list(tr.index) + list(te.index) + list(pv.index))
    P = pd.concat([pd.DataFrame({"chave": S.sigla, "origem": "lab", "lat": S.lat, "lng": S.lng}),
                   pd.DataFrame({"chave": PU.index, "origem": "ultra", "lat": PU.lat.to_numpy(), "lng": PU.lng.to_numpy()})], ignore_index=True)
    P["x"], P["y"] = TF.transform(P.lng.to_numpy(), P.lat.to_numpy())
    tree = shapely.STRtree(shapely.buffer(shapely.points(P.x.to_numpy(), P.y.to_numpy()), RAIO))
    ux0, ux1, uy0, uy1 = P.x.min() - JANELA, P.x.max() + JANELA, P.y.min() - JANELA, P.y.max() + JANELA
    seg, cob, shas, wl = [], {}, [], []
    for dd in sorted(GRAFO.iterdir()):
        nf, ef = dd / "nodes.parquet", dd / "edges.parquet"
        shas.append(f"{hashlib.sha256(nf.read_bytes()).hexdigest()} *{dd.name}/nodes.parquet")
        shas.append(f"{hashlib.sha256(ef.read_bytes()).hexdigest()} *{dd.name}/edges.parquet")
        cid = int(dd.name.split("_")[1])
        n = pq.read_table(nf).to_pandas().set_index("node_id")
        cx = CAIXAS.get(cid)
        if cx is None:  # sem caixa declarada: usa a extensao dos nos (registrado no meta)
            cx = dict(lat_min=n.lat.min(), lat_max=n.lat.max(), lng_min=n.lng.min(), lng_max=n.lng.max())
        cob[dd.name] = margem_graus(P.lat.to_numpy(), P.lng.to_numpy(), cx["lat_min"], cx["lat_max"], cx["lng_min"], cx["lng_max"])
        e = pq.read_table(ef, columns=["u", "v", "length_m", "hw", "way_id"]).to_pandas()
        e = e[e.hw.isin(CARRO)]
        wl.append(e[e.hw.isin(ART)].groupby("way_id").length_m.sum())
        nx, ny = TF.transform(n.lng.to_numpy(), n.lat.to_numpy())
        pos = pd.Series(np.arange(len(n)), index=n.index)
        iu, iv = pos.reindex(e.u).to_numpy(), pos.reindex(e.v).to_numpy()
        ok = ~(np.isnan(iu) | np.isnan(iv)); e, iu, iv = e[ok], iu[ok].astype(int), iv[ok].astype(int)
        x0, y0, x1, y1 = nx[iu], ny[iu], nx[iv], ny[iv]
        pre = (np.maximum(x0, x1) >= ux0) & (np.minimum(x0, x1) <= ux1) & (np.maximum(y0, y1) >= uy0) & (np.minimum(y0, y1) <= uy1)
        if not pre.any():
            continue
        e, x0, y0, x1, y1 = e[pre], x0[pre], y0[pre], x1[pre], y1[pre]
        L = shapely.linestrings(np.stack([np.column_stack([x0, y0]), np.column_stack([x1, y1])], axis=1))
        hit = np.unique(tree.query(L, predicate="intersects")[0])
        if len(hit):
            seg.append(pd.DataFrame({"way_id": e.way_id.to_numpy()[hit], "u": e.u.to_numpy()[hit], "v": e.v.to_numpy()[hit], "hw": e.hw.to_numpy()[hit],
                                     "x0": x0[hit], "y0": y0[hit], "x1": x1[hit], "y1": y1[hit], "caixa": dd.name}))
        print(f"{dd.name}: {len(e):,} segmentos na janela, {len(hit):,} a <= {RAIO:.0f} m", flush=True)
    V = pd.concat(seg, ignore_index=True)
    k0 = len(V)
    V["a"], V["b"] = np.minimum(V.u, V.v), np.maximum(V.u, V.v)
    V = V.drop_duplicates(subset=["way_id", "a", "b"]).drop(columns=["a", "b"]).reset_index(drop=True)  # chave exata (§19)
    V.to_parquet(OUT / "vias_entorno.parquet", index=False)
    M = pd.DataFrame(cob)
    C = P[["chave", "origem", "lat", "lng"]].copy()
    C["margem_m"] = M.max(axis=1).to_numpy(); C["caixa"] = M.idxmax(axis=1).to_numpy()
    C.to_parquet(OUT / "cobertura.parquet", index=False)
    (OUT / "grafo_sha.txt").write_text("\n".join(shas) + "\n", encoding="utf-8")
    W = pd.concat(wl)
    meta = dict(raio_m=RAIO, gerado=f"{datetime.now():%Y-%m-%d %H:%M}", segmentos=len(V), duplicatas_entre_caixas=k0 - len(V),
                caixas_sem_json=sorted(k for k in M.columns if int(k.split("_")[1]) not in CAIXAS),
                way_arterial_m={str(q): round(float(W.quantile(q)), 0) for q in (0.5, 0.9, 0.95, 0.99)},
                way_arterial_frac_gt_1km=round(float((W > 1000).mean()), 4), way_arterial_frac_gt_5km=round(float((W > 5000).mean()), 4))
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"segmentos gravados: {len(V):,} (de {k0:,}); unidades: {len(C)}; margem >= 1 km: lab {int(((C.origem == 'lab') & (C.margem_m >= 1000)).sum())}, "
          f"ultra {int(((C.origem == 'ultra') & (C.margem_m >= 1000)).sum())}; >= 3 km lab {int(((C.origem == 'lab') & (C.margem_m >= 3000)).sum())}; "
          f">= 5 km lab {int(((C.origem == 'lab') & (C.margem_m >= 5000)).sum())}")
    print("meta:", meta)


if __name__ == "__main__":
    main()
