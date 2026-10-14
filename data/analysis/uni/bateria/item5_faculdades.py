# -*- coding: utf-8 -*-
"""BLK-UNI-10, item 5 (bateria/protocolo_bateria.md §7 + §9.9 + §13-§15 + §16 + §17): faculdade MUITO PROXIMA da unidade.
D500 = 1 se ha' >= 1 CNPJ ATIVO (Receita, set/2026) com CNAE PRINCIPAL de ensino superior (8531-7, 8532-5, 8533-3),
geocodificado por endereco exato ou por CEP (sem CEP de area e sem prefixo), a <= 500 m do pino da unidade, com inicio
ANTES da data de decisao (2025-01-01 no laboratorio e no treino; a inauguracao no teste e na turma). Medida redefinida pelo
Felipe em 05/10, antes de qualquer desfecho (§16): a pergunta e' a faculdade vizinha, nao o volume de faculdades da regiao.
Teste primario no LABORATORIO SMART FIT do item 2 (amostra_lab); p primario = o MAIOR entre as quadriculas (normais e
deslocadas) com G* >= 10 (§17). Na Ultra: efeito descritivo e c2/c3 (contam so' se o laboratorio passar). Turma de 2026
congelada sempre. Nao le dado sensivel.
Uso: item5_faculdades.py --seco | --ensaio | (sem flag = teste; exige REGISTRO_CONGELAMENTO_item5.txt). .venv, PYTHONPATH=src."""
import importlib.util
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds
import pyarrow.parquet as pq
import shapely
from scipy import stats
from sklearn.neighbors import BallTree

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
ROOT = UNI.parent.parent.parent
POI = ROOT / "data" / "staging" / "poi"
BPU = POI / "base_poi_unica"
GEO = ROOT / "data" / "outputs" / "setores_censitarios_2022_geo"  # atributos dos circulos (it2.setores_para_circulos)
HEX = ROOT / "data" / "staging" / "brasil"                          # UF da chave nome + UF do crosswalk (tm.crosswalk)
REG5 = AQUI / "REGISTRO_CONGELAMENTO_item5.txt"
EDU = ["8531700", "8532500", "8533300"]  # o grupo CNAE 85.3 inteiro (unicos codigos 853x da base, conferido)
GRAD = ("8531700", "8532500")            # sensibilidade: sem pos-graduacao/extensao (8533)
ACADEMIA = "9313100"
PRECISO = ("cep_numero", "cep")          # endereco exato ou centroide do CEP; cep_area e cep5 erram mais que o raio
IMPRECISO = ("cep_area", "cep5")
CORTE_LAB = "20250101"
R_T = 6371008.8
R_PRINC = 500
R_INDET = 1500                           # faculdade imprecisa a <= 1,5 km de quem tem D500 = 0 -> "indeterminado"
D_TETO, D_PISO = 3000.0, 50.0            # versao continua: log(3000 / max(d, 50)), teto quando nao ha faculdade a <= 3 km
BILATERAL = True                         # §17: decisao do Felipe (05/10): "aumento ou queda" -> p = 2 x o menor lado
ALFA_MAX_HOLM = 0.05 / 4                 # §17: com os p dos itens 1, 6 e 2 (> 0,05), o item 5 fica no maximo no posto 3


