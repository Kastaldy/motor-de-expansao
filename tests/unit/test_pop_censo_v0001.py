"""
Testes de regressao para correcao do undercount em pop_total_setor_2022.

Bug corrigido em 2026-05-15:
  - v0001 = "Total de pessoas" (populacao total do setor) — variavel CORRETA
  - v0002 = "Total de Domicilios" (nao populacao) — estava sendo usada ERRADO
  - Impacto: pop_total_setor_2022 era ~44% do valor real (aprox. 2.3x undercount)
"""

from __future__ import annotations

import geopandas as gpd
import h3
import pandas as pd
import pytest
from shapely.geometry import Polygon

from jobs.pipelines.fase_a_censo2022_setores import (
    POP_V002_CANDIDATES,
    _resolve_column,
    spatial_join_area_weighted,
)


def _hex_polygon(hex_id: str) -> Polygon:
    boundary = h3.cell_to_boundary(hex_id)
    return Polygon([(lng, lat) for lat, lng in boundary])


# ---------------------------------------------------------------------------
# Teste 1: POP_V002_CANDIDATES prioriza v0001
# ---------------------------------------------------------------------------


def test_pop_candidates_prioriza_v0001():
    """v0001 deve ser a primeira candidata para populacao total."""
    assert POP_V002_CANDIDATES[0].lower() == "v0001", (
        "v0001 deve ser a primeira candidata: "
        f"POP_V002_CANDIDATES = {POP_V002_CANDIDATES}"
    )


def test_resolve_column_escolhe_v0001_quando_disponivel():
    """_resolve_column deve retornar v0001 quando a coluna existe no DataFrame."""
    df = pd.DataFrame({"v0001": [100, 200], "v0002": [50, 80]})
    col = _resolve_column(df, POP_V002_CANDIDATES, "populacao")
    assert col == "v0001", f"Esperado v0001, obtido {col}"


def test_resolve_column_fallback_para_v0002_quando_v0001_ausente():
    """Compatibilidade retroativa: se v0001 ausente, deve aceitar variantes legadas."""
    df = pd.DataFrame({"V002": [100, 200]})
    col = _resolve_column(df, POP_V002_CANDIDATES, "populacao")
    assert col == "V002"


# ---------------------------------------------------------------------------
# Teste 2: spatial_join agrega TODOS os setores contribuintes (nao apenas o maior)
# ---------------------------------------------------------------------------


def _make_tiny_sector(center_lat: float, center_lng: float,
                      delta: float, pop: float, renda_pc: float) -> dict:
    return {
        "cod_setor": f"setor_{center_lat}_{center_lng}",
        "geometry": Polygon([
            (center_lng - delta, center_lat - delta),
            (center_lng + delta, center_lat - delta),
            (center_lng + delta, center_lat + delta),
            (center_lng - delta, center_lat + delta),
        ]),
        "pop_total_setor_2022": pop,
        "renda_per_capita_setor_2022": renda_pc,
        "renda_total_setor_2022": pop * renda_pc,
    }


@pytest.fixture()
def hex_com_dois_setores():
    """
    Monta um hex real de res7 em Goiania com dois setores censitarios sinteticos
    que cobrem partes distintas do hex.
    """
    # Hex em Goiania (GO)
    hex_id = h3.latlng_to_cell(-16.6864, -49.2643, 7)
    hex_geom = _hex_polygon(hex_id)
    centroid = hex_geom.centroid

    # Setor 1: cobre metade esquerda do hex com 1000 pessoas
    bounds = hex_geom.bounds  # (minx, miny, maxx, maxy)
    mid_x = (bounds[0] + bounds[2]) / 2
    setor1_geom = Polygon([
        (bounds[0] - 0.01, bounds[1] - 0.01),
        (mid_x, bounds[1] - 0.01),
        (mid_x, bounds[3] + 0.01),
        (bounds[0] - 0.01, bounds[3] + 0.01),
    ])
    # Setor 2: cobre metade direita com 2000 pessoas
    setor2_geom = Polygon([
        (mid_x, bounds[1] - 0.01),
        (bounds[2] + 0.01, bounds[1] - 0.01),
        (bounds[2] + 0.01, bounds[3] + 0.01),
        (mid_x, bounds[3] + 0.01),
    ])

    # Area dos setores em degrees^2
    area_s1 = setor1_geom.area
    area_s2 = setor2_geom.area

    records = [
        {
            "cod_setor": "setor_1",
            "geometry": setor1_geom,
            "pop_total_setor_2022": 1000.0,
            "renda_per_capita_setor_2022": 2000.0,
            "renda_total_setor_2022": 2_000_000.0,
            "area_setor": area_s1,
        },
        {
            "cod_setor": "setor_2",
            "geometry": setor2_geom,
            "pop_total_setor_2022": 2000.0,
            "renda_per_capita_setor_2022": 3000.0,
            "renda_total_setor_2022": 6_000_000.0,
            "area_setor": area_s2,
        },
    ]
    gdf_setores = gpd.GeoDataFrame(records, crs="EPSG:4326")
    df_hex = pd.DataFrame({"hex_id": [hex_id], "lat": [centroid.y], "lng": [centroid.x]})
    return hex_id, df_hex, gdf_setores


