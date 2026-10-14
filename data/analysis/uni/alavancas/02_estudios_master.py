# -*- coding: utf-8 -*-
"""BLK-UNI-05B passo 2 — estudios x master (protocolo_estudios_master.md, congelado antes de rodar). Exploratorio.
Rodar com PYTHONPATH=src.
"""
import hashlib
import importlib.util
import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent


def mod(nome, p):
    s = importlib.util.spec_from_file_location(nome, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


# A regra ATUAL (faixa_alunos_por_densidade) nao e' usada aqui; o import dela puxa pyarrow.dataset, que a politica de
# Controle de Aplicativo do Windows passou a bloquear em 2026-09-29. Stub que falha se alguem chamar.
_stub = types.ModuleType("motor_expansao.dimensionamento.viabilidade_ponto")
_stub.faixa_alunos_por_densidade = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("regra ATUAL nao usada neste passo"))
sys.modules.setdefault("motor_expansao.dimensionamento.viabilidade_ponto", _stub)
alav = mod("alav", AQUI / "01_alavancas.py")
ex, u2 = alav.ex, alav.u2
BASE = ["l_m2", "l_renda", "l_pop"]
GRUPOS = {"DF/GO": "DF/GO", "ULTRA": "ULTRA", "RJ/SP 01": "RJ/SP 01"}
DUM = ["m_ULTRA", "m_RJSP01", "m_outros"]
N_BOOT = 2000


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def pct(v):
    return "–" if pd.isna(v) else f"{100 * (np.exp(v) - 1):+.1f}%"


def com_master(A, d):
    A = A.copy()
    g = d.master.map(lambda m: GRUPOS.get(m, "outros")).reindex(A.index)
    A["master_g"] = g
    A["m_ULTRA"], A["m_RJSP01"], A["m_outros"] = [(g == k).astype(float) for k in ("ULTRA", "RJ/SP 01", "outros")]
    return A


def X_(D, cols):
    return np.column_stack([np.ones(len(D))] + [D[c].to_numpy(float) for c in cols])


def ajuste(tr, cols, alvo="studios"):
    X, y = X_(tr, cols), tr.l_fat.to_numpy(float)
    b, e, h, XtXi = ex.ols(y, X)
    se = ex.se_hc3(X, e, h, XtXi)
    j = 1 + cols.index(alvo)
    tq = stats.t.ppf(0.95, len(y) - X.shape[1])
    lomo = []
    for m in sorted(tr.metro.unique()):
        t2 = tr[tr.metro != m]
        if len(t2) > X.shape[1] + 2 and t2[alvo].std() > 0:
            lomo.append(np.linalg.lstsq(X_(t2, cols), t2.l_fat.to_numpy(float), rcond=None)[0][j])
    return dict(beta=b[j], lo=b[j] - tq * se[j], hi=b[j] + tq * se[j], r2_loo=ex.r2_loo(y, e, h), n=len(y),
                lomo_ok=bool(lomo and all(np.sign(v) == np.sign(b[j]) for v in lomo)), lomo_n=len(lomo), e_loo=e / (1 - h))


def comparar(tr, te, cols0, cols1, cal, rng):
    out = {}
    for versao, tx in (("com", te), ("sem", te[te.index != alav.BOTAFOGO])):
        y = tx.l_fat.to_numpy(float)
        p0 = u2.ajusta_prevê(tr, tx, cols0) + cal
        p1 = u2.ajusta_prevê(tr, tx, cols1) + cal
        e0, e1 = np.abs(np.exp(y - p0) - 1), np.abs(np.exp(y - p1) - 1)
        dif = [np.median(e1[i]) - np.median(e0[i]) for i in (rng.integers(0, len(y), len(y)) for _ in range(N_BOOT))]
        r0, r1 = stats.spearmanr(p0, y)[0], stats.spearmanr(p1, y)[0]
        out[versao] = dict(n=len(y), e0=np.median(e0), e1=np.median(e1), lo=np.quantile(dif, 0.05), hi=np.quantile(dif, 0.95),
                           r0=r0, r1=r1, ok=bool(np.median(e1) < np.median(e0) and r1 >= r0))
    out["leitura"] = "consistente" if out["com"]["ok"] and out["sem"]["ok"] else "não se repete"
    return out


def base_teste(A, Y25, Y26, fonte_ok, m2_teste):
    """Mesmas linhas de u2.rodar (UNI-02) para treino, teste e calendario, sem a regra ATUAL."""
    tr = A.join(Y25, how="inner").dropna(subset=["l_fat"] + BASE + ["frac_indep"])
    te = A.drop(columns=["l_m2"]).join(m2_teste.rename("l_m2")).join(Y26, how="inner")
    te = te[~te.index.isin(tr.index) & te.index.isin(fonte_ok)].dropna(subset=["l_fat"] + BASE + ["frac_indep"])
    ambos = tr.index.intersection(Y26.index)
    return te, float(np.median(Y26.loc[ambos, "l_fat"] - Y25.loc[ambos, "l_fat"]))


