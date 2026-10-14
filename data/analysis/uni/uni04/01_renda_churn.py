# -*- coding: utf-8 -*-
"""BLK-UNI-04 parte A — renda da praca x churn: confirmacao em unidades novas e ponte com a DEC-014 (protocolo_uni04a.md v1.1).

Reusa as funcoes do UNI-01 (carregar, desfechos, atributos, montar). Renda da isocrona padronizada pela amostra exata do T17.
"""
import hashlib
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
REPO = UNI.parents[2]
s_ = importlib.util.spec_from_file_location("ex", UNI / "uni01" / "01_exploracao.py"); ex = importlib.util.module_from_spec(s_); s_.loader.exec_module(ex)
N_MIN = 12
INI26, FIM26 = "2026-01", "2026-08"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def ols(D, y, xs, alvo):
    """MQO com HC3; efeito de `alvo`, IC 90%, p e dR2 LOO contra o modelo sem `alvo` (mesmas unidades)."""
    D = D[[y] + xs].replace([np.inf, -np.inf], np.nan).dropna()
    n = len(D)
    if n < N_MIN:
        return dict(n=n)
    def fit(cols):
        X = np.column_stack([np.ones(n)] + [D[c].to_numpy(float) for c in cols]); yy = D[y].to_numpy(float)
        XtXi = np.linalg.pinv(X.T @ X); b = XtXi @ X.T @ yy; e = yy - X @ b
        h = np.einsum("ij,jk,ik->i", X, XtXi, X)
        V = XtXi @ (X.T * (e / (1 - h)) ** 2) @ X @ XtXi
        return b, np.sqrt(np.diag(V)), X.shape[1], 1 - np.sum((e / (1 - h)) ** 2) / np.sum((yy - yy.mean()) ** 2)
    b, se, k, r2 = fit(xs)
    _, _, _, r20 = fit([c for c in xs if c != alvo])
    i = xs.index(alvo) + 1
    tq = stats.t.ppf(0.95, n - k)
    return dict(n=n, beta=b[i], lo=b[i] - tq * se[i], hi=b[i] + tq * se[i], p=2 * stats.t.sf(abs(b[i] / se[i]), n - k), dr2=r2 - r20)


def idade_media(f, ini, fim):
    g = f[f.valido & (f.competencia >= ini) & (f.competencia <= fim) & (f.mv >= 12)]
    return np.log(g.groupby("unidade_id").mv.mean())


