# -*- coding: utf-8 -*-
"""BLK-UNI-10, item 4 (bateria/protocolo_bateria.md §7 + §9.9 + §15 + §17.3 + §18 + §19): visibilidade objetiva do ponto.
A30 = 1 se o pino da unidade fica a <= 30 m do eixo de uma via ARTERIAL do OSM (highway = primary, secondary ou trunk;
os *_link nao entram), 0 se nao. Vias: grafo do pipeline de isocronas, extraido para insumos_item4/ por item4_prep_vias.py
(so' unidades com >= 1 km de margem ate a borda das caixas do grafo, medida em graus). Teste primario no LABORATORIO SMART
FIT do item 2 (amostra_lab), direcao POSITIVA (§3), p primario = o MAIOR entre as quadriculas com G* >= 10 (§17.3). Tres
guardas de robustez (§18.4 + §19): sem a maior area, com filiais a <= 500 m e com shopping. Na Ultra: efeito descritivo e
c2/c3 (contam so' se o laboratorio passar). Turma de 2026 congelada sempre. Nao le dado sensivel.
Uso: item4_visibilidade.py --seco | --ensaio | (sem flag = teste; exige REGISTRO_CONGELAMENTO_item4.txt). .venv, PYTHONPATH=src."""
import importlib.util
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer
from scipy import stats
from sklearn.neighbors import BallTree

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
ROOT = UNI.parent.parent.parent
ISO = UNI.parent / "isocronas"
INS = AQUI / "insumos_item4"
GRAFO = Path(r"C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\9259d0a1-7dda-49bd-a390-c88f3d4ac1a6\scratchpad\iso\grafo")
MALLS = ROOT / "data" / "staging" / "poi" / "osm_malls_poligonos.parquet"
REG4 = AQUI / "REGISTRO_CONGELAMENTO_item4.txt"
ART = ("primary", "secondary", "trunk")
LINK = ("primary_link", "secondary_link", "trunk_link")
ESQ = ("primary", "secondary", "trunk", "tertiary", "unclassified", "residential", "living_street", "road")  # §19: sem service, motorway e *_link
R_PRINC, MARGEM, MARGEM_SENS = 30.0, 1000.0, 5000.0
R_SHOP, R_SHOP_POI = 50.0, 150.0         # §19: shopping = dentro do poligono ou a <= 50 m; 150 m (regra do POI) e' sensibilidade
CONCORDA = 50.0                          # §19: pino do site e do TotalPass concordam se a <= 50 m
D_TETO, D_PISO = 300.0, 10.0             # §19: o extrato tem vias so' ate 300 m; continua = log(300 / max(d, 10))
CORTE_LAB = "20250101"
ALFA_MAX_HOLM = 0.05 / 5                 # §18.4: com os p dos itens 1, 6, 2 e 5 (> 0,05), o item 4 fica no maximo no posto 2
DIRECAO = "unilateral, coef > 0"
TF = Transformer.from_crs(4326, 5880, always_xy=True)


