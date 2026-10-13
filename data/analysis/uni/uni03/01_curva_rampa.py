# -*- coding: utf-8 -*-
"""BLK-UNI-03 — curva de rampa observada (protocolo_uni03.md v1.1, congelado antes de rodar).

Le o fato e o dim do painel UNI-00 e usa a funcao de densidade da viabilidade em producao
(dimensionamento.viabilidade_ponto.faixa_alunos_por_densidade; rodar com PYTHONPATH=src).
Monta a curva na EXPLORACAO (inauguracao + 13 meses <= dez/2025), compara com a rampa do simulador (padrao, so' balcao
e linear recalibrada) na CONFIRMACAO (1o ano fecha em 2026) e mede o erro da projecao do nivel maduro no mes 1, 3 e 6.
Saidas em data/analysis/uni/uni03/ (gitignored).
"""
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from motor_expansao.dimensionamento.viabilidade_ponto import faixa_alunos_por_densidade

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
FIM_EXP = "2025-12"
SERIES = ["ativos", "pagantes", "agregadores", "faturamento"]
ROTULO = {"ativos": "alunos (total)", "pagantes": "balcão", "agregadores": "agregador", "faturamento": "faturamento"}
SIM_A0, SIM_MATURACAO, SIM_SHARE_BALCAO = 500.0, 8, 0.69  # dimensionamento/config.py (E9, E13, SIM_SHARE_BALCAO)
BRACOS = ["curva", "sim_padrao", "sim_balcao", "linear_recal", "sim_padrao_sem_f0"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def carregar():
    f = pd.read_parquet(UNI / "fato_unidade_mes.parquet")
    d = pd.read_parquet(UNI / "dim_unidade.parquet")
    d = d[~d.excluida_rede].set_index("unidade_id")
    f = f[f.unidade_id.isin(d.index) & ~f.flag_inauguracao_placeholder.astype(bool) & f.mes_vida.notna()].copy()
    f = f[f.inauguracao_competencia >= "2022-04"]
    f["k"] = f.mes_vida.astype(int)
    ok = f.mes_completo.astype(bool)
    for s in ("ativos", "pagantes", "agregadores"):
        f[s + "_v"] = f[s].where(ok).astype(float)
    f["faturamento_v"] = f.faturamento.where(f.operacao_mes_cheio.astype(bool) & (f.faturamento > 0))
    ina = f.groupby("unidade_id").inauguracao.first()
    f0 = (ina.dt.days_in_month - ina.dt.day + 1) / ina.dt.days_in_month
    info = pd.DataFrame({"ina_comp": f.groupby("unidade_id").inauguracao_competencia.first(), "f0": f0,
                         "ult_k": f.groupby("unidade_id").k.max(), "encerrada": f.groupby("unidade_id").serie_encerrada.first().astype(bool)})
    return f, d, info


def painel(f, unidades):
    P, L = {}, {}
    for s in SERIES:
        p = f.pivot_table(index="unidade_id", columns="k", values=s + "_v", aggfunc="first")
        p = p.reindex(index=unidades, columns=range(0, 25))
        P[s] = p
        lv = p[[11, 12, 13]]
        L[s] = lv.mean(axis=1).where(lv.notna().sum(axis=1) >= 2)
    L = pd.DataFrame(L)
    lv24 = P["ativos"][[22, 23, 24]]
    L["ativos_24"] = lv24.mean(axis=1).where(lv24.notna().sum(axis=1) >= 2)
    return P, L


def razoes(P, L, unidades, s, ks):
    return P[s].reindex(unidades)[list(ks)].div(L[s].reindex(unidades), axis=0)


def curva(P, L, unidades, s, ks=range(0, 13)):
    r = razoes(P, L, unidades, s, ks)
    return pd.DataFrame({"n": r.notna().sum(), "p10": r.quantile(0.10), "p50": r.median(), "p90": r.quantile(0.90)})


def reta(a0f, M, t):
    return a0f + (1 - a0f) * np.minimum(t / M, 1.0)


def recalibrar(P, L, exp_, info):
    r = razoes(P, L, exp_, "ativos", range(1, 11))
    t = np.add.outer(info.f0.reindex(exp_).to_numpy(), np.arange(1, 11))
    R = r.to_numpy()
    m = np.isfinite(R)
    melhor = (np.inf, None, None)
    for a0f in np.round(np.arange(0, 1.0001, 0.01), 2):
        for M in range(1, 13):
            err = np.abs(reta(a0f, M, t[m]) / R[m] - 1).mean()
            if err < melhor[0]:
                melhor = (err, a0f, M)
    return melhor


def previsoes(u, k, L_at, f0, c_at, cal):
    t = k + f0
    a0 = min(SIM_A0, L_at)
    b_mat = SIM_SHARE_BALCAO * L_at
    b0 = min(SIM_A0, b_mat)
    return {"curva": c_at.at[k, "p50"] * L_at,
            "sim_padrao": a0 + (L_at - a0) * min(t / SIM_MATURACAO, 1.0),
            "sim_balcao": b0 + (b_mat - b0) * min(t / SIM_MATURACAO, 1.0) + (1 - SIM_SHARE_BALCAO) * L_at,
            "linear_recal": L_at * reta(cal[1], cal[2], t),
            "sim_padrao_sem_f0": a0 + (L_at - a0) * min(k / SIM_MATURACAO, 1.0)}


def teste_p2(P, L, conf, info, C, cal):
    rows = []
    for u in conf:
        L_at = L.at[u, "ativos"]
        for s in ("ativos", "faturamento"):
            Ls = L.at[u, s]
            if not np.isfinite(Ls):
                continue
            ks = [k for k in range(1, 13) if np.isfinite(P[s].at[u, k])]
            if len(ks) < 6:
                continue
            real = np.array([P[s].at[u, k] for k in ks])
            o = {"unidade_id": u, "serie": s, "meses": len(ks)}
            for b in BRACOS:
                if s == "ativos":
                    pred = np.array([previsoes(u, k, L_at, info.at[u, "f0"], C["ativos"], cal)[b] for k in ks])
                elif b == "curva":
                    pred = np.array([C["faturamento"].at[k, "p50"] * Ls for k in ks])
                else:  # rampa de alunos aplicada ao faturamento (proporcional; sem anuidade)
                    pred = np.array([previsoes(u, k, L_at, info.at[u, "f0"], C["ativos"], cal)[b] / L_at * Ls for k in ks])
                ape = np.abs(pred / real - 1)
                a110 = [e for k, e in zip(ks, ape) if k <= 10]
                o[f"a_{b}"] = np.mean(a110) if a110 else np.nan
                o[f"b_{b}"] = pred.sum() / real.sum() - 1
            rows.append(o)
    return pd.DataFrame(rows)


def main():
    import sys
    hashes = {p.name: sha(p) for p in [AQUI / "protocolo_uni03.md", Path(__file__), UNI / "fato_unidade_mes.parquet", UNI / "dim_unidade.parquet"]}
    f, d, info = carregar()
    P, L = painel(f, sorted(info.index))
    com_L = L.index[L.ativos.notna()]
    lim = pd.Period(FIM_EXP, "M")
    exp_ = [u for u in com_L if pd.Period(info.at[u, "ina_comp"], "M") + 13 <= lim]
    conf = [u for u in com_L if u not in exp_]
    n_enc = int((info.encerrada & (info.ult_k < 13)).sum())

    C = {s: curva(P, L, exp_, s) for s in SERIES}
    pd.concat({s: C[s] for s in SERIES}, names=["serie", "k"]).reset_index().to_csv(AQUI / "curva_uni03.csv", sep=";", encoding="utf-8-sig", index=False)
    cal = recalibrar(P, L, exp_, info)

    # P2
    T = teste_p2(P, L, conf, info, C, cal)
    T.to_csv(AQUI / "confirmacao_uni03.csv", sep=";", encoding="utf-8-sig", index=False)
    resumo = {}
    for s in ("ativos", "faturamento"):
        t = T[T.serie == s]
        resumo[s] = {b: dict(a=t[f"a_{b}"].median(), absb=t[f"b_{b}"].abs().median(), vies=t[f"b_{b}"].median()) for b in BRACOS}
        resumo[s]["n"] = len(t)
        resumo[s]["curva_melhor_que_sim"] = int((t.a_curva < t.a_sim_padrao).sum())
        rc, rs = resumo[s]["curva"], resumo[s]["sim_padrao"]
        resumo[s]["curva_vence"] = bool(rc["a"] < rs["a"] and rc["absb"] < rs["absb"])
        resumo[s]["recal_basta"] = bool(resumo[s]["linear_recal"]["a"] - rc["a"] <= 0.01)

    # P3
    ca = C["ativos"]
    alerta = []
    for k in (1, 3, 6):
        ee = []
        for u in exp_:  # curva leave-one-out
            outros = [x for x in exp_ if x != u]
            ck = razoes(P, L, outros, "ativos", [k])[k].median()
            v = P["ativos"].at[u, k]
            if np.isfinite(v):
                ee.append(L.at[u, "ativos"] / (v / ck) - 1)
        ee = pd.Series(ee)
        ec = (L.loc[conf, "ativos"] / (P["ativos"].loc[conf, k] / ca.at[k, "p50"]) - 1).dropna()
        lo, hi = ee.quantile(0.10), ee.quantile(0.90)
        cob = ec.between(lo, hi).mean()
        alerta.append(dict(k=k, n_exp=len(ee), lo=lo, hi=hi, abs_exp=ee.abs().median(), n_conf=len(ec), cobertura=cob,
                           compativel=bool(0.57 <= cob <= 0.93), abs_conf=ec.abs().median()))
    alerta = pd.DataFrame(alerta)
    m2 = d.tam_metragem_m2
    base = pd.DataFrame({"metragem": m2.reindex(exp_), "alunos_por_m2": L.loc[exp_, "ativos"] / m2.reindex(exp_)}).dropna()
    conf_m2 = [u for u in conf if np.isfinite(m2.get(u, np.nan)) and np.isfinite(P["ativos"].at[u, 3])]
    e0 = pd.Series({u: L.at[u, "ativos"] / faixa_alunos_por_densidade(float(m2[u]), base)["faixa_alunos_p50"] - 1 for u in conf_m2}, dtype=float)
    e3 = pd.Series({u: L.at[u, "ativos"] / (P["ativos"].at[u, 3] / ca.at[3, "p50"]) - 1 for u in conf_m2}, dtype=float)

    # P4
    todos = exp_ + conf
    pos = curva(P, L, todos, "ativos", ks=range(13, 25))
    ambos = L.loc[todos, ["ativos", "ativos_24"]].dropna()
    r24 = (ambos.ativos_24 / ambos.ativos).median()
    publica_24 = bool(abs(r24 - 1) > 0.05)
    fator24 = (ambos.ativos / ambos.ativos_24).median()

    absol = P["ativos"].loc[exp_, [0, 1, 3, 6, 12]].median()
    shr = (P["agregadores"].loc[exp_, [1, 3, 6, 12]] / P["ativos"].loc[exp_, [1, 3, 6, 12]]).median()
    L_med = L.loc[exp_, "ativos"].median()
    f0_med = info.f0.reindex(exp_).median()

    # grafico
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(8.5, 5))
        ks = np.arange(0, 13)
        for s, cor in (("ativos", "#1f4e79"), ("pagantes", "#2e8b57"), ("agregadores", "#c77c02")):
            c = C[s].loc[ks]
            ax.plot(ks, 100 * c.p50, color=cor, lw=2.4 if s == "ativos" else 1.6, label=f"{ROTULO[s]} (mediana)")
            if s == "ativos":
                ax.fill_between(ks, 100 * c.p10, 100 * c.p90, color=cor, alpha=0.13, label="alunos: faixa p10–p90")
        sim = [np.nan] + [100 * (min(SIM_A0, L_med) + (L_med - min(SIM_A0, L_med)) * min((k + f0_med) / SIM_MATURACAO, 1)) / L_med for k in ks[1:]]
        ax.plot(ks, sim, color="#888888", ls="--", lw=2, label="simulador hoje (500 alunos, reta até o mês 8)")
        ax.axhline(100, color="#cccccc", lw=0.8)
        ax.set_xlabel("mês de vida da unidade (0 = mês da inauguração)")
        ax.set_ylabel("% do nível maduro (meses 11–13)")
        ax.set_title(f"Rampa de abertura observada — {len(exp_)} unidades Ultra (abertas até nov/2024)")
        ax.set_xticks(ks); ax.set_ylim(0, 125); ax.legend(fontsize=8, loc="lower right"); ax.grid(alpha=0.2)
        fig.tight_layout(); fig.savefig(AQUI / "curva_uni03.png", dpi=150)
    except Exception as ex:
        print("grafico falhou:", ex, file=sys.stderr)

    pct = lambda v: "–" if pd.isna(v) else f"{100 * v:.0f}%"
    sg = lambda v: "–" if pd.isna(v) else f"{100 * v:+.0f}%"
    M = ["# BLK-UNI-03 — resultado da curva de rampa", "",
         f"Protocolo `protocolo_uni03.md` v1.1 (SHA-256 `{hashes['protocolo_uni03.md'][:16]}…`). Rodado uma vez.", "",
         f"- Exploração (monta a curva): **{len(exp_)} unidades**; confirmação: **{len(conf)} unidades** "
         f"(inauguradas de {min(info.ina_comp[conf])} a {max(info.ina_comp[conf])}). Elegíveis que pararam de reportar antes do mês 13: {n_enc}.",
         f"- Nível maduro mediano (exploração, meses 11–13): {L_med:,.0f} alunos. Fração mediana do mês da inauguração já aberta (f0): {f0_med:.2f}.", "",
         "## P1 — curva do 1º ano (% do nível maduro; exploração)", "",
         "| mês | alunos (mediana) | alunos p10–p90 | balcão | agregador | faturamento | simulador hoje* |", "|---|---|---|---|---|---|---|"]
    for k in range(0, 13):
        simk = "–" if k == 0 else pct((min(SIM_A0, L_med) + (L_med - min(SIM_A0, L_med)) * min((k + f0_med) / SIM_MATURACAO, 1)) / L_med)
        M.append(f"| {k} | {pct(C['ativos'].at[k, 'p50'])} | {pct(C['ativos'].at[k, 'p10'])}–{pct(C['ativos'].at[k, 'p90'])} | "
                 f"{pct(C['pagantes'].at[k, 'p50'])} | {pct(C['agregadores'].at[k, 'p50'])} | {pct(C['faturamento'].at[k, 'p50'])} | {simk} |")
    M += ["", f"\\* rampa do simulador (modo padrão) para o nível maduro mediano, no tempo de operação mediano (k + {f0_med:.2f}).", "",
          f"Alunos medianos (absolutos) nos meses 0/1/3/6/12: {' / '.join(f'{v:,.0f}' for v in absol)}. "
          f"Participação do agregador nos meses 1/3/6/12: {' / '.join(pct(v) for v in shr)}.",
          f"Linear recalibrada na exploração: começa em {pct(cal[1])} do nível maduro e chega a 100% no mês {cal[2]} (erro médio {pct(cal[0])}).", "",
          "## P2 — previsão do 1º ano nas unidades de confirmação", "",
          "(a) = erro médio mês a mês (meses 1–10); (b) = erro na soma do 1º ano (mediana do erro absoluto; entre parênteses, o viés).", ""]
    for s in ("ativos", "faturamento"):
        r = resumo[s]
        M += [f"**{s}** ({r['n']} unidades) — curva vence o simulador atual? **{'sim' if r['curva_vence'] else 'não'}**; "
              f"curva erra menos em {r['curva_melhor_que_sim']} de {r['n']} unidades; "
              f"{'basta recalibrar 500/8' if r['recal_basta'] else 'o formato da rampa importa'} (critério fixado antes).", "",
              "| braço | (a) erro mensal | (b) erro na soma do 1º ano |", "|---|---|---|"]
        for b in BRACOS:
            M.append(f"| {b} | {pct(r[b]['a'])} | {pct(r[b]['absb'])} ({sg(r[b]['vies'])}) |")
        M.append("")
    M += ["## P3 — alerta precoce: projetar o nível maduro a partir do mês k", "",
          "| mês | faixa de erro p10–p90 (exploração, leave-one-out) | erro típico (exploração) | erro típico (confirmação) | cobertura na confirmação | compatível (57–93%)? |",
          "|---|---|---|---|---|---|"]
    for _, r in alerta.iterrows():
        M.append(f"| {int(r.k)} | {sg(r.lo)} a {sg(r.hi)} | {pct(r.abs_exp)} | {pct(r.abs_conf)} | {pct(r.cobertura)} ({int(r.n_conf)} unid.) | {'sim' if r.compativel else 'não'} |")
    if len(e0) >= 8:
        M += ["", f"**Antes de abrir × mês 3** ({len(e0)} unidades da confirmação com metragem): erro típico da projeção pela metragem "
              f"(função da viabilidade, base = exploração) = {pct(e0.abs().median())}; pelo mês 3 = {pct(e3.abs().median())}."]
    else:
        M += ["", f"**Antes de abrir × mês 3:** sem amostra ({len(e0)} unidades da confirmação com metragem; mínimo 8)."]
    M += ["", "## P4 — depois do mês 12 (% do nível dos meses 11–13; todas as unidades, dados até ago/2026)", "",
          "| mês | N | mediana | p10 | p90 |", "|---|---|---|---|---|"]
    for k in (13, 15, 18, 21, 24):
        r = pos.loc[k]
        M.append(f"| {k} | {int(r.n)} | {pct(r.p50)} | {pct(r.p10)} | {pct(r.p90)} |")
    M += ["", f"Nível dos meses 22–24 sobre o dos meses 11–13 (mediana, {len(ambos)} unidades): {pct(r24)}. "
          + (f"**Afasta-se de 1 por mais de 5%: a curva recomendada para o simulador é a do nível do mês 24** (curva × {fator24:.3f})."
             if publica_24 else "Dentro de ±5%: o nível dos meses 11–13 vale como nível maduro.")]
    if publica_24:
        M += ["", "| mês | alunos, % do nível do mês 24 |", "|---|---|"] + [f"| {k} | {pct(C['ativos'].at[k, 'p50'] * fator24)} |" for k in range(0, 13)]
    M += ["", "## Insumos (SHA-256)", ""] + [f"- `{k}`: `{v}`" for k, v in hashes.items()]
    (AQUI / "resultado_uni03.md").write_text("\n".join(M) + "\n", encoding="utf-8")
    print("\n".join(M))


if __name__ == "__main__":
    main()
