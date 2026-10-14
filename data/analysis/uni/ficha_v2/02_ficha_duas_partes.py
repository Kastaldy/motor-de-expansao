# -*- coding: utf-8 -*-
"""Ficha tecnica dos modelos separados (balcao e agregador; BLK-UNI-09), no mesmo formato da ficha da v2 (pedido do Felipe, 06/10).
Cada parte: OLS no log, mesmas variaveis da v2; balcao = vendas_ux - tem_saude; agregador = gympass + totalpass, normalizado pelo
aceite do cadastro (UNI-09). Total = balcao + fator de aceite x agregador (+ ajuste de nivel k). Confere contra o publicado no UNI-09.
Tambem: correlacao simples x parcial de cada variavel (por que uma variavel com correlacao negativa entra no modelo).
Uso: 02_ficha_duas_partes.py  (.venv, PYTHONPATH=src)."""
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
from scipy import stats  # noqa: E402

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


def boot(fn, *arrs, nb=NB, seed=1):
    rng = np.random.default_rng(seed); n = len(arrs[0])
    v = [fn(*[a[ii] for a in arrs]) for ii in (rng.integers(0, n, n) for _ in range(nb))]
    return float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))


def dp_lados(e):
    e = np.asarray(e, float); e = e[np.isfinite(e)]; s = float(np.std(e, ddof=1))
    return 100 * (np.exp(-s) - 1), 100 * (np.exp(s) - 1)


def ols(X, y):
    XtXi = np.linalg.inv(X.T @ X); b = XtXi @ X.T @ y; e = y - X @ b
    return b, e, np.einsum("ij,jk,ik->i", X, XtXi, X), XtXi


def resid(a, B):
    B1 = np.column_stack([np.ones(len(B)), B]); return a - B1 @ np.linalg.lstsq(B1, a, rcond=None)[0]


