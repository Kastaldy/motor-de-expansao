# -*- coding: utf-8 -*-
"""Pontos de interesse do OpenStreetMap (Geofabrik, extratos regionais do Brasil) -> data/staging/poi/osm_poi_<regiao>.parquet

Nos e ways com tags de atividade; way vira o centroide simples dos seus nos. Uma regiao por execucao.
Uso: venv-iso\\python 01_osm_poi.py <regiao>   (centro-oeste, sudeste, sul, nordeste, norte)
Colunas: osm_tipo, osm_id, lat, lng, chave, valor, categoria, nome, fonte, regiao_pbf
"""
import sys
import time
from pathlib import Path

import osmium
import pandas as pd

PBF = Path(r"C:\dev\motor-de-expansao\data\osm_cache\pbf")
OUT = Path(r"C:\dev\motor-de-expansao\data\staging\poi"); OUT.mkdir(parents=True, exist_ok=True)

# (chave, valor ou "*") -> categoria. Ordem importa: a primeira regra que casa vence.
REGRAS = [
    ("shop", "mall", "shopping"),
    ("amenity", "marketplace", "shopping"),
    ("leisure", "fitness_centre", "fitness"), ("leisure", "sports_centre", "fitness"), ("sport", "fitness", "fitness"),
    ("railway", "station", "transporte"), ("railway", "subway_entrance", "transporte"), ("railway", "halt", "transporte"),
    ("public_transport", "station", "transporte"), ("amenity", "bus_station", "transporte"), ("highway", "bus_stop", "ponto_onibus"),
    ("amenity", "university", "educacao_superior"), ("amenity", "college", "educacao_superior"),
    ("amenity", "school", "educacao_basica"), ("amenity", "kindergarten", "educacao_basica"),
    ("amenity", "hospital", "saude"), ("amenity", "clinic", "saude"), ("amenity", "doctors", "saude"), ("amenity", "dentist", "saude"),
    ("amenity", "pharmacy", "farmacia"), ("healthcare", "*", "saude"),
    ("amenity", "restaurant", "alimentacao"), ("amenity", "fast_food", "alimentacao"), ("amenity", "cafe", "alimentacao"),
    ("amenity", "bar", "alimentacao"), ("amenity", "pub", "alimentacao"), ("amenity", "food_court", "alimentacao"),
    ("shop", "supermarket", "supermercado"), ("shop", "convenience", "comercio"), ("shop", "*", "comercio"),
    ("amenity", "bank", "servico_financeiro"), ("amenity", "atm", "servico_financeiro"),
    ("office", "*", "escritorio"), ("building", "office", "escritorio"), ("building", "commercial", "comercio"), ("building", "retail", "comercio"),
    ("amenity", "place_of_worship", "religioso"), ("amenity", "townhall", "governo"), ("office", "government", "governo"),
    ("leisure", "park", "lazer"), ("leisure", "stadium", "lazer"), ("leisure", "pitch", "lazer"), ("amenity", "cinema", "lazer"), ("amenity", "theatre", "lazer"),
    ("tourism", "hotel", "hospedagem"), ("tourism", "*", "turismo"),
    ("amenity", "fuel", "posto"), ("amenity", "parking", "estacionamento"),
]
CHAVES = {c for c, _, _ in REGRAS}


def classificar(tags):
    for c, v, cat in REGRAS:
        tv = tags.get(c)
        if tv is not None and (v == "*" or tv == v):
            return c, tv, cat
    return None


class H(osmium.SimpleHandler):
    def __init__(self, reg):
        super().__init__(); self.reg = reg; self.rows = []

    def node(self, n):
        if not any(k in n.tags for k in CHAVES):
            return
        r = classificar(n.tags)
        if r and n.location.valid():
            self.rows.append(("node", n.id, n.location.lat, n.location.lon, *r, n.tags.get("name", ""), self.reg))

    def way(self, w):
        if not any(k in w.tags for k in CHAVES):
            return
        r = classificar(w.tags)
        if not r:
            return
        la = lo = 0.0; k = 0
        for nd in w.nodes:
            try:
                if nd.location.valid():
                    la += nd.location.lat; lo += nd.location.lon; k += 1
            except osmium.InvalidLocationError:
                pass
        if k:
            self.rows.append(("way", w.id, la / k, lo / k, *r, w.tags.get("name", ""), self.reg))


def main(reg):
    t0 = time.time()
    rows = []
    # filtro nativo: so' objetos com alguma das chaves chegam ao Python; locations no C++ para os ways
    fp = osmium.FileProcessor(str(PBF / f"{reg}-latest.osm.pbf")).with_locations("flex_mem").with_filter(osmium.filter.KeyFilter(*sorted(CHAVES)))
    for o in fp:
        if o.is_node():
            r = classificar(o.tags)
            if r and o.location.valid():
                rows.append(("node", o.id, o.location.lat, o.location.lon, *r, o.tags.get("name", ""), reg))
        elif o.is_way():
            r = classificar(o.tags)
            if not r:
                continue
            la = lo = 0.0; k = 0
            for nd in o.nodes:
                try:
                    if nd.location.valid():
                        la += nd.location.lat; lo += nd.location.lon; k += 1
                except osmium.InvalidLocationError:
                    pass
            if k:
                rows.append(("way", o.id, la / k, lo / k, *r, o.tags.get("name", ""), reg))
    df = pd.DataFrame(rows, columns=["osm_tipo", "osm_id", "lat", "lng", "chave", "valor", "categoria", "nome", "regiao_pbf"])
    df["fonte"] = "osm_geofabrik_2026-09-23"
    df.to_parquet(OUT / f"osm_poi_{reg}.parquet", index=False)
    print(f"[{reg}] {len(df):,} POIs em {time.time()-t0:.0f}s | {df.categoria.value_counts().head(12).to_dict()}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
