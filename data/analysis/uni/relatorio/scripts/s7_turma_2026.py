"""s7_turma_2026 — a turma de 2026 é a prova que falta (DESCRITIVO).

Fontes:
- previsao_2026/previsoes_turma_2026.csv (modelo da praça M0 no nível 2026 e faixa provisória p10–p90; a coluna
  `master`, que traz a sigla regional, NÃO é lida nem gravada);
- previsao_2026/previsoes_turma_2026_master_real.csv (v2 de trabalho = M0 + master real + estúdios, nível 2026;
  sem previsão para Jardim das Américas e Vila Izabel);
- previsao_2026/leitura_precoce.md (projeção precoce e mês de vida, 11 unidades);
- previsao_2026/fachada_turma_2026.csv (nota de fachada registrada antes do desempenho maduro);
- previsao_2026/REGISTRO_CONGELAMENTO.txt e protocolo_previsao_2026.md (data do congelamento e regra da conferência);
- uni03/curva_uni03.csv (série 'faturamento': p10/p50/p90 da razão mês k ÷ nível maduro, para a incerteza da
  projeção: projeção × p50/p90 a projeção × p50/p10);
- fato_unidade_mes.parquet (só o mês de vida do último mês com faturamento das 5 unidades sem leitura precoce).
"""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _estilo import *  # noqa: E402,F403
import matplotlib.transforms  # noqa: E402

ID = "s7_turma_2026"
P26 = UNI / "previsao_2026"
COLS_PREV = ["unidade_id", "nome", "uf", "inauguracao", "estudios", "prev_M0_cal2026", "faixa_p10_M0_cal2026",
             "faixa_p90_M0_cal2026"]  # sem a coluna 'master' (sigla regional)
prev = pd.read_csv(P26 / "previsoes_turma_2026.csv", sep=";", encoding="utf-8-sig", usecols=COLS_PREV)
mreal = pd.read_csv(P26 / "previsoes_turma_2026_master_real.csv", sep=";", encoding="utf-8-sig",
                    usecols=["unidade_id", "prev_M0+MrealE_cal2026"])
fach = pd.read_csv(P26 / "fachada_turma_2026.csv", sep=";", encoding="utf-8-sig", usecols=["unidade_id", "nota"])
LP = (P26 / "leitura_precoce.md").read_text(encoding="utf-8")
REG = (P26 / "REGISTRO_CONGELAMENTO.txt").read_text(encoding="utf-8")
PROT = (P26 / "protocolo_previsao_2026.md").read_text(encoding="utf-8")
cur = pd.read_csv(UNI / "uni03" / "curva_uni03.csv", sep=";", encoding="utf-8-sig")
cur = cur[cur["serie"] == "faturamento"].set_index("k")

df = prev.merge(mreal, on="unidade_id", how="left").merge(fach, on="unidade_id", how="left")
df = df.rename(columns={"prev_M0+MrealE_cal2026": "prev_v2", "prev_M0_cal2026": "prev_M0",
                        "faixa_p10_M0_cal2026": "faixa_p10", "faixa_p90_M0_cal2026": "faixa_p90",
                        "nota": "nota_fachada"})
df["inauguracao"] = pd.to_datetime(df["inauguracao"])

# ------------------------------------------------------------------ leitura precoce (tabela do .md)
lp = tabela_md(LP, "| unidade | UF | abertura | mês de vida |")
lp["mes_vida"] = lp["mês de vida"].astype(int)
lp["projecao"] = lp["projeção precoce"].map(numero_br)
lp["proj_div_M0_pub"] = lp["projeção ÷ M0"].map(numero_br)
lp["prev_M0_md"] = lp["previsto M0"].map(numero_br)
lp = lp[["unidade", "UF", "mes_vida", "projecao", "proj_div_M0_pub", "prev_M0_md"]]
df = df.merge(lp, left_on=["nome", "uf"], right_on=["unidade", "UF"], how="left").drop(columns=["unidade", "UF"])
df["tem_leitura"] = df["projecao"].notna()

