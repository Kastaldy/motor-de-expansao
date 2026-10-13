"""s5_agregador — o agregador troca ticket por volume com saldo pequeno; a premissa de 60% fica.

Fontes:
- uni01/resultado_uni01.md: T06 (alunos), T07 (ticket), T18 (cancelamento), sensibilidades A (maturidade ajustada)
  e B (jan–set/2025); desvio-padrão da fatia de agregador (0,176);
- alavancas/resultado_alavancas.md, seção D: receita mensal por aluno (R$ 62 × R$ 136), ρ = 47%, Wellhub e TotalPass;
- CADERNO_ESTUDO_UNI.md, etapa 10: decisão do dono (29/09) de manter a premissa de 60% (medição manual ≈ 60%, sem
  arquivo no estudo).
Faturamento = conta (1 + alunos) × (1 + ticket) − 1, sem IC.
"""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _estilo import *  # noqa: E402,F403
from _estilo import _cracha  # noqa: E402

ID = "s5_agregador"
R01 = (UNI / "uni01" / "resultado_uni01.md").read_text(encoding="utf-8")
ALV = (UNI / "alavancas" / "resultado_alavancas.md").read_text(encoding="utf-8")
CAD = (UNI / "CADERNO_ESTUDO_UNI.md").read_text(encoding="utf-8")

t = tabela_md(R01, "| teste | destino |").set_index("teste")


def ic(s):
    lo, hi = s.strip("[]").split(",")
    return numero_br(lo.replace("pp", "")), numero_br(hi.replace("pp", ""))


def linha(tid):
    r = t.loc[tid]
    e = numero_br(r["efeito"].replace("pp", ""))
    lo, hi = ic(r["IC 90%"])
    return e, lo, hi, numero_br(r["A"].replace("pp", "")), numero_br(r["B"].replace("pp", "")), int(r["N"])


alu, tic, chu = linha("T06"), linha("T07"), linha("T18")
dp_agr = float(re.search(r"% agregador (\d\.\d+)", R01).group(1))

# ------------------------------------------------------------------ conferência
for nome, v, e in [("T06 alunos", alu, (17.9, 8.5, 28.0, 5.8, 18.5)), ("T07 ticket", tic, (-10.4, -12.9, -7.9, -9.8, -10.5)),
                   ("T18 cancelamento", chu, (0.64, 0.18, 1.11, 0.59, 0.76))]:
    for k, parte in enumerate(("efeito", "IC inf.", "IC sup.", "sens. A", "sens. B")):
        conferir(f"{nome}: {parte}", v[k], e[k])
conferir("N (maduras de 2025)", alu[5], 39)
conferir("desvio-padrão da fatia de agregador", dp_agr, 0.176)
fat = (1 + alu[0] / 100) * (1 + tic[0] / 100) - 1
fat_a = (1 + alu[3] / 100) * (1 + tic[3] / 100) - 1
fat_b = (1 + alu[4] / 100) * (1 + tic[4] / 100) - 1
conferir("faturamento pela conta (%)", round(100 * fat, 1), 5.6)
conferir("faturamento com a maturidade ajustada (≈ −5%)", round(100 * fat_a), -5, 0.5)

rec_agr = float(re.search(r"aluno de agregador: \*\*R\$ (\d+)\*\*", ALV).group(1))
rec_rec = float(re.search(r"Por recorrente: \*\*R\$ (\d+)\*\*", ALV).group(1))
rho = float(re.search(r"\*\*ρ = (\d+)%", ALV).group(1))
wh = float(re.search(r"Wellhub (\d+)% \(\d+ meses\)", ALV).group(1))
tp = float(re.search(r"TotalPass (\d+)% \(\d+ meses\)", ALV).group(1))
m = re.search(r"(\d+) meses de (\d+) unidades maduras em 2025", ALV)
n_meses, n_unid = int(m.group(1)), int(m.group(2))
conferir("receita por aluno de agregador (R$)", rec_agr, 62)
conferir("receita por recorrente (R$)", rec_rec, 136)
conferir("ρ mediano (%)", rho, 47)
conferir("Wellhub (%)", wh, 47)
conferir("TotalPass (%)", tp, 50)
conferir("meses", n_meses, 418)
conferir("unidades", n_unid, 43)
conferir("caderno: decisão de manter 60%", int("a premissa do agregador fica em 60%" in CAD), 1)
premissa = 0.60 * rec_rec
conferir("premissa 60% × R$ 136 (R$)", round(premissa), 82)

