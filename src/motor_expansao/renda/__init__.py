"""Ponto unico da renda exibida (E0 do plano de correcao da renda; DEC-072).

Tudo que multiplica uma renda do Censo por uplift de composicao ou por fator temporal mora
aqui; fora deste pacote, so se CHAMA estas funcoes. A escala do score
(`renda_per_capita_setor_2022_calibrada` e suas reguas) fica FORA: e outro numero.

Importar o pacote nao le fator nem staging -- a carga e preguicosa (`carregar_fatores` com
cache). E por isso o bot nao pode depender dele: `perfil.py`, `api/coord.py`, `api/geo.py` e
`api/settings.py` NAO importam este pacote (DEC-049; travado por teste).
"""

from __future__ import annotations

from motor_expansao.renda.carregador import (
    ENV_VERSAO,
    FatoresGrupo,
    FatoresRenda,
    FatoresRendaInvalidos,
    carregar_fatores,
)
from motor_expansao.renda.formula import (
    campos_referencia_ponto,
    fator,
    fator_composto_domiciliar,
    fatores_do_health,
    renda_domiciliar,
    renda_per_capita,
    v06004_de_fallback,
)
from motor_expansao.renda.hex import (
    CENSO_HEX_STAGING_PARQUET,
    CENSO_MALHA_PARQUET,
    COL_RENDA_DOM_MALHA,
    COL_RENDA_PC_MALHA,
    COLS_RENDA_LEITURA,
    COLS_RENDA_MALHA,
    K_CALIBRACAO_FALLBACK,
    InsumoRendaInvalido,
    base_renda_domiciliar,
    colunas_malha_por_hex,
    fator_hex,
    k_calibracao_renda,
    renda_2022_da_malha,
    renda_domiciliar_hex,
    renda_domiciliar_por_hex,
    renda_per_capita_hex,
    serie_renda,
)
from motor_expansao.renda.insumos import (
    configurar_staging,
    limpar_caches,
    moradores_nacional,
    moradores_por_domicilio,
    staging_dir,
    uplift_extrapolado,
    uplift_municipio,
    uplift_nacional,
    uplift_setor,
)
from motor_expansao.renda.setor import rendas_2022_setores
from motor_expansao.renda.subida import validar_na_subida

__all__ = [
    "CENSO_HEX_STAGING_PARQUET",
    "CENSO_MALHA_PARQUET",
    "COLS_RENDA_LEITURA",
    "COLS_RENDA_MALHA",
    "COL_RENDA_DOM_MALHA",
    "COL_RENDA_PC_MALHA",
    "ENV_VERSAO",
    "K_CALIBRACAO_FALLBACK",
    "FatoresGrupo",
    "FatoresRenda",
    "FatoresRendaInvalidos",
    "InsumoRendaInvalido",
    "base_renda_domiciliar",
    "campos_referencia_ponto",
    "carregar_fatores",
    "colunas_malha_por_hex",
    "configurar_staging",
    "fator",
    "fator_composto_domiciliar",
    "fator_hex",
    "fatores_do_health",
    "k_calibracao_renda",
    "limpar_caches",
    "moradores_nacional",
    "moradores_por_domicilio",
    "renda_domiciliar",
    "renda_domiciliar_hex",
    "renda_2022_da_malha",
    "renda_domiciliar_por_hex",
    "renda_per_capita",
    "renda_per_capita_hex",
    "rendas_2022_setores",
    "serie_renda",
    "staging_dir",
    "uplift_extrapolado",
    "uplift_municipio",
    "uplift_nacional",
    "uplift_setor",
    "v06004_de_fallback",
    "validar_na_subida",
]
