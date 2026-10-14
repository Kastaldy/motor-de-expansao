"""s5_estudio_separa — nas unidades novas, as com estúdio faturaram acima do previsto e as sem estúdio, abaixo.

Fontes:
- alavancas/confirmacao_alavancas.csv, linhas id == 'L2' (valor = tem estúdio 0/1; erro_M0 = real/previsto − 1 pelo
  modelo da praça, com o ajuste de calendário do UNI-02);
- alavancas/resultado_estudios_master_real.md (composição: M2 com 6 unidades no teste, 0 com estúdio);
- alavancas/master_id_cadastro.csv + dim_unidade.parquet (cod_cadastro) só para marcar a master anonimizada (M1–M7);
- CADERNO_ESTUDO_UNI.md, etapa 10 (72 de 80 pares; 11 de 11 dentro da mesma master).
"""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _estilo import *  # noqa: E402,F403
from _estilo import _cracha  # noqa: E402

ID = "s5_estudio_separa"
ALV = UNI / "alavancas"
MR = (ALV / "resultado_estudios_master_real.md").read_text(encoding="utf-8")
CAD = (UNI / "CADERNO_ESTUDO_UNI.md").read_text(encoding="utf-8")

conf = pd.read_csv(ALV / "confirmacao_alavancas.csv", sep=";", encoding="utf-8-sig")
df = conf[conf["id"] == "L2"].copy()
df["estudio"] = df["valor"].astype(int)
df["uf"] = df["unidade_id"].str[-2:].str.upper()
df["rotulo"] = [nome_unidade(n, u) for n, u in zip(df["nome"], df["uf"])]

