"""s7_faixas_seguranca — a v2 passa a entregar faixa (UNI-07, verificado; faixa provisória).

Fontes:
- uni07/faixas_indicadores.csv (p10/p50/p90 do faturamento maduro, chance de ser viável, faturamento/payback/viável
  real no simulador; 18 unidades de teste + a linha 'unidade típica', que fica fora do gráfico e vai para a nota);
- uni07/resultado_uni07.md (faixa adotada (A), cobertura e IC, Brier, erro por estado, custo do estúdio);
- uni05/comparacao_por_unidade.csv (UF das unidades; viáveis no UNI-05 sem o custo do estúdio; payback de Paranoá);
- CADERNO_ESTUDO_UNI.md etapa 13 (decisões pendentes; folha de 17% confirmada pelo dono em 30/09).

O script lê o CSV do UNI-07: basta rodá-lo de novo quando o UNI-07 fechar.
"""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _estilo import *  # noqa: E402,F403
import matplotlib.transforms  # noqa: E402

ID = "s7_faixas_seguranca"
CSV = UNI / "uni07" / "faixas_indicadores.csv"
MD = (UNI / "uni07" / "resultado_uni07.md").read_text(encoding="utf-8")
CAD = (UNI / "CADERNO_ESTUDO_UNI.md").read_text(encoding="utf-8")
U05 = pd.read_csv(UNI / "uni05" / "comparacao_por_unidade.csv", sep=";", encoding="utf-8-sig")
U05 = U05[U05["grupo"] == "teste"].set_index("nome")

bruto = pd.read_csv(CSV, sep=";", encoding="utf-8-sig")
tipica = bruto[bruto["unidade"].str.startswith("unidade típica")].iloc[0]
df = bruto[~bruto["unidade"].str.startswith("unidade típica")].copy()
df["uf"] = df["unidade"].map(U05["uf"])
df["rotulo"] = [nome_unidade(n, u) + ("*" if n == "PARANOA PARQUE" else "") for n, u in zip(df["unidade"], df["uf"])]
df["viavel_real"] = df["viavel_real"].astype(str).str.lower().eq("true")
df["estudio"] = df["estudio"].astype(float).eq(1.0)
df["posicao"] = np.where(df["faturamento_real"] < df["p10_faturamento"], "abaixo",
                         np.where(df["faturamento_real"] > df["p90_faturamento"], "acima", "dentro"))
df = df.sort_values("p50_faturamento", ascending=False).reset_index(drop=True)
n = len(df)

# ------------------------------------------------------------------ números publicados (resultado_uni07.md)
m = re.search(r"\| \(A\) só treino — teste limpo \| 80% \| (-?\d+)% a \+(\d+)% \| (\d+)% \((\d+)/(\d+)\) \| "
              r"\[(\d+); (\d+)\]", MD)
fx_lo, fx_hi, cob_pct, cob_n, cob_N, ic_lo, ic_hi = (int(g) for g in m.groups())
m = re.search(r"Brier ([\d.]+) contra ([\d.]+) da taxa-base \((\d+)/(\d+) viáveis\)", MD)
brier_pub, brier_base_pub = float(m.group(1)), float(m.group(2))
m = re.search(r"das (\d+) unidades com chance ≥ 50%, (\d+) seriam viáveis; das (\d+) com chance < 50%, (\d+)\.", MD)
n_alta, via_alta, n_baixa, via_baixa = (int(g) for g in m.groups())
err_df = int(re.search(r"\| estado \| DF-GO \| \d+ \| (\d+)% \|", MD).group(1))
err_sp = int(re.search(r"\| estado \| SP \| \d+ \| (\d+)% \|", MD).group(1))
custo_est = int(re.search(r"custo do estúdio R\$ ([\d,]+)/mês", MD).group(1).replace(",", ""))
p50_rel = int(re.search(r"\*\*Faixa adotada \(regra do §3\): \(A\)\*\*, de -\d+% a \+\d+% em torno da previsão; p50 "
                        r"(-?\d+)%", MD).group(1))

