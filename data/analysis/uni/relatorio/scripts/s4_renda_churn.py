"""s4_renda_churn — praça mais rica cancela menos na rede madura, mas o efeito não apareceu nas unidades novas.

Fontes: uni04/resultado_uni04a.md (T17; Q2; Q1 = o teste que decide; Q4 '+ todos').
Pós-hoc (EXPLORATÓRIO): uni04/02_posthoc_idade.py, rodado uma vez em 2026-09-30, em primeiro plano, só para ler os
IC. Saída copiada abaixo (o script lê o painel do UNI-01; não é re-executado aqui):
    T17 + log idade : -1.15 [-1.66; -0.64] (ΔR² LOO +0.264)
    Q3 churn EB 60d (pp) ~ renda isocrona + pop + idade: -0.38 [-0.75; -0.02] (ΔR² LOO +0.018) | media 8.14
"""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _estilo import *  # noqa: E402,F403

ID = "s4_renda_churn"
MD = (UNI / "uni04" / "resultado_uni04a.md").read_text(encoding="utf-8")
CAD = (UNI / "CADERNO_ESTUDO_UNI.md").read_text(encoding="utf-8")

POSTHOC = {  # saída de uni04/02_posthoc_idade.py (2026-09-30)
    "T17_idade": (-1.15, -1.66, -0.64),
    "lifetime": (-0.38, -0.75, -0.02),
    "lifetime_media_pp": 8.14,
}


def efeito(s):
    m = re.match(r"(\S+) \[(\S+); (\S+)\]", s.strip())
    return tuple(float(x.replace("+", "")) for x in m.groups())


q12 = tabela_md(MD, "| amostra | N | efeito [IC 90%] |").set_index("amostra")
q4 = tabela_md(MD, "| modelo | efeito da renda [IC 90%] |").set_index("modelo")
q3n = int(re.search(r"N = (\d+) \(SP \d+, DF \d+\)", MD).group(1))
t17 = efeito(q12.loc["T17 (UNI-01, reproduzido)", "efeito [IC 90%]"])
q2 = efeito(q12.loc["Q2: unidades do T17 em 2026", "efeito [IC 90%]"])
q1 = efeito(q12.loc["Q1: unidades novas, com idade (DECIDE)", "efeito [IC 90%]"])
todos = efeito(q4.loc["+ todos", "efeito da renda [IC 90%]"])
n_q1 = int(q12.loc["Q1: unidades novas, com idade (DECIDE)", "N"])
n_t17 = int(q12.loc["T17 (UNI-01, reproduzido)", "N"])

# ------------------------------------------------------------------ conferência
for nome, v, e in [("T17", t17, (-1.29, -1.72, -0.86)), ("Q2", q2, (-0.90, -1.20, -0.61)),
                   ("Q1", q1, (-0.20, -1.10, 0.69)), ("Q4 + todos", todos, (-0.88, -1.33, -0.43))]:
    for i, parte in enumerate(("efeito", "IC inferior", "IC superior")):
        conferir(f"{nome}: {parte}", v[i], e[i])
conferir("N da rede madura (T17)", n_t17, 39)
conferir("N do teste que decide (Q1)", n_q1, 17)
conferir("N do Lifetime (Q3)", q3n, 56)
conferir("Q1 classificado como inconclusivo", int("| inconclusivo |" in MD), 1)
conferir("caderno cita o pós-hoc com idade (−1,15)", int("−1,15 ponto" in CAD), 1)
conferir("caderno cita o Lifetime (−0,38; média 8,1%)", int("−0,38 ponto (média 8,1%)" in CAD), 1)

# ------------------------------------------------------------------ linhas
L = [
    dict(rotulo=f"Rede madura 2025 (N = {n_t17})", ef=t17, grupo="madura", posthoc=False,
         fonte="uni04/resultado_uni04a.md (T17)"),
    dict(rotulo="mesma, com a idade da unidade controlada*", ef=POSTHOC["T17_idade"], grupo="madura", posthoc=True,
         fonte="uni04/02_posthoc_idade.py (pós-hoc)"),
    dict(rotulo="mesma, controlando ticket, agregador,\ninadimplência e cobrança", ef=todos, grupo="madura",
         posthoc=False, fonte="uni04/resultado_uni04a.md (Q4, + todos)"),
    dict(rotulo=f"mesmas unidades em 2026 (N = {n_t17})", ef=q2, grupo="madura", posthoc=False,
         fonte="uni04/resultado_uni04a.md (Q2)"),
    dict(rotulo=f"Lifetime, churn de 60 dias\n(N = {q3n}, idade controlada)*", ef=POSTHOC["lifetime"],
         grupo="outra_medida", posthoc=True, fonte="uni04/02_posthoc_idade.py (pós-hoc)"),
    dict(rotulo=f"{n_q1} unidades que amadureceram em 2026\n— o teste que decide", ef=q1, grupo="decide",
         posthoc=False, fonte="uni04/resultado_uni04a.md (Q1)"),
]

