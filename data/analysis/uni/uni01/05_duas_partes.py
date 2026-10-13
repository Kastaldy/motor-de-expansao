# -*- coding: utf-8 -*-
"""Modelo em duas partes (alunos x ticket) contra o modelo de uma equacao — protocolo_duas_partes.md (fixado antes).

Previsao do log faturamento = soma das previsoes das partes (log alunos + log ticket). Avaliacao fora da amostra por
LOO (formula fechada, cada parte sem a unidade) e retirando a cidade inteira (leave-one-metro-out). Mesmas unidades
em todas as variantes. O termo do diretor entra como produto cru log m2 x fracao (com os efeitos principais no modelo,
e' equivalente ao produto padronizado e nao vaza media/dp entre dobras).
"""
import hashlib
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
s_ = importlib.util.spec_from_file_location("ex", AQUI / "01_exploracao.py"); ex = importlib.util.module_from_spec(s_); s_.loader.exec_module(ex)
BASE = ["l_m2", "l_renda", "l_pop"]
DIR = ["frac_indep", "m2xfi"]
VARIANTES = {
    "M0": [("l_fat", BASE)],
    "M0d": [("l_fat", BASE + DIR)],
    "M1": [("l_ativos", BASE), ("l_ticket", ["l_renda"])],
    "M2": [("l_ativos", BASE + DIR), ("l_ticket", ["l_renda"])],
    "M3": [("l_ativos", BASE + ["agr_uf"]), ("l_ticket", ["l_renda", "agr_uf"])],
    "M4": [("l_ativos", BASE + DIR + ["agr_uf"]), ("l_ticket", ["l_renda", "agr_uf"])],
}
DESC = {"M0": "uma equação (referência atual)", "M0d": "uma equação + hipótese do diretor", "M1": "duas partes",
        "M2": "duas partes + diretor (em alunos)", "M3": "duas partes + política de agregador da UF",
        "M4": "duas partes + diretor + política de agregador da UF"}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def X_(D, cols):
    return np.column_stack([np.ones(len(D))] + [D[c].to_numpy(float) for c in cols])


def pred_loo(D, y, cols):
    X = X_(D, cols); yy = D[y].to_numpy(float)
    XtXi = np.linalg.pinv(X.T @ X); b = XtXi @ X.T @ yy; e = yy - X @ b
    h = np.einsum("ij,jk,ik->i", X, XtXi, X)
    return yy - e / (1 - h)


def pred_lomo(D, y, cols):
    out = pd.Series(np.nan, index=D.index)
    for m in D.metro.unique():
        tr, te = D[D.metro != m], D[D.metro == m]
        b = np.linalg.lstsq(X_(tr, cols), tr[y].to_numpy(float), rcond=None)[0]
        out[te.index] = X_(te, cols) @ b
    return out.to_numpy()


def main():
    hashes = {p.name: sha(p) for p in [AQUI / "protocolo_duas_partes.md", Path(__file__), AQUI.parent / "fato_unidade_mes.parquet", AQUI.parent / "dim_unidade.parquet"]}
    f, d = ex.carregar()
    A = ex.atributos(d)
    Y = ex.desfechos(f, ex.INI, ex.FIM)
    g6 = f[f.valido & (f.competencia <= ex.FIM) & (f.mv >= 6)]
    ult = g6.sort_values("competencia").groupby("unidade_id").tail(6).groupby("unidade_id").agr.mean()
    ufu = d.uf.reindex(ult.index)
    D = A.join(Y, how="inner")
    D["agr_uf"] = [ult[(ufu == d.at[u, "uf"]) & (ult.index != u)].median() for u in D.index]
    D["m2xfi"] = D.l_m2 * D.frac_indep
    cols = ["l_fat", "l_ativos", "l_ticket", "metro"] + BASE + DIR + ["agr_uf"]
    fora = D.index[D[cols].isna().any(axis=1)].tolist()
    D = D.dropna(subset=cols)
    yf = D.l_fat.to_numpy(float)
    sst = np.sum((yf - yf.mean()) ** 2)
    R = []
    for k, partes in VARIANTES.items():
        pl = sum(pred_loo(D, y, c) for y, c in partes)
        pm = sum(pred_lomo(D, y, c) for y, c in partes)
        R.append(dict(id=k, desc=DESC[k], r2_loo=1 - np.sum((yf - pl) ** 2) / sst, r2_lomo=1 - np.sum((yf - pm) ** 2) / sst,
                      erro_loo=np.median(np.abs(np.exp(yf - pl) - 1)), erro_lomo=np.median(np.abs(np.exp(yf - pm) - 1))))
    R = pd.DataFrame(R).set_index("id")
    r0 = R.loc["M0"]
    R["supera_M0"] = (R.r2_loo - r0.r2_loo >= 0.02) & (R.r2_lomo - r0.r2_lomo >= 0.02)
    R.loc["M0", "supera_M0"] = False
    venc = [k for k in ("M0d", "M1", "M2", "M3", "M4") if R.at[k, "supera_M0"]]
    R.round(4).to_csv(AQUI / "resultado_duas_partes.csv", sep=";", encoding="utf-8-sig")
    L = ["# Modelo em duas partes (alunos × ticket) — resultado", "",
         f"Protocolo `protocolo_duas_partes.md` (SHA-256 `{hashes['protocolo_duas_partes.md'][:16]}…`). N = {len(D)} unidades maduras de 2025, "
         f"as mesmas em todas as variantes (fora por falta de variável: {fora or 'nenhuma'}).", "",
         "| variante | descrição | R² fora da amostra (LOO) | R² retirando a cidade | erro típico (LOO) | erro típico (sem a cidade) | supera o M0? |",
         "|---|---|---|---|---|---|---|"]
    for k, r in R.iterrows():
        L.append(f"| {k} | {r.desc} | {r.r2_loo:.3f} | {r.r2_lomo:.3f} | {r.erro_loo:.0%} | {r.erro_lomo:.0%} | {'sim' if r.supera_M0 else 'não'} |")
    L += ["", "Regra (fixada antes): supera o M0 só com +0,02 de R² nas duas avaliações; entre as que superam, vale a mais simples.", "",
          f"**Decisão:** {('a variante ' + venc[0] + ' (' + DESC[venc[0]] + ') vira a estrutura candidata do UNI-02') if venc else 'nenhuma variante supera o M0; ele segue como estrutura do UNI-02 e as duas partes ficam como ferramenta de explicação do erro'}.", "",
          "## Insumos (SHA-256)", ""] + [f"- `{k}`: `{v}`" for k, v in hashes.items()]
    (AQUI / "resultado_duas_partes.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
