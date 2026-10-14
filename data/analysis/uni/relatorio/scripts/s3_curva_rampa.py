"""s3_curva_rampa — a rampa real é bem mais rápida que a do simulador: 68% do nível maduro no 1º mês, contra 37%.

Fontes: uni03/curva_uni03.csv (séries 'ativos' e 'faturamento'; p10/p50/p90 em fração do nível maduro, meses
11–13); uni03/resultado_uni03.md (coluna 'simulador hoje*' da tabela P1; participação do agregador; P4).
"""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _estilo import *  # noqa: E402,F403

ID = "s3_curva_rampa"
CURVA = pd.read_csv(UNI / "uni03" / "curva_uni03.csv", sep=";", encoding="utf-8-sig")
MD = (UNI / "uni03" / "resultado_uni03.md").read_text(encoding="utf-8")

at = CURVA[CURVA["serie"].eq("ativos")].set_index("k")
fa = CURVA[CURVA["serie"].eq("faturamento")].set_index("k")
p1 = tabela_md(MD, "| mês | alunos (mediana) |")
p1["mês"] = p1["mês"].astype(int)
sim = p1.set_index("mês")["simulador hoje*"].map(lambda s: np.nan if s.strip() in ("–", "-") else numero_br(s))
agr = [int(x) for x in re.search(r"Participação do agregador nos meses 1/3/6/12: (\d+)% / (\d+)% / (\d+)% / (\d+)%",
                                  MD).groups()]
nivel = numero_br(re.search(r"Nível maduro mediano \(exploração, meses 11–13\): ([\d,\.]+) alunos", MD).group(1))
n_expl = int(re.search(r"Exploração \(monta a curva\): \*\*(\d+) unidades\*\*", MD).group(1))
p4 = tabela_md(MD, "| mês | N | mediana | p10 | p90 |")
p4["mês"] = p4["mês"].astype(int)
p4 = p4.set_index("mês")
estavel = int(re.search(r"Nível dos meses 22–24 sobre o dos meses 11–13 \(mediana, \d+ unidades\): (\d+)%", MD).group(1))

# ------------------------------------------------------------------ conferência
conferir("alunos p50 no mês 0 (%)", round(at.loc[0, "p50"] * 100), 80)
conferir("alunos p50 no mês 1 (%)", round(at.loc[1, "p50"] * 100), 68)
conferir("alunos p50 no mês 6 (%)", round(at.loc[6, "p50"] * 100), 92)
conferir("faturamento p50 no mês 1 (%)", round(fa.loc[1, "p50"] * 100), 52)
conferir("unidades no mês 0", int(at.loc[0, "n"]), 8)
conferir("unidades nos meses 1–12", int(at.loc[1:12, "n"].min()), 33)
conferir("unidades da exploração", n_expl, 33)
conferir("simulador no mês 1 (%)", sim.loc[1], 37)
conferir("simulador soma meses 1–12 (%)", sim.loc[1:12].sum(), 37 + 47 + 57 + 66 + 76 + 86 + 95 + 100 * 5)
conferir("agregador nos meses 1/3/6/12 (%)", agr[0] * 1e6 + agr[1] * 1e4 + agr[2] * 1e2 + agr[3],
         18 * 1e6 + 24 * 1e4 + 24 * 1e2 + 26)
conferir("nível maduro mediano (alunos)", nivel, 2213)
conferir("nível mediano do mês 12 ao 24 (%)", estavel, 101)
# conversão do simulador (uni03/01_curva_rampa.py): 500 + (nível − 500) × (k + f0)/8, com f0 = 0,53 (abre no meio do mês)
F0 = 0.53
sim1_recalc = 100 * (500 + (nivel - 500) * min((1 + F0) / 8, 1)) / nivel
conferir("simulador no mês 1 recalculado com k + 0,53 (%)", round(sim1_recalc), 37)
conferir("500 / nível maduro (sem o tempo de operação) (%)", round(100 * 500 / nivel), 23)
# a tabela P1 do .md bate com o CSV
for k in (1, 3, 6, 12):
    conferir(f"P1 do .md = CSV no mês {k} (alunos, %)", numero_br(p1.set_index("mês").loc[k, "alunos (mediana)"]),
             round(at.loc[k, "p50"] * 100))

