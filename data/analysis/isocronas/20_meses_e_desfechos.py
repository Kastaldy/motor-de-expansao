# -*- coding: utf-8 -*-
"""(a) Modelo de faturamento em cada mes do Financeiro (set/25 a ago/26) e na mediana de 12 meses, mesma
especificacao (log m2, log renda 10 min, log pop 10 min), LOO; comparado com a viabilidade atual no mesmo mes.
(b) Validacao temporal: ajusta com a mediana de set/25-fev/26 e testa em mar-ago/26 (mesmas unidades, periodo novo).
(c) Outros desfechos com as mesmas variaveis: alunos, alunos/m2, receita por aluno, % agregador, churn, NPS (12 m).
"""
import importlib.util
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LinearRegression

warnings.filterwarnings("ignore")
ISO = Path(r"C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\9259d0a1-7dda-49bd-a390-c88f3d4ac1a6\scratchpad\iso")
SC = ISO.parent
sys.path.insert(0, r"C:\dev\motor-de-expansao\src")
from motor_expansao.dimensionamento.viabilidade_ponto import faixa_alunos_por_densidade  # noqa: E402
def mod(n, f):
    s = importlib.util.spec_from_file_location(n, ISO / f); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
r17 = mod("r17", "17_regressao.py")
VARS = ["log_metragem", "log_renda", "log_pop"]
MD = []


def loo(X, y):
    p = np.zeros(len(y))
    for i in range(len(y)):
        m = np.ones(len(y), bool); m[i] = False
        p[i] = LinearRegression().fit(X[m], y[m]).predict(X[i:i + 1])[0]
    return p


def r2(y, p):
    return 1 - ((y - p) ** 2).sum() / ((y - y.mean()) ** 2).sum()


