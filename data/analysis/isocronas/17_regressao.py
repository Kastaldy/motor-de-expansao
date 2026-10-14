# -*- coding: utf-8 -*-
"""Regressao transparente com validacao fora da amostra (variaveis fixadas antes de rodar).

R1 (principal): log(alunos) ~ rede + log metragem + log renda 10 min + log pop 10 min + concorrencia 10 min
     + metragem x concorrencia + canibalizacao + crescimento municipal + crescimento do hexagono.  Ultra + EdC.
R2: log(faturamento Financeiro ago/26) ~ mesmas variaveis (sem dummy de rede). So' Ultra.
Concorrencia = log(1 + alunos dos concorrentes na isocrona de carro 10 min por mil habitantes), com alunos reais
quando existem e proxy de 1.800 (cadeia) / 400 (independente). Canibalizacao = log(1 + ativos de outras Ultras).
Validacao: leave-one-out e GroupKFold por UF; OLS e ridge; R2 fora da amostra com IC bootstrap; modelos aninhados
para ver o ganho de cada bloco. Pesos: coeficientes padronizados do OLS com IC95 por bootstrap (2.000).
"""
import importlib.util
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from shapely import wkb
from sklearn.linear_model import LinearRegression, RidgeCV
from sklearn.model_selection import GroupKFold, LeaveOneOut
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")
ISO = Path(r"C:\Users\Felipe\AppData\Local\Temp\claude\C--dev-motor-de-expansao\9259d0a1-7dda-49bd-a390-c88f3d4ac1a6\scratchpad\iso")
spec = importlib.util.spec_from_file_location("v2", ISO / "14_aproveitamento_v2.py"); v2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(v2)
OUT = ISO / "regressao"; OUT.mkdir(exist_ok=True)
RNG = np.random.default_rng(42)
MD = []


def features(d):
    c = "carro_10"
    conc_alunos = d[f"cap_real__{c}"] + d[f"cap_rede__{c}"] + d[f"n_cadeia_proxy__{c}"] * 1800 + d[f"n_indep__{c}"] * 400
    X = pd.DataFrame({
        "log_metragem": np.log(d["metragem"]),
        "log_renda": np.log(d[f"renda_pc__{c}"].clip(lower=300)),
        "log_pop": np.log1p(d[f"pop__{c}"]),
        "concorrencia": np.log1p(1000 * conc_alunos / d[f"pop__{c}"].clip(lower=1)),
        "canibalizacao": np.log1p(d[f"ultra_outras__{c}"].fillna(0)),
        "cresc_municipal": d["dim_media"],
        "cresc_hex": d["cres_hex_taxa"],
    }, index=d.index)
    X["metragem_x_concorrencia"] = (X.log_metragem - X.log_metragem.mean()) * (X.concorrencia - X.concorrencia.mean())
    return X


BLOCOS = {
    "B0 só rede/intercepto": [],
    "B1 + metragem": ["log_metragem"],
    "B2 + renda": ["log_metragem", "log_renda"],
    "B3 + população": ["log_metragem", "log_renda", "log_pop"],
    "B4 + concorrência": ["log_metragem", "log_renda", "log_pop", "concorrencia"],
    "B5 + metragem x concorrência": ["log_metragem", "log_renda", "log_pop", "concorrencia", "metragem_x_concorrencia"],
    "B6 + canibalização": ["log_metragem", "log_renda", "log_pop", "concorrencia", "metragem_x_concorrencia", "canibalizacao"],
    "B7 completo (+ crescimento)": ["log_metragem", "log_renda", "log_pop", "concorrencia", "metragem_x_concorrencia", "canibalizacao", "cresc_municipal", "cresc_hex"],
}


def oof(X, y, grupos, modelo):
    pred = np.zeros(len(y))
    split = LeaveOneOut().split(X) if grupos is None else GroupKFold(n_splits=min(8, len(np.unique(grupos)))).split(X, y, grupos)
    for tr, te in split:
        if X.shape[1] == 0:
            pred[te] = y[tr].mean(); continue
        m = make_pipeline(StandardScaler(), LinearRegression() if modelo == "ols" else RidgeCV(alphas=np.logspace(-2, 3, 30)))
        m.fit(X[tr], y[tr]); pred[te] = m.predict(X[te])
    return pred


