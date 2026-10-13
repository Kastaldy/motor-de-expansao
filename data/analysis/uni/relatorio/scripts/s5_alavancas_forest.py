"""s5_alavancas_forest — das alavancas, só o estúdio tem efeito medido no faturamento; com a master controlada, ele
já não se distingue de zero.

Fontes:
- alavancas/alavancas_corte.csv (parte B: efeito_unid / ic_lo_unid / ic_hi_unid em LOG; convertido exp(x) − 1 e
  conferido contra alavancas/resultado_alavancas.md);
- alavancas/resultado_alavancas.md (parte A: entrada do TotalPass, sensibilidades 1 e 3; parte C: erro nas 18 novas;
  conta de substituição para "não aceita agregador");
- alavancas/resultado_estudios_master_real.md (estúdios com a master real controlada; v2 de trabalho no teste).
"""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _estilo import *  # noqa: E402,F403

ID = "s5_alavancas_forest"
ALV = UNI / "alavancas"
MD = (ALV / "resultado_alavancas.md").read_text(encoding="utf-8")
MR = (ALV / "resultado_estudios_master_real.md").read_text(encoding="utf-8")
CORTE = pd.read_csv(ALV / "alavancas_corte.csv", sep=";", encoding="utf-8-sig")


def pct3(s):
    """'+10.2% [-0.6%; +22.1%]' -> (10.2, -0.6, 22.1)."""
    m = re.search(r"([+\-−]?\d+\.?\d*)%\*?\*?\s*\|?\s*\[([+\-−]?\d+\.?\d*)%; ([+\-−]?\d+\.?\d*)%\]", s)
    return tuple(float(x.replace("−", "-")) for x in m.groups())


# ------------------------------------------------------------------ parte B (CSV em log -> %)
fat = CORTE[CORTE["desfecho"] == "l_fat"].set_index("id")
b = {i: tuple(100 * (np.exp(fat.loc[i, c]) - 1) for c in ("efeito_unid", "ic_lo_unid", "ic_hi_unid"))
     for i in ("L1", "L2", "L3", "L4")}
esperado_b = {"L1": (9.7, -1.0, 21.5), "L2": (30.3, 6.8, 59.0), "L3": (5.2, -3.7, 15.0), "L4": (1.1, -4.6, 7.2)}
tb = tabela_md(MD, "| alavanca | desfecho | N | efeito (unidade de negócio) |")
tb = tb[tb["desfecho"] == "faturamento"].reset_index(drop=True)
for (i, e), (_, r) in zip(esperado_b.items(), tb.iterrows()):
    md_ef = numero_br(r["efeito (unidade de negócio)"].strip("*"))
    lo, hi = [numero_br(x) for x in r["IC 90%"].strip("[]").split(";")]
    for k, (parte, v_md) in enumerate((("efeito", md_ef), ("IC inf.", lo), ("IC sup.", hi))):
        conferir(f"{i} {parte}: CSV convertido × .md", round(b[i][k], 1), v_md, 0.051)
        conferir(f"{i} {parte}: × roteiro", round(b[i][k], 1), e[k], 0.051)
conferir("N da parte B", int(fat["n"].iloc[0]), 39)

# ------------------------------------------------------------------ parte A (entrada do TotalPass)
linha_fat = next(ln for ln in MD.splitlines() if ln.startswith("| faturamento | **"))
agr = pct3(linha_fat.replace("**", ""))
conferir("entrada do TotalPass: efeito", agr[0], 10.2)
conferir("entrada do TotalPass: IC inf.", agr[1], -0.6)
conferir("entrada do TotalPass: IC sup.", agr[2], 22.1)
tsens = tabela_md(MD, "| sensibilidade | tratadas |")
s1 = pct3(tsens.iloc[0]["faturamento"])[0]
s3 = pct3(tsens.iloc[2]["faturamento"])[0]
conferir("sensibilidade 1 (faturamento)", s1, -6.6)
conferir("sensibilidade 3 (faturamento)", s3, -1.2)
conferir("3 eventos tratados na estimativa principal", int("3 unidades tratadas" in MD), 1)
m = re.search(r"sem canibalização \(s = 0\), (-?\d+)%; com canibalização total \(s = 1\), \+?(\d+)%", MD)
sem_lo, sem_hi = float(m.group(1)), float(m.group(2))
conferir("sem agregador: referência s = 0", sem_lo, -25)
conferir("sem agregador: referência s = 1", sem_hi, 27)
conferir("conta de substituição: +486%", int("fatura **+486%**" in MD), 1)

