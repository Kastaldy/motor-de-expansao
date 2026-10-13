"""s5_botafogo — as alavancas declaradas explicam parte do caso; o resto é volume excepcional.

Fontes:
- alavancas/resultado_quanto_melhora.md, seção 3 (v2 R$ 244.762; + agregador declarado R$ 276.870;
  + preço + agregador R$ 353.853; real R$ 697.407);
- CADERNO_ESTUDO_UNI.md, etapa 9, "Teste 1" (payback 40 / 33 / 24 / 12 meses; viável não/sim/sim/sim;
  ~4.100 × ~2.100 alunos; corte ≈ R$ 260 mil com custo-padrão) e "Teste 2" (regressão robusta: 22% → 23–25%);
- uni05/comparacao_por_unidade.csv (conferência: fat_V2, fat_real, pb_V2, pb_REAL de Botafogo).
Ilustração: uma unidade, mesma demanda da v2, custos-padrão.
"""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _estilo import *  # noqa: E402,F403

ID = "s5_botafogo"
QM = (UNI / "alavancas" / "resultado_quanto_melhora.md").read_text(encoding="utf-8")
CAD = (UNI / "CADERNO_ESTUDO_UNI.md").read_text(encoding="utf-8")
U5 = pd.read_csv(UNI / "uni05" / "comparacao_por_unidade.csv", sep=";", encoding="utf-8-sig").set_index("unidade_id")

t3 = tabela_md(QM, "| cenário | erro típico | viés (mediana) |").set_index("cenário")


def prev(cen):
    a, b = t3.loc[cen, "Botafogo: previsto → real"].split("→")
    return numero_br(a), numero_br(b)


v2, real = prev("v2 (só praça)")
agr, _ = prev("v2 + agregador declarado")
pre_agr, _ = prev("v2 + preço + agregador")

# payback e viabilidade (caderno, etapa 9, Teste 1)
cad = {}
for rot, chave in [("como estava", "v2"), ("**100% recorrente (não aceita agregador)**", "agr"),
                   ("100% recorrente + preço real do plano (R$ 177)", "pre_agr"), ("realidade", "real")]:
    ln = next(x for x in CAD.splitlines() if x.startswith("| " + rot))
    cel = [c.strip().strip("*") for c in ln.strip().strip("|").split("|")]
    cad[chave] = dict(fat_mil=float(re.search(r"R\$ (\d+) mil", cel[1]).group(1)),
                      payback=int(re.search(r"(\d+) meses", cel[2]).group(1)), viavel=cel[3])
b5 = U5.loc["botafogo-rj"]

# ------------------------------------------------------------------ conferência
conferir("v2 (R$)", v2, 244762)
conferir("+ agregador declarado (R$)", agr, 276870)
conferir("+ preço + agregador (R$)", pre_agr, 353853)
conferir("real (R$)", real, 697407)
conferir("v2 = uni05 fat_V2 (R$ mil)", round(b5["fat_V2"] / 1000), round(v2 / 1000))
conferir("real = uni05 fat_real (R$ mil)", round(b5["fat_real"] / 1000), round(real / 1000))
conferir("payback v2 = uni05 pb_V2", cad["v2"]["payback"], int(b5["pb_V2"]))
conferir("payback real = uni05 pb_REAL", cad["real"]["payback"], int(b5["pb_REAL"]))
for k, e in {"v2": (245, 40, "não"), "agr": (277, 33, "sim"), "pre_agr": (354, 24, "sim"),
             "real": (697, 12, "sim")}.items():
    conferir(f"caderno {k}: faturamento (R$ mil)", cad[k]["fat_mil"], e[0])
    conferir(f"caderno {k}: payback", cad[k]["payback"], e[1])
    conferir(f"caderno {k}: viável = {e[2]}", int(cad[k]["viavel"] == e[2]), 1)
conferir("caderno: ~4.100 alunos reais × ~2.100 previstos", int("~4.100 alunos reais contra ~2.100 previstos" in CAD), 1)
conferir("caderno: corte ≈ R$ 260 mil", int("faturar mais de ~R$ 260 mil" in CAD), 1)
conferir("caderno: regressão robusta 22% → 23–25%", int("O erro vai de 22% para 23–25%" in CAD), 1)

