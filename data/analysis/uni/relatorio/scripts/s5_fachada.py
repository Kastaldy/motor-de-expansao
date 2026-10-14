"""s5_fachada — sinal a favor que enfraqueceu com o primeiro avaliador independente; ainda em avaliação.

Fontes:
- alavancas/resultado_fachada_sem_botafogo.md (Spearman nota × resíduo, com e sem Botafogo, amostra principal e
  ampliada);
- leitura parcial do avaliador independente (29/09), em alavancas/ (arquivo resultado_fachada_*_parcial.md): médias
  por nota e Spearman das unidades novas e de todas as notas sem Botafogo;
- alavancas/resultado_v2_fachada.md (v2 sem Botafogo: 21,8% base, 17,5% só nível, 18,9% com fachada);
- alavancas/protocolo_fachada.md v1.3 e CADERNO_ESTUDO_UNI.md etapa 12 ("só lojas de rua, sem Botafogo":
  +0,30 [−0,03; +0,64]; N não registrado).
Avaliadores nunca aparecem por nome no gráfico nem no CSV.
"""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _estilo import *  # noqa: E402,F403
from _estilo import _cracha  # noqa: E402,F401

ID = "s5_fachada"
ALV = UNI / "alavancas"
SB = (ALV / "resultado_fachada_sem_botafogo.md").read_text(encoding="utf-8")
PARCIAL = next(ALV.glob("resultado_fachada_*_parcial.md"))  # leitura parcial do avaliador independente
PA = PARCIAL.read_text(encoding="utf-8")
V2F = (ALV / "resultado_v2_fachada.md").read_text(encoding="utf-8")
PROT = (ALV / "protocolo_fachada.md").read_text(encoding="utf-8")
CAD = (UNI / "CADERNO_ESTUDO_UNI.md").read_text(encoding="utf-8")
AMP = (ALV / "resultado_fachada_ampliada.md").read_text(encoding="utf-8")  # v1.1, o número citado no caderno


def sp(celula_rho, celula_ic):
    lo, hi = [numero_br(x) for x in celula_ic.strip("[]").split(";")]
    return numero_br(celula_rho), lo, hi


tsb = tabela_md(SB, "| amostra | N | Spearman nota × resíduo |").set_index("amostra")
rho = {k: (*sp(tsb.loc[k, "Spearman nota × resíduo"], tsb.loc[k, "IC 90%"]), int(tsb.loc[k, "N"]))
       for k in tsb.index}
tpa = tabela_md(PA, "| amostra | N | Spearman nota × faturamento acima do previsto |")
tpa["amostra"] = tpa["amostra"].str.replace("*", "", regex=False)
tpa = tpa.set_index("amostra")
k_novas = next(k for k in tpa.index if k.startswith("só as unidades novas"))
k_todas = next(k for k in tpa.index if k.startswith("todas as notas"))
r_novas = (*sp(tpa.loc[k_novas, "Spearman nota × faturamento acima do previsto"], tpa.loc[k_novas, "IC 90%"]),
           int(tpa.loc[k_novas, "N"]))
r_todas = (*sp(tpa.loc[k_todas, "Spearman nota × faturamento acima do previsto"], tpa.loc[k_todas, "IC 90%"]),
           int(tpa.loc[k_todas, "N"]))
m = re.search(r"só fora de shopping, sem Botafogo: \+(\d,\d+) \[−(\d,\d+); \+(\d,\d+)\]", PROT)
r_rua = (numero_br(m.group(1)), -numero_br(m.group(2)), numero_br(m.group(3)), None)
tamp = tabela_md(AMP, "| amostra | N | Spearman nota × resíduo |")
l_amp = tamp[tamp["amostra"].str.startswith("ampliada (+")].iloc[0]
r_amp = (*sp(l_amp["Spearman nota × resíduo"], l_amp["IC 90%"]), int(l_amp["N"]))

medias = {int(a): (float(b), int(c)) for a, b, c in
          re.findall(r"nota (\d): ([+\-−]?\d+)% \(n=(\d+)\)", PA.replace("−", "-"))}
