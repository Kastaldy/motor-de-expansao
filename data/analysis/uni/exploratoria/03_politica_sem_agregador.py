# -*- coding: utf-8 -*-
"""Exploratoria do BLK-UNI, lote 3 (06/10): a politica da rede de NAO abrir com agregador (so' planos de balcao nos
primeiros meses), que veio com a inauguracao de Botafogo (mar/2025) e segue viva (informacao do Felipe, 06/10).
(a) unidades abertas sem agregador x com agregador desde o 1o mes, por mes de vida; (b) o que acontece com o balcao
quando o agregador entra depois da abertura. So' descritivo; grupos diferem em estado e epoca (ver LEIA-ME).
Fontes: fato_unidade_mes (Growth + Financeiro). NADA da Base Consolidada nem de LOCAL_ vai para o OneDrive.
Uso: 03_politica_sem_agregador.py  (.venv)."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

AQUI = Path(__file__).resolve().parent
UNI = AQUI.parent
OUT = Path(r"C:\Users\Felipe\OneDrive - Grupo Ultra\Área de Trabalho\Análises - Motor de Expansão\Exploratória BLK-UNI\03 - Política sem agregador na abertura")
plt.rcParams.update({"figure.dpi": 110, "savefig.dpi": 150, "font.size": 9, "axes.grid": True, "grid.alpha": .3})
G_SEM, G_COM = "sem agregador nos 3 primeiros meses", "com agregador desde o 1º mês (aberturas de 2024 em diante)"
COR = {G_SEM: "#c44e52", G_COM: "#4c72b0"}


def salvar(fig, nome):
    fig.tight_layout(); fig.savefig(OUT / nome, bbox_inches="tight"); plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    d = pd.read_parquet(UNI / "dim_unidade.parquet")
    d = d[~d.excluida_rede].set_index("unidade_id")
    f = pd.read_parquet(UNI / "fato_unidade_mes.parquet")
    f = f[f.unidade_id.isin(d.index) & f.mes_vida.notna() & ~f.flag_inauguracao_placeholder.fillna(False).astype(bool)].copy()
    f["B"] = f.fin_vendas_ux - f.fin_tem_saude.fillna(0)
    f["AG"] = f.fin_gympass.fillna(0) + f.fin_totalpass.fillna(0)
    f["pas"] = f.passagens_gympass + f.passagens_totalpass
    f["alunos_ag"] = f.alunos_gympass + f.alunos_totalpass
    fin_ok = f.fin_vendas_ux.notna() & f.mes_completo.astype(bool)

    # ---------- grupos por unidade
    rows = []
    for u, g in f.groupby("unidade_id"):
        if not (g.mes_vida == 1).any():
            continue
        first = g[g.pas > 0].mes_vida.min()
        rows.append({"unidade_id": u, "inauguracao": str(g.inauguracao_competencia.iloc[0]), "uf": g.uf.iloc[0],
                     "mes_vida_1o_agregador": first, "ultimo_mes_vida": g.mes_vida.max()})
    Gr = pd.DataFrame(rows).set_index("unidade_id")
    sem = (Gr.mes_vida_1o_agregador.isna() | (Gr.mes_vida_1o_agregador > 3)) & (Gr.ultimo_mes_vida >= 3)
    com = (Gr.mes_vida_1o_agregador <= 1) & (Gr.inauguracao >= "2024-01")
    Gr["grupo"] = np.where(sem, G_SEM, np.where(com, G_COM, "fora da comparação"))
    Gr["df_go"] = Gr.uf.isin(["DF", "GO"])
    Gr = Gr.sort_values(["grupo", "inauguracao"])

    # ---------- (a) curvas por mes de vida
    h = f[fin_ok & f.mes_vida.between(1, 12)].join(Gr[["grupo", "df_go"]], on="unidade_id")
    h = h[h.grupo.isin(list(COR))].copy(); h["df_go"] = h.df_go.astype(bool)
    met = (("pagantes", "Pagantes (alunos de balcão)", 1), ("B", "Balcão (R$ mil/mês)", 1e3), ("AG", "Agregador (R$ mil/mês)", 1e3),
           ("faturamento", "Faturamento total (R$ mil/mês)", 1e3))
    fig, axs = plt.subplots(2, 2, figsize=(15, 10))
    curvas = []
    for ax, (col, rot, div) in zip(axs.flat, met):
        for gname, c_ in COR.items():
            for todas, est in ((True, "-o"), (False, "--")):
                s_ = h[(h.grupo == gname) & (todas | ~h.df_go)]
                q = s_.groupby("mes_vida")[col].agg(["median", "size"])
                ax.plot(q.index, q["median"] / div, est, ms=3, color=c_, lw=1.4 if todas else .9,
                        label=f"{gname}{'' if todas else ' — sem DF+GO'}")
                if todas:
                    for x_, (m_, n_) in q.iterrows():
                        ax.annotate(f"{int(n_)}", (x_, m_ / div), fontsize=6, color=c_, xytext=(0, 5), textcoords="offset points", ha="center")
                    curvas.append(q.assign(metrica=col, grupo=gname).reset_index())
        ax.set_xlabel("mês de vida"); ax.set_ylabel(rot); ax.set_title(rot + " — mediana por mês de vida (número = unidades)")
    axs[0, 0].legend(fontsize=7)
    fig.suptitle("Abrir sem agregador × abrir com agregador: as mesmas medidas ao longo dos 12 primeiros meses", y=1.01)
    salvar(fig, "01_curvas_sem_x_com_agregador.png")

    # ---------- (a2) balcao por m2 e mix no mes 6 e 12, unidade a unidade
    met2 = d.tam_metragem_m2
    pts = []
    for k in (3, 6, 12):
        s_ = h[h.mes_vida == k]
        for r in s_.itertuples():
            pts.append({"unidade_id": r.unidade_id, "mes_vida": k, "grupo": r.grupo, "uf": r.uf, "pagantes": r.pagantes, "balcao": r.B, "agregador": r.AG,
                        "faturamento": r.faturamento, "pct_agregador": r.AG / (r.B + r.AG) if (r.B + r.AG) > 0 else np.nan,
                        "pagantes_por_m2": r.pagantes / met2.get(r.unidade_id, np.nan)})
    PT = pd.DataFrame(pts)
    fig, axs = plt.subplots(1, 3, figsize=(17, 6))
    for ax, k in zip(axs, (3, 6, 12)):
        s_ = PT[PT.mes_vida == k]
        for j, gname in enumerate(COR):
            v = s_[s_.grupo == gname]
            x = np.full(len(v), j) + np.random.default_rng(k + j).uniform(-.15, .15, len(v))
            ax.scatter(x, v.faturamento / 1e3, color=COR[gname], s=30, edgecolor="k", lw=.3)
            for xx, (_, r) in zip(x, v.iterrows()):
                ax.annotate(r.unidade_id[:16], (xx, r.faturamento / 1e3), fontsize=5.5, alpha=.75, xytext=(3, 0), textcoords="offset points")
            if len(v):
                ax.hlines(v.faturamento.median() / 1e3, j - .3, j + .3, color=COR[gname], lw=2)
        ax.set_xticks([0, 1]); ax.set_xticklabels([f"sem agregador\n(n {int((s_.grupo == G_SEM).sum())})", f"com agregador\n(n {int((s_.grupo == G_COM).sum())})"])
        ax.set_ylabel("faturamento (R$ mil/mês)"); ax.set_title(f"Mês de vida {k}: faturamento unidade a unidade (traço = mediana)")
    salvar(fig, "02_faturamento_mes_3_6_12_por_unidade.png")

    # ---------- (b) o que acontece com o balcao quando o agregador entra depois da abertura
    ev = Gr[(Gr.mes_vida_1o_agregador >= 2)].copy()
    ev["competencia_entrada"] = [f[(f.unidade_id == u) & (f.mes_vida == m)].competencia.iloc[0] for u, m in zip(ev.index, ev.mes_vida_1o_agregador)]
    ev = ev[ev.inauguracao >= "2025-01"].sort_values("competencia_entrada")
    n = len(ev); cols = 3; lin = int(np.ceil(n / cols)) if n else 1
    fig, axs = plt.subplots(lin, cols, figsize=(17, 3.8 * lin), squeeze=False)
    evt = []
    for ax, (u, r) in zip(axs.flat, ev.iterrows()):
        g = f[f.unidade_id == u].sort_values("competencia")
        x = np.arange(len(g))
        ax.plot(x, g.pagantes, "-o", ms=3, color="#4c72b0", label="pagantes (balcão)")
        ax.plot(x, g.alunos_ag, "-o", ms=3, color="#dd8452", label="alunos de agregador")
        parc = ~g.mes_completo.astype(bool).to_numpy()
        ax.scatter(x[parc], g.pagantes.to_numpy()[parc], s=40, facecolor="none", edgecolor="k", zorder=3, label="mês parcial")
        i0 = int(np.where(g.competencia.to_numpy() == r.competencia_entrada)[0][0])
        ax.axvline(i0, color="k", ls=":", lw=1)
        ax.set_xticks(x[::2]); ax.set_xticklabels(g.competencia.iloc[::2], rotation=45, fontsize=7)
        ax.set_title(f"{u} ({r.uf}) — agregador entra no mês de vida {int(r.mes_vida_1o_agregador)} ({r.competencia_entrada})", fontsize=8)
        antes = g[(g.competencia < r.competencia_entrada) & g.mes_completo.astype(bool)].pagantes.tail(2)
        depois = g[(g.competencia > r.competencia_entrada) & g.mes_completo.astype(bool)].pagantes.head(2)
        evt.append({"unidade_id": u, "uf": r.uf, "mes_vida_entrada": r.mes_vida_1o_agregador, "competencia_entrada": r.competencia_entrada,
                    "pagantes_2m_antes": antes.mean() if len(antes) else np.nan, "pagantes_2m_depois": depois.mean() if len(depois) else np.nan,
                    "meses_completos_depois": int(len(g[(g.competencia > r.competencia_entrada) & g.mes_completo.astype(bool)]))})
    for ax in list(axs.flat)[n:]:
        ax.axis("off")
    if n:
        list(axs.flat)[0].legend(fontsize=7)
    fig.suptitle("Unidades abertas desde 2025 em que o agregador entrou DEPOIS da abertura: o balcão cai quando ele entra? (pontilhado = 1º mês com passagem)", y=1.01)
    salvar(fig, "03_balcao_quando_o_agregador_entra.png")
    EV = pd.DataFrame(evt)
    if len(EV):
        EV["var_pagantes_pct"] = 100 * (EV.pagantes_2m_depois / EV.pagantes_2m_antes - 1)

    C = pd.concat(curvas)
    leia = pd.DataFrame({"campo": ["Pergunta", "Grupos", "Com agregador", "Mês de vida", "Cuidado", "O que NÃO está aqui", "Gerado por"], "descrição": [
        "A política da rede de abrir só com planos de balcão (desde Botafogo, mar/2025) muda a rampa e o patamar? E o balcão quando o agregador entra?",
        f"'{G_SEM}': nenhuma passagem de agregador (Growth) nos meses de vida 1–3, com pelo menos 3 meses de vida. "
        f"'{G_COM}': passagem já no mês 1 e inauguração em 2024 ou depois. As demais ficam fora da comparação (aba grupos).",
        "Agregador = Wellhub + TotalPass. Passagens vêm da Growth; R$ vêm do Financeiro (até ago/2026).",
        "Mês 1 = primeiro mês completo depois da inauguração. Só meses completos entram nas medianas.",
        "Os grupos diferem em ESTADO (o sem agregador tem muito RJ; o com agregador, muito DF/GO) e em ÉPOCA (2026 × 2024–25). "
        "Leitura descritiva, não efeito causal. Os tracejados refazem sem DF+GO. Poucas unidades sem agregador passaram do mês 9.",
        "Nada da Base Consolidada nem de arquivos LOCAL_ (pasta sincronizada com a nuvem).",
        "data/analysis/uni/exploratoria/03_politica_sem_agregador.py (repositório motor-de-expansao)."]})
    with pd.ExcelWriter(OUT / "numeros_dos_graficos.xlsx") as w:
        leia.to_excel(w, sheet_name="LEIA-ME", index=False)
        Gr.to_excel(w, sheet_name="grupos")
        C.to_excel(w, sheet_name="01_curvas", index=False)
        PT.to_excel(w, sheet_name="02_mes_3_6_12", index=False)
        EV.to_excel(w, sheet_name="03_entrada_do_agregador", index=False)
    print(Gr.grupo.value_counts().to_string())
    print(Gr[Gr.grupo == G_SEM][["inauguracao", "uf", "mes_vida_1o_agregador", "ultimo_mes_vida"]].to_string())
    piv = C.pivot_table(index=["metrica", "mes_vida"], columns="grupo", values=["median", "size"]).loc[(slice(None), [1, 3, 6, 9, 12]), :]
    print(piv.round(0).to_string())
    print(EV.round(1).to_string())
    print(f"ok: {len(list(OUT.glob('*.png')))} gráficos em {OUT}")


if __name__ == "__main__":
    main()
