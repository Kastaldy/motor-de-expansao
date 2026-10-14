# -*- coding: utf-8 -*-
"""BLK-UNI-05 — viabilidade v2 x atual no simulador de producao (protocolo_uni05.md, congelado antes de rodar).

So' analise: nada toca producao. Rodar com PYTHONPATH=src.
Principal: 18 unidades de teste do UNI-02. Secundaria: 39 maduras de 2025 com previsoes leave-one-out.
"""
import hashlib
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

from motor_expansao.dimensionamento.config import SIM_ALUGUEL_MES, SIM_CAPEX_DEFAULT, SIM_MENSALIDADE_BALCAO, SIM_SHARE_BALCAO
from motor_expansao.dimensionamento.simulador import Premissas, simular
from motor_expansao.dimensionamento.viabilidade_ponto import faixa_alunos_por_densidade

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
COL = UNI / "coleta_metragem"
BASE = ["l_m2", "l_renda", "l_pop"]
RAMPA_OBS = (0.64, 11)      # UNI-03: reta ajustada a curva mediana de faturamento
RAMPA_ATUAL = (500.0, 8)    # simulador hoje
HORIZ = 61                  # payback alem do horizonte de 60 meses


def mod(nome, p):
    s = importlib.util.spec_from_file_location(nome, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


ex = mod("ex", UNI / "uni01" / "01_exploracao.py")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def prem(a0, M):
    return Premissas(ticket_cheio=float(SIM_MENSALIDADE_BALCAO), share_balcao=SIM_SHARE_BALCAO, aluguel_mes=float(SIM_ALUGUEL_MES),
                     alunos_inicial=float(a0), maturacao_meses=int(M))


P_REF = prem(*RAMPA_ATUAL)
FIXO = P_REF.faturamento(0, com_anuidade=True)
R_ALUNO = P_REF.faturamento(1, com_anuidade=True) - FIXO


def alunos_de(fat):
    return max((fat - FIXO) / R_ALUNO, 1.0)


def sim(alunos, rampa):
    a0 = rampa[0] * alunos if rampa[0] <= 1 else rampa[0]
    r = simular(float(alunos), prem(a0, rampa[1]), obra=float(SIM_CAPEX_DEFAULT))
    pb = r.payback_meses if np.isfinite(r.payback_meses) else HORIZ
    return dict(payback=min(pb, HORIZ), viavel=bool(r.flag_viavel), margem=r.margem_ebitda_pct)


def X_(D, cols):
    return np.column_stack([np.ones(len(D))] + [D[c].to_numpy(float) for c in cols])


def main():
    hashes = {p.name: sha(p) for p in [AQUI / "protocolo_uni05.md", Path(__file__), UNI / "fato_unidade_mes.parquet", UNI / "dim_unidade.parquet",
                                       COL / "metragem_estimada.csv", UNI / "uni02" / "01_confirmacao.py"]}
    f, d = ex.carregar()
    A = ex.atributos(d)
    Y25, Y26 = ex.desfechos(f, "2025-01", "2025-12"), ex.desfechos(f, "2026-01", "2026-08")
    est = pd.read_csv(COL / "metragem_estimada.csv", sep=";", encoding="utf-8-sig", index_col=0).metragem_estimada_m2.dropna()
    of = d.tam_metragem_m2.dropna()
    m2 = np.log(pd.concat([of, est[~est.index.isin(of.index)]]))
    tr = A.join(Y25, how="inner").dropna(subset=["l_fat"] + BASE + ["frac_indep"])
    te = A.drop(columns=["l_m2"]).join(m2.rename("l_m2")).join(Y26, how="inner")
    te = te[~te.index.isin(tr.index)].dropna(subset=["l_fat"] + BASE + ["frac_indep"])
    ambos = tr.index.intersection(Y26.index)
    cal = float(np.median(Y26.loc[ambos, "l_fat"] - Y25.loc[ambos, "l_fat"]))
    # M0: teste (fora do tempo) e treino (LOO)
    Xtr, ytr = X_(tr, BASE), tr.l_fat.to_numpy(float)
    XtXi = np.linalg.pinv(Xtr.T @ Xtr); b = XtXi @ Xtr.T @ ytr
    e = ytr - Xtr @ b; h = np.einsum("ij,jk,ik->i", Xtr, XtXi, Xtr)
    pred_tr = ytr - e / (1 - h)
    pred_te = X_(te, BASE) @ b + cal
    err_pool = np.concatenate([ytr - pred_tr, te.l_fat.to_numpy(float) - pred_te])
    q10, q90 = np.quantile(err_pool, [0.10, 0.90])
    base_tr = pd.DataFrame({"metragem": np.exp(tr.l_m2), "alunos_por_m2": np.exp(tr.l_ativos) / np.exp(tr.l_m2)}, index=tr.index)

    linhas = []
    for grupo, D, pred in (("teste", te, pred_te), ("treino_loo", tr, pred_tr)):
        for i, u in enumerate(D.index):
            base_u = base_tr.drop(index=u, errors="ignore")
            dens = faixa_alunos_por_densidade(float(np.exp(D.at[u, "l_m2"])), base_u)["faixa_alunos_p50"]
            fat_real = float(np.exp(D.at[u, "l_fat"]))
            fat_v2 = float(np.exp(pred[i])); fat_v2p = float(np.exp(pred[i] + q10))
            al = {"REAL": alunos_de(fat_real), "ATUAL": dens, "V2": alunos_de(fat_v2), "V2 pessimista": alunos_de(fat_v2p)}
            cen = {"REAL": (al["REAL"], RAMPA_OBS), "ATUAL": (al["ATUAL"], RAMPA_ATUAL), "V2": (al["V2"], RAMPA_OBS),
                   "V2 pessimista": (al["V2 pessimista"], RAMPA_OBS), "A: demanda ATUAL + rampa obs.": (al["ATUAL"], RAMPA_OBS),
                   "B: demanda V2 + rampa 500/8": (al["V2"], RAMPA_ATUAL)}
            row = {"grupo": grupo, "unidade_id": u, "nome": d.at[u, "nome"], "uf": d.at[u, "uf"], "fat_real": fat_real,
                   "fat_ATUAL": P_REF.faturamento(dens, com_anuidade=True), "fat_V2": fat_v2, "fat_V2p10": fat_v2p,
                   "fat_V2p90": float(np.exp(pred[i] + q90))}
            for k, (alunos, rampa) in cen.items():
                s = sim(alunos, rampa)
                row[f"pb_{k}"], row[f"ok_{k}"] = s["payback"], s["viavel"]
            linhas.append(row)
    R = pd.DataFrame(linhas)
    R.round(2).to_csv(AQUI / "comparacao_por_unidade.csv", sep=";", encoding="utf-8-sig", index=False)

    CEN = ["ATUAL", "V2", "V2 pessimista", "A: demanda ATUAL + rampa obs.", "B: demanda V2 + rampa 500/8"]
    def resumo(G):
        out = {}
        for k in CEN:
            fk = {"ATUAL": "fat_ATUAL", "V2": "fat_V2", "V2 pessimista": "fat_V2p10"}.get(k)
            r = {}
            if fk:
                rz = G.fat_real / G[fk] - 1
                r["fat_erro"], r["fat_vies"] = rz.abs().median(), rz.median()
            dpb = G[f"pb_{k}"] - G["pb_REAL"]
            r["pb_erro"], r["pb_vies"] = dpb.abs().median(), dpb.median()
            r["concorda"] = (G[f"ok_{k}"] == G["ok_REAL"]).mean()
            r["aprov_indevida"] = int((G[f"ok_{k}"] & ~G["ok_REAL"]).sum())
            r["rejei_indevida"] = int((~G[f"ok_{k}"] & G["ok_REAL"]).sum())
            out[k] = r
        return out
    S = {g: resumo(R[R.grupo == g]) for g in ("teste", "treino_loo")}
    st, sa = S["teste"]["V2"], S["teste"]["ATUAL"]
    recomenda = bool(st["pb_erro"] < sa["pb_erro"] and (st["aprov_indevida"] < sa["aprov_indevida"]
                                                        or (st["aprov_indevida"] == sa["aprov_indevida"] and st["pb_erro"] < sa["pb_erro"])))
    pct = lambda v: "–" if pd.isna(v) else f"{100 * v:+.0f}%"
    ab = lambda v: "–" if pd.isna(v) else f"{100 * v:.0f}%"
    L = ["# BLK-UNI-05 — viabilidade v2 × atual (só análise)", "",
         f"Protocolo `protocolo_uni05.md` (SHA-256 `{hashes['protocolo_uni05.md'][:16]}…`). Rodado uma vez.", "",
         f"- Premissas iguais para todos: ticket R$ {SIM_MENSALIDADE_BALCAO}, balcão {SIM_SHARE_BALCAO:.0%}, aluguel R$ {SIM_ALUGUEL_MES:,}, obra R$ {SIM_CAPEX_DEFAULT:,}. "
         f"Receita por aluno no simulador (regime pleno): R$ {R_ALUNO:,.0f}.",
         f"- Faixa da V2 (erros fora da amostra juntados, N = {len(err_pool)}): p10 {pct(np.exp(q10) - 1)}, p90 {pct(np.exp(q90) - 1)} em torno da previsão.",
         f"- Payback além de 60 meses conta como {HORIZ}. REAL = simulador com o faturamento que a unidade de fato teve e a rampa observada.",
         f"- Unidades viáveis no REAL: teste {int(R[R.grupo == 'teste'].ok_REAL.sum())} de {int((R.grupo == 'teste').sum())}; "
         f"treino {int(R[R.grupo == 'treino_loo'].ok_REAL.sum())} de {int((R.grupo == 'treino_loo').sum())}.", ""]
    for g, titulo in (("teste", "Principal — 18 unidades de teste (abertas em 2025)"), ("treino_loo", "Secundária — 39 maduras de 2025 (leave-one-out)")):
        L += [f"## {titulo}", "", "| cenário | faturamento: erro / viés | payback: erro típico / viés (meses) | decisão igual ao REAL | aprovações indevidas | rejeições indevidas |",
              "|---|---|---|---|---|---|"]
        for k, r in S[g].items():
            fe = f"{ab(r['fat_erro'])} / {pct(r['fat_vies'])}" if "fat_erro" in r else "–"
            L.append(f"| {k} | {fe} | {r['pb_erro']:.0f} / {r['pb_vies']:+.0f} | {ab(r['concorda'])} | {r['aprov_indevida']} | {r['rejei_indevida']} |")
        L.append("")
    L += [f"**V2 recomendada para DEC? {'SIM' if recomenda else 'NÃO'}** (critério fixado antes, nas 18 unidades de teste).", "",
          "Viés de payback negativo = o cenário promete retorno mais rápido que o real (otimista).", "",
          "## Por unidade (teste)", "", "| unidade | UF | faturamento real | ATUAL | V2 (p10–p90) | payback REAL | ATUAL | V2 | viável REAL / ATUAL / V2 |", "|---|---|---|---|---|---|---|---|---|"]
    fm = lambda v: f"{v / 1000:,.0f} mil"
    sn = lambda b: "sim" if b else "não"
    for _, r in R[R.grupo == "teste"].sort_values("fat_real").iterrows():
        L.append(f"| {r['nome']} | {r.uf} | {fm(r.fat_real)} | {fm(r.fat_ATUAL)} | {fm(r.fat_V2)} ({fm(r.fat_V2p10)}–{fm(r.fat_V2p90)}) | "
                 f"{r.pb_REAL:.0f} | {r.pb_ATUAL:.0f} | {r.pb_V2:.0f} | {sn(r.ok_REAL)} / {sn(r.ok_ATUAL)} / {sn(r.ok_V2)} |")
    L += ["", "## Insumos (SHA-256)", ""] + [f"- `{k}`: `{v}`" for k, v in hashes.items()]
    (AQUI / "resultado_uni05.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
