"""
Expansao de Dominio — Relatorio executivo
==========================================
Bloco 5: gera data/reports/expansao_dominio.md.

Compara o plano com carteira_expansao_acionavel e plano_expansao_curto_prazo
sem alterar esses artefatos.

Uso:
    python jobs/pipelines/gerar_relatorio_expansao_dominio.py
"""

from __future__ import annotations

import textwrap
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PLANO = ROOT / "data" / "outputs" / "plano_expansao_dominio.parquet"
CARTEIRA = ROOT / "data" / "outputs" / "carteira_expansao_acionavel.parquet"
PLANO_CP = ROOT / "data" / "outputs" / "plano_expansao_curto_prazo.parquet"
SAIDA = ROOT / "data" / "reports" / "expansao_dominio.md"

TOP_CIDADES = 15
TOP_CLUSTERS = 10


# =============================================================================
# Helpers
# =============================================================================

def _tese_label(tese: str) -> str:
    mapa = {
        "dominar_white_space": "Dominar white space",
        "adensar_cluster": "Adensar cluster",
        "abrir_com_disputa": "Abrir com disputa",
        "proteger_corredor_ultra": "Proteger corredor Ultra",
        "monitorar": "Monitorar",
        "bloqueado_canibalizacao": "Bloqueado (canibalizacao)",
    }
    return mapa.get(tese, tese)


def _fmt(n: float, decimais: int = 0) -> str:
    return f"{n:,.{decimais}f}".replace(",", ".")


def _pct(n: float) -> str:
    return f"{n:.1f}%"


# =============================================================================
# Secoes do relatorio
# =============================================================================

def secao_sumario(dom: pd.DataFrame) -> str:
    total_ancoras = len(dom)
    total_cidades = dom["nome_municipio"].nunique()
    total_uf = dom["uf"].nunique()
    residual_total = dom["residual_incremental_capturado"].sum()
    tese_dist = dom["tese_dominio"].value_counts()

    linhas = [
        "## Sumario executivo",
        "",
        f"- **Ancoras recomendadas:** {total_ancoras}",
        f"- **Cidades cobertas:** {total_cidades} em {total_uf} UFs",
        f"- **Residual incremental total capturado:** {_fmt(residual_total)} alunos/mes potencial",
        "",
        "**Distribuicao por tese:**",
        "",
    ]
    for tese, cnt in tese_dist.items():
        pct = cnt / total_ancoras * 100
        linhas.append(f"- {_tese_label(tese)}: {cnt} ancoras ({_pct(pct)})")

    return "\n".join(linhas)


def secao_top_cidades(dom: pd.DataFrame, n: int = TOP_CIDADES) -> str:
    agg = (
        dom.groupby(["uf", "nome_municipio"])
        .agg(
            ancoras=("hex_id", "count"),
            residual_total=("residual_incremental_capturado", "sum"),
            score_max=("score_oportunidade_residual", "max"),
            tese_principal=("tese_dominio", lambda x: x.value_counts().index[0]),
            n_clusters=("cluster_id", "nunique"),
        )
        .sort_values("residual_total", ascending=False)
        .head(n)
        .reset_index()
    )

    linhas = [
        f"## Top {n} cidades por residual capturado",
        "",
        "| # | UF | Cidade | Ancoras | Clusters | Residual capturado | Score max | Tese principal |",
        "|---|----|----|---|---|---|---|---|",
    ]
    for i, row in agg.iterrows():
        linhas.append(
            f"| {i+1} | {row['uf']} | {row['nome_municipio']} "
            f"| {int(row['ancoras'])} | {int(row['n_clusters'])} "
            f"| {_fmt(row['residual_total'])} | {_fmt(row['score_max'], 1)} "
            f"| {_tese_label(row['tese_principal'])} |"
        )

    return "\n".join(linhas)


def secao_top_clusters(dom: pd.DataFrame, n: int = TOP_CLUSTERS) -> str:
    agg = (
        dom.groupby(["uf", "nome_municipio", "cluster_id"])
        .agg(
            ancoras=("hex_id", "count"),
            residual_cluster=("residual_incremental_capturado", "sum"),
            n_hex_cluster=("n_hex_cluster", "first"),
            score_max=("score_oportunidade_residual", "max"),
            tese=("tese_dominio", lambda x: x.value_counts().index[0]),
            dist_ultra_min=("dist_ultra_mais_proxima_m", "min"),
        )
        .sort_values("residual_cluster", ascending=False)
        .head(n)
        .reset_index()
    )

    linhas = [
        f"## Top {n} clusters por residual capturado",
        "",
        "| # | UF | Cidade | Cluster | Hexes total | Ancoras | Residual cluster | Dist Ultra min (m) | Tese |",
        "|---|----|----|---|---|---|---|---|---|",
    ]
    for i, row in agg.iterrows():
        linhas.append(
            f"| {i+1} | {row['uf']} | {row['nome_municipio']} "
            f"| {row['cluster_id']} | {int(row['n_hex_cluster'])} "
            f"| {int(row['ancoras'])} | {_fmt(row['residual_cluster'])} "
            f"| {_fmt(row['dist_ultra_min'])} | {_tese_label(row['tese'])} |"
        )

    return "\n".join(linhas)


