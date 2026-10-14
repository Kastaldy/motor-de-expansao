"""s3_alerta_mes3 — no 3º mês, a projeção dos alunos maduros erra 5–9%, contra ~22% antes de abrir.

Fonte: uni03/resultado_uni03.md (P3: faixa p10–p90 da exploração, erro típico na exploração e na confirmação,
cobertura nos meses 1/3/6; linha 'Antes de abrir × mês 3', 13 unidades da confirmação com metragem).
"""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _estilo import *  # noqa: E402,F403

ID = "s3_alerta_mes3"
MD = (UNI / "uni03" / "resultado_uni03.md").read_text(encoding="utf-8")

# ------------------------------------------------------------------ leitura
p3 = tabela_md(MD, "| mês | faixa de erro p10–p90")
p3.columns = ["mes", "faixa", "erro_expl", "erro_conf", "cobertura", "compativel"]
p3["mes"] = p3["mes"].astype(int)
fx = p3["faixa"].str.extract(r"(\S+)% a (\S+)%")
p3["faixa_p10_pct"] = fx[0].map(numero_br)
p3["faixa_p90_pct"] = fx[1].map(numero_br)
p3["erro_tipico_exploracao_pct"] = p3["erro_expl"].map(numero_br)
p3["erro_tipico_confirmacao_pct"] = p3["erro_conf"].map(numero_br)
cob = p3["cobertura"].str.extract(r"(\d+)% \((\d+) unid\.\)")
p3["cobertura_confirmacao_pct"] = cob[0].astype(int)
p3["n_confirmacao"] = cob[1].astype(int)
p3 = p3.set_index("mes")
faixa_ok = re.search(r"compatível \((\d+)–(\d+)%\)", MD).groups()
m = re.search(r"\*\*Antes de abrir × mês 3\*\* \((\d+) unidades da confirmação com metragem\): erro típico da "
              r"projeção pela metragem.*?\) = (\d+)%; pelo mês 3 = (\d+)%", MD)
n_esq, antes, mes3 = map(int, m.groups())

# ------------------------------------------------------------------ conferência
conferir("unidades do painel esquerdo", n_esq, 13)
conferir("erro antes de abrir, pela metragem (%)", antes, 22)
conferir("erro pelo mês 3 (painel esquerdo, %)", mes3, 5)
for k, (e_c, e_e, lo, hi, c) in {1: (21, 17, -24, 36, 59), 3: (9, 11, -20, 23, 77), 6: (9, 8, -13, 11, 64)}.items():
    r = p3.loc[k]
    conferir(f"mês {k}: erro típico na confirmação (%)", r["erro_tipico_confirmacao_pct"], e_c)
    conferir(f"mês {k}: erro típico na exploração (%)", r["erro_tipico_exploracao_pct"], e_e)
    conferir(f"mês {k}: faixa p10 (%)", r["faixa_p10_pct"], lo)
    conferir(f"mês {k}: faixa p90 (%)", r["faixa_p90_pct"], hi)
    conferir(f"mês {k}: cobertura na confirmação (%)", r["cobertura_confirmacao_pct"], c)
    conferir(f"mês {k}: unidades na confirmação", r["n_confirmacao"], 22)
conferir("faixa de cobertura compatível, mínimo (%)", int(faixa_ok[0]), 57)
conferir("faixa de cobertura compatível, máximo (%)", int(faixa_ok[1]), 93)

# ------------------------------------------------------------------ figura
fig = figura()
y_topo = cabecalho(
    fig,
    "No 3º mês, a projeção dos alunos maduros erra 5–9%, contra ~22% antes de abrir",
    "Erro típico ao projetar o nível maduro de alunos antes de abrir e a partir dos meses 1, 3 e 6",
    chip="CONFIRMADO",
)
y_base = rodape(
    fig,
    f"Fonte: uni03/resultado_uni03.md (P3) · N = {n_esq} (painel esquerdo) e 22 (painel direito), unidades abertas "
    "dez/2024–ago/2025 · erro típico = mediana de |real/projetado − 1| do nível maduro",
)
# notas embaixo
w_nota = (1 - 2 * MARGEM_X - 0.02) / 2
y_notas = y_base + 0.098
c3 = p3.loc[3]
yb1 = caixa(fig, MARGEM_X, y_notas, w_nota,
            f"Faixa do mês 3: o maduro fica entre {pct(c3['faixa_p10_pct'])} e {pct(c3['faixa_p90_pct'], sinal=True)} "
            f"da projeção; cobriu {c3['cobertura_confirmacao_pct']}% das unidades novas, dentro do esperado "
            f"({faixa_ok[0]}–{faixa_ok[1]}% para 22 unidades).",
            tamanho=TAM_NOTA + 0.5, fundo=DESTAQUE_MUITO_CLARO, barra=DESTAQUE)