def mod(nome, p):
    s = importlib.util.spec_from_file_location(nome, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


i5 = mod("i5", AQUI / "item5_faculdades.py")  # reaproveita it2 (laboratorio) e a leitura de filiais do item 5; nao roda o item 5
it2, op, tm, ex, X_, et, sha = i5.it2, i5.op, i5.tm, i5.ex, i5.X_, i5.et, i5.sha
INSUMOS4 = (i5.INSUMOS5 + [Path(__file__), AQUI / "item4_prep_vias.py", INS / "vias_entorno.parquet", INS / "cobertura.parquet",
                           INS / "grafo_sha.txt", INS / "meta.json", MALLS, ISO / "02_grafo.py", ISO / "multirede" / "metros_novos.json"]
            + sorted((ROOT / "data" / "osm_cache" / "pbf").glob("*.osm.pbf")) + sorted(GRAFO.glob("metro_*/*.parquet")))


# ------------------------------------------------------------------ medidas
def _seg_dist(px, py, V):
    """Distancia (m) de cada ponto ao segmento mais proximo de V (EPSG:5880), ate D_TETO; inf se nada."""
    if V.empty:
        return np.full(len(px), np.inf)
    L = shapely.linestrings(np.stack([V[["x0", "y0"]].to_numpy(), V[["x1", "y1"]].to_numpy()], axis=1))
    idx, dist = shapely.STRtree(L).query_nearest(shapely.points(px, py), max_distance=D_TETO, return_distance=True, all_matches=False)
    out = np.full(len(px), np.inf); out[idx[0]] = dist
    return out


def _esquinas(V):
    """No' de esquina: >= 3 segmentos de vias de quadra (ESQ: sem service, motorway e *_link) de >= 2 ways diferentes. O grafo
    nao e' simplificado (no' de grau 2 e' ponto de forma). Inclui abertura de canteiro entre pistas de avenida duplicada."""
    W = V[V.hw.isin(ESQ)]
    ends = pd.concat([pd.DataFrame({"n": W.u, "w": W.way_id, "x": W.x0, "y": W.y0}), pd.DataFrame({"n": W.v, "w": W.way_id, "x": W.x1, "y": W.y1})])
    g = ends.groupby("n").agg(k=("w", "size"), nw=("w", "nunique"), x=("x", "first"), y=("y", "first"))
    return g[(g.k >= 3) & (g.nw >= 2)][["x", "y"]].to_numpy()


def _shop(px, py, malls, r):
    mp = shapely.transform(shapely.from_wkb(malls.poligono_wkb.to_numpy()), lambda c: np.column_stack(TF.transform(c[:, 0], c[:, 1])))
    hit = shapely.STRtree(mp).query(shapely.points(px, py), predicate="dwithin", distance=r)[0]
    return np.isin(np.arange(len(px)), hit).astype(float)


def medir(pts, cortes, V, Fl, malls):
    """Por unidade (pino em lat/lng + data de decisao): distancia a arterial (e variantes), esquina, shopping e o controle de
    centralidade local (filiais a <= 500 m, como no item 5)."""
    px, py = TF.transform(pts.lng.to_numpy(), pts.lat.to_numpy())
    R = pd.DataFrame(index=pts.index)
    R["d_art"] = _seg_dist(px, py, V[V.hw.isin(ART)])
    R["d_art_link"] = _seg_dist(px, py, V[V.hw.isin(ART + LINK)])
    R["d_art_ter"] = _seg_dist(px, py, V[V.hw.isin(ART + ("tertiary",))])
    R["d_motorway"] = _seg_dist(px, py, V[V.hw.isin(("motorway",))])
    for r in (15, 30, 50, 100):
        R[f"A{r}"] = (R.d_art <= r).astype(float)
    R["A30_link"], R["A30_ter"] = (R.d_art_link <= 30).astype(float), (R.d_art_ter <= 30).astype(float)
    R["prox_art"] = np.log(D_TETO / np.clip(np.minimum(R.d_art, D_TETO), D_PISO, None))
    E = _esquinas(V)
    R["d_esquina"] = BallTree(E).query(np.column_stack([px, py]), k=1)[0][:, 0] if len(E) else np.inf
    R["esquina30"] = (R.d_esquina <= 30).astype(float)
    R["A30_esquina"] = ((R.A30 == 1) & (R.esquina30 == 1)).astype(float)
    R["em_shopping"] = _shop(px, py, malls, R_SHOP)
    R["em_shopping150"] = _shop(px, py, malls, R_SHOP_POI)
    ind, _ = i5._vizinhos(pts, Fl, 500); fdt = Fl.data_inicio.to_numpy()
    R["lf500"] = np.log1p([int((fdt[ii] < c).sum()) for ii, c in zip(ind, cortes)])
    return R


def pinos_tp():
    """Segunda fonte de pino da Smart Fit: a listagem do TotalPass, casada por nome + UF como no crosswalk do termometro."""
    k, _, _ = tm.painel()
    ult = k.sort_values("Data_Ref").groupby("Sigla").tail(1).set_index("Sigla")
    kk = ult.Nome.map(tm.norm) + "|" + ult.uf
    tp = pd.read_parquet(tm.TP)
    tp = tp[tp.nome.astype(str).map(lambda s: bool(re.match(r"^\s*smart\s*fit", tm.sem_acento(s))))].copy()
    tp["chave"] = tp.nome.map(tm.norm) + "|" + tp.uf
    tp = tp[~tp.chave.duplicated(keep=False)].set_index("chave")
    ok = kk.isin(tp.index) & ~kk.isin(set(kk[kk.duplicated(keep=False)]))
    return pd.DataFrame({"lat_tp": kk[ok].map(tp.lat).astype(float), "lng_tp": kk[ok].map(tp.lng).astype(float)})


def _hav_m(la1, lo1, la2, lo2):
    la1, lo1, la2, lo2 = map(np.radians, (la1, lo1, la2, lo2))
    a = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371008.8 * np.arcsin(np.sqrt(a))


# ------------------------------------------------------------------ inferencia (unilateral, coef > 0)
def lab4(S, cl, xq="A30", cols_extra=(), rng=None, boot=True):
    """y ~ x + l_renda_dom + l_pop + extra + FE de area (it2.preparar_lab chama a candidata de 'Qf'). op.wcr devolve
    (p coef > 0, p coef < 0, t, coef); a direcao do §3 e' positiva."""
    S, base, inc = it2.preparar_lab(S, xq, cols_extra)
    assert not inc and S.semQ.sum() == 0, "candidata com ausencia"
    Xm = X_(S, base + ["Qf"]); yv = S.y.to_numpy(float); j = Xm.shape[1] - 1
    op._posto(Xm, f"lab {xq} {cols_extra}")
    b, e, h, XtXi = ex.ols(yv, Xm); assert h.max() < 1 - 1e-9, "alavancagem 1 no laboratorio"
    g = op.regua(S[cl].astype(str)); G = len(np.unique(g))
    out = dict(coef=float(b[j]), n=len(S), G=G, Gst=float(np.nanmin([it2.g_estrela(Xm, j, g, 0.0), it2.g_estrela(Xm, j, g, 1.0)])),
               com=float(S[xq].mean()), areas=int(S.metro.nunique()))
    if boot:
        p_pos, p_neg, t, _ = op.wcr(yv, Xm, j, g, rng)
        out.update(p=float(p_pos), p_oposto=float(p_neg), t=float(t))
    Xb_ = X_(S, base); b0, e0, h0, _ = ex.ols(yv, Xb_); sst = np.sum((yv - yv.mean()) ** 2)
    out["r2loo0"], out["r2loo1"] = float(1 - np.sum((e0 / (1 - h0)) ** 2) / sst), float(1 - np.sum((e / (1 - h)) ** 2) / sst)
    return out


def pc(b):
    return 100 * (np.exp(b) - 1)


# ------------------------------------------------------------------ principal
def main():
    seco, ensaio = "--seco" in sys.argv, "--ensaio" in sys.argv
    out_dir = AQUI / "ensaio_item4" if ensaio else AQUI
    arq, res = out_dir / "previsoes_turma_2026_v2_V.csv", out_dir / "resultado_item4_visibilidade.md"
    if ensaio:
        out_dir.mkdir(exist_ok=True)
        for p in out_dir.iterdir():
            p.unlink()
    if not seco:
        assert not arq.exists() and not res.exists(), "congelamento/resultado do item 4 ja existem"
    if not seco and not ensaio:
        reg = REG4.read_text(encoding="utf-8") if REG4.exists() else ""
        for p in INSUMOS4:
            assert sha(p) in reg, f"TRAVA: {p} nao esta congelado (ou mudou) em {REG4.name}"
    assert sha(op.PV) == op.PV_SHA, "previsao congelada da turma mudou"
    meta = json.load(open(INS / "meta.json", encoding="utf-8"))
    assert D_TETO <= meta["raio_m"], "o teto da distancia passa do raio do extrato de vias"
    rng = np.random.default_rng(20261006)
    V = pd.read_parquet(INS / "vias_entorno.parquet")
    COB = pd.read_parquet(INS / "cobertura.parquet")
    malls = pd.read_parquet(MALLS, columns=["poligono_wkb"])
    _, Fl = i5.ler_cnpj()
    c = it2.ler_comodidades()
    f, d = ex.carregar()
    S, F = it2.amostra_lab(c, ensaio=ensaio)
    cl_ = COB[COB.origem == "lab"].set_index("chave")
    assert S.sigla.isin(cl_.index).all(), "unidade do laboratorio sem registro de cobertura (rodar item4_prep_vias.py)"
    assert np.allclose(S.lat.to_numpy(float), cl_.lat.reindex(S.sigla).to_numpy(float), atol=1e-9) and \
        np.allclose(S.lng.to_numpy(float), cl_.lng.reindex(S.sigla).to_numpy(float), atol=1e-9), "pino do laboratorio mudou desde o preparo"
    S["margem_m"] = S.sigla.map(cl_.margem_m)
    F["com >= 1 km de margem no grafo viario"] = int((S.margem_m >= MARGEM).sum())
    S = S[S.margem_m >= MARGEM].reset_index(drop=True)
    S = S.join(medir(S.set_index("sigla")[["lat", "lng"]], [CORTE_LAB] * len(S), V, Fl, malls), on="sigla")
    TPp = pinos_tp()
    S = S.join(TPp, on="sigla")
    S["d_pinos"] = _hav_m(S.lat, S.lng, S.lat_tp, S.lng_tp)
    S["pino_concorda"] = S.d_pinos <= CONCORDA
    # ---- Ultra (pinos corrigidos; data de decisao = 2025-01-01 no treino, inauguracao no teste e na turma)
    tr, te, DUM, cal, A, dummies = tm.bases(f, d)
    if ensaio:  # o desfecho da Ultra vira ruido ANTES de qualquer conta com ele
        rz = np.random.default_rng(2)
        for D in (tr, te):
            D["l_fat"] = np.where(D.l_fat.notna(), rz.normal(12.0, 0.3, len(D)), np.nan)
    pv = pd.read_csv(op.PV, sep=";", encoding="utf-8-sig", index_col=0)
    PU = it2.poligonos_ultra(list(tr.index) + list(te.index) + list(pv.index))
    ina = pd.to_datetime(d.inauguracao, errors="coerce")
    ph = d.flag_inauguracao_placeholder.fillna(False).astype(bool)
    corte = pd.Series(CORTE_LAB, index=tr.index)
    for idx in (te.index, pv.index):
        assert ina.reindex(idx).notna().all() and not ph.reindex(idx).any(), "inauguracao ausente ou placeholder no teste/turma"
        corte = pd.concat([corte, ina.reindex(idx).dt.strftime("%Y%m%d")])
    assert not corte.index.duplicated().any() and corte.index.isin(PU.index).all()
    cu = COB[COB.origem == "ultra"].set_index("chave").reindex(corte.index)
    assert (cu.margem_m >= MARGEM).all(), f"Ultra sem margem de 1 km no grafo: {list(cu[cu.margem_m < MARGEM].index)}"
    assert np.allclose(PU.loc[corte.index, "lat"].to_numpy(float), cu.lat.to_numpy(float), atol=1e-9), "pino da Ultra mudou desde o preparo"
    MU = medir(PU.loc[corte.index, ["lat", "lng"]], corte.to_numpy(), V, Fl, malls)
    conf = d.confianca_coord.reindex(corte.index)
    for D in (tr, te):
        for col in MU.columns:
            D[col] = MU[col].reindex(D.index).to_numpy(float)
        D["metro"] = d.iso_metro.reindex(D.index)
        D["cl_metro"] = D.metro.astype(str).where(D.metro.notna(), "u_" + D.index.astype(str))
        D["pino_alta"] = conf.reindex(D.index).eq("alta").to_numpy()
    V2 = ["l_m2", "l_renda_dom", "l_pop"] + DUM + ["studios"]
    if not ensaio:
        _, rt, _ = op.residuos_v2(tr, te, V2, "l_fat", cal["l_fat"])
        r2v2 = float(ex.r2_loo(tr.l_fat.to_numpy(float), *ex.ols(tr.l_fat.to_numpy(float), X_(tr, V2))[1:3]))
        assert abs(r2v2 - 0.264) <= 0.005 and abs(et(rt.to_numpy()) - 0.221) <= 0.003, (r2v2, et(rt.to_numpy()))
    # ---- desenho (sem a medida contra o desfecho): G* em todas as quadriculas, normais e deslocadas (regra do §17.3)
    DS = {f"{km}{suf}": it2.desenho(S, f"cel{km}{suf}", xq="A30") for km in it2.KMS for suf in ("", "s")}
    VALIDAS = [k for k in DS if DS[k]["Gst"] >= it2.G_MIN]
    ok_km = [km for km in it2.KMS if DS[str(km)]["Gst"] >= it2.G_MIN]
    cl0 = f"cel{max(ok_km)}" if ok_km else f"cel{min(it2.KMS)}"
    D0 = DS[cl0[3:]]
    Sd, base_d, _ = it2.preparar_lab(S, "A30")  # amostra que de fato roda (areas com < 2 unidades saem)
    cnt = Sd.metro.value_counts(); big = cnt.index[0]; share = cnt.iloc[0] / len(Sd)
    SU = pd.concat([tr, te])
    if seco:
        du = i5.desenho_ultra5(tr, te, V2, "A30")
        print("CHECAGEM SECA OK item 4 (sem ajuste da medida contra o desfecho).")
        print(f"  vias no entorno: {len(V):,} segmentos ({V.hw.isin(ART).sum():,} arteriais); meta do extrato: {meta}")
        print(f"  funil do laboratorio: {F}; no modelo (depois de tirar areas com < 2): n {len(Sd)}, areas {Sd.metro.nunique()}; maior area {big} ({100 * share:.0f}%)")
        print(f"  N por area (top 8): {cnt.head(8).to_dict()}")
        print("  G* com A30 (rho 0 / rho 1 / min, G): " + "; ".join(f"{k_} km: {v['Gst0']:.1f}/{v['Gst1']:.1f}/{v['Gst']:.1f} (G {v['G']}, n {v['n']})" for k_, v in DS.items()))
        print(f"  grades validas (G* >= 10): {VALIDAS}; referencia {cl0}; por area G* {D0['Gst_area']:.1f}")
        print("  lab, fracao COM: " + ", ".join(f"{k}: {Sd[k].mean():.1%}" for k in ("A15", "A30", "A50", "A100", "A30_link", "A30_ter", "esquina30", "A30_esquina", "em_shopping", "em_shopping150"))
              + f"; motorway a <= 30 m {np.mean(Sd.d_motorway <= 30):.1%}")
        h = pd.cut(np.minimum(Sd.d_art, 9999), [0, 5, 10, 20, 30, 50, 100, 300, 10000], right=True, include_lowest=True).value_counts().sort_index()
        print(f"  histograma de d_art (m): {h.to_dict()}")
        print(f"  pinos repetidos no lab: {int(Sd.duplicated(['lat', 'lng'], keep=False).sum())}; com <= 4 casas decimais: "
              f"{int(((Sd.lat * 1e4).round(6) % 1 == 0).sum())}")
        print(f"  shopping: A30 dentro (<= 50 m) {Sd.loc[Sd.em_shopping == 1, 'A30'].mean():.1%} (n {int(Sd.em_shopping.sum())}), fora {Sd.loc[Sd.em_shopping == 0, 'A30'].mean():.1%}; "
              f"faixa 50-150 m: n {int(((Sd.em_shopping150 == 1) & (Sd.em_shopping == 0)).sum())}, A30 {Sd.loc[(Sd.em_shopping150 == 1) & (Sd.em_shopping == 0), 'A30'].mean():.1%}")
        tpok = Sd.d_pinos.notna()
        print(f"  pino site x TotalPass: casadas {int(tpok.sum())} de {len(Sd)}; distancia mediana {Sd.d_pinos.median():.0f} m, p75 {Sd.d_pinos.quantile(.75):.0f} m; "
              f"<= 30 m {np.mean(Sd.d_pinos[tpok] <= 30):.0%}, <= 50 m {np.mean(Sd.d_pinos[tpok] <= 50):.0%}; concordantes (<= {CONCORDA:.0f} m) {int(Sd.pino_concorda.sum())}")
        perto = Sd[tpok & (Sd.d_pinos <= 250)]
        if len(perto):
            a_tp = (_seg_dist(*TF.transform(perto.lng_tp.to_numpy(), perto.lat_tp.to_numpy()), V[V.hw.isin(ART)]) <= 30).astype(float)
            print(f"  A30 pelo pino do TotalPass (casadas a <= 250 m, n {len(perto)}): {a_tp.mean():.1%} contra {perto.A30.mean():.1%} pelo site; concordancia {np.mean(a_tp == perto.A30.to_numpy()):.0%}")
        xv = Sd.A30.to_numpy(float)
        for rot, cols in (("FE + renda + pop", base_d), ("+ filiais a <= 500 m", base_d + ["lf500"]), ("+ em shopping", base_d + ["em_shopping"])):
            Xd = X_(Sd, cols); xr = xv - Xd @ np.linalg.lstsq(Xd, xv, rcond=None)[0]
            print(f"  R2 de A30 sobre {rot}: {1 - xr.var() / xv.var():.2f}")
        print(f"  corr(A30, .): renda dom {Sd.A30.corr(Sd.l_renda_dom):+.2f}; pop {Sd.A30.corr(Sd.l_pop):+.2f}; filiais {Sd.A30.corr(Sd.lf500):+.2f}; "
              f"esquina {Sd.A30.corr(Sd.esquina30):+.2f}; shopping {Sd.A30.corr(Sd.em_shopping):+.2f}; areas com e sem: {int(Sd.groupby('metro').A30.agg(lambda z: 0 < z.mean() < 1).sum())} de {Sd.metro.nunique()}")
        for nm, al in (("0,05", .05), ("a/6", op.LIMIAR)):
            print(f"  efeito detectavel no lab (80%, {nm}, unilateral): iid {pc(it2.mde(D0['se_iid'], D0['gl'], al)):+.1f}%; "
                  + "; ".join(f"cluster {k} (gl {DS[k]['Gst'] - 1:.0f}) {pc(it2.mde(DS[k]['se_cl'], max(DS[k]['Gst'] - 1, 1), al)):+.1f}%" for k in VALIDAS))
        dif = _hav_m(PU.lat.reindex(corte.index), PU.lng.reindex(corte.index), d.lat.reindex(corte.index), d.lng.reindex(corte.index))
        print(f"  Ultra: pino dos poligonos x pino atual do dim_unidade: max {np.nanmax(dif):.1f} m; > 1 m em {int((dif > 1).sum())} de {len(dif)} "
              f"({list(dif[dif > 1].round(0).to_dict().items())[:6]})")
        print(f"  Ultra com A30: treino {int(tr.A30.sum())}/39, teste {int(te.A30.sum())}/18, turma {int(MU.A30.reindex(pv.index).sum())}/16; "
              f"em shopping {int(SU.em_shopping.sum())}/57; esquina {int(SU.esquina30.sum())}/57")
        orig = d.origem_coord.reindex(SU.index).astype(str) if "origem_coord" in d.columns else conf.reindex(SU.index).astype(str)
        print("  Ultra, A30 por confianca: " + str(SU.assign(o=conf.reindex(SU.index).astype(str)).groupby("o").A30.agg(["mean", "size"]).round(2).to_dict("index")))
        print("  Ultra, A30 por origem do pino: " + str(SU.assign(o=orig).groupby("o").A30.agg(["mean", "size"]).round(2).to_dict("index")))
        print(f"  Ultra corr(A30, renda dom) {SU.A30.corr(SU.l_renda_dom):+.2f}, (m2) {SU.A30.corr(SU.l_m2):+.2f}, (estudios) {SU.A30.corr(SU.studios):+.2f}, (filiais) {SU.A30.corr(SU.lf500):+.2f}")
        print(f"  Ultra, detectavel (80%, 0,05): iid {pc(it2.mde(du['se_iid'], du['gl'], .05)):+.1f}% / cluster {pc(it2.mde(du['se_cl'], max(du['Gst'] - 1, 1), .05)):+.1f}% "
              f"(G* min por metro {du['Gst']:.1f}, G {du['G']})")
        return
    # ---------------- teste
    if not VALIDAS:
        P, PV_ = dict(pd=1.0, coef=np.nan, nota=f"G* < {it2.G_MIN} em todas as quadrículas: o laboratório não dá p (p = 1)"), {}
    else:
        PV_ = {k: lab4(S, f"cel{k}", rng=rng) for k in VALIDAS}
        kmax = max(PV_, key=lambda k: PV_[k]["p"])
        P = dict(PV_[cl0[3:]] if cl0[3:] in PV_ else PV_[kmax]); P["pd"] = PV_[kmax]["p"]
        P["p_oposto_max"] = max(r["p_oposto"] for r in PV_.values())
        P["nota"] = f"p primário = o maior entre as quadrículas com G* ≥ 10 ({', '.join(VALIDAS)} km; 's' = deslocada), que é o da {kmax} km (§17.3)"
    sem_big = lab4(S[S.metro != big], cl0, rng=rng)
    com_fil = lab4(S, cl0, cols_extra=("lf500",), rng=rng)
    com_shop = lab4(S, cl0, cols_extra=("em_shopping",), rng=rng)
    rob = lambda r: np.isfinite(P.get("coef", np.nan)) and np.sign(r["coef"]) == np.sign(P["coef"]) and abs(r["coef"]) >= 0.5 * abs(P["coef"])
    pp = P["pd"]
    if not VALIDAS:
        c1 = "não testável (G* < 10); entra no Holm com p = 1"
    elif pp <= op.LIMIAR:
        c1 = "significativo"
    elif pp <= ALFA_MAX_HOLM:
        c1 = "pendente (Holm no fechamento)"
    elif pp <= 0.05:
        c1 = "não significativo após Holm (com os itens 1, 6, 2 e 5, o limiar máximo do item 4 é α/5 = 0,010)"
    else:
        c1 = "não significativo"
    vivo = c1 in ("significativo", "pendente (Holm no fechamento)")
    if vivo and not rob(sem_big):
        c1 = "frágil à dependência espacial (não resiste sem a maior área); entra no Holm com p = 1"
    elif vivo and not rob(com_fil):
        c1 = "confundido com CENTRALIDADE local (não resiste ao controle de filiais a ≤ 500 m); entra no Holm com p = 1"
    elif vivo and not rob(com_shop):
        c1 = "confundido com SHOPPING (não resiste ao controle de unidade em shopping); entra no Holm com p = 1"
    lab_passa = c1 == "significativo" or c1.startswith("pendente")
    L = ["# BLK-UNI-10, item 4 — visibilidade objetiva do ponto (protocolo da bateria §7 + §9.9 + §17.3 + §18 + §19, congelado antes de rodar)", "",
         "A30 = 1 se o pino da unidade fica a até 30 m do eixo de uma via arterial do OSM (primária, secundária ou expressa trunk; "
         "acessos *_link não entram). OpenStreetMap de set/2026, grafo do pipeline de isócronas.", "",
         f"## Laboratório Smart Fit (teste primário; {DIRECAO})", "",
         f"- Funil: {F}.",
         f"- No modelo: n = {len(Sd)} em {Sd.metro.nunique()} áreas ({int(Sd.dentro_metro.sum())} unidades em metrô, {int((~Sd.dentro_metro).sum())} em município); "
         f"isócrona real {int((Sd.geom_tipo == 'isocrona').sum())}, círculo {int((Sd.geom_tipo == 'circulo').sum())}. Maior área com {100 * share:.0f}% do N.",
         f"- De frente para arterial (≤ 30 m): {Sd.A30.mean():.0%} das unidades ({int(Sd.A30.sum())} de {len(Sd)}); em shopping (≤ 50 m do polígono) {int(Sd.em_shopping.sum())}.",
         "- G* (mínimo entre ρ 0 e ρ 1): " + "; ".join(f"{k_} km {v['Gst']:.1f}" for k_, v in DS.items()) + f". {P['nota']}."]
    if np.isfinite(P.get("coef", np.nan)):
        L += [f"- Coeficiente de A30: **{P['coef']:+.3f}** → **{pc(P['coef']):+.1f}% de alunos** de frente para arterial, contra não; n = {P['n']}.",
              f"- **p de decisão ({DIRECAO}; wild cluster bootstrap restrito, Webb, B = {it2.B_BOOT}): {pp:.4f}.** Por quadrícula: "
              + "; ".join(f"{k} km p(coef > 0) {r['p']:.4f}, p(coef < 0) {r['p_oposto']:.4f}" for k, r in PV_.items())
              + f". R² LOO com efeito fixo: {P['r2loo0']:.3f} → {P['r2loo1']:.3f}.",
              f"- Robustez (§18.4 + §19): sem a maior área {sem_big['coef']:+.3f} ({'resiste' if rob(sem_big) else 'NÃO resiste'}); com log(1 + filiais "
              f"a ≤ 500 m) {com_fil['coef']:+.3f} ({'resiste' if rob(com_fil) else 'NÃO resiste'}); com o controle de shopping {com_shop['coef']:+.3f} "
              f"({'resiste' if rob(com_shop) else 'NÃO resiste'}). O controle de shopping tende a subir o coeficiente por construção (§19), "
              "então resistir a ele não é corroboração."]
    L += [f"- c1: **{c1}**.", "", f"## Sensibilidades do laboratório (descritivas; p da grade de {cl0[3:]} km, NÃO comparável ao p de decisão)", "",
          "| versão | n | com | coef. | efeito | p (coef > 0) | p (coef < 0) | G* |", "|---|---|---|---|---|---|---|---|"]

    def sl(rot, r, efeito=True):
        ef = f"{pc(r['coef']):+.1f}%" if efeito else "—"
        com = f"{100 * r['com']:.0f}%" if efeito else "—"
        L.append(f"| {rot} | {r['n']} | {com} | {r['coef']:+.3f} | {ef} | {r['p']:.4f} | {r['p_oposto']:.4f} | {r['Gst']:.1f} |")
    sl(f"sem a maior área ({big}) — obrigatória", sem_big)
    sl("controle: log(1 + filiais de CNPJ a ≤ 500 m) — obrigatória", com_fil)
    sl("controle: em shopping (≤ 50 m do polígono) — obrigatória", com_shop)
    sl(f"sem as unidades em shopping ({int(S.em_shopping.sum())})", lab4(S[S.em_shopping == 0], cl0, rng=rng))
    sl("controle: shopping a ≤ 150 m (regra do POI)", lab4(S, cl0, cols_extra=("em_shopping150",), rng=rng))
    sl(f"só pinos concordantes (site × TotalPass ≤ {CONCORDA:.0f} m; {int(S.pino_concorda.sum())})", lab4(S[S.pino_concorda], cl0, rng=rng))
    sl("a ≤ 15 m", lab4(S, cl0, xq="A15", rng=rng))
    sl("a ≤ 50 m", lab4(S, cl0, xq="A50", rng=rng))
    sl("a ≤ 100 m", lab4(S, cl0, xq="A100", rng=rng))
    sl("distância contínua: log(300 m / distância), piso 10 m (por +1)", lab4(S, cl0, xq="prox_art", rng=rng), efeito=False)
    sl("com os acessos (*_link)", lab4(S, cl0, xq="A30_link", rng=rng))
    sl("com as terciárias", lab4(S, cl0, xq="A30_ter", rng=rng))
    sl("esquina (≥ 3 segmentos de via de quadra de ≥ 2 vias, a ≤ 30 m)", lab4(S, cl0, xq="esquina30", rng=rng))
    sl("arterial E esquina", lab4(S, cl0, xq="A30_esquina", rng=rng))
    sl(f"margem ≥ 5 km no grafo viário ({int((S.margem_m >= MARGEM_SENS).sum())})", lab4(S[S.margem_m >= MARGEM_SENS], cl0, rng=rng))
    for k_ in DS:
        if k_ not in PV_ and f"cel{k_}" != cl0:
            sl(f"cluster = quadrícula de {k_[:-1] + ' km deslocada' if k_.endswith('s') else k_ + ' km'} (G* < 10)", lab4(S, f"cel{k_}", rng=rng))
    sl("cluster = área (metrô ou município)", lab4(S, "metro", rng=rng))
    sl("só isócronas reais (sem círculos)", lab4(S[S.geom_tipo == "isocrona"], cl0, rng=rng))
    sl("só dentro das áreas metropolitanas", lab4(S[S.dentro_metro], cl0, rng=rng))
    Sx = S.assign(idade_12_23=((S.idade_m >= 12) & (S.idade_m <= 23)).astype(float))
    sl("controles de idade (12–23 meses) e franquia", lab4(Sx, cl0, cols_extra=("idade_12_23", "franquia"), rng=rng))
    if np.isfinite(P.get("coef", np.nan)):
        lomo = {m: lab4(S[S.metro != m], cl0, rng=rng, boot=False)["coef"] for m in cnt.index[cnt >= 20]}
        L += ["", "Tirando uma área com ≥ 20 unidades por vez (coeficiente): " + ", ".join(f"sem {m}: {v:+.3f}" for m, v in lomo.items())
              + f". Mesmo sinal em {sum(np.sign(v) == np.sign(P['coef']) for v in lomo.values())} de {len(lomo)}.", ""]
    # ---------------- Ultra
    Ue = op.empilhado(tr, te, V2, "A30", "l_fat", rng, cl="cl_metro")
    Ua = op.empilhado(tr[tr.pino_alta], te[te.pino_alta], V2, "A30", "l_fat", rng, cl="cl_metro")
    trq, teq = tr.assign(Q=-tr.d_art.clip(upper=D_TETO)), te.assign(Q=-te.d_art.clip(upper=D_TETO))  # it2.c2c3 corta pela coluna Q: acima da mediana = mais perto da arterial
    Mx = it2.c2c3(trq, teq, V2, ["A30"], "l_fat", cal["l_fat"], rng)
    c2, c3, c3r = Mx["dl"] >= 0.02, Mx["dt"] >= 0.02, Mx["dt_rec"] >= 0.02
    coerente = np.isfinite(P.get("coef", np.nan)) and np.sign(Mx["coef"]) == np.sign(P["coef"])
    alvo = ("MELHORA A PRECISÃO" if (c2 and c3 and c3r and coerente) else
            ("CANDIDATA (o c3 só passa por nível)" if (c2 and c3 and coerente) else ("CANDIDATA" if (Mx["dl"] >= 0 and coerente) else "NÃO MELHORA")))
    if c1 == "significativo":
        v = alvo
    elif c1.startswith("pendente"):
        v = "PENDENTE DO HOLM — se c1 passar: " + alvo.lower()
    elif c1.startswith("frágil") or c1.startswith("confundido"):
        v = c1.split(";")[0].upper()
    elif c1.startswith("não testável"):
        v = "NÃO TESTÁVEL no laboratório (G* < 10; entra no Holm com p = 1)"
    elif c1.startswith("não significativo após Holm"):
        v = f"NÃO DEMONSTRADO após Holm (p {pp:.4f} > 0,010)"
    else:
        v = "NÃO DEMONSTRADO no laboratório (não vai à Ultra)" + (" — efeito na direção OPOSTA (descritivo; vale em todas as grades)" if P.get("p_oposto_max", 1) <= 0.05 else "")
    L += ["## Ultra (57 unidades, pinos corrigidos)", "",
          f"- De frente para arterial (≤ 30 m): treino {int(tr.A30.sum())} de 39, teste {int(te.A30.sum())} de 18; em shopping {int(SU.em_shopping.sum())}.",
          f"- Efeito de A30 (empilhado, cluster por metrô; descritivo): {Ue['coef']:+.3f} → {pc(Ue['coef']):+.1f}% de faturamento; p (coef > 0) {Ue['p']:.4f}, "
          f"p (coef < 0) {Ue['p_neg']:.4f}; HC3 IC 90% {pc(Ue['lo']):+.1f}% a {pc(Ue['hi']):+.1f}%.",
          f"- Só pinos de confiança alta ({int(SU.pino_alta.sum())} de 57): {Ua['coef']:+.3f} → {pc(Ua['coef']):+.1f}%; p (coef > 0) {Ua['p']:.4f}.",
          f"- c2/c3 (v2 contra v2 + A30; {'CONTAM' if lab_passa else 'só relatados, o laboratório não passou'}): coeficiente nas 39 {Mx['coef']:+.3f} "
          f"(IC 90% {Mx['lo']:+.3f} a {Mx['hi']:+.3f}){'' if coerente else ' — sinal diferente do laboratório'}; estúdios {Mx['studios0']:+.3f} → {Mx['studios1']:+.3f}.",
          f"  LOO {100 * Mx['e_l0']:.1f}% → {100 * Mx['e_l1']:.1f}% (queda {100 * Mx['dl']:+.1f} pp; IC 90% {100 * Mx['ic_dl'][0]:+.1f} a {100 * Mx['ic_dl'][1]:+.1f}); "
          f"teste {100 * Mx['e_t0']:.1f}% → {100 * Mx['e_t1']:.1f}% (queda {100 * Mx['dt']:+.1f} pp; IC 90% {100 * Mx['ic_dt'][0]:+.1f} a {100 * Mx['ic_dt'][1]:+.1f}; "
          f"{Mx['k18']} de {Mx['n_te']} melhoram; recentrado {100 * Mx['dt_rec']:+.1f} pp); viés {100 * Mx['vies0']:+.1f}% → {100 * Mx['vies1']:+.1f}%; "
          f"deslocamento {100 * Mx['desloc']:+.1f}%; queda nas mais perto de arterial {100 * Mx['dt_alto']:+.1f} pp, nas mais longe {100 * Mx['dt_baixo']:+.1f} pp.", "",
          f"**Veredito do item 4: {v}.**", ""]
    # ---------------- turma 2026 (congela sempre)
    est = pd.read_csv(op.MET, sep=";", encoding="utf-8-sig", index_col=0).metragem_estimada_m2.dropna()
    of = d.tam_metragem_m2.dropna(); m2 = pd.concat([of, est[~est.index.isin(of.index)]])
    cand = A.reindex(pv.index).drop(columns=["l_m2"]).join(np.log(m2).rename("l_m2"))
    cand["master_id"] = pv.master_id
    cand = dummies(cand)
    cand["A30"] = MU.A30.reindex(cand.index)
    me = float(SU.A30.mean()); g = Ue["coef"]
    out = pd.DataFrame(index=pv.index)
    out["dist_arterial_m"] = MU.d_art.reindex(pv.index).clip(upper=D_TETO).round(0)  # 300 = "300 m ou mais"
    out["A30"] = cand.A30
    out["em_shopping"] = MU.em_shopping.reindex(pv.index)
    out["pino_confianca"] = conf.reindex(pv.index)
    out["prev_v2dom_cal2026"] = pv.prev_v2dom_cal2026
    out["prev_v2dom_x_V"] = (pv.prev_v2dom_cal2026 * np.exp(g * (cand.A30 - me))).round(0)
    out["prev_v2dom_mesmo_nivel"] = (pv.prev_v2dom_cal2026 * np.exp(g * (cand.A30.mean() - me))).round(0)
    okm = cand[V2 + ["A30"]].notna().all(axis=1)
    p_c = pd.Series(np.nan, index=cand.index); p_c[okm] = np.exp(X_(cand[okm], V2 + ["A30"]) @ Mx["b1"] + cal["l_fat"])
    out["prev_v2_V_39_cal2026"] = p_c.round(0)
    out.to_csv(arq, sep=";", encoding="utf-8-sig")
    h = sha(arq)
    with (out_dir / REG4.name).open("a", encoding="utf-8") as fh:
        fh.write(f"Turma 2026 congelada pelo item 4 em {datetime.now():%Y-%m-%d %H:%M} (gamma A30 Ultra {g:+.4f}; media A30 {me:.4f}; "
                 f"lab: coef {P.get('coef', np.nan):+.4f}, p de decisao {pp:.4f}, grades {VALIDAS}, {DIRECAO}): {h} *{arq.name}\n")
    L += ["## Turma de 2026 congelada", "", f"`{arq.name}`: {len(out)} unidades, {int(out.A30.sum())} de frente para arterial; γ̂ (Ultra) = {g:+.3f}. SHA-256 `{h}`.",
          "Conferência (§19): junto com o BLK-UNI-12, quando ≥ 10 das 16 tiverem 12 meses de vida e ≥ 3 meses válidos. Métrica: a diferença "
          "média do resíduo da v2 congelada entre quem está e quem não está de frente para arterial (5 contra 11; EP ≈ 0,16, detectável de "
          "~+50%: confere quase só o nível), comparada a γ̂, também sem o pino de confiança baixa; a `prev_v2dom_x_V` só conta se o erro "
          "típico dela vencer o da `prev_v2dom_mesmo_nivel`.", ""]
    res.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
