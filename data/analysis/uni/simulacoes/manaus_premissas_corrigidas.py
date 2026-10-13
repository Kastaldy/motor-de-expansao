# -*- coding: utf-8 -*-
"""EXPLORATORIO (2026-09-30, Felipe): Manaus NOVA CIDADE com as premissas CORRIGIDAS e o "feeling" do diretor.
Premissas corrigidas: 2.000 m2, obra R$ 2,3 mi, equipamentos R$ 1,5 mi em 60x a 2% a.m., taxa de franquia ZERO,
aluguel R$ 80 mil, plano cheio R$ 167, 1 estudio (100 vagas e terreno de 4.000 m2 nao entram no modelo).
Feeling do diretor: 5% da base em plano de estudio (mais caro); o preco nao foi dado -> sensibilidade.
Demanda (alunos maduros) em tres leituras: v2 com a master de RJ/SP (~R$ 230 mil), comparaveis de renda baixa com
estudio (mediana R$ 329 mil) e o numero do diretor (R$ 400 mil a R$ 167). Horizonte estendido a 120 meses so para
reportar o payback em meses (o criterio de viabilidade e o mesmo). .venv, PYTHONPATH=src."""
import importlib.util
from pathlib import Path

import numpy as np

from motor_expansao.dimensionamento import config as cfg
from motor_expansao.dimensionamento.simulador import Premissas, simular

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent


