"""s4_erro_e_volume — o que o modelo erra é volume de alunos, e nenhuma das 22 características explica o erro de
faturamento de forma confiável (no erro de alunos, 3 de 22 passam de p < 0,05, perto do acaso).

Fontes: uni01/anatomia_erros.md (decomposição e R² fora da amostra); uni01/anatomia_erros_correlacoes.csv (Spearman do
erro de faturamento com 22 características, lista fixada antes); uni01/anatomia_erros.csv (erro por unidade, para
recalcular a decomposição e o recorte de SP); CADERNO_ESTUDO_UNI.md, etapa 6.
"""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _estilo import *  # noqa: E402,F403
from scipy import stats  # noqa: E402

ID = "s4_erro_e_volume"
MD = (UNI / "uni01" / "anatomia_erros.md").read_text(encoding="utf-8")
COR = pd.read_csv(UNI / "uni01" / "anatomia_erros_correlacoes.csv", sep=";", encoding="utf-8-sig")
AN = pd.read_csv(UNI / "uni01" / "anatomia_erros.csv", sep=";", encoding="utf-8-sig")

# ------------------------------------------------------------------ decomposição
m = re.search(r"alunos respondem por (\d+)% e ticket por (\d+)% \(covariância (-?\d+)%\)", MD)
dec_md = dict(alunos=int(m.group(1)), ticket=int(m.group(2)), cov=int(m.group(3)))
r2 = re.search(r"faturamento R² ([\d.]+); \*\*alunos R² ([\d.]+); ticket R² ([\d.]+)\*\*", MD)
r2_fat, r2_alu, r2_tic = (float(x) for x in r2.groups())
v = AN["e_fat"].var(ddof=0)
dec = dict(alunos=AN["e_alunos"].var(ddof=0) / v * 100, ticket=AN["e_ticket"].var(ddof=0) / v * 100,
           cov=2 * np.cov(AN["e_alunos"], AN["e_ticket"], ddof=0)[0, 1] / v * 100)
n_an = len(AN)
conferir("N da anatomia", n_an, 39)
conferir("erro de faturamento = erro de alunos + erro de ticket (log; máx. desvio)",
         round(float((AN["e_alunos"] + AN["e_ticket"] - AN["e_fat"]).abs().max()), 3), 0, 0.001)
for k, e in [("alunos", 92), ("ticket", 19), ("cov", -11)]:
    conferir(f"decomposição recalculada: {k} (%)", round(dec[k]), e, 0.5)
    conferir(f"decomposição no .md: {k} (%)", dec_md[k], e)
conferir("soma da decomposição (%)", round(sum(dec.values())), 100, 0.5)
conferir("R² fora da amostra, alunos", r2_alu, 0.12)

# ------------------------------------------------------------------ correlações
COR = COR.sort_values("e_fat", ascending=True).reset_index(drop=True)
n_var = len(COR)
n_sig = int((COR["p_e_fat"] < 0.05).sum())
t_c = stats.t.ppf(0.975, 39 - 2)
r_crit = t_c / np.sqrt(39 - 2 + t_c ** 2)
gold = COR[COR["variável"].eq("preço do plano Gold")].iloc[0]
conferir("características comparadas", n_var, 22)
conferir("características com p < 0,05 no erro de faturamento", n_sig, 0)
conferir("valor crítico do Spearman para N = 39 (p = 0,05)", round(r_crit, 2), 0.32, 0.005)
conferir("Gold: Spearman", round(gold["e_fat"], 2), 0.31)
conferir("Gold: p", round(gold["p_e_fat"], 3), 0.055)
conferir("N mínimo por variável", int(COR["N"].min()), 36)
n_sig_alunos = int((COR["p_e_alunos"] < 0.05).sum())
conferir("características com p < 0,05 no erro de ALUNOS", n_sig_alunos, 3)
SIG_AL = COR[COR["p_e_alunos"] < 0.05].sort_values("p_e_alunos")
g_al = COR[COR["variável"].eq("preço do plano Gold")].iloc[0]
conferir("Gold no erro de alunos: Spearman", round(g_al["e_alunos"], 2), 0.47)
conferir("Gold no erro de alunos: p", round(g_al["p_e_alunos"], 3), 0.003, 0.0005)


def rotulo_var(v: str) -> str:
    """Camada de rótulo de negócio (o nome bruto segue no CSV)."""
    v = v.replace("retenção EB 60d (Lifetime)", "retenção de alunos em 60 dias")
    v = v.replace(" (F1)", "").replace(" (F2)", "")
    v = v.replace("/mil hab c10)", "/mil hab., 10 min de carro)").replace("(hab/km² c10)", "(hab/km², 10 min de carro)")
    v = v.replace(" (c10)", " (10 min de carro)").replace(" c10", " (10 min de carro)")
    v = v.replace("isócrona", "praça").replace("crescimento do hexágono", "crescimento do entorno")
    return v


def lista_pt(itens):
    return "; ".join(itens[:-1]) + "; " + itens[-1] if len(itens) > 1 else itens[0]