# ------------------------------------------------------------------ conferência
conferir("N de unidades de teste", n, 18)
conferir("faixa adotada (A): piso (%)", fx_lo, -37)
conferir("faixa adotada (A): teto (%)", fx_hi, 58)
dentro = int((df["posicao"] == "dentro").sum())
conferir("CSV: unidades dentro da faixa", dentro, 13)
conferir("md: cobertura publicada (n)", cob_n, dentro)
conferir("md: cobertura publicada (%)", cob_pct, round(100 * dentro / n))
conferir("IC 90% da cobertura", ic_lo * 100 + ic_hi, 50 * 100 + 88)
abaixo = sorted(df.loc[df["posicao"] == "abaixo", "unidade"])
acima = sorted(df.loc[df["posicao"] == "acima", "unidade"])
conferir("abaixo da faixa = só Mococa", int(abaixo == ["MOCOCA"]), 1)
conferir("acima da faixa = Botafogo, Butantã, Cariacica, Noroeste", int(acima == ["BOTAFOGO", "BUTANTA", "CARIACICA",
                                                                                  "NOROESTE"]), 1)
conferir("as 4 acima têm estúdio", int(df.loc[df["posicao"] == "acima", "estudio"].all()), 1)
viaveis = int(df["viavel_real"].sum())
conferir("viáveis (com custo do estúdio)", viaveis, 7)
brier = float(((df["chance_viavel"] - df["viavel_real"].astype(float)) ** 2).mean())
base = viaveis / n
brier_base = float(((base - df["viavel_real"].astype(float)) ** 2).mean())
conferir("Brier calculado", round(brier, 3), brier_pub, 0.0005)
conferir("Brier da taxa-base calculado", round(brier_base, 3), brier_base_pub, 0.0005)
conferir("Brier publicado = 0,175", brier_pub, 0.175)
alta = df["chance_viavel"] >= 0.5
conferir("chance ≥ 50%: unidades", int(alta.sum()), n_alta)
conferir("chance ≥ 50%: viáveis", int((alta & df["viavel_real"]).sum()), via_alta)
conferir("chance < 50%: unidades", int((~alta).sum()), n_baixa)
conferir("chance < 50%: viáveis (reprovadas por corte em 50%)", int((~alta & df["viavel_real"]).sum()), via_baixa)
conferir("corte em 50% reprovaria 5 das 7 viáveis", via_baixa * 10 + viaveis, 5 * 10 + 7)
conferir("erro típico DF-GO (%)", err_df, 17)
conferir("erro típico SP (%)", err_sp, 32)
conferir("custo do estúdio (R$/mês)", custo_est, 6000)
viaveis_u05 = int(U05["ok_REAL"].astype(str).str.lower().eq("true").sum())
conferir("UNI-05: viáveis sem custo do estúdio", viaveis_u05, 8)
pb_par_u05 = float(U05.loc["PARANOA PARQUE", "pb_REAL"])
pb_par_u07 = float(df.set_index("unidade").loc["PARANOA PARQUE", "payback_real"])
conferir("Paranoá Parque: payback no UNI-05", pb_par_u05, 34)
conferir("Paranoá Parque: payback no UNI-07", pb_par_u07, 37)
conferir("caderno: faixa adotada provisoriamente", int("**provisoriamente**, porque passou por uma unidade só"
                                                    in (UNI / "CADERNO_ESTUDO_UNI.md").read_text(encoding="utf-8")), 1)
conferir("unidade típica: p50 (R$ mil)", round(tipica["p50_faturamento"] / 1000), 215)
conferir("unidade típica: chance de viável (%)", round(100 * tipica["chance_viavel"]), 38)
conferir("caderno: folha de 17% é a premissa válida (decisão de 30/09)",
         int("folha de 17%: é a premissa válida" in CAD), 1)

# ------------------------------------------------------------------ figura
fig = figura()
y_topo = cabecalho(
    fig,
    f"A v2 passa a entregar faixa: de {MENOS}{abs(fx_lo)}% a +{fx_hi}% em torno da previsão, "
    f"que cobriu {dentro} das {n} unidades novas",
    "Faixa de 80% da v2 (praça + estúdios + master) em torno da previsão, nível 2026, custos-padrão e rampa observada",
    selo="FAIXA PROVISÓRIA · UNI-07 VERIFICADO",
)
nota = (
    f"Viável aqui inclui o custo do estúdio (R$ {num(custo_est / 1000)} mil/mês): {viaveis} de {n}, contra "
    f"{viaveis_u05} de {n} no UNI-05. * Paranoá Parque: {num(pb_par_u07)} meses com o custo do estúdio, "
    f"{num(pb_par_u05)} sem ele (por isso aparece como 'se pagou' em s1 e s6). "
    f"Custos-padrão: aluguel R$ 20 mil, obra R$ 2,34 mi e folha de 17% (premissa confirmada pelo dono em 30/09), "
    f"não os custos reais de cada unidade. Unidade típica (mediana das previsões): p50 "
    f"{mil(tipica['p50_faturamento'])}, chance de ser viável de {num(100 * tipica['chance_viavel'])}%."
)
y_base = rodape(
    fig,
    f"Fonte: uni07/faixas_indicadores.csv; uni07/resultado_uni07.md · N = {n} · faixa construída só com os erros do "
    f"treino (39) · p50 = previsão {MENOS}{abs(p50_rel)}% (viés mediano do treino) · viável = payback ≤ 36 meses "
    "no simulador com o faturamento real",
    nota=nota,
)