# master anonimizada (M1–M7): cod_cadastro do painel × master_id_cadastro.csv (zfill(2), como em 07_*.py)
dim = pd.read_parquet(UNI / "dim_unidade.parquet", columns=["unidade_id", "cod_cadastro"])
dim["cod_cadastro"] = dim["cod_cadastro"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(2)
mid = pd.read_csv(ALV / "master_id_cadastro.csv", sep=";", dtype=str)
mid["cod_cadastro"] = mid["cod_cadastro"].str.zfill(2)
df = df.merge(dim, on="unidade_id", how="left").merge(mid, on="cod_cadastro", how="left")
# grupos do modelo: masters com < 4 unidades no treino vão para 'outras' (resultado_estudios_master_real.md)
grupos_modelo = re.search(r"Grupos: (.*?)\. Masters com", MR).group(1)
proprios = re.findall(r"(M\d) \((?:referência, )?\d+(?: no treino)?\)", grupos_modelo)
df["grupo_master"] = np.where(df["master_id"].isin(proprios), df["master_id"], "outras")

com = df[df["estudio"] == 1]
sem = df[df["estudio"] == 0]
med_com, med_sem = com["erro_M0"].median(), sem["erro_M0"].median()
pares = [(a, b) for a in com.itertuples() for b in sem.itertuples()]
acima = sum(a.erro_M0 > b.erro_M0 for a, b in pares)
pares_mm = [(a, b) for a, b in pares if a.grupo_master == b.grupo_master]
acima_mm = sum(a.erro_M0 > b.erro_M0 for a, b in pares_mm)
pares_strict = [(a, b) for a, b in pares if a.master_id == b.master_id]
acima_strict = sum(a.erro_M0 > b.erro_M0 for a, b in pares_strict)
m2_sem = int(((df["master_id"] == "M2") & (df["estudio"] == 0)).sum())
m2_com = int(((df["master_id"] == "M2") & (df["estudio"] == 1)).sum())

# ------------------------------------------------------------------ conferência
conferir("N de unidades novas", len(df), 18)
conferir("com estúdio", len(com), 8)
conferir("sem estúdio", len(sem), 10)
conferir("mediana com estúdio (%)", round(100 * med_com), 54, 0.5)
conferir("mediana sem estúdio (%)", round(100 * med_sem), -21, 0.5)
conferir("pares (com, sem)", len(pares), 80)
conferir("pares em que a com estúdio fica acima", acima, 72)
conferir("pares dentro do mesmo grupo de master (modelo)", len(pares_mm), 11)
conferir("… com a de estúdio acima", acima_mm, 11)
conferir("todas as 18 com master ligada", int(df["master_id"].notna().sum()), 18)
conferir("M2 no teste sem estúdio", m2_sem, 6)
conferir("M2 no teste com estúdio", m2_com, 0)
conferir("resultado_estudios_master_real.md: M2 6 no teste, 0 com estúdio", int("M2: 10 / 6 (com estúdio 6 / 0)" in MR), 1)
conferir("caderno cita 72 de 80 pares", int("72 de 80 pares" in CAD), 1)
conferir("Botafogo +185%", round(100 * df.loc[df["nome"] == "BOTAFOGO", "erro_M0"].iloc[0]), 185, 0.5)

# ------------------------------------------------------------------ figura
fig = figura()
y_topo = cabecalho(
    fig,
    "Nas unidades novas, as com estúdio faturaram acima do previsto (+54%) e as sem estúdio, abaixo (−21%)",
    "Faturamento real × previsto pelo modelo da praça nas 18 unidades novas, por presença de estúdio",
    selo="EXPLORATÓRIO",
)
y_base = rodape(
    fig,
    "Fonte: alavancas/confirmacao_alavancas.csv (L2); alavancas/resultado_estudios_master_real.md · N = 18 · "
    "faturou vs. previsto = real/previsto − 1 (modelo da praça: m², renda e população); estúdio = cadastro de ago/2026",
)

X_AX0, X_AX1 = 0.10, 0.60
ax = fig.add_axes([X_AX0, y_base + 0.07, X_AX1 - X_AX0, y_topo - y_base - 0.10])
eixo_limpo(ax, grade="y")
ax.set_facecolor("none")
ax.set_yscale("log")
Y0, Y1 = 0.42, 3.25
ax.set_ylim(Y0, Y1)
ticks = [-50, -25, 0, 50, 100, 200]
ax.set_yticks([1 + t / 100 for t in ticks])
ax.set_yticklabels([pct(t, sinal=True) if t else "0%" for t in ticks])
ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
ax.set_ylabel("faturou vs. previsto pelo modelo da praça", fontsize=TAM_NOTA, color=CINZA_ESCURO)
ax.axhline(1, color=TEXTO, lw=1.0, zorder=1)
XC = {1: 0.0, 0: 1.40}
ax.set_xlim(-0.85, 2.6)
ax.set_xticks([XC[1], XC[0]])
ax.set_xticklabels([f"com estúdio (n = {len(com)})", f"sem estúdio (n = {len(sem)})"], fontsize=TAM_TEXTO)
for t, cor in zip(ax.get_xticklabels(), (DESTAQUE, CINZA_ESCURO)):
    t.set_color(cor)
    t.set_fontweight("bold")
ax.text(-0.82, 1.0, "acertou", ha="left", va="bottom", fontsize=TAM_NOTA - 0.5, color=TEXTO)

# altura de uma linha de rótulo em unidades de log10
bb = ax.get_position()
h_in = bb.height * ALTURA_POL
dec_por_pol = (np.log10(Y1) - np.log10(Y0)) / h_in
GAP = 11.5 / 72 * dec_por_pol


def repelir(ys, gap):
    """Posições de rótulo ordenadas, com espaçamento mínimo `gap`, o mais perto possível das originais."""
    ordem = np.argsort(ys)
    y = np.array(ys, float)[ordem]
    pos = y.copy()
    for _ in range(200):
        mudou = False
        for i in range(1, len(pos)):
            d = pos[i] - pos[i - 1]
            if d < gap:
                ajuste = (gap - d) / 2
                pos[i - 1] -= ajuste
                pos[i] += ajuste
                mudou = True
        if not mudou:
            break
    out = np.empty_like(pos)
    out[ordem] = pos
    return out


linhas_csv = []
for est, g in ((1, com), (0, sem)):
    xc = XC[est]
    cor = DESTAQUE if est else CINZA_ESCURO
    ly = np.log10(1 + g["erro_M0"].to_numpy())
    # desloca em x os pontos muito próximos (beeswarm simples)
    ordem = np.argsort(ly)
    dx = np.zeros(len(ly))
    for k in range(1, len(ordem)):
        i, j = ordem[k], ordem[k - 1]
        if abs(ly[i] - ly[j]) < 0.02:
            dx[i] = dx[j] + 0.09 if dx[j] <= 0 else -dx[j]
    xs = xc - 0.05 + dx * 0.9
    lab_y = repelir(ly, GAP)
    x_lab = xc + 0.28
    for (row, x, yl, yl_lab) in zip(g.itertuples(), xs, ly, lab_y):
        m2 = row.master_id == "M2"
        ax.scatter(x, 10 ** yl, s=70, color=cor, edgecolor="white", lw=1.1, zorder=4)
        if m2:
            ax.scatter(x, 10 ** yl, s=175, facecolor="none", edgecolor=TEXTO, lw=1.2, zorder=3)
        rot = f"{row.rotulo}  {pct(100 * row.erro_M0, sinal=True)}"
        ax.plot([x + 0.05, x_lab - 0.02], [10 ** yl, 10 ** yl_lab], color=CINZA_CLARO, lw=0.7, zorder=2)
        ax.text(x_lab, 10 ** yl_lab, rot, ha="left", va="center", fontsize=TAM_NOTA - 0.5,
                color=cor if est else TEXTO, zorder=5,
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none"))
        linhas_csv.append(dict(unidade_id=row.unidade_id, rotulo=row.rotulo, tem_estudio=est,
                               master_anonimizada=row.master_id, grupo_master_modelo=row.grupo_master,
                               faturou_vs_previsto=round(row.erro_M0, 4)))
    med = g["erro_M0"].median()
    ax.plot([xc - 0.27, xc + 0.17], [1 + med, 1 + med], color=cor, lw=2.6, zorder=3, solid_capstyle="butt")
    if est:
        ax.text(xc - 0.29, 1 + med, f"mediana\n{pct(100 * med, sinal=True)}", ha="right", va="center",
                fontsize=TAM_NOTA, color=cor, fontweight="bold", linespacing=1.05)
    else:  # uma linha, logo abaixo do traço, para não encostar nos rótulos do outro grupo
        ax.annotate(f"mediana {pct(100 * med, sinal=True)}", xy=(xc - 0.27, 1 + med), xytext=(xc - 0.30, 0.735),
                    ha="right", va="center", fontsize=TAM_NOTA, color=cor, fontweight="bold",
                    arrowprops=dict(arrowstyle="-", color=cor, lw=0.8, shrinkA=1, shrinkB=1))

# (a legenda do anel M2 fica fora do eixo, na coluna da direita)

# ------------------------------------------------------------------ coluna da direita
X_C, W_C = 0.645, 1 - MARGEM_X - 0.645
y = y_topo - 0.02
fig.text(X_C, y, f"{acima} de {len(pares)}", ha="left", va="top", fontsize=26, fontweight="bold", color=DESTAQUE)
fig.text(X_C + largura_texto(fig, f"{acima} de {len(pares)}", 26, "bold") + 0.012, y - 0.012,
         f"pares ({num(100 * acima / len(pares))}%)", ha="left", va="top", fontsize=TAM_TEXTO + 1, color=DESTAQUE,
         fontweight="bold")
y -= 0.075
t = quebrar(fig, "Comparando cada unidade com estúdio com cada uma sem estúdio, a com estúdio ficou mais acima do "
            f"previsto em {acima} de {len(pares)} pares. Dentro do mesmo grupo de master: {acima_mm} de "
            f"{len(pares_mm)}.", W_C, TAM_NOTA + 0.5)
fig.text(X_C, y, t, ha="left", va="top", fontsize=TAM_NOTA + 0.5, color=TEXTO, linespacing=1.3)
y -= altura_linhas(fig, t.count("\n") + 1, TAM_NOTA + 0.5, 1.3) + 0.012
t = quebrar(fig, "A direção é firme; o tamanho do efeito (+26% a +30%) é incerto.", W_C, TAM_NOTA + 0.5, "bold")
fig.text(X_C, y, t, ha="left", va="top", fontsize=TAM_NOTA + 0.5, color=TEXTO, fontweight="bold", linespacing=1.3)
y -= altura_linhas(fig, t.count("\n") + 1, TAM_NOTA + 0.5, 1.3) + 0.025
y = caixa(fig, X_C, y, W_C,
          "Estúdio é o retrato de ago/2026 contra o desfecho: unidade que vai bem pode ter aberto estúdio depois.",
          tamanho=TAM_NOTA, titulo="Cautelas", barra=AMBAR)
y = caixa(fig, X_C, y - 0.012, W_C,
          f"As {m2_sem} unidades novas da master M2 estão todas sem estúdio: estúdio e operador se confundem até o "
          "teste do operador.", tamanho=TAM_NOTA, barra=AMBAR)
y = caixa(fig, X_C, y - 0.03, W_C,
          "Estúdios + master real entram na v2 de trabalho; conferência na turma de 2026, já congelada.",
          tamanho=TAM_NOTA + 0.5, fundo=DESTAQUE_MUITO_CLARO, barra=DESTAQUE, titulo="Decisão do dono")
# legenda do anel (fora da área de dados; cor neutra, diferente da dos selos)
y_leg = y - 0.045
x_leg = X_C + 0.012
fig.add_artist(matplotlib.lines.Line2D([x_leg], [y_leg], marker="o", markersize=np.sqrt(175), markerfacecolor="none",
                                       markeredgecolor=TEXTO, markeredgewidth=1.2, transform=fig.transFigure))
fig.add_artist(matplotlib.lines.Line2D([x_leg], [y_leg], marker="o", markersize=np.sqrt(70),
                                       markerfacecolor=CINZA_ESCURO, markeredgecolor="white", markeredgewidth=1.1,
                                       transform=fig.transFigure))
fig.text(x_leg + 0.018, y_leg, f"anel = unidade da master M2\n({m2_sem} unidades, todas sem estúdio)", ha="left",
         va="center", fontsize=TAM_NOTA, color=TEXTO, linespacing=1.2)

# ------------------------------------------------------------------ dados
dados = pd.DataFrame(linhas_csv).sort_values(["tem_estudio", "faturou_vs_previsto"], ascending=[False, False])
dados["mediana_grupo"] = np.where(dados["tem_estudio"] == 1, round(med_com, 4), round(med_sem, 4))
dados["pares_com_acima"] = f"{acima} de {len(pares)}"
dados["pares_mesmo_grupo_master"] = f"{acima_mm} de {len(pares_mm)} (M1, M2, M3 e 'outras', como no modelo); " \
    f"mesma master estrita: {acima_strict} de {len(pares_strict)}"
salvar(fig, ID, dados)