# mês de vida do último mês com faturamento, para as unidades sem leitura precoce (< 3 meses)
f = pd.read_parquet(UNI / "fato_unidade_mes.parquet", columns=["unidade_id", "competencia", "mes_vida", "faturamento"])
ult = (f[f["unidade_id"].isin(df["unidade_id"]) & f["faturamento"].notna()].sort_values("competencia")
       .groupby("unidade_id").tail(1).set_index("unidade_id"))
df["mes_vida_painel"] = df["unidade_id"].map(ult["mes_vida"]).astype(float)
df["mes_vida"] = df["mes_vida"].fillna(df["mes_vida_painel"]).astype(int)

# incerteza da projeção pela curva de faturamento do UNI-03 no mês de vida da leitura
k = df["mes_vida"]
df["proj_lo"] = df["projecao"] * k.map(cur["p50"]) / k.map(cur["p90"])
df["proj_hi"] = df["projecao"] * k.map(cur["p50"]) / k.map(cur["p10"])
df["dif_proj_M0"] = 100 * (df["projecao"] / df["prev_M0"] - 1)
df["dif_proj_v2"] = 100 * (df["projecao"] / df["prev_v2"] - 1)
df = df.sort_values(["inauguracao", "nome"]).reset_index(drop=True)
n = len(df)
idx = df.set_index("nome")

# ------------------------------------------------------------------ conferência
conferir("N de unidades congeladas", n, 16)
conferir("unidades com leitura precoce", int(df["tem_leitura"].sum()), 11)
conferir("v2 de trabalho disponível", int(df["prev_v2"].notna().sum()), 14)
conferir("sem v2 = Jardim das Américas e Vila Izabel",
         int(sorted(df.loc[df["prev_v2"].isna(), "nome"]) == ["JARDIM DAS AMERICAS", "VILA IZABEL"]), 1)
conferir("abertura mais antiga = 2025-08", int(df["inauguracao"].min().strftime("%Y-%m") == "2025-08"), 1)
conferir("congelado em 29/09 com hash", int("gerada em 2026-09-29, antes de qualquer conferencia" in REG), 1)
conferir("regra: conferência com ≥ 10 maduras",
         int("Confere-se quando houver ≥ 10 unidades maduras" in PROT and "`mes_vida` ≥ 12" in PROT), 1)
fx_lo = float(np.median(100 * (df["faixa_p10"] / df["prev_M0"] - 1)))
fx_hi = float(np.median(100 * (df["faixa_p90"] / df["prev_M0"] - 1)))
m = re.search(r"Faixa provisória p10–p90 do M0: (-?\d+)% a \+(\d+)%", LP)
conferir("faixa provisória: piso (%)", round(fx_lo), int(m.group(1)), 0.5)
conferir("faixa provisória: teto (%)", round(fx_hi), int(m.group(2)), 0.5)
t = df[df["tem_leitura"]]
conferir("M0 do .md = M0 do CSV (máx. |dif|, R$)", float((t["prev_M0_md"] - t["prev_M0"]).abs().max()), 0, 0.5)
conferir("projeção ÷ M0 recalculada = publicada (máx. |dif|, pp)",
         float((t["dif_proj_M0"].round() - t["proj_div_M0_pub"]).abs().max()), 0)
conferir("Buritis: projeção ÷ praça (%)", round(idx.loc["BURITIS", "dif_proj_M0"]), -59)
conferir("Americana Centro: projeção ÷ praça (%)", round(idx.loc["AMERICANA CENTRO", "dif_proj_M0"]), -42)
conferir("Laranjeiras: projeção ÷ praça (%)", round(idx.loc["LARANJEIRAS", "dif_proj_M0"]), 134)
conferir("Buritis e Americana no mês 12", int(idx.loc["BURITIS", "mes_vida"] == 12 and
                                              idx.loc["AMERICANA CENTRO", "mes_vida"] == 12), 1)
