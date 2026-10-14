# -*- coding: utf-8 -*-
"""Diagnostico lado a lado: modelo de FATURAMENTO x modelo de ALUNOS/M2 (Ultra, N=54, mesmas unidades, LOO).

MF: log(faturamento) ~ log m2 + log renda 10 min + log pop 10 min
MA: log(alunos/m2)   ~ log m2 + log renda 10 min + log pop 10 min   (alunos = ativos ago/26; faturamento via receita/aluno)
Referencia: V = viabilidade atual (mediana de alunos/m2 dos comparaveis por metragem).
Metricas fora da amostra: R2 (escala log e escala real), Spearman, erro % mediano, MAPE, p75, p90.
Outliers: (a) quem sao os maiores erros; (b) metricas sem os 5 piores e sem os 10% piores (recalculadas: o modelo e'
reajustado sem eles); (c) distancia de Cook; (d) regressao robusta (Huber); (e) jackknife do R2.
Grafico: previsto x real dos dois modelos, com os maiores erros rotulados.
"""
import importlib.util
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from shapely import wkb
from sklearn.linear_model import HuberRegressor, LinearRegression

warnings.filterwarnings("ignore")
ISO = Path(r"C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\9259d0a1-7dda-49bd-a390-c88f3d4ac1a6\scratchpad\iso")
sys.path.insert(0, r"C:\dev\motor-de-expansao\src")
from motor_expansao.dimensionamento.viabilidade_ponto import faixa_alunos_por_densidade  # noqa: E402
def mod(n, f):
    s = importlib.util.spec_from_file_location(n, ISO / f); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
v2 = mod("v2", "14_aproveitamento_v2.py"); r17 = mod("r17", "17_regressao.py")
OUT = ISO / "regressao"; MD = []
VARS = ["log_metragem", "log_renda", "log_pop"]


def loo(X, y, est=LinearRegression):
    p = np.zeros(len(y))
    for i in range(len(y)):
        m = np.ones(len(y), bool); m[i] = False
        p[i] = est().fit(X[m], y[m]).predict(X[i:i + 1])[0]
    return p


def metricas(real, prev):
    e = np.abs(prev / real - 1)
    lr, lp = np.log(real), np.log(prev)
    return {"R2_log": 1 - ((lr - lp) ** 2).sum() / ((lr - lr.mean()) ** 2).sum(),
            "R2_real": 1 - ((real - prev) ** 2).sum() / ((real - real.mean()) ** 2).sum(),
            "rho": spearmanr(real, prev)[0], "erro_mediano": np.median(e), "MAPE": e.mean(),
            "erro_p75": np.percentile(e, 75), "erro_p90": np.percentile(e, 90)}


