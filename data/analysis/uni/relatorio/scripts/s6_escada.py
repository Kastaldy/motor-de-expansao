"""s6_escada — o ganho está na demanda da praça; estúdios + master ordenam melhor com a mesma precisão.

Fontes (todas nas 18 unidades novas do UNI-02; treino nas 39 maduras de 2025):
- uni02/resultado_uni02.md (regra atual: 27% / 0,35);
- alavancas/resultado_quanto_melhora.md §2 (M0, + estado, + escritórios, + estado + escritórios) e §3 (conta do
  simulador: + preço, + agregador, + preço + agregador);
- alavancas/resultado_estudios_master_real.md (+ master real; + estúdios; + master real + estúdios = v2 de trabalho,
  IC da diferença [−9,2; +5,1]; versão com a sigla regional 20,6% / 0,73);
- uni07/resultado_uni07.md §1 (v2 23% no treino, 22% no teste; M0 22%).
"""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _estilo import *  # noqa: E402,F403
from _estilo import _cracha  # noqa: E402

ID = "s6_escada"
U02 = (UNI / "uni02" / "resultado_uni02.md").read_text(encoding="utf-8")
QM = (UNI / "alavancas" / "resultado_quanto_melhora.md").read_text(encoding="utf-8")
MR = (UNI / "alavancas" / "resultado_estudios_master_real.md").read_text(encoding="utf-8")
U07 = (UNI / "uni07" / "resultado_uni07.md").read_text(encoding="utf-8")

t02 = tabela_md(U02, "| modelo | erro típico | viés | ordenação (Spearman) |").set_index("modelo")
atual = (numero_br(t02.loc["ATUAL", "erro típico"]), numero_br(t02.loc["ATUAL", "ordenação (Spearman)"]))
t2 = tabela_md(QM, "| modelo | faturamento: erro típico | Spearman |")
t2.columns = ["modelo", "erro", "rho", "erro_alunos", "rho_alunos", "r2"]
t2 = t2.set_index("modelo")
q2 = {k: (numero_br(t2.loc[k, "erro"]), numero_br(t2.loc[k, "rho"])) for k in t2.index}
t3 = tabela_md(QM, "| cenário | erro típico | viés (mediana) | Spearman |").set_index("cenário")
q3 = {k: (numero_br(t3.loc[k, "erro típico"]), numero_br(t3.loc[k, "Spearman"])) for k in t3.index}


def mr(rotulo):
    ln = next(x for x in MR.splitlines() if x.startswith("| " + rotulo) and "| com Botafogo |" in x)
    c = [x.strip() for x in ln.strip().strip("|").split("|")]
    ords = re.findall(r"([+\-]\d\.\d+)", c[6])
    ic = [float(x) for x in re.findall(r"[+\-]\d+\.\d", c[5])]
    return dict(antes=numero_br(c[3]), depois=numero_br(c[4]), ic=ic, rho_antes=float(ords[0]),
                rho_depois=float(ords[1]))


m_master = mr("Q2: M0 → M0 + master real")
m_est = mr("M0 → M0 + estúdios (sem master)")
m_v2 = mr("**v2 candidata: M0 → M0 + master real + estúdios**")
m_sigla = mr("mesma, com a sigla regional (v1.0)")
t07 = tabela_md(U07, "| modelo | amostra | N | desvio-padrão do erro (log) |")
v2_tr = numero_br(t07[(t07["modelo"].str.startswith("v2")) & (t07["amostra"] == "treino (LOO)")]["erro típico"].iloc[0])
v2_te = numero_br(t07[(t07["modelo"].str.startswith("v2")) & (t07["amostra"].str.startswith("teste"))]["erro típico"]
                  .iloc[0])
m0_07 = numero_br(t07[(t07["modelo"].str.startswith("M0")) & (t07["amostra"] == "juntos")]["erro típico"].iloc[0])