# ------------------------------------------------------------------ figura
fig = figura()
y_topo = cabecalho(
    fig,
    "O agregador troca ticket por volume com saldo pequeno; a premissa de 60% fica",
    f"Associação da fatia de agregador em {alu[5]} unidades maduras de 2025 e receita por aluno em {n_meses} meses "
    f"de {n_unid} unidades; IC 90%",
)
y_base = rodape(
    fig,
    f"Fonte: uni01/resultado_uni01.md (T06, T07, T18); alavancas/resultado_alavancas.md (seção D); decisão do dono em "
    f"29/09 · N = {alu[5]}; {n_unid} · IC 90% · sensibilidades: A = maturidade ajustada (55 unidades), "
    "B = jan–set/2025",
    nota="Toda conta com a contagem de alunos de agregador carrega a ressalva de que ela não é 100% limpa; o modelo de "
    "faturamento (v2) não é afetado, porque prevê o faturamento do Financeiro direto.",
)

# ---------------- painel esquerdo
X_L0, X_L1 = 0.215, 0.53
y_pt = y_topo - 0.01
fig.text(MARGEM_X, y_pt, "Efeito de 1 degrau típico a mais de agregador", ha="left", va="top", fontsize=TAM_TEXTO,
         fontweight="bold", color=TEXTO)
fig.text(MARGEM_X, y_pt - 0.03, f"= +{num(100 * dp_agr, 1)} pontos na fatia de alunos ativos (1 desvio-padrão entre "
         "unidades)", ha="left", va="top", fontsize=TAM_NOTA, color=CINZA_ESCURO)
_cracha(fig, 0.56, y_pt + 0.002, "EXPLORATÓRIO", AMBAR)
h_pt = 0.075
ax_bot_c = y_base + 0.085
ax_h_c = 0.085
ax_bot = ax_bot_c + ax_h_c + 0.07
ax = fig.add_axes([X_L0, ax_bot, X_L1 - X_L0, y_pt - h_pt - ax_bot])
eixo_limpo(ax, grade="x")
ax.spines["left"].set_visible(False)
ax.set_facecolor("none")
linhas = [
    ("alunos ativos", alu, CINZA_ESCURO, False),
    ("ticket médio", tic, CINZA_ESCURO, False),
    ("faturamento (conta, sem IC)", (100 * fat, np.nan, np.nan, 100 * fat_a, 100 * fat_b), DESTAQUE, True),
]
for i, (rot, v, cor, conta) in enumerate(linhas):
    e = v[0]
    if conta:
        ax.barh(i, e, height=0.5, color="white", edgecolor=cor, hatch="////", lw=1.2, zorder=2)
    else:
        ax.barh(i, e, height=0.5, color=misturar(cor, 0.35), edgecolor="none", zorder=2)
        ax.plot([v[1], v[2]], [i, i], color=cor, lw=2.2, zorder=3, solid_capstyle="round")
        ax.scatter(e, i, s=48, color=cor, edgecolor="white", lw=1.0, zorder=4)
    for sv in (v[3], v[4]):
        ax.scatter(sv, i, s=40, facecolor="white", edgecolor=cor, lw=1.4, zorder=5)
    if conta:
        sub = f"≈ {num(e, 1, sinal=True)}%  (1,179 × 0,896 − 1)"
    else:
        sub = f"{num(e, 1, sinal=True)}%  [{num(v[1], 1, sinal=True)}; {num(v[2], 1, sinal=True)}]"
    ax.text(-17.5, i - 0.08, rot, ha="right", va="bottom", fontsize=TAM_NOTA + 0.5,
            color=DESTAQUE if conta else TEXTO, fontweight="bold")
    ax.text(-17.5, i + 0.02, sub, ha="right", va="top", fontsize=TAM_NOTA - 0.5,
            color=DESTAQUE if conta else CINZA_ESCURO)
