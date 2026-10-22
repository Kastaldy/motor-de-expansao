"""Orquestracao da recomendacao unica: a UNICA porta que web, API e bot vao chamar (Fase 4).

Junta o que o nucleo puro nao pode ler sozinho: a regua vigente (`carregar_regra`), o carimbo
k da malha (`renda.hex.k_da_malha`) e a renda domiciliar do card, calculada pelo dono da conta
(`renda.hex.renda_domiciliar_por_linha`) -- nunca aqui. Nao le arquivo nenhum alem do carimbo k
e dos insumos que o pacote da renda ja le (uplift/moradores municipais e fatores versionados).

Sem o carimbo k o Top 10 INTEIRO fica indisponivel (decisao do GATE 2): uma lista ordenada por
renda calculada com o k errado (o fallback 1,0239, ou o k do staging hex) erraria a escala em
~20% sem nenhuma pista na tela -- melhor nao recomendar do que recomendar com a renda de outro
numero.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from motor_expansao.recomendacao.carregador import Regra, carregar_regra
from motor_expansao.recomendacao.nucleo import (
    COL_RENDA,
    COL_RENDA_ORIGEM,
    COLUNAS_OBRIGATORIAS,
    COLUNAS_REPASSADAS,
    ProcedenciaRenda,
    Recomendacao,
    Recorte,
    linhas_que_precisam_de_renda,
    recomendar,
    validar_colunas,
)
from motor_expansao.renda.carregador import carregar_fatores
from motor_expansao.renda.hex import (
    COLS_RENDA_LEITURA,
    k_da_malha,
    renda_domiciliar_por_linha,
    serie_renda,
)

_LOG = logging.getLogger("motor_expansao.recomendacao")

#: Colunas que a renda do card le de CADA linha (alem das obrigatorias do nucleo): UF e
#: municipio (fator e uplift/moradores) e as DUAS colunas de leitura da renda (`serie_renda`).
#: Todas obrigatorias: o artefato BR sempre as traz, e um frame PROJETADO sem elas (a web
#: projeta colunas por rota -- familia DEC-038) daria renda NaN em toda linha, Mata Virgem
#: vazio e o rotulo FALSO "nao ha outra regiao", sem erro nenhum.
COLUNAS_RENDA_POR_LINHA: tuple[str, ...] = ("uf", "cod_municipio", *COLS_RENDA_LEITURA)


def montar_recomendacao(
    df_recorte: pd.DataFrame,
    *,
    recorte: Recorte,
    staging_dir: Path | str | None = None,
    regra: Regra | None = None,
) -> Recomendacao | None:
    """Top 10 do recorte ja selecionado (`df_recorte` = linhas da particao enriquecida).

    - `regra` None -> a vigente do pais; pais SEM regua -> devolve `None` (a superficie segue o
      comportamento legado, sem recomendacao).
    - Sem o carimbo k da malha -> `Recomendacao` com os dois segmentos `indisponivel`.
    - Com k -> renda domiciliar do card SO nas linhas em que ela decide alguma coisa
      (`linhas_que_precisam_de_renda`), com a origem de cada valor (`serie_renda`), e o nucleo.

    `staging_dir` aponta o carimbo k e o artefato da malha (as colunas da E3, quando o frame nao
    as traz); uplift e moradores saem de onde o pacote da renda ja le
    (`renda.insumos.staging_dir()`). A entrada nao e alterada.
    """
    if regra is None:
        regra = carregar_regra()
        if regra is None:
            return None
    # Fail-closed ANTES de qualquer leitura: coluna faltando e erro de quem chama, nao "sem k".
    validar_colunas(df_recorte, renda_disponivel=False)
    # A renda do card e por municipio (uplift/moradores) e por UF (excecao de fator, PE/MS na
    # PNAD 2025). Sem a COLUNA `uf` a conta cairia em silencio no fator nacional nessas UFs --
    # e a particao lida direto do arquivo nao traz `uf` (e chave de particao hive). Sem as
    # colunas de leitura, a renda sumiria (ou viraria toda municipal) em silencio.
    faltando = [c for c in COLUNAS_RENDA_POR_LINHA if c not in df_recorte.columns]
    if faltando:
        raise ValueError(
            f"recomendacao: coluna(s) obrigatoria(s) ausente(s): {', '.join(faltando)} "
            "(a renda do card le UF, municipio e as colunas de renda de cada linha)"
        )

    k = k_da_malha(staging_dir)
    if k is None:
        _LOG.warning(
            "recomendacao (%s, regua %s): sem o carimbo k da malha -- Top 10 indisponivel",
            regra.pais,
            regra.versao,
        )
        return recomendar(df_recorte, regra, renda=None, recorte=recorte)

    fatores = carregar_fatores()
    n = len(df_recorte)
    renda = np.full(n, np.nan, dtype="float64")
    origem = np.array([None] * n, dtype=object)
    precisa = linhas_que_precisam_de_renda(df_recorte, regra).to_numpy(dtype=bool)
    if precisa.any():
        # Por POSICAO, nao por rotulo: o indice do recorte pode vir repetido de um concat.
        posicoes = np.flatnonzero(precisa)
        sub = df_recorte.iloc[posicoes]
        renda[posicoes] = renda_domiciliar_por_linha(
            sub, k=k.valor, staging_dir=staging_dir
        ).to_numpy(dtype="float64")
        _valor, origem_sub = serie_renda(sub)
        origem[posicoes] = origem_sub.to_numpy(dtype=object)

    # So as colunas que o nucleo le: o `assign` sobre o frame largo do Brasil (88 colunas)
    # copiava ~1 GB a cada chamada.
    usadas = [c for c in df_recorte.columns if c in (*COLUNAS_OBRIGATORIAS, *COLUNAS_REPASSADAS)]
    hexes = df_recorte[usadas].assign(**{COL_RENDA: renda, COL_RENDA_ORIGEM: origem})
    procedencia = ProcedenciaRenda(
        k=k.valor,
        carimbo=k.carimbo,
        fatores_versao=fatores.versao,
        pais=fatores.pais,
    )
    return recomendar(hexes, regra, renda=procedencia, recorte=recorte)
