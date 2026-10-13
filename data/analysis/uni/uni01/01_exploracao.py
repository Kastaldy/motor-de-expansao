# -*- coding: utf-8 -*-
"""BLK-UNI-01 — exploracao de hipoteses com dados ate dez/2025 (protocolo_uni01.md, congelado antes de rodar).

Le so' o painel UNI-00 (fato_unidade_mes, dim_unidade) e o agregado LOCAL da demanda TotalPass (so' para o T14; a
saida nao carrega nenhum valor por unidade dessa fonte). Saidas em data/analysis/uni/uni01/ (gitignored).
"""
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
INI, FIM, FIM_B = "2025-01", "2025-12", "2025-09"
YS = ["l_fat", "l_ativos", "l_ticket", "agr", "churn"]
BASE = ["l_m2", "l_renda", "l_pop"]
FAIXAS = [(6, 8, "f06"), (9, 11, "f09"), (12, 17, "f12"), (18, 23, "f18")]  # 24+ = referencia
# faixa de irrelevancia (protocolo §6), na escala do coeficiente
IRRELEVANTE = {"log": (np.log(0.9), np.log(1.1)), "frac": (-0.05, 0.05), "pp": (-0.5, 0.5), "int": (-0.15, 0.15)}

TESTES = [
    dict(id="T01", h="renda x ticket", y="l_ticket", x="l_renda", sinal=+1, tipo="log"),
    dict(id="T02", h="renda x agregador", y="agr", x="l_renda", sinal=0, tipo="frac"),
    dict(id="T03", h="tier Wellhub x ticket", y="l_ticket", x="wh_tier", sinal=0, tipo="log"),
    dict(id="T04", h="tier Wellhub x agregador", y="agr", x="wh_tier", sinal=-1, tipo="frac"),  # tier maior = menos assinantes elegiveis
    dict(id="T05", h="preco relativo a concorrencia", y="l_fat", x="wh_gap", sinal=0, tipo="log"),
    dict(id="T06", h="agregador traz volume", y="l_ativos", x="agr_x", sinal=+1, tipo="log"),
    dict(id="T07", h="agregador dilui ticket", y="l_ticket", x="agr_x", sinal=-1, tipo="log"),
    dict(id="T08", h="tamanho x praca boa (diretor)", y="l_fat", x="int", mod="l_renda", sinal=+1, tipo="int"),
    dict(id="T09", h="tamanho x concorrencia de estrutura menor (diretor)", y="l_fat", x="int", mod="frac_indep", sinal=+1, tipo="int"),
    dict(id="T10", h="saturacao x faturamento", y="l_fat", x="l_sat", sinal=-1, tipo="log"),
    dict(id="T11", h="saturacao x volume", y="l_ativos", x="l_sat", sinal=-1, tipo="log"),
    dict(id="T12", h="crescimento do municipio", y="l_fat", x="cres_mun", sinal=+1, tipo="log", grupo="municipio"),  # X do municipio: CR1 por municipio
    dict(id="T13", h="crescimento do hexagono", y="l_fat", x="cres_hex", sinal=+1, tipo="log"),
    dict(id="T14", h="demanda revelada TotalPass (so' local)", y="l_fat", x="l_tpd", sinal=+1, tipo="log"),
    dict(id="T15", h="populacao a pe na mesma cidade", y="l_fat", x="l_pop_pe15", sinal=+1, tipo="log", fe=True),
    dict(id="T16", h="rampa preve o nivel maduro", y="l_ativos", x="l_ativos_m3", sinal=+1, tipo="log"),
    dict(id="T17", h="renda x churn", y="churn", x="l_renda", sinal=-1, tipo="pp"),
    dict(id="T18", h="agregador x churn", y="churn", x="agr_x", sinal=0, tipo="pp"),
    dict(id="T19", h="saturacao x churn", y="churn", x="l_sat", sinal=+1, tipo="pp"),
]


