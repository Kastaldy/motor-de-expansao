"""s2_metragem_satelite — a metragem por satélite é boa o bastante (erro típico 20%; 25% depois de corrigir o viés de +12%).

Fonte: coleta_metragem/qualidade_coleta_2026-09-29.md (tabela 'Calibração'); uni07/resultado_uni07.md (§3).
Privacidade: o avaliador do arquivo vira 'A' (primeiro nome distinto na tabela) ou 'B' (segundo);
o nome original nunca é gravado no CSV nem na imagem.
"""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _estilo import *  # noqa: E402,F403

ID = "s2_metragem_satelite"
MD = (UNI / "coleta_metragem" / "qualidade_coleta_2026-09-29.md").read_text(encoding="utf-8")
R07 = (UNI / "uni07" / "resultado_uni07.md").read_text(encoding="utf-8")

cal = tabela_md(MD, "| estimada | conhecida |")
cal.columns = ["unidade_id", "avaliador_original", "estimada", "conhecida", "razao"]
cal["estimada"] = cal["estimada"].map(numero_br)
cal["conhecida"] = cal["conhecida"].map(numero_br)
cal["razao"] = cal["estimada"] / cal["conhecida"]
ordem_aval = list(dict.fromkeys(cal["avaliador_original"]))
mapa = {nome: letra for nome, letra in zip(ordem_aval, "ABCDEFG")}
cal["avaliador"] = cal["avaliador_original"].map(mapa)
cal = cal.drop(columns="avaliador_original")
cal["unidade"] = cal["unidade_id"].map(nome_de_id)

# ------------------------------------------------------------------ conferência
vies = cal["razao"].median()
# erro típico pela regra da coleta (02_consolidar.py): mediana de |razão − 1|, sem a correção do viés
erro = (cal["razao"] - 1).abs().median() * 100
erro_corrigido = (cal["razao"] / vies - 1).abs().median() * 100
conferir("medições na calibração", len(cal), 9)
conferir("unidades na calibração", cal["unidade_id"].nunique(), 8)
conferir("viés (mediana da razão estimada/conhecida)", round(vies, 2), 1.12)
conferir("erro típico, mediana de |razão − 1| (%)", round(erro), 20, 0.5)
# revisão: 20% é ANTES da correção; depois de dividir por 1,12 a mediana nesta amostra de 9 é 25%
conferir("erro típico depois de dividir pelo viés (%)", round(erro_corrigido), 25, 0.5)
conferir("avaliadores distintos", len(ordem_aval), 2)
rec = cal[cal["unidade_id"].eq("recanto-das-emas-df")].iloc[0]
conferir("razão de Recanto das Emas", round(rec["razao"], 2), 1.90)
cot = cal[cal["unidade_id"].eq("cotia-sp")].sort_values("avaliador")
conferir("razão de Cotia, avaliador A", round(cot["razao"].iloc[0], 2), 1.40)
conferir("razão de Cotia, avaliador B", round(cot["razao"].iloc[1], 2), 1.42)
m = re.search(r"concordaram em (\d) de (\d)|Tipo de imóvel igual nos dois: (\d) de (\d)", MD)
g = [x for x in m.groups() if x]
conferir("concordância no tipo de imóvel (iguais)", int(g[0]), 1)
t3 = tabela_md(R07, "| divisão | grupo |")
sat_err = t3[(t3["divisão"] == "metragem") & (t3["grupo"] == "satélite")]["erro típico"].iloc[0]
of_err = t3[(t3["divisão"] == "metragem") & (t3["grupo"] == "oficial")]["erro típico"].iloc[0]
n_sat07 = int(t3[(t3["divisão"] == "metragem") & (t3["grupo"] == "satélite")]["N"].iloc[0])
n_of07 = int(t3[(t3["divisão"] == "metragem") & (t3["grupo"] == "oficial")]["N"].iloc[0])
conferir("UNI-07: unidades com metragem por satélite", n_sat07, 3)
conferir("UNI-07: unidades com metragem oficial", n_of07, 54)
conferir("erro típico do modelo com metragem por satélite (UNI-07, %)", numero_br(sat_err), 23)
conferir("erro típico do modelo com metragem oficial (UNI-07, %)", numero_br(of_err), 23)
n_novas = int(re.search(r"Unidades novas com metragem estimada: \*\*(\d+)\*\*", MD).group(1))
conferir("unidades novas que ganharam metragem", n_novas, 19)

