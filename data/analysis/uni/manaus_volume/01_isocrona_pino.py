# -*- coding: utf-8 -*-
"""Passo 0b do protocolo_manaus_volume.md: isocrona REAL (carro 5/10/15 min) do pino NOVA CIDADE com a MESMA funcao do
pipeline das unidades (03_isocronas.processar_lote, ISO_VERSAO=_v2; grafo metro_44) e atributos com
04_atributos.atributos_poligono (setores + academias_pontos + ultra_pontos da caixa do metro). Wellhub/TotalPass na
isocrona de 10 min pela regra de 03_dim_unidade.planos (sem Ultra, sem estudio boutique, musculacao). So' le e grava
nesta pasta. .venv, PYTHONPATH=src."""
import os

os.environ["ISO_VERSAO"] = "_v2"
import importlib.util  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
from pathlib import Path  # noqa: E402

import geopandas as gpd  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import shapely  # noqa: E402
from shapely import wkb  # noqa: E402
from shapely.geometry import Point  # noqa: E402

from motor_expansao.dashboard import planos_agregador as pa  # noqa: E402
from motor_expansao.pipelines.enriquecimento_espacial_hexagonos import REDES_ESTUDIO_BOUTIQUE  # noqa: E402

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
SIM = UNI / "simulacoes"
SC = Path(r"C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\9259d0a1-7dda-49bd-a390-c88f3d4ac1a6\scratchpad")
ISO = SC / "iso"
PIN = dict(ponto_id="manaus_nova_cidade", lat=-3.03514, lng=-59.996833)
MUSC_V2 = re.compile(r"muscula|treino de forca|fisiculturismo|levantamento de peso|treino hibrido")  # = 03_dim_unidade.py:54


def mod(nome, p):
    s = importlib.util.spec_from_file_location(nome, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def contar_planos(poly4326, fonte):
    """Mesma regra de 03_dim_unidade.planos (sem gravar ordem_tiers): musculacao V2 no Wellhub / coluna no TotalPass."""
    p = pd.read_parquet(UNI / "insumos_vps" / f"planos_{fonte}.parquet")
    p["e_ultra"] = pa._e_ultra(p.nome)
    rx = pa.padrao_de_redes(REDES_ESTUDIO_BOUTIQUE)
    p["estudio"] = p.nome.map(lambda n: bool(re.search(rx, pa._sem_acento(n)))) if rx else False
    musc = p.modalidades.fillna("").map(lambda m: bool(MUSC_V2.search(pa._sem_acento(m)))) if fonte == "wellhub" else p.musculacao.fillna(False).astype(bool)
    conc = p[~p.e_ultra & ~p.estudio & musc]
    dentro = conc[shapely.contains_xy(poly4326, conc.lng.to_numpy(float), conc.lat.to_numpy(float))]
    return int(len(dentro)), int(dentro.preco.notna().sum())


def main():
    i03 = mod("i03", ISO / "03_isocronas.py")
    i04 = mod("i04", ISO / "04_atributos.py")
    mn = mod("mn", SIM / "manaus_nova_cidade.py")
    mtr = next(m for m in json.load(open(ISO / "metros.json", encoding="utf-8")) if m["id"] == 44)
    alvos = pd.DataFrame([{**PIN, "tipo": "ultra_nova", "subtipo": None}])
    iso = i03.processar_lote((44, "carro", 0, alvos, mtr["lat_c"], mtr["lng_c"], mtr))
    iso.to_parquet(AQUI / "isocrona_pino.parquet", index=False)
    g = mn.setores_no_bbox(mtr)  # leitor com ParquetFile (o pyarrow do .venv falha na particao uf=)
    acad = pd.read_parquet(i04.ISO / "academias_pontos.parquet")
    acad = acad[acad.lat.between(mtr["lat_min"], mtr["lat_max"]) & acad.lng.between(mtr["lng_min"], mtr["lng_max"])].reset_index(drop=True)
    ult = pd.read_parquet(i04.ISO / "ultra_pontos.parquet").dropna(subset=["lat"])
    ult = ult[ult.lat.between(mtr["lat_min"], mtr["lat_max"]) & ult.lng.between(mtr["lng_min"], mtr["lng_max"])]
    ctx = i04.Contexto(g, acad, ult)
    xy = gpd.GeoSeries([Point(PIN["lng"], PIN["lat"])], crs=4326).to_crs(5880).iloc[0]
    out = {"setores": int(len(g)), "academias_caixa": int(len(acad)), "ultra_caixa": int(len(ult))}
    for r in iso.itertuples(index=False):
        cen = f"carro_{int(r.limite_s) // 60}"
        base = {"area_km2": r.area_km2, "km_rua": r.km_rua, "n_nos": r.n_nos, "snap_dist_m": r.snap_dist_m, "r_max_m": r.r_max_m,
                "dist_borda_m": r.dist_borda_m, "truncada": bool(r.truncada)}
        if r.poligono_wkb is None:
            out[cen] = {**base, "sem_poligono": True}; continue
        p4326 = wkb.loads(r.poligono_wkb)
        p5880 = gpd.GeoSeries([p4326], crs=4326).to_crs(5880).iloc[0]
        at = i04.atributos_poligono(p5880, ctx, (xy.x, xy.y))
        out[cen] = {**base, **{k: (float(v) if isinstance(v, (int, float, np.floating, np.integer)) else v) for k, v in at.items()}}
        if cen == "carro_10":
            out[cen]["wh_n_conc_c10"], out[cen]["wh_n_conc_com_preco_c10"] = contar_planos(p4326, "wellhub")
            out[cen]["tp_n_conc_c10"], out[cen]["tp_n_conc_com_preco_c10"] = contar_planos(p4326, "totalpass")
    (AQUI / "atributos_pino.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