# ------------------------------------------------------------------ estúdios com a master real
mm = re.search(r"\| M0 \+ master real \+ estúdios \| ([+\-]\d+\.\d)% \| \[([+\-]\d+\.\d)%; ([+\-]\d+\.\d)%\]", MR)
em = tuple(float(x) for x in mm.groups())
conferir("estúdios com master real: efeito", em[0], 25.7)
conferir("estúdios com master real: IC inf.", em[1], -1.1)
conferir("estúdios com master real: IC sup.", em[2], 59.7)
ret = int(re.search(r"Retenção: (\d+)%", MR).group(1))
conferir("retenção do efeito com a master real (%)", ret, 86)
v2t = re.search(r"\*\*v2 candidata: M0 → M0 \+ master real \+ estúdios\*\* \| com Botafogo \| 18 \| (\d+\.\d)% \| "
                r"(\d+\.\d)% \| .*? \| \+(\d\.\d+) → \+(\d\.\d+)", MR)
v2t = tuple(float(x) for x in v2t.groups())
conferir("v2 de trabalho no teste: erro depois (%)", v2t[1], 22.1)
conferir("v2 de trabalho no teste: ordenação depois", v2t[3], 0.69)

# ------------------------------------------------------------------ parte C (erro nas 18 novas, com Botafogo)
tc = tabela_md(MD, "| alavanca | versão | N | erro M0 |")
tc = tc[tc["versão"] == "com Botafogo"].set_index("alavanca")


def c(al):
    r = tc.loc[al]
    return (numero_br(r["erro M0"]), numero_br(r["erro M0 + alavanca"]), numero_br(r["ordenação M0"]),
            numero_br(r["ordenação M0 + alavanca"]), int(r["N"]))


c_pre, c_est, c_mod, c_vag = c("preço do plano Gold"), c("tem estúdios"), c("nº de modalidades"), \
    c("vagas de estacionamento")
for nome, v, e in [("preço", c_pre, (21.5, 23.3)), ("estúdios", c_est, (21.5, 25.0)),
                   ("modalidades", c_mod, (21.5, 25.1)), ("vagas", c_vag, (22.2, 22.7))]:
    conferir(f"parte C {nome}: erro antes", v[0], e[0])
    conferir(f"parte C {nome}: erro depois", v[1], e[1])
conferir("parte C estúdios: ordenação 0,50 → 0,73", (c_est[2], c_est[3]) == (0.50, 0.73), True)
conferir("parte C: nenhuma alavanca reduz o erro (com Botafogo)",
         int(all(v[1] > v[0] for v in (c_pre, c_est, c_mod, c_vag))), 1)


def seta(v):
    return f"{num(v[0], 1)}% → {num(v[1], 1)}%"


# ------------------------------------------------------------------ linhas
L = [
    dict(rot="Ter estúdios", ef=b["L2"], estilo="destaque",
         c1=f"não ({seta(c_est)}), mas ordena melhor ({num(c_est[2], 2)} → {num(c_est[3], 2)})",
         c2="medido, não confirmado", fonte="alavancas_corte.csv (L2, l_fat)"),
    dict(rot="Estúdios, com a master controlada", ef=em, estilo="destaque_claro",
         c1=f"v2 de trabalho: {num(v2t[0], 1)}% → {num(v2t[1], 1)}%, ordena {num(v2t[2], 2)} → {num(v2t[3], 2)}",
         c2=f"retém {ret}% do efeito, mas o intervalo cruza zero: não distingue",
         fonte="resultado_estudios_master_real.md (Q1)"),
    dict(rot="Entrar no TotalPass", ef=agr, estilo="normal", sens=(s1, s3),
         c1="—", c2="não medido: 3 eventos; em duas sensibilidades o sinal inverte",
         fonte="resultado_alavancas.md (parte A)", extra="3 eventos, dentro da unidade"),
    dict(rot="Preço do plano Gold (+R$ 10)", ef=b["L1"], estilo="normal", c1=f"não ({seta(c_pre)})",
         c2="reflete o operador pondo preço alto onde a demanda é forte", fonte="alavancas_corte.csv (L1, l_fat)"),
    dict(rot="+1 modalidade", ef=b["L3"], estilo="normal", c1=f"não ({seta(c_mod)})",
         c2="sobe o ticket ~5%, sem efeito claro no faturamento", fonte="alavancas_corte.csv (L3, l_fat)"),
    dict(rot="Dobrar as vagas", ef=b["L4"], estilo="normal", c1=f"não ({seta(c_vag)}; {c_vag[4]} unidades)",
         c2="andam junto com o tamanho", fonte="alavancas_corte.csv (L4, l_fat)"),
    dict(rot="Não aceitar agregador", ef=(np.nan, sem_lo, sem_hi), estilo="conta", c1="—",
         c2="experimento: RJ passou a aceitar Wellhub em set/2026", fonte="resultado_alavancas.md (conta de "
         "substituição, s = 0 e s = 1)", extra="conta, não medido"),
]
n = len(L)

