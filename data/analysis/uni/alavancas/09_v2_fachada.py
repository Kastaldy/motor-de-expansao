# -*- coding: utf-8 -*-
"""EXPLORATORIO (2026-09-30, pedido do Felipe): a nota de fachada melhora a v2 adotada (praca + estudios + master real)?
As notas ja foram vistas; a confirmacao limpa segue sendo as notas restantes do Juan (protocolo_fachada.md v1.3).
Metodo: residuo fora da amostra da v2 (LOO no treino de 2025; teste do UNI-02 com o calendario) e, nas unidades com nota,
ajuste em 2o estagio r ~ a + b*nota com validacao LOO. Compara v2, v2 + correcao de nivel (so a) e v2 + fachada (a + b*nota).
Uso: 09_v2_fachada.py <planilha_do_juan.xlsx>. .venv, PYTHONPATH=src."""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
COL = UNI / "coleta_metragem"
BASE = ["l_m2", "l_renda", "l_pop"]


def mod(nome, p):
    s = importlib.util.spec_from_file_location(nome, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


fj = mod("fj", AQUI / "08_fachada_juan.py")
ex, cons = fj.ex, fj.cons
alav = mod("alav", AQUI / "01_alavancas.py")
X_ = lambda D, cols: np.column_stack([np.ones(len(D))] + [D[c].to_numpy(float) for c in cols])


def main():
    f, d = ex.carregar()
    A = alav.atributos_ext(d)
    mid = pd.read_csv(AQUI / "master_id_cadastro.csv", sep=";", dtype=str)
    A["master_id"] = d.cod_cadastro.map(mid.assign(c=mid.cod_cadastro.str.zfill(2)).set_index("c").master_id).reindex(A.index)
    Y25, Y26 = ex.desfechos(f, "2025-01", "2025-12"), ex.desfechos(f, "2026-01", "2026-08")
    tr = A.join(Y25, how="inner").dropna(subset=["l_fat"] + BASE + ["frac_indep", "studios", "master_id"])
    t2 = pd.read_csv(UNI / "uni02" / "confirmacao_por_unidade.csv", sep=";", encoding="utf-8-sig", index_col=0)
    te = A.drop(columns=["l_m2"]).join(np.log(t2.m2).rename("l_m2")).join(Y26, how="inner").loc[t2.index]
    amb = tr.index.intersection(Y26.index); cal = float(np.median(Y26.loc[amb, "l_fat"] - Y25.loc[amb, "l_fat"]))
    cont = tr.master_id.value_counts(); proprios = sorted(m for m, n in cont.items() if n >= 4 and m != "M1")
    for D in (tr, te):
        for m in proprios:
            D[f"mr_{m}"] = (D.master_id == m).astype(float)
        D["mr_outras"] = (~D.master_id.isin(["M1"] + proprios)).astype(float)
    V2 = BASE + [f"mr_{m}" for m in proprios] + ["mr_outras", "studios"]
    res = {}
    for nome, cols in (("M0 (praça)", BASE), ("v2 (praça + estúdios + master real)", V2)):
        y = tr.l_fat.to_numpy(float); X = X_(tr, cols)
        b, e, h, _ = ex.ols(y, X)
        r_tr = pd.Series(e / (1 - h), index=tr.index)
        r_te = te.l_fat - (X_(te, cols) @ b + cal)
        res[nome] = pd.concat([r_tr, r_te])
    # notas: Felipe/Vini (planilhas) + Juan (coluna 'Notas'); media por unidade
    t = cons.ler(); fv = t[t.nota_fachada_1a5.notna()][["unidade_id", "nota_fachada_1a5"]].rename(columns={"nota_fachada_1a5": "nota"})
    j = pd.read_excel(Path(sys.argv[1]), sheet_name="Juan"); col = "Notas" if "Notas" in j and j.Notas.notna().any() else "nota_fachada_1a5"
    jj = j[j[col].notna()][["unidade_id", col]].rename(columns={col: "nota"})
    nota = pd.concat([fv, jj]).groupby("unidade_id").nota.mean()
    rng = np.random.default_rng(20261011)
    L = ["# Fachada dentro da v2 — teste EXPLORATÓRIO (2026-09-30)", "",
         "As notas já foram vistas; não é confirmação. A confirmação limpa são as notas restantes do Juan (protocolo_fachada.md v1.3).", "",
         "Resíduo fora da amostra (treino de 2025 por LOO; teste do UNI-02 com calendário). Nas unidades com nota, a correção pela fachada "
         "é ajustada sem a própria unidade (LOO). Erro típico = mediana de |erro| no faturamento.", "",
         "| modelo base | amostra | N | erro base | + só correção de nível | + fachada | IC 90% da diferença (fachada − nível) | Spearman base → + fachada | efeito da fachada (% por ponto) |",
         "|---|---|---|---|---|---|---|---|---|"]
    for nome, r in res.items():
        for amostra, excluir in (("sem Botafogo", ["botafogo-rj"]), ("com Botafogo", [])):
            D = pd.DataFrame({"r": r, "nota": nota}).dropna().drop(index=excluir, errors="ignore")
            yhat_real = None
            n = len(D); rr = D.r.to_numpy(float); nt = D.nota.to_numpy(float)
            c_niv, c_fac = np.empty(n), np.empty(n)
            for i in range(n):
                m = np.arange(n) != i
                c_niv[i] = rr[m].mean()
                bb = np.polyfit(nt[m], rr[m], 1); c_fac[i] = bb[0] * nt[i] + bb[1]
            e0, e1, e2 = np.abs(np.exp(rr) - 1), np.abs(np.exp(rr - c_niv) - 1), np.abs(np.exp(rr - c_fac) - 1)
            dif = [np.median(e2[i]) - np.median(e1[i]) for i in (rng.integers(0, n, n) for _ in range(2000))]
            lo, hi = np.quantile(dif, [0.05, 0.95])
            # ordenacao: previsto = real - residuo
            yr = pd.concat([tr.l_fat, te.l_fat]).reindex(D.index).to_numpy(float)
            s0, s2 = stats.spearmanr(yr - rr, yr)[0], stats.spearmanr(yr - rr + c_fac, yr)[0]
            bf = np.polyfit(nt, rr, 1)[0]
            L.append(f"| {nome} | {amostra} | {n} | {100 * np.median(e0):.1f}% | {100 * np.median(e1):.1f}% | {100 * np.median(e2):.1f}% | "
                     f"[{100 * lo:+.1f}; {100 * hi:+.1f}] p.p. | {s0:+.2f} → {s2:+.2f} | {100 * (np.exp(bf) - 1):+.0f}% |")
    L += ["", f"Notas usadas: {len(nota)} unidades (Felipe, Vini e Juan; média quando há mais de uma). Juan: coluna `{col}`."]
    (AQUI / "resultado_v2_fachada.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