# ---------------- eixo principal
X0, W = 0.215, 0.335
y_ax0 = y_base + 0.075
h_ax = y_topo - y_ax0 - 0.075
ax = fig.add_axes([X0, y_ax0, W, h_ax])
eixo_limpo(ax, grade="x")
y = np.arange(n)
XMAX = 800
for i, r in df.iterrows():
    ax.plot([r["p10_faturamento"] / 1000, r["p90_faturamento"] / 1000], [i, i], color=CINZA_CLARO, lw=7.5,
            solid_capstyle="butt", zorder=1)
    ax.plot([r["p50_faturamento"] / 1000] * 2, [i - 0.3, i + 0.3], color=CINZA_ESCURO, lw=2.0, zorder=2)
fora = df["posicao"] != "dentro"
ax.scatter(df.loc[~fora, "faturamento_real"] / 1000, y[~fora], s=48, marker="D", color=REAL, zorder=4,
           edgecolor="white", lw=1.0)
ax.scatter(df.loc[fora, "faturamento_real"] / 1000, y[fora], s=58, marker="D", color=DESTAQUE, zorder=5,
           edgecolor="white", lw=1.0)
for i, r in df[fora].iterrows():
    v = r["faturamento_real"] / 1000
    if r["posicao"] == "abaixo":
        ax.text(v - 14, i, f"{num(v)} mil", ha="right", va="center", fontsize=TAM_NOTA - 0.5, color=DESTAQUE,
                fontweight="bold")
    else:
        ax.text(v + 14, i, f"{num(v)} mil", ha="left", va="center", fontsize=TAM_NOTA - 0.5, color=DESTAQUE,
                fontweight="bold")

ax.set_yticks(y)
ax.set_yticklabels(df["rotulo"], fontsize=TAM_NOTA + 0.5, color=TEXTO)
ax.tick_params(axis="y", pad=17)
ax.set_ylim(n - 0.45, -0.75)
ax.set_xlim(0, XMAX)
ax.set_xticks(range(0, XMAX + 1, 100))
ax.xaxis.set_major_formatter(formatador_num(0))
ax.set_xlabel("faturamento mensal maduro (R$ mil, nível 2026)", color=CINZA_ESCURO, fontsize=TAM_NOTA)
ax.spines["left"].set_visible(False)

# marcador 'E' (estúdio) entre o nome e o eixo
trans = matplotlib.transforms.blended_transform_factory(fig.transFigure, ax.transData)
for i, r in df.iterrows():
    if r["estudio"]:
        ax.text(X0 - 0.009, i, "E", transform=trans, ha="center", va="center", fontsize=7, fontweight="bold",
                color="white", bbox=dict(boxstyle="round,pad=0.22,rounding_size=0.3", fc=CINZA_ESCURO, ec="none"))

# legenda manual, acima do eixo
H = matplotlib.lines.Line2D
handles = [
    H([], [], color=CINZA_CLARO, lw=7.5, label="faixa 80% (p10–p90)"),
    H([], [], color=CINZA_ESCURO, lw=2.0, marker="|", markersize=10, ls="none", markeredgewidth=2.0, label="p50"),
    H([], [], marker="D", color=REAL, ls="none", markersize=6.5, markeredgecolor="white", label="real dentro"),
    H([], [], marker="D", color=DESTAQUE, ls="none", markersize=7, markeredgecolor="white", label="real fora"),
]
ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(-0.02, 1.0), ncol=4, handletextpad=0.55,
          columnspacing=0.8, fontsize=TAM_NOTA - 0.5, handlelength=1.4)
fig.text(X0 - 0.009, y_ax0 + h_ax + 0.013, "E", ha="center", va="bottom", fontsize=7, fontweight="bold",
         color="white", bbox=dict(boxstyle="round,pad=0.22,rounding_size=0.3", fc=CINZA_ESCURO, ec="none"))
fig.text(X0 - 0.018, y_ax0 + h_ax + 0.013, "com estúdio", ha="right", va="bottom", fontsize=TAM_NOTA - 0.5,
         color=CINZA_ESCURO)

