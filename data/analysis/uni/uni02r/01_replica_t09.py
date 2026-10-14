# -*- coding: utf-8 -*-
"""UNI-02 (reforco) — replica da hipotese do diretor (T09) na Engenharia do Corpo e na Pacer (protocolo_uni02r.md).

log alunos ~ log m2 + log renda c10 + log pop c10 + frac_indep + z(log m2)*z(frac_indep) [+ efeito fixo de rede].
Efeito = coef. da interacao / dp(log m2) = variacao da elasticidade ao m2 por 1 dp de frac_indep. IC 90% HC3.
Referencia: o mesmo modelo na Ultra com desfecho log ativos (amostra primaria do UNI-01).
"""
import glob
import hashlib
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
REPO = UNI.parents[2]
MR = REPO / "data" / "analysis" / "isocronas" / "multirede"
CEN = "carro_10min"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def atributos_multirede(arqs):
    a = pd.concat([pd.read_parquet(p) for p in arqs], ignore_index=True)
    a = a[a.cenario == CEN].drop_duplicates("ponto_id").set_index("ponto_id")
    return pd.DataFrame({"pop": a["pop"], "renda": a.renda_pc, "frac_indep": a.n_independente_agregador / a.n_academias.where(a.n_academias > 0),
                         "n_acad": a.n_academias})


def edc():
    pf = pd.read_parquet(MR / "perfil.parquet")
    e = pf[pf.marca == "engenharia_do_corpo"].set_index("ponto_id")[["unidade", "metro", "metragem", "alunos_reais"]]
    return e.join(atributos_multirede(glob.glob(str(MR / "atributos" / "metro_*.parquet")))).assign(rede="edc")


def pacer():
    r = pd.read_parquet(REPO / "data" / "staging" / "alunos_reais_por_unidade.parquet")
    r = r[r.rede == "pacer"].set_index("concorrente_id")
    a = atributos_multirede([AQUI / "insumos" / "pacer_atributos_metro_43.parquet"])
    return a.join(r[["nome_unidade", "metragem", "alunos_total"]], how="inner").rename(columns={"nome_unidade": "unidade", "alunos_total": "alunos_reais"}).assign(metro=43, rede="pacer")


def ajustar(D, fe_rede=False):
    D = D.copy()
    D["l_y"] = np.log(D.y.where(D.y > 0)); D["l_m2"] = np.log(D.m2.where(D.m2 > 0))
    D["l_renda"] = np.log(D.renda.where(D.renda > 0)); D["l_pop"] = np.log(D["pop"].where(D["pop"] > 0))
    D = D.replace([np.inf, -np.inf], np.nan).dropna(subset=["l_y", "l_m2", "l_renda", "l_pop", "frac_indep"])
    sd_m2 = D.l_m2.std(ddof=0)
    D["X"] = ((D.l_m2 - D.l_m2.mean()) / sd_m2) * ((D.frac_indep - D.frac_indep.mean()) / D.frac_indep.std(ddof=0))

    def mat(G):
        M = [np.ones(len(G)), G.l_m2, G.l_renda, G.l_pop, G.frac_indep]
        if fe_rede:
            for rr in sorted(G.rede.unique())[1:]:
                M.append((G.rede == rr).astype(float))
        M.append(G.X)
        return np.column_stack([np.asarray(m, float) for m in M])

    X, y = mat(D), D.l_y.to_numpy(float)
    XtXi = np.linalg.pinv(X.T @ X); b = XtXi @ X.T @ y; e = y - X @ b
    h = np.einsum("ij,jk,ik->i", X, XtXi, X)
    se = np.sqrt(np.diag(XtXi @ (X.T * (e / (1 - h)) ** 2) @ X @ XtXi))[-1]
    df = len(D) - X.shape[1]; tq = stats.t.ppf(0.95, df)
    betas = []
    for m in sorted(D.metro.unique()):
        G = D[D.metro != m]
        if len(G) >= 10:
            betas.append(np.linalg.lstsq(mat(G), G.l_y.to_numpy(float), rcond=None)[0][-1] / sd_m2)
    return dict(n=len(D), n_metros=D.metro.nunique(), beta=b[-1] / sd_m2, lo=(b[-1] - tq * se) / sd_m2, hi=(b[-1] + tq * se) / sd_m2,
                p=2 * stats.t.sf(abs(b[-1] / se), df), mde=(tq + stats.t.ppf(0.80, df)) * se / sd_m2,
                lomo_mesmo_sinal=sum(np.sign(x) == np.sign(b[-1]) for x in betas), lomo_n=len(betas), h_max=float(h.max()))


