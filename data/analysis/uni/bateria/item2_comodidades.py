# -*- coding: utf-8 -*-
"""BLK-UNI-10, item 2 (bateria/protocolo_bateria.md §9.9 + §13 + §14 + §15): qualidade da concorrencia ao redor.
Q = fracao das academias listadas no Wellhub (planilha de comodidades do Juan, 29/09/2026) dentro da isocrona de 10 min de
carro (ou circulo de raio equivalente) que declaram vestiario, chuveiro e armario, entre as que declararam comodidades;
sem a propria rede. Teste primario no LABORATORIO SMART FIT (log alunos 2025 ~ Q + log renda domiciliar + log pop + efeito
fixo de area; wild cluster bootstrap restrito por quadricula dentro da area; direcao NEGATIVA). Na Ultra: efeito principal e
interacao m2 x Q (hipotese do diretor), descritivos, e c2/c3 (contam so' se o laboratorio passar). Nao le dado sensivel.
Uso: item2_comodidades.py --seco | --ensaio | (sem flag = teste; exige REGISTRO_CONGELAMENTO_item2.txt). .venv, PYTHONPATH=src."""
import hashlib
import importlib.util
import json
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import shapely
from scipy import stats

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
ROOT = UNI.parent.parent.parent
ISO = UNI.parent / "isocronas"           # copia permanente do pipeline de isocronas v2
POL, ATR = ISO / "poligonos_v2", ISO / "atributos_v2"
CSV = UNI / "insumos_locais" / "comodidades_concorrentes_2026-10-01.csv"
CSV_SHA = "07abe5684bf86f93db1988bb6fbe845e5623da73032a3e303c6adc094ccf4bd1"
REG2 = AQUI / "REGISTRO_CONGELAMENTO_item2.txt"
PROT = AQUI / "protocolo_bateria.md"
B_BOOT = 9_999
KMS = (10, 15, 20, 30)
G_MIN = 10


def mod(nome, p):
    s = importlib.util.spec_from_file_location(nome, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


op = mod("op", UNI / "LOCAL_bateria_operador" / "01_operador.py")  # so' funcoes (nao le a Base Consolidada aqui)
aj = mod("aj", UNI / "_ajustes.py")
tm, ex, X_, ajustar, et = op.tm, op.ex, op.X_, op.ajustar, op.et
INSUMOS2 = ([p for p in op.INSUMOS if p != op.BASE] + [Path(__file__), CSV, UNI / "_ajustes.py", ISO / "academias_pontos.parquet", ISO / "metros.json",
            ISO / "04_atributos.py", UNI / "correcoes_pinos" / "poligonos_corrigidos.parquet", UNI / "correcoes_pinos" / "ultra_pontos_corrigidos.parquet",
            ROOT / "data" / "staging" / "brasil_estrutural.parquet", ROOT / "data" / "validacao" / "KPIs_Smart_2025_02 (1).xlsx",
            UNI / "insumos_vps" / "concorrentes_mapeados_2026-09-27.parquet", UNI / "insumos_vps" / "planos_totalpass.parquet"]
            + sorted(POL.glob("metro_*.parquet")) + sorted(ATR.glob("*.parquet")))


def nz(s):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()).strip()


# ------------------------------------------------------------------ comodidades
def ler_comodidades():
    assert sha(CSV) == CSV_SHA, "planilha de comodidades mudou"
    c = pd.read_csv(CSV, sep=None, engine="python", encoding="utf-8-sig")
    c = c[c.latitude.notna() & c.longitude.notna()].copy()
    c["nm"] = c.nome.map(nz)
    c["is_sf"] = c.marca.astype(str).eq("smart_fit") | c.nm.str.startswith("smart fit")
    c["is_ultra"] = c.marca.astype(str).str.contains("ultra", case=False) | c.nm.str.contains(r"\bultra academia\b")
    c["declarou"] = c.declarou_comodidades.astype(str).str.lower().eq("sim")
    c["completa"] = c.vestiario.eq("sim") & c.chuveiro.eq("sim") & c.armario.eq("sim")
    return c


def poligonos_academia(ids):
    t = pd.concat([pd.read_parquet(f, columns=["ponto_id", "tipo", "metro", "modo", "limite_s", "lat", "lng", "poligono_wkb"]) for f in sorted(POL.glob("metro_*.parquet"))])
    t = t[t.tipo.eq("academia") & t.modo.eq("carro") & t.limite_s.eq(600) & t.ponto_id.isin(set(ids))].drop_duplicates("ponto_id").set_index("ponto_id")
    t["geom"] = shapely.from_wkb(t.poligono_wkb)
    return t.drop(columns=["poligono_wkb"])


def poligonos_ultra(ids):
    t = aj.poligonos_ultra(["ponto_id", "tipo", "metro", "modo", "limite_s", "lat", "lng", "poligono_wkb"])  # pinos corrigidos (28/09)
    t = t[t.modo.eq("carro") & t.limite_s.eq(600) & t.ponto_id.isin(set(ids))].drop_duplicates("ponto_id").set_index("ponto_id")
    t["geom"] = shapely.from_wkb(t.poligono_wkb)
    return t.drop(columns=["poligono_wkb"])