d_agr, d_pre, d_resto = agr - v2, pre_agr - agr, real - pre_agr
# degraus exibidos = diferença dos totais arredondados (a cascata fecha em R$ mil: 245 + 32 + 77 = 354; 354 + 343 = 697)
def degrau(a, b):
    return round(b / 1000) - round(a / 1000)


conferir("degrau agregador (R$ mil)", degrau(v2, agr), 32)
conferir("degrau preço (R$ mil)", degrau(agr, pre_agr), 77)
conferir("diferença não explicada (R$ mil)", degrau(pre_agr, real), 343)

# ------------------------------------------------------------------ figura
fig = figura()
y_topo = cabecalho(
    fig,
    "Botafogo: as alavancas declaradas explicam parte do caso — o resto é volume excepcional",
    "Faturamento mensal maduro previsto para Botafogo (RJ) com as alavancas declaradas pelo operador, mesma demanda "
    "do modelo da praça (conta do simulador, no cenário mais favorável)",
    selo="ILUSTRAÇÃO",
)
y_base = rodape(
    fig,
    "Fonte: alavancas/resultado_quanto_melhora.md (seção 3); CADERNO_ESTUDO_UNI.md etapa 9 · N = 1 unidade; "
    "custos-padrão: aluguel R$ 20 mil, obra R$ 2,34 mi · payback pelo simulador de produção, com a rampa observada",
)

