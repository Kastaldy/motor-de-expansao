"""s4_poi_nulo — empresas, shoppings e estações no entorno não melhoram a previsão, nem na Ultra nem na Smart Fit.

Fontes: poi/saidas/resultado_teste_poi.json (S1 Ultra: dR2_LOO_OLS e IC95_boot; S2 Smart Fit: dR2_GKF_metro_OLS e
IC95_boot_cluster; réplicas SkyFit e Engenharia do Corpo em 'relatado', ΔR² LOO sem IC);
poi/saidas/resultado_teste_poi.md (vereditos, N); poi/relatorio_teste_poi_2026-09-25.md (poder e decisão).
"""
from pathlib import Path
import json
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _estilo import *  # noqa: E402,F403

ID = "s4_poi_nulo"
J = json.loads((POI / "saidas" / "resultado_teste_poi.json").read_text(encoding="utf-8"))
MD = (POI / "saidas" / "resultado_teste_poi.md").read_text(encoding="utf-8")
REL = (POI / "relatorio_teste_poi_2026-09-25.md").read_text(encoding="utf-8")


def ic(s):
    a, b = s.strip("[]").split(";")
    return float(a.replace("+", "")), float(b.replace("+", ""))


n_s1 = int(re.search(r"## S1 — Ultra, faturamento Financeiro 2025 \(N = (\d+)", MD).group(1))
n_s2 = int(re.search(r"## S2 — Smart Fit, alunos 2025 \(N = (\d+)", MD).group(1))
FAM = {"F1": "Escritórios a pé", "F3": "Âncora de fluxo a pé (shopping, estação, atacarejo)",
       "F5": "Academias fora do mapeado"}
linhas = []
for fam in FAM:
    s1 = next((r for r in J["S1"] if r["familia"] == fam), None)
    if s1:
        lo, hi = ic(s1["IC95_boot"])
        linhas.append(dict(familia=fam, rede="Ultra", N=n_s1, desfecho="faturamento", validacao="LOO",
                           dR2=s1["dR2_LOO_OLS"], ic95_lo=lo, ic95_hi=hi, avaliavel=True))
    else:
        linhas.append(dict(familia=fam, rede="Ultra", N=n_s1, desfecho="faturamento", validacao="LOO",
                           dR2=np.nan, ic95_lo=np.nan, ic95_hi=np.nan, avaliavel=False))
    s2 = next(r for r in J["S2"] if r["familia"] == fam)
    lo, hi = ic(s2["IC95_boot_cluster"])
    linhas.append(dict(familia=fam, rede="Smart Fit", N=n_s2, desfecho="alunos", validacao="GroupKFold por metrô",
                       dR2=s2["dR2_GKF_metro_OLS"], ic95_lo=lo, ic95_hi=hi, avaliavel=True))
    for am, nome in [("skyfit", "SkyFit"), ("engenharia_do_corpo", "Engenharia do Corpo")]:
        r = next(x for x in J["relatado"] if x["amostra"] == am and x["variavel"] == fam)
        linhas.append(dict(familia=fam, rede=nome, N=r["N"], desfecho="alunos", validacao="LOO", dR2=r["dR2"],
                           ic95_lo=np.nan, ic95_hi=np.nan, avaliavel=True, p_perm=r["p_perm"]))
df = pd.DataFrame(linhas)
D = df.set_index(["familia", "rede"])

# ------------------------------------------------------------------ conferência
esp = {("F1", "Ultra"): (-0.031, -0.055, -0.016), ("F3", "Ultra"): (-0.028, -0.073, 0.009),
       ("F1", "Smart Fit"): (-0.043, -0.096, 0.021), ("F3", "Smart Fit"): (-0.002, -0.017, 0.003),
       ("F5", "Smart Fit"): (-0.014, -0.079, 0.013)}
for (f, r), (v, lo, hi) in esp.items():
    conferir(f"{f} {r}: ΔR²", round(D.loc[(f, r), "dR2"], 3), v, 0.0005)
    conferir(f"{f} {r}: IC95 inferior", D.loc[(f, r), "ic95_lo"], lo)
    conferir(f"{f} {r}: IC95 superior", D.loc[(f, r), "ic95_hi"], hi)
