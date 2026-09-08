"""Trava a paridade da paleta de score entre o núcleo Python e o piloto web.

A rampa de 10 faixas existe DUAS vezes, como cópia manual — não há import nem
geração de código entre as duas linguagens:

  - Python: ``constants.RESIDUAL_SCORE_BANDS`` -> colore os PDFs que o piloto emite;
  - TypeScript: ``SCORE_BANDS_HEX`` (``web/src/lib/colors.ts``) -> colore o mapa deck.gl.

O teste de front (``web/src/lib/colors.test.ts``) repete os mesmos literais em JS,
então fica VERDE mesmo se o Python mudar. Este teste lê o ``.ts`` e compara banda a
banda com o Python: sem ele, mexer num lado só faz o mapa web e o PDF divergirem em
silêncio. Ele NÃO define a paleta — apenas trava que as duas cópias andem juntas.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from motor_expansao.dashboard.constants import RESIDUAL_SCORE_BANDS

_REPO = Path(__file__).resolve().parents[2]  # tests/unit/ -> raiz do worktree
_WEB_SRC = _REPO / "web" / "src"
_COLORS_TS = _WEB_SRC / "lib" / "colors.ts"

# `export const SCORE_BANDS_HEX = [ ... ] as const` (com ou sem anotação de tipo).
_BLOCO_RE = re.compile(
    r"export\s+const\s+SCORE_BANDS_HEX\s*(?::[^=]+)?=\s*\[(?P<corpo>[^\]]*)\]",
    re.DOTALL,
)
_HEX_RE = re.compile(r"""['"]\s*(#[0-9A-Fa-f]{6})\s*['"]""")

# O piloto web só existe na branch do piloto; sem ele não há paridade a travar.
pytestmark = pytest.mark.skipif(
    not _WEB_SRC.is_dir(),
    reason="piloto web (web/src) ausente nesta árvore — nada a comparar",
)


def _paleta_web() -> list[str]:
    """Hex de `SCORE_BANDS_HEX`, na ordem em que aparecem no colors.ts."""
    assert _COLORS_TS.is_file(), (
        f"{_COLORS_TS.relative_to(_REPO).as_posix()} não existe, mas web/src existe.\n"
        "Se o arquivo foi movido/renomeado, atualize ESTE teste — ele é a única trava "
        "entre a paleta do mapa web e a do núcleo Python (RESIDUAL_SCORE_BANDS)."
    )
    fonte = _COLORS_TS.read_text(encoding="utf-8")
    bloco = _BLOCO_RE.search(fonte)
    assert bloco is not None, (
        "não achei o array `export const SCORE_BANDS_HEX = [...]` em "
        f"{_COLORS_TS.relative_to(_REPO).as_posix()}.\n"
        "Se a constante mudou de nome/formato, atualize este teste — sem ele a paleta "
        "do mapa web e a dos PDFs divergem em silêncio."
    )
    return _HEX_RE.findall(bloco.group("corpo"))


def test_paleta_web_tem_as_mesmas_10_faixas() -> None:
    web = _paleta_web()
    nucleo = [cor for _faixa, cor in RESIDUAL_SCORE_BANDS]
    assert len(web) == len(nucleo), (
        f"a paleta do piloto web tem {len(web)} faixas e RESIDUAL_SCORE_BANDS tem "
        f"{len(nucleo)}.\n"
        "constants.RESIDUAL_SCORE_BANDS (colore o PDF) e SCORE_BANDS_HEX em "
        "web/src/lib/colors.ts (colore o mapa deck.gl) são cópias manuais: precisam "
        "andar juntas, faixa a faixa, na mesma ordem."
    )