def secao_comparativo(
    dom: pd.DataFrame, carteira: pd.DataFrame, plano_cp: pd.DataFrame
) -> str:
    cidades_dom = set(dom["nome_municipio"].dropna())
    cidades_carteira = set(carteira["nome_municipio"].dropna())
    cidades_cp = set(plano_cp["nome_municipio"].dropna())

    em_carteira = cidades_dom & cidades_carteira
    em_cp = cidades_dom & cidades_cp
    novas = cidades_dom - cidades_carteira - cidades_cp

    linhas = [
        "## Comparativo com artefatos M1",
        "",
        "> Nenhum artefato M1 foi alterado. Esta secao e leitura comparativa apenas.",
        "",
        f"- Cidades no plano Expansao de Dominio: **{len(cidades_dom)}**",
        f"- Ja presentes na carteira acionavel: **{len(em_carteira)}** de {len(cidades_dom)}",
        f"- Ja presentes no plano curto prazo: **{len(em_cp)}** de {len(cidades_dom)}",
        f"- Cidades exclusivas do Dominio (nao na carteira nem no CP): **{len(novas)}**",
    ]
    if novas:
        linhas.append("")
        linhas.append("**Cidades exclusivas do Dominio:**")
        for c in sorted(novas):
            linhas.append(f"- {c}")

    return "\n".join(linhas)


def secao_detalhes_uf(dom: pd.DataFrame) -> str:
    agg = (
        dom.groupby("uf")
        .agg(
            cidades=("nome_municipio", "nunique"),
            ancoras=("hex_id", "count"),
            residual=("residual_incremental_capturado", "sum"),
        )
        .sort_values("residual", ascending=False)
        .reset_index()
    )

    linhas = [
        "## Resumo por UF",
        "",
        "| UF | Cidades | Ancoras | Residual capturado |",
        "|----|----|---|---|",
    ]
    for _, row in agg.iterrows():
        linhas.append(
            f"| {row['uf']} | {int(row['cidades'])} "
            f"| {int(row['ancoras'])} | {_fmt(row['residual'])} |"
        )

    return "\n".join(linhas)


def secao_cautelas() -> str:
    return textwrap.dedent("""\
        ## Limitacoes e cautelas

        - **Concorrentes mapeados:** apenas grandes redes nacionais (Smartfit, Bluefit, etc.);
          academias independentes, estudiosboutique e concorrentes regionais nao estao na base.
          O residual pode estar superestimado em regioes com alta densidade de independentes.
        - **Capacidade proxy:** 2.500 alunos/unidade para todos os concorrentes, independente
          de formato. Unidades menores ou maiores distorcem o calculo de oferta consumida.
        - **Populacao:** usa `pop_total_setor_2022` quando disponivel; fallback por proporcao
          municipal quando o setor censitario nao esta mapeado no hex.
        - **Score residual:** depende de `sam_fitness_potencial`, que usa penetracao de 8% sobre
          populacao adulta com renda >= R$ 4.500. Nao reflete ciclo economico atual.
        - **Distancia Ultra:** usa `dist_ultra_mais_proxima_m` da base de mercado; novos pontos
          Ultra abertos apos o ultimo snapshot nao estao refletidos.
        - **Esta feature nao substitui o M1**, a carteira acionavel nem o plano curto prazo.
          `score_priorizacao` e `hex_score_estrutural` nao foram alterados.
    """).strip()


def secao_parametros() -> str:
    return textwrap.dedent("""\
        ## Parametros utilizados

        | Parametro | Valor |
        |---|---|
        | H3 resolucao | 7 |
        | Raio de captura residual | 2,0 km |
        | Distancia minima entre novas ancoras | 1,5 km |
        | Distancia minima de Ultra existente | 1,0 km |
        | Score residual minimo (gate) | 20,0 |
        | Maximo de ancoras por cidade (default) | 10 |
        | Capacidade proxy concorrente | 2.500 alunos |
        | Cidades materializadas (--top-cidades 30) | 30 |
    """).strip()


# =============================================================================
# Funcao principal
# =============================================================================

def gerar_relatorio() -> None:
    dom = pd.read_parquet(PLANO)
    carteira = pd.read_parquet(CARTEIRA)
    plano_cp = pd.read_parquet(PLANO_CP)

    secoes = [
        "# Relatorio executivo — Expansao de Dominio Ultra Academia",
        "",
        f"**Gerado em:** {date.today().isoformat()}  ",
        "**Fonte:** `data/outputs/plano_expansao_dominio.parquet`  ",
        f"**Ancoras materializadas:** {len(dom)}  ",
        "**Ciclo:** Expansao de Dominio (paralelo ao M1 oficial)  ",
        "",
        secao_sumario(dom),
        "",
        secao_top_cidades(dom),
        "",
        secao_top_clusters(dom),
        "",
        secao_detalhes_uf(dom),
        "",
        secao_comparativo(dom, carteira, plano_cp),
        "",
        secao_parametros(),
        "",
        secao_cautelas(),
    ]

    texto = "\n".join(secoes)
    SAIDA.write_text(texto, encoding="utf-8")
    print(f"Relatorio gerado: {SAIDA} ({SAIDA.stat().st_size} bytes)")


if __name__ == "__main__":
    gerar_relatorio()
