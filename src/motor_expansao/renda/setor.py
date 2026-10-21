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
