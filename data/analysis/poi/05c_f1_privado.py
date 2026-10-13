# -*- coding: utf-8 -*-
"""F1 privado para as unidades Ultra (area pe_15): a familia F1 do 05b SEM administracao publica (CNAE 84) e SEM
hospitais (8610). Pedido do Felipe (2026-09-29, BLK-UNI-05C): Wellhub/TotalPass sao beneficio de EMPRESA; servidor
publico em geral nao recebe. NAO le desfecho nenhum. Mesmo metodo do 05b (ponto exato + rateio por CEP, estoque < 2025).
Usa os poligonos com os pinos CORRIGIDOS em 28/09 (uni/correcoes_pinos) e confere o F1_fil contra uni/poi_painel
(o que o painel le). Correcao de 2026-09-29: a 1a versao usava os poligonos antigos (plaza-sul-sp, sagrada-familia-mt).
Saida: saidas/f1_privado_ultra.parquet. Uso: .venv\\python 05c_f1_privado.py (um script por vez; RAM curta).
"""
import importlib.util
import time
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
s_ = importlib.util.spec_from_file_location("p05b", AQUI / "05b_familias_poi.py"); b = importlib.util.module_from_spec(s_); s_.loader.exec_module(b)
FAM = ["F1_fil", "F1p_fil"]


def main():
    t0 = time.time()
    import shapely
    from shapely import wkb
    UNI = AQUI.parent / "uni"
    P = b.poligonos()
    P = P[P.origem.eq("ultra_v2") & P.area.eq("pe_15")].reset_index(drop=True)
    corr = pd.read_parquet(UNI / "correcoes_pinos" / "poligonos_corrigidos.parquet")
    corr = corr[corr.poligono_wkb.notna() & (corr.modo == "pe") & (corr.limite_s == 900)].drop_duplicates("ponto_id").copy()
    corr["origem"], corr["area"], corr["metro"] = "ultra_v2", "pe_15", corr.metro.astype(str)
    corr["geom"] = [wkb.loads(x) for x in corr.poligono_wkb]
    for g_ in corr.geom:
        shapely.prepare(g_)
    corr[["xmin", "ymin", "xmax", "ymax"]] = shapely.bounds(np.array(corr.geom.tolist()))
    P = pd.concat([P[~P.ponto_id.isin(corr.ponto_id)], corr[P.columns.intersection(corr.columns)]], ignore_index=True)
    print(f"poligonos corrigidos trocados: {sorted(corr.ponto_id)}", flush=True)
    print(f"{len(P)} poligonos Ultra pe_15", flush=True)
    linhas = []
    for uf, cxu in b.caixas_uf().items():
        sel = P[(P.xmax >= cxu[0]) & (P.xmin <= cxu[2]) & (P.ymax >= cxu[1]) & (P.ymin <= cxu[3])]
        if sel.empty:
            continue
        t1 = time.time()
        bb = (sel.xmin.min(), sel.ymin.min(), sel.xmax.max(), sel.ymax.max())
        c = pd.read_parquet(b.POI / f"cnpj_ativos_{uf}.parquet", columns=["matriz_filial", "data_inicio", "cnae_principal", "cep", "lat", "lng", "geo_nivel"])
        c = c[c.geo_nivel.ne("sem_coordenada")]
        cn, dv = c.cnae_principal.fillna(""), c.cnae_principal.fillna("").str[:2]
        est = c.data_inicio.fillna("99999999") < b.ESTOQUE
        fil = c.matriz_filial.eq("2")
        f1 = (dv.isin(b.F1_DIV) | cn.str.startswith("8610")) & ~cn.isin(b.F1_EXC)
        f1p = f1 & dv.ne("84") & ~cn.str.startswith("8610")
        flags = pd.DataFrame({"F1_fil": f1 & fil & est, "F1p_fil": f1p & fil & est})
        keep = flags.any(axis=1)
        c, flags = c[keep], flags[keep]
        exato = c.geo_nivel.eq("cep_numero").to_numpy()
        Fx = flags.to_numpy(np.float64)
        cb = b.em_caixa(c.assign(_i=np.arange(len(c))), bb)
        PT = b.Pontos(cb.lng.to_numpy(), cb.lat.to_numpy(), i=cb._i.to_numpy())
        cl = c.geo_nivel.isin(["cep", "cep_area"]).to_numpy()
        ccep = pd.DataFrame(Fx[cl], columns=FAM).assign(cep=c.cep.to_numpy()[cl]).groupby("cep").sum()
        ce_tot = pd.read_parquet(b.POI / f"cnefe_cep_{uf}.parquet", columns=["cep", "n"]).set_index("cep").n
        cnf = b.em_caixa(pd.read_parquet(b.POI / f"cnefe_cep_numero_{uf}.parquet", columns=["cep", "lat", "lng", "n"]), bb)
        cnf = cnf[cnf.cep.isin(ccep.index)]
        ceps = pd.Index(ccep.index)
        CN = b.Pontos(cnf.lng.to_numpy(), cnf.lat.to_numpy(), k=ceps.get_indexer(cnf.cep), n=cnf.n.to_numpy(float))
        tot = ce_tot.reindex(ceps).fillna(np.inf).to_numpy(float)
        C = ccep.to_numpy(float)
        for r in sel.itertuples():
            gi = PT.c["i"][PT.dentro(r)]
            ex = gi[exato[gi]]
            pt = Fx[ex].sum(0)
            jj = CN.dentro(r)
            rat = (np.bincount(CN.c["k"][jj], weights=CN.c["n"][jj], minlength=len(ceps)) / tot) @ C if len(jj) else np.zeros(len(FAM))
            linhas.append({"ponto_id": r.ponto_id, **{f: pt[k] + rat[k] for k, f in enumerate(FAM)}, **{f + "_exato": pt[k] for k, f in enumerate(FAM)}})
        del c, cb, cnf
        print(f"[{uf}] {len(sel)} poligonos | {time.time() - t1:.0f}s", flush=True)
    d = pd.DataFrame(linhas).groupby("ponto_id", as_index=False).sum()
    d.to_parquet(b.OUT / "f1_privado_ultra.parquet", index=False)
    ref = pd.read_parquet(UNI / "poi_painel" / "familias_por_poligono.parquet").query("origem == 'ultra_v2' and area == 'pe_15'").set_index("ponto_id").F1_fil
    cmp_ = d.set_index("ponto_id").F1_fil.reindex(ref.index)
    print(f"conferencia F1_fil x poi_painel (o que o painel le): {int(np.isclose(cmp_, ref, rtol=1e-9, atol=1e-6).sum())} de {len(ref)} iguais; "
          f"max |dif| {np.nanmax(np.abs(cmp_ - ref)):.6f}")
    print(f"F1p / F1 (mediana): {np.nanmedian(d.F1p_fil / d.F1_fil.replace(0, np.nan)):.3f} | {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