def main():
    base = pd.read_parquet(ISO / "aproveitamento_v3").pipe(lambda _: None) if False else None
    bu = pd.read_parquet(ISO / "testes_v2" / "base_ultra.parquet")
    A = bu[bu.metragem.notna() & ~bu.confianca.eq("baixa") & bu["pop__carro_10"].notna()].reset_index(drop=True)
    X = r17.features(A.assign(**{f"cap_real__carro_10": 0, "cap_rede__carro_10": 0, "n_cadeia_proxy__carro_10": 0, "n_indep__carro_10": 0,
                               "ultra_outras__carro_10": 0, "dim_media": 0, "cres_hex_taxa": 0}))[VARS].to_numpy(float)
    m2 = A.metragem.to_numpy(float)
    fech = pd.read_parquet(SC / "fech_mensal_financeiro.parquet")
    fin = fech[fech.mes_completo & fech.operacao_mes_cheio].copy()
    fin.loc[(fin.unidade_id == "guaruja-sp") & (fin.competencia == "2026-08"), "faturamento"] = 217525.74
    fin = fin[fin.origem_faturamento.eq("financeiro")]
    piv = fin.pivot_table(index="unidade_id", columns="competencia", values="faturamento", aggfunc="first")
    ativ = fech.pivot_table(index="unidade_id", columns="competencia", values="ativos", aggfunc="first")
    MD.append(f"# Modelo de faturamento em vários meses e outros desfechos (Ultra, N até {len(A)})\n")
    MD.append("## (a) Mês a mês e mediana de 12 meses — faturamento do Financeiro\n")
    linhas = []
    meses = [c for c in piv.columns if "2025-09" <= c <= "2026-08"]
    for mes in meses + ["mediana 12 m"]:
        if mes == "mediana 12 m":
            y_ = A.unidade_id.map(piv[meses].median(axis=1)); al_ = A.unidade_id.map(ativ[meses].median(axis=1))
        else:
            y_ = A.unidade_id.map(piv[mes]); al_ = A.unidade_id.map(ativ[mes])
        ok = (y_.notna() & al_.notna() & (y_ > 0)).to_numpy()
        y = np.log(y_[ok].to_numpy(float)); al = al_[ok].to_numpy(float); fa = np.exp(y)
        p = loo(X[ok], y)
        tk = np.array([np.median(np.delete(fa / al, i)) for i in range(ok.sum())]); v = np.zeros(ok.sum()); mm = m2[ok]
        for i in range(ok.sum()):
            k = np.ones(ok.sum(), bool); k[i] = False
            v[i] = faixa_alunos_por_densidade(float(mm[i]), pd.DataFrame({"metragem": mm[k], "alunos_por_m2": al[k] / mm[k]}))["faixa_alunos_p50"] * tk[i]
        linhas.append({"mes": mes, "n": int(ok.sum()), "R2_modelo": r2(y, p), "rho_modelo": spearmanr(y, p)[0], "erro_mediano_modelo": np.median(np.abs(np.exp(p) / fa - 1)),
                       "R2_viabilidade": r2(y, np.log(v)), "rho_viabilidade": spearmanr(y, v)[0], "erro_mediano_viabilidade": np.median(np.abs(v / fa - 1))})
    t = pd.DataFrame(linhas); MD.append(t.round(3).to_markdown(index=False))
    MD.append(f"\nMês a mês (12 meses): R² do modelo entre {t.R2_modelo[:-1].min():+.2f} e {t.R2_modelo[:-1].max():+.2f}; viabilidade entre {t.R2_viabilidade[:-1].min():+.2f} e {t.R2_viabilidade[:-1].max():+.2f}.")
    # (b) validacao temporal
    ini = [c for c in meses if c <= "2026-02"]; fim = [c for c in meses if c >= "2026-03"]
    y1 = A.unidade_id.map(piv[ini].median(axis=1)); y2 = A.unidade_id.map(piv[fim].median(axis=1))
    ok = (y1.notna() & y2.notna()).to_numpy()
    lr = LinearRegression().fit(X[ok], np.log(y1[ok].to_numpy(float))); p2 = lr.predict(X[ok]); yy = np.log(y2[ok].to_numpy(float))
    ing = r2(yy, p2 - p2.mean() + yy.mean())
    MD.append(f"\n## (b) Validação temporal\n\nAjustado com a mediana de set/25–fev/26 e aplicado à mediana de mar–ago/26 (N = {ok.sum()}): R² {r2(yy, p2):+.3f} (com nível recentrado {ing:+.3f}), rho {spearmanr(yy, p2)[0]:+.2f}, erro mediano {np.median(np.abs(np.exp(p2)/np.exp(yy)-1)):.0%}.")
    MD.append(f"Persistência pura (usar o próprio faturamento do 1º semestre para prever o 2º): rho {spearmanr(y1[ok], y2[ok])[0]:+.2f} — é o teto do que qualquer modelo sem histórico pode sonhar.")
    # (c) outros desfechos
    MD.append("\n## (c) Mesmas variáveis prevendo outros resultados (mediana 12 m, LOO)\n")
    outs = {"faturamento": A.unidade_id.map(piv[meses].median(axis=1)), "alunos (ativos)": A["ativos_med_12m"], "alunos/m²": A["ativos_med_12m"] / A.metragem,
            "receita por aluno": A.unidade_id.map(piv[meses].median(axis=1)) / A["ativos_med_12m"], "% agregador": 100 * A["agreg_med_12m"] / (A["pag_med_12m"] + A["agreg_med_12m"]),
            "churn %": A["churn_med_12m"], "NPS": A["nps_med_12m"], "visitas/mês": A["visitas_med_12m"], "conversão %": A["conv_med_12m"]}
    linhas = []
    rng = np.random.default_rng(42)
    for nome, s in outs.items():
        ok = (s.notna() & np.isfinite(s) & (s > 0)).to_numpy() if nome not in ("NPS",) else s.notna().to_numpy()
        y = s[ok].to_numpy(float); ylog = np.log(y) if nome not in ("NPS", "churn %", "% agregador", "conversão %") else y
        p = loo(X[ok], ylog); c = LinearRegression().fit(X[ok], ylog)
        bs = [r2(ylog[i], p[i]) for i in (rng.integers(0, ok.sum(), ok.sum()) for _ in range(1000))]
        linhas.append({"desfecho": nome, "n": int(ok.sum()), "R2_fora_amostra": r2(ylog, p), "IC95": f"[{np.percentile(bs,2.5):+.2f}; {np.percentile(bs,97.5):+.2f}]", "rho": spearmanr(ylog, p)[0],
                       "coef_m2": c.coef_[0], "coef_renda": c.coef_[1], "coef_pop": c.coef_[2]})
    MD.append(pd.DataFrame(linhas).round(3).to_markdown(index=False))
    MD.append("\n(desfechos com escala proporcional em log; churn, % agregador, conversão e NPS em nível)")
    out = ISO / "regressao" / "meses_e_desfechos.md"; out.write_text("\n".join(MD), encoding="utf-8"); print("\n".join(MD))


if __name__ == "__main__":
    main()
