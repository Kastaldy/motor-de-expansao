"""
tests/conftest.py — Fixtures globais do pytest

Disponíveis em todos os testes sem importação explícita.
"""

import os
import uuid
from pathlib import Path

import pytest
import pandas as pd

# Garantir modo de teste
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://ultra:ultra123@localhost:5432/motor_expansao_test")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql+psycopg2://ultra:ultra123@localhost:5432/motor_expansao_test")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("H3_RESOLUTION", "7")
os.environ.setdefault("DIST_MIN_ULTRA_KM", "1.0")
os.environ.setdefault("RENDA_MIN", "4500")
os.environ.setdefault("AREA_MIN_M2", "1200")
os.environ.setdefault("M1_SCORE_OFICIAL", "score_priorizacao")
os.environ.setdefault("M1_PRIORIZACAO_TOP_PCT_POR_UF", "0.20")
os.environ.setdefault("M1_OSM_ENABLED", "false")


@pytest.fixture
def tmp_path():
    """Workspace-local tmp path for sandboxes where the OS temp dir is restricted."""
    root = Path("tmp_codex_runtime") / "manual_pytest"
    root.mkdir(parents=True, exist_ok=True)
    path = root / uuid.uuid4().hex
    path.mkdir()
    return path


@pytest.fixture
def imovel_base():
    """Imóvel válido base para testes."""
    return {
        "area_m2": 1500.0,
        "lat": -23.55,
        "lng": -46.63,
        "preco_aluguel": 75_000.0,
        "cidade": "São Paulo",
        "uf": "SP",
        "tem_estacionamento": True,
        "tem_fachada": True,
        "dist_ultra_mais_proxima_km": 5.0,
        "fonte": "zap",
    }


@pytest.fixture
def df_imoveis_misto():
    """DataFrame com mix de imóveis válidos e inválidos."""
    return pd.DataFrame([
        # Válidos
        {"area_m2": 900,  "lat": -23.55, "lng": -46.63, "preco_aluguel": 45_000, "cidade": "São Paulo", "dist_ultra_mais_proxima_km": 5.0},
        {"area_m2": 1200, "lat": -22.91, "lng": -43.17, "preco_aluguel": 60_000, "cidade": "Rio de Janeiro", "dist_ultra_mais_proxima_km": 3.0},
        # Inválidos
        {"area_m2": 300,  "lat": -23.55, "lng": -46.63, "preco_aluguel": 15_000, "cidade": "São Paulo", "dist_ultra_mais_proxima_km": 5.0},
        {"area_m2": 800,  "lat": None,   "lng": None,   "preco_aluguel": 40_000, "cidade": "São Paulo", "dist_ultra_mais_proxima_km": 5.0},
        {"area_m2": 700,  "lat": -23.55, "lng": -46.63, "preco_aluguel": None,   "cidade": "São Paulo", "dist_ultra_mais_proxima_km": 5.0},
    ])


@pytest.fixture
def df_hexagonos_sample():
    """DataFrame de hexágonos para testes de scoring."""
    return pd.DataFrame({
        "hex_id": [f"8a2a{i:07x}fffff" for i in range(5)],
        "renda_media": [8_000, 5_000, 3_000, 1_500, 10_000],
        "pop_total": [20_000, 12_000, 8_000, 3_000, 25_000],
        "n_concorrentes": [0, 1, 3, 5, 0],
        "cidade": ["São Paulo"] * 5,
        "uf": ["SP"] * 5,
    })


@pytest.fixture
def unidades_ultra_coords():
    """Coordenadas fictícias de unidades Ultra para testes de anti-canibalização."""
    return [
        (-23.55, -46.63),  # São Paulo centro
        (-22.91, -43.17),  # Rio
        (-15.78, -47.93),  # Brasília
    ]