def r2(y, p, i=None):
    if i is not None:
        y, p = y[i], p[i]
    return 1 - ((y - p) ** 2).sum() / ((y - y.mean()) ** 2).sum()


def analisar(d, y, nome, dummies):
    X0 = features(d)
    n_imp = {c: int(X0[c].isna().sum()) for c in ("cresc_municipal", "cresc_hex")}
    for c in ("cresc_municipal", "cresc_hex"):
        X0[c] = X0[c].fillna(X0[c].median())  # crescimento ausente -> mediana (declarado)
    ok = X0.notna().all(axis=1) & np.isfinite(y)
    d, X0, y = d[ok].reset_index(drop=True), X0[ok].reset_index(drop=True), y[ok.to_numpy()]
    D = pd.get_dummies(d["rede"], drop_first=True).astype(float) if dummies else pd.DataFrame(index=d.index)
    g = d["uf"].to_numpy()
    MD.append(f"\n## {nome} (N = {len(y)}{', ' + str(d.rede.value_counts().to_dict()) if dummies else ''})\n")
    linhas, preds = [], {}
    for bn, cols in BLOCOS.items():
        X = pd.concat([D, X0[cols]], axis=1).to_numpy(float)
        p_loo_ols = oof(X, y, None, "ols"); p_loo_r = oof(X, y, None, "ridge"); p_uf = oof(X, y, g, "ridge")
        preds[bn] = p_loo_r
        linhas.append({"modelo": bn, "R2_LOO_ols": r2(y, p_loo_ols), "R2_LOO_ridge": r2(y, p_loo_r), "R2_UF_ridge": r2(y, p_uf)})
    t = pd.DataFrame(linhas)
    base = preds["B0 só rede/intercepto"]
    ic = []
    for bn in BLOCOS:
        bs = [r2(y, preds[bn], i) for i in (RNG.integers(0, len(y), len(y)) for _ in range(2000))]
        ic.append(f"[{np.percentile(bs,2.5):+.2f}; {np.percentile(bs,97.5):+.2f}]")
    t["IC95_R2_LOO_ridge"] = ic
    MD.append(t.round(3).to_markdown(index=False))
    # ganho de cada bloco (LOO ridge, pareado)
    MD.append("\nGanho de cada passo (R² LOO ridge, bootstrap pareado):\n")
    nomes = list(BLOCOS)
    for a, b in zip(nomes[:-1], nomes[1:]):
        ds = []
        for _ in range(2000):
            i = RNG.integers(0, len(y), len(y)); ds.append(r2(y, preds[b], i) - r2(y, preds[a], i))
        MD.append(f"- {b.split(' ',1)[1]}: {r2(y,preds[b])-r2(y,preds[a]):+.3f} IC95 [{np.percentile(ds,2.5):+.3f}; {np.percentile(ds,97.5):+.3f}]")
    # pesos: OLS completo padronizado, IC bootstrap
    cols = BLOCOS["B7 completo (+ crescimento)"]
    Xs = pd.concat([D, X0[cols]], axis=1)
    mu, sd = Xs.mean(), Xs.std().replace(0, 1)
    Z = ((Xs - mu) / sd).to_numpy(float)
    ysd = y.std()
    coef = LinearRegression().fit(Z, y).coef_ / ysd
    bs = []
    for _ in range(2000):
        i = RNG.integers(0, len(y), len(y)); bs.append(LinearRegression().fit(Z[i], y[i]).coef_ / ysd)
    bs = np.array(bs)
    pesos = pd.DataFrame({"variavel": Xs.columns, "peso_padronizado": coef, "IC95_baixo": np.percentile(bs, 2.5, axis=0), "IC95_alto": np.percentile(bs, 97.5, axis=0)})
    pesos["exclui_zero"] = (pesos.IC95_baixo > 0) | (pesos.IC95_alto < 0)
    raw = LinearRegression().fit(Xs.to_numpy(float), y)
    pesos["coef_bruto"] = raw.coef_
    MD.append("\nPesos (OLS completo; peso padronizado = efeito de +1 desvio-padrão da variável, em desvios-padrão do desfecho; coef_bruto em log):\n")
    MD.append(pesos.sort_values("peso_padronizado", key=abs, ascending=False).round(3).to_markdown(index=False))
    pd.DataFrame({"pid": d.pid, "rede": d.rede, "real_log": y, "previsto_loo_completo": preds["B7 completo (+ crescimento)"], "previsto_loo_B2": preds["B2 + renda"]}).to_csv(OUT / f"previsoes_{nome.split()[0]}.csv", sep=";", encoding="utf-8-sig", index=False)
    return t, pesos


