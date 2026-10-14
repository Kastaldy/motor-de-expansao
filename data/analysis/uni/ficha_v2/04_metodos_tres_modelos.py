# -*- coding: utf-8 -*-
"""Outros tipos de modelo (ML) nos TRES modelos (pedido do Felipe, 06/10): faturamento, balcao, agregador e o total recombinado.
Metodos: media simples, OLS (atual), Ridge, Lasso, Random Forest, Gradient Boosting (familia do XGBoost). Mesmas variaveis da v2
(com masters), mesmas bases (39 treino 2025 / 18 teste 2026), hiperparametros fixados antes (iguais aos da ficha da v2).
Total recombinado = log(exp(balcao) + fator de aceite x exp(agregador)), sem o ajuste de nivel k (igual para todos os metodos).
Confere: linhas do faturamento = ficha_tecnica_v2 (verificada); OLS de cada parte = ficha dos modelos separados (verificada).
Uso: 04_metodos_tres_modelos.py  (.venv, PYTHONPATH=src)."""
import importlib.util
import sys
import types
import warnings
from pathlib import Path

try:
    import h3  # noqa: F401
except ImportError:
    for _k in [k for k in sys.modules if k == "h3" or k.startswith("h3.")]:
        del sys.modules[_k]
    sys.modules["h3"] = types.ModuleType("h3")

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
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
    e = np.asarray(e, float); e = e[np.isfinite(e)]
    return float(np.median(np.abs(np.exp(e) - 1)))


def r2(y, e):
    y, e = np.asarray(y, float), np.asarray(e, float); ok = np.isfinite(y) & np.isfinite(e); y, e = y[ok], e[ok]
    return float(1 - np.sum(e ** 2) / np.sum((y - y.mean()) ** 2))


def boot_dif(fn, y, a, b, nb=NB, seed=1):
    ok = np.isfinite(y) & np.isfinite(a) & np.isfinite(b); y, a, b = y[ok], a[ok], b[ok]
    rng = np.random.default_rng(seed); n = len(y)
    v = [fn(y[ii], a[ii]) - fn(y[ii], b[ii]) for ii in (rng.integers(0, n, n) for _ in range(nb))]
    return float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))


def f_ols(A, ya, B):
    return np.column_stack([np.ones(len(B)), B]) @ np.linalg.lstsq(np.column_stack([np.ones(len(A)), A]), ya, rcond=None)[0]


def esc(mk):
    def f_(A, ya, B):
        sc = StandardScaler().fit(A); return mk().fit(sc.transform(A), ya).predict(sc.transform(B))
    return f_


METODOS = {"Média simples (sem modelo)": lambda A, ya, B: np.full(len(B), ya.mean()),
           "Regressão linear OLS (atual)": f_ols,
           "Ridge": esc(lambda: RidgeCV(alphas=np.logspace(-3, 3, 25))),
           "Lasso": esc(lambda: LassoCV(cv=5, random_state=0, max_iter=20000)),
           "Random Forest": lambda A, ya, B: RandomForestRegressor(n_estimators=500, min_samples_leaf=3, random_state=0).fit(A, ya).predict(B),
           "Gradient Boosting (família XGBoost)": lambda A, ya, B: GradientBoostingRegressor(n_estimators=300, learning_rate=.03, max_depth=2, subsample=.8,
                                                                                            random_state=0).fit(A, ya).predict(B)}