# ------------------------------------------------------------------ figura
fig = figura()
y_topo = cabecalho(
    fig,
    "Praça mais rica cancela menos na rede madura, mas o efeito não apareceu nas unidades novas",
    "Efeito da renda da praça sobre o cancelamento mensal, em amostras e fontes diferentes; IC 90%",
)
y_base = rodape(
    fig,
    "Fonte: uni04/resultado_uni04a.md; uni04/02_posthoc_idade.py (pós-hoc) · IC 90% · efeito por degrau típico de "
    "renda (1 desvio-padrão do log da renda da isócrona de 10 min de carro)",
    nota="* pós-hoc (EXPLORATÓRIO, marcador vazado): análise feita depois do protocolo, só para ajudar a ler; não muda o resultado "
    "oficial.",
)
x_ax0, x_ax1 = 0.36, 0.73
ax = fig.add_axes([x_ax0, y_base + 0.09, x_ax1 - x_ax0, y_topo - y_base - 0.13])
eixo_limpo(ax, grade="x")
ax.spines["left"].set_visible(False)
ys = [0, 1, 2, 3, 4.15, 5.6]
for yv, r in zip(ys, L):
    e, lo, hi = r["ef"]
    if r["grupo"] == "decide":
        cor, s, lw = DESTAQUE, 90, 3.0
    elif r["grupo"] == "outra_medida":
        cor, s, lw = CINZA, 55, 2.2
    else:
        cor, s, lw = CINZA_ESCURO, 60, 2.4
    ax.plot([lo, hi], [yv, yv], color=cor, lw=lw, zorder=2, solid_capstyle="round")
    if r["posthoc"]:
        ax.scatter(e, yv, s=s, facecolor="white", edgecolor=cor, lw=1.8, zorder=3)
    else:
        ax.scatter(e, yv, s=s, color=cor, edgecolor="white", lw=1.1, zorder=3)
    ax.text(hi + 0.06, yv, f"{num(e, 2, sinal=True)}  [{num(lo, 2, sinal=True)}; {num(hi, 2, sinal=True)}]",
            ha="left", va="center", fontsize=TAM_NOTA + (1 if r["grupo"] == "decide" else 0),
            color=cor if r["grupo"] != "outra_medida" else CINZA_ESCURO,
            fontweight="bold" if r["grupo"] == "decide" else "normal", zorder=4,
            bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.92))
ax.axvline(0, color=TEXTO, lw=1.0, zorder=1)
ax.axhline(4.85, color=CINZA_CLARO, lw=0.9, xmin=-0.9, clip_on=False)
ax.set_yticks(ys)
ax.set_yticklabels([r["rotulo"] for r in L], fontsize=TAM_NOTA + 0.5, linespacing=1.15)
for t, r in zip(ax.get_yticklabels(), L):
    if r["grupo"] == "decide":
        t.set_color(DESTAQUE)
        t.set_fontweight("bold")
    elif r["grupo"] == "outra_medida":
        t.set_color(CINZA_ESCURO)
ax.set_ylim(6.2, -0.8)
ax.set_xlim(-2.0, 1.55)
ax.set_xticks([-2, -1.5, -1, -0.5, 0, 0.5, 1])
ax.xaxis.set_major_formatter(formatador_num(1, sinal=True))
ax.set_xlabel("pontos percentuais de churn mensal por degrau típico de renda (churn médio ~7% ao mês)",
              fontsize=TAM_NOTA, color=CINZA_ESCURO)
ax.text(-1.97, -0.62, "← praça mais rica cancela menos", ha="left", va="center", fontsize=TAM_NOTA - 0.5,
        color=CINZA_ESCURO)
ax.text(0.03, -0.62, "cancela mais →", ha="left", va="center", fontsize=TAM_NOTA - 0.5, color=CINZA_ESCURO)
ax.text(1.52, 4.15 + 0.38, "outra medida de cancelamento", ha="right", va="center", fontsize=TAM_NOTA - 1,
        color=CINZA_ESCURO, style="italic")
ax.text(1.52, 5.6 + 0.42, "intervalo cruza zero: inconclusivo", ha="right", va="center", fontsize=TAM_NOTA - 1,
        color=DESTAQUE, style="italic")

# notas à direita
x_col, w_col = 0.755, 1 - MARGEM_X - 0.755
yb = caixa(fig, x_col, y_topo - 0.03, w_col,
           "Sinal real na rede madura; não serve para prometer o churn de uma unidade nova. Não entra na viabilidade "
           "por enquanto; vale acompanhar na operação.",
           tamanho=TAM_NOTA + 0.5, fundo=DESTAQUE_MUITO_CLARO, barra=DESTAQUE, titulo="Leitura")
yb = caixa(fig, x_col, yb - 0.02, w_col,
           f"Parte do efeito anda junto com ticket maior e menos alunos em cobrança: controlando esses fatores, "
           f"{num(t17[0], 2, sinal=True)} vira {num(todos[0], 2, sinal=True)} (decomposição, não prova de causa).",
           tamanho=TAM_NOTA)
caixa(fig, x_col, yb - 0.02, w_col,
      f"No Lifetime, o churn de 60 dias tem média de {num(POSTHOC['lifetime_media_pp'], 1)}%; o efeito vai na "
      "mesma direção, mas é pequeno.", tamanho=TAM_NOTA)

# ------------------------------------------------------------------ dados
dados = pd.DataFrame([dict(ordem=i + 1, rotulo=r["rotulo"].replace("\n", " "), efeito_pp=r["ef"][0],
                           ic90_lo=r["ef"][1], ic90_hi=r["ef"][2], pos_hoc=r["posthoc"], grupo=r["grupo"],
                           fonte=r["fonte"]) for i, r in enumerate(L)])
salvar(fig, ID, dados)