yb2 = caixa(fig, MARGEM_X + w_nota + 0.02, y_notas, w_nota,
            "É outra grandeza (alunos, depois de abrir): complementa, não substitui, a previsão de faturamento "
            "da praça.", tamanho=TAM_NOTA + 0.5)
y0 = min(yb1, yb2) + 0.0  # só para referência
y_pain0 = y_notas + 0.095
y_pain1 = y_topo - 0.1

# ---------------- painel esquerdo
axL = fig.add_axes([0.075, y_pain0, 0.3, y_pain1 - y_pain0])
eixo_limpo(axL, grade="y")
fig.text(0.075, y_pain1 + 0.062, f"Mesmas {n_esq} unidades: antes de abrir × 3º mês", ha="left", va="bottom",
         fontsize=TAM_TEXTO + 1, fontweight="bold")
fig.text(0.075, y_pain1 + 0.058, "erro típico da projeção do nível maduro de alunos", ha="left", va="top",
         fontsize=TAM_NOTA - 0.5, color=CINZA_ESCURO)
barrasL = [("antes de abrir\n(pela metragem, a regra\nda viabilidade de hoje)", antes, CINZA_ESCURO),
           ("no 3º mês\n(pelos alunos do mês 3)", mes3, DESTAQUE)]
for i, (rot, v, cor) in enumerate(barrasL):
    axL.bar(i, v, width=0.58, color=cor, zorder=2)
    axL.text(i, v + 0.6, pct(v), ha="center", va="bottom", fontsize=TAM_TITULO + 2, fontweight="bold",
             color=cor if cor == DESTAQUE else TEXTO)
axL.set_xticks([0, 1])
axL.set_xticklabels([b[0] for b in barrasL], fontsize=TAM_NOTA, color=TEXTO, linespacing=1.15)
axL.set_xlim(-0.55, 1.55)
axL.set_ylim(0, 27)
axL.set_yticks([0, 5, 10, 15, 20, 25])
axL.yaxis.set_major_formatter(formatador_num(0, "%"))

# ---------------- painel direito: dois eixos — erro típico (tamanho, sem sinal) e faixa p10–p90 (com sinal)
xR = 0.47
fig.text(xR, y_pain1 + 0.062, "22 unidades de confirmação: projetando a partir do mês 1, 3 ou 6", ha="left",
         va="bottom", fontsize=TAM_TEXTO + 1, fontweight="bold")
fig.text(xR, y_pain1 + 0.058, "à esquerda, o tamanho típico do erro (sem sinal); à direita, a faixa normal do erro "
         "(com sinal)", ha="left", va="top", fontsize=TAM_NOTA - 0.5, color=CINZA_ESCURO)
meses = [1, 3, 6]
rot_meses = [f"pelo\nmês {k}" for k in meses]
xR1a, xR1b = xR + 0.035, 0.675
xR2a, xR2b = 0.755, 1 - MARGEM_X - 0.01
axR1 = fig.add_axes([xR1a, y_pain0, xR1b - xR1a, y_pain1 - y_pain0 - 0.04])
axR2 = fig.add_axes([xR2a, y_pain0, xR2b - xR2a, y_pain1 - y_pain0 - 0.04])
for a in (axR1, axR2):
    eixo_limpo(a, grade="y")
fig.text((xR1a + xR1b) / 2, y_pain1 - 0.012, "erro típico na confirmação", ha="center", va="top",
         fontsize=TAM_NOTA, fontweight="bold", color=TEXTO)