def main():
    ac, tree = v2.oferta()
    fech = pd.read_parquet(v2.SC / "fech_mensal_financeiro.parquet")
    fin = fech[fech.origem_faturamento.eq("financeiro") & fech.mes_completo & fech.operacao_mes_cheio]
    fat = fin[fin.competencia == "2026-08"].set_index("unidade_id")["faturamento"].copy(); fat.loc["guaruja-sp"] = 217525.74
    ativos = fech[fech.competencia == "2026-08"].set_index("unidade_id")["ativos"]
    at12 = fech[fech.competencia.between("2025-09", "2026-08")].groupby("unidade_id")["ativos"].median()
    bu = pd.read_parquet(ISO / "testes_v2" / "base_ultra.parquet").rename(columns={"unidade_id": "pid"})
    bu["rede"] = "ultra"; bu["fat"] = bu.pid.map(fat); bu["alunos"] = bu.pid.map(ativos); bu["ativos_ref"] = bu.pid.map(at12)
    ultra_ref = bu.dropna(subset=["lat"])[["pid", "lat", "lng", "ativos_ref"]]
    iso = pd.concat([pd.read_parquet(f, columns=["ponto_id", "tipo", "modo", "limite_s", "poligono_wkb"], filters=[("tipo", "==", "ultra")]) for f in sorted((ISO / "isocronas_v2").glob("metro_*.parquet"))])
    polys = {c: dict(zip(s.ponto_id, gpd.GeoSeries([wkb.loads(b) for b in s.poligono_wkb], crs=4326).to_crs(5880).values)) for c, (m, l) in v2.CEN.items() for s in [iso[(iso.modo == m) & (iso.limite_s == l) & iso.poligono_wkb.notna()]]}
    A = bu[bu.metragem.notna() & bu.fat.notna() & bu.alunos.notna() & ~bu.confianca.eq("baixa") & bu["pop__carro_10"].notna()].reset_index(drop=True)
    A = v2.crescimento(v2.componentes(A, polys, ac, tree, ultra_ref, auto_m=2.0))
    X = r17.features(A)[VARS].to_numpy(float)
    m2, al, fa = A.metragem.to_numpy(float), A.alunos.to_numpy(float), A.fat.to_numpy(float)
    tk = np.array([np.median(np.delete(fa / al, i)) for i in range(len(A))])

    def prever(idx, est=LinearRegression):
        Xs, m2s, als, fas = X[idx], m2[idx], al[idx], fa[idx]
        tks = np.array([np.median(np.delete(fas / als, i)) for i in range(len(idx))])
        mf = np.exp(loo(Xs, np.log(fas), est))
        ma_al = m2s * np.exp(loo(Xs, np.log(als / m2s), est))
        v_al = np.zeros(len(idx))
        for i in range(len(idx)):
            mk = np.ones(len(idx), bool); mk[i] = False
            base = pd.DataFrame({"metragem": m2s[mk], "alunos_por_m2": als[mk] / m2s[mk]})
            v_al[i] = faixa_alunos_por_densidade(float(m2s[i]), base)["faixa_alunos_p50"]
        return {"MF faturamento": mf, "MA alunos/m2 -> faturamento": ma_al * tks, "V viabilidade -> faturamento": v_al * tks,
                "MA alunos/m2 -> alunos": ma_al, "V viabilidade -> alunos": v_al}, fas, als, m2s

    todos = np.arange(len(A))
    P, fas, als, m2s = prever(todos)
    MD.append(f"# Diagnóstico: modelo de faturamento x modelo de alunos/m² (Ultra, N = {len(A)}, fora da amostra LOO)\n")
    MD.append("## 1. Variáveis e pesos (ajuste em todas as unidades; coeficientes em log, IC95 bootstrap)\n")
    rng = np.random.default_rng(42); linhas = []
    for nome, y in (("MF: log faturamento", np.log(fa)), ("MA: log alunos/m²", np.log(al / m2))):
        c = LinearRegression().fit(X, y); bs = np.array([LinearRegression().fit(X[i], y[i]).coef_ for i in (rng.integers(0, len(y), len(y)) for _ in range(2000))])
        r2in = c.score(X, y)
        for j, v in enumerate(VARS):
            linhas.append({"modelo": nome, "variavel": v, "coef": c.coef_[j], "IC95": f"[{np.percentile(bs[:,j],2.5):+.2f}; {np.percentile(bs[:,j],97.5):+.2f}]", "R2_dentro_da_amostra": r2in})
    MD.append(pd.DataFrame(linhas).round(3).to_markdown(index=False))
    MD.append("\nLeitura: em MF o coeficiente de m² é a elasticidade do faturamento ao tamanho; em MA, o de m² é essa elasticidade menos 1 (densidade cai com o tamanho). Renda e população têm o mesmo significado nos dois.\n")
    MD.append("## 2. Precisão fora da amostra (todas as 54)\n")
    t = pd.DataFrame([{"modelo": k, **metricas(fas if "faturamento" in k else als, v)} for k, v in P.items()])
    MD.append(t.round(3).to_markdown(index=False))
    # --- erros por unidade
    E = pd.DataFrame({"unidade": A.pid, "m2": m2, "faturamento": fa.round(0), "alunos": al, "alunos_por_m2": (al / m2).round(2), "fat_por_aluno": (fa / al).round(0)})
    for k, v in P.items():
        real = fas if "faturamento" in k else als
        E[f"erro_{k.split()[0]}_{'fat' if 'faturamento' in k else 'al'}"] = (v / real - 1).round(3)
    E["abs_MF"] = E["erro_MF_fat"].abs(); E["abs_MA"] = E["erro_MA_fat"].abs()
    MD.append("\n## 3. Onde o erro está (erro = previsto/real − 1; negativo = unidade fatura MAIS que o previsto)\n")
    MD.append("**Distribuição do erro absoluto (faturamento):**\n")
    q = [0.1, 0.25, 0.5, 0.75, 0.9, 1.0]
    MD.append(pd.DataFrame({"quantil": [f"p{int(x*100)}" for x in q], "MF": np.quantile(E.abs_MF, q), "MA": np.quantile(E.abs_MA, q), "V": np.quantile(E["erro_V_fat"].abs(), q)}).round(3).to_markdown(index=False))
    MD.append("\n**10 maiores erros (MF) e o que eles têm em comum:**\n")
    MD.append(E.sort_values("abs_MF", ascending=False).head(10)[["unidade", "m2", "faturamento", "alunos", "alunos_por_m2", "fat_por_aluno", "erro_MF_fat", "erro_MA_fat", "erro_V_fat"]].to_markdown(index=False))
    rt = np.corrcoef(E.abs_MF, E.abs_MA)[0, 1]
    MD.append(f"\nCorrelação entre os erros absolutos de MF e MA: {rt:+.2f} (perto de 1 = erram nas mesmas unidades).")
    share = E.abs_MF.sort_values(ascending=False); tot = (share ** 2).sum()
    MD.append(f"Parcela do erro quadrático total (MF) concentrada nas 5 piores unidades: {(share.head(5) ** 2).sum() / tot:.0%}; nas 10 piores: {(share.head(10) ** 2).sum() / tot:.0%}.")
    # --- sem outliers (reajuste)
    MD.append("\n## 4. É outlier ou é o padrão? (modelos REAJUSTADOS sem as unidades removidas, LOO)\n")
    linhas = []
    ordem = E.sort_values("abs_MF", ascending=False).index.to_numpy()
    for rot, idx in (("todas (54)", todos), ("sem as 5 piores", np.setdiff1d(todos, ordem[:5])), ("sem os 10% piores (6)", np.setdiff1d(todos, ordem[:6])), ("sem os 20% piores (11)", np.setdiff1d(todos, ordem[:11]))):
        Pk, fk, ak, _ = prever(idx)
        for k in ("MF faturamento", "MA alunos/m2 -> faturamento", "V viabilidade -> faturamento"):
            linhas.append({"amostra": rot, "modelo": k, **{m: v for m, v in metricas(fk, Pk[k]).items() if m in ("R2_log", "rho", "erro_mediano", "MAPE")}})
    MD.append(pd.DataFrame(linhas).round(3).to_markdown(index=False))
    MD.append("\nAtenção: tirar os piores sempre melhora qualquer modelo (inclusive o da viabilidade). O que importa é se o modelo GANHA da viabilidade depois da limpeza e quanto o erro TÍPICO cai.\n")
    # --- Cook + Huber
    y = np.log(fa); Xc = np.c_[np.ones(len(y)), X]; beta = np.linalg.lstsq(Xc, y, rcond=None)[0]; res = y - Xc @ beta
    H = Xc @ np.linalg.inv(Xc.T @ Xc) @ Xc.T; h = np.diag(H); s2 = (res ** 2).sum() / (len(y) - Xc.shape[1])
    cook = res ** 2 / (Xc.shape[1] * s2) * h / (1 - h) ** 2
    infl = A.pid[cook > 4 / len(y)].tolist()
    MD.append(f"**Distância de Cook (MF):** {len(infl)} unidades influentes (> 4/N): {', '.join(infl)}.")
    ph = {"MF Huber (robusta)": np.exp(loo(X, np.log(fa), lambda: HuberRegressor(max_iter=2000))), "MA Huber (robusta) -> faturamento": m2 * np.exp(loo(X, np.log(al / m2), lambda: HuberRegressor(max_iter=2000))) * tk}
    MD.append(pd.DataFrame([{"modelo": k, **metricas(fa, v)} for k, v in ph.items()]).round(3).to_markdown(index=False))
    # jackknife do R2 LOO de MF
    jk = []
    for i in range(len(A)):
        idx = np.delete(todos, i); p = np.exp(loo(X[idx], np.log(fa[idx])))
        jk.append(metricas(fa[idx], p)["R2_log"])
    jk = np.array(jk)
    MD.append(f"\n**Jackknife (MF):** R² fora da amostra tirando uma unidade por vez varia de {jk.min():+.3f} a {jk.max():+.3f} (mediana {np.median(jk):+.3f}); a unidade cuja saída mais muda o R² é {A.pid[int(np.argmax(np.abs(jk - np.median(jk))))]}.")
    E.drop(columns=["abs_MF", "abs_MA"]).to_csv(OUT / "erros_por_unidade.csv", sep=";", encoding="utf-8-sig", index=False)
    # grafico
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 3, figsize=(18, 6))
    for ax, k in zip(axs, ("MF faturamento", "MA alunos/m2 -> faturamento", "V viabilidade -> faturamento")):
        p = P[k]; ax.scatter(p / 1e3, fa / 1e3, s=22)
        lim = [0, max(fa.max(), p.max()) / 1e3 * 1.05]; ax.plot(lim, lim, "k--", lw=1)
        ax.fill_between(lim, [l * 0.75 for l in lim], [l * 1.25 for l in lim], color="gray", alpha=0.12, label="±25%")
        for j in np.argsort(-np.abs(p / fa - 1))[:6]:
            ax.annotate(A.pid[j], (p[j] / 1e3, fa[j] / 1e3), fontsize=7)
        mm = metricas(fa, p); ax.set_title(f"{k}\nR² log {mm['R2_log']:+.2f} | rho {mm['rho']:+.2f} | erro mediano {mm['erro_mediano']:.0%}", fontsize=9)
        ax.set_xlabel("previsto (R$ mil)"); ax.set_ylabel("real, Financeiro ago/26 (R$ mil)"); ax.legend(fontsize=7)
    fig.tight_layout(); fig.savefig(OUT / "diagnostico_modelos.png", dpi=120)
    (OUT / "diagnostico_modelos.md").write_text("\n".join(MD), encoding="utf-8"); print("\n".join(MD))


if __name__ == "__main__":
    main()
