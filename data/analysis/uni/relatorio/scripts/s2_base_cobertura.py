"""s2_base_cobertura — uma base única: 98 unidades, 2.088 meses de faturamento, ~240 características.

Fontes: COBERTURA_UNI00.md (tabela 'cobertura por bloco'), fato_unidade_mes.parquet, dim_unidade.parquet,
docs/fontes_bases_poi.md (46.028.012 pontos) e coleta_metragem/metragem_estimada_2026-09-29.csv.
"""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _estilo import *  # noqa: E402,F403

ID = "s2_base_cobertura"
MD = (UNI / "COBERTURA_UNI00.md").read_text(encoding="utf-8")
POI_DOC = (REPO / "docs" / "fontes_bases_poi.md").read_text(encoding="utf-8")

# ------------------------------------------------------------------ números
tab = tabela_md(MD, "unidades com dado")
tab.columns = ["bloco", "unidades_com_dado", "coluna_chave"]
tab["unidades_com_dado"] = tab["unidades_com_dado"].astype(int)
tab["coluna_chave"] = tab["coluna_chave"].str.strip("`")

dim = pd.read_parquet(UNI / "dim_unidade.parquet")
rede = dim[~dim["excluida_rede"].astype(bool)]
fato = pd.read_parquet(UNI / "fato_unidade_mes.parquet")
valida = fato["faturamento"].notna() & fato["mes_completo"].astype(bool) & fato["operacao_mes_cheio"].astype(bool)
meses = int(valida.sum())
unid_fat = fato.loc[valida, "unidade_id"].nunique()
comp_min, comp_max = fato.loc[valida, "competencia"].min(), fato.loc[valida, "competencia"].max()

sat = pd.read_csv(UNI / "coleta_metragem" / "metragem_estimada_2026-09-29.csv", sep=";", encoding="utf-8-sig")
sat_princ = sat[sat["uso_no_modelo"].eq("principal")]
sem_oficial = rede.set_index("unidade_id").reindex(sat_princ["unidade_id"])["tam_metragem_m2"].isna()
n_sat = int(sem_oficial.sum())

m = re.search(r"São ([\d.]+) linhas", POI_DOC)
n_poi = int(m.group(1).replace(".", ""))

sem_m2 = rede[rede["tam_metragem_m2"].isna()]
sem_m2_2025 = int((pd.to_datetime(sem_m2["inauguracao"]).dt.year >= 2025).sum())

conferir("unidades comparáveis", len(rede), 98)
conferir("unidade-mês de receita válida", meses, 2088)
conferir("unidades com receita válida", unid_fat, 95)
conferir("primeiro mês com receita válida", int(comp_min.replace("-", "")), 202204)
conferir("último mês com receita válida", int(comp_max.replace("-", "")), 202608)
conferir("colunas do painel de atributos", dim.shape[1], 243)
conferir("pontos de interesse na base única", n_poi, 46_028_012)
conferir("linhas da tabela de cobertura", len(tab), 16)
conferir("unidades com metragem oficial", int(rede["tam_metragem_m2"].notna().sum()), 54)
conferir("metragem medida por satélite (uso principal) em unidades sem a oficial", n_sat, 19)
conferir("sem metragem oficial", len(sem_m2), 44)
conferir("sem metragem e abertas a partir de 2025", sem_m2_2025, 43)

# camada de rótulo de negócio (o nome bruto do bloco segue no CSV)
ROTULO = {
    "Isócronas (pop, renda, oferta)": "Praça a 10 min (população, renda, academias)",
    "POIs": "Pontos de interesse (comércio e serviços)",
    "Crescimento do hexágono (satélite)": "Crescimento do entorno (satélite)",
    "Lifetime: retenção EB": "Retenção de alunos em 60 dias",
    "Lifetime: prob. 90d utilizável": "Chance de cancelar em 90 dias",
    "Rampa observável": "Rampa de abertura acompanhada",
    "Patamar (estabilizou)": "Nível maduro (unidade já estabilizou)",
    "TotalPass: concorrência com ≥ 3 preços": "TotalPass: preço dos concorrentes",
    "Wellhub: concorrência com ≥ 3 preços": "Wellhub: preço dos concorrentes",
}
tab["bloco_rotulo"] = tab["bloco"].map(ROTULO).fillna(tab["bloco"])
tab["fonte_extra"] = 0
tab.loc[tab["coluna_chave"].eq("tam_metragem_m2"), "fonte_extra"] = n_sat
tab = tab.sort_values("unidades_com_dado", ascending=True).reset_index(drop=True)  # barh: maior no topo

