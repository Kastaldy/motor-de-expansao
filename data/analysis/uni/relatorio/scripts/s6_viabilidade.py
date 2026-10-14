"""s6_viabilidade — no simulador, o modelo da praça (v2 do UNI-05) prevê melhor faturamento e payback e empata com a regra atual na decisão.

Fontes:
- uni05/resultado_uni05.md (v1.1), tabela "Principal — 18 unidades de teste" (ATUAL 33% / −24%, V2 22% / +1%;
  payback nas não censuradas 20 × 14; decisão 72% × 67%; aprovações 0 × 1; rejeições 5 × 5; 'reprovar tudo' 56%;
  V2 erra menos o payback em 6 de 10; cenário A: 3 aprovações indevidas; receita por aluno no simulador R$ 115);
- uni05/comparacao_por_unidade.csv (conferência de todos os números acima, unidade a unidade);
- CADERNO_ESTUDO_UNI.md etapas 9 e 10 (decisão do dono de 29/09; Mococa no corte; excepcionais; R$ 117 × R$ 108;
  ressalva da contagem de agregador).
"""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _estilo import *  # noqa: E402,F403

ID = "s6_viabilidade"
MD = (UNI / "uni05" / "resultado_uni05.md").read_text(encoding="utf-8")
CAD = (UNI / "CADERNO_ESTUDO_UNI.md").read_text(encoding="utf-8")
CSV = pd.read_csv(UNI / "uni05" / "comparacao_por_unidade.csv", sep=";", encoding="utf-8-sig")

# ------------------------------------------------------------------ números publicados (tabela principal, teste)
bloco = MD.split("## Principal — 18 unidades de teste")[1].split("## Secundária")[0]
tp = tabela_md(bloco, "| cenário | faturamento: erro / viés |").set_index("cenário")


def lin(cen):
    r = tp.loc[cen]
    fe, fv = [numero_br(x) for x in r["faturamento: erro / viés"].split("/")]
    return dict(erro=fe, vies=fv, pb_nc=numero_br(r["payback: erro só nas não censuradas"]),
                dec=numero_br(r["decisão igual ao REAL"]), aprov=int(r["aprovações indevidas"]),
                rej=int(r["rejeições indevidas"]))


A, V = lin("ATUAL"), lin("V2")
aprov_A_rampa = int(tp.loc["A: demanda ATUAL + rampa obs.", "aprovações indevidas"])
reprovar_tudo = float(re.search(r"'reprovar tudo': acerta (\d+)%", bloco).group(1))
m = re.search(r"Unidades não censuradas \(REAL < 61 meses\): (\d+); V2 erra menos o payback em (\d+)", bloco)
n_nc, v2_melhor = int(m.group(1)), int(m.group(2))
rec_sim = float(re.search(r"Receita por aluno no simulador \(regime pleno\): R\$ (\d+)", MD).group(1))
conferir("V2 recomendada para DEC? NÃO", int("**V2 recomendada para DEC? NÃO**" in MD), 1)

# ------------------------------------------------------------------ conferência contra o roteiro e o CSV
for k, v, e in [("erro faturamento", (A["erro"], V["erro"]), (33, 22)), ("viés", (A["vies"], V["vies"]), (-24, 1)),
                ("payback nas não censuradas", (A["pb_nc"], V["pb_nc"]), (20, 14)),
                ("decisão", (A["dec"], V["dec"]), (72, 67)), ("aprovações indevidas", (A["aprov"], V["aprov"]), (0, 1)),
                ("rejeições indevidas", (A["rej"], V["rej"]), (5, 5))]:
    conferir(f"{k}: regra atual", v[0], e[0])
    conferir(f"{k}: v2", v[1], e[1])
