# -*- coding: utf-8 -*-
"""EXPLORATORIO (2026-09-30, Felipe): Manaus NOVA CIDADE — (A) faturamento com os fatores do operador (plano R$ 167,
plano de estudio em 5% da base a R$ 272 = meio da faixa testada, so' referencia) nas tres leituras de demanda;
(B) payback por prazo e juros do financiamento dos equipamentos (R$ 1,5 mi). Reusa manaus_premissas_corrigidas.py.
.venv, PYTHONPATH=src."""
import importlib.util
from pathlib import Path

AQUI = Path(__file__).resolve().parent


def mod(nome, p):
    s = importlib.util.spec_from_file_location(nome, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


mc = mod("mc", AQUI / "manaus_premissas_corrigidas.py")
PRECO_STUDIO, PCT = 272.0, 0.05


def pmt(v, i, n):
    return v * i / (1 - (1 + i) ** -n) if i > 0 else v / n


def main():
    DEM = {"Modelo v2 (master de RJ/SP)": mc.c5.alunos_de(230_000.0),
           "Comparáveis de renda baixa com estúdio": mc.c5.alunos_de(329_000.0),
           "Diretor": mc.alunos_para_fat_167(400_000.0)}
    L = ["# Manaus — faturamento com os fatores do operador e financiamento (EXPLORATÓRIO, 2026-09-30)", "",
         f"Premissas corrigidas (obra R$ 2,3 mi, franquia 0, aluguel R$ 80 mil, plano R$ 167, 1 estúdio). Plano de estúdio: {PCT:.0%} da base "
         f"total a R$ {PRECO_STUDIO:.0f} (meio da faixa testada; só referência).", "",
         "## A. Faturamento", "",
         "| demanda | alunos maduros | faturamento no mês 1 | faturamento maduro sem plano | com plano de estúdio | margem EBITDA | payback |",
         "|---|---|---|---|---|---|---|"]
    for rot, al in DEM.items():
        a, b = mc.sim(al), mc.sim(al, PRECO_STUDIO, PCT)
        m1 = next(x["faturamento_mensal"] for x in b["serie"] if x.get("fase") != "pre" and x["faturamento_mensal"] > 0)
        L.append(f"| {rot} | {al:,.0f} | R$ {m1 / 1000:,.0f} mil | R$ {a['fat'] / 1000:,.0f} mil | R$ {b['fat'] / 1000:,.0f} mil | "
                 f"{100 * b['margem']:.0f}% | {mc.fmt_pb(b['payback'])} |")
    L += ["", "Margem e payback com o plano de estúdio.", ""]
    al_d = DEM["Diretor"]
    PRAZOS, JUROS = (36, 48, 60, 72, 84, 96, 120), (0.02, 0.018, 0.015, 0.01)
    L += ["## B. Financiamento dos equipamentos (R$ 1,5 mi) — payback em meses, demanda do diretor, com plano de estúdio", "",
          "| prazo | " + " | ".join(f"{100 * j:.1f}% a.m." for j in JUROS) + " |", "|---|" + "---|" * len(JUROS)]
    for n in PRAZOS:
        L.append(f"| {n}x | " + " | ".join(mc.fmt_pb(mc.sim(al_d, PRECO_STUDIO, PCT, juros=j, prazo=n)["payback"]) for j in JUROS) + " |")
    L += ["", "Parcela mensal e juros totais:", "", "| prazo | " + " | ".join(f"{100 * j:.1f}% a.m." for j in JUROS) + " |", "|---|" + "---|" * len(JUROS)]
    for n in PRAZOS:
        L.append(f"| {n}x | " + " | ".join(f"R$ {pmt(mc.EQUIP, j, n) / 1000:,.0f} mil (juros R$ {(pmt(mc.EQUIP, j, n) * n - mc.EQUIP) / 1e6:,.2f} mi)" for j in JUROS) + " |")
    L += ["", "## C. Combinações, demanda do diretor, com plano de estúdio", "", "| cenário | payback |", "|---|---|"]
    for rot, kw in (("1,8% a.m. em 60x", dict(juros=0.018)), ("1,8% a.m. em 96x", dict(juros=0.018, prazo=96)),
                    ("1,8% a.m. em 60x + aluguel R$ 70 mil", dict(juros=0.018, aluguel=70_000.0)),
                    ("1,8% a.m. em 60x + aluguel R$ 60 mil", dict(juros=0.018, aluguel=60_000.0)),
                    ("1,8% a.m. em 96x + aluguel R$ 60 mil", dict(juros=0.018, prazo=96, aluguel=60_000.0)),
                    ("1,0% a.m. em 60x + aluguel R$ 60 mil", dict(juros=0.01, aluguel=60_000.0))):
        L.append(f"| {rot} | {mc.fmt_pb(mc.sim(al_d, PRECO_STUDIO, PCT, **kw)['payback'])} |")
    L += ["", "Na demanda da v2 (master de RJ/SP), com o melhor financiamento da tabela (1,0% em 120x) e plano de estúdio: "
          f"{mc.fmt_pb(mc.sim(DEM['Modelo v2 (master de RJ/SP)'], PRECO_STUDIO, PCT, juros=0.01, prazo=120)['payback'])} meses.", ""]
    (AQUI / "resultado_manaus_financiamento.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