DESTINO = {**{k: "UNI-02" for k in ("T05", "T08", "T09", "T10", "T12", "T13", "T15")},
           **{k: "UNI-06" for k in ("T06", "T07", "T18", "T14", "T16")},
           **{k: "mecanismo" for k in ("T01", "T02", "T17", "T03", "T04", "T11", "T19")}}
LOG_ZERO = {}  # atributo -> unidades com valor <= 0 (viram ausentes no log)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def carregar():
    f = pd.read_parquet(UNI / "fato_unidade_mes.parquet")
    d = pd.read_parquet(UNI / "dim_unidade.parquet")
    d = d[~d.excluida_rede].set_index("unidade_id")
    t = pd.read_parquet(UNI / "LOCAL_demanda_totalpass_por_unidade.parquet").set_index("unidade_id")
    d = d.join(t[["tpd_membros_por_mil_hab_c10"]])
    f = f[f.unidade_id.isin(d.index)].copy()
    f["mv"] = f.mes_vida.fillna(f.mes_vida_minimo)
    f["valido"] = (f.faturamento.notna() & (f.faturamento > 0) & f.mes_completo.astype(bool)
                   & f.operacao_mes_cheio.astype(bool) & (f.ativos > 0))
    f["l_fat"] = np.log(f.faturamento.where(f.valido))
    f["l_ativos"] = np.log(f.ativos.where(f.valido).astype(float))
    f["l_ticket"] = f.l_fat - f.l_ativos
    f["agr"] = f.pct_agregador_ativos.where(f.valido)
    f["churn"] = f.churn_pct.where(f.valido)
    return f, d


def desfechos(f, ini, fim, mv_min=12, min_meses=3):
    g = f[f.valido & (f.competencia >= ini) & (f.competencia <= fim) & (f.mv >= mv_min)]
    n = g.groupby("unidade_id").size()
    g = g[g.unidade_id.isin(n[n >= min_meses].index)]
    Y = g.groupby("unidade_id")[YS].mean()
    Y["n_meses"] = n.reindex(Y.index)
    return Y


def desfechos_ajustados(f):
    """Sensibilidade A: Y = efeito da unidade + efeito do mes-calendario + faixa de maturidade, no painel inteiro ate FIM
    com mv >= 6 (efeito da unidade por demeaning; FWL). Placeholders = 24+ em todos os meses (idade so' limite inferior).
    Nivel = media de (y - faixa - mes) nos meses validos de 2025 (>= 3)."""
    g = f[f.valido & (f.competencia <= FIM)].copy()
    g["mvA"] = np.where(g.flag_inauguracao_placeholder.astype(bool), 999, g.mv)
    g = g[g.mvA >= 6].copy()
    cols = []
    for a, b, k in FAIXAS:
        g[k] = ((g.mvA >= a) & (g.mvA <= b)).astype(float); cols.append(k)
    meses = sorted(g.competencia.unique())[:-1]  # ultimo mes = referencia
    for m in meses:
        g["m" + m] = (g.competencia == m).astype(float); cols.append("m" + m)
    out, efeitos = {}, {}
    for y in YS:
        h = g[g[y].notna()]
        Xd = h[cols] - h.groupby("unidade_id")[cols].transform("mean")
        yd = h[y] - h.groupby("unidade_id")[y].transform("mean")
        beta = np.linalg.lstsq(Xd.to_numpy(), yd.to_numpy(), rcond=None)[0]
        efeitos[y] = dict(zip(cols[:len(FAIXAS)], beta[:len(FAIXAS)].round(3)))
        h25 = h[h.competencia >= INI]
        n25 = h25.groupby("unidade_id").size()
        h25 = h25[h25.unidade_id.isin(n25[n25 >= 3].index)]
        out[y] = (h25[y] - h25[cols].to_numpy() @ beta).groupby(h25.unidade_id).mean()
    Y = pd.DataFrame(out)
    return Y, efeitos


