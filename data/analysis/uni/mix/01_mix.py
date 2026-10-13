# -*- coding: utf-8 -*-
"""BLK-UNI-05C — o que explica a fatia do agregador (protocolo_mix.md, congelado antes de rodar).
Argumento: "alunos" (v1.1, principal: agregadores / ativos, volume) ou "receita" (v1.0: fatia na receita do Financeiro).
Le so' o painel UNI-00 e o agregado LOCAL da demanda TotalPass (X3; a saida nao carrega valor por unidade dessa fonte).
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
s_ = importlib.util.spec_from_file_location("ex", UNI / "uni01" / "01_exploracao.py"); ex = importlib.util.module_from_spec(s_); s_.loader.exec_module(ex)
CTRL = ["l_renda", "l_pop"]
TESTES = [("X1", "l_renda", "renda da praça", 0, "antes de abrir"), ("X2", "escritorios", "escritórios a pé", +1, "antes de abrir"),
          ("X3", "l_tpd", "demanda revelada de TotalPass", +1, "foto atual"), ("X4", "tier_wh", "tier do Wellhub", 0, "decisão do operador"),
          ("X5", "l_indep", "independentes no agregador", 0, "foto atual"), ("X6", "preco", "preço do plano Gold", 0, "decisão do operador"),
          ("X7", "shopping", "em shopping", 0, "antes de abrir")]
BINARIOS = {"shopping"}
DESF = sys.argv[1] if len(sys.argv) > 1 else "receita"
COL_Y, COL_2 = ("pct_agregador_ativos", "pct_agregador_receita_fin") if DESF == "alunos" else ("pct_agregador_receita_fin", "pct_agregador_ativos")
SUF = "_alunos" if DESF == "alunos" else ""
ROT_Y, ROT_2 = ("nos alunos ativos (UX)", "na receita (Financeiro)") if DESF == "alunos" else ("na receita", "nos alunos, UX")
N_BOOT = 2000


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def desfecho(f, ini, fim, mv_min):
    g = f[f.valido & (f.competencia >= ini) & (f.competencia <= fim) & (f.mv >= mv_min) & f[COL_Y].notna()].copy()
    n = g.groupby("unidade_id").size()
    g = g[g.unidade_id.isin(n[n >= 3].index)]
    g["wh_pos"], g["tp_pos"] = g.fin_gympass.fillna(0) > 0, g.fin_totalpass.fillna(0) > 0
    Y = g.groupby("unidade_id").agg(mix=(COL_Y, "mean"), mix_alunos=(COL_2, "mean"),
                                    aceita_wh=("wh_pos", "mean"), aceita_tp=("tp_pos", "mean"))
    Y["aceita_wh"], Y["aceita_tp"] = (Y.aceita_wh >= 0.5).astype(float), (Y.aceita_tp >= 0.5).astype(float)
    return Y


def atributos(d):
    lg = lambda s: np.log(pd.to_numeric(s, errors="coerce").where(lambda v: v > 0))
    A = pd.DataFrame(index=d.index)
    A["l_renda"], A["l_pop"] = lg(d.iso_renda_pc__carro_10), lg(d.iso_pop__carro_10)
    A["escritorios"] = pd.to_numeric(d.poi_F1, errors="coerce")
    A["l_tpd"] = np.log1p(pd.to_numeric(d.tpd_membros_por_mil_hab_c10, errors="coerce"))
    A["tier_wh"] = pd.to_numeric(d.wh_ord_ultra_cadastro, errors="coerce")
    A["l_indep"] = np.log1p(pd.to_numeric(d.iso_n_independente_agregador__carro_10, errors="coerce"))
    A["preco"] = pd.to_numeric(d.cad_preco_gold, errors="coerce")
    A["shopping"] = pd.to_numeric(d.poi_em_shopping.map(lambda v: {True: 1.0, False: 0.0}.get(v, v)), errors="coerce")
    A["metro"], A["uf"], A["regional"] = d.iso_metro, d.uf, d.master
    A["anomalia"] = d.anomalia_conferir.notna() & (d.anomalia_conferir.astype(str).str.strip() != "")
    return A


def amostra(A, Y, ambos=True):
    D = A.join(Y, how="inner")
    D = D[(D.aceita_wh + D.aceita_tp) >= 1]
    return D[(D.aceita_wh == 1) & (D.aceita_tp == 1)] if ambos else D


def ajustar(D, x, extra=(), com_ic=True):
    ctrl = [c for c in CTRL if c != x] + list(extra)
    D = D[["mix", x, "metro", "uf"] + ctrl].dropna().copy()
    n = len(D)
    if x in BINARIOS and (D[x].sum() < 5 or (1 - D[x]).sum() < 5):
        return dict(n=n, motivo="menos de 5 unidades numa classe")
    if n < 12 or D[x].std() == 0:
        return dict(n=n, motivo="N < 12")
    D["X"] = D[x] if x in BINARIOS else (D[x] - D[x].mean()) / D[x].std(ddof=0)
    y = D.mix.to_numpy(float)
    mk = lambda Dm: np.column_stack([np.ones(len(Dm))] + [Dm[c].to_numpy(float) for c in ctrl] + [Dm.X.to_numpy(float)])
    X1 = mk(D); X0 = X1[:, :-1]
    b, e, h, XtXi = ex.ols(y, X1)
    r = dict(n=n, beta=b[-1], h_max=float(h.max()))
    if not com_ic:
        return r
    se = ex.se_hc3(X1, e, h, XtXi)[-1]
    tq = stats.t.ppf(0.95, n - X1.shape[1])
    # CR1 por metro
    G = D.metro.nunique()
    meat = np.zeros((X1.shape[1], X1.shape[1]))
    for m in D.metro.unique():
        k_ = (D.metro == m).to_numpy(); s1 = X1[k_].T @ e[k_]; meat += np.outer(s1, s1)
    c_ = G / (G - 1) * (n - 1) / (n - X1.shape[1])
    se_cl = np.sqrt(c_ * np.diag(XtXi @ meat @ XtXi))[-1]
    tq_cl = stats.t.ppf(0.95, G - 1)
    b0, e0, h0, _ = ex.ols(y, X0)
    lomo, louo = [], []
    for col, lista in (("metro", lomo), ("uf", louo)):
        for m in sorted(D[col].unique()):
            Dm = D[D[col] != m]
            if len(Dm) >= 10 and Dm.X.std() > 0:
                lista.append(np.sign(np.linalg.lstsq(mk(Dm), Dm.mix.to_numpy(float), rcond=None)[0][-1]))
    r.update(ic_lo=b[-1] - tq * se, ic_hi=b[-1] + tq * se, p=2 * stats.t.sf(abs(b[-1] / se), n - X1.shape[1]),
             cl_lo=b[-1] - tq_cl * se_cl, cl_hi=b[-1] + tq_cl * se_cl, g_metro=G,
             r2_loo_base=ex.r2_loo(y, e0, h0), r2_loo=ex.r2_loo(y, e, h), dr2_loo=ex.r2_loo(y, e, h) - ex.r2_loo(y, e0, h0),
             lomo_n=len(lomo), lomo_sinal_ok=bool(lomo and all(s == np.sign(b[-1]) for s in lomo)),
             louo_n=len(louo), louo_sinal_ok=bool(louo and all(s == np.sign(b[-1]) for s in louo)), grupo="metro")
    return r


def confirmar(Dexp, Dconf, x, rng):
    ctrl = [c for c in CTRL if c != x]
    tr, te = Dexp[["mix", x] + ctrl].dropna(), Dconf[["mix", x] + ctrl].dropna()
    if len(te) < 5:
        return dict(n=len(te), leitura="sem amostra")
    X_ = lambda D, cols: np.column_stack([np.ones(len(D))] + [D[c].to_numpy(float) for c in cols])
    b0 = np.linalg.lstsq(X_(tr, ctrl), tr.mix.to_numpy(float), rcond=None)[0]
    b1 = np.linalg.lstsq(X_(tr, ctrl + [x]), tr.mix.to_numpy(float), rcond=None)[0]
    p0, p1 = X_(te, ctrl) @ b0, X_(te, ctrl + [x]) @ b1
    y = te.mix.to_numpy(float)
    e0, e1 = np.abs(y - p0), np.abs(y - p1)
    dif = [e1[i].mean() - e0[i].mean() for i in (rng.integers(0, len(y), len(y)) for _ in range(N_BOOT))]
    lo, hi = np.quantile(dif, [0.05, 0.95])
    r0, r1 = stats.spearmanr(p0, y)[0], stats.spearmanr(p1, y)[0]
    # intercepto reajustado na confirmacao (tira o nivel de 2026)
    a0, a1 = np.abs((y - p0) - np.mean(y - p0)).mean(), np.abs((y - p1) - np.mean(y - p1)).mean()
    ok = e1.mean() < e0.mean() and r1 >= r0 and hi < 0
    return dict(n=len(y), mae0=e0.mean(), mae1=e1.mean(), lo=lo, hi=hi, r0=r0, r1=r1, mae0_int=a0, mae1_int=a1,
                leitura="consistente" if ok else "não se repete")


def main():
    hashes = {p.name: sha(p) for p in [AQUI / "protocolo_mix.md", Path(__file__), UNI / "uni01" / "01_exploracao.py",
                                       UNI / "fato_unidade_mes.parquet", UNI / "dim_unidade.parquet", UNI / "LOCAL_demanda_totalpass_por_unidade.parquet"]}
    f, d = ex.carregar()
    A = atributos(d)
    Yexp = desfecho(f, "2025-01", "2025-12", 12)
    # confirmacao primeiro: novas (mes_vida < 12 em dez/2025 ou ainda nao abertas), maduras em 2026, fora da exploracao
    mv_dez = f[f.competencia == "2025-12"].set_index("unidade_id").mv
    Yc = desfecho(f, "2026-01", "2026-08", 12)
    nova = mv_dez.reindex(Yc.index).fillna(0) < 12
    Yc = Yc[nova & ~Yc.index.isin(Yexp.index)]
    Dexp, Dconf = amostra(A, Yexp), amostra(A, Yc)
    DA = amostra(A, desfecho(f, "2025-01", "2025-12", 6)); DA = DA[~DA.index.isin(Yc.index)]
    DB = amostra(A, desfecho(f, "2025-01", "2025-09", 12))
    DS = amostra(A, Yexp, ambos=False)
    DC = Dexp[~Dexp.anomalia]
    rng = np.random.default_rng(20261003)
    fora = A.join(Yexp, how="inner")
    fora_nenhum = sorted(fora[(fora.aceita_wh + fora.aceita_tp) == 0].index)
    so_um = A.join(Yexp, how="inner"); so_um = so_um[(so_um.aceita_wh + so_um.aceita_tp) == 1]

    linhas = []
    for tid, x, nome, sinal, natureza in TESTES:
        T = dict(id=tid, sinal=sinal, tipo="frac")
        r = ajustar(Dexp, x)
        r["beta_A"], r["beta_B"] = ajustar(DA, x, com_ic=False).get("beta", np.nan), ajustar(DB, x, com_ic=False).get("beta", np.nan)
        r["beta_S"] = ajustar(DS, x, extra=("aceita_wh", "aceita_tp"), com_ic=False).get("beta", np.nan)
        r["beta_C"] = ajustar(DC, x, com_ic=False).get("beta", np.nan)
        if "beta" in r and "ic_lo" in r:
            classe, falhou = ex.classificar(r, T)
            if classe == "candidata" and not (r["cl_lo"] > 0 or r["cl_hi"] < 0):
                classe, falhou = "fraca", "IC agrupado por metro cobre zero"
        else:
            classe, falhou = "sem amostra", r.get("motivo", "")
        c = confirmar(Dexp, Dconf, x, rng)
        linhas.append(dict(teste=tid, x=nome, natureza=natureza, sinal={1: "+", -1: "−", 0: "±"}[sinal], classe=classe, falhou=falhou,
                           **r, **{"conf_" + k: v for k, v in c.items()}))
    R = pd.DataFrame(linhas)
    R.to_csv(AQUI / f"mix_testes{SUF}.csv", sep=";", encoding="utf-8-sig", index=False)

    # R2 LOO base na amostra comum (so' controles)
    Dc = Dexp[["mix"] + CTRL].dropna(); yb = Dc.mix.to_numpy(float)
    bb, eb, hb, _ = ex.ols(yb, np.column_stack([np.ones(len(Dc))] + [Dc[c].to_numpy(float) for c in CTRL]))
    corr = Dexp[[x for _, x, *_ in TESTES]].corr(method="spearman").round(2)

    pf = lambda v: "–" if pd.isna(v) else f"{100 * v:+.1f} p.f."
    L = [f"# BLK-UNI-05C — o que explica a fatia do agregador {ROT_Y}: resultado", "",
         f"Protocolo `protocolo_mix.md` (SHA-256 `{hashes['protocolo_mix.md'][:16]}…`). Rodado uma vez.", "",
         f"- Exploração (2025, aceita os dois agregadores): **{len(Dexp)} unidades**; fatia do agregador {ROT_Y}: mediana "
         f"{100 * Dexp.mix.median():.0f}% (p10 {100 * Dexp.mix.quantile(0.1):.0f}%, p90 {100 * Dexp.mix.quantile(0.9):.0f}%); "
         f"desvio-padrão entre unidades {100 * Dexp.mix.std():.1f} p.f. (a faixa de irrelevância de ±5 p.f. equivale a "
         f"{5 / (100 * Dexp.mix.std()):.2f} desvio-padrão da fatia).",
         f"- Aceita só um agregador em 2025: {len(so_um)} ({', '.join(f'{u} (' + ('Wellhub' if r.aceita_wh else 'TotalPass') + ')' for u, r in so_um.iterrows()) or '–'}); "
         f"não aceita nenhum: {fora_nenhum or 'nenhuma'}.",
         f"- Confirmação (novas, maduras em 2026, aceita os dois): **{len(Dconf)} unidades**; mediana {100 * Dconf.mix.median():.0f}%.",
         f"- R² LOO só com renda e população (amostra comum, N = {len(Dc)}): {ex.r2_loo(yb, eb, hb):.3f}.", "",
         "## Testes", "",
         "Efeito em pontos de fração por 1 desvio-padrão de X (X7: diferença bruta shopping × não). Controles: renda e população c10. "
         "IC HC3 e IC agrupado por metro. A e B entram na classificação; S (inclui quem aceita só um, com aceitação como controle) e C (sem anomalias) são reportadas.", "",
         "| teste | X | natureza | sinal esp. | N | efeito | IC 90% HC3 | IC 90% por metro | ΔR² LOO | estável metro / UF | h máx. | A | B | S | C | classe |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in R.itertuples():
        if pd.isna(getattr(r, "beta", np.nan)) or pd.isna(getattr(r, "ic_lo", np.nan)):
            L.append(f"| {r.teste} | {r.x} | {r.natureza} | {r.sinal} | {r.n} | – | – | – | – | – | – | – | – | – | – | {r.classe} ({r.falhou}) |")
            continue
        L.append(f"| {r.teste} | {r.x} | {r.natureza} | {r.sinal} | {r.n} | **{pf(r.beta)}** | [{pf(r.ic_lo)}; {pf(r.ic_hi)}] | "
                 f"[{pf(r.cl_lo)}; {pf(r.cl_hi)}] ({r.g_metro} metros) | {r.dr2_loo:+.3f} | {'sim' if r.lomo_sinal_ok else 'não'} / "
                 f"{'sim' if r.louo_sinal_ok else 'não'} | {r.h_max:.2f} | {pf(r.beta_A)} | {pf(r.beta_B)} | {pf(r.beta_S)} | {pf(r.beta_C)} | "
                 f"**{r.classe}**{' — ' + r.falhou if r.falhou else ''} |")
    L += ["", f"Contagem: {R.classe.value_counts().to_dict()}.", "", "## Confirmação (unidades novas, 2026)", "",
          "| teste | X | N | erro médio: só controles → com X | IC 90% da diferença | com intercepto reajustado | Spearman | leitura |",
          "|---|---|---|---|---|---|---|---|"]
    for r in R.itertuples():
        if pd.isna(getattr(r, "conf_mae0", np.nan)):
            L.append(f"| {r.teste} | {r.x} | {r.conf_n} | – | – | – | – | {r.conf_leitura} |")
            continue
        L.append(f"| {r.teste} | {r.x} | {r.conf_n} | {100 * r.conf_mae0:.1f} → {100 * r.conf_mae1:.1f} p.f. | [{100 * r.conf_lo:+.1f}; {100 * r.conf_hi:+.1f}] | "
                 f"{100 * r.conf_mae0_int:.1f} → {100 * r.conf_mae1_int:.1f} p.f. | {r.conf_r0:+.2f} → {r.conf_r1:+.2f} | {r.conf_leitura} |")
    L += ["", "## Correlações entre os X (Spearman, exploração)", "", "| | " + " | ".join(corr.columns) + " |", "|---" * (len(corr.columns) + 1) + "|"]
    for i, row in corr.iterrows():
        L.append(f"| {i} | " + " | ".join(f"{v:+.2f}" for v in row) + " |")
    L += ["", "## Descritivo por UF e regional do Growth (exploração + confirmação; aceita os dois)", "",
          f"| grupo | unidades | fatia {ROT_Y} (mediana) | fatia {ROT_2} (mediana) |", "|---|---|---|---|"]
    tudo = pd.concat([Dexp, Dconf])
    for col, rot in (("uf", "UF"), ("regional", "regional")):
        for g_, h in tudo.groupby(col):
            L.append(f"| {rot} {g_} | {len(h)} | {100 * h.mix.median():.0f}% | {100 * h.mix_alunos.median():.0f}% |")
    L += ["", f"Spearman entre fatia {ROT_Y} e fatia {ROT_2}: {stats.spearmanr(tudo.mix, tudo.mix_alunos, nan_policy='omit')[0]:+.2f}.", "",
          "## Insumos (SHA-256)", ""] + [f"- `{k}`: `{v}`" for k, v in hashes.items()]
    (AQUI / f"resultado_mix{SUF}.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
