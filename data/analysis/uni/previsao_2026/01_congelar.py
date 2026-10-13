# -*- coding: utf-8 -*-
"""Previsao congelada da turma de 2026 (protocolo_previsao_2026.md). Gera as previsoes (M0, M0+E, M0+ME) e a leitura
precoce pela curva do UNI-03. Nao usa a regra ATUAL. Rodar com PYTHONPATH=src.
"""
import hashlib
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
COL = UNI / "coleta_metragem"
s_ = importlib.util.spec_from_file_location("ex", UNI / "uni01" / "01_exploracao.py"); ex = importlib.util.module_from_spec(s_); s_.loader.exec_module(ex)
BASE = ["l_m2", "l_renda", "l_pop"]
DUM = ["m_ULTRA", "m_RJSP01", "m_outros"]
MODELOS = {"M0": BASE, "M0+E": BASE + ["studios"], "M0+ME": BASE + DUM + ["studios"]}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def X_(D, cols):
    return np.column_stack([np.ones(len(D))] + [D[c].to_numpy(float) for c in cols])


def main():
    arqs = [AQUI / "protocolo_previsao_2026.md", Path(__file__), UNI / "fato_unidade_mes.parquet", UNI / "dim_unidade.parquet",
            COL / "metragem_estimada.csv", COL / "metragem_estimada_2026-09-29.csv", UNI / "uni03" / "curva_uni03.csv"]
    hashes = {p.name: sha(p) for p in arqs}
    f, d = ex.carregar()
    A = ex.atributos(d)
    A["studios"] = d.cad_mod_studios.map({True: 1.0, False: 0.0}).astype(float)
    g = d.master.map(lambda m: m if m in ("DF/GO", "ULTRA", "RJ/SP 01") else "outros")
    for k, v in (("m_ULTRA", "ULTRA"), ("m_RJSP01", "RJ/SP 01"), ("m_outros", "outros")):
        A[k] = (g == v).astype(float)
    Y25, Y26 = ex.desfechos(f, "2025-01", "2025-12"), ex.desfechos(f, "2026-01", "2026-08")
    tr = A.join(Y25, how="inner").dropna(subset=["l_fat"] + BASE + ["frac_indep"])
    ambos = tr.index.intersection(Y26.index)
    cal = float(np.median(Y26.loc[ambos, "l_fat"] - Y25.loc[ambos, "l_fat"]))
    # erros fora da amostra do M0: LOO do treino + teste do UNI-02 (arquivo do UNI-02)
    X0, y0 = X_(tr, BASE), tr.l_fat.to_numpy(float)
    b, e, h, _ = ex.ols(y0, X0)
    loo = e / (1 - h)
    t2 = pd.read_csv(UNI / "uni02" / "confirmacao_por_unidade.csv", sep=";", encoding="utf-8-sig", index_col=0)
    oos = np.concatenate([loo, np.log1p(t2.erro_M0.to_numpy(float))])
    q10, q90 = np.quantile(oos, [0.10, 0.90])

    est_novo = pd.read_csv(COL / "metragem_estimada_2026-09-29.csv", sep=";", encoding="utf-8-sig", index_col=0).metragem_estimada_m2.dropna()
    oficial = d.tam_metragem_m2.dropna()
    m2 = pd.concat([oficial, est_novo[~est_novo.index.isin(oficial.index)]])
    fonte = pd.Series("oficial", index=oficial.index).reindex(m2.index).fillna("satélite")
    cand = A.drop(columns=["l_m2"]).join(np.log(m2).rename("l_m2"), how="inner")
    cand = cand[~cand.index.isin(tr.index) & ~cand.index.isin(t2.index) & ~cand.index.isin(Y26.index)].dropna(subset=BASE)
    out = pd.DataFrame(index=cand.index)
    out["nome"], out["uf"], out["inauguracao"] = d.nome.reindex(cand.index), d.uf.reindex(cand.index), d.inauguracao.reindex(cand.index)
    out["m2"], out["fonte_m2"] = np.exp(cand.l_m2).round(0), fonte.reindex(cand.index)
    out["estudios"], out["master"] = cand.studios, d.master.reindex(cand.index)
    for nome, cols in MODELOS.items():
        bb = np.linalg.lstsq(X_(tr, cols), y0, rcond=None)[0]
        ok = cand[cols].notna().all(axis=1)
        p = pd.Series(np.nan, index=cand.index)
        p[ok] = X_(cand[ok], cols) @ bb
        out[f"prev_{nome}_nivel2025"] = np.exp(p).round(0)
        out[f"prev_{nome}_cal2026"] = np.exp(p + cal).round(0)
    out["faixa_p10_M0_cal2026"] = (out["prev_M0_cal2026"] * np.exp(q10)).round(0)
    out["faixa_p90_M0_cal2026"] = (out["prev_M0_cal2026"] * np.exp(q90)).round(0)
    out = out.sort_values("inauguracao")
    out.to_csv(AQUI / "previsoes_turma_2026.csv", sep=";", encoding="utf-8-sig")
    reg = ["Previsao congelada da turma de 2026 — gerada em 2026-09-29, antes de qualquer conferencia.",
           f"{sha(AQUI / 'previsoes_turma_2026.csv')} *previsao_2026/previsoes_turma_2026.csv"] + [f"{v} *{k}" for k, v in hashes.items()]
    (AQUI / "REGISTRO_CONGELAMENTO.txt").write_text("\n".join(reg) + "\n", encoding="utf-8")

    # leitura precoce (descritiva): ultimo mes valido com mes_vida 3..12 / mediana da curva de faturamento
    cur = pd.read_csv(UNI / "uni03" / "curva_uni03.csv", sep=";", encoding="utf-8-sig")
    cur = cur[cur.serie == "faturamento"].set_index("k").p50
    L = ["# Previsão congelada da turma de 2026 — leitura precoce (descritiva)", "",
         f"Previsões congeladas em `previsoes_turma_2026.csv` ({len(out)} unidades). Calendário 2026: {100 * (np.exp(cal) - 1):+.1f}%. "
         f"Faixa provisória p10–p90 do M0: {100 * (np.exp(q10) - 1):+.0f}% a {100 * (np.exp(q90) - 1):+.0f}%.", "",
         "Projeção precoce = faturamento do último mês válido ÷ mediana da curva do UNI-03 naquele mês de vida (sinal antecipado, "
         "erro de 9–21% conforme o mês; não é a conferência).", "",
         "| unidade | UF | abertura | mês de vida | estúdio | previsto M0 | previsto M0+E | previsto M0+ME | projeção precoce | projeção ÷ M0 |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    fv = f[f.valido].sort_values("competencia")
    for u, r in out.iterrows():
        h_ = fv[(fv.unidade_id == u) & fv.mv.between(3, 12)]
        if h_.empty:
            continue
        ult = h_.iloc[-1]
        proj = ult.faturamento / cur.get(int(ult.mv), np.nan)
        fm = lambda v: "–" if pd.isna(v) else f"R$ {v:,.0f}"
        L.append(f"| {r.nome} | {r.uf} | {str(r.inauguracao)[:10]} | {int(ult.mv)} | {'sim' if r.estudios == 1 else ('não' if r.estudios == 0 else '?')} | "
                 f"{fm(r.prev_M0_cal2026)} | {fm(r['prev_M0+E_cal2026'])} | {fm(r['prev_M0+ME_cal2026'])} | {fm(proj)} | "
                 f"{'–' if pd.isna(proj) else f'{100 * (proj / r.prev_M0_cal2026 - 1):+.0f}%'} |")
    L += ["", "## Insumos (SHA-256)", ""] + [f"- `{k}`: `{v}`" for k, v in hashes.items()]
    (AQUI / "leitura_precoce.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(out[["nome", "uf", "m2", "fonte_m2", "estudios", "prev_M0_cal2026", "prev_M0+E_cal2026", "prev_M0+ME_cal2026"]].to_string())
    print("\n".join(L))


if __name__ == "__main__":
    main()
