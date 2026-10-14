# -*- coding: utf-8 -*-
"""EXPLORATORIO (2026-09-30, pergunta do Felipe): por que a v2 da' previsao baixa para Manaus? (1) decomposicao da
previsao contra a unidade tipica do treino; (2) renda DOMICILIAR no lugar da per capita (domiciliar = renda per capita x
moradores por domicilio da propria isocrona): desempenho LOO e no teste, e a previsao de Manaus. .venv, PYTHONPATH=src."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent


def mod(nome, p):
    s = importlib.util.spec_from_file_location(nome, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


mn = mod("mn", AQUI / "manaus_nova_cidade.py")
ex, alav, X_ = mn.ex, mn.alav, mn.X_


def main():
    f, d = ex.carregar()
    A = alav.atributos_ext(d)
    A["l_renda_dom"] = np.log(pd.to_numeric(d.iso_renda_pc__carro_10, errors="coerce") * pd.to_numeric(d.iso_pop__carro_10, errors="coerce")
                              / pd.to_numeric(d.iso_domicilios__carro_10, errors="coerce"))
    A["moradores"] = pd.to_numeric(d.iso_pop__carro_10, errors="coerce") / pd.to_numeric(d.iso_domicilios__carro_10, errors="coerce")
    mid = pd.read_csv(UNI / "alavancas" / "master_id_cadastro.csv", sep=";", dtype=str)
    A["master_id"] = d.cod_cadastro.map(mid.assign(c=mid.cod_cadastro.str.zfill(2)).set_index("c").master_id).reindex(A.index)
    Y25, Y26 = ex.desfechos(f, "2025-01", "2025-12"), ex.desfechos(f, "2026-01", "2026-08")
    tr = A.join(Y25, how="inner").dropna(subset=["l_fat", "l_m2", "l_renda", "l_pop", "frac_indep", "studios", "master_id", "l_renda_dom"])
    t2 = pd.read_csv(UNI / "uni02" / "confirmacao_por_unidade.csv", sep=";", encoding="utf-8-sig", index_col=0)
    te = A.drop(columns=["l_m2"]).join(np.log(t2.m2).rename("l_m2")).join(Y26, how="inner").loc[t2.index]
    amb = tr.index.intersection(Y26.index); cal = float(np.median(Y26.loc[amb, "l_fat"] - Y25.loc[amb, "l_fat"]))
    cont = tr.master_id.value_counts(); proprios = sorted(m for m, n in cont.items() if n >= 4 and m != "M1")
    for D in (tr, te):
        for m in proprios:
            D[f"mr_{m}"] = (D.master_id == m).astype(float)
        D["mr_outras"] = (~D.master_id.isin(["M1"] + proprios)).astype(float)
    DUM = [f"mr_{m}" for m in proprios] + ["mr_outras"]
    MOD = {"v2 (renda per capita)": ["l_m2", "l_renda", "l_pop"] + DUM + ["studios"],
           "v2 (renda domiciliar)": ["l_m2", "l_renda_dom", "l_pop"] + DUM + ["studios"]}
    # Manaus
    ctx = mn.contexto(mn.PIN["lat"], mn.PIN["lng"])
    a = mn.attrs_circulo(mn.PIN["lat"], mn.PIN["lng"], 4.97, ctx)
    man = {"l_m2": np.log(2000.0), "l_renda": np.log(a["renda_pc"]), "l_pop": np.log(a["pop"]), "l_renda_dom": np.log(a["renda_pc"] * a["pop"] / a["domicilios"]),
           "studios": 1.0, **{c: 0.0 for c in DUM}, "mr_outras": 1.0}
    mor_man = a["pop"] / a["domicilios"]
    L = ["# Por que a previsão de Manaus ficou baixa — diagnóstico (EXPLORATÓRIO)", ""]
    L += [f"- Moradores por domicílio na área de 10 min: Manaus {mor_man:.2f}; rede (mediana das isócronas) {A.moradores.median():.2f} "
          f"(min {A.moradores.min():.2f}, máx {A.moradores.max():.2f}).",
          f"- Renda per capita: Manaus R$ {a['renda_pc']:,.0f} × mediana da rede R$ {np.exp(A.l_renda.median()):,.0f} ({100 * (a['renda_pc'] / np.exp(A.l_renda.median()) - 1):+.0f}%).",
          f"- Renda domiciliar: Manaus R$ {np.exp(man['l_renda_dom']):,.0f} × mediana da rede R$ {np.exp(A.l_renda_dom.median()):,.0f} ({100 * (np.exp(man['l_renda_dom']) / np.exp(A.l_renda_dom.median()) - 1):+.0f}%).",
          f"- Correlação per capita × domiciliar nas unidades (Spearman): {stats.spearmanr(A.l_renda, A.l_renda_dom, nan_policy='omit')[0]:+.2f}.", ""]
    for nome, cols in MOD.items():
        y = tr.l_fat.to_numpy(float); X = X_(tr, cols)
        b, e, h, _ = ex.ols(y, X)
        r2 = ex.r2_loo(y, e, h)
        pte = X_(te, cols) @ b + cal
        et = np.exp(te.l_fat.to_numpy(float) - pte) - 1
        pm = float(X_(pd.DataFrame([man]), cols) @ b) + cal
        L += [f"## {nome}", "", f"R² LOO (treino) {r2:.3f}; teste: erro típico {100 * np.median(np.abs(et)):.1f}%, viés {100 * np.median(et):+.1f}%, "
              f"Spearman {stats.spearmanr(pte, te.l_fat)[0]:+.2f}. **Manaus: R$ {np.exp(pm) / 1000:,.0f} mil/mês** (~{mn.c5.alunos_de(np.exp(pm)):,.0f} alunos).", "",
              "| variável | coeficiente | Manaus | unidade típica do treino | contribuição para Manaus × típica |", "|---|---|---|---|---|"]
        tip = tr[cols].median()
        for j, c in enumerate(cols):
            xm, xt = man[c], (tr[c].mean() if c in DUM + ["studios"] else tip[c])
            contrib = b[j + 1] * (xm - xt)
            fmt = (lambda v: f"{np.exp(v):,.0f}") if c.startswith("l_") else (lambda v: f"{v:.2f}")
            L.append(f"| {c} | {b[j + 1]:+.3f} | {fmt(xm)} | {fmt(xt)} | {100 * (np.exp(contrib) - 1):+.0f}% |")
        L.append("")
    (AQUI / "resultado_manaus_diagnostico.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