def medir_q(P, c, rede):
    """Q por geometria. `rede` = 'is_sf' (laboratorio) ou 'is_ultra' (Ultra); a propria rede sai de tudo (a propria academia
    esta contida na propria rede)."""
    wh = c[c.fonte.eq("wellhub") & ~c[rede]].reset_index(drop=True)
    whr = c[c.fonte.eq("wellhub") & c[rede]].reset_index(drop=True)
    tp = c[c.fonte.eq("totalpass") & ~c[rede]].reset_index(drop=True)
    st = c[c.fonte.eq("site") & c[rede]].reset_index(drop=True)
    arv = lambda D: shapely.STRtree(shapely.points(D.longitude.to_numpy(), D.latitude.to_numpy())) if len(D) else None
    tw, twr, tt, ts = arv(wh), arv(whr), arv(tp), arv(st)
    n_in = lambda tree, g: len(tree.query(g, predicate="contains")) if tree is not None else 0
    R = []
    for pid, g in P.geom.items():
        W = wh.iloc[tw.query(g, predicate="contains")]; dec = W[W.declarou]
        ntp = n_in(tt, g)
        R.append(dict(ponto_id=pid, n_wh=len(W), n_dec=len(dec), Q=float(dec.completa.mean()) if len(dec) else np.nan,
                      n_rede=n_in(twr, g), n_tp=ntp, tp_share=ntp / (ntp + len(W)) if (ntp + len(W)) else np.nan, n_rede_site=n_in(ts, g)))
    return pd.DataFrame(R).set_index("ponto_id")


# ------------------------------------------------------------------ amostra do laboratorio (§14)
def setores_para_circulos(circ):
    """Uma passada pela malha de setores (GEO): so' os setores cujo bbox cruza o bbox de algum circulo."""
    import geopandas as gpd
    import pyarrow.parquet as pq
    from shapely import wkb as _wkb
    i04 = mod("i04", ISO / "04_atributos.py")
    bx = np.array([g.bounds for g in circ])
    cols = ["cod_setor", "geometry_wkb", "pop_total_setor_2022", "domicilios_particulares_ocupados_setor_2022",
            "renda_per_capita_setor_2022_calibrada", "renda_per_capita_setor_2022", "flag_geometria_valida", "bbox_minx", "bbox_miny", "bbox_maxx", "bbox_maxy"]
    frames = []
    for ufdir in i04.GEO.glob("uf=*"):
        for mdir in ufdir.glob("cod_municipio=*"):
            f = next(mdir.glob("*.parquet"), None)
            if f is None:
                continue
            pf = pq.ParquetFile(f)
            bb = pf.read(columns=["bbox_minx", "bbox_miny", "bbox_maxx", "bbox_maxy"]).to_pandas()
            if bb.empty:
                continue
            fx0, fy0, fx1, fy1 = bb.bbox_minx.min(), bb.bbox_miny.min(), bb.bbox_maxx.max(), bb.bbox_maxy.max()
            if not ((bx[:, 2] >= fx0) & (bx[:, 0] <= fx1) & (bx[:, 3] >= fy0) & (bx[:, 1] <= fy1)).any():
                continue
            df = pf.read(columns=[c_ for c_ in cols if c_ in pf.schema_arrow.names]).to_pandas()
            if "flag_geometria_valida" not in df:
                df["flag_geometria_valida"] = True
            m = np.zeros(len(df), bool)
            for x0, y0, x1, y1 in bx:
                m |= (df.bbox_maxx.to_numpy() >= x0) & (df.bbox_minx.to_numpy() <= x1) & (df.bbox_maxy.to_numpy() >= y0) & (df.bbox_miny.to_numpy() <= y1)
            frames.append(df[m])
    s = pd.concat(frames, ignore_index=True)
    s = s[s["flag_geometria_valida"].fillna(True)]
    g = gpd.GeoDataFrame(s.drop(columns=["geometry_wkb"]), geometry=[_wkb.loads(x) for x in s["geometry_wkb"]], crs=4674).to_crs(5880)
    g["renda"] = g["renda_per_capita_setor_2022_calibrada"].fillna(g["renda_per_capita_setor_2022"])
    g["area"] = g.geometry.area
    g["rp"] = g.geometry.representative_point()
    return i04, g.reset_index(drop=True)


