"""
Testes da Fase A — Ingestao do Censo 2022 por Setor Censitario.

Testa: leitura de CSVs, spatial join ponderado por area, score experimental,
fallback, rastreabilidade, validacao de gates.
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import Polygon, box

from jobs.pipelines.fase_a_censo2022_setores import (
    _hex_polygon,
    _resolve_column,
    adicionar_rastreabilidade,
    aplicar_fallback,
    calcular_score_setor_2022,
    gerar_relatorio,
    juntar_malha_com_atributos,
    ler_basico_setor,
    ler_renda_setor,
    preparar_atributos_setor,
    spatial_join_area_weighted,
    validar_uf,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_dir(tmp_path: Path):
    return tmp_path


@pytest.fixture
def basico_csv(tmp_dir):
    """CSV Basico com V002 (populacao)."""
    path = tmp_dir / "Basico_GO.csv"
    data = "Cod_setor;V002\n520001001000001;1500\n520001001000002;2000\n520001001000003;0\n520001001000004;-5\n"
    path.write_text(data, encoding="latin-1")
    return path


@pytest.fixture
def renda_csv(tmp_dir):
    """CSV DomicilioRenda com V003 (renda total)."""
    path = tmp_dir / "DomicilioRenda_GO.csv"
    data = "Cod_setor;V003\n520001001000001;3000000\n520001001000002;5000000\n520001001000003;100000\n"
    path.write_text(data, encoding="latin-1")
    return path


def _make_hex_df(center_lat: float = -16.68, center_lng: float = -49.25, n: int = 5) -> pd.DataFrame:
    """Cria DataFrame de hexagonos H3-r7 em torno de um ponto."""
    center_hex = h3.latlng_to_cell(center_lat, center_lng, 7)
    neighbors = list(h3.grid_disk(center_hex, 1))[:n]
    records = []
    for hex_id in neighbors:
        lat, lng = h3.cell_to_latlng(hex_id)
        records.append({"hex_id": hex_id, "lat": lat, "lng": lng, "uf": "GO", "regiao": "CO"})
    return pd.DataFrame(records)


def _make_setores_gdf(hex_df: pd.DataFrame) -> gpd.GeoDataFrame:
    """Cria GeoDataFrame de setores falsos que cobrem os hexagonos."""
    setores = []
    for i, row in hex_df.iterrows():
        hex_poly = _hex_polygon(row["hex_id"])
        centroid = hex_poly.centroid
        # Setor um pouco maior que o hex para garantir cobertura
        setor_poly = box(
            centroid.x - 0.05, centroid.y - 0.05,
            centroid.x + 0.05, centroid.y + 0.05,
        )
        setores.append({
            "cod_setor": f"52000100100000{i+1}",
            "geometry": setor_poly,
            "pop_total_setor_2022": 1000 + i * 500,
            "renda_total_setor_2022": 2000000 + i * 1000000,
            "renda_per_capita_setor_2022": (2000000 + i * 1000000) / (1000 + i * 500),
            "area_setor": setor_poly.area,
        })
    return gpd.GeoDataFrame(setores, crs="EPSG:4326")


def _make_base_oficial(n: int = 100) -> pd.DataFrame:
    """Cria base oficial fake para ancoragem de percentis."""
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "renda_per_capita": rng.uniform(500, 5000, n),
        "populacao_proxy": rng.uniform(100, 50000, n),
    })


# ---------------------------------------------------------------------------
# Testes de leitura de CSV
# ---------------------------------------------------------------------------


class TestLerBasicoSetor:
    def test_leitura_valida(self, basico_csv):
        df, info = ler_basico_setor(basico_csv)
        assert len(df) == 2  # setores 3 e 4 descartados (0 e -5)
        assert "cod_setor" in df.columns
        assert "pop_total_setor_2022" in df.columns
        assert info["descartados_pop_invalida"] == 2
        assert (df["pop_total_setor_2022"] > 0).all()

    def test_coluna_nao_encontrada(self, tmp_dir):
        path = tmp_dir / "bad.csv"
        path.write_text("X;Y\n1;2\n", encoding="latin-1")
        with pytest.raises(ValueError, match="codigo de setor"):
            ler_basico_setor(path)


class TestLerRendaSetor:
    def test_leitura_valida(self, renda_csv):
        df, info = ler_renda_setor(renda_csv)
        assert len(df) == 3
        assert "renda_total_setor_2022" in df.columns
        assert info["descartados_renda_invalida"] == 0

    def test_descarta_negativos(self, tmp_dir):
        path = tmp_dir / "renda.csv"
        path.write_text("Cod_setor;V003\n1;-100\n2;500\n", encoding="latin-1")
        df, info = ler_renda_setor(path)
        assert len(df) == 1
        assert info["descartados_renda_invalida"] == 1


class TestPrepararAtributos:
    def test_join_e_renda_per_capita(self, basico_csv, renda_csv):
        df_basico, _ = ler_basico_setor(basico_csv)
        df_renda, _ = ler_renda_setor(renda_csv)
        df = preparar_atributos_setor(df_basico, df_renda)
        assert "renda_per_capita_setor_2022" in df.columns
        assert len(df) == 2  # only setores 1 and 2 survive both
        expected_rpc = 3000000 / 1500
        assert abs(df.iloc[0]["renda_per_capita_setor_2022"] - expected_rpc) < 0.01


# ---------------------------------------------------------------------------
# Testes de resolucao de coluna
# ---------------------------------------------------------------------------


class TestResolveColumn:
    def test_match_exato(self):
        df = pd.DataFrame({"V002": [1], "other": [2]})
        assert _resolve_column(df, ("V002",), "test") == "V002"

    def test_match_case_insensitive(self):
        df = pd.DataFrame({"v002": [1]})
        assert _resolve_column(df, ("V002",), "test") == "v002"

    def test_nao_encontrada(self):
        df = pd.DataFrame({"X": [1]})
        with pytest.raises(ValueError):
            _resolve_column(df, ("V002",), "test")


# ---------------------------------------------------------------------------
# Testes de spatial join
# ---------------------------------------------------------------------------


class TestSpatialJoin:
    def test_join_com_cobertura(self):
        hex_df = _make_hex_df(n=3)
        gdf_setores = _make_setores_gdf(hex_df)
        result = spatial_join_area_weighted(hex_df, gdf_setores)

        assert len(result) == len(hex_df)
        assert "pop_total_setor_2022" in result.columns
        assert "renda_per_capita_setor_2022" in result.columns
        assert "coverage_pct_setor_2022" in result.columns
        assert "n_setores_contribuintes" in result.columns

        # Todos os hexagonos devem ter match (setores cobrem)
        assert (result["n_setores_contribuintes"] > 0).all()
        assert (result["coverage_pct_setor_2022"] > 0).all()

    def test_join_sem_setores(self):
        hex_df = _make_hex_df(n=2)
        # Setores em lugar nenhum perto
        gdf_empty = gpd.GeoDataFrame(
            [{
                "cod_setor": "999",
                "geometry": box(100, 100, 101, 101),  # longe
                "pop_total_setor_2022": 1000,
                "renda_total_setor_2022": 2000000,
                "renda_per_capita_setor_2022": 2000.0,
                "area_setor": 1.0,
            }],
            crs="EPSG:4326",
        )
        result = spatial_join_area_weighted(hex_df, gdf_empty)
        assert len(result) == len(hex_df)
        assert result["n_setores_contribuintes"].sum() == 0

    def test_hex_polygon_valido(self):
        hex_id = h3.latlng_to_cell(-16.68, -49.25, 7)
        poly = _hex_polygon(hex_id)
        assert isinstance(poly, Polygon)
        assert poly.is_valid
        assert poly.area > 0


# ---------------------------------------------------------------------------
# Testes de fallback
# ---------------------------------------------------------------------------


class TestFallback:
    def test_marca_baixa_cobertura(self):
        df = pd.DataFrame({
            "hex_id": ["a", "b", "c"],
            "coverage_pct_setor_2022": [5.0, 50.0, 95.0],
            "pop_total_setor_2022": [100, 200, 300],
            "renda_per_capita_setor_2022": [1000, 2000, 3000],
            "n_setores_contribuintes": [1, 2, 3],
        })
        result = aplicar_fallback(df, threshold=0.10)
        assert result.loc[0, "fallback_setor_2022"] == True
        assert pd.isna(result.loc[0, "pop_total_setor_2022"])
        assert result.loc[1, "fallback_setor_2022"] == False
        assert result.loc[2, "fallback_setor_2022"] == False
        assert result.loc[1, "pop_total_setor_2022"] == 200


# ---------------------------------------------------------------------------
# Testes de score experimental
# ---------------------------------------------------------------------------


class TestScoreSetor2022:
    def test_calculo_com_ancoragem(self):
        df = pd.DataFrame({
            "pop_total_setor_2022": [1000, 5000, 20000],
            "renda_per_capita_setor_2022": [800, 2500, 4500],
            "fallback_setor_2022": [False, False, False],
            "n_setores_contribuintes": [2, 3, 4],
        })
        base = _make_base_oficial(200)
        result = calcular_score_setor_2022(df, base_nacional=base)

        assert "score_setor_2022_exp" in result.columns
        assert "renda_pct_setor" in result.columns
        assert "pop_pct_setor" in result.columns
        assert "percentil_escopo" in result.columns
        assert result["percentil_escopo"].iloc[0] == "nacional_m1"

        # Score deve estar entre 0 e 100
        scores = result["score_setor_2022_exp"].dropna()
        assert (scores >= 0).all()
        assert (scores <= 100).all()

    def test_fallback_nao_recebe_score(self):
        df = pd.DataFrame({
            "pop_total_setor_2022": [1000, np.nan],
            "renda_per_capita_setor_2022": [2500, np.nan],
            "fallback_setor_2022": [False, True],
            "n_setores_contribuintes": [2, 0],
        })
        result = calcular_score_setor_2022(df)
        assert pd.notna(result.loc[0, "score_setor_2022_exp"])
        assert pd.isna(result.loc[1, "score_setor_2022_exp"])

    def test_calculo_sem_base_nacional(self):
        df = pd.DataFrame({
            "pop_total_setor_2022": [1000, 5000],
            "renda_per_capita_setor_2022": [800, 2500],
            "fallback_setor_2022": [False, False],
            "n_setores_contribuintes": [2, 3],
        })
        result = calcular_score_setor_2022(df, base_nacional=None)
        assert result["percentil_escopo"].iloc[0] == "local_subconjunto"
        assert result["score_setor_2022_exp"].notna().all()


# ---------------------------------------------------------------------------
# Testes de rastreabilidade
# ---------------------------------------------------------------------------


class TestRastreabilidade:
    def test_colunas_presentes(self):
        df = pd.DataFrame({
            "hex_id": ["a", "b"],
            "n_setores_contribuintes": [2, 0],
        })
        result = adicionar_rastreabilidade(df, "2026-04-08")
        for col in ["fonte_setor_2022", "data_referencia_setor_2022",
                     "metodo_agregacao_setor_2022", "qualidade_setor_2022"]:
            assert col in result.columns

        # Hex com match tem rastreabilidade
        assert result.loc[0, "fonte_setor_2022"] == "IBGE_Censo2022_Setores"
        assert result.loc[0, "qualidade_setor_2022"] == "gold"
        # Hex sem match tem nulo
        assert pd.isna(result.loc[1, "fonte_setor_2022"])


# ---------------------------------------------------------------------------
# Testes de validacao
# ---------------------------------------------------------------------------


class TestValidarUF:
    def test_go_com_dados_bons(self):
        rng = np.random.default_rng(42)
        n = 100
        df = pd.DataFrame({
            "n_setores_contribuintes": np.full(n, 3),
            "score_setor_2022_exp": rng.uniform(10, 90, n),
            "coverage_pct_setor_2022": np.full(n, 80.0),
            "fonte_setor_2022": ["IBGE_Censo2022_Setores"] * n,
            "data_referencia_setor_2022": ["2026-04-08"] * n,
        })
        result = validar_uf(df, "GO")
        assert result["status"] == "GO"
        assert result["gate_cobertura"] == True
        assert result["gate_amplitude"] == True
        assert result["gate_nulos"] == True

    def test_falha_cobertura(self):
        n = 100
        df = pd.DataFrame({
            "n_setores_contribuintes": [3] * 50 + [0] * 50,
            "score_setor_2022_exp": list(range(50)) + [np.nan] * 50,
            "coverage_pct_setor_2022": [80.0] * 50 + [0.0] * 50,
            "fonte_setor_2022": ["IBGE_Censo2022_Setores"] * 50 + [pd.NA] * 50,
            "data_referencia_setor_2022": ["2026-04-08"] * 50 + [pd.NA] * 50,
        })
        result = validar_uf(df, "GO")
        assert result["cobertura_pct"] == 50.0
        assert result["gate_cobertura"] == False

    def test_vazio(self):
        df = pd.DataFrame(columns=["n_setores_contribuintes", "score_setor_2022_exp",
                                    "coverage_pct_setor_2022", "fonte_setor_2022",
                                    "data_referencia_setor_2022"])
        result = validar_uf(df, "GO")
        assert result["status"] == "NO-GO"


# ---------------------------------------------------------------------------
# Teste de relatorio
# ---------------------------------------------------------------------------


class TestRelatorio:
    def test_gera_markdown(self):
        validacoes = [{
            "uf": "GO",
            "total_hex": 100,
            "hex_com_match": 95,
            "cobertura_pct": 95.0,
            "amplitude_p95_p05": 65.0,
            "std_score": 20.0,
            "valores_distintos": 80,
            "pct_nulos_rastreio": 0.0,
            "gate_cobertura": True,
            "gate_amplitude": True,
            "gate_nulos": True,
            "status": "GO",
            "ref_2010_cobertura": 100.0,
            "ref_2010_amplitude": 71.47,
        }]
        df = pd.DataFrame({"score_setor_2022_exp": np.random.default_rng(42).uniform(10, 90, 100)})
        info = {"por_uf": {"GO": {"setores_basico": 5000, "setores_renda": 4800,
                                   "setores_join": 4500, "descartados_pop": 50,
                                   "descartados_renda": 30}}}
        relatorio = gerar_relatorio(validacoes, info, df)
        assert "Fase A" in relatorio
        assert "GO" in relatorio
        assert "PASS" in relatorio
        assert "score_setor_2022_exp" in relatorio


# ---------------------------------------------------------------------------
# Teste de juntar malha com atributos
# ---------------------------------------------------------------------------


class TestJuntarMalha:
    def test_join_valido(self):
        gdf = gpd.GeoDataFrame({
            "cod_setor": ["001", "002"],
            "geometry": [box(0, 0, 1, 1), box(1, 0, 2, 1)],
        }, crs="EPSG:4326")
        df_attr = pd.DataFrame({
            "cod_setor": ["001", "002"],
            "pop_total_setor_2022": [1000, 2000],
            "renda_total_setor_2022": [3000000, 5000000],
            "renda_per_capita_setor_2022": [3000.0, 2500.0],
        })
        result = juntar_malha_com_atributos(gdf, df_attr)
        assert "area_setor" in result.columns
        assert len(result) == 2

    def test_join_vazio_levanta_erro(self):
        gdf = gpd.GeoDataFrame({
            "cod_setor": ["001"],
            "geometry": [box(0, 0, 1, 1)],
        }, crs="EPSG:4326")
        df_attr = pd.DataFrame({
            "cod_setor": ["999"],
            "pop_total_setor_2022": [1000],
            "renda_total_setor_2022": [3000000],
            "renda_per_capita_setor_2022": [3000.0],
        })
        with pytest.raises(ValueError, match="vazio"):
            juntar_malha_com_atributos(gdf, df_attr)