n_aval = re.search(r"Leitura parcial: (\d+) de (\d+) unidades novas avaliadas", PA)
tv = tabela_md(V2F, "| modelo base | amostra | N | erro base |")
lin_v2 = tv[(tv["modelo base"].str.startswith("v2")) & (tv["amostra"] == "sem Botafogo")].iloc[0]
v2_base, v2_nivel, v2_fach = (numero_br(lin_v2["erro base"]), numero_br(lin_v2["+ só correção de nível"]),
                              numero_br(lin_v2["+ fachada"]))

# ------------------------------------------------------------------ conferência
esperado = {"principal, com Botafogo": (0.37, -0.19, 0.86, 14), "principal, sem Botafogo": (0.67, 0.27, 0.91, 13),
            "ampliada, com Botafogo": (0.31, -0.10, 0.67, 22), "ampliada, sem Botafogo": (0.49, 0.15, 0.76, 21)}
for k, e in esperado.items():
    for i, parte in enumerate(("ρ", "IC inf.", "IC sup.", "N")):
        conferir(f"{k}: {parte}", rho[k][i], e[i])
for nome, v, e in [("independente, só novas", r_novas, (-0.25, -0.64, 0.26, 11)),
                   ("todas as notas sem Botafogo", r_todas, (0.22, -0.07, 0.48, 32))]:
    for i, parte in enumerate(("ρ", "IC inf.", "IC sup.", "N")):
        conferir(f"{nome}: {parte}", v[i], e[i])
for i, parte in enumerate(("ρ", "IC inf.", "IC sup.")):
    conferir(f"só lojas de rua sem Botafogo: {parte}", r_rua[i], (0.30, -0.03, 0.64)[i])
for i, parte in enumerate(("ρ", "IC inf.", "IC sup.", "N")):
    conferir(f"ampliada v1.1 (como no caderno): {parte}", r_amp[i], (0.32, -0.09, 0.66, 22)[i])
conferir("caderno cita ampliada +0,32 [−0,09; +0,66]", int("Spearman +0,32 [−0,09; +0,66]" in CAD), 1)
conferir("caderno cita lojas de rua +0,30 [−0,03; +0,64]", int("sem Botafogo: **+0,30** [−0,03; +0,64]" in CAD), 1)
for nota, e in {1: (-20, 1), 2: (32, 3), 3: (-12, 12), 4: (14, 11), 5: (31, 5)}.items():
    conferir(f"média nota {nota} (%)", medias[nota][0], e[0])
    conferir(f"n nota {nota}", medias[nota][1], e[1])
conferir("soma dos n por nota = 32", sum(v[1] for v in medias.values()), 32)
conferir("avaliadas pelo independente", int(n_aval.group(1)), 11)
conferir("total a avaliar", int(n_aval.group(2)), 45)
conferir("v2 sem Botafogo: erro base (%)", v2_base, 21.8)
conferir("v2 sem Botafogo: só nível (%)", v2_nivel, 17.5)
conferir("v2 sem Botafogo: + fachada (%)", v2_fach, 18.9)

# ------------------------------------------------------------------ figura
fig = figura()
y_topo = cabecalho(
    fig,
    "Fachada: sinal a favor que enfraqueceu com o primeiro avaliador independente — ainda em avaliação",
    "Nota de fachada (1 a 5, pelo Street View) × faturamento acima ou abaixo do previsto pelo modelo da praça",
    selo="EM AVALIAÇÃO",
)
y_base = rodape(
    fig,
    "Fonte: alavancas/resultado_fachada_sem_botafogo.md; alavancas/resultado_fachada_ampliada.md (v1.1); leitura parcial do avaliador independente (29/09); "
    "alavancas/resultado_v2_fachada.md; CADERNO etapa 12 · IC 90%",
    nota="* Exclusão de Botafogo decidida pelo dono depois de ver o dado (maior exceção da rede); as duas versões "
    "ficam registradas. Ampliada: +0,32 [−0,09; +0,66] é o resultado v1.1 citado no caderno; a nova rodada com e sem "
    "Botafogo deu +0,31 [−0,10; +0,67] (outra reamostragem do IC). Médias por nota: n = 1 a 3 nas notas 1 e 2.",
)
# caixa de decisão, largura toda, logo acima do rodapé
y_cx = caixa(fig, MARGEM_X, y_base + 0.075, 1 - 2 * MARGEM_X,
             f"Por ora a fachada não entra na v2 (exploratório: v2 + fachada erra {num(v2_fach, 1)}%, contra "
             f"{num(v2_nivel, 1)}% só com correção de nível). Veredito com as notas restantes "
             f"({n_aval.group(1)} de {n_aval.group(2)} avaliadas), testando a hipótese 'loja de rua', escrita antes "
             "delas.", tamanho=TAM_NOTA + 0.5, fundo=DESTAQUE_MUITO_CLARO, barra=DESTAQUE)
