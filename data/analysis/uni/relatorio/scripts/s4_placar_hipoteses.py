"""s4_placar_hipoteses — além do modelo da praça, nenhuma variável de território se confirmou.

Placar (hipótese × veredito). Os vereditos resumem os resultados publicados e são conferidos contra eles:
uni01/resultado_uni01.md (classe de T01, T02, T05, T06, T07, T09–T17); uni02/resultado_uni02.md;
uni02r/resultado_uni02r.md; uni03/resultado_uni03.md; uni04/resultado_uni04a.md; uni01/resultado_duas_partes.md;
alavancas/resultado_quanto_melhora.md; mix/resultado_mix_alunos.md (X1); poi/saidas/resultado_teste_poi.md;
CADERNO_ESTUDO_UNI.md (etapa 2 e mensagens-chave 6 e 8).
"""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _estilo import *  # noqa: E402,F403
from matplotlib.patches import FancyBboxPatch  # noqa: E402

ID = "s4_placar_hipoteses"


def ler(p):
    return (UNI / p).read_text(encoding="utf-8")


R01, R02, R02R, R03 = ler("uni01/resultado_uni01.md"), ler("uni02/resultado_uni02.md"), \
    ler("uni02r/resultado_uni02r.md"), ler("uni03/resultado_uni03.md")
R04, DP, QM, MIX = ler("uni04/resultado_uni04a.md"), ler("uni01/resultado_duas_partes.md"), \
    ler("alavancas/resultado_quanto_melhora.md"), ler("mix/resultado_mix_alunos.md")
POI_MD = (POI / "saidas" / "resultado_teste_poi.md").read_text(encoding="utf-8")
CAD = ler("CADERNO_ESTUDO_UNI.md")

# ------------------------------------------------------------------ conferência contra as fontes
t01 = tabela_md(R01, "| teste | destino |").set_index("teste")
classe = t01["classe"].str.strip("*")
for t, c in {"T01": "candidata", "T02": "inconclusiva", "T05": "inconclusiva", "T06": "candidata",
             "T07": "candidata", "T09": "candidata", "T10": "inconclusiva", "T11": "inconclusiva",
             "T12": "inconclusiva", "T13": "inconclusiva", "T14": "candidata", "T15": "inconclusiva",
             "T16": "candidata", "T17": "candidata"}.items():
    conferir(f"UNI-01 {t} classe = {c}", int(classe[t] == c), 1)
ef = lambda t: numero_br(t01.loc[t, "efeito"].split()[0])  # noqa: E731
conferir("T01 renda → ticket (+%)", ef("T01"), 8.0)
conferir("T06 agregador → alunos (+%)", ef("T06"), 17.9)
conferir("T06 na sensibilidade A (maturidade ajustada, +%)", numero_br(t01.loc["T06", "A"]), 5.8)
conferir("T07 agregador → ticket (%)", ef("T07"), -10.4)
conferir("T14 demanda TotalPass (+%)", ef("T14"), 14.4)
conferir("UNI-02: M0 se confirma", int("**M0 se confirma? SIM.**" in R02), 1)
conferir("UNI-02r: Engenharia do Corpo inconclusivo", int("| **inconclusivo** |" in R02R), 1)
conferir("UNI-03: curva vence o simulador (ativos e faturamento)", R03.count("curva vence o simulador atual? **sim**"), 2)
q1 = tabela_md(R04, "| amostra | N | efeito [IC 90%] |").set_index("amostra")
conferir("UNI-04 Q1 inconclusivo", int(q1.loc["Q1: unidades novas, com idade (DECIDE)", "classe"] == "inconclusivo"), 1)
conferir("UNI-04 Q2 persiste (efeito, pp)", numero_br(q1.loc["Q2: unidades do T17 em 2026", "efeito [IC 90%]"].split()[0]),
         -0.90)
dp = tabela_md(DP, "| variante | descrição |").set_index("variante")
conferir("duas partes: R² LOO do M0", float(dp.loc["M0", "R² fora da amostra (LOO)"]), 0.302)
conferir("duas partes: R² LOO do M1 (duas partes)", float(dp.loc["M1", "R² fora da amostra (LOO)"]), 0.268)
qm = tabela_md(QM, "| modelo | faturamento: erro típico |").set_index("modelo")
e_m0 = numero_br(qm.loc["M0 (m², renda, população)", "faturamento: erro típico"])
e_est = numero_br(qm.loc["M0 + estado", "faturamento: erro típico"])
e_esc = numero_br(qm.loc["M0 + escritórios", "faturamento: erro típico"])
e_amb = numero_br(qm.loc["M0 + estado + escritórios", "faturamento: erro típico"])
conferir("etapa 12: erro do M0 (%)", e_m0, 21.5)
conferir("etapa 12: + estado piora (%)", e_est, 24.9)
conferir("etapa 12: + escritórios piora (%)", e_esc, 24.8)
conferir("etapa 12: + estado + escritórios piora (%)", e_amb, 26.0)
x1 = re.search(r"^\| X1 \|.*\*\*(\w+)\*\* \|$", MIX, re.M).group(1)
conferir("mix X1 (renda → % agregador) inconclusiva", int(x1 == "inconclusiva"), 1)
conferir("POI: 3 famílias sem ganho detectável", POI_MD.count("sem ganho detectável neste N"), 3)
conferir("caderno: população a pé não se repetiu na Ultra", int("não\nse repetiu" in CAD or "não se repetiu" in CAD), 1)

