# -*- coding: utf-8 -*-
"""Base unica de pontos de interesse -> data/staging/poi/base_poi_unica/uf=XX/parte-0.parquet

Junta as tres fontes ja processadas (01_osm_poi, 02_cnefe, 03_cnpj), uma UF por vez (memoria):
  osm   : POIs do OpenStreetMap (categoria pelas REGRAS do 01)
  cnefe : enderecos NAO residenciais do Censo 2022 (especie IBGE)
  cnpj  : estabelecimentos ATIVOS da Receita (categoria pela divisao/classe CNAE)
Colunas: fonte, uf, h3_r7, lat, lng, categoria, subcategoria, geo_nivel, nome (so' OSM), cnae_principal,
         data_inicio, matriz_filial, multi_estab, id_origem
h3_r7 casa direto com o hex_id do motor. UF do OSM vem do hex r7 da base H3 Brasil (fallback: pai r5).
Linha CNPJ sem coordenada fica (lat/h3 nulos, geo_nivel=sem_coordenada) para contagem por municipio.
Uso: venv-iso\\python 04_base_unica.py
"""
import time
from pathlib import Path

import h3
import pandas as pd

ROOT = Path(r"C:\dev\motor-de-expansao")
POI = ROOT / "data" / "staging" / "poi"
OUT = POI / "base_poi_unica"
UFS = sorted(p.name[3:] for p in (ROOT / "data" / "staging" / "brasil").glob("uf=*"))
COLS = ["fonte", "uf", "h3_r7", "lat", "lng", "categoria", "subcategoria", "geo_nivel", "nome",
        "cnae_principal", "data_inicio", "matriz_filial", "multi_estab", "id_origem"]

CNEFE_CAT = {"ensino": "educacao", "saude": "saude", "religioso": "religioso", "agropecuario": "agropecuario",
             "outras_finalidades": "estabelecimento"}


def categoria_cnae(c):
    """CNAE 2.3 (7 digitos) -> categoria. Classes especificas primeiro, depois a divisao."""
    c = str(c or "")
    esp = {"9313100": "fitness", "4771701": "farmacia", "4771702": "farmacia", "4771703": "farmacia",
           "4711301": "supermercado", "4711302": "supermercado", "4712100": "comercio",
           "6810201": "imobiliario", "6810202": "imobiliario", "6821801": "imobiliario", "6822600": "imobiliario",
           "9491000": "religioso"}
    if c in esp:
        return esp[c]
    if c[:4] in ("8531", "8532", "8533"):
        return "educacao_superior"
    d = c[:2]
    if not d.isdigit():
        return "outros"
    d = int(d)
    faixas = [((1, 3), "agropecuario"), ((5, 33), "industria"), ((35, 39), "utilidades"), ((41, 43), "construcao"),
              ((45, 47), "comercio"), ((49, 53), "transporte_logistica"), ((55, 55), "hospedagem"),
              ((56, 56), "alimentacao"), ((58, 63), "informacao_tecnologia"), ((64, 66), "servico_financeiro"),
              ((68, 68), "imobiliario"), ((69, 75), "escritorio"), ((77, 82), "servicos_administrativos"),
              ((84, 84), "governo"), ((85, 85), "educacao"), ((86, 88), "saude"), ((90, 93), "lazer"),
              ((94, 94), "associacao"), ((95, 96), "servicos_pessoais"), ((97, 97), "domestico")]
    for (a, b), cat in faixas:
        if a <= d <= b:
            return cat
    return "outros"


def h3_col(lat, lng):
    return [h3.latlng_to_cell(a, b, 7) if a == a and b == b else None for a, b in zip(lat, lng)]


def mapa_uf():
    hx = pd.concat([pd.read_parquet(ROOT / "data" / "staging" / "brasil" / f"uf={u}" / "hexagonos.parquet", columns=["hex_id"]).assign(uf=u) for u in UFS])
    r7 = dict(zip(hx.hex_id, hx.uf))
    hx["r5"] = [h3.cell_to_parent(h, 5) for h in hx.hex_id]
    r5 = hx.groupby("r5").uf.agg(lambda s: s.mode().iat[0]).to_dict()
    return r7, r5