# ------------------------------------------------------------------ linhas
BLOCOS = [
    ("PRAÇA", [
        ("Regra atual (só metragem)", atual, "atual", "uni02/resultado_uni02.md (ATUAL)"),
        ("Modelo da praça (m², renda, população)", q2["M0 (m², renda, população)"], "destaque",
         "alavancas/resultado_quanto_melhora.md §2 (M0)"),
    ]),
    ("TERRITÓRIO", [
        ("+ estado", q2["M0 + estado"], "cinza", "resultado_quanto_melhora.md §2"),
        ("+ escritórios a pé", q2["M0 + escritórios"], "cinza", "resultado_quanto_melhora.md §2"),
        ("+ estado + escritórios", q2["M0 + estado + escritórios"], "cinza", "resultado_quanto_melhora.md §2"),
    ]),
    ("OPERADOR (MODELO)", [
        ("+ master real", (m_master["depois"], m_master["rho_depois"]), "cinza",
         "resultado_estudios_master_real.md (Q2, com Botafogo)"),
        ("+ estúdios", (m_est["depois"], m_est["rho_depois"]), "cinza",
         "resultado_estudios_master_real.md (M0 + estúdios, com Botafogo)"),
        ("+ estúdios + master real = v2 de trabalho", (m_v2["depois"], m_v2["rho_depois"]), "destaque",
         "resultado_estudios_master_real.md (v2 candidata, com Botafogo)"),
    ]),
    ("CONTA DO SIMULADOR (SOBRE A PRAÇA)", [
        ("+ preço declarado (conta)", q3["v2 + preço declarado"], "cinza", "resultado_quanto_melhora.md §3"),
        ("+ agregador declarado (conta)", q3["v2 + agregador declarado"], "cinza", "resultado_quanto_melhora.md §3"),
        ("+ preço + agregador (conta)", q3["v2 + preço + agregador"], "cinza", "resultado_quanto_melhora.md §3"),
    ]),
]

# ------------------------------------------------------------------ conferência
esp = [(27, 0.35), (21.5, 0.50), (24.9, 0.36), (24.8, 0.51), (26.0, 0.35), (31.0, 0.32), (25.0, 0.73), (22.1, 0.69),
       (24.3, 0.67), (21.5, 0.56), (24.3, 0.68)]
todas = [ln for _, b in BLOCOS for ln in b]
for (rot, v, _, _), e in zip(todas, esp):
    conferir(f"{rot}: erro (%)", v[0], e[0])
    conferir(f"{rot}: ordenação", v[1], e[1])
conferir("IC da diferença v2 de trabalho − praça: inf.", m_v2["ic"][0], -9.2)
conferir("IC da diferença v2 de trabalho − praça: sup.", m_v2["ic"][1], 5.1)
conferir("sigla regional: erro (%)", m_sigla["depois"], 20.6)
conferir("sigla regional: ordenação", m_sigla["rho_depois"], 0.73)
conferir("UNI-07 v2 treino (%)", v2_tr, 23)
conferir("UNI-07 v2 teste (%)", v2_te, 22)
conferir("UNI-07 M0 juntos (%)", m0_07, 22)
conferir("M0 antes (base das comparações do .md de master)", m_v2["antes"], 21.5)

# ------------------------------------------------------------------ figura
fig = figura()
y_topo = cabecalho(
    fig,
    "O ganho está na demanda da praça; estúdios + master ordenam melhor com a mesma precisão",
    "Erro típico e ordenação do faturamento maduro nas 18 unidades novas, somando cada ajuste ao modelo da praça",
    selo="EXPLORATÓRIO",
)
y_base = rodape(
    fig,
    "Fonte: alavancas/resultado_quanto_melhora.md; uni02/resultado_uni02.md; alavancas/resultado_estudios_master_real.md; "
    "uni07/resultado_uni07.md · treino N = 39; teste N = 18 · erro típico = mediana de |real/previsto − 1|; "
    "ordenação = Spearman previsto × real",
    nota="Três nomes fixos: regra atual (só metragem) · modelo da praça (a v2 do UNI-05) · v2 de trabalho (praça + "
         "estúdios + master). Por que 27% aqui e 33% no simulador (s6_viabilidade): 27% = regra de metragem com a "
         "receita por aluno observada (UNI-02); 33% = cálculo exato do simulador de produção (R$ 115 por aluno, UNI-05).",
)

