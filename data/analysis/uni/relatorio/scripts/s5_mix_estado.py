"""s5_mix_estado — a fatia de agregador se separa por estado, mas não muda faturamento nem payback.

Fontes:
- mix/resultado_universo_cv.md (universo de 64 unidades; medianas por grupo; SP − DF/GO +23,1 p.f. [+20,0; +26,1]);
- mix/universo_cv.csv (linhas base == "com controle 'só um'", E3 e E4; loo0/loo1/metro0/metro1 × 100);
- uni01/resultado_uni01.md (descritivo por UF: RJ mediana 0%);
- CADERNO_ESTUDO_UNI.md etapa 11 (decisão: o mix não muda faturamento/payback; erro no nº de alunos de agregador
  ~±30% → ~±23% em SP e DF/GO).
"""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _estilo import *  # noqa: E402,F403
from _estilo import _cracha  # noqa: E402

ID = "s5_mix_estado"
MD = (UNI / "mix" / "resultado_universo_cv.md").read_text(encoding="utf-8")
CV = pd.read_csv(UNI / "mix" / "universo_cv.csv", sep=";", encoding="utf-8-sig")
R01 = (UNI / "uni01" / "resultado_uni01.md").read_text(encoding="utf-8")
CAD = (UNI / "CADERNO_ESTUDO_UNI.md").read_text(encoding="utf-8")

med = {g: (float(p), int(n)) for g, p, n in re.findall(r"(DFGO|SP|outros) (\d+)% \(n=(\d+)\)", MD)}
n_univ = int(re.search(r"\*\*Universo: (\d+) unidades\*\*", MD).group(1))
m = re.search(r"SP contra DF/GO: \+(\d+\.\d) p\.f\. \[\+(\d+\.\d) p\.f\.; \+(\d+\.\d) p\.f\.\]; outros", MD)
sp_dfgo = tuple(float(x) for x in m.groups())
rj = tabela_md(R01, "| UF | unidades | mediana |").set_index("UF").loc["RJ"]
rj_med, rj_n = numero_br(rj["mediana"]), int(rj["unidades"])

base = CV[CV["base"] == "com controle 'só um'"].set_index("id")
padrao = (100 * base.loc["E3", "loo0"], 100 * base.loc["E3", "metro0"])
estado = (100 * base.loc["E3", "loo1"], 100 * base.loc["E3", "metro1"])
est_esc = (100 * base.loc["E4", "loo1"], 100 * base.loc["E4", "metro1"])
n_cv = int(base.loc["E3", "n"])

# ------------------------------------------------------------------ conferência
conferir("universo (unidades)", n_univ, 64)
conferir("N na validação cruzada", n_cv, 64)
for g, e in {"DFGO": (32, 24), "SP": (56, 24), "outros": (43, 16)}.items():
    conferir(f"mediana {g} (%)", med[g][0], e[0])
    conferir(f"n {g}", med[g][1], e[1])
conferir("soma dos n = 64", sum(v[1] for v in med.values()), 64)
for i, parte in enumerate(("efeito", "IC inf.", "IC sup.")):
    conferir(f"SP − DF/GO: {parte} (p.f.)", sp_dfgo[i], (23.1, 20.0, 26.1)[i])
conferir("RJ mediana (%)", rj_med, 0)
for nome, v, e in [("padrão da rede", padrao, (12.7, 14.3)), ("por estado", estado, (9.8, 9.5)),
                   ("estado + escritórios", est_esc, (9.6, 10.4))]:
    conferir(f"{nome}: erro sem a própria unidade", round(v[0], 1), e[0])
    conferir(f"{nome}: erro sem a metrópole", round(v[1], 1), e[1])
conferir("caderno: mix não muda faturamento nem payback", int("**não muda o faturamento nem o payback**" in CAD), 1)
conferir("caderno: ~±30% → ~±23%", int("~±30% para ~±23%" in CAD), 1)

# ------------------------------------------------------------------ figura
fig = figura()
y_topo = cabecalho(
    fig,
    "A fatia de agregador se separa por estado — SP ~56%, DF/GO ~32% — mas não muda faturamento nem payback",
    f"Proporção de alunos ativos vindos de agregador em {n_univ} unidades que aceitam ao menos um agregador",
    selo="EXPLORATÓRIO",
)
y_base = rodape(
    fig,
    f"Fonte: mix/resultado_universo_cv.md; mix/universo_cv.csv · N = {n_univ} · RJ: uni01/resultado_uni01.md "
    "(descritivo por UF, até dez/2025; uma das 3 é Cabo Frio, fora da Grande Rio) · p.f. = pontos de fração",
    nota="Cautelas: a contagem de agregador do sistema não é 100% limpa; o agrupamento foi escolhido vendo os dados; "
    "DF/GO é praticamente uma regional só (mercado e política comercial não se separam); para estado novo (RJ, MG) a "
    "regra acerta pouco.",
)
TXT_DEC = ("Mix por estado não muda faturamento nem payback da v2, que prevê o faturamento direto. Muda a divisão "
           "dos alunos e o planejamento de Wellhub/TotalPass: o erro no nº de alunos de agregador cai de ~±30% "
           "para ~±23% em SP e DF/GO.")