ax.set_ylim(2.6, -0.6)
ax.set_xlim(-16, 32)
ax.set_xticks([-10, 0, 10, 20, 30])
ax.xaxis.set_major_formatter(formatador_num(0, "%", sinal=True))
ax.set_yticks([])
ax.axvline(0, color=TEXTO, lw=1.0, zorder=1)
# anotações das sensibilidades
ax.annotate(f"{num(alu[3], 1, sinal=True)}% com a\nmaturidade ajustada", xy=(alu[3], 0), xytext=(-1.5, -0.45),
            ha="right", va="center", fontsize=TAM_NOTA - 1, color=CINZA_ESCURO, linespacing=1.1,
            arrowprops=dict(arrowstyle="-", color=CINZA, lw=0.7, shrinkA=1, shrinkB=4))
ax.annotate(f"com a maturidade ajustada ≈ {num(round(100 * fat_a), 0)}%", xy=(100 * fat_a, 2), xytext=(-1.0, 2.42),
            ha="right", va="center", fontsize=TAM_NOTA - 1, color=DESTAQUE,
            arrowprops=dict(arrowstyle="-", color=DESTAQUE, lw=0.7, shrinkA=1, shrinkB=4))
ax.text(31.5, 2.42, "o saldo pode sumir", ha="right", va="center", fontsize=TAM_NOTA - 0.5, color=DESTAQUE,
        fontweight="bold")
ax.text(1.0, 1.0, "← firme: intervalo longe de zero", ha="left", va="center", fontsize=TAM_NOTA - 0.5,
        color=CINZA_ESCURO, style="italic")

# cancelamento, eixo próprio
axc = fig.add_axes([X_L0, ax_bot_c, X_L1 - X_L0, ax_h_c])
eixo_limpo(axc, grade="x")
axc.spines["left"].set_visible(False)
axc.set_facecolor("none")
axc.barh(0, chu[0], height=0.5, color=misturar(CINZA_ESCURO, 0.35), edgecolor="none", zorder=2)
axc.plot([chu[1], chu[2]], [0, 0], color=CINZA_ESCURO, lw=2.2, zorder=3, solid_capstyle="round")
axc.scatter(chu[0], 0, s=48, color=CINZA_ESCURO, edgecolor="white", lw=1.0, zorder=4)
for sv in (chu[3], chu[4]):
    axc.scatter(sv, 0, s=40, facecolor="white", edgecolor=CINZA_ESCURO, lw=1.4, zorder=5)
axc.set_xlim(-0.5, 1.5)
axc.set_ylim(0.6, -0.6)
axc.set_xticks([0, 0.5, 1.0, 1.5])
axc.xaxis.set_major_formatter(formatador_num(1, sinal=True))
axc.set_yticks([])
axc.axvline(0, color=TEXTO, lw=1.0, zorder=1)
axc.set_xlabel("pontos de cancelamento mensal (média ~7% ao mês)", fontsize=TAM_NOTA - 0.5, color=CINZA_ESCURO,
               labelpad=2)
axc.text(-0.547, -0.08, "cancelamento", ha="right", va="bottom", fontsize=TAM_NOTA + 0.5, color=TEXTO,
         fontweight="bold")
axc.text(-0.547, 0.02, f"{num(chu[0], 2, sinal=True)} ponto  [{num(chu[1], 2, sinal=True)}; "
         f"{num(chu[2], 2, sinal=True)}]", ha="right", va="top", fontsize=TAM_NOTA - 0.5, color=CINZA_ESCURO)
fig.text(X_L1, ax_bot - 0.045, "○ sensibilidades A e B", ha="right", va="center", fontsize=TAM_NOTA - 1,
         color=CINZA_ESCURO)

# ---------------- painel direito
X_R0, X_R1 = 0.64, 1 - MARGEM_X
fig.add_artist(matplotlib.lines.Line2D([0.585, 0.585], [y_base + 0.03, y_pt], color=CINZA_CLARO, lw=0.8))
fig.text(0.61, y_pt, "Receita mensal por aluno", ha="left", va="top", fontsize=TAM_TEXTO, fontweight="bold",
         color=TEXTO)
fig.text(0.61, y_pt - 0.03, "receita do Financeiro ÷ contagem de alunos do sistema", ha="left", va="top",
         fontsize=TAM_NOTA, color=CINZA_ESCURO)