# ------------------------------------------------------------------ figura
fig = figura()
y_topo = cabecalho(
    fig,
    "A rampa real é bem mais rápida que a do simulador: 68% do nível maduro no 1º mês, contra 37%",
    "Alunos ativos e faturamento no 1º ano, em % do nível maduro; mediana e faixa normal (p10–p90) de 33 unidades "
    "abertas até nov/2024",
)
y_base = rodape(
    fig,
    f"Fonte: uni03/curva_uni03.csv; uni03/resultado_uni03.md · N = {n_expl} (8 no mês 0) · nível maduro = média dos "
    f"meses 11–13; nível maduro mediano {num(nivel)} alunos",
)
ax = fig.add_axes([0.075, y_base + 0.085, 0.6, y_topo - y_base - 0.11])
eixo_limpo(ax, grade="y")

ks = np.arange(1, 13)
Y = lambda s: s * 100  # noqa: E731
# faixa p10–p90 dos alunos
ax.fill_between(ks, Y(at.loc[1:12, "p10"]), Y(at.loc[1:12, "p90"]), color=DESTAQUE, alpha=0.13, lw=0, zorder=1,
                label="alunos: faixa normal (p10–p90)")
ax.axhline(100, color=CINZA, lw=0.9, zorder=1)
ax.text(12.45, 100, "nível\nmaduro", ha="left", va="center", fontsize=TAM_NOTA - 1, color=CINZA_ESCURO,
        linespacing=1.1)
# simulador
ax.plot(ks, sim.loc[1:12].to_numpy(), color=CINZA_ESCURO, lw=1.8, marker="o", ms=4.2, zorder=3,
        label="simulador hoje")
# faturamento
ax.plot(ks, Y(fa.loc[1:12, "p50"]), color=CINZA, lw=2.0, ls=(0, (5, 3)), zorder=3, label="faturamento (mediana)")
# alunos
ax.plot(ks, Y(at.loc[1:12, "p50"]), color=DESTAQUE, lw=2.8, zorder=4, label="alunos ativos (mediana)")
ax.plot([0, 1], [Y(at.loc[0, "p50"]), Y(at.loc[1, "p50"])], color=DESTAQUE, lw=1.4, ls=(0, (1.5, 2)), zorder=4)
ax.plot([0, 0], [Y(at.loc[0, "p10"]), Y(at.loc[0, "p90"])], color=DESTAQUE, lw=1.0, alpha=0.5, zorder=2)
ax.scatter([0], [Y(at.loc[0, "p50"])], s=58, facecolor="white", edgecolor=DESTAQUE, lw=1.8, zorder=5)
# nota do mês 0, no alto (acima da faixa)
ax.plot([0, 0], [Y(at.loc[0, "p90"]), 106.5], color=DESTAQUE, lw=0.8, alpha=0.5, ls=(0, (1.5, 2)), zorder=2)
ax.text(-0.35, 107.5, "mês 0 = inauguração: pré-venda; só 8 unidades", ha="left", va="bottom",
        fontsize=TAM_NOTA - 0.5, color=CINZA_ESCURO)


# valores nos meses 0, 1 e 6
def rot(x, yv, txt, cor, ha="right", dx=-0.13, dy=0, peso="bold"):
    ax.text(x + dx, yv + dy, txt, ha=ha, va="center", fontsize=TAM_NOTA, color=cor, fontweight=peso, zorder=6,
            bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.9))


rot(0, Y(at.loc[0, "p50"]), pct(Y(at.loc[0, "p50"])), DESTAQUE, ha="center", dx=0, dy=5)
rot(1, Y(at.loc[1, "p50"]), pct(Y(at.loc[1, "p50"])), DESTAQUE, dx=-0.16, dy=-2.5)
rot(1, Y(fa.loc[1, "p50"]), pct(Y(fa.loc[1, "p50"])), CINZA_ESCURO, dx=-0.16)
rot(1, sim.loc[1], pct(sim.loc[1]), CINZA_ESCURO, dx=-0.16)
rot(6, Y(at.loc[6, "p50"]), pct(Y(at.loc[6, "p50"])), DESTAQUE, ha="center", dx=0, dy=5)

# anotações (área vazia embaixo, à esquerda)
x_queda = 0.2
y_queda = Y(at.loc[0, "p50"]) + (Y(at.loc[1, "p50"]) - Y(at.loc[0, "p50"])) * x_queda
ax.annotate("queda do mês 1: parece pré-venda que não renova —\na confirmar com o Lifetime",
            xy=(x_queda, y_queda - 1.2), xytext=(-0.35, 17), ha="left", va="center", fontsize=TAM_NOTA,
            color=TEXTO, linespacing=1.15,
            arrowprops=dict(arrowstyle="-", color=CINZA, lw=0.8, shrinkA=0, shrinkB=1, relpos=(0.095, 1.0)))
