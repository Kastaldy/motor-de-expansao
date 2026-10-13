# -*- coding: utf-8 -*-
"""Passo 2 formal (protocolo_manaus_volume.md §12 + emenda v1.3 §13, congelado antes de rodar): efeito praca de Manaus
medido pela Smart Fit, crosswalk nacional pela listagem do TotalPass, circulo de 4,97 km igual para todas, efeito fixo
por metro (caixas de metros.json), IC bootstrap e IC-t HC3 (vale o mais largo), veredito = o menos favoravel entre
(ii-casadas), (ii-todas-imputada) e as duas (ii-offset). So' le; grava nesta pasta (indice de bbox no scratchpad).
.venv, PYTHONPATH=src."""
import glob
import importlib.util
import json
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import shapely
from pyproj import Transformer
from scipy import stats
from scipy.spatial import cKDTree
from shapely import wkb

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
REPO = UNI.parent.parent.parent
SC = Path(r"C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\9259d0a1-7dda-49bd-a390-c88f3d4ac1a6\scratchpad")
ISO = SC / "iso"
GEO = REPO / "data" / "outputs" / "setores_censitarios_2022_geo"
RAIO_M, MIN_KM_CIDADE, MANAUS = 4970.0, 40.0, "44"
PIN = (-3.03514, -59.996833)
NAO_CASAM_ESPERADAS = {"Amazonas Shopping", "Jardim Amazonas"}
FAIXAS = [("id_le8", 0, 8), ("id_9_11", 9, 11), ("id_12_17", 12, 17), ("id_18_23", 18, 23)]  # referencia: >= 24 ou legado
ORDEM = {"C": 0, "D": 1, "B": 2, "A": 3}
T4674 = Transformer.from_crs(4674, 5880, always_xy=True)
T4326 = Transformer.from_crs(4326, 5880, always_xy=True)


