# -*- coding: utf-8 -*-
"""POS-HOC (fora do protocolo congelado) do UNI-04 parte A.

1. O T17 (renda x churn, 39 maduras de 2025) com controle de idade: quanto do efeito era maturidade?
2. A Q3 com o churn EB do Lifetime em pontos percentuais (no resultado oficial ele saiu em fracao e arredondou para 0,00).
Nao muda o resultado oficial; so' ajuda a ler.
"""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
s_ = importlib.util.spec_from_file_location("r4", AQUI / "01_renda_churn.py"); r4 = importlib.util.module_from_spec(s_); s_.loader.exec_module(r4)
ex = r4.ex

f, d = ex.carregar()
A = ex.atributos(d)
Yp = ex.desfechos(f, ex.INI, ex.FIM)
Y26 = ex.desfechos(f, r4.INI26, r4.FIM26)
T17 = next(t for t in ex.TESTES if t["id"] == "T17")
u17 = list(ex.montar(T17, Yp, A)[0].index)
ref = A.loc[u17, "l_renda"]
A["renda_z"] = (A.l_renda - ref.mean()) / ref.std(ddof=0)
A["l_idade25"] = r4.idade_media(f, ex.INI, ex.FIM)
A["l_idade26"] = r4.idade_media(f, r4.INI26, r4.FIM26)
D = A.join(Yp).loc[u17]
pp = lambda r: f"{r['beta']:+.2f} [{r['lo']:+.2f}; {r['hi']:+.2f}] (ΔR² LOO {r['dr2']:+.3f})"
print("T17 original             :", pp(r4.ols(D, "churn", ["l_m2", "l_pop", "renda_z"], "renda_z")))
print("T17 + log idade          :", pp(r4.ols(D, "churn", ["l_m2", "l_pop", "l_idade25", "renda_z"], "renda_z")))
D["idade_z"] = (D.l_idade25 - D.l_idade25.mean()) / D.l_idade25.std(ddof=0)
print("idade (sem renda)        :", pp(r4.ols(D, "churn", ["l_m2", "l_pop", "idade_z"], "idade_z")))
print("idade (com renda)        :", pp(r4.ols(D, "churn", ["l_m2", "l_pop", "renda_z", "idade_z"], "idade_z")))
print("meses de vida medios 2025: p10/p50/p90", np.exp(D.l_idade25).quantile([.1, .5, .9]).round(0).tolist())
# Q3 em pontos percentuais
novas = [u for u in Y26.index if u not in Yp.index and u not in set(f[(f.competencia <= ex.FIM) & (f.mv >= 12)].unidade_id)]
q3u = [u for u in u17 if u in Y26.index] + novas
G = A.loc[q3u].join(d[["lt_eb_churn_60d", "lt_e_meses_ativos_12m_mediano"]])
G = G.dropna(subset=["lt_eb_churn_60d", "lt_e_meses_ativos_12m_mediano", "l_pop", "l_idade26", "l_renda"]).copy()
G["br"] = d.hex_id_res7.reindex(G.index)
G["lt_churn_pp"] = 100 * G.lt_eb_churn_60d
G["z"] = (G.l_renda - G.l_renda.mean()) / G.l_renda.std(ddof=0)
print("Q3 churn EB 60d (pp) ~ renda isocrona + pop + idade:", pp(r4.ols(G, "lt_churn_pp", ["l_pop", "l_idade26", "z"], "z")), "| media", round(G.lt_churn_pp.mean(), 2))