y_plot_bot = y_base + 0.075 + 0.075

# ---------------- painel esquerdo: média por nota
y_pt = y_topo - 0.005
fig.text(MARGEM_X, y_pt, "Faturou vs. previsto, média por nota", ha="left", va="top", fontsize=TAM_TEXTO,
         fontweight="bold", color=TEXTO)
fig.text(MARGEM_X, y_pt - 0.03, f"todas as notas, sem Botafogo (N = {sum(v[1] for v in medias.values())})",
         ha="left", va="top", fontsize=TAM_NOTA, color=CINZA_ESCURO)
axl = fig.add_axes([0.085, y_plot_bot, 0.33, y_pt - 0.08 - y_plot_bot])
eixo_limpo(axl, grade="y")
axl.set_facecolor("none")
notas = [1, 2, 3, 4, 5]
for nt in notas:
    v, n = medias[nt]
    axl.bar(nt, v, width=0.62, color=CINZA_ESCURO, zorder=2)  # mesma cor nas 5 notas: sem destaque seletivo
    yt = v + 3 if v >= 0 else v - 3
    axl.text(nt, yt, f"{pct(v, sinal=True)}", ha="center", va="bottom" if v >= 0 else "top",
             fontsize=TAM_NOTA + 0.5, fontweight="bold", color=TEXTO)
    axl.text(nt, -33, f"n = {n}", ha="center", va="bottom", fontsize=TAM_NOTA - 1, color=CINZA_ESCURO)
axl.axhline(0, color=TEXTO, lw=1.0, zorder=3)
axl.set_xticks(notas)
axl.set_xticklabels([f"nota {nt}" for nt in notas], fontsize=TAM_NOTA)
axl.set_xlim(0.4, 5.6)
axl.set_ylim(-35, 88)
axl.set_yticks([-25, 0, 25, 50])
axl.yaxis.set_major_formatter(formatador_num(0, "%", sinal=True))
txt2 = quebrar(fig, "Unidades de shopping/galeria (Botanic Mall, Noroeste, Mooca) faturam acima com nota 2 — daí a "
               "hipótese 'loja de rua'", 0.215, TAM_NOTA - 0.5)
axl.annotate(txt2, xy=(2, medias[2][0] + 10), xytext=(0.55, 84), ha="left", va="top", fontsize=TAM_NOTA - 0.5,
             color=CINZA_ESCURO, linespacing=1.15,
             arrowprops=dict(arrowstyle="-", color=CINZA, lw=0.7, shrinkA=2, shrinkB=2))
axl.text(5.55, 47, "sem escada clara: a nota 2\nfica acima das notas 3 e 4", ha="right", va="bottom",
         fontsize=TAM_NOTA - 0.5, color=CINZA_ESCURO, linespacing=1.15)

# ---------------- painel direito: forest do Spearman
X_LAB = 0.735
X_AX0, X_AX1 = 0.745, 1 - MARGEM_X
fig.add_artist(matplotlib.lines.Line2D([0.46, 0.46], [y_plot_bot - 0.02, y_pt], color=CINZA_CLARO, lw=0.8))
fig.text(0.485, y_pt, "Nota × faturou acima do previsto", ha="left", va="top", fontsize=TAM_TEXTO,
         fontweight="bold", color=TEXTO)
fig.text(0.485, y_pt - 0.03, "correlação de Spearman, IC 90%", ha="left", va="top", fontsize=TAM_NOTA,
         color=CINZA_ESCURO)
