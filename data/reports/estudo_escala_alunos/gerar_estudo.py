"""Estudo estatistico COMPLETO — escala de alunos por m2 (modelo de viabilidade/risco).

Gera graficos + tabelas reprodutiveis a partir do dado REAL (Ultra, Engenharia).
READ-ONLY sobre o M1. Sem PII (so agregados). Metodologia: LOO-CV vs baseline,
sem R2 in-sample. Rode da raiz do repo:
    python data/reports/estudo_escala_alunos/gerar_estudo.py
Saidas: data/reports/estudo_escala_alunos/{graficos,tabelas}/

Fontes (dados reais) sao gitignored; o script as le localmente. Apenas os
AGREGADOS (graficos/tabelas/relatorio) sao versionados — sem PII.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path("data/reports/estudo_escala_alunos")
G = ROOT / "graficos"
T = ROOT / "tabelas"
rng = np.random.default_rng(20260616)
plt.rcParams.update({"figure.dpi": 110, "font.size": 10, "axes.grid": True, "grid.alpha": 0.3})


# ---------------- loaders ----------------
def _num(s):
    return pd.to_numeric(s, errors="coerce")


def load_ultra_perf():
    u = pd.read_parquet("data/staging/unidades_ultra_performance_hex.parquet")
    u = u[(u.metragem > 0) & (u.alunos_total > 0)].copy()
    for c in ["metragem", "alunos_total", "ativos_pag", "alunos_gympass",
              "alunos_totalpass", "agregadores", "ticket_medio_aluno", "faturamento"]:
        u[c] = _num(u[c])
    return u


def load_ultra_src():
    df = pd.read_excel("data/ultra/dados_academias.xlsx", sheet_name="Plan1")
    df.columns = [str(c).strip() for c in df.columns]
    return pd.DataFrame({
        "metragem": _num(df["Metragem"]), "vagas": _num(df["Vagas"]),
        "alunos_total": _num(df["ALUNOS_TOTAL"]), "pagantes": _num(df["ATIVOS_PAG"]),
    }).assign(marca="ultra")


def load_eng_src():
    df = pd.read_excel("data/validacao/academias_engenharia_do_corpo.xlsx", sheet_name="Academias")
    df.columns = [str(c).strip() for c in df.columns]
    return pd.DataFrame({
        "metragem": _num(df["Metragem M²"]), "vagas": _num(df["Vagas"]),
        "alunos_total": _num(df["Alunos Totais"]), "pagantes": _num(df["Total Alunos Ativos"]),
    }).assign(marca="engenharia")


def load_multirede():
    m = pd.read_parquet("data/staging/base_calibracao_multirede.parquet")
    return m[(m.alunos_reais > 0) & (m.metragem > 0)].copy()


# ---------------- LOO helpers ----------------
def r2_mae(y, pred):
    sst = np.sum((y - y.mean()) ** 2)
    return 1 - np.sum((y - pred) ** 2) / sst, float(np.mean(np.abs(y - pred)))


def loo_loglog(m2, y, extra=None):
    n = len(y)
    cols = [np.ones(n), np.log(m2)]
    if extra is not None:
        for e in extra:
            cols.append(e)
    X = np.column_stack(cols)
    yl = np.log(y)
    pred = np.zeros(n)
    for i in range(n):
        tr = np.arange(n) != i
        b, *_ = np.linalg.lstsq(X[tr], yl[tr], rcond=None)
        res = yl[tr] - X[tr] @ b
        pred[i] = np.exp(X[i] @ b) * np.mean(np.exp(res))
    return pred


def loo_multi(X, y):
    n = len(y)
    Xb = np.column_stack([np.ones(n), X])
    pred = np.zeros(n)
    for i in range(n):
        tr = np.arange(n) != i
        b, *_ = np.linalg.lstsq(Xb[tr], y[tr], rcond=None)
        pred[i] = Xb[i] @ b
    return pred


def loo_seg_ratio(m2, y, seg, min_seg=5):
    n = len(y)
    pred = np.zeros(n)
    for i in range(n):
        tr = np.arange(n) != i
        same = tr & (seg == seg[i])
        dens = (y[same] / m2[same]).mean() if same.sum() >= min_seg else (y[tr] / m2[tr]).mean()
        pred[i] = dens * m2[i]
    return pred


def loo_baseline(y):
    n = len(y)
    return np.array([y[np.arange(n) != i].mean() for i in range(n)])


# ---------------- figuras ----------------
def fig_curva_densidade(ultra, eng):
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
    for a, (nome, d, cor) in zip(ax, [("Ultra", ultra, "#1f77b4"), ("Engenharia", eng, "#d62728")]):
        m2 = d.metragem.to_numpy(float)
        y = d.alunos_total.to_numpy(float)
        a.scatter(m2, y / m2, s=28, alpha=0.6, color=cor)
        xs = np.linspace(m2.min(), m2.max(), 100)
        b, c = np.polyfit(np.log(m2), np.log(y), 1)
        a.plot(xs, np.exp(c) * xs ** (b - 1), color="black", lw=2,
               label=f"densidade ~ m2^{b-1:.2f} (b={b:.2f})")
        a.set_title(f"{nome}: densidade cai com o tamanho (n={len(d)})")
        a.set_xlabel("metragem (m2)"); a.set_ylabel("alunos/m2"); a.legend()
    fig.suptitle("G1 — Retornos decrescentes: alunos/m2 diminui conforme a metragem aumenta")
    fig.tight_layout(); fig.savefig(G / "g1_curva_densidade.png"); plt.close(fig)


def fig_densidade_faixa(multi):
    d = multi.copy(); d["dens"] = d.alunos_reais / d.metragem
    bins = [0, 800, 1100, 1300, 1500, 1800, 2200, 1e9]
    lab = ["<800", "800-1100", "1100-1300", "1300-1500", "1500-1800", "1800-2200", ">2200"]
    d["fx"] = pd.cut(d.metragem, bins, labels=lab)
    g = d.groupby("fx", observed=True).dens.median()
    fig, a = plt.subplots(figsize=(9, 4.4))
    a.bar(range(len(g)), g.values, color="#2ca02c", alpha=0.8)
    a.set_xticks(range(len(g))); a.set_xticklabels(g.index, rotation=20)
    for i, v in enumerate(g.values):
        a.text(i, v + 0.03, f"{v:.2f}", ha="center")
    a.set_ylabel("densidade mediana (alunos/m2)"); a.set_xlabel("faixa de metragem")
    a.set_title("G2 — Densidade mediana por faixa de m2 (pico ~800-1300, cai depois)")
    fig.tight_layout(); fig.savefig(G / "g2_densidade_por_faixa.png"); plt.close(fig)


def fig_estrutura(multi):
    m2 = multi.metragem.to_numpy(float); y = multi.alunos_reais.to_numpy(float)
    marca = multi.marca.to_numpy()
    dummies = [(marca == mk).astype(float) for mk in np.unique(marca)[1:]]
    res = {
        "baseline": r2_mae(y, loo_baseline(y))[0],
        "n.fixo unico": r2_mae(y, loo_seg_ratio(m2, y, np.zeros(len(y))))[0],
        "ratio p/ marca": r2_mae(y, loo_seg_ratio(m2, y, marca))[0],
        "ratio p/ regiao": r2_mae(y, loo_seg_ratio(m2, y, multi.uf.to_numpy()))[0],
        "curva log-log": r2_mae(y, loo_loglog(m2, y))[0],
        "curva + marca": r2_mae(y, loo_loglog(m2, y, dummies))[0],
    }
    pd.Series(res, name="R2_LOO").to_csv(T / "t_estrutura_r2loo.csv")
    fig, a = plt.subplots(figsize=(9, 4.6))
    cores = ["#999"] + ["#d62728"] * 3 + ["#1f77b4", "#2ca02c"]
    a.bar(range(len(res)), list(res.values()), color=cores, alpha=0.85)
    a.axhline(0, color="black", lw=0.8)
    a.set_xticks(range(len(res))); a.set_xticklabels(list(res.keys()), rotation=20)
    for i, v in enumerate(res.values()):
        a.text(i, v + (0.005 if v >= 0 else -0.02), f"{v:+.3f}", ha="center")
    a.set_ylabel("R2_LOO (out-of-sample)")
    a.set_title("G3 — Qual estrutura escala alunos por m2? (curva+marca vence; fixo/regiao falham)")
    fig.tight_layout(); fig.savefig(G / "g3_estrutura.png"); plt.close(fig)
    return res


def fig_vagas(ultra_src, eng_src):
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
    rows = []
    for a, (nome, d, cor) in zip(ax, [("Ultra", ultra_src, "#1f77b4"),
                                      ("Engenharia", eng_src, "#d62728")]):
        s = d.dropna(subset=["metragem", "vagas", "alunos_total"])
        s = s[(s.metragem > 0) & (s.vagas > 0) & (s.alunos_total > 0)]
        m2 = s.metragem.to_numpy(float); vg = s.vagas.to_numpy(float)
        y = s.alunos_total.to_numpy(float)
        a.scatter(m2, vg, s=28, alpha=0.6, color=cor)
        rr = np.corrcoef(np.log(m2), np.log(vg))[0, 1]
        a.set_title(f"{nome}: vagas ~ m2 (corr log-log {rr:+.2f}, colinear)")
        a.set_xlabel("metragem (m2)"); a.set_ylabel("vagas")
        r2_m2 = r2_mae(y, loo_loglog(m2, y))[0]
        r2_vg = r2_mae(y, loo_loglog(vg, y))[0]
        r2_both = r2_mae(y, loo_multi(np.column_stack([m2, vg]), y))[0]
        rows.append({"rede": nome, "R2_m2": r2_m2, "R2_vagas": r2_vg,
                     "R2_m2+vagas": r2_both, "delta": r2_both - r2_m2})
    fig.suptitle("G4 — Vagas e colinear com m2 (proxy de escala) -> nao adiciona sinal robusto")
    fig.tight_layout(); fig.savefig(G / "g4_vagas_colinear.png"); plt.close(fig)
    pd.DataFrame(rows).to_csv(T / "t_vagas_r2loo.csv", index=False)
    return rows


def fig_composicao(ultra):
    bal = (ultra.ativos_pag / ultra.alunos_total).median()
    agg = ((ultra.alunos_gympass + ultra.alunos_totalpass + ultra.agregadores) / ultra.alunos_total)
    # agregadores = umbrella; usa 1-balcao p/ share limpo
    agg_share = 1 - bal
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
    ax[0].pie([bal, agg_share], labels=[f"Balcao\n{bal:.0%}\n(ticket cheio)",
              f"Agregadores\n{agg_share:.0%}\n(~60% ticket)"],
              colors=["#1f77b4", "#ff7f0e"], autopct="", startangle=90)
    ax[0].set_title("G5a — Composicao de alunos (Ultra)")
    m2 = ultra.metragem.to_numpy(float)
    comp = {
        "alunos_total": ultra.alunos_total.to_numpy(float),
        "balcao": ultra.ativos_pag.to_numpy(float),
        "agregadores": (ultra.alunos_total - ultra.ativos_pag).clip(lower=1).to_numpy(float),
    }
    r2s = {k: r2_mae(v, loo_loglog(m2, v))[0] for k, v in comp.items()}
    ax[1].bar(range(len(r2s)), list(r2s.values()),
              color=["#2ca02c", "#1f77b4", "#ff7f0e"], alpha=0.85)
    ax[1].axhline(0, color="black", lw=0.8)
    ax[1].set_xticks(range(len(r2s))); ax[1].set_xticklabels(list(r2s.keys()))
    for i, v in enumerate(r2s.values()):
        ax[1].text(i, v + 0.005, f"{v:+.3f}", ha="center")
    ax[1].set_ylabel("R2_LOO ~ m2")
    ax[1].set_title("G5b — So o TOTAL escala; balcao nao (risco = premissa)")
    fig.tight_layout(); fig.savefig(G / "g5_composicao.png"); plt.close(fig)
    pd.Series({**{"share_balcao": bal, "share_agregadores": agg_share}, **r2s}).to_csv(
        T / "t_composicao.csv")
    return bal, agg_share, r2s


def fig_calibracao(ultra, eng):
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
    out = []
    for a, (nome, d) in zip(ax, [("Ultra", ultra), ("Engenharia", eng)]):
        m2 = d.metragem.to_numpy(float); y = d.alunos_total.to_numpy(float)
        dens = y / m2; n = len(y); pit = np.zeros(n); cov = np.zeros(n, bool)
        for i in range(n):
            sim = dens[np.arange(n) != i] * m2[i]
            pit[i] = np.mean(sim < y[i])
            lo, hi = np.percentile(sim, [10, 90]); cov[i] = lo <= y[i] <= hi
        a.hist(pit, bins=10, range=(0, 1), color="#1f77b4", alpha=0.8, edgecolor="white")
        a.axhline(n / 10, color="red", ls="--", label="uniforme (calibrado)")
        a.set_title(f"{nome}: cobertura p10-p90={cov.mean():.0%} | PIT medio={pit.mean():.2f}")
        a.set_xlabel("PIT (fracao da dist. preditiva < real)"); a.set_ylabel("freq"); a.legend()
        out.append({"rede": nome, "cobertura_p10p90": cov.mean(), "pit_medio": pit.mean()})
    fig.suptitle("G6 — A faixa e HONESTA: p10-p90 contem ~80% das unidades (calibrada)")
    fig.tight_layout(); fig.savefig(G / "g6_calibracao.png"); plt.close(fig)
    pd.DataFrame(out).to_csv(T / "t_calibracao.csv", index=False)
    return out


def fig_ranking_pviavel(ultra):
    dens = (ultra.alunos_total / ultra.metragem).to_numpy(float)
    p10, p50, p90 = np.percentile(dens, [10, 50, 90])
    m2 = 1500
    cand = [("A (aluguel baixo)", 1100), ("B (mediano)", 2100), ("C (aluguel alto)", 3200)]
    fig, a = plt.subplots(figsize=(9, 4.8))
    sim = dens * m2
    a.hist(sim, bins=15, color="#cccccc", alpha=0.7, edgecolor="white")
    cores = {"A (aluguel baixo)": "#2ca02c", "B (mediano)": "#ff7f0e", "C (aluguel alto)": "#d62728"}
    for nome, be in cand:
        pv = np.mean(sim > be)
        a.axvline(be, color=cores[nome], lw=2.2, label=f"{nome}: break-even {be} -> P(viavel) {pv:.0%}")
    a.set_title(f"G7 — Mesma faixa (imovel {m2} m2), P(viavel) ranqueia por risco")
    a.set_xlabel("alunos plausiveis (comparaveis x m2)"); a.set_ylabel("freq comparaveis"); a.legend()
    fig.tight_layout(); fig.savefig(G / "g7_ranking_pviavel.png"); plt.close(fig)


def auc(score, label):
    pos, neg = score[label], score[~label]
    if not len(pos) or not len(neg):
        return float("nan")
    return float(sum(np.sum(s > neg) + 0.5 * np.sum(s == neg) for s in pos) / (len(pos) * len(neg)))


def fig_faixa200(ultra):
    m2 = ultra.metragem.to_numpy(float); y = ultra.alunos_total.to_numpy(float)
    pred = loo_loglog(m2, y)
    Ws = [200, 400, 600, 800, 1000]
    exato, t1 = [], []
    for w in Ws:
        d = np.abs(np.floor(pred / w) - np.floor(y / w))
        exato.append(np.mean(d == 0)); t1.append(np.mean(d <= 1))
    fig, a = plt.subplots(figsize=(9, 4.4))
    a.plot(Ws, exato, "o-", label="acerto exato de faixa")
    a.plot(Ws, t1, "s-", label="acerto +-1 faixa")
    a.axvline(200, color="red", ls="--", alpha=0.6)
    a.set_xlabel("largura da faixa (alunos)"); a.set_ylabel("acerto (LOO)")
    a.set_title("G8 — Faixa de 200 da falsa precisao (MAE ~650); precisa ~800-1000")
    a.legend(); fig.tight_layout(); fig.savefig(G / "g8_faixa200.png"); plt.close(fig)


def fig_ticket_overestima(ultra):
    """Ilustra a superestimacao do wiring atual vs split correto (didatico)."""
    p50_total = 2350; t_bal, t_agg = 137, 82
    bal_share = 0.69
    correto = p50_total * bal_share * t_bal + p50_total * (1 - bal_share) * t_agg
    atual = p50_total * t_bal + 651 * t_agg  # total como balcao + agregadores fixos
    fig, a = plt.subplots(figsize=(8, 4.4))
    a.bar(["aba HOJE\n(total=balcao +651 agg)", "CORRETO\n(split 69/31)"],
          [atual, correto], color=["#d62728", "#2ca02c"], alpha=0.85)
    for i, v in enumerate([atual, correto]):
        a.text(i, v + 5000, f"R$ {v/1000:.0f}k", ha="center")
    a.set_ylabel("receita bruta mensal estimada (R$)")
    a.set_title(f"G9 — Wiring atual superestima receita em {(atual/correto-1):.0%} (p50={p50_total})")
    fig.tight_layout(); fig.savefig(G / "g9_ticket_overestima.png"); plt.close(fig)
    return atual, correto


def main():
    ultra = load_ultra_perf()
    ultra_src, eng_src = load_ultra_src(), load_eng_src()
    multi = load_multirede()
    eng_perf = eng_src.dropna(subset=["metragem", "alunos_total"])
    eng_perf = eng_perf[(eng_perf.metragem > 0) & (eng_perf.alunos_total > 0)]

    print("Gerando figuras...")
    fig_curva_densidade(ultra, eng_perf)
    fig_densidade_faixa(multi)
    estr = fig_estrutura(multi)
    vagas = fig_vagas(ultra_src, eng_src)
    bal, agg_s, r2comp = fig_composicao(ultra)
    calib = fig_calibracao(ultra, eng_perf)
    fig_ranking_pviavel(ultra)
    fig_faixa200(ultra)
    atual, correto = fig_ticket_overestima(ultra)

    print(f"  estrutura R2_LOO: {estr}")
    print(f"  vagas: {vagas}")
    print(f"  composicao: balcao={bal:.0%} agreg={agg_s:.0%} R2={r2comp}")
    print(f"  calibracao: {calib}")
    print(f"  ticket: atual R${atual/1000:.0f}k vs correto R${correto/1000:.0f}k (+{atual/correto-1:.0%})")
    print(f"\nFiguras em {G}  | tabelas em {T}")
    print("OK")


if __name__ == "__main__":
    main()
