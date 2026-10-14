# -*- coding: utf-8 -*-
"""Ficha tecnica do modelo v2 (pedido do Felipe, 06/10). Versao 2: aplica a verificacao independente wf_8e999bb2-63f
(numeros reproduzidos; corrigidas as leituras: IC/p pelo erro-padrao robusto HC3, R2 x erro tipico, faixa do real so' ilustrativa,
IC por faixa e nas diferencas entre metodos, erro em regiao nao vista, DP assimetrico, bootstrap com reajuste).
Uso: 01_ficha_tecnica.py  (.venv, PYTHONPATH=src). Sem Base Consolidada nem LOCAL_ na saida."""
import importlib.util
import sys
import types
import warnings
from pathlib import Path

try:
    import h3  # noqa: F401
except ImportError:  # o Controle de Aplicativo do Windows bloqueia a DLL do h3; este script nao usa h3
    for _k in [k for k in sys.modules if k == "h3" or k.startswith("h3.")]:
        del sys.modules[_k]
    sys.modules["h3"] = types.ModuleType("h3")

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor  # noqa: E402
from sklearn.linear_model import LassoCV, RidgeCV  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

warnings.filterwarnings("ignore")
AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
OUT = Path(r"C:\Users\Felipe\OneDrive - Grupo Ultra\Área de Trabalho\Análises - Motor de Expansão\Exploratória BLK-UNI\08 - Ficha técnica do modelo v2")
NB = 5000
plt.rcParams.update({"figure.dpi": 110, "savefig.dpi": 150, "font.size": 9, "axes.grid": True, "grid.alpha": .3})


def mod(nome, p):
    s = importlib.util.spec_from_file_location(nome, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def et(e):
    return float(np.median(np.abs(np.exp(np.asarray(e, float)) - 1)))


def r2(y, e):
    y, e = np.asarray(y, float), np.asarray(e, float)
    return float(1 - np.sum(e ** 2) / np.sum((y - y.mean()) ** 2))


def boot(fn, *arrs, nb=NB, seed=1):
    rng = np.random.default_rng(seed); n = len(arrs[0])
    v = [fn(*[a[ii] for a in arrs]) for ii in (rng.integers(0, n, n) for _ in range(nb))]
    return float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))


def dp_lados(e):
    s = float(np.std(e, ddof=1))
    return 100 * (np.exp(-s) - 1), 100 * (np.exp(s) - 1)