conferir("Laranjeiras no mês 4", int(idx.loc["LARANJEIRAS", "mes_vida"]), 4)
conferir("Buritis tem estúdio", float(idx.loc["BURITIS", "estudios"]), 1.0)
conferir("Laranjeiras: RJ", int(idx.loc["LARANJEIRAS", "uf"] == "RJ"), 1)
gua_m0, gua_v2 = idx.loc["GUARAPARI", "dif_proj_M0"], idx.loc["GUARAPARI", "dif_proj_v2"]
conferir("Guarapari sem estúdio", float(idx.loc["GUARAPARI", "estudios"]), 0.0)
conferir("Laranjeiras sem estúdio", float(idx.loc["LARANJEIRAS", "estudios"]), 0.0)
print("Guarapari: projeção × praça", round(gua_m0), "· × v2", round(gua_v2))
print("projeção × v2: Buritis", round(idx.loc["BURITIS", "dif_proj_v2"]), "· Americana",
      round(idx.loc["AMERICANA CENTRO", "dif_proj_v2"]), "· Laranjeiras", round(idx.loc["LARANJEIRAS", "dif_proj_v2"]))

# ------------------------------------------------------------------ figura
fig = figura()
y_topo = cabecalho(
    fig,
    "A turma de 2026 é a prova que falta: previsões congeladas antes do resultado, com primeiras leituras "
    "para os dois lados",
    "Previsões congeladas em 29/09 (com hash) para as unidades abertas de ago/2025 em diante; conferência quando "
    "≥ 10 estiverem maduras",
    selo="DESCRITIVO",
)
y_base = rodape(
    fig,
    "Fonte: previsao_2026/previsoes_turma_2026.csv; previsoes_turma_2026_master_real.csv; leitura_precoce.md; "
    f"fachada_turma_2026.csv; uni03/curva_uni03.csv · N = {n} ({int(df['tem_leitura'].sum())} com leitura precoce) "
    "· nível 2026 (calendário −2%)",
    nota="Projeção precoce = faturamento do último mês ÷ curva do UNI-03; é sinal antecipado, não a conferência. "
    "O traço em volta dela é a incerteza da curva naquele mês de vida (p10–p90). Conferência formal, fixada em 29/09: "
    "quando ≥ 10 unidades tiverem ≥ 3 meses com mês de vida ≥ 12; decide estúdios, master, faixa e fachada. "
    "Jardim das Américas e Vila Izabel não têm estúdio nem master no cadastro: sem v2 de trabalho. A faixa cinza é "
    f"a do modelo da praça ({pct(fx_lo)} a {pct(fx_hi, sinal=True)}); a faixa da v2 de trabalho, no slide anterior "
    "(s7_faixas_seguranca), é −37% a +58%.",
)

X0, W = 0.305, 0.555
y_ax0 = y_base + 0.07
h_ax = y_topo - y_ax0 - 0.11
ax = fig.add_axes([X0, y_ax0, W, h_ax])
eixo_limpo(ax, grade="x")
XMAX = 1050
y = np.arange(n)
for i, r in df.iterrows():
    ax.plot([r["faixa_p10"] / 1000, r["faixa_p90"] / 1000], [i, i], color=CINZA_CLARO, lw=7, solid_capstyle="butt",
            zorder=1)
    if r["tem_leitura"]:
        ax.plot([r["proj_lo"] / 1000, r["proj_hi"] / 1000], [i, i], color=REAL, lw=1.1, zorder=3)
        for xe in (r["proj_lo"] / 1000, r["proj_hi"] / 1000):
            ax.plot([xe, xe], [i - 0.16, i + 0.16], color=REAL, lw=1.1, zorder=3)