def mod(nome, p):
    s = importlib.util.spec_from_file_location(nome, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def sem_acento(s):
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower().strip()


def norm(s):
    return re.sub(r"[^a-z0-9]", "", re.sub(r"^\s*smart\s*fit\s*", "", sem_acento(s)))


def norm_ordenado(s):
    return "".join(sorted(re.findall(r"[a-z0-9]+", re.sub(r"^\s*smart\s*fit\s*", "", sem_acento(s)))))


def hav_km(la1, lo1, la2, lo2):
    la1, lo1, la2, lo2 = map(np.radians, (la1, lo1, la2, lo2))
    a = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    return 6371.0088 * 2 * np.arcsin(np.sqrt(a))


def indice_bbox():
    cache = SC / "indice_setores_bbox.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    rows = []
    for f in GEO.glob("uf=*/cod_municipio=*/*.parquet"):
        b = pq.ParquetFile(f).read(columns=["bbox_minx", "bbox_miny", "bbox_maxx", "bbox_maxy"]).to_pandas()
        if len(b):
            rows.append((str(f), b.bbox_minx.min(), b.bbox_miny.min(), b.bbox_maxx.max(), b.bbox_maxy.max()))
    ix = pd.DataFrame(rows, columns=["arquivo", "minx", "miny", "maxx", "maxy"])
    ix.to_parquet(cache, index=False)
    return ix


def pontos_setores(arquivos):
    """Ponto representativo (point_on_surface) + pop/dom/renda, como 04_atributos.atributos_poligono (area > 40 km2)."""
    cols = ["pop_total_setor_2022", "domicilios_particulares_ocupados_setor_2022", "renda_per_capita_setor_2022_calibrada",
            "renda_per_capita_setor_2022", "geometry_wkb", "flag_geometria_valida"]
    fr = []
    for f in arquivos:
        pf = pq.ParquetFile(f)
        df = pf.read(columns=[c for c in cols if c in pf.schema_arrow.names]).to_pandas()
        if "flag_geometria_valida" in df:
            df = df[df.flag_geometria_valida.fillna(True).astype(bool)]
        df = df[df.geometry_wkb.notna()]
        rp = shapely.point_on_surface(shapely.from_wkb(df.geometry_wkb.to_numpy()))
        x, y = T4674.transform(shapely.get_x(rp), shapely.get_y(rp))
        ren = df["renda_per_capita_setor_2022_calibrada"].fillna(df["renda_per_capita_setor_2022"]) if "renda_per_capita_setor_2022_calibrada" in df else df["renda_per_capita_setor_2022"]
        fr.append(pd.DataFrame({"x": x, "y": y, "pop": np.nan_to_num(df.pop_total_setor_2022.clip(lower=0).to_numpy(float)),
                                "dom": np.nan_to_num(df.domicilios_particulares_ocupados_setor_2022.clip(lower=0).to_numpy(float)), "renda": ren.to_numpy(float)}))
    P = pd.concat(fr, ignore_index=True)
    ok = np.isfinite(P.x) & np.isfinite(P.y)
    return P[ok].reset_index(drop=True), int((~ok).sum())


def caixa(lat, lng, metros):
    for b in metros:
        if b["lat_min"] <= lat <= b["lat_max"] and b["lng_min"] <= lng <= b["lng_max"]:
            return int(b["id"])
    return None


def idade_meses(ts):
    return np.where(ts <= pd.Timestamp("2023-01-31"), 999, (2025 * 12 + 7) - (ts.dt.year * 12 + ts.dt.month))


def main():
    e2 = mod("e2", AQUI / "02_evidencias.py")
    ex, X_ = e2.ex, e2.X_
    metros = json.load(open(ISO / "metros.json", encoding="utf-8"))
    L = ["# Passo 2 formal — efeito praça de Manaus pela Smart Fit (protocolo §12 + emenda v1.3 §13)", ""]

    # ---------------- base Ultra
    at = json.loads((AQUI / "atributos_pino.json").read_text(encoding="utf-8"))["carro_10"]
    f, d = ex.carregar()
    tr, DUM = e2.base_treino(f, d)
    V2 = ["l_m2", "l_renda_dom", "l_pop"] + DUM + ["studios"]
    y2 = tr.l_ativos.to_numpy(float)
    b, e, h, _ = ex.ols(y2, X_(tr, V2))
    ql, qh = np.quantile(e / (1 - h), [.1, .9])
    row = {"l_m2": np.log(2000.0), "l_renda_dom": np.log(at["renda_pc"] * at["pop"] / at["domicilios"]), "l_pop": np.log(at["pop"]), "studios": 1.0}

    def pv(dm):
        return float(np.asarray(X_(pd.DataFrame([{**row, **dm}]), V2) @ b).ravel()[0])
    p_media = pv({c: float(tr[c].mean()) for c in DUM})
    BASE = float(np.exp(p_media)); CENTRAL_M3 = float(np.exp(pv({**{c: 0.0 for c in DUM}, "mr_M3": 1.0})))
    assert abs(BASE - 2532) <= 2 and abs(CENTRAL_M3 - 2958) <= 2, (BASE, CENTRAL_M3)
    bv_r, bv_p = float(b[1 + V2.index("l_renda_dom")]), float(b[1 + V2.index("l_pop")])
    ug = d.iso_metro.reindex(tr.index).dropna().astype(int)
    ucx = pd.Series([caixa(la, lo, metros) for la, lo in zip(d.lat.reindex(ug.index), d.lng.reindex(ug.index))], index=ug.index)
    div = int((ucx != ug).sum())
    wU_all = ug.astype(str).value_counts()
    L += [f"Base Ultra: v2 em ativos com master média na isócrona real = **{BASE:,.0f}** (faixa 80% {np.exp(p_media + ql):,.0f}–{np.exp(p_media + qh):,.0f}); "
          f"central M3 (teto de cenário) = {CENTRAL_M3:,.0f}. Inclinações da v2: renda domiciliar {bv_r:+.3f}, população {bv_p:+.3f}. "
          f"Pesos por `iso_metro` ({len(ug)} unidades; divergências contra a regra da caixa: {div}).", ""]

    # ---------------- painel Smart Fit
    k = pd.read_excel(glob.glob(str(REPO / "data" / "validacao" / "KPIs_Smart_*.xlsx"))[0], sheet_name="Base").drop_duplicates(["Sigla", "Data_Ref"])
    k["uf"] = k.Sigla.astype(str).str[3:5]
    ultS = k.sort_values("Data_Ref").groupby("Sigla").tail(1).set_index("Sigla")
    ch_all = ultS.Nome.map(norm) + "|" + ultS.uf
    dup_k = set(ch_all[ch_all.duplicated(keep=False)])
    first = k.groupby("Sigla").Data_Ref.min()
    k25 = k[(k.Data_Ref >= "2025-01-01") & (k.Data_Ref <= "2025-12-31")]
    ym = k25.groupby("Sigla")["Alunos Totais SF"].agg(["median", "count"])
    U = pd.DataFrame({"nome": ultS.Nome.astype(str).str.strip(), "uf": ultS.uf, "chave": ch_all}).join(first.rename("primeiro")).join(ym)
    U["franquia"] = k.groupby("Sigla").Propriedade.agg(lambda s: s.mode().iat[0]).reindex(U.index).eq("Franquia").astype(float)
    U = U[(U.primeiro <= "2024-12-31") & (U["count"] >= 6) & (U["median"] > 0)].copy()
    U["y"] = np.log(U["median"].astype(float))
    U["idade"] = idade_meses(U.primeiro)
    for nm, a, z in FAIXAS:
        U[nm] = ((U.idade >= a) & (U.idade <= z)).astype(float)
    IDADE = [nm for nm, _, _ in FAIXAS]

    # ---------------- crosswalk (listagem do TotalPass)
    tp = pd.read_parquet(UNI / "insumos_vps" / "planos_totalpass.parquet")
    tp["cid_k"] = tp.cidade.map(sem_acento)
    med = tp.groupby(["cid_k", "uf"])[["lat", "lng"]].median().rename(columns={"lat": "c_lat", "lng": "c_lng"})
    tp = tp.join(med, on=["cid_k", "uf"])
    tp["d_km"] = hav_km(tp.lat, tp.lng, tp.c_lat, tp.c_lng)
    lim = tp.groupby(["cid_k", "uf"]).d_km.quantile(.95).clip(lower=MIN_KM_CIDADE).rename("lim_km")
    npar = tp.groupby(["cid_k", "uf"]).size().rename("n_parceiros")
    tp = tp.join(lim, on=["cid_k", "uf"]).join(npar, on=["cid_k", "uf"])
    sfp = tp[tp.nome.astype(str).map(lambda s: bool(re.match(r"^\s*smart\s*fit", sem_acento(s))))].copy()
    sfp["chave"] = sfp.nome.map(norm) + "|" + sfp.uf
    dup_tp = set(sfp.chave[sfp.chave.duplicated(keep=False)])
    sfp_ord = set(sfp.nome.map(norm_ordenado) + "|" + sfp.uf)
    sfp = sfp[~sfp.chave.isin(dup_tp)].set_index("chave")
    U["casada"] = U.chave.isin(sfp.index) & ~U.chave.isin(dup_k)
    for c in ("lat", "lng", "d_km", "lim_km", "n_parceiros"):
        U[c] = U.chave.map(sfp[c]).where(U.casada)
    U["valida"] = U.casada & (U.d_km <= U.lim_km)
    nc_am = set(U[(U.uf == "AM") & ~U.casada].nome)
    if not nc_am <= NAO_CASAM_ESPERADAS:
        print("TRAVA (§13.2): nao casadas do AM divergem do declarado:", nc_am); sys.exit(3)
    U["grupo"] = None
    for s, r in U[U.valida].iterrows():
        cx = caixa(r.lat, r.lng, metros)
        U.at[s, "grupo"] = str(cx) if cx is not None else f"fora_{r.uf}"
    am_val = U[(U.uf == "AM") & U.valida]
    assert (am_val.grupo == MANAUS).all(), am_val[["nome", "grupo"]]
    nao = U[~U.casada]
    diag_ord = int((nao.nome.map(norm_ordenado) + "|" + nao.uf).isin(sfp_ord).sum())
    desc_uf = U[U.casada & ~U.valida].uf.value_counts().to_dict()
    L += ["## Casamento", "",
          f"Smart Fit com desfecho (≥ 6 meses em 2025, no painel até 2024-12): {len(U)}. Casadas: {int(U.casada.sum())} ({100 * U.casada.mean():.0f}%); "
          f"coordenada inválida (limite por cidade = máx(40 km, p95)): {int((U.casada & ~U.valida).sum())} {desc_uf}; válidas: {int(U.valida.sum())}; "
          f"válidas em cidade com 1 parceiro só: {int((U.valida & (U.n_parceiros == 1)).sum())}. "
          f"Diagnóstico: das {len(nao)} não casadas, {diag_ord} casariam com as palavras ordenadas.",
          "AM por situação: " + "; ".join(f"{r.nome} = {'válida' if r.valida else ('coordenada inválida' if r.casada else 'não casada')}"
                                          for _, r in U[U.uf == 'AM'].sort_values('primeiro').iterrows()) + ".", ""]

    # ---------------- geometria
    V = U[U.valida].copy()
    ix = indice_bbox(); pad = 0.06; need = set()
    for la, lo in zip(V.lat, V.lng):
        m = (ix.maxx >= lo - pad) & (ix.minx <= lo + pad) & (ix.maxy >= la - pad) & (ix.miny <= la + pad)
        need |= set(ix.arquivo[m])
    P, n_inval = pontos_setores(sorted(need))
    tree = cKDTree(P[["x", "y"]].to_numpy())
    ux, uy = T4326.transform(V.lng.to_numpy(float), V.lat.to_numpy(float))
    pops, doms, rds = [], [], []
    for x, y in zip(ux, uy):
        s = P.iloc[tree.query_ball_point([x, y], RAIO_M)]; w = np.where(np.isnan(s.renda), 0, s["pop"])
        pops.append(s["pop"].sum()); doms.append(s.dom.sum()); rds.append((np.nan_to_num(s.renda) * w).sum() / w.sum() if w.sum() > 0 else np.nan)
    V["pop"], V["dom"], V["renda_pc"] = pops, doms, rds
    with np.errstate(divide="ignore", invalid="ignore"):
        V["log_pop"] = np.log(V["pop"]); V["log_renda_dom"] = np.log(V.renda_pc * V["pop"] / V.dom)
    okg = np.isfinite(V.log_pop) & np.isfinite(V.log_renda_dom)
    quedas = V[~okg].grupo.value_counts().to_dict()
    V = V[okg].copy()
    man = V[V.grupo == MANAUS]
    imp = {"log_renda_dom": man.log_renda_dom.mean(), "log_pop": man.log_pop.mean()}
    VI = pd.concat([V, U[(U.uf == "AM") & ~U.valida].assign(grupo=MANAUS, **imp)])
    L += [f"Círculo de {RAIO_M / 1000:.2f} km: {len(need)} arquivos, {len(P):,} setores ({n_inval} pontos inválidos fora); com atributos: {len(V)} "
          f"(quedas por grupo: {quedas or 'nenhuma'}).",
          f"Manaus casadas (n={len(man)}): população mediana {man['pop'].median():,.0f} (DP do log {man.log_pop.std():.2f}); renda domiciliar mediana "
          f"R$ {np.exp(man.log_renda_dom.median()):,.0f} (DP do log {man.log_renda_dom.std():.2f}). Demais: {V[V.grupo != MANAUS]['pop'].median():,.0f} e "
          f"R$ {np.exp(V[V.grupo != MANAUS].log_renda_dom.median()):,.0f}. Imputação das não casadas: médias das casadas.", ""]

    # ---------------- estimacao
    def ajuste(S, ctrl, yc="y"):
        S = S.reset_index(drop=True)
        grupos = sorted(S.grupo.unique())
        wU = wU_all[[g in set(grupos) and g != MANAUS for g in wU_all.index]]
        if MANAUS not in grupos or not len(wU):
            return None
        X = np.column_stack([(S.grupo.to_numpy() == g).astype(float) for g in grupos] + [S[c].to_numpy(float) for c in ctrl])
        if np.linalg.matrix_rank(X) < X.shape[1]:
            return None
        yv = S[yc].to_numpy(float)
        bb, ee, hh, XtXi = ex.ols(yv, X)
        cvec = np.zeros(X.shape[1]); cvec[grupos.index(MANAUS)] = 1.0
        for g, w in wU.items():
            cvec[grupos.index(g)] -= w / wU.sum()
        est = float(cvec @ bb)
        ww = np.where(hh < 1 - 1e-9, (ee / np.where(hh < 1 - 1e-9, 1 - hh, 1)) ** 2, 0.0)
        V_ = XtXi @ (X.T * ww) @ X @ XtXi
        coefs = {c: float(bb[len(grupos) + i]) for i, c in enumerate(ctrl)}
        return est, float(np.sqrt(cvec @ V_ @ cvec)), coefs, int((S.grupo == MANAUS).sum()), wU

    def rodar(S, ctrl, rot, rng, yc="y"):
        S = S.reset_index(drop=True)
        a = ajuste(S, ctrl, yc)
        if a is None:
            L.append(f"| {rot} | {len(S)} | – | – | sem Manaus ou posto deficiente | – | – | – | – |"); return None
        est, se, coefs, n_man, wU = a
        idx_g = {g: S.index[S.grupo == g].to_numpy() for g in S.grupo.unique()}
        bs, desc = [], 0
        for _ in range(2000):
            ii = np.concatenate([rng.choice(v, len(v), replace=True) for v in idx_g.values()])
            r = ajuste(S.loc[ii], ctrl, yc)
            if r is None:
                desc += 1
            else:
                bs.append(r[0])
        lo_b, hi_b = np.quantile(bs, [.05, .95])
        tc = stats.t.ppf(.95, max(n_man - 1, 1))
        lo, hi = min(lo_b, est - tc * se), max(hi_b, est + tc * se)
        alt, alo, ahi = BASE * np.exp(est), BASE * np.exp(lo), BASE * np.exp(hi)
        cat = "A" if alo >= max(3000.0, CENTRAL_M3) else ("B" if alo > BASE else ("C" if ahi < BASE else "D"))
        cf = ", ".join(f"{c.replace('log_', '')} {v:+.3f}" for c, v in coefs.items() if c.startswith("log_")) or "–"
        L.append(f"| {rot} | {len(S)} | {n_man} | {100 * wU.sum() / len(ug):.0f}% | r {np.exp(est):.2f} (boot {np.exp(lo_b):.2f}–{np.exp(hi_b):.2f}; "
                 f"t {np.exp(est - tc * se):.2f}–{np.exp(est + tc * se):.2f}) | **{alt:,.0f}** ({alo:,.0f}–{ahi:,.0f}) | {cf} | {len(bs)}/{desc} | {cat} |")
        return dict(cat=cat, n_man=n_man, coefs=coefs, est=est)

    rng = np.random.default_rng(42)
    CT = ["log_renda_dom", "log_pop", "franquia"] + IDADE
    CO = ["franquia"] + IDADE
    todas = pd.concat([U[U.valida], U[(U.uf == "AM") & ~U.valida].assign(grupo=MANAUS)])
    todas.loc[todas.uf == "AM", "grupo"] = MANAUS
    for S_ in (V, VI):
        S_["y_off"] = S_.y - bv_r * S_.log_renda_dom - bv_p * S_.log_pop
    L += [f"## Efeito praça (r) e número alternativo = {BASE:,.0f} × r", "",
          "| versão | n | Manaus | peso Ultra coberto | r (IC90 bootstrap; IC90 t-HC3) | alt (IC mais largo) | inclinações Smart Fit | reamostras válidas/descartadas | categoria |",
          "|---|---|---|---|---|---|---|---|---|"]
    rodar(todas, [], "(i-todas) sem controles", rng)
    rodar(U[U.valida], [], "(i-casadas) sem controles", rng)
    R = {"casadas": rodar(V, CT, "**(ii-casadas)**", rng), "imputada": rodar(VI, CT, "**(ii-todas-imputada)**", rng),
         "off_casadas": rodar(V, CO, "**(ii-offset, casadas)**", rng, "y_off"), "off_imputada": rodar(VI, CO, "**(ii-offset, todas-imputada)**", rng, "y_off")}
    sub = V[(V.id_le8 == 0) & (V.id_9_11 == 0)]
    s12 = rodar(sub, [c for c in CT if c not in ("id_le8", "id_9_11")], "(ii-casadas) sem as com < 12 meses", rng)
    if s12 and s12["n_man"] < 5:
        L.append("*(sensibilidade sem as com < 12 meses: Manaus abaixo do portão de 5 — não interpretar.)*")
    gate = R["casadas"] is not None and R["casadas"]["n_man"] >= 5
    if not gate or any(v is None for v in R.values()):
        veredito = "INCONCLUSIVO (portão ou estimação)"
        p2 = "inconclusivo"
    else:
        cmin = min((v["cat"] for v in R.values()), key=lambda c: ORDEM[c])
        veredito = {"A": "A — média do modelo corrigida pela praça ≥ 3.000 e ≥ central M3", "B": "B — acima do modelo (média), sem chegar ao teto de cenário",
                    "C": "C — abaixo do modelo", "D": "D — neutro"}[cmin]
        p2 = "maior" if cmin == "A" else ("menor" if cmin == "C" else "neutro")
    L += ["", f"Inclinações da v2 para comparar: renda domiciliar {bv_r:+.3f}, população {bv_p:+.3f}.",
          f"**Veredito do Passo 2 (o menos favorável das 4 versões principais): {veredito}.** Na síntese do §11, o Passo 2 conta como: **{p2}**.", ""]

    # ---------------- idade dentro de Manaus x nacional
    if R["imputada"]:
        am = U[U.uf == "AM"]
        L += ["## Idade: Manaus por dentro × coeficientes nacionais", "",
              "Manaus (log médio por faixa, n): " + "; ".join(
                  f"{nm} {am[am[nm] == 1].y.mean():.2f} (n={int(am[nm].sum())})" for nm in IDADE if am[nm].sum() > 0) +
              f"; referência {am[am[IDADE].sum(axis=1) == 0].y.mean():.2f} (n={int((am[IDADE].sum(axis=1) == 0).sum())}).",
              "Coeficientes nacionais (ii-todas-imputada): " + "; ".join(f"{c} {v:+.2f}" for c, v in R["imputada"]["coefs"].items() if c.startswith("id_")) + ".", ""]

    # ---------------- descritivos
    L += ["## Descritivos", ""]
    for sig in ("SBRAMCCNO01", "SBRAMCPDN01", "SBRAMCNSG01"):
        s = k[k.Sigla == sig].sort_values("Data_Ref")
        if len(s):
            L.append(f"- {s.Nome.iloc[-1].strip()}: " + "; ".join(f"{r.Data_Ref:%Y-%m} {r._2:,.0f}" for r in s[["Data_Ref", "Alunos Totais SF"]].itertuples()
                                                               if r.Data_Ref.month in (1, 4, 7, 10) or r.Data_Ref >= pd.Timestamp("2025-10-01")) + ".")
    iso = pd.read_parquet(AQUI / "isocrona_pino.parquet")
    poly = wkb.loads(iso[iso.limite_s == 600].poligono_wkb.iloc[0])
    c = pd.read_parquet(REPO / "data" / "staging" / "concorrentes_mapeados.parquet")
    c = c[c.status_registro.eq("valido")]
    dentro = c[shapely.contains_xy(poly, c.lng.to_numpy(float), c.lat.to_numpy(float))]
    sfd = U[U.valida & (U.uf == "AM")]
    sf_in = int(shapely.contains_xy(poly, sfd.lng.to_numpy(float), sfd.lat.to_numpy(float)).sum())
    L += [f"- Isócrona de 10 min do pino: base de concorrentes {dentro.rede.value_counts().to_dict()}; Smart Fit válidas do painel dentro: {sf_in}.",
          "- Distância do pino (km): " + "; ".join(f"{r.nome} {hav_km(PIN[0], PIN[1], r.lat, r.lng):.1f}" for _, r in sfd.iterrows()) + ".", ""]
    (AQUI / "resultado_smartfit_formal.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
