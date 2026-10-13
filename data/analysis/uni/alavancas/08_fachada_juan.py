# -*- coding: utf-8 -*-
"""Fachada — confirmacao com as notas do Juan (protocolo_fachada.md v1.2). LEITURA PARCIAL enquanto a planilha nao estiver
completa. O Juan registrou a nota numa coluna propria 'Notas' (e nao em nota_fachada_1a5); usa-se 'Notas' e, se vazia,
nota_fachada_1a5. Botafogo fora (decisao do Felipe). .venv, PYTHONPATH=src.
Uso: 08_fachada_juan.py <planilha_do_juan.xlsx>"""
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


def residuos(ids):
    """Residuo fora da amostra do M0 (mesma regra do 05_fachada_ampliada): treino LOO; teste UNI-02; madura sem metragem
    pelo modelo sem m2; jovem 6-12 meses projetada pela curva do UNI-03."""
    f, d = ex.carregar(); A = ex.atributos(d)
    Y25, Y26 = ex.desfechos(f, "2025-01", "2025-12"), ex.desfechos(f, "2026-01", "2026-08")
    tr = A.join(Y25, how="inner").dropna(subset=["l_fat"] + BASE + ["frac_indep"])
    y = tr.l_fat.to_numpy(float)
    b, e, h, _ = ex.ols(y, X_(tr, BASE)); b_sem = ex.ols(y, X_(tr, ["l_renda", "l_pop"]))[0]
    amb = tr.index.intersection(Y26.index); cal = float(np.median(Y26.loc[amb, "l_fat"] - Y25.loc[amb, "l_fat"]))
    t2 = pd.read_csv(UNI / "uni02" / "confirmacao_por_unidade.csv", sep=";", encoding="utf-8-sig", index_col=0)
    est = pd.read_csv(COL / "metragem_estimada_2026-09-29.csv", sep=";", encoding="utf-8-sig", index_col=0).metragem_estimada_m2.dropna()
    of = d.tam_metragem_m2.dropna(); m2 = pd.concat([of, est[~est.index.isin(of.index)]])
    cur = pd.read_csv(UNI / "uni03" / "curva_uni03.csv", sep=";", encoding="utf-8-sig").query("serie == 'faturamento'").set_index("k").p50
    fv = f[f.valido].sort_values("competencia")
    out = {}
    for u in ids:
        if u in tr.index:
            i = tr.index.get_loc(u); out[u] = (float(e[i] / (1 - h[i])), "treino (LOO)"); continue
        if u in t2.index:
            out[u] = (float(np.log1p(t2.erro_M0[u])), "teste UNI-02"); continue
        if u not in A.index or pd.isna(A.l_renda.get(u)) or pd.isna(A.l_pop.get(u)):
            continue
        madura = u in Y25.index or u in Y26.index
        if madura and u not in m2.index:
            yy = (Y26 if u in Y26.index else Y25).l_fat[u]
            out[u] = (float(yy - (X_(A.loc[[u]], ["l_renda", "l_pop"]) @ b_sem)[0] - (cal if u in Y26.index else 0.0)), "madura sem metragem"); continue
        if madura and u in m2.index:  # madura em 2026 fora do teste do UNI-02 (ex.: metragem nova)
            Du = A.loc[[u]].copy(); Du["l_m2"] = np.log(m2[u])
            yy = (Y26 if u in Y26.index else Y25).l_fat[u]
            out[u] = (float(yy - (X_(Du, BASE) @ b)[0] - (cal if u in Y26.index else 0.0)), "madura com metragem nova"); continue
        if u in m2.index:
            hh = fv[(fv.unidade_id == u) & fv.mv.between(6, 12)]
            if hh.empty:
                continue
            ult = hh.iloc[-1]; Du = A.loc[[u]].copy(); Du["l_m2"] = np.log(m2[u])
            out[u] = (float(np.log(ult.faturamento / cur.get(int(ult.mv), np.nan)) - (X_(Du, BASE) @ b)[0] - cal), f"jovem, mês {int(ult.mv)}")
    return pd.DataFrame(out, index=["residuo", "origem"]).T.astype({"residuo": float})