def amostra_lab(c, ensaio=False):
    """Painel KPI inteiro -> nivel 2025 -> coordenada (crosswalk do termometro) -> isocrona v2 real nao truncada (Smart Fit a
    <= 150 m) ou circulo de raio equivalente -> area (caixa de metro ou municipio) com >= 2 unidades."""
    import h3
    import shapely.ops as shp_ops
    from pyproj import Transformer
    from sklearn.neighbors import BallTree
    k, first, ini = tm.painel()
    g25 = k[(k.Data_Ref >= "2025-01-01") & (k.Data_Ref <= "2025-12-31") & (k.idade >= 12) & (k["Alunos Totais SF"] > 0)]
    s = g25.groupby("Sigla")["Alunos Totais SF"].agg(["median", "count"]); alunos = s.loc[s["count"] >= 6, "median"].astype(float)
    F = {"painel KPI (Siglas)": int(k.Sigla.nunique()), "nivel 2025 (idade >= 12 m, >= 6 meses)": len(alunos)}
    X, _, info = tm.crosswalk(k)
    S = pd.DataFrame({"alunos": alunos}).join(X, how="inner"); F["com coordenada (crosswalk nome + UF)"] = len(S)
    fs = pd.Series(S.index, index=S.index).map(first)
    S["idade_m"] = np.where(fs <= ini, 999, ((pd.Timestamp("2025-07-01") - fs).dt.days / 30.44).astype(int))
    S["franquia"] = (pd.Series(S.index, index=S.index).map(k.groupby("Sigla").Propriedade.agg(lambda v: v.mode().iat[0])) == "Franquia").astype(float)
    ap = pd.read_parquet(ISO / "academias_pontos.parquet"); sf_ids = set(ap[ap.rede.eq("smart_fit")].id.astype(str))
    P = poligonos_academia(sf_ids)
    at = pd.concat([pd.read_parquet(f, columns=["ponto_id", "tipo", "cenario", "pop", "domicilios", "renda_pc", "truncada", "area_km2"]) for f in sorted(ATR.glob("*.parquet"))])
    at = at[at.tipo.eq("academia") & at.cenario.eq("carro_10min")].drop_duplicates("ponto_id").set_index("ponto_id")
    bt = BallTree(np.radians(P[["lat", "lng"]].to_numpy()), metric="haversine")
    dd, ii = bt.query(np.radians(S[["lat", "lng"]].to_numpy()), k=1)
    S["pid"] = np.where(dd[:, 0] * 6371008.8 <= 150, P.index.to_numpy()[ii[:, 0]], None)
    dup = S.pid.notna() & S.pid.duplicated(keep=False)
    F["isocrona compartilhada por 2 Siglas (vira circulo)"] = int(dup.sum()); S.loc[dup, "pid"] = None
    a = at.reindex(S.pid)
    S["truncada"] = a.truncada.to_numpy()
    real = (S.pid.notna() & (S.truncada == False)).to_numpy()  # noqa: E712
    S["geom_tipo"] = np.where(real, "isocrona", "circulo")
    R_CIRC = float(np.sqrt(at.area_km2.reindex(S.loc[real, "pid"]) * 1e6 / np.pi).median())  # raio equivalente = sqrt(area/pi)
    F["isocrona real nao truncada"] = int(real.sum()); F["circulo (sem isocrona, truncada ou compartilhada)"] = int((~real).sum())
    F["raio do circulo (m)"] = round(R_CIRC)
    tf, tb = Transformer.from_crs(4326, 5880, always_xy=True), Transformer.from_crs(5880, 4326, always_xy=True)
    x, y_ = tf.transform(S.lng.to_numpy(), S.lat.to_numpy())
    S["geom"] = [P.geom[pid] if ok else shp_ops.transform(lambda X1, Y1: tb.transform(X1, Y1), shapely.Point(x[i], y_[i]).buffer(R_CIRC, 64))
                 for i, (pid, ok) in enumerate(zip(S.pid, real))]
    S["pop"], S["dom"], S["renda_pc"] = a["pop"].to_numpy(float), a.domicilios.to_numpy(float), a.renda_pc.to_numpy(float)
    i04, gset = setores_para_circulos(S.geom[~real].tolist())
    vazio = pd.DataFrame({"lat": [], "lng": [], "tipo": []})
    ctx = i04.Contexto(gset, vazio, vazio)
    for i in np.nonzero(~real)[0]:
        r = i04.atributos_poligono(shapely.Point(x[i], y_[i]).buffer(R_CIRC, 64), ctx, (x[i], y_[i]))
        S.iloc[i, S.columns.get_loc("pop")] = r["pop"]; S.iloc[i, S.columns.get_loc("dom")] = r["domicilios"]; S.iloc[i, S.columns.get_loc("renda_pc")] = r["renda_pc"]
    S = S[(S["pop"] > 0) & (S.dom > 0) & (S.renda_pc > 0)]; F["com pop/domicilios/renda"] = len(S)
    M = json.load(open(ISO / "metros.json", encoding="utf-8"))

    def caixa(la, lo):
        for m in M:
            if m["lat_min"] <= la <= m["lat_max"] and m["lng_min"] <= lo <= m["lng_max"]:
                return f"metro_{m['id']}"
        return None
    hx = pd.read_parquet(ROOT / "data" / "staging" / "brasil_estrutural.parquet", columns=["hex_id", "cod_municipio"]).drop_duplicates("hex_id").set_index("hex_id").cod_municipio
    S["metro"] = [caixa(a_, b_) or f"mun_{hx.get(h3.latlng_to_cell(a_, b_, 7), 'nd')}" for a_, b_ in zip(S.lat, S.lng)]
    assert not S.metro.eq("mun_nd").any(), "unidade fora de metro sem municipio"
    S["dentro_metro"] = S.metro.str.startswith("metro_")
    cnt = S.metro.value_counts(); S = S[S.metro.isin(cnt[cnt >= 2].index)]; F["em area (metro ou municipio) com >= 2"] = len(S)
    S = S.join(medir_q(pd.DataFrame({"geom": S.geom}, index=S.index), c, "is_sf"))
    S["l_renda_dom"] = np.log(S.renda_pc * S["pop"] / S.dom); S["l_pop"] = np.log(S["pop"]); S["l_nwh"] = np.log1p(S.n_wh)
    x, y_ = tf.transform(S.lng.to_numpy(), S.lat.to_numpy())
    for km in KMS:
        for suf, d0 in (("", 0.0), ("s", 0.5)):  # "s" = grade deslocada em meia celula
            S[f"cel{km}{suf}"] = (S.metro.astype(str) + "_" + pd.Series(np.floor(x / (km * 1000) + d0).astype(int), index=S.index).astype(str) + "_"
                                  + pd.Series(np.floor(y_ / (km * 1000) + d0).astype(int), index=S.index).astype(str))
    S["y"] = np.log(S.alunos)
    if ensaio:
        S["y"] = np.random.default_rng(1).normal(8.0, 0.3, len(S))
    return S.drop(columns=["geom"]).reset_index().rename(columns={"index": "sigla", "Sigla": "sigla"}), F


