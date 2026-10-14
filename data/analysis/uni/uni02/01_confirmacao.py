# -*- coding: utf-8 -*-
"""BLK-UNI-02 — confirmacao do modelo de faturamento maduro (protocolo_uni02.md, congelado antes de rodar).

Treino: maduras de 2025 (amostra primaria do UNI-01). Teste: unidades fora do treino, maduras em jan-ago/2026, com
metragem (oficial ou satelite corrigida). Compara ATUAL (regra de densidade da viabilidade), M0, M0d e INGENUO.
Rodar com PYTHONPATH=src (usa a funcao de densidade da viabilidade em producao).
"""
import hashlib
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from motor_expansao.dimensionamento.viabilidade_ponto import faixa_alunos_por_densidade

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
COL = UNI / "coleta_metragem"


def mod(nome, p):
    s = importlib.util.spec_from_file_location(nome, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


ex = mod("ex", UNI / "uni01" / "01_exploracao.py")
cons = mod("cons", COL / "02_consolidar.py")
RNG = np.random.default_rng(20260928)
BASE = ["l_m2", "l_renda", "l_pop"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def X_(D, cols):
    return np.column_stack([np.ones(len(D))] + [D[c].to_numpy(float) for c in cols])


def ajusta_prevê(tr, te, cols):
    b = np.linalg.lstsq(X_(tr, cols), tr.l_fat.to_numpy(float), rcond=None)[0]
    return X_(te, cols) @ b


def residuos_loo(tr, cols):
    X = X_(tr, cols); y = tr.l_fat.to_numpy(float)
    XtXi = np.linalg.pinv(X.T @ X); e = y - X @ (XtXi @ X.T @ y)
    h = np.einsum("ij,jk,ik->i", X, XtXi, X)
    return e / (1 - h)


def metricas(y, p):
    err = np.exp(y - p) - 1
    rho = stats.spearmanr(p, y)[0]
    bs = []
    for _ in range(2000):
        i = RNG.integers(0, len(y), len(y))
        if len(set(i)) > 3:
            bs.append(stats.spearmanr(p[i], y[i])[0])
    return dict(erro=np.median(np.abs(err)), vies=np.median(err), rho=rho, rho_lo=np.nanquantile(bs, 0.05), rho_hi=np.nanquantile(bs, 0.95))


def rodar(A, Y25, Y26, d, fonte_ok, m2_teste, calendario=True):
    tr = A.join(Y25, how="inner").dropna(subset=["l_fat"] + BASE + ["frac_indep"])
    te = A.drop(columns=["l_m2"]).join(m2_teste.rename("l_m2")).join(Y26, how="inner")
    te = te[~te.index.isin(tr.index) & te.index.isin(fonte_ok)].dropna(subset=["l_fat"] + BASE + ["frac_indep"])
    ambos = tr.index.intersection(Y26.index)
    cal = float(np.median(Y26.loc[ambos, "l_fat"] - Y25.loc[ambos, "l_fat"])) if calendario else 0.0
    for D in (tr, te):
        D["m2xfi"] = D.l_m2 * D.frac_indep
    y = te.l_fat.to_numpy(float)
    P = {}
    P["M0"] = ajusta_prevê(tr, te, BASE) + cal
    P["M0d"] = ajusta_prevê(tr, te, BASE + ["frac_indep", "m2xfi"]) + cal
    P["INGÊNUO"] = np.full(len(te), np.median(tr.l_fat)) + cal
    base = pd.DataFrame({"metragem": np.exp(tr.l_m2), "alunos_por_m2": np.exp(tr.l_ativos) / np.exp(tr.l_m2)})
    rpa = np.median(np.exp(tr.l_ticket))
    P["ATUAL"] = np.array([np.log(faixa_alunos_por_densidade(float(np.exp(m)), base)["faixa_alunos_p50"] * rpa) for m in te.l_m2]) + cal
    M = {k: metricas(y, p) for k, p in P.items()}
    q10, q90 = np.quantile(residuos_loo(tr, BASE), [0.10, 0.90])
    M["M0"]["cobertura"] = float(np.mean((y - P["M0"] >= q10) & (y - P["M0"] <= q90)))
    fora = te.index[(te.l_m2 < tr.l_m2.min()) | (te.l_m2 > tr.l_m2.max()) | (te.l_renda < tr.l_renda.min()) | (te.l_renda > tr.l_renda.max())
                    | (te.l_pop < tr.l_pop.min()) | (te.l_pop > tr.l_pop.max())].tolist()
    return dict(n_tr=len(tr), n_te=len(te), cal=cal, M=M, P=P, te=te, fora=fora)


def main():
    hashes = {p.name: sha(p) for p in [AQUI / "protocolo_uni02.md", Path(__file__), UNI / "fato_unidade_mes.parquet", UNI / "dim_unidade.parquet",
                                       COL / "metragem_estimada.csv", COL / "planilha_felipe_2026-09-28.xlsx", COL / "planilha_vini_2026-09-28.xlsx"]}
    f, d = ex.carregar()
    A = ex.atributos(d)
    Y25 = ex.desfechos(f, "2025-01", "2025-12")
    Y26 = ex.desfechos(f, "2026-01", "2026-08")
    est = pd.read_csv(COL / "metragem_estimada.csv", sep=";", encoding="utf-8-sig", index_col=0)
    raw = cons.ler()
    raw = raw[raw.unidade_id.map(pd.read_csv(COL / "_gabarito_nao_abrir" / "gabarito_calibracao.csv", sep=";", encoding="utf-8-sig", index_col=0).tam_metragem_m2).isna()]
    sat_bruta = raw.groupby("unidade_id").estimativa_m2.mean()
    oficial = d.tam_metragem_m2.dropna()
    sat = est.metragem_estimada_m2.dropna()
    m2_princ = np.log(pd.concat([oficial, sat[~sat.index.isin(oficial.index)]]))
    m2_bruta = np.log(pd.concat([oficial, sat_bruta.dropna()[~sat_bruta.dropna().index.isin(oficial.index)]]))
    fonte = pd.concat([pd.Series("oficial", index=oficial.index), pd.Series("satélite", index=sat.index.difference(oficial.index))])
    todos = list(fonte.index)

    R = {"principal": rodar(A, Y25, Y26, d, todos, m2_princ),
         "(a) só metragem oficial": rodar(A, Y25, Y26, d, list(oficial.index), m2_princ),
         "(b) satélite sem correção": rodar(A, Y25, Y26, d, todos, m2_bruta),
         "(c) sem ajuste de calendário": rodar(A, Y25, Y26, d, todos, m2_princ, calendario=False)}
    P = R["principal"]
    m = P["M"]
    conf_m0 = bool(m["M0"]["erro"] < m["ATUAL"]["erro"] and m["M0"]["erro"] < m["INGÊNUO"]["erro"] and m["M0"]["rho_lo"] > 0)
    conf_m0d = bool(conf_m0 and m["M0d"]["erro"] < m["M0"]["erro"])

    te = P["te"]
    aceita = (d.wh_tem_agregador_cadastro.astype("boolean").fillna(False) | d.tp_tem_agregador_cadastro.astype("boolean").fillna(False)).reindex(te.index)
    tab = pd.DataFrame({"nome": d.nome.reindex(te.index), "uf": d.uf.reindex(te.index), "fonte_m2": fonte.reindex(te.index),
                        "m2": np.exp(te.l_m2).round(0), "aceita_agregador": aceita, "real": np.exp(te.l_fat).round(0),
                        "prev_M0": np.exp(P["P"]["M0"]).round(0), "erro_M0": np.exp(te.l_fat.to_numpy() - P["P"]["M0"]) - 1,
                        "prev_ATUAL": np.exp(P["P"]["ATUAL"]).round(0), "erro_ATUAL": np.exp(te.l_fat.to_numpy() - P["P"]["ATUAL"]) - 1}).sort_values("erro_M0")
    tab.to_csv(AQUI / "confirmacao_por_unidade.csv", sep=";", encoding="utf-8-sig")

    pct = lambda v: "–" if pd.isna(v) else f"{100 * v:+.0f}%"
    ab = lambda v: "–" if pd.isna(v) else f"{100 * v:.0f}%"
    L = ["# BLK-UNI-02 — confirmação do modelo de faturamento maduro", "",
         f"Protocolo `protocolo_uni02.md` (SHA-256 `{hashes['protocolo_uni02.md'][:16]}…`). Rodado uma vez.", "",
         f"- Treino: {P['n_tr']} maduras de 2025. Teste: **{P['n_te']} unidades** maduras só em 2026 "
         f"({int((tab.fonte_m2 == 'oficial').sum())} com metragem oficial, {int((tab.fonte_m2 == 'satélite').sum())} por satélite).",
         f"- Ajuste de calendário 2025→2026 (mediana nas unidades de treino): {pct(np.exp(P['cal']) - 1)}.",
         f"- Unidades de teste fora do envelope do treino (m², renda ou população): {P['fora'] or 'nenhuma'}.", "",
         "## Resultado principal", "",
         "| modelo | erro típico | viés | ordenação (Spearman) | IC 90% |", "|---|---|---|---|---|"]
    for k in ("ATUAL", "INGÊNUO", "M0", "M0d"):
        r = m[k]
        L.append(f"| {k} | {ab(r['erro'])} | {pct(r['vies'])} | {r['rho']:+.2f} | [{r['rho_lo']:+.2f}; {r['rho_hi']:+.2f}] |")
    L += ["", f"Faixa p10–p90 do M0: cobertura no teste {ab(m['M0']['cobertura'])} (esperado ≈ 80%).", "",
          f"**M0 se confirma? {'SIM' if conf_m0 else 'NÃO'}.** **Hipótese do diretor (M0d) se confirma? {'SIM' if conf_m0d else 'NÃO'}.** (critério fixado antes)", "",
          "## Sensibilidades (erro típico; ordenação)", "", "| cenário | N teste | ATUAL | INGÊNUO | M0 | M0d |", "|---|---|---|---|---|---|"]
    for nome, r in R.items():
        mm = r["M"]
        L.append(f"| {nome} | {r['n_te']} | " + " | ".join(f"{ab(mm[k]['erro'])}; ρ {mm[k]['rho']:+.2f}" for k in ("ATUAL", "INGÊNUO", "M0", "M0d")) + " |")
    L += ["", "## Por unidade de teste", "", "| unidade | UF | m² (fonte) | aceita agregador | real | previsto M0 | erro M0 | previsto ATUAL | erro ATUAL |",
          "|---|---|---|---|---|---|---|---|---|"]
    for u, r in tab.iterrows():
        L.append(f"| {r['nome']} | {r.uf} | {r.m2:,.0f} ({r.fonte_m2}) | {'sim' if r.aceita_agregador else 'NÃO'} | {r.real:,.0f} | {r.prev_M0:,.0f} | {pct(r.erro_M0)} | {r.prev_ATUAL:,.0f} | {pct(r.erro_ATUAL)} |")
    L += ["", "## Insumos (SHA-256)", ""] + [f"- `{k}`: `{v}`" for k, v in hashes.items()]
    (AQUI / "resultado_uni02.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