def altura_caixa(largura, texto, tamanho, titulo=None):
    """Mesma conta de _estilo.caixa, para posicionar a caixa pela base."""
    pad = 0.012
    h = altura_linhas(fig, quebrar(fig, texto, largura - 2 * pad, tamanho).count("\n") + 1, tamanho, 1.3)
    if titulo:
        h += altura_linhas(fig, quebrar(fig, titulo, largura - 2 * pad, tamanho + 0.5, "bold").count("\n") + 1,
                           tamanho + 0.5, 1.3) + 0.006
    return h + 2 * pad


h_cx = altura_caixa(1 - 2 * MARGEM_X, TXT_DEC, TAM_NOTA + 0.5, "Decisão")
y_cx_topo = y_base + 0.012 + h_cx
caixa(fig, MARGEM_X, y_cx_topo, 1 - 2 * MARGEM_X, TXT_DEC, tamanho=TAM_NOTA + 0.5, fundo=DESTAQUE_MUITO_CLARO,
      barra=DESTAQUE, titulo="Decisão")
y_plot_bot = y_cx_topo + 0.085
y_pt = y_topo - 0.005

# ---------------- painel esquerdo
fig.text(MARGEM_X, y_pt, "Fatia mediana de agregador nos alunos ativos", ha="left", va="top", fontsize=TAM_TEXTO,
         fontweight="bold", color=TEXTO)
fig.text(MARGEM_X, y_pt - 0.03, f"SP − DF/GO: +{num(sp_dfgo[0], 0)} pontos [+{num(sp_dfgo[1], 0)}; "
         f"+{num(sp_dfgo[2], 0)}] (IC otimista: poucos metrôs)", ha="left", va="top", fontsize=TAM_NOTA,
         color=CINZA_ESCURO)
axl = fig.add_axes([0.075, y_plot_bot, 0.36, y_pt - 0.085 - y_plot_bot])
eixo_limpo(axl, grade="y")
axl.set_facecolor("none")
grupos = [("DF/GO", "DFGO", CINZA_ESCURO), ("outros", "outros", CINZA), ("SP", "SP", DESTAQUE)]
for i, (rot, k, cor) in enumerate(grupos):
    v, n = med[k]
    axl.bar(i, v, width=0.6, color=cor, zorder=2)
    axl.text(i, v + 1.5, f"{num(v)}%", ha="center", va="bottom", fontsize=TAM_TEXTO + 2, fontweight="bold",
             color=DESTAQUE if k == "SP" else TEXTO)
    axl.text(i, 2, f"n = {n}", ha="center", va="bottom", fontsize=TAM_NOTA - 0.5, color="white", fontweight="bold")
# Grande Rio, marcador à parte
xg = 3.25
axl.axvline(2.72, color=CINZA_CLARO, lw=0.9, ymin=0, ymax=0.85)
axl.scatter(xg, 0.6, s=70, marker="D", facecolor="white", edgecolor=TEXTO, lw=1.4, zorder=4, clip_on=False)
axl.text(xg, 4, f"RJ: mediana\n{num(rj_med)}%", ha="center", va="bottom", fontsize=TAM_NOTA, fontweight="bold",
         color=TEXTO, linespacing=1.1)
axl.text(xg, 15, f"{rj_n} unidades;\na Grande Rio não\naceitava agregador\naté set/2026", ha="center",
         va="bottom", fontsize=TAM_NOTA - 1, color=CINZA_ESCURO, linespacing=1.1)
axl.set_xticks([0, 1, 2, xg])
axl.set_xticklabels(["DF/GO", "outros", "SP", "fora do\nuniverso"], fontsize=TAM_NOTA + 0.5)
for t, (_, k, cor) in zip(axl.get_xticklabels()[:3], grupos):
    t.set_color(DESTAQUE if k == "SP" else TEXTO)
    t.set_fontweight("bold")