# ------------------------------------------------------------------ inferencia do laboratorio
def g_estrela(X, j, g, rho):
    """G* de Carter-Schnepel-Steigerwald para o coeficiente j: gamma_g = (1-rho)*sum((X_g a)^2) + rho*(sum X_g a)^2.
    rho = 1 degenera so' quando o cluster coincide com a area do efeito fixo; na quadricula aninhada usa-se min(rho 0, rho 1)."""
    a = np.linalg.pinv(X.T @ X)[:, j]; v = X @ a
    gam = np.array([(1 - rho) * np.sum(v[g == k] ** 2) + rho * np.sum(v[g == k]) ** 2 for k in np.unique(g)])
    gb = gam.mean()
    return float("nan") if gb <= 1e-15 else float(len(gam) / (1 + np.mean(((gam - gb) / gb) ** 2)))


def preparar_lab(S, xq="Q", cols_extra=()):
    S = S.copy()
    for _ in range(3):  # area com < 2 unidades sai em TODO recorte (efeito fixo de 1 unidade = alavancagem 1)
        cnt_ = S.metro.value_counts(); S = S[S.metro.isin(cnt_[cnt_ >= 2].index)]
    mq = float(S[xq].mean()); S["semQ"] = S[xq].isna().astype(float); S["Qf"] = S[xq].fillna(mq)
    com_q = S.groupby("metro").semQ.transform("min") == 0  # sem-Q so' e' identificado em area com alguma unidade com Q
    S = S[(S.semQ == 0) | com_q]
    inc = ["semQ"] if (S.semQ.sum() >= 3 and S[S.semQ == 1].metro.nunique() >= 2) else []
    if S.semQ.sum() and not inc:
        S = S[S.semQ == 0]
        cnt_ = S.metro.value_counts(); S = S[S.metro.isin(cnt_[cnt_ >= 2].index)]
    M = pd.get_dummies(S.metro.astype(str), prefix="m", drop_first=True).astype(float)
    S = pd.concat([S.reset_index(drop=True), M.reset_index(drop=True)], axis=1)
    base = ["l_renda_dom", "l_pop", *cols_extra] + inc + list(M.columns)
    return S, base, inc


def desenho(S, cl, xq="Q", cols_extra=()):
    """So' X (e o modelo NULO, sem Q): G*, efeito detectavel com EP iid e com EP de cluster sob o nulo."""
    S, base, inc = preparar_lab(S, xq, cols_extra)
    Xm = X_(S, base + ["Qf"]); j = Xm.shape[1] - 1; g = op.regua(S[cl].astype(str)); G = len(np.unique(g))
    Xb = X_(S, base); yv = S.y.to_numpy(float); e0 = yv - Xb @ np.linalg.lstsq(Xb, yv, rcond=None)[0]
    n, kx = Xm.shape
    XtXi = np.linalg.pinv(Xm.T @ Xm)
    se_iid = float(np.sqrt(np.sum(e0 ** 2) / (n - Xb.shape[1])) * np.sqrt(XtXi[j, j]))
    Sg = np.zeros((g.max() + 1, kx)); np.add.at(Sg, g, Xm * e0[:, None])
    V = (G / (G - 1)) * ((n - 1) / (n - kx)) * XtXi @ (Sg.T @ Sg) @ XtXi
    g0, g1 = g_estrela(Xm, j, g, 0.0), g_estrela(Xm, j, g, 1.0)
    return dict(n=n, G=G, Gst0=g0, Gst1=g1, Gst=float(np.nanmin([g0, g1])), se_iid=se_iid, se_cl=float(np.sqrt(V[j, j])), gl=n - kx,
                Gst_area=g_estrela(Xm, j, op.regua(S.metro.astype(str)), 0.0), n_semQ=int(S.semQ.sum()), inc=inc)


def mde(se, gl, alfa):
    return float((stats.t.ppf(1 - alfa, gl) + stats.t.ppf(.80, gl)) * se)


def lab(S, cl, xq="Q", cols_extra=(), rng=None, boot=True):
    """y ~ Qf (+ semQ) + l_renda_dom + l_pop + extra + FE de area. Direcao NEGATIVA: p = lado de coef < 0."""
    S, base, inc = preparar_lab(S, xq, cols_extra)
    Xm = X_(S, base + ["Qf"]); yv = S.y.to_numpy(float); j = Xm.shape[1] - 1
    op._posto(Xm, f"lab {xq} {cols_extra}")
    b, e, h, XtXi = ex.ols(yv, Xm); assert h.max() < 1 - 1e-9, "alavancagem 1 no laboratorio"
    g = op.regua(S[cl].astype(str)); G = len(np.unique(g))
    out = dict(coef=float(b[j]), n=len(S), G=G, Gst=float(np.nanmin([g_estrela(Xm, j, g, 0.0), g_estrela(Xm, j, g, 1.0)])), n_semQ=int(S.semQ.sum()))
    if boot:
        p_pos, p_neg, t, _ = op.wcr(yv, Xm, j, g, rng)
        out.update(p=float(p_neg), p_oposto=float(p_pos), t=float(t), p_cr1=float(stats.t.cdf(t, G - 1)))
    Xb_ = X_(S, base); b0, e0, h0, _ = ex.ols(yv, Xb_); sst = np.sum((yv - yv.mean()) ** 2)
    out["r2loo0"], out["r2loo1"] = float(1 - np.sum((e0 / (1 - h0)) ** 2) / sst), float(1 - np.sum((e / (1 - h)) ** 2) / sst)
    return out


# ------------------------------------------------------------------ Ultra
def ultra(c, f, d):
    tr, te, DUM, cal, A, dummies = tm.bases(f, d)
    pv = pd.read_csv(op.PV, sep=";", encoding="utf-8-sig", index_col=0)
    P = poligonos_ultra(list(tr.index) + list(te.index) + list(pv.index))
    return tr, te, pv, DUM, cal, A, dummies, medir_q(P, c, "is_ultra"), P


