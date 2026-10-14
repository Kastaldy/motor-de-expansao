# -*- coding: utf-8 -*-
"""EXPLORATORIO (2026-09-30, Felipe): "como a v2 deu ~1.900 alunos para uma unidade desse porte?" Olha o VOLUME
direto, sem passar pela conversao faturamento -> alunos do simulador:
(1) faturamento por aluno ativo REAL da rede x o que o simulador supoe; (2) quantos ativos a rede tem de fato (e as
grandes, e as comparaveis de renda baixa com estudio); (3) a v2 ajustada em log(ATIVOS) e a previsao de Manaus;
(4) faturamento e payback a R$ 167 com esse volume. Praca de Manaus do resultado_manaus_diagnostico.md (circulo 5 km).
.venv, PYTHONPATH=src."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent


def mod(nome, p):
    s = importlib.util.spec_from_file_location(nome, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


u7 = mod("u7", UNI / "uni07" / "01_incerteza.py")
ex, alav, X_ = u7.ex, u7.alav, u7.X_
mc = mod("mc", AQUI / "manaus_premissas_corrigidas.py")
MAN = dict(renda_pc=1073.0, renda_dom=3511.0, pop=525_532.0, m2=2000.0)
COMPARAVEIS = ("PARANOA PARQUE", "SANTA MARIA", "SUZANO", "BANGU", "BOA VISTA", "CARIACICA", "VALPARAISO")


def main():
    f, d = ex.carregar()
    A = alav.atributos_ext(d)
    A["l_renda_dom"] = np.log(pd.to_numeric(d.iso_renda_pc__carro_10, errors="coerce") * pd.to_numeric(d.iso_pop__carro_10, errors="coerce")
                              / pd.to_numeric(d.iso_domicilios__carro_10, errors="coerce"))
    mid = pd.read_csv(UNI / "alavancas" / "master_id_cadastro.csv", sep=";", dtype=str)
    A["master_id"] = d.cod_cadastro.map(mid.assign(c=mid.cod_cadastro.str.zfill(2)).set_index("c").master_id).reindex(A.index)
    Y25, Y26 = ex.desfechos(f, "2025-01", "2025-12"), ex.desfechos(f, "2026-01", "2026-08")
    tr = A.join(Y25, how="inner").dropna(subset=["l_fat", "l_ativos", "l_m2", "l_renda", "l_pop", "frac_indep", "studios", "master_id", "l_renda_dom"])
    cont = tr.master_id.value_counts(); proprios = sorted(m for m, n in cont.items() if n >= 4 and m != "M1")
    for m in proprios:
        tr[f"mr_{m}"] = (tr.master_id == m).astype(float)
    tr["mr_outras"] = (~tr.master_id.isin(["M1"] + proprios)).astype(float)
    DUM = [f"mr_{m}" for m in proprios] + ["mr_outras"]
    V2 = ["l_m2", "l_renda_dom", "l_pop"] + DUM + ["studios"]
    tr["ativos"], tr["fat"], tr["fat_por_ativo"] = np.exp(tr.l_ativos), np.exp(tr.l_fat), np.exp(tr.l_ticket)
    tr["nome"], tr["m2"] = d.nome.reindex(tr.index), np.exp(tr.l_m2)

    L = ["# Manaus — o volume de alunos, olhado direto (EXPLORATÓRIO, 2026-09-30)", "",
         f"Base: as {len(tr)} unidades maduras de treino (2025), médias mensais. 'Ativos' = alunos ativos no mês (balcão + agregador).", ""]
    # 1) faturamento por ativo
    fpa = tr.fat_por_ativo
    L += ["## 1. Quanto cada aluno ativo fatura de verdade", "",
          f"- Rede (2025): mediana **R$ {fpa.median():,.0f}** por ativo/mês (p25 R$ {fpa.quantile(.25):,.0f}, p75 R$ {fpa.quantile(.75):,.0f}); "
          f"agregador mediano {100 * tr.agr.median():.0f}% dos ativos.",
          f"- Simulador (plano R$ 137, 69% balcão): R$ {mc.c5.R_ALUNO:,.0f} por aluno. A conversão faturamento → alunos usada até aqui "
          f"divide por esse número; se o real é R$ {fpa.median():,.0f}, ela conta **{100 * (1 - fpa.median() / mc.c5.R_ALUNO):.0f}% alunos a menos**.", ""]
    # 2) volume real
    q = tr.ativos.quantile([.25, .5, .75, .9])
    L += ["## 2. Quantos ativos a rede tem", "",
          f"- Mediana {q[.5]:,.0f}; p25 {q[.25]:,.0f}; p75 {q[.75]:,.0f}; p90 {q[.9]:,.0f}; máximo {tr.ativos.max():,.0f}.", "",
          "| unidade | m² | estúdio | ativos | faturamento/mês | R$ por ativo | agregador |", "|---|---|---|---|---|---|---|"]
    grandes = tr[tr.m2 >= 1800].sort_values("ativos", ascending=False)
    comp = tr[tr.nome.str.upper().str.contains("|".join(COMPARAVEIS), na=False)]
    for rot, g in (("≥ 1.800 m²", grandes), ("comparáveis de renda baixa com estúdio", comp)):
        L.append(f"| **{rot}** (n={len(g)}, mediana {g.ativos.median():,.0f} ativos) | | | | | | |")
        for _, r in g.iterrows():
            L.append(f"| {r.nome} | {r.m2:,.0f} | {'sim' if r.studios else 'não'} | {r.ativos:,.0f} | R$ {r.fat / 1000:,.0f} mil | R$ {r.fat_por_ativo:,.0f} | {100 * r.agr:.0f}% |")
    # 3) v2 em ativos
    y = tr.l_ativos.to_numpy(float); X = X_(tr, V2)
    b, e, h, _ = ex.ols(y, X)
    loo = e / (1 - h)
    man = {"l_m2": np.log(MAN["m2"]), "l_renda_dom": np.log(MAN["renda_dom"]), "l_pop": np.log(MAN["pop"]), "studios": 1.0, **{c: 0.0 for c in DUM}}
    ql, qm, qh = np.quantile(loo, [.1, .5, .9])
    L += ["", "## 3. A v2 ajustada direto em ATIVOS", "",
          f"R² LOO {ex.r2_loo(y, e, h):.3f}; erro típico LOO {100 * np.median(np.abs(np.exp(loo) - 1)):.0f}%.", "",
          "| variável | coeficiente | Manaus | típica | contribuição |", "|---|---|---|---|---|"]
    man_m3 = {**man, "mr_M3": 1.0} if "mr_M3" in DUM else man
    for j, c in enumerate(V2):
        xt = tr[c].mean() if c in DUM + ["studios"] else tr[c].median()
        fmt = (lambda v: f"{np.exp(v):,.0f}") if c.startswith("l_") else (lambda v: f"{v:.2f}")
        L.append(f"| {c} | {b[j + 1]:+.3f} | {fmt(man_m3[c])} | {fmt(xt)} | {100 * (np.exp(b[j + 1] * (man_m3[c] - xt)) - 1):+.0f}% |")
    prev = {}
    for rot, row in (("master de RJ/SP (M3)", man_m3), ("master 'outras'", {**man, "mr_outras": 1.0})):
        p = float(X_(pd.DataFrame([row]), V2) @ b)
        prev[rot] = p
        L.append("")
        L.append(f"**Manaus, {rot}: {np.exp(p):,.0f} ativos** (faixa 80%: {np.exp(p + ql):,.0f} a {np.exp(p + qh):,.0f}).")
    st = tr.groupby("studios").ativos.median()
    L += ["", f"Ativos medianos na rede: com estúdio {st.get(1.0, np.nan):,.0f}, sem estúdio {st.get(0.0, np.nan):,.0f}.", ""]
    # 4) faturamento e payback a R$ 167 com esse volume
    L += ["## 4. Faturamento e payback a R$ 167 (premissas corrigidas + plano de estúdio a R$ 272 em 5%)", "",
          "| volume | ativos | faturamento maduro (simulador) | payback |", "|---|---|---|---|"]
    ref = [("v2 em ativos, M3", float(np.exp(prev["master de RJ/SP (M3)"]))),
           ("v2 em ativos, M3, p90 da faixa", float(np.exp(prev["master de RJ/SP (M3)"] + qh))),
           ("mediana das comparáveis", float(comp.ativos.median())),
           ("p90 da rede", float(q[.9]))]
    for rot, al in ref:
        s = mc.sim(al, 272.0, 0.05)
        L.append(f"| {rot} | {al:,.0f} | R$ {s['fat'] / 1000:,.0f} mil | {mc.fmt_pb(s['payback'])} |")
    r167 = (mc.premissas(2000.0).faturamento(2000.0, com_anuidade=True) - mc.premissas(1000.0).faturamento(1000.0, com_anuidade=True)) / 1000
    L += ["", f"O simulador fatura R$ {r167:,.0f} por aluno a R$ 167 (69% de balcão); a rede real fatura R$ {fpa.median():,.0f} por ativo "
          f"com os preços de hoje e {100 * tr.agr.median():.0f}% de agregador.", ""]
    (AQUI / "resultado_manaus_volume.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