ax.annotate(f"o faturamento anda mais devagar que os alunos\n({pct(Y(fa.loc[1, 'p50']))} × "
            f"{pct(Y(at.loc[1, 'p50']))} no mês 1): o ticket começa baixo",
            xy=(1.12, Y(fa.loc[1, "p50"]) - 2.5), xytext=(2.2, 30), ha="left", va="center", fontsize=TAM_NOTA,
            color=TEXTO, linespacing=1.15,
            arrowprops=dict(arrowstyle="-", color=CINZA, lw=0.8, shrinkA=0, shrinkB=1, relpos=(0.0, 0.5)))

ax.set_xlim(-0.6, 12.4)
ax.set_ylim(0, 116)
ax.set_xticks(range(0, 13))
ax.set_yticks(range(0, 101, 20))
ax.yaxis.set_major_formatter(formatador_num(0, "%"))
ax.set_xlabel("mês de vida da unidade (0 = mês da inauguração)", fontsize=TAM_NOTA, color=CINZA_ESCURO)
ax.set_ylabel("% do nível maduro (meses 11–13)", fontsize=TAM_NOTA, color=CINZA_ESCURO)
h, lab = ax.get_legend_handles_labels()
ordem = [lab.index(x) for x in ["alunos ativos (mediana)", "alunos: faixa normal (p10–p90)",
                                 "faturamento (mediana)", "simulador hoje"]]


# coluna de notas à direita
x_col, w_col = 0.715, 1 - MARGEM_X - 0.715
yb = caixa(fig, x_col, y_topo - 0.02, w_col,
           f"A unidade abre com ~{pct(Y(at.loc[0, 'p50']))} do nível maduro, cai para "
           f"{pct(Y(at.loc[1, 'p50']))} no 1º mês e chega a {pct(Y(at.loc[6, 'p50']))} no 6º. "
           f"O simulador supõe {pct(sim.loc[1])} no mês 1.",
           tamanho=TAM_NOTA + 0.5, fundo=DESTAQUE_MUITO_CLARO, barra=DESTAQUE, titulo="O que a curva mostra")
yb = caixa(fig, x_col, yb - 0.02, w_col,
           f"O agregador entra devagar: {agr[0]}% dos alunos no mês 1, {agr[1]}% no 3º, {agr[2]}% no 6º e "
           f"{agr[3]}% no mês 12.", tamanho=TAM_NOTA)
yb = caixa(fig, x_col, yb - 0.02, w_col,
           f"Do mês 12 ao 24, o nível mediano fica estável ({estavel}%), mas a dispersão abre: a faixa normal vai de "
           f"{p4.loc[13, 'p10']}–{p4.loc[13, 'p90']} no mês 13 para {p4.loc[24, 'p10']}–{p4.loc[24, 'p90']} "
           f"no mês 24.", tamanho=TAM_NOTA)
yb = caixa(fig, x_col, yb - 0.02, w_col,
           f"Simulador hoje: 500 alunos no 1º mês e reta até o mês 8. No mesmo tempo de operação das unidades "
           f"reais (abrem no meio do mês: o mês 1 tem ~1,5 mês de portas abertas), isso dá {pct(sim.loc[1])} do "
           f"nível maduro mediano ({num(nivel)} alunos) no mês 1.", tamanho=TAM_NOTA, cor_texto=CINZA_ESCURO)

fig.legend([h[i] for i in ordem], [lab[i] for i in ordem], loc="upper left", bbox_to_anchor=(x_col, yb - 0.025),
           fontsize=TAM_NOTA - 0.5, handlelength=2.2, labelspacing=0.5, borderaxespad=0, borderpad=0)

# ------------------------------------------------------------------ dados
k_all = np.arange(0, 13)
dados = pd.DataFrame({
    "k": k_all,
    "n_unidades": at.loc[k_all, "n"].to_numpy(),
    "alunos_p10_pct": Y(at.loc[k_all, "p10"]).round(1).to_numpy(),
    "alunos_p50_pct": Y(at.loc[k_all, "p50"]).round(1).to_numpy(),
    "alunos_p90_pct": Y(at.loc[k_all, "p90"]).round(1).to_numpy(),
    "faturamento_p50_pct": Y(fa.reindex(k_all)["p50"]).round(1).to_numpy(),
    "simulador_hoje_pct": sim.reindex(k_all).to_numpy(),
})
dados["agregador_pct_dos_alunos"] = dados["k"].map({1: agr[0], 3: agr[1], 6: agr[2], 12: agr[3]})
salvar(fig, ID, dados)