def mod(nome, p):
    s = importlib.util.spec_from_file_location(nome, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


c5 = mod("c5", UNI / "uni05" / "01_comparacao.py")
TICKET, ALUGUEL, OBRA, EQUIP, PRAZO, JUROS, FRANQUIA = 167.0, 80_000.0, 2_300_000.0, 1_500_000.0, 60, 0.02, 0.0
HORIZONTE = 120


def premissas(al, preco_studio=None, pct_studio=0.0, aluguel=ALUGUEL):
    """Plano de estudio: pct_studio da base TOTAL paga preco_studio no lugar do plano cheio (todos de balcao).
    O ticket do agregador fica preso ao plano cheio (60% de R$ 167): o plano de estudio nao passa pelo agregador."""
    s = cfg.SIM_SHARE_BALCAO
    tk_bal = TICKET + ((preco_studio - TICKET) * pct_studio / s if preco_studio else 0.0)
    return Premissas(ticket_cheio=tk_bal, share_balcao=s, ticket_agregador_absoluto=TICKET * cfg.SIM_TICKET_AGREGADOR_FATOR,
                     aluguel_mes=aluguel, alunos_inicial=float(c5.RAMPA_OBS[0] * al), maturacao_meses=int(c5.RAMPA_OBS[1]),
                     outros_fixos_mes=float(cfg.SIM_OUTROS_FIXOS_MES) + float(cfg.SIM_CUSTO_STUDIO), horizonte_meses=HORIZONTE)


def sim(al, preco_studio=None, pct_studio=0.0, obra=OBRA, franquia=FRANQUIA, aluguel=ALUGUEL, juros=JUROS, prazo=PRAZO):
    p = premissas(al, preco_studio, pct_studio, aluguel)
    r = simular(float(al), p, obra=obra, equipamentos=EQUIP, prazo_equipamentos=prazo, juros_equipamentos_am=juros,
                taxa_franquia=franquia)
    pb = r.payback_meses if np.isfinite(r.payback_meses) else np.inf
    return dict(fat=p.faturamento(al, com_anuidade=True), margem=r.margem_ebitda_pct, payback=pb, serie=r.serie_mensal, r=r)


def alunos_para_fat_167(fat):
    lo, hi = 100.0, 10_000.0
    for _ in range(60):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if premissas(m).faturamento(m, com_anuidade=True) < fat else (lo, m)
    return hi


def preco_para(al, alvo, pct=0.05):
    """Menor preco do plano de estudio que leva o payback a <= alvo meses (None se nem R$ 1.000 leva)."""
    if sim(al, 1000.0, pct)["payback"] > alvo:
        return None
    lo, hi = TICKET, 1000.0
    for _ in range(40):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if sim(al, m, pct)["payback"] > alvo else (lo, m)
    return hi


def fmt_pb(pb):
    return ">120" if not np.isfinite(pb) else f"{pb:.0f}"


def main():
    DEM = {"Modelo v2 (master de RJ/SP)": c5.alunos_de(230_000.0),
           "Comparáveis de renda baixa com estúdio (mediana)": c5.alunos_de(329_000.0),
           "Diretor (R$ 400 mil a R$ 167)": alunos_para_fat_167(400_000.0)}
    L = ["# Manaus — premissas corrigidas e plano de estúdio (EXPLORATÓRIO, 2026-09-30)", "",
         f"Premissas: obra R$ {OBRA / 1e6:.1f} mi; equipamentos R$ {EQUIP / 1e6:.1f} mi em {PRAZO}x a {100 * JUROS:.0f}% a.m.; "
         f"taxa de franquia R$ {FRANQUIA:,.0f}; aluguel R$ {ALUGUEL:,.0f}; plano cheio R$ {TICKET:.0f}; 1 estúdio (+R$ {cfg.SIM_CUSTO_STUDIO:,.0f}/mês); "
         f"balcão {cfg.SIM_SHARE_BALCAO:.0%}; agregador a {cfg.SIM_TICKET_AGREGADOR_FATOR:.0%} do plano cheio; rampa observada {c5.RAMPA_OBS}. "
         "Vagas (100) e terreno (4.000 m²) não entram no modelo.", "",
         "Plano de estúdio: 5% da base TOTAL paga o preço do plano de estúdio no lugar do plano cheio (são alunos de balcão; "
         "o agregador não paga plano de estúdio).", ""]
    # 1) antes x depois das correcoes
    L += ["## 1. Efeito das correções (sem plano de estúdio)", "",
          "| demanda | alunos maduros | faturamento maduro | payback antes (obra 2,5 mi + franquia 160 mil) | payback agora |", "|---|---|---|---|---|"]
    for rot, al in DEM.items():
        a = sim(al, obra=2_500_000.0, franquia=cfg.SIM_TAXA_FRANQUIA); b = sim(al)
        L.append(f"| {rot} | {al:,.0f} | R$ {b['fat'] / 1000:,.0f} mil | {fmt_pb(a['payback'])} | {fmt_pb(b['payback'])} |")
    # 2) plano de estudio
    PRECOS = (197.0, 247.0, 297.0, 347.0)
    L += ["", "## 2. Plano de estúdio em 5% da base (payback em meses)", "",
          "| demanda | sem plano | " + " | ".join(f"R$ {p:.0f}" for p in PRECOS) + " | preço p/ 48 meses | preço p/ 36 meses |",
          "|---|---|" + "---|" * len(PRECOS) + "---|---|"]
    for rot, al in DEM.items():
        cel = [fmt_pb(sim(al)["payback"])] + [fmt_pb(sim(al, p, 0.05)["payback"]) for p in PRECOS]
        p48, p36 = preco_para(al, 48), preco_para(al, 36)
        L.append(f"| {rot} | " + " | ".join(cel) + f" | {'R$ %.0f' % p48 if p48 else 'não alcança'} | {'R$ %.0f' % p36 if p36 else 'não alcança'} |")
    al_d = DEM["Diretor (R$ 400 mil a R$ 167)"]
    ganho = (sim(al_d, 297.0, 0.05)["fat"] - sim(al_d)["fat"])
    L += ["", f"Quanto o plano rende: com a demanda do diretor, 5% a R$ 297 somam ~R$ {ganho / 1000:,.1f} mil/mês de faturamento "
          f"({100 * ganho / sim(al_d)['fat']:.1f}%).", ""]
    # 3) o mes maduro (decomposicao) para a demanda do diretor
    s = sim(al_d)["serie"]
    m = next(x for x in s if x.get("mes") == 24) if any(x.get("mes") == 24 for x in s) else s[len(s) // 2]
    L += ["## 3. Um mês maduro (mês 24), demanda do diretor, sem plano de estúdio", "",
          "| linha | R$/mês |", "|---|---|"]
    for k, v in m.items():
        if isinstance(v, (int, float)) and k != "mes":
            L.append(f"| {k} | {v:,.0f} |")
    # 4) alavancas combinadas
    L += ["", "## 4. Alavancas (payback em meses, demanda do diretor)", "", "| cenário | sem plano | plano R$ 297 em 5% |", "|---|---|---|"]
    for rot, kw in (("premissas corrigidas", {}), ("equipamento a 1% a.m.", {"juros": 0.01}), ("aluguel R$ 60 mil", {"aluguel": 60_000.0}),
                    ("aluguel R$ 60 mil + equipamento a 1%", {"aluguel": 60_000.0, "juros": 0.01}),
                    ("aluguel R$ 50 mil + equipamento a 1%", {"aluguel": 50_000.0, "juros": 0.01})):
        L.append(f"| {rot} | {fmt_pb(sim(al_d, **kw)['payback'])} | {fmt_pb(sim(al_d, 297.0, 0.05, **kw)['payback'])} |")
    (AQUI / "resultado_manaus_premissas_corrigidas.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