conferir("F5 na Ultra não avaliável", int(not D.loc[("F5", "Ultra"), "avaliavel"]), 1)
conferir("N Ultra", n_s1, 53)
conferir("N Smart Fit", n_s2, 454)
conferir("N SkyFit (F1)", int(D.loc[("F1", "SkyFit"), "N"]), 175)
conferir("N Engenharia do Corpo (F5)", int(D.loc[("F5", "Engenharia do Corpo"), "N"]), 36)
conferir("vereditos 'sem ganho detectável'", sum(c["veredito"].startswith("sem ganho") for c in J["criterio"]), 3)
conferir("poder na Ultra: efeito de ~13% com ~50% de chance de passar despercebido",
         int("~13% no faturamento" in REL and "~50% de chance" in REL), 1)
conferir("Smart Fit exclui efeito acima de ~2% de R²", int("acima de ~2% de R² parcial" in REL), 1)

# ------------------------------------------------------------------ figura
fig = figura()
y_topo = cabecalho(
    fig,
    "Empresas, shoppings e estações no entorno não melhoram a previsão — nem na Ultra, nem em 454 Smart Fit",
    "Ganho de previsão fora da amostra ao acrescentar cada família de POI ao modelo base; regras pré-registradas "
    "(25/09) · IC 95% (os demais usam 90%)",
)
y_base = rodape(
    fig,
    f"Fonte: poi/saidas/resultado_teste_poi.json e .md; poi/relatorio_teste_poi_2026-09-25.md · Ultra N = {n_s1}; "
    f"Smart Fit N = {n_s2}; réplicas SkyFit N = 175–176 e Engenharia do Corpo N = 35–36 (relatadas sem decidir, "
    "sem IC) · IC 95% por bootstrap",
)
ax = fig.add_axes([0.235, y_base + 0.075, 0.405, y_topo - y_base - 0.115])
eixo_limpo(ax, grade="x")
ax.spines["left"].set_visible(False)

REDES = ["Ultra", "Smart Fit", "SkyFit", "Engenharia do Corpo"]
ESTILO = {"Ultra": (DESTAQUE, 64, True), "Smart Fit": (CINZA_ESCURO, 54, True),
          "SkyFit": (CINZA, 34, False), "Engenharia do Corpo": (CINZA, 34, False)}
y = 0.0
ypos, yrot, ycab = [], [], []
for f in FAM:
    ycab.append((y, f))
    y += 0.9
    for rd in REDES:
        r = D.loc[(f, rd)]
        cor, s, forte = ESTILO[rd]
        ypos.append(y)
        yrot.append(f"{rd}  (N = {int(r['N'])})" + ("  réplica" if not forte else ""))
        if not r["avaliavel"]:
            ax.text(0.0 - 0.004, y, "não avaliável (poder)", ha="right", va="center", fontsize=TAM_NOTA - 0.5,
                    color=DESTAQUE, style="italic")
        else:
            if not np.isnan(r["ic95_lo"]):
                ax.plot([r["ic95_lo"], r["ic95_hi"]], [y, y], color=cor, lw=2.2, zorder=2, solid_capstyle="round")
            ax.scatter(r["dR2"], y, s=s, color=cor, edgecolor="white", lw=1.0, zorder=3)
            xl = r["ic95_hi"] if not np.isnan(r["ic95_hi"]) else r["dR2"]
            ax.text(xl + 0.003, y, num(r["dR2"], 3, sinal=True), ha="left", va="center",
                    fontsize=TAM_NOTA - 0.5 if not forte else TAM_NOTA, color=cor if forte else CINZA_ESCURO,
                    fontweight="bold" if rd == "Ultra" else "normal", zorder=4,
                    bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.9))
        y += 1
    y += 0.35
