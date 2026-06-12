"""Pacote da API GeoEspacial (on-demand) — BLK-API-02.

Camada paralela de consumo do Motor de Expansao. READ-ONLY sobre o M1:
importa `censo_*` mas nunca os edita, e nao recalcula nenhum artefato oficial.
Contrato: docs/api_geoespacial_contrato.md (DEC-005).
"""

__all__ = ["__version__"]

# Carimbo de versao do contrato (Decisao 6). Usado no /health e nos payloads.
__version__ = "api-geoespacial/v1"
