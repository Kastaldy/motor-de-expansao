"""Renda media DOMICILIAR por SETOR censitario: a forma canonica, uma redacao so (E1; DEC-072).

    renda_domiciliar_setor = (V06004 x uplift_setor) x F_dom(uf)

com a V06004 reconstruida pela per capita BRUTA x moradores onde ela falta
(`v06004_de_fallback`) -- nunca pela calibrada, que carrega o k. E a conta que o Relatorio
Pontual faz setor a setor (`censo_point`) e que a camada de setores da ficha da rede ja fazia
(`app._rede_setores_entorno`). Ate a E1, o mapa de calor de setor do Mapa servia a coluna
CALIBRADA crua (escala do score: V06004 / moradores x k, sem uplift e sem fator) sob o rotulo
"Renda domiciliar", e o perfil do bairro do PDF servia a V06004 BRUTA (renda do responsavel).

As colunas lidas sao as do artefato GEO setorial (`setores_censitarios_2022_geo`).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import pandas as pd

from motor_expansao.renda import insumos as _insumos
from motor_expansao.renda.formula import renda_domiciliar, v06004_de_fallback

#: V06004: rendimento medio do RESPONSAVEL pelo domicilio (Censo 2022).
COL_V06004 = "renda_responsavel_media_setor_2022"
#: Per capita BRUTA (V06004 / moradores, sem k): so serve para reconstruir a V06004.
COL_PER_CAPITA_BRUTA = "renda_per_capita_setor_2022"
#: Moradores medios por domicilio do setor (v0005, Censo 2022).
COL_MORADORES = "avg_moradores_domicilio_setor_2022"


def _finito(v: Any) -> float | None:
    """float finito ou None (None, NaN, pd.NA, inf e texto viram None)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def renda_domiciliar_setor(
    v06004: Any,
    per_capita_bruta: Any,
    moradores: Any,
    cod_setor: object,
    uf: str | None,
    cod_municipio: str | None,
) -> float | None:
    """Renda media domiciliar do setor = (V06004 x uplift do setor) x F_dom(uf). Sem arredondar.

    `uplift` pela cascata setor -> municipio -> UF -> nacional (`insumos.uplift_setor`). Sem
    V06004 nem per capita bruta x moradores -> None (setor sem leitura), nunca zero.
    """
    base = _finito(v06004)
    if base is None:
        base = _finito(
            v06004_de_fallback(None, _finito(per_capita_bruta), _finito(moradores))
        )
    if base is None:
        return None
    # Insumo lido como ATRIBUTO do modulo (e nao por nome importado), como em `censo_point`:
    # um teste que fixe o uplift em `renda.insumos` vale aqui tambem.
    return renda_domiciliar(base, float(_insumos.uplift_setor(cod_setor, uf, cod_municipio)), uf)


def renda_domiciliar_da_linha(
    linha: Mapping[str, Any] | pd.Series, uf: str | None, cod_municipio: str | None
) -> float | None:
    """`renda_domiciliar_setor` sobre uma linha do artefato GEO (dict ou `pd.Series`)."""
    return renda_domiciliar_setor(
        linha.get(COL_V06004),
        linha.get(COL_PER_CAPITA_BRUTA),
        linha.get(COL_MORADORES),
        linha.get("cod_setor"),
        uf,
        cod_municipio,
    )


def renda_domiciliar_setores(
    df: pd.DataFrame, *, uf: str | None = None, cod_municipio: str | None = None
) -> pd.Series:
    """`renda_domiciliar_setor` de cada linha de `df` (float64, NaN onde nao ha leitura).

    UF e municipio da cascata do uplift e do fator: os da PROPRIA linha quando o frame traz as
    colunas `uf`/`cod_municipio` (um frame de divisa mistura municipios); senao, os argumentos.
    """
    tem_uf = "uf" in df.columns
    tem_cod = "cod_municipio" in df.columns
    valores: list[float] = []
    for _, linha in df.iterrows():
        uf_linha = _texto(linha.get("uf")) if tem_uf else None
        cod_linha = _texto(linha.get("cod_municipio")) if tem_cod else None
        v = renda_domiciliar_da_linha(linha, uf_linha or uf, cod_linha or cod_municipio)
        valores.append(float("nan") if v is None else float(v))
    return pd.Series(valores, index=df.index, dtype="float64")


