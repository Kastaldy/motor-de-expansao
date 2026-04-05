"""
jobs/pipelines/score_consolidado.py — Ranking final de oportunidades

Une os outputs dos módulos M1, M2 e M3 para calcular o score_abertura
e gerar o ranking consolidado de oportunidades para o time imobiliário.

Fluxo:
    hex_features (M1) + concorrentes (M2) + imoveis qualificados (M3)
    → score_area + score_competitivo + imovel_score
    → score_abertura (ranking final)
    → tabela oportunidades

Uso:
    python -m jobs.pipelines.score_consolidado
"""

from datetime import datetime
from typing import Optional

import h3
import pandas as pd
import structlog
from geopy.distance import geodesic

from api.config import settings
from jobs.pipelines.imovel_qualification import processar_lote_imoveis

log = structlog.get_logger()

# Pesos do score final de abertura
PESOS_SCORE_ABERTURA = {
    "hex_score":          0.30,
    "score_competitivo":  0.25,
    "imovel_score":       0.20,
    "alunos_est":         0.15,
    "payback_est":        0.10,   # invertido: menor payback = maior score
}


def calcular_score_competitivo(
    hex_id: str,
    df_concorrentes: pd.DataFrame,
    raio_km: float = 1.5,
) -> float:
    """
    Score competitivo (0-100) para um hexágono.

    Lógica:
    - 0 concorrentes no raio → 100 (oportunidade clara)
    - Muitos concorrentes grandes → penalidade maior
    - Academia independente próxima → oportunidade de conversão (penalidade menor)

    Pesos de penalidade por tipo de concorrente:
    - rede_grande (SmartFit, Bluefit): -20 por unidade
    - rede_media:                       -15 por unidade
    - boutique:                         -10 por unidade
    - independente:                      -5 por unidade (alvo de aquisição)
    """
    PENALIDADE = {
        "rede_grande":  20,
        "rede_media":   15,
        "boutique":     10,
        "independente":  5,
        "low_cost":     18,
    }

    lat, lng = h3.h3_to_geo(hex_id)
    penalidade_total = 0.0

    if df_concorrentes.empty:
        return 100.0

    for _, c in df_concorrentes.iterrows():
        if pd.isna(c.get("lat")) or pd.isna(c.get("lng")):
            continue
        dist = geodesic((lat, lng), (c["lat"], c["lng"])).km
        if dist <= raio_km:
            tipo = c.get("tipo", "independente")
            penalidade_total += PENALIDADE.get(tipo, 10)

    score = max(0.0, 100.0 - penalidade_total)
    return round(score, 2)


def calcular_alunos_estimados(
    hex_score: float,
    area_m2: float,
    score_competitivo: float,
    referencia_alunos: float = 800.0,
) -> float:
    """
    Estimativa simples de alunos em 12 meses.
    Placeholder até o M4 (modelos ML) estar disponível.

    Fórmula heurística baseada nas 79 unidades:
    - Unidade média Ultra: ~800 alunos em 12 meses
    - Ajustada pelo hex_score, área e pressão competitiva
    """
    fator_hex  = hex_score / 100
    fator_area = min(area_m2 / 1000, 1.5)    # área ideal ~1000m²
    fator_comp = score_competitivo / 100

    estimativa = referencia_alunos * fator_hex * fator_area * fator_comp
    return round(estimativa, 0)


def calcular_payback_estimado(
    alunos_est: float,
    preco_aluguel: float,
    capex_estimado: float = 800_000.0,
    ticket_medio: float = 117.0,
    margem_operacional: float = 0.35,
) -> float:
    """
    Estimativa de payback em meses.
    Baseado no ticket médio GOLD (R$117) e margem operacional de 35%.

    capex_estimado: R$800k como referência para academia padrão Ultra
    """
    receita_mensal = alunos_est * ticket_medio
    lucro_mensal = receita_mensal * margem_operacional - preco_aluguel

    if lucro_mensal <= 0:
        return 999.0  # Inviável financeiramente

    payback = capex_estimado / lucro_mensal
    return round(payback, 1)


def _normalizar_payback(payback: float, referencia_max: float = 36.0) -> float:
    """Converte payback (meses) em score (0-100). Menor payback = maior score."""
    if payback >= referencia_max:
        return 0.0
    return round((1 - payback / referencia_max) * 100, 2)


def calcular_score_abertura(row: pd.Series) -> float:
    """
    Score final de abertura (0-100) combinando todos os scores parciais.
    """
    hex_score        = row.get("hex_score", 50) or 50
    score_comp       = row.get("score_competitivo", 50) or 50
    imovel_score     = row.get("imovel_score", 50) or 50
    alunos_est       = row.get("alunos_est", 400) or 400
    payback_est      = row.get("payback_est", 24) or 24

    # Normalizar alunos (referência: 1000 alunos = 100 pontos)
    score_alunos = min(alunos_est / 1000 * 100, 100)

    # Normalizar payback
    score_payback = _normalizar_payback(payback_est)

    score = (
        hex_score        * PESOS_SCORE_ABERTURA["hex_score"] +
        score_comp       * PESOS_SCORE_ABERTURA["score_competitivo"] +
        imovel_score     * PESOS_SCORE_ABERTURA["imovel_score"] +
        score_alunos     * PESOS_SCORE_ABERTURA["alunos_est"] +
        score_payback    * PESOS_SCORE_ABERTURA["payback_est"]
    )
    return round(score, 2)