txt_sig_al = lista_pt([f"{rotulo_var(r['variável'])}: ρ {num(r['e_alunos'], 2, sinal=True)}, p = {num(r['p_e_alunos'], 3)}"
                       for _, r in SIG_AL.iterrows()])

# ------------------------------------------------------------------ recorte de SP
AN["grupo"] = np.select(
    [AN["unidade_id"].isin(["santos-sp", "praia-grande-sp", "guaruja-sp"]), AN["uf"].eq("SP"), AN["uf"].eq("DF")],
    ["Baixada Santista", "demais de SP", "DF"], "outras UFs")
reg = AN.groupby("grupo")["erro_pct"].agg(["median", "size"])
grande_sp = AN[AN["uf"].eq("SP") & AN["metro"].eq(0) & ~AN["grupo"].eq("Baixada Santista")]
med_sp_todo = AN.loc[AN["uf"].eq("SP"), "erro_pct"].median() * 100
conferir("Baixada Santista: unidades", int(reg.loc["Baixada Santista", "size"]), 3)
conferir("Grande SP: erro mediano (%)", round(grande_sp["erro_pct"].median() * 100), -4, 0.5)
conferir("demais de SP: erro mediano (%)", round(reg.loc["demais de SP", "median"] * 100), -4, 0.5)
conferir("DF: erro mediano (%)", round(reg.loc["DF", "median"] * 100), -5, 0.5)
conferir("SP inteiro: erro mediano (%)", round(med_sp_todo), 21, 0.5)

# ------------------------------------------------------------------ figura
fig = figura()
y_topo = cabecalho(
    fig,
    "O que o modelo erra é volume de alunos — e nenhuma das 22 características explica o erro de faturamento "
    "de forma confiável",
    "Anatomia dos erros do modelo da praça nas 39 unidades maduras de 2025 (erro fora da amostra)",
    selo="EXPLORATÓRIO",
)
y_base = rodape(
    fig,
    "Fonte: uni01/anatomia_erros.md; uni01/anatomia_erros_correlacoes.csv; uni01/anatomia_erros.csv · N = 39 "
    "(36–39 por variável) · erro = real/previsto − 1, fora da amostra",
    nota=f"No erro de ALUNOS, {n_sig_alunos} de {n_var} passam de p < 0,05 ({txt_sig_al}), perto do esperado por "
    f"acaso com {n_var} comparações; o preço é foto de ago/2026 e pode ser efeito, não causa. Candidatos ao que falta: "
    "fatores que as bases não medem (gestão, ponto, fachada) — hipótese, ainda sem teste.",
)

# ---------------- painel esquerdo: decomposição
xL, wL = 0.075, 0.2
yL0 = y_base + 0.33
yL1 = y_topo - 0.085
axL = fig.add_axes([xL, yL0, wL, yL1 - yL0])
eixo_limpo(axL, grade="y")
fig.text(MARGEM_X, yL1 + 0.055, "De onde vem o erro", ha="left", va="bottom", fontsize=TAM_TEXTO + 1,
         fontweight="bold")
fig.text(MARGEM_X, yL1 + 0.052, "parte da variância do erro de faturamento", ha="left", va="top",
         fontsize=TAM_NOTA - 0.5, color=CINZA_ESCURO)
barras = [("alunos", dec["alunos"], DESTAQUE), ("ticket", dec["ticket"], CINZA), ("covariância", dec["cov"], CINZA_CLARO)]
for i, (rot, val, cor) in enumerate(barras):
    axL.bar(i, val, width=0.62, color=cor, zorder=2)
    axL.text(i, val + (3 if val >= 0 else -3), pct(val, sinal=val < 0), ha="center", va="bottom" if val >= 0 else "top",
             fontsize=TAM_TEXTO + 2 if i == 0 else TAM_TEXTO, fontweight="bold",
             color=DESTAQUE if i == 0 else TEXTO)
axL.axhline(0, color=CINZA_ESCURO, lw=0.8)
axL.set_xticks(range(3))
axL.set_xticklabels([b[0] for b in barras], fontsize=TAM_NOTA)
axL.set_ylim(-22, 108)
axL.set_yticks([0, 25, 50, 75, 100])
axL.yaxis.set_major_formatter(formatador_num(0, "%"))
axL.text(2.4, 104, "soma 100%", ha="right", va="top", fontsize=TAM_NOTA - 1, color=CINZA_ESCURO)
yb = caixa(fig, MARGEM_X, yL0 - 0.05, 0.25,
           f"O modelo explica só {num(r2_alu * 100)}% da diferença de alunos entre unidades (R² fora da amostra; "
           f"{num(r2_fat * 100)}% no faturamento).", tamanho=TAM_NOTA)
