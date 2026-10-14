"""s1_payback_prometido — no payback, a regra atual promete demais às fracas e de menos às fortes.

Fonte: uni05/comparacao_por_unidade.csv (grupo == 'teste'; v1.1 do UNI-05).
x = payback real no simulador (REAL = faturamento que a unidade de fato teve + rampa observada);
y = payback prometido pela regra atual. Payback acima de 60 meses conta como 61.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _estilo import *  # noqa: E402,F403

ID = "s1_payback_prometido"
FONTE = UNI / "uni05" / "comparacao_por_unidade.csv"
CORTE = 36
X_CENSURA = 67  # posição da coluna '>60' no eixo x

df = pd.read_csv(FONTE, sep=";", encoding="utf-8-sig")
df = df[df["grupo"].eq("teste")].copy().reset_index(drop=True)
for c in ("ok_REAL", "ok_ATUAL"):
    df[c] = df[c].astype(str).str.lower().eq("true")
df["rotulo"] = [nome_unidade(n) for n in df["nome"]]

indevida = df["ok_REAL"] & ~df["ok_ATUAL"]
aprov_indevida = ~df["ok_REAL"] & df["ok_ATUAL"]
censurada = df["pb_REAL"].ge(61)
df["grupo_visual"] = np.where(indevida, "rejeição indevida (se pagou, a regra recusaria)",
                              np.where(censurada, "não se paga em 5 anos", "demais"))

# ------------------------------------------------------------------ conferência
conferir("N de unidades de teste", len(df), 18)
conferir("rejeições indevidas (ok_REAL e não ok_ATUAL)", int(indevida.sum()), 5)
conferir("aprovações indevidas", int(aprov_indevida.sum()), 0)
conferir("unidades viáveis no REAL", int(df["ok_REAL"].sum()), 8)
esperadas = {"VILA GUANABARA", "CARIACICA", "BOTANIC MALL", "BUTANTA", "BOTAFOGO"}
conferir("rejeições indevidas são as 5 esperadas", int(set(df.loc[indevida, "nome"]) == esperadas), 1)
cens = df[censurada & df["pb_ATUAL"].lt(61)]
conferir("não se pagam em 5 anos (pb_REAL = 61, pb_ATUAL < 61)", len(cens), 8)
conferir("prometido mínimo dessas 8 (meses)", cens["pb_ATUAL"].min(), 37)
conferir("prometido máximo dessas 8 (meses)", cens["pb_ATUAL"].max(), 58)
conferir("todas as 8 acima do corte de 36 meses", int((cens["pb_ATUAL"] > CORTE).all()), 1)
fortes = df[df["nome"].isin(["NOROESTE", "BOTAFOGO", "BUTANTA"])]
conferir("payback real das 3 mais fortes: mínimo", fortes["pb_REAL"].min(), 12)
conferir("payback real das 3 mais fortes: máximo", fortes["pb_REAL"].max(), 18)
conferir("prometido às 3 mais fortes: mínimo", fortes["pb_ATUAL"].min(), 31)
conferir("prometido às 3 mais fortes: máximo", fortes["pb_ATUAL"].max(), 53)
conferir("CPA tem pb_REAL = 60 (não censurada)", df.loc[df["nome"].eq("CPA"), "pb_REAL"].iloc[0], 60)
# erro típico do payback da regra atual nas não censuradas (resultado_uni05.md: 20 meses)
nc = df[~censurada]
erro_nc = (nc["pb_ATUAL"] - nc["pb_REAL"]).abs().median()
conferir("erro típico do payback da regra atual nas não censuradas (meses)", erro_nc, 20, 0.5)

# posição x com jitter na coluna '>60'
df["x_plot"] = df["pb_REAL"].astype(float)
ordem = df[censurada].sort_values("pb_ATUAL").index
offsets = [-1.6, 0.0, 1.6]
for k, idx in enumerate(ordem):
    df.loc[idx, "x_plot"] = X_CENSURA + offsets[k % 3]

# ------------------------------------------------------------------ figura
fig = figura()
y_topo = cabecalho(
    fig,
    "No payback, a regra atual promete demais às fracas e de menos às fortes",
    "Payback prometido pela regra de hoje × payback real no simulador de produção, "
    "18 unidades abertas em 2025, custos-padrão",
)
y_base = rodape(
    fig,
    "Fonte: uni05/comparacao_por_unidade.csv; uni05/resultado_uni05.md (v1.1) · N = 18 · "
    "aluguel R$ 20 mil/mês, obra R$ 2,34 mi; payback acima de 60 meses conta como 61",
)
ax = fig.add_axes([0.075, y_base + 0.085, 0.555, y_topo - y_base - 0.11])
eixo_limpo(ax, grade=None)
ax.set_xlim(6, 72)
ax.set_ylim(22, 62)

# quadrantes pelo corte de 36 meses
ax.axvline(CORTE, color=CINZA, lw=1, ls=(0, (4, 3)), zorder=1)
ax.axhline(CORTE, color=CINZA, lw=1, ls=(0, (4, 3)), zorder=1)
ax.axvspan(6, CORTE, ymin=(CORTE - 22) / 40, ymax=1, color=DESTAQUE_MUITO_CLARO, lw=0, zorder=0)
kw = dict(fontsize=TAM_NOTA, color=CINZA_ESCURO, style="italic")
ax.text(7, 61.3, "recusaria e se pagou", ha="left", va="top", color=DESTAQUE, fontsize=TAM_NOTA,
        style="italic", fontweight="bold")
ax.text(7, 23, "aprovaria e se pagou", ha="left", va="bottom", **kw)
ax.text(62.5, 23, "aprovaria e não se pagou: nenhuma", ha="right", va="bottom", **kw)
ax.text(62.5, 61.3, "recusaria e não se pagou", ha="right", va="top", **kw)

# diagonal y = x
ax.plot([22, 62], [22, 62], color=CINZA_CLARO, lw=1.2, zorder=1)
ax.text(46.5, 47.3, "previsto = real", rotation=45, rotation_mode="anchor", transform_rotates_text=True,
        color=CINZA, fontsize=TAM_NOTA - 0.5, ha="center", va="bottom")

# separador da coluna '>60'
ax.axvline(63.5, color=CINZA_CLARO, lw=0.8, zorder=1)

cores = np.where(indevida, DESTAQUE, CINZA_ESCURO)
ax.scatter(df["x_plot"], df["pb_ATUAL"], s=70, color=cores, edgecolor="white", lw=1.2, zorder=4)

# rótulos
desloc = {
    "NOROESTE": (1.2, 1.6, "left"), "BOTAFOGO": (1.2, 0.9, "left"), "BUTANTA": (1.2, 1.6, "left"),
    "BOTANIC MALL": (1.2, 0.4, "left"), "CARIACICA": (1.2, 0.4, "left"),
    "VILA GUANABARA": (-1.2, 0.0, "right"),
    "VALPARAISO": (-1.2, -1.4, "right"), "FLORIANO": (-1.2, 0.0, "right"), "CPA": (-1.1, 1.0, "right"),
}
r_par = df[df["nome"].eq("PARANOA PARQUE")].iloc[0]
ax.annotate(r_par["rotulo"], xy=(r_par["x_plot"], r_par["pb_ATUAL"]), xytext=(38.2, 33.4), ha="left",
            va="center", fontsize=TAM_NOTA, color=TEXTO,
            arrowprops=dict(arrowstyle="-", color=CINZA, lw=0.8, shrinkA=1, shrinkB=5))
for _, r in df.iterrows():
    if r["nome"] in desloc:
        dx, dy, ha = desloc[r["nome"]]
        destaque = bool(indevida.loc[_])
        txt = r["rotulo"]
        if r["nome"] in ("NOROESTE", "BOTAFOGO", "BUTANTA"):
            txt += f"  ({int(r['pb_REAL'])} × {int(r['pb_ATUAL'])} meses)"
        ax.text(r["x_plot"] + dx, r["pb_ATUAL"] + dy, txt, ha=ha, va="center",
                fontsize=TAM_NOTA, color=DESTAQUE if destaque else TEXTO,
                fontweight="bold" if destaque else "normal")

# eixos
ax.set_xticks([12, 24, 36, 48, 60, X_CENSURA])
ax.set_xticklabels(["12", "24", "36", "48", "60", ">60"])
ax.set_yticks([24, 30, 36, 42, 48, 54, 60])
ax.set_xlabel("payback real no simulador (meses) — \"se pagou\" = em até 36 meses", fontsize=TAM_NOTA,
              color=CINZA_ESCURO)
ax.set_ylabel("payback prometido pela regra atual (meses)", fontsize=TAM_NOTA, color=CINZA_ESCURO)
ax.text(CORTE + 0.4, 58.5, "corte: 36 meses", fontsize=TAM_NOTA - 0.5, color=CINZA_ESCURO, rotation=90,
        va="top", ha="left")

# colchete sobre a coluna '>60'
yb0, yb1 = cens["pb_ATUAL"].min(), cens["pb_ATUAL"].max()
xb = X_CENSURA + 3.0
ax.plot([xb - 0.6, xb, xb, xb - 0.6], [yb0, yb0, yb1, yb1], color=TEXTO, lw=1, clip_on=False, zorder=5)
bb = ax.get_position()
y_fig = lambda v: bb.y0 + (v - 22) / 40 * bb.height  # noqa: E731
texto_colchete = (f"{len(cens)} unidades que não se pagam em 5 anos: prometidos {int(yb0)}–{int(yb1)} "
                  "meses, todos acima do corte")
caixa(fig, bb.x1 + 0.035, y_fig(yb1) + 0.02, 0.29, texto_colchete, tamanho=TAM_TEXTO,
      fundo=FUNDO, barra=TEXTO)

# legenda e caixa de decisão
from matplotlib.lines import Line2D  # noqa: E402

handles = [
    Line2D([], [], marker="o", ls="", color=DESTAQUE, markeredgecolor="white", markersize=8.5,
           label="se pagou em até 36 meses, mas a regra recusaria"),
    Line2D([], [], marker="o", ls="", color=CINZA_ESCURO, markeredgecolor="white", markersize=8.5,
           label="demais unidades"),
]
fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(bb.x1 + 0.03, y_fig(33)), fontsize=TAM_NOTA,
           handletextpad=0.3, labelspacing=0.6)
caixa(
    fig, bb.x1 + 0.035, y_fig(27.5), 0.29,
    f"Na decisão: {int(aprov_indevida.sum())} aprovações indevidas e {int(indevida.sum())} rejeições "
    "indevidas. A v2 também recusa 5 (ver seção 6).",
    tamanho=TAM_TEXTO, titulo="Corte de viabilidade: payback em até 36 meses",
)

# ------------------------------------------------------------------ dados
dados = df[["nome", "uf", "pb_REAL", "pb_ATUAL", "ok_REAL", "ok_ATUAL", "grupo_visual"]].copy()
dados["x_plot"] = df["x_plot"].round(2)
salvar(fig, ID, dados)