X_LAB = 0.335
X1A, X1B = 0.35, 0.55
X2A, X2B = 0.585, 0.745
X_N = 0.775
h_cab = 0.045
y_top_rows = y_topo - h_cab
y_bot_rows = y_base + 0.06
# posições (em "linhas"): cada bloco ganha 0,75 de linha para o nome
pos, y_cursor, cab_blocos = [], 0.0, []
for nome, linhas in BLOCOS:
    cab_blocos.append((nome, y_cursor))
    y_cursor += 0.8
    for _ in linhas:
        pos.append(y_cursor)
        y_cursor += 1.0
total = y_cursor - 0.4
ax1 = fig.add_axes([X1A, y_bot_rows, X1B - X1A, y_top_rows - y_bot_rows])
ax2 = fig.add_axes([X2A, y_bot_rows, X2B - X2A, y_top_rows - y_bot_rows])
for a in (ax1, ax2):
    eixo_limpo(a, grade="x")
    a.spines["left"].set_visible(False)
    a.set_facecolor("none")
    a.set_ylim(total, -0.2)
    a.set_yticks([])


def y_fig(p):
    return y_bot_rows + (y_top_rows - y_bot_rows) * (total - p) / (total + 0.2)


fig.text((X1A + X1B) / 2, y_topo - 0.012, "erro típico do faturamento", ha="center", va="top", fontsize=TAM_NOTA + 0.5,
         fontweight="bold", color=TEXTO)
fig.text((X1A + X1B) / 2, y_topo - 0.036, "menor é melhor", ha="center", va="top", fontsize=TAM_NOTA - 1,
         color=CINZA_ESCURO)
fig.text((X2A + X2B) / 2, y_topo - 0.012, "ordenação (Spearman)", ha="center", va="top", fontsize=TAM_NOTA + 0.5,
         fontweight="bold", color=TEXTO)
fig.text((X2A + X2B) / 2, y_topo - 0.036, "maior é melhor", ha="center", va="top", fontsize=TAM_NOTA - 1,
         color=CINZA_ESCURO)

COR = {"atual": CINZA_ESCURO, "destaque": DESTAQUE, "cinza": CINZA}
linhas_csv = []
k = 0
for (nome, linhas), (_, yb) in zip(BLOCOS, cab_blocos):
    yfb = y_fig(yb + 0.35)
    fig.text(MARGEM_X, yfb, nome, ha="left", va="center", fontsize=TAM_NOTA - 1, fontweight="bold",
             color=CINZA_ESCURO)
    fig.add_artist(matplotlib.lines.Line2D([MARGEM_X + largura_texto(fig, nome, TAM_NOTA - 1, "bold") + 0.008, X2B],
                                           [yfb, yfb], color=CINZA_CLARO, lw=0.8))
    for rot, (erro, rho), tipo, fonte in linhas:
        p = pos[k]
        cor = COR[tipo]
        ax1.barh(p, erro, height=0.62, color=cor, zorder=2)
        caixa_valor = dict(boxstyle="round,pad=0.12", fc="white", ec="none")
        ax1.text(erro + 0.5, p, f"{num(erro, 0 if tipo == 'atual' else 1)}%", ha="left", va="center",
                 fontsize=TAM_NOTA, color=DESTAQUE if tipo == "destaque" else TEXTO,
                 fontweight="bold" if tipo != "cinza" else "normal", zorder=5, bbox=caixa_valor)
        ax2.barh(p, rho, height=0.62, color=cor, zorder=2)
        ax2.text(rho + 0.012, p, num(rho, 2), ha="left", va="center", fontsize=TAM_NOTA,
                 color=DESTAQUE if tipo == "destaque" else TEXTO, fontweight="bold" if tipo != "cinza" else "normal",
                 zorder=5, bbox=caixa_valor)
        yf = y_fig(p)
        fig.text(X_LAB, yf, rot, ha="right", va="center", fontsize=TAM_NOTA + 0.5,
                 color=DESTAQUE if tipo == "destaque" else TEXTO,
                 fontweight="bold" if tipo != "cinza" else "normal")
        if k == 0:  # regra atual: só a referência, sem chip de confirmação
            wl = largura_texto(fig, rot, TAM_NOTA + 0.5, "bold")
            fig.text(X_LAB - wl - 0.012, yf, "REFERÊNCIA", ha="right", va="center", fontsize=7, fontweight="bold",
                     color=CINZA_ESCURO,
                     bbox=dict(boxstyle="round,pad=0.3,rounding_size=0.5", fc="white", ec=CINZA, lw=0.9))
        elif k == 1:  # chip CONFIRMADO só no modelo da praça
            wl = largura_texto(fig, rot, TAM_NOTA + 0.5, "bold")
            fig.text(X_LAB - wl - 0.012, yf, "CONFIRMADO", ha="right", va="center", fontsize=7, fontweight="bold",
                     color="white", bbox=dict(boxstyle="round,pad=0.3,rounding_size=0.5", fc=DESTAQUE, ec="none"))
        linhas_csv.append(dict(ordem=k + 1, bloco=nome.lower(), ajuste=rot, erro_tipico_pct=erro, ordenacao=rho,
                               confirmado=k == 1, papel="referência" if k == 0 else "", fonte=fonte))
        k += 1

