"""s1_regra_achata — a regra atual dá quase o mesmo número a toda unidade.

Fonte: uni02/confirmacao_por_unidade.csv (18 unidades de teste do UNI-02).
Mesma ordem de linhas (real decrescente) e mesma escala (R$ mil, 0–750) que s3_previsto_real.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _estilo import *  # noqa: E402,F403

ID = "s1_regra_achata"
FONTE = UNI / "uni02" / "confirmacao_por_unidade.csv"

df = pd.read_csv(FONTE, sep=";", encoding="utf-8-sig")
df = df.sort_values("real", ascending=False).reset_index(drop=True)
df["rotulo"] = [nome_unidade(n, u) for n, u in zip(df["nome"], df["uf"])]

# ------------------------------------------------------------------ números e conferência
n = len(df)
prev_min, prev_max = df["prev_ATUAL"].min() / 1000, df["prev_ATUAL"].max() / 1000
real_min, real_max = df["real"].min() / 1000, df["real"].max() / 1000
vies = df["erro_ATUAL"].median() * 100
erro_tipico = df["erro_ATUAL"].abs().median() * 100
conferir("N de unidades de teste", n, 18)
conferir("mínimo do previsto pela regra atual (R$ mil)", prev_min, 182.7, 0.06)
conferir("máximo do previsto pela regra atual (R$ mil)", prev_max, 295.5, 0.06)
conferir("mínimo do real (R$ mil)", round(real_min), 114, 0.5)
conferir("máximo do real (R$ mil)", round(real_max), 697, 0.5)
conferir("viés da regra atual (mediana de real/previsto − 1, %)", round(vies), -17, 0.5)
conferir("erro típico da regra atual (mediana de |erro|, %)", round(erro_tipico), 27, 0.5)
conferir("unidades que não aceitam agregador", int((~df["aceita_agregador"].astype(bool)).sum()), 1)
botafogo = df.index[df["nome"].eq("BOTAFOGO")][0]
conferir("Botafogo é a única que não aceita agregador", int(not bool(df.loc[botafogo, "aceita_agregador"])), 1)

# ------------------------------------------------------------------ figura
fig = figura()
y_topo = cabecalho(
    fig,
    "A regra atual dá quase o mesmo número a toda unidade — e, na mediana, o real ficou 17% abaixo",
    "Faturamento mensal maduro previsto pela regra de hoje (só metragem) × real, "
    "18 unidades abertas em 2025 e maduras em 2026",
)
y_base = rodape(
    fig,
    "Fonte: uni02/confirmacao_por_unidade.csv; uni02/resultado_uni02.md · N = 18 · "
    "real = média dos meses maduros de 2026; erro = real/previsto − 1",
    nota="Regra atual = alunos pela densidade da metragem × receita por aluno observada em 2025 (UNI-02). "
    "No cálculo exato do simulador de produção (receita por aluno de R$ 115), o real fica 24% abaixo (UNI-05).",
)

ax = fig.add_axes([0.175, y_base + 0.075, 0.79, y_topo - y_base - 0.125])
eixo_limpo(ax, grade="x")
y = np.arange(n)

# faixa da regra atual
ax.axvspan(prev_min, prev_max, color=DESTAQUE, alpha=0.12, lw=0, zorder=0)
ax.text((prev_min + prev_max) / 2, -1.4, "a regra atual fica aqui", ha="center", va="bottom",
        fontsize=TAM_NOTA, color=DESTAQUE, fontweight="bold")
ax.text((prev_min + prev_max) / 2, -0.72, f"{num(prev_min)}–{num(prev_max)} mil", ha="center", va="bottom",
        fontsize=TAM_NOTA - 0.5, color=DESTAQUE)

for i, r in df.iterrows():
    ax.plot([r["prev_ATUAL"] / 1000, r["real"] / 1000], [i, i], color=CINZA_CLARO, lw=1.6, zorder=1,
            solid_capstyle="round")
ax.scatter(df["prev_ATUAL"] / 1000, y, s=58, color=CINZA_ESCURO, zorder=3, edgecolor="white", lw=1.2,
           label="previsto pela regra atual (só metragem)")
ax.scatter(df["real"] / 1000, y, s=62, marker="D", color=REAL, zorder=4, edgecolor="white", lw=1.2,
           label="real (média dos meses maduros de 2026)")

ax.set_yticks(y)
ax.set_yticklabels(df["rotulo"], fontsize=TAM_NOTA + 0.5, color=TEXTO)
ax.set_ylim(n - 0.4, -1.25)
ax.set_xlim(0, 750)
ax.set_xticks(range(0, 751, 100))
ax.xaxis.set_major_formatter(formatador_num(0))
ax.set_xlabel("faturamento mensal maduro (R$ mil)", color=CINZA_ESCURO, fontsize=TAM_NOTA)
ax.spines["left"].set_visible(False)

# Botafogo
xb = df.loc[botafogo, "real"] / 1000
ax.annotate("única que não aceita agregador", xy=(xb, botafogo), xytext=(xb - 18, botafogo - 0.95),
            ha="right", va="center", fontsize=TAM_NOTA, color=TEXTO,
            arrowprops=dict(arrowstyle="-", color=CINZA, lw=0.8, shrinkA=2, shrinkB=5,
                            connectionstyle="angle,angleA=0,angleB=90,rad=0"))

# resumo no canto inferior direito (área vazia: reais abaixo de R$ 350 mil)
ax.text(740, n - 2.6,
        f"Mediana: real {num(abs(vies))}% abaixo do previsto\nerro típico {num(erro_tipico)}%",
        ha="right", va="center", fontsize=TAM_TEXTO + 1, color=TEXTO, fontweight="bold", linespacing=1.4,
        bbox=dict(boxstyle="round,pad=0.6", fc=CINZA_FUNDO, ec="none"))
ax.text(740, n - 5.0,
        f"a previsão fica entre R$ {num(prev_min)} e {num(prev_max)} mil;\n"
        f"o real vai de R$ {num(real_min)} a {num(real_max)} mil",
        ha="right", va="center", fontsize=TAM_NOTA, color=CINZA_ESCURO, linespacing=1.4)

ax.legend(loc="lower right", bbox_to_anchor=(1.0, 1.005), ncol=2, handletextpad=0.4, columnspacing=1.6,
          fontsize=TAM_NOTA)

# ------------------------------------------------------------------ dados
dados = df[["nome", "uf", "real", "prev_ATUAL", "erro_ATUAL"]].copy()
dados.insert(0, "ordem", np.arange(1, n + 1))
dados["rotulo"] = df["rotulo"]
dados["aceita_agregador"] = df["aceita_agregador"]
salvar(fig, ID, dados)
