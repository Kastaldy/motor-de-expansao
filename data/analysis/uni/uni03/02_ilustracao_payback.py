# -*- coding: utf-8 -*-
"""ILUSTRACAO (fora do protocolo): quanto a rampa muda o payback de uma unidade tipica no simulador de producao.

Unidade tipica = nivel maduro mediano da exploracao do UNI-03 (2.213 alunos), premissas-padrao do simulador, investimento
= SIM_CAPEX_DEFAULT como obra (sem financiamento), taxa de franquia padrao. O simulador so' aceita rampa linear
(alunos_inicial, maturacao_meses); a curva observada entra pela reta que melhor a aproxima:
- alunos: a linear recalibrada do UNI-03 (62% no mes 1, 100% no mes 8);
- faturamento: a reta ajustada a curva MEDIANA de faturamento (o simulador faz faturamento proporcional a alunos, entao
  dar a ele a forma do faturamento reproduz o caixa observado).
Rodar com PYTHONPATH=src.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from motor_expansao.dimensionamento.config import SIM_ALUGUEL_MES, SIM_CAPEX_DEFAULT, SIM_MENSALIDADE_BALCAO, SIM_SHARE_BALCAO
from motor_expansao.dimensionamento.simulador import Premissas, simular

AQUI = Path(__file__).resolve().parent
D = 2213.0

c = pd.read_csv(AQUI / "curva_uni03.csv", sep=";", encoding="utf-8-sig")
fat = c[(c.serie == "faturamento") & c.k.between(1, 12)].set_index("k").p50
melhor = min(((np.abs(a + (1 - a) * np.minimum(fat.index.to_numpy() / M, 1) - fat.to_numpy()).mean(), a, M)
              for a in np.round(np.arange(0, 1.0001, 0.01), 2) for M in range(1, 13)))
_, a_fat, M_fat = melhor

cenarios = {
    "hoje (500 alunos, reta até o mês 8)": dict(alunos_inicial=500.0, maturacao_meses=8),
    "curva de alunos observada (62% no mês 1, 100% no mês 8)": dict(alunos_inicial=0.62 * D, maturacao_meses=8),
    f"curva de faturamento observada ({a_fat:.0%} no mês 1, 100% no mês {M_fat})": dict(alunos_inicial=a_fat * D, maturacao_meses=int(M_fat)),
}
linhas = []
for nome, kw in cenarios.items():
    r = simular(D, Premissas(ticket_cheio=float(SIM_MENSALIDADE_BALCAO), share_balcao=SIM_SHARE_BALCAO, aluguel_mes=float(SIM_ALUGUEL_MES), **kw), obra=float(SIM_CAPEX_DEFAULT))
    ser = pd.DataFrame(r.serie_mensal)
    fat12 = ser[(ser.mes >= 1) & (ser.mes <= 12)].faturamento_mensal.sum() if ser is not None else np.nan
    caixa_min = ser.fcf_acumulado.min() if ser is not None else np.nan
    linhas.append({"cenario": nome, "payback_meses": r.payback_meses, "faturamento_1o_ano": fat12, "caixa_minimo": caixa_min})
T = pd.DataFrame(linhas)
print(T.to_string(index=False))
L = ["# UNI-03 — ilustração: a rampa no payback de uma unidade típica (fora do protocolo)", "",
     f"Unidade de {D:,.0f} alunos maduros (mediana da exploração), premissas-padrão do simulador, obra de R$ {SIM_CAPEX_DEFAULT:,.0f} sem financiamento.", "",
     "| rampa | payback (meses) | faturamento do 1º ano | pior caixa acumulado |", "|---|---|---|---|"]
for _, r in T.iterrows():
    L.append(f"| {r.cenario} | {r.payback_meses:.0f} | R$ {r.faturamento_1o_ano:,.0f} | R$ {r.caixa_minimo:,.0f} |")
(AQUI / "ilustracao_payback_uni03.md").write_text("\n".join(L) + "\n", encoding="utf-8")