X_AX0, X_AX1 = 0.085, 0.705
ax = fig.add_axes([X_AX0, y_base + 0.15, X_AX1 - X_AX0, y_topo - y_base - 0.20])
eixo_limpo(ax, grade="y")
ax.set_facecolor("none")
M = 1000
etapas = [
    dict(rot="Modelo da praça", base=0, alt=v2, tipo="total", cor=CINZA_ESCURO, pb=cad["v2"]),
    dict(rot="+ não aceita agregador", base=v2, alt=d_agr, tipo="passo", cor=DESTAQUE_CLARO,
         pb=cad["agr"], sup="supondo que todo aluno de agregador vira recorrente"),
    dict(rot="+ preço real do plano (R$ 177)", base=agr, alt=d_pre, tipo="passo", cor=DESTAQUE_CLARO, pb=None,
         sup="mesmos alunos com o preço novo; a reação do volume ao preço não foi medida"),
    dict(rot="Com as alavancas declaradas", base=0, alt=pre_agr, tipo="total", cor=DESTAQUE, pb=cad["pre_agr"]),
    dict(rot="+ diferença não explicada (volume: ~4.100 alunos reais × ~2.100 previstos)", base=pre_agr, alt=d_resto,
         tipo="resto", cor=CINZA_CLARO, pb=None),
    dict(rot="Real", base=0, alt=real, tipo="total", cor=REAL, pb=cad["real"]),
]
L_BAR = 0.62
for i, e in enumerate(etapas):
    if e["tipo"] == "resto":
        ax.bar(i, e["alt"] / M, bottom=e["base"] / M, width=L_BAR, color="white", edgecolor=CINZA, hatch="////",
               lw=0.9, zorder=2)
    else:
        ax.bar(i, e["alt"] / M, bottom=e["base"] / M, width=L_BAR, color=e["cor"], zorder=2)
    topo = (e["base"] + e["alt"]) / M
    # valor
    if e["tipo"] == "total":
        txt, cor_t = num(topo), TEXTO
    else:
        txt = f"+{degrau(e['base'], e['base'] + e['alt'])}"
        cor_t = DESTAQUE if e["tipo"] == "passo" else CINZA_ESCURO
    if e["tipo"] == "resto":
        ax.text(i, (e["base"] + e["alt"] / 2) / M, txt, ha="center", va="center", fontsize=TAM_TEXTO + 1,
                fontweight="bold", color=cor_t, bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none"))
    else:
        ax.text(i, topo + 8, txt, ha="center", va="bottom", fontsize=TAM_TEXTO + 1, fontweight="bold", color=cor_t,
                zorder=4, bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none"))
    # payback e viabilidade
    if e["pb"]:
        pb = e["pb"]
        via = "viável" if pb["viavel"] == "sim" else "não viável"
        cor_pb = DESTAQUE if pb["viavel"] == "sim" else CINZA_ESCURO
        ax.text(i, topo + 45, f"payback {pb['payback']} meses\n{via}", ha="center", va="bottom",
                fontsize=TAM_NOTA - 0.5, color=cor_pb, linespacing=1.15,
                fontweight="bold" if pb["viavel"] == "sim" else "normal")
    # suposição da conta, sob o degrau
    if e.get("sup"):
        ax.text(i, 120, quebrar(fig, e["sup"], 0.098, TAM_NOTA - 1), ha="center", va="center",
                fontsize=TAM_NOTA - 1, color=CINZA_ESCURO, style="italic", linespacing=1.15)
    # conector
    if i < len(etapas) - 1:
        ax.plot([i + L_BAR / 2, i + 1 - L_BAR / 2], [topo, topo], color=CINZA, lw=0.8, ls=(0, (2, 2)), zorder=1)

CORTE = 260
ax.axhline(CORTE, color=AMBAR, lw=1.1, ls=(0, (5, 3)), zorder=1)
ax.text(4.0, CORTE - 10, "viável ≈ faturar mais de\nR$ 260 mil (custos-padrão)", ha="center", va="top",
        fontsize=TAM_NOTA - 0.5, color=AMBAR, linespacing=1.1,
        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"))
ax.set_xlim(-0.55, len(etapas) - 0.45)
ax.set_ylim(0, 800)
ax.set_yticks(range(0, 801, 200))
ax.yaxis.set_major_formatter(formatador_num(0))
ax.set_ylabel("R$ mil por mês", fontsize=TAM_NOTA, color=CINZA_ESCURO)
ax.set_xticks(range(len(etapas)))
ax.set_xticklabels([quebrar(fig, e["rot"], 0.095, TAM_NOTA) for e in etapas], fontsize=TAM_NOTA,
                   linespacing=1.15)
for t, e in zip(ax.get_xticklabels(), etapas):
    if e["rot"] in ("Com as alavancas declaradas",):
        t.set_color(DESTAQUE)
        t.set_fontweight("bold")
    elif e["tipo"] == "total":
        t.set_fontweight("bold")
        t.set_color(TEXTO)

# ------------------------------------------------------------------ coluna da direita
X_C, W_C = 0.73, 1 - MARGEM_X - 0.73
y = y_topo - 0.02
y = caixa(fig, X_C, y, W_C,
          f"Declarar 'não aceita agregador' e o preço real do plano leva a previsão de R$ {num(v2 / M)} mil para "
          f"R$ {num(pre_agr / M)} mil (+{num(100 * (pre_agr / v2 - 1))}%): nessa conta, passaria o corte de "
          "viabilidade. É a ponta otimista — todo aluno de agregador vira recorrente e o volume não reage ao preço.",
          tamanho=TAM_NOTA + 0.5, fundo=DESTAQUE_MUITO_CLARO, barra=DESTAQUE, titulo="Leitura")
y = caixa(fig, X_C, y - 0.02, W_C,
          "O que falta até o real é volume: ~4.100 alunos reais contra ~2.100 previstos. É uma demanda local "
          "excepcional.", tamanho=TAM_NOTA)
y = caixa(fig, X_C, y - 0.02, W_C,
          "Excepcional se trata com alavancas declaradas pelo operador, não abafando dados: a regressão robusta não "
          "melhora (erro 22% → 23–25%).", tamanho=TAM_NOTA)
caixa(fig, X_C, y - 0.02, W_C,
      "Botafogo fica em todos os testes do modelo; sai só do teste de fachada (decisão do dono).",
      tamanho=TAM_NOTA, barra=AMBAR)

# ------------------------------------------------------------------ dados
dados = pd.DataFrame([dict(ordem=i + 1, etapa=e["rot"], tipo=e["tipo"], base_reais=round(e["base"]),
                           valor_reais=round(e["alt"]), topo_reais=round(e["base"] + e["alt"]),
                           payback_meses=e["pb"]["payback"] if e["pb"] else None,
                           viavel=e["pb"]["viavel"] if e["pb"] else None, suposicao=e.get("sup", ""))
                      for i, e in enumerate(etapas)])
dados["corte_viavel_aprox_reais"] = CORTE * M
salvar(fig, ID, dados)