def teste(D, rng):
    n = len(D)
    if n < 6:
        return n, np.nan, np.nan, np.nan, np.nan, "sem amostra"
    rho = stats.spearmanr(D.nota, D.residuo)[0]
    bs = [stats.spearmanr(D.nota.to_numpy()[i], D.residuo.to_numpy()[i])[0] for i in (rng.integers(0, n, n) for _ in range(2000))]
    lo, hi = np.nanquantile(bs, [0.05, 0.95]); sl = np.polyfit(D.nota.astype(float), D.residuo.astype(float), 1)[0]
    return n, rho, lo, hi, sl, ("confirma" if lo > 0 else "contrário" if hi < 0 else "inconclusivo")


def main():
    arq = Path(sys.argv[1])
    j = pd.read_excel(arq, sheet_name="Juan")
    col = "Notas" if "Notas" in j.columns and j["Notas"].notna().any() else "nota_fachada_1a5"
    j = j[j[col].notna()].set_index("unidade_id")
    nota_j = j[col].astype(float)
    cal_ids = set(pd.read_csv(COL / "_gabarito_nao_abrir" / "fachada_juan_calibracao.csv", sep=";", encoding="utf-8-sig").unidade_id)
    t = cons.ler(); t = t[t.nota_fachada_1a5.notna()]
    nota_fv = t.groupby("unidade_id").nota_fachada_1a5.mean()
    conc = pd.DataFrame({"juan": nota_j[nota_j.index.isin(cal_ids)], "felipe_vini": nota_fv.reindex([u for u in nota_j.index if u in cal_ids])})
    novas = nota_j[~nota_j.index.isin(cal_ids) & (nota_j.index != "botafogo-rj")]
    todas = pd.concat([nota_fv.drop(index=["botafogo-rj"], errors="ignore"), novas])
    R = residuos(sorted(set(todas.index)))
    rng = np.random.default_rng(20261010)
    Dj = pd.DataFrame({"nota": novas}).join(R, how="inner")
    Dt = pd.DataFrame({"nota": todas}).join(R, how="inner")
    L = ["# Fachada — confirmação com as notas do Juan (LEITURA PARCIAL)", "",
         f"Planilha: `{arq.name}` (SHA-256 `{sha(arq)[:16]}…`); coluna usada: `{col}`. Protocolo `protocolo_fachada.md` v1.2 "
         f"(SHA-256 `{sha(AQUI / 'protocolo_fachada.md')[:16]}…`). Botafogo fora (decisão do Felipe).", "",
         f"- Notas do Juan: {len(nota_j)} ({len(conc)} de controle; {len(novas)} unidades novas). Checklist dos 6 itens: vazio.",
         "- **Concordância nas unidades de controle** (Juan × média Felipe/Vini): " + "; ".join(f"{u} {r.juan:g} × {r.felipe_vini:g}" for u, r in conc.iterrows()) +
         f". Diferença de mais de 1 ponto em {int((conc.juan - conc.felipe_vini).abs().gt(1).sum())} de {len(conc)} (regra: 3 ou mais → réguas diferentes).", "",
         "| amostra | N | Spearman nota × faturamento acima do previsto | IC 90% | inclinação | leitura |", "|---|---|---|---|---|---|"]
    for nome, D in (("**só as unidades novas do Juan** (confirmação)", Dj), ("todas as notas (Felipe, Vini e Juan), sem Botafogo", Dt)):
        n, rho, lo, hi, sl, leit = teste(D, rng)
        L.append(f"| {nome} | {n} | {rho:+.2f} | [{lo:+.2f}; {hi:+.2f}] | {100 * (np.exp(sl) - 1):+.0f}% por ponto | **{leit}** |" if n >= 6 else f"| {nome} | {n} | – | – | – | sem amostra |")
    L += ["", "Média do faturamento acima/abaixo do previsto por nota (todas, sem Botafogo): " +
          "; ".join(f"nota {k:g}: {100 * (np.exp(v.residuo.mean()) - 1):+.0f}% (n={len(v)})" for k, v in Dt.assign(nr=Dt.nota.round()).groupby("nr")) + ".", "",
          "| unidade (Juan, novas) | origem | nota | faturou vs. previsto |", "|---|---|---|---|"]
    for u, r in Dj.sort_values("residuo").iterrows():
        L.append(f"| {u} | {r.origem} | {r.nota:g} | {100 * (np.exp(r.residuo) - 1):+.0f}% |")
    L += ["", f"Leitura parcial: {len(novas)} de 45 unidades novas avaliadas. O resultado final sai quando a planilha estiver completa."]
    (AQUI / "resultado_fachada_juan_parcial.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
