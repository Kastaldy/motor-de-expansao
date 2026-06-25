"""Camada paralela de Demanda Revelada (H3 res-7, sem PII).

Pacote DISJUNTO (BLK-TP-01 / DEC-012): NUNCA importa de `pipelines/m1/`, `censo_*`
nem `dashboard/`; é READ-ONLY sobre o M1 e usa só deps da base (pandas/numpy/pyarrow/h3).
A demanda é insumo OBSERVADO (DEC-009), NUNCA preditor geográfico de magnitude.
"""

from __future__ import annotations

from .contrato import (
    COLUNAS_PII_PROIBIDAS,
    CONTRATO_COLUNAS,
    H3_RES_CONTRATO,
    VERSAO_CONTRATO,
)
from .ingestao import ingerir_demanda_revelada

__all__ = [
    "ingerir_demanda_revelada",
    "CONTRATO_COLUNAS",
    "COLUNAS_PII_PROIBIDAS",
    "VERSAO_CONTRATO",
    "H3_RES_CONTRATO",
]