# ------------------------------------------------------------------ figura
fig = figura()
y_topo = cabecalho(
    fig,
    "Uma base única: 98 unidades, 2.088 meses de faturamento e ~240 características por unidade",
    "Painel unidade × mês e atributos por unidade (UNI-00); unidades com dado em cada bloco, de 98",
)
y_base = rodape(
    fig,
    "Fonte: COBERTURA_UNI00.md; docs/fontes_bases_poi.md; coleta_metragem/metragem_estimada_2026-09-29.csv · "
    "N = 98 unidades",
)

# KPIs
mes_nome = {"01": "jan", "02": "fev", "03": "mar", "04": "abr", "05": "mai", "06": "jun", "07": "jul",
            "08": "ago", "09": "set", "10": "out", "11": "nov", "12": "dez"}
periodo = f"{mes_nome[comp_min[5:]]}/{comp_min[:4]}–{mes_nome[comp_max[5:]]}/{comp_max[:4]}"
kpis = [
    (num(len(rede)), "unidades comparáveis"),
    (num(meses), f"meses de faturamento fechado\n({unid_fat} unidades, {periodo})"),
    ("~240", f"características por unidade\n({dim.shape[1]} colunas no painel)"),
    (f"{num(n_poi / 1e6)} milhões", "pontos de interesse (Receita/CNPJ,\nIBGE/CNEFE, OpenStreetMap)"),
]
larg = (1 - 2 * MARGEM_X - 3 * 0.015) / 4
y_kpi = y_topo - 0.005
for i, (valor, legenda) in enumerate(kpis):
    x = MARGEM_X + i * (larg + 0.015)
    fig.add_artist(matplotlib.patches.FancyBboxPatch(
        (x, y_kpi - 0.155), larg, 0.155, boxstyle="round,pad=0,rounding_size=0.01",
        transform=fig.transFigure, fc=CINZA_FUNDO, ec="none"))
    fig.text(x + 0.014, y_kpi - 0.018, valor, ha="left", va="top", fontsize=24, fontweight="bold", color=TEXTO)
    fig.text(x + 0.014, y_kpi - 0.083, legenda, ha="left", va="top", fontsize=TAM_NOTA + 0.5,
             color=CINZA_ESCURO, linespacing=1.3)

# barras de cobertura
ax_top = y_kpi - 0.155 - 0.045
ax = fig.add_axes([0.285, y_base + 0.055, 0.37, ax_top - y_base - 0.06])
eixo_limpo(ax, grade=None)
y = np.arange(len(tab))
eh_tam = tab["coluna_chave"].eq("tam_metragem_m2").to_numpy()
cor_cinza = misturar(CINZA, 0.45)
cor_barra = np.where(eh_tam, DESTAQUE, cor_cinza)
ax.axvline(98, color=CINZA, lw=0.9, ls=(0, (3, 3)), zorder=1)
ax.text(98, len(tab) - 0.35, "98", ha="center", va="bottom", fontsize=TAM_NOTA - 0.5, color=CINZA_ESCURO)
ax.barh(y, tab["unidades_com_dado"], height=0.68, color=cor_barra, zorder=2)
i_tam = int(np.flatnonzero(eh_tam)[0])
n_of = int(tab.loc[i_tam, "unidades_com_dado"])
ax.barh(i_tam, n_sat, left=n_of, height=0.68, color=DESTAQUE_CLARO, hatch="////", edgecolor=FUNDO, lw=0,
        zorder=2)