# caixa "Não é efeito São Paulo"
g = reg["median"] * 100
caixa(fig, MARGEM_X, yb - 0.02, 0.25,
      f"SP inteiro fica {pct(med_sp_todo, sinal=True)} acima do previsto, mas o excesso vem da Baixada Santista "
      f"({int(reg.loc['Baixada Santista', 'size'])} unidades, {pct(g['Baixada Santista'], sinal=True)}). Nas demais de SP, "
      f"{pct(g['demais de SP'], sinal=True)}; no DF, {pct(g['DF'], sinal=True)}.",
      tamanho=TAM_NOTA, titulo="Não é efeito São Paulo", fundo=DESTAQUE_MUITO_CLARO, barra=DESTAQUE)

# ---------------- painel direito: correlações
xR0 = 0.52
axR = fig.add_axes([xR0, y_base + 0.075, 1 - MARGEM_X - xR0, y_topo - y_base - 0.16])
eixo_limpo(axR, grade="x")
axR.spines["left"].set_visible(False)
bbR = axR.get_position()
fig.text(0.315, bbR.y1 + 0.058, "O erro anda junto com alguma característica?", ha="left", va="bottom",
         fontsize=TAM_TEXTO + 1, fontweight="bold")
fig.text(0.315, bbR.y1 + 0.055, f"Spearman entre o erro de faturamento e cada uma das {n_var} características "
         "(lista fixada antes)", ha="left", va="top", fontsize=TAM_NOTA - 0.5, color=CINZA_ESCURO)
axR.axvspan(-r_crit, r_crit, color=CINZA_MUITO_CLARO, lw=0, zorder=0)
axR.axvline(0, color=CINZA_ESCURO, lw=0.8, zorder=1)
ys = np.arange(n_var)
axR.barh(ys, COR["e_fat"], height=0.62, color=CINZA, zorder=2)
axR.set_yticks(ys)
axR.set_yticklabels([rotulo_var(v) for v in COR["variável"]], fontsize=TAM_NOTA - 1)
axR.set_ylim(-0.7, n_var - 0.3)
axR.set_xlim(-0.45, 0.62)
axR.set_xticks([-0.4, -0.2, 0, 0.2, 0.4])
axR.xaxis.set_major_formatter(formatador_num(1, sinal=True))
axR.text(0, n_var - 0.35, f"zona do acaso (p ≥ 0,05): ±{num(r_crit, 2)}", ha="center", va="bottom",
         fontsize=TAM_NOTA - 1, color=CINZA_ESCURO, zorder=3,
         bbox=dict(boxstyle="round,pad=0.15", fc=CINZA_MUITO_CLARO, ec="none"))
axR.set_ylim(-0.7, n_var + 0.4)
ig = int(COR.index[COR["variável"].eq("preço do plano Gold")][0])
axR.text(gold["e_fat"] + 0.015, ig, f"{num(gold['e_fat'], 2, sinal=True)} (p = {num(gold['p_e_fat'], 3)})",
         ha="left", va="center", fontsize=TAM_NOTA - 0.5, color=TEXTO, fontweight="bold")
axR.text(0.25, ig - 1.6, "na borda — mas é foto de\nago/2026, depois do resultado:\no preço pode ter subido\n"
         "porque a unidade encheu", ha="left", va="top", fontsize=TAM_NOTA - 1, color=CINZA_ESCURO,
         linespacing=1.15)
axR.set_xlabel("correlação de Spearman com o erro de faturamento (N = 36–39)", fontsize=TAM_NOTA,
               color=CINZA_ESCURO)

# ------------------------------------------------------------------ dados
d_cor = COR.rename(columns={"variável": "item"})[["item", "N", "e_fat", "p_e_fat", "e_alunos", "p_e_alunos"]].copy()
d_cor.insert(0, "painel", "correlacao_erro_faturamento")
d_cor.insert(2, "rotulo", [rotulo_var(v) for v in d_cor["item"]])
d_cor["valor_critico_N39"] = r_crit
d_dec = pd.DataFrame([{"painel": "decomposicao_variancia_pct", "item": k, "e_fat": dec[k]} for k in dec])
d_reg = pd.DataFrame([{"painel": "erro_mediano_regiao_pct", "item": gname, "N": int(reg.loc[gname, "size"]),
                       "e_fat": reg.loc[gname, "median"] * 100} for gname in reg.index])
d_extra = pd.DataFrame([{"painel": "erro_mediano_regiao_pct", "item": "Grande SP (metrô de SP, sem Baixada)",
                         "N": len(grande_sp), "e_fat": grande_sp["erro_pct"].median() * 100},
                        {"painel": "erro_mediano_regiao_pct", "item": "SP inteiro",
                         "N": int(AN["uf"].eq("SP").sum()), "e_fat": med_sp_todo},
                        {"painel": "r2_fora_da_amostra", "item": "alunos", "e_fat": r2_alu},
                        {"painel": "r2_fora_da_amostra", "item": "faturamento", "e_fat": r2_fat}])
dados = pd.concat([d_dec, d_cor, d_reg, d_extra], ignore_index=True).rename(columns={"e_fat": "valor"})
salvar(fig, ID, dados)