def ols(X, y):
    XtXi = np.linalg.inv(X.T @ X); b = XtXi @ X.T @ y; e = y - X @ b
    return b, e, np.einsum("ij,jk,ik->i", X, XtXi, X), XtXi


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    u14 = mod("u14", UNI / "uni14" / "01_validacao_ampliada.py")
    Bs = u14.base()
    tm, d, tr, te, cal = Bs["tm"], Bs["d"], Bs["tr"].copy(), Bs["te"].copy(), Bs["cal"]["l_fat"]
    V2 = Bs["V2"]
    nomes = {"l_m2": "log metragem", "l_renda_dom": "log renda domiciliar (isócrona 10 min)", "l_pop": "log população (isócrona 10 min)",
             "mr_M2": "master M2 (contra M1 = DF/GO)", "mr_M3": "master M3 (contra M1)", "mr_outras": "outras masters (contra M1)", "studios": "tem estúdio"}
    X, y = tm.X_(tr, V2), tr.l_fat.to_numpy(float)
    n, p = X.shape; gl = n - p
    b, e, h, XtXi = ols(X, y)
    s2 = float(e @ e / gl); sigma = np.sqrt(s2)
    se = np.sqrt(np.diag(s2 * XtXi)); se_hc3 = Bs["ex"].se_hc3(X, e, h, XtXi)
    tq = stats.t.ppf(.975, gl)
    cook = (e ** 2 / (p * s2)) * h / (1 - h) ** 2
    infl = tr.index[int(np.argmax(cook))]
    msk = tr.index != infl
    b_sem, *_ = ols(X[msk], y[msk])
    # ---------------------------------------------------------------- 1. coeficientes (IC e p pelo erro-padrao ROBUSTO HC3)
    coef = pd.DataFrame({"variavel": ["intercepto"] + V2, "nome": ["intercepto"] + [nomes[v] for v in V2], "coeficiente": b,
                         "ep_robusto_HC3": se_hc3, "ic95_robusto_lo": b - tq * se_hc3, "ic95_robusto_hi": b + tq * se_hc3,
                         "p_robusto": 2 * stats.t.sf(np.abs(b / se_hc3), gl), "ep_classico": se, "p_classico": 2 * stats.t.sf(np.abs(b / se), gl),
                         f"coef_sem_{infl}": b_sem})
    coef["significativo_robusto_5%"] = coef.p_robusto < .05
    coef["leitura"] = [("" if v == "intercepto" else
                        f"+10% na variável → {100 * (1.1 ** c - 1):+.1f}% no faturamento" if v.startswith("l_") else f"efeito {100 * (np.exp(c) - 1):+.0f}%")
                       for v, c in zip(coef.variavel, coef.coeficiente)]
    R2_in = r2(y, e); R2_adj = 1 - (1 - R2_in) * (n - 1) / gl
    F = (R2_in / (p - 1)) / ((1 - R2_in) / gl); pF = float(stats.f.sf(F, p - 1, gl))
    e_loo = e / (1 - h)
    Xte, yte = tm.X_(te, V2), te.l_fat.to_numpy(float)
    e_te = yte - (Xte @ b + cal)
    # regiao nao vista (deixa um metro inteiro de fora)
    metro = d.iso_metro.reindex(tr.index).fillna(-1).to_numpy()
    e_lomo = np.empty(n)
    for mm in np.unique(metro):
        s_ = metro == mm
        bb, *_ = ols(X[~s_], y[~s_]) if (~s_).sum() > p else (np.linalg.lstsq(X[~s_], y[~s_], rcond=None)[0],)
        e_lomo[s_] = y[s_] - X[s_] @ bb
    # IC do R2 fora da amostra com REAJUSTE (bootstrap de casos; avalia nas unidades que ficaram fora da reamostra)
    rng = np.random.default_rng(7); r2_oob = []
    for _ in range(2000):
        ii = rng.integers(0, n, n); fora = np.setdiff1d(np.arange(n), ii)
        if len(fora) < 8:
            continue
        bb = np.linalg.lstsq(X[ii], y[ii], rcond=None)[0]
        r2_oob.append(r2(y[fora], y[fora] - X[fora] @ bb))
    ic_r2_oob = (float(np.percentile(r2_oob, 2.5)), float(np.median(r2_oob)), float(np.percentile(r2_oob, 97.5)))
    # intervalo de previsao: teste pela formula do OLS; deixa-um-fora pela formula correta s_(i)/sqrt(1-h)
    s_i = np.sqrt((s2 * gl - e ** 2 / (1 - h)) / (gl - 1))
    se_pred_tr = s_i / np.sqrt(1 - h)
    se_pred_te = sigma * np.sqrt(1 + np.einsum("ij,jk,ik->i", Xte, XtXi, Xte))
    cob = {}
    for nivel in (.80, .90):
        cob[nivel] = (float(np.mean(np.abs(e_loo) <= stats.t.ppf(.5 + nivel / 2, gl - 1) * se_pred_tr)),
                      float(np.mean(np.abs(e_te) <= stats.t.ppf(.5 + nivel / 2, gl) * se_pred_te)), stats.t.ppf(.5 + nivel / 2, gl))
    prec = []
    for rot, yy, ee, ic_r2 in (("Ajuste (as próprias 39)", y, e, None),
                               ("Fora da amostra: cada uma das 39 prevista sem ela", y, e_loo, (ic_r2_oob[0], ic_r2_oob[2])),
                               ("Fora da amostra: teste, 18 abertas depois", yte, e_te, boot(lambda a, c: r2(a, c), yte, e_te)),
                               ("Região não vista: metrô inteiro fora do ajuste (39)", y, e_lomo, None)):
        lo, hi = dp_lados(ee)
        prec.append({"medida": rot, "n": len(yy), "R2": r2(yy, ee), "R2_ic95": "" if ic_r2 is None else f"{ic_r2[0]:.2f} a {ic_r2[1]:.2f}",
                     "erro_tipico_%": 100 * et(ee), "erro_tipico_ic95": "{:.0f} a {:.0f}".format(*[100 * v for v in boot(lambda c: et(c), ee)]),
                     "RMSE_log": float(np.sqrt(np.mean(ee ** 2))), "1_desvio_padrao_para_baixo_%": lo, "1_desvio_padrao_para_cima_%": hi,
                     "vies_mediano_%": 100 * (np.exp(np.median(ee)) - 1), "dispersao_do_faturamento_log": float(np.std(yy, ddof=1))})
    PREC = pd.DataFrame(prec)
    # modelo sem masters: R2 e erro tipico lado a lado (R2 e erro tipico apontam vencedores diferentes)
    Vs = [c for c in V2 if not c.startswith("mr_")]
    Xs_, Xts_ = tm.X_(tr, Vs), tm.X_(te, Vs)
    bs, es, hs, _ = ols(Xs_, y); es_loo = es / (1 - hs); es_te = yte - (Xts_ @ bs + cal)
    es_lomo = np.empty(n)
    for mm in np.unique(metro):
        s_ = metro == mm
        bb = np.linalg.lstsq(Xs_[~s_], y[~s_], rcond=None)[0]; es_lomo[s_] = y[s_] - Xs_[s_] @ bb
    COMP = pd.DataFrame([{"modelo": "v2 (com masters)", "R2_fora_39": r2(y, e_loo), "R2_teste": r2(yte, e_te), "erro_tipico_fora_39_%": 100 * et(e_loo),
                          "erro_tipico_teste_%": 100 * et(e_te), "erro_tipico_regiao_nao_vista_%": 100 * et(e_lomo), "RMSE_fora_39": float(np.sqrt(np.mean(e_loo ** 2)))},
                         {"modelo": "v2 sem masters", "R2_fora_39": r2(y, es_loo), "R2_teste": r2(yte, es_te), "erro_tipico_fora_39_%": 100 * et(es_loo),
                          "erro_tipico_teste_%": 100 * et(es_te), "erro_tipico_regiao_nao_vista_%": 100 * et(es_lomo), "RMSE_fora_39": float(np.sqrt(np.mean(es_loo ** 2)))}])
    # ---------------------------------------------------------------- 2. erro por faixa do PREVISTO (com IC), separado treino x teste
    tab = pd.concat([pd.DataFrame({"grupo": "treino (sem ela)", "real": np.exp(y), "previsto": np.exp(y - e_loo), "e": e_loo}, index=tr.index),
                     pd.DataFrame({"grupo": "teste 18", "real": np.exp(yte), "previsto": np.exp(yte - e_te), "e": e_te}, index=te.index)])
    tab["erro_%"] = 100 * (np.exp(tab.e) - 1)
    cortes, rot_f = [0, 175e3, 225e3, 300e3, 1e9], ["até R$ 175 mil", "R$ 175–225 mil", "R$ 225–300 mil", "acima de R$ 300 mil"]
    fx = []
    for base_, col in (("PREVISTO (régua de decisão)", "previsto"), ("REAL (só ilustrativo: viés por construção)", "real")):
        tab[f"faixa_{col}"] = pd.cut(tab[col], cortes, labels=rot_f)
        for fz, g_ in tab.groupby(f"faixa_{col}", observed=True):
            ee = g_.e.to_numpy(); lo, hi = dp_lados(ee) if len(ee) > 1 else (np.nan, np.nan)
            ic = boot(lambda c: et(c), ee); icv = boot(lambda c: 100 * (np.exp(np.median(c)) - 1), ee)
            fx.append({"agrupado_pelo": base_, "faixa": fz, "n": len(g_), "n_treino": int((g_.grupo != "teste 18").sum()), "n_teste": int((g_.grupo == "teste 18").sum()),
                       "erro_tipico_%": 100 * et(ee), "erro_tipico_ic95": f"{100 * ic[0]:.0f} a {100 * ic[1]:.0f}",
                       "vies_mediano_%": 100 * (np.exp(np.median(ee)) - 1), "vies_ic95": f"{icv[0]:+.0f} a {icv[1]:+.0f}",
                       "1_DP_para_baixo_%": lo, "1_DP_para_cima_%": hi})
    FX = pd.DataFrame(fx)
    # ---------------------------------------------------------------- 3. correlacoes individuais (cada fator sozinho x log faturamento; teste no nivel de 2025)
    for D in (tr, te):
        D["mr_M1"] = (D.master_id == "M1").astype(float)
        D["l_preco"] = np.log(pd.to_numeric(d.cad_preco_gold.reindex(D.index), errors="coerce"))
    te["l_fat_2025"] = te.l_fat - cal; tr["l_fat_2025"] = tr.l_fat
    cand = {"l_m2": "log metragem", "l_renda_dom": "log renda domiciliar", "l_pop": "log população", "studios": "tem estúdio", "mr_M1": "master M1 (DF/GO)",
            "mr_M2": "master M2", "mr_M3": "master M3", "mr_outras": "outras masters", "inter_est_renda": "estúdio × renda",
            "wh_ord_cad": "tier do Wellhub (cadastro, FOTO 06/08/26)", "l_preco": "log preço do plano Gold (FOTO 06/08/26)",
            "x1_parceiros_mil": "parceiros de agregador por mil hab. (foto set/26)", "x2_indep_ag": "independentes no agregador (foto set/26)"}
    both = pd.concat([tr, te])
    cr = []
    for v, nm in cand.items():
        for rot, D in (("39 do treino", tr), ("57 (treino + teste)", both)):
            z = D[[v, "l_fat_2025"]].dropna()
            r_, pr = stats.pearsonr(z[v], z.l_fat_2025); zf, sz = np.arctanh(r_), 1 / np.sqrt(len(z) - 3)
            cr.append({"fator": nm, "base": rot, "n": len(z), "pearson_r": r_, "ic95_lo": np.tanh(zf - 1.96 * sz), "ic95_hi": np.tanh(zf + 1.96 * sz), "p_valor": pr,
                       "spearman": stats.spearmanr(z[v], z.l_fat_2025)[0], "R2_sozinho": r_ ** 2, "no_modelo_v2": v in V2})
    CR = pd.DataFrame(cr)
    imp = []
    grupos = {"metragem": ["l_m2"], "renda": ["l_renda_dom"], "população": ["l_pop"], "masters (as 3)": [c for c in V2 if c.startswith("mr_")], "estúdio": ["studios"]}
    for gname, cols in grupos.items():
        Vg = [c for c in V2 if c not in cols]
        bg, eg, hg, _ = ols(tm.X_(tr, Vg), y); eg_te = yte - (tm.X_(te, Vg) @ bg + cal)
        imp.append({"fator retirado": gname, "R2_fora_39_sem_ele": r2(y, eg / (1 - hg)), "variacao_R2_fora_39": r2(y, eg / (1 - hg)) - r2(y, e_loo),
                    "R2_teste_sem_ele": r2(yte, eg_te), "erro_tipico_fora_39_sem_ele_%": 100 * et(eg / (1 - hg)), "erro_tipico_teste_sem_ele_%": 100 * et(eg_te)})
    IMP = pd.DataFrame(imp)
    # ---------------------------------------------------------------- 4. metodos (mesmas variaveis; hiperparametros fixados antes; IC da diferenca contra o OLS)
    Xa_, Xt_ = tr[V2].to_numpy(float), te[V2].to_numpy(float)

    def loo_teste(fz):
        el = np.empty(n)
        for i in range(n):
            m = np.ones(n, bool); m[i] = False
            el[i] = y[i] - fz(Xa_[m], y[m], Xa_[[i]])[0]
        return el, yte - (fz(Xa_, y, Xt_) + cal)

    def f_ols(A, ya, B):
        return np.column_stack([np.ones(len(B)), B]) @ np.linalg.lstsq(np.column_stack([np.ones(len(A)), A]), ya, rcond=None)[0]

    def esc(mk):
        def f_(A, ya, B):
            sc = StandardScaler().fit(A); return mk().fit(sc.transform(A), ya).predict(sc.transform(B))
        return f_

    metodos = {"Média simples (sem modelo)": lambda A, ya, B: np.full(len(B), ya.mean()),
               "Regressão linear OLS em log (v2, método atual)": f_ols,
               "Ridge (encolhe todos os coeficientes)": esc(lambda: RidgeCV(alphas=np.logspace(-3, 3, 25))),
               "Lasso (zera variáveis fracas)": esc(lambda: LassoCV(cv=5, random_state=0, max_iter=20000)),
               "Random Forest (500 árvores)": lambda A, ya, B: RandomForestRegressor(n_estimators=500, min_samples_leaf=3, random_state=0).fit(A, ya).predict(B),
               "Gradient Boosting (família do XGBoost)": lambda A, ya, B: GradientBoostingRegressor(n_estimators=300, learning_rate=.03, max_depth=2, subsample=.8,
                                                                                                    random_state=0).fit(A, ya).predict(B)}
    res = {nm: loo_teste(fz) for nm, fz in metodos.items()}
    SP = u14.specs(Bs)
    R2p, _, _ = u14.avalia(Bs, {k: SP[k] for k in ("v2", "2p")}, tr, te, {})
    res["Duas partes (balcão + agregador, OLS em log cada)"] = (R2p["2p"]["loo"], R2p["2p"]["test"])
    ref_l, ref_t = res["Regressão linear OLS em log (v2, método atual)"]
    mt = []
    for nm, (el, ete) in res.items():
        dl = boot(lambda a, c: r2(y[:len(a)] if False else a, c) - 0, y, el)  # placeholder nao usado
        dif_l = boot(lambda a, c1, c2: r2(a, c1) - r2(a, c2), y, el, ref_l)
        dif_t = boot(lambda a, c1, c2: r2(a, c1) - r2(a, c2), yte, ete, ref_t)
        mt.append({"metodo": nm, "R2_fora_39": r2(y, el), "R2_teste_18": r2(yte, ete), "erro_tipico_fora_39_%": 100 * et(el), "erro_tipico_teste_%": 100 * et(ete),
                   "dif_R2_fora_vs_OLS_ic95": f"{dif_l[0]:+.2f} a {dif_l[1]:+.2f}", "dif_R2_teste_vs_OLS_ic95": f"{dif_t[0]:+.2f} a {dif_t[1]:+.2f}"})
    MT = pd.DataFrame(mt)
    # ---------------------------------------------------------------- bases (contadas dos arquivos)
    tv2 = pd.read_csv(UNI / "previsao_2026" / "previsoes_turma_2026_v2_domiciliar.csv", sep=";", encoding="utf-8-sig", index_col=0)
    tb = pd.read_csv(UNI / "previsao_turma_b" / "previsoes_turma_b_v2_congel1.csv", sep=";", encoding="utf-8-sig", index_col=0)
    mt_time = pd.read_csv(UNI / "coleta_metragem" / "metragem_time_expansao_2026-10-06.csv", sep=";")
    BASES = pd.DataFrame([
        {"base": "Treino", "unidades": len(tr), "o que é": "maduras em 2025 (≥ 12 meses de vida, ≥ 3 meses válidos, com metragem)", "uso": "ajusta o modelo e mede o erro de cada uma prevista sem ela"},
        {"base": "Teste", "unidades": len(te), "o que é": "abertas depois do treino, maduras em 2026 (jan–ago)", "uso": "erro fora do treino — sempre as mesmas 18"},
        {"base": "Turma B", "unidades": int(tb[tb.variante == "principal_time"].shape[0]), "o que é": f"sem metragem até 06/10; o time passou {len(mt_time)} metragens (São Carlos sem cadastro)",
         "uso": "conferência extra (resultado já visto)"},
        {"base": "Turma de 2026", "unidades": int(tv2.prev_v2dom_cal2026.notna().sum()), "o que é": f"{len(tv2)} congeladas em 30/09, {int(tv2.prev_v2dom_cal2026.notna().sum())} com previsão "
         "(5 cegas com 1–2 meses)", "uso": "conferência quando amadurecerem (2027)"}])
    # ---------------------------------------------------------------- graficos
    fig, axs = plt.subplots(1, 2, figsize=(16, 7))
    for g_, c_, mk, sep in (("treino (sem ela)", "#4c72b0", "o", se_pred_tr), ("teste 18", "#c44e52", "s", se_pred_te)):
        s_ = tab[tab.grupo == g_]; q = cob[.80][2] * sep
        axs[0].errorbar(s_.previsto / 1e3, s_.real / 1e3, xerr=[s_.previsto / 1e3 * (1 - np.exp(-q)), s_.previsto / 1e3 * (np.exp(q) - 1)], fmt=mk, color=c_,
                        ecolor=c_, alpha=.75, ms=5, elinewidth=.6, label=f"{g_} (barra = faixa de previsão de 80%)")
    lim = [60, 900]; axs[0].plot(lim, lim, "k-", lw=.8)
    axs[0].set_xscale("log"); axs[0].set_yscale("log"); axs[0].set_xlim(lim); axs[0].set_ylim(lim)
    axs[0].set_xlabel("previsto pela v2 (R$ mil/mês)"); axs[0].set_ylabel("real (R$ mil/mês)"); axs[0].legend(fontsize=8)
    axs[0].set_title(f"Real × previsto. R² fora da amostra {PREC.R2[1]:.2f} (IC {PREC.R2_ic95[1]}); teste {PREC.R2[2]:.2f} (IC {PREC.R2_ic95[2]})", fontsize=9)
    f1 = FX[FX.agrupado_pelo.str.startswith("PREVISTO")].reset_index(drop=True)
    xx = np.arange(len(f1))
    lo_ = [float(s.split(" a ")[0]) for s in f1.erro_tipico_ic95]; hi_ = [float(s.split(" a ")[1]) for s in f1.erro_tipico_ic95]
    axs[1].bar(xx, f1["erro_tipico_%"], .55, color="#4c72b0", yerr=[f1["erro_tipico_%"] - lo_, np.array(hi_) - f1["erro_tipico_%"]], capsize=4, label="erro típico (barra = IC 95%)")
    for i, r_ in f1.iterrows():
        axs[1].text(i, 2, f"n {r_.n}\n({r_.n_treino}+{r_.n_teste})", ha="center", fontsize=7, color="w")
    axs[1].set_xticks(xx); axs[1].set_xticklabels(f1.faixa); axs[1].set_ylabel("erro típico (%)"); axs[1].legend(fontsize=8)
    axs[1].set_title("Erro por faixa do faturamento PREVISTO (treino sem ela + teste). ICs se sobrepõem: faixas não se distinguem", fontsize=9)
    fig.tight_layout(); fig.savefig(OUT / "01_precisao_e_erro_por_faixa.png", bbox_inches="tight"); plt.close(fig)
    fig, axs = plt.subplots(1, 2, figsize=(17, 6.5), gridspec_kw={"width_ratios": [1.2, 1]})
    c57 = CR[CR.base == "57 (treino + teste)"].sort_values("pearson_r")
    yy = np.arange(len(c57))
    axs[0].errorbar(c57.pearson_r, yy, xerr=[c57.pearson_r - c57.ic95_lo, c57.ic95_hi - c57.pearson_r], fmt="o", color="k", ecolor="gray", capsize=3)
    axs[0].axvline(0, color="k", lw=.7); axs[0].set_yticks(yy); axs[0].set_yticklabels([f"{f_} (n {n_})" for f_, n_ in zip(c57.fator, c57.n)], fontsize=8)
    axs[0].set_xlabel("correlação com o log do faturamento (Pearson; barra = IC 95%)"); axs[0].set_title("Cada fator sozinho (57). Barra que cruza o zero = sem relação clara", fontsize=9)
    m_ = MT.set_index("metodo"); xm = np.arange(len(m_))
    axs[1].barh(xm + .2, m_.R2_fora_39, .4, color="#4c72b0", label="R² fora da amostra (39)")
    axs[1].barh(xm - .2, m_.R2_teste_18, .4, color="#c44e52", label="R² no teste (18)")
    axs[1].axvline(0, color="k", lw=.7); axs[1].set_yticks(xm); axs[1].set_yticklabels(m_.index, fontsize=7.5); axs[1].legend(fontsize=7)
    axs[1].set_title("Métodos (maior = melhor). Nenhum se distingue do OLS (IC da diferença na planilha)", fontsize=9)
    fig.tight_layout(); fig.savefig(OUT / "02_correlacoes_e_metodos.png", bbox_inches="tight"); plt.close(fig)
    leia = pd.DataFrame({"campo": ["Método", "R²", "R² do teste > R² do treino?", "Erro típico", "R² × erro típico", "Desvio padrão", "Faixa por REAL",
                                   "Coeficientes", "Fotos posteriores", "Verificação", "Gerado por"], "descrição": [
        "Regressão linear por mínimos quadrados (OLS) no log do faturamento: log fat = a + b1·log m² + b2·log renda domiciliar + b3·log população + masters + estúdio. "
        "Treino: 39 maduras de 2025. Teste: 18 abertas depois, no nível de 2026 (calendário −2%).",
        "Fração da diferença de faturamento entre unidades (em log) que o modelo explica. 'Fora da amostra' = prevista sem participar do ajuste.",
        "Não quer dizer que acerta mais no teste: as 18 são mais dispersas entre si (DP 0,55 contra 0,41), o que infla o R². Compare pelo erro típico.",
        "Mediana de |real ÷ previsto − 1|: o erro de uma unidade comum.",
        "Apontam vencedores diferentes: sem masters, o R² melhora (puxado por poucas unidades extremas) e o erro típico piora (a unidade comum). A v2 foi escolhida pelo erro típico.",
        "Em log, convertido nos dois lados (o erro em % é assimétrico).",
        "Agrupar pelo faturamento REAL cria viés por construção (regressão à média): só ilustrativo. Para decidir, use a faixa do PREVISTO.",
        f"IC e p pelo erro-padrão robusto (HC3), que não supõe erro igual em todas as unidades. Coluna 'coef sem {infl}': a unidade de maior influência.",
        "Tier do Wellhub e preço Gold são fotos de 06/08/2026, posteriores ao faturamento que explicam: correlação, não causa.",
        "Todos os números reproduzidos por recálculo independente (workflow wf_8e999bb2-63f).", "data/analysis/uni/ficha_v2/01_ficha_tecnica.py"]})
    with pd.ExcelWriter(OUT / "ficha_tecnica_v2.xlsx") as w:
        leia.to_excel(w, sheet_name="LEIA-ME", index=False); BASES.to_excel(w, sheet_name="bases", index=False)
        coef.to_excel(w, sheet_name="coeficientes", index=False)
        pd.DataFrame([{"R2": R2_in, "R2_ajustado": R2_adj, "F": F, "p_F": pF, "sigma_log": sigma, "graus_liberdade": gl,
                       "unidade_de_maior_influencia": infl, "cook_max": float(cook.max())}]).to_excel(w, sheet_name="ajuste", index=False)
        PREC.to_excel(w, sheet_name="precisao", index=False); COMP.to_excel(w, sheet_name="com_x_sem_masters", index=False)
        pd.DataFrame([{"nivel": f"{int(100 * k)}%", "dentro_39_sem_ela": v[0], "dentro_teste_18": v[1]} for k, v in cob.items()]).to_excel(w, sheet_name="faixa_de_previsao", index=False)
        FX.to_excel(w, sheet_name="erro_por_faixa", index=False); CR.to_excel(w, sheet_name="correlacoes", index=False)
        IMP.to_excel(w, sheet_name="tirando_cada_fator", index=False); MT.to_excel(w, sheet_name="metodos", index=False)
        tab.to_excel(w, sheet_name="por_unidade")
    pd.set_option("display.width", 260)
    print(BASES[["base", "unidades", "o que é"]].to_string(index=False)); print()
    print(coef[["nome", "coeficiente", "ic95_robusto_lo", "ic95_robusto_hi", "p_robusto", "p_classico", f"coef_sem_{infl}", "leitura"]].round(3).to_string(index=False))
    print(f"R2 {R2_in:.3f} ajustado {R2_adj:.3f} F {F:.2f} p {pF:.4f} sigma {sigma:.3f} gl {gl} | maior influencia {infl} (Cook {cook.max():.2f}) | R2 fora (reajuste) mediana {ic_r2_oob[1]:.2f}")
    print(PREC.round(3).to_string(index=False)); print(COMP.round(3).to_string(index=False))
    print("faixa de previsão:", {f'{int(100 * k)}%': (round(v[0], 2), round(v[1], 2)) for k, v in cob.items()})
    print(FX.round(1).to_string(index=False)); print(CR[CR.base == "57 (treino + teste)"].round(3).to_string(index=False))
    print(IMP.round(3).to_string(index=False)); print(MT.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