def main():
    u14 = mod("u14", UNI / "uni14" / "01_validacao_ampliada.py")
    Bs = u14.base()
    u9, d, tr, te, V2 = Bs["u9"], Bs["d"], Bs["tr"], Bs["te"], Bs["V2"]
    wh, tp, _ = u9.aceite(d, tr.index); fr = u9.fator(wh, tp, Bs["s_tp"]).to_numpy(float)
    wht, tpt, _ = u9.aceite(d, te.index); ft = u9.fator(wht, tpt, Bs["s_tp"]).to_numpy(float)
    Xa, Xt = tr[V2].to_numpy(float), te[V2].to_numpy(float)
    n = len(tr)
    alvos = {"faturamento": (tr.Y_tot.to_numpy(float), te.Y_tot.to_numpy(float), Bs["cal"]["l_fat"], np.zeros(len(te))),
             "balcão": (tr.Y_B.to_numpy(float), te.Y_B.to_numpy(float), Bs["calB"], np.zeros(len(te))),
             "agregador": (tr.Y_A.to_numpy(float) - np.log(fr), te.Y_A.to_numpy(float), Bs["calA"], np.log(np.where(ft > 0, ft, np.nan)))}
    P = {}                              # (alvo, metodo) -> (pred_loo_treino, pred_teste) em log, ja' no nivel/fator do proprio alvo
    for alvo, (y, yte, calp, logft) in alvos.items():
        for nm, fz in METODOS.items():
            pl = np.empty(n)
            for i in range(n):
                m = np.ones(n, bool); m[i] = False
                pl[i] = fz(Xa[m], y[m], Xa[[i]])[0]
            P[(alvo, nm)] = (pl, fz(Xa, y, Xt) + calp + logft)
    linhas, base = [], {}
    for alvo, (y, yte, calp, logft) in alvos.items():
        for nm in METODOS:
            pl, pt = P[(alvo, nm)]
            base[(alvo, nm)] = (y - pl, yte - pt)
    # total recombinado das partes (mesmo metodo nas duas), sem ajuste de nivel k
    ytot, ytot_te = tr.Y_tot.to_numpy(float), te.Y_tot.to_numpy(float)
    for nm in METODOS:
        pB_l, pB_t = P[("balcão", nm)]; pA_l, pA_t = P[("agregador", nm)]
        pA_t_amb = pA_t - np.log(np.where(ft > 0, ft, np.nan))      # agregador 'se aceitasse os dois' no teste
        tot_l = np.log(np.exp(pB_l) + fr * np.exp(pA_l))
        tot_t = np.log(np.exp(pB_t) + ft * np.exp(np.nan_to_num(pA_t_amb, nan=0.0)))
        base[("balcão + agregador somados", nm)] = (ytot - tot_l, ytot_te - tot_t)
    alvos_y = {"faturamento": (alvos["faturamento"][0], alvos["faturamento"][1]), "balcão": (alvos["balcão"][0], alvos["balcão"][1]),
               "agregador": (alvos["agregador"][0], alvos["agregador"][1]), "balcão + agregador somados": (ytot, ytot_te)}
    for (alvo, nm), (el, ete) in base.items():
        y, yte = alvos_y[alvo]
        ref_l, ref_t = base[(alvo, "Regressão linear OLS (atual)")]
        L = {"modelo": alvo, "metodo": nm, "R2_fora_39": r2(y, el), "R2_teste": r2(yte, ete), "n_teste": int(np.isfinite(ete).sum()),
             "erro_tipico_fora_%": 100 * et(el), "erro_tipico_teste_%": 100 * et(ete)}
        if nm != "Regressão linear OLS (atual)":
            lo, hi = boot_dif(lambda Y, E: 100 * et(E), y, el, ref_l); L["dif_erro_fora_pp_vs_OLS_ic95"] = f"{lo:+.1f} a {hi:+.1f}"
            lo, hi = boot_dif(lambda Y, E: 100 * et(E), yte, ete, ref_t); L["dif_erro_teste_pp_vs_OLS_ic95"] = f"{lo:+.1f} a {hi:+.1f}"
            lo, hi = boot_dif(r2, y, el, ref_l); L["dif_R2_fora_vs_OLS_ic95"] = f"{lo:+.2f} a {hi:+.2f}"
        linhas.append(L)
    T = pd.DataFrame(linhas)
    # conferencias contra numeros ja verificados
    g = lambda a, m, c: float(T[(T.modelo == a) & (T.metodo == m)][c].iloc[0])
    assert abs(g("faturamento", "Regressão linear OLS (atual)", "R2_fora_39") - .264) < .002 and abs(g("faturamento", "Regressão linear OLS (atual)", "erro_tipico_teste_%") - 22.1) < .1
    for m_, (a_, b_) in {"Ridge": (.302, .365), "Lasso": (.253, .424), "Random Forest": (.292, .394), "Gradient Boosting (família XGBoost)": (.089, .352)}.items():
        assert abs(g("faturamento", m_, "R2_fora_39") - a_) < .002 and abs(g("faturamento", m_, "R2_teste") - b_) < .002, m_
    assert abs(g("balcão", "Regressão linear OLS (atual)", "R2_fora_39") - .412) < .002 and abs(g("agregador", "Regressão linear OLS (atual)", "R2_teste") - .453) < .002
    # grafico
    fig, axs = plt.subplots(1, 4, figsize=(21, 6), sharey=True)
    for ax, alvo in zip(axs, ["faturamento", "balcão", "agregador", "balcão + agregador somados"]):
        t_ = T[T.modelo == alvo].reset_index(drop=True); yy = np.arange(len(t_))
        ax.barh(yy + .2, t_["erro_tipico_fora_%"], .4, color="#4c72b0", label="erro típico fora da amostra (39)")
        ax.barh(yy - .2, t_["erro_tipico_teste_%"], .4, color="#c44e52", label="erro típico no teste (18)")
        for i, r_ in t_.iterrows():
            ax.text(r_["erro_tipico_fora_%"] + .5, i + .2, f"{r_['erro_tipico_fora_%']:.0f}", va="center", fontsize=7)
            ax.text(r_["erro_tipico_teste_%"] + .5, i - .2, f"{r_['erro_tipico_teste_%']:.0f}", va="center", fontsize=7)
        ax.set_yticks(yy); ax.set_yticklabels(t_.metodo, fontsize=8); ax.set_title(alvo, fontsize=10); ax.set_xlabel("erro típico (%) — menor = melhor")
    axs[0].legend(fontsize=7)
    fig.suptitle("Outros métodos nos três modelos e no total somado (mesmas variáveis, mesmas bases)", y=1.02)
    fig.tight_layout(); fig.savefig(OUT / "05_metodos_ml_tres_modelos.png", bbox_inches="tight"); plt.close(fig)
    with pd.ExcelWriter(OUT / "metodos_ml_tres_modelos.xlsx") as w:
        pd.DataFrame({"campo": ["O que é", "Métodos", "Total somado", "Diferença", "Conferência", "Gerado por"], "descrição": [
            "Os mesmos dados e variáveis da v2 (com masters) em 6 métodos, para os três modelos (faturamento, balcão, agregador) e para o total somado das partes.",
            "Média simples (referência), regressão linear OLS (atual), Ridge, Lasso, Random Forest (500 árvores) e Gradient Boosting (família do XGBoost). "
            "Hiperparâmetros fixados antes, iguais aos da ficha da v2; Ridge/Lasso com escolha interna em cada rodada.",
            "log(exp(balcão) + fator de aceite × exp(agregador)), com o mesmo método nas duas partes, sem o ajuste de nível k (igual para todos).",
            "Contra o OLS do mesmo modelo, IC 95% por bootstrap pareado (descritivo): se cruza o zero, a diferença não é distinguível.",
            "Faturamento reproduz a ficha da v2 (verificada); OLS de balcão e agregador reproduz a ficha dos modelos separados (verificada).",
            "data/analysis/uni/ficha_v2/04_metodos_tres_modelos.py"]}).to_excel(w, sheet_name="LEIA-ME", index=False)
        T.to_excel(w, sheet_name="metodos", index=False)
    pd.set_option("display.width", 250)
    print(T.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