def main():
    hashes = {p.name: sha(p) for p in [AQUI / "protocolo_estudios_master.md", Path(__file__), AQUI / "01_alavancas.py",
                                       UNI / "fato_unidade_mes.parquet", UNI / "dim_unidade.parquet"]}
    f, d = ex.carregar()
    A = com_master(alav.atributos_ext(d), d)
    Y25 = ex.desfechos(f, "2025-01", "2025-12")
    Y26 = ex.desfechos(f, "2026-01", "2026-08")
    COL = UNI / "coleta_metragem"
    est = pd.read_csv(COL / "metragem_estimada.csv", sep=";", encoding="utf-8-sig", index_col=0)
    oficial, sat = d.tam_metragem_m2.dropna(), est.metragem_estimada_m2.dropna()
    m2 = np.log(pd.concat([oficial, sat[~sat.index.isin(oficial.index)]]))
    te, cal = base_teste(A, Y25, Y26, list(oficial.index) + list(sat.index.difference(oficial.index)), m2)
    tr = A.join(Y25, how="inner").dropna(subset=["l_fat"] + BASE + ["frac_indep", "studios"])
    te = te.dropna(subset=["studios"])

    q1_sem = ajuste(tr, BASE + ["studios"])
    q1_com = ajuste(tr, BASE + DUM + ["studios"])
    X0 = X_(tr, BASE); y = tr.l_fat.to_numpy(float)
    b0, e0, h0, _ = ex.ols(y, X0)
    tr = tr.assign(res_loo_M0=e0 / (1 - h0))
    ret = q1_com["beta"] / q1_sem["beta"] if q1_sem["beta"] != 0 else np.nan
    if alav.exclui0(q1_com["lo"], q1_com["hi"]) and ret >= 0.5:
        q1 = "estúdio sobrevive"
    elif ret < 0.5 and q1_com["lo"] <= 0 <= q1_com["hi"]:
        q1 = "era a master"
    else:
        q1 = "não distingue"
    rng = np.random.default_rng(20261002)
    q2 = comparar(tr, te, BASE, BASE + DUM, cal, rng)
    q3 = comparar(tr, te, BASE + DUM, BASE + DUM + ["studios"], cal, rng)
    # master sozinha no treino (efeitos contra DF/GO)
    Xm = X_(tr, BASE + DUM); bm, em, hm, XtXim = ex.ols(y, Xm); sem_ = ex.se_hc3(Xm, em, hm, XtXim)
    tq = stats.t.ppf(0.95, len(y) - Xm.shape[1])

    L = ["# Estúdios × master — resultado (exploratório, pós-hoc)", "",
         f"Protocolo `protocolo_estudios_master.md` (SHA-256 `{hashes['protocolo_estudios_master.md'][:16]}…`). Rodado uma vez.", "",
         "## Composição", "", "| grupo de master | treino: com estúdio / sem | teste: com estúdio / sem |", "|---|---|---|"]
    for g in ("DF/GO", "ULTRA", "RJ/SP 01", "outros"):
        a_, b_ = tr[tr.master_g == g], te[te.master_g == g]
        L.append(f"| {g} | {int(a_.studios.sum())} / {int((a_.studios == 0).sum())} | {int(b_.studios.sum())} / {int((b_.studios == 0).sum())} |")
    L += ["", "## Q1 — Estúdios com e sem a master (treino, 39 unidades)", "",
          "| modelo | efeito dos estúdios | IC 90% | R² LOO | estável ao retirar cada metro |", "|---|---|---|---|---|",
          f"| M0 + estúdios | **{pct(q1_sem['beta'])}** | [{pct(q1_sem['lo'])}; {pct(q1_sem['hi'])}] | {q1_sem['r2_loo']:.3f} | {'sim' if q1_sem['lomo_ok'] else 'não'} ({q1_sem['lomo_n']}) |",
          f"| M0 + master + estúdios | **{pct(q1_com['beta'])}** | [{pct(q1_com['lo'])}; {pct(q1_com['hi'])}] | {q1_com['r2_loo']:.3f} | {'sim' if q1_com['lomo_ok'] else 'não'} ({q1_com['lomo_n']}) |",
          "", f"Retenção do efeito com a master: {100 * ret:.0f}% (em log). **Leitura: {q1}.**", "",
          f"Master no treino (M0 + master, contra DF/GO; R² LOO do M0 {ex.r2_loo(y, e0, h0):.3f} → {ex.r2_loo(y, em, hm):.3f}): "
          + "; ".join(f"{k.replace('m_', '')} {pct(bm[4 + i])} [{pct(bm[4 + i] - tq * sem_[4 + i])}; {pct(bm[4 + i] + tq * sem_[4 + i])}]"
                      for i, k in enumerate(DUM)) + ".", "",
          "**Dentro de cada master** (mediana do erro LOO do M0; positivo = fatura acima do previsto):", "",
          "| grupo | com estúdio | sem estúdio |", "|---|---|---|"]
    for g in ("DF/GO", "ULTRA", "RJ/SP 01", "outros"):
        a_ = tr[tr.master_g == g]
        L.append(f"| {g} | {pct(a_[a_.studios == 1].res_loo_M0.median())} (n={int(a_.studios.sum())}) | "
                 f"{pct(a_[a_.studios == 0].res_loo_M0.median())} (n={int((a_.studios == 0).sum())}) |")
    L += ["", "## Q2 e Q3 — Fora da amostra (18 unidades de teste)", "",
          "| comparação | versão | N | erro antes | erro depois | diferença IC 90% | ordenação antes → depois |", "|---|---|---|---|---|---|---|"]
    for nome, q in (("Q2: M0 → M0 + master", q2), ("Q3: M0 + master → + estúdios", q3)):
        for v, txt in (("com", "com Botafogo"), ("sem", "sem Botafogo")):
            r = q[v]
            L.append(f"| {nome} | {txt} | {r['n']} | {100 * r['e0']:.1f}% | {100 * r['e1']:.1f}% | [{100 * r['lo']:+.1f}; {100 * r['hi']:+.1f}] p.p. | "
                     f"{r['r0']:+.2f} → {r['r1']:+.2f} |")
        L.append(f"| **{nome}** | **leitura** | | | | | **{q['leitura']}** |")
    L += ["", "## Insumos (SHA-256)", ""] + [f"- `{k}`: `{v}`" for k, v in hashes.items()]
    (AQUI / "resultado_estudios_master.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
