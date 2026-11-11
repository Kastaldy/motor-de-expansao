"""O filtro "melhores hexes" do piloto (``FAIXA_FILTROS``) SAIU em 11/11/2026.

Este arquivo travava ``constants.FAIXA_LABELS`` como contrato FUNCIONAL daquele filtro:
ele comparava o rótulo acentuado ("Prioridade máxima" / "Alta" / "Média") como string, e
renomear um label no núcleo esvaziava o mapa em silêncio. O seletor UNIDADES tomou o lugar
do filtro para todos que têm o mapa (pedido do Felipe), e o filtro saiu do código — então o
contrato deixou de existir.

O que fica travado é a SAÍDA: se um filtro que casa rótulo de faixa como string voltar ao
``MapScreen``, a trava de paridade com ``FAIXA_LABELS`` tem de voltar junto.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]  # tests/unit/ -> raiz do worktree
_WEB_SRC = _REPO / "web" / "src"
_MAP_SCREEN = _WEB_SRC / "screens" / "MapScreen.tsx"

pytestmark = pytest.mark.skipif(
    not _WEB_SRC.is_dir(),
    reason="piloto web (web/src) ausente nesta árvore — nada a comparar",
)


def test_o_filtro_por_rotulo_de_faixa_continua_fora_do_mapa() -> None:
    fonte = _MAP_SCREEN.read_text(encoding="utf-8")
    assert "FAIXA_FILTROS" not in fonte and "filtroFaixa" not in fonte, (
        "o filtro por faixa voltou ao MapScreen. Ele compara o rótulo de "
        "constants.FAIXA_LABELS como string: restaure a trava de paridade deste arquivo "
        "(ver o histórico do git), senão renomear um label esvazia o mapa sem erro."
    )
