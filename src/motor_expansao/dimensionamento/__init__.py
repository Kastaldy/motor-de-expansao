"""Camada PARALELA de Dimensionamento e Viabilidade (epic BLK-DIM).

READ-ONLY sobre o M1: nao recalcula `score_priorizacao`, `hex_score_estrutural`,
pesos, carteira, plano nem artefatos oficiais do M1 (DEC-001). Apenas materializa
fundacao de dados em staging (Parquet/JSON) a partir da Growth API, do catchment
censitario e do simulador financeiro.
"""
