"""s3_placar_modelo — o modelo da praça se confirmou em unidades que nunca viu: sem viés e ordenando melhor.

Fonte: uni02/resultado_uni02.md (tabela 'Resultado principal' e tabela 'Sensibilidades', linha (a) só metragem
oficial, N = 15); cobertura da faixa p10–p90 do M0 no mesmo .md. Conferência do erro típico e do viés contra
uni02/confirmacao_por_unidade.csv (18 unidades de teste).
"""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _estilo import *  # noqa: E402,F403

ID = "s3_placar_modelo"
MD = (UNI / "uni02" / "resultado_uni02.md").read_text(encoding="utf-8")
POR_UNIDADE = pd.read_csv(UNI / "uni02" / "confirmacao_por_unidade.csv", sep=";", encoding="utf-8-sig")

# ------------------------------------------------------------------ leitura
MODELOS = ["ATUAL", "INGÊNUO", "M0", "M0d"]
ROTULO = {
    "ATUAL": ("Regra atual", "(só metragem)"),
    "INGÊNUO": ("Sem informação", "(média da rede)"),
    "M0": ("Modelo da praça", "(metragem + renda + população)"),
    "M0d": ("Modelo + hipótese", "do diretor"),
}
COR = {"ATUAL": CINZA_ESCURO, "INGÊNUO": CINZA, "M0": DESTAQUE, "M0d": CINZA}

princ = tabela_md(MD, "| modelo | erro típico |").set_index("modelo")
sens = tabela_md(MD, "| cenário | N teste |")
linha_a = sens[sens["cenário"].str.startswith("(a)")].iloc[0]
n_a = int(linha_a["N teste"])


def ic(s):
    a, b = s.strip("[]").split(";")
    return (np.nan if "nan" in a else numero_br(a)), (np.nan if "nan" in b else numero_br(b))


linhas = []
for m in MODELOS:
    r = princ.loc[m]
    lo, hi = ic(r["IC 90%"])
    rho = np.nan if "nan" in r["ordenação (Spearman)"] else numero_br(r["ordenação (Spearman)"])
    erro_a = numero_br(linha_a[m].split(";")[0])
    linhas.append(
        dict(modelo=m, rotulo=" ".join(ROTULO[m]), erro_tipico_pct=numero_br(r["erro típico"]),
             erro_tipico_so_oficial_pct=erro_a, vies_pct=numero_br(r["viés"]), spearman=rho,
             spearman_ic90_lo=lo, spearman_ic90_hi=hi)
    )
df = pd.DataFrame(linhas).set_index("modelo")
cobertura = int(re.search(r"cobertura no teste (\d+)%", MD).group(1))
esperado_cob = int(re.search(r"esperado ≈ (\d+)%", MD).group(1))

# ------------------------------------------------------------------ conferência
esp = {
    "ATUAL": (27, 22, -17, 0.35, -0.09, 0.74), "INGÊNUO": (37, 38, -19, np.nan, np.nan, np.nan),
    "M0": (22, 22, 1, 0.50, 0.12, 0.78), "M0d": (20, 22, 8, 0.51, 0.08, 0.85),
}
for m, (e, ea, v, rho, lo, hi) in esp.items():
    r = df.loc[m]
    conferir(f"{m}: erro típico (%)", r["erro_tipico_pct"], e)
    conferir(f"{m}: erro típico só metragem oficial (%)", r["erro_tipico_so_oficial_pct"], ea)
    conferir(f"{m}: viés (%)", r["vies_pct"], v)
    if not np.isnan(rho):
        conferir(f"{m}: Spearman", r["spearman"], rho)
        conferir(f"{m}: IC 90% inferior", r["spearman_ic90_lo"], lo)
        conferir(f"{m}: IC 90% superior", r["spearman_ic90_hi"], hi)
conferir("N da sensibilidade só metragem oficial", n_a, 15)
conferir("cobertura da faixa p10–p90 do M0 (%)", cobertura, 67)
conferir("cobertura esperada (%)", esperado_cob, 80)
# o .md bate com a tabela por unidade
for m, col in [("ATUAL", "erro_ATUAL"), ("M0", "erro_M0")]:
    conferir(f"{m}: erro típico recalculado do CSV (%)", round(POR_UNIDADE[col].abs().median() * 100),
             df.loc[m, "erro_tipico_pct"], 0.5)
    conferir(f"{m}: viés recalculado do CSV (%)", round(POR_UNIDADE[col].median() * 100), df.loc[m, "vies_pct"], 0.5)
