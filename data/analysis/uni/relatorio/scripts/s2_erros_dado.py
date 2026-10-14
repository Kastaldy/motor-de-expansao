"""s2_erros_dado — no caminho, achamos erros de dado que já distorciam a tela de produção.

Quadro desenhado em matplotlib. Os números de cada linha são lidos e conferidos nas fontes:
depara_divergencias.md, COBERTURA_UNI00.md, poi/relatorio_teste_poi_2026-09-25.md e CADERNO_ESTUDO_UNI.md.
"""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _estilo import *  # noqa: E402,F403
from matplotlib.patches import Rectangle  # noqa: E402

ID = "s2_erros_dado"
depara = (UNI / "depara_divergencias.md").read_text(encoding="utf-8")
cob = (UNI / "COBERTURA_UNI00.md").read_text(encoding="utf-8")
poi = (POI / "relatorio_teste_poi_2026-09-25.md").read_text(encoding="utf-8")
caderno = (UNI / "CADERNO_ESTUDO_UNI.md").read_text(encoding="utf-8")

# ------------------------------------------------------------------ números lidos
m = re.search(r"planilha atual traz R\$ ([\d.,]+); a copia da VPS[^R]*R\$ ([\d.,]+)", depara)
gua_real, gua_vps = numero_br(m.group(1)), numero_br(m.group(2))
alias_sc = "SÃO CARLOS" in depara and "ALIAS DECLARADO" in depara
zeros = int(re.search(r"'financeiro_zero_com_ativos[^']*': (\d+)", cob).group(1))
sem_m2 = int(re.search(r"Sem metragem: (\d+)", cob).group(1))
sagrada = "Sagrada Família, com pino em Cuiabá e cadastro em Rondonópolis" in cob
plaza_km = numero_br(re.search(r"plaza-sul-sp\*\* saiu[^,]*, ([\d,]+) km", poi).group(1))
wellhub = int(re.search(r"Filtro de musculação do Wellhub:\*\* perdia (\d+)%", caderno).group(1))

conferir("Guarujá ago/26 na cópia da VPS (R$)", gua_vps, 547745.05, 0.01)
conferir("Guarujá ago/26 na planilha (R$)", gua_real, 217525.74, 0.01)
conferir("razão VPS / real em Guarujá (≈ 2,5 vezes)", round(gua_vps / gua_real, 1), 2.5)
conferir("São Carlos por alias declarado", int(alias_sc), 1)
conferir("meses com faturamento zero e academia operando", zeros, 16)
conferir("unidades sem metragem", sem_m2, 44)
conferir("Sagrada Família com pino em outra cidade", int(sagrada), 1)
conferir("distância do pino da Plaza Sul (km)", plaza_km, 1.34, 0.001)
conferir("academias perdidas pelo filtro de musculação do Wellhub (%)", wellhub, 13)

linhas = [
    (f"Guarujá ago/26: a Visão Executiva mostrava {mil(gua_vps, 1)} contra {mil(gua_real, 1)} reais "
     "(célula carregada ainda em edição)", "tela de produção",
     "ingestão corrigida no código (PR #421); recarga na produção a conferir", True),
    ("São Carlos: o faturamento não aparecia na Visão Executiva (nome diferente entre sistemas)",
     "tela de produção", "corrigido no código: casa por código (PR #418); produção a conferir", True),
    (f"Pinos errados: Plaza Sul a {num(plaza_km, 1)} km da academia; Sagrada Família em outra cidade",
     "praça e concorrência calculadas no lugar errado",
     "corrigido no painel e no código (PR #422); produção a conferir", True),
    (f"Filtro de musculação do Wellhub perdia {wellhub}% das academias", "concorrência subcontada",
     "corrigido no código (PR #419); produção a conferir", True),
    (f"{zeros} meses com faturamento zero com a academia operando", "meses excluídos do modelo",
     "excluídos no painel; correção na origem cobrada do dono (PR #423)", False),
    (f"Metragem ausente em {sem_m2} de 98 unidades, quase todas abertas a partir de 2025",
     "impedia confirmar o modelo",
     "preenchida por satélite no painel; oficial cobrada do dono (PR #423)", False),
]

# ------------------------------------------------------------------ figura
fig = figura()
y_topo = cabecalho(
    fig,
    "No caminho, achamos erros de dado que já distorciam a tela de produção",
    "Erros de dado achados ao montar o painel da rede (UNI-00)",
)
y_base = rodape(
    fig,
    "Fonte: CADERNO_ESTUDO_UNI.md etapa 1; depara_divergencias.md; COBERTURA_UNI00.md; "
    "poi/relatorio_teste_poi_2026-09-25.md; git (PRs #418, #419, #421, #422 e #423, na main em 28/09) · "
    "status em 30/09: se as correções já estão no ar deve ser conferido antes da apresentação (BLK-DADOS-UNI-01)",
)

x0 = MARGEM_X + 0.012
colunas = [(x0, 0.43), (x0 + 0.455, 0.225), (x0 + 0.705, 1 - MARGEM_X - (x0 + 0.705))]
cab = ["o que estava errado", "onde afetava", "status"]
TAM = TAM_TEXTO + 0.5
y = y_topo - 0.02
for (cx, _), t in zip(colunas, cab):
    fig.text(cx, y, t.upper(), fontsize=8.5, fontweight="bold", color=CINZA_ESCURO, va="top")
y -= 0.04
fig.add_artist(matplotlib.lines.Line2D([MARGEM_X, 1 - MARGEM_X], [y, y], color=CINZA, lw=1))

espaco = y - (y_base + 0.045)
textos = []
alturas = []
for ln in linhas:
    cel = [quebrar(fig, ln[i], colunas[i][1] - 0.01, TAM, "bold" if i == 0 else "normal") for i in range(3)]
    n = max(c.count("\n") + 1 for c in cel)
    textos.append(cel)
    alturas.append(altura_linhas(fig, n, TAM, 1.3))
folga = (espaco - sum(alturas)) / len(linhas)
for (cel, h, ln) in zip(textos, alturas, linhas):
    y_lin = y - folga / 2
    if ln[3]:
        fig.add_artist(Rectangle((MARGEM_X, y - folga - h + 0.012), 0.005, h + folga - 0.024,
                                 transform=fig.transFigure, fc=DESTAQUE, ec="none"))
    for i, ((cx, _), c) in enumerate(zip(colunas, cel)):
        fig.text(cx, y_lin, c, fontsize=TAM, va="top", color=TEXTO if i != 1 else CINZA_ESCURO,
                 fontweight="bold" if i == 0 else "normal", linespacing=1.3)
    y -= h + folga
    fig.add_artist(matplotlib.lines.Line2D([MARGEM_X, 1 - MARGEM_X], [y, y], color=CINZA_CLARO, lw=0.8))

# legenda da barra (abaixo do quadro)
fig.add_artist(Rectangle((MARGEM_X, y_base + 0.004), 0.005, 0.022, transform=fig.transFigure, fc=DESTAQUE,
                         ec="none"))
fig.text(MARGEM_X + 0.012, y_base + 0.015, "barra azul = o erro tocava a tela de produção (linhas 1 a 4)",
         fontsize=TAM_NOTA, color=DESTAQUE, va="center", fontweight="bold")

# ------------------------------------------------------------------ dados
dados = pd.DataFrame(linhas, columns=["o_que_estava_errado", "onde_afetava", "status",
                                      "toca_producao"])
dados.insert(0, "linha", range(1, len(linhas) + 1))
salvar(fig, ID, dados)