def gerar_ranking_oportunidades(
    df_imoveis: pd.DataFrame,
    df_hexagonos: pd.DataFrame,
    df_concorrentes: pd.DataFrame,
) -> pd.DataFrame:
    """
    Pipeline principal: une M1 + M2 + M3 e gera ranking de oportunidades.

    Args:
        df_imoveis: Output do imovel_qualification (já qualificados)
        df_hexagonos: Output do hex_enrichment (com hex_score)
        df_concorrentes: Output dos scrapers de concorrentes

    Returns:
        DataFrame rankeado por score_abertura
    """
    log.info("gerando_ranking_oportunidades")

    # Filtrar apenas imóveis qualificados
    df = df_imoveis[df_imoveis["qualificado"] == True].copy()

    if df.empty:
        log.warning("nenhum_imovel_qualificado")
        return pd.DataFrame()

    # Associar hex_id a cada imóvel (se não tiver)
    if "hex_id" not in df.columns or df["hex_id"].isna().any():
        df["hex_id"] = df.apply(
            lambda r: h3.geo_to_h3(r["lat"], r["lng"], settings.H3_RESOLUTION)
            if pd.notna(r.get("lat")) and pd.notna(r.get("lng")) else None,
            axis=1,
        )

    # Join com features dos hexágonos (M1)
    if not df_hexagonos.empty:
        cols_hex = ["hex_id", "hex_score", "renda_media", "pop_18_45", "n_concorrentes"]
        cols_hex = [c for c in cols_hex if c in df_hexagonos.columns]
        df = df.merge(df_hexagonos[cols_hex], on="hex_id", how="left")
    else:
        df["hex_score"] = 50.0  # fallback

    # Calcular score competitivo (M2)
    df["score_competitivo"] = df["hex_id"].apply(
        lambda h: calcular_score_competitivo(h, df_concorrentes)
        if h else 50.0
    )

    # Calcular estimativas (placeholder M4)
    df["alunos_est"] = df.apply(
        lambda r: calcular_alunos_estimados(
            r.get("hex_score", 50),
            r.get("area_m2", 800),
            r.get("score_competitivo", 50),
        ),
        axis=1,
    )

    df["payback_est"] = df.apply(
        lambda r: calcular_payback_estimado(
            r.get("alunos_est", 400),
            r.get("preco_aluguel", 30_000),
        ),
        axis=1,
    )

    # Score final de abertura
    df["score_abertura"] = df.apply(calcular_score_abertura, axis=1)

    # Ordenar por score
    df = df.sort_values("score_abertura", ascending=False).reset_index(drop=True)
    df["rank"] = df.index + 1

    # Colunas de saída
    colunas_output = [
        "rank", "score_abertura", "hex_score", "score_competitivo", "imovel_score",
        "titulo", "endereco", "cidade", "uf", "area_m2", "preco_aluguel",
        "alunos_est", "payback_est", "hex_id", "url", "fonte",
    ]
    colunas_presentes = [c for c in colunas_output if c in df.columns]
    df_output = df[colunas_presentes].copy()

    # Exportar ranking
    ts = datetime.now().strftime("%Y%m%d")
    output_path = f"data/reports/ranking_oportunidades_{ts}.csv"
    df_output.to_csv(output_path, sep=";", encoding="utf-8-sig", index=False)

    log.info(
        "ranking_gerado",
        total_oportunidades=len(df_output),
        top_score=df_output["score_abertura"].max() if len(df_output) else 0,
        output=output_path,
    )

    return df_output


def imprimir_top_oportunidades(df: pd.DataFrame, n: int = 10) -> None:
    """Imprime as top N oportunidades no terminal com rich formatting."""
    try:
        from rich.table import Table
        from rich.console import Console

        console = Console()
        table = Table(title=f"🏆 Top {n} Oportunidades de Expansão — Ultra Academia")

        table.add_column("Rank", style="bold cyan", width=5)
        table.add_column("Score", style="bold green", width=8)
        table.add_column("Cidade", width=15)
        table.add_column("Endereço", width=35)
        table.add_column("Área m²", width=8)
        table.add_column("Aluguel", width=12)
        table.add_column("Alunos Est.", width=12)
        table.add_column("Payback", width=10)

        for _, row in df.head(n).iterrows():
            table.add_row(
                str(row.get("rank", "-")),
                f"{row.get('score_abertura', 0):.1f}",
                str(row.get("cidade", "-")),
                str(row.get("endereco", "-"))[:35],
                f"{row.get('area_m2', 0):.0f}",
                f"R${row.get('preco_aluguel', 0)/1000:.0f}k",
                f"{row.get('alunos_est', 0):.0f}",
                f"{row.get('payback_est', 0):.0f}m",
            )

        console.print(table)
    except ImportError:
        # Fallback sem rich
        print(df.head(n).to_string())