conferir("N de unidades de teste", len(POR_UNIDADE), 18)
n_oficial = int(POR_UNIDADE["fonte_m2"].eq("oficial").sum())
conferir("unidades de teste com metragem oficial", n_oficial, 15)

# ------------------------------------------------------------------ figura
fig = figura()
y_topo = cabecalho(
    fig,
    "O modelo da praça se confirmou em unidades que nunca viu: sem viés e ordenando melhor",
    "Faturamento maduro previsto × real em 18 unidades abertas em 2025 e maduras em 2026; modelos ajustados só "
    "com dados até dez/2025; regras fixadas antes",
    chip="CONFIRMADO",
)
y_base = rodape(
    fig,
    "Fonte: uni02/resultado_uni02.md · treino N = 39 maduras de 2025; teste N = 18 (15 com metragem oficial, "
    "3 por satélite) · erro = real/previsto − 1; erro típico = mediana de |erro|",
)
y_caixa_base = caixa(
    fig, MARGEM_X, y_base + 0.09, 1 - 2 * MARGEM_X,
    "O que é firme em todos os recortes: sem viés e ordenar melhor. "
    f"A faixa p10–p90 do modelo cobriu {cobertura}% das unidades (esperado {esperado_cob}%): na viabilidade, "
    "a faixa precisa ser mais larga (seção 7).",
    tamanho=TAM_TEXTO, fundo=DESTAQUE_MUITO_CLARO, barra=DESTAQUE,
)

y0 = y_base + 0.205  # base dos painéis (abaixo: ticks, notas e a caixa)
y1 = y_topo - 0.085  # topo dos painéis (deixa espaço para o título do painel)
alt = y1 - y0
X_ROT = 0.215
paineis = [(X_ROT + 0.005, 0.215), (0.485, 0.215), (0.745, 0.22)]
ys = np.arange(len(MODELOS))


def preparar(ax, titulo, subt):
    eixo_limpo(ax, grade="x")
    ax.spines["left"].set_visible(False)
    ax.set_yticks([])
    ax.set_ylim(len(MODELOS) - 0.45, -0.55)
    bb = ax.get_position()
    fig.text(bb.x0, y1 + 0.058, titulo, ha="left", va="bottom", fontsize=TAM_TEXTO + 1, fontweight="bold",
             color=TEXTO)
    fig.text(bb.x0, y1 + 0.056, subt, ha="left", va="top", fontsize=TAM_NOTA - 0.5, color=CINZA_ESCURO)


# painel 1 — erro típico
ax = ax_ref = fig.add_axes([paineis[0][0], y0, paineis[0][1], alt])
preparar(ax, "Erro típico", "mediana de |real/previsto − 1| · menor é melhor")
for i, m in enumerate(MODELOS):
    v = df.loc[m, "erro_tipico_pct"]
    ax.barh(i, v, height=0.55, color=COR[m], zorder=2)
    ax.text(v + 0.8, i - 0.13, pct(v), ha="left", va="center", fontsize=TAM_TEXTO + 1, fontweight="bold",
            color=DESTAQUE if m == "M0" else TEXTO)
    va = df.loc[m, "erro_tipico_so_oficial_pct"]
    ax.scatter(va, i + 0.36, s=46, facecolor="white", edgecolor=TEXTO, lw=1.3, zorder=4)
    ax.text(va + 1.2, i + 0.36, pct(va), ha="left", va="center", fontsize=TAM_NOTA - 0.5, color=CINZA_ESCURO)
ax.set_xlim(0, 46)
ax.set_xticks([0, 10, 20, 30, 40])
ax.xaxis.set_major_formatter(formatador_num(0, "%"))
leg1 = [matplotlib.patches.Patch(color=CINZA, label="teste completo (N = 18)"),
        matplotlib.lines.Line2D([], [], marker="o", ls="", markerfacecolor="white", markeredgecolor=TEXTO,
                                markersize=6.5, label=f"só metragem oficial (N = {n_a})")]
ax.legend(handles=leg1, loc="upper left", bbox_to_anchor=(0.0, -0.1), ncol=1, fontsize=TAM_NOTA - 0.5,
          handlelength=1.2, borderaxespad=0, labelspacing=0.3)

