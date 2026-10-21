"""Entradas da Viabilidade v2 na ISOCRONA de 10 min de carro (DEC-077 ampliada).

Recebe a malha de setores JA CARREGADA (a uniao das particoes que a isocrona alcanca —
mecanismo da DEC-065/DEC-071, em `api.service._resolver_e_carregar(geometria=...)`) e o
poligono da isocrona (DEC-074, `alcance_ponto.isocrona_carro`), e agrega por INTERSECAO
DE AREA, na mesma projecao local (AEQD centrada no ponto) do motor censitario:

    peso_i  = area(setor_i ∩ isocrona) / area(setor_i)        [ambas na AEQD local]
    pop_c10 = Σ v0001_i x peso_i          (`pop_total_setor_2022`)
    dom_c10 = Σ v0007_i x peso_i          (`domicilios_particulares_ocupados_setor_2022`)
    renda_pc_c10 = media de `renda_per_capita_setor_2022_calibrada` ponderada por
                   (v0001_i x peso_i); setor SEM calibrada usa a bruta
                   (`renda_per_capita_setor_2022`), setor a setor.

As tres regras abaixo sao as do ESTUDO que gerou os coeficientes
(`data/analysis/isocronas/04_atributos.py`, `carregar_setores` e `atributos_poligono`), para
que a mesma praca de as mesmas entradas aqui e la':
  - fallback de renda SETOR A SETOR (`calibrada.fillna(bruta)`), nao "toda nula";
  - `flag_geometria_valida` ausente conta como VALIDA (`fillna(True)`);
  - isocrona acima de `AREA_RAPIDA_M2` (40 km2) pesa o setor INTEIRO quando o ponto
    representativo dele cai dentro, em vez da fracao de area (adendo v2, item 7).
    renda_dom_c10 = renda_pc_c10 x pop_c10 / dom_c10   (em `EntradasV2`)

SEM uplift e SEM fator temporal: NAO e' a renda domiciliar do Relatorio Pontual (V06004 x
uplift x FATOR_TEMPORAL_RENDA). Domicilios = v0007 (particulares OCUPADOS), a base de
renda por domicilio; v0002 (total, com vagos e de uso ocasional) diluiria a renda.

Puro sobre os frames recebidos (sem rede, sem disco). Nunca cai no raio: sem area
analisavel ou sem populacao/domicilio, levanta `EntradasC10Indisponiveis` com o motivo.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from shapely.geometry.base import BaseGeometry

COL_POP = "pop_total_setor_2022"
COL_DOM = "domicilios_particulares_ocupados_setor_2022"
COL_RENDA_CALIBRADA = "renda_per_capita_setor_2022_calibrada"
COL_RENDA_BRUTA = "renda_per_capita_setor_2022"
# Acima desta area a isocrona do estudo trocou a fracao de area pelo ponto representativo.
AREA_RAPIDA_M2 = 40e6
# Acima desta area a isocrona do estudo trocou a fracao de area pelo ponto representativo.
AREA_RAPIDA_M2 = 40e6


class EntradasC10Indisponiveis(ValueError):
    """A isocrona nao rende entradas utilizaveis. `str(exc)` e' o motivo ao usuario."""


@dataclass(frozen=True)
class EntradasC10:
    pop_c10: float
    dom_c10: float
    renda_pc_c10: float
    n_setores: int
    renda_fonte: str  # "calibrada" | "bruta" | "mista" (bruta so' nos setores sem calibrada)

    @property
    def renda_dom_c10(self) -> float:
        return self.renda_pc_c10 * self.pop_c10 / self.dom_c10


def agregar_entradas_c10(
    setores_df: pd.DataFrame | None,
    geometria_wgs84: BaseGeometry,
    lat: float,
    lng: float,
) -> EntradasC10:
    """Agrega populacao, domicilios e renda per capita dos setores DENTRO da isocrona."""
    from motor_expansao.dashboard.censo_point import (
        CRS_ORIGEM_CENSO,
        _bbox_prefilter,
        _decode_geometry,
        _local_metric_crs,
        _numeric,
        _project_geometry,
        _transformer,
    )

    if geometria_wgs84 is None or geometria_wgs84.is_empty:
        raise EntradasC10Indisponiveis("A área de 10 min de carro veio vazia.")
    if setores_df is None or setores_df.empty:
        raise EntradasC10Indisponiveis("Não há setores censitários carregados para esta área.")
    col_geom = "geometry_wkb" if "geometry_wkb" in setores_df.columns else "geometry"
    if col_geom not in setores_df.columns:
        raise EntradasC10Indisponiveis("A malha de setores não tem geometria.")

    to_metric = _transformer(CRS_ORIGEM_CENSO, _local_metric_crs(lat, lng))
    recorte = _project_geometry(geometria_wgs84, to_metric)
    candidatos = _bbox_prefilter(setores_df, geometria_wgs84)
    if "flag_geometria_valida" in candidatos.columns:
        candidatos = candidatos.loc[
            candidatos["flag_geometria_valida"].astype("boolean").fillna(True).astype(bool)
        ]

    pesos: list[float] = []
    indices: list[object] = []
    por_ponto = float(recorte.area) > AREA_RAPIDA_M2
    for idx, valor in candidatos[col_geom].items():
        geom = _decode_geometry(valor)
        if geom is None:
            continue
        geom_m = _project_geometry(geom, to_metric)
        area_setor = float(geom_m.area)
        if area_setor <= 0:
            continue
        if por_ponto:
            if recorte.contains(geom_m.representative_point()):
                pesos.append(1.0)
                indices.append(idx)
            continue
        inter = geom_m.intersection(recorte)
        if inter.is_empty or inter.area <= 0:
            continue
        pesos.append(max(0.0, min(1.0, float(inter.area) / area_setor)))
        indices.append(idx)
    if not indices:
        raise EntradasC10Indisponiveis("Nenhum setor censitário cai na área de 10 min de carro.")

    sel = candidatos.loc[indices]
    peso = pd.Series(pesos, index=sel.index, dtype="float64")
    pop_i = _numeric(sel, COL_POP).clip(lower=0).fillna(0.0) * peso
    dom_i = _numeric(sel, COL_DOM).clip(lower=0).fillna(0.0) * peso
    calibrada = _numeric(sel, COL_RENDA_CALIBRADA)
    renda = calibrada.fillna(_numeric(sel, COL_RENDA_BRUTA))
    usou_bruta = calibrada.isna() & renda.notna()
    fonte = "bruta" if usou_bruta.all() else ("mista" if usou_bruta.any() else "calibrada")

    pop_c10 = float(pop_i.sum())
    dom_c10 = float(dom_i.sum())
    validos = renda.notna() & pop_i.gt(0)
    if pop_c10 <= 0 or dom_c10 <= 0:
        raise EntradasC10Indisponiveis(
            "A área de 10 min de carro não tem população ou domicílios no Censo 2022."
        )
    if not validos.any():
        raise EntradasC10Indisponiveis(
            "A área de 10 min de carro não tem renda publicada no Censo 2022."
        )
    renda_pc = float(np.average(renda[validos], weights=pop_i[validos]))
    return EntradasC10(
        pop_c10=pop_c10,
        dom_c10=dom_c10,
        renda_pc_c10=renda_pc,
        n_setores=int(len(indices)),
        renda_fonte=fonte,
    )


__all__ = ["EntradasC10", "EntradasC10Indisponiveis", "agregar_entradas_c10"]
