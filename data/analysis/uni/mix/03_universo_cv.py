# -*- coding: utf-8 -*-
"""BLK-UNI-05C v1.3 — universo inteiro (aceita >= 1 agregador) com validacao cruzada (protocolo_mix.md §11).
Desfecho: proporcao de agregadores nos ativos (UX). Rodar com PYTHONPATH=src (.venv do projeto).
"""
import hashlib
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
POI = UNI.parent / "poi" / "saidas"
_argv = sys.argv
sys.argv = [_argv[0], "alunos"]
s_ = importlib.util.spec_from_file_location("mx", AQUI / "01_mix.py"); mx = importlib.util.module_from_spec(s_); s_.loader.exec_module(mx)
sys.argv = _argv
ex = mx.ex
N_BOOT = 2000
BASE = ["l_renda", "l_pop", "jovem", "so_um"]
CAND = {"E1": ["escritorios"], "E2": ["escr_priv"], "E3": ["g_SP", "g_outros"], "E4": ["escr_priv", "g_SP", "g_outros"]}
NOMES = {"E1": "escritórios a pé", "E2": "escritórios privados a pé", "E3": "grupo de estado (SP / DF-GO / outros)", "E4": "escritórios privados + estado"}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def X_(D, cols):
    return np.column_stack([np.ones(len(D))] + [D[c].to_numpy(float) for c in cols])


def cv(D, cols, grupos):
    """Previsao de cada unidade por modelo ajustado sem o seu grupo (grupo = a propria unidade no LOO)."""
    p = np.full(len(D), np.nan)
    y = D.mix.to_numpy(float)
    for g in pd.unique(grupos):
        m = grupos == g
        tr = D[~m]
        b = np.linalg.lstsq(X_(tr, cols), tr.mix.to_numpy(float), rcond=None)[0]
        p[m] = X_(D[m], cols) @ b
    return y - p


