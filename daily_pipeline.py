"""
jobs/daily_pipeline.py — Orquestrador diário do Motor de Expansão

Roda todos os dias às 3h da manhã (configurado no Prefect ou cron).
Executa na ordem:
    1. Scraping de concorrentes (M2)
    2. Scraping de imóveis (M3)
    3. Geocodificação
    4. Qualificação de imóveis
    5. Score consolidado e ranking
    6. Alertas para novas oportunidades

Uso local:
    python -m jobs.daily_pipeline --cidades "São Paulo,SP;Belo Horizonte,MG"

Uso Prefect:
    prefect deployment run daily-pipeline/prod
"""

import asyncio
import argparse
from datetime import datetime
from typing import NamedTuple

import pandas as pd
import structlog

from jobs.scrapers.base_scraper import WellhubScraper, TotalpassScraper, SmartfitScraper
from jobs.scrapers.imovel_scraper import rodar_coleta_imoveis
from jobs.pipelines.geocoding import geocodificar_lote
from jobs.pipelines.imovel_qualification import processar_lote_imoveis
from jobs.pipelines.score_consolidado import gerar_ranking_oportunidades, imprimir_top_oportunidades

log = structlog.get_logger()


class CidadeConfig(NamedTuple):
    cidade: str
    uf: str


def parse_cidades(cidades_str: str) -> list[CidadeConfig]:
    """Parse 'São Paulo,SP;Belo Horizonte,MG' → lista de CidadeConfig."""
    configs = []
    for par in cidades_str.split(";"):
        partes = par.strip().split(",")
        if len(partes) == 2:
            configs.append(CidadeConfig(cidade=partes[0].strip(), uf=partes[1].strip()))
    return configs


# ----------------------------------------------------------------
# Etapas do pipeline (podem ser decoradas com @task do Prefect)
# ----------------------------------------------------------------

async def etapa_concorrentes(cidades: list[CidadeConfig]) -> pd.DataFrame:
    """Coleta e consolida concorrentes de todas as cidades."""
    log.info("etapa_concorrentes_iniciada", total_cidades=len(cidades))
    todos = []

    scrapers_classe = [WellhubScraper, TotalpassScraper, SmartfitScraper]

    for cfg in cidades:
        for ScraperClasse in scrapers_classe:
            scraper = ScraperClasse()
            try:
                resultados = await scraper.rodar(cidade=cfg.cidade, uf=cfg.uf)
                todos.extend(resultados)
            except Exception as e:
                log.error("etapa_concorrentes_erro",
                          scraper=ScraperClasse.NOME, cidade=cfg.cidade, erro=str(e))

    if not todos:
        return pd.DataFrame()

    df = pd.DataFrame(todos)

    # Geocodificar concorrentes sem coordenadas
    registros = geocodificar_lote(df.to_dict("records"))
    df = pd.DataFrame(registros)

    # Deduplicar por nome + cidade
    df = df.drop_duplicates(subset=["nome", "cidade"], keep="first")

    log.info("etapa_concorrentes_concluida", total=len(df))
    return df


async def etapa_imoveis(cidades: list[CidadeConfig]) -> pd.DataFrame:
    """Coleta imóveis de todas as cidades."""
    log.info("etapa_imoveis_iniciada", total_cidades=len(cidades))
    dfs = []

    for cfg in cidades:
        try:
            df = await rodar_coleta_imoveis(cfg.cidade, cfg.uf)
            if not df.empty:
                dfs.append(df)
        except Exception as e:
            log.error("etapa_imoveis_erro", cidade=cfg.cidade, erro=str(e))

    if not dfs:
        return pd.DataFrame()

    df_total = pd.concat(dfs, ignore_index=True)

    # Geocodificar imóveis sem coordenadas
    registros = geocodificar_lote(df_total.to_dict("records"), usar_google=True)
    df_total = pd.DataFrame(registros)

    log.info("etapa_imoveis_concluida", total=len(df_total))
    return df_total