conferir("'reprovar tudo' (%)", reprovar_tudo, 56)
conferir("não censuradas", n_nc, 10)
conferir("v2 erra menos o payback em", v2_melhor, 6)
conferir("cenário A: aprovações indevidas", aprov_A_rampa, 3)
conferir("receita por aluno no simulador (R$)", rec_sim, 115)
conferir("caderno: R$ 117 × R$ 108", int("~R$ 117, contra ~R$ 108" in CAD), 1)

t = CSV[CSV["grupo"] == "teste"].copy()
conferir("CSV: 18 unidades de teste", len(t), 18)
nc = t[t["pb_REAL"] < 61]
for k, cod in (("regra atual", "ATUAL"), ("v2", "V2")):
    e = t["fat_real"] / t[f"fat_{cod}"] - 1
    ref = A if cod == "ATUAL" else V
    conferir(f"CSV {k}: erro típico (%)", round(100 * e.abs().median(), 1), ref["erro"], 0.5)
    conferir(f"CSV {k}: viés (%)", round(100 * e.median(), 1), ref["vies"], 0.5)
    conferir(f"CSV {k}: erro de payback nas não censuradas", float(np.median(np.abs(nc[f"pb_{cod}"] - nc["pb_REAL"]))),
             ref["pb_nc"], 0.5)
    conferir(f"CSV {k}: decisão igual (%)", round(100 * (t[f"ok_{cod}"] == t["ok_REAL"]).mean()), ref["dec"], 0.5)
    conferir(f"CSV {k}: aprovações indevidas", int((t[f"ok_{cod}"] & ~t["ok_REAL"]).sum()), ref["aprov"])
    conferir(f"CSV {k}: rejeições indevidas", int((~t[f"ok_{cod}"] & t["ok_REAL"]).sum()), ref["rej"])
exc = sorted(t.loc[t["ok_REAL"] & ~t["ok_ATUAL"] & ~t["ok_V2"], "nome"])
conferir("excepcionais que as duas regras deixam de fora", int(exc == ["BOTAFOGO", "BUTANTA", "CARIACICA",
                                                                        "VILA GUANABARA"]), 1)
moc = t.set_index("nome").loc["MOCOCA"]
conferir("Mococa: payback v2 no corte de 36 meses", float(moc["pb_V2"]), 36)
conferir("Mococa: aprovação indevida da v2", int(bool(moc["ok_V2"]) and not bool(moc["ok_REAL"])), 1)
conferir("decisão: diferença líquida de 1 unidade", int((t["ok_ATUAL"] == t["ok_REAL"]).sum() -
                                                        (t["ok_V2"] == t["ok_REAL"]).sum()), 1)

# ------------------------------------------------------------------ figura
fig = figura()
y_topo = cabecalho(
    fig,
    "No simulador, o modelo da praça prevê melhor faturamento e payback — e empata na decisão de aprovar",
    "As 18 unidades abertas em 2025 passadas pelo simulador de produção, com custos-padrão · modelo da praça = "
    "a v2 do UNI-05 (m², renda e população da praça + rampa observada), sem estúdios nem master",
)
y_base = rodape(
    fig,
    "Fonte: uni05/resultado_uni05.md (v1.1; a v1.0 tinha um ajuste de calendário assimétrico, corrigido, que invertia "
    "a conclusão) · N = 18 · aluguel R$ 20 mil, obra R$ 2,34 mi; payback > 60 conta como 61",
    nota="A v2 de trabalho (modelo da praça + estúdios + master) erra o mesmo no faturamento (22,1%; UNI-07: 22–23%) "
         "e NÃO foi rodada no simulador contra a regra atual. Por que 33% aqui e 27% no placar (s3/s6_escada): 27% = "
         "regra de metragem com a receita por aluno observada (UNI-02); 33% = cálculo exato do simulador de produção "
         "(R$ 115 por aluno, UNI-05).",
)