def test_paleta_web_bate_cor_a_cor_com_residual_score_bands() -> None:
    web = _paleta_web()
    divergencias = [
        f"  faixa {faixa} (índice {i}): RESIDUAL_SCORE_BANDS={cor_py} != SCORE_BANDS_HEX={web[i]}"
        for i, (faixa, cor_py) in enumerate(RESIDUAL_SCORE_BANDS)
        if i < len(web) and cor_py.upper() != web[i].upper()
    ]
    assert not divergencias, (
        "a paleta de score DIVERGIU entre o núcleo Python e o piloto web:\n"
        + "\n".join(divergencias)
        + "\n\nOs dois arquivos precisam andar juntos (são cópias manuais, sem import):\n"
        "  - src/motor_expansao/dashboard/constants.py -> RESIDUAL_SCORE_BANDS (PDF)\n"
        "  - web/src/lib/colors.ts -> SCORE_BANDS_HEX (mapa deck.gl do piloto)\n"
        "Ajuste o lado que ficou para trás; não mude a paleta sem decisão explícita."
    )


# ---------------------------------------------------------------------------
# Bloco D — faixas ABSOLUTAS de densidade/renda de setor (mapa de calor opcional).
# Mesma lógica de paridade acima, formato diferente: cada item é
# `[corte_superior, 'rótulo', [r, g, b, a]]`, e a última faixa usa infinito.
# ---------------------------------------------------------------------------

from motor_expansao.dashboard.constants import (  # noqa: E402
    DENSIDADE_POP_BANDS,
    RENDA_PER_CAPITA_BANDS,
)

_FAIXA_ABS_ITEM_RE = re.compile(
    # O rotulo pode ser string simples ('...') ou template literal (`...`, quando
    # interpola moedaRenda() — ver RENDA_SETOR_BANDS). O teste nao checa o TEXTO do
    # rotulo, so' precisa transpor-lo para chegar no corte e na cor.
    r"\[\s*(?P<corte>[\d_]+|Infinity)\s*,\s*(?:'[^']*'|`[^`]*`)\s*,\s*"
    r"\[\s*(?P<r>\d+)\s*,\s*(?P<g>\d+)\s*,\s*(?P<b>\d+)\s*,\s*(?P<a>\d+)\s*\]\s*\]"
)


def _faixas_absolutas_web(nome_const: str) -> list[tuple[float, tuple[int, int, int, int]]]:
    """Lê `[corte, 'rotulo', [r,g,b,a]]` de uma constante TS de `colors.ts`."""
    fonte = _COLORS_TS.read_text(encoding="utf-8")
    bloco_re = re.compile(
        rf"export\s+const\s+{nome_const}\s*:[^=]*=\s*\[(?P<corpo>.*?)\n\]",
        re.DOTALL,
    )
    bloco = bloco_re.search(fonte)
    assert bloco is not None, (
        f"não achei `export const {nome_const} = [...]` em "
        f"{_COLORS_TS.relative_to(_REPO).as_posix()}."
    )
    itens = []
    for m in _FAIXA_ABS_ITEM_RE.finditer(bloco.group("corpo")):
        corte_txt = m.group("corte")
        corte = float("inf") if corte_txt == "Infinity" else float(corte_txt.replace("_", ""))
        rgba = (int(m.group("r")), int(m.group("g")), int(m.group("b")), int(m.group("a")))
        itens.append((corte, rgba))
    return itens


@pytest.mark.parametrize(
    "nome_web,bands_py",
    [
        ("DENSIDADE_BANDS", DENSIDADE_POP_BANDS),
        ("RENDA_SETOR_BANDS", RENDA_PER_CAPITA_BANDS),
    ],
)
def test_faixas_absolutas_batem_corte_e_cor_com_o_nucleo(nome_web, bands_py) -> None:
    web = _faixas_absolutas_web(nome_web)
    nucleo = [(corte, rgba) for corte, _rotulo, rgba in bands_py]
    assert web == nucleo, (
        f"{nome_web} (web/src/lib/colors.ts) divergiu de {bands_py!r} "
        "(src/motor_expansao/dashboard/constants.py) — as duas são cópias manuais que "
        "precisam andar juntas, corte e cor, na mesma ordem. "
        f"web={web!r} núcleo={nucleo!r}"
    )
