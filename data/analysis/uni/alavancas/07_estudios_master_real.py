# -*- coding: utf-8 -*-
"""Estudios x master REAL do cadastro (protocolo_estudios_master.md v1.1, congelado antes de rodar). .venv, PYTHONPATH=src.
Reusa 02_estudios_master.py (ajuste, comparar, base_teste). Congela previsoes da turma de 2026 com a master real."""
import hashlib
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
s_ = importlib.util.spec_from_file_location("em", AQUI / "02_estudios_master.py"); em = importlib.util.module_from_spec(s_); s_.loader.exec_module(em)
ex, alav = em.ex, em.alav
BASE = em.BASE
MIN_TREINO = 4


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def pct(v):
    return em.pct(v)


def main():
    hashes = {p.name: sha(p) for p in [AQUI / "protocolo_estudios_master.md", Path(__file__), AQUI / "02_estudios_master.py",
                                       AQUI / "master_id_cadastro.csv", UNI / "fato_unidade_mes.parquet", UNI / "dim_unidade.parquet"]}
    f, d = ex.carregar()
    A = em.com_master(alav.atributos_ext(d), d)  # mantem os dummies da sigla regional (v1.0) para comparar
    mid = pd.read_csv(AQUI / "master_id_cadastro.csv", sep=";", dtype=str)
    mid = mid.assign(cod_cadastro=mid.cod_cadastro.str.zfill(2)).set_index("cod_cadastro").master_id  # v1.1.1: o painel usa zfill(2)
    A["master_id"] = d.cod_cadastro.map(mid).reindex(A.index)
    A["master_imputada"] = A.master_id.isna()
    Y25, Y26 = ex.desfechos(f, "2025-01", "2025-12"), ex.desfechos(f, "2026-01", "2026-08")
    COL = UNI / "coleta_metragem"
    est = pd.read_csv(COL / "metragem_estimada.csv", sep=";", encoding="utf-8-sig", index_col=0)
    oficial, sat = d.tam_metragem_m2.dropna(), est.metragem_estimada_m2.dropna()
    m2 = np.log(pd.concat([oficial, sat[~sat.index.isin(oficial.index)]]))
    te, cal = em.base_teste(A, Y25, Y26, list(oficial.index) + list(sat.index.difference(oficial.index)), m2)
    tr = A.join(Y25, how="inner").dropna(subset=["l_fat"] + BASE + ["frac_indep", "studios"])
    # imputacao: master que predomina na regional do Growth (entre as ligadas)
    lig = A.dropna(subset=["master_id"])
    dom = lig.groupby("regional" if "regional" in lig else "master_g").master_id.agg(lambda s: s.value_counts().index[0]) if False else \
        pd.Series({g: h.master_id.value_counts().index[0] for g, h in lig.assign(reg=d.master.reindex(lig.index)).groupby("reg")})
    for D in (A, tr, te):
        faltam = D.master_id.isna()
        D.loc[faltam, "master_id"] = d.master.reindex(D.index)[faltam].map(dom)
    cont = tr.master_id.value_counts()
    proprios = sorted([m for m, n in cont.items() if n >= MIN_TREINO and m != "M1"])
    DUMR = [f"mr_{m}" for m in proprios] + ["mr_outras"]
    for D in (tr, te):
        for m in proprios:
            D[f"mr_{m}"] = (D.master_id == m).astype(float)
        D["mr_outras"] = (~D.master_id.isin(["M1"] + proprios)).astype(float)
    rng = np.random.default_rng(20261009)
    q1_sem = em.ajuste(tr, BASE + ["studios"])
    q1_com = em.ajuste(tr, BASE + DUMR + ["studios"])
    ret = q1_com["beta"] / q1_sem["beta"]
    q1 = ("estúdio sobrevive" if (alav.exclui0(q1_com["lo"], q1_com["hi"]) and ret >= 0.5) else
          "era a master" if (ret < 0.5 and q1_com["lo"] <= 0 <= q1_com["hi"]) else "não distingue")
    q2 = em.comparar(tr, te, BASE, BASE + DUMR, cal, rng)
    q3 = em.comparar(tr, te, BASE + DUMR, BASE + DUMR + ["studios"], cal, rng)
    q0 = em.comparar(tr, te, BASE, BASE + DUMR + ["studios"], cal, rng)  # a v2 candidata contra o M0
    q0_reg = em.comparar(tr, te, BASE, BASE + em.DUM + ["studios"], cal, rng)  # a mesma com a sigla regional (v1.0)
    q_e = em.comparar(tr, te, BASE, BASE + ["studios"], cal, rng)  # M0 + estudios, sem master (referencia)

    L = ["# Estúdios × master real do cadastro — resultado (v1.1)", "",
         f"Protocolo `protocolo_estudios_master.md` v1.1 (SHA-256 `{hashes['protocolo_estudios_master.md'][:16]}…`). Rodado uma vez.", "",
         f"- Treino: {len(tr)} ({int(tr.master_imputada.sum())} com master imputada pela regional); teste: {len(te)} ({int(te.master_imputada.sum())} imputadas).",
         f"- Grupos: M1 (referência, {cont.get('M1', 0)} no treino), " + ", ".join(f"{m} ({cont[m]})" for m in proprios) +
         f", outras ({int(tr.mr_outras.sum())} no treino). Masters com < {MIN_TREINO} unidades no treino vão para 'outras'.", "",
         "## Q1 — estúdios com e sem a master real (treino)", "",
         "| modelo | efeito dos estúdios | IC 90% | R² LOO | estável por metro |", "|---|---|---|---|---|",
         f"| M0 + estúdios | {pct(q1_sem['beta'])} | [{pct(q1_sem['lo'])}; {pct(q1_sem['hi'])}] | {q1_sem['r2_loo']:.3f} | {'sim' if q1_sem['lomo_ok'] else 'não'} |",
         f"| M0 + master real + estúdios | {pct(q1_com['beta'])} | [{pct(q1_com['lo'])}; {pct(q1_com['hi'])}] | {q1_com['r2_loo']:.3f} | {'sim' if q1_com['lomo_ok'] else 'não'} |",
         "", f"Retenção: {100 * ret:.0f}%. **Leitura: {q1}.**", "",
         "## Fora da amostra (18 unidades de teste)", "",
         "| comparação | versão | N | erro antes | erro depois | IC 90% da diferença | ordenação antes → depois | leitura |", "|---|---|---|---|---|---|---|---|"]
    for nome, q in (("Q2: M0 → M0 + master real", q2), ("Q3: M0 + master real → + estúdios", q3),
                    ("**v2 candidata: M0 → M0 + master real + estúdios**", q0), ("mesma, com a sigla regional (v1.0)", q0_reg),
                    ("M0 → M0 + estúdios (sem master)", q_e)):
        for v, txt in (("com", "com Botafogo"), ("sem", "sem Botafogo")):
            r = q[v]
            L.append(f"| {nome} | {txt} | {r['n']} | {100 * r['e0']:.1f}% | {100 * r['e1']:.1f}% | [{100 * r['lo']:+.1f}; {100 * r['hi']:+.1f}] p.p. | {r['r0']:+.2f} → {r['r1']:+.2f} | {q['leitura'] if v == 'sem' else ''} |")
    L += ["", "**Composição (treino / teste):** " + "; ".join(f"{g}: {int((tr.master_id == g).sum())} / {int((te.master_id == g).sum())} (com estúdio {int(tr.loc[tr.master_id == g, 'studios'].sum())} / {int(te.loc[te.master_id == g, 'studios'].sum())})" for g in sorted(tr.master_id.dropna().unique()))]
    # congelar previsoes da turma de 2026 com a master real
    p26 = UNI / "previsao_2026" / "previsoes_turma_2026.csv"
    prev = pd.read_csv(p26, sep=";", encoding="utf-8-sig", index_col=0)
    est2 = pd.read_csv(COL / "metragem_estimada_2026-09-29.csv", sep=";", encoding="utf-8-sig", index_col=0).metragem_estimada_m2.dropna()
    m2b = pd.concat([oficial, est2[~est2.index.isin(oficial.index)]])
    C = A.drop(columns=["l_m2"]).join(np.log(m2b).rename("l_m2")).reindex(prev.index)
    faltam = C.master_id.isna(); C.loc[faltam, "master_id"] = d.master.reindex(C.index)[faltam].map(dom)
    for m in proprios:
        C[f"mr_{m}"] = (C.master_id == m).astype(float)
    C["mr_outras"] = (~C.master_id.isin(["M1"] + proprios)).astype(float)
    cols = BASE + DUMR + ["studios"]
    bb = np.linalg.lstsq(em.X_(tr, cols), tr.l_fat.to_numpy(float), rcond=None)[0]
    ok = C[cols].notna().all(axis=1)
    pr = pd.Series(np.nan, index=C.index); pr[ok] = em.X_(C[ok], cols) @ bb
    out = pd.DataFrame({"master_id": C.master_id, "master_imputada": C.master_imputada, "prev_M0+MrealE_nivel2025": np.exp(pr).round(0),
                        "prev_M0+MrealE_cal2026": np.exp(pr + cal).round(0)})
    arq = UNI / "previsao_2026" / "previsoes_turma_2026_master_real.csv"
    out.to_csv(arq, sep=";", encoding="utf-8-sig")
    with open(UNI / "previsao_2026" / "REGISTRO_CONGELAMENTO.txt", "a", encoding="utf-8") as fh:
        fh.write(f"Previsoes M0 + master real (cadastro, anonimizada) + estudios — 2026-09-29, antes de qualquer conferencia: {sha(arq)} *previsao_2026/previsoes_turma_2026_master_real.csv\n")
    L += ["", f"Previsões da turma de 2026 com a master real congeladas em `previsao_2026/previsoes_turma_2026_master_real.csv` ({int(ok.sum())} de {len(out)} unidades).",
          "", "## Insumos (SHA-256)", ""] + [f"- `{k}`: `{v}`" for k, v in hashes.items()]
    (AQUI / "resultado_estudios_master_real.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
