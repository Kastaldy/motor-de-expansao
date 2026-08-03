from __future__ import annotations

import pytest

# NOTA DE ESCOPO: helpers de roteamento da cascata de busca que vivem em
# `dashboard/pages.py` (UI Streamlit) — este arquivo sera DELETADO junto com o
# modulo no corte da DEC-022. A cascata pura (data.py / maps_geocoder) segue
# coberta em tests/unit/test_coord_search.py.

# ── helpers de roteamento da cascata (BLK-UI-09, funções de módulo puras) ──────


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://www.google.com/maps/@-23.55,-46.63,15z", True),
        ("http://maps.app.goo.gl/abc", True),
        ("Av. Paulista 1000, Sao Paulo", False),
        ("-23.55,-46.63", False),
        ("", False),
    ],
)
def test_parece_link(raw, expected):
    from motor_expansao.dashboard.pages import _parece_link

    assert _parece_link(raw) is expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://maps.app.goo.gl/abc123", True),
        ("https://goo.gl/maps/xyz", True),
        ("https://www.google.com/maps/place/x/@-23.5,-46.6,17z", False),
        ("Av. Paulista 1000", False),
    ],
)
def test_e_link_curto_maps(raw, expected):
    from motor_expansao.dashboard.pages import _e_link_curto_maps

    assert _e_link_curto_maps(raw) is expected
