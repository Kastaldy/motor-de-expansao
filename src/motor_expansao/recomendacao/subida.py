"""Checagem de subida da recomendacao unica (ligar no boot e Fase 4).

Mesmo espirito de `renda/subida.py`: a falha aparece no boot, uma vez, e nao como uma lista
vazia em cada tela.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from motor_expansao.recomendacao.carregador import Regra, carregar_regra
from motor_expansao.renda.hex import InsumoRendaInvalido, k_da_malha

_LOG = logging.getLogger("motor_expansao.recomendacao")


def validar_na_subida(staging_dir: Path | str | None = None) -> Regra | None:
    """Carrega a regua vigente e confere o carimbo k da malha. Devolve a regua (ou None).

    - Regua invalida -> `RegraRecomendacaoInvalida` SEMPRE (a regua vai na imagem).
    - Pais sem regua -> `None`, sem conferir mais nada (nao ha recomendacao a servir).
    - Com regua e `MOTOR_DATA_DIR` setado (producao): o k da malha tem de ser legivel e
      plausivel -> senao `InsumoRendaInvalido`. Sem ele o Top 10 inteiro sairia indisponivel em
      toda tela; em producao isso e deploy quebrado, nao estado aceitavel.
    - Sem `MOTOR_DATA_DIR` (dev/teste): so WARNING; a recomendacao sai indisponivel.
    """
    regra = carregar_regra()
    if regra is None:
        return None
    if k_da_malha(staging_dir) is None:
        if os.environ.get("MOTOR_DATA_DIR"):
            raise InsumoRendaInvalido(
                f"recomendacao ({regra.pais}, regua {regra.versao}): carimbo k da malha "
                "ausente ou ilegivel -- o Top 10 ficaria indisponivel em todas as telas"
            )
        _LOG.warning(
            "recomendacao (%s, regua %s): sem o carimbo k da malha -- dev/teste, o Top 10 "
            "sai indisponivel",
            regra.pais,
            regra.versao,
        )
    if regra.fixada_por_env:
        _LOG.warning(
            "recomendacao (%s): subindo com a regua FIXADA por env %s (rollback ativo)",
            regra.pais,
            regra.versao,
        )
    return regra
