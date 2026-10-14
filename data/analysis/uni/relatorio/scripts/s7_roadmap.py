"""s7_roadmap — o próximo ganho de precisão vem de dado novo (quadro de próximos passos).

Fontes (cada linha do quadro é conferida contra o texto de origem):
- CADERNO_ESTUDO_UNI.md: mensagem-chave 8, etapa 10 (RJ e Wellhub), etapa 12 (avaliador independente, 6 de
  controle), etapa 13 (decisões pendentes; folha de 17% confirmada pelo dono em 30/09), 'Pendências e pedidos'
  e a recomendação de DEC Estratégica (etapa 9);
- previsao_2026/protocolo_previsao_2026.md e leitura_precoce.md (16 previsões congeladas; regra de conferência);
- alavancas/resultado_fachada_juan_parcial.md (leitura parcial do avaliador independente: 11 de 45);
- uni07/resultado_uni07.md (faixa por estado levada à decisão do dono).

Sem nomes de pessoas no gráfico.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _estilo import *  # noqa: E402,F403

ID = "s7_roadmap"
CAD = (UNI / "CADERNO_ESTUDO_UNI.md").read_text(encoding="utf-8")
PROT = (UNI / "previsao_2026" / "protocolo_previsao_2026.md").read_text(encoding="utf-8")
LP = (UNI / "previsao_2026" / "leitura_precoce.md").read_text(encoding="utf-8")
FJ = (UNI / "alavancas" / "resultado_fachada_juan_parcial.md").read_text(encoding="utf-8")
U07 = (UNI / "uni07" / "resultado_uni07.md").read_text(encoding="utf-8")

# ------------------------------------------------------------------ conferência das linhas contra as fontes
conferir("caderno: 2 decisões pendentes do dono (faixa por estado; chance como ranking)",
         int("**Decisões do Felipe pendentes:**" in CAD and "1. faixa única ou fator por estado" in CAD
             and "2. apresentar a chance de viabilidade como ranking" in CAD), 1)
conferir("UNI-07: faixa por estado levada à decisão", int("Faixa por grupo" in U07 and "estado. Levado à decisão" in U07),
         1)
conferir("avaliador independente: 45 unidades, 6 de controle", int("45 unidades que ninguém tinha avaliado, com 6 de "
                                                                   "controle" in CAD.replace("\n", " ").replace("  ", " ")), 1)
conferir("leitura parcial: 11 de 45", int("Leitura parcial: 11 de 45 unidades novas avaliadas" in FJ), 1)
conferir("turma de 2026: 16 previsões congeladas", int("(16 unidades)" in LP), 1)
conferir("conferência com ≥ 10 maduras", int("Confere-se quando houver ≥ 10 unidades maduras" in PROT), 1)
conferir("pedido: operador/franqueado anonimizado", int("**Teste do operador/franqueado** (IDs anonimizados" in CAD), 1)
conferir("pedido: preço no tempo pela API Growth, agregado",
         int("**Preço ao longo do tempo:**" in CAD and "API Growth, só" in CAD), 1)
conferir("folha de 17% confirmada pelo dono (30/09)", int("folha de 17%: é a premissa válida" in CAD), 1)
conferir("antes de uma DEC: aluguel e obra reais", int("rodar com o aluguel e a obra reais de cada unidade" in CAD), 1)
conferir("RJ passando a aceitar Wellhub (set/2026), ~6 meses",
         int("**RJ passando a aceitar Wellhub (set/2026):** reavaliar em ~6 meses" in CAD), 1)
conferir("export agregado do Lifetime (pré-venda)", int("**Export agregado do Projeto Lifetime**" in CAD
                                                        and "A confirmar com o export do Lifetime" in CAD), 1)
conferir("correções na produção em andamento", int("**Correções na produção** (Financeiro na VPS, pinos, São Carlos, "
                                                   "filtro Wellhub): em andamento" in CAD), 1)
conferir("DEC Estratégica emendando DEC-043 e DEC-009",
         int("uma DEC Estratégica que emende a DEC-043 e a DEC-009" in CAD), 1)
conferir("mensagem 8: 22 características sem explicar o erro de volume",
         int("nenhuma das 22" in CAD.replace("\n", " ").replace("   ", " ")), 1)

# ------------------------------------------------------------------ linhas do quadro
EM_ANDAMENTO = "EM ANDAMENTO"
LINHAS = [
    ("Faixas de segurança (UNI-07)", "faixa única ou por estado; chance de viável como ranking",
     "indicadores com incerteza na viabilidade", EM_ANDAMENTO, "2 decisões do dono"),
    ("Notas de fachada por avaliador independente", "~45 unidades, com 6 de controle",
     "veredito da fachada; testa 'loja de rua'", EM_ANDAMENTO, "11 de 45 avaliadas"),
    ("Turma de 2026 amadurecendo", "16 previsões congeladas em 29/09, com hash",
     "confirma estúdios, master, faixa e fachada", "AGUARDA MATURIDADE", "≥ 10 unidades maduras"),
    ("Identificador do operador/franqueado", "anonimizado",
     "separa estúdio × gestão; ataca o erro de volume", "PEDIDO", ""),
    ("Histórico de preço", "vendas da API Growth, só agregado",
     "mede quanto o preço tira de alunos", "PEDIDO", ""),
    ("Aluguel e obra reais de cada unidade", "a folha de 17% foi confirmada pelo dono em 30/09",
     "rodar a v2 de trabalho × regra atual no simulador antes de uma DEC", "PEDIDO", ""),
    ("RJ passando a aceitar Wellhub", "desde set/2026",
     "1º experimento 'não aceitava → passou a aceitar'", "REAVALIAR EM ~6 MESES", ""),
    ("Export agregado do Lifetime", "pré-venda e coorte de abertura",
     "explica a queda do mês 1", "PENDENTE", ""),
    ("Correções de dado na produção", "Financeiro, pinos, São Carlos, filtro Wellhub (PRs #418–#422)",
     "tela de produção coerente com o painel", EM_ANDAMENTO, "código na main; conferir no ar"),
    ("Revisão do dicionário de variáveis", "medidas de ponto, imóvel, fachada e operador",
     "reabre os 'nãos' com medidas melhores", "A PLANEJAR", ""),
]
n = len(LINHAS)
conferir("linhas do quadro", n, 10)
conferir("linhas EM ANDAMENTO", sum(1 for ln in LINHAS if ln[3] == EM_ANDAMENTO), 3)

# ------------------------------------------------------------------ figura
fig = figura()
y_topo = cabecalho(
    fig,
    "O próximo ganho de precisão vem de dado novo, não de mais uma variável geográfica",
    "Pedidos de dado, decisões pendentes e conferências que definem as próximas versões da viabilidade",
)
y_base = rodape(
    fig,
    "Fonte: CADERNO_ESTUDO_UNI.md (Pendências e pedidos; etapa 13); previsao_2026/protocolo_previsao_2026.md; "
    "leitura parcial do avaliador independente (29/09)",
)

L = 1 - 2 * MARGEM_X
X_NUM = MARGEM_X + 0.012
X_C1 = MARGEM_X + 0.038
X_C2 = 0.475
X_C3 = 0.815  # início da coluna de situação
X_CHIP = X_C3 + 0.005

# lead + faixa final
TXT_LEAD = ("O erro que sobra (~22%) é quase todo volume de alunos, e nenhuma das 22 características de território, "
            "concorrência ou preço o explica: só cai com dado que as bases não têm. Os 'nãos' deste estudo podem ser "
            "reabertos com medidas melhores.")
lead = quebrar(fig, TXT_LEAD, L, TAM_TEXTO)
fig.text(MARGEM_X, y_topo - 0.002, lead, ha="left", va="top", fontsize=TAM_TEXTO, color=TEXTO, linespacing=1.3)
y_tab_top = y_topo - 0.002 - altura_linhas(fig, lead.count("\n") + 1, TAM_TEXTO, 1.3) - 0.022

TXT_DEC = ("Para produção: DEC Estratégica emendando a DEC-043 e a DEC-009 "
           "(usar localização para prever demanda)")
h_band = 0.062
y_band = y_base + 0.012
fig.add_artist(matplotlib.patches.FancyBboxPatch((MARGEM_X, y_band), L, h_band,
                                                 boxstyle="round,pad=0,rounding_size=0.008",
                                                 transform=fig.transFigure, fc=DESTAQUE, ec="none"))
fig.text(MARGEM_X + 0.016, y_band + h_band / 2, TXT_DEC, ha="left", va="center", fontsize=TAM_TEXTO + 1.5,
         fontweight="bold", color="white")

# cabeçalho da tabela
y_hdr = y_tab_top
for x, t_ in ((X_C1, "dado ou decisão"), (X_C2, "o que destrava"), (X_CHIP, "situação")):
    fig.text(x, y_hdr - 0.018, t_.upper(), ha="left", va="baseline", fontsize=TAM_NOTA - 1, fontweight="bold",
             color=CINZA_ESCURO)
y_rows_top = y_hdr - 0.032
y_rows_bot = y_band + h_band + 0.02
h_row = (y_rows_top - y_rows_bot) / n
fig.add_artist(matplotlib.lines.Line2D([MARGEM_X, 1 - MARGEM_X], [y_rows_top + 0.004] * 2, color=CINZA, lw=0.9))


def chip(x, y, texto, destaque):
    """EM ANDAMENTO em âmbar de contorno (como PRELIMINAR / EM AVALIAÇÃO); azul cheio fica só para CONFIRMADO."""
    t = fig.text(x, y, texto, ha="left", va="center", fontsize=TAM_NOTA - 1, fontweight="bold",
                 color=AMBAR if destaque else TEXTO,
                 bbox=dict(boxstyle="round,pad=0.42,rounding_size=0.6", fc="white" if destaque else CINZA_CLARO,
                           ec=AMBAR if destaque else "none", lw=1.2))
    return t


linhas_csv = []
for j, (dado, detalhe, destrava, sit, sit_det) in enumerate(LINHAS):
    yt = y_rows_top - j * h_row
    yc = yt - h_row / 2
    destaque = sit == EM_ANDAMENTO
    if destaque:
        fig.add_artist(matplotlib.patches.Rectangle((MARGEM_X, yt - h_row), L, h_row, transform=fig.transFigure,
                                                    fc=misturar(AMBAR, 0.07), ec="none", zorder=0))
    fig.add_artist(matplotlib.lines.Line2D([MARGEM_X, 1 - MARGEM_X], [yt - h_row] * 2, color=CINZA_CLARO, lw=0.6))
    fig.text(X_NUM, yc, str(j + 1), ha="center", va="center", fontsize=TAM_NOTA + 0.5, fontweight="bold",
             color=AMBAR if destaque else CINZA_ESCURO)
    fig.text(X_C1, yc + 0.011, dado, ha="left", va="center", fontsize=TAM_TEXTO, fontweight="bold", color=TEXTO)
    fig.text(X_C1, yc - 0.013, detalhe, ha="left", va="center", fontsize=TAM_NOTA - 0.5, color=CINZA_ESCURO)
    txt2 = quebrar(fig, destrava, X_C3 - X_C2 - 0.02, TAM_TEXTO)
    fig.text(X_C2, yc, txt2, ha="left", va="center", fontsize=TAM_TEXTO, color=TEXTO, linespacing=1.2)
    if sit_det:
        chip(X_CHIP, yc + 0.009, sit, destaque)
        fig.text(X_CHIP, yc - 0.016, sit_det, ha="left", va="center", fontsize=TAM_NOTA - 1, color=CINZA_ESCURO)
    else:
        chip(X_CHIP, yc, sit, destaque)
    linhas_csv.append(dict(ordem=j + 1, dado_ou_decisao=dado, detalhe=detalhe, o_que_destrava=destrava,
                           situacao=sit, situacao_detalhe=sit_det, em_andamento=destaque))

linhas_csv.append(dict(ordem="final", dado_ou_decisao="Para produção: DEC Estratégica emendando a DEC-043 e a DEC-009",
                       detalhe="usar localização para prever demanda", o_que_destrava="viabilidade v2 em produção",
                       situacao="depois das conferências", situacao_detalhe="", em_andamento=False))
salvar(fig, ID, pd.DataFrame(linhas_csv))
