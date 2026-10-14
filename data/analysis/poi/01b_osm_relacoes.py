# -*- coding: utf-8 -*-
"""Complemento do 01_osm_poi.py: POIs mapeados como RELACAO multipolygon (o 01 so' via nos e ways).
Shopping grande, campus e algumas estacoes existem so' como relacao. Achado da auditoria de 2026-09-25.
Mesmas REGRAS de categoria do 01; ponto = centroide simples dos vertices dos aneis externos.
Saida: data/staging/poi/osm_poi_rel_<regiao>.parquet (osm_tipo = "relation"; o 04 le pelo mesmo glob).
Uso: venv-iso\\python 01b_osm_relacoes.py <regiao>
"""
import importlib.util
import sys
import time
from pathlib import Path

import osmium
import pandas as pd

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location("osm01", HERE / "01_osm_poi.py"); m01 = importlib.util.module_from_spec(spec); spec.loader.exec_module(m01)


def main(reg):
    t0 = time.time()
    rows = []
    fp = (osmium.FileProcessor(str(m01.PBF / f"{reg}-latest.osm.pbf"))
          .with_areas(osmium.filter.KeyFilter(*sorted(m01.CHAVES)))
          .with_filter(osmium.filter.EntityFilter(osmium.osm.AREA))
          .with_filter(osmium.filter.KeyFilter(*sorted(m01.CHAVES))))
    for o in fp:
        if o.from_way():
            continue  # ways fechados ja estao no 01
        r = m01.classificar(o.tags)
        if not r:
            continue
        la = lo = 0.0; k = 0
        for anel in o.outer_rings():
            for nd in anel:
                if nd.location.valid():
                    la += nd.location.lat; lo += nd.location.lon; k += 1
        if k:
            rows.append(("relation", o.orig_id(), la / k, lo / k, *r, o.tags.get("name", ""), reg))
    df = pd.DataFrame(rows, columns=["osm_tipo", "osm_id", "lat", "lng", "chave", "valor", "categoria", "nome", "regiao_pbf"])
    df["fonte"] = "osm_geofabrik_2026-09-23"
    df.to_parquet(m01.OUT / f"osm_poi_rel_{reg}.parquet", index=False)
    print(f"[{reg}] {len(df):,} relacoes em {time.time()-t0:.0f}s | {df.categoria.value_counts().head(10).to_dict()} | mall: {int((df.valor.eq('mall') & df.chave.eq('shop')).sum())}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
