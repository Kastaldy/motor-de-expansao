"""s4_diretor_replica — a hipótese do diretor aparece com o mesmo tamanho em outra rede: evidência a favor, sem prova.

Fontes: uni02r/resultado_uni02r.md (Ultra faturamento e alunos; Engenharia do Corpo; EdC + Pacer; IC 90% HC3);
uni02/resultado_uni02.md (M0d nas 18 unidades novas); uni01/resultado_duas_partes.md (M0d: R² LOO contra M0).
"""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _estilo import *  # noqa: E402,F403

ID = "s4_diretor_replica"
R2R = (UNI / "uni02r" / "resultado_uni02r.md").read_text(encoding="utf-8")
R02 = (UNI / "uni02" / "resultado_uni02.md").read_text(encoding="utf-8")
DP = (UNI / "uni01" / "resultado_duas_partes.md").read_text(encoding="utf-8")

t = tabela_md(R2R, "| amostra | desfecho | N |")
t["amostra"] = t["amostra"].str.replace("*", "", regex=False)


def ic(s):
    a, b = s.strip("[]").split(",")
    return float(a.replace("+", "")), float(b.replace("+", ""))


def linha(amostra_contem, desfecho):
    r = t[t["amostra"].str.contains(amostra_contem, regex=False) & t["desfecho"].eq(desfecho)].iloc[0]
    lo, hi = ic(r["IC 90%"])
    md = r["mín. detectável"]
    return dict(efeito=float(r["efeito"].replace("+", "")), lo=lo, hi=hi, N=int(r["N"]),
                min_detectavel=float(md) if md not in ("–", "-", "") else np.nan,
                cidades=r["cidades"], sinal=r["mesmo sinal ao tirar cada cidade"])


L = [
    dict(rotulo="Ultra — faturamento", **linha("Ultra (referência, UNI-01)", "faturamento"), grupo="ultra"),
    dict(rotulo="Ultra — alunos", **linha("Ultra (referência)", "alunos"), grupo="ultra"),
    dict(rotulo="Engenharia do Corpo — alunos", **linha("Engenharia do Corpo (primária)", "alunos"), grupo="edc"),
    dict(rotulo="Engenharia do Corpo + Pacer — alunos", **linha("EdC + Pacer", "alunos"), grupo="outra"),
]
princ = tabela_md(R02, "| modelo | erro típico |").set_index("modelo")
e_m0d, e_m0 = numero_br(princ.loc["M0d", "erro típico"]), numero_br(princ.loc["M0", "erro típico"])
v_m0d = numero_br(princ.loc["M0d", "viés"])
sens = tabela_md(R02, "| cenário | N teste |")
m0d_sens = [numero_br(x.split(";")[0]) for x in sens["M0d"]]
m0_sens = [numero_br(x.split(";")[0]) for x in sens["M0"]]
dp = tabela_md(DP, "| variante | descrição |").set_index("variante")
ganho_r2 = float(dp.loc["M0d", "R² fora da amostra (LOO)"]) - float(dp.loc["M0", "R² fora da amostra (LOO)"])
regua = 0.02

# ------------------------------------------------------------------ conferência
esp = [(0.34, 0.04, 0.65, 39), (0.40, 0.12, 0.69, 39), (0.30, -0.40, 1.01, 36), (0.35, -0.27, 0.97, 45)]
for r, (e, lo, hi, n) in zip(L, esp):
    conferir(f"{r['rotulo']}: efeito", r["efeito"], e)
    conferir(f"{r['rotulo']}: IC inferior", r["lo"], lo)
    conferir(f"{r['rotulo']}: IC superior", r["hi"], hi)
    conferir(f"{r['rotulo']}: N", r["N"], n)
conferir("Engenharia do Corpo: cidades", int(L[2]["cidades"]), 27)
conferir("Engenharia do Corpo: mesmo sinal em 27 de 27", int(L[2]["sinal"] == "27 de 27"), 1)
conferir("valor da Ultra dentro do IC da Engenharia do Corpo", int(L[2]["lo"] <= L[0]["efeito"] <= L[2]["hi"]), 1)
conferir("M0d nas 18 novas: erro típico (%)", e_m0d, 20)
conferir("M0 nas 18 novas: erro típico (%)", e_m0, 22)
conferir("M0d nas 18 novas: viés (%)", v_m0d, 8)
# sensibilidades (a) só metragem oficial e (b) satélite sem correção: erro típico igual ao do M0
conferir("M0d = M0 nas sensibilidades (a) e (b)", sum(a == b for a, b in zip(m0d_sens[1:3], m0_sens[1:3])), 2)
conferir("ganho de R² fora da amostra do M0d (2025)", round(ganho_r2, 3), 0.013)
conferir("menor efeito detectável na Engenharia do Corpo", L[2]["min_detectavel"], 1.06)

