"""s2_metodo — cada ideia foi testada em dois tempos: achada em 2025, conferida em unidades nunca vistas.

Diagrama do desenho do estudo. Os números são lidos dos resultados e protocolos (UNI-01, UNI-02, UNI-03,
previsão congelada da turma de 2026) e do CADERNO_ESTUDO_UNI.md, e conferidos contra o roteiro.
"""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _estilo import *  # noqa: E402,F403
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

ID = "s2_metodo"


def ler(p):
    return (UNI / p).read_text(encoding="utf-8")


r01, r02, r03 = ler("uni01/resultado_uni01.md"), ler("uni02/resultado_uni02.md"), ler("uni03/resultado_uni03.md")
prot26 = ler("previsao_2026/protocolo_previsao_2026.md")
registro = ler("previsao_2026/REGISTRO_CONGELAMENTO.txt")
caderno = ler("CADERNO_ESTUDO_UNI.md")
r05 = ler("uni05/resultado_uni05.md")

# ------------------------------------------------------------------ números lidos
n_prim = int(re.search(r"Primária[^\n]*?\*\*(\d+) unidades\*\*", r01).group(1))
n_testes = int(tabela_md(r01, "| teste |").loc[0, "N"])
m = re.search(r"Treino: (\d+) maduras de 2025\. Teste: \*\*(\d+) unidades\*\*[^(]*\((\d+) com metragem oficial, "
              r"(\d+) por satélite\)", r02)
n_treino, n_teste, n_of, n_sat = map(int, m.groups())
m = re.search(r"Exploração \(monta a curva\): \*\*(\d+) unidades\*\*; confirmação: \*\*(\d+) unidades\*\*", r03)
n_curva, n_rampa_conf = map(int, m.groups())
prev26 = pd.read_csv(UNI / "previsao_2026" / "previsoes_turma_2026.csv", sep=";", encoding="utf-8-sig")
n_turma = len(prev26)
min_maduras = int(re.search(r"Confere-se quando houver ≥ (\d+) unidades maduras", prot26).group(1))
congelado = re.search(r"gerada em (\d{4}-\d{2}-\d{2})", registro).group(1)
n_ideias = int(re.search(r"(\d+) ideias escritas antes", caderno).group(1))
falhas = [int(x) for x in re.findall(r"achou (\d+) falhas, corrigidas|\((\d+) falhas corrigidas|\((\d+) correções\)",
                                         caderno) for x in x if x]
v11 = "v1.1 corrige" in r05
# as 4 contagens acima são, na ordem do caderno, de UNI-01, UNI-03, UNI-04 e UNI-07; a das alavancas vem à parte
m_alav = re.search(r"achou (\d+) falhas graves e (\d+) correções", caderno)
n_alav = int(m_alav.group(1)) + int(m_alav.group(2))
rev_etapas = ["UNI-01", "UNI-03", "UNI-04", "alavancas", "UNI-07"]
rev_n = falhas[:3] + [n_alav] + falhas[3:]

conferir("amostra primária do UNI-01", n_prim, 40)
conferir("unidades nos testes do UNI-01", n_testes, 39)
conferir("treino do UNI-02", n_treino, 39)
conferir("teste do UNI-02", n_teste, 18)
conferir("teste com metragem oficial", n_of, 15)
conferir("teste com metragem por satélite", n_sat, 3)
conferir("unidades da curva de rampa", n_curva, 33)
conferir("unidades de confirmação da rampa", n_rampa_conf, 22)
conferir("previsões congeladas da turma de 2026", n_turma, 16)
conferir("mínimo de unidades maduras para a conferência", min_maduras, 10)
conferir("data do congelamento (aaaammdd)", int(congelado.replace("-", "")), 20260929)
conferir("ideias escritas antes (UNI-01)", n_ideias, 19)
conferir("falhas achadas pelos revisores antes de rodar (soma)", sum(falhas), 7 + 11 + 10 + 11)
conferir("UNI-05 tem versão corrigida (v1.1) guardada ao lado da original", int(v11), 1)
conferir("alavancas: 2 graves + 10 correções", n_alav, 12)
conferir("revisão antes de rodar: etapas com contagem", len(rev_n), 5)
f_txt = ", ".join(str(f) for f in rev_n[:-1]) + " e " + str(rev_n[-1])
e_txt = ", ".join(rev_etapas[:-1]) + " e " + rev_etapas[-1]

# ------------------------------------------------------------------ figura
fig = figura()
y_topo = cabecalho(
    fig,
    "Cada ideia foi testada em dois tempos: achada em 2025, conferida em unidades que o modelo nunca viu",
    "Desenho do estudo BLK-UNI: amostras, datas e regras de conferência",
)
y_base = rodape(fig, "Fonte: CADERNO_ESTUDO_UNI.md; protocolos e REGISTRO_CONGELAMENTO.txt de UNI-01 a UNI-07")


