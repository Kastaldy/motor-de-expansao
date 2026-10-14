# -*- coding: utf-8 -*-
"""BLK-UNI-14 (protocolo_uni14.md v1.1, 06/10) — validacao ampliada pedida pelo Felipe:
 P1 fator sem agregador na v2 e nas duas partes (estimado SEM a turma de 2026);
 P2 turma de 2026 ja' (leitura precoce e exposta, SEM veredito);
 P3 bracos de master nas duas familias (A peso reduzido; B mercado de agregador — nas duas partes em 2 versoes; C estudio x renda;
    D tier do cadastro no criterio; D-diag R$ por passagem so' como diagnostico);
 P4 antes e depois nas unidades que ligaram/desligaram agregador (datas pela Growth, conferidas no Financeiro).
Modos (um por vez):  --seca | --ensaio | --registrar | --rodar      (.venv, PYTHONPATH=src)
Sem Base Consolidada; LOCAL_ so' entra como SHA."""
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
PROT = AQUI / "protocolo_uni14.md"
REG_PRE = AQUI / "REGISTRO_PRE.txt"
RES = AQUI / "resultado_uni14.md"
PREV = AQUI / "previsoes_turma_2026_uni14.csv"
REG_POS = AQUI / "REGISTRO_CONGELAMENTO_turma_2026.txt"
MET_TIME = UNI / "coleta_metragem" / "metragem_time_expansao_2026-10-06.csv"
MET_SAT = UNI / "coleta_metragem" / "metragem_estimada_2026-09-29.csv"
CURVA = UNI / "uni03" / "curva_uni03.csv"
TURMA = UNI / "previsao_2026" / "previsoes_turma_2026.csv"
TURMA_V2 = UNI / "previsao_2026" / "previsoes_turma_2026_v2_domiciliar.csv"
SHA_TURMA = "8f7b216327ddd476f42253f969c0b46fb41b1bf385f86e7c1313ddef87a172dc"
SHA_TURMA_V2 = "999bd027263459ecf2a2eafc914ad832c0e863f2d36d385a23386e37d1ad6df9"
TURMA_B = ["boa-vista-ba", "ceilandia-qnm33-df", "bangu-rj", "berrini-sp", "picarras-sc", "flow-pr", "visconde-de-rio-claro-sp", "vicente-pires-rua-8-df", "boqueirao-sp"]
OUT = Path(r"C:\Users\Felipe\OneDrive - Grupo Ultra\Área de Trabalho\Análises - Motor de Expansão\Exploratória BLK-UNI\07 - Validação ampliada")
ENSAIO = Path(r"C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\9259d0a1-7dda-49bd-a390-c88f3d4ac1a6\scratchpad\uni14_ensaio")
JAN, JAN25 = ("2026-01", "2026-08"), ("2025-01", "2025-12")
FIM_FIN = "2026-08"
CEGAS = ["belford-roxo-rj", "novo-gama-df", "paulinia-sp", "domingos-ferreira-pe", "bonsucesso-rj"]
TRAVADAS_FORA = ["icarai-rj"]
SEED, NB = 20261007, 9999
LAMBDAS = [0, 0.25, 0.5, 1, 2, 4, 8, 16, 32, 64, 1000]
ALFA = 0.05
PREMISSAS = (0.47, 0.60)
UNI09 = {"calB": -0.0622, "calA": 0.1172, "s_tp": 0.3705, "teste_2p": 0.229, "loo_2p_publicado": 22.2}
NOMES = {"v2": "v2 (vigente)", "v2_A_peso_reduzido": "v2 + masters com peso reduzido", "v2_B_mercado_agregador": "v2 com mercado de agregador no lugar das masters",
         "v2_C_estudio_x_renda": "v2 + estúdio × renda", "v2_D_tier_cadastro": "v2 + tier do Wellhub (cadastro)", "v2_Ddiag_rpp": "v2 + R$ por passagem (diagnóstico)",
         "ref_v2_sem_masters": "v2 sem masters (referência)", "2p": "duas partes (UNI-09)", "2p_A_peso_reduzido": "duas partes + masters com peso reduzido",
         "2p_B_so_agregador": "duas partes, mercado de agregador só no agregador", "2p_B_duas_partes": "duas partes, mercado de agregador nas duas",
         "2p_C_estudio_x_renda": "duas partes + estúdio × renda (balcão)", "2p_D_tier_cadastro": "duas partes + tier do cadastro (agregador)",
         "2p_Ddiag_rpp": "duas partes + R$ por passagem (diagnóstico)"}
plt.rcParams.update({"figure.dpi": 110, "savefig.dpi": 150, "font.size": 9, "axes.grid": True, "grid.alpha": .3})