fig.text((xR2a + xR2b) / 2, y_pain1 - 0.012, "faixa normal do erro (p10–p90)", ha="center", va="top",
         fontsize=TAM_NOTA, fontweight="bold", color=TEXTO)
_expl = [pct(p3.loc[k, "erro_tipico_exploracao_pct"]) for k in (1, 3, 6)]
fig.text((xR1a + xR1b) / 2, y_pain1 - 0.037, f"(na exploração: {_expl[0]}, {_expl[1]} e {_expl[2]})",
         ha="center", va="top", fontsize=TAM_NOTA - 1, color=CINZA_ESCURO)
fig.text((xR2a + xR2b) / 2, y_pain1 - 0.037, "(com sinal; medida na exploração)", ha="center", va="top",
         fontsize=TAM_NOTA - 1, color=CINZA_ESCURO)
for i, k in enumerate(meses):
    r = p3.loc[k]
    cor = DESTAQUE if k == 3 else CINZA
    v = r["erro_tipico_confirmacao_pct"]
    axR1.bar(i, v, width=0.58, color=cor, zorder=2)
    axR1.text(i, v + 0.6, pct(v), ha="center", va="bottom", fontsize=TAM_TEXTO + 2, fontweight="bold",
              color=DESTAQUE if k == 3 else TEXTO)
    lo, hi = r["faixa_p10_pct"], r["faixa_p90_pct"]
    cor_s = DESTAQUE if k == 3 else CINZA_ESCURO
    axR2.plot([i, i], [lo, hi], color=cor_s, lw=2.4, zorder=3, solid_capstyle="butt")
    for yy in (lo, hi):
        axR2.plot([i - 0.12, i + 0.12], [yy, yy], color=cor_s, lw=1.6, zorder=3)
    axR2.text(i + 0.16, hi, pct(hi, sinal=True), ha="left", va="center", fontsize=TAM_NOTA - 0.5, color=cor_s)
    axR2.text(i + 0.16, lo, pct(lo), ha="left", va="center", fontsize=TAM_NOTA - 0.5, color=cor_s)
    axR2.text(i, -31, f"cobre\n{r['cobertura_confirmacao_pct']}%", ha="center", va="top", fontsize=TAM_NOTA - 1,
              color=cor_s, linespacing=1.1, fontweight="bold" if k == 3 else "normal")
axR1.set_ylim(0, 27)
axR1.set_yticks([0, 5, 10, 15, 20, 25])
axR1.yaxis.set_major_formatter(formatador_num(0, "%"))
axR2.axhline(0, color=TEXTO, lw=0.9, zorder=2)
axR2.set_ylim(-40, 40)
axR2.set_yticks([-30, -20, -10, 0, 10, 20, 30, 40])
axR2.yaxis.set_major_formatter(formatador_num(0, "%", sinal=True))
for a in (axR1, axR2):
    a.set_xticks(range(len(meses)))
    a.set_xticklabels(rot_meses, fontsize=TAM_NOTA, color=TEXTO, linespacing=1.1)
    a.set_xlim(-0.6, 2.75)
fig.text(xR2b, y_pain0 - 0.075, "cobre = % das unidades novas dentro da faixa (esperado 57–93%)", ha="right",
         va="top", fontsize=TAM_NOTA - 1.5, color=CINZA_ESCURO)

# ------------------------------------------------------------------ dados
dados = p3[["faixa_p10_pct", "faixa_p90_pct", "erro_tipico_exploracao_pct", "erro_tipico_confirmacao_pct",
            "cobertura_confirmacao_pct", "n_confirmacao"]].reset_index().rename(columns={"mes": "mes_projecao"})
dados.insert(0, "painel", "direito")
esq = pd.DataFrame([
    {"painel": "esquerdo", "mes_projecao": "antes de abrir (metragem)", "erro_tipico_confirmacao_pct": antes,
     "n_confirmacao": n_esq},
    {"painel": "esquerdo", "mes_projecao": 3, "erro_tipico_confirmacao_pct": mes3, "n_confirmacao": n_esq},
])
dados = pd.concat([esq, dados], ignore_index=True)
dados["cobertura_esperada_pct"] = 80
salvar(fig, ID, dados)
