# -*- coding: utf-8 -*-
"""Teste pedido por Felipe (2026-09-29): 'suprimir um pouco as unidades excepcionais' no AJUSTE do modelo.
Regressao robusta (Huber) no lugar de MQO: unidades muito fora da curva pesam menos no treino, sem ser excluidas.
Avaliada nas mesmas 18 unidades de teste do UNI-02 (segunda olhada no teste; declarado como sensibilidade)."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import HuberRegressor

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
s_ = importlib.util.spec_from_file_location("ex", UNI / "uni01" / "01_exploracao.py"); ex = importlib.util.module_from_spec(s_); s_.loader.exec_module(ex)
BASE = ["l_m2", "l_renda", "l_pop"]
f, d = ex.carregar(); A = ex.atributos(d)
Y25, Y26 = ex.desfechos(f, "2025-01", "2025-12"), ex.desfechos(f, "2026-01", "2026-08")
est = pd.read_csv(UNI / "coleta_metragem" / "metragem_estimada.csv", sep=";", encoding="utf-8-sig", index_col=0).metragem_estimada_m2.dropna()
of = d.tam_metragem_m2.dropna(); m2 = np.log(pd.concat([of, est[~est.index.isin(of.index)]]))
tr = A.join(Y25, how="inner").dropna(subset=["l_fat"] + BASE)
te = A.drop(columns=["l_m2"]).join(m2.rename("l_m2")).join(Y26, how="inner"); te = te[~te.index.isin(tr.index)].dropna(subset=["l_fat"] + BASE + ["frac_indep"])
amb = tr.index.intersection(Y26.index); cal = float(np.median(Y26.loc[amb, "l_fat"] - Y25.loc[amb, "l_fat"]))
Xtr, ytr, Xte, yte = tr[BASE].to_numpy(float), tr.l_fat.to_numpy(float), te[BASE].to_numpy(float), te.l_fat.to_numpy(float)
mu, sd = Xtr.mean(0), Xtr.std(0)
out = {}
for nome, mdl in (("MQO (M0 atual)", None), ("Huber eps=1,35 (padrão)", 1.35), ("Huber eps=1,1 (mais robusto)", 1.1)):
    if mdl is None:
        X1 = np.column_stack([np.ones(len(Xtr)), Xtr]); b = np.linalg.lstsq(X1, ytr, rcond=None)[0]
        p = np.column_stack([np.ones(len(Xte)), Xte]) @ b + cal; w = None
    else:
        h = HuberRegressor(epsilon=mdl, alpha=0.0, max_iter=1000).fit((Xtr - mu) / sd, ytr)
        p = h.predict((Xte - mu) / sd) + cal
        w = pd.Series(~h.outliers_, index=tr.index)
    err = np.exp(yte - p) - 1
    out[nome] = p
    print(f"{nome:30s} erro típico {np.median(np.abs(err)):.0%} | viés {np.median(err):+.0%} | Spearman {stats.spearmanr(p, yte)[0]:+.2f}"
          + (f" | unidades com peso reduzido no treino: {int((~w).sum())} ({', '.join(d.nome.reindex(w.index[~w]).tolist())})" if w is not None else ""))
dif = np.exp(out["Huber eps=1,35 (padrão)"] - out["MQO (M0 atual)"]) - 1
print(f"Mudança da previsão (Huber padrão × MQO) nas 18 de teste: mediana {np.median(dif):+.1%}, de {dif.min():+.1%} a {dif.max():+.1%}")