def bloco(x, y1, w, h, etapa, titulo, corpo, destaque=False):
    fc = DESTAQUE_MUITO_CLARO if destaque else CINZA_FUNDO
    ec = DESTAQUE if destaque else "none"
    fig.add_artist(FancyBboxPatch((x, y1 - h), w, h, boxstyle="round,pad=0,rounding_size=0.01",
                                  transform=fig.transFigure, fc=fc, ec=ec, lw=1.4))
    pad = 0.011
    fig.text(x + pad, y1 - pad, etapa, ha="left", va="top", fontsize=8, fontweight="bold",
             color=DESTAQUE if destaque else CINZA_ESCURO)
    t = quebrar(fig, titulo, w - 2 * pad, TAM_TEXTO + 0.5, "bold")
    fig.text(x + pad, y1 - pad - 0.03, t, ha="left", va="top", fontsize=TAM_TEXTO + 0.5, fontweight="bold",
             color=DESTAQUE if destaque else TEXTO, linespacing=1.2)
    nt = t.count("\n") + 1
    c = quebrar(fig, corpo, w - 2 * pad, TAM_NOTA)
    fig.text(x + pad, y1 - pad - 0.03 - altura_linhas(fig, nt, TAM_TEXTO + 0.5, 1.25) - 0.008, c, ha="left",
             va="top", fontsize=TAM_NOTA, color=TEXTO, linespacing=1.3)


def seta(p0, p1, estilo="arc3", cor=CINZA_ESCURO):
    fig.add_artist(FancyArrowPatch(p0, p1, transform=fig.transFigure, arrowstyle="-|>", mutation_scale=12,
                                   color=cor, lw=1.3, connectionstyle=estilo, shrinkA=0, shrinkB=0))


# fluxo principal
gap, w = 0.032, (1 - 2 * MARGEM_X - 3 * 0.032) / 4
y1, h = y_topo - 0.005, 0.225
xs = [MARGEM_X + i * (w + gap) for i in range(4)]
bloco(xs[0], y1, w, h, "PONTO DE PARTIDA", "98 unidades comparáveis",
      "Painel unidade × mês de abr/2022 a ago/2026, com ~240 características por unidade.")
bloco(xs[1], y1, w, h, "1 · EXPLORAÇÃO (dados até dez/2025)", f"{n_testes} maduras de 2025",
      f"{n_ideias} ideias com régua escrita antes de olhar os números; só efeitos grandes aparecem.")
bloco(xs[2], y1, w, h, "2 · CONFIRMAÇÃO (jan–ago/2026)", f"{n_teste} unidades abertas em 2025",
      f"Maduras só em 2026, nunca vistas pelo modelo ({n_of} com metragem oficial, {n_sat} por satélite). "
      "É a prova que decide.", destaque=True)
bloco(xs[3], y1, w, h, "3 · PRÓXIMA CONFERÊNCIA", f"Turma de 2026: {n_turma} previsões",
      f"Congeladas com hash em 29/09/2026, antes do resultado; conferência quando ≥ {min_maduras} "
      "unidades estiverem maduras.")
for i in range(3):
    seta((xs[i] + w + 0.004, y1 - h / 2), (xs[i + 1] - 0.004, y1 - h / 2))

# ramo lateral: rampa
yr1, hr = y1 - h - 0.035, 0.085
xr, wr = xs[1], 2 * w + gap
fig.add_artist(FancyBboxPatch((xr, yr1 - hr), wr, hr, boxstyle="round,pad=0,rounding_size=0.01",
                              transform=fig.transFigure, fc=FUNDO, ec=CINZA, lw=1.0, ls=(0, (4, 3))))
fig.text(xr + 0.011, yr1 - 0.011, "RAMPA DE ABERTURA (UNI-03)", fontsize=8, fontweight="bold",
         color=CINZA_ESCURO, va="top")
fig.text(xr + 0.011, yr1 - 0.036,
         quebrar(fig, f"Curva montada com {n_curva} unidades abertas até nov/2024; conferida em {n_rampa_conf} "
                 "unidades abertas de dez/2024 a ago/2025, que não entraram nela.", wr - 0.022, TAM_NOTA),
         fontsize=TAM_NOTA, va="top", color=TEXTO, linespacing=1.3)
seta((xs[0] + w / 2, y1 - h - 0.004), (xr - 0.004, yr1 - hr / 2), estilo="angle,angleA=-90,angleB=180,rad=0")

# linha do tempo
yt0, yt1 = y_base + 0.30, yr1 - hr - 0.04
axt = fig.add_axes([MARGEM_X + 0.01, yt0, 1 - 2 * MARGEM_X - 0.02, yt1 - yt0])
axt.set_xlim(2022.0, 2027.6)
axt.set_ylim(0, 1)
for lado in ("top", "right", "left"):
    axt.spines[lado].set_visible(False)
axt.spines["bottom"].set_color(CINZA)
axt.set_yticks([])
axt.set_xticks([2022, 2023, 2024, 2025, 2026, 2027])
axt.set_xticklabels(["2022", "2023", "2024", "2025", "2026", "2027"], fontsize=TAM_NOTA)
axt.tick_params(axis="x", length=4, color=CINZA)
axt.axvspan(2022 + 3 / 12, 2026.0, color=CINZA_MUITO_CLARO, lw=0)
axt.axvspan(2026.0, 2026 + 8 / 12, color=DESTAQUE, alpha=0.18, lw=0)
axt.text(2024.1, 0.62, "dados usados para achar (abr/2022 – dez/2025)", ha="center", va="center",
         fontsize=TAM_NOTA + 0.5, color=CINZA_ESCURO, fontweight="bold")