# ------------------------------------------------------------------ figura
fig = figura()
y_topo = cabecalho(
    fig,
    "Das alavancas, só o estúdio tem efeito medido no faturamento — e, com a master controlada, ele já não se "
    "distingue de zero",
    "Efeito no faturamento com a praça controlada, 39 unidades maduras de 2025; IC 90% · ainda precisa se repetir "
    "na turma de 2026",
    selo="EXPLORATÓRIO",
)
y_base = rodape(
    fig,
    "Fonte: alavancas/resultado_alavancas.md; alavancas/alavancas_corte.csv; alavancas/resultado_estudios_master_real.md"
    " · N = 39 (conferência em 18 novas) · agregador: 3 eventos de entrada do TotalPass, cada unidade contra ela mesma",
    nota="A conta de substituição para 'sem agregador' dá +486%: extrapolação sem sentido prático, não plotada. "
    "A barra hachurada vai de nenhum aluno de agregador virar recorrente (−25%) a todos virarem (+27%).",
)

X_ROT = 0.262  # borda direita dos rótulos
X_AX0, X_AX1 = 0.275, 0.535
X_C1, W_C1 = 0.555, 0.19
X_C2, W_C2 = 0.765, 1 - MARGEM_X - 0.765
h_cab = 0.05
ax_top = y_topo - h_cab - 0.005
ax_bot = y_base + 0.075
ax = fig.add_axes([X_AX0, ax_bot, X_AX1 - X_AX0, ax_top - ax_bot])
eixo_limpo(ax, grade="x")
ax.spines["left"].set_visible(False)
ax.set_ylim(n - 0.5, -0.5)
ax.set_facecolor("none")
ax.set_xlim(-32, 66)
ax.set_xticks([-25, 0, 25, 50])
ax.xaxis.set_major_formatter(formatador_num(0, "%", sinal=True))
ax.set_yticks([])
ax.set_xlabel("efeito no faturamento", fontsize=TAM_NOTA, color=CINZA_ESCURO)
ax.axvline(0, color=TEXTO, lw=1.0, zorder=1)


def y_fig(i):
    return ax_bot + (ax_top - ax_bot) * (n - 0.5 - i) / n


# cabeçalho das colunas
y_h = y_topo - h_cab / 2
fig.text(X_ROT, y_h, "alavanca", ha="right", va="center", fontsize=TAM_NOTA, color=CINZA_ESCURO, fontweight="bold")
fig.text((X_AX0 + X_AX1) / 2, y_h, "efeito e IC 90%", ha="center", va="center", fontsize=TAM_NOTA,
         color=CINZA_ESCURO, fontweight="bold")
fig.text(X_C1, y_h, "reduziu o erro nas 18 novas?", ha="left", va="center", fontsize=TAM_NOTA, color=CINZA_ESCURO,
         fontweight="bold")
fig.text(X_C2, y_h, "leitura", ha="left", va="center", fontsize=TAM_NOTA, color=CINZA_ESCURO, fontweight="bold")
fig.add_artist(matplotlib.lines.Line2D([MARGEM_X, 1 - MARGEM_X], [y_topo - h_cab, y_topo - h_cab], color=CINZA,
                                       lw=0.8))