# painel 2 — viés
ax2 = fig.add_axes([paineis[1][0], y0, paineis[1][1], alt])
preparar(ax2, "Viés", "mediana de real/previsto − 1")
for i, m in enumerate(MODELOS):
    v = df.loc[m, "vies_pct"]
    ax2.barh(i, v, height=0.55, color=COR[m], zorder=2)
    ha = "right" if v < 0 else "left"
    ax2.text(v + (-0.8 if v < 0 else 0.8), i, pct(v, sinal=True), ha=ha, va="center", fontsize=TAM_TEXTO + 1,
             fontweight="bold", color=DESTAQUE if m == "M0" else TEXTO)
ax2.axvline(0, color=TEXTO, lw=0.9, zorder=3)
ax2.set_xlim(-30, 18)
ax2.set_xticks([-20, -10, 0, 10])
ax2.xaxis.set_major_formatter(formatador_num(0, "%", sinal=True))
ax2.text(0, -0.1, "negativo = previsão acima do real\n(promete demais)", transform=ax2.transAxes, ha="left",
         va="top", fontsize=TAM_NOTA - 0.5, color=CINZA_ESCURO, linespacing=1.2)

# painel 3 — ordenação
ax3 = fig.add_axes([paineis[2][0], y0, paineis[2][1], alt])
preparar(ax3, "Ordenação (Spearman)", "ponto e IC 90% · maior é melhor")
for i, m in enumerate(MODELOS):
    r = df.loc[m]
    if np.isnan(r["spearman"]):
        ax3.text(0.05, i, "— não ordena (mesmo número\n   para todas as unidades)", ha="left", va="center",
                 fontsize=TAM_NOTA - 0.5, color=CINZA_ESCURO)
        continue
    ax3.plot([r["spearman_ic90_lo"], r["spearman_ic90_hi"]], [i, i], color=COR[m], lw=2.4, zorder=2,
             solid_capstyle="round")
    ax3.scatter(r["spearman"], i, s=70, color=COR[m], edgecolor="white", lw=1.2, zorder=3)
    ax3.text(r["spearman"], i - 0.22, num(r["spearman"], 2, sinal=True), ha="center", va="bottom",
             fontsize=TAM_TEXTO + 0.5, fontweight="bold", color=DESTAQUE if m == "M0" else TEXTO)
    ax3.text(r["spearman_ic90_hi"] + 0.03, i, f"[{num(r['spearman_ic90_lo'], 2, sinal=True)}; "
             f"{num(r['spearman_ic90_hi'], 2, sinal=True)}]", ha="left", va="center", fontsize=TAM_NOTA - 1,
             color=CINZA_ESCURO)
ax3.axvline(0, color=TEXTO, lw=0.9, zorder=1)
ax3.set_xlim(-0.25, 1.28)
ax3.set_xticks([0, 0.5, 1.0])
ax3.xaxis.set_major_formatter(formatador_num(1))
ax3.text(0, -0.1, "os intervalos se sobrepõem: a diferença entre\nmodelos não é, sozinha, significativa",
         transform=ax3.transAxes, ha="left", va="top", fontsize=TAM_NOTA - 0.5, color=CINZA_ESCURO,
         linespacing=1.2)

# rótulos das categorias (coluna à esquerda, compartilhada)
for i, m in enumerate(MODELOS):
    yfig = ax_ref.transData.transform((0, i))
    yfig = fig.transFigure.inverted().transform(yfig)[1]
    l1, l2 = ROTULO[m]
    cor = DESTAQUE if m == "M0" else TEXTO
    peso = "bold" if m in ("M0", "ATUAL") else "normal"
    fig.text(X_ROT - 0.012, yfig + 0.012, l1, ha="right", va="center", fontsize=TAM_TEXTO + 0.5, color=cor,
             fontweight=peso)
    fig.text(X_ROT - 0.012, yfig - 0.017, l2, ha="right", va="center", fontsize=TAM_NOTA - 0.5,
             color=DESTAQUE if m == "M0" else CINZA_ESCURO)
    if m == "M0d":
        fig.text(X_ROT - 0.012, yfig - 0.047, "passou na régua por 2 pontos,\nmas empata nas sensibilidades",
                 ha="right", va="top", fontsize=TAM_NOTA - 1, color=CINZA_ESCURO, style="italic", linespacing=1.15)

# ------------------------------------------------------------------ dados
dados = df.reset_index()
dados["n_teste"] = 18
dados["n_so_oficial"] = n_a
dados["cobertura_faixa_p10_p90_M0_pct"] = [cobertura if m == "M0" else np.nan for m in dados["modelo"]]
salvar(fig, ID, dados)