def test_spatial_join_soma_todos_setores(hex_com_dois_setores):
    """
    spatial_join_area_weighted deve somar contribuicoes de TODOS os setores
    que intersectam o hex, nao apenas o primeiro ou o maior.
    """
    hex_id, df_hex, gdf_setores = hex_com_dois_setores
    result = spatial_join_area_weighted(df_hex, gdf_setores)

    row = result[result["hex_id"] == hex_id].iloc[0]

    # Deve ter encontrado 2 setores contribuintes
    assert row["n_setores_contribuintes"] == 2, (
        f"Esperado 2 setores, obtido {row['n_setores_contribuintes']}"
    )

    # Populacao deve ser >= 1000 (soma das duas contribuicoes)
    # Cada setor divide a area do hex ao meio, entao contribuicao proporcional
    assert row["pop_total_setor_2022"] > 500, (
        f"Populacao muito baixa: {row['pop_total_setor_2022']:.1f} — "
        "provavel bug de agregacao: apenas 1 setor sendo somado"
    )

    # Coverage deve ser proximo de 100%
    assert row["coverage_pct_setor_2022"] > 80.0, (
        f"Coverage inesperado: {row['coverage_pct_setor_2022']:.1f}%"
    )


def test_spatial_join_sem_duplicacao_de_populacao(hex_com_dois_setores):
    """
    Populacao total agregada nao deve exceder a soma das populacoes dos setores.
    Garante que cada setor e contado somente uma vez.
    """
    hex_id, df_hex, gdf_setores = hex_com_dois_setores
    result = spatial_join_area_weighted(df_hex, gdf_setores)

    row = result[result["hex_id"] == hex_id].iloc[0]
    pop_sum_setores = float(gdf_setores["pop_total_setor_2022"].sum())  # 3000

    # pop do hex deve ser <= soma dos setores (nunca mais por duplicacao)
    assert row["pop_total_setor_2022"] <= pop_sum_setores + 1.0, (
        f"Pop do hex {row['pop_total_setor_2022']:.1f} excede soma dos setores "
        f"{pop_sum_setores:.1f} — possivel dupla contagem"
    )


# ---------------------------------------------------------------------------
# Teste 3: v0001 vs v0002 — verificacao numerica de escala
# ---------------------------------------------------------------------------


def test_v0001_e_populacao_total_nao_domicilios():
    """
    Valida que v0001 contem populacao total (escala de pessoas) e nao de domicilios.
    Para SP, v0001 sum deve ser ~44.4M (IBGE 2022); v0002 sum ~19.6M (domicilios).
    Este teste usa dados reais do parquet de piloto se disponivel.
    """
    import os
    parquet_path = "data/staging/censo2022_setores_h3_res7.parquet"
    if not os.path.exists(parquet_path):
        pytest.skip("Parquet de piloto nao disponivel — pular teste de integracao")

    df = pd.read_parquet(parquet_path)
    sp = df[df["uf"] == "SP"]

    pop_sum = sp["pop_total_setor_2022"].sum()

    # Apos correcao, a soma deve ser proximo do total IBGE (44.4M)
    # Antes da correcao era ~19.6M (v0002 = domicilios)
    # Usamos threshold de 35M para detectar regressao ao estado com bug
    assert pop_sum > 35_000_000, (
        f"pop_total_setor_2022 soma para SP = {pop_sum:,.0f}. "
        "Valor abaixo de 35M indica que v0002 (domicilios) esta sendo usado "
        "ao inves de v0001 (populacao total). Regerar parquet apos correcao."
    )
