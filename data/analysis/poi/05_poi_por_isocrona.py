# -*- coding: utf-8 -*-
"""Conta POIs da base unica dentro das isocronas das academias (NAO le desfecho nenhum).

Poligonos:
  ultra_v2  : isocronas_v2/metro_*.parquet, tipo == "ultra"          (base do modelo de faturamento Ultra)
  multirede : multirede/atributos/poligonos_metro_*.parquet          (Ultra, Engenharia do Corpo, SkyFit)
Areas: carro_5 (300 s), carro_10 (600 s), pe_10 (600 s), pe_15 (900 s).
Saida longa (uma linha por poligono x chave com n > 0) em data/analysis/poi/saidas/poi_por_isocrona.parquet:
  origem_poligono, ponto_id, area, fonte, categoria, geo_grupo, recente, n
  geo_grupo: osm | cnefe | cnpj_exato (CEP+numero) | cnpj_cep (centroide do CEP); CNPJ sem coordenada fica fora.
  recente  : CNPJ com data_inicio >= 2023-01-01 (dinamismo); nas outras fontes = False.
Le uma UF por vez e so' a caixa envolvente dos poligonos daquela UF (memoria).
Uso: venv-iso\\python 05_poi_por_isocrona.py
"""
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.compute as pc
import pyarrow.dataset as ds
import shapely
from shapely import wkb

ROOT = Path(r"C:\dev\motor-de-expansao")
ISO = Path(r"C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\9259d0a1-7dda-49bd-a390-c88f3d4ac1a6\scratchpad\iso")
BASE = ROOT / "data" / "staging" / "poi" / "base_poi_unica"
OUT = ROOT / "data" / "analysis" / "poi" / "saidas"; OUT.mkdir(parents=True, exist_ok=True)
AREAS = {("carro", 300): "carro_5", ("carro", 600): "carro_10", ("pe", 600): "pe_10", ("pe", 900): "pe_15"}
MARGEM = 0.02  # graus: folga para poligono que cruza divisa de UF


def poligonos():
    fr = []
    for f in sorted((ISO / "isocronas_v2").glob("metro_*.parquet")):
        s = pd.read_parquet(f, columns=["ponto_id", "tipo", "modo", "limite_s", "poligono_wkb"], filters=[("tipo", "==", "ultra")])
        fr.append(s.assign(origem_poligono="ultra_v2"))
    for f in sorted((ISO / "multirede" / "atributos").glob("poligonos_metro_*.parquet")):
        fr.append(pd.read_parquet(f).assign(origem_poligono="multirede"))
    p = pd.concat(fr, ignore_index=True)
    p["area"] = [AREAS.get((m, int(l))) for m, l in zip(p.modo, p.limite_s)]
    p = p[p.area.notna() & p.poligono_wkb.notna()].drop_duplicates(["origem_poligono", "ponto_id", "area"]).reset_index(drop=True)
    p["geom"] = [wkb.loads(b) for b in p.poligono_wkb]
    b = shapely.bounds(np.array(p.geom.tolist()))
    p[["xmin", "ymin", "xmax", "ymax"]] = b
    return p.drop(columns=["poligono_wkb"])


def caixas_uf():
    cx = {}
    for d in sorted((ROOT / "data" / "staging" / "brasil").glob("uf=*")):
        h = pd.read_parquet(d / "hexagonos.parquet", columns=["lat", "lng"])
        cx[d.name[3:]] = (h.lng.min() - MARGEM, h.lat.min() - MARGEM, h.lng.max() + MARGEM, h.lat.max() + MARGEM)
    return cx


def main():
    t0 = time.time()
    P = poligonos()
    print(f"{len(P):,} poligonos ({P.groupby(['origem_poligono', 'area']).size().to_dict()})", flush=True)
    cx = caixas_uf()
    res = []
    for uf, (x0, y0, x1, y1) in cx.items():
        sel = P[(P.xmax >= x0) & (P.xmin <= x1) & (P.ymax >= y0) & (P.ymin <= y1)]
        if sel.empty:
            continue
        t1 = time.time()
        bx0, by0, bx1, by1 = sel.xmin.min(), sel.ymin.min(), sel.xmax.max(), sel.ymax.max()
        dset = ds.dataset(BASE / f"uf={uf}", format="parquet")
        filt = (pc.field("lng") >= bx0) & (pc.field("lng") <= bx1) & (pc.field("lat") >= by0) & (pc.field("lat") <= by1)
        t = dset.to_table(columns=["fonte", "categoria", "geo_nivel", "data_inicio", "lat", "lng"], filter=filt).to_pandas()
        if t.empty:
            continue
        t = t[~t.geo_nivel.eq("cnpj_sem_coordenada")]
        geo = np.where(t.fonte.eq("cnpj"), np.where(t.geo_nivel.eq("cnpj_cep_numero"), "cnpj_exato", "cnpj_cep"), t.fonte)
        rec = t.fonte.eq("cnpj").to_numpy() & (t.data_inicio.fillna("0").to_numpy() >= "20230101")
        chave = pd.Categorical(t.fonte.astype(str) + "|" + t.categoria.astype(str) + "|" + geo + "|" + rec.astype(str))
        cod = chave.codes; cats = chave.categories
        # ordena por longitude para recortar a caixa de cada poligono por busca binaria
        ordem = np.argsort(t.lng.to_numpy()); X = t.lng.to_numpy()[ordem]; Y = t.lat.to_numpy()[ordem]; C = cod[ordem]
        del t
        for r in sel.itertuples():
            a, b = np.searchsorted(X, r.xmin, "left"), np.searchsorted(X, r.xmax, "right")
            m = (Y[a:b] >= r.ymin) & (Y[a:b] <= r.ymax)
            xs, ys, cs = X[a:b][m], Y[a:b][m], C[a:b][m]
            if len(xs) == 0:
                continue
            dentro = shapely.contains_xy(r.geom, xs, ys)
            n = np.bincount(cs[dentro], minlength=len(cats))
            for k in np.nonzero(n)[0]:
                f, cat, g, rc = cats[k].split("|")
                res.append((r.origem_poligono, r.ponto_id, r.area, uf, f, cat, g, rc == "True", int(n[k])))
        print(f"[{uf}] {len(sel)} poligonos | {len(X):,} POIs na caixa | {time.time()-t1:.0f}s", flush=True)
    d = pd.DataFrame(res, columns=["origem_poligono", "ponto_id", "area", "uf_base", "fonte", "categoria", "geo_grupo", "recente", "n"])
    # poligono que cruza divisa soma as duas UFs
    d = d.groupby(["origem_poligono", "ponto_id", "area", "fonte", "categoria", "geo_grupo", "recente"], as_index=False)["n"].sum()
    d.to_parquet(OUT / "poi_por_isocrona.parquet", index=False)
    cob = d.groupby(["origem_poligono", "area"]).ponto_id.nunique()
    print(f"{len(d):,} linhas | poligonos com POI: {cob.to_dict()} | {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