axr = fig.add_axes([X_R0, y_base + 0.085, X_R1 - X_R0, y_pt - h_pt - y_base - 0.085])
eixo_limpo(axr, grade="y")
axr.set_facecolor("none")
xs = [0, 1]
axr.bar(xs, [rec_rec, rec_agr], width=0.52, color=[CINZA_ESCURO, CINZA], zorder=2)
for x, v in zip(xs, [rec_rec, rec_agr]):
    axr.text(x, v + 3, f"R$ {num(v)}", ha="center", va="bottom", fontsize=TAM_TEXTO + 1, fontweight="bold",
             color=TEXTO)
axr.set_xticks(xs)
axr.set_xticklabels(["recorrente\n(balcão)", "agregador\n(Wellhub, TotalPass)"],
                    fontsize=TAM_NOTA + 0.5, color=TEXTO)
axr.set_ylim(0, 175)
axr.set_xlim(-0.45, 2.75)
axr.set_yticks([0, 50, 100, 150])
axr.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"R$ {num(v)}"))
# premissa 60%
axr.plot([0.62, 1.30], [premissa, premissa], color=DESTAQUE, lw=2.4, zorder=4, solid_capstyle="round")
axr.text(1.35, premissa + 5, "premissa do simulador\n60% — MANTIDA", ha="left", va="bottom",
         fontsize=TAM_NOTA + 0.5, color=DESTAQUE, fontweight="bold", linespacing=1.15)
axr.text(1.35, premissa + 3, f"= R$ {num(premissa)} (medição\nmanual nas unidades\n≈ 60%)", ha="left", va="top",
         fontsize=TAM_NOTA - 0.5, color=DESTAQUE, linespacing=1.15)
axr.text(1.37, 38, f"{num(rho)}% pela contagem\ndo sistema (Wellhub\n{num(wh)}%, TotalPass "
         f"{num(tp)}%)", ha="left", va="center", fontsize=TAM_NOTA - 0.5, color=CINZA_ESCURO, linespacing=1.15)
axr.text(1.37, 16, "mediana mês a mês\nda razão; a contagem\nnão é 100% limpa", ha="left", va="center",
         fontsize=TAM_NOTA - 1.5, color=CINZA, linespacing=1.1, style="italic")

# ------------------------------------------------------------------ dados
dados = pd.DataFrame([
    dict(painel="efeito de +1 dp de agregador", medida="alunos ativos (%)", valor=alu[0], ic90_lo=alu[1],
         ic90_hi=alu[2], sens_A=alu[3], sens_B=alu[4], n=alu[5], fonte="uni01/resultado_uni01.md (T06)"),
    dict(painel="efeito de +1 dp de agregador", medida="ticket médio (%)", valor=tic[0], ic90_lo=tic[1],
         ic90_hi=tic[2], sens_A=tic[3], sens_B=tic[4], n=tic[5], fonte="uni01/resultado_uni01.md (T07)"),
    dict(painel="efeito de +1 dp de agregador", medida="faturamento, conta (%)", valor=round(100 * fat, 2),
         ic90_lo=None, ic90_hi=None, sens_A=round(100 * fat_a, 2), sens_B=round(100 * fat_b, 2), n=alu[5],
         fonte="conta (1 + T06) × (1 + T07) − 1"),
    dict(painel="efeito de +1 dp de agregador", medida="cancelamento mensal (pontos)", valor=chu[0], ic90_lo=chu[1],
         ic90_hi=chu[2], sens_A=chu[3], sens_B=chu[4], n=chu[5], fonte="uni01/resultado_uni01.md (T18)"),
    dict(painel="receita por aluno", medida="recorrente (R$/mês)", valor=rec_rec, n=n_unid,
         fonte="alavancas/resultado_alavancas.md (seção D)"),
    dict(painel="receita por aluno", medida="agregador (R$/mês)", valor=rec_agr, n=n_unid,
         fonte="alavancas/resultado_alavancas.md (seção D)"),
    dict(painel="receita por aluno", medida="ρ mediano pela contagem do sistema (%)", valor=rho, n=n_unid,
         fonte="alavancas/resultado_alavancas.md (seção D); Wellhub 47%, TotalPass 50%"),
    dict(painel="receita por aluno", medida="premissa do simulador, 60% × recorrente (R$/mês)",
         valor=round(premissa, 1), fonte="decisão do dono (29/09): premissa de 60% mantida"),
])
dados["dp_fatia_agregador_pontos"] = 100 * dp_agr
salvar(fig, ID, dados)
