"""s3_rampa_confirmacao — em 22 unidades novas, a curva real erra metade do simulador nos alunos; uma reta
recalibrada já resolve.

Fontes: uni03/resultado_uni03.md (P2: erro mensal (a) e erro na soma do 1º ano (b)); uni03/confirmacao_uni03.csv
(conferência: a mediana por unidade reproduz o (a) e a contagem de 21 de 22); uni03/ilustracao_payback_uni03.md
(ilustração fora do protocolo); uni05/resultado_uni05.md (cenário 'A: demanda ATUAL + rampa obs.').
"""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _estilo import *  # noqa: E402,F403

ID = "s3_rampa_confirmacao"
MD = (UNI / "uni03" / "resultado_uni03.md").read_text(encoding="utf-8")
CONF = pd.read_csv(UNI / "uni03" / "confirmacao_uni03.csv", sep=";", encoding="utf-8-sig")
ILU = (UNI / "uni03" / "ilustracao_payback_uni03.md").read_text(encoding="utf-8")
R05 = (UNI / "uni05" / "resultado_uni05.md").read_text(encoding="utf-8")

# ------------------------------------------------------------------ leitura
BRACOS = ["curva", "sim_padrao", "linear_recal"]
NOME_BRACO = {"curva": "curva observada (mediana)", "sim_padrao": "simulador hoje",
              "linear_recal": "reta recalibrada"}
# a "reta recalibrada" tem a mesma cor nos dois painéis
COR_BRACO = {"curva": DESTAQUE, "sim_padrao": CINZA_ESCURO, "linear_recal": DESTAQUE_CLARO}
SERIES = {"ativos": "Alunos ativos", "faturamento": "Faturamento"}


def tabela_serie(serie):
    bloco = MD.split(f"**{serie}** (22 unidades)")[1]
    t = tabela_md(bloco, "| braço | (a) erro mensal |").set_index("braço")
    n_melhor = int(re.search(r"curva erra menos em (\d+) de (\d+) unidades", bloco).group(1))
    return t, n_melhor


linhas = []
melhor = {}
for serie in SERIES:
    t, n_melhor = tabela_serie(serie)
    melhor[serie] = n_melhor
    for b in BRACOS:
        a = numero_br(t.loc[b, "(a) erro mensal"])
        m = re.match(r"(\S+) \((\S+)\)", t.loc[b, "(b) erro na soma do 1º ano"])
        linhas.append(dict(painel="erro_1o_ano", serie=serie, braco=b, rotulo=NOME_BRACO[b], erro_mensal_pct=a,
                           erro_soma_1o_ano_pct=numero_br(m.group(1)), vies_soma_1o_ano_pct=numero_br(m.group(2))))
erros = pd.DataFrame(linhas)
n_conf = int(re.search(r"confirmação: \*\*(\d+) unidades\*\*", MD).group(1))

ilu = tabela_md(ILU, "| rampa | payback (meses) |")
ilu["payback"] = ilu["payback (meses)"].astype(int)
ilu["fat_1o_ano"] = ilu["faturamento do 1º ano"].map(numero_br)
ilu["chave"] = ["hoje", "curva_alunos", "curva_fat"]
ilu = ilu.set_index("chave")
# as "curvas observadas" da ilustração são retas: 62% → 100% no mês 8 (alunos) e 64% → 100% no mês 11 (faturamento)
conferir("ilustração: alunos = reta 62% no mês 1, 100% no mês 8",
         int("62% no mês 1, 100% no mês 8" in ilu.loc["curva_alunos", "rampa"]), 1)
conferir("ilustração: faturamento = reta 64% no mês 1, 100% no mês 11",
         int("64% no mês 1, 100% no mês 11" in ilu.loc["curva_fat", "rampa"]), 1)
nivel_ilu = numero_br(re.search(r"Unidade de ([\d,\.]+) alunos maduros", ILU).group(1))

t05 = tabela_md(R05, "| cenário | faturamento: erro / viés |")  # primeira = principal (18 de teste)
aprov_A = int(t05.set_index("cenário").loc["A: demanda ATUAL + rampa obs.", "aprovações indevidas"])
aprov_atual = int(t05.set_index("cenário").loc["ATUAL", "aprovações indevidas"])

# ------------------------------------------------------------------ conferência
E = erros.set_index(["serie", "braco"])
for (s, b), v in {("ativos", "curva"): 10, ("ativos", "sim_padrao"): 21, ("ativos", "linear_recal"): 10,
                  ("faturamento", "curva"): 12, ("faturamento", "sim_padrao"): 17,
                  ("faturamento", "linear_recal"): 13}.items():
    conferir(f"erro mensal {s}/{b} (%)", E.loc[(s, b), "erro_mensal_pct"], v)
    # o (a) do .md é a mediana, entre as 22 unidades, do erro médio mês a mês de cada unidade
    conferir(f"CSV: mediana de a_{b} em {s} (%)",
             round(CONF.loc[CONF["serie"].eq(s), f"a_{b}"].median() * 100), v, 0.5)