ax.scatter(df["prev_M0"] / 1000, y, s=46, color=CINZA_ESCURO, edgecolor="white", lw=1.0, zorder=4)
ok_v2 = df["prev_v2"].notna()
ax.scatter(df.loc[ok_v2, "prev_v2"] / 1000, y[ok_v2], s=50, color=DESTAQUE, edgecolor="white", lw=1.0, zorder=5)
cheio = df["tem_leitura"] & (df["mes_vida"] >= 6)
vazado = df["tem_leitura"] & (df["mes_vida"] < 6)
ax.scatter(df.loc[cheio, "projecao"] / 1000, y[cheio], s=62, marker="D", color=REAL, edgecolor="white", lw=1.0,
           zorder=6)
ax.scatter(df.loc[vazado, "projecao"] / 1000, y[vazado], s=56, marker="D", facecolor="white", edgecolor=REAL,
           lw=1.5, zorder=6)
for i, r in df[~ok_v2].iterrows():  # '—' onde falta a v2
    x_txt = np.nanmax([r["faixa_p90"], r["proj_hi"]]) / 1000 + 14
    ax.text(x_txt, i, "v2: —", ha="left", va="center", fontsize=TAM_NOTA - 1, color=CINZA_ESCURO)

# anotações das leituras que já apontam para um lado
for nome, dy in (("BURITIS", 0.0), ("AMERICANA CENTRO", 0.0)):
    i = int(df.index[df["nome"] == nome][0])
    r = df.loc[i]
    ax.text(r["faixa_p90"] / 1000 + 16, i + dy,
            f"projeção {pct(r['dif_proj_M0'], sinal=True)} contra a praça · {pct(r['dif_proj_v2'], sinal=True)} "
            "contra a v2", ha="left", va="center", fontsize=TAM_NOTA - 0.5, color=TEXTO, fontweight="bold")
i_lar = int(df.index[df["nome"] == "LARANJEIRAS"][0])
r = df.loc[i_lar]
ax.annotate(f"{pct(r['dif_proj_M0'], sinal=True)} contra a praça · {pct(r['dif_proj_v2'], sinal=True)} contra a v2"
            "\n(RJ, sem agregador; ainda no mês 4)",
            xy=(r["projecao"] / 1000, i_lar + 0.2), xytext=(r["projecao"] / 1000 - 40, i_lar + 1.15),
            ha="left", va="top", fontsize=TAM_NOTA - 0.5, color=TEXTO, fontweight="bold", linespacing=1.2,
            arrowprops=dict(arrowstyle="-", color=CINZA, lw=0.8, shrinkA=0, shrinkB=4))

# nota do estúdio (canto inferior direito, área vazia)
i_bur = int(df.index[df["nome"] == "BURITIS"][0])
txt_est = quebrar(fig, "Buritis (com estúdio) está bem abaixo; Guarapari "
                       f"({pct(gua_m0, sinal=True)}) e Laranjeiras, sem estúdio, bem acima: sinais contra a "
                       "hipótese dos estúdios. A conferência formal decide.",
                  0.27, TAM_NOTA)
ax.text(XMAX - 10, n - 0.95, txt_est, ha="right", va="bottom", fontsize=TAM_NOTA, color=TEXTO, linespacing=1.3,
        bbox=dict(boxstyle="round,pad=0.6", fc=CINZA_FUNDO, ec="none"))

ax.set_yticks(y)
rot = [f"{nome_unidade(r['nome'], r['uf'])} · {r['inauguracao']:%m/%Y} · mês {r['mes_vida']}" for _, r in df.iterrows()]
ax.set_yticklabels(rot, fontsize=TAM_NOTA, color=TEXTO)
ax.tick_params(axis="y", pad=17)
ax.set_ylim(n - 0.45, -0.7)
ax.set_xlim(0, XMAX)
ax.set_xticks(range(0, 1001, 100))
ax.xaxis.set_major_formatter(formatador_num(0))
ax.set_xlabel("faturamento mensal maduro (R$ mil, nível 2026)", color=CINZA_ESCURO, fontsize=TAM_NOTA)
ax.spines["left"].set_visible(False)