ax1.axvline(21.5, color=DESTAQUE, lw=1.0, ls=(0, (4, 3)), zorder=3)
ax1.set_xlim(0, 36)
ax1.set_xticks([0, 10, 20, 30])
ax1.xaxis.set_major_formatter(formatador_num(0, "%"))
ax2.axvline(0.50, color=DESTAQUE, lw=1.0, ls=(0, (4, 3)), zorder=3)
ax2.set_xlim(0, 0.88)
ax2.set_xticks([0, 0.25, 0.5, 0.75])
ax2.xaxis.set_major_formatter(formatador_num(2))

# ------------------------------------------------------------------ notas à direita
W_N = 1 - MARGEM_X - X_N
y = y_topo - 0.01
y = caixa(fig, X_N, y, W_N,
          f"Diferenças de poucos pontos são ruído com 18 unidades (IC da diferença v2 de trabalho − modelo da praça: "
          f"{num(round(m_v2['ic'][0]))} a +{num(round(m_v2['ic'][1]))} pontos).", tamanho=TAM_NOTA - 0.5,
          barra=AMBAR)
y = caixa(fig, X_N, y - 0.015, W_N,
          f"No UNI-07, a v2 de trabalho erra {num(v2_tr)}% (treino) e {num(v2_te)}% (teste), igual ao modelo da praça: o ganho "
          "dela é ordenar, não precisão.", tamanho=TAM_NOTA - 0.5, fundo=DESTAQUE_MUITO_CLARO, barra=DESTAQUE)
y = caixa(fig, X_N, y - 0.015, W_N,
          "Preço e agregador entram como conta do simulador, somados ao modelo da praça: ordenam melhor, mas erram o "
          "tamanho — servem para o operador simular cenários.", tamanho=TAM_NOTA - 0.5)
caixa(fig, X_N, y - 0.015, W_N,
      f"Versão com a sigla regional no lugar da master real: {num(m_sigla['depois'], 1)}% / "
      f"{num(m_sigla['rho_depois'], 2)}.", tamanho=TAM_NOTA - 0.5)

dados = pd.DataFrame(linhas_csv)
dados["ic90_dif_v2trabalho_menos_praca_pp"] = f"[{m_v2['ic'][0]}; {m_v2['ic'][1]}]"
dados["uni07_v2_treino_teste_pct"] = f"{v2_tr} / {v2_te}"
salvar(fig, ID, dados)