def main():
    u14 = mod("u14", UNI / "uni14" / "01_validacao_ampliada.py")
    Bs = u14.base()
    tm, u9, d, tr, te, V2 = Bs["tm"], Bs["u9"], Bs["d"], Bs["tr"].copy(), Bs["te"].copy(), Bs["V2"]
    nomes = {"l_m2": "log metragem", "l_renda_dom": "log renda domiciliar", "l_pop": "log população", "mr_M2": "master M2 (contra M1)",
             "mr_M3": "master M3 (contra M1)", "mr_outras": "outras masters (contra M1)", "studios": "tem estúdio"}
    wh, tp, _ = u9.aceite(d, tr.index); fr = u9.fator(wh, tp, Bs["s_tp"]).to_numpy(float)
    wht, tpt, _ = u9.aceite(d, te.index); ft = u9.fator(wht, tpt, Bs["s_tp"]).to_numpy(float)
    X, Xte = tm.X_(tr, V2), tm.X_(te, V2)
    partes = {"balcão": (tr.Y_B.to_numpy(float), te.Y_B.to_numpy(float), Bs["calB"], np.zeros(len(te))),
              "agregador": (tr.Y_A.to_numpy(float) - np.log(fr), te.Y_A.to_numpy(float), Bs["calA"], np.log(np.where(ft > 0, ft, np.nan)))}
    coefs, prec, cors = [], [], []
    n, p = X.shape; gl = n - p; tq = stats.t.ppf(.975, gl)
    metro = d.iso_metro.reindex(tr.index).fillna(-1).to_numpy()
    for parte, (y, yte, calp, logft) in partes.items():
        b, e, h, XtXi = ols(X, y)
        s2 = float(e @ e / gl); hc3 = Bs["ex"].se_hc3(X, e, h, XtXi)
        for j, v in enumerate(["intercepto"] + V2):
            coefs.append({"parte": parte, "variavel": nomes.get(v, v), "coeficiente": b[j], "ic95_robusto_lo": b[j] - tq * hc3[j], "ic95_robusto_hi": b[j] + tq * hc3[j],
                          "p_robusto": 2 * stats.t.sf(abs(b[j] / hc3[j]), gl),
                          "leitura": "" if v == "intercepto" else (f"+10% → {100 * (1.1 ** b[j] - 1):+.1f}%" if v.startswith("l_") else f"efeito {100 * (np.exp(b[j]) - 1):+.0f}%")})
        e_loo = e / (1 - h)
        e_te = yte - (Xte @ b + calp + logft)
        e_lomo = np.empty(n)
        for mm in np.unique(metro):
            s_ = metro == mm
            bb = np.linalg.lstsq(X[~s_], y[~s_], rcond=None)[0]; e_lomo[s_] = y[s_] - X[s_] @ bb
        for rot, yy, ee in (("ajuste (39)", y, e), ("fora da amostra (39, cada uma sem ela)", y, e_loo), ("teste (18)", yte, e_te), ("região não vista (39)", y, e_lomo)):
            ok = np.isfinite(yy) & np.isfinite(ee); lo, hi = dp_lados(ee[ok])
            prec.append({"parte": parte, "medida": rot, "n": int(ok.sum()), "R2": r2(yy[ok], ee[ok]),
                         "R2_ic95": "" if rot.startswith(("ajuste", "região")) else "{:.2f} a {:.2f}".format(*boot(lambda a, c: r2(a, c), yy[ok], ee[ok])),
                         "erro_tipico_%": 100 * et(ee[ok]), "erro_tipico_ic95": "{:.0f} a {:.0f}".format(*[100 * v for v in boot(lambda c: et(c), ee[ok])]),
                         "1_DP_para_baixo_%": lo, "1_DP_para_cima_%": hi, "vies_mediano_%": 100 * (np.exp(np.median(ee[ok])) - 1)})
        # correlacao simples x parcial (39) e simples nas 57 (teste no nivel de 2025 da parte)
        y57 = np.concatenate([y, yte - calp - np.nan_to_num(logft)])
        D57 = pd.concat([tr[V2], te[V2]])
        for v in V2:
            outras = tr[V2].drop(columns=[v]).to_numpy(float)
            rp = np.corrcoef(resid(tr[v].to_numpy(float), outras), resid(y, outras))[0, 1]
            ok57 = np.isfinite(y57)
            cors.append({"parte": parte, "fator": nomes[v], "corr_simples_39": np.corrcoef(tr[v], y)[0, 1], "corr_parcial_39": rp,
                         "corr_simples_57": np.corrcoef(D57[v].to_numpy(float)[ok57], y57[ok57])[0, 1], "coeficiente_no_modelo": b[1 + V2.index(v)]})
    # v2 (total) para comparar no mesmo quadro
    b0, e0, h0, _ = ols(X, tr.l_fat.to_numpy(float))
    for v in V2:
        outras = tr[V2].drop(columns=[v]).to_numpy(float)
        cors.append({"parte": "faturamento total (v2)", "fator": nomes[v], "corr_simples_39": np.corrcoef(tr[v], tr.l_fat)[0, 1],
                     "corr_parcial_39": np.corrcoef(resid(tr[v].to_numpy(float), outras), resid(tr.l_fat.to_numpy(float), outras))[0, 1],
                     "corr_simples_57": np.corrcoef(pd.concat([tr[v], te[v]]), np.concatenate([tr.l_fat, te.l_fat - Bs["cal"]["l_fat"]]))[0, 1],
                     "coeficiente_no_modelo": b0[1 + V2.index(v)]})
    # total recombinado (o mesmo do UNI-09/UNI-14) e por faixa do previsto
    SP = u14.specs(Bs)
    R, _, _ = u14.avalia(Bs, {k: SP[k] for k in ("v2", "2p")}, tr, te, {})
    for nome, rot in (("v2", "v2 (faturamento total, um modelo)"), ("2p", "separados recombinados (balcão + agregador)")):
        for med, yy, ee in (("fora da amostra (39)", tr.Y_tot.to_numpy(float), R[nome]["loo"]), ("teste (18)", te.Y_tot.to_numpy(float), R[nome]["test"]),
                            ("região não vista (39)", tr.Y_tot.to_numpy(float), R[nome]["lomo"])):
            lo, hi = dp_lados(ee)
            prec.append({"parte": rot, "medida": med, "n": len(yy), "R2": r2(yy, ee),
                         "R2_ic95": "" if med.startswith("região") else "{:.2f} a {:.2f}".format(*boot(lambda a, c: r2(a, c), yy, ee)),
                         "erro_tipico_%": 100 * et(ee), "erro_tipico_ic95": "{:.0f} a {:.0f}".format(*[100 * v for v in boot(lambda c: et(c), ee)]),
                         "1_DP_para_baixo_%": lo, "1_DP_para_cima_%": hi, "vies_mediano_%": 100 * (np.exp(np.median(ee)) - 1)})
    PREC, COEF, COR = pd.DataFrame(prec), pd.DataFrame(coefs), pd.DataFrame(cors)
    # conferencia contra o publicado (UNI-09: R2 fora da amostra das partes 0,41 e 0,32; UNI-14: total 21,8% / 22,9%)
    r2b = PREC[(PREC.parte == "balcão") & PREC.medida.str.startswith("fora")].R2.iloc[0]
    r2a = PREC[(PREC.parte == "agregador") & PREC.medida.str.startswith("fora")].R2.iloc[0]
    tot = PREC[PREC.parte.str.startswith("separados")]
    assert abs(r2b - 0.41) < .01 and abs(r2a - 0.32) < .01, (r2b, r2a)
    assert abs(tot.iloc[0]["erro_tipico_%"] - 21.8) < .1 and abs(tot.iloc[1]["erro_tipico_%"] - 22.9) < .1
    # faixas do previsto (total), separados x v2
    fx = []
    cortes, rot_f = [0, 175e3, 225e3, 300e3, 1e9], ["até R$ 175 mil", "R$ 175–225 mil", "R$ 225–300 mil", "acima de R$ 300 mil"]
    for nome, rot in (("v2", "v2"), ("2p", "separados")):
        ytot = np.concatenate([tr.Y_tot.to_numpy(float), te.Y_tot.to_numpy(float)]); ee = np.concatenate([R[nome]["loo"], R[nome]["test"]])
        prev = np.exp(ytot - ee)
        fxs = pd.cut(prev, cortes, labels=rot_f)
        for fz in rot_f:
            m = np.asarray(fxs == fz)
            if m.sum():
                ic = boot(lambda c: et(c), ee[m])
                fx.append({"modelo": rot, "faixa_do_previsto": fz, "n": int(m.sum()), "erro_tipico_%": 100 * et(ee[m]), "erro_tipico_ic95": f"{100 * ic[0]:.0f} a {100 * ic[1]:.0f}"})
    FX = pd.DataFrame(fx)
    # grafico: simples x parcial
    fig, axs = plt.subplots(1, 3, figsize=(18, 5.5), sharey=True)
    for ax, parte in zip(axs, ("faturamento total (v2)", "balcão", "agregador")):
        c_ = COR[COR.parte == parte].reset_index(drop=True)
        yy = np.arange(len(c_))
        ax.barh(yy + .2, c_.corr_simples_39, .4, color="#bbbbbb", label="correlação simples (sozinha)")
        ax.barh(yy - .2, c_.corr_parcial_39, .4, color="#4c72b0", label="correlação parcial (descontando as outras)")
        ax.axvline(0, color="k", lw=.7); ax.set_yticks(yy); ax.set_yticklabels(c_.fator, fontsize=8); ax.set_title(parte, fontsize=9)
    axs[0].legend(fontsize=7)
    fig.suptitle("Por que uma variável com correlação simples negativa ou nula entra no modelo: o coeficiente segue a correlação PARCIAL (39 maduras)", y=1.02)
    fig.tight_layout(); fig.savefig(OUT / "03_correlacao_simples_x_parcial.png", bbox_inches="tight"); plt.close(fig)
    with pd.ExcelWriter(OUT / "ficha_tecnica_modelos_separados.xlsx") as w:
        pd.DataFrame({"campo": ["Método", "Agregador", "Total", "Correlação parcial", "Conferência", "Gerado por"], "descrição": [
            "Duas regressões lineares (OLS) no log, com as mesmas variáveis da v2: uma para o faturamento de balcão (vendas_ux − Tem Saúde) e outra para o de agregador "
            "(Wellhub + TotalPass). Treino 39 (2025), teste 18 (2026, calendário por parte: balcão −6,2%, agregador +11,7%).",
            "Normalizado pelo aceite do cadastro, como no UNI-09: unidade que só aceita um app tem o agregador escalado para 'como se aceitasse os dois'. "
            "No teste, unidade sem agregador fica fora da parte agregador.",
            "Balcão + fator de aceite × agregador, mais o ajuste de nível k (UNI-09).",
            "Correlação da variável com o faturamento depois de descontar as outras variáveis do modelo: é o que o coeficiente mede.",
            "Bate com o publicado: R² fora da amostra 0,41 (balcão) e 0,32 (agregador) no UNI-09; total 21,8% / 22,9% no UNI-14.",
            "data/analysis/uni/ficha_v2/02_ficha_duas_partes.py"]}).to_excel(w, sheet_name="LEIA-ME", index=False)
        PREC.to_excel(w, sheet_name="precisao", index=False); COEF.to_excel(w, sheet_name="coeficientes", index=False)
        COR.to_excel(w, sheet_name="correlacao_simples_x_parcial", index=False); FX.to_excel(w, sheet_name="erro_por_faixa", index=False)
    pd.set_option("display.width", 250)
    print(PREC.round(3).to_string(index=False)); print()
    print(COEF.round(3).to_string(index=False)); print()
    print(COR.round(2).to_string(index=False)); print()
    print(FX.round(1).to_string(index=False))


if __name__ == "__main__":
    main()