def classe(r):
    if r["lo"] > 0:
        return "replicou"
    if r["hi"] < 0.15:
        return "não replicou"
    return "inconclusivo"


def ultra_alunos():
    s = importlib.util.spec_from_file_location("ex", UNI / "uni01" / "01_exploracao.py"); ex = importlib.util.module_from_spec(s); s.loader.exec_module(ex)
    f, d = ex.carregar()
    Yp = ex.desfechos(f, ex.INI, ex.FIM)
    out = {}
    for y in ("l_fat", "l_ativos"):
        T = dict(id="ref", h="", y=y, x="int", mod="frac_indep", sinal=+1, tipo="int")
        r = ex.ajustar(T, Yp, ex.atributos(d))
        out[y] = dict(n=r["n"], beta=r["beta"], lo=r["ic_lo"], hi=r["ic_hi"])
    return out


def main():
    hashes = {p.name: sha(p) for p in [AQUI / "protocolo_uni02r.md", Path(__file__), MR / "perfil.parquet",
                                       AQUI / "insumos" / "pacer_atributos_metro_43.parquet", REPO / "data" / "staging" / "alunos_reais_por_unidade.parquet"]}
    E, P = edc(), pacer()
    E = E.rename(columns={"metragem": "m2", "alunos_reais": "y"})
    P = P.rename(columns={"metragem": "m2", "alunos_reais": "y"})
    cols = ["unidade", "rede", "metro", "m2", "y", "pop", "renda", "frac_indep"]
    rE = ajustar(E[cols]); rE["classe"] = classe(rE)
    rJ = ajustar(pd.concat([E[cols], P[cols]]), fe_rede=True); rJ["classe"] = classe(rJ)
    U = ultra_alunos()
    f2 = lambda v: f"{v:+.2f}"
    L = ["# UNI-02 (reforço) — réplica da hipótese do diretor em outras redes", "",
         f"Protocolo `protocolo_uni02r.md` (SHA-256 `{hashes['protocolo_uni02r.md'][:16]}…`). Rodado uma vez.", "",
         "Efeito = quanto a elasticidade de alunos (ou faturamento) ao m² aumenta por 1 desvio-padrão da fração de academias "
         "independentes na isócrona de carro 10 min. IC 90% HC3.", "",
         "| amostra | desfecho | N | cidades | efeito | IC 90% | mín. detectável | mesmo sinal ao tirar cada cidade | classe |",
         "|---|---|---|---|---|---|---|---|---|",
         f"| **Engenharia do Corpo (primária)** | alunos | {rE['n']} | {rE['n_metros']} | {f2(rE['beta'])} | [{f2(rE['lo'])}, {f2(rE['hi'])}] | "
         f"{rE['mde']:.2f} | {rE['lomo_mesmo_sinal']} de {rE['lomo_n']} | **{rE['classe']}** |",
         f"| EdC + Pacer (efeito fixo de rede) | alunos | {rJ['n']} | {rJ['n_metros']} | {f2(rJ['beta'])} | [{f2(rJ['lo'])}, {f2(rJ['hi'])}] | "
         f"{rJ['mde']:.2f} | {rJ['lomo_mesmo_sinal']} de {rJ['lomo_n']} | {rJ['classe']} |",
         f"| Ultra (referência, UNI-01) | faturamento | {U['l_fat']['n']} | – | {f2(U['l_fat']['beta'])} | [{f2(U['l_fat']['lo'])}, {f2(U['l_fat']['hi'])}] | – | – | – |",
         f"| Ultra (referência) | alunos | {U['l_ativos']['n']} | – | {f2(U['l_ativos']['beta'])} | [{f2(U['l_ativos']['lo'])}, {f2(U['l_ativos']['hi'])}] | – | – | – |", "",
         f"- O valor da Ultra (+0,34, faturamento) {'está' if rE['lo'] <= 0.34 <= rE['hi'] else 'NÃO está'} dentro do IC da Engenharia do Corpo.",
         f"- Unidades da Pacer usadas: {len(P)} (as 2 de Sertãozinho ficam fora do grafo).", "",
         "## Insumos (SHA-256)", ""] + [f"- `{k}`: `{v}`" for k, v in hashes.items()]
    (AQUI / "resultado_uni02r.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
