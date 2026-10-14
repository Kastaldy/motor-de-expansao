# -*- coding: utf-8 -*-
"""Comparacao fora da amostra (LOO), nas MESMAS unidades:
  V   = metodo atual da viabilidade: alunos = m2 x mediana de alunos/m2 dos comparaveis (janela +/-20% de m2,
        alarga para 50% se < 3; funcao real do repo `faixa_alunos_por_densidade`); faturamento = alunos x receita
        por aluno mediana dos outros.
  RF  = regressao log(faturamento) ~ log m2 + log renda 10 min + log pop 10 min (a do 17).
  RA  = regressao log(alunos/m2) ~ log m2 + log renda + log pop  -> alunos = m2 x previsto; faturamento = alunos x
        receita por aluno mediana.
  RA+ = RA + concorrencia per capita (10 min).
Metrica: erro percentual absoluto mediano e medio (MAPE), com IC95 bootstrap da diferenca contra V.
Bases: Ultra (N=54; alunos = ativos agosto/26 Growth; faturamento Financeiro agosto/26, Guaruja corrigido) e,
so' para alunos, Ultra + Engenharia do Corpo (N=89, comparaveis da mesma rede).
"""
import importlib.util
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import wkb
from sklearn.linear_model import LinearRegression

warnings.filterwarnings("ignore")
ISO = Path(r"C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\9259d0a1-7dda-49bd-a390-c88f3d4ac1a6\scratchpad\iso")
sys.path.insert(0, r"C:\dev\motor-de-expansao\src")
from motor_expansao.dimensionamento.viabilidade_ponto import faixa_alunos_por_densidade  # noqa: E402
spec = importlib.util.spec_from_file_location("v2", ISO / "14_aproveitamento_v2.py"); v2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(v2)
spec = importlib.util.spec_from_file_location("r17", ISO / "17_regressao.py"); r17 = importlib.util.module_from_spec(spec); spec.loader.exec_module(r17)
OUT = ISO / "regressao"; RNG = np.random.default_rng(42); MD = []


def loo_reg(X, y):
    p = np.zeros(len(y))
    for i in range(len(y)):
        m = np.ones(len(y), bool); m[i] = False
        p[i] = LinearRegression().fit(X[m], y[m]).predict(X[i:i + 1])[0]
    return p


def loo_viab(d, alunos, grupo=None):
    p = np.zeros(len(d))
    for i in range(len(d)):
        m = np.ones(len(d), bool); m[i] = False
        if grupo is not None:
            m &= (d[grupo].to_numpy() == d[grupo].iloc[i])
        base = pd.DataFrame({"metragem": d.metragem[m], "alunos_por_m2": alunos[m] / d.metragem[m].to_numpy()})
        p[i] = faixa_alunos_por_densidade(float(d.metragem.iloc[i]), base)["faixa_alunos_p50"]
    return p


def erros(real, prev):
    e = np.abs(prev / real - 1)
    return e


def tabela(real, previsoes, titulo):
    MD.append(f"\n**{titulo}** (N = {len(real)})\n")
    base = erros(real, previsoes["V (viabilidade atual)"])
    linhas = []
    for nome, p in previsoes.items():
        e = erros(real, p)
        ds = []
        for _ in range(2000):
            i = RNG.integers(0, len(e), len(e)); ds.append(np.median(e[i]) - np.median(base[i]))
        linhas.append({"metodo": nome, "erro_mediano": np.median(e), "MAPE": e.mean(), "erro_p75": np.percentile(e, 75),
                       "dif_erro_mediano_vs_V": np.median(e) - np.median(base), "IC95": f"[{np.percentile(ds,2.5):+.3f}; {np.percentile(ds,97.5):+.3f}]"})
    MD.append(pd.DataFrame(linhas).round(3).to_markdown(index=False))