def mod(nome, p):
    s = importlib.util.spec_from_file_location(nome, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def et(e):
    e = np.asarray(e, float); e = e[np.isfinite(e)]
    return float(np.median(np.abs(np.exp(e) - 1))) if len(e) else np.nan


def pct(x):
    return 100 * (np.exp(x) - 1)


def fpct(x, nd=0):
    try:
        ok = x is not None and np.isfinite(x)
    except TypeError:
        ok = False
    return f"{pct(x):+.{nd}f}%" if ok else "—"


def mes_add(m, k):
    y, mm = int(m[:4]), int(m[5:]) + k
    while mm > 12:
        y, mm = y + 1, mm - 12
    while mm < 1:
        y, mm = y - 1, mm + 12
    return f"{y}-{mm:02d}"


def insumos():
    kpi = glob.glob(str(REPO / "data" / "validacao" / "KPIs_Smart_*.xlsx"))
    b = {"protocolo": PROT, "script": Path(__file__), "fato_unidade_mes": UNI / "fato_unidade_mes.parquet", "dim_unidade": UNI / "dim_unidade.parquet",
         "local_demanda_totalpass": UNI / "LOCAL_demanda_totalpass_por_unidade.parquet", "metragem_time": MET_TIME, "metragem_satelite": MET_SAT,
         "curva_uni03": CURVA, "turma_2026": TURMA, "turma_2026_v2": TURMA_V2, "confirmacao_uni02": UNI / "uni02" / "confirmacao_por_unidade.csv",
         "master_id_cadastro": UNI / "alavancas" / "master_id_cadastro.csv", "mod_duas_partes": UNI / "uni09" / "01_duas_partes.py",
         "mod_termometro": UNI / "termometro" / "01_termometro.py", "mod_evidencias": UNI / "manaus_volume" / "02_evidencias.py",
         "mod_alavancas": UNI / "alavancas" / "01_alavancas.py", "mod_incerteza": UNI / "uni07" / "01_incerteza.py",
         "mod_exploracao": UNI / "uni01" / "01_exploracao.py", "mod_confirmacao": UNI / "uni02" / "01_confirmacao.py",
         "mod_comparacao_uni05": UNI / "uni05" / "01_comparacao.py", "mod_premissas_manaus": UNI / "simulacoes" / "manaus_premissas_corrigidas.py",
         "mod_consolidar_metragem": UNI / "coleta_metragem" / "02_consolidar.py",
         "mod_viabilidade_ponto": REPO / "src" / "motor_expansao" / "dimensionamento" / "viabilidade_ponto.py",
         "mod_catchment_batch": REPO / "src" / "motor_expansao" / "dimensionamento" / "catchment_batch.py",
         "dim_config": REPO / "src" / "motor_expansao" / "dimensionamento" / "config.py", "dim_simulador": REPO / "src" / "motor_expansao" / "dimensionamento" / "simulador.py",
         "conc_mapeados": UNI / "insumos_vps" / "concorrentes_mapeados_2026-09-27.parquet", "planos_totalpass": UNI / "insumos_vps" / "planos_totalpass.parquet"}
    if len(kpi) == 1:
        b["kpis_smart"] = Path(kpi[0])
    return b


# ------------------------------------------------------------------ base
def base():
    u9 = mod("u9", UNI / "uni09" / "01_duas_partes.py")
    tm, ex = u9.tm, u9.ex
    f, d = ex.carregar()
    tr, te, DUM, cal, A, dummies = tm.bases(f, d)
    assert len(tr) == 39 and len(te) == 18 and "mr_M3" in DUM, (len(tr), len(te), DUM)
    Y25, Y26 = u9.partes(f, *JAN25), u9.partes(f, *JAN)
    tr = tr.join(Y25.drop(columns=[c for c in Y25.columns if c in tr.columns]), how="left")
    te = te.join(Y26.drop(columns=[c for c in Y26.columns if c in te.columns]), how="left")
    assert np.allclose(tr.Y_tot, tr.l_fat) and np.allclose(te.Y_tot, te.l_fat) and tr.Y_A.notna().all()
    whr, tpr, _ = u9.aceite(d, tr.index)
    s_tp = float(tr.loc[whr & tpr, "s_TP"].median())
    amb = tr.index.intersection(Y26.index)
    est = [u for u in amb if pd.notna(Y25.Y_A.get(u)) and pd.notna(Y26.Y_A.get(u)) and (Y25.s_TP.get(u, 0) > 0) == (Y26.s_TP.get(u, 0) > 0)]
    calB = float(np.median(Y26.reindex(est).Y_B - Y25.reindex(est).Y_B)); calA = float(np.median(Y26.reindex(est).Y_A - Y25.reindex(est).Y_A))
    f = f.copy()
    f["WH"], f["TP"] = f.fin_gympass.fillna(0), f.fin_totalpass.fillna(0)
    f["AG"] = f.WH + f.TP; f["BAL"] = f.fin_vendas_ux - f.fin_tem_saude.fillna(0)
    f["mv_ev"] = f.mv.fillna(999)                                   # placeholder de inauguracao = madura (como a Etapa 10)
    V2 = ["l_m2", "l_renda_dom", "l_pop"] + DUM + ["studios"]
    ONE = ["mr_M1"] + DUM
    Bs = dict(u9=u9, tm=tm, ex=ex, f=f, d=d, tr=tr, te=te, DUM=DUM, ONE=ONE, cal=cal, calB=calB, calA=calA, s_tp=s_tp, A=A, dummies=dummies, V2=V2,
              mu_renda=float(tr.l_renda_dom.mean()), sd_renda=float(tr.l_renda_dom.std(ddof=0)))
    for D, ini, fim in ((tr, *JAN25), (te, *JAN)):
        meses = f[f.valido & (f.competencia >= ini) & (f.competencia <= fim) & (f.mv >= 12) & f.unidade_id.isin(D.index)]
        covariaveis(Bs, D, meses)
    return Bs


def covariaveis(Bs, D, meses):
    d = Bs["d"]
    D["mr_M1"] = (D.master_id == "M1").astype(float)
    D["x1_parceiros_mil"] = np.log((d.wh_n_conc_c10.reindex(D.index) + d.tp_n_conc_c10.reindex(D.index) + 1) / (d.iso_pop__carro_10.reindex(D.index) / 1000))
    D["x2_indep_ag"] = np.log1p(d.iso_n_independente_agregador__carro_10.reindex(D.index))
    D["inter_est_renda"] = D.studios * (D.l_renda_dom - Bs["mu_renda"]) / Bs["sd_renda"]
    D["wh_ord_cad"] = d.wh_ord_ultra_cadastro.reindex(D.index).astype(float)
    m = meses[(meses.fin_gympass.fillna(0) > 0) & (meses.passagens_gympass > 0)]
    D["l_rpp_wh"] = np.log((m.fin_gympass / m.passagens_gympass).groupby(m.unidade_id).median().reindex(D.index))
    return D


def metragem(Bs):
    d, te = Bs["d"], Bs["te"]
    mt = pd.read_csv(MET_TIME, sep=";", encoding="utf-8").set_index("unidade_id").metragem_m2.astype(float)
    sat = pd.read_csv(MET_SAT, sep=";", encoding="utf-8-sig", index_col=0).metragem_estimada_m2
    tur = pd.read_csv(TURMA, sep=";", encoding="utf-8-sig", index_col=0).m2
    m2 = d.tam_metragem_m2.combine_first(mt).combine_first(sat)
    fonte = pd.Series(np.where(d.tam_metragem_m2.notna(), "oficial", np.where(mt.reindex(d.index).notna(), "time", np.where(sat.reindex(d.index).notna(), "satélite", "sem"))), index=d.index)
    m2.loc[te.index] = np.exp(te.l_m2); fonte.loc[te.index] = "UNI-02"
    m2.loc[tur.index] = tur; fonte.loc[tur.index] = "turma 30/09"
    return m2, fonte


# ------------------------------------------------------------------ desfechos fora do treino
def desfechos(Bs, unidades):
    """Regras madura / jovem / precoce (aviso). Devolve (tabela, descartadas com motivo)."""
    f, d = Bs["f"], Bs["d"]
    cv = pd.read_csv(CURVA, sep=";", encoding="utf-8-sig")
    curva = {s: cv[cv.serie == s].set_index("k").p50 for s in ("faturamento", "pagantes")}
    cf = lambda mv, s="faturamento": mv.astype(int).map(lambda k: 1.0 if k >= 12 else curva[s].get(k, np.nan))
    g = f[f.valido & (f.competencia >= JAN[0]) & (f.competencia <= JAN[1])]
    rows, desc = [], []
    for u in unidades:
        gu = g[g.unidade_id == u].sort_values("competencia")
        mad, jov, pre = gu[gu.mv >= 12], gu[gu.mv.between(6, 11)], gu[gu.mv >= 3]
        if len(mad) >= 3:
            regra, M = "madura", mad
        elif len(jov) >= 3:
            regra, M = "jovem", jov
        elif len(pre) >= 2:
            regra, M = "precoce (aviso)", pre.tail(3)
        else:
            desc.append({"unidade_id": u, "motivo": f"menos de 2 meses válidos com mês de vida ≥ 3 até {JAN[1]} (tem {len(pre)})"}); continue
        fa = float((M.AG > 0).mean()); fw = float((M.WH > 0).mean()); ft = float((M.TP > 0).mean())
        wh_o, tp_o = fw >= .5, ft >= .5
        if fa >= .5 and not (wh_o or tp_o):                       # agregador na maioria, mas nenhuma fonte sozinha: fica a de mais meses
            wh_o, tp_o = fw >= ft, ft > fw
        aceite = "nenhum" if fa < .5 else ("os dois" if (wh_o and tp_o) else "um só")
        mudou = bool(any(0 < x < 1 for x in (fw, ft)))
        lf = np.log(M.faturamento)
        y = float(lf.mean()) if regra == "madura" else float((lf - np.log(cf(M.mv))).mean())
        y_pag = y if (regra == "madura" or aceite != "nenhum") else float((lf - np.log(cf(M.mv, "pagantes"))).mean())
        m = M[(M.fin_gympass.fillna(0) > 0) & (M.passagens_gympass > 0)]
        rows.append({"unidade_id": u, "uf": d.uf.get(u), "regra": regra, "n_meses": len(M), "mv_min": float(M.mv.min()), "mv_max": float(M.mv.max()),
                     "aceite": aceite, "aceita_wh_obs": wh_o, "aceita_tp_obs": tp_o, "mudou_aceite_na_janela": mudou,
                     "l_real": y, "l_real_curva_pagantes": y_pag,
                     "l_rpp_wh_obs": float(np.log((m.fin_gympass / m.passagens_gympass).median())) if len(m) else np.nan})
    return (pd.DataFrame(rows).set_index("unidade_id") if rows else pd.DataFrame()), desc


def montar(Bs, unidades, m2):
    A = Bs["A"]
    D = A.reindex(unidades).drop(columns=["l_m2"], errors="ignore").assign(l_m2=np.log(m2.reindex(unidades)))
    D = Bs["dummies"](D)
    return covariaveis(Bs, D, Bs["f"].iloc[0:0])


# ------------------------------------------------------------------ modelos
def ridge(X, y, pen, lam):
    P = np.zeros(X.shape[1]); P[list(pen)] = 1.0
    M = np.linalg.pinv(X.T @ X + lam * np.diag(P))
    b = M @ X.T @ y
    return b, y - X @ b, np.einsum("ij,jk,ik->i", X, M, X)


def escolhe_lam(X, y, pen):
    if not pen:
        return 0
    sse = []
    for l_ in LAMBDAS:
        _, e, h = ridge(X, y, pen, l_)
        r = np.where(h >= 1 - 1e-9, np.inf, e / np.where(h >= 1 - 1e-9, 1.0, 1 - h))
        sse.append(float(np.sum(r ** 2)))
    return LAMBDAS[int(np.nanargmin(sse))]


def specs(Bs):
    V2, ONE = Bs["V2"], Bs["ONE"]
    VA = ["l_m2", "l_renda_dom", "l_pop"] + ONE + ["studios"]
    VB = ["l_m2", "l_renda_dom", "l_pop", "x1_parceiros_mil", "x2_indep_ag", "studios"]
    VR = ["l_m2", "l_renda_dom", "l_pop", "studios"]
    return {  # bases primeiro (os fallbacks dependem delas)
        "v2": dict(fam="v2", T=V2), "2p": dict(fam="2p", B=V2, A=V2), "ref_v2_sem_masters": dict(fam="v2", T=VR, ref=True),
        "v2_A_peso_reduzido": dict(fam="v2", T=VA, pen=ONE), "v2_B_mercado_agregador": dict(fam="v2", T=VB),
        "v2_C_estudio_x_renda": dict(fam="v2", T=V2 + ["inter_est_renda"]), "v2_D_tier_cadastro": dict(fam="v2", T=V2 + ["wh_ord_cad"], fallback="v2"),
        "v2_Ddiag_rpp": dict(fam="v2", T=V2 + ["l_rpp_wh"], fallback="v2", diag=True),
        "2p_A_peso_reduzido": dict(fam="2p", B=VA, A=VA, pen=ONE), "2p_B_so_agregador": dict(fam="2p", B=V2, A=VB),
        "2p_B_duas_partes": dict(fam="2p", B=VB, A=VB), "2p_C_estudio_x_renda": dict(fam="2p", B=V2 + ["inter_est_renda"], A=V2),
        "2p_D_tier_cadastro": dict(fam="2p", B=V2, A=V2 + ["wh_ord_cad"], fallback="2p"),
        "2p_Ddiag_rpp": dict(fam="2p", B=V2, A=V2 + ["l_rpp_wh"], fallback="2p", diag=True)}


def colunas(sp):
    return list(dict.fromkeys(sp.get("T", []) + sp.get("B", []) + sp.get("A", [])))


def completo(sp, D):
    return D[colunas(sp)].notna().all(axis=1).to_numpy()


def ajusta(Bs, sp, D):
    tm, u9 = Bs["tm"], Bs["u9"]
    if sp["fam"] == "v2":
        X = tm.X_(D, sp["T"]); y = D.Y_tot.to_numpy(float)
        pen = [1 + sp["T"].index(c) for c in sp.get("pen", [])]
        lam = escolhe_lam(X, y, pen)
        return dict(b=ridge(X, y, pen, lam)[0], lam=lam)
    wh, tp, _ = u9.aceite(Bs["d"], D.index)
    fr = u9.fator(wh, tp, Bs["s_tp"]).to_numpy(float)
    yA = D.Y_A.to_numpy(float) - np.log(np.where(fr > 0, fr, np.nan))
    out = {}
    for parte, y in (("B", D.Y_B.to_numpy(float)), ("A", yA)):
        cols = sp[parte]; X = tm.X_(D, cols)
        pen = [1 + cols.index(c) for c in sp.get("pen", []) if c in cols]
        lam = escolhe_lam(X, y, pen)
        out[f"b{parte}"], out[f"lam{parte}"] = ridge(X, y, pen, lam)[0], lam
    fitB, fitA = tm.X_(D, sp["B"]) @ out["bB"], tm.X_(D, sp["A"]) @ out["bA"]
    out["k"] = float(np.mean(D.Y_tot.to_numpy(float) - u9.lse(fitB, fitA, fr)))
    return out


def prever(Bs, sp, m, D, nivel2026, fac=None, partes=False):
    """Previsao em log; NaN onde falta covariavel do modelo (mascara explicita)."""
    tm, u9 = Bs["tm"], Bs["u9"]
    ok = completo(sp, D)
    Z = D.copy()
    for c in colunas(sp):
        Z[c] = Z[c].fillna(0.0)
    if sp["fam"] == "v2":
        p = tm.X_(Z, sp["T"]) @ m["b"] + (Bs["cal"]["l_fat"] if nivel2026 else 0.0)
        return np.where(ok, p, np.nan)
    pB = tm.X_(Z, sp["B"]) @ m["bB"] + (Bs["calB"] if nivel2026 else 0.0)
    pA = tm.X_(Z, sp["A"]) @ m["bA"] + (Bs["calA"] if nivel2026 else 0.0)
    if partes:
        return np.where(ok, pB, np.nan), np.where(ok, pA, np.nan), m["k"]
    return np.where(ok, u9.lse(pB, pA, fac) + m["k"], np.nan)


def fac_cadastro(Bs, idx):
    wh, tp, _ = Bs["u9"].aceite(Bs["d"], idx)
    return Bs["u9"].fator(wh, tp, Bs["s_tp"]).to_numpy(float)


def fac_obs(Bs, S):
    return Bs["u9"].fator(S.aceita_wh_obs.astype(bool), S.aceita_tp_obs.astype(bool), Bs["s_tp"]).to_numpy(float)


def avalia(Bs, SP, tr, te, outros):
    """LOO por reajuste explicito, teste, metro de fora e previsao nos conjuntos externos. Fallback: onde o modelo nao tem a
    covariavel (tier), vale o modelo base, inclusive no treino."""
    metro = Bs["d"].iso_metro.reindex(tr.index).fillna(-1).to_numpy()
    fr_tr, ft_te = fac_cadastro(Bs, tr.index), fac_cadastro(Bs, te.index)
    ytr = tr.Y_tot.to_numpy(float)
    R, fits = {}, {}
    for nome, sp in SP.items():
        mk = completo(sp, tr)
        if not sp.get("fallback"):
            assert mk.all(), f"{nome}: treino incompleto"
        base_ = R.get(sp.get("fallback"))
        loo = np.full(len(tr), np.nan)
        for i in np.where(mk)[0]:
            m = mk.copy(); m[i] = False
            mi = ajusta(Bs, sp, tr[m])
            loo[i] = ytr[i] - prever(Bs, sp, mi, tr.iloc[[i]], False, fr_tr[[i]])[0]
        if base_ is not None:
            loo = np.where(mk, loo, base_["loo"])
        mf = ajusta(Bs, sp, tr[mk]); fits[nome] = mf
        pt = prever(Bs, sp, mf, te, True, ft_te)
        if base_ is not None:
            pt = np.where(np.isfinite(pt), pt, base_["pt"])
        lomo = np.full(len(tr), np.nan)
        for mm in np.unique(metro):
            s = metro == mm
            ms = ajusta(Bs, sp, tr[mk & ~s])
            lomo[s] = ytr[s] - prever(Bs, sp, ms, tr[s], False, fr_tr[s])
        if base_ is not None:
            lomo = np.where(np.isfinite(lomo), lomo, base_["lomo"])
        R[nome] = dict(loo=loo, pt=pt, test=te.Y_tot.to_numpy(float) - pt, lomo=lomo, n_com_cov_treino=int(mk.sum()), metro=metro)
    ext = {}
    for rot, (S, D) in outros.items():
        fac = fac_obs(Bs, S)
        cols = {}
        for nome, sp in SP.items():
            p = prever(Bs, sp, fits[nome], D, True, fac)
            if sp.get("fallback"):
                p = np.where(np.isfinite(p), p, prever(Bs, SP[sp["fallback"]], fits[sp["fallback"]], D, True, fac))
            cols[nome] = S.l_real.to_numpy(float) - p
        ext[rot] = pd.DataFrame(cols, index=S.index)
    return R, fits, ext


def tabela_modelos(R, ext, SP, rng):
    linhas = []
    for nome, r in R.items():
        rec = r["test"] - np.median(r["test"])
        l_ = {"modelo": nome, "nome": NOMES.get(nome, nome), "LOO_39": 100 * et(r["loo"]), "teste_18": 100 * et(r["test"]), "teste_18_recentrado": 100 * et(rec),
              "regiao_nao_vista": 100 * et(r["lomo"]), "rmse_log_LOO": float(np.sqrt(np.nanmean(r["loo"] ** 2))), "vies_teste_pct": pct(np.median(r["test"])),
              "n_treino_com_covariavel": r["n_com_cov_treino"]}
        for rot, E in ext.items():
            l_[rot] = 100 * et(E[nome]); l_[f"n_{rot}"] = int(E[nome].notna().sum())
        linhas.append(l_)
    T = pd.DataFrame(linhas).set_index("modelo")
    crit = [k for k in R if k not in ("v2", "2p") and not SP[k].get("ref") and not SP[k].get("diag")]
    ps = {}
    for k in [k for k in R if k != "v2"]:
        for ref in (("v2", "2p") if k.startswith("2p_") else ("v2",)):
            idx = rng.integers(0, len(R["v2"]["loo"]), size=(NB, len(R["v2"]["loo"])))
            dl = np.array([et(R[k]["loo"][ii]) - et(R[ref]["loo"][ii]) for ii in idx])
            idt = rng.integers(0, len(R["v2"]["test"]), size=(NB, len(R["v2"]["test"])))
            dt = np.array([et(R[k]["test"][ii]) - et(R[ref]["test"][ii]) for ii in idt])
            s = "" if ref == "v2" else "_vs_2p"
            T.loc[k, [f"queda_LOO_pp{s}", f"ic90_LOO_lo{s}", f"ic90_LOO_hi{s}", f"queda_teste_pp{s}", f"ic90_teste_lo{s}", f"ic90_teste_hi{s}", f"queda_teste_recentrado_pp{s}"]] = [
                T.loc[ref, "LOO_39"] - T.loc[k, "LOO_39"], -100 * np.percentile(dl, 95), -100 * np.percentile(dl, 5),
                T.loc[ref, "teste_18"] - T.loc[k, "teste_18"], -100 * np.percentile(dt, 95), -100 * np.percentile(dt, 5),
                T.loc[ref, "teste_18_recentrado"] - T.loc[k, "teste_18_recentrado"]]
            if ref == "v2" and k in crit:
                ps[k] = float(np.mean(dl >= 0))
    ordem = sorted(ps, key=ps.get); ok_ = True
    for i, k in enumerate(ordem):                       # Holm step-down nos bracos do criterio, alfa de familia 0,05 unilateral
        ok_ = ok_ and ps[k] <= ALFA / (len(ordem) - i)
        T.loc[k, "p_boot"] = ps[k]; T.loc[k, "holm_ok"] = ok_
    for k in crit:
        c2 = bool(T.loc[k, "queda_LOO_pp"] >= 2 and T.loc[k, "holm_ok"])
        c3 = bool(T.loc[k, "queda_teste_pp"] >= 2 and T.loc[k, "queda_teste_recentrado_pp"] >= 2)
        trava = ("_B_" not in k) or (T.loc[k, "regiao_nao_vista"] <= T.loc["v2", "regiao_nao_vista"])
        T.loc[k, ["c2", "c3", "trava_metro_ok"]] = [c2, c3, trava]
        T.loc[k, "leitura"] = "MELHORA A PRECISÃO" if (c2 and c3 and trava) else "não melhora"
    for k in R:
        if SP[k].get("diag"):
            T.loc[k, "leitura"] = "diagnóstico (usa a receita do próprio período)"
        elif SP[k].get("ref"):
            T.loc[k, "leitura"] = "referência"
    T.loc["v2", "leitura"] = "vigente"; T.loc["2p", "leitura"] = "referência (UNI-09)"
    metro = R["v2"]["metro"]
    grupos = ("metrô 1 (Brasília)", "metrô 0", "demais")
    dobra = np.where(metro == 1, grupos[0], np.where(metro == 0, grupos[1], grupos[2]))
    TL = pd.DataFrame({k: {g_: 100 * et(r["lomo"][dobra == g_]) for g_ in grupos} for k, r in R.items()}).T
    TL["n"] = ", ".join(f"{g_} {int((dobra == g_).sum())}" for g_ in grupos)
    return T, TL, len(crit)


# ------------------------------------------------------------------ P1 / P2
def theta(e, grp):
    e, grp = np.asarray(e, float), np.asarray(grp)
    ok = np.isfinite(e)
    e, grp = e[ok], grp[ok]
    if (grp == "nenhum").sum() == 0 or (grp == "os dois").sum() == 0:
        return np.nan
    return float(np.median(e[grp == "nenhum"]) - np.median(e[grp == "os dois"]))


def p1(Bs, SP, fits, S, D, rng):
    fac = fac_obs(Bs, S)
    S = S.copy()
    S["e_v2"] = S.l_real - prever(Bs, SP["v2"], fits["v2"], D, True)
    S["e_2p"] = S.l_real - prever(Bs, SP["2p"], fits["2p"], D, True, fac)
    S["e_v2_curva_pagantes"] = S.l_real_curva_pagantes - (S.l_real - S.e_v2)
    S["e_2p_curva_pagantes"] = S.l_real_curva_pagantes - (S.l_real - S.e_2p)
    pB, pA, k = prever(Bs, SP["2p"], fits["2p"], D, True, partes=True)
    S["balcao_previsto"], S["agregador_previsto_se_aceitasse"] = np.exp(pB + k), np.exp(pA + k)
    for p_ in PREMISSAS:
        S[f"sobra_balcao_em_alunos_ag_p{int(round(100 * p_))}"] = np.where(S.aceite == "nenhum", p_ * (np.exp(S.l_real) - S.balcao_previsto) / S.agregador_previsto_se_aceitasse, np.nan)
    out = {}
    for fam in ("v2", "2p"):
        e = S[f"e_{fam}"]
        nen, dois = S[S.aceite == "nenhum"], S[S.aceite == "os dois"]
        th = theta(e, S.aceite)
        en, ed = nen[f"e_{fam}"].to_numpy(float), dois[f"e_{fam}"].to_numpy(float)
        boot = np.array([np.median(rng.choice(en, len(en))) - np.median(rng.choice(ed, len(ed))) for _ in range(NB)])
        loo = {u: float(np.median(nen[f"e_{fam}"].drop(u)) - np.median(ed)) for u in nen.index}
        mad, jov, sem_pre = S[S.regra == "madura"], S[S.regra == "jovem"], S[~S.regra.str.startswith("precoce")]
        semm = S[~S.mudou_aceite_na_janela]
        cal_aj = (Bs["cal"]["l_fat"] - Bs["calB"]) if fam == "v2" else (Bs["calB"] - Bs["cal"]["l_fat"])
        sens = {"maduras": theta(mad[f"e_{fam}"], mad.aceite), "jovens": theta(jov[f"e_{fam}"], jov.aceite),
                "sem_precoces": theta(sem_pre[f"e_{fam}"], sem_pre.aceite), "curva_pagantes": theta(S[f"e_{fam}_curva_pagantes"], S.aceite),
                "sem_RJ": theta(S[S.uf != "RJ"][f"e_{fam}"], S[S.uf != "RJ"].aceite),
                "sem_quem_mudou_de_aceite": theta(semm[f"e_{fam}"], semm.aceite),
                ("calendario_do_balcao" if fam == "v2" else "calendario_do_total"): th + cal_aj}
        sg = np.sign(th)
        port = {"pelo menos 4 sem agregador": len(nen) >= 4, "sinal estável tirando cada uma": all(np.sign(v) == sg for v in loo.values()),
                "maduras e jovens no mesmo sentido": bool(all(np.isfinite([sens["maduras"], sens["jovens"]])) and np.sign(sens["maduras"]) == sg and np.sign(sens["jovens"]) == sg),
                "curva de pagantes no mesmo sentido": bool(np.isfinite(sens["curva_pagantes"]) and np.sign(sens["curva_pagantes"]) == sg)}
        out[fam] = dict(theta=th, amp=(float(np.percentile(boot, 5)), float(np.percentile(boot, 95))),
                        ordem=(float(en.min() - np.median(ed)), float(en.max() - np.median(ed))), sens=sens, portoes=port, ok=all(port.values()),
                        n_nenhum=len(nen), n_dois=len(dois), chk_sem=et(en), chk_com=et([nen.loc[u, f"e_{fam}"] - loo[u] for u in nen.index]))
    return S, out


def p2(V, ext_v, thetas, checar):
    TV = pd.read_csv(TURMA_V2, sep=";", encoding="utf-8-sig", index_col=0)
    P = ext_v.copy()
    lv2c = np.log(TV.prev_v2dom_cal2026.reindex(V.index))
    if checar:
        rec = V.l_real - P["v2"]
        assert np.nanmax(np.abs(np.exp(rec - lv2c) - 1)) < 0.005, "v2 remontada nao bate com a congelada de 30/09"
    nen = (V.aceite == "nenhum").to_numpy()
    for fam in ("v2", "2p"):
        if thetas[fam]["ok"]:
            P[f"{fam}_x_fator"] = P[fam] - np.where(nen, thetas[fam]["theta"], 0.0)
    modelos = list(P.columns)
    resumo = []
    for c in modelos:
        r = {"modelo": c, "nome": NOMES.get(c, c.replace("_x_fator", " × fator")), "todas": 100 * et(P[c]), "n": int(P[c].notna().sum())}
        for g_ in ("nenhum", "um só", "os dois"):
            r[g_] = 100 * et(P.loc[V.aceite == g_, c]); r[f"n_{g_}"] = int((V.aceite == g_).sum())
        resumo.append(r)
    leituras = []
    curto = (V.regra.str.startswith("precoce") & (V.n_meses <= 2)).to_numpy()
    ep = (V.l_real_curva_pagantes - V.l_real).to_numpy()
    for fam in ("v2", "2p"):
        th = thetas[fam]["theta"]
        for rot, msk, aj in (("todas", np.ones(len(V), bool), 0.0), ("sem as unidades de 2 meses", ~curto, 0.0),
                             ("sem quem mudou de aceite", ~V.mudou_aceite_na_janela.to_numpy(), 0.0), ("curva de pagantes", np.ones(len(V), bool), ep)):
            e = (P[fam].to_numpy() + aj)[msk]
            g_ = V.aceite.to_numpy()[msk]
            dlt = theta(e, g_)
            nN, nD = int((g_ == "nenhum").sum()), int((g_ == "os dois").sum())
            dirc = "sem dado" if not np.isfinite(dlt) else ("mesma direção do fator" if np.sign(dlt) == np.sign(th) and dlt != 0 else "direção contrária ao fator")
            leituras.append({"modelo": "v2" if fam == "v2" else "duas partes", "recorte": rot, "sem_agregador_n": nN, "os_dois_n": nD,
                             "diferenca_turma": dlt, "fator_estimado": th, "leitura": dirc})
    P.insert(0, "aceite", V.aceite); P.insert(1, "regra", V.regra)
    P.insert(2, "meses_de_vida", V.mv_min.astype(int).astype(str) + "–" + V.mv_max.astype(int).astype(str))
    P.insert(3, "n_meses", V.n_meses); P.insert(4, "mudou_aceite", V.mudou_aceite_na_janela)
    return P, pd.DataFrame(resumo).set_index("modelo"), pd.DataFrame(leituras)


# ------------------------------------------------------------------ P4 eventos
def eventos(Bs, f=None):
    f = Bs["f"] if f is None else f
    f = f[~f.unidade_id.isin(CEGAS)].sort_values(["unidade_id", "competencia"])
    cv = pd.read_csv(CURVA, sep=";", encoding="utf-8-sig")
    curva = {s: cv[cv.serie == s].set_index("k").p50 for s in ("faturamento", "pagantes", "agregadores")}
    ev = []
    for u, g in f[f.competencia <= "2026-09"].groupby("unidade_id"):
        g = g.reset_index(drop=True)
        for src, col, fin in (("Wellhub", "passagens_gympass", "fin_gympass"), ("TotalPass", "passagens_totalpass", "fin_totalpass")):
            on = (g[col].fillna(0) > 0).to_numpy()
            for i in range(1, len(g)):
                if on[i] == on[i - 1]:
                    continue
                k = i - 1
                while k >= 0 and on[k] == on[i - 1]:
                    k -= 1
                if i - 1 - k < 3:
                    continue
                j = i
                while j < len(g) and on[j] == on[i]:
                    j += 1
                t0 = g.competencia[i]
                datacao = "ok"
                if on[i]:
                    janela = g[(g.competencia >= mes_add(t0, -12)) & (g.competencia <= mes_add(t0, -2))]
                    registra = src == "Wellhub" or t0 >= "2024-01"
                    if (janela[fin].fillna(0) > 0).any():
                        datacao = "fora (Financeiro mostra a fonte antes)"
                    elif not registra:
                        datacao = "só Growth (Financeiro não registrava TotalPass)"
                ev.append({"unidade_id": u, "fonte": src, "evento": "liga" if on[i] else "desliga", "competencia": t0, "mes_vida": float(g.mv_ev[i]),
                           "uf": g.uf[i], "meses_no_estado_novo": int(j - i), "persiste": bool((j - i) >= 2 or j == len(g)),
                           "volta_em_ate_6_meses": bool((j < len(g)) and (j - i) <= 6), "datacao": datacao})
    EV = pd.DataFrame(ev)
    v = f[f.valido].copy()
    v["alunos_ag"] = (v.alunos_gympass + v.alunos_totalpass).astype(float)
    ref = v[v.mv_ev >= 12]
    perto = set()
    for r in EV.itertuples():                                      # unidade em evento nao entra na referencia nos +-6 meses
        for kk in range(-6, 7):
            perto.add((r.unidade_id, mes_add(r.competencia, kk)))
    ref = ref[[(u, m) not in perto for u, m in zip(ref.unidade_id, ref.competencia)]]
    medidas = (("pagantes", "pagantes"), ("BAL", "pagantes"), ("alunos_ag", "agregadores"), ("faturamento", "faturamento"))
    rows, series = [], []
    for r in EV.itertuples():
        rf = ref[ref.unidade_id != r.unidade_id]
        g = v[v.unidade_id == r.unidade_id].set_index("competencia").sort_index()
        rel = {}
        for c, s in medidas:
            lim = FIM_FIN if c in ("BAL", "faturamento") else "2026-09"
            MED = rf[rf.competencia <= lim].groupby("competencia")[c].median()
            x = g[c].where(g[c] > 0).astype(float)
            x = x[x.index <= lim]
            adj = g.mv_ev.reindex(x.index).astype(int).map(lambda k_: 1.0 if k_ >= 12 else curva[s].get(k_, np.nan))
            rel[c] = np.log(x / adj) - np.log(MED.reindex(x.index))
        R_ = pd.DataFrame(rel)
        t0 = r.competencia
        pre = [m for m in R_.index if mes_add(t0, -6) <= m <= mes_add(t0, -1)]
        pos = [m for m in R_.index if mes_add(t0, 1) <= m <= mes_add(t0, 6) and m <= FIM_FIN]
        prep = [m for m in R_.index if mes_add(t0, -12) <= m <= mes_add(t0, -7)]
        posp = [m for m in R_.index if mes_add(t0, -5) <= m <= mes_add(t0, -1)]
        out = {**{k_: getattr(r, k_) for k_ in EV.columns}, "na_rampa": bool(r.mes_vida < 12)}
        for c, _s in medidas:
            a, b_ = R_.loc[pre, c].dropna(), R_.loc[pos, c].dropna()
            ok = len(a) >= 3 and len(b_) >= 2 and not (c == "faturamento" and min(pre + pos, default="0000") < "2023-10")
            out[f"dif_{c}"] = float(b_.mean() - a.mean()) if ok else np.nan
            out[f"n_antes_{c}"], out[f"n_depois_{c}"] = len(a), len(b_)
            ap, bp = R_.loc[prep, c].dropna(), R_.loc[posp, c].dropna()
            okp = len(ap) >= 3 and len(bp) >= 2 and not (c == "faturamento" and min(prep + posp, default="0000") < "2023-10")
            out[f"placebo_{c}"] = float(bp.mean() - ap.mean()) if okp else np.nan
        if t0 > FIM_FIN:
            out["status"] = "sem meses depois (set/2026): só gráfico"
        elif not r.persiste:
            out["status"] = "não persiste (1 mês)"
        elif np.isfinite(out["dif_pagantes"]) and np.isfinite(out["dif_BAL"]):
            out["status"] = "ok"
        else:
            out["status"] = "poucos meses"
        out["sensivel"] = bool(out["status"] == "ok" and (r.volta_em_ate_6_meses or r.datacao.startswith("fora")))
        rows.append(out)
        series.append(R_.assign(unidade_id=r.unidade_id, chave=f"{r.unidade_id} | {r.fonte} {r.evento} {t0}", t0=t0).reset_index())
    gz = v[v.unidade_id == "suzano-sp"].set_index("competencia").sort_index()
    if len(gz):                                                    # Suzano: sem evento (as passagens nao zeram) — so' a serie
        relz = {}
        for c, _s in medidas:
            MED = ref[ref.unidade_id != "suzano-sp"].groupby("competencia")[c].median()
            x = gz[c].where(gz[c] > 0).astype(float)
            relz[c] = np.log(x) - np.log(MED.reindex(x.index))
        series.append(pd.DataFrame(relz).assign(unidade_id="suzano-sp", chave="suzano-sp | sem evento (agregador caiu sem zerar)", t0="").reset_index())
    return pd.DataFrame(rows), (pd.concat(series) if series else pd.DataFrame())


def resumo_eventos(EVR):
    ok = EVR[EVR.status == "ok"]
    linhas = []
    for (fo, evn, rampa), g_ in ok.groupby(["fonte", "evento", "na_rampa"]):
        for sens, gg in (("todos", g_), ("sem os sensíveis", g_[~g_.sensivel])):
            if not len(gg):
                continue
            linhas.append({"tipo": f"{fo} {evn}", "fase": "na rampa" if rampa else "madura", "recorte": sens, "n": len(gg),
                           "pagantes": gg.dif_pagantes.median(), "balcao_rs": gg.dif_BAL.median(), "alunos_agregador": gg.dif_alunos_ag.median(),
                           "total_rs": gg.dif_faturamento.median(), "placebo_balcao_rs": gg.placebo_BAL.median(), "n_placebo": int(gg.placebo_BAL.notna().sum())})
    return pd.DataFrame(linhas)


# ------------------------------------------------------------------ saidas
def graficos(out, S1, th, P2, T, EVR, EVS, crit):
    out.mkdir(parents=True, exist_ok=True)
    fig, axs = plt.subplots(1, 2, figsize=(18, 7))
    mods = [("v2", "v2", "#7f7f7f", "o"), ("v2_x_fator", "v2 × fator", "#c44e52", "s"), ("2p", "duas partes", "#4c72b0", "^"), ("2p_x_fator", "duas partes × fator", "#55a868", "D")]
    P2s = P2.sort_values("v2"); y = np.arange(len(P2s))
    for c, rot, cor_, mk in mods:
        if c in P2s:
            axs[0].scatter(pct(P2s[c]), y, color=cor_, marker=mk, s=40, label=rot, edgecolor="k", lw=.3)
    axs[0].set_yticks(y); axs[0].set_yticklabels([f"{u} ({r.aceite}; meses {r.meses_de_vida}; {r.regra})" for u, r in P2s.iterrows()], fontsize=7)
    axs[0].axvline(0, color="k", lw=.8); axs[0].axvspan(-25, 25, color="gray", alpha=.08)
    axs[0].set_xlabel("erro = real ÷ previsto − 1 (%): positivo = faturou ACIMA do previsto"); axs[0].legend(fontsize=7)
    axs[0].set_title("Turma de 2026, já (leitura PRECOCE e já vista em 29/09; sem veredito). Faixa cinza = ±25%", fontsize=9)
    Eb = S1[S1.index.isin(TURMA_B)].sort_values("e_v2"); yb = np.arange(len(Eb))
    axs[1].scatter(pct(Eb.e_v2), yb, color="#7f7f7f", s=40, label="v2", edgecolor="k", lw=.3)
    axs[1].scatter(pct(Eb.e_2p), yb, color="#4c72b0", marker="^", s=40, label="duas partes", edgecolor="k", lw=.3)
    axs[1].set_yticks(yb); axs[1].set_yticklabels([f"{u} ({r.aceite}; {r.regra})" for u, r in Eb.iterrows()], fontsize=7)
    axs[1].axvline(0, color="k", lw=.8); axs[1].axvspan(-25, 25, color="gray", alpha=.08); axs[1].legend(fontsize=7)
    axs[1].set_xlabel("erro = real ÷ previsto − 1 (%)"); axs[1].set_title("Turma B (metragem do time; já vista): v2 × duas partes", fontsize=9)
    fig.tight_layout(); fig.savefig(out / "01_turma_2026_e_turma_B.png", bbox_inches="tight"); plt.close(fig)
    fig, axs = plt.subplots(1, 3, figsize=(19, 6.5), gridspec_kw={"width_ratios": [1, 1, .9]})
    cores = {"nenhum": "#c44e52", "um só": "#8172b2", "os dois": "#4c72b0"}
    for ax, fam, rot in ((axs[0], "v2", "v2"), (axs[1], "2p", "duas partes (sem agregador = só o balcão previsto)")):
        for j, gname in enumerate(("os dois", "um só", "nenhum")):
            s_ = S1[S1.aceite == gname]
            x = np.full(len(s_), j) + np.random.default_rng(j).uniform(-.18, .18, len(s_))
            ax.scatter(x, pct(s_[f"e_{fam}"]), color=cores[gname], s=34, edgecolor="k", lw=.3)
            for xx, (u, r) in zip(x, s_.iterrows()):
                ax.annotate(u[:16] + ("*" if r.regra.startswith("precoce") else ""), (xx, pct(r[f"e_{fam}"])), fontsize=6, alpha=.75, xytext=(3, 0), textcoords="offset points")
            if len(s_):
                ax.hlines(pct(np.median(s_[f"e_{fam}"])), j - .3, j + .3, color=cores[gname], lw=2)
        ax.axhline(0, color="k", lw=.7); ax.set_xticks([0, 1, 2]); ax.set_xticklabels([f"{g} (n {(S1.aceite == g).sum()})" for g in ("os dois", "um só", "nenhum")])
        sn = th[fam]["sens"]
        ax.set_title(f"{rot}\ndiferença sem − com os dois = {fpct(th[fam]['theta'])} | sem RJ {fpct(sn['sem_RJ'])} | sem precoces {fpct(sn['sem_precoces'])}\n"
                     f"{'portões OK: congelado para conferência' if th[fam]['ok'] else 'portão FALHOU: não congelado'}", fontsize=8.5)
        ax.set_ylabel("erro = real ÷ previsto − 1 (%)")
    sg = S1[S1.aceite == "nenhum"].sort_values("sobra_balcao_em_alunos_ag_p60")
    yy = np.arange(len(sg))
    axs[2].barh(yy + .2, sg.sobra_balcao_em_alunos_ag_p60, .4, color="#c44e52", label="premissa 0,60")
    axs[2].barh(yy - .2, sg.sobra_balcao_em_alunos_ag_p47, .4, color="#f4a582", label="premissa 0,47")
    axs[2].axvline(1, color="k", ls="--", lw=1); axs[2].set_yticks(yy); axs[2].set_yticklabels(sg.index, fontsize=7); axs[2].legend(fontsize=7)
    axs[2].set_xlabel("sobra do balcão acima do previsto ÷ agregador previsto (em alunos equivalentes)")
    axs[2].set_title("Sem agregador: sobra do balcão acima do previsto\n(acima de 1 = maior do que a troca app → balcão explicaria)", fontsize=8.5)
    fig.text(.01, -.02, "* = leitura precoce (poucos meses de vida)", fontsize=7)
    fig.tight_layout(); fig.savefig(out / "02_fator_sem_agregador.png", bbox_inches="tight"); plt.close(fig)
    cols = ["LOO_39", "teste_18", "teste_18_recentrado", "regiao_nao_vista", "turma_B", "turma_2026"]
    rot = ["39 maduras\n(decide)", "teste 18\n(decide)", "teste sem\nnível", "região\nnão vista", "turma B", "turma 2026\n(precoce)"]
    outros = [k for k in T.index if k != "v2"]
    nc = 4; nl = int(np.ceil(len(outros) / nc))
    fig, axs = plt.subplots(nl, nc, figsize=(20, 4.2 * nl), squeeze=False, sharey=True)
    for ax, k in zip(axs.flat, outros):
        x = np.arange(len(cols))
        ax.bar(x - .2, T.loc["v2", cols].astype(float), .4, color="#bbbbbb", label="v2")
        ax.bar(x + .2, T.loc[k, cols].astype(float), .4, color="#4c72b0", label="este modelo")
        for i_, b_ in enumerate(T.loc[k, cols].astype(float)):
            ax.text(i_ + .2, b_ + .5, f"{b_:.0f}", ha="center", fontsize=6.5)
        ax.set_xticks(x); ax.set_xticklabels(rot, fontsize=6.5)
        ax.set_title(f"{NOMES.get(k, k)}\n→ {T.loc[k, 'leitura']}", fontsize=8)
    for ax in list(axs.flat)[len(outros):]:
        ax.axis("off")
    axs[0, 0].legend(fontsize=7); axs[0, 0].set_ylabel("erro típico (%) — menor = melhor")
    fig.suptitle(f"Cada modelo contra a v2 (cinza). 'Decide' = critério de aprovação (Holm com {crit} braços). Turma B (n ≈ 9) e turma 2026 (n = 8): só sinal.", y=1.01)
    fig.tight_layout(); fig.savefig(out / "03_masters_cada_modelo_contra_v2.png", bbox_inches="tight"); plt.close(fig)
    ok = EVR[EVR.status == "ok"].copy()
    if len(ok):
        ok["rot"] = (ok.unidade_id + " — " + ok.fonte + " " + ok.evento + " " + ok.competencia + np.where(ok.na_rampa, " (rampa)", "")
                     + np.where(ok.sensivel, " [sensível]", ""))
        ok = ok.sort_values(["evento", "fonte", "na_rampa", "competencia"])
        fig, axs = plt.subplots(1, 2, figsize=(18, max(5, .38 * len(ok))), sharey=True)
        yy = np.arange(len(ok))
        for ax, c, rot_ in ((axs[0], "pagantes", "pagantes (balcão)"), (axs[1], "BAL", "balcão em R$")):
            ax.barh(yy - .2, pct(ok[f"dif_{c}"]), .4, color=np.where(ok.evento == "liga", "#dd8452", "#4c72b0"), label="depois − antes")
            ax.barh(yy + .2, pct(ok[f"placebo_{c}"]), .4, color="lightgray", label="placebo (mesma conta 6 meses antes)")
            ax.axvline(0, color="k", lw=.8); ax.set_xlabel(f"{rot_}: variação contra a rede madura (%)")
        axs[0].set_yticks(yy); axs[0].set_yticklabels(ok.rot, fontsize=7); axs[0].legend(fontsize=7)
        fig.suptitle("Antes e depois: o balcão muda quando a unidade LIGA (laranja) ou DESLIGA (azul) um agregador? [sensível] = data duvidosa ou volta em até 6 meses", y=1.01)
        fig.tight_layout(); fig.savefig(out / "04_antes_e_depois.png", bbox_inches="tight"); plt.close(fig)
    if len(EVS):
        chaves = list(dict.fromkeys(EVS.chave))
        nc = 4; nl = int(np.ceil(len(chaves) / nc))
        fig, axs = plt.subplots(nl, nc, figsize=(19, 3.2 * nl), squeeze=False)
        for ax, ch in zip(axs.flat, chaves):
            s_ = EVS[EVS.chave == ch].sort_values("competencia")
            x = np.arange(len(s_))
            ax.plot(x, pct(s_.pagantes), "-o", ms=2, color="#4c72b0", label="pagantes")
            ax.plot(x, pct(s_.alunos_ag), "-o", ms=2, color="#dd8452", label="alunos de agregador")
            t0 = s_.t0.iloc[0]
            if t0 and t0 in set(s_.competencia):
                ax.axvline(int(np.where(s_.competencia.to_numpy() == t0)[0][0]), color="k", ls=":")
            ax.set_xticks(x[::6]); ax.set_xticklabels(s_.competencia.iloc[::6], rotation=45, fontsize=6)
            ax.set_title(ch, fontsize=7); ax.axhline(0, color="gray", lw=.5)
        for ax in list(axs.flat)[len(chaves):]:
            ax.axis("off")
        list(axs.flat)[0].legend(fontsize=6)
        fig.suptitle("Cada evento: a unidade contra a mediana da rede madura no mesmo mês (%, ajustado pela rampa). Pontilhado = mês da mudança.", y=1.01)
        fig.tight_layout(); fig.savefig(out / "05_antes_e_depois_series.png", bbox_inches="tight"); plt.close(fig)


def escrever(destino, ensaio, Bs, T, TL, crit, S1, th, P2, R2, L2, EVR, RE, excl, extra):
    v2, p2_ = T.loc["v2"], T.loc["2p"]
    L = [f"# BLK-UNI-14 — validação ampliada{' (ENSAIO COM RUÍDO — NÃO INTERPRETAR)' if ensaio else ''}", "",
         f"Protocolo `protocolo_uni14.md` v1.1. Rodado em {datetime.now():%Y-%m-%d %H:%M}.", "", "## Como ler", "",
         "- **Erro típico** = quanto a previsão erra numa unidade comum (a mediana das unidades). 22% = a unidade típica fatura 22% a mais ou a menos que o previsto.",
         "- **Erro de uma unidade** = real ÷ previsto − 1. Positivo = faturou ACIMA do previsto.",
         "- **Aviso:** todas as unidades daqui já tinham faturamento visto antes (exploratória, UNI-02, turma B, leitura precoce de 29/09). Nada aqui é teste cego: é "
         "estimação e conferência. O teste cego são as 5 unidades da turma de 2026 que ainda não foram olhadas, em 2027.", "",
         "## Respostas (uma por pedido)", "",
         f"**(a) Modelos separados × v2.** Nas 39 maduras: separados {p2_.LOO_39:.1f}% × v2 {v2.LOO_39:.1f}%. No teste das 18: {p2_.teste_18:.1f}% × {v2.teste_18:.1f}%. "
         f"Na turma B: {p2_.turma_B:.1f}% × {v2.turma_B:.1f}% (n {int(p2_.n_turma_B)}). Na turma de 2026 (precoce): {p2_.turma_2026:.1f}% × {v2.turma_2026:.1f}% "
         f"(n {int(p2_.n_turma_2026)}). Menor = melhor.", ""]
    for fam, rot in (("v2", "na v2"), ("2p", "nos modelos separados")):
        t = th[fam]
        L.append(f"**Sem agregador, {rot}:** quem não tem agregador fica {fpct(t['theta'])} em relação a quem aceita os dois apps ({t['n_nenhum']} sem × {t['n_dois']} com). "
                 f"Sem o RJ: {fpct(t['sens']['sem_RJ'])}. " + ("Passou nos 4 portões e ficou congelado para conferência (não adotado)." if t["ok"] else "Algum portão falhou: NÃO congelado."))
    L.append("")
    d2 = L2[L2.recorte == "todas"]
    L.append("**(b) Turma de 2026, já (precoce, sem veredito):** " + "; ".join(
        f"{r.modelo}: diferença sem − com os dois {fpct(r.diferenca_turma)}, fator estimado {fpct(r.fator_estimado)} → {r.leitura} ({r.sem_agregador_n} sem, {r.os_dois_n} com)"
        for r in d2.itertuples()) + ". Outros recortes na tabela P2.")
    L.append("")
    melhores = [k for k in T.index if T.loc[k, "leitura"] == "MELHORA A PRECISÃO"]
    L.append(f"**(c) Testes de master ({crit} braços no critério):** " + (f"MELHORAM a precisão: {', '.join(NOMES[k] for k in melhores)}." if melhores else
             "nenhum melhora a precisão pela régua (cair ≥ 2 pontos nas 39 E no teste).") + " Números de cada um na tabela P3 e no gráfico 03.")
    L.append("")
    if len(RE):
        frases = [f"{r.tipo} ({r.fase}, {r.n} evento{'s' if r.n > 1 else ''}): balcão em R$ {fpct(r.balcao_rs)}, pagantes {fpct(r.pagantes)}, placebo do balcão "
                  f"{fpct(r.placebo_balcao_rs)} (n {r.n_placebo})" for r in RE[RE.recorte == "todos"].itertuples()]
        L.append("**(d) Antes e depois** (variação contra a rede madura no mesmo mês; placebo = a mesma conta 6 meses antes, onde há dado): " + "; ".join(frases) + ".")
    L += ["", "## P3 — todos os modelos em todos os testes (erro típico, %)", "",
          "| modelo | 39 maduras | teste 18 | teste sem nível | região não vista | turma B | turma 2026 | queda nas 39 (pp) [IC 90%] | queda no teste (pp) [IC 90%] | p | leitura |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, r in T.iterrows():
        q = "" if k == "v2" else f"{r.queda_LOO_pp:+.1f} [{r.ic90_LOO_lo:+.1f}; {r.ic90_LOO_hi:+.1f}]"
        qt = "" if k == "v2" else f"{r.queda_teste_pp:+.1f} [{r.ic90_teste_lo:+.1f}; {r.ic90_teste_hi:+.1f}]"
        p_ = "" if pd.isna(r.get("p_boot", np.nan)) else f"{r.p_boot:.3f}"
        L.append(f"| {NOMES.get(k, k)} | {r.LOO_39:.1f} | {r.teste_18:.1f} | {r.teste_18_recentrado:.1f} | {r.regiao_nao_vista:.1f} | {r.turma_B:.1f} | "
                 f"{r.turma_2026:.1f} | {q} | {qt} | {p_} | {r.leitura} |")
    L += ["", "Modelos separados com braço contra os separados sem braço (o que vem do braço, e não da separação):", "",
          "| modelo | queda nas 39 (pp) | queda no teste (pp) |", "|---|---|---|"] + [
        f"| {NOMES.get(k, k)} | {T.loc[k, 'queda_LOO_pp_vs_2p']:+.1f} | {T.loc[k, 'queda_teste_pp_vs_2p']:+.1f} |" for k in T.index if k.startswith("2p_")]
    gcols = [c for c in TL.columns if c != "n"]
    L += ["", "Região não vista, por dobra (%):", "", "| modelo | " + " | ".join(gcols) + " |", "|---" * (len(gcols) + 1) + "|"] + [
        f"| {NOMES.get(k, k)} | " + " | ".join(f"{r[c]:.1f}" for c in gcols) + " |" for k, r in TL.iterrows()] + ["", f"Unidades por dobra: {TL.n.iloc[0]}.", ""]
    L += [f"Reprodução do UNI-09: calendário do balcão {Bs['calB']:+.4f} (publicado −0,062), do agregador {Bs['calA']:+.4f} (+0,117), s_TP {Bs['s_tp']:.3f} (0,371); "
          f"teste das 18 dos separados {T.loc['2p', 'teste_18']:.1f}% (publicado 22,9%); nas 39, {T.loc['2p', 'LOO_39']:.1f}% por reajuste completo contra "
          f"{UNI09['loo_2p_publicado']}% publicado (o UNI-09 usou um ajuste de nível aproximado). O s_TP fica fixo (das 39) dentro das dobras.",
          f"Tier do cadastro × R$ por passagem nas 39: correlação {extra['corr_tier']:.2f}. O braço D usa as {int(T.loc['v2_D_tier_cadastro', 'n_treino_com_covariavel'])} do "
          "treino com tier declarado; nas demais, vale a previsão do modelo base.",
          "Os braços A e B da v2 repetem os do UNI-13: o veredito do UNI-13 continua valendo, este é complementar. Ridge one-hot nas masters equivale a um efeito "
          "aleatório de master com variância fixada pelo λ.", ""]
    L += ["## P1 — fator sem agregador (estimado sem a turma de 2026)", ""]
    for fam, rot in (("v2", "v2"), ("2p", "duas partes")):
        t = th[fam]
        L.append(f"- **{rot}:** {fpct(t['theta'])}; faixa por reamostragem {fpct(t['amp'][0])} a {fpct(t['amp'][1])}; da menor à maior unidade {fpct(t['ordem'][0])} a {fpct(t['ordem'][1])}. "
                 + "; ".join(f"{k.replace('_', ' ')} {fpct(v)}" for k, v in t["sens"].items()) + ". Portões: " + ", ".join(f"{k} {'OK' if v else 'FALHOU'}" for k, v in t["portoes"].items())
                 + f". Conferência interna (não é teste): nas sem agregador, erro típico {100 * t['chk_sem']:.0f}% sem fator → {100 * t['chk_com']:.0f}% com o fator estimado sem a própria unidade.")
    L += ["- Nos modelos separados, a unidade sem agregador é prevista só pelo balcão, que usa o calendário do balcão (−6%); a v2 usa o do total (−2%). Parte da diferença "
          "entre os dois fatores vem disso (ver 'calendario do total').", "",
          "| unidade | UF | regra | aceite | mudou de aceite | metragem | pop abaixo do treino | erro v2 | erro separados | sobra do balcão (0,60) |", "|---|---|---|---|---|---|---|---|---|---|"] + [
        f"| {u} | {r.uf} | {r.regra} | {r.aceite} | {'sim' if r.mudou_aceite_na_janela else ''} | {r.fonte_m2} | {'sim' if r.pop_abaixo_do_treino else ''} | {fpct(r.e_v2)} | {fpct(r.e_2p)} | "
        f"{'' if pd.isna(r.sobra_balcao_em_alunos_ag_p60) else f'{r.sobra_balcao_em_alunos_ag_p60:.2f}'} |" for u, r in S1.sort_values(["aceite", "e_v2"]).iterrows()]
    L += ["", "Fora da conta (com o motivo): " + ("; ".join(f"{r.unidade_id} ({r.motivo})" for r in excl.itertuples()) if len(excl) else "nenhuma") + ".", "",
          "## P2 — turma de 2026, já (precoce e já vista; sem veredito)", "",
          "'Turma de 2026' = as 16 congeladas em 30/09, não 'todas as abertas em 2026'. Rio Claro, Vicente Pires R8 e Boqueirão (abertas em jan–mar) estão na estimação; "
          "Laranjeiras e Ceilândia QNM24 (abril), na validação.", "",
          "| unidade | aceite | meses de vida | regra | mudou de aceite | " + " | ".join(r.nome for _, r in R2.iterrows()) + " |", "|---" * (5 + len(R2)) + "|"] + [
        f"| {u} | {r.aceite} | {r.meses_de_vida} | {r.regra} | {'sim' if r.mudou_aceite else ''} | " + " | ".join(fpct(r[c]) for c in R2.index) + " |" for u, r in P2.iterrows()]
    L += ["", "| modelo | todas | sem agregador | um só | os dois |", "|---|---|---|---|---|"] + [
        f"| {r.nome} | {r.todas:.1f}% (n {r.n}) | {r['nenhum']:.1f}% (n {r['n_nenhum']}) | {r['um só']:.1f}% (n {r['n_um só']}) | {r['os dois']:.1f}% (n {r['n_os dois']}) |"
        for _, r in R2.iterrows()]
    L += ["", "| modelo | recorte | sem agregador | com os dois | diferença na turma | fator estimado | leitura |", "|---|---|---|---|---|---|---|"] + [
        f"| {r.modelo} | {r.recorte} | {r.sem_agregador_n} | {r.os_dois_n} | {fpct(r.diferenca_turma)} | {fpct(r.fator_estimado)} | {r.leitura} |" for r in L2.itertuples()]
    L += ["", "A projeção pela curva de rampa nos meses 3–5 de vida tem incerteza grande (no faturamento, ~−34% a +22% em torno da mediana); a curva vem de unidades que "
          "abriram com agregador, o que tende a inflar as sem agregador.", "", "## P4 — antes e depois", "",
          "Datas pela Growth (passagens); o TotalPass só entra no Financeiro a partir de out/2023. 'Sensível' = o Financeiro mostra a fonte antes da data da Growth, ou "
          "a unidade volta ao estado anterior em até 6 meses. Placebo = a mesma conta 6 meses antes (o 'depois' do placebo tem 5 meses, para não pegar o mês da mudança). "
          "Quase todos os eventos com antes e depois são de TotalPass: nenhum 'Wellhub liga' tem meses depois suficientes (reler por volta de mar/2027).", ""]
    if len(RE):
        L += ["| tipo | fase | recorte | n | balcão R$ | pagantes | alunos de agregador | total R$ | placebo balcão | n placebo |", "|---|---|---|---|---|---|---|---|---|---|"] + [
            f"| {r.tipo} | {r.fase} | {r.recorte} | {r.n} | {fpct(r.balcao_rs)} | {fpct(r.pagantes)} | {fpct(r.alunos_agregador)} | {fpct(r.total_rs)} | {fpct(r.placebo_balcao_rs)} | {r.n_placebo} |"
            for r in RE.itertuples()]
    L += ["", "| unidade | evento | mês | mês de vida | data | pagantes | balcão R$ | alunos de agregador | total R$ | placebo balcão | situação |", "|---|---|---|---|---|---|---|---|---|---|---|"] + [
        f"| {r.unidade_id} | {r.fonte} {r.evento} | {r.competencia} | {int(r.mes_vida) if r.mes_vida < 999 else '24+'}{' (rampa)' if r.na_rampa else ''} | {r.datacao} | "
        f"{fpct(r.dif_pagantes)} | {fpct(r.dif_BAL)} | {fpct(r.dif_alunos_ag)} | {fpct(r.dif_faturamento)} | {fpct(r.placebo_BAL)} | {r.status}{' [sensível]' if r.sensivel else ''} |"
        for r in EVR.sort_values(["evento", "fonte", "competencia"]).itertuples()]
    destino.write_text("\n".join(L) + "\n", encoding="utf-8")
    return "\n".join(L)


# ------------------------------------------------------------------ principal
def main():
    modo = [m for m in ("--seca", "--ensaio", "--registrar", "--rodar") if m in sys.argv]
    if len(modo) != 1:
        sys.exit("use exatamente um modo: --seca | --ensaio | --registrar | --rodar")
    modo = modo[0]
    if modo == "--registrar":
        if REG_PRE.exists():
            sys.exit("RECUSADO: REGISTRO_PRE.txt ja existe")
        txt = [f"REGISTRO PRE-RODADA BLK-UNI-14 (protocolo v1.1) — {datetime.now():%Y-%m-%d %H:%M}"] + [f"{k}: {Path(p).name}  SHA-256 {sha(p)}" for k, p in insumos().items()]
        REG_PRE.write_text("\n".join(txt) + "\n", encoding="utf-8"); print("\n".join(txt)); print("SHA do REGISTRO_PRE:", sha(REG_PRE)); return
    assert sha(TURMA) == SHA_TURMA and sha(TURMA_V2) == SHA_TURMA_V2
    Bs = base()
    d, tr, te = Bs["d"], Bs["tr"].copy(), Bs["te"].copy()
    SP = specs(Bs)
    m2, fonte = metragem(Bs)
    TV = pd.read_csv(TURMA_V2, sep=";", encoding="utf-8-sig", index_col=0)
    turma_ok = list(TV.index[TV.prev_v2dom_cal2026.notna()])
    candE = [u for u in d.index if u not in tr.index and u not in TV.index and u not in TRAVADAS_FORA]
    SE, descE = desfechos(Bs, candE)
    excl = [dict(x, conjunto="estimação") for x in descE]
    for u in list(SE.index):
        a = Bs["A"].loc[u] if u in Bs["A"].index else None
        if a is None or a[["l_renda_dom", "l_pop", "studios"]].isna().any() or pd.isna(a.get("master_id")):
            excl.append({"unidade_id": u, "motivo": "sem atributo da v2 no cadastro (master/estúdio)", "conjunto": "estimação"}); SE = SE.drop(index=u)
        elif pd.isna(m2.get(u)):
            excl.append({"unidade_id": u, "motivo": "sem metragem", "conjunto": "estimação"}); SE = SE.drop(index=u)
    SV, descV = desfechos(Bs, [u for u in turma_ok if u not in CEGAS])
    excl += [dict(x, conjunto="turma 2026") for x in descV]
    excl += [{"unidade_id": u, "motivo": "travada fora (UNI-13)", "conjunto": "estimação"} for u in TRAVADAS_FORA]
    excl += [{"unidade_id": u, "motivo": "cega da turma de 2026 (1–2 meses de vida)", "conjunto": "turma 2026"} for u in CEGAS]
    excl += [{"unidade_id": u, "motivo": "turma de 2026 sem previsão congelada (sem master/estúdio)", "conjunto": "turma 2026"} for u in TV.index if u not in turma_ok]
    excl = pd.DataFrame(excl).drop_duplicates("unidade_id")
    DE, DV = montar(Bs, SE.index, m2), montar(Bs, SV.index, m2)
    DE["l_rpp_wh"], DV["l_rpp_wh"] = SE.l_rpp_wh_obs, SV.l_rpp_wh_obs
    SE["fonte_m2"] = fonte.reindex(SE.index); SE["pop_abaixo_do_treino"] = (np.exp(DE.l_pop) < np.exp(tr.l_pop.min())).to_numpy()
    corr_tier = float(pd.concat([tr.l_rpp_wh, tr.wh_ord_cad], axis=1).corr(method="spearman").iloc[0, 1])
    if modo == "--seca":
        print("E:"); print(SE.drop(columns=["l_real", "l_real_curva_pagantes", "l_rpp_wh_obs"]).to_string())
        print("V:"); print(SV.drop(columns=["l_real", "l_real_curva_pagantes", "l_rpp_wh_obs"]).to_string())
        print(excl.to_string())
        print("tier cadastro treino/teste/E/V:", int(tr.wh_ord_cad.notna().sum()), int(te.wh_ord_cad.notna().sum()), int(DE.wh_ord_cad.notna().sum()), int(DV.wh_ord_cad.notna().sum()),
              "| R$/passagem treino/teste:", int(tr.l_rpp_wh.notna().sum()), int(te.l_rpp_wh.notna().sum()), "| corr:", round(corr_tier, 3))
        print("calB, calA, s_tp:", round(Bs["calB"], 4), round(Bs["calA"], 4), round(Bs["s_tp"], 4))
        EV, _ = eventos(Bs)
        print(EV[["unidade_id", "fonte", "evento", "competencia", "mes_vida", "datacao", "persiste", "volta_em_ate_6_meses", "status", "sensivel"]].to_string())
        return
    rng = np.random.default_rng(SEED)
    fe = None
    if modo == "--ensaio":
        rz = np.random.default_rng(5)
        for D in (tr, te):
            D["Y_B"] = rz.normal(11.8, .3, len(D)); D["Y_A"] = D.Y_B - 1.1 + rz.normal(0, .3, len(D)); D["Y_tot"] = np.log(np.exp(D.Y_B) + np.exp(D.Y_A))
            D["l_rpp_wh"] = rz.normal(2.9, .2, len(D))
        for S in (SE, SV):
            S["l_real"] = rz.normal(12.3, .35, len(S)); S["l_real_curva_pagantes"] = S.l_real + rz.normal(0, .05, len(S)); S["l_rpp_wh_obs"] = rz.normal(2.9, .2, len(S))
        DE["l_rpp_wh"], DV["l_rpp_wh"] = SE.l_rpp_wh_obs.to_numpy(), SV.l_rpp_wh_obs.to_numpy()
        fe = Bs["f"].copy()
        for c, nv in (("pagantes", 1200), ("BAL", 1.7e5), ("alunos_gympass", 400), ("alunos_totalpass", 200), ("faturamento", 2.3e5)):
            fe[c] = nv * np.exp(rz.normal(0, .3, len(fe)))           # ruido PURO: nenhum valor real
        dest = outd = ENSAIO; dest.mkdir(parents=True, exist_ok=True)
    else:
        linhas = REG_PRE.read_text(encoding="utf-8").splitlines()
        for k, p in insumos().items():
            reg = next(l_ for l_ in linhas if l_.startswith(f"{k}:")).split("SHA-256 ")[1].strip()
            assert sha(p) == reg, f"{k} mudou depois do REGISTRO_PRE"
        if PREV.exists() or RES.exists() or REG_POS.exists():
            sys.exit("RECUSADO: a rodada real ja aconteceu")
        dest, outd = AQUI, OUT
    B_mask = SE.index.isin(TURMA_B)
    R, fits, ext = avalia(Bs, SP, tr, te, {"turma_B": (SE[B_mask], DE[B_mask]), "turma_2026": (SV, DV)})
    T, TL, crit = tabela_modelos(R, ext, SP, rng)
    if modo == "--rodar":                                  # reproduz o UNI-09 e a v2
        assert abs(Bs["calB"] - UNI09["calB"]) < .001 and abs(Bs["calA"] - UNI09["calA"]) < .001 and abs(Bs["s_tp"] - UNI09["s_tp"]) < .001
        assert abs(T.loc["2p", "teste_18"] / 100 - UNI09["teste_2p"]) <= .003, T.loc["2p", "teste_18"]
        assert abs(T.loc["v2", "teste_18"] / 100 - 0.221) <= .003 and abs(T.loc["v2", "LOO_39"] / 100 - 0.235) <= .003
    S1, th = p1(Bs, SP, fits, SE, DE, rng)
    P2, R2, L2 = p2(SV, ext["turma_2026"], th, checar=(modo == "--rodar"))
    EVR, EVS = eventos(Bs, fe)
    RE = resumo_eventos(EVR)
    DT = montar(Bs, turma_ok, m2)
    PT = pd.DataFrame(index=turma_ok)
    v2rec = prever(Bs, SP["v2"], fits["v2"], DT, True)
    if modo == "--rodar":
        chk = np.abs(np.exp(v2rec) / TV.prev_v2dom_cal2026.reindex(turma_ok).to_numpy(float) - 1)
        assert np.nanmax(chk) < .005 and np.isfinite(chk).sum() == 14, chk
    for nome, sp in SP.items():
        if sp.get("diag"):
            continue
        if sp["fam"] == "v2":
            p = prever(Bs, sp, fits[nome], DT, True)
            if sp.get("fallback"):
                PT[f"tem_{colunas(sp)[-1]}"] = np.isfinite(p)
                p = np.where(np.isfinite(p), p, prever(Bs, SP[sp["fallback"]], fits[sp["fallback"]], DT, True))
            PT[f"prev_{nome}_2026"] = np.exp(p)
        else:
            pB, pA, k = prever(Bs, sp, fits[nome], DT, True, partes=True)
            PT[f"log_balcao_sem_k_{nome}_2026"], PT[f"log_agregador_ambos_sem_k_{nome}_2026"], PT[f"k_{nome}"] = pB, pA, k
    for fam in ("v2", "2p"):
        PT[f"fator_sem_agregador_{fam}"] = th[fam]["theta"] if th[fam]["ok"] else np.nan
    PT["s_tp"], PT["calB_2026"], PT["calA_2026"], PT["calT_2026"] = Bs["s_tp"], Bs["calB"], Bs["calA"], Bs["cal"]["l_fat"]
    txt = escrever(dest / RES.name, modo == "--ensaio", Bs, T, TL, crit, S1, th, P2, R2, L2, EVR, RE, excl, {"corr_tier": corr_tier})
    PT.to_csv(dest / PREV.name, sep=";", encoding="utf-8-sig", float_format="%.6f")
    if modo == "--rodar":
        REG_POS.write_text(f"Previsoes da turma de 2026 (BLK-UNI-14, protocolo v1.1) congeladas em {datetime.now():%Y-%m-%d %H:%M}. Pecas das duas partes SEM k (k em coluna).\n"
                           f"{PREV.name}  SHA-256 {sha(PREV)}\n{RES.name}  SHA-256 {sha(RES)}\nREGISTRO_PRE.txt  SHA-256 {sha(REG_PRE)}\n", encoding="utf-8")
        print(REG_POS.read_text(encoding="utf-8"))
    graficos(outd, S1, th, P2, T, EVR, EVS, crit)
    with pd.ExcelWriter(outd / "numeros_dos_graficos.xlsx") as w:
        pd.DataFrame({"campo": ["O que é", "Como ler", "Modelos", "Turma 2026", "Antes e depois", "Cuidado", "Gerado por"], "descrição": [
            "BLK-UNI-14: validação ampliada pedida pelo Felipe em 06/10 (modelos separados, turma de 2026 já, testes de master, antes e depois).",
            "Erro típico = quanto a previsão erra numa unidade comum (mediana). Erro de uma unidade = real ÷ previsto − 1 (positivo = acima do previsto).",
            "v2 = vigente; 2p = duas partes (balcão + agregador). A = masters com peso reduzido; B = mercado de agregador no lugar das masters (nas duas partes: "
            "só no agregador e nas duas); C = estúdio × renda; D = tier do Wellhub do cadastro; D-diag = R$ por passagem (diagnóstico, fora do critério).",
            "Leitura precoce e já vista em 29/09: só sinal, sem veredito. As 5 cegas ficam de fora (1–2 meses).",
            "Datas pela Growth, conferidas no Financeiro; valores contra a mediana da rede madura no mesmo mês. Placebo = a mesma conta 6 meses antes.",
            "Todas as unidades já tinham faturamento visto. Nada foi adotado.", "data/analysis/uni/uni14/01_validacao_ampliada.py (protocolo v1.1)"]}).to_excel(w, sheet_name="LEIA-ME", index=False)
        T.to_excel(w, sheet_name="P3_modelos"); TL.to_excel(w, sheet_name="P3_regiao_por_dobra")
        S1.to_excel(w, sheet_name="P1_unidades"); pd.DataFrame({fam: {**th[fam]["sens"], "fator": th[fam]["theta"]} for fam in th}).to_excel(w, sheet_name="P1_resumo")
        P2.to_excel(w, sheet_name="P2_turma_2026"); R2.to_excel(w, sheet_name="P2_por_aceite"); L2.to_excel(w, sheet_name="P2_leituras", index=False)
        EVR.to_excel(w, sheet_name="P4_eventos", index=False); RE.to_excel(w, sheet_name="P4_resumo", index=False)
        excl.to_excel(w, sheet_name="fora_da_conta", index=False)
        for rot, E in ext.items():
            E.to_excel(w, sheet_name=f"P3_{rot}")
    print(txt if modo == "--rodar" else f"ensaio ok: {dest}")


if __name__ == "__main__":
    main()