for i, r in tab.iterrows():
    if eh_tam[i]:
        ax.text(n_of - 1.2, i, f"{n_of} oficiais", ha="right", va="center", fontsize=TAM_NOTA, color="white",
                fontweight="bold", zorder=3)
        ax.text(n_of + n_sat / 2, i, f"+{n_sat}", ha="center", va="center", fontsize=TAM_NOTA, color=TEXTO,
                fontweight="bold", zorder=3,
                bbox=dict(boxstyle="round,pad=0.12", fc=DESTAQUE_CLARO, ec="none"))
        ax.text(n_of + n_sat + 1.2, i, f"= {n_of + n_sat}", ha="left", va="center", fontsize=TAM_NOTA,
                color=DESTAQUE, fontweight="bold")
    else:
        ax.text(r["unidades_com_dado"] - 1.2, i, num(r["unidades_com_dado"]), ha="right", va="center",
                fontsize=TAM_NOTA, color=TEXTO, zorder=3)
ax.set_yticks(y)
ax.set_yticklabels(tab["bloco_rotulo"], fontsize=TAM_NOTA)
for lbl, t in zip(ax.get_yticklabels(), eh_tam):
    lbl.set_color(DESTAQUE if t else TEXTO)
    lbl.set_fontweight("bold" if t else "normal")
ax.set_xlim(0, 100)
ax.set_ylim(-0.6, len(tab) - 0.2)
ax.set_xticks([0, 25, 50, 75, 98])
ax.set_xlabel("unidades com dado (de 98)", fontsize=TAM_NOTA, color=CINZA_ESCURO)
ax.spines["left"].set_visible(False)

# legenda e nota da metragem (coluna da direita)
from matplotlib.patches import Patch  # noqa: E402

bb = ax.get_position()
x_dir = bb.x1 + 0.045
fig.legend(handles=[Patch(fc=DESTAQUE, label="metragem oficial (planilha da rede)"),
                    Patch(fc=DESTAQUE_CLARO, hatch="////", ec=FUNDO, label="metragem medida por satélite"),
                    Patch(fc=cor_cinza, label="demais blocos")],
           loc="upper left", bbox_to_anchor=(x_dir - 0.008, bb.y1 + 0.01), fontsize=TAM_NOTA, handlelength=1.4,
           labelspacing=0.7)
caixa(
    fig, x_dir, bb.y1 - 0.13, 1 - MARGEM_X - x_dir,
    f"A lacuna era a metragem: faltava em {len(sem_m2)} unidades, {sem_m2_2025} delas abertas a partir de "
    "2025, justamente as necessárias para confirmar o modelo em unidades novas.",
    tamanho=TAM_TEXTO, fundo=DESTAQUE_MUITO_CLARO, barra=DESTAQUE, titulo="O que faltava",
    cor_titulo=DESTAQUE,
)
caixa(
    fig, x_dir, bb.y1 - 0.33, 1 - MARGEM_X - x_dir,
    f"A coleta por satélite (área do telhado × andares) acrescentou {n_sat} unidades. "
    "Medida às cegas em unidades de metragem conhecida: viés de +12% (corrigido dividindo por 1,12) e "
    "erro típico de 20–25%.",
    tamanho=TAM_TEXTO, titulo="Como foi preenchido",
)

# ------------------------------------------------------------------ dados
dados = tab.sort_values("unidades_com_dado", ascending=False)[["bloco", "bloco_rotulo", "unidades_com_dado",
                                                              "fonte_extra", "coluna_chave"]]
dados = pd.concat([dados, pd.DataFrame([
    {"bloco": "KPI: unidades comparáveis", "unidades_com_dado": len(rede)},
    {"bloco": f"KPI: unidade-mês de faturamento fechado ({periodo})", "unidades_com_dado": meses},
    {"bloco": "KPI: unidades com faturamento fechado", "unidades_com_dado": unid_fat},
    {"bloco": "KPI: colunas do painel de atributos", "unidades_com_dado": dim.shape[1]},
    {"bloco": "KPI: pontos de interesse na base única", "unidades_com_dado": n_poi},
])], ignore_index=True)
salvar(fig, ID, dados)