ax.axvline(0, color=TEXTO, lw=1.0, zorder=1)
ax.text(0.0, y - 0.05, "sem ganho", ha="center", va="bottom", fontsize=TAM_NOTA, color=TEXTO, fontweight="bold",
        zorder=4, bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"))
ax.set_yticks(ypos)
ax.set_yticklabels(yrot, fontsize=TAM_NOTA)
for t, rd in zip(ax.get_yticklabels(), [r for _ in FAM for r in REDES]):
    t.set_color(DESTAQUE if rd == "Ultra" else (TEXTO if rd == "Smart Fit" else CINZA_ESCURO))
    if rd == "Ultra":
        t.set_fontweight("bold")
ax.set_ylim(y + 0.15, -0.6)
ax.set_xlim(-0.115, 0.058)
ax.set_xticks([-0.10, -0.08, -0.06, -0.04, -0.02, 0, 0.02, 0.04])
ax.xaxis.set_major_formatter(formatador_num(2, sinal=True))
ax.set_xlabel("ΔR² fora da amostra (ganho de previsão ao acrescentar a família)", fontsize=TAM_NOTA,
              color=CINZA_ESCURO)
ax.text(-0.113, y - 0.05, "← pior que sem a variável", ha="left", va="bottom", fontsize=TAM_NOTA - 1,
        color=CINZA_ESCURO)
ax.text(0.056, y - 0.05, "melhor →", ha="right", va="bottom", fontsize=TAM_NOTA - 1, color=CINZA_ESCURO)
# cabeçalhos das famílias (à esquerda, alinhados com os rótulos)
for yc, f in ycab:
    yf = fig.transFigure.inverted().transform(ax.transData.transform((0, yc)))[1]
    fig.text(MARGEM_X, yf, f"{f} · {FAM[f]}", ha="left", va="center", fontsize=TAM_TEXTO, fontweight="bold",
             color=TEXTO)
# réplica com ΔR² positivo: declarar
r_edc5 = D.loc[("F5", "Engenharia do Corpo")]

# coluna de notas
x_col, w_col = 0.675, 1 - MARGEM_X - 0.675
yb = caixa(fig, x_col, y_topo - 0.03, w_col,
           "POI vira informação descritiva da praça, sem peso em modelo. O nulo vale para estas variáveis como foram "
           "medidas, não para \"POI em geral\".", tamanho=TAM_NOTA + 0.5, fundo=DESTAQUE_MUITO_CLARO, barra=DESTAQUE,
           titulo="Decisão")
yb = caixa(fig, x_col, yb - 0.018, w_col,
           "ΔR² negativo = acrescentar a variável equivale a acrescentar ruído; não quer dizer que POI piora a "
           "unidade.", tamanho=TAM_NOTA)
yb = caixa(fig, x_col, yb - 0.018, w_col,
           "Ultra: faturamento, validação deixando uma unidade de fora; Smart Fit: alunos, validação deixando a "
           "metrópole de fora — compare cada ponto com o zero, não as redes entre si.", tamanho=TAM_NOTA)
yb = caixa(fig, x_col, yb - 0.018, w_col,
           "Ultra: teste com pouco poder (efeito de ~13% tinha ~50% de chance de passar despercebido); Smart Fit "
           "exclui efeito acima de ~2% de R².", tamanho=TAM_NOTA)
caixa(fig, x_col, yb - 0.018, w_col,
      f"Réplicas: 1 de 6 com ΔR² acima de zero (Engenharia do Corpo, F5: {num(r_edc5['dR2'], 3, sinal=True)}, "
      f"p = {num(r_edc5['p_perm'], 2)}), dentro do que se espera por acaso.", tamanho=TAM_NOTA - 0.5,
      cor_texto=CINZA_ESCURO)

# legenda
leg = [matplotlib.lines.Line2D([], [], color=DESTAQUE, lw=2.2, marker="o", ms=7, mec="white",
                               label=f"Ultra (N = {n_s1}): ponto e IC 95%"),
       matplotlib.lines.Line2D([], [], color=CINZA_ESCURO, lw=2.2, marker="o", ms=6.5, mec="white",
                               label=f"Smart Fit (N = {n_s2}): ponto e IC 95%"),
       matplotlib.lines.Line2D([], [], color=CINZA, lw=0, marker="o", ms=5, mec="white",
                               label="réplicas: só ponto")]
ax.legend(handles=leg, loc="lower left", bbox_to_anchor=(-0.02, 1.0), ncol=3, fontsize=TAM_NOTA - 1,
          handlelength=1.4, columnspacing=1.0, handletextpad=0.4)

conferir("réplicas com ΔR² > 0", int((df[df["rede"].isin(["SkyFit", "Engenharia do Corpo"])]["dR2"] > 0).sum()), 1)
df["familia_nome"] = df["familia"].map(FAM)
salvar(fig, ID, df)