def atributos(d):
    def lg(s):
        s = pd.to_numeric(s, errors="coerce")
        LOG_ZERO[s.name] = int((s <= 0).sum())
        return np.log(s.where(s > 0))
    A = pd.DataFrame(index=d.index)
    A["l_m2"] = lg(d.tam_metragem_m2)
    A["l_renda"] = lg(d.iso_renda_pc__carro_10)
    A["l_pop"] = lg(d.iso_pop__carro_10)
    A["wh_tier"] = d.wh_ord_ultra_cadastro
    A["wh_gap"] = d.wh_gap_ord_c10
    A["frac_indep"] = d.iso_n_independente_agregador__carro_10 / d.iso_n_academias__carro_10.where(d.iso_n_academias__carro_10 > 0)
    A["l_sat"] = lg(d.conc_alunos_por_mil_hab__carro_10)
    A["cres_mun"] = d.cres_dim_media
    A["cres_hex"] = d.cres_hex_taxa
    A["l_tpd"] = np.log1p(d.tpd_membros_por_mil_hab_c10)
    A["l_pop_pe15"] = lg(d.iso_pop__pe_15)
    A["l_ativos_m3"] = lg(d.rampa_ativos_m3)
    A["metro"] = d.iso_metro
    A["municipio"] = d.cres_cod6
    return A


def ols(y, X):
    XtXi = np.linalg.pinv(X.T @ X)
    b = XtXi @ X.T @ y
    e = y - X @ b
    h = np.einsum("ij,jk,ik->i", X, XtXi, X)
    return b, e, h, XtXi


def se_hc3(X, e, h, XtXi):
    w = (e / (1 - h)) ** 2
    return np.sqrt(np.diag(XtXi @ (X.T * w) @ X @ XtXi))


def r2_loo(y, e, h):
    return 1 - np.sum((e / (1 - h)) ** 2) / np.sum((y - y.mean()) ** 2)


def montar(T, Y, A):
    """Df do teste (casos completos), controles e escala do coeficiente."""
    D = A.join(Y, how="inner")
    D["agr_x"] = D["agr"]
    ctrl = [c for c in BASE if c != T["x"]]
    if T["x"] == "int":
        ctrl = list(dict.fromkeys(BASE + [T["mod"]]))
    need = [T["y"]] + ctrl + ([T["mod"], "l_m2"] if T["x"] == "int" else [T["x"]]) + ["metro"]
    need += ["municipio"] if T.get("grupo") == "municipio" else []
    D = D[list(dict.fromkeys(need))].replace([np.inf, -np.inf], np.nan).dropna().copy()
    if T.get("fe"):
        cnt = D.metro.value_counts()
        D = D[D.metro.isin(cnt[cnt >= 2].index)].copy()
    escala = 1.0
    if T["x"] == "int":
        zm2 = (D.l_m2 - D.l_m2.mean()) / D.l_m2.std(ddof=0)
        zmod = (D[T["mod"]] - D[T["mod"]].mean()) / D[T["mod"]].std(ddof=0)
        D["X"] = zm2 * zmod
        escala = 1 / D.l_m2.std(ddof=0)  # coef. por 1 dp de log m2 -> variacao na ELASTICIDADE ao m2 por 1 dp do modificador
    else:
        D["X"] = (D[T["x"]] - D[T["x"]].mean()) / D[T["x"]].std(ddof=0)
    return D, ctrl, escala


def matriz(D, ctrl, com_x, fe):
    M = [np.ones(len(D))] + [D[c].to_numpy(float) for c in ctrl]
    if fe:
        for m in sorted(D.metro.unique())[1:]:
            M.append((D.metro == m).to_numpy(float))
    if com_x:
        M.append(D["X"].to_numpy(float))
    return np.column_stack(M)


