# -*- coding: utf-8 -*-
"""Tres modelos lado a lado (pedido do Felipe, 06/10): faturamento (v2), balcao e agregador — e o total recombinado das partes —,
cada um em 3 versoes de master: COM masters (como hoje), SEM masters e masters com PESO REDUZIDO (ridge one-hot, lambda por
validacao interna). Mesmas bases (39 treino 2025, 18 teste 2026), mesma regua. Diferenca contra a versao 'com masters' com IC 95%
(bootstrap pareado). Uso: 03_tres_modelos_masters.py  (.venv, PYTHONPATH=src)."""
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
    ok = np.all([np.isfinite(a) for a in arrs], axis=0); arrs = [a[ok] for a in arrs]
    rng = np.random.default_rng(seed); n = len(arrs[0])
    v = [fn(*[a[ii] for a in arrs]) for ii in (rng.integers(0, n, n) for _ in range(nb))]
    return float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))


def main():
    u14 = mod("u14", UNI / "uni14" / "01_validacao_ampliada.py")
    Bs = u14.base()
    tm, u9, d, tr, te = Bs["tm"], Bs["u9"], Bs["d"], Bs["tr"].copy(), Bs["te"].copy()
    V2, ONE = Bs["V2"], Bs["ONE"]
    VA = ["l_m2", "l_renda_dom", "l_pop"] + ONE + ["studios"]
    VR = ["l_m2", "l_renda_dom", "l_pop", "studios"]
    versoes = {"com masters (hoje)": (V2, []), "sem masters": (VR, []), "masters com peso reduzido": (VA, ONE)}
    wh, tp, _ = u9.aceite(d, tr.index); fr = u9.fator(wh, tp, Bs["s_tp"]).to_numpy(float)
    wht, tpt, _ = u9.aceite(d, te.index); ft = u9.fator(wht, tpt, Bs["s_tp"]).to_numpy(float)
    alvos = {"faturamento (v2)": (tr.Y_tot.to_numpy(float), te.Y_tot.to_numpy(float), Bs["cal"]["l_fat"], np.zeros(len(te))),
             "balcão": (tr.Y_B.to_numpy(float), te.Y_B.to_numpy(float), Bs["calB"], np.zeros(len(te))),
             "agregador": (tr.Y_A.to_numpy(float) - np.log(fr), te.Y_A.to_numpy(float), Bs["calA"], np.log(np.where(ft > 0, ft, np.nan)))}
    metro = d.iso_metro.reindex(tr.index).fillna(-1).to_numpy()
    n = len(tr)
    res = {}

    def ajusta(X, y, pen):
        lam = u14.escolhe_lam(X, y, pen) if pen else 0
        return u14.ridge(X, y, pen, lam)[0], lam

    for alvo, (y, yte, calp, logft) in alvos.items():
        for ver, (cols, pen_cols) in versoes.items():
            X, Xte = tm.X_(tr, cols), tm.X_(te, cols)
            pen = [1 + cols.index(c) for c in pen_cols]
            loo = np.empty(n); lams = []
            for i in range(n):
                m = np.ones(n, bool); m[i] = False
                bi, li = ajusta(X[m], y[m], pen); lams.append(li)
                loo[i] = y[i] - X[i] @ bi
            b, lam = ajusta(X, y, pen)
            test = yte - (Xte @ b + calp + logft)
            lomo = np.empty(n)
            for mm in np.unique(metro):
                s_ = metro == mm
                bb, _ = ajusta(X[~s_], y[~s_], pen); lomo[s_] = y[s_] - X[s_] @ bb
            res[(alvo, ver)] = dict(y=y, yte=yte, loo=loo, test=test, lomo=lomo, lam=lam, lams=sorted(set(lams)))
    # total recombinado das partes (mesma regra do UNI-09/UNI-14), nas 3 versoes
    SP = {"com masters (hoje)": dict(fam="2p", B=V2, A=V2), "sem masters": dict(fam="2p", B=VR, A=VR), "masters com peso reduzido": dict(fam="2p", B=VA, A=VA, pen=ONE),
          "balcão sem masters + agregador com masters (pós-hoc)": dict(fam="2p", B=VR, A=V2),
          "balcão sem masters + agregador peso reduzido (pós-hoc)": dict(fam="2p", B=VR, A=VA, pen=ONE)}
    R, _, _ = u14.avalia(Bs, {"v2": u14.specs(Bs)["v2"], **{f"2p::{k}": v for k, v in SP.items()}}, tr, te, {})
    for ver in SP:
        r = R[f"2p::{ver}"]
        res[("total recombinado (balcão + agregador)", ver)] = dict(y=tr.Y_tot.to_numpy(float), yte=te.Y_tot.to_numpy(float), loo=r["loo"], test=r["test"], lomo=r["lomo"], lam=None, lams=[])
    # conferencia com o ja publicado
    chk = res[("faturamento (v2)", "com masters (hoje)")]
    assert abs(r2(chk["y"], chk["loo"]) - 0.264) < .002 and abs(et(chk["test"]) - 0.221) < .002
    assert abs(r2(res[("balcão", "com masters (hoje)")]["y"], res[("balcão", "com masters (hoje)")]["loo"]) - 0.412) < .002
    assert abs(et(res[("total recombinado (balcão + agregador)", "com masters (hoje)")]["test"]) - 0.229) < .002
    linhas = []
    for (alvo, ver), r in res.items():
        base_ = res[(alvo, "com masters (hoje)")]
        L = {"modelo": alvo, "versao": ver, "R2_fora_39": r2(r["y"], r["loo"]), "R2_teste": r2(r["yte"], r["test"]), "n_teste": int(np.isfinite(r["test"]).sum()),
             "erro_tipico_fora_39_%": 100 * et(r["loo"]), "erro_tipico_teste_%": 100 * et(r["test"]), "erro_tipico_regiao_nao_vista_%": 100 * et(r["lomo"]),
             "R2_regiao_nao_vista": r2(r["y"], r["lomo"]), "lambda": r["lam"]}
        if ver != "com masters (hoje)":
            for k, (yy, a, b_) in {"R2_fora": (r["y"], r["loo"], base_["loo"]), "R2_teste": (r["yte"], r["test"], base_["test"])}.items():
                lo, hi = boot(lambda Y, A, B_: r2(Y, A) - r2(Y, B_), yy, a, b_)
                L[f"dif_{k}_vs_com_masters_ic95"] = f"{lo:+.2f} a {hi:+.2f}"
            for k, (a, b_) in {"erro_fora": (r["loo"], base_["loo"]), "erro_teste": (r["test"], base_["test"])}.items():
                lo, hi = boot(lambda A, B_: 100 * (et(A) - et(B_)), a, b_)
                L[f"dif_{k}_pp_vs_com_masters_ic95"] = f"{lo:+.1f} a {hi:+.1f}"
        linhas.append(L)
    T = pd.DataFrame(linhas)
    # grafico: 4 paineis (3 modelos + total recombinado), 3 versoes, metricas principais
    cores = {"com masters (hoje)": "#7f7f7f", "sem masters": "#4c72b0", "masters com peso reduzido": "#55a868"}
    mets = [("R2_fora_39", "R² fora da\namostra (39)"), ("R2_teste", "R² no\nteste (18)")]
    mete = [("erro_tipico_fora_39_%", "erro típico\nfora (39)"), ("erro_tipico_teste_%", "erro típico\nteste (18)"), ("erro_tipico_regiao_nao_vista_%", "erro típico\nregião não vista")]
    fig, axs = plt.subplots(2, 4, figsize=(21, 9))
    for j, alvo in enumerate(["faturamento (v2)", "balcão", "agregador", "total recombinado (balcão + agregador)"]):
        for i, (grupo, ax) in enumerate(((mets, axs[0, j]), (mete, axs[1, j]))):
            x = np.arange(len(grupo))
            vers_ = list(T[T.modelo == alvo].versao); w_ = .8 / len(vers_)
            for k, ver in enumerate(vers_):
                vals = [T[(T.modelo == alvo) & (T.versao == ver)][c].iloc[0] for c, _ in grupo]
                pos = x + (k - (len(vers_) - 1) / 2) * w_
                ax.bar(pos, vals, w_, color=cores.get(ver, "#dd8452" if "com masters (pós" in ver else "#c44e52"), label=ver)
                for xi, v in zip(pos, vals):
                    ax.text(xi, v + (0.01 if i == 0 else 0.8), f"{v:.2f}" if i == 0 else f"{v:.0f}", ha="center", fontsize=6)
            ax.set_xticks(x); ax.set_xticklabels([r_ for _, r_ in grupo], fontsize=7.5); ax.axhline(0, color="k", lw=.6)
            ax.set_title(alvo if i == 0 else "", fontsize=9)
        axs[0, j].set_ylabel("R² (maior = melhor)" if j == 0 else ""); axs[1, j].set_ylabel("erro típico % (menor = melhor)" if j == 0 else "")
    axs[0, 0].legend(fontsize=7); axs[0, 3].legend(fontsize=6)
    fig.suptitle("Três modelos lado a lado (e o total recombinado das partes), com e sem masters. O R² de cada parte é medido no próprio alvo.", y=1.01)
    fig.tight_layout(); fig.savefig(OUT / "04_tres_modelos_com_e_sem_masters.png", bbox_inches="tight"); plt.close(fig)
    with pd.ExcelWriter(OUT / "tres_modelos_masters.xlsx") as w:
        pd.DataFrame({"campo": ["Modelos", "Versões", "R²", "Diferença", "Conferência", "Gerado por"], "descrição": [
            "Faturamento (v2), balcão e agregador: regressão linear (OLS) no log, mesmas variáveis; total recombinado = balcão + fator de aceite × agregador (UNI-09).",
            "Com masters (hoje); sem masters; masters com peso reduzido (ridge só nas masters, one-hot, λ escolhido por validação interna em cada rodada).",
            "O R² de cada parte é medido no próprio alvo (balcão contra o balcão real; agregador contra o agregador real) e não se compara direto ao do faturamento. "
            "A comparação na mesma moeda é o total recombinado contra a v2.",
            "Contra a versão 'com masters' do mesmo modelo, IC 95% por bootstrap pareado: se o intervalo cruza o zero, a diferença não é distinguível.",
            "Reproduz o publicado (v2 R² fora 0,264 e teste 22,1%; balcão R² fora 0,412; total recombinado no teste 22,9%) e foi recalculada de forma independente "
            "(workflow wf_77881a53-dec): todos os números batem.",
            "data/analysis/uni/ficha_v2/03_tres_modelos_masters.py"]}).to_excel(w, sheet_name="LEIA-ME", index=False)
        pd.DataFrame({"ressalva": [
            "O R² fora do agregador é medido no alvo normalizado pelo aceite (como o modelo é ajustado); no agregador cru fica 0,27 com masters e −0,01 sem.",
            "No agregador o teste tem 17 unidades: Botafogo não tem agregador e fica fora.",
            "Botafogo pesa 36% a 59% do erro quadrático do teste (única M3 e única sem agregador no teste): o R² do teste depende dela. "
            "Sem ela, o ganho do balcão sem masters no R² do teste cai de +0,22 para +0,08.",
            "'Região não vista' mistura master com região: 16 das 17 unidades M1 (referência) são de Brasília. Tirando Brasília do ajuste, a M1 fica com 1 unidade.",
            "As duas combinações marcadas 'pós-hoc' foram montadas depois de ver o teste: o erro de teste delas é otimista. No deixa-um-fora, que não foi usado na escolha, "
            "elas não ganham.",
            "Os IC das diferenças reamostram os erros já calculados (sem reajustar) e são 95% sem correção para várias comparações: são descritivos. Pelo erro típico, "
            "nenhuma diferença exclui o zero."]}).to_excel(w, sheet_name="RESSALVAS", index=False)
        T.to_excel(w, sheet_name="tres_modelos", index=False)
    pd.set_option("display.width", 260)
    print(T.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
