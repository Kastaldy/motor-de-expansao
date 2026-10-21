"""Recomendacao unica: Top 10 = 5 Mata Virgem + 5 Premium por hexagono H3 res-7 (DEC-077).

A regua (os numeros) e versionada em `regra/<PAIS>/<versao>.json` + `VIGENTE`, no molde dos
fatores da renda; o nucleo (`nucleo.py`) e puro; `montar_recomendacao` e a unica orquestracao
que as superficies chamam. Camada paralela READ-ONLY sobre o M1: nao le nem altera
`score_priorizacao`, carteira, plano ou artefato oficial.

Importar o pacote nao le regua, staging nem perfil -- a carga e preguicosa (`carregar_regra`
com cache).
"""

from __future__ import annotations

from motor_expansao.recomendacao.carregador import (
    ENV_VERSAO,
    Regra,
    RegraRecomendacaoInvalida,
    ReguaMataVirgem,
    ReguaPremium,
    carregar_regra,
    limpar_cache,
)
from motor_expansao.recomendacao.montar import montar_recomendacao
from motor_expansao.recomendacao.nomes import bairros_ordenados_por_hex, rotulos_das_regioes
from motor_expansao.recomendacao.nucleo import (
    CHAVES_SEM_DADO,
    COLUNAS_OBRIGATORIAS,
    ROTULO_MOTIVO,
    ROTULO_SEGMENTO,
    ROTULO_SEM_DADO,
    ROTULO_STATUS,
    SEGMENTOS,
    ItemRecomendado,
    ProcedenciaRenda,
    Recomendacao,
    Recorte,
    ResultadoSegmento,
    VagaVazia,
    candidatos_ordenados,
    classificar,
    recomendar,
)
from motor_expansao.recomendacao.subida import validar_na_subida

__all__ = [
    "CHAVES_SEM_DADO",
    "COLUNAS_OBRIGATORIAS",
    "ENV_VERSAO",
    "ROTULO_MOTIVO",
    "ROTULO_SEGMENTO",
    "ROTULO_SEM_DADO",
    "ROTULO_STATUS",
    "SEGMENTOS",
    "ItemRecomendado",
    "ProcedenciaRenda",
    "Recomendacao",
    "Recorte",
    "Regra",
    "RegraRecomendacaoInvalida",
    "ReguaMataVirgem",
    "ReguaPremium",
    "ResultadoSegmento",
    "VagaVazia",
    "bairros_ordenados_por_hex",
    "candidatos_ordenados",
    "carregar_regra",
    "classificar",
    "limpar_cache",
    "montar_recomendacao",
    "recomendar",
    "rotulos_das_regioes",
    "validar_na_subida",
]
