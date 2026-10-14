# -*- coding: utf-8 -*-
"""BLK-UNI-00 / BLK-DADOS-UNI-01 itens 1-2: refaz a geografia das unidades com pino corrigido (Felipe, 2026-09-28).

  plaza-sul-sp       : -23.619836588209818, -46.62658767878267 (Shopping Plaza Sul; = pino 'Plaza / SP' do cadastro a 6 m;
                       22 m da listagem 'Ultra Academia - Shopping Plaza Sul' no Wellhub). Antes: Rua Itaucama, 1,34 km.
  sagrada-familia-mt : -16.472689780537294, -54.60695014754936 (Rondonopolis-MT; 1 m da listagem 'Ultra Sagrada Familia' no
                       Wellhub). Antes: geocodificado como 'Sagrada Familia, Cuiaba, MT' (cidade errada).

Reusa as funcoes do motor de isocronas (03/04/05 de data/analysis/isocronas, ISO_VERSAO=_v2) e do 05b de POI, SO' para esses
pontos, e grava tudo a parte em data/analysis/uni/correcoes_pinos/ — os arquivos das analises anteriores nao sao tocados.
Rondonopolis nao estava nas 137 regioes: o grafo viario dela e' extraido aqui (metro 900, bbox +-0,30 grau, PBF centro-oeste).
Depois: poi_painel/ = saidas do teste de POI com as linhas dessas unidades substituidas (o painel le daqui).
Uso: venv-iso\\python 06_corrigir_pinos.py   (um script por vez; extrai grafo + le setores de SP)
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ["ISO_VERSAO"] = "_v2"  # antes de importar os modulos do motor de isocronas

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import shapely  # noqa: E402
from shapely import wkb  # noqa: E402

UNI = Path(__file__).parent
ISO_REPO = UNI.parent / "isocronas"
POI_SAIDAS = UNI.parent / "poi" / "saidas"
SC_ISO = Path(r"C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\9259d0a1-7dda-49bd-a390-c88f3d4ac1a6\scratchpad\iso")
OUT = UNI / "correcoes_pinos"; OUT.mkdir(exist_ok=True)
PAINEL_POI = UNI / "poi_painel"; PAINEL_POI.mkdir(exist_ok=True)
CORR = {
    "plaza-sul-sp": {"lat": -23.619836588209818, "lng": -46.62658767878267, "fonte": "Felipe 2026-09-28: Shopping Plaza Sul (antes: Rua Itaucama, 1,34 km)"},
    "sagrada-familia-mt": {"lat": -16.472689780537294, "lng": -54.60695014754936, "fonte": "Felipe 2026-09-28: Rondonopolis-MT (antes: geocodificado em Cuiaba)"},
}
METRO_NOVO = 900


def mod(nome, caminho):
    s = importlib.util.spec_from_file_location(nome, caminho); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def metro_do_ponto(metros, lat, lng):
    for m in metros:
        if m["lat_min"] <= lat <= m["lat_max"] and m["lng_min"] <= lng <= m["lng_max"] and (SC_ISO / "grafo" / f"metro_{m['id']}" / "edges.parquet").exists():
            return m
    return None


def main():
    metros = json.load(open(ISO_REPO / "metros.json", encoding="utf-8"))
    m03 = mod("m03", ISO_REPO / "03_isocronas.py")
    m04 = mod("m04", ISO_REPO / "04_atributos.py")
    m05 = mod("m05", ISO_REPO / "05_base_testes.py")
    m05b = mod("m05b", UNI.parent / "poi" / "05b_familias_poi.py")
    # ---- pinos corrigidos
    up = pd.read_parquet(ISO_REPO / "ultra_pontos.parquet")
    for u, c in CORR.items():
        k = up.unidade_id.eq(u); assert k.sum() == 1, u
        up.loc[k, ["lat", "lng"]] = [c["lat"], c["lng"]]; up.loc[k, "confianca"] = "alta"; up.loc[k, "origem_coord"] = "correcao_manual_2026-09-28"
    up[up.unidade_id.isin(CORR)].assign(fonte=lambda d: d.unidade_id.map({u: c["fonte"] for u, c in CORR.items()})).to_parquet(OUT / "ultra_pontos_corrigidos.parquet", index=False)
    # ---- metro de cada ponto (Rondonopolis: extrai o grafo)
    alvo_metro = {}
    for u, c in CORR.items():
        m = metro_do_ponto(metros, c["lat"], c["lng"])
        if m is None:
            m = {"id": METRO_NOVO, "n_pontos": 1, "lat_min": c["lat"] - 0.30, "lat_max": c["lat"] + 0.30, "lng_min": c["lng"] - 0.32, "lng_max": c["lng"] + 0.32, "lat_c": c["lat"], "lng_c": c["lng"]}
            if not (SC_ISO / "grafo" / f"metro_{METRO_NOVO}" / "edges.parquet").exists():
                tmp = Path(tempfile.gettempdir()) / "metros_rondonopolis.json"
                json.dump([m], open(tmp, "w", encoding="utf-8"))
                print(f"extraindo grafo de {u} (metro {METRO_NOVO}) do PBF centro-oeste...", flush=True)
                r = subprocess.run([sys.executable, str(ISO_REPO / "02_grafo.py"), "centro-oeste"], env={**os.environ, "METROS_FILE": str(tmp)}, capture_output=True, text=True)
                print(r.stdout[-800:], r.stderr[-800:], flush=True)
                assert (SC_ISO / "grafo" / f"metro_{METRO_NOVO}" / "edges.parquet").exists(), "grafo nao gerado"
            json.dump(m, open(OUT / f"metro_{METRO_NOVO}.json", "w", encoding="utf-8"))
        alvo_metro[u] = m
        print(f"{u}: metro {m['id']}", flush=True)
    # ---- isocronas (mesmas funcoes do 03, v2)
    iso = []
    for u, m in alvo_metro.items():
        alvos = pd.DataFrame({"ponto_id": [u], "tipo": ["ultra"], "subtipo": [None], "lat": [CORR[u]["lat"]], "lng": [CORR[u]["lng"]]})
        for modo in ("carro", "pe"):
            iso.append(m03.processar_lote((m["id"], modo, 0, alvos, m["lat_c"], m["lng_c"], m)))
    iso = pd.concat(iso, ignore_index=True)
    iso.to_parquet(OUT / "poligonos_corrigidos.parquet", index=False)
    print(iso[["ponto_id", "modo", "limite_s", "snap_dist_m", "n_nos", "area_km2", "truncada"]].round(2).to_string(), flush=True)
    # ---- atributos (04 v2): diretorio temporario com as isocronas e o ultra_pontos corrigido
    tmpd = Path(tempfile.mkdtemp(prefix="uni_corr_"))
    (tmpd / "isocronas_v2").mkdir(); (tmpd / "atributos_v2").mkdir()
    up.to_parquet(tmpd / "ultra_pontos.parquet", index=False)
    pd.read_parquet(ISO_REPO / "academias_pontos.parquet").to_parquet(tmpd / "academias_pontos.parquet", index=False)
    m04.ISO, m04.OUT = tmpd, tmpd / "atributos_v2"
    lista = []
    for mid in sorted({m["id"] for m in alvo_metro.values()}):
        iso[iso.metro == mid].to_parquet(tmpd / "isocronas_v2" / f"metro_{mid}.parquet", index=False)
        mtr = next(m for m in alvo_metro.values() if m["id"] == mid)
        m04.rodar_metro(mid, [mtr])
        lista.append(pd.read_parquet(tmpd / "atributos_v2" / f"metro_{mid}.parquet"))
    at = pd.concat(lista, ignore_index=True)
    at.to_parquet(OUT / "atributos_corrigidos.parquet", index=False)
    # ---- linhas de base_ultra (colunas largas do 05) com a geografia nova
    w = m05.largo(at)
    bu = pd.read_parquet(ISO_REPO / "testes_v2" / "base_ultra.parquet")
    linhas = bu[bu.unidade_id.isin(CORR)].copy().set_index("unidade_id")
    geo_cols = [c for c in bu.columns if "__" in c]
    linhas[geo_cols] = np.nan
    for c in w.columns:
        if c in linhas.columns or "__" in c:
            linhas[c] = w[c].reindex(linhas.index)
    for c in [c for c in linhas.columns if c.startswith("n_ultra__")]:
        linhas[c.replace("n_ultra__", "n_ultra_outras__")] = (linhas[c] - 1).clip(lower=0)
    for u, c in CORR.items():
        linhas.loc[u, ["lat", "lng"]] = [c["lat"], c["lng"]]; linhas.loc[u, "confianca"] = "alta"; linhas.loc[u, "origem_coord"] = "correcao_manual_2026-09-28"
    linhas.reset_index().to_parquet(OUT / "base_ultra_linhas_corrigidas.parquet", index=False)
    # ---- canibalizacao (mesma conta do 05) das unidades corrigidas contra as outras Ultras do mesmo metro
    outras = pd.concat([pd.read_parquet(p, columns=["ponto_id", "tipo", "lat", "lng", "metro", "modo", "limite_s", "poligono_wkb"], filters=[("tipo", "==", "ultra")])
                        for p in sorted((ISO_REPO / "poligonos_v2").glob("metro_*.parquet"))])
    outras = outras[~outras.ponto_id.isin(CORR) & outras.poligono_wkb.notna() & (outras.modo == "carro")]
    pares = []
    for r in iso[(iso.modo == "carro") & iso.limite_s.isin([300, 600]) & iso.poligono_wkb.notna()].itertuples():
        pa_ = wkb.loads(r.poligono_wkb)
        cand = outras[(outras.limite_s == r.limite_s) & (outras.metro == r.metro)]
        for o in cand.itertuples():
            pb = wkb.loads(o.poligono_wkb); inter = pa_.intersection(pb).area
            if inter > 0:
                p = np.pi / 180
                dist = 2 * 6371 * np.arcsin(np.sqrt(np.sin((o.lat - r.lat) * p / 2) ** 2 + np.cos(r.lat * p) * np.cos(o.lat * p) * np.sin((o.lng - r.lng) * p / 2) ** 2))
                pares.append({"a": r.ponto_id, "b": o.ponto_id, "metro": int(r.metro), "limite_min": int(r.limite_s) // 60, "dist_km": float(dist), "frac_a": inter / pa_.area, "frac_b": inter / pb.area})
    pd.DataFrame(pares, columns=["a", "b", "metro", "limite_min", "dist_km", "frac_a", "frac_b"]).to_parquet(OUT / "canibal_pares_corrigidos.parquet", index=False)
    print(f"canibalizacao: {len(pares)} pares", flush=True)
    # ---- POI (05b) so' nos poligonos corrigidos
    def poligonos_corrigidos():
        p = iso[iso.poligono_wkb.notna()].copy()
        p["origem"] = "ultra_v2"; p["metro"] = p.metro.astype(str)
        p["area"] = [m05b.AREAS.get((m, int(l))) for m, l in zip(p.modo, p.limite_s)]
        p = p[p.area.notna()].reset_index(drop=True)
        p["geom"] = [wkb.loads(b) for b in p.poligono_wkb]
        for g in p.geom:
            shapely.prepare(g)
        p[["xmin", "ymin", "xmax", "ymax"]] = shapely.bounds(np.array(p.geom.tolist()))
        return p[["ponto_id", "lat", "lng", "metro", "origem", "area", "geom", "xmin", "ymin", "xmax", "ymax"]]
    (OUT / "poi").mkdir(exist_ok=True)
    m05b.poligonos, m05b.OUT = poligonos_corrigidos, OUT / "poi"
    m05b.main()
    # ---- poi_painel: saidas do teste de POI com as linhas dessas unidades trocadas (o teste congelado fica intacto)
    for nome in ("familias_por_poligono", "ancoras_pe15", "fitness_carro10"):
        base = pd.read_parquet(POI_SAIDAS / f"{nome}.parquet")
        base = base[~(base.origem.eq("ultra_v2") & base.ponto_id.isin(CORR))]
        novo = pd.read_parquet(OUT / "poi" / f"{nome}.parquet")
        pd.concat([base, novo], ignore_index=True).to_parquet(PAINEL_POI / f"{nome}.parquet", index=False)
    print("ok: correcoes_pinos/ e poi_painel/ gravados", flush=True)


if __name__ == "__main__":
    main()
