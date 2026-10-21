"""Insumos SINTETICOS da recomendacao unica (nenhum teste le `data/` nem `C:\\tmp`).

- `regra_teste(...)`: uma `Regra` montada direto (sem arquivo), com os numeros da BR v1 por
  default e qualquer campo trocavel -- para provar que a regua manda (teste 8) e para cobrir os
  dois valores de `premium.exige_residual_medido` (teste 9).
- `hexes(...)`: DataFrame no formato da particao enriquecida, ja com a coluna
  `renda_domiciliar` que `montar.py` calcularia (o nucleo nao faz conta de renda).
- `PROCEDENCIA`: uma procedencia de renda qualquer (o nucleo so a carimba).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np
import pandas as pd

from motor_expansao.recomendacao import (
    ProcedenciaRenda,
    Recorte,
    Regra,
    ReguaMataVirgem,
    ReguaPremium,
)
from motor_expansao.recomendacao.nucleo import COL_RENDA, FONTE_MEDIDA

FONTE_ESTIMADA = "m1_municipal_proxy_per_hex"

PROCEDENCIA = ProcedenciaRenda(
    k=1.2, carimbo="multiplicativo_global_k=1.2", fatores_versao="teste_v1", pais="BR"
)
RECORTE_BR = Recorte(nivel="brasil")


def regra_teste(
    *,
    versao: str = "2026-10_v1",
    vagas: int = 5,
    renda_min: float = 4500.0,
    residual_min: float = 2000.0,
    mv_pop_min: float | None = None,
    mv_exige_medido: bool = True,
    score_min: float = 50.0,
    premium_pop_min: float | None = 10000.0,
    premium_exige_medido: bool = True,
) -> Regra:
    return Regra(
        versao=versao,
        pais="BR",
        dec="DEC-077",
        aprovado_por="teste",
        vagas_por_segmento=vagas,
        mata_virgem=ReguaMataVirgem(
            renda_domiciliar_min=renda_min,
            residual_min=residual_min,
            populacao_min=mv_pop_min,
            exige_residual_medido=mv_exige_medido,
        ),
        premium=ReguaPremium(
            score_min=score_min,
            populacao_min=premium_pop_min,
            exige_residual_medido=premium_exige_medido,
        ),
    )


REGRA_V1 = regra_teste()


def com(regra: Regra, **mudancas: Any) -> Regra:
    return replace(regra, **mudancas)


def linha(
    hex_id: str,
    *,
    renda: float | None = 3000.0,
    residual: float | None = 100.0,
    populacao: float | None = 5000.0,
    score: float | None = 30.0,
    medido: bool = True,
    uf: str = "SP",
    cod_municipio: str = "3550308",
    nome_municipio: str = "São Paulo",
    **extras: Any,
) -> dict[str, Any]:
    """Uma linha que, por default, NAO e candidata a nada (renda/residual/score baixos)."""
    return {
        "hex_id": hex_id,
        "uf": uf,
        "cod_municipio": cod_municipio,
        "nome_municipio": nome_municipio,
        "lat": -23.5,
        "lng": -46.6,
        COL_RENDA: np.nan if renda is None else renda,
        "oferta_efetiva_disponivel": np.nan if residual is None else residual,
        "score_setor_2022_calibrado": np.nan if score is None else score,
        "pop_total_setor_2022": np.nan if populacao is None else populacao,
        "fonte_pop_hex_base": FONTE_MEDIDA if medido else FONTE_ESTIMADA,
        **extras,
    }


def mv(
    hex_id: str, residual: float | None = 3000.0, populacao: float | None = 8000.0, **kw: Any
) -> dict:
    """Linha Mata Virgem (renda alta, residual alto, medido)."""
    kw.setdefault("renda", 9000.0)
    return linha(hex_id, residual=residual, populacao=populacao, **kw)


def premium(
    hex_id: str, populacao: float | None = 20000.0, score: float | None = 70.0, **kw: Any
) -> dict:
    """Linha Premium (residual baixo -> provadamente nao-MV; score e populacao altos)."""
    kw.setdefault("residual", 500.0)
    return linha(hex_id, populacao=populacao, score=score, **kw)


def hexes(linhas: list[dict[str, Any]], *, float32: bool = True) -> pd.DataFrame:
    """DataFrame com os dtypes do artefato: residual e score em Float32 (como servidos)."""
    df = pd.DataFrame(linhas)
    if float32:
        df["oferta_efetiva_disponivel"] = df["oferta_efetiva_disponivel"].astype("float32")
        df["score_setor_2022_calibrado"] = df["score_setor_2022_calibrado"].astype("float32")
    return df