# ------------------------------------------------------------------ placar
CONF, FAV, SINAL = "CONFIRMADO", "A FAVOR, SEM PROVA", "SINAL NA EXPLORAÇÃO"
SEM, NREP, NEXP, NMEL, SOMAD, SGAN = ("SEM EFEITO GRANDE", "NÃO SE REPETIU", "NÃO EXPLICA", "NÃO MELHORA",
                                      "SÓ NA REDE MADURA", "SEM GANHO")
PIORA = "PIORA A PREVISÃO"
GRUPOS = [
    ("TERRITÓRIO E PRAÇA", "prever o faturamento de um ponto novo", [
        ("Metragem + renda + população a 10 min de carro", CONF, "sem viés, ordena melhor; erro típico ~22%",
         "UNI-02", "uni02/resultado_uni02.md"),
        ("Hipótese do diretor: tamanho rende mais entre independentes", FAV,
         "passou por 2 pontos nas novas; empata nas sensibilidades; igual em outra rede",
         "T09 · UNI-02 · réplica",
         "uni01/resultado_uni01.md; uni02/resultado_uni02.md; uni02r/resultado_uni02r.md"),
        ("Quantidade de concorrência / saturação", SEM, "", "T10 · T11", "uni01/resultado_uni01.md"),
        ("Crescimento da cidade e do bairro", SEM, "", "T12 · T13", "uni01/resultado_uni01.md"),
        ("Preço da Ultra frente à concorrência", SEM, "", "T05", "uni01/resultado_uni01.md"),
        ("População a pé na mesma cidade", NREP, "pista vinda da Smart Fit", "T15",
         "uni01/resultado_uni01.md; poi/relatorio_teste_poi_2026-09-25.md"),
        ("Empresas, shoppings e estações no entorno (POI)", SGAN, "nem na Ultra, nem na Smart Fit",
         "POI 25/09", "poi/saidas/resultado_teste_poi.md"),
        ("Estado ou escritórios somados ao modelo", NMEL,
         f"exploratório: erro {num(e_m0, 1)}% → {num(e_esc, 1)}–{num(e_amb, 1)}%", "etapa 12",
         "alavancas/resultado_quanto_melhora.md"),
        ("Modelo em duas partes (alunos × ticket)", NMEL,
         f"R² fora da amostra {num(float(dp.loc['M0', 'R² fora da amostra (LOO)']), 2)} → "
         f"{num(float(dp.loc['M1', 'R² fora da amostra (LOO)']), 2)}", "etapa 7",
         "uni01/resultado_duas_partes.md; CADERNO_ESTUDO_UNI.md (etapa 7)"),
    ]),
    ("RENDA", "como a renda da praça age", [
        ("Renda → ticket", SINAL, f"+{num(ef('T01'))}% por degrau típico; não conferido em unidades novas", "T01",
         "uni01/resultado_uni01.md"),
        ("Renda → cancelamento", SOMAD, "−1,3 ponto na rede madura; −0,2 (IC cruza zero) nas novas", "UNI-04",
         "uni04/resultado_uni04a.md"),
        ("Renda → % de agregador", NEXP, "", "T02 · X1", "uni01/resultado_uni01.md; mix/resultado_mix_alunos.md"),
    ]),
    ("OPERAÇÃO", "depois de abrir e decisões do operador", [
        ("Alunos do mês 3 → nível maduro", CONF, "erro de 5–9% em 22 unidades novas", "T16 · UNI-03",
         "uni01/resultado_uni01.md; uni03/resultado_uni03.md"),
        ("Rampa real × simulador", CONF, "a curva erra metade do simulador nos alunos", "UNI-03",
         "uni03/resultado_uni03.md"),
        ("Mais agregador: menos ticket e mais alunos", SINAL,
         f"ticket {num(ef('T07'))}% (firme); alunos +{num(ef('T06'))}%, +{num(numero_br(t01.loc['T06', 'A']))}% "
         "com maturidade ajustada; contagem não 100% limpa", "T06 · T07", "uni01/resultado_uni01.md"),
        ("Demanda de TotalPass na região", SINAL, "fonte restrita: não entra no modelo", "T14",
         "uni01/resultado_uni01.md"),
    ]),
]
ESTILO_CHIP = {
    CONF: dict(fc=DESTAQUE, ec=DESTAQUE, cor="white", peso="bold"),
    FAV: dict(fc="white", ec=DESTAQUE, cor=DESTAQUE, peso="bold"),
    SINAL: dict(fc="white", ec=DESTAQUE, cor=DESTAQUE, peso="bold"),
    PIORA: dict(fc=CINZA_ESCURO, ec=CINZA_ESCURO, cor="white", peso="bold"),
}
for v in (SEM, NREP, NEXP, NMEL, SOMAD, SGAN):
    ESTILO_CHIP[v] = dict(fc=CINZA_CLARO, ec=CINZA_CLARO, cor=TEXTO, peso="normal")

