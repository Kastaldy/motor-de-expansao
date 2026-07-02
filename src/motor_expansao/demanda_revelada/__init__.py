"""Camada paralela de Demanda Revelada (H3 res-7, sem PII).

Pacote DISJUNTO (BLK-TP-01 / DEC-012): NUNCA importa de `pipelines/m1/`, `censo_*`
nem `dashboard/`; é READ-ONLY sobre o M1 e usa só deps da base (pandas/numpy/pyarrow/h3).
A demanda é insumo OBSERVADO (DEC-009), NUNCA preditor geográfico de magnitude.
"""

from __future__ import annotations

from .backtest_tp05 import (
    BacktestTP05Result,
    backtest_demanda_captura,
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
]
