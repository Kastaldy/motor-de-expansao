# -*- coding: utf-8 -*-
"""BLK-UNI-13 (protocolo_uni13.md v1.1, 06/10). Parte I: fator para unidade sem agregador (theta_sem) estimado fora do treino,
com estratos e portoes; congelado (para conferencia, nao adotado) nas 5 cegas da turma de 2026. Parte II: masters encolhidas (ridge
one-hot) e mercado de agregador no lugar das masters, contra a v2 (c2/c3 da bateria, Holm alfa 0,05 unilateral).
Modos (um por vez):  --seca | --ensaio | --registrar | --rodar      (.venv, PYTHONPATH=src)
  --seca      contagens por grupo, sem desfecho de faturamento;
  --ensaio    TODOS os desfechos (inclusive a fatia de agregador) trocados por ruido/constante; saida so' no scratchpad;
  --registrar REGISTRO_PRE.txt com SHA do protocolo, do script e dos insumos (recusa sobrescrever);
  --rodar     confere o REGISTRO_PRE, roda de verdade, grava previsoes + resultado + REGISTRO da turma e so' depois os graficos.
Sem Base Consolidada; LOCAL_ so' entra como SHA (nada dele sai daqui)."""
import glob
import hashlib
import importlib.util
import sys
import types
from datetime import datetime
from pathlib import Path

try:
    import h3  # noqa: F401
except ImportError:  # 06/10: o Controle de Aplicativo do Windows bloqueia a DLL do h3; este script nao usa h3
    for _k in [k for k in sys.modules if k == "h3" or k.startswith("h3.")]:
        del sys.modules[_k]
    sys.modules["h3"] = types.ModuleType("h3")

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
REPO = UNI.parent.parent.parent
PROT = AQUI / "protocolo_uni13.md"
REG_PRE = AQUI / "REGISTRO_PRE.txt"
RES = AQUI / "resultado_uni13.md"
PREV_T = AQUI / "previsoes_turma_2026_uni13.csv"
REG_POS = AQUI / "REGISTRO_CONGELAMENTO_turma_2026.txt"
MET_TIME = UNI / "coleta_metragem" / "metragem_time_expansao_2026-10-06.csv"
MET_SAT = UNI / "coleta_metragem" / "metragem_estimada_2026-09-29.csv"
CURVA = UNI / "uni03" / "curva_uni03.csv"
TURMA = UNI / "previsao_2026" / "previsoes_turma_2026.csv"
TURMA_V2 = UNI / "previsao_2026" / "previsoes_turma_2026_v2_domiciliar.csv"
SHA_TURMA = "8f7b216327ddd476f42253f969c0b46fb41b1bf385f86e7c1313ddef87a172dc"
SHA_TURMA_V2 = "999bd027263459ecf2a2eafc914ad832c0e863f2d36d385a23386e37d1ad6df9"
OUT = Path(r"C:\Users\Felipe\OneDrive - Grupo Ultra\Área de Trabalho\Análises - Motor de Expansão\Exploratória BLK-UNI\06 - Fator sem agregador e masters")
ENSAIO = Path(r"C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\9259d0a1-7dda-49bd-a390-c88f3d4ac1a6\scratchpad\uni13_ensaio")
JAN, JAN25 = ("2026-01", "2026-08"), ("2025-01", "2025-12")
CEGAS = ["belford-roxo-rj", "novo-gama-df", "paulinia-sp", "domingos-ferreira-pe", "bonsucesso-rj"]
TRAVADAS_FORA = ["icarai-rj"]
SEED, NB = 20261006, 9999
LAMBDAS = [0, 0.25, 0.5, 1, 2, 4, 8, 16, 32, 64, 1000]
PREMISSAS = (0.47, 0.60)
ALFA = 0.05
plt.rcParams.update({"figure.dpi": 110, "savefig.dpi": 150, "font.size": 9, "axes.grid": True, "grid.alpha": .3})