# ---------------- colunas de texto: chance de ser viável e foi viável?
XC1, XC2 = 0.613, 0.668
for xc, cab in ((XC1, "chance de\nser viável"), (XC2, "foi\nviável?")):
    fig.text(xc, y_ax0 + h_ax + 0.008, cab, ha="center", va="bottom", fontsize=TAM_NOTA - 0.5, color=CINZA_ESCURO,
             fontweight="bold", linespacing=1.1)
for i, r in df.iterrows():
    ch = 100 * r["chance_viavel"]
    ax.text(XC1, i, f"{num(ch)}%", transform=trans, ha="center", va="center", fontsize=TAM_NOTA,
            color=TEXTO, fontweight="bold" if ch >= 50 else "normal")
    ax.text(XC2, i, "sim" if r["viavel_real"] else "não", transform=trans, ha="center", va="center",
            fontsize=TAM_NOTA, color=TEXTO if r["viavel_real"] else CINZA,
            fontweight="bold" if r["viavel_real"] else "normal")

# ---------------- painel à direita
XP, WP = 0.712, 1 - MARGEM_X - 0.712
yp = y_topo - 0.005
fig.text(XP, yp, f"{dentro} de {n}", ha="left", va="top", fontsize=34, fontweight="bold", color=DESTAQUE)
fig.text(XP, yp - 0.088, f"dentro da faixa ({cob_pct}%; IC 90%: {ic_lo}–{ic_hi}%)", ha="left", va="top",
         fontsize=TAM_TEXTO, color=DESTAQUE, fontweight="bold")
fig.text(XP, yp - 0.118, "esperado: 80%; adotada provisoriamente\n(passou por uma unidade só)", ha="left", va="top",
         fontsize=TAM_NOTA - 0.5, color=CINZA_ESCURO, linespacing=1.2)
yp -= 0.18
yp = caixa(fig, XP, yp, WP,
           f"O piso segurou: só Mococa ficou abaixo. O teto não: {len(acima)} acima (Noroeste, Butantã, Cariacica e "
           "Botafogo), todas com estúdio.", tamanho=TAM_NOTA)
yp -= 0.018
yp = caixa(fig, XP, yp, WP,
           f"Ordena as praças: Brier {num(brier_pub, 3)} contra {num(brier_base_pub, 3)} da taxa-base. Não serve como "
           f"corte: com corte em 50%, reprovaria {via_baixa} das {viaveis} viáveis. Serve para comparar pontos.",
           titulo="Chance de ser viável", tamanho=TAM_NOTA, barra=CINZA_ESCURO)
yp -= 0.018
caixa(fig, XP, yp, WP,
      f"1. Faixa única ou por estado: o erro é maior em SP ({err_sp}%) que em DF/GO ({err_df}%).\n"
      "2. Chance de ser viável como ranking, não como corte.",
      titulo="Decisões pendentes do dono", tamanho=TAM_NOTA, fundo=DESTAQUE_MUITO_CLARO, barra=DESTAQUE)

# ------------------------------------------------------------------ dados
dados = pd.DataFrame({
    "ordem": np.arange(1, n + 1),
    "unidade": df["unidade"], "uf": df["uf"], "rotulo": df["rotulo"], "estudio": df["estudio"],
    "p10_faturamento": df["p10_faturamento"].round(0), "p50_faturamento": df["p50_faturamento"].round(0),
    "p90_faturamento": df["p90_faturamento"].round(0), "faturamento_real": df["faturamento_real"].round(0),
    "posicao_real": df["posicao"], "chance_viavel": df["chance_viavel"].round(4),
    "payback_real": df["payback_real"], "viavel_real": df["viavel_real"], "no_grafico": True,
})
linha_tipica = pd.DataFrame([{
    "ordem": np.nan, "unidade": tipica["unidade"], "uf": "", "rotulo": "unidade típica (citada em nota)",
    "estudio": False, "p10_faturamento": round(tipica["p10_faturamento"]),
    "p50_faturamento": round(tipica["p50_faturamento"]), "p90_faturamento": round(tipica["p90_faturamento"]),
    "faturamento_real": np.nan, "posicao_real": "", "chance_viavel": round(tipica["chance_viavel"], 4),
    "payback_real": np.nan, "viavel_real": np.nan, "no_grafico": False,
}])
dados = pd.concat([dados.astype(object), linha_tipica.astype(object)], ignore_index=True)
salvar(fig, ID, dados)
