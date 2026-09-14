"""Fonte unica de verdade da regua operacional de populacao do corte (pop_cut).

Helpers PUROS (sem I/O) compartilhados entre o dashboard (`dashboard/data.py`) e o
pipeline de mercado (`calcular_colunas_mercado.py`). A logica e identica a que vivia
em `dashboard/data.py`; foi extraida para um modulo NEUTRO de pipeline para garantir
que o gate do SAM e a regua do dashboard nunca divirjam, sem criar dependencia
arquitetural invertida (pipeline -> dashboard).

Definicao canonica de `granular` (NAO e `flag_censo_elegivel` nem `mask_hex_censo`):
(`qualidade_join_uf in {A,B}` OU `classe_join_municipio in {A,B}`)
AND (`flag_censo_disponivel` OR `score_setor_2022_calibrado` notna).

A segunda perna da disjuncao e a nota de MUNICIPIO (BLK-JOINUF-01): `qualidade_join_uf`
e' UM VALOR POR ESTADO, entao um interior rural mal casado arrasta a capital junto --
Manaus mede 0,975 de match por chave (classe A) dentro de um AM que agrega 0,787 (C), e
perdia 2.038 dos seus 2.139 hexagonos por isso. A nota fina entra como DISJUNCAO, nunca
como substituicao: por construcao ela so pode PROMOVER (adicionar um caminho para
`granular`), jamais rebaixar quem o estado ja aprovou. Trocar uma nota pela outra seria
regressao liquida de 231.891 hexagonos -- medido, nao suposto.

Nao altera score_priorizacao nem qualquer artefato oficial do M1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def normalized_join_quality(df: pd.DataFrame) -> pd.Series:
    if "qualidade_join_uf" not in df.columns:
        return pd.Series("", index=df.index, dtype="object")
    return (
        df["qualidade_join_uf"]
        .astype(object)
        .where(df["qualidade_join_uf"].notna(), "")
        .astype(str)
        .str.upper()
    )


#: Classes de join que liberam leitura granular. Vale para a nota de UF e para a de
#: municipio -- as duas usam o mesmo vocabulario {A,B,C}.
CLASSES_GRANULARES = ("A", "B")


def normalized_municipal_quality(df: pd.DataFrame) -> pd.Series:
    """Nota de join do MUNICIPIO, normalizada. Ausente = string vazia (inerte).

    Ausencia da coluna NAO e erro: artefato materializado antes do BLK-JOINUF-01 nao a
    tem, e a promocao simplesmente nao acontece -- o comportamento cai, byte a byte, no
    de antes. Isso e seguro justamente PORQUE a nota so promove: uma coluna faltando
    nunca pode rebaixar hexagono nenhum.
    """
    if "classe_join_municipio" not in df.columns:
        return pd.Series("", index=df.index, dtype="object")
    return (
        df["classe_join_municipio"]
        .astype(object)
        .where(df["classe_join_municipio"].notna(), "")
        .astype(str)
        .str.upper()
    )


def has_censo_signal(df: pd.DataFrame) -> pd.Series:
    signal = pd.Series(False, index=df.index)
    if "flag_censo_disponivel" in df.columns:
        signal |= df["flag_censo_disponivel"].fillna(False).astype(bool)
    if "score_setor_2022_calibrado" in df.columns:
        signal |= df["score_setor_2022_calibrado"].notna()
    return signal


def derive_confianca_geografica(df: pd.DataFrame) -> pd.Series:
    if "confianca_geografica" in df.columns:
        base = (
            df["confianca_geografica"]
            .astype(object)
            .where(df["confianca_geografica"].notna(), "municipal")
            .astype(str)
            .str.lower()
        )
        base = base.where(base.isin(["granular", "municipal"]), "municipal")
    else:
        base = pd.Series("municipal", index=df.index, dtype="object")

    # DISJUNCAO, nao substituicao: a nota do municipio SOMA um caminho para `granular`.
    # Escrito como `|` de proposito -- e' o que torna "so promove" uma propriedade
    # ARITMETICA (adicionar termo a um OR nunca remove elemento do conjunto), e nao uma
    # convencao que um refactor futuro possa quebrar sem o teste perceber.
    aprovado = normalized_join_quality(df).isin(CLASSES_GRANULARES) | normalized_municipal_quality(
        df
    ).isin(CLASSES_GRANULARES)
    granular_mask = aprovado & has_censo_signal(df)
    return pd.Series(
        np.where(granular_mask, "granular", base),
        index=df.index,
        dtype="object",
    )


def derive_pop_cut_columns(df: pd.DataFrame, pop_min: int = 5_000) -> pd.DataFrame:
    """Deriva colunas auditaveis para a regua operacional de populacao minima.

    - populacao_corte_hex: valor usado no corte (setor 2022 preferencial, fallback total municipal)
    - fonte_populacao_corte: origem do valor ("setor_2022", "total_municipal" ou "ausente")
    - flag_pop_min_5k: True quando populacao_corte_hex >= pop_min
    Nao altera score_priorizacao nem artefatos oficiais do M1.
    """
    result = df.copy()
    is_granular = (
        result["confianca_geografica"].eq("granular")
        if "confianca_geografica" in result.columns
        else pd.Series(False, index=result.index)
    )
    has_setor = "pop_total_setor_2022" in result.columns
    # Preferir pop_total (total real) sobre populacao_proxy legado (proxy 18-45 antigo).
    has_pop_total = "pop_total" in result.columns
    has_proxy = "populacao_proxy" in result.columns

    pop_municipal = (
        result["pop_total"] if has_pop_total else
        result["populacao_proxy"] if has_proxy else
        pd.Series(pd.NA, index=result.index, dtype="Float64")
    )
    pop_municipal_notna = (
        result["pop_total"].notna() if has_pop_total else
        result["populacao_proxy"].notna() if has_proxy else
        pd.Series(False, index=result.index)
    )

    if has_setor:
        use_setor = is_granular & result["pop_total_setor_2022"].notna()
        pop_val = result["pop_total_setor_2022"].where(use_setor, pop_municipal)
        fonte = np.where(
            use_setor,
            "setor_2022",
            np.where(pop_municipal_notna, "total_municipal", "ausente"),
        )
    else:
        pop_val = pop_municipal
        fonte = np.where(pop_municipal_notna, "total_municipal", "ausente")

    result["populacao_corte_hex"] = pd.to_numeric(pop_val, errors="coerce")
    result["fonte_populacao_corte"] = fonte
    result["flag_pop_min_5k"] = result["populacao_corte_hex"].ge(pop_min).fillna(False)
    return result