def etapa_qualificacao(df_imoveis: pd.DataFrame) -> pd.DataFrame:
    """Aplica filtros de elegibilidade."""
    log.info("etapa_qualificacao_iniciada", total_entrada=len(df_imoveis))
    if df_imoveis.empty:
        return df_imoveis
    df = processar_lote_imoveis(df_imoveis)
    qualificados = df["qualificado"].sum()
    log.info("etapa_qualificacao_concluida",
             qualificados=int(qualificados), descartados=int(len(df) - qualificados))
    return df


def etapa_ranking(
    df_imoveis: pd.DataFrame,
    df_concorrentes: pd.DataFrame,
) -> pd.DataFrame:
    """Gera ranking consolidado de oportunidades."""
    log.info("etapa_ranking_iniciada")

    # Carregar hexágonos do banco ou do staging
    # TODO: Substituir por query ao banco em produção
    df_hexagonos = pd.DataFrame()  # Placeholder

    df_ranking = gerar_ranking_oportunidades(df_imoveis, df_hexagonos, df_concorrentes)
    log.info("etapa_ranking_concluida", total_oportunidades=len(df_ranking))
    return df_ranking


def etapa_alertas(df_ranking: pd.DataFrame, min_score: float = 60.0) -> None:
    """Envia alertas para novas oportunidades acima do threshold de score."""
    if df_ranking.empty:
        return

    novas = df_ranking[df_ranking["score_abertura"] >= min_score]
    if novas.empty:
        log.info("nenhuma_oportunidade_acima_threshold", threshold=min_score)
        return

    log.info("alertas_novas_oportunidades", total=len(novas), min_score=min_score)

    # TODO: Integrar com Slack/Teams/email
    # _enviar_slack(novas)
    # _enviar_email(novas)

    imprimir_top_oportunidades(df_ranking, n=5)


# ----------------------------------------------------------------
# Pipeline principal
# ----------------------------------------------------------------

async def rodar_pipeline_diario(cidades: list[CidadeConfig]) -> dict:
    """
    Executa o pipeline completo e retorna métricas de execução.
    """
    inicio = datetime.now()
    log.info("pipeline_diario_iniciado", cidades=[f"{c.cidade}/{c.uf}" for c in cidades])

    metricas = {
        "iniciado_em": inicio.isoformat(),
        "cidades": len(cidades),
        "concorrentes_coletados": 0,
        "imoveis_coletados": 0,
        "imoveis_qualificados": 0,
        "oportunidades_geradas": 0,
        "status": "running",
    }

    try:
        # 1. Concorrentes
        df_concorrentes = await etapa_concorrentes(cidades)
        metricas["concorrentes_coletados"] = len(df_concorrentes)

        # 2. Imóveis
        df_imoveis_bruto = await etapa_imoveis(cidades)
        metricas["imoveis_coletados"] = len(df_imoveis_bruto)

        # 3. Qualificação
        df_imoveis = etapa_qualificacao(df_imoveis_bruto)
        metricas["imoveis_qualificados"] = int(df_imoveis["qualificado"].sum()) if not df_imoveis.empty else 0

        # 4. Ranking
        df_ranking = etapa_ranking(df_imoveis, df_concorrentes)
        metricas["oportunidades_geradas"] = len(df_ranking)

        # 5. Alertas
        etapa_alertas(df_ranking)

        metricas["status"] = "success"

    except Exception as e:
        log.error("pipeline_diario_falhou", erro=str(e))
        metricas["status"] = "failed"
        metricas["erro"] = str(e)
        raise

    finally:
        fim = datetime.now()
        metricas["duracao_s"] = (fim - inicio).total_seconds()
        metricas["finalizado_em"] = fim.isoformat()

        log.info("pipeline_diario_finalizado", **metricas)

    return metricas


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline diário do Motor de Expansão")
    parser.add_argument(
        "--cidades",
        default="São Paulo,SP;Belo Horizonte,MG;Goiânia,GO",
        help="Cidades no formato 'Cidade1,UF1;Cidade2,UF2'",
    )
    args = parser.parse_args()

    cidades = parse_cidades(args.cidades)
    if not cidades:
        print("❌ Nenhuma cidade válida fornecida. Use: --cidades 'São Paulo,SP;Campinas,SP'")
        exit(1)

    asyncio.run(rodar_pipeline_diario(cidades))
