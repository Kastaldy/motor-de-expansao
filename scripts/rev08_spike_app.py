"""rev08_spike_app.py — LANÇADOR standalone do spike (BLK-REV-08), DESCARTÁVEL.

Serve APENAS a página opt-in `render_spike_page()` do protótipo deck.gl. NÃO é
importado por produção (`pages.py`/`streamlit_app.py` não o importam); é a rota
de medição isolada. Remover junto com o spike após a decisão do BLK-REV-12.

Uso:
    streamlit run scripts/rev08_spike_app.py

READ-ONLY sobre o M1: não recalcula/altera score/pesos/artefatos oficiais.
"""
from __future__ import annotations

import os

# Liga o opt-in antes de importar o módulo do spike.
os.environ.setdefault("ULTRA_SPIKE_DECKGL", "1")

import streamlit as st  # noqa: E402

from motor_expansao.dashboard.ui_spike_deckgl import (  # noqa: E402
    is_spike_enabled,
    render_spike_page,
)

st.set_page_config(
    page_title="Ultra Spike deck.gl (BLK-REV-08)",
    layout="wide",
)

if is_spike_enabled():
    render_spike_page()
else:
    st.error(
        "Spike desabilitado. Defina `ULTRA_SPIKE_DECKGL=1` no ambiente "
        "antes de rodar `streamlit run scripts/rev08_spike_app.py`."
    )