axt.text(2026 + 4 / 12, 0.62, "guardado para\nconferir\n(jan–ago/2026)", ha="center", va="center",
         fontsize=TAM_NOTA - 0.5, color=DESTAQUE, fontweight="bold", linespacing=1.15)
x_cong = 2026 + 8.95 / 12
axt.axvline(x_cong, color=TEXTO, lw=1.2)
axt.text(x_cong + 0.04, 0.97, "29/09/2026: previsões da\nturma de 2026 congeladas", ha="left", va="top",
         fontsize=TAM_NOTA - 0.5, color=TEXTO, linespacing=1.15)
axt.annotate("", xy=(2027.55, 0.12), xytext=(x_cong, 0.12),
             arrowprops=dict(arrowstyle="-|>", color=CINZA, lw=1.1, ls=(0, (3, 2))))
axt.text(x_cong + 0.04, 0.2, f"conferência com\n≥ {min_maduras} maduras", ha="left", va="bottom",
         fontsize=TAM_NOTA - 0.5, color=CINZA_ESCURO, linespacing=1.15)

# caixa "Como protegemos o resultado" e legenda dos selos
yb = yt0 - 0.055
largura_prot = 0.49
caixa(
    fig, MARGEM_X, yb, largura_prot,
    f"• Regras congeladas com hash antes de rodar.\n"
    f"• Revisão adversarial antes de rodar nas etapas {e_txt} ({f_txt} falhas corrigidas); a confirmação "
    "principal (UNI-02) não tem revisão prévia registrada.\n"
    "• Verificação depois de rodar, que já derrubou uma conclusão (UNI-05: a versão corrigida fica guardada "
    "ao lado da original).",
    tamanho=TAM_NOTA, titulo="Como protegemos o resultado", barra=DESTAQUE,
)
x_leg = MARGEM_X + largura_prot + 0.03
fig.text(x_leg, yb - 0.004, "Selos usados no relatório", fontsize=TAM_NOTA + 0.5, fontweight="bold", va="top")
itens = [
    ("CONFIRMADO", DESTAQUE, "passou na régua em unidades novas"),
    ("EXPLORATÓRIO", AMBAR, "achado em 2025 ou após ver o dado; sem conferência"),
    ("EM AVALIAÇÃO", AMBAR, "teste com dado ainda em coleta (fachada)"),
    ("PRELIMINAR", AMBAR, "etapa em andamento, com decisões pendentes"),
    ("ILUSTRAÇÃO", AMBAR, "conta com premissas-padrão, fora do protocolo"),
    ("DESCRITIVO", AMBAR, "retrato do que já se vê, sem teste"),
]
for k, (selo, cor, desc) in enumerate(itens):
    cy = yb - 0.047 - k * 0.0305
    fig.text(x_leg + 0.004, cy, selo, ha="left", va="center", fontsize=7.5, fontweight="bold", color="white",
             bbox=dict(boxstyle="round,pad=0.3,rounding_size=0.5", fc=cor, ec="none"))
    fig.text(x_leg + 0.105, cy, desc, ha="left", va="center", fontsize=TAM_NOTA, color=TEXTO)

# ------------------------------------------------------------------ dados
dados = pd.DataFrame([
    {"etapa": "universo", "amostra": "unidades comparáveis da rede", "N": 98, "periodo": "abr/2022–ago/2026",
     "papel": "painel unidade × mês"},
    {"etapa": "UNI-01 exploração", "amostra": "maduras de 2025", "N": n_testes, "periodo": "jan–dez/2025",
     "papel": f"achar: {n_ideias} ideias com régua escrita antes (amostra primária {n_prim})"},
    {"etapa": "UNI-02 confirmação", "amostra": "abertas em 2025, maduras em 2026", "N": n_teste,
     "periodo": "jan–ago/2026", "papel": f"conferir ({n_of} metragem oficial, {n_sat} satélite)"},
    {"etapa": "UNI-03 curva de rampa", "amostra": "abertas até nov/2024", "N": n_curva, "periodo": "até nov/2024",
     "papel": "montar a curva"},
    {"etapa": "UNI-03 confirmação da rampa", "amostra": "abertas de dez/2024 a ago/2025", "N": n_rampa_conf,
     "periodo": "dez/2024–ago/2025", "papel": "conferir a curva"},
    {"etapa": "turma de 2026", "amostra": "abertas de ago/2025 em diante", "N": n_turma,
     "periodo": "congelada em 29/09/2026", "papel": f"próxima conferência (≥ {min_maduras} maduras)"},
    {"etapa": "revisão adversarial", "amostra": f"falhas corrigidas antes de rodar ({e_txt}: {f_txt})",
     "N": sum(rev_n),
     "periodo": "UNI-01, UNI-03, UNI-04, UNI-07", "papel": f_txt},
])
salvar(fig, ID, dados)
