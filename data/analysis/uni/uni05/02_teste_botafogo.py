# -*- coding: utf-8 -*-
"""Teste pedido por Felipe (2026-09-29): a previsao V2 de Botafogo com as alavancas do operador declaradas.

A demanda (alunos) e' a mesma da V2 (UNI-05 v1.1). Muda so' o que o operador decide antes de abrir:
(1) como esta' — 69% balcao / 31% agregador, ticket padrao R$ 137;
(2) 100% recorrente (a unidade nao aceita agregador), ticket padrao;
(3) 100% recorrente com o preco real do plano Gold da unidade (R$ 177).
Mesmos custos-padrao e rampa observada do UNI-05. Rodar com PYTHONPATH=src.
"""
import importlib.util
from pathlib import Path

import pandas as pd

from motor_expansao.dimensionamento.config import SIM_ALUGUEL_MES, SIM_CAPEX_DEFAULT
from motor_expansao.dimensionamento.simulador import Premissas, simular

AQUI = Path(__file__).resolve().parent
s_ = importlib.util.spec_from_file_location("c5", AQUI / "01_comparacao.py"); c5 = importlib.util.module_from_spec(s_); s_.loader.exec_module(c5)

c = pd.read_csv(AQUI / "comparacao_por_unidade.csv", sep=";", encoding="utf-8-sig").set_index("unidade_id").loc["botafogo-rj"]
D = c5.alunos_de(c.fat_V2)
print(f"Botafogo: faturamento real R$ {c.fat_real:,.0f}; V2 previu R$ {c.fat_V2:,.0f} => {D:,.0f} alunos (payback REAL {c.pb_REAL:.0f})")
for nome, ticket, share in (("(1) como esta' (69/31, R$ 137)", 137.0, 0.69), ("(2) 100% recorrente, R$ 137", 137.0, 1.0), ("(3) 100% recorrente, R$ 177", 177.0, 1.0)):
    p = Premissas(ticket_cheio=ticket, share_balcao=share, aluguel_mes=float(SIM_ALUGUEL_MES), alunos_inicial=0.64 * D, maturacao_meses=11)
    r = simular(D, p, obra=float(SIM_CAPEX_DEFAULT))
    fat = p.faturamento(D, com_anuidade=True)
    print(f"{nome:32s} faturamento maduro R$ {fat:,.0f} ({fat / c.fat_real - 1:+.0%} do real) | payback {r.payback_meses:.0f} meses | margem {r.margem_ebitda_pct:.0%} | viavel {r.flag_viavel}")
alunos_reais = c5.alunos_de(c.fat_real)
print(f"Para chegar ao real com (3), a demanda teria de ser ~{(c.fat_real - 5000) / (Premissas(ticket_cheio=177.0, share_balcao=1.0, aluguel_mes=20000.0).faturamento(1, com_anuidade=True) - Premissas(ticket_cheio=177.0, share_balcao=1.0, aluguel_mes=20000.0).faturamento(0, com_anuidade=True)):,.0f} alunos (a V2 previu {D:,.0f}).")
