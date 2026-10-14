# -*- coding: utf-8 -*-
"""Termometro de praca pela Smart Fit (protocolo_termometro.md v1.0 + emenda v1.1 §10, congelado antes de rodar):
o volume (relativo ao nacional) das Smart Fit vizinhas melhora a previsao fora da amostra da v2 adotada?
Modelo principal: v2 + T (com indicador de ausencia) nas 39 contra a v2 nas 39; LOO nas 39 e teste nas 18 (T do teste
= 12 meses ANTES da inauguracao). Congela tambem a previsao v2 + T da turma de 2026. So' le; grava nesta pasta.
.venv, PYTHONPATH=src."""
import glob
import hashlib
import importlib.util
import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
REPO = UNI.parent.parent.parent
CONC = UNI / "insumos_vps" / "concorrentes_mapeados_2026-09-27.parquet"
TP = UNI / "insumos_vps" / "planos_totalpass.parquet"
PIN = (-3.03514, -59.996833)
_g = glob.glob(str(REPO / "data" / "validacao" / "KPIs_Smart_*.xlsx"))
assert len(_g) == 1, _g
KPI = Path(_g[0])


def mod(nome, p):
    s = importlib.util.spec_from_file_location(nome, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sem_acento(s):
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower().strip()


def norm(s):
    return re.sub(r"[^a-z0-9]", "", re.sub(r"^\s*smart\s*fit\s*[-–]?\s*", "", sem_acento(s)))


def hav_km(la1, lo1, la2, lo2):
    la1, lo1, la2, lo2 = map(np.radians, (la1, lo1, la2, lo2))
    a = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    return 6371.0088 * 2 * np.arcsin(np.sqrt(a))


e2 = mod("e2", UNI / "manaus_volume" / "02_evidencias.py")
ex, alav, X_ = e2.ex, e2.alav, e2.X_


# ------------------------------------------------------------------ Smart Fit
def painel():
    k = pd.read_excel(KPI, sheet_name="Base").drop_duplicates(["Sigla", "Data_Ref"])
    assert k.Sigla.astype(str).str[:3].eq("SBR").all()
    k["uf"] = k.Sigla.astype(str).str[3:5]
    first = k.groupby("Sigla").Data_Ref.min()
    ini = k.Data_Ref.min()
    k["primeiro"] = k.Sigla.map(first)
    meses = (k.Data_Ref.dt.year * 12 + k.Data_Ref.dt.month) - (k.primeiro.dt.year * 12 + k.primeiro.dt.month)
    k["idade"] = np.where(k.primeiro == ini, 999, meses)
    return k, first, ini


def nivel(k, a, b):
    g = k[(k.Data_Ref >= a) & (k.Data_Ref <= b) & (k.idade >= 12) & (k["Alunos Totais SF"] > 0)]
    s = g.groupby("Sigla")["Alunos Totais SF"].agg(["median", "count"])
    s = s[s["count"] >= 6]["median"].astype(float)
    return np.log(s) - np.log(s.median()) if len(s) else s


def crosswalk(k):
    hexuf = pd.concat([pd.read_parquet(p, columns=["hex_id", "uf"]) for p in sorted((REPO / "data" / "staging" / "brasil").glob("uf=*/hexagonos.parquet"))])
    hexuf = hexuf.drop_duplicates("hex_id").set_index("hex_id").uf
    ult = k.sort_values("Data_Ref").groupby("Sigla").tail(1).set_index("Sigla")
    kk = ult.Nome.map(norm) + "|" + ult.uf
    c = pd.read_parquet(CONC)
    c = c[c.rede.eq("smart_fit") & c.status_registro.eq("valido")].copy()
    c["uf"] = c.hex_id_res7.map(hexuf)
    c["chave"] = c.nome_unidade.map(norm) + "|" + c.uf.fillna("??")
    dk, dc = set(kk[kk.duplicated(keep=False)]), set(c.chave[c.chave.duplicated(keep=False)])
    cc = c[~c.chave.isin(dc)].set_index("chave")
    ok = kk.isin(cc.index) & ~kk.isin(dk)
    X = pd.DataFrame({"lat": kk[ok].map(cc.lat), "lng": kk[ok].map(cc.lng)})
    # trava contra o crosswalk do TotalPass
    tp = pd.read_parquet(TP)
    tp = tp[tp.nome.astype(str).map(lambda s: bool(re.match(r"^\s*smart\s*fit", sem_acento(s))))].copy()
    tp["chave"] = tp.nome.map(norm) + "|" + tp.uf
    tp = tp[~tp.chave.duplicated(keep=False)].set_index("chave")
    com = kk[ok & kk.isin(tp.index)]
    dist = hav_km(X.loc[com.index].lat.to_numpy(float), X.loc[com.index].lng.to_numpy(float), com.map(tp.lat).to_numpy(float), com.map(tp.lng).to_numpy(float))
    frac_longe = float((dist > 1.0).mean()) if len(dist) else 0.0
    assert frac_longe <= 0.02, f"TRAVA §10.1: {frac_longe:.1%} dos casados nos dois crosswalks a > 1 km"
    base_all = c[["lat", "lng"]].to_numpy(float)
    info = dict(painel=len(ult), casadas=int(ok.sum()), sem_uf_base=int(c.uf.isna().sum()), comum_tp=len(com), frac_longe=frac_longe)
    return X, base_all, info


def termo(lat, lng, rel, X, base_all, first, ini, modo="T5", antes=None, cobertura=True):
    """Media do log relativo das Smart Fit casadas com nivel na janela, perto do ponto. NaN se nao houver ou se a
    cobertura de casamento a 5 km for < 50%."""
    if not (np.isfinite(lat) and np.isfinite(lng)):
        return np.nan, 0, "sem coordenada"
    if cobertura:
        nb = int((hav_km(lat, lng, base_all[:, 0], base_all[:, 1]) <= 5.0).sum())
        nm = int((hav_km(lat, lng, X.lat.to_numpy(float), X.lng.to_numpy(float)) <= 5.0).sum())
        if nb > 0 and nm / nb < 0.5:
            return np.nan, 0, "cobertura < 50%"
    S = X[X.index.isin(rel.index)]
    if antes is not None:
        fs = first.reindex(S.index)
        S = S[(fs < antes) & ((fs > ini) | (antes > ini))]
    if not len(S):
        return np.nan, 0, "sem Smart Fit"
    dk = hav_km(lat, lng, S.lat.to_numpy(float), S.lng.to_numpy(float))
    r = rel.reindex(S.index).to_numpy(float)
    if modo == "T3":
        o = np.argsort(dk)[:3]; o = o[dk[o] <= 15.0]
    else:
        o = np.nonzero(dk <= (10.0 if modo == "T10" else 5.0))[0]
    return (float(r[o].mean()), len(o), "ok") if len(o) else (np.nan, 0, "sem Smart Fit no raio")


# ------------------------------------------------------------------ Ultra
def bases(f, d):
    tr, DUM = e2.base_treino(f, d)
    A = alav.atributos_ext(d)
    A["l_renda_dom"] = np.log(e2.renda_dom(d))
    mid = pd.read_csv(UNI / "alavancas" / "master_id_cadastro.csv", sep=";", dtype=str)
    A["master_id"] = d.cod_cadastro.map(mid.assign(c=mid.cod_cadastro.str.zfill(2)).set_index("c").master_id).reindex(A.index)
    Y25, Y26 = ex.desfechos(f, "2025-01", "2025-12"), ex.desfechos(f, "2026-01", "2026-08")
    t2 = pd.read_csv(UNI / "uni02" / "confirmacao_por_unidade.csv", sep=";", encoding="utf-8-sig", index_col=0)
    te = A.drop(columns=["l_m2"]).join(np.log(t2.m2).rename("l_m2")).join(Y26, how="inner").loc[t2.index]
    proprios = [c[3:] for c in DUM if c != "mr_outras"]

    def dummies(D):
        for m in proprios:
            D[f"mr_{m}"] = (D.master_id == m).astype(float)
        D["mr_outras"] = (~D.master_id.isin(["M1"] + proprios)).astype(float)
        return D
    te = dummies(te)
    amb = tr.index.intersection(Y26.index)
    cal = {y: float(np.median(Y26.loc[amb, y] - Y25.loc[amb, y])) for y in ("l_fat", "l_ativos")}
    return tr, te, DUM, cal, A, dummies


def ajustar(D, cols, y):
    X = X_(D, cols); yv = D[y].to_numpy(float)
    b, e, h, XtXi = ex.ols(yv, X)
    assert h.max() < 1 - 1e-9, f"alavancagem 1 em {cols}"
    return b, ex.se_hc3(X, e, h, XtXi), e / (1 - h), e, h


def et(r):
    return float(np.median(np.abs(np.exp(r) - 1)))


def main():
    rng = np.random.default_rng(20260930)
    f, d = ex.carregar()
    tr, te, DUM, cal, A, dummies = bases(f, d)
    assert len(tr) == 39 and len(te) == 18 and "mr_M3" in DUM
    V2 = ["l_m2", "l_renda_dom", "l_pop"] + DUM + ["studios"]
    assert te[V2].notna().all().all()
    k, first, ini = painel()
    X, base_all, info = crosswalk(k)
    rel25 = nivel(k, pd.Timestamp("2025-01-01"), pd.Timestamp("2025-12-31"))
    temdesf = int(k[k.Data_Ref.dt.year == 2025].groupby("Sigla")["Alunos Totais SF"].count().ge(6).sum())
    L = ["# Termômetro de praça pela Smart Fit (protocolo v1.0 + emenda v1.1)", "",
         f"Insumos: painel `{KPI.name}` (SHA `{sha(KPI)[:12]}…`), base da VPS `{CONC.name}` (SHA `{sha(CONC)[:12]}…`).",
         f"Casamento nome + UF: {info['casadas']} de {info['painel']} Smart Fit do painel ({100 * info['casadas'] / info['painel']:.0f}%; "
         f"{temdesf} têm ≥ 6 meses em 2025). Smart Fit da base sem UF pelo hexágono: {info['sem_uf_base']}. Trava contra o TotalPass: "
         f"{info['comum_tp']} casadas nos dois, {100 * info['frac_longe']:.1f}% a > 1 km (limite 2%).",
         f"Nível 2025 (meses com idade ≥ 12, ≥ 6 meses): {len(rel25)} Smart Fit; mediana nacional = referência do termômetro relativo.", ""]

    # --- termometros
    def ultra_T(D, janela, modo="T5", pre=False, cob=True):
        out, mot = [], []
        for u in D.index:
            la, lo = float(d.lat.get(u, np.nan)), float(d.lng.get(u, np.nan))
            ina = d.inauguracao.get(u)
            if janela == "2025":
                rel = rel25
            else:
                if pd.isna(ina) or bool(d.get("flag_inauguracao_placeholder", pd.Series(dtype=bool)).get(u, False)):
                    out.append(np.nan); mot.append("inauguração indisponível"); continue
                ina = pd.Timestamp(ina); rel = nivel(k, ina - pd.DateOffset(months=12), ina - pd.Timedelta(days=1))
            t, n, m = termo(la, lo, rel, X, base_all, first, ini, modo, antes=(pd.Timestamp(ina) if pre and pd.notna(ina) else None), cobertura=cob)
            out.append(t); mot.append(m)
        return pd.Series(out, index=D.index), pd.Series(mot, index=D.index)
    tr["T"], mot_tr = ultra_T(tr, "2025"); te["T"], mot_te = ultra_T(te, "pre")
    conf = d.get("confianca_coord", pd.Series(dtype=object))
    L += [f"Cobertura T5: treino {int(tr['T'].notna().sum())}/39 ({mot_tr.value_counts().to_dict()}); teste {int(te['T'].notna().sum())}/18 "
          f"({mot_te.value_counts().to_dict()}). Coordenada de baixa confiança: treino {int(conf.reindex(tr.index).isin(['baixa', 'nenhuma']).sum())}, "
          f"teste {int(conf.reindex(te.index).isin(['baixa', 'nenhuma']).sum())}.", ""]

    def montar(D, col, mT):
        D = D.copy(); D["Tf"] = D[col].fillna(mT); D["semT"] = D[col].isna().astype(float); return D

    # --- modelo principal
    mT = float(tr["T"].mean())
    trP, teP = montar(tr, "T", mT), montar(te, "T", mT)
    C1 = V2 + ["Tf"] + (["semT"] if trP.semT.sum() >= 3 else [])
    res = {}
    for y in ("l_fat", "l_ativos"):
        b0, s0, l0, _, _ = ajustar(trP, V2, y); b1, s1, l1, _, _ = ajustar(trP, C1, y)
        t0 = teP[y].to_numpy(float) - (X_(teP, V2) @ b0 + cal[y]); t1 = teP[y].to_numpy(float) - (X_(teP, C1) @ b1 + cal[y])
        res[y] = dict(b0=b0, b1=b1, s1=s1, l0=l0, l1=l1, t0=t0, t1=t1)
    R = res["l_fat"]
    r2v2 = float(ex.r2_loo(trP.l_fat.to_numpy(float), *ex.ols(trP.l_fat.to_numpy(float), X_(trP, V2))[1:3]))
    assert abs(r2v2 - 0.264) <= 0.005 and abs(et(R["t0"]) - 0.221) <= 0.003, (r2v2, et(R["t0"]))
    j = C1.index("Tf") + 1
    df_ = len(trP) - len(C1) - 1; tq = stats.t.ppf(0.95, df_)
    cb, cs = float(R["b1"][j]), float(R["s1"][j]); lo, hi = cb - tq * cs, cb + tq * cs
    dl = et(R["l0"]) - et(R["l1"]); dt = et(R["t0"]) - et(R["t1"])
    bs = []
    for _ in range(2000):
        ii = rng.integers(0, len(trP), len(trP)); bs.append(et(R["l0"][ii]) - et(R["l1"][ii]))
    bl, bh = np.quantile(bs, [.05, .95])
    kmelhor = int((np.abs(R["t1"]) < np.abs(R["t0"])).sum())
    # leave-one-metro-out
    met = d.iso_metro.reindex(trP.index)
    lomo = {0: [], 1: []}
    for m in met.dropna().unique():
        fora = (met == m).to_numpy()
        for kx, cols in ((0, V2), (1, C1)):
            bb = np.linalg.lstsq(X_(trP[~fora], cols), trP.l_fat.to_numpy(float)[~fora], rcond=None)[0]
            lomo[kx] += list(trP.l_fat.to_numpy(float)[fora] - X_(trP[fora], cols) @ bb)
    larg = lambda r: float(np.exp(np.quantile(r, .9)) - np.exp(np.quantile(r, .1)))
    c1, c2, c3 = lo > 0, dl >= 0.02, dt >= 0.02
    v = "MELHORA A PRECISÃO" if (c1 and c2 and c3) else ("CANDIDATA" if (c1 and dl >= 0) else "NÃO MELHORA")
    sem_tr, sem_te = trP.semT.to_numpy() == 1, teP.semT.to_numpy() == 1
    L += ["## Resultado principal (faturamento, v2 + T5 com indicador de ausência, nas 39 / 18)", "",
          f"Reprodução da v2: R² LOO {r2v2:.3f}, erro no teste {100 * et(R['t0']):.1f}% ✓.",
          f"- Coeficiente de T: **{cb:+.3f}** (IC 90% t, gl {df_}: {lo:+.3f} a {hi:+.3f}) — cada +10% de alunos na Smart Fit vizinha (relativo ao nacional) ≈ {100 * (1.1 ** cb - 1):+.1f}% no faturamento.",
          f"- Erro típico LOO: v2 {100 * et(R['l0']):.1f}% → v2+T {100 * et(R['l1']):.1f}% (queda {100 * dl:+.1f} pp; IC 90% bootstrap pareado {100 * bl:+.1f} a {100 * bh:+.1f} pp). "
          f"R² LOO {r2v2:.3f} → {float(1 - np.sum(R['l1'] ** 2) / np.sum((trP.l_fat - trP.l_fat.mean()) ** 2)):.3f}.",
          f"- Teste (18, T de antes da abertura): erro típico v2 {100 * et(R['t0']):.1f}% → v2+T {100 * et(R['t1']):.1f}% (queda {100 * dt:+.1f} pp); "
          f"viés {100 * np.median(np.exp(R['t0']) - 1):+.1f}% → {100 * np.median(np.exp(R['t1']) - 1):+.1f}%; {kmelhor} de 18 com |erro| menor; "
          f"Spearman {stats.spearmanr(X_(teP, V2) @ R['b0'], teP.l_fat)[0]:+.2f} → {stats.spearmanr(X_(teP, C1) @ R['b1'], teP.l_fat)[0]:+.2f}.",
          f"- Leave-one-metro-out (relatado): {100 * et(np.array(lomo[0])):.1f}% → {100 * et(np.array(lomo[1])):.1f}%. "
          f"Largura da faixa de 80% (LOO): {100 * larg(R['l0']):.0f} → {100 * larg(R['l1']):.0f} pontos percentuais.",
          f"- v2 nas unidades sem T: LOO {100 * et(R['l0'][sem_tr]) if sem_tr.any() else float('nan'):.1f}% (n={int(sem_tr.sum())}); "
          f"teste {100 * et(R['t0'][sem_te]) if sem_te.any() else float('nan'):.1f}% (n={int(sem_te.sum())}).",
          f"- Ativos (secundário): coeficiente {float(res['l_ativos']['b1'][j]):+.3f}; erro LOO {100 * et(res['l_ativos']['l0']):.1f}% → {100 * et(res['l_ativos']['l1']):.1f}%; "
          f"teste {100 * et(res['l_ativos']['t0']):.1f}% → {100 * et(res['l_ativos']['t1']):.1f}%.", "",
          f"Critério: c1 {'sim' if c1 else 'não'}; c2 (≥ 2 pp no LOO) {'sim' if c2 else 'não'}; c3 (≥ 2 pp no teste) {'sim' if c3 else 'não'}. → **{v}**."
          + (" Coeficiente negativo significativo: sinal de DISPUTA (relatado à parte)." if hi < 0 else ""), ""]

    # --- sensibilidades (descritivas)
    L += ["## Sensibilidades (descritivas; não mudam o veredito)", "", "| versão | cobertura treino/teste | coef. T | erro LOO v2 → v2+T | erro teste v2 → v2+T |", "|---|---|---|---|---|"]

    def sens(rot, Ttr, Tte, extra=None):
        a, b_ = tr.copy(), te.copy(); a["T"], b_["T"] = Ttr, Tte
        mt = float(a["T"].mean()); a, b_ = montar(a, "T", mt), montar(b_, "T", mt)
        cols = V2 + ["Tf"] + (["semT"] if a.semT.sum() >= 3 else []) + (extra or [])
        base_cols = V2 + (extra or [])
        try:
            p0, _, q0, _, _ = ajustar(a, base_cols, "l_fat"); p1, _, q1, _, _ = ajustar(a, cols, "l_fat")
        except AssertionError as err:
            L.append(f"| {rot} | – | – | {err} | – |"); return
        u0 = b_.l_fat.to_numpy(float) - (X_(b_, base_cols) @ p0 + cal["l_fat"]); u1 = b_.l_fat.to_numpy(float) - (X_(b_, cols) @ p1 + cal["l_fat"])
        L.append(f"| {rot} | {int(a['T'].notna().sum())}/{int(b_['T'].notna().sum())} | {float(p1[cols.index('Tf') + 1]):+.3f} | "
                 f"{100 * et(q0):.1f}% → {100 * et(q1):.1f}% | {100 * et(u0):.1f}% → {100 * et(u1):.1f}% |")
    for modo in ("T10", "T3"):
        sens(modo, ultra_T(tr, "2025", modo)[0], ultra_T(te, "pre", modo)[0])
    sens("T5_pre (só Smart Fit anteriores à Ultra)", ultra_T(tr, "2025", pre=True)[0], ultra_T(te, "pre", pre=True)[0])
    sens("T5 sem a regra de cobertura", ultra_T(tr, "2025", cob=False)[0], ultra_T(te, "pre", cob=False)[0])
    for D in (tr, te):
        D["l_nsf5"] = [np.log1p(int((hav_km(float(d.lat.get(u, np.nan)), float(d.lng.get(u, np.nan)), base_all[:, 0], base_all[:, 1]) <= 5.0).sum())) for u in D.index]
    sens("T5 + controle nº de Smart Fit a 5 km", tr["T"], te["T"], ["l_nsf5"])
    # subconjunto so com T (descritivo), master com < 3 -> outras
    sub = tr[tr["T"].notna()].copy(); subte = te[te["T"].notna()].copy()
    dm = [c for c in DUM if c != "mr_outras" and sub[c].sum() < 3]
    for D in (sub, subte):
        for c in dm:
            D["mr_outras"] = D["mr_outras"] + D[c]
    Vs = [c for c in V2 if c not in dm]
    try:
        p0, _, q0, _, _ = ajustar(sub, Vs, "l_fat"); p1, _, q1, _, _ = ajustar(sub, Vs + ["T"], "l_fat")
        u0 = subte.l_fat.to_numpy(float) - (X_(subte, Vs) @ p0 + cal["l_fat"]); u1 = subte.l_fat.to_numpy(float) - (X_(subte, Vs + ["T"]) @ p1 + cal["l_fat"])
        L.append(f"| só unidades com T (masters < 3 → outras: {dm or 'nenhuma'}) | {len(sub)}/{len(subte)} | {float(p1[-1]):+.3f} | "
                 f"{100 * et(q0):.1f}% → {100 * et(q1):.1f}% | {100 * et(u0):.1f}% → {100 * et(u1):.1f}% |")
    except AssertionError as err:
        L.append(f"| só unidades com T | – | – | {err} | – |")
    L.append("")

    # --- Manaus
    at = json.loads((UNI / "manaus_volume" / "atributos_pino.json").read_text(encoding="utf-8"))["carro_10"]
    tM, nM, mM = termo(PIN[0], PIN[1], rel25, X, base_all, first, ini)
    rel_ant = rel25[rel25.index.isin(first[first <= pd.Timestamp("2023-12-31")].index)]
    tA, nA, _ = termo(PIN[0], PIN[1], rel_ant, X, base_all, first, ini, cobertura=False)
    pct = float((tr["T"].dropna() < tM).mean()) if np.isfinite(tM) else np.nan
    L += ["## Manaus (descritivo)", "",
          f"- T5 do pino (2025): {'%+.2f' % tM if np.isfinite(tM) else 'sem termômetro'} ({nM} Smart Fit; {mM}) = {100 * (np.exp(tM) - 1) if np.isfinite(tM) else float('nan'):+.0f}% "
          f"de alunos contra a Smart Fit mediana do país; percentil no treino {100 * pct:.0f}"
          + (" — **acima do máximo do treino (extrapolação)**" if np.isfinite(tM) and tM > tr['T'].max() else "") + ".",
          f"- Sem a leva de 2024 (só Smart Fit no painel até 2023-12): {'%+.2f' % tA if np.isfinite(tA) else '–'} ({nA} Smart Fit)."]
    rowM = {"l_m2": np.log(2000.0), "l_renda_dom": np.log(at["renda_pc"] * at["pop"] / at["domicilios"]), "l_pop": np.log(at["pop"]), "studios": 1.0,
            "Tf": tM if np.isfinite(tM) else mT, "semT": 0.0 if np.isfinite(tM) else 1.0}
    for y in ("l_fat", "l_ativos"):
        for rot, dmr in (("M3", {**{c: 0.0 for c in DUM}, "mr_M3": 1.0}), ("master média", {c: float(tr[c].mean()) for c in DUM})):
            p0 = float(np.asarray(X_(pd.DataFrame([{**rowM, **dmr}]), V2) @ res[y]["b0"]).ravel()[0])
            p1 = float(np.asarray(X_(pd.DataFrame([{**rowM, **dmr}]), C1) @ res[y]["b1"]).ravel()[0])
            fm = (lambda v: f"R$ {v / 1000:,.0f} mil") if y == "l_fat" else (lambda v: f"{v:,.0f}")
            L.append(f"- {'Faturamento' if y == 'l_fat' else 'Ativos'}, {rot}: v2 {fm(np.exp(p0))} → v2+T {fm(np.exp(p1))} (nível 2025); "
                     f"com calendário 2026: {fm(np.exp(p0 + cal[y]))} → {fm(np.exp(p1 + cal[y]))}.")
    L.append("")

    # --- congelar turma 2026
    pv = pd.read_csv(UNI / "previsao_2026" / "previsoes_turma_2026_v2_domiciliar.csv", sep=";", encoding="utf-8-sig", index_col=0)
    COLM = UNI / "coleta_metragem"
    est = pd.read_csv(COLM / "metragem_estimada_2026-09-29.csv", sep=";", encoding="utf-8-sig", index_col=0).metragem_estimada_m2.dropna()
    of = d.tam_metragem_m2.dropna(); m2 = pd.concat([of, est[~est.index.isin(of.index)]])
    cand = A.reindex(pv.index).drop(columns=["l_m2"]).join(np.log(m2).rename("l_m2"))
    cand["master_id"] = pv.master_id
    cand = dummies(cand)
    cand["T"], mot26 = ultra_T(cand, "pre")
    cand = montar(cand, "T", mT)
    okc = cand[C1].notna().all(axis=1)
    out = pd.DataFrame(index=cand.index)
    out["T5_pre_abertura"] = cand["T"].round(4); out["motivo_T"] = mot26
    for rot, bb, cols in (("v2dom", R["b0"], V2), ("v2T", R["b1"], C1)):
        p = pd.Series(np.nan, index=cand.index); p[okc] = X_(cand[okc], cols) @ bb
        out[f"prev_{rot}_nivel2025"] = np.exp(p).round(0); out[f"prev_{rot}_cal2026"] = np.exp(p + cal["l_fat"]).round(0)
    arq = AQUI / "previsoes_turma_2026_v2T.csv"
    out.to_csv(arq, sep=";", encoding="utf-8-sig")
    L += ["## Turma de 2026 congelada (teste limpo futuro)", "",
          f"`{arq.name}`: {len(out)} unidades, {int(out.T5_pre_abertura.notna().sum())} com termômetro de antes da abertura; SHA-256 `{sha(arq)}`.", ""]
    (AQUI / "resultado_termometro.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
