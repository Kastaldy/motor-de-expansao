# -*- coding: utf-8 -*-
"""BLK-UNI-05C v1.2 — confirmacao ampliada da proporcao de agregadores nos ativos (protocolo_mix.md §10).
Reusa 01_mix.py com o desfecho "alunos". Rodar com PYTHONPATH=src.
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
_argv = sys.argv
sys.argv = [_argv[0], "alunos"]  # 01_mix le o desfecho no import
s_ = importlib.util.spec_from_file_location("mx", AQUI / "01_mix.py"); mx = importlib.util.module_from_spec(s_); s_.loader.exec_module(mx)
sys.argv = _argv
ex = mx.ex
CANDIDATAS = {"X2", "X3", "X5", "X6"}
N_BOOT = 2000


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def conf_ampliada(Dexp, Dconf, x, rng):
    ctrl = [c for c in mx.CTRL if c != x]
    tr, te = Dexp[["mix", x] + ctrl].dropna(), Dconf[["mix", x] + ctrl].dropna()
    if len(te) < 5:
        return dict(n=len(te), leitura="sem amostra")
    X_ = lambda D, cols: np.column_stack([np.ones(len(D))] + [D[c].to_numpy(float) for c in cols])
    p0 = X_(te, ctrl) @ np.linalg.lstsq(X_(tr, ctrl), tr.mix.to_numpy(float), rcond=None)[0]
    p1 = X_(te, ctrl + [x]) @ np.linalg.lstsq(X_(tr, ctrl + [x]), tr.mix.to_numpy(float), rcond=None)[0]
    y = te.mix.to_numpy(float)
    r0, r1 = y - p0, y - p1
    aj = lambda r, i: np.abs(r[i] - r[i].mean()).mean()  # erro com o intercepto reajustado na (re)amostra
    idx = np.arange(len(y))
    dif = [aj(r1, i) - aj(r0, i) for i in (rng.integers(0, len(y), len(y)) for _ in range(N_BOOT))]
    lo, hi = np.quantile(dif, [0.05, 0.95])
    s0, s1 = stats.spearmanr(p0, y)[0], stats.spearmanr(p1, y)[0]
    e0, e1 = aj(r0, idx), aj(r1, idx)
    ok = e1 < e0 and s1 >= s0 and hi < 0
    return dict(n=len(y), aj0=e0, aj1=e1, lo=lo, hi=hi, bruto0=np.abs(r0).mean(), bruto1=np.abs(r1).mean(), nivel=r0.mean(),
                s0=s0, s1=s1, leitura="consistente" if ok else "não se repete")


def main():
    hashes = {p.name: sha(p) for p in [AQUI / "protocolo_mix.md", Path(__file__), AQUI / "01_mix.py", UNI / "uni01" / "01_exploracao.py",
                                       UNI / "fato_unidade_mes.parquet", UNI / "dim_unidade.parquet", UNI / "LOCAL_demanda_totalpass_por_unidade.parquet"]}
    f, d = ex.carregar()
    A = mx.atributos(d)
    Yexp = mx.desfecho(f, "2025-01", "2025-12", 12)
    Dexp = mx.amostra(A, Yexp)
    mv_dez = f[f.competencia == "2025-12"].set_index("unidade_id").mv
    amostras = {}
    for mvmin in (6, 9, 12):
        Yc = mx.desfecho(f, "2026-01", "2026-08", mvmin)
        nova = mv_dez.reindex(Yc.index).fillna(0) < 12
        Yc = Yc[nova & ~Yc.index.isin(Yexp.index)]
        amostras[mvmin] = mx.amostra(A, Yc)
    rng = np.random.default_rng(20261004)
    linhas = []
    for tid, x, nome, _, natureza in mx.TESTES:
        for mvmin in (6, 9, 12):
            c = conf_ampliada(Dexp, amostras[mvmin], x, rng)
            linhas.append(dict(teste=tid, x=nome, natureza=natureza, candidata=tid in CANDIDATAS, mv_min=mvmin, **c))
    R = pd.DataFrame(linhas)
    R.to_csv(AQUI / "confirmacao_ampliada.csv", sep=";", encoding="utf-8-sig", index=False)
    D6 = amostras[6]
    idade = f[f.valido & f.competencia.between("2026-01", "2026-08") & f.unidade_id.isin(D6.index) & (f.mv >= 6)].groupby("unidade_id").mv.median()

    L = ["# BLK-UNI-05C v1.2 — confirmação ampliada (proporção de agregadores nos ativos)", "",
         f"Protocolo `protocolo_mix.md` §10 (SHA-256 `{hashes['protocolo_mix.md'][:16]}…`). Rodado uma vez.", "",
         f"- Exploração (2025): {len(Dexp)} unidades (as mesmas da v1.1).",
         f"- Confirmação ampliada (`mes_vida` ≥ 6): **{len(D6)} unidades** (≥ 9: {len(amostras[9])}; ≥ 12, a da v1.1: {len(amostras[12])}); "
         f"mês de vida mediano nos meses usados: {idade.median():.0f} (de {idade.min():.0f} a {idade.max():.0f}).",
         f"- Proporção observada na confirmação ampliada: mediana {100 * D6.mix.median():.0f}% (exploração: {100 * Dexp.mix.median():.0f}%).", "",
         "Erro = erro médio absoluto em pontos de fração; \"reajustado\" = com o intercepto reajustado na amostra (tira o nível mais baixo das unidades jovens). "
         "Consistente = erro reajustado cai, Spearman não piora e IC 90% da diferença < 0.", "",
         "| teste | X | natureza | amostra | N | erro reajustado: só controles → com X | IC 90% da diferença | erro bruto | Spearman | leitura |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for r in R.itertuples():
        amo = {6: "mês ≥ 6 (principal)", 9: "mês ≥ 9", 12: "mês ≥ 12 (v1.1)"}[r.mv_min]
        cand = " (candidata)" if r.candidata else ""
        if pd.isna(getattr(r, "aj0", np.nan)):
            L.append(f"| {r.teste} | {r.x}{cand} | {r.natureza} | {amo} | {r.n} | – | – | – | – | {r.leitura} |")
            continue
        L.append(f"| {r.teste} | {r.x}{cand} | {r.natureza} | {amo} | {r.n} | {100 * r.aj0:.1f} → {100 * r.aj1:.1f} | "
                 f"[{100 * r.lo:+.1f}; {100 * r.hi:+.1f}] | {100 * r.bruto0:.1f} → {100 * r.bruto1:.1f} | {r.s0:+.2f} → {r.s1:+.2f} | "
                 f"{'**' + r.leitura + '**' if r.leitura == 'consistente' else r.leitura} |")
    L += ["", "## Insumos (SHA-256)", ""] + [f"- `{k}`: `{v}`" for k, v in hashes.items()]
    (AQUI / "resultado_confirmacao_ampliada.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
