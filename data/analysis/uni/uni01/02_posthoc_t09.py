# -*- coding: utf-8 -*-
"""POS-HOC (fora do protocolo congelado): influencia no T09 — tamanho x concorrencia de estrutura menor.

O T09 passou como candidata com p = 0,067 e uma unidade com alavancagem 0,54. Aqui: quem e' essa unidade, o efeito
sem ela, e o efeito tirando uma unidade por vez (faixa). Nao muda a classificacao do protocolo; so' informa o
pre-registro do UNI-02.
"""
import importlib.util
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
s = importlib.util.spec_from_file_location("ex", AQUI / "01_exploracao.py"); ex = importlib.util.module_from_spec(s); s.loader.exec_module(ex)

f, d = ex.carregar()
A = ex.atributos(d)
Yp = ex.desfechos(f, ex.INI, ex.FIM)
T = next(t for t in ex.TESTES if t["id"] == "T09")
D, ctrl, esc = ex.montar(T, Yp, A)
X1 = ex.matriz(D, ctrl, True, False)
b, e, h, _ = ex.ols(D[T["y"]].to_numpy(float), X1)
i = int(np.argmax(h))
u = D.index[i]
print(f"N={len(D)} beta={b[-1] * esc:+.3f} | maior alavancagem: {u} h={h[i]:.2f} m2={np.exp(D.l_m2.iloc[i]):.0f} "
      f"frac_indep={D.frac_indep.iloc[i]:.2f} (mediana {D.frac_indep.median():.2f})")
betas = {}
for j, uj in enumerate(D.index):
    T2 = dict(T)
    r = ex.ajustar(T2, Yp.drop(uj), A)
    betas[uj] = (r["beta"], r["ic_lo"], r["ic_hi"])
bu = betas[u]
print(f"sem {u}: beta={bu[0]:+.3f} IC90 [{bu[1]:+.3f}, {bu[2]:+.3f}]")
v = np.array([x[0] for x in betas.values()]); lo = np.array([x[1] for x in betas.values()])
print(f"tirando 1 unidade por vez: beta min {v.min():+.3f} max {v.max():+.3f}; IC exclui zero em {(lo > 0).sum()} de {len(v)}")
top = sorted(betas.items(), key=lambda kv: kv[1][0])[:3]
print("retiradas que mais reduzem o efeito:", [(k, round(x[0], 3), round(x[1], 3)) for k, x in top])