# ------------------------------------------------------------------ figura
fig = figura()
y_topo = cabecalho(
    fig,
    f"A metragem por satélite é boa o bastante: erro típico de {num(erro)}% ({num(erro_corrigido)}% depois de "
    "corrigir o viés de +12%)",
    "Metragem estimada pelo Google Earth/Street View (área do telhado × andares) × metragem oficial, "
    "medida sem saber o valor",
)
y_base = rodape(
    fig,
    "Fonte: coleta_metragem/qualidade_coleta_2026-09-29.md; uni07/resultado_uni07.md · "
    "N = 9 medições em 8 unidades (amostra pequena)",
    nota=f"Erro típico pela regra da coleta: mediana de |estimada/oficial − 1| = {num(erro)}%. Depois de dividir "
    f"pelo viés de {num(vies, 2)}, a mediana nesta amostra de 9 é {num(erro_corrigido)}%: a correção acerta o "
    "nível médio, não a dispersão. Cotia: os pontos A e B foram afastados 15 m² na horizontal só para não se "
    "esconderem (valores exatos no CSV).",
)
alt = y_topo - y_base - 0.1
larg = alt * ALTURA_POL / LARGURA_POL  # eixo quadrado
ax = fig.add_axes([0.085, y_base + 0.075, larg, alt])
eixo_limpo(ax, grade="both")
lo, hi = 500, 2200
xs = np.linspace(lo, hi, 50)
ax.fill_between(xs, xs * (1 - erro / 100), xs * (1 + erro / 100), color=CINZA, alpha=0.13, lw=0, zorder=1)
ax.plot(xs, xs, color=CINZA, lw=1, zorder=2)
ax.plot(xs, xs * vies, color=DESTAQUE, lw=1.6, ls=(0, (5, 3)), zorder=2)
ax.text(2150, 2150 - 55, "sem erro", color=CINZA_ESCURO, fontsize=TAM_NOTA - 0.5, ha="right", va="top",
        rotation=45, rotation_mode="anchor", transform_rotates_text=True)
ax.text(640, 640 * vies + 25, "viés de +12%", color=DESTAQUE, fontsize=TAM_NOTA, fontweight="bold",
        ha="left", va="bottom", rotation=45, rotation_mode="anchor", transform_rotates_text=True)

marc = {"A": "o", "B": "s"}
for av, sub in cal.groupby("avaliador"):
    # Cotia tem as duas medições quase no mesmo ponto: afasta A e B 15 m² na horizontal, só no desenho
    x_des = sub["conhecida"] + np.where(sub["unidade_id"].eq("cotia-sp"), -15 if av == "A" else 15, 0)
    ax.scatter(x_des, sub["estimada"], s=62, marker=marc[av], color=CINZA_ESCURO, edgecolor="white",
               lw=1.2, zorder=4, label=f"avaliador {av}")

# rótulos das unidades (fundo branco para não brigar com as linhas)
fundo_rot = None  # sem fundo branco: não recorta a faixa sombreada
pos = {
    "centro-comendador-pr": (25, -45, "left", "center"), "samambaia-df": (25, -40, "left", "center"),
    "jundiai-sp": (0, -45, "center", "top"), "botafogo-rj": (-30, 20, "right", "center"),
    "vila-guilherme-sp": (-30, 10, "right", "center"), "vila-matilde-sp": (-30, 10, "right", "center"),
}
for _, r in cal.iterrows():
    if r["unidade_id"] in pos:
        dx, dy, ha, va = pos[r["unidade_id"]]
        ax.text(r["conhecida"] + dx, r["estimada"] + dy, r["unidade"], fontsize=TAM_NOTA - 0.5, ha=ha,
                va=va, color=TEXTO, bbox=fundo_rot, zorder=5)
