# -*- coding: utf-8 -*-
"""Exploratoria do BLK-UNI (pedido do Felipe, 06/10): lote 1, BALCAO x AGREGADOR, antes de qualquer modelo novo.
Gera graficos PNG e uma planilha com os numeros de cada grafico na pasta de analises do Felipe (OneDrive). So' dados do
painel do estudo (fato_unidade_mes, dim_unidade, metragem) e do Financeiro ja' consolidado nele; NADA da Base Consolidada nem
de arquivos LOCAL_ (o OneDrive sincroniza com a nuvem).
Uso: 01_balcao_agregador.py  (.venv, PYTHONPATH=src)."""
import importlib.util
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
OUT = Path(r"C:\Users\Felipe\OneDrive - Grupo Ultra\Área de Trabalho\Análises - Motor de Expansão\Exploratória BLK-UNI\01 - Balcão x agregador")
JAN = ("2026-03", "2026-08")      # janela recente: ultimos 6 meses fechados
CORES_UF = {"DF": "#1f77b4", "GO": "#17becf", "SP": "#d62728", "RJ": "#2ca02c", "MG": "#9467bd", "PR": "#8c564b", "MT": "#e377c2",
            "ES": "#ff7f0e", "SC": "#bcbd22", "BA": "#7f7f7f", "PE": "#393b79", "RS": "#637939", "AM": "#843c39"}
plt.rcParams.update({"figure.dpi": 110, "savefig.dpi": 150, "font.size": 9, "axes.grid": True, "grid.alpha": .3})


