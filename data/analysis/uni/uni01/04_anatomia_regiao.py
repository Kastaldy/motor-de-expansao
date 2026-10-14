# -*- coding: utf-8 -*-
"""Seguimento da anatomia dos erros (exploratorio, declarado DEPOIS de ver 03): quanto do erro e' regiao (SP)?

1. Base + indicador de regiao (SP; SP/DF/outros; metro com >= 2 unidades): ganho de R2 LOO em faturamento, alunos e ticket.
2. As correlacoes mais fortes do 03 recalculadas DENTRO de SP e DENTRO do DF (se somem, eram efeito de regiao).
3. Politica de agregador da UF (mediana do % agregador das OUTRAS unidades da mesma UF — conhecida antes de abrir)
   como candidata ex ante no lugar do % agregador da propria unidade.
"""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

AQUI = Path(__file__).resolve().parent
s_ = importlib.util.spec_from_file_location("an", AQUI / "03_anatomia_erros.py"); an = importlib.util.module_from_spec(s_); s_.loader.exec_module(an)
ex = an.ex


def r2loo(D, y, xs):
    return an.loo(D, y, xs)[1]


def main():
    f, d = ex.carregar()
    A = ex.atributos(d)
    D, _ = an.rodar(f, d, A, ex.INI, ex.FIM)
    D = D.join(d[["uf", "cad_preco_gold", "poi_F1", "canib_frac_max__carro_10"]].rename(columns={"uf": "uf_"}))
    D["sp"] = (D.uf_ == "SP").astype(float)
    D["df"] = (D.uf_ == "DF").astype(float)
    cnt = D.metro.value_counts()
    for m in cnt[cnt >= 2].index[1:]:
        D[f"m_{int(m)}"] = (D.metro == m).astype(float)
    metros = [c for c in D.columns if c.startswith("m_")]
    # politica de agregador da UF, sem a propria unidade (leave-one-out dentro da UF), medida em todas as unidades com mv>=6 ate dez/25
    g6 = f[f.valido & (f.competencia <= ex.FIM) & (f.mv >= 6)]
    ult = g6.sort_values("competencia").groupby("unidade_id").tail(6).groupby("unidade_id").agr.mean()
    ufu = d.uf.reindex(ult.index)
    D["agr_uf_outras"] = [ult[(ufu == d.at[u, "uf"]) & (ult.index != u)].median() for u in D.index]

    L = ["# Seguimento: quanto do erro é região? (exploratório, desenhado depois de ver a anatomia)", "",
         "| modelo | faturamento R² LOO | alunos R² LOO | ticket R² LOO |", "|---|---|---|---|"]
    for nome, xs in (("base", ex.BASE), ("base + SP", ex.BASE + ["sp"]), ("base + SP + DF", ex.BASE + ["sp", "df"]),
                     (f"base + metro ({len(metros) + 1} metros com ≥ 2 unid.)", ex.BASE + metros),
                     ("base + política de agregador da UF", ex.BASE + ["agr_uf_outras"]),
                     ("base + SP + política de agregador da UF", ex.BASE + ["sp", "agr_uf_outras"]),
                     ("base + preço Gold", ex.BASE + ["cad_preco_gold"]), ("base + SP + preço Gold", ex.BASE + ["sp", "cad_preco_gold"])):
        G = D.dropna(subset=xs)
        L.append(f"| {nome} | {r2loo(G, 'l_fat', xs):.2f} | {r2loo(G, 'l_ativos', xs):.2f} | {r2loo(G, 'l_ticket', xs):.2f} |")
    L += ["", f"Preço Gold mediano: SP {D[D.sp == 1].cad_preco_gold.median():.0f}, DF {D[D.df == 1].cad_preco_gold.median():.0f}, "
          f"outros {D[(D.sp == 0) & (D.df == 0)].cad_preco_gold.median():.0f}. % agregador mediano (2025): SP {D[D.sp == 1].agr.median():.0%}, "
          f"DF {D[D.df == 1].agr.median():.0%}, outros {D[(D.sp == 0) & (D.df == 0)].agr.median():.0%}.", "",
          "## Correlações do erro dentro de cada região (Spearman)", "",
          "| variável | erro | toda a amostra | só SP (N=16) | só DF (N=15) |", "|---|---|---|---|---|"]
    for c, nome in (("cad_preco_gold", "preço Gold"), ("agr", "% agregador"), ("frac_indep", "fração de independentes"),
                    ("poi_F1", "escritórios a pé"), ("canib_frac_max__carro_10", "sobreposição com outra Ultra")):
        for e, en in (("e_alunos", "alunos"), ("e_ticket", "ticket")):
            cel = []
            for m in (D.index == D.index, D.sp == 1, D.df == 1):
                G = D[m]
                r, p = stats.spearmanr(pd.to_numeric(G[c], errors="coerce"), G[e], nan_policy="omit")
                cel.append(f"{r:+.2f}{'*' if p < 0.05 else ''}")
            L.append(f"| {nome} | {en} | {cel[0]} | {cel[1]} | {cel[2]} |")
    L += ["", "\\* p < 0,05 sem correção. Com N = 15–16, só correlações acima de ~0,5 passam de 5%."]
    (AQUI / "anatomia_regiao.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
