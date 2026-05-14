"""Shared constants for the M1 expansion model.

`config.py` remains the operational source of settings. This module only exposes
stable aliases used by package code and legacy entrypoints.
"""

from __future__ import annotations

try:
    from api.config import settings
except ModuleNotFoundError:
    from config import settings

H3_RESOLUTION = settings.H3_RESOLUTION
DIST_MIN_ULTRA_KM = settings.DIST_MIN_ULTRA_KM
RENDA_MIN = settings.RENDA_MIN
AREA_MIN_M2 = settings.AREA_MIN_M2
AREA_IDEAL_MIN_M2 = settings.AREA_IDEAL_MIN_M2
AREA_IDEAL_MAX_M2 = settings.AREA_IDEAL_MAX_M2
PE_DIREITO_MIN = settings.PE_DIREITO_MIN
M1_SCORE_OFICIAL = settings.M1_SCORE_OFICIAL
M1_PRIORIZACAO_TOP_PCT_POR_UF = settings.M1_PRIORIZACAO_TOP_PCT_POR_UF
M1_OSM_ENABLED = settings.M1_OSM_ENABLED
M1_SETOR_CENSITARIO_OBRIGATORIO = settings.M1_SETOR_CENSITARIO_OBRIGATORIO
M1_POP_MINIMA_PROXY = settings.M1_POP_MINIMA_PROXY

PESOS_HEX_SCORE = {
    "renda_normalizada": 0.35,
    "pop_jovem_normalizada": 0.25,
    "ausencia_concorrencia": 0.25,
    "vitalidade_comercial": 0.15,
}

PESOS_HEX_SCORE_ESTRUTURAL = {
    "renda_per_capita": 0.40,
    "populacao_proxy": 0.60,
}

PESOS_HEX_SCORE_FINAL = {
    "hex_score_estrutural": round(
        (
            PESOS_HEX_SCORE_ESTRUTURAL["renda_per_capita"]
            + PESOS_HEX_SCORE_ESTRUTURAL["populacao_proxy"]
        )
        / (
            PESOS_HEX_SCORE_ESTRUTURAL["renda_per_capita"]
            + PESOS_HEX_SCORE_ESTRUTURAL["populacao_proxy"]
            + PESOS_HEX_SCORE["ausencia_concorrencia"]
        ),
        6,
    ),
    "score_concorrencia": round(
        PESOS_HEX_SCORE["ausencia_concorrencia"]
        / (
            PESOS_HEX_SCORE_ESTRUTURAL["renda_per_capita"]
            + PESOS_HEX_SCORE_ESTRUTURAL["populacao_proxy"]
            + PESOS_HEX_SCORE["ausencia_concorrencia"]
        ),
        6,
    ),
}

FAIXAS_OPORTUNIDADE = [
    "inviavel",
    "descartado",
    "baixa",
    "media",
    "alta",
    "prioridade_maxima",
]

OSM_STATUS_NAO_APLICADO = "nao_aplicado_mvp_nacional"
PERCENTIL_CORTE_SUPERIOR = 0.75
PERCENTIL_CORTE_INFERIOR = 0.25

CAPITAIS_UF = {
    "AC": {"cod_municipio": "1200401", "capital": "Rio Branco"},
    "AL": {"cod_municipio": "2704302", "capital": "Maceio"},
    "AM": {"cod_municipio": "1302603", "capital": "Manaus"},
    "AP": {"cod_municipio": "1600303", "capital": "Macapa"},
    "BA": {"cod_municipio": "2927408", "capital": "Salvador"},
    "CE": {"cod_municipio": "2304400", "capital": "Fortaleza"},
    "DF": {"cod_municipio": "5300108", "capital": "Brasilia"},
    "ES": {"cod_municipio": "3205309", "capital": "Vitoria"},
    "GO": {"cod_municipio": "5208707", "capital": "Goiania"},
    "MA": {"cod_municipio": "2111300", "capital": "Sao Luis"},
    "MG": {"cod_municipio": "3106200", "capital": "Belo Horizonte"},
    "MS": {"cod_municipio": "5002704", "capital": "Campo Grande"},
    "MT": {"cod_municipio": "5103403", "capital": "Cuiaba"},
    "PA": {"cod_municipio": "1501402", "capital": "Belem"},
    "PB": {"cod_municipio": "2507507", "capital": "Joao Pessoa"},
    "PE": {"cod_municipio": "2611606", "capital": "Recife"},
    "PI": {"cod_municipio": "2211001", "capital": "Teresina"},
    "PR": {"cod_municipio": "4106902", "capital": "Curitiba"},
    "RJ": {"cod_municipio": "3304557", "capital": "Rio de Janeiro"},
    "RN": {"cod_municipio": "2408102", "capital": "Natal"},
    "RO": {"cod_municipio": "1100205", "capital": "Porto Velho"},
    "RR": {"cod_municipio": "1400100", "capital": "Boa Vista"},
    "RS": {"cod_municipio": "4314902", "capital": "Porto Alegre"},
    "SC": {"cod_municipio": "4205407", "capital": "Florianopolis"},
    "SE": {"cod_municipio": "2800308", "capital": "Aracaju"},
    "SP": {"cod_municipio": "3550308", "capital": "Sao Paulo"},
    "TO": {"cod_municipio": "1721000", "capital": "Palmas"},
}

CAPITAL_POR_CODIGO = {
    meta["cod_municipio"]: meta["capital"]
    for meta in CAPITAIS_UF.values()
}
