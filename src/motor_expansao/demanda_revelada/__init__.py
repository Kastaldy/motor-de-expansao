"""Camada paralela de Demanda Revelada (H3 res-7, sem PII).

Pacote DISJUNTO (BLK-TP-01 / DEC-012): NUNCA importa de `pipelines/m1/`, `censo_*`
nem `dashboard/`; é READ-ONLY sobre o M1 e usa só deps da base (pandas/numpy/pyarrow/h3).
A demanda é insumo OBSERVADO (DEC-009), NUNCA preditor geográfico de magnitude.

**Re-export PREGUIÇOSO (PEP 562) `[BLK-MA-02-FU1 item 2]`.** Este `__init__` reexporta 9
submódulos. Enquanto isso era feito com `from .x import y` no topo, importar **qualquer** coisa
do pacote — inclusive um submódulo leve, porque o interpretador executa o `__init__` do pai
primeiro — carregava o conjunto inteiro: `sklearn`, `scipy`, `shapely`, `requests`, `pyproj` e
módulos de `dashboard/`, em ~18 s. O peso não está espalhado: vem de `backtest_tp05`,
`calibracao_*`, `estrutura_funil`, `huff_captura` e `validacao`, que importam `scipy`/`sklearn` no
topo. `classificacao_rede_menor`, por exemplo, só precisa de `re`/`unicodedata`/`pathlib`.

Quem pagava a conta era o `vulnerabilidade/`, que importa **um** nome daqui
(`classificar_rede`, em `snapshots.py`) e é o módulo destinado ao cron do coletor — onde
`sklearn`/`scipy` podem nem estar instalados, e o passo quebraria já no import.

O contrato público não muda: `from motor_expansao.demanda_revelada import classificar_rede`,
`import ... as dr; dr.classificar_rede` e `from ... import *` continuam funcionando, e cada nome
resolvido é memoizado em `globals()` para que o segundo acesso não passe por aqui.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

# Nome público -> (submódulo, nome dentro do submódulo). A segunda posição existe por causa dos
# três apelidos do `aferir_overlap_nao_abra`, cujo nome local difere do exportado.
_EXPORTS: dict[str, tuple[str, str]] = {
    # aferir_overlap_nao_abra (BLK-ATR-01-FU1)
    "COMPETIDORES_DEFAULT": ("aferir_overlap_nao_abra", "COMPETIDORES_DEFAULT"),
    "DENSOS_DEFAULT": ("aferir_overlap_nao_abra", "DENSOS_DEFAULT"),
    "SMARTFIT_DEFAULT": ("aferir_overlap_nao_abra", "SMARTFIT_DEFAULT"),
    "VERSAO_CONTRATO_OVERLAP": ("aferir_overlap_nao_abra", "VERSAO_CONTRATO_OVERLAP"),
    "calcular_metricas_competidores": (
        "aferir_overlap_nao_abra",
        "calcular_metricas_competidores",
    ),
    "calcular_metricas_smartfit": ("aferir_overlap_nao_abra", "calcular_metricas_smartfit"),
    "RELATORIO_OVERLAP_DEFAULT": ("aferir_overlap_nao_abra", "RELATORIO_DEFAULT"),
    "executar_overlap_nao_abra": ("aferir_overlap_nao_abra", "executar"),
    "gerar_relatorio_overlap": ("aferir_overlap_nao_abra", "gerar_relatorio"),
    # backtest_tp05 (PESADO: scipy + sklearn)
    "BacktestTP05Result": ("backtest_tp05", "BacktestTP05Result"),
    "backtest_demanda_captura": ("backtest_tp05", "backtest_demanda_captura"),
    # classificacao_rede_menor (BLK-TP-08-FU) - LEVE; e' o unico nome que o `vulnerabilidade/` usa
    "CONTRATO_COLUNAS_CAP_REDE": ("classificacao_rede_menor", "CONTRATO_COLUNAS_CAP_REDE"),
    "CONTRATO_COLUNAS_OFERTA_MENORES_REDE": (
        "classificacao_rede_menor",
        "CONTRATO_COLUNAS_OFERTA_MENORES_REDE",
    ),
    "VERSAO_CONTRATO_CAP_REDE": ("classificacao_rede_menor", "VERSAO_CONTRATO_CAP_REDE"),
    "VERSAO_CONTRATO_OFERTA_MENORES_REDE": (
        "classificacao_rede_menor",
        "VERSAO_CONTRATO_OFERTA_MENORES_REDE",
    ),
    "classificar_rede": ("classificacao_rede_menor", "classificar_rede"),
    "gerar_capacidade_media_por_rede": (
        "classificacao_rede_menor",
        "gerar_capacidade_media_por_rede",
    ),
    "gerar_relatorio_classificacao": ("classificacao_rede_menor", "gerar_relatorio_classificacao"),
    "ingerir_oferta_menores_por_rede": (
        "classificacao_rede_menor",
        "ingerir_oferta_menores_por_rede",
    ),
    # concorrentes_densos (BLK-ATR-01)
    "CONTRATO_COLUNAS_CONCORRENTES_DENSOS": (
        "concorrentes_densos",
        "CONTRATO_COLUNAS_CONCORRENTES_DENSOS",
    ),
    "VERSAO_CONTRATO_CONCORRENTES_DENSOS": (
        "concorrentes_densos",
        "VERSAO_CONTRATO_CONCORRENTES_DENSOS",
    ),
    "deduplicar": ("concorrentes_densos", "deduplicar"),
    "gerar_relatorio_huff_densa": ("concorrentes_densos", "gerar_relatorio_huff_densa"),
    "ingerir_csvs_concorrentes": ("concorrentes_densos", "ingerir_csvs_concorrentes"),
    "materializar": ("concorrentes_densos", "materializar"),
    "revalidar_huff_densa": ("concorrentes_densos", "revalidar_huff_densa"),
    # contrato
    "COLUNAS_PII_PROIBIDAS": ("contrato", "COLUNAS_PII_PROIBIDAS"),
    "CONTRATO_COLUNAS": ("contrato", "CONTRATO_COLUNAS"),
    "H3_RES_CONTRATO": ("contrato", "H3_RES_CONTRATO"),
    "VERSAO_CONTRATO": ("contrato", "VERSAO_CONTRATO"),
    # ingestao
    "ingerir_demanda_revelada": ("ingestao", "ingerir_demanda_revelada"),
    # oferta_academias_menores (BLK-TP-08)
    "CONTRATO_COLUNAS_OFERTA_MENORES": (
        "oferta_academias_menores",
        "CONTRATO_COLUNAS_OFERTA_MENORES",
    ),
    "VERSAO_CONTRATO_OFERTA_MENORES": (
        "oferta_academias_menores",
        "VERSAO_CONTRATO_OFERTA_MENORES",
    ),
    "gerar_relatorio_qualidade": ("oferta_academias_menores", "gerar_relatorio_qualidade"),
    "ingerir_oferta_academias_menores": (
        "oferta_academias_menores",
        "ingerir_oferta_academias_menores",
    ),
    # validacao (PESADO: scipy)
    "executar_validacao_completa": ("validacao", "executar_validacao_completa"),
    # vazios_competitivos (BLK-TP-03)
    "CONTRATO_COLUNAS_VAZIOS": ("vazios_competitivos", "CONTRATO_COLUNAS_VAZIOS"),
    "LIMIAR_MEMBROS_GT5KM": ("vazios_competitivos", "LIMIAR_MEMBROS_GT5KM"),
    "VERSAO_CONTRATO_VAZIOS": ("vazios_competitivos", "VERSAO_CONTRATO_VAZIOS"),
    "flag_vazio_competitivo": ("vazios_competitivos", "flag_vazio_competitivo"),
    "gerar_vazios_competitivos": ("vazios_competitivos", "gerar_vazios_competitivos"),
}

if TYPE_CHECKING:  # pragma: no cover - só para o type checker enxergar os nomes reexportados
    from .aferir_overlap_nao_abra import (
        COMPETIDORES_DEFAULT,
        DENSOS_DEFAULT,
        SMARTFIT_DEFAULT,
        VERSAO_CONTRATO_OVERLAP,
        calcular_metricas_competidores,
        calcular_metricas_smartfit,
    )
    from .aferir_overlap_nao_abra import (
        RELATORIO_DEFAULT as RELATORIO_OVERLAP_DEFAULT,
    )
    from .aferir_overlap_nao_abra import (
        executar as executar_overlap_nao_abra,
    )
    from .aferir_overlap_nao_abra import (
        gerar_relatorio as gerar_relatorio_overlap,
    )
    from .backtest_tp05 import (
        BacktestTP05Result,
        backtest_demanda_captura,
    )
    from .classificacao_rede_menor import (
        CONTRATO_COLUNAS_CAP_REDE,
        CONTRATO_COLUNAS_OFERTA_MENORES_REDE,
        VERSAO_CONTRATO_CAP_REDE,
        VERSAO_CONTRATO_OFERTA_MENORES_REDE,
        classificar_rede,
        gerar_capacidade_media_por_rede,
        gerar_relatorio_classificacao,
        ingerir_oferta_menores_por_rede,
    )
    from .concorrentes_densos import (
        CONTRATO_COLUNAS_CONCORRENTES_DENSOS,
        VERSAO_CONTRATO_CONCORRENTES_DENSOS,
        deduplicar,
        gerar_relatorio_huff_densa,
        ingerir_csvs_concorrentes,
        materializar,
        revalidar_huff_densa,
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


def __getattr__(name: str) -> object:
    """Resolve um nome reexportado carregando só o submódulo que o define (PEP 562)."""
    alvo = _EXPORTS.get(name)
    if alvo is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    submodulo, atributo = alvo
    valor = getattr(importlib.import_module(f".{submodulo}", __name__), atributo)
    # Memoiza: a partir daqui o acesso normal encontra o nome e o `__getattr__` não roda de novo.
    globals()[name] = valor
    return valor


def __dir__() -> list[str]:
    return sorted(set(__all__) | set(globals()))


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
    # BLK-TP-08-FU: classificação de rede das academias menores
    "classificar_rede",
    "ingerir_oferta_menores_por_rede",
    "gerar_capacidade_media_por_rede",
    "gerar_relatorio_classificacao",
    "CONTRATO_COLUNAS_OFERTA_MENORES_REDE",
    "CONTRATO_COLUNAS_CAP_REDE",
    "VERSAO_CONTRATO_OFERTA_MENORES_REDE",
    "VERSAO_CONTRATO_CAP_REDE",
    # BLK-ATR-01-FU1: aferição de overlap base densa vs NAO_ABRA
    "calcular_metricas_smartfit",
    "calcular_metricas_competidores",
    "gerar_relatorio_overlap",
    "executar_overlap_nao_abra",
    "RELATORIO_OVERLAP_DEFAULT",
    "SMARTFIT_DEFAULT",
    "COMPETIDORES_DEFAULT",
    "DENSOS_DEFAULT",
    "VERSAO_CONTRATO_OVERLAP",
    # BLK-ATR-01: base densa de concorrentes do Huff
    "materializar",
    "ingerir_csvs_concorrentes",
    "deduplicar",
    "revalidar_huff_densa",
    "gerar_relatorio_huff_densa",
    "CONTRATO_COLUNAS_CONCORRENTES_DENSOS",
    "VERSAO_CONTRATO_CONCORRENTES_DENSOS",
]
