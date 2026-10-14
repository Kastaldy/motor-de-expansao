# -*- coding: utf-8 -*-
"""Fachada x residuo do M0 — amostra ampliada (protocolo_fachada.md v1.1, congelado antes de rodar). .venv, PYTHONPATH=src."""
import hashlib
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


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


_argv = sys.argv; sys.argv = [_argv[0], "2026-09-29"]
cons = mod("cons", COL / "02_consolidar.py"); sys.argv = _argv
ex = mod("ex", UNI / "uni01" / "01_exploracao.py")
X_ = lambda D, cols: np.column_stack([np.ones(len(D))] + [D[c].to_numpy(float) for c in cols])


def main():
    hashes = {p.name: sha(p) for p in [AQUI / "protocolo_fachada.md", Path(__file__), COL / "planilha_felipe_2026-09-28.xlsx",
                                       COL / "planilha_vini_2026-09-29.xlsx", UNI / "fato_unidade_mes.parquet", UNI / "dim_unidade.parquet",
                                       UNI / "uni02" / "confirmacao_por_unidade.csv", UNI / "uni03" / "curva_uni03.csv"]}
    t = cons.ler(); t = t[t.nota_fachada_1a5.notna()]
    nota = t.groupby("unidade_id").nota_fachada_1a5.mean()
    f, d = ex.carregar(); A = ex.atributos(d)
    Y25, Y26 = ex.desfechos(f, "2025-01", "2025-12"), ex.desfechos(f, "2026-01", "2026-08")
    tr = A.join(Y25, how="inner").dropna(subset=["l_fat"] + BASE + ["frac_indep"])
    y = tr.l_fat.to_numpy(float)
    b, e, h, _ = ex.ols(y, X_(tr, BASE))
    b_sem, e_sem, h_sem, _ = ex.ols(y, X_(tr, ["l_renda", "l_pop"]))
    ambos = tr.index.intersection(Y26.index)
    cal = float(np.median(Y26.loc[ambos, "l_fat"] - Y25.loc[ambos, "l_fat"]))
    t2 = pd.read_csv(UNI / "uni02" / "confirmacao_por_unidade.csv", sep=";", encoding="utf-8-sig", index_col=0)
    est = pd.read_csv(COL / "metragem_estimada_2026-09-29.csv", sep=";", encoding="utf-8-sig", index_col=0).metragem_estimada_m2.dropna()
    of = d.tam_metragem_m2.dropna(); m2 = pd.concat([of, est[~est.index.isin(of.index)]])
    cur = pd.read_csv(UNI / "uni03" / "curva_uni03.csv", sep=";", encoding="utf-8-sig").query("serie == 'faturamento'").set_index("k").p50
    fv = f[f.valido].sort_values("competencia")
    linhas = []
    for u, nt in nota.items():
        if u in tr.index:  # treino: LOO
            i = tr.index.get_loc(u); linhas.append((u, nt, float(e[i] / (1 - h[i])), "principal", "treino (LOO)")); continue
        if u in t2.index:
            linhas.append((u, nt, float(np.log1p(t2.erro_M0[u])), "principal", "teste UNI-02")); continue
        madura = u in Y25.index or u in Y26.index
        if u not in A.index or pd.isna(A.l_renda.get(u)) or pd.isna(A.l_pop.get(u)):
            continue
        if madura and u not in m2.index:  # shopping: modelo sem metragem
            yy = (Y26 if u in Y26.index else Y25).l_fat[u]
            pr = float(X_(A.loc[[u]], ["l_renda", "l_pop"]) @ b_sem) + (cal if u in Y26.index else 0.0)
            linhas.append((u, nt, float(yy - pr), "ampliada", "madura sem metragem (modelo sem m²)")); continue
        if not madura and u in m2.index:
            hh = fv[(fv.unidade_id == u) & fv.mv.between(6, 12)]
            if hh.empty:
                continue
            ult = hh.iloc[-1]
            proj = ult.faturamento / cur.get(int(ult.mv), np.nan)
            Du = A.loc[[u]].copy(); Du["l_m2"] = np.log(m2[u])
            pr = float(X_(Du, BASE) @ b) + cal
            linhas.append((u, nt, float(np.log(proj) - pr), "ampliada", f"jovem, projetada do mês {int(ult.mv)}"))
    D = pd.DataFrame(linhas, columns=["unidade", "nota", "residuo", "amostra", "origem"]).set_index("unidade")
    rng = np.random.default_rng(20261007)
    L = ["# Fachada × desempenho — amostra ampliada (v1.1)", "", f"Protocolo `protocolo_fachada.md` v1.1 (SHA-256 `{hashes['protocolo_fachada.md'][:16]}…`). Rodado uma vez.", "",
         "| amostra | N | Spearman nota × resíduo | IC 90% | inclinação | leitura |", "|---|---|---|---|---|---|"]
    rp = None
    for nome, Dx in (("principal (maduras com metragem)", D[D.amostra == "principal"]), ("ampliada (+ jovens projetadas + shopping)", D)):
        n = len(Dx); rho = stats.spearmanr(Dx.nota, Dx.residuo)[0]
        bs = [stats.spearmanr(Dx.nota.to_numpy()[i], Dx.residuo.to_numpy()[i])[0] for i in (rng.integers(0, n, n) for _ in range(2000))]
        lo, hi = np.nanquantile(bs, [0.05, 0.95]); sl = np.polyfit(Dx.nota.to_numpy(float), Dx.residuo.to_numpy(float), 1)[0]
        if rp is None:
            rp = rho
        leit = ("sinal" if lo > 0 else "contrário" if hi < 0 else "inconclusivo")
        if nome.startswith("ampliada") and leit == "sinal" and np.sign(rp) != np.sign(rho):
            leit = "inconclusivo (sinal diverge da principal)"
        L.append(f"| {nome} | {n} | {rho:+.2f} | [{lo:+.2f}; {hi:+.2f}] | {100 * (np.exp(sl) - 1):+.0f}% por ponto | **{leit}** |")
    Ds = D.drop(index=["botafogo-rj"], errors="ignore")
    rs = stats.spearmanr(Ds.nota, Ds.residuo)[0]
    L += ["", f"Descritivo (sem Botafogo, a maior exceção): Spearman {rs:+.2f}, N = {len(Ds)}.", "",
          "Média do resíduo por nota (ampliada): " + "; ".join(f"nota {k:g}: {100 * (np.exp(v.residuo.mean()) - 1):+.0f}% (n={len(v)})"
                                                         for k, v in D.assign(nr=D.nota.round()).groupby("nr")) + ".", "",
          "| unidade | origem | nota | faturou vs. previsto |", "|---|---|---|---|"]
    for u, r in D.sort_values("residuo").iterrows():
        L.append(f"| {u} | {r.origem} | {r.nota:g} | {100 * (np.exp(r.residuo) - 1):+.0f}% |")
    L += ["", "## Insumos (SHA-256)", ""] + [f"- `{k}`: `{v}`" for k, v in hashes.items()]
    (AQUI / "resultado_fachada_ampliada.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