def preparar_ultra(tr, te, d, Q):
    for D in (tr, te):
        for col in ("Q", "n_dec", "n_rede", "tp_share", "n_wh"):
            D[col] = Q[col].reindex(D.index).to_numpy(float)
        D["metro"] = d.iso_metro.reindex(D.index)
        D["cl_metro"] = D.metro.astype(str).where(D.metro.notna(), "u_" + D.index.astype(str))
    assert tr.Q.notna().all() and te.Q.notna().all(), "Ultra sem Q nas 57 (regra do §15: sem imputacao)"
    S = pd.concat([tr, te]); mq = float(S.Q.mean()); mm = float(S.l_m2.mean())
    for D in (tr, te):
        D["Qf"] = D.Q; D["m2xQ"] = (D.l_m2 - mm) * (D.Q - mq)
    return tr, te, mq, mm


def desenho_ultra(tr, te, V2, x, extra=()):
    S = pd.concat([tr.assign(teste=0.0), te.assign(teste=1.0)]).dropna(subset=["l_fat"])
    C = V2 + ["teste", *extra]; Xb = X_(S, C); Xm = X_(S, C + [x]); yv = S.l_fat.to_numpy(float); j = Xm.shape[1] - 1
    e0 = yv - Xb @ np.linalg.lstsq(Xb, yv, rcond=None)[0]; n, kx = Xm.shape; XtXi = np.linalg.pinv(Xm.T @ Xm)
    g = op.regua(S.cl_metro.astype(str)); G = len(np.unique(g))
    Sg = np.zeros((g.max() + 1, kx)); np.add.at(Sg, g, Xm * e0[:, None])
    V = (G / (G - 1)) * ((n - 1) / (n - kx)) * XtXi @ (Sg.T @ Sg) @ XtXi
    return dict(se_iid=float(np.sqrt(np.sum(e0 ** 2) / (n - Xb.shape[1])) * np.sqrt(XtXi[j, j])), se_cl=float(np.sqrt(V[j, j])), G=G,
                Gst=g_estrela(Xm, j, g, 0.0), gl=n - kx, n=n, sem_metro=int(S.metro.isna().sum()))


def c2c3(tr, te, base, add, y, cal_y, rng):
    a, b_ = tr.dropna(subset=[y] + add), te.dropna(subset=[y] + add)
    op._posto(X_(a, base + add), f"39 com {add}")
    b0, _, l0, _, _ = ajustar(a, base, y); b1, s1, l1, _, _ = ajustar(a, base + add, y)
    yv = b_[y].to_numpy(float); p0 = X_(b_, base) @ b0 + cal_y; p1 = X_(b_, base + add) @ b1 + cal_y
    t0, t1 = yv - p0, yv - p1
    gl = len(a) - len(base) - len(add) - 1; j = len(base) + len(add); js = 1 + base.index("studios")
    bl = [et(l0[ii]) - et(l1[ii]) for ii in (rng.integers(0, len(a), len(a)) for _ in range(2000))]
    bt = [et(t0[ii]) - et(t1[ii]) for ii in (rng.integers(0, len(b_), len(b_)) for _ in range(2000))]
    m = (b_.Q > b_.Q.median()).to_numpy()
    return dict(coef=float(b1[j]), lo=float(b1[j] - stats.t.ppf(.95, gl) * s1[j]), hi=float(b1[j] + stats.t.ppf(.95, gl) * s1[j]), gl=gl,
                dl=et(l0) - et(l1), dt=et(t0) - et(t1), e_l0=et(l0), e_l1=et(l1), e_t0=et(t0), e_t1=et(t1),
                ic_dl=np.quantile(bl, [.05, .95]), ic_dt=np.quantile(bt, [.05, .95]), vies0=float(np.median(np.exp(t0) - 1)),
                vies1=float(np.median(np.exp(t1) - 1)), desloc=float(np.exp(np.mean(p1 - p0)) - 1), studios0=float(b0[js]), studios1=float(b1[js]),
                dt_alto=et(t0[m]) - et(t1[m]), dt_baixo=et(t0[~m]) - et(t1[~m]),
                dt_rec=et(t0 - np.median(t0)) - et(t1 - np.median(t1)), k18=int((np.abs(t1) < np.abs(t0)).sum()), n_te=len(b_), b1=b1)