ax.text(rec["conhecida"] + 35, rec["estimada"], f"Recanto das Emas (DF)\nrazão {num(rec['razao'], 2)}",
        fontsize=TAM_NOTA - 0.5, ha="left", va="center", color=TEXTO, fontweight="bold", bbox=fundo_rot, zorder=5)
ax.text(515, 1175, f"Cotia (SP)\nrazões {num(cot['razao'].iloc[0], 2)} (A)\ne {num(cot['razao'].iloc[1], 2)} (B)",
        fontsize=TAM_NOTA - 0.5, ha="left", va="bottom", color=TEXTO, fontweight="bold", bbox=fundo_rot, zorder=5)

ax.set_xlim(lo, hi)
ax.set_ylim(lo, hi)
ax.set_aspect("equal")
tk = [500, 1000, 1500, 2000]
ax.set_xticks(tk)
ax.set_yticks(tk)
ax.xaxis.set_major_formatter(formatador_num(0))
ax.yaxis.set_major_formatter(formatador_num(0))
ax.set_xlabel("metragem oficial (m²)", fontsize=TAM_NOTA, color=CINZA_ESCURO)
ax.set_ylabel("metragem estimada por satélite (m²)", fontsize=TAM_NOTA, color=CINZA_ESCURO)

# legenda e caixas à direita
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

bb = ax.get_position()
x_dir = bb.x1 + 0.06
handles = [
    Line2D([], [], marker="o", ls="", color=CINZA_ESCURO, markeredgecolor="white", markersize=8, label="avaliador A"),
    Line2D([], [], marker="s", ls="", color=CINZA_ESCURO, markeredgecolor="white", markersize=8, label="avaliador B"),
    Line2D([], [], color=CINZA, lw=1, label="sem erro (estimada = oficial)"),
    Line2D([], [], color=DESTAQUE, lw=1.6, ls=(0, (5, 3)),
           label="viés de +12%: corrigido dividindo por " + num(vies, 2)),
    Patch(fc=CINZA, alpha=0.13, label=f"erro típico: ±{num(erro)}% (mediana de |estimada/oficial − 1|)"),
]
fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(x_dir - 0.008, bb.y1 + 0.005), fontsize=TAM_NOTA,
           handlelength=2.2, labelspacing=0.7)
largura_dir = 1 - MARGEM_X - x_dir
yb = caixa(
    fig, x_dir, bb.y1 - 0.2, largura_dir,
    f"Recanto das Emas (razão {num(rec['razao'], 2)}): a academia ocupa 1 dos 2 andares do prédio — o maior "
    f"erro vem de contar andares. Cotia ({num(cot['razao'].iloc[0], 2)} e {num(cot['razao'].iloc[1], 2)}): os "
    "dois avaliadores mediram ~1.050 m² contra 750 m² oficiais — vale conferir a oficial.",
    tamanho=TAM_NOTA, titulo="Onde a medida mais erra",
)
yb = caixa(
    fig, x_dir, yb - 0.02, largura_dir,
    f"Com a correção, {n_novas} unidades novas ganharam metragem. O modelo da praça se confirma usando só as 15 "
    f"unidades com metragem oficial (erro 22%, s3). Nas {n_sat07} medidas por satélite, o erro da v2 de trabalho "
    f"({sat_err}) ficou no nível das {n_of07} oficiais ({of_err}), com N pequeno.",
    tamanho=TAM_NOTA, titulo="Bom o bastante para o modelo", fundo=DESTAQUE_MUITO_CLARO, barra=DESTAQUE,
    cor_titulo=DESTAQUE,
)
caixa(
    fig, x_dir, yb - 0.02, largura_dir,
    "O tipo de imóvel visto pelo mapa não é confiável: os dois avaliadores concordaram em 1 de 7 unidades. "
    "As categorias precisam ser redesenhadas antes de usar.",
    tamanho=TAM_NOTA, titulo="O que não serve",
)

# ------------------------------------------------------------------ dados
dados = cal[["unidade_id", "unidade", "avaliador", "estimada", "conhecida", "razao"]].copy()
dados["razao"] = dados["razao"].round(3)
salvar(fig, ID, dados)