def mod(nome, p):
    s = importlib.util.spec_from_file_location(nome, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def et(e):
    return float(np.median(np.abs(np.exp(np.asarray(e, float)) - 1)))


def pct(x):
    return 100 * (np.exp(x) - 1)


def insumos():
    kpi = glob.glob(str(REPO / "data" / "validacao" / "KPIs_Smart_*.xlsx"))
    base_ = {"protocolo": PROT, "script": Path(__file__), "fato_unidade_mes": UNI / "fato_unidade_mes.parquet", "dim_unidade": UNI / "dim_unidade.parquet",
             "local_demanda_totalpass": UNI / "LOCAL_demanda_totalpass_por_unidade.parquet",
             "metragem_time": MET_TIME, "metragem_satelite": MET_SAT, "curva_uni03": CURVA, "turma_2026": TURMA, "turma_2026_v2": TURMA_V2,
             "confirmacao_uni02": UNI / "uni02" / "confirmacao_por_unidade.csv", "master_id_cadastro": UNI / "alavancas" / "master_id_cadastro.csv",
             "mod_termometro": UNI / "termometro" / "01_termometro.py", "mod_evidencias": UNI / "manaus_volume" / "02_evidencias.py",
             "mod_alavancas": UNI / "alavancas" / "01_alavancas.py", "mod_incerteza": UNI / "uni07" / "01_incerteza.py",
             "mod_exploracao": UNI / "uni01" / "01_exploracao.py", "mod_confirmacao": UNI / "uni02" / "01_confirmacao.py",
             "mod_comparacao_uni05": UNI / "uni05" / "01_comparacao.py", "mod_premissas_manaus": UNI / "simulacoes" / "manaus_premissas_corrigidas.py",
             "mod_consolidar_metragem": UNI / "coleta_metragem" / "02_consolidar.py",
             "mod_viabilidade_ponto": REPO / "src" / "motor_expansao" / "dimensionamento" / "viabilidade_ponto.py",
             "mod_catchment_batch": REPO / "src" / "motor_expansao" / "dimensionamento" / "catchment_batch.py",
             "conc_mapeados": UNI / "insumos_vps" / "concorrentes_mapeados_2026-09-27.parquet", "planos_totalpass": UNI / "insumos_vps" / "planos_totalpass.parquet"}
    if len(kpi) == 1:
        base_["kpis_smart"] = Path(kpi[0])
    return base_


# ------------------------------------------------------------------ base comum
def base():
    tm = mod("tm", UNI / "termometro" / "01_termometro.py"); ex = tm.ex
    f, d = ex.carregar()
    tr, te, DUM, cal, A, dummies = tm.bases(f, d)
    assert len(tr) == 39 and len(te) == 18 and "mr_M3" in DUM, (len(tr), len(te), DUM)
    V2 = ["l_m2", "l_renda_dom", "l_pop"] + DUM + ["studios"]
    y = tr.l_fat.to_numpy(float)
    b, e, h, _ = ex.ols(y, tm.X_(tr, V2))
    e_te = te.l_fat.to_numpy(float) - (tm.X_(te, V2) @ b + cal["l_fat"])
    r2 = float(ex.r2_loo(y, e, h))
    assert abs(r2 - 0.264) <= 0.005 and abs(et(e_te) - 0.221) <= 0.003, (r2, et(e_te))
    f = f.copy()
    f["AG"] = f.fin_gympass.fillna(0) + f.fin_totalpass.fillna(0)
    f["BAL"] = f.fin_vendas_ux - f.fin_tem_saude.fillna(0)
    # calendario do BALCAO (sensibilidade da parte I): mesma regra do cal['l_fat'] (termometro:146-147), no log do balcao
    def lbal(ini, fim):
        g = f[f.valido & (f.competencia >= ini) & (f.competencia <= fim) & (f.mv >= 12) & (f.BAL > 0)]
        n = g.groupby("unidade_id").size(); g = g[g.unidade_id.isin(n[n >= 3].index)]
        return np.log(g.BAL).groupby(g.unidade_id).mean()
    b25, b26 = lbal(*JAN25), lbal(*JAN)
    amb = tr.index.intersection(b25.index).intersection(b26.index)
    cal_bal = float(np.median(b26[amb] - b25[amb]))
    for D in (tr, te):
        D["mr_M1"] = (D.master_id == "M1").astype(float)
    return dict(tm=tm, ex=ex, f=f, d=d, tr=tr, te=te, DUM=DUM, cal=cal, cal_bal=cal_bal, A=A, dummies=dummies, V2=V2, b=b, r2=r2, et_te=et(e_te))


def metragem(Bs):
    d, te = Bs["d"], Bs["te"]
    mt = pd.read_csv(MET_TIME, sep=";", encoding="utf-8").set_index("unidade_id").metragem_m2.astype(float)
    sat = pd.read_csv(MET_SAT, sep=";", encoding="utf-8-sig", index_col=0).metragem_estimada_m2
    m2 = d.tam_metragem_m2.combine_first(mt).combine_first(sat)
    fonte = pd.Series(np.where(d.tam_metragem_m2.notna(), "oficial", np.where(mt.reindex(d.index).notna(), "time", np.where(sat.reindex(d.index).notna(), "satélite", "sem"))), index=d.index)
    m2.loc[te.index] = np.exp(te.l_m2); fonte.loc[te.index] = "UNI-02"
    return m2, fonte


# ------------------------------------------------------------------ PARTE I
def amostra_I(Bs, com_desfecho=True):
    """Unidades fora do treino, das cegas e das travadas, com atributos, metragem e regra madura/jovem na janela.
    Devolve tambem as elegiveis excluidas e o motivo."""
    f, d, tr, A = Bs["f"], Bs["d"], Bs["tr"], Bs["A"]
    m2, fonte = metragem(Bs)
    cv = pd.read_csv(CURVA, sep=";", encoding="utf-8-sig")
    curva = {s: cv[cv.serie == s].set_index("k").p50 for s in ("faturamento", "pagantes")}
    g = f[f.valido & (f.competencia >= JAN[0]) & (f.competencia <= JAN[1])]
    rows, excl = [], []
    for u in d.index:
        if u in tr.index:
            continue
        gu = g[g.unidade_id == u]
        mad = gu[gu.mv >= 12]; jov = gu[gu.mv.between(6, 11)]
        if len(mad) >= 3:
            regra, M = "madura", mad
        elif len(jov) >= 3:
            regra, M = "jovem", jov
        else:
            if len(gu[gu.mv >= 6]):
                excl.append({"unidade_id": u, "motivo": "menos de 3 meses na regra (madura ou jovem 6-11)"})
            continue
        a = A.loc[u] if u in A.index else None
        if u in CEGAS:
            excl.append({"unidade_id": u, "motivo": "cega da turma de 2026"}); continue
        if u in TRAVADAS_FORA:
            excl.append({"unidade_id": u, "motivo": "travada fora (protocolo v1.1)"}); continue
        if a is None or a[["l_renda_dom", "l_pop", "studios"]].isna().any() or pd.isna(a.get("master_id")):
            excl.append({"unidade_id": u, "motivo": "sem atributo da v2 no cadastro"}); continue
        if pd.isna(m2.get(u)):
            excl.append({"unidade_id": u, "motivo": "sem metragem"}); continue
        fa = float((M.AG > 0).mean()); fw = float((M.fin_gympass.fillna(0) > 0).mean()); ft = float((M.fin_totalpass.fillna(0) > 0).mean())
        aceite = "nenhum" if fa < .5 else ("os dois" if (fw >= .5 and ft >= .5) else "um só")
        r = {"unidade_id": u, "uf": d.uf.get(u), "master_id": a.get("master_id"), "studios": a.get("studios"), "regra": regra, "n_meses": len(M),
             "mv_min": float(M.mv.min()), "mv_max": float(M.mv.max()), "aceite": aceite, "frac_meses_agregador": fa, "m2": float(m2[u]),
             "fonte_m2": fonte[u], "no_teste_18": u in Bs["te"].index}
        if com_desfecho:
            lf = np.log(M.faturamento)
            if regra == "madura":
                y = y_pag = float(lf.mean())
            else:
                mvk = M.mv.astype(int)
                y = float((lf - np.log(mvk.map(curva["faturamento"]))).mean())
                y_pag = float((lf - np.log(mvk.map(curva["pagantes"]))).mean()) if aceite == "nenhum" else y
            ss = M.BAL.sum() + M.AG.sum()
            r.update({"l_real": y, "l_real_curva_pagantes": y_pag, "fatia_agregador": float(M.AG.sum() / ss) if ss > 0 else np.nan})
        rows.append(r)
    S = pd.DataFrame(rows).set_index("unidade_id")
    X = Bs["dummies"](A.loc[S.index].drop(columns=["l_m2"], errors="ignore").assign(l_m2=np.log(S.m2)))
    S["l_prev"] = Bs["tm"].X_(X, Bs["V2"]) @ Bs["b"] + Bs["cal"]["l_fat"]
    pop_min = float(np.exp(Bs["tr"].l_pop.min()))
    S["pop_iso10"] = np.exp(A.loc[S.index, "l_pop"]); S["pop_abaixo_do_treino"] = S.pop_iso10 < pop_min
    return S, pd.DataFrame(excl).drop_duplicates("unidade_id")


def theta_sem(e, grp):
    e, grp = np.asarray(e, float), np.asarray(grp)
    if (grp == "nenhum").sum() == 0 or (grp == "os dois").sum() == 0:
        return np.nan
    return float(np.median(e[grp == "nenhum"]) - np.median(e[grp == "os dois"]))


def parte_I(S, Bs, rng):
    S = S.copy(); S["e"] = S.l_real - S.l_prev; S["e_curva_pagantes"] = S.l_real_curva_pagantes - S.l_prev
    nen, dois = S[S.aceite == "nenhum"], S[S.aceite == "os dois"]
    th = theta_sem(S.e, S.aceite)
    en, ed = nen.e.to_numpy(), dois.e.to_numpy()
    boot = np.array([np.median(rng.choice(en, len(en))) - np.median(rng.choice(ed, len(ed))) for _ in range(NB)])
    amp = (float(np.percentile(boot, 5)), float(np.percentile(boot, 95)))
    ordem = (float(en.min() - np.median(ed)), float(en.max() - np.median(ed)))
    loo = {u: float(np.median(nen.e.drop(u)) - np.median(ed)) for u in nen.index}
    mad, jov = S[S.regra == "madura"], S[S.regra == "jovem"]
    sens = {"maduras": theta_sem(mad.e, mad.aceite), "jovens": theta_sem(jov.e, jov.aceite),
            "curva_pagantes": theta_sem(S.e_curva_pagantes, S.aceite),
            "sem_RJ": theta_sem(S[S.uf != "RJ"].e, S[S.uf != "RJ"].aceite),
            "calendario_balcao": th + (Bs["cal"]["l_fat"] - Bs["cal_bal"])}
    sg = np.sign(th)
    portoes = {"n_nenhum_>=4": len(nen) >= 4,
               "sinal_estavel_tirando_cada": all(np.sign(v) == sg for v in loo.values()),
               "estratos_mesmo_sinal": bool(np.isfinite(sens["maduras"]) and np.isfinite(sens["jovens"]) and np.sign(sens["maduras"]) == sg and np.sign(sens["jovens"]) == sg),
               "curva_pagantes_mesmo_sinal": bool(np.isfinite(sens["curva_pagantes"]) and np.sign(sens["curva_pagantes"]) == sg)}
    a_q = dois.fatia_agregador.quantile([.25, .5, .75]).to_dict()
    sig = [{"a": f"p{int(100 * q)} = {a:.2f}", "premissa": p_, "sigma_alunos": p_ * (np.exp(th) - 1 + a) / a, "fator_substituicao_total": 1 + a * (1 / p_ - 1)}
           for q, a in a_q.items() for p_ in PREMISSAS]
    a = float(a_q[.5])
    chk = pd.DataFrame({"erro_v2_pct": pct(nen.e), "theta_sem_ela": pd.Series(loo),
                        "erro_v2_x_fator_pct": [pct(e_ - loo[u]) for u, e_ in nen.e.items()]})
    return dict(S=S, theta=th, amp=amp, ordem=ordem, loo=loo, sens=sens, portoes=portoes, portoes_ok=all(portoes.values()), a=a,
                sigma=pd.DataFrame(sig), sigma_p50_060=0.60 * (np.exp(th) - 1 + a) / a, chk=chk, n_nenhum=len(nen), n_dois=len(dois),
                n_um=int((S.aceite == "um só").sum()), et_chk_v2=et(nen.e), et_chk_fator=et([e_ - loo[u] for u, e_ in nen.e.items()]))


# ------------------------------------------------------------------ PARTE II
def ridge(X, y, pen, lam):
    P = np.zeros(X.shape[1]); P[pen] = 1.0
    M = np.linalg.pinv(X.T @ X + lam * np.diag(P))
    bta = M @ X.T @ y
    e = y - X @ bta
    h = np.einsum("ij,jk,ik->i", X, M, X)
    return bta, e, h


def escolhe_lam(X, y, pen):
    sse = []
    for l_ in LAMBDAS:
        _, e, h = ridge(X, y, pen, l_)
        r = np.where(h >= 1 - 1e-9, np.inf, e / np.where(h >= 1 - 1e-9, 1.0, 1 - h))
        sse.append(float(np.sum(r ** 2)))
    return LAMBDAS[int(np.nanargmin(sse))]


def boot_queda(e_arm, e_ref, rng):
    idx = rng.integers(0, len(e_ref), size=(NB, len(e_ref)))
    dif = np.array([et(e_arm[ii]) - et(e_ref[ii]) for ii in idx])       # < 0 = braco melhor
    return float(np.mean(dif >= 0)), (float(-100 * np.percentile(dif, 95)), float(-100 * np.percentile(dif, 5)))


def parte_II(Bs, tr, te, rng):
    tm, d, DUM, V2, cal, ex = Bs["tm"], Bs["d"], Bs["DUM"], Bs["V2"], Bs["cal"], Bs["ex"]
    for D in (tr, te):
        D["x1_parceiros_mil"] = np.log((d.wh_n_conc_c10.reindex(D.index) + d.tp_n_conc_c10.reindex(D.index) + 1) / (d.iso_pop__carro_10.reindex(D.index) / 1000))
        D["x2_indep_ag"] = np.log1p(d.iso_n_independente_agregador__carro_10.reindex(D.index))
    ONE = ["mr_M1"] + DUM
    VA = ["l_m2", "l_renda_dom", "l_pop"] + ONE + ["studios"]
    VB = ["l_m2", "l_renda_dom", "l_pop", "x1_parceiros_mil", "x2_indep_ag", "studios"]
    VR = ["l_m2", "l_renda_dom", "l_pop", "studios"]
    assert (tr[ONE].sum(axis=1) == 1).all() and (te[ONE].sum(axis=1) == 1).all(), "one-hot de master incompleto"
    assert tr[VB].notna().all().all() and te[VB].notna().all().all(), "faltam covariaveis do braco B"
    y = tr.l_fat.to_numpy(float); yt = te.l_fat.to_numpy(float)
    X2, Xt2, XA, XtA = tm.X_(tr, V2), tm.X_(te, V2), tm.X_(tr, VA), tm.X_(te, VA)
    XB, XtB, XR, XtR = tm.X_(tr, VB), tm.X_(te, VB), tm.X_(tr, VR), tm.X_(te, VR)
    pen = [1 + VA.index(c) for c in ONE]
    out = {}
    b0, e0, h0, _ = ex.ols(y, X2)
    out["v2"] = dict(loo=e0 / (1 - h0), test=yt - (Xt2 @ b0 + cal["l_fat"]), coef=b0)
    eA = np.empty(len(y)); lams = []
    for i in range(len(y)):
        m = np.ones(len(y), bool); m[i] = False
        l_ = escolhe_lam(XA[m], y[m], pen); lams.append(l_)
        bi, _, _ = ridge(XA[m], y[m], pen, l_)
        eA[i] = y[i] - XA[i] @ bi
    lamA = escolhe_lam(XA, y, pen); bA, _, _ = ridge(XA, y, pen, lamA)
    out["A_masters_encolhidas"] = dict(loo=eA, test=yt - (XtA @ bA + cal["l_fat"]), lam=lamA, lams_dobras=lams, coef=bA)
    bB, eB, hB, _ = ex.ols(y, XB)
    out["B_mercado_agregador"] = dict(loo=eB / (1 - hB), test=yt - (XtB @ bB + cal["l_fat"]), coef=bB)
    bR, eR, hR, _ = ex.ols(y, XR)
    out["ref_v2_sem_masters"] = dict(loo=eR / (1 - hR), test=yt - (XtR @ bR + cal["l_fat"]), coef=bR)
    metro = d.iso_metro.reindex(tr.index).fillna(-1).to_numpy()
    lomo = {k: np.empty(len(y)) for k in out}
    for mm in np.unique(metro):
        s = metro == mm; t = ~s
        bb, *_ = ex.ols(y[t], X2[t]); lomo["v2"][s] = y[s] - X2[s] @ bb
        ba, *_ = ridge(XA[t], y[t], pen, escolhe_lam(XA[t], y[t], pen)); lomo["A_masters_encolhidas"][s] = y[s] - XA[s] @ ba
        bbB, *_ = ex.ols(y[t], XB[t]); lomo["B_mercado_agregador"][s] = y[s] - XB[s] @ bbB
        bbR, *_ = ex.ols(y[t], XR[t]); lomo["ref_v2_sem_masters"][s] = y[s] - XR[s] @ bbR
    dobra = np.where(metro == 1, "metrô 1", np.where(metro == 0, "metrô 0", "demais"))
    TL = pd.DataFrame({k: {g_: 100 * et(lomo[k][dobra == g_]) for g_ in ("metrô 1", "metrô 0", "demais")} for k in out}).T
    TL = TL.assign(n_metro1=int((dobra == "metrô 1").sum()), n_metro0=int((dobra == "metrô 0").sum()), n_demais=int((dobra == "demais").sum()))
    tab, ps = [], {}
    for k, r in out.items():
        rec = r["test"] - np.median(r["test"])
        tab.append({"modelo": k, "erro_tipico_LOO_39": 100 * et(r["loo"]), "erro_tipico_teste_18": 100 * et(r["test"]),
                    "erro_tipico_teste_18_recentrado": 100 * et(rec), "erro_tipico_deixando_metro_fora": 100 * et(lomo[k]),
                    "rmse_log_LOO": float(np.sqrt(np.mean(r["loo"] ** 2))), "vies_mediano_teste_pct": pct(np.median(r["test"]))})
    T = pd.DataFrame(tab).set_index("modelo")
    for k in ("A_masters_encolhidas", "B_mercado_agregador"):
        ps[k], ic_loo = boot_queda(out[k]["loo"], out["v2"]["loo"], rng)
        _, ic_te = boot_queda(out[k]["test"], out["v2"]["test"], rng)
        T.loc[k, ["ic90_queda_LOO_lo", "ic90_queda_LOO_hi", "ic90_queda_teste_lo", "ic90_queda_teste_hi"]] = [*ic_loo, *ic_te]
    ordem = sorted(ps, key=ps.get)
    holm, ok_ate_aqui = {}, True
    for i, k in enumerate(ordem):                                   # Holm step-down, alfa de familia 0,05 unilateral
        ok_ate_aqui = ok_ate_aqui and ps[k] <= ALFA / (len(ordem) - i)
        holm[k] = ok_ate_aqui
    for k in ps:
        q2 = T.loc["v2", "erro_tipico_LOO_39"] - T.loc[k, "erro_tipico_LOO_39"]
        q3 = T.loc["v2", "erro_tipico_teste_18"] - T.loc[k, "erro_tipico_teste_18"]
        q3r = T.loc["v2", "erro_tipico_teste_18_recentrado"] - T.loc[k, "erro_tipico_teste_18_recentrado"]
        trava = (k != "B_mercado_agregador") or (T.loc[k, "erro_tipico_deixando_metro_fora"] <= T.loc["v2", "erro_tipico_deixando_metro_fora"])
        c2 = bool((q2 >= 2) and holm[k]); c3 = bool((q3 >= 2) and (q3r >= 2))
        T.loc[k, ["queda_LOO_pp", "p_boot", "holm_ok", "queda_teste_pp", "queda_teste_recentrado_pp", "trava_metro_ok", "c2", "c3"]] = [q2, ps[k], holm[k], q3, q3r, trava, c2, c3]
        T.loc[k, "leitura"] = "MELHORA A PRECISÃO" if (c2 and c3 and trava) else "não melhora"
    return dict(T=T, TL=TL, out=out, VA=VA, VB=VB, VR=VR, ONE=ONE, pen=pen)


def prever_turma(Bs, resI, resII):
    """Previsoes da turma de 2026 congeladas: v2 (recalculada e conferida contra 29-30/09), bracos A e B, e o fator nas 5 cegas."""
    assert sha(TURMA) == SHA_TURMA and sha(TURMA_V2) == SHA_TURMA_V2, "previsoes da turma de 29-30/09 mudaram"
    tm, d, A, cal = Bs["tm"], Bs["d"], Bs["A"], Bs["cal"]
    T0 = pd.read_csv(TURMA, sep=";", encoding="utf-8-sig", index_col=0)
    TV = pd.read_csv(TURMA_V2, sep=";", encoding="utf-8-sig", index_col=0)
    U = A.reindex(TV.index).drop(columns=["l_m2"], errors="ignore").assign(l_m2=np.log(T0.m2.reindex(TV.index)))
    U = Bs["dummies"](U); U["mr_M1"] = (U.master_id == "M1").astype(float)
    U["x1_parceiros_mil"] = np.log((d.wh_n_conc_c10.reindex(U.index) + d.tp_n_conc_c10.reindex(U.index) + 1) / (d.iso_pop__carro_10.reindex(U.index) / 1000))
    U["x2_indep_ag"] = np.log1p(d.iso_n_independente_agregador__carro_10.reindex(U.index))
    ok2 = U[Bs["V2"]].notna().all(axis=1) & TV.prev_v2dom_cal2026.notna()
    okB = U[resII["VB"]].notna().all(axis=1) & ok2
    Z = U.fillna(0)
    P = pd.DataFrame(index=U.index)
    P["prev_v2_cal2026_congelada_30_09"] = TV.prev_v2dom_cal2026
    P["prev_v2_recalc"] = np.where(ok2, np.exp(tm.X_(Z, Bs["V2"]) @ Bs["b"] + cal["l_fat"]), np.nan)
    assert (P.prev_v2_recalc.isna() == P.prev_v2_cal2026_congelada_30_09.isna()).all(), "padrao de previsao faltante diverge do congelado"
    chk = (P.prev_v2_recalc / P.prev_v2_cal2026_congelada_30_09 - 1).abs().dropna()
    assert len(chk) == 14 and (chk < 0.005).all(), f"v2 recalculada diverge da congelada: {chk.to_dict()}"
    P["prev_A_masters_encolhidas"] = np.where(ok2, np.exp(tm.X_(Z, resII["VA"]) @ resII["out"]["A_masters_encolhidas"]["coef"] + cal["l_fat"]), np.nan)
    P["prev_B_mercado_agregador"] = np.where(okB, np.exp(tm.X_(Z, resII["VB"]) @ resII["out"]["B_mercado_agregador"]["coef"] + cal["l_fat"]), np.nan)
    P["cega"] = P.index.isin(CEGAS)
    P["prev_v2_x_fator_se_sem_agregador"] = np.where(P.cega & resI["portoes_ok"], P.prev_v2_cal2026_congelada_30_09 * np.exp(resI["theta"]), np.nan)
    P["prev_v2_sigma0_se_sem_agregador"] = np.where(P.cega, P.prev_v2_cal2026_congelada_30_09 * (1 - resI["a"]), np.nan)
    P["theta_sem_congelado"] = resI["theta"] if resI["portoes_ok"] else np.nan
    return P


# ------------------------------------------------------------------ resultado e graficos
def escrever(resI, resII, P, excl, Bs, destino, ensaio):
    T, TL, S = resII["T"], resII["TL"], resI["S"]
    sn = resI["sens"]
    L = [f"# BLK-UNI-13 — resultado{' (ENSAIO COM RUÍDO — não interpretar)' if ensaio else ''}", "",
         f"Protocolo `protocolo_uni13.md` v1.1. Rodado em {datetime.now():%Y-%m-%d %H:%M}. v2 conferida: R² LOO {Bs['r2']:.3f}, erro nas 18 {100 * Bs['et_te']:.1f}%.",
         "ESTIMAÇÃO com exposição: o θ̂_sem é quase calculável com números já vistos. O juiz é a turma de 2026 (contraste dentro da turma), "
         "e a leitura de 2027 provavelmente será inconclusiva.", "",
         "## Parte I — fator para unidade sem agregador", "",
         f"- Amostra: {len(S)} unidades fora do treino ({(S.regra == 'madura').sum()} maduras, {(S.regra == 'jovem').sum()} jovens). Aceite: "
         f"nenhum {resI['n_nenhum']}, um só {resI['n_um']}, os dois {resI['n_dois']}.",
         f"- **θ̂_sem = {resI['theta']:+.3f} em log ({pct(resI['theta']):+.0f}%).** Amplitude do bootstrap (n = {resI['n_nenhum']}, descritiva): "
         f"{pct(resI['amp'][0]):+.0f}% a {pct(resI['amp'][1]):+.0f}%. Intervalo de ordem [x(1), x({resI['n_nenhum']})]: {pct(resI['ordem'][0]):+.0f}% a {pct(resI['ordem'][1]):+.0f}%.",
         f"- Estratos: só maduras {pct(sn['maduras']):+.0f}%; só jovens {pct(sn['jovens']):+.0f}%.",
         f"- Sensibilidades: curva `pagantes` {pct(sn['curva_pagantes']):+.0f}%; sem RJ {pct(sn['sem_RJ']):+.0f}%; calendário do balcão "
         f"{pct(sn['calendario_balcao']):+.0f}% (cal total {Bs['cal']['l_fat']:+.3f}, cal balcão {Bs['cal_bal']:+.3f}).",
         "- Portões: " + "; ".join(f"{k} {'OK' if v else 'FALHOU'}" for k, v in resI["portoes"].items()) + ".",
         f"- **Fator {'congelado para conferência (não adotado)' if resI['portoes_ok'] else 'NÃO congelado (portão falhou)'}.**",
         f"- Checagem interna, NÃO é teste (fator estimado sem a própria unidade): erro típico nas 'nenhum' v2 {100 * resI['et_chk_v2']:.1f}% → v2 × fator {100 * resI['et_chk_fator']:.1f}%.",
         f"- Leitura estrutural (σ = fração dos ALUNOS de agregador que voltam pelo balcão; teto 1): com a = {resI['a']:.2f} e premissa 0,60, "
         f"σ̂ = {resI['sigma_p50_060']:.2f} → {'a substituição sozinha NÃO explica o desvio' if resI['sigma_p50_060'] > 1 else 'compatível com substituição pelo balcão'}. Grade na planilha.", "",
         "| unidade | UF | master | estúdio | regra | aceite | m² (fonte) | pop abaixo do treino | erro da v2 |", "|---|---|---|---|---|---|---|---|---|"] + [
         f"| {u} | {r.uf} | {r.master_id} | {'sim' if r.studios == 1 else 'não'} | {r.regra} | {r.aceite} | {r.m2:.0f} ({r.fonte_m2}) | {'sim' if r.pop_abaixo_do_treino else ''} | {pct(r.e):+.0f}% |"
         for u, r in S.sort_values(["aceite", "e"]).iterrows()] + [
         "", "Elegíveis excluídas: " + ("; ".join(f"{r.unidade_id} ({r.motivo})" for r in excl.itertuples()) if len(excl) else "nenhuma") + ".", "",
         "## Parte II — masters", "",
         "| modelo | LOO 39 | teste 18 | teste recentrado | metrô de fora | viés teste | queda LOO (pp) [IC 90%] | queda teste (pp) [IC 90%] | p | c2 | c3 | leitura |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, r in T.iterrows():
        arm = k in ("A_masters_encolhidas", "B_mercado_agregador")
        L.append(f"| {k} | {r.erro_tipico_LOO_39:.1f}% | {r.erro_tipico_teste_18:.1f}% | {r.erro_tipico_teste_18_recentrado:.1f}% | {r.erro_tipico_deixando_metro_fora:.1f}% | "
                 f"{r.vies_mediano_teste_pct:+.0f}% | "
                 + (f"{r.queda_LOO_pp:+.1f} [{r.ic90_queda_LOO_lo:+.1f}; {r.ic90_queda_LOO_hi:+.1f}] | {r.queda_teste_pp:+.1f} [{r.ic90_queda_teste_lo:+.1f}; {r.ic90_queda_teste_hi:+.1f}] | "
                    f"{r.p_boot:.3f} | {r.c2} | {r.c3} | {r.leitura} |" if arm else " | | | | | referência |" if k.startswith("ref") else " | | | | | |"))
    L += ["", f"Erro típico deixando um metrô de fora, por dobra (%; n = {int(TL.n_metro1.iloc[0])} no metrô 1, {int(TL.n_metro0.iloc[0])} no metrô 0, "
          f"{int(TL.n_demais.iloc[0])} nas demais):", "", "| modelo | metrô 1 | metrô 0 | demais |", "|---|---|---|---|"] + [
          f"| {k} | {r['metrô 1']:.1f} | {r['metrô 0']:.1f} | {r['demais']:.1f} |" for k, r in TL.iterrows()] + ["",
          f"- Braço A: λ escolhido nas 39 = {resII['out']['A_masters_encolhidas']['lam']}; nas dobras: {sorted(set(resII['out']['A_masters_encolhidas']['lams_dobras']))}.",
          f"- Braço B ({', '.join(['const'] + resII['VB'])}): {np.round(resII['out']['B_mercado_agregador']['coef'], 3).tolist()}. Com log pop no modelo, x1 equivale à "
          "contagem de parceiros e o coeficiente de log pop deixa de ser comparável ao da v2.",
          "- O c3 do braço B é um reteste nas 18 que deram origem à pista (uni09/resultado_uni09.md:44); com estúdios, a master acerta o nível (CADERNO:568-569).", "",
          "## Turma de 2026 — previsões congeladas", "",
          f"`{PREV_T.name}`: as 14 com previsão (a turma tem 16). O fator só nas 5 cegas e só se os portões passaram.", ""]
    destino.write_text("\n".join(L) + "\n", encoding="utf-8")
    return "\n".join(L)


def graficos(resI, resII, out):
    out.mkdir(parents=True, exist_ok=True)
    S = resI["S"]
    fig, axs = plt.subplots(1, 2, figsize=(17, 6.8), gridspec_kw={"width_ratios": [1, 1.3]})
    cores = {"nenhum": "#c44e52", "um só": "#8172b2", "os dois": "#4c72b0"}
    for j, gname in enumerate(("os dois", "um só", "nenhum")):
        s_ = S[S.aceite == gname]
        x = np.full(len(s_), j) + np.random.default_rng(j).uniform(-.18, .18, len(s_))
        axs[0].scatter(x, pct(s_.e), color=cores[gname], s=36, edgecolor="k", lw=.3, marker="o")
        for xx, (u, r) in zip(x, s_.iterrows()):
            axs[0].annotate(u[:18] + (" (jovem)" if r.regra == "jovem" else ""), (xx, pct(r.e)), fontsize=6, alpha=.75, xytext=(3, 0), textcoords="offset points")
        if len(s_):
            axs[0].hlines(pct(np.median(s_.e)), j - .3, j + .3, color=cores[gname], lw=2)
    axs[0].axhline(0, color="k", lw=.7)
    axs[0].set_xticks([0, 1, 2]); axs[0].set_xticklabels([f"{g} (n {(S.aceite == g).sum()})" for g in ("os dois", "um só", "nenhum")])
    axs[0].set_ylabel("erro da v2 = real / previsto − 1 (%)")
    sn = resI["sens"]
    axs[0].set_title(f"Erro da v2 por aceite de agregador (fora do treino). θ̂_sem = {pct(resI['theta']):+.0f}% (traço = mediana)\n"
                     f"só maduras {pct(sn['maduras']):+.0f}% | só jovens {pct(sn['jovens']):+.0f}% | curva pagantes {pct(sn['curva_pagantes']):+.0f}% | "
                     f"sem RJ {pct(sn['sem_RJ']):+.0f}% — {'congelado para conferência' if resI['portoes_ok'] else 'NÃO congelado'}", fontsize=8)
    T = resII["T"]
    cols = ["erro_tipico_LOO_39", "erro_tipico_teste_18", "erro_tipico_teste_18_recentrado", "erro_tipico_deixando_metro_fora"]
    rot = ["LOO nas 39", "teste nas 18", "teste recentrado", "deixando um metrô de fora"]
    w = .2
    for k_, (mname, c_) in enumerate(zip(T.index, ("#7f7f7f", "#55a868", "#dd8452", "#c7c7c7"))):
        axs[1].bar(np.arange(len(cols)) + (k_ - 1.5) * w, T.loc[mname, cols].astype(float), w, color=c_, label=mname)
        for i, v in enumerate(T.loc[mname, cols].astype(float)):
            axs[1].text(i + (k_ - 1.5) * w, v + .3, f"{v:.1f}", ha="center", fontsize=6.5)
    axs[1].set_xticks(range(len(cols))); axs[1].set_xticklabels(rot); axs[1].set_ylabel("erro típico (%)"); axs[1].legend(fontsize=7)
    leit = "; ".join(f"{k}: {T.loc[k, 'leitura']}" for k in ("A_masters_encolhidas", "B_mercado_agregador"))
    axs[1].set_title(f"Masters: v2 × encolhidas (A) × mercado de agregador (B). Menor = melhor\n{leit}", fontsize=8)
    fig.tight_layout(); fig.savefig(out / "01_fator_sem_agregador_e_masters.png", bbox_inches="tight"); plt.close(fig)


def planilha(resI, resII, P, excl, out):
    with pd.ExcelWriter(out / "numeros_dos_graficos.xlsx") as w:
        pd.DataFrame({"campo": ["O que é", "Parte I", "Parte II", "Turma 2026", "Cuidado", "Gerado por"], "descrição": [
            "BLK-UNI-13: fator para unidade sem agregador (θ_sem) e masters da v2 (encolhidas ou trocadas por mercado de agregador).",
            "Unidades fora do treino com desfecho em jan–ago/2026 (maduras pela regra do UNI-02; jovens de 6–11 meses ajustadas pela curva de faturamento do UNI-03). "
            "θ_sem = mediana do erro das sem agregador − mediana das que aceitam os dois. Estratos e portões no resultado.",
            "Régua da bateria: c2 (LOO das 39, Holm com 2 braços, α 0,05 unilateral) e c3 (teste das 18, cru e recentrado); braço B com trava deixando um metrô de fora.",
            "Previsões congeladas para a conferência (BLK-UNI-12). O fator, se congelado, só nas 5 cegas; a leitura é o contraste dentro da turma e provavelmente sairá "
            "inconclusiva, porque as unidades tendem a ligar o agregador antes do mês 12.",
            "Todas as unidades da parte I já tinham faturamento visto (estimação, não teste). Fator congelado para conferência, NÃO adotado.",
            "data/analysis/uni/uni13/01_fator_e_masters.py (protocolo v1.1)"]}).to_excel(w, sheet_name="LEIA-ME", index=False)
        resI["S"].to_excel(w, sheet_name="parte_I_unidades"); excl.to_excel(w, sheet_name="parte_I_excluidas", index=False)
        pd.DataFrame([resI["sens"]]).to_excel(w, sheet_name="parte_I_sensibilidades", index=False)
        resI["chk"].to_excel(w, sheet_name="parte_I_checagem_interna"); resI["sigma"].to_excel(w, sheet_name="parte_I_sigma_grade", index=False)
        resII["T"].to_excel(w, sheet_name="parte_II_modelos"); resII["TL"].to_excel(w, sheet_name="parte_II_metro_por_dobra")
        P.to_excel(w, sheet_name="turma_2026_congelada")


def main():
    modo = [m for m in ("--seca", "--ensaio", "--registrar", "--rodar") if m in sys.argv]
    if len(modo) != 1:
        sys.exit("use exatamente um modo: --seca | --ensaio | --registrar | --rodar")
    modo = modo[0]
    if modo == "--registrar":
        if REG_PRE.exists():
            sys.exit("RECUSADO: REGISTRO_PRE.txt ja existe")
        txt = [f"REGISTRO PRE-RODADA BLK-UNI-13 (protocolo v1.1) — {datetime.now():%Y-%m-%d %H:%M}"] + [f"{k}: {Path(p).name}  SHA-256 {sha(p)}" for k, p in insumos().items()]
        REG_PRE.write_text("\n".join(txt) + "\n", encoding="utf-8"); print("\n".join(txt)); print("SHA do REGISTRO_PRE:", sha(REG_PRE)); return
    Bs = base()
    if modo == "--seca":
        S, excl = amostra_I(Bs, com_desfecho=False)
        print(S.drop(columns=["frac_meses_agregador"]).to_string()); print(S.groupby(["aceite", "regra"]).size().to_string())
        print(excl.to_string()); print("cal balcao:", round(Bs["cal_bal"], 4), "cal total:", round(Bs["cal"]["l_fat"], 4))
        return
    rng = np.random.default_rng(SEED)
    tr, te = Bs["tr"].copy(), Bs["te"].copy()
    S, excl = amostra_I(Bs)
    if modo == "--ensaio":
        rr = np.random.default_rng(1)
        S["l_real"] = S.l_prev + rr.normal(0, .3, len(S)); S["l_real_curva_pagantes"] = S.l_real + rr.normal(0, .05, len(S))
        S["fatia_agregador"] = 0.25
        tr["l_fat"] = tr.l_fat.mean() + rr.normal(0, .3, len(tr)); te["l_fat"] = tr.l_fat.mean() + rr.normal(0, .3, len(te))
        Bs["cal_bal"] = Bs["cal"]["l_fat"]
        dest = out = ENSAIO
        dest.mkdir(parents=True, exist_ok=True)
    else:
        linhas = REG_PRE.read_text(encoding="utf-8").splitlines()
        for k, p in insumos().items():
            reg = next(l_ for l_ in linhas if l_.startswith(f"{k}:")).split("SHA-256 ")[1].strip()
            assert sha(p) == reg, f"{k} mudou depois do REGISTRO_PRE"
        if PREV_T.exists() or RES.exists():
            sys.exit("RECUSADO: a rodada real ja aconteceu (resultado/previsoes existem)")
        dest, out = AQUI, OUT
    resI = parte_I(S, Bs, rng)
    resII = parte_II(Bs, tr, te, rng)
    P = prever_turma(Bs, resI, resII)
    P.to_csv(dest / PREV_T.name, sep=";", encoding="utf-8-sig", float_format="%.4f")
    txt = escrever(resI, resII, P, excl, Bs, dest / RES.name, modo == "--ensaio")
    if modo == "--rodar":
        REG_POS.write_text(f"Previsoes da turma de 2026 (BLK-UNI-13, protocolo v1.1) congeladas em {datetime.now():%Y-%m-%d %H:%M}, antes de qualquer conferencia.\n"
                           f"{PREV_T.name}  SHA-256 {sha(PREV_T)}\n{RES.name}  SHA-256 {sha(RES)}\nREGISTRO_PRE.txt  SHA-256 {sha(REG_PRE)}\n", encoding="utf-8")
        print(REG_POS.read_text(encoding="utf-8"))
    graficos(resI, resII, out)
    planilha(resI, resII, P, excl, out)
    print(txt); print(P.round(0).to_string())


if __name__ == "__main__":
    main()