linhas = [
    ("Maduras, notas da equipe", rho["principal, com Botafogo"], "base"),
    ("Maduras sem Botafogo*", rho["principal, sem Botafogo"], "posthoc"),
    ("Ampliada", r_amp, "base"),
    ("Ampliada sem Botafogo*", rho["ampliada, sem Botafogo"], "posthoc"),
    ("Avaliador independente, só unidades novas", r_novas, "indep"),
    ("Todas as notas, sem Botafogo", r_todas, "base"),
    ("Só lojas de rua, sem Botafogo — hipótese para a conferência", r_rua, "hip"),
]
n = len(linhas)
ax_top, ax_bot = y_pt - 0.08, y_plot_bot
ax = fig.add_axes([X_AX0, ax_bot, X_AX1 - X_AX0, ax_top - ax_bot])
eixo_limpo(ax, grade="x")
ax.spines["left"].set_visible(False)
ax.set_facecolor("none")
ax.set_ylim(n - 0.5, -0.5)
ax.set_xlim(-0.75, 1.0)
ax.set_xticks([-0.5, 0, 0.5, 1.0])
ax.xaxis.set_major_formatter(formatador_num(1, sinal=True))
ax.set_yticks([])
ax.axvline(0, color=TEXTO, lw=1.0, zorder=1)
h_row = (ax_top - ax_bot) / n
linhas_csv = []
for i, (rot, v, tipo) in enumerate(linhas):
    e, lo, hi, nn = v
    cor = {"base": CINZA_ESCURO, "posthoc": CINZA, "indep": DESTAQUE, "hip": CINZA_ESCURO}[tipo]
    if tipo == "hip":
        ax.plot([lo, hi], [i, i], color=cor, lw=2.2, ls=(0, (2, 1.5)), zorder=2)
        ax.scatter(e, i, s=55, facecolor="white", edgecolor=cor, lw=1.6, zorder=3)
    else:
        ax.plot([lo, hi], [i, i], color=cor, lw=3.0 if tipo == "indep" else 2.3, zorder=2, solid_capstyle="round")
        ax.scatter(e, i, s=85 if tipo == "indep" else 55, color=cor, edgecolor="white", lw=1.0, zorder=3)
    yf = ax_bot + (ax_top - ax_bot) * (n - 0.5 - i) / n
    rot_n = f"{rot} (N {'a registrar' if nn is None else '= ' + str(nn)})"
    r1 = quebrar(fig, rot_n, X_LAB - 0.49, TAM_NOTA - 0.5, "bold" if tipo == "indep" else "normal")
    r2 = f"{num(e, 2, sinal=True)}  [{num(lo, 2, sinal=True)}; {num(hi, 2, sinal=True)}]"
    nl = r1.count("\n") + 1
    h_tot = altura_linhas(fig, nl, TAM_NOTA - 0.5, 1.15) + altura_linhas(fig, 1, TAM_NOTA - 1, 1.15)
    y0 = yf + h_tot / 2
    fig.text(X_LAB, y0, r1, ha="right", va="top", fontsize=TAM_NOTA - 0.5, linespacing=1.05,
             color=DESTAQUE if tipo == "indep" else TEXTO, fontweight="bold" if tipo == "indep" else "normal")
    fig.text(X_LAB, y0 - altura_linhas(fig, nl, TAM_NOTA - 0.5, 1.15), r2, ha="right", va="top",
             fontsize=TAM_NOTA - 1, color=DESTAQUE if tipo == "indep" else CINZA_ESCURO)
    linhas_csv.append(dict(painel="Spearman nota × faturou acima do previsto", linha=rot, n=nn, valor=e,
                           ic90_lo=lo, ic90_hi=hi, tipo=tipo))
ax.text(r_novas[2] + 0.06, 4, "← 1º dado\nindependente", ha="left", va="center", linespacing=1.05,
        fontsize=TAM_NOTA - 1,
        color=DESTAQUE, fontweight="bold")
ax.axhline(3.5, color=CINZA_CLARO, lw=0.9, xmin=-1.2, clip_on=False)

# ------------------------------------------------------------------ dados
for nt in notas:
    linhas_csv.append(dict(painel="média de faturou vs. previsto por nota (todas, sem Botafogo)",
                           linha=f"nota {nt}", n=medias[nt][1], valor=medias[nt][0], tipo="média (%)"))
linhas_csv.append(dict(painel="v2 com fachada (sem Botafogo, N = 24)", linha="erro típico: base / só nível / + fachada",
                       valor=f"{v2_base} / {v2_nivel} / {v2_fach}", tipo="exploratório (%)"))
salvar(fig, ID, pd.DataFrame(linhas_csv))
