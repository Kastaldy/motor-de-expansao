# -*- coding: utf-8 -*-
"""Etapa 1 do protocolo_poi_uni00.md v1: materializa as familias de POI por poligono (NAO le desfecho nenhum).

Poligonos (areas pe_15 = 900 s a pe e carro_10 = 600 s de carro):
  ultra_v2  : isocronas_v2 tipo ultra
  smartfit  : isocronas_v2 tipo academia com ponto_id da Smart Fit em alunos_reais_por_unidade (VPS)
  multirede : multirede/atributos (Ultra, Engenharia do Corpo, SkyFit)
Saidas em data/analysis/poi/saidas/:
  familias_por_poligono.parquet  uma linha por (origem, ponto_id, area)
     pe_15   : F1_fil / F1_all / F2_fil / F2_all  = pontos exatos + rateio por CEP; *_exato = so' a parte exata; F2b_cnefe
     carro_10: F1_fil_c10 / F1_all_c10 / F2_fil_c10 / F2_all_c10 (todo CNPJ localizado como ponto); edu_cnpj; edu_osm
  ancoras_pe15.parquet           mall / estacao / hiper dentro de pe_15 (deduplicacao e regra dos 150 m ficam no 06)
  fitness_carro10.parquet        CNPJ 9313-1/00 localizado dentro de carro_10 (ano de inicio; filtro de 150 m no 06)
Estoque: familias F1/F2 so' com data_inicio < 2025-01-01. Uso: venv-iso\\python 05b_familias_poi.py
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
SC = Path(r"C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\9259d0a1-7dda-49bd-a390-c88f3d4ac1a6\scratchpad")
ISO = SC / "iso"
POI = ROOT / "data" / "staging" / "poi"
OUT = ROOT / "data" / "analysis" / "poi" / "saidas"; OUT.mkdir(parents=True, exist_ok=True)
AREAS = {("pe", 900): "pe_15", ("carro", 600): "carro_10"}
MARGEM = 0.02
ESTOQUE = "20250101"
F1_DIV = {"62", "63", "64", "65", "66", "69", "70", "71", "84"}
F1_EXC = {"6462000", "6470101", "6470102", "6470103"}
F2_DIV = {"47", "56", "96"}
OSM_ANCORA = {"shop=mall": "mall", "railway=station": "estacao", "public_transport=station": "estacao", "amenity=bus_station": "estacao"}
FAM = ["F1_fil", "F1_all", "F2_fil", "F2_all"]


def poligonos():
    sf_ids = set(pd.read_parquet(SC / "vps" / "alunos_reais_por_unidade.parquet").query("rede == 'smart_fit'").concorrente_id)
    fr = []
    for f in sorted((ISO / "isocronas_v2").glob("metro_*.parquet")):
        s = pd.read_parquet(f, columns=["ponto_id", "tipo", "lat", "lng", "metro", "modo", "limite_s", "poligono_wkb"])
        s = s[s.tipo.eq("ultra") | (s.tipo.eq("academia") & s.ponto_id.isin(sf_ids))]
        fr.append(s.assign(origem=np.where(s.tipo.eq("ultra"), "ultra_v2", "smartfit")).drop(columns="tipo"))
    pts = pd.read_parquet(ISO / "multirede" / "pontos.parquet")[["ponto_id", "lat", "lng"]]
    for f in sorted((ISO / "multirede" / "atributos").glob("poligonos_metro_*.parquet")):
        s = pd.read_parquet(f).merge(pts, on="ponto_id", how="left")
        fr.append(s.assign(origem="multirede", metro=f.stem.split("_")[-1]))
    p = pd.concat(fr, ignore_index=True)
    p["metro"] = p["metro"].astype(str)
    p["area"] = [AREAS.get((m, int(l))) for m, l in zip(p.modo, p.limite_s)]
    p = p[p.area.notna() & p.poligono_wkb.notna()].drop_duplicates(["origem", "ponto_id", "area"]).reset_index(drop=True)
    p["geom"] = [wkb.loads(b) for b in p.poligono_wkb]
    for g in p.geom:
        shapely.prepare(g)
    p[["xmin", "ymin", "xmax", "ymax"]] = shapely.bounds(np.array(p.geom.tolist()))
    return p.drop(columns=["poligono_wkb", "modo", "limite_s"])


def caixas_uf():
    cx = {}
    for d in sorted((ROOT / "data" / "staging" / "brasil").glob("uf=*")):
        h = pd.read_parquet(d / "hexagonos.parquet", columns=["lat", "lng"])
        cx[d.name[3:]] = (h.lng.min() - MARGEM, h.lat.min() - MARGEM, h.lng.max() + MARGEM, h.lat.max() + MARGEM)
    return cx


def em_caixa(df, b):
    return df[(df.lng >= b[0]) & (df.lng <= b[2]) & (df.lat >= b[1]) & (df.lat <= b[3])]


class Pontos:
    """Pontos ordenados por longitude para recorte rapido da caixa de cada poligono."""
    def __init__(self, lng, lat, **cols):
        o = np.argsort(lng); self.x = np.asarray(lng)[o]; self.y = np.asarray(lat)[o]
        self.c = {k: np.asarray(v)[o] for k, v in cols.items()}

    def dentro(self, r):
        a, b = np.searchsorted(self.x, r.xmin, "left"), np.searchsorted(self.x, r.xmax, "right")
        idx = np.arange(a, b)
        m = (self.y[a:b] >= r.ymin) & (self.y[a:b] <= r.ymax)
        idx = idx[m]
        if len(idx) == 0:
            return idx
        return idx[shapely.contains_xy(r.geom, self.x[idx], self.y[idx])]


def main():
    t0 = time.time()
    P = poligonos()
    print(f"{len(P):,} poligonos {P.groupby(['origem', 'area']).size().to_dict()}", flush=True)
    linhas, anc, fit = [], [], []
    for uf, cxu in caixas_uf().items():
        sel = P[(P.xmax >= cxu[0]) & (P.xmin <= cxu[2]) & (P.ymax >= cxu[1]) & (P.ymin <= cxu[3])]
        if sel.empty:
            continue
        t1 = time.time()
        bb = (sel.xmin.min(), sel.ymin.min(), sel.xmax.max(), sel.ymax.max())
        # ---- CNPJ
        c = pd.read_parquet(POI / f"cnpj_ativos_{uf}.parquet", columns=["matriz_filial", "data_inicio", "cnae_principal", "cep", "lat", "lng", "geo_nivel"])
        c = c[c.geo_nivel.ne("sem_coordenada")]
        cn, dv = c.cnae_principal.fillna(""), c.cnae_principal.fillna("").str[:2]
        est = c.data_inicio.fillna("99999999") < ESTOQUE
        fil = c.matriz_filial.eq("2")
        f1 = dv.isin(F1_DIV) | cn.str.startswith("8610")
        f1 &= ~cn.isin(F1_EXC)
        f2 = dv.isin(F2_DIV)
        flags = pd.DataFrame({"F1_fil": f1 & fil & est, "F1_all": f1 & est, "F2_fil": f2 & fil & est, "F2_all": f2 & est})
        edu = cn.str[:4].isin(["8531", "8532", "8533"]) & est
        hip = cn.eq("4711301") & c.geo_nivel.isin(["cep_numero", "cep"]) & est  # estoque tambem na ancora (auditoria)
        fitn = cn.eq("9313100")
        keep = flags.any(axis=1) | edu | hip | fitn
        c, flags, edu, hip, fitn = c[keep], flags[keep], edu[keep], hip[keep], fitn[keep]
        exato = c.geo_nivel.eq("cep_numero").to_numpy()
        # pontos exatos (a pe) e todos localizados (carro)
        Fx = flags.to_numpy(np.float64)
        cb = em_caixa(c.assign(_i=np.arange(len(c))), bb)
        PT = Pontos(cb.lng.to_numpy(), cb.lat.to_numpy(), i=cb._i.to_numpy())
        # CEP-level para rateio: contagem por CEP das familias
        cl = c.geo_nivel.isin(["cep", "cep_area"]).to_numpy()
        ccep = pd.DataFrame(Fx[cl], columns=FAM).assign(cep=c.cep.to_numpy()[cl]).groupby("cep").sum()
        # ---- CNEFE para rateio
        ce_tot = pd.read_parquet(POI / f"cnefe_cep_{uf}.parquet", columns=["cep", "n"]).set_index("cep").n
        cnf = em_caixa(pd.read_parquet(POI / f"cnefe_cep_numero_{uf}.parquet", columns=["cep", "lat", "lng", "n"]), bb)
        cnf = cnf[cnf.cep.isin(ccep.index)]
        ceps = pd.Index(ccep.index)
        CN = Pontos(cnf.lng.to_numpy(), cnf.lat.to_numpy(), k=ceps.get_indexer(cnf.cep), n=cnf.n.to_numpy(float))
        tot = ce_tot.reindex(ceps).fillna(np.inf).to_numpy(float)
        C = ccep.to_numpy(float)
        # ---- base unica (OSM ancoras/universidade, CNEFE F2b)
        dset = ds.dataset(ROOT / "data" / "staging" / "poi" / "base_poi_unica" / f"uf={uf}", format="parquet")
        filt = (pc.field("lng") >= bb[0]) & (pc.field("lng") <= bb[2]) & (pc.field("lat") >= bb[1]) & (pc.field("lat") <= bb[3])
        u = dset.to_table(columns=["fonte", "categoria", "subcategoria", "geo_nivel", "nome", "lat", "lng"], filter=filt).to_pandas()
        osm = u[u.fonte.eq("osm") & (u.subcategoria.isin(list(OSM_ANCORA)) | u.subcategoria.eq("amenity=university"))].reset_index(drop=True)
        OS = Pontos(osm.lng.to_numpy(), osm.lat.to_numpy(), i=np.arange(len(osm)))
        f2b = u[u.fonte.eq("cnefe") & u.categoria.eq("estabelecimento") & u.geo_nivel.isin(["cnefe_nv1", "cnefe_nv2", "cnefe_nv3"])]
        FB = Pontos(f2b.lng.to_numpy(), f2b.lat.to_numpy())
        del u
        for r in sel.itertuples():
            row = {"origem": r.origem, "ponto_id": r.ponto_id, "area": r.area, "metro": r.metro}
            ii = PT.dentro(r); gi = PT.c["i"][ii]
            if r.area == "pe_15":
                ex = gi[exato[gi]]
                pt = Fx[ex].sum(0)
                jj = CN.dentro(r)
                if len(jj):
                    ins = np.bincount(CN.c["k"][jj], weights=CN.c["n"][jj], minlength=len(ceps))
                    rat = (ins / tot) @ C
                else:
                    rat = np.zeros(len(FAM))
                for k, f in enumerate(FAM):
                    row[f] = pt[k] + rat[k]; row[f + "_exato"] = pt[k]
                row["F2b_cnefe"] = len(FB.dentro(r))
                oo = OS.c["i"][OS.dentro(r)]
                for _, o in osm.iloc[oo].iterrows():
                    if o.subcategoria in OSM_ANCORA and (o.subcategoria != "shop=mall" or isinstance(o.nome, str)):
                        anc.append((r.origem, r.ponto_id, OSM_ANCORA[o.subcategoria], o.nome, o.lat, o.lng, "osm"))
                hh = gi[hip.to_numpy()[gi]]
                for j in hh:
                    anc.append((r.origem, r.ponto_id, "hiper", None, c.lat.iat[j], c.lng.iat[j], "cnpj"))
            else:
                s = Fx[gi].sum(0)
                for k, f in enumerate(FAM):
                    row[f + "_c10"] = s[k]
                row["edu_cnpj"] = int(edu.to_numpy()[gi].sum())
                oo = OS.c["i"][OS.dentro(r)]
                row["edu_osm"] = int(osm.subcategoria.iloc[oo].eq("amenity=university").sum())
                ff = gi[fitn.to_numpy()[gi]]
                for j in ff:
                    fit.append((r.origem, r.ponto_id, c.lat.iat[j], c.lng.iat[j], c.geo_nivel.iat[j], c.data_inicio.iat[j]))
            linhas.append(row)
        print(f"[{uf}] {len(sel)} poligonos | CNPJ {len(c):,} | CNEFE rateio {len(cnf):,} | {time.time()-t1:.0f}s", flush=True)
    d = pd.DataFrame(linhas)
    num = [c_ for c_ in d.columns if c_ not in ("origem", "ponto_id", "area", "metro")]
    d = d.groupby(["origem", "ponto_id", "area"], as_index=False).agg({**{c_: "sum" for c_ in num}, "metro": "first"})
    d.to_parquet(OUT / "familias_por_poligono.parquet", index=False)
    pd.DataFrame(anc, columns=["origem", "ponto_id", "tipo", "nome", "lat", "lng", "fonte"]).drop_duplicates().to_parquet(OUT / "ancoras_pe15.parquet", index=False)
    # sem drop_duplicates: CNPJs distintos no mesmo centroide de CEP sao academias distintas (auditoria)
    pd.DataFrame(fit, columns=["origem", "ponto_id", "lat", "lng", "geo_nivel", "data_inicio"]).to_parquet(OUT / "fitness_carro10.parquet", index=False)
    print(f"{len(d):,} linhas | {d.groupby(['origem', 'area']).size().to_dict()} | ancoras {len(anc):,} | fitness {len(fit):,} | {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