def ajustar(T, Y, A):
    D, ctrl, esc = montar(T, Y, A)
    n = len(D)
    grp = T.get("grupo", "metro")
    if n < 12 or D["X"].std() == 0 or (grp == "municipio" and D.municipio.nunique() < 8):
        return dict(n=n, n_grupos=D[grp].nunique() if n else 0)
    y = D[T["y"]].to_numpy(float)
    X1, X0 = matriz(D, ctrl, True, T.get("fe")), matriz(D, ctrl, False, T.get("fe"))
    b, e, h, XtXi = ols(y, X1)
    if grp == "municipio":  # CR1 agrupado: unidades do mesmo municipio repetem X
        G = D.municipio.nunique()
        meat = np.zeros((X1.shape[1], X1.shape[1]))
        for g_ in D.municipio.unique():
            k_ = (D.municipio == g_).to_numpy()
            s_ = X1[k_].T @ e[k_]
            meat += np.outer(s_, s_)
        c_ = G / (G - 1) * (n - 1) / (n - X1.shape[1])
        se = np.sqrt(c_ * np.diag(XtXi @ meat @ XtXi))[-1]
        df = G - 1
    else:
        se = se_hc3(X1, e, h, XtXi)[-1]
        df = n - X1.shape[1]
    tq = stats.t.ppf(0.95, df)
    b0, e0, h0, _ = ols(y, X0)
    r = dict(n=n, k=X1.shape[1], beta=b[-1] * esc, ic_lo=(b[-1] - tq * se) * esc, ic_hi=(b[-1] + tq * se) * esc,
             p=2 * stats.t.sf(abs(b[-1] / se), df), r2_loo_base=r2_loo(y, e0, h0), r2_loo=r2_loo(y, e, h),
             mde=(tq + stats.t.ppf(0.80, df)) * se * esc, n_metros=D.metro.nunique(), n_grupos=D[grp].nunique(), grupo=grp,
             h_max=float(max(h.max(), h0.max())))
    r["dr2_loo"] = r["r2_loo"] - r["r2_loo_base"]
    # estabilidade: retira cada metro (T12: cada municipio) inteiro
    sinais, betas = [], []
    for m in sorted(D[grp].unique()):
        Dm = D[D[grp] != m]
        if len(Dm) < 10 or Dm["X"].std() == 0:
            continue
        Xm = matriz(Dm, ctrl, True, T.get("fe"))
        bm = np.linalg.lstsq(Xm, Dm[T["y"]].to_numpy(float), rcond=None)[0]
        betas.append(bm[-1] * esc); sinais.append(np.sign(bm[-1]))
    r["lomo_n"] = len(sinais)
    r["lomo_sinal_ok"] = bool(len(sinais) and all(s == np.sign(b[-1]) for s in sinais))
    r["lomo_beta_min"], r["lomo_beta_max"] = (min(betas), max(betas)) if betas else (np.nan, np.nan)
    return r


def classificar(r, T):
    """Precedencia do §6: sem amostra > descartada > contraria > candidata > fraca > inconclusiva. Devolve (classe, falhou)."""
    if "beta" not in r:
        return "sem amostra", ""
    lo, hi, s = r["ic_lo"], r["ic_hi"], T["sinal"]
    a, b = IRRELEVANTE[T["tipo"]]
    if a < lo and hi < b:
        return "descartada", ""
    exclui = lo > 0 or hi < 0
    if not exclui:
        return "inconclusiva", ""
    sb = np.sign(r["beta"])
    if s != 0 and sb != s:
        return "contraria", ""
    falhou = []
    if not r["dr2_loo"] > 0:
        falhou.append("ΔR² LOO ≤ 0")
    if not r["lomo_sinal_ok"]:
        falhou.append("sinal muda ao retirar " + ("município" if r.get("grupo") == "municipio" else "metro"))
    for k in ("A", "B"):
        v = r.get("beta_" + k, np.nan)
        if pd.isna(v):
            falhou.append(f"sensib. {k} sem amostra")
        elif np.sign(v) != sb:
            falhou.append(f"sinal oposto na sensib. {k}")
    return ("candidata" if not falhou else "fraca"), "; ".join(falhou)


