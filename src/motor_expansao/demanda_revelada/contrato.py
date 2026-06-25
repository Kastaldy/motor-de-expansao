"""Contrato canônico da camada de Demanda Revelada (H3, sem PII).

Fonte única de verdade do schema de saída (`data/staging/demanda_revelada_h3.parquet`).
SEM I/O e SEM dependências do M1 — apenas constantes puras (BLK-TP-01 / DEC-012).

READ-ONLY sobre o M1: nada aqui recalcula `score_priorizacao`/pesos/artefatos oficiais.
A demanda é insumo OBSERVADO (DEC-009), NUNCA preditor geográfico de magnitude.
"""

from __future__ import annotations

# Carimbo de reprodutibilidade do contrato (gravado em todas as linhas do parquet).
VERSAO_CONTRATO = "demanda_revelada_v1"

# Resolução H3 da chave de join com o Motor (mesma do M1: H3_RESOLUTION=7).
H3_RES_CONTRATO = 7

# Ordem e dtypes canônicos do parquet de saída (9 colunas genéricas do backlog).
# Nomes GENÉRICOS (não acoplados à marca Smart Fit): "concorrente_lc" = concorrente
# low-cost de referência (CLAUDE.md §1).
CONTRATO_COLUNAS: dict[str, str] = {
    "hex_id": "string",                          # H3 res-7 (chave de join)
    "membros": "int64",                          # demanda paga agregada ao hex
    "membros_gt5km_concorrente_lc": "int64",     # subconjunto a >5km do concorrente LC
    "dist_concorrente_lc_min_m": "float64",      # menor dist. ao concorrente LC no hex (m)
    "n_celulas_agregadas": "int64",              # nº de células de origem agregadas
    "n_acad_parceiras": "int64",                 # academias parceiras no hex
    "alunos_parceiras": "int64",                 # soma de alunos das parceiras
    "n_concorrente_lc": "int64",                 # unidades do concorrente LC no hex
    "versao_contrato": "string",                 # carimbo de reprodutibilidade
}

# Colunas PROIBIDAS no artefato de saída. O teste anti-PII falha se QUALQUER uma
# destas aparecer no parquet. A anti-PII é por construção (a ingestão só lê células
# já agregadas), e esta lista é a rede de segurança automatizada.
COLUNAS_PII_PROIBIDAS: frozenset[str] = frozenset(
    {
        "employee_id",
        "company_id",
        "cpf",
        "email",
        "telefone",
        "nome",
        "lat",
        "lng",
        "latitude",
        "longitude",
        "lat_residencial",
        "lng_residencial",
        "sf_nome",
        "id",
        "membro_id",
    }
)

__all__ = [
    "VERSAO_CONTRATO",
    "H3_RES_CONTRATO",
    "CONTRATO_COLUNAS",
    "COLUNAS_PII_PROIBIDAS",
]
