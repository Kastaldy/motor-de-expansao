"""O critério de renda da ficha do ponto manda a sentinela da RENDA, não o símbolo.

Achado a-03 da conferência de 2026-10-29 (defeito S4 de
`docs/expansao-latam/00-baseline-argentina.md`): `_criterios_do_ponto` mandava `"R$"` como
unidade da renda, e a tela o escrevia cravado, também sobre a renda em DÓLAR da Argentina.
Agora vai a sentinela `UNIDADE_RENDA` de `web/src/lib/format.ts`, e a tela escolhe o símbolo
pelo perfil (`moedaRenda()`).

A RÉGUA (`RENDA_MIN`, em reais) segue a mesma nos dois países: é o S1 do baseline, ainda
aberto, e este teste não o trava.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_SERVER = _REPO / "web" / "server"
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

import app as pilot  # noqa: E402  (backend do piloto; web/server no sys.path acima)


def _sentinela_da_tela() -> str:
    texto = (_REPO / "web" / "src" / "lib" / "format.ts").read_text(encoding="utf-8")
    m = re.search(r"export const UNIDADE_RENDA = '([^']+)'", texto)
    assert m, "UNIDADE_RENDA sumiu de web/src/lib/format.ts"
    return m.group(1)


def test_a_renda_vai_com_a_sentinela_que_a_tela_conhece() -> None:
    itens = pilot._criterios_do_ponto(
        {"populacao": 9000, "renda_media_domiciliar": 5200.0, "score_socioeconomico": 61.0},
        {},
        {},
    )
    renda = {c["chave"]: c for c in itens}["renda_domiciliar"]
    assert renda["unidade"] == _sentinela_da_tela()
    assert "R$" not in {c["unidade"] for c in itens}, "o símbolo voltou a ser chave de despacho"