# ------------------------------------------------------------------ figura
fig = figura()
y_topo = cabecalho(
    fig,
    "A hipótese do diretor aparece com o mesmo tamanho em outra rede — evidência a favor, ainda sem prova",
    "Hipótese do diretor: unidade maior rende proporcionalmente mais onde a concorrência é de academias pequenas e "
    "independentes; IC 90%",
    selo="EXPLORATÓRIO",
)
y_base = rodape(
    fig,
    "Fonte: uni02r/resultado_uni02r.md; uni02/resultado_uni02.md; uni01/resultado_duas_partes.md · IC 90% · "
    "Engenharia do Corpo: 36 unidades em 27 cidades; Pacer: 9 unidades",
    nota="Limites: as outras redes só informam alunos (não faturamento); sem data de inauguração (maturidade não "
    "controlada); preço e posicionamento diferentes da Ultra. Definição técnica do eixo: aumento da elasticidade do "
    "faturamento (ou dos alunos) ao m² por degrau típico (1 desvio-padrão) da fração de academias independentes em "
    "volta.",
)
x0, x1 = 0.3, 0.7
ax = fig.add_axes([x0, y_base + 0.1, x1 - x0, y_topo - y_base - 0.17])
eixo_limpo(ax, grade="x")
ax.spines["left"].set_visible(False)
ult = L[0]["efeito"]
ax.axvspan(ult - 0.015, ult + 0.015, color=DESTAQUE, alpha=0.12, lw=0, zorder=0)
ax.axvline(0, color=TEXTO, lw=1.0, zorder=1)
ys = [0, 1, 2.35, 3.35]
for yv, r in zip(ys, L):
    cor = {"ultra": CINZA_ESCURO, "edc": DESTAQUE, "outra": CINZA}[r["grupo"]]
    ax.plot([r["lo"], r["hi"]], [yv, yv], color=cor, lw=3.0 if r["grupo"] == "edc" else 2.4, zorder=2,
            solid_capstyle="round")
    ax.scatter(r["efeito"], yv, s=90 if r["grupo"] == "edc" else 62, color=cor, edgecolor="white", lw=1.1,
               zorder=3)
    ax.text(r["hi"] + 0.04, yv, f"{num(r['efeito'], 2, sinal=True)}  [{num(r['lo'], 2, sinal=True)}; "
            f"{num(r['hi'], 2, sinal=True)}]", ha="left", va="center",
            fontsize=TAM_NOTA + (1 if r["grupo"] == "edc" else 0),
            color=cor if r["grupo"] != "outra" else CINZA_ESCURO,
            fontweight="bold" if r["grupo"] == "edc" else "normal")
    if r["grupo"] in ("edc", "outra"):
        a, b = r["sinal"].split(" de ")
        ax.text(r["hi"] + 0.04, yv + 0.32, f"mesmo sinal em {a} de {b} retiradas de cidade", ha="left", va="center",
                fontsize=TAM_NOTA - 1.5, color=CINZA_ESCURO)
ax.set_yticks(ys)
ax.set_yticklabels([f"{r['rotulo']}  (N = {r['N']})" for r in L], fontsize=TAM_NOTA + 0.5)
for tl, r in zip(ax.get_yticklabels(), L):
    if r["grupo"] == "edc":
        tl.set_color(DESTAQUE)
        tl.set_fontweight("bold")
ax.set_ylim(3.9, -0.95)
ax.set_xlim(-0.6, 1.75)
ax.set_xticks([-0.5, 0, 0.5, 1.0])
ax.xaxis.set_major_formatter(formatador_num(1, sinal=True))
ax.set_xlabel("quanto cada m² a mais rende a mais onde há +1 degrau de academias independentes\nem volta "
              "(0 = nenhum efeito; à direita = o tamanho rende mais)", fontsize=TAM_NOTA, color=CINZA_ESCURO,
              linespacing=1.2)
ax.text(ult, -0.62, f"valor da Ultra ({num(ult, 2, sinal=True)})\ncabe no IC das outras redes", ha="center",
        va="bottom", fontsize=TAM_NOTA - 1, color=DESTAQUE, linespacing=1.1, zorder=4,
        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"))
ax.text(0.01, -0.62, "", ha="left")
ax.axhline(1.68, color=CINZA_CLARO, lw=0.8, zorder=0)
ax.text(-0.58, 1.68 - 0.08, "Ultra (achado original, UNI-01)", ha="left", va="bottom", fontsize=TAM_NOTA - 1.5,
        color=CINZA_ESCURO, zorder=4, bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none"))
ax.text(-0.58, 1.68 + 0.1, "outras redes (réplica)", ha="left", va="top", fontsize=TAM_NOTA - 1.5,
        color=CINZA_ESCURO, zorder=4, bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none"))

# caixa lateral
x_col, w_col = 0.735, 1 - MARGEM_X - 0.735
yb = caixa(fig, x_col, y_topo - 0.03, w_col,
           f"Erro {num(e_m0d)}% × {num(e_m0)}% do modelo simples (viés {pct(v_m0d, sinal=True)}), mas empata nas "
           f"sensibilidades. Fora da amostra em 2025, ganho de só {num(ganho_r2, 3, sinal=True)} de R² (régua: "
           f"{num(regua, 2, sinal=True)}).", tamanho=TAM_NOTA + 0.5, titulo="Nas 18 unidades novas da Ultra",
           fundo=DESTAQUE_MUITO_CLARO, barra=DESTAQUE)
caixa(fig, x_col, yb - 0.02, w_col,
      "O resultado da réplica era previsto como inconclusivo antes de rodar: com 36 unidades, o menor efeito "
      f"detectável na Engenharia do Corpo era ~{num(L[2]['min_detectavel'], 2)}, mais de três vezes o efeito medido. "
      "É evidência a favor, não prova.",
      tamanho=TAM_NOTA)

# ------------------------------------------------------------------ dados
dados = pd.DataFrame([dict(ordem=i + 1, rotulo=r["rotulo"], N=r["N"], efeito=r["efeito"], ic90_lo=r["lo"],
                           ic90_hi=r["hi"], cidades=r["cidades"], mesmo_sinal_retirando_cidade=r["sinal"])
                      for i, r in enumerate(L)])
dados["m0d_erro_18_novas_pct"] = e_m0d
dados["m0_erro_18_novas_pct"] = e_m0
dados["m0d_ganho_r2_loo_2025"] = round(ganho_r2, 3)
salvar(fig, ID, dados)