def main():
    hashes = {p.name: sha(p) for p in [AQUI / "protocolo_uni04a.md", Path(__file__), UNI / "uni01" / "01_exploracao.py",
                                       UNI / "fato_unidade_mes.parquet", UNI / "dim_unidade.parquet", REPO / "data" / "staging" / "brasil_estrutural.parquet"]}
    f, d = ex.carregar()
    A = ex.atributos(d)
    Yp = ex.desfechos(f, ex.INI, ex.FIM)
    Y26 = ex.desfechos(f, INI26, FIM26)
    # amostra exata do T17 e regua da renda
    T17 = next(t for t in ex.TESTES if t["id"] == "T17")
    D17, _, _ = ex.montar(T17, Yp, A)
    u17 = list(D17.index)
    ref = A.loc[u17, "l_renda"]
    A["renda_z"] = (A.l_renda - ref.mean()) / ref.std(ddof=0)
    br = pd.read_parquet(REPO / "data" / "staging" / "brasil_estrutural.parquet", columns=["hex_id", "renda_per_capita"]).set_index("hex_id").renda_per_capita
    A["l_renda_mun"] = np.log(d.hex_id_res7.map(br).where(lambda s: s > 0))
    A["l_idade25"] = idade_media(f, ex.INI, ex.FIM)
    A["l_idade26"] = idade_media(f, INI26, FIM26)

    R = {}
    r = ols(A.join(Yp).loc[u17], "churn", ["l_m2", "l_pop", "renda_z"], "renda_z")
    assert r["n"] == 39 and abs(r["beta"] + 1.288) < 0.02, ("T17 nao reproduz", r)
    R["T17 (UNI-01, reproduzido)"] = r
    R["ponte: T17 sem m²"] = ols(A.join(Yp).loc[u17], "churn", ["l_pop", "renda_z"], "renda_z")

    maduro25 = set(f[(f.competencia <= ex.FIM) & (f.mv >= 12)].unidade_id)
    fora = [u for u in Y26.index if u not in Yp.index]
    novas = [u for u in fora if u not in maduro25]
    ja_maduras = [u for u in fora if u in maduro25]
    Q1 = A.join(Y26).loc[novas]
    q1 = ols(Q1, "churn", ["l_pop", "l_idade26", "renda_z"], "renda_z")
    if "beta" in q1:
        q1["classe"] = "não confirmou" if q1["lo"] > -0.5 else "confirmou" if q1["hi"] < 0 else "inconclusivo"
    else:
        q1["classe"] = "sem amostra"
    R["Q1: unidades novas, com idade (DECIDE)"] = q1
    R["Q1 sem idade (sensibilidade)"] = ols(Q1, "churn", ["l_pop", "renda_z"], "renda_z")
    u2 = [u for u in u17 if u in Y26.index]
    R["Q2: unidades do T17 em 2026"] = ols(A.join(Y26).loc[u2], "churn", ["l_m2", "l_pop", "renda_z"], "renda_z")
    rho_q1 = stats.spearmanr(Q1.l_renda, Q1.l_idade26, nan_policy="omit")[0]

    # Q3 — mesma amostra para as duas rendas
    q3u = u2 + novas
    G = A.loc[q3u].join(d[["lt_eb_churn_60d", "lt_e_meses_ativos_12m_mediano"]]).join(Y26.churn)
    G = G.dropna(subset=["lt_eb_churn_60d", "lt_e_meses_ativos_12m_mediano", "l_pop", "l_idade26", "l_renda", "l_renda_mun"]).copy()
    for col in ("l_renda", "l_renda_mun"):
        G["z_" + col] = (G[col] - G[col].mean()) / G[col].std(ddof=0)
    q3 = {(y, nome): ols(G, y, ["l_pop", "l_idade26", "z_" + col], "z_" + col)
          for y in ("lt_eb_churn_60d", "lt_e_meses_ativos_12m_mediano")
          for nome, col in (("renda da isócrona", "l_renda"), ("renda municipal (M1, DEC-014)", "l_renda_mun"))}
    sp = {y: stats.spearmanr(G.churn, G[y], nan_policy="omit") for y in ("lt_eb_churn_60d", "lt_e_meses_ativos_12m_mediano")}
    n_mun = {uf: G.loc[[u for u in G.index if d.at[u, "uf"] == uf], "l_renda_mun"].nunique() for uf in ("SP", "DF")}
    n_uf = {uf: sum(d.at[u, "uf"] == uf for u in G.index) for uf in ("SP", "DF")}
    rho_q3 = stats.spearmanr(G.l_renda, G.l_idade26)[0]

    # Q4 — decomposicao, amostra fixa
    g = f[f.valido & (f.competencia >= ex.INI) & (f.competencia <= ex.FIM) & (f.mv >= 12) & f.unidade_id.isin(u17)].copy()
    g["inad"] = g.inadimplente / g.pagantes.where(g.pagantes > 0)
    g["cobr"] = g.em_cobranca / g.pagantes.where(g.pagantes > 0)
    M = A.join(Yp).join(g.groupby("unidade_id")[["inad", "cobr"]].mean()).loc[u17]
    base = ["l_m2", "l_pop"]
    med = ["l_ticket", "agr", "inad", "cobr"]
    M = M.dropna(subset=base + med + ["renda_z", "churn"])
    q4 = {"sem controle adicional": ols(M, "churn", base + ["renda_z"], "renda_z")}
    for nome, c in (("+ ticket", ["l_ticket"]), ("+ % agregador", ["agr"]), ("+ % inadimplente", ["inad"]), ("+ % em cobrança", ["cobr"]), ("+ todos", med)):
        q4[nome] = ols(M, "churn", base + c + ["renda_z"], "renda_z")
    cor = {c: stats.spearmanr(M.renda_z, M[c])[0] for c in med}
    rho_t17 = stats.spearmanr(A.loc[u17, "l_renda"], A.loc[u17, "l_idade25"], nan_policy="omit")[0]

    pp = lambda r: "–" if "beta" not in r else f"{r['beta']:+.2f} [{r['lo']:+.2f}; {r['hi']:+.2f}]"
    L = ["# BLK-UNI-04 parte A — renda da praça × churn", "",
         f"Protocolo `protocolo_uni04a.md` v1.1 (SHA-256 `{hashes['protocolo_uni04a.md'][:16]}…`). Rodado uma vez.", "",
         "Efeito = pontos percentuais de churn mensal por 1 desvio-padrão do log da renda da isócrona (régua do T17). IC 90% HC3.", "",
         "## Q1/Q2 — confirmação", "", "| amostra | N | efeito [IC 90%] | ΔR² LOO | classe |", "|---|---|---|---|---|"]
    for nome, r in R.items():
        L.append(f"| {nome} | {r.get('n')} | {pp(r)} | {r.get('dr2', np.nan):+.3f} | {r.get('classe', '')} |")
    L += ["", f"- Unidades da Q1 (amadureceram só em 2026): {len(novas)}. Maduras em 2025 que ficaram fora do UNI-01 e não entram: {ja_maduras or 'nenhuma'}.",
          f"- Correlação renda × idade: T17 {rho_t17:+.2f}; Q1 {rho_q1:+.2f}; Q3 {rho_q3:+.2f}.", "",
          "## Q3 — Lifetime: renda da isócrona × renda municipal (a da DEC-014), mesma amostra", "",
          f"N = {len(G)} (SP {n_uf['SP']}, DF {n_uf['DF']}). Valores distintos de renda municipal: SP {n_mun['SP']}, DF {n_mun['DF']}. "
          "Controles: log pop e log idade. Efeito por 1 dp da renda na própria amostra.", "",
          "| desfecho do Lifetime | renda | efeito [IC 90%] | ΔR² LOO |", "|---|---|---|---|"]
    for (y, nome), r in q3.items():
        L.append(f"| {y} | {nome} | {pp(r)} | {r.get('dr2', np.nan):+.3f} |")
    L += ["", "Concordância entre as fontes (Spearman, churn da Growth em 2026 × Lifetime, mesma amostra): "
          + "; ".join(f"{y} ρ = {sp[y][0]:+.2f}" for y in sp) + ".", "",
          f"## Q4 — decomposição (unidades do T17, 2025; amostra fixa N = {len(M)})", "",
          "| modelo | efeito da renda [IC 90%] |", "|---|---|"] + [f"| {k} | {pp(r)} |" for k, r in q4.items()]
    L += ["", "Correlação (Spearman) da renda com: " + "; ".join(f"{k} {v:+.2f}" for k, v in cor.items()) + ".",
          "Cautela: a inadimplência é em parte o próprio desfecho (cancelamento por falta de pagamento).", "",
          "## Insumos (SHA-256)", ""] + [f"- `{k}`: `{v}`" for k, v in hashes.items()]
    (AQUI / "resultado_uni04a.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