def fmt(v, tipo):
    if pd.isna(v):
        return "–"
    if tipo == "log":
        return f"{100 * (np.exp(v) - 1):+.1f}%"
    if tipo == "frac":
        return f"{100 * v:+.1f} p.f."
    if tipo == "pp":
        return f"{v:+.2f} pp"
    return f"{v:+.3f}"


def main():
    hashes = {p.name: sha(p) for p in [AQUI / "protocolo_uni01.md", Path(__file__), UNI / "fato_unidade_mes.parquet",
                                       UNI / "dim_unidade.parquet", UNI / "LOCAL_demanda_totalpass_por_unidade.parquet"]}
    f, d = carregar()
    A = atributos(d)
    Yp = desfechos(f, INI, FIM)
    Yb = desfechos(f, INI, FIM_B)
    Ya, efeitos = desfechos_ajustados(f)

    linhas = []
    for T in TESTES:
        r = ajustar(T, Yp, A)
        ra, rb = ajustar(T, Ya, A), ajustar(T, Yb, A)
        r["beta_A"], r["n_A"], r["ic_lo_A"], r["ic_hi_A"] = ra.get("beta", np.nan), ra.get("n"), ra.get("ic_lo", np.nan), ra.get("ic_hi", np.nan)
        r["beta_B"], r["n_B"] = rb.get("beta", np.nan), rb.get("n")
        r["classe"], r["falhou"] = classificar(r, T)
        linhas.append({"teste": T["id"], "destino": DESTINO[T["id"]], "hipotese": T["h"], "desfecho": T["y"], "x": T["mod"] if T["x"] == "int" else T["x"],
                       "sinal_esperado": {1: "+", -1: "−", 0: "±"}[T["sinal"]], "tipo": T["tipo"], **r})
    R = pd.DataFrame(linhas)
    R.to_csv(AQUI / "resultado_uni01.csv", sep=";", encoding="utf-8-sig", index=False)

    # descritivos
    comp = d.loc[Yp.index]
    g6 = f[f.valido & (f.competencia <= FIM) & (f.mv >= 6)]
    ult = g6.sort_values("competencia").groupby("unidade_id").tail(6).groupby("unidade_id").agr.mean()
    uf = pd.DataFrame({"agr": ult, "uf": d.uf.reindex(ult.index)}).groupby("uf").agr.agg(["size", "median", "min", "max"])
    uf_todas = d.uf.value_counts()
    tier = A.join(d[["tp_ord_ultra_cadastro"]])
    rho_wh = stats.spearmanr(tier.wh_tier, tier.l_renda, nan_policy="omit")
    rho_tp = stats.spearmanr(tier.tp_ord_ultra_cadastro, tier.l_renda, nan_policy="omit")
    n_wh = tier[["wh_tier", "l_renda"]].dropna().shape[0]
    n_tp = tier[["tp_ord_ultra_cadastro", "l_renda"]].dropna().shape[0]

    L = ["# BLK-UNI-01 — resultado da exploração (dados até dez/2025)", "",
         f"Protocolo: `protocolo_uni01.md` (SHA-256 `{hashes['protocolo_uni01.md'][:16]}…`). Rodado uma vez.", "",
         "## Amostras", "",
         f"- Primária (maduras, jan–dez/2025, ≥ 3 meses com `mes_vida >= 12`): **{len(Yp)} unidades** em {comp.iso_metro.nunique()} metros; "
         f"UF {comp.uf.value_counts().to_dict()}.",
         f"- Sensibilidade A (maturidade ajustada; nível medido em 2025 com `mes_vida >= 6`): {Ya.l_fat.notna().sum()} unidades. "
         f"Efeito da faixa no log do faturamento, contra 24+: {efeitos['l_fat']}.",
         f"- Sensibilidade B (jan–set/2025): {len(Yb)} unidades.",
         f"- Desvio-padrão entre unidades (primária): log faturamento {Yp.l_fat.std():.3f}, log ativos {Yp.l_ativos.std():.3f}, "
         f"log ticket {Yp.l_ticket.std():.3f}, % agregador {Yp.agr.std():.3f}, churn {Yp.churn.std():.2f} pp.", "",
         "## Testes", "",
         "Efeito = 1 desvio-padrão de X (interação: variação da elasticidade ao m² por 1 dp do modificador). IC 90% HC3 "
         "(T12: agrupado por município). ΔR² LOO contra a base nas mesmas unidades. Estável = mesmo sinal ao retirar cada metro "
         "(T12: município; entre parênteses, quantas retiradas). A e B = efeito nas sensibilidades.", "",
         "| teste | destino | hipótese | Y | sinal esp. | N | efeito | IC 90% | ΔR² LOO | estável | A | B | mín. detectável | classe | falhou |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in R.iterrows():
        if pd.isna(r.get("beta")):
            L.append(f"| {r.teste} | {r.destino} | {r.hipotese} | {r.desfecho} | {r.sinal_esperado} | {r.n} | – | – | – | – | – | – | – | {r.classe} | "
                     f"grupos: {r.get('n_grupos')} |")
            continue
        L.append(f"| {r.teste} | {r.destino} | {r.hipotese} | {r.desfecho} | {r.sinal_esperado} | {r.n} | {fmt(r.beta, r.tipo)} | "
                 f"[{fmt(r.ic_lo, r.tipo)}, {fmt(r.ic_hi, r.tipo)}] | {r.dr2_loo:+.3f} | {'sim' if r.lomo_sinal_ok else 'não'} ({r.lomo_n}) | "
                 f"{fmt(r.beta_A, r.tipo)} | {fmt(r.beta_B, r.tipo)} | {fmt(r.mde, r.tipo).lstrip('+')} | **{r.classe}** | {r.falhou} |")
    sobe = R[(R.destino == "UNI-02") & (R.classe == "candidata")].sort_values("dr2_loo", ascending=False)
    L += ["", f"Contagem: {R.classe.value_counts().to_dict()}.", "",
          "**Candidatas ao UNI-02** (Y1, X conhecido antes de abrir; no máximo 2, por ΔR² LOO): "
          + (", ".join(f"{r.teste} ({r.hipotese}, ΔR² LOO {r.dr2_loo:+.3f})" for _, r in sobe.head(2).iterrows()) or "nenhuma")
          + (f". Ficam de fora pelo limite: {', '.join(sobe.teste.iloc[2:])}." if len(sobe) > 2 else "."), "",
          f"Unidades com valor ≤ 0 em atributo logaritmizado (viram ausentes): {LOG_ZERO}.", "",
          "## Descritivos", "",
          f"- **% agregador por UF** (média dos 6 últimos meses válidos até dez/25, `mes_vida >= 6`; unidades na rede hoje por UF: {uf_todas.to_dict()}):", "",
          "| UF | unidades | mediana | mín. | máx. |", "|---|---|---|---|---|"]
    for u, r in uf.sort_values("size", ascending=False).iterrows():
        L.append(f"| {u} | {int(r['size'])} | {100 * r['median']:.0f}% | {100 * r['min']:.0f}% | {100 * r['max']:.0f}% |")
    L += ["", f"- **Tier do agregador × renda da praça** (Spearman, todas as unidades com os dois): Wellhub ρ = {rho_wh[0]:+.2f} "
          f"(N = {n_wh}, p = {rho_wh[1]:.3f}); TotalPass ρ = {rho_tp[0]:+.2f} (N = {n_tp}, p = {rho_tp[1]:.3f}).", "",
          "## Insumos (SHA-256)", ""] + [f"- `{k}`: `{v}`" for k, v in hashes.items()]
    (AQUI / "resultado_uni01.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    Yp.join(Ya, rsuffix="_A").round(4).to_csv(AQUI / "amostra_uni01.csv", sep=";", encoding="utf-8-sig")
    print("\n".join(L))


if __name__ == "__main__":
    main()