TXT_DEC = ("Critério fixado antes: modelo da praça não recomendado para DEC agora. Decisão do dono (29/09): o objetivo "
           "é prever melhor, e ele vale como base de previsão da viabilidade (depois ganhou estúdios e master e virou "
           "a v2 de trabalho). Antes de uma DEC: aluguel e obra reais e repetir na turma de 2026.")


def altura_caixa(largura, texto, tamanho, titulo=None):
    """Mesma conta de _estilo.caixa, para posicionar a caixa pela base."""
    pad = 0.012
    h = altura_linhas(fig, quebrar(fig, texto, largura - 2 * pad, tamanho).count("\n") + 1, tamanho, 1.3)
    if titulo:
        h += altura_linhas(fig, quebrar(fig, titulo, largura - 2 * pad, tamanho + 0.5, "bold").count("\n") + 1,
                           tamanho + 0.5, 1.3) + 0.006
    return h + 2 * pad


h_dec = altura_caixa(1 - 2 * MARGEM_X, TXT_DEC, TAM_NOTA + 0.5)
y_dec = y_base + 0.012 + h_dec
caixa(fig, MARGEM_X, y_dec, 1 - 2 * MARGEM_X, TXT_DEC, tamanho=TAM_NOTA + 0.5, fundo=DESTAQUE_MUITO_CLARO,
      barra=DESTAQUE)

# notas em três colunas
NOTAS = [
    "Com custo-padrão, viável ≈ faturar mais de R$ 260 mil: várias unidades ficam coladas no corte. A diferença "
    "líquida é 1 unidade: Mococa, com payback previsto de 36 meses, no corte. As duas regras deixam de fora as mesmas "
    "excepcionais (Botafogo, Butantã, Cariacica, Vila Guanabara).",
    f"Trocar só a rampa, sem a demanda da praça, aprovaria {aprov_A_rampa} fracas: as duas mudanças andam juntas.",
    f"Parte do otimismo da regra atual vem da receita por aluno do simulador (R$ {num(rec_sim)}–117 contra ~R$ 108 "
    "observados), número que carrega a ressalva da contagem de agregador.",
]
W_N = (1 - 2 * MARGEM_X - 2 * 0.02) / 3
h_n = max(altura_caixa(W_N, n_, TAM_NOTA - 0.5) for n_ in NOTAS)
y_n = y_dec + 0.018 + h_n
for j, n_ in enumerate(NOTAS):
    caixa(fig, MARGEM_X + j * (W_N + 0.02), y_n, W_N, n_, tamanho=TAM_NOTA - 0.5)
y_pan_bot = y_n + 0.13  # espaço para os rótulos do eixo e a linha de aprovações/rejeições