def mod(nome, p):
    s = importlib.util.spec_from_file_location(nome, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def cor(uf):
    return CORES_UF.get(uf, "#444444")


def salvar(fig, nome):
    fig.tight_layout(); fig.savefig(OUT / nome, bbox_inches="tight"); plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tm = mod("tm", UNI / "termometro" / "01_termometro.py"); ex = tm.ex
    f, d = ex.carregar()
    tr, te, DUM, cal, A, dummies = tm.bases(f, d)
    met = pd.read_csv(UNI / "coleta_metragem" / "metragem_estimada_2026-09-29.csv", sep=";", encoding="utf-8-sig", index_col=0).metragem_estimada_m2
    m2 = d.tam_metragem_m2.combine_first(met)
    m2_origem = pd.Series(np.where(d.tam_metragem_m2.notna(), "oficial", np.where(met.reindex(d.index).notna(), "estimada", "sem dado")), index=d.index)
    f = f.copy()
    f["B"] = f.fin_vendas_ux - f.fin_tem_saude.fillna(0)
    f["WH"], f["TP"] = f.fin_gympass.fillna(0), f.fin_totalpass.fillna(0)
    f["AG"] = f.WH + f.TP
    ok = f.valido & f.fin_vendas_ux.notna()
    # ---------------- corte transversal: unidades maduras na janela recente
    g = f[ok & (f.competencia >= JAN[0]) & (f.competencia <= JAN[1]) & (f.mv >= 12)]
    n = g.groupby("unidade_id").size(); g = g[g.unidade_id.isin(n[n >= 3].index)]
    U = g.groupby("unidade_id")[["faturamento", "B", "WH", "TP", "AG", "pagantes", "alunos_gympass", "alunos_totalpass", "ativos"]].mean()
    U["n_meses"] = n.reindex(U.index)
    U["uf"] = d.uf.reindex(U.index)
    U["master"] = A.master_id.reindex(U.index)
    U["m2"] = m2.reindex(U.index); U["m2_origem"] = m2_origem.reindex(U.index)
    U["renda_dom"] = np.exp(A.l_renda_dom.reindex(U.index)); U["pop_iso10"] = np.exp(A.l_pop.reindex(U.index))
    U["inauguracao"] = d.inauguracao.reindex(U.index)
    U["pct_agregador_receita"] = U.AG / (U.B + U.AG)
    U["pct_tp_no_agregador"] = U.TP / U.AG.where(U.AG > 0)
    U["fat_por_m2"] = U.faturamento / U.m2
    U["ticket_balcao"] = U.B / U.pagantes.where(U.pagantes > 0)
    U["rs_por_aluno_agregador"] = U.AG / (U.alunos_gympass + U.alunos_totalpass).where(lambda s: s > 0)
    U["sem_agregador"] = U.AG <= 0
    U["df_go"] = U.uf.isin(["DF", "GO"])
    U = U.sort_values("faturamento", ascending=False)
    planilhas = {}

    # 1) composicao da receita por unidade
    fig, ax = plt.subplots(figsize=(10, max(6, 0.22 * len(U))))
    y = np.arange(len(U))[::-1]
    ax.barh(y, U.B / 1e3, color="#4c72b0", label="Balcão (vendas próprias)")
    ax.barh(y, U.WH / 1e3, left=U.B / 1e3, color="#dd8452", label="Wellhub")
    ax.barh(y, U.TP / 1e3, left=(U.B + U.WH) / 1e3, color="#55a868", label="TotalPass")
    ax.set_yticks(y); ax.set_yticklabels([f"{u}  ({uf})" for u, uf in zip(U.index, U.uf)], fontsize=7)
    for t, uf in zip(ax.get_yticklabels(), U.uf):
        t.set_color(cor(uf))
    ax.set_xlabel("R$ mil por mês (média mar–ago/2026)"); ax.legend(loc="lower right")
    ax.set_title(f"Composição da receita das {len(U)} unidades maduras (≥ 12 meses), mar–ago/2026 — Financeiro")
    salvar(fig, "01_composicao_receita_por_unidade.png")
    planilhas["01_composicao"] = U[["uf", "master", "faturamento", "B", "WH", "TP", "pct_agregador_receita", "pct_tp_no_agregador", "n_meses"]]

    # 2) % agregador x faturamento (total e por m2)
    fig, axs = plt.subplots(1, 2, figsize=(13, 5.5))
    for ax, col, rot in ((axs[0], "faturamento", "Faturamento total (R$ mil/mês)"), (axs[1], "fat_por_m2", "Faturamento por m² (R$/m²/mês)")):
        sub = U[U[col].notna()]
        val = sub[col] / (1e3 if col == "faturamento" else 1)
        ax.scatter(100 * sub.pct_agregador_receita, val, c=[cor(u) for u in sub.uf], s=35, edgecolor="k", lw=.3)
        for u, x_, y_ in zip(sub.index, 100 * sub.pct_agregador_receita, val):
            ax.annotate(u.replace("-df", "").replace("-sp", "").replace("-go", "").replace("-rj", ""), (x_, y_), fontsize=6, alpha=.75, xytext=(2, 2), textcoords="offset points")
        for msk, est, rotulo in ((np.ones(len(sub), bool), "-", "todas"), (~sub.df_go.to_numpy(), "--", "sem DF+GO")):
            xx, yy = 100 * sub.pct_agregador_receita[msk], np.log(val[msk])
            b = np.polyfit(xx, yy, 1); xs = np.linspace(0, xx.max(), 50)
            ax.plot(xs, np.exp(np.polyval(b, xs)), "k" + est, lw=1, label=f"tendência {rotulo}: {100 * (np.exp(10 * b[0]) - 1):+.0f}% a cada +10 p.p.")
        ax.set_yscale("log"); ax.set_xlabel("% da receita vinda de agregador (Wellhub + TotalPass)"); ax.set_ylabel(rot); ax.legend(fontsize=7)
    axs[0].set_title("Mais agregador, menos faturamento?"); axs[1].set_title("O mesmo, por m² (só unidades com metragem)")
    fig.legend(handles=[plt.Line2D([], [], marker="o", ls="", color=c, label=u) for u, c in CORES_UF.items() if u in set(U.uf)], loc="upper center", ncol=12, fontsize=7, bbox_to_anchor=(.5, 1.04))
    salvar(fig, "02_pct_agregador_x_faturamento.png")
    planilhas["02_agregador_x_fat"] = U[["uf", "pct_agregador_receita", "faturamento", "m2", "m2_origem", "fat_por_m2"]]

    # 3) balcao x agregador em reais
    fig, ax = plt.subplots(figsize=(8.5, 7))
    s3 = U[U.AG > 0]
    ax.scatter(s3.B / 1e3, s3.AG / 1e3, c=[cor(u) for u in s3.uf], s=40, edgecolor="k", lw=.3)
    for u, x_, y_ in zip(s3.index, s3.B / 1e3, s3.AG / 1e3):
        ax.annotate(u[:18], (x_, y_), fontsize=6, alpha=.75, xytext=(2, 2), textcoords="offset points")
    xs = np.linspace(40, 700, 50)
    for sh in (.1, .25, .4, .55):
        ax.plot(xs, xs * sh / (1 - sh), ":", color="gray", lw=.8); ax.text(xs[-1], xs[-1] * sh / (1 - sh), f"{int(100 * sh)}% agreg.", fontsize=7, color="gray")
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlabel("Balcão (R$ mil/mês)"); ax.set_ylabel("Agregador (R$ mil/mês)")
    ax.set_title(f"Balcão × agregador por unidade (mar–ago/2026). Sem agregador: {', '.join(U.index[U.sem_agregador])}")
    salvar(fig, "03_balcao_x_agregador.png")

    # 4) praca x partes (renda, pop, m2) — com e sem DF+GO
    fig, axs = plt.subplots(2, 3, figsize=(15, 9))
    for i, (parte, rot_p) in enumerate((("B", "Balcão"), ("AG", "Agregador"))):
        for j, (x, rot_x) in enumerate((("renda_dom", "Renda domiciliar da isócrona de 10 min (R$)"), ("pop_iso10", "População da isócrona de 10 min"), ("m2", "Metragem (m²)"))):
            ax = axs[i, j]; sub = U[(U[parte] > 0) & U[x].notna()]
            ax.scatter(sub[x], sub[parte] / 1e3, c=[cor(u) for u in sub.uf], s=28, edgecolor="k", lw=.3)
            for msk, est, rotulo in ((np.ones(len(sub), bool), "-", "todas"), (~sub.df_go.to_numpy(), "--", "sem DF+GO")):
                xx, yy = np.log(sub[x][msk]), np.log(sub[parte][msk])
                b = np.polyfit(xx, yy, 1); xs = np.linspace(xx.min(), xx.max(), 50)
                ax.plot(np.exp(xs), np.exp(np.polyval(b, xs)) / 1e3, "k" + est, lw=1, label=f"{rotulo}: elasticidade {b[0]:+.2f}, corr {np.corrcoef(xx, yy)[0, 1]:+.2f}")
            ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlabel(rot_x); ax.set_ylabel(f"{rot_p} (R$ mil/mês)"); ax.legend(fontsize=7)
            ax.set_title(f"{rot_p} × {rot_x.split(' (')[0].split(' da ')[0].lower()}")
    fig.suptitle("Praça e metragem contra cada parte da receita (unidades maduras, mar–ago/2026). Simples, sem controlar as outras variáveis.", y=1.01)
    salvar(fig, "04_praca_x_partes.png")
    planilhas["04_praca_partes"] = U[["uf", "B", "AG", "renda_dom", "pop_iso10", "m2", "m2_origem"]]

    # 5) evolucao mensal da rede
    h = f[ok & f.mes_completo.astype(bool) & (f.competencia >= "2024-01")]
    M = h.groupby("competencia")[["B", "WH", "TP"]].sum() / 1e6
    M["unidades"] = h.groupby("competencia").unidade_id.nunique()
    M["pct_agregador"] = (M.WH + M.TP) / (M.B + M.WH + M.TP)
    hm = h[h.mv >= 12]
    Mm = hm.groupby("competencia")[["B", "AG"]].median() / 1e3
    fig, axs = plt.subplots(1, 3, figsize=(17, 5))
    idx = range(len(M))
    axs[0].stackplot(idx, M.B, M.WH, M.TP, labels=["Balcão", "Wellhub", "TotalPass"], colors=["#4c72b0", "#dd8452", "#55a868"])
    axs[0].set_xticks(list(idx)[::3]); axs[0].set_xticklabels(M.index[::3], rotation=45); axs[0].set_ylabel("R$ milhões/mês (rede)"); axs[0].legend(loc="upper left")
    axs[0].set_title("Receita da rede por tipo")
    axs[1].plot(idx, 100 * M.pct_agregador, "k-o", ms=3); axs[1].set_xticks(list(idx)[::3]); axs[1].set_xticklabels(M.index[::3], rotation=45)
    axs[1].set_ylabel("% da receita"); axs[1].set_title("Peso do agregador na receita da rede")
    ix = range(len(Mm))
    axs[2].plot(ix, Mm.B, "-o", ms=3, color="#4c72b0", label="Balcão"); axs[2].plot(ix, Mm.AG, "-o", ms=3, color="#dd8452", label="Agregador")
    axs[2].set_xticks(list(ix)[::3]); axs[2].set_xticklabels(Mm.index[::3], rotation=45); axs[2].set_ylabel("R$ mil/mês (mediana por unidade)")
    axs[2].set_title("Unidade madura típica (≥ 12 meses): balcão × agregador"); axs[2].legend()
    salvar(fig, "05_evolucao_mensal_rede.png")
    planilhas["05_evolucao_rede"] = M.join(Mm.rename(columns={"B": "mediana_balcao_madura_mil", "AG": "mediana_agregador_madura_mil"}))

    # 6) rampa por parte (mes de vida)
    r = f[ok & f.mes_completo.astype(bool) & f.mes_vida.between(1, 24)]
    R = r.groupby("mes_vida").agg(unidades=("unidade_id", "nunique"), balcao_p25=("B", lambda s: s.quantile(.25)), balcao_med=("B", "median"),
                                   balcao_p75=("B", lambda s: s.quantile(.75)), agreg_p25=("AG", lambda s: s.quantile(.25)), agreg_med=("AG", "median"),
                                   agreg_p75=("AG", lambda s: s.quantile(.75)))
    R["pct_agregador_med"] = r.assign(p=r.AG / (r.B + r.AG)).groupby("mes_vida").p.median()
    fig, axs = plt.subplots(1, 2, figsize=(14, 5))
    for col, c_, rot in (("balcao", "#4c72b0", "Balcão"), ("agreg", "#dd8452", "Agregador")):
        axs[0].plot(R.index, R[f"{col}_med"] / 1e3, "-o", ms=3, color=c_, label=f"{rot} (mediana)")
        axs[0].fill_between(R.index, R[f"{col}_p25"] / 1e3, R[f"{col}_p75"] / 1e3, color=c_, alpha=.15)
    axs[0].set_xlabel("Mês de vida da unidade"); axs[0].set_ylabel("R$ mil/mês"); axs[0].set_title("Rampa por parte (faixa = metade central das unidades)"); axs[0].legend()
    axs[1].plot(R.index, 100 * R.pct_agregador_med, "k-o", ms=3); axs[1].set_xlabel("Mês de vida"); axs[1].set_ylabel("% da receita (mediana)")
    ax2 = axs[1].twinx(); ax2.bar(R.index, R.unidades, alpha=.15, color="gray"); ax2.set_ylabel("unidades com dado", color="gray"); ax2.grid(False)
    axs[1].set_title("Peso do agregador ao longo da vida da unidade")
    salvar(fig, "06_rampa_por_parte.png")
    planilhas["06_rampa"] = R

    # 7) mix por UF e por master
    fig, axs = plt.subplots(1, 2, figsize=(14, 5))
    for ax, grp, rot in ((axs[0], "uf", "estado"), (axs[1], "master", "master (anonimizada)")):
        cont = U[grp].value_counts(); keep = cont[cont >= 3].index
        ordem = U[U[grp].isin(keep)].groupby(grp).pct_agregador_receita.median().sort_values().index
        dados = [100 * U.loc[U[grp] == k, "pct_agregador_receita"] for k in ordem]
        ax.boxplot(dados, tick_labels=[f"{k}\n(n {cont[k]})" for k in ordem], showmeans=True)
        for i_, k in enumerate(ordem):
            ax.scatter(np.full((U[grp] == k).sum(), i_ + 1) + np.random.default_rng(1).uniform(-.12, .12, (U[grp] == k).sum()),
                       100 * U.loc[U[grp] == k, "pct_agregador_receita"], s=12, alpha=.6, color="k")
        ax.set_ylabel("% da receita vinda de agregador"); ax.set_title(f"Mix de agregador por {rot} (grupos com ≥ 3 unidades)")
    salvar(fig, "07_mix_por_uf_e_master.png")
    resumo = []
    for grp in ("uf", "master"):
        for k, s_ in U.groupby(grp):
            resumo.append({"agrupamento": grp, "grupo": k, "n": len(s_), "fat_mediano_mil": s_.faturamento.median() / 1e3, "balcao_mediano_mil": s_.B.median() / 1e3,
                           "agregador_mediano_mil": s_.AG.median() / 1e3, "pct_agregador_mediano": s_.pct_agregador_receita.median(),
                           "fat_por_m2_mediano": s_.fat_por_m2.median(), "ticket_balcao_mediano": s_.ticket_balcao.median(),
                           "rs_por_aluno_agregador_mediano": s_.rs_por_aluno_agregador.median()})
    planilhas["07_resumo_uf_master"] = pd.DataFrame(resumo)

    # 8) v2: real x previsto (39 LOO + 18 teste) e o modelo em duas partes
    V2 = ["l_m2", "l_renda_dom", "l_pop"] + DUM + ["studios"]
    b, e, hh, _ = ex.ols(tr.l_fat.to_numpy(float), tm.X_(tr, V2))
    loo = e / (1 - hh)
    prev_tr = np.exp(tr.l_fat - loo); prev_te = np.exp(tm.X_(te, V2) @ b + cal["l_fat"])
    fig, ax = plt.subplots(figsize=(8.5, 8))
    ax.scatter(prev_tr / 1e3, np.exp(tr.l_fat) / 1e3, s=35, color="#4c72b0", edgecolor="k", lw=.3, label="maduras 2025 (previsão sem a própria unidade)")
    ax.scatter(prev_te / 1e3, np.exp(te.l_fat) / 1e3, s=45, marker="s", color="#c44e52", edgecolor="k", lw=.3, label="teste 2026 (18)")
    for idx_, px, py in list(zip(tr.index, prev_tr / 1e3, np.exp(tr.l_fat) / 1e3)) + list(zip(te.index, prev_te / 1e3, np.exp(te.l_fat) / 1e3)):
        if abs(np.log(py / px)) > 0.35:
            ax.annotate(idx_, (px, py), fontsize=7, xytext=(3, 2), textcoords="offset points")
    lim = [80, 800]; ax.plot(lim, lim, "k-", lw=.8)
    for k in (1.25, 1 / 1.25):
        ax.plot(lim, [l * k for l in lim], "k:", lw=.6)
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(lim); ax.set_ylim(lim)
    ax.set_xlabel("Previsto pela v2 (R$ mil/mês)"); ax.set_ylabel("Real (R$ mil/mês)"); ax.legend(loc="upper left", fontsize=8)
    ax.set_title("v2: real × previsto. Linha cheia = acerto; pontilhadas = ±25%. Nome = erro maior que ~40%.")
    salvar(fig, "08_v2_real_x_previsto.png")
    planilhas["08_v2_real_previsto"] = pd.concat([pd.DataFrame({"grupo": "maduras 2025 (LOO)", "real": np.exp(tr.l_fat), "previsto_v2": prev_tr}),
                                                  pd.DataFrame({"grupo": "teste 2026", "real": np.exp(te.l_fat), "previsto_v2": prev_te}, index=te.index)]).assign(
        erro_pct=lambda D: 100 * (D.real / D.previsto_v2 - 1))

    # ---------------- planilha
    leia = pd.DataFrame({"campo": [
        "Fonte", "Janela do corte transversal", "Balcão", "Agregador", "Unidades maduras", "Metragem", "Renda e população", "DF+GO",
        "O que NÃO está aqui", "Gerado por"], "descrição": [
        "Painel do estudo BLK-UNI (Financeiro consolidado em fato_unidade_mes) e cadastro da VPS (dim_unidade).",
        f"Média mensal de {JAN[0]} a {JAN[1]}, só meses completos e com operação no mês cheio; unidade com ≥ 3 meses válidos.",
        "vendas_ux − tem_saude (Financeiro).", "gympass + totalpass (Financeiro).", "12 meses de vida ou mais em cada mês da janela.",
        "Oficial do cadastro; quando falta, a estimada por satélite de 29/09 (coluna m2_origem).",
        "Isócrona de 10 min de carro do pino corrigido; renda domiciliar = renda per capita × moradores por domicílio.",
        "As linhas tracejadas dos gráficos refazem a tendência sem DF e GO (Brasília concentra 30% das unidades).",
        "Nada da Base Consolidada nem de arquivos LOCAL_ (pasta sincronizada com a nuvem).",
        "data/analysis/uni/exploratoria/01_balcao_agregador.py (repositório motor-de-expansao)."]})
    with pd.ExcelWriter(OUT / "numeros_dos_graficos.xlsx") as w:
        leia.to_excel(w, sheet_name="LEIA-ME", index=False)
        for nome, df in planilhas.items():
            df.to_excel(w, sheet_name=nome[:31])
    print(f"ok: {len(U)} unidades maduras na janela; {len(list(OUT.glob('*.png')))} gráficos em {OUT}")


if __name__ == "__main__":
    main()
