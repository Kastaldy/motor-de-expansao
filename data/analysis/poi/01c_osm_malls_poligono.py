# -*- coding: utf-8 -*-
"""Poligonos dos shoppings (shop=mall, ways fechados e relacoes) para a regra "unidade em shopping" do F3.
O centroide de um shopping grande pode ficar a > 150 m da academia que esta DENTRO dele (auditoria 2, 2026-09-25).
Saida: data/staging/poi/osm_malls_poligonos.parquet (osm_tipo, osm_id, nome, poligono_wkb em EPSG:4326)
Uso: venv-iso\\python 01c_osm_malls_poligono.py   (as 5 regioes, em sequencia)
"""
import time
from pathlib import Path

import osmium
import pandas as pd

PBF = Path(r"C:\dev\motor-de-expansao\data\osm_cache\pbf")
OUT = Path(r"C:\dev\motor-de-expansao\data\staging\poi")
REGIOES = ["centro-oeste", "sul", "nordeste", "norte", "sudeste"]


def main():
    wkbf = osmium.geom.WKBFactory()
    rows = []
    for reg in REGIOES:
        t0 = time.time(); n0 = len(rows)
        fp = (osmium.FileProcessor(str(PBF / f"{reg}-latest.osm.pbf"))
              .with_areas(osmium.filter.TagFilter(("shop", "mall")))
              .with_filter(osmium.filter.EntityFilter(osmium.osm.AREA))
              .with_filter(osmium.filter.TagFilter(("shop", "mall"))))
        for o in fp:
            try:
                g = wkbf.create_multipolygon(o)
            except Exception:  # anel invalido
                continue
            rows.append(("way" if o.from_way() else "relation", o.orig_id(), o.tags.get("name", ""), bytes.fromhex(g) if isinstance(g, str) else g))
        print(f"[{reg}] {len(rows) - n0:,} shoppings com poligono | {time.time()-t0:.0f}s", flush=True)
    df = pd.DataFrame(rows, columns=["osm_tipo", "osm_id", "nome", "poligono_wkb"]).drop_duplicates(["osm_tipo", "osm_id"])
    df.to_parquet(OUT / "osm_malls_poligonos.parquet", index=False)
    print(f"total {len(df):,}")


if __name__ == "__main__":
    main()