# ------------------------------------------------------------------ principal
def main():
    seco, ensaio = "--seco" in sys.argv, "--ensaio" in sys.argv
    out_dir = AQUI / "ensaio_item2" if ensaio else AQUI
    arq, res = out_dir / "previsoes_turma_2026_v2_Q.csv", out_dir / "resultado_item2_comodidades.md"
    if ensaio:
        out_dir.mkdir(exist_ok=True)
        for p in out_dir.iterdir():
            p.unlink()
    if not seco:
        assert not arq.exists() and not res.exists(), "congelamento/resultado do item 2 ja existem"
    if not seco and not ensaio:
        reg = REG2.read_text(encoding="utf-8") if REG2.exists() else ""
        for p in INSUMOS2:
            assert sha(p) in reg, f"TRAVA: {p.name} nao esta congelado (ou mudou) em {REG2.name}"
    assert sha(op.PV) == op.PV_SHA, "previsao congelada da turma mudou"
    rng = np.random.default_rng(20261003)
    c = ler_comodidades()
    f, d = ex.carregar()
    S, F = amostra_lab(c, ensaio=ensaio)
    tr, te, pv, DUM, cal, A, dummies, QU, PU = ultra(c, f, d)
    tr, te, mq, mm = preparar_ultra(tr, te, d, QU)
    V2 = ["l_m2", "l_renda_dom", "l_pop"] + DUM + ["studios"]
    _, rt, _ = op.residuos_v2(tr, te, V2, "l_fat", cal["l_fat"])
    r2v2 = float(ex.r2_loo(tr.l_fat.to_numpy(float), *ex.ols(tr.l_fat.to_numpy(float), X_(tr, V2))[1:3]))
    assert abs(r2v2 - 0.264) <= 0.005 and abs(et(rt.to_numpy()) - 0.221) <= 0.003, (r2v2, et(rt.to_numpy()))
    # ---- desenho (sem Q contra o desfecho): escolha da quadricula pela regra do §15
    DS = {f"{km}{suf}": desenho(S, f"cel{km}{suf}") for km in KMS for suf in ("", "s")}
    ok_km = [km for km in KMS if DS[str(km)]["Gst"] >= G_MIN]
    CEL = f"cel{max(ok_km)}" if ok_km else None
    D0 = DS[str(max(ok_km))] if ok_km else DS[str(min(KMS))]
    cnt = S.metro.value_counts(); big = cnt.index[0]; share = cnt.iloc[0] / len(S)
    q = S.Q.dropna(); iqr = float(q.quantile(.75) - q.quantile(.25))
    du_q, du_i = desenho_ultra(tr, te, V2, "Qf"), desenho_ultra(tr, te, V2, "m2xQ", extra=("Qf",))
    SU = pd.concat([tr, te]); iqr_qu = float(SU.Q.quantile(.75) - SU.Q.quantile(.25))
    pct10 = lambda b: 100 * (np.exp(-b * 0.1) - 1)
    if seco:
        print("CHECAGEM SECA OK item 2 (sem ajuste de Q contra o desfecho).")
        print(f"  funil: {F}")
        print("  G* por quadricula (rho 0 / rho 1 / usado = min): " + "; ".join(f"{k_} km: {v['Gst0']:.1f}/{v['Gst1']:.1f}/{v['Gst']:.1f} (G {v['G']})" for k_, v in DS.items()))
        print(f"  escolhida: {CEL}; por area seria G* {D0['Gst_area']:.1f}")
        print(f"  areas: {S.metro.nunique()} ({int(S.dentro_metro.sum())} em metro, {int((~S.dentro_metro).sum())} em municipio); isocrona real {int((S.geom_tipo == 'isocrona').sum())}, "
              f"circulo {int((S.geom_tipo == 'circulo').sum())}; maiores: {cnt.head(6).to_dict()} (maior {100 * share:.0f}%)")
        print(f"  Q: sem Q {int(S.Q.isna().sum())}; p10/p25/p50/p75/p90 = {q.quantile(.1):.2f}/{q.quantile(.25):.2f}/{q.median():.2f}/{q.quantile(.75):.2f}/{q.quantile(.9):.2f}; vizinhas declarantes p50 {S.n_dec.median():.0f}")
        print(f"  corr(Q, .): renda dom {S.Q.corr(S.l_renda_dom):+.2f}; pop {S.Q.corr(S.l_pop):+.2f}; log n_wh {S.Q.corr(S.l_nwh):+.2f}; tp_share {S.Q.corr(S.tp_share):+.2f} "
              f"(tp_share mediana {S.tp_share.median():.2f}, sem a propria rede)")
        print(f"  efeito detectavel no lab (80%), por +10 p.p. de Q: EP iid -> {pct10(mde(D0['se_iid'], D0['gl'], .05)):+.1f}% (a 0,05) / {pct10(mde(D0['se_iid'], D0['gl'], op.LIMIAR)):+.1f}% (a/6); "
              f"EP de cluster (gl G* - 1 = {D0['Gst'] - 1:.0f}) -> {pct10(mde(D0['se_cl'], max(D0['Gst'] - 1, 1), .05)):+.1f}% / {pct10(mde(D0['se_cl'], max(D0['Gst'] - 1, 1), op.LIMIAR)):+.1f}%; IQR de Q {iqr:.2f}")
        print(f"  Ultra: poligonos (pinos corrigidos) {int(SU.index.isin(PU.index).sum())}/57, turma {int(pv.index.isin(PU.index).sum())}/16; sem Q {int(SU.Q.isna().sum())}; Q mediana {SU.Q.median():.2f}; "
              f"G* por metro {du_q['Gst']:.1f} (G {du_q['G']}, {du_q['sem_metro']} sem metro)")
        print(f"  Ultra, efeito principal detectavel (80%, a 0,05): EP iid {pct10(mde(du_q['se_iid'], du_q['gl'], .05)):+.1f}% / EP cluster {pct10(mde(du_q['se_cl'], max(du_q['Gst'] - 1, 1), .05)):+.1f}% por +10 p.p.")
        mi, mc = mde(du_i["se_iid"], du_i["gl"], .05), mde(du_i["se_cl"], max(du_i["Gst"] - 1, 1), .05)
        print(f"  Ultra, interacao m2 x Q detectavel (80%, a 0,05): coef {mi:.2f} (iid) / {mc:.2f} (cluster) = diferenca de elasticidade do m2 de {mi * iqr_qu:.2f} / {mc * iqr_qu:.2f} "
              f"entre Q no p25 e no p75 (elasticidade do m2 na v2 ~0,5)")
        return
    # ---------------- teste
    if CEL is None:
        P = dict(p=1.0, coef=np.nan, nota=f"G* < {G_MIN} em todas as quadrículas: o laboratório não dá p (p = 1)")
    else:
        P = lab(S, CEL, rng=rng); P["nota"] = f"cluster = quadrícula de {CEL[3:]} km dentro da área (§15)"
    cl0 = CEL or "cel30"
    sem_big = lab(S[S.metro != big], cl0, rng=rng)
    com_nwh = lab(S, cl0, cols_extra=("l_nwh",), rng=rng)
    rob = lambda r: np.isfinite(P.get("coef", np.nan)) and np.sign(r["coef"]) == np.sign(P["coef"]) and abs(r["coef"]) >= 0.5 * abs(P["coef"])
    c1 = "significativo" if P["p"] <= op.LIMIAR else ("não significativo" if P["p"] > 0.05 else "pendente (Holm no fechamento)")
    if c1 != "não significativo" and not rob(sem_big):
        c1 = "frágil à dependência espacial (não resiste sem a maior área); entra no Holm com p = 1"
    elif c1 != "não significativo" and not rob(com_nwh):
        c1 = "confundido com a QUANTIDADE de concorrência (não resiste ao controle do nº de academias); entra no Holm com p = 1"
    lab_passa = c1 == "significativo" or c1.startswith("pendente")
    pc = lambda v: f"{100 * (np.exp(v) - 1):+.1f}%"
    L = ["# BLK-UNI-10, item 2 — qualidade da concorrência (protocolo da bateria §9.9 + §13 + §14 + §15, congelado antes de rodar)", "",
         f"Q = fração das academias **listadas no Wellhub** na isócrona de 10 min de carro (ou círculo de raio equivalente) com vestiário, "
         f"chuveiro e armário, entre as que declararam comodidades; sem a própria rede. Foto da planilha: 29/09/2026 (SHA `{CSV_SHA[:12]}…`).", "",
         "## Laboratório Smart Fit (teste primário; direção esperada: negativa)", "",
         f"- Funil: {F}.",
         f"- Áreas de comparação: {S.metro.nunique()} ({int(S.dentro_metro.sum())} unidades em metrô, {int((~S.dentro_metro).sum())} em município); "
         f"isócrona real {int((S.geom_tipo == 'isocrona').sum())}, círculo {int((S.geom_tipo == 'circulo').sum())}. Maior área com {100 * share:.0f}% do N.",
         "- G* (mínimo entre ρ 0 e ρ 1) por quadrícula: " + "; ".join(f"{k_} km {v['Gst']:.1f}" for k_, v in DS.items() if not k_.endswith("s")) + f". Usado: {P['nota']}."]
    if np.isfinite(P.get("coef", np.nan)):
        L += [f"- Coeficiente de Q: **{P['coef']:+.3f}** em log de alunos por +1 de Q → **{pc(P['coef'] * 0.1)} de alunos por +10 p.p.** de concorrência "
              f"completa; n = {P['n']}, {P['n_semQ']} sem Q.",
              f"- **p unilateral (coef < 0; wild cluster bootstrap restrito, Webb, B = {B_BOOT}): {P['p']:.4f}.** p CR1 (gl G − 1) {P['p_cr1']:.4f}; "
              f"lado oposto (descritivo) {P['p_oposto']:.4f}. R² LOO com efeito fixo: {P['r2loo0']:.3f} → {P['r2loo1']:.3f}.",
              f"- Robustez (§15): sem a maior área {sem_big['coef']:+.3f} ({'resiste' if rob(sem_big) else 'NÃO resiste'}); com log(1 + nº de academias "
              f"Wellhub) {com_nwh['coef']:+.3f} ({'resiste' if rob(com_nwh) else 'NÃO resiste'})."]
    L += [f"- c1: **{c1}**.", "", "## Sensibilidades do laboratório (descritivas)", "", "| versão | n | coef. | p (coef < 0) | G* |", "|---|---|---|---|---|"]

    def sl(rot, r):
        L.append(f"| {rot} | {r['n']} | {r['coef']:+.3f} | {r['p']:.4f} | {r['Gst']:.1f} |")
    sl(f"sem a maior área ({big}) — obrigatória", sem_big)
    sl("controle: log(1 + nº de academias Wellhub na isócrona) — obrigatória", com_nwh)
    for k_ in DS:
        if f"cel{k_}" != cl0:
            sl(f"cluster = quadrícula de {k_[:-1] + ' km deslocada' if k_.endswith('s') else k_ + ' km'}", lab(S, f"cel{k_}", rng=rng))
    sl("cluster = área (metrô ou município)", lab(S, "metro", rng=rng))
    sl("só isócronas reais (sem círculos)", lab(S[S.geom_tipo == "isocrona"], cl0, rng=rng))
    sl("só dentro das áreas metropolitanas", lab(S[S.dentro_metro], cl0, rng=rng))
    sl("controle: log(1 + nº de Smart Fit na isócrona, pelo site da rede)", lab(S.assign(l_nrede=np.log1p(S.n_rede_site)), cl0, cols_extra=("l_nrede",), rng=rng))
    sl("controle: fração de vizinhas vindas do TotalPass", lab(S.assign(tps=S.tp_share.fillna(S.tp_share.mean())), cl0, cols_extra=("tps",), rng=rng))
    Sx = S.assign(idade_12_23=((S.idade_m >= 12) & (S.idade_m <= 23)).astype(float))
    sl("controles de idade (12–23 meses) e franquia", lab(Sx, cl0, cols_extra=("idade_12_23", "franquia"), rng=rng))
    lomo = {m: lab(S[S.metro != m], cl0, rng=rng, boot=False)["coef"] for m in cnt.index[cnt >= 20]}
    L += ["", "Tirando uma área com ≥ 20 unidades por vez (coeficiente): " + ", ".join(f"sem {m}: {v:+.3f}" for m, v in lomo.items())
          + f". Mesmo sinal em {sum(np.sign(v) == np.sign(P.get('coef', 0)) for v in lomo.values())} de {len(lomo)}.", ""]
    # ---------------- Ultra
    if ensaio:
        rz = np.random.default_rng(2)
        for D in (tr, te):
            D["l_fat"] = np.where(D.l_fat.notna(), rz.normal(12.0, 0.3, len(D)), np.nan)
    Uq = op.empilhado(tr, te, V2, "Qf", "l_fat", rng, cl="cl_metro")
    Ui = op.empilhado(tr, te, V2, "m2xQ", "l_fat", rng, cl="cl_metro", extra=("Qf",))
    Mx = c2c3(tr, te, V2, ["Qf"], "l_fat", cal["l_fat"], rng)
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
    else:
        v = "NÃO DEMONSTRADO no laboratório (não vai à Ultra)" + (" — efeito na direção OPOSTA (descritivo)" if P.get("p_oposto", 1) <= 0.05 else "")
    L += ["## Ultra (57 unidades, pinos corrigidos)", "",
          f"- Efeito principal de Q (empilhado, cluster por metrô; descritivo): {Uq['coef']:+.3f} → {pc(Uq['coef'] * 0.1)} por +10 p.p.; p (coef < 0) {Uq['p_neg']:.4f}.",
          f"- **Hipótese do diretor (interação m² × Q, descritiva, fora do Holm):** {Ui['coef']:+.3f}; p (coef < 0) {Ui['p_neg']:.4f}; p (coef > 0) {Ui['p']:.4f}. "
          f"Negativo = o tamanho rende menos onde a concorrência é completa. Diferença de elasticidade do m² entre Q no p25 e no p75: {Ui['coef'] * iqr_qu:+.2f}.",
          f"- c2/c3 (v2 contra v2 + Q; {'CONTAM' if lab_passa else 'só relatados, o laboratório não passou'}): coeficiente nas 39 {Mx['coef']:+.3f} "
          f"(IC 90% {Mx['lo']:+.3f} a {Mx['hi']:+.3f}){'' if coerente else ' — sinal diferente do laboratório'}; estúdios {Mx['studios0']:+.3f} → {Mx['studios1']:+.3f}.",
          f"  LOO {100 * Mx['e_l0']:.1f}% → {100 * Mx['e_l1']:.1f}% (queda {100 * Mx['dl']:+.1f} pp; IC 90% {100 * Mx['ic_dl'][0]:+.1f} a {100 * Mx['ic_dl'][1]:+.1f}); "
          f"teste {100 * Mx['e_t0']:.1f}% → {100 * Mx['e_t1']:.1f}% (queda {100 * Mx['dt']:+.1f} pp; IC 90% {100 * Mx['ic_dt'][0]:+.1f} a {100 * Mx['ic_dt'][1]:+.1f}; "
          f"{Mx['k18']} de {Mx['n_te']} melhoram; recentrado {100 * Mx['dt_rec']:+.1f} pp); viés {100 * Mx['vies0']:+.1f}% → {100 * Mx['vies1']:+.1f}%; "
          f"deslocamento {100 * Mx['desloc']:+.1f}%; queda com Q acima da mediana {100 * Mx['dt_alto']:+.1f} pp, abaixo {100 * Mx['dt_baixo']:+.1f} pp.", "",
          f"**Veredito do item 2: {v}.**", ""]
    # ---------------- turma 2026 (congela sempre)
    est = pd.read_csv(op.MET, sep=";", encoding="utf-8-sig", index_col=0).metragem_estimada_m2.dropna()
    of = d.tam_metragem_m2.dropna(); m2 = pd.concat([of, est[~est.index.isin(of.index)]])
    cand = A.reindex(pv.index).drop(columns=["l_m2"]).join(np.log(m2).rename("l_m2"))
    cand["master_id"] = pv.master_id
    cand = dummies(cand)
    cand["Q"] = QU.Q.reindex(cand.index); cand["Qf"] = cand.Q
    ok = cand.Q.notna(); g = Uq["coef"]
    out = pd.DataFrame(index=pv.index)
    out["Q"] = cand.Q
    out["prev_v2dom_cal2026"] = pv.prev_v2dom_cal2026
    out["prev_v2dom_x_Q"] = np.where(ok, pv.prev_v2dom_cal2026 * np.exp(g * (cand.Q - mq)), np.nan).round(0)
    out["prev_v2dom_mesmo_nivel"] = np.where(ok, pv.prev_v2dom_cal2026 * np.exp(g * (cand.Q[ok].mean() - mq)), np.nan).round(0)
    okm = ok & cand[V2].notna().all(axis=1)
    p_c = pd.Series(np.nan, index=cand.index); p_c[okm] = np.exp(X_(cand[okm], V2 + ["Qf"]) @ Mx["b1"] + cal["l_fat"])
    out["prev_v2_Q_39_cal2026"] = p_c.round(0)
    out.to_csv(arq, sep=";", encoding="utf-8-sig")
    h = sha(arq)
    with (out_dir / REG2.name).open("a", encoding="utf-8") as fh:
        fh.write(f"Turma 2026 congelada pelo item 2 em {datetime.now():%Y-%m-%d %H:%M} (gamma Q Ultra {g:+.4f}; media Q {mq:.4f}): {h} *{arq.name}\n")
    L += ["## Turma de 2026 congelada", "", f"`{arq.name}`: {len(out)} unidades, {int(ok.sum())} com Q; γ̂ (Ultra) = {g:+.3f}. SHA-256 `{h}`.",
          "Conferência: a inclinação do resíduo da v2 congelada sobre (Q − média) dentro da turma, comparada a γ̂; a `prev_v2dom_x_Q` só conta "
          "se vencer a `prev_v2dom_mesmo_nivel`.", ""]
    res.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