def main():
    ac, tree = v2.oferta()
    # Ultra: ativos 12 m (para canibalizacao) e faturamento Financeiro
    fech = pd.read_parquet(v2.SC / "fech_mensal_financeiro.parquet")
    fin = fech[fech.origem_faturamento.eq("financeiro") & fech.mes_completo & fech.operacao_mes_cheio]
    fat = fin[fin.competencia == "2026-08"].set_index("unidade_id")["faturamento"].copy(); fat.loc["guaruja-sp"] = 217525.74
    at12 = fech[fech.competencia.between("2025-09", "2026-08")].groupby("unidade_id")["ativos"].median()
    bu = pd.read_parquet(ISO / "testes_v2" / "base_ultra.parquet").rename(columns={"unidade_id": "pid"})
    bu["rede"] = "ultra"; bu["fat"] = bu.pid.map(fat); bu["ativos_ref"] = bu.pid.map(at12)
    ultra_ref = bu.dropna(subset=["lat"])[["pid", "lat", "lng", "ativos_ref"]]
    # R1: Ultra + EdC (poligonos da base multirede)
    p = pd.read_parquet(ISO / "multirede" / "perfil.parquet").rename(columns={"ponto_id": "pid", "marca": "rede"})
    B = p[p.rede.isin(["ultra", "engenharia_do_corpo"]) & p.metragem.notna() & (p.alunos_reais > 0) & p["pop__carro_10"].notna()].reset_index(drop=True)
    mp = {c: {} for c in v2.CEN}
    for f in sorted((ISO / "multirede" / "atributos").glob("poligonos_metro_*.parquet")):
        s = pd.read_parquet(f)
        for c, (modo, lim) in v2.CEN.items():
            ss = s[(s.modo == modo) & (s.limite_s == lim) & s.poligono_wkb.notna()]
            mp[c].update(dict(zip(ss.ponto_id, gpd.GeoSeries([wkb.loads(b) for b in ss.poligono_wkb], crs=4326).to_crs(5880).values)))
    B = v2.crescimento(v2.componentes(B, mp, ac, tree, ultra_ref, auto_m=75.0))
    MD.append("# Regressão com validação fora da amostra\n\nVariáveis fixadas antes de rodar (docstring de `17_regressao.py`). Área de referência: isócrona de carro de 10 min. Desfechos em log.")
    analisar(B, np.log(B.alunos_reais.to_numpy(float)), "R1 alunos Ultra + Engenharia do Corpo", True)
    # R2: Ultra faturamento
    polys = {}
    iso = pd.concat([pd.read_parquet(f, columns=["ponto_id", "tipo", "modo", "limite_s", "poligono_wkb"], filters=[("tipo", "==", "ultra")]) for f in sorted((ISO / "isocronas_v2").glob("metro_*.parquet"))])
    for c, (modo, lim) in v2.CEN.items():
        s = iso[(iso.modo == modo) & (iso.limite_s == lim) & iso.poligono_wkb.notna()]
        polys[c] = dict(zip(s.ponto_id, gpd.GeoSeries([wkb.loads(b) for b in s.poligono_wkb], crs=4326).to_crs(5880).values))
    A = bu[bu.metragem.notna() & bu.fat.notna() & ~bu.confianca.eq("baixa") & bu["pop__carro_10"].notna()].reset_index(drop=True)
    A = v2.crescimento(v2.componentes(A, polys, ac, tree, ultra_ref, auto_m=2.0))
    analisar(A, np.log(A.fat.to_numpy(float)), "R2 faturamento Ultra (Financeiro ago/26)", False)
    (OUT / "resultados.md").write_text("\n".join(MD), encoding="utf-8")
    print("\n".join(MD))


if __name__ == "__main__":
    main()