conferir("viés do simulador na soma do 1º ano, alunos (%)", E.loc[("ativos", "sim_padrao"), "vies_soma_1o_ano_pct"], -15)
conferir("viés do simulador na soma do 1º ano, faturamento (%)",
         E.loc[("faturamento", "sim_padrao"), "vies_soma_1o_ano_pct"], -7)
for s in SERIES:
    g = CONF[CONF["serie"].eq(s)]
    conferir(f"CSV: curva erra menos que o simulador em {s} (unidades)", int((g["a_curva"] < g["a_sim_padrao"]).sum()),
             melhor[s])
    conferir(f".md: curva erra menos em {s}", melhor[s], 21)
    conferir(f"unidades de confirmação em {s}", len(g), 22)
conferir("unidades de confirmação (.md)", n_conf, 22)
conferir("payback hoje (meses)", ilu.loc["hoje", "payback"], 38)
conferir("payback curva de faturamento (meses)", ilu.loc["curva_fat", "payback"], 37)
conferir("payback curva de alunos (meses)", ilu.loc["curva_alunos", "payback"], 36)
conferir("faturamento 1º ano hoje (R$ mi)", round(ilu.loc["hoje", "fat_1o_ano"] / 1e6, 2), 2.37)
conferir("faturamento 1º ano curva de faturamento (R$ mi)", round(ilu.loc["curva_fat", "fat_1o_ano"] / 1e6, 2), 2.60)
conferir("faturamento 1º ano curva de alunos (R$ mi)", round(ilu.loc["curva_alunos", "fat_1o_ano"] / 1e6, 2), 2.71)
d_fat = ilu.loc["curva_fat", "fat_1o_ano"] - ilu.loc["hoje", "fat_1o_ano"]
d_alu = ilu.loc["curva_alunos", "fat_1o_ano"] - ilu.loc["hoje", "fat_1o_ano"]
conferir("ganho no 1º ano, curva de faturamento (R$ mil)", round(d_fat / 1000), 225, 1)
conferir("ganho no 1º ano, curva de alunos (R$ mil; caderno arredonda para 340)", round(d_alu / 1000), 340, 3)
conferir("nível maduro da ilustração (alunos)", nivel_ilu, 2213)
conferir("UNI-05: aprovações indevidas com só a rampa trocada", aprov_A, 3)
conferir("UNI-05: aprovações indevidas da regra atual", aprov_atual, 0)

# ------------------------------------------------------------------ figura
fig = figura()
y_topo = cabecalho(
    fig,
    "Em 22 unidades novas, a curva real erra metade do simulador nos alunos — e uma reta recalibrada já resolve",
    "Erro da previsão do 1º ano em unidades que não entraram na curva; ilustração de payback com premissas-padrão",
)
y_base = rodape(
    fig,
    "Fonte: uni03/resultado_uni03.md; uni03/confirmacao_uni03.csv; uni03/ilustracao_payback_uni03.md; "
    f"uni05/resultado_uni05.md · N = {n_conf} unidades de confirmação (abertas dez/2024–ago/2025)",
)

# ---------------- painel esquerdo
y0, y1 = y_base + 0.09, y_topo - 0.1
axL = fig.add_axes([0.075, y0, 0.47, y1 - y0])
eixo_limpo(axL, grade="y")
fig.text(0.075, y1 + 0.062, "Erro da previsão mês a mês (meses 1–10)", ha="left", va="bottom",
         fontsize=TAM_TEXTO + 1, fontweight="bold")
fig.text(0.075, y1 + 0.058, f"mediana das {n_conf} unidades de confirmação · menor é melhor", ha="left", va="top",
         fontsize=TAM_NOTA - 0.5, color=CINZA_ESCURO)
larg = 0.26
for gi, s in enumerate(SERIES):
    for bi, b in enumerate(BRACOS):
        v = E.loc[(s, b), "erro_mensal_pct"]
        x = gi + (bi - 1) * (larg + 0.03)
        axL.bar(x, v, width=larg, color=COR_BRACO[b], zorder=2, label=NOME_BRACO[b] if gi == 0 else None)
        axL.text(x, v + 0.5, pct(v), ha="center", va="bottom", fontsize=TAM_TEXTO + 1, fontweight="bold",
                 color=DESTAQUE if b == "curva" else TEXTO)
axL.set_xticks(range(len(SERIES)))
axL.set_xticklabels(list(SERIES.values()), fontsize=TAM_TEXTO + 0.5, color=TEXTO)
axL.set_xlim(-0.55, 1.55)
axL.set_ylim(0, 32.5)
axL.set_yticks([0, 5, 10, 15, 20, 25])
axL.yaxis.set_major_formatter(formatador_num(0, "%"))
axL.legend(loc="upper right", bbox_to_anchor=(1.0, 0.80), ncol=1, fontsize=TAM_NOTA, handlelength=1.2,
           labelspacing=0.35)
