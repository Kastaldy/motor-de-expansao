"""s3_previsto_real — com a praça, o erro fica equilibrado (9 acima e 9 abaixo, contra 7 e 11 na regra atual).

Retoma s1_regra_achata: mesmas 18 linhas, mesma ordem (real decrescente), mesma escala (R$ mil, 0–750),
acrescentando o modelo da praça (M0). Fonte: uni02/confirmacao_por_unidade.csv.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _estilo import *  # noqa: E402,F403

ID = "s3_previsto_real"
FONTE = UNI / "uni02" / "confirmacao_por_unidade.csv"

df = pd.read_csv(FONTE, sep=";", encoding="utf-8-sig")
df = df.sort_values("real", ascending=False).reset_index(drop=True)
df["rotulo"] = [nome_unidade(n, u) for n, u in zip(df["nome"], df["uf"])]
n = len(df)
y = np.arange(n)

# ------------------------------------------------------------------ números e conferência
a_min, a_max = df["prev_ATUAL"].min() / 1000, df["prev_ATUAL"].max() / 1000
m_min, m_max = df["prev_M0"].min() / 1000, df["prev_M0"].max() / 1000
acima_at, abaixo_at = int((df["erro_ATUAL"] > 0).sum()), int((df["erro_ATUAL"] <= 0).sum())
acima_m0, abaixo_m0 = int((df["erro_M0"] > 0).sum()), int((df["erro_M0"] <= 0).sum())
dentro25_at = int((df["erro_ATUAL"].abs() <= 0.25).sum())
dentro25_m0 = int((df["erro_M0"].abs() <= 0.25).sum())
conferir("N de unidades de teste", n, 18)
conferir("mínimo do previsto pelo modelo da praça (R$ mil)", round(m_min, 1), 153.0, 0.05)
conferir("máximo do previsto pelo modelo da praça (R$ mil)", round(m_max, 1), 436.5, 0.05)
conferir("mínimo do previsto pela regra atual (R$ mil)", round(a_min), 183, 0.5)
conferir("máximo do previsto pela regra atual (R$ mil)", round(a_max), 295, 0.5)
conferir("regra atual: real acima do previsto", acima_at, 7)
conferir("regra atual: real abaixo do previsto", abaixo_at, 11)
conferir("modelo da praça: real acima do previsto", acima_m0, 9)
conferir("modelo da praça: real abaixo do previsto", abaixo_m0, 9)
conferir("dentro de ±25%: modelo da praça", dentro25_m0, 10)
conferir("dentro de ±25%: regra atual", dentro25_at, 9)
ERROS_ESP = {"BOTAFOGO": 185, "CARIACICA": 100, "BUTANTA": 90, "NOROESTE": 59, "MOCOCA": -53}
idx = {nm: df.index[df["nome"].eq(nm)][0] for nm in ERROS_ESP}
for nm, e in ERROS_ESP.items():
    conferir(f"erro do modelo da praça em {nm} (%)", round(df.loc[idx[nm], "erro_M0"] * 100), e, 0.5)
conferir("Botafogo é a única que não aceita agregador",
         int((~df["aceita_agregador"].astype(bool)).sum() == 1 and not df.loc[idx["BOTAFOGO"], "aceita_agregador"]), 1)

# ------------------------------------------------------------------ figura
fig = figura()
y_topo = cabecalho(
    fig,
    f"Com a praça, o erro fica equilibrado: {acima_m0} acima e {abaixo_m0} abaixo, contra {acima_at} e {abaixo_at} "
    "na regra atual",
    "Faturamento mensal maduro previsto pela regra de hoje e pelo modelo da praça × real, 18 unidades abertas "
    "em 2025 (nunca vistas pelo modelo)",
)
y_base = rodape(
    fig,
    "Fonte: uni02/confirmacao_por_unidade.csv · N = 18 · erro = real/previsto − 1 · real = média dos meses "
    "maduros de 2026",
    nota=f"Dentro de ±25% do real ficam {dentro25_m0} unidades no modelo da praça e {dentro25_at} na regra atual — "
    f"praticamente igual. O que muda: a regra atual achata (subestima as fortes e superestima as fracas; viés "
    f"mediano de {pct(100 * df['erro_ATUAL'].median(), sinal=True)}) e o modelo da praça fica sem viés "
    f"({pct(100 * df['erro_M0'].median(), sinal=True)}); e a amplitude das previsões abre de "
    f"R$ {num(a_min)}–{num(a_max)} mil para R$ {num(m_min)}–{num(m_max)} mil (não é a faixa p10–p90 de s3_placar/s7).",
)
ax = fig.add_axes([0.175, y_base + 0.075, 0.79, y_topo - y_base - 0.135])
eixo_limpo(ax, grade="x")

# faixas: regra atual (cinza, preenchida) e modelo da praça (contorno em destaque)
ax.axvspan(a_min, a_max, color=CINZA_MUITO_CLARO, lw=0, zorder=0)
ax.add_patch(matplotlib.patches.Rectangle((m_min, n - 0.4), m_max - m_min, -(n - 0.4 + 0.55), fill=False,
                                          ec=DESTAQUE, lw=1.2, ls=(0, (4, 2.5)), zorder=0.5))
ax.text((a_min + a_max) / 2, -0.62, f"regra atual: {num(a_min)}–{num(a_max)} mil", ha="center", va="bottom",
        fontsize=TAM_NOTA - 0.5, color=CINZA_ESCURO, fontweight="bold")
ax.text((m_min + m_max) / 2, -1.3, f"modelo da praça: {num(m_min)}–{num(m_max)} mil", ha="center",
        va="bottom", fontsize=TAM_NOTA - 0.5, color=DESTAQUE, fontweight="bold")

for i, r in df.iterrows():
    ax.plot([r["prev_M0"] / 1000, r["real"] / 1000], [i, i], color=DESTAQUE, lw=1.1, alpha=0.75, zorder=1,
            solid_capstyle="round")
ax.scatter(df["prev_ATUAL"] / 1000, y, s=52, color=CINZA_ESCURO, zorder=3, edgecolor="white", lw=1.1,
           label="regra atual (só metragem)")
ax.scatter(df["prev_M0"] / 1000, y, s=60, color=DESTAQUE, zorder=3.5, edgecolor="white", lw=1.1,
           label="modelo da praça (metragem + renda + população)")
ax.scatter(df["real"] / 1000, y, s=60, marker="D", color=REAL, zorder=4, edgecolor="white", lw=1.1,
           label="real")

ax.set_yticks(y)
ax.set_yticklabels(df["rotulo"], fontsize=TAM_NOTA + 0.5, color=TEXTO)
ax.set_ylim(n - 0.4, -2.0)
ax.set_xlim(0, 750)
ax.set_xticks(range(0, 751, 100))
ax.xaxis.set_major_formatter(formatador_num(0))
ax.set_xlabel("faturamento mensal maduro (R$ mil)", color=CINZA_ESCURO, fontsize=TAM_NOTA)
ax.spines["left"].set_visible(False)


def rotulo_erro(nm, texto, lado, dx=12):
    i = idx[nm]
    r = df.loc[i]
    xs = [r["prev_ATUAL"] / 1000, r["prev_M0"] / 1000, r["real"] / 1000]
    if lado == "esq":
        ax.text(min(xs) - dx, i, texto, ha="right", va="center", fontsize=TAM_NOTA - 0.5, color=TEXTO,
                linespacing=1.15, zorder=5)
    else:
        ax.text(max(xs) + dx, i, texto, ha="left", va="center", fontsize=TAM_NOTA - 0.5, color=TEXTO,
                linespacing=1.15, zorder=5)


def e(nm):
    return pct(df.loc[idx[nm], "erro_M0"] * 100, sinal=True)


# Botafogo: acima da linha (à esquerda dela não cabe)
ib = idx["BOTAFOGO"]
ax.text(df.loc[ib, "real"] / 1000 - 8, ib - 0.42,
        f"{e('BOTAFOGO')} no modelo\nnão aceita agregador; ~4.000 alunos de balcão",
        ha="right", va="bottom", fontsize=TAM_NOTA - 0.5, color=TEXTO, linespacing=1.15, zorder=5)
rotulo_erro("NOROESTE", f"{e('NOROESTE')} no modelo", "esq")
rotulo_erro("BUTANTA", f"{e('BUTANTA')} no modelo", "dir")
rotulo_erro("CARIACICA", f"{e('CARIACICA')} no modelo", "dir")
rotulo_erro("MOCOCA", f"{e('MOCOCA')} no modelo", "dir")

# resumo no canto inferior direito
ax.text(740, n - 3.2, "Real acima / abaixo do previsto", ha="right", va="bottom", fontsize=TAM_TEXTO,
        color=TEXTO, fontweight="bold")
ax.text(740, n - 2.35, f"regra atual   {acima_at} / {abaixo_at}", ha="right", va="center", fontsize=TAM_TEXTO + 1,
        color=CINZA_ESCURO, fontweight="bold")
ax.text(740, n - 1.35, f"modelo da praça   {acima_m0} / {abaixo_m0}", ha="right", va="center",
        fontsize=TAM_TEXTO + 1, color=DESTAQUE, fontweight="bold")
ax.add_patch(matplotlib.patches.FancyBboxPatch((520, n - 3.55), 228, 2.95, boxstyle="round,pad=0,rounding_size=6",
                                               fc=CINZA_FUNDO, ec="none", zorder=0.2, mutation_aspect=1 / 60))

ax.legend(loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=3, handletextpad=0.4, columnspacing=1.4,
          fontsize=TAM_NOTA)

# ------------------------------------------------------------------ dados
dados = df[["nome", "uf", "real", "prev_ATUAL", "prev_M0", "erro_ATUAL", "erro_M0", "aceita_agregador"]].copy()
dados.insert(0, "ordem", np.arange(1, n + 1))
dados["rotulo"] = df["rotulo"]
dados["faixa_ATUAL_min"], dados["faixa_ATUAL_max"] = df["prev_ATUAL"].min(), df["prev_ATUAL"].max()
dados["faixa_M0_min"], dados["faixa_M0_max"] = df["prev_M0"].min(), df["prev_M0"].max()
salvar(fig, ID, dados)