# ------------------------------------------------------------------ figura
fig = figura()
y_topo = cabecalho(
    fig,
    "Além do modelo da praça, nenhuma variável de território se confirmou",
    "Hipóteses testadas no estudo, com regra escrita antes e, quando possível, conferência em unidades novas",
)
y_base = rodape(
    fig,
    "Fonte: resultados UNI-01 a UNI-05 e teste de POI (ver dados/s4_placar_hipoteses.csv) · Sem efeito = sem "
    "efeito grande: com 39 unidades, só efeitos grandes aparecem; vale para as variáveis como foram medidas e pode "
    "ser revisitado",
)

X_HIP, X_CHIP, W_CHIP, X_LEIT, X_ID = MARGEM_X + 0.012, 0.535, 0.165, 0.63, 0.965
n_linhas = sum(len(g[2]) for g in GRUPOS)
h_cab = 0.034
h_grupo = 0.040
h_linha = (y_topo - 0.012 - h_cab - y_base - 0.006 - len(GRUPOS) * h_grupo) / n_linhas
y = y_topo - 0.005
# cabeçalho das colunas
for x, txt, ha in [(X_HIP, "hipótese", "left"), (X_CHIP, "veredito", "center"), (X_LEIT, "leitura", "left"),
                   (X_ID, "teste / etapa", "right")]:
    fig.text(x, y - h_cab / 2, txt, ha=ha, va="center", fontsize=TAM_NOTA - 0.5, color=CINZA_ESCURO,
             fontweight="bold")
y -= h_cab
fig.add_artist(matplotlib.lines.Line2D([MARGEM_X, 1 - MARGEM_X], [y, y], color=CINZA, lw=0.8))

linhas_csv = []
for nome_g, sub_g, itens in GRUPOS:
    fig.text(MARGEM_X, y - h_grupo * 0.55, nome_g, ha="left", va="center", fontsize=TAM_TEXTO, fontweight="bold",
             color=TEXTO)
    wg = largura_texto(fig, nome_g, TAM_TEXTO, "bold")
    fig.text(MARGEM_X + wg + 0.01, y - h_grupo * 0.55, sub_g, ha="left", va="center", fontsize=TAM_NOTA - 0.5,
             color=CINZA_ESCURO)
    y -= h_grupo
    for j, (hip, ver, leit, tid, fonte) in enumerate(itens):
        yc = y - h_linha / 2
        if j % 2 == 0:
            fig.add_artist(matplotlib.patches.Rectangle((MARGEM_X, y - h_linha), 1 - 2 * MARGEM_X, h_linha,
                                                        transform=fig.transFigure, fc=CINZA_FUNDO, ec="none",
                                                        zorder=0))
        destaque = ver == CONF
        fig.text(X_HIP, yc, hip, ha="left", va="center", fontsize=TAM_NOTA + 0.5, color=TEXTO,
                 fontweight="bold" if destaque else "normal")
        e = ESTILO_CHIP[ver]
        hc = h_linha * 0.66
        fig.add_artist(FancyBboxPatch((X_CHIP - W_CHIP / 2, yc - hc / 2), W_CHIP, hc,
                                      boxstyle="round,pad=0,rounding_size=0.008", transform=fig.transFigure,
                                      fc=e["fc"], ec=e["ec"], lw=1.1, zorder=2))
        fig.text(X_CHIP, yc, ver, ha="center", va="center", fontsize=TAM_NOTA - 1, color=e["cor"],
                 fontweight=e["peso"], zorder=3)
        if leit:
            lt = quebrar(fig, leit, X_ID - 0.1 - X_LEIT, TAM_NOTA - 1)
            fig.text(X_LEIT, yc, lt, ha="left", va="center", fontsize=TAM_NOTA - 1, color=CINZA_ESCURO,
                     linespacing=1.1)
        fig.text(X_ID, yc, tid, ha="right", va="center", fontsize=TAM_NOTA - 1, color=CINZA_ESCURO)
        linhas_csv.append(dict(grupo=nome_g, hipotese=hip, veredito=ver, leitura=leit, teste_etapa=tid,
                               fonte=fonte))
        y -= h_linha
    fig.add_artist(matplotlib.lines.Line2D([MARGEM_X, 1 - MARGEM_X], [y, y], color=CINZA_CLARO, lw=0.8))

dados = pd.DataFrame(linhas_csv)
contagem = dados["veredito"].value_counts()
conferir("hipóteses no placar", len(dados), 16)
conferir("CONFIRMADO no placar", int(contagem.get(CONF, 0)), 3)
salvar(fig, ID, dados)