axl.get_xticklabels()[3].set_color(CINZA_ESCURO)
axl.get_xticklabels()[3].set_fontsize(TAM_NOTA - 1)
axl.set_xlim(-0.55, 3.75)
axl.set_ylim(0, 68)
axl.set_yticks([0, 20, 40, 60])
axl.yaxis.set_major_formatter(formatador_num(0, "%"))

# ---------------- painel direito
fig.add_artist(matplotlib.lines.Line2D([0.475, 0.475], [y_plot_bot - 0.03, y_pt], color=CINZA_CLARO, lw=0.8))
fig.text(0.50, y_pt, "Erro médio da proporção prevista (pontos de fração)", ha="left", va="top",
         fontsize=TAM_TEXTO, fontweight="bold", color=TEXTO)
fig.text(0.50, y_pt - 0.03, "menor é melhor · cada unidade prevista por um modelo que não a viu", ha="left",
         va="top", fontsize=TAM_NOTA, color=CINZA_ESCURO)
axr = fig.add_axes([0.535, y_plot_bot, 0.245, y_pt - 0.085 - y_plot_bot])
eixo_limpo(axr, grade="y")
axr.set_facecolor("none")
regras = [("padrão\nda rede", padrao, CINZA_ESCURO), ("por\nestado", estado, DESTAQUE),
          ("estado +\nescritórios", est_esc, CINZA)]
W = 0.36
for i, (rot, v, cor) in enumerate(regras):
    for j, (val, alfa) in enumerate(zip(v, (1.0, 0.45))):
        x = i + (j - 0.5) * (W + 0.03)
        axr.bar(x, val, width=W, color=misturar(cor, alfa), zorder=2)
        axr.text(x, val + 0.25, num(val, 1), ha="center", va="bottom", fontsize=TAM_NOTA + 0.5,
                 fontweight="bold" if j == 0 else "normal", color=DESTAQUE if cor == DESTAQUE else TEXTO)
axr.set_xticks(range(len(regras)))
axr.set_xticklabels([r[0] for r in regras], fontsize=TAM_NOTA + 0.5, linespacing=1.1)
for t, r in zip(axr.get_xticklabels(), regras):
    if r[2] == DESTAQUE:
        t.set_color(DESTAQUE)
        t.set_fontweight("bold")
axr.set_ylim(0, 17)
axr.set_yticks([0, 5, 10, 15])
axr.yaxis.set_major_formatter(formatador_num(0))
axr.set_xlim(-0.6, 2.6)
# legenda das duas avaliações
lx = 0.795
ly = y_pt - 0.1
for j, (txt, alfa) in enumerate((("escuro: sem a própria\nunidade", 1.0), ("claro: sem a metrópole\ninteira", 0.45))):
    yy = ly - j * 0.06
    # a amostra de cor segue os dois tons usados nas barras (cinza nas demais regras, azul na regra por estado)
    for dx, cor_base in ((0.0, CINZA_ESCURO), (0.016, DESTAQUE)):
        fig.add_artist(matplotlib.patches.Rectangle((lx + dx, yy - 0.011), 0.014, 0.022, transform=fig.transFigure,
                                                    fc=misturar(cor_base, alfa), ec="none"))
    fig.text(lx + 0.036, yy, txt, ha="left", va="center", fontsize=TAM_NOTA, color=TEXTO, linespacing=1.1)
caixa(fig, lx, ly - 0.12, 1 - MARGEM_X - lx,
      "Escritórios soma ~0,2 ponto dentro das regiões conhecidas e piora em metrópole nova "
      f"({num(estado[1], 1)} → {num(est_esc[1], 1)}): fica fora.", tamanho=TAM_NOTA - 0.5)

# ------------------------------------------------------------------ dados
linhas = [dict(painel="fatia mediana de agregador", item=r, valor_pct=med[k][0], n=med[k][1])
          for r, k, _ in grupos]
linhas.append(dict(painel="fatia mediana de agregador", item="RJ (3 unidades; descritivo UNI-01)", valor_pct=rj_med,
                   n=rj_n, obs="RJ: 3 unidades, mediana 0% (Cabo Frio aceita); fora do universo de 64"))
linhas.append(dict(painel="fatia mediana de agregador", item="SP − DF/GO (p.f.)", valor_pct=sp_dfgo[0],
                   ic90_lo=sp_dfgo[1], ic90_hi=sp_dfgo[2], n=n_univ))
for r, v, _ in regras:
    linhas.append(dict(painel="erro médio da proporção (p.f.)", item=r.replace("\n", " "),
                       erro_sem_a_propria=round(v[0], 2), erro_sem_a_metropole=round(v[1], 2), n=n_cv))
salvar(fig, ID, pd.DataFrame(linhas))
