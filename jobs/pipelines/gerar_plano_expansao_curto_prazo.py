"""
Plano de Expansao de Curto Prazo — Ultra Academia
===================================================
Entrada : data/outputs/carteira_expansao_acionavel.parquet
Saidas  : data/outputs/plano_expansao_curto_prazo.parquet
          data/outputs/plano_expansao_curto_prazo.csv

Logica de selecao
-----------------
  Top 50 Brasil  : rank_carteira_brasil <= 50
  Top 10 por UF  : rank_carteira_uf <= 10
  Uniao deduplicada por hex_id.

nivel_prioridade_final
-----------------------
  Estrategico : rank_carteira_brasil <= 20
  Alta        : 21 <= rank_carteira_brasil <= 50
  Tatica      : top 10 UF que nao aparece no top 50 Brasil

Restricoes canonicas
---------------------
  - Nenhum score e recalculado.
  - score_priorizacao M1 nao e alterado.
  - Artefatos oficiais do M1 nao sao tocados.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
ENTRADA = ROOT / "data" / "outputs" / "carteira_expansao_acionavel.parquet"
SAIDA_PARQUET = ROOT / "data" / "outputs" / "plano_expansao_curto_prazo.parquet"
SAIDA_CSV = ROOT / "data" / "outputs" / "plano_expansao_curto_prazo.csv"

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _nivel_prioridade(row: pd.Series) -> str:
    rank_br = row["rank_carteira_brasil"]
    rank_uf = row["rank_carteira_uf"]
    if rank_br <= 20:
        return "Estrategico"
    if rank_br <= 50:
        return "Alta"
    if rank_uf <= 10:
        return "Tatica"
    return "Media"


def _motivo_enriquecido(row: pd.Series) -> str:
    """
    Gera texto curto e auditavel em 1 linha:
    #<rank_brasil> Brasil | #<rank_uf> <UF> | M1=<score_priorizacao> | Censo=<score_setor> | <qualidade_join>
    """
    rank_br = int(row["rank_carteira_brasil"])
    rank_uf = int(row["rank_carteira_uf"])
    uf = str(row.get("uf", ""))
    m1 = row.get("score_priorizacao", 0.0)
    censo = row.get("score_setor_2022_calibrado", 0.0)
    join_q = row.get("qualidade_join_uf", "?")
    modo = str(row.get("modo_selecao_carteira", "") or "")

    m1_str = "M1=max" if m1 >= 99.9 else f"M1={m1:.1f}"
    if pd.isna(censo):
        censo_str = "Censo=n/a"
    else:
        censo_str = "Censo=max" if censo >= 99.9 else f"Censo={censo:.1f}"

    outlier_flag = " [outlier explicado]" if row.get("flag_outlier_espacial", False) else ""
    baixa_pop = " [densidade < 5k hab/km2]" if row.get("flag_baixa_pop_setor", False) else ""
    modo_str = " | Fallback M1" if modo == "fallback_municipal_m1" else ""

    return (
        f"#{rank_br} Brasil | #{rank_uf} {uf} | {m1_str} | {censo_str} "
        f"| Join {join_q}{modo_str}{outlier_flag}{baixa_pop}"
    )


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def gerar_plano() -> pd.DataFrame:
    if not ENTRADA.exists():
        log.error("Carteira acionavel nao encontrada: %s", ENTRADA)
        sys.exit(1)

    log.info("Carregando carteira: %s", ENTRADA)
    df = pd.read_parquet(ENTRADA)
    log.info("  Linhas carregadas: %d | Municipios: %d | UFs: %d",
             len(df), df["cod_municipio"].nunique(), df["uf"].nunique())

    # ------------------------------------------------------------------
    # 1. Shortlist executiva: top 50 Brasil UNION top 10 por UF
    # ------------------------------------------------------------------
    mask_top50_br = df["rank_carteira_brasil"] <= 50
    mask_top10_uf = df["rank_carteira_uf"] <= 10

    plano = (
        pd.concat([df[mask_top50_br], df[mask_top10_uf]])
        .drop_duplicates(subset="hex_id")
        .copy()
    )
    log.info("Shortlist: %d hexes | %d municipios | %d UFs",
             len(plano), plano["cod_municipio"].nunique(), plano["uf"].nunique())

    # ------------------------------------------------------------------
    # 2. nivel_prioridade_final
    # ------------------------------------------------------------------
    plano["nivel_prioridade_final"] = plano.apply(_nivel_prioridade, axis=1)

    dist = plano["nivel_prioridade_final"].value_counts()
    for nivel, n in dist.items():
        log.info("  %s: %d", nivel, n)

    # ------------------------------------------------------------------
    # 3. motivo_priorizacao enriquecido
    # ------------------------------------------------------------------
    plano["motivo_priorizacao"] = plano.apply(_motivo_enriquecido, axis=1)

    # ------------------------------------------------------------------
    # 4. status_pipeline
    # ------------------------------------------------------------------
    plano["status_pipeline"] = "Novo"

    # ------------------------------------------------------------------
    # 5. Ordenacao final: nivel -> rank_carteira_brasil -> rank_carteira_uf
    # ------------------------------------------------------------------
    ordem_nivel = {"Estrategico": 0, "Alta": 1, "Tatica": 2}
    plano["_ordem"] = plano["nivel_prioridade_final"].map(ordem_nivel)
    plano = plano.sort_values(["_ordem", "rank_carteira_brasil", "rank_carteira_uf"]).drop(columns="_ordem")
    plano = plano.reset_index(drop=True)

    # ------------------------------------------------------------------
    # Validacoes
    # ------------------------------------------------------------------
    assert plano["hex_id"].nunique() == len(plano), "Duplicatas detectadas no plano."
    assert plano["nivel_prioridade_final"].notna().all(), "nivel_prioridade_final com nulos."
    assert (plano["nivel_prioridade_final"] == "Estrategico").sum() <= 20, \
        "Mais de 20 hexes Estrategicos."
    assert (plano["nivel_prioridade_final"].isin(["Estrategico", "Alta"])).sum() <= 50, \
        "Mais de 50 hexes Estrategico+Alta."
    assert (
        (plano["rank_carteira_brasil"] <= 50) | (plano["rank_carteira_uf"] <= 10)
    ).all(), "Plano contem linhas fora da uniao Top 50 Brasil + Top 10 por UF."

    log.info("Validacoes: OK")

    # ------------------------------------------------------------------
    # 6. Salvar
    # ------------------------------------------------------------------
    SAIDA_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    plano.to_parquet(SAIDA_PARQUET, index=False)
    log.info("Parquet salvo: %s", SAIDA_PARQUET)

    plano.to_csv(SAIDA_CSV, sep=";", encoding="utf-8-sig", index=False)
    log.info("CSV salvo: %s", SAIDA_CSV)

    # ------------------------------------------------------------------
    # Resumo executivo
    # ------------------------------------------------------------------
    log.info("=" * 60)
    log.info("PLANO DE EXPANSAO — CURTO PRAZO")
    log.info("  Total de oportunidades : %d hexes", len(plano))
    log.info("  Municipios cobertos    : %d", plano["cod_municipio"].nunique())
    log.info("  UFs cobertas           : %s", ", ".join(sorted(plano["uf"].unique())))
    log.info("  Estrategico (top 20)   : %d", int((plano["nivel_prioridade_final"] == "Estrategico").sum()))
    log.info("  Alta (top 21-50)       : %d", int((plano["nivel_prioridade_final"] == "Alta").sum()))
    log.info("  Tatica (top 10 UF)     : %d", int((plano["nivel_prioridade_final"] == "Tatica").sum()))
    log.info("")
    log.info("  Distribuicao por UF:")
    for uf, grp in plano.groupby("uf"):
        munis = grp["cod_municipio"].nunique()
        log.info("    %s: %d hexes / %d municipios", uf, len(grp), munis)
    log.info("=" * 60)

    return plano


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    gerar_plano()
