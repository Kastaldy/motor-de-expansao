from __future__ import annotations

import pandas as pd

from motor_expansao.dashboard.competitors import ULTRA_COLUMNS
from motor_expansao.dashboard.components import _build_ultra_icon_layer

# NOTA DE ESCOPO: este arquivo cobre APENAS `components._build_ultra_icon_layer`
# (camada pydeck da UI Streamlit, que morre no corte da DEC-022). A cobertura do
# motor compartilhado de logos/pins vive em tests/unit/test_competitors_pins.py.

# ── helpers ────────────────────────────────────────────────────────────────────


def _make_ultra_df(n: int = 2) -> pd.DataFrame:
    return pd.DataFrame({
        "nome_unidade": [f"Unidade {i}" for i in range(n)],
        "lat": [-23.55 - i * 0.01 for i in range(n)],
        "lng": [-46.63 - i * 0.01 for i in range(n)],
        "cidade": ["Sao Paulo"] * n,
        "uf": ["SP"] * n,
        "arquivo_origem": ["Ultra.csv"] * n,
    })


def _make_reference_df() -> pd.DataFrame:
    return pd.DataFrame({
        "lat": [-23.54, -23.56],
        "lng": [-46.62, -46.64],
    })


# ── _build_ultra_icon_layer ────────────────────────────────────────────────────


def test_build_ultra_icon_layer_retorna_layer_valido():
    layer = _build_ultra_icon_layer(_make_ultra_df(), _make_reference_df())
    assert layer is not None


def test_build_ultra_icon_layer_ultra_vazio_retorna_none():
    layer = _build_ultra_icon_layer(pd.DataFrame(columns=ULTRA_COLUMNS), _make_reference_df())
    assert layer is None


def test_build_ultra_icon_layer_ultra_none_retorna_none():
    layer = _build_ultra_icon_layer(None, _make_reference_df())
    assert layer is None


def test_build_ultra_icon_layer_reference_vazia_retorna_none():
    layer = _build_ultra_icon_layer(_make_ultra_df(), pd.DataFrame())
    assert layer is None


def test_build_ultra_icon_layer_filtra_fora_do_bounding_box():
    ultra = pd.DataFrame({
        "nome_unidade": ["Distante"],
        "lat": [5.0],
        "lng": [-46.63],
        "cidade": ["Manaus"],
        "uf": ["AM"],
        "arquivo_origem": ["Ultra.csv"],
    })
    layer = _build_ultra_icon_layer(ultra, _make_reference_df())
    assert layer is None


def test_build_ultra_icon_layer_usa_atlas():
    """_build_ultra_icon_layer produz layer com icon_atlas/icon_mapping e get_icon
    apontando para a chave (sem icon_data por linha)."""
    layer = _build_ultra_icon_layer(_make_ultra_df(), _make_reference_df())
    assert layer is not None
    assert layer.icon_atlas is not None
    assert layer.icon_mapping is not None
    assert "__ultra__" in layer.icon_mapping
    assert str(layer.get_icon) in ("icon_key", "@@=icon_key")
    payload = pd.DataFrame(layer.data)
    assert "icon_data" not in payload.columns
    assert "icon_key" in payload.columns