def main():
    ac, tree = v2.oferta()
    fech = pd.read_parquet(v2.SC / "fech_mensal_financeiro.parquet")
    fin = fech[fech.origem_faturamento.eq("financeiro") & fech.mes_completo & fech.operacao_mes_cheio]
    fat = fin[fin.competencia == "2026-08"].set_index("unidade_id")["faturamento"].copy(); fat.loc["guaruja-sp"] = 217525.74
    ativos_ago = fech[fech.competencia == "2026-08"].set_index("unidade_id")["ativos"]
    at12 = fech[fech.competencia.between("2025-09", "2026-08")].groupby("unidade_id")["ativos"].median()
    bu = pd.read_parquet(ISO / "testes_v2" / "base_ultra.parquet").rename(columns={"unidade_id": "pid"})
    bu["rede"] = "ultra"; bu["fat"] = bu.pid.map(fat); bu["alunos"] = bu.pid.map(ativos_ago); bu["ativos_ref"] = bu.pid.map(at12)
    ultra_ref = bu.dropna(subset=["lat"])[["pid", "lat", "lng", "ativos_ref"]]
    iso = pd.concat([pd.read_parquet(f, columns=["ponto_id", "tipo", "modo", "limite_s", "poligono_wkb"], filters=[("tipo", "==", "ultra")]) for f in sorted((ISO / "isocronas_v2").glob("metro_*.parquet"))])
    polys = {c: dict(zip(s.ponto_id, gpd.GeoSeries([wkb.loads(b) for b in s.poligono_wkb], crs=4326).to_crs(5880).values)) for c, (m, l) in v2.CEN.items() for s in [iso[(iso.modo == m) & (iso.limite_s == l) & iso.poligono_wkb.notna()]]}
    A = bu[bu.metragem.notna() & bu.fat.notna() & bu.alunos.notna() & ~bu.confianca.eq("baixa") & bu["pop__carro_10"].notna()].reset_index(drop=True)
    A = v2.crescimento(v2.componentes(A, polys, ac, tree, ultra_ref, auto_m=2.0))
    X = r17.features(A)
    m2 = A.metragem.to_numpy(float); alunos = A.alunos.to_numpy(float); fatr = A.fat.to_numpy(float)
    ticket_loo = np.array([np.median(np.delete(fatr / alunos, i)) for i in range(len(A))])
    XA = X[["log_metragem", "log_renda", "log_pop"]].to_numpy(float)
    XB = X[["log_metragem", "log_renda", "log_pop", "concorrencia"]].to_numpy(float)
    V_al = loo_viab(A, alunos)
    RA_al = m2 * np.exp(loo_reg(XA, np.log(alunos / m2)))
    RAp_al = m2 * np.exp(loo_reg(XB, np.log(alunos / m2)))
    RF_fat = np.exp(loo_reg(XA, np.log(fatr)))
    MD.append("# Viabilidade atual (alunos/m² por comparáveis) x regressão — fora da amostra (LOO)\n")
    tabela(alunos, {"V (viabilidade atual)": V_al, "RA (alunos/m² ~ m², renda, pop)": RA_al, "RA+ (+ concorrência)": RAp_al}, "Ultra — ALUNOS (ativos agosto/26)")
    tabela(fatr, {"V (viabilidade atual)": V_al * ticket_loo, "RA x receita/aluno": RA_al * ticket_loo, "RA+ x receita/aluno": RAp_al * ticket_loo, "RF (faturamento ~ m², renda, pop)": RF_fat},
           "Ultra — FATURAMENTO (Financeiro agosto/26)")
    # coeficientes do RA (alunos/m2)
    lr = LinearRegression().fit(XA, np.log(alunos / m2))
    MD.append(f"\nRA ajustado em todas: log(alunos/m²) = {lr.intercept_:+.2f} {lr.coef_[0]:+.2f}·log m² {lr.coef_[1]:+.2f}·log renda {lr.coef_[2]:+.2f}·log pop")
    # Ultra + EdC, alunos
    p = pd.read_parquet(ISO / "multirede" / "perfil.parquet").rename(columns={"ponto_id": "pid", "marca": "rede"})
    B = p[p.rede.isin(["ultra", "engenharia_do_corpo"]) & p.metragem.notna() & (p.alunos_reais > 0) & p["pop__carro_10"].notna()].reset_index(drop=True)
    mp = {c: {} for c in v2.CEN}
    for f in sorted((ISO / "multirede" / "atributos").glob("poligonos_metro_*.parquet")):
        s = pd.read_parquet(f)
        for c, (modo, lim) in v2.CEN.items():
            ss = s[(s.modo == modo) & (s.limite_s == lim) & s.poligono_wkb.notna()]
            mp[c].update(dict(zip(ss.ponto_id, gpd.GeoSeries([wkb.loads(b) for b in ss.poligono_wkb], crs=4326).to_crs(5880).values)))
    B = v2.crescimento(v2.componentes(B, mp, ac, tree, ultra_ref, auto_m=75.0))
    XBf = r17.features(B); ok = XBf[["log_metragem", "log_renda", "log_pop", "concorrencia"]].notna().all(axis=1).to_numpy()
    B = B[ok].reset_index(drop=True); XBf = XBf[ok].reset_index(drop=True)
    al = B.alunos_reais.to_numpy(float); mm = B.metragem.to_numpy(float)
    dum = (B.rede == "ultra").astype(float).to_numpy()[:, None]
    X1 = np.c_[dum, XBf[["log_metragem", "log_renda", "log_pop"]].to_numpy(float)]
    X2 = np.c_[dum, XBf[["log_metragem", "log_renda", "log_pop", "concorrencia"]].to_numpy(float)]
    tabela(al, {"V (viabilidade atual)": loo_viab(B, al, grupo="rede"), "RA (alunos/m² ~ rede, m², renda, pop)": mm * np.exp(loo_reg(X1, np.log(al / mm))),
                "RA+ (+ concorrência)": mm * np.exp(loo_reg(X2, np.log(al / mm)))}, "Ultra + Engenharia do Corpo — ALUNOS (comparáveis da mesma rede)")
    (OUT / "comparacao_viabilidade.md").write_text("\n".join(MD), encoding="utf-8"); print("\n".join(MD))


if __name__ == "__main__":
    main()