def _texto(v: Any) -> str | None:
    if v is None or (isinstance(v, float) and math.isnan(v)) or v is pd.NA:
        return None
    s = str(v).strip().removesuffix(".0")
    return s or None


# ---------------------------------------------------------------------------------------------
# Renda de 2022 por setor, SEM fator temporal: insumo da agregacao para o hexagono (E3).
# ---------------------------------------------------------------------------------------------

#: Domicilios particulares ocupados do setor (v0007, Censo 2022): peso da domiciliar do hex.
COL_DOMICILIOS = "domicilios_particulares_ocupados_setor_2022"


def _uplift_setores(df: pd.DataFrame) -> pd.Series:
    """Uplift de cada linha pela cascata setor -> municipio -> UF -> nacional (vetorizado).

    O mesmo valor que `insumos.uplift_setor(cod_setor, uf, cod_municipio)` daria linha a
    linha; aqui a tabela do setor e mapeada de uma vez e so as linhas sem uplift proprio
    descem a cascata (uma chamada por par UF/municipio distinto, nao por setor).
    """
    mapa = _insumos._carregar_uplift_setor()
    cods = df["cod_setor"].astype("string").str.strip() if "cod_setor" in df.columns else None
    if cods is not None:
        uplift = pd.to_numeric(cods.map(mapa), errors="coerce").astype("float64")
    else:
        uplift = pd.Series(float("nan"), index=df.index, dtype="float64")
    falta = uplift.isna()
    if falta.any():
        ufs = df["uf"] if "uf" in df.columns else pd.Series([None] * len(df), index=df.index)
        munis = (
            df["cod_municipio"]
            if "cod_municipio" in df.columns
            else pd.Series([None] * len(df), index=df.index)
        )
        chaves = list(zip(ufs[falta].map(_texto), munis[falta].map(_texto), strict=True))
        cache: dict[tuple[str | None, str | None], float] = {}
        valores = []
        for chave in chaves:
            if chave not in cache:
                cache[chave] = float(_insumos.uplift_municipio(chave[0], chave[1]))
            valores.append(cache[chave])
        uplift.loc[falta] = valores
    return uplift


def rendas_2022_setores(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """(domiciliar 2022, per capita 2022) de cada setor de `df`, SEM fator temporal.

        domiciliar_2022 = V06004 x uplift_setor
        per_capita_2022 = (V06004 x uplift_setor) / moradores_setor (de 2022)

    E a renda do setor na DATA do Censo (secao 9.3 do plano, passos 3 e 5). O fator temporal
    entra so na exibicao, uma vez, com o tipo certo (`renda.hex`): este par vira coluna de
    artefato (`agregar_censo_hex_da_malha`) e o artefato nao pode carregar fator nenhum,
    senao trocar a versao dos fatores exigiria regenera-lo.

    V06004 ausente e reconstruida pela per capita BRUTA x moradores (`v06004_de_fallback`),
    como no Relatorio Pontual. Sem leitura (ou moradores <= 0, para a per capita) -> NaN.
    """
    if df.empty:
        vazio = pd.Series(dtype="float64", index=df.index)
        return vazio, vazio.copy()

    def _col(nome: str) -> pd.Series:
        if nome not in df.columns:
            return pd.Series(float("nan"), index=df.index, dtype="float64")
        return pd.to_numeric(df[nome], errors="coerce").astype("float64")

    moradores = _col(COL_MORADORES)
    base = v06004_de_fallback(_col(COL_V06004), _col(COL_PER_CAPITA_BRUTA), moradores)
    base = base.where(base > 0)
    if base.isna().all():
        # Sem leitura nenhuma: nao toca nos insumos do uplift (frame sem colunas de renda).
        vazio = pd.Series(float("nan"), index=df.index, dtype="float64")
        return vazio, vazio.copy()
    dom = base * _uplift_setores(df)
    pc = (dom / moradores).where(moradores > 0)
    return dom.astype("float64"), pc.astype("float64")
