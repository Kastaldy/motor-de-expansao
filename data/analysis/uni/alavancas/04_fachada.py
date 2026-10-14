# -*- coding: utf-8 -*-
"""Fachada x residuo do M0 (protocolo_fachada.md, congelado antes de rodar). Rodar com PYTHONPATH=src (.venv).
Tambem registra as notas de fachada da turma de 2026 ao lado das previsoes congeladas (previsao_2026/)."""
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


def X_(D, cols):
    return np.column_stack([np.ones(len(D))] + [D[c].to_numpy(float) for c in cols])


def main():
    hashes = {p.name: sha(p) for p in [AQUI / "protocolo_fachada.md", Path(__file__), COL / "planilha_felipe_2026-09-28.xlsx",
                                       COL / "planilha_vini_2026-09-29.xlsx", UNI / "fato_unidade_mes.parquet", UNI / "dim_unidade.parquet",
                                       UNI / "uni02" / "confirmacao_por_unidade.csv"]}
    t = cons.ler()
    itens = cons.FACHADA
    t = t[t[itens + ["nota_fachada_1a5"]].notna().any(axis=1)].copy()
    sim = t[itens].eq("sim").sum(axis=1); vis = t[itens].isin(["sim", "não"]).sum(axis=1)
    t["indice"] = (sim / vis.replace(0, np.nan))
    fach = t.groupby("unidade_id").agg(nota=("nota_fachada_1a5", "mean"), indice=("indice", "mean"), n_aval=("avaliador", "nunique"))
    dup = t.groupby("unidade_id").filter(lambda g: g.avaliador.nunique() == 2).pivot_table(index="unidade_id", columns="avaliador", values="nota_fachada_1a5", aggfunc="first").dropna()

    f, d = ex.carregar()
    A = ex.atributos(d)
    Y25, Y26 = ex.desfechos(f, "2025-01", "2025-12"), ex.desfechos(f, "2026-01", "2026-08")
    tr = A.join(Y25, how="inner").dropna(subset=["l_fat"] + BASE + ["frac_indep"])
    y = tr.l_fat.to_numpy(float); X0 = X_(tr, BASE)
    b, e, h, _ = ex.ols(y, X0)
    res = pd.Series(e / (1 - h), index=tr.index, name="residuo")
    origem = pd.Series("treino (LOO)", index=tr.index)
    t2 = pd.read_csv(UNI / "uni02" / "confirmacao_por_unidade.csv", sep=";", encoding="utf-8-sig", index_col=0)
    res = pd.concat([res, np.log1p(t2.erro_M0).rename("residuo")]); origem = pd.concat([origem, pd.Series("teste UNI-02", index=t2.index)])
    # outras maduras em 2026 com metragem e isocrona
    cal = float(np.median(Y26.loc[tr.index.intersection(Y26.index), "l_fat"] - Y25.loc[tr.index.intersection(Y26.index), "l_fat"]))
    est = pd.read_csv(COL / "metragem_estimada_2026-09-29.csv", sep=";", encoding="utf-8-sig", index_col=0).metragem_estimada_m2.dropna()
    m2 = pd.concat([d.tam_metragem_m2.dropna(), est[~est.index.isin(d.tam_metragem_m2.dropna().index)]])
    outras = [u for u in fach.index if u in Y26.index and u not in res.index and u in m2.index]
    if outras:
        Do = A.drop(columns=["l_m2"]).join(np.log(m2).rename("l_m2")).loc[outras].join(Y26[["l_fat"]]).dropna(subset=BASE + ["l_fat"])
        ro = Do.l_fat - (X_(Do, BASE) @ b + cal)
        res = pd.concat([res, ro.rename("residuo")]); origem = pd.concat([origem, pd.Series("outra madura 2026", index=Do.index)])
    D = fach.join(res, how="inner").join(origem.rename("origem"))

    rng = np.random.default_rng(20261006)
    L = ["# Fachada × desempenho — resultado", "", f"Protocolo `protocolo_fachada.md` (SHA-256 `{hashes['protocolo_fachada.md'][:16]}…`). Rodado uma vez.", "",
         f"- Unidades com fachada avaliada: {len(fach)}; com resíduo do M0 fora da amostra: **{len(D)}** ({D.origem.value_counts().to_dict()}).",
         f"- Concordância entre avaliadores (nota), {len(dup)} unidades avaliadas pelos dois: " + "; ".join(f"{u} {r.iloc[0]:g}/{r.iloc[1]:g}" for u, r in dup.iterrows()) + ".", "",
         "| X | N | Spearman com o resíduo | IC 90% | inclinação | leitura |", "|---|---|---|---|---|---|"]
    for x, rot, unid in (("nota", "nota da fachada (1–5)", "por ponto"), ("indice", "índice dos 6 itens (0–1)", "de 0 a 1")):
        Dx = D.dropna(subset=[x, "residuo"])
        n = len(Dx)
        if n < 8:
            L.append(f"| {rot} | {n} | – | – | – | sem amostra |"); continue
        rho = stats.spearmanr(Dx[x], Dx.residuo)[0]
        bs = [stats.spearmanr(Dx[x].to_numpy()[i], Dx.residuo.to_numpy()[i])[0] for i in (rng.integers(0, n, n) for _ in range(2000))]
        lo, hi = np.nanquantile(bs, [0.05, 0.95])
        sl = np.polyfit(Dx[x].to_numpy(float), Dx.residuo.to_numpy(float), 1)[0]
        leit = "sinal" if lo > 0 else ("contrário" if hi < 0 else "inconclusivo")
        L.append(f"| {rot} | {n} | {rho:+.2f} | [{lo:+.2f}; {hi:+.2f}] | {100 * (np.exp(sl) - 1):+.0f}% {unid} | **{leit}** |")
    L += ["", "| unidade | origem | nota | índice | faturou vs. previsto |", "|---|---|---|---|---|"]
    for u, r in D.sort_values("residuo").iterrows():
        L.append(f"| {u} | {r.origem} | {'–' if pd.isna(r.nota) else f'{r.nota:g}'} | {'–' if pd.isna(r.indice) else f'{r.indice:.2f}'} | {100 * (np.exp(r.residuo) - 1):+.0f}% |")
    # registro das notas da turma de 2026 ao lado das previsoes congeladas
    p26 = UNI / "previsao_2026" / "previsoes_turma_2026.csv"
    prev = pd.read_csv(p26, sep=";", encoding="utf-8-sig", index_col=0)
    reg = prev[[]].join(fach[["nota", "indice"]])
    reg.to_csv(UNI / "previsao_2026" / "fachada_turma_2026.csv", sep=";", encoding="utf-8-sig")
    with open(UNI / "previsao_2026" / "REGISTRO_CONGELAMENTO.txt", "a", encoding="utf-8") as fh:
        fh.write(f"Fachada registrada em 2026-09-29 (antes de desempenho maduro): {sha(UNI / 'previsao_2026' / 'fachada_turma_2026.csv')} *previsao_2026/fachada_turma_2026.csv "
                 f"— hipotese: nota/indice de fachada maiores -> faturamento acima do previsto (Spearman com o residuo do M0).\n")
    L += ["", f"Turma de 2026: notas de fachada registradas para {int(reg.nota.notna().sum())} das {len(reg)} unidades com previsão congelada "
          "(`previsao_2026/fachada_turma_2026.csv`).", "", "## Insumos (SHA-256)", ""] + [f"- `{k}`: `{v}`" for k, v in hashes.items()]
    (AQUI / "resultado_fachada.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