for i, r in enumerate(L):
    yf = y_fig(i)
    h_row = (ax_top - ax_bot) / n
    if i % 2 == 0:
        fig.add_artist(matplotlib.patches.Rectangle((MARGEM_X, yf - h_row / 2), 1 - 2 * MARGEM_X, h_row,
                                                    transform=fig.transFigure, fc=CINZA_FUNDO, ec="none", zorder=0))
    e, lo, hi = r["ef"]
    est = r["estilo"]
    cor = {"destaque": DESTAQUE, "destaque_claro": DESTAQUE_CLARO, "normal": CINZA_ESCURO, "conta": CINZA}[est]
    cor_txt = {"destaque": DESTAQUE, "destaque_claro": DESTAQUE, "normal": TEXTO, "conta": CINZA_ESCURO}[est]
    # rótulo + número
    if est == "conta":
        sub = f"{num(lo, 0, sinal=True)}% a {num(hi, 0, sinal=True)}%"
    else:
        sub = f"{num(e, 1, sinal=True)}%  [{num(lo, 1, sinal=True)}; {num(hi, 1, sinal=True)}]"
        if r.get("extra"):
            sub += f"\n{r['extra']}"
    rot = quebrar(fig, r["rot"], X_ROT - MARGEM_X - 0.01, TAM_NOTA + 0.5, "bold")
    n_rot = rot.count("\n") + 1
    n_sub = sub.count("\n") + 1
    h_tot = altura_linhas(fig, n_rot, TAM_NOTA + 0.5, 1.2) + altura_linhas(fig, n_sub, TAM_NOTA - 0.5, 1.2)
    y0 = yf + h_tot / 2
    fig.text(X_ROT, y0, rot, ha="right", va="top", fontsize=TAM_NOTA + 0.5, color=cor_txt,
             fontweight="bold" if est.startswith("destaque") else "normal", linespacing=1.1)
    fig.text(X_ROT, y0 - altura_linhas(fig, n_rot, TAM_NOTA + 0.5, 1.2), sub, ha="right", va="top",
             fontsize=TAM_NOTA - 0.5, color=cor_txt if est.startswith("destaque") else CINZA_ESCURO,
             linespacing=1.1)
    # marca no eixo
    if est == "conta":
        ax.barh(i, hi - lo, left=lo, height=0.34, color="white", edgecolor=CINZA, hatch="////", lw=0.9, zorder=2)
        ax.text((lo + hi) / 2, i, "conta, não medido", ha="center", va="center", fontsize=TAM_NOTA - 0.5,
                color=TEXTO, style="italic", zorder=4,
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none"))
    else:
        lw = 3.0 if est == "destaque" else 2.4
        ax.plot([lo, hi], [i, i], color=cor, lw=lw, zorder=2, solid_capstyle="round")
        ax.scatter(e, i, s=85 if est == "destaque" else 60, color=cor, edgecolor="white", lw=1.1, zorder=3)
        for sv in r.get("sens", ()):
            ax.scatter(sv, i, s=42, facecolor="white", edgecolor=CINZA_ESCURO, lw=1.4, zorder=4)
        if r.get("sens"):
            ax.text(np.mean(r["sens"]), i - 0.27, "sensibilidades", ha="center", va="center",
                    fontsize=TAM_NOTA - 1.5, color=CINZA_ESCURO, style="italic")
    # colunas de texto
    t1 = quebrar(fig, r["c1"], W_C1 - 0.01, TAM_NOTA - 0.5)
    fig.text(X_C1, yf, t1, ha="left", va="center", fontsize=TAM_NOTA - 0.5,
             color=TEXTO if r["c1"] != "—" else CINZA, linespacing=1.15)
    t2 = quebrar(fig, r["c2"], W_C2 - 0.005, TAM_NOTA - 0.5)
    fig.text(X_C2, yf, t2, ha="left", va="center", fontsize=TAM_NOTA - 0.5,
             color=DESTAQUE if est == "destaque" else CINZA_ESCURO,
             fontweight="bold" if est == "destaque" else "normal", linespacing=1.15)

# separador entre "medido" e "não medido"
y_sep = ax_bot + (ax_top - ax_bot) * (n - 2) / n
fig.add_artist(matplotlib.lines.Line2D([MARGEM_X, 1 - MARGEM_X], [y_sep, y_sep], color=CINZA, lw=0.9, zorder=5))

# ------------------------------------------------------------------ dados
dados = pd.DataFrame([dict(ordem=i + 1, alavanca=r["rot"], efeito_fat_pct=None if np.isnan(r["ef"][0]) else
                           round(r["ef"][0], 2), ic90_lo_pct=round(r["ef"][1], 2), ic90_hi_pct=round(r["ef"][2], 2),
                           tipo="conta (faixa s = 0 a s = 1)" if r["estilo"] == "conta" else "estimado",
                           sensibilidades_pct="; ".join(num(s, 1) for s in r.get("sens", ())),
                           reduziu_erro_18_novas=r["c1"], leitura=r["c2"], fonte=r["fonte"])
                      for i, r in enumerate(L)])
salvar(fig, ID, dados)