def main():
    t0 = time.time()
    r7, r5 = mapa_uf()
    osm = pd.concat([pd.read_parquet(f) for f in sorted(POI.glob("osm_poi_*.parquet"))], ignore_index=True)
    osm = osm.drop_duplicates(["osm_tipo", "osm_id"])  # extratos regionais se sobrepoem na borda
    osm["h3_r7"] = h3_col(osm.lat.to_numpy(), osm.lng.to_numpy())
    osm["uf"] = osm.h3_r7.map(r7)
    sem = osm.uf.isna()
    osm.loc[sem, "uf"] = [r5.get(h3.cell_to_parent(h, 5)) for h in osm.loc[sem, "h3_r7"]]
    osm = pd.DataFrame({"fonte": "osm", "uf": osm.uf, "h3_r7": osm.h3_r7, "lat": osm.lat, "lng": osm.lng,
                        "categoria": osm.categoria, "subcategoria": osm.chave + "=" + osm.valor, "geo_nivel": "osm",
                        "nome": osm.nome.where(osm.nome != ""), "id_origem": osm.osm_tipo + "/" + osm.osm_id.astype(str)})
    print(f"OSM: {len(osm):,} POIs, {osm.uf.isna().sum():,} fora do Brasil (descartados) | {time.time()-t0:.0f}s", flush=True)
    osm = osm.dropna(subset=["uf"])

    resumo = []
    for uf in UFS:
        t1 = time.time()
        ce = pd.read_parquet(POI / f"cnefe_estab_{uf}.parquet")
        ce = pd.DataFrame({"fonte": "cnefe", "uf": uf, "h3_r7": h3_col(ce.lat.to_numpy(), ce.lng.to_numpy()), "lat": ce.lat, "lng": ce.lng,
                           "categoria": ce.especie.map(CNEFE_CAT), "subcategoria": ce.especie, "geo_nivel": "cnefe_nv" + ce.nv_geo.astype(str),
                           "multi_estab": ce.multi_estab, "id_origem": ce.cod_setor})
        cj = pd.read_parquet(POI / f"cnpj_ativos_{uf}.parquet", columns=["matriz_filial", "data_inicio", "cnae_principal", "lat", "lng", "geo_nivel", "municipio_rf"])
        cats = {c: categoria_cnae(c) for c in cj.cnae_principal.unique()}
        cj = pd.DataFrame({"fonte": "cnpj", "uf": uf, "h3_r7": h3_col(cj.lat.to_numpy(), cj.lng.to_numpy()), "lat": cj.lat, "lng": cj.lng,
                           "categoria": cj.cnae_principal.map(cats), "subcategoria": cj.cnae_principal, "geo_nivel": "cnpj_" + cj.geo_nivel,
                           "cnae_principal": cj.cnae_principal, "data_inicio": cj.data_inicio, "matriz_filial": cj.matriz_filial,
                           "id_origem": "mun_rf/" + cj.municipio_rf.astype(str)})
        d = pd.concat([osm[osm.uf == uf], ce, cj], ignore_index=True).reindex(columns=COLS)
        (OUT / f"uf={uf}").mkdir(parents=True, exist_ok=True)
        d.to_parquet(OUT / f"uf={uf}" / "parte-0.parquet", index=False)
        resumo.append(d.groupby(["fonte", "categoria"]).size().rename(uf))
        print(f"[{uf}] {len(d):,} linhas ({d.fonte.value_counts().to_dict()}) | {time.time()-t1:.0f}s", flush=True)
    r = pd.concat(resumo, axis=1).fillna(0).astype(int)
    r["BR"] = r.sum(axis=1)
    r.to_csv(OUT / "resumo_fonte_categoria_uf.csv", sep=";", encoding="utf-8-sig")
    print(f"Total {r['BR'].sum():,} linhas em {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