trans = matplotlib.transforms.blended_transform_factory(fig.transFigure, ax.transData)
for i, r in df.iterrows():
    if r["estudios"] == 1.0:
        ax.text(X0 - 0.009, i, "E", transform=trans, ha="center", va="center", fontsize=7, fontweight="bold",
                color="white", bbox=dict(boxstyle="round,pad=0.22,rounding_size=0.3", fc=CINZA_ESCURO, ec="none"))

# coluna de fachada
XF = X0 + W + 0.05
fig.text(XF, y_ax0 + h_ax + 0.008, "nota de\nfachada (1–5)", ha="center", va="bottom", fontsize=TAM_NOTA - 0.5,
         color=CINZA_ESCURO, fontweight="bold", linespacing=1.1)
for i, r in df.iterrows():
    v = r["nota_fachada"]
    ax.text(XF, i, "—" if pd.isna(v) else num(v), transform=trans, ha="center", va="center", fontsize=TAM_NOTA,
            color=TEXTO if pd.notna(v) else CINZA)

# legenda
H = matplotlib.lines.Line2D
handles = [
    H([], [], color=CINZA_CLARO, lw=7,
      label=f"faixa do modelo da praça ({pct(fx_lo)} a {pct(fx_hi, sinal=True)})"),
    H([], [], marker="o", color=CINZA_ESCURO, ls="none", markersize=7, markeredgecolor="white",
      label="modelo da praça"),
    H([], [], marker="o", color=DESTAQUE, ls="none", markersize=7, markeredgecolor="white", label="v2 de trabalho"),
    H([], [], marker="D", color=REAL, ls="-", lw=1.1, markersize=7, markeredgecolor="white",
      label="projeção precoce, mês ≥ 6"),
    H([], [], marker="D", markerfacecolor="white", color=REAL, ls="-", lw=1.1, markersize=6.5, markeredgewidth=1.5,
      label="projeção, mês < 6"),
]
ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(-0.01, 1.0), ncol=3, handletextpad=0.6,
          columnspacing=1.4, fontsize=TAM_NOTA - 0.5, handlelength=1.5)
fig.text(X0 - 0.009, y_ax0 + h_ax + 0.012, "E", ha="center", va="bottom", fontsize=7, fontweight="bold",
         color="white", bbox=dict(boxstyle="round,pad=0.22,rounding_size=0.3", fc=CINZA_ESCURO, ec="none"))
fig.text(X0 - 0.018, y_ax0 + h_ax + 0.012, "com estúdio", ha="right", va="bottom", fontsize=TAM_NOTA - 0.5,
         color=CINZA_ESCURO)

# ------------------------------------------------------------------ dados (sem a coluna master)
dados = pd.DataFrame({
    "ordem": np.arange(1, n + 1), "unidade_id": df["unidade_id"], "nome": df["nome"], "uf": df["uf"],
    "rotulo": rot, "inauguracao": df["inauguracao"].dt.strftime("%Y-%m-%d"), "estudios": df["estudios"],
    "mes_vida": df["mes_vida"], "tem_leitura_precoce": df["tem_leitura"],
    "prev_praca_M0_cal2026": df["prev_M0"], "faixa_p10_M0_cal2026": df["faixa_p10"],
    "faixa_p90_M0_cal2026": df["faixa_p90"], "prev_v2_trabalho_cal2026": df["prev_v2"],
    "projecao_precoce": df["projecao"].round(0), "projecao_lo_curva": df["proj_lo"].round(0),
    "projecao_hi_curva": df["proj_hi"].round(0), "dif_projecao_vs_praca_pct": df["dif_proj_M0"].round(1),
    "dif_projecao_vs_v2_pct": df["dif_proj_v2"].round(1), "nota_fachada": df["nota_fachada"],
})
salvar(fig, ID, dados)