def mod(nome, p):
    s = importlib.util.spec_from_file_location(nome, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


it2 = mod("it2", AQUI / "item2_comodidades.py")  # amostra do laboratorio e inferencia (§14/§15); nao le dado sensivel
op, tm, ex, X_, et, sha = it2.op, it2.tm, it2.ex, it2.X_, it2.et, it2.sha
CNPJ_FILES = sorted(POI.glob("cnpj_ativos_*.parquet"))
INSUMOS5 = (it2.INSUMOS2 + [Path(__file__)] + CNPJ_FILES + sorted(BPU.glob("uf=*/*.parquet"))
            + sorted(GEO.glob("uf=*/cod_municipio=*/*.parquet")) + sorted(HEX.glob("uf=*/hexagonos.parquet")))

# a geometria de cada Smart Fit da amostra so' existe dentro de amostra_lab; ela passa por medir_q, entao guardamos ali
GEOM = {}
_medir_q = it2.medir_q


def _medir_q_e_guardar(P, c, rede):
    GEOM.update(P.geom.to_dict())
    return _medir_q(P, c, rede)


it2.medir_q = _medir_q_e_guardar


# ------------------------------------------------------------------ insumos de POI
def ler_cnpj():
    """Ensino superior (todas as datas; o corte e' por unidade) e filiais com coordenada precisa, SEM ensino superior e SEM
    academias (a propria faculdade e a propria unidade nao entram no controle de centralidade; §17)."""
    E, Fl = [], []
    for f in CNPJ_FILES:
        E.append(pq.read_table(f, columns=["cnae_principal", "data_inicio", "geo_nivel", "cep", "lat", "lng"],
                               filters=[("cnae_principal", "in", EDU)]).to_pandas())
        fl = pq.read_table(f, columns=["cnae_principal", "data_inicio", "geo_nivel", "lat", "lng"],
                           filters=[("matriz_filial", "=", "2"), ("geo_nivel", "in", list(PRECISO))]).to_pandas()
        Fl.append(fl[~fl.cnae_principal.isin(EDU + [ACADEMIA]) & fl.lat.notna() & fl.data_inicio.notna()][["data_inicio", "lat", "lng"]])
    E = pd.concat(E, ignore_index=True)
    E = E[E.geo_nivel.ne("sem_coordenada") & E.lat.notna() & E.lng.notna()].reset_index(drop=True)
    assert E.data_inicio.str.fullmatch(r"\d{8}").all(), "data_inicio fora do formato AAAAMMDD"
    E["cep9"] = E.cep.fillna("").str[-3:].str.match(r"^9\d\d$")  # CEP de grande usuario (campus grande costuma ter)
    return E, pd.concat(Fl, ignore_index=True)


def ler_osm_univ():
    arqs = [str(p) for p in sorted(BPU.glob("uf=*/*.parquet"))]  # a pasta tem um CSV de resumo
    return ds.dataset(arqs, format="parquet").to_table(
        columns=["lat", "lng"], filter=(ds.field("fonte") == "osm") & (ds.field("subcategoria") == "amenity=university")).to_pandas()


def _arvore(Q):
    return BallTree(np.radians(Q[["lat", "lng"]].to_numpy()), metric="haversine")


def _vizinhos(pts, Q, r):
    return _arvore(Q).query_radius(np.radians(pts[["lat", "lng"]].to_numpy()), r=r / R_T, return_distance=True)


def _dmin(pts, cortes, Q, r=D_TETO, mask=None):
    """Distancia (m) ate o ponto mais proximo de Q (com data_inicio < corte, se Q tem data; e com `mask`, se dada)."""
    ind, dist = _vizinhos(pts, Q, r)
    di = Q.data_inicio.to_numpy() if "data_inicio" in Q else None
    out = np.full(len(pts), np.inf)
    for k, (ii, dd, c) in enumerate(zip(ind, dist, cortes)):
        ok = np.ones(len(ii), bool)
        if di is not None and c is not None:
            ok &= di[ii] < c
        if mask is not None:
            ok &= mask[ii]
        if ok.any():
            out[k] = dd[ok].min() * R_T
    return out


def dentro(g, lng, lat):
    x0, y0, x1, y1 = g.bounds
    m = np.nonzero((lng >= x0) & (lng <= x1) & (lat >= y0) & (lat <= y1))[0]
    return m[shapely.contains_xy(g, lng[m], lat[m])] if len(m) else m


def medir(pts, cortes, geoms, E, Fl, O):
    """Por unidade (pino + data de decisao): distancias, binarios de proximidade, indeterminados, controle de centralidade
    local e a contagem original na isocrona (so' referencia)."""
    cortes = list(cortes)
    Ep = E[E.geo_nivel.isin(PRECISO)].reset_index(drop=True)
    Ei = E[E.geo_nivel.isin(IMPRECISO)].reset_index(drop=True)
    R = pd.DataFrame(index=pts.index)
    R["d_edu"] = _dmin(pts, cortes, Ep)
    R["d_exato"] = _dmin(pts, cortes, Ep, mask=Ep.geo_nivel.eq("cep_numero").to_numpy())
    R["d_grad"] = _dmin(pts, cortes, Ep, mask=Ep.cnae_principal.isin(GRAD).to_numpy())
    R["d_todos"] = _dmin(pts, cortes, E)
    R["d_sem_data"] = _dmin(pts, [None] * len(pts), Ep)
    R["d_osm"] = _dmin(pts, [None] * len(pts), O)
    R["d_imprec"] = _dmin(pts, cortes, Ei, r=R_INDET)
    R["d_imprec9"] = _dmin(pts, cortes, Ei, r=R_INDET, mask=Ei.cep9.to_numpy())
    for r in (300, 500, 1000):
        R[f"D{r}"] = (R.d_edu <= r).astype(float)
    for k in ("exato", "grad", "todos", "sem_data", "osm"):
        R[f"D500_{k}"] = (R[f"d_{k}"] <= 500).astype(float)
    R["D500_uniao_osm"] = np.maximum(R.D500, R.D500_osm)
    R["indet"] = ((R.D500 == 0) & (R.d_imprec <= R_INDET)).astype(float)
    R["indet9"] = ((R.D500 == 0) & (R.d_imprec9 <= R_INDET)).astype(float)
    R["prox"] = np.log(D_TETO / np.clip(np.minimum(R.d_edu, D_TETO), D_PISO, None))
    ind, _ = _vizinhos(pts, Fl, R_PRINC); fdt = Fl.data_inicio.to_numpy()
    R["lf500"] = np.log1p([int((fdt[ii] < c).sum()) for ii, c in zip(ind, cortes)])
    elng, elat, edt = E.lng.to_numpy(), E.lat.to_numpy(), E.data_inicio.to_numpy()
    n_iso = []
    for g, c in zip(geoms, cortes):
        shapely.prepare(g); i = dentro(g, elng, elat); n_iso.append(int((edt[i] < c).sum()))
    R["x_iso"] = np.log1p(n_iso)
    return R


# ------------------------------------------------------------------ inferencia
def pdec(r):
    """p de decisao: unilateral (coef > 0) ou bilateral (2 x o menor lado), conforme o §17."""
    return float(min(1.0, 2 * min(r["p"], r["p_oposto"]))) if BILATERAL else float(r["p"])


def lab5(S, cl, xq="D500", cols_extra=(), rng=None, boot=True):
    """y ~ x + l_renda_dom + l_pop + extra + FE de area. it2.preparar_lab chama a candidata de 'Qf' (a medida nunca falta, entao
    nao ha indicador de ausencia). op.wcr devolve (p coef > 0, p coef < 0, t, coef)."""
    S, base, inc = it2.preparar_lab(S, xq, cols_extra)
    assert not inc and S.semQ.sum() == 0, "candidata com ausencia"
    Xm = X_(S, base + ["Qf"]); yv = S.y.to_numpy(float); j = Xm.shape[1] - 1
    op._posto(Xm, f"lab {xq} {cols_extra}")
    b, e, h, XtXi = ex.ols(yv, Xm); assert h.max() < 1 - 1e-9, "alavancagem 1 no laboratorio"
    g = op.regua(S[cl].astype(str)); G = len(np.unique(g))
    out = dict(coef=float(b[j]), n=len(S), G=G, Gst=float(np.nanmin([it2.g_estrela(Xm, j, g, 0.0), it2.g_estrela(Xm, j, g, 1.0)])),
               com=float(S[xq].mean()))
    if boot:
        p_pos, p_neg, t, _ = op.wcr(yv, Xm, j, g, rng)
        out.update(p=float(p_pos), p_oposto=float(p_neg), t=float(t))
        out["pd"] = pdec(out)
    Xb_ = X_(S, base); b0, e0, h0, _ = ex.ols(yv, Xb_); sst = np.sum((yv - yv.mean()) ** 2)
    out["r2loo0"], out["r2loo1"] = float(1 - np.sum((e0 / (1 - h0)) ** 2) / sst), float(1 - np.sum((e / (1 - h)) ** 2) / sst)
    return out


def desenho_ultra5(tr, te, V2, x):
    """Como it2.desenho_ultra, mas com G* = minimo entre rho 0 e rho 1 (§15.1)."""
    S = pd.concat([tr.assign(teste=0.0), te.assign(teste=1.0)]).dropna(subset=["l_fat"])
    C = V2 + ["teste"]; Xb = X_(S, C); Xm = X_(S, C + [x]); yv = S.l_fat.to_numpy(float); j = Xm.shape[1] - 1
    e0 = yv - Xb @ np.linalg.lstsq(Xb, yv, rcond=None)[0]; n, kx = Xm.shape; XtXi = np.linalg.pinv(Xm.T @ Xm)
    g = op.regua(S.cl_metro.astype(str)); G = len(np.unique(g))
    Sg = np.zeros((g.max() + 1, kx)); np.add.at(Sg, g, Xm * e0[:, None])
    V = (G / (G - 1)) * ((n - 1) / (n - kx)) * XtXi @ (Sg.T @ Sg) @ XtXi
    return dict(se_iid=float(np.sqrt(np.sum(e0 ** 2) / (n - Xb.shape[1])) * np.sqrt(XtXi[j, j])), se_cl=float(np.sqrt(V[j, j])), G=G, gl=n - kx,
                Gst=float(np.nanmin([it2.g_estrela(Xm, j, g, 0.0), it2.g_estrela(Xm, j, g, 1.0)])), sem_metro=int(S.metro.isna().sum()))


def pc(b):
    return 100 * (np.exp(b) - 1)


def mde_pc(se, gl, alfa):
    """Efeito detectavel (80%) em %; bilateral usa alfa/2 em cada lado."""
    return pc(it2.mde(se, gl, alfa / 2 if BILATERAL else alfa))


# ------------------------------------------------------------------ principal
def main():
    seco, ensaio = "--seco" in sys.argv, "--ensaio" in sys.argv
    if not seco:
        assert BILATERAL in (True, False), "§17: a direcao (BILATERAL) precisa estar fixada antes de rodar"
    out_dir = AQUI / "ensaio_item5" if ensaio else AQUI
    arq, res = out_dir / "previsoes_turma_2026_v2_F.csv", out_dir / "resultado_item5_faculdades.md"
    if ensaio:
        out_dir.mkdir(exist_ok=True)
        for p in out_dir.iterdir():
            p.unlink()
    if not seco:
        assert not arq.exists() and not res.exists(), "congelamento/resultado do item 5 ja existem"
    if not seco and not ensaio:
        reg = REG5.read_text(encoding="utf-8") if REG5.exists() else ""
        for p in INSUMOS5:
            assert sha(p) in reg, f"TRAVA: {p} nao esta congelado (ou mudou) em {REG5.name}"
    assert sha(op.PV) == op.PV_SHA, "previsao congelada da turma mudou"
    rng = np.random.default_rng(20261005)
    E, Fl = ler_cnpj(); O = ler_osm_univ()
    c = it2.ler_comodidades()
    f, d = ex.carregar()
    S, F = it2.amostra_lab(c, ensaio=ensaio)
    assert set(S.sigla) <= set(GEOM), "geometria do laboratorio nao capturada"
    S = S.join(medir(S.set_index("sigla")[["lat", "lng"]], [CORTE_LAB] * len(S), [GEOM[s] for s in S.sigla], E, Fl, O), on="sigla")
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
    assert not corte.index.duplicated().any(), "unidade em mais de um conjunto"
    assert corte.index.isin(PU.index).all(), f"Ultra sem pino/poligono: {sorted(set(corte.index) - set(PU.index))}"
    MU = medir(PU.loc[corte.index, ["lat", "lng"]], corte.to_numpy(), PU.geom.reindex(corte.index).tolist(), E, Fl, O)
    conf = d.confianca_coord.reindex(corte.index)
    for D in (tr, te):
        for col in MU.columns:
            D[col] = MU[col].reindex(D.index).to_numpy(float)
        D["metro"] = d.iso_metro.reindex(D.index)
        D["cl_metro"] = D.metro.astype(str).where(D.metro.notna(), "u_" + D.index.astype(str))
        D["pino_fraco"] = conf.reindex(D.index).isin(["baixa", "nenhuma"]).to_numpy()
    V2 = ["l_m2", "l_renda_dom", "l_pop"] + DUM + ["studios"]
    if not ensaio:
        _, rt, _ = op.residuos_v2(tr, te, V2, "l_fat", cal["l_fat"])
        r2v2 = float(ex.r2_loo(tr.l_fat.to_numpy(float), *ex.ols(tr.l_fat.to_numpy(float), X_(tr, V2))[1:3]))
        assert abs(r2v2 - 0.264) <= 0.005 and abs(et(rt.to_numpy()) - 0.221) <= 0.003, (r2v2, et(rt.to_numpy()))
    # ---- desenho (sem a medida contra o desfecho): G* em todas as quadriculas, normais e deslocadas (§17)
    DS = {f"{km}{suf}": it2.desenho(S, f"cel{km}{suf}", xq="D500") for km in it2.KMS for suf in ("", "s")}
    VALIDAS = [k for k in DS if DS[k]["Gst"] >= it2.G_MIN]
    ok_km = [km for km in it2.KMS if DS[str(km)]["Gst"] >= it2.G_MIN]
    cl0 = f"cel{max(ok_km)}" if ok_km else f"cel{min(it2.KMS)}"  # grade de referencia das sensibilidades (regra do §15)
    D0 = DS[cl0[3:]]
    cnt = S.metro.value_counts(); big = cnt.index[0]; share = cnt.iloc[0] / len(S)
    SU = pd.concat([tr, te])
    if seco:
        du = desenho_ultra5(tr, te, V2, "D500")
        print(f"CHECAGEM SECA OK item 5 (sem ajuste da medida contra o desfecho). BILATERAL = {BILATERAL}.")
        print(f"  CNPJ de ensino superior com coordenada: {len(E)} ({E.geo_nivel.isin(PRECISO).mean():.0%} exato ou CEP; CEP de grande usuario {int(E.cep9.sum())}, "
              f"{int((E.cep9 & E.geo_nivel.isin(IMPRECISO)).sum())} deles impreciso); filiais precisas sem 853x/9313: {len(Fl):,}; universidades OSM: {len(O)}")
        print(f"  funil do laboratorio: {F}")
        print("  G* com D500 (rho 0 / rho 1 / min): " + "; ".join(f"{k_} km: {v['Gst0']:.1f}/{v['Gst1']:.1f}/{v['Gst']:.1f} (G {v['G']})" for k_, v in DS.items()))
        print(f"  grades validas (G* >= 10): {VALIDAS}; referencia das sensibilidades {cl0}; por area G* {D0['Gst_area']:.1f}; maior area {big} ({100 * share:.0f}% do N)")
        print("  lab, fracao COM: " + ", ".join(f"{k}: {S[k].mean():.1%}" for k in ("D300", "D500", "D1000", "D500_exato", "D500_todos", "D500_grad", "D500_osm", "D500_uniao_osm", "D500_sem_data"))
              + f"; distancia mediana {np.median(np.minimum(S.d_edu, D_TETO)):.0f} m")
        print(f"  lab: indeterminados (D500 = 0 e faculdade imprecisa a <= {R_INDET} m) {int(S.indet.sum())} ({S.indet.mean():.1%}), {int(S.indet9.sum())} com CEP de grande usuario; "
              f"mudam de D500 sem o corte de data: {int((S.D500 != S.D500_sem_data).sum())}")
        Sd, base_d, _ = it2.preparar_lab(S, "D500")
        xv = Sd.D500.to_numpy(float)
        for rot, cols in (("FE + renda + pop", base_d), ("+ filiais a <= 500 m", base_d + ["lf500"])):
            Xd = X_(Sd, cols); xr = xv - Xd @ np.linalg.lstsq(Xd, xv, rcond=None)[0]
            print(f"  R2 de D500 sobre {rot}: {1 - xr.var() / xv.var():.2f}")
        print(f"  corr(D500, .): renda dom {S.D500.corr(S.l_renda_dom):+.2f}; pop {S.D500.corr(S.l_pop):+.2f}; filiais locais {S.D500.corr(S.lf500):+.2f}; "
              f"contagem na isocrona {S.D500.corr(S.x_iso):+.2f}; areas com e sem: {int(S.groupby('metro').D500.agg(lambda z: 0 < z.mean() < 1).sum())} de {S.metro.nunique()}")
        for lado, div in (("unilateral", 1), ("bilateral", 2)):
            for nm, al in (("0,05", .05), ("a/6", op.LIMIAR)):
                print(f"  efeito detectavel no lab (80%, {nm}, {lado}): iid {pc(it2.mde(D0['se_iid'], D0['gl'], al / div)):+.1f}%; "
                      + "; ".join(f"cluster {k} (gl {DS[k]['Gst'] - 1:.0f}) {pc(it2.mde(DS[k]['se_cl'], max(DS[k]['Gst'] - 1, 1), al / div)):+.1f}%" for k in VALIDAS))
        print(f"  Ultra: pinos {int(SU.index.isin(PU.index).sum())}/57, turma {int(pv.index.isin(PU.index).sum())}/16; pino fraco (baixa/nenhuma) {int(SU.pino_fraco.sum())}/57, "
              f"turma {int(conf.reindex(pv.index).isin(['baixa', 'nenhuma']).sum())}/16; inauguracao turma {d.inauguracao_origem.reindex(pv.index).value_counts().to_dict()}")
        print(f"  Ultra com D500: treino {int(tr.D500.sum())}/39, teste {int(te.D500.sum())}/18, turma {int(MU.D500.reindex(pv.index).sum())}/16; indeterminados {int(SU.indet.sum())}/57; "
              f"corr(D500, renda dom) {SU.D500.corr(SU.l_renda_dom):+.2f}, (m2) {SU.D500.corr(SU.l_m2):+.2f}, (estudios) {SU.D500.corr(SU.studios):+.2f}, (filiais) {SU.D500.corr(SU.lf500):+.2f}")
        print(f"  Ultra, detectavel (80%, 0,05): iid {mde_pc(du['se_iid'], du['gl'], .05):+.1f}% / cluster {mde_pc(du['se_cl'], max(du['Gst'] - 1, 1), .05):+.1f}% "
              f"(G* min por metro {du['Gst']:.1f}, G {du['G']})")
        return
    # ---------------- teste
    if not VALIDAS:
        P = dict(pd=1.0, coef=np.nan, nota=f"G* < {it2.G_MIN} em todas as quadrículas: o laboratório não dá p (p = 1)")
        PV_ = {}
    else:
        PV_ = {k: lab5(S, f"cel{k}", rng=rng) for k in VALIDAS}
        kmax = max(PV_, key=lambda k: PV_[k]["pd"])
        P = dict(PV_[cl0[3:]] if cl0[3:] in PV_ else PV_[kmax]); P["pd"] = PV_[kmax]["pd"]
        P["nota"] = (f"p primário = o maior entre as quadrículas com G* ≥ 10 ({', '.join(VALIDAS)} km; 's' = deslocada), "
                     f"que é o da {kmax} km (§17)")
    sem_big = lab5(S[S.metro != big], cl0, rng=rng)
    com_fil = lab5(S, cl0, cols_extra=("lf500",), rng=rng)
    rob = lambda r: np.isfinite(P.get("coef", np.nan)) and np.sign(r["coef"]) == np.sign(P["coef"]) and abs(r["coef"]) >= 0.5 * abs(P["coef"])
    pp = P["pd"]
    if not VALIDAS:
        c1 = "não testável (G* < 10); entra no Holm com p = 1"
    elif pp <= op.LIMIAR:
        c1 = "significativo"
    elif pp <= ALFA_MAX_HOLM:
        c1 = "pendente (Holm no fechamento)"
    elif pp <= 0.05:
        c1 = "não significativo após Holm (com os itens 1, 6 e 2, o limiar máximo do item 5 é α/4 = 0,0125)"
    else:
        c1 = "não significativo"
    if c1 in ("significativo", "pendente (Holm no fechamento)") and not rob(sem_big):
        c1 = "frágil à dependência espacial (não resiste sem a maior área); entra no Holm com p = 1"
    elif c1 in ("significativo", "pendente (Holm no fechamento)") and not rob(com_fil):
        c1 = "confundido com CENTRALIDADE local (não resiste ao controle de filiais a ≤ 500 m); entra no Holm com p = 1"
    lab_passa = c1 == "significativo" or c1.startswith("pendente")
    lado = "bilateral" if BILATERAL else "unilateral, coef > 0"
    L = ["# BLK-UNI-10, item 5 — faculdade muito próxima (protocolo da bateria §9.9 + §15 + §16 + §17, congelado antes de rodar)", "",
         "D500 = 1 se há pelo menos um CNPJ ativo com CNAE principal de ensino superior (8531-7, 8532-5, 8533-3), com endereço exato ou "
         "por CEP, a até 500 m do pino da unidade, com início antes da data de decisão (01/01/2025 no laboratório e no treino; a "
         "inauguração no teste e na turma). Receita Federal, set/2026: só CNPJ ativo hoje.", "",
         f"## Laboratório Smart Fit (teste primário; {lado})", "",
         f"- Funil: {F}.",
         f"- Áreas de comparação: {S.metro.nunique()} ({int(S.dentro_metro.sum())} unidades em metrô, {int((~S.dentro_metro).sum())} em município); "
         f"isócrona real {int((S.geom_tipo == 'isocrona').sum())}, círculo {int((S.geom_tipo == 'circulo').sum())}. Maior área com {100 * share:.0f}% do N.",
         f"- Com faculdade a ≤ 500 m: {S.D500.mean():.0%} das unidades ({int(S.D500.sum())} de {len(S)}); indeterminadas (sem faculdade precisa a ≤ 500 m, "
         f"mas com faculdade imprecisa a ≤ {R_INDET / 1000:.1f} km): {int(S.indet.sum())}.".replace("1.5 km", "1,5 km"),
         "- G* (mínimo entre ρ 0 e ρ 1): " + "; ".join(f"{k_} km {v['Gst']:.1f}" for k_, v in DS.items()) + f". {P['nota']}."]
    if np.isfinite(P.get("coef", np.nan)):
        L += [f"- Coeficiente de D500: **{P['coef']:+.3f}** → **{pc(P['coef']):+.1f}% de alunos** com faculdade a ≤ 500 m, contra sem; n = {P['n']}.",
              f"- **p de decisão ({lado}; wild cluster bootstrap restrito, Webb, B = {it2.B_BOOT}): {pp:.4f}.** Por quadrícula: "
              + "; ".join(f"{k} km p(coef > 0) {r['p']:.4f}, p(coef < 0) {r['p_oposto']:.4f}" for k, r in PV_.items())
              + f". R² LOO com efeito fixo: {P['r2loo0']:.3f} → {P['r2loo1']:.3f}.",
              f"- Robustez (§16.5): sem a maior área {sem_big['coef']:+.3f} ({'resiste' if rob(sem_big) else 'NÃO resiste'}); com log(1 + filiais "
              f"a ≤ 500 m) {com_fil['coef']:+.3f} ({'resiste' if rob(com_fil) else 'NÃO resiste'})."]
    L += [f"- c1: **{c1}**.", "", f"## Sensibilidades do laboratório (descritivas; cluster {cl0[3:]} km)", "",
          "| versão | n | com | coef. | efeito | p (coef > 0) | p (coef < 0) | G* |", "|---|---|---|---|---|---|---|---|"]

    def sl(rot, r, efeito=True):
        ef = f"{pc(r['coef']):+.1f}%" if efeito else "—"
        com = f"{100 * r['com']:.0f}%" if efeito else "—"
        L.append(f"| {rot} | {r['n']} | {com} | {r['coef']:+.3f} | {ef} | {r['p']:.4f} | {r['p_oposto']:.4f} | {r['Gst']:.1f} |")
    sl(f"sem a maior área ({big}) — obrigatória", sem_big)
    sl("controle: log(1 + filiais de CNPJ a ≤ 500 m, sem ensino superior e sem academia) — obrigatória", com_fil)
    sl(f"sem as indeterminadas ({int(S.indet.sum())})", lab5(S[S.indet == 0], cl0, rng=rng))
    sl("CNPJ ou universidade do OSM a ≤ 500 m (união)", lab5(S, cl0, xq="D500_uniao_osm", rng=rng))
    sl("a ≤ 300 m", lab5(S, cl0, xq="D300", rng=rng))
    sl("a ≤ 1 km", lab5(S, cl0, xq="D1000", rng=rng))
    sl("distância contínua: log(3 km / distância), piso 50 m (por +1)", lab5(S, cl0, xq="prox", rng=rng), efeito=False)
    sl("só endereço exato (CEP + número)", lab5(S, cl0, xq="D500_exato", rng=rng))
    sl("todo nível com coordenada", lab5(S, cl0, xq="D500_todos", rng=rng))
    sl("só graduação (8531 + 8532)", lab5(S, cl0, xq="D500_grad", rng=rng))
    sl("universidade mapeada no OSM (foto set/2026, sem data)", lab5(S, cl0, xq="D500_osm", rng=rng))
    sl("referência: contagem na isócrona de 10 min, log(1 + n) (medida original, G* < 10)", lab5(S, cl0, xq="x_iso", rng=rng), efeito=False)
    for k_ in DS:
        if k_ not in PV_ and f"cel{k_}" != cl0:
            sl(f"cluster = quadrícula de {k_[:-1] + ' km deslocada' if k_.endswith('s') else k_ + ' km'} (G* < 10)", lab5(S, f"cel{k_}", rng=rng))
    sl("cluster = área (metrô ou município)", lab5(S, "metro", rng=rng))
    sl("só isócronas reais (sem círculos)", lab5(S[S.geom_tipo == "isocrona"], cl0, rng=rng))
    sl("só dentro das áreas metropolitanas", lab5(S[S.dentro_metro], cl0, rng=rng))
    Sx = S.assign(idade_12_23=((S.idade_m >= 12) & (S.idade_m <= 23)).astype(float))
    sl("controles de idade (12–23 meses) e franquia", lab5(Sx, cl0, cols_extra=("idade_12_23", "franquia"), rng=rng))
    if np.isfinite(P.get("coef", np.nan)):
        lomo = {m: lab5(S[S.metro != m], cl0, rng=rng, boot=False)["coef"] for m in cnt.index[cnt >= 20]}
        L += ["", "Tirando uma área com ≥ 20 unidades por vez (coeficiente): " + ", ".join(f"sem {m}: {v:+.3f}" for m, v in lomo.items())
              + f". Mesmo sinal em {sum(np.sign(v) == np.sign(P['coef']) for v in lomo.values())} de {len(lomo)}.", ""]
    # ---------------- Ultra
    Ue = op.empilhado(tr, te, V2, "D500", "l_fat", rng, cl="cl_metro")
    trq, teq = tr.assign(Q=-tr.d_edu.clip(upper=D_TETO)), te.assign(Q=-te.d_edu.clip(upper=D_TETO))  # it2.c2c3 corta pela coluna Q: acima da mediana = mais perto
    Mx = it2.c2c3(trq, teq, V2, ["D500"], "l_fat", cal["l_fat"], rng)
    c2, c3, c3r = Mx["dl"] >= 0.02, Mx["dt"] >= 0.02, Mx["dt_rec"] >= 0.02
    coerente = np.isfinite(P.get("coef", np.nan)) and np.sign(Mx["coef"]) == np.sign(P["coef"])
    alvo = ("MELHORA A PRECISÃO" if (c2 and c3 and c3r and coerente) else
            ("CANDIDATA (o c3 só passa por nível)" if (c2 and c3 and coerente) else ("CANDIDATA" if (Mx["dl"] >= 0 and coerente) else "NÃO MELHORA")))
    sentido = ("aumenta" if P.get("coef", 0) > 0 else "reduz")
    if c1 == "significativo":
        v = f"{alvo} (faculdade a ≤ 500 m {sentido} alunos no laboratório)"
    elif c1.startswith("pendente"):
        v = "PENDENTE DO HOLM — se c1 passar: " + alvo.lower()
    elif c1.startswith("frágil") or c1.startswith("confundido"):
        v = c1.split(";")[0].upper()
    elif c1.startswith("não testável"):
        v = "NÃO TESTÁVEL no laboratório (G* < 10; entra no Holm com p = 1)"
    elif c1.startswith("não significativo após Holm"):
        v = f"NÃO DEMONSTRADO após Holm (p {pp:.4f} > 0,0125)"
    else:
        v = "NÃO DEMONSTRADO no laboratório (não vai à Ultra)" + (" — efeito na direção OPOSTA (descritivo)" if (not BILATERAL and P.get("p_oposto", 1) <= 0.05) else "")
    L += ["## Ultra (57 unidades, pinos corrigidos)", "",
          f"- Com faculdade a ≤ 500 m: treino {int(tr.D500.sum())} de 39, teste {int(te.D500.sum())} de 18; indeterminadas {int(SU.indet.sum())}.",
          f"- Efeito de D500 (empilhado, cluster por metrô; descritivo): {Ue['coef']:+.3f} → {pc(Ue['coef']):+.1f}% de faturamento; p (coef > 0) {Ue['p']:.4f}, "
          f"p (coef < 0) {Ue['p_neg']:.4f}; HC3 IC 90% {pc(Ue['lo']):+.1f}% a {pc(Ue['hi']):+.1f}%.",
          f"- Pinos de confiança baixa ou nenhuma nas 57: {int(SU.pino_fraco.sum())} (a sensibilidade sem eles coincide com o principal).",
          f"- c2/c3 (v2 contra v2 + D500; {'CONTAM' if lab_passa else 'só relatados, o laboratório não passou'}): coeficiente nas 39 {Mx['coef']:+.3f} "
          f"(IC 90% {Mx['lo']:+.3f} a {Mx['hi']:+.3f}){'' if coerente else ' — sinal diferente do laboratório'}; estúdios {Mx['studios0']:+.3f} → {Mx['studios1']:+.3f}.",
          f"  LOO {100 * Mx['e_l0']:.1f}% → {100 * Mx['e_l1']:.1f}% (queda {100 * Mx['dl']:+.1f} pp; IC 90% {100 * Mx['ic_dl'][0]:+.1f} a {100 * Mx['ic_dl'][1]:+.1f}); "
          f"teste {100 * Mx['e_t0']:.1f}% → {100 * Mx['e_t1']:.1f}% (queda {100 * Mx['dt']:+.1f} pp; IC 90% {100 * Mx['ic_dt'][0]:+.1f} a {100 * Mx['ic_dt'][1]:+.1f}; "
          f"{Mx['k18']} de {Mx['n_te']} melhoram; recentrado {100 * Mx['dt_rec']:+.1f} pp); viés {100 * Mx['vies0']:+.1f}% → {100 * Mx['vies1']:+.1f}%; "
          f"deslocamento {100 * Mx['desloc']:+.1f}%; queda nas mais perto de faculdade {100 * Mx['dt_alto']:+.1f} pp, nas mais longe {100 * Mx['dt_baixo']:+.1f} pp.", "",
          f"**Veredito do item 5: {v}.**", ""]
    # ---------------- turma 2026 (congela sempre)
    est = pd.read_csv(op.MET, sep=";", encoding="utf-8-sig", index_col=0).metragem_estimada_m2.dropna()
    of = d.tam_metragem_m2.dropna(); m2 = pd.concat([of, est[~est.index.isin(of.index)]])
    cand = A.reindex(pv.index).drop(columns=["l_m2"]).join(np.log(m2).rename("l_m2"))
    cand["master_id"] = pv.master_id
    cand = dummies(cand)
    cand["D500"] = MU.D500.reindex(cand.index)
    me = float(SU.D500.mean()); g = Ue["coef"]
    out = pd.DataFrame(index=pv.index)
    out["dist_faculdade_m"] = MU.d_edu.reindex(pv.index).clip(upper=D_TETO).round(0)
    out["D500"] = cand.D500
    out["indeterminada"] = MU.indet.reindex(pv.index)
    out["prev_v2dom_cal2026"] = pv.prev_v2dom_cal2026
    out["prev_v2dom_x_F"] = (pv.prev_v2dom_cal2026 * np.exp(g * (cand.D500 - me))).round(0)
    out["prev_v2dom_mesmo_nivel"] = (pv.prev_v2dom_cal2026 * np.exp(g * (cand.D500.mean() - me))).round(0)
    okm = cand[V2 + ["D500"]].notna().all(axis=1)
    p_c = pd.Series(np.nan, index=cand.index); p_c[okm] = np.exp(X_(cand[okm], V2 + ["D500"]) @ Mx["b1"] + cal["l_fat"])
    out["prev_v2_F_39_cal2026"] = p_c.round(0)
    out.to_csv(arq, sep=";", encoding="utf-8-sig")
    h = sha(arq)
    with (out_dir / REG5.name).open("a", encoding="utf-8") as fh:
        fh.write(f"Turma 2026 congelada pelo item 5 em {datetime.now():%Y-%m-%d %H:%M} (gamma D500 Ultra {g:+.4f}; media D500 {me:.4f}; "
                 f"lab: coef {P.get('coef', np.nan):+.4f}, p de decisao {pp:.4f}, grades {VALIDAS}, BILATERAL {BILATERAL}): {h} *{arq.name}\n")
    L += ["## Turma de 2026 congelada", "", f"`{arq.name}`: {len(out)} unidades, {int(out.D500.sum())} com faculdade a ≤ 500 m; γ̂ (Ultra) = {g:+.3f}. SHA-256 `{h}`.",
          "Conferência (§17): junto com o BLK-UNI-12, quando ≥ 10 das 16 tiverem 12 meses de vida e ≥ 3 meses válidos. Métrica: a diferença "
          "média do resíduo da v2 congelada entre quem tem e quem não tem faculdade a ≤ 500 m, comparada a γ̂ (o sinal bate? o IC 90% do "
          "contraste cobre γ̂?); a `prev_v2dom_x_F` só conta se o erro típico dela vencer o da `prev_v2dom_mesmo_nivel`.", ""]
    res.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
