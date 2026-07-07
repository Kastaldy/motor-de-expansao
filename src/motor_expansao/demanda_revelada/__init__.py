"""Camada paralela de Demanda Revelada (H3 res-7, sem PII).

Pacote DISJUNTO (BLK-TP-01 / DEC-012): NUNCA importa de `pipelines/m1/`, `censo_*`
nem `dashboard/`; é READ-ONLY sobre o M1 e usa só deps da base (pandas/numpy/pyarrow/h3).
A demanda é insumo OBSERVADO (DEC-009), NUNCA preditor geográfico de magnitude.
"""

from __future__ import annotations

from .aferir_overlap_nao_abra import (
    COMPETIDORES_DEFAULT,
    DENSOS_DEFAULT,
    SMARTFIT_DEFAULT,
    VERSAO_CONTRATO_OVERLAP,
    calcular_metricas_competidores,
    calcular_metricas_smartfit,
)
from .aferir_overlap_nao_abra import (
    RELATORIO_DEFAULT as RELATORIO_OVERLAP_DEFAULT,
)
from .aferir_overlap_nao_abra import (
    executar as executar_overlap_nao_abra,
)
from .aferir_overlap_nao_abra import (
    gerar_relatorio as gerar_relatorio_overlap,
)
from .backtest_tp05 import (
    BacktestTP05Result,
    backtest_demanda_captura,
)
from .classificacao_rede_menor import (
    CONTRATO_COLUNAS_CAP_REDE,
    CONTRATO_COLUNAS_OFERTA_MENORES_REDE,
    VERSAO_CONTRATO_CAP_REDE,
    VERSAO_CONTRATO_OFERTA_MENORES_REDE,
    classificar_rede,
    gerar_capacidade_media_por_rede,
    gerar_relatorio_classificacao,
    ingerir_oferta_menores_por_rede,
)
from .concorrentes_densos import (
    CONTRATO_COLUNAS_CONCORRENTES_DENSOS,
    VERSAO_CONTRATO_CONCORRENTES_DENSOS,
    deduplicar,
    gerar_relatorio_huff_densa,
    ingerir_csvs_concorrentes,
    materializar,
    revalidar_huff_densa,
)
from .contrato import (
    COLUNAS_PII_PROIBIDAS,
    CONTRATO_COLUNAS,
    H3_RES_CONTRATO,
    VERSAO_CONTRATO,
)
from .ingestao import ingerir_demanda_revelada
from .oferta_academias_menores import (
    CONTRATO_COLUNAS_OFERTA_MENORES,
    VERSAO_CONTRATO_OFERTA_MENORES,
    gerar_relatorio_qualidade,
    ingerir_oferta_academias_menores,
)
from .validacao import executar_validacao_completa
from .vazios_competitivos import (
    CONTRATO_COLUNAS_VAZIOS,
    LIMIAR_MEMBROS_GT5KM,
    VERSAO_CONTRATO_VAZIOS,
    flag_vazio_competitivo,
    gerar_vazios_competitivos,
)

__all__ = [
    "ingerir_demanda_revelada",
    "executar_validacao_completa",
    "CONTRATO_COLUNAS",
    "COLUNAS_PII_PROIBIDAS",
    "VERSAO_CONTRATO",
    "H3_RES_CONTRATO",
    "backtest_demanda_captura",
    "BacktestTP05Result",
    # BLK-TP-03: vazios competitivos
    "flag_vazio_competitivo",
    "gerar_vazios_competitivos",
    "LIMIAR_MEMBROS_GT5KM",
    "VERSAO_CONTRATO_VAZIOS",
    "CONTRATO_COLUNAS_VAZIOS",
    # BLK-TP-08: oferta de academias menores (WellHub/TotalPass)
    "ingerir_oferta_academias_menores",
    "gerar_relatorio_qualidade",
    "CONTRATO_COLUNAS_OFERTA_MENORES",
    "VERSAO_CONTRATO_OFERTA_MENORES",
    # BLK-TP-08-FU: classificação de rede das academias menores
    "classificar_rede",
    "ingerir_oferta_menores_por_rede",
    "gerar_capacidade_media_por_rede",
    "gerar_relatorio_classificacao",
    "CONTRATO_COLUNAS_OFERTA_MENORES_REDE",
    "CONTRATO_COLUNAS_CAP_REDE",
    "VERSAO_CONTRATO_OFERTA_MENORES_REDE",
    "VERSAO_CONTRATO_CAP_REDE",
    # BLK-ATR-01-FU1: aferição de overlap base densa vs NAO_ABRA
    "calcular_metricas_smartfit",
    "calcular_metricas_competidores",
    "gerar_relatorio_overlap",
    "executar_overlap_nao_abra",
    "RELATORIO_OVERLAP_DEFAULT",
    "SMARTFIT_DEFAULT",
    "COMPETIDORES_DEFAULT",
    "DENSOS_DEFAULT",
    "VERSAO_CONTRATO_OVERLAP",
    # BLK-ATR-01: base densa de concorrentes do Huff
    "materializar",
    "ingerir_csvs_concorrentes",
    "deduplicar",
    "revalidar_huff_densa",
    "gerar_relatorio_huff_densa",
    "CONTRATO_COLUNAS_CONCORRENTES_DENSOS",
    "VERSAO_CONTRATO_CONCORRENTES_DENSOS",
]
