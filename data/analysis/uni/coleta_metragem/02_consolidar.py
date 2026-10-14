# -*- coding: utf-8 -*-
"""Consolida a coleta manual de metragem (Felipe e Vini, 2026-09-28) e mede a qualidade da estimativa por satelite.

Regras (fixadas antes de olhar a calibracao):
- Estimativa valida = area_telhado_m2 x pavimentos_academia, so' com mede_por_satelite == "sim" e os dois numeros.
  "nao" com area preenchida NAO conta (fica listado).
- Calibracao: razao estimativa / metragem conhecida nas unidades do gabarito. Vies = mediana da razao; erro tipico =
  mediana de |razao - 1|.
- Correcao: so' se houver >= 5 unidades de calibracao medidas e |vies - 1| > 5%; aí estimativa corrigida = estimativa / vies.
- Se o erro tipico passar de 30%, a metragem estimada entra no modelo so' como sensibilidade.
- Unidade medida pelos dois: media das duas estimativas (corrigidas).
Saidas: metragem_estimada.csv, qualidade_coleta.md. Nenhum dado de desempenho e' lido aqui.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
GAB = AQUI / "_gabarito_nao_abrir"
# versao da coleta: "2026-09-28" (padrao; entrada dos estudos congelados) ou "2026-09-29" (Vini completou 10 unidades).
# A regra e' a mesma; so' muda a planilha do Vini e o sufixo das saidas (as de 28/09 ficam intactas).
VERSAO = sys.argv[1] if len(sys.argv) > 1 else "2026-09-28"
SUF = "" if VERSAO == "2026-09-28" else f"_{VERSAO}"
FACHADA = ["letreiro_visivel_da_rua", "vitrine_para_rua", "frente_para_via_principal", "esquina", "estacionamento_proprio", "acesso_pelo_terreo"]


def ler():
    f = pd.read_excel(AQUI / "planilha_felipe_2026-09-28.xlsx", sheet_name="Felipe").assign(avaliador="Felipe")
    v = pd.read_excel(AQUI / f"planilha_vini_{VERSAO}.xlsx", sheet_name="Vini").assign(avaliador="Vini")
    t = pd.concat([f, v], ignore_index=True)
    t = t[t[["mede_por_satelite", "area_telhado_m2", "tipo_imovel"]].notna().any(axis=1)].copy()
    ok = t.mede_por_satelite.eq("sim") & t.area_telhado_m2.notna() & t.pavimentos_academia.notna()
    t["estimativa_m2"] = (t.area_telhado_m2 * t.pavimentos_academia).where(ok)
    t["inconsistente"] = t.mede_por_satelite.eq("não") & t.area_telhado_m2.notna()
    return t


def main():
    t = ler()
    gab = pd.read_csv(GAB / "gabarito_calibracao.csv", sep=";", encoding="utf-8-sig", index_col=0)
    t["conhecida_m2"] = t.unidade_id.map(gab.tam_metragem_m2)
    cal = t[t.conhecida_m2.notna() & t.estimativa_m2.notna()].copy()
    cal["razao"] = cal.estimativa_m2 / cal.conhecida_m2
    n_cal = len(cal)
    vies = cal.razao.median() if n_cal else np.nan
    erro = (cal.razao - 1).abs().median() if n_cal else np.nan
    corrige = bool(n_cal >= 5 and abs(vies - 1) > 0.05)
    t["estimativa_corrigida_m2"] = t.estimativa_m2 / vies if corrige else t.estimativa_m2
    precisao = "sensibilidade" if (pd.notna(erro) and erro > 0.30) else "principal"
    # concordancia entre avaliadores
    dup = t[t.estimativa_m2.notna()].groupby("unidade_id").filter(lambda g: g.avaliador.nunique() == 2)
    conc = dup.pivot_table(index="unidade_id", columns="avaliador", values="estimativa_m2", aggfunc="first")
    tip = t.groupby("unidade_id").filter(lambda g: g.avaliador.nunique() == 2).pivot_table(index="unidade_id", columns="avaliador", values="tipo_imovel", aggfunc="first")
    # consolidado por unidade (so' as que NAO sao de calibracao entram como metragem nova)
    novas = t[t.conhecida_m2.isna()]
    agg = novas.groupby("unidade_id").agg(
        metragem_estimada_m2=("estimativa_corrigida_m2", "mean"), n_medidas=("estimativa_m2", "count"),
        avaliadores=("avaliador", lambda s: "+".join(sorted(set(s)))), prioridade=("prioridade", "first"),
        tipo_imovel=("tipo_imovel", lambda s: s.dropna().iloc[0] if s.notna().any() else None),
        confianca=("confianca_medida", lambda s: ",".join(sorted(set(s.dropna())))))
    for c in FACHADA:
        agg[c] = novas.groupby("unidade_id")[c].agg(lambda s: s.dropna().iloc[0] if s.notna().any() else None)
    agg["nota_fachada_1a5"] = novas.groupby("unidade_id").nota_fachada_1a5.mean()
    agg["uso_no_modelo"] = np.where(agg.metragem_estimada_m2.notna(), precisao, "sem metragem")
    agg.to_csv(AQUI / f"metragem_estimada{SUF}.csv", sep=";", encoding="utf-8-sig")

    pct = lambda v: "–" if pd.isna(v) else f"{100 * v:.0f}%"
    L = [f"# Coleta manual de metragem — qualidade da estimativa por satélite ({VERSAO})", "",
         f"- Linhas preenchidas: {len(t)} (Felipe {int((t.avaliador == 'Felipe').sum())}, Vini {int((t.avaliador == 'Vini').sum())}); "
         f"com estimativa válida: {int(t.estimativa_m2.notna().sum())}; 'não mede' mas com área (não usadas): {t[t.inconsistente].unidade_id.tolist() or 'nenhuma'}.",
         f"- Unidades novas com metragem estimada: **{int(agg.metragem_estimada_m2.notna().sum())}** "
         f"(P1: {int(agg[agg.prioridade == 'P1'].metragem_estimada_m2.notna().sum())}); sem metragem (shopping/andar compartilhado): {int(agg.metragem_estimada_m2.isna().sum())}.", "",
         "## Calibração (unidades de metragem conhecida, medidas sem saber o valor)", "",
         "| unidade | avaliador | estimada | conhecida | razão |", "|---|---|---|---|---|"]
    for _, r in cal.sort_values("razao").iterrows():
        L.append(f"| {r.unidade_id} | {r.avaliador} | {r.estimativa_m2:,.0f} | {r.conhecida_m2:,.0f} | {r.razao:.2f} |")
    L += ["", f"- N = {n_cal}. **Viés (mediana da razão): {vies:.2f}**; **erro típico: {pct(erro)}**.",
          f"- Correção aplicada: {'sim, estimativa ÷ ' + format(vies, '.2f') if corrige else 'não'} (regra: ≥ 5 unidades e viés > 5%).",
          f"- Uso da metragem estimada no modelo: **{precisao}** (regra: erro típico > 30% → só sensibilidade).",
          f"- Calibração em shopping medida: {int(t[t.conhecida_m2.notna() & t.unidade_id.map(gab.poi_em_shopping).eq(1)].estimativa_m2.notna().sum())} de "
          f"{int(t.conhecida_m2.notna().sum() and t[t.conhecida_m2.notna()].unidade_id.map(gab.poi_em_shopping).eq(1).sum())} tentadas.", "",
          "## Concordância entre avaliadores (unidades medidas pelos dois)", ""]
    if len(conc):
        L += ["| unidade | Felipe | Vini | razão V/F |", "|---|---|---|---|"] + \
             [f"| {u} | {r.get('Felipe', np.nan):,.0f} | {r.get('Vini', np.nan):,.0f} | {r.get('Vini', np.nan) / r.get('Felipe', np.nan):.2f} |" for u, r in conc.iterrows()]
    else:
        L.append("Nenhuma unidade com estimativa dos dois.")
    if len(tip):
        L += ["", f"Tipo de imóvel igual nos dois: {int((tip.Felipe == tip.Vini).sum())} de {len(tip)} unidades "
              f"({', '.join(f'{u}: {r.Felipe} × {r.Vini}' for u, r in tip[tip.Felipe != tip.Vini].iterrows())})."]
    (AQUI / f"qualidade_coleta{SUF}.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