v_a = E.loc[("ativos", "sim_padrao"), "vies_soma_1o_ano_pct"]
v_f = E.loc[("faturamento", "sim_padrao"), "vies_soma_1o_ano_pct"]
axL.text(-0.5, 32.2, f"a curva erra menos que o simulador\nem {melhor['ativos']} de {n_conf} unidades "
         f"(nos alunos e no faturamento)", ha="left", va="top", fontsize=TAM_NOTA + 0.5, color=DESTAQUE,
         fontweight="bold", linespacing=1.2)
axL.text(-0.5, 28.6, f"o simulador subestima o 1º ano em {num(abs(v_a))}% dos alunos\ne {num(abs(v_f))}% do "
         "faturamento (soma dos 12 meses)", ha="left", va="top", fontsize=TAM_NOTA, color=CINZA_ESCURO,
         linespacing=1.2)

# ---------------- painel direito (ilustração)
xR, wR = 0.655, 0.31
yR0 = y0 + 0.26
axR = fig.add_axes([xR, yR0, wR, y1 - yR0])
eixo_limpo(axR, grade=None)
axR.spines["left"].set_visible(False)
axR.set_yticks([])
fig.text(xR, y1 + 0.062, "Unidade típica: 1º ano", ha="left", va="bottom", fontsize=TAM_TEXTO + 1,
         fontweight="bold")
fig.text(xR, y1 + 0.058, f"{num(nivel_ilu)} alunos maduros · premissas-padrão do simulador", ha="left", va="top",
         fontsize=TAM_NOTA - 0.5, color=CINZA_ESCURO)
fig.text(1 - MARGEM_X, y1 + 0.064, "ILUSTRAÇÃO", ha="right", va="bottom", fontsize=8, fontweight="bold",
         color="white", bbox=dict(boxstyle="round,pad=0.4,rounding_size=0.5", fc=AMBAR, ec="none"))
ordem_R = [("hoje", "simulador hoje\n(500 alunos,\nreta até o mês 8)", CINZA_ESCURO),
           ("curva_fat", "reta no\nfaturamento\n(64% no mês 1,\n100% no mês 11)", CINZA),
           ("curva_alunos", "reta recalibrada\nnos alunos\n(62% no mês 1,\n100% no mês 8)", DESTAQUE_CLARO)]
for i, (k, rot, cor) in enumerate(ordem_R):
    v = ilu.loc[k, "fat_1o_ano"] / 1e6
    axR.bar(i, v, width=0.74, color=cor, zorder=2)
    cor_txt = TEXTO if cor in (DESTAQUE_CLARO, CINZA) else "white"
    axR.text(i, v - 0.08, f"R$ {num(v, 2)} mi", ha="center", va="top", fontsize=TAM_NOTA, color=cor_txt,
             fontweight="bold")
    axR.text(i, v + 0.06, f"payback\n{ilu.loc[k, 'payback']} meses", ha="center", va="bottom",
             fontsize=TAM_NOTA + 0.5, color=TEXTO, fontweight="bold" if k != "hoje" else "normal", linespacing=1.1)
    if k != "hoje":
        dv = (ilu.loc[k, "fat_1o_ano"] - ilu.loc["hoje", "fat_1o_ano"]) / 1000
        axR.text(i, v - 0.42, f"+R$ {num(dv)} mil", ha="center", va="top", fontsize=TAM_NOTA - 0.5, color=cor_txt)
axR.set_xticks(range(3))
axR.set_xticklabels([r for _, r, _ in ordem_R], fontsize=TAM_NOTA - 0.5, color=TEXTO, linespacing=1.1)
axR.set_xlim(-0.5, 2.5)
axR.set_ylim(0, 3.35)

# notas sob o painel direito
yb = caixa(fig, xR, yR0 - 0.105, wR,
           "É correção do 1º ano: o que decide a viabilidade continua sendo o nível maduro.", tamanho=TAM_NOTA)
caixa(fig, xR, yb - 0.012, wR,
      f"Trocar só a rampa, sem a demanda da praça, faria o simulador aprovar {aprov_A} unidades fracas "
      f"(UNI-05; {aprov_atual} com a regra atual): as duas mudanças andam juntas.", tamanho=TAM_NOTA,
      fundo=DESTAQUE_MUITO_CLARO, barra=DESTAQUE)

# ------------------------------------------------------------------ dados
ilu_df = ilu.reset_index()[["chave", "rampa", "payback", "fat_1o_ano"]].rename(
    columns={"chave": "braco", "rampa": "rotulo", "payback": "payback_meses", "fat_1o_ano": "fat_1o_ano_reais"})
ilu_df["painel"] = "ilustracao_payback"
ilu_df["ganho_1o_ano_reais"] = ilu_df["fat_1o_ano_reais"] - ilu.loc["hoje", "fat_1o_ano"]
erros["curva_erra_menos_em"] = erros["serie"].map(melhor)
erros["n_unidades"] = n_conf
dados = pd.concat([erros, ilu_df], ignore_index=True)
dados["uni05_aprov_indevidas_so_rampa"] = aprov_A
salvar(fig, ID, dados)