# ---------------- 4 painéis
PAINEIS = [
    dict(tit="Erro típico do faturamento", sub="menor é melhor", va=(A["erro"], V["erro"]), fmt="%", lim=(0, 40)),
    dict(tit="Viés do faturamento", sub="negativo = promete demais", va=(A["vies"], V["vies"]), fmt="%s",
         lim=(-30, 10)),
    dict(tit="Erro típico do payback", sub=f"nas {n_nc} que se pagam em até 60 meses", va=(A["pb_nc"], V["pb_nc"]),
         fmt=" meses", lim=(0, 28)),
    dict(tit="Acerto da decisão 'viável'", sub=f"tracejado: 'reprovar tudo' acerta {num(reprovar_tudo)}%",
         va=(A["dec"], V["dec"]), fmt="%", lim=(0, 100)),
]
W_P, GAP = 0.17, 0.068
x0 = MARGEM_X + 0.035
y_pt = y_topo - 0.01
linhas_csv = []
for i, pn in enumerate(PAINEIS):
    xa = x0 + i * (W_P + GAP)
    fig.text(xa - 0.03, y_pt, pn["tit"], ha="left", va="top", fontsize=TAM_TEXTO, fontweight="bold", color=TEXTO)
    fig.text(xa - 0.03, y_pt - 0.03, pn["sub"], ha="left", va="top", fontsize=TAM_NOTA - 0.5, color=CINZA_ESCURO)
    ax = fig.add_axes([xa, y_pan_bot, W_P, y_pt - 0.085 - y_pan_bot])
    eixo_limpo(ax, grade="y")
    ax.set_facecolor("none")
    cores = (CINZA_ESCURO, DESTAQUE)
    for j, (v, cor) in enumerate(zip(pn["va"], cores)):
        ax.bar(j, v, width=0.58, color=cor, zorder=2)
        if pn["fmt"] == "%s":
            txt = pct(v, sinal=True)
        elif pn["fmt"] == "%":
            txt = pct(v)
        else:
            txt = f"{num(v)}{pn['fmt']}"
        span = pn["lim"][1] - pn["lim"][0]
        yv = v + 0.02 * span if v >= 0 else v - 0.02 * span
        ax.text(j, yv, txt, ha="center", va="bottom" if v >= 0 else "top", fontsize=TAM_TEXTO + 2,
                fontweight="bold", color=DESTAQUE if j == 1 else TEXTO, zorder=4)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Regra\natual", "Modelo\nda praça"], fontsize=TAM_NOTA + 0.5, linespacing=1.1)
    ax.get_xticklabels()[1].set_color(DESTAQUE)
    ax.get_xticklabels()[1].set_fontweight("bold")
    ax.set_xlim(-0.6, 1.6)
    ax.set_ylim(*pn["lim"])
    if pn["fmt"] in ("%", "%s"):
        ax.yaxis.set_major_formatter(formatador_num(0, "%", sinal=pn["fmt"] == "%s"))
    if i == 1:
        ax.axhline(0, color=TEXTO, lw=1.0, zorder=3)
        ax.set_yticks([-30, -20, -10, 0, 10])
    if i == 2:
        ax.text(1.6, 27.5, f"praça erra menos em {v2_melhor} de {n_nc}", ha="right", va="top", fontsize=TAM_NOTA - 0.5,
                color=DESTAQUE)
    if i == 3:
        ax.axhline(reprovar_tudo, color=AMBAR, lw=1.1, ls=(0, (5, 3)), zorder=3)
        ax.set_yticks([0, 25, 50, 75, 100])
        fig.text(xa + W_P / 2, y_pan_bot - 0.078,
                 f"aprov. indevidas: {A['aprov']} (atual) × {V['aprov']} (praça)\nrejeições indevidas: {A['rej']} × "
                 f"{V['rej']}",
                 ha="center", va="top", fontsize=TAM_NOTA - 0.5, color=TEXTO, linespacing=1.2)
    for j, (cen, v) in enumerate(zip(("regra atual", "modelo da praça (v2 do UNI-05)"), pn["va"])):
        linhas_csv.append(dict(painel=pn["tit"], cenario=cen, valor=v,
                               unidade="%" if pn["fmt"] in ("%", "%s") else "meses"))

# ------------------------------------------------------------------ dados
for cen, r in (("regra atual", A), ("modelo da praça (v2 do UNI-05)", V)):
    linhas_csv.append(dict(painel="aprovações indevidas", cenario=cen, valor=r["aprov"], unidade="unidades"))
    linhas_csv.append(dict(painel="rejeições indevidas", cenario=cen, valor=r["rej"], unidade="unidades"))
linhas_csv.append(dict(painel="linha de base 'reprovar tudo'", cenario="—", valor=reprovar_tudo, unidade="%"))
linhas_csv.append(dict(painel="cenário A (demanda atual + rampa observada): aprovações indevidas", cenario="—",
                       valor=aprov_A_rampa, unidade="unidades"))
linhas_csv.append(dict(painel="payback: modelo da praça erra menos (não censuradas)",
                       cenario="modelo da praça (v2 do UNI-05)", valor=v2_melhor,
                       unidade=f"de {n_nc}"))
salvar(fig, ID, pd.DataFrame(linhas_csv))