def main():
    hashes = {p.name: sha(p) for p in [AQUI / "protocolo_mix.md", Path(__file__), AQUI / "01_mix.py", UNI / "uni01" / "01_exploracao.py",
                                       UNI / "fato_unidade_mes.parquet", UNI / "dim_unidade.parquet", POI / "f1_privado_ultra.parquet"]}
    f, d = ex.carregar()
    A = mx.atributos(d)
    Y = mx.desfecho(f, "2025-01", "2026-08", 6)
    g = f[f.valido & f.competencia.between("2025-01", "2026-08") & (f.mv >= 6) & f.pct_agregador_ativos.notna()]
    Y["mv_medio"] = g.groupby("unidade_id").mv.mean().reindex(Y.index)
    D = A.join(Y, how="inner")
    D = D[(D.aceita_wh + D.aceita_tp) >= 1].copy()
    D["jovem"] = (D.mv_medio < 12).astype(float)
    D["so_um"] = ((D.aceita_wh + D.aceita_tp) == 1).astype(float)
    fp = pd.read_parquet(POI / "f1_privado_ultra.parquet").set_index("ponto_id")
    D["escr_priv"] = np.log1p(fp.F1p_fil.reindex(D.index)) - np.log1p(pd.to_numeric(d.iso_pop__pe_15, errors="coerce").reindex(D.index))
    grp = np.where(D.uf == "SP", "SP", np.where(D.uf.isin(["DF", "GO"]), "DFGO", "outros"))
    D["g_SP"], D["g_outros"] = (grp == "SP").astype(float), (grp == "outros").astype(float)
    todas = sorted({c for v in CAND.values() for c in v})
    D = D.dropna(subset=["mix", "metro"] + [c for c in BASE] + todas)
    n = len(D)
    y = D.mix.to_numpy(float)
    rng = np.random.default_rng(20261005)

    linhas = []
    for base_nome, base in (("com controle 'só um'", BASE), ("sem controle 'só um'", [c for c in BASE if c != "so_um"])):
        r0 = cv(D, base, D.index.to_numpy()); m0 = cv(D, base, D.metro.to_numpy())
        for k, cols in CAND.items():
            r1 = cv(D, base + cols, D.index.to_numpy()); m1 = cv(D, base + cols, D.metro.to_numpy())
            dif = [np.abs(r1[i]).mean() - np.abs(r0[i]).mean() for i in (rng.integers(0, n, n) for _ in range(N_BOOT))]
            s0, s1 = stats.spearmanr(y - r0, y)[0], stats.spearmanr(y - r1, y)[0]
            ok = np.abs(r1).mean() < np.abs(r0).mean() and np.abs(m1).mean() < np.abs(m0).mean() and s1 >= s0
            linhas.append(dict(base=base_nome, id=k, candidata=NOMES[k], n=n, loo0=np.abs(r0).mean(), loo1=np.abs(r1).mean(),
                               lo=np.quantile(dif, 0.05), hi=np.quantile(dif, 0.95), metro0=np.abs(m0).mean(), metro1=np.abs(m1).mean(),
                               s0=s0, s1=s1, leitura="melhora a previsão" if ok else "não melhora"))
    R = pd.DataFrame(linhas)
    R.to_csv(AQUI / "universo_cv.csv", sep=";", encoding="utf-8-sig", index=False)

    # coeficientes no universo todo (com controle 'so um'); E1/E2 por 1 dp, IC agrupado por metro
    def coef(cols, alvo):
        Dz = D.copy()
        for c in cols:
            if c in ("escritorios", "escr_priv"):
                Dz[c] = (Dz[c] - Dz[c].mean()) / Dz[c].std(ddof=0)
        Xm = X_(Dz, BASE + cols); b, e, h, XtXi = ex.ols(y, Xm)
        G = Dz.metro.nunique(); meat = np.zeros((Xm.shape[1],) * 2)
        for m in Dz.metro.unique():
            k_ = (Dz.metro == m).to_numpy(); s1 = Xm[k_].T @ e[k_]; meat += np.outer(s1, s1)
        se = np.sqrt(G / (G - 1) * (n - 1) / (n - Xm.shape[1]) * np.diag(XtXi @ meat @ XtXi))
        j = 1 + (BASE + cols).index(alvo); tq = stats.t.ppf(0.95, G - 1)
        return b[j], b[j] - tq * se[j], b[j] + tq * se[j], G
    ce1, ce2 = coef(["escritorios"], "escritorios"), coef(["escr_priv"], "escr_priv")
    ce4 = {c: coef(["escr_priv", "g_SP", "g_outros"], c) for c in ("escr_priv", "g_SP", "g_outros")}
    # regra so' por estado (E3), ajustada no universo, com os controles (v1.3.1: faltava na 1a rodada)
    bE3 = np.linalg.lstsq(X_(D, BASE + ["g_SP", "g_outros"]), y, rcond=None)[0]
    ce3 = {c: coef(["g_SP", "g_outros"], c) for c in ("g_SP", "g_outros")}
    med = D.assign(grp=np.where(D.uf == "SP", "SP", np.where(D.uf.isin(["DF", "GO"]), "DFGO", "outros"))).groupby("grp").mix.agg(["size", "median"])
    # regra final E2 (sem padronizar) para a v2 + efeito pratico: p10 -> p90 de escritorios privados
    bE2 = np.linalg.lstsq(X_(D, BASE + ["escr_priv"]), y, rcond=None)[0]
    p10, p90 = D.escr_priv.quantile([0.10, 0.90])
    efeito_p10_p90 = bE2[-1] * (p90 - p10)

    pf = lambda v: f"{100 * v:+.1f} p.f."
    L = ["# BLK-UNI-05C v1.3 — universo inteiro com validação cruzada (proporção de agregadores nos ativos)", "",
         f"Protocolo `protocolo_mix.md` §11 (SHA-256 `{hashes['protocolo_mix.md'][:16]}…`). Rodado uma vez.", "",
         f"- **Universo: {n} unidades** (aceitam ≥ 1 agregador; ≥ 3 meses com mês de vida ≥ 6 em jan/25–ago/26), em {D.metro.nunique()} metrôs; "
         f"{int(D.so_um.sum())} aceitam só um; {int(D.jovem.sum())} 'jovens' (mês de vida médio < 12).",
         f"- Proporção de agregadores nos ativos: mediana {100 * D.mix.median():.0f}% (p10 {100 * D.mix.quantile(.1):.0f}%, p90 {100 * D.mix.quantile(.9):.0f}%).",
         f"- Correlação (Spearman) escritórios × escritórios privados: {stats.spearmanr(D.escritorios, D.escr_priv)[0]:+.2f}.", "",
         "## Validação cruzada", "",
         "Erro = erro médio absoluto em pontos de fração da proporção. LOO = cada unidade prevista sem ela; por metro = cada metrópole prevista sem ela.", "",
         "| controles | candidata | N | erro LOO: base → com X | IC 90% da diferença | erro por metro: base → com X | Spearman LOO | leitura |",
         "|---|---|---|---|---|---|---|---|"]
    for r in R.itertuples():
        L.append(f"| {r.base} | {r.id} {r.candidata} | {r.n} | {100 * r.loo0:.1f} → {100 * r.loo1:.1f} | [{100 * r.lo:+.1f}; {100 * r.hi:+.1f}] | "
                 f"{100 * r.metro0:.1f} → {100 * r.metro1:.1f} | {r.s0:+.2f} → {r.s1:+.2f} | {'**' + r.leitura + '**' if r.leitura == 'melhora a previsão' else r.leitura} |")
    L += ["", "## Tamanho do efeito (universo todo, com os controles; IC 90% agrupado por metro)", "",
          f"- E1 escritórios a pé: {pf(ce1[0])} por desvio-padrão [{pf(ce1[1])}; {pf(ce1[2])}] ({ce1[3]} metrôs).",
          f"- E2 escritórios privados a pé: {pf(ce2[0])} por desvio-padrão [{pf(ce2[1])}; {pf(ce2[2])}].",
          f"- E4 (escritórios privados + estado): escritórios privados {pf(ce4['escr_priv'][0])}/dp [{pf(ce4['escr_priv'][1])}; {pf(ce4['escr_priv'][2])}]; "
          f"SP contra DF/GO {pf(ce4['g_SP'][0])} [{pf(ce4['g_SP'][1])}; {pf(ce4['g_SP'][2])}]; outros contra DF/GO {pf(ce4['g_outros'][0])} "
          f"[{pf(ce4['g_outros'][1])}; {pf(ce4['g_outros'][2])}].",
          f"- **Efeito prático (E2):** de uma praça com poucos escritórios privados (p10) para uma com muitos (p90), a proporção de agregadores "
          f"prevista muda {pf(efeito_p10_p90)}.", "",
          "## Regra só por estado (E3), ajustada no universo", "",
          f"- SP contra DF/GO: {pf(ce3['g_SP'][0])} [{pf(ce3['g_SP'][1])}; {pf(ce3['g_SP'][2])}]; outros contra DF/GO: {pf(ce3['g_outros'][0])} "
          f"[{pf(ce3['g_outros'][1])}; {pf(ce3['g_outros'][2])}] (IC agrupado por metro: otimista, poucos metros por grupo).",
          "- Mediana observada (UX) por grupo: " + "; ".join(f"{k} {100 * r['median']:.0f}% (n={int(r['size'])})" for k, r in med.iterrows()) + ".",
          "- Regra: proporção = " + f"{bE3[0]:+.3f} " + " ".join(f"{v:+.3f}·{c}" for c, v in zip(BASE + ['g_SP', 'g_outros'], bE3[1:])) + ".", "",
          "## Regra ajustada no universo (E2, para a v2 avaliar)", "",
          "proporção de agregadores = " + f"{bE2[0]:+.3f} " + " ".join(f"{v:+.3f}·{c}" for c, v in zip(BASE + ['escr_priv'], bE2[1:])) +
          " (escr_priv = log(1 + escritórios privados a pé) − log(1 + população a pé); para uma unidade nova, jovem = 0 e só_um conforme a política).", "",
          "## Insumos (SHA-256)", ""] + [f"- `{k}`: `{v}`" for k, v in hashes.items()]
    (AQUI / "resultado_universo_cv.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
