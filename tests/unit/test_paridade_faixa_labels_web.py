"""Trava `FAIXA_LABELS` como CONTRATO FUNCIONAL do filtro do piloto web.

``constants.FAIXA_LABELS`` deixou de ser só exibição: o filtro global "melhores
hexes" do piloto (``FAIXA_FILTROS`` em ``web/src/screens/MapScreen.tsx``) compara o
RÓTULO acentuado como string ("Prioridade máxima" / "Alta" / "Média"), e esse rótulo
chega pela API em ``web/server/app.py`` (``_faixa_label`` -> ``FAIXA_LABELS``).
Renomear um label no núcleo faz o filtro parar de casar e o mapa ficar vazio, EM
SILÊNCIO — nenhum teste travava isso.

Por que em Python (e não em TS): quem renomeia o label mexe no núcleo e roda o
pytest, não o vitest do `web/`; e aqui a comparação é contra o dicionário REAL
(``FAIXA_LABELS`` importado), sem criar uma terceira cópia dos rótulos. Um teste TS
teria que reimplementar/parsear o dicionário Python para dizer a mesma coisa.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from motor_expansao.dashboard.constants import FAIXA_LABELS

_REPO = Path(__file__).resolve().parents[2]  # tests/unit/ -> raiz do worktree
_WEB_SRC = _REPO / "web" / "src"
_MAP_SCREEN = _WEB_SRC / "screens" / "MapScreen.tsx"

# `const FAIXA_FILTROS: Record<string, Set<string>> = { ... }` (fecha em `\n}`).
_BLOCO_RE = re.compile(
    r"const\s+FAIXA_FILTROS\s*(?::[^=]+)?=\s*\{(?P<corpo>.*?)\n\}",
    re.DOTALL,
)
_STR_RE = re.compile(r"""(?:'([^']*)'|"([^"]*)")""")

# O piloto web só existe na branch do piloto; sem ele não há contrato a travar.
pytestmark = pytest.mark.skipif(
    not _WEB_SRC.is_dir(),
    reason="piloto web (web/src) ausente nesta árvore — nada a comparar",
)


def _rotulos_do_filtro() -> list[str]:
    """Rótulos de faixa comparados como string pelo filtro global do piloto."""
    assert _MAP_SCREEN.is_file(), (
        f"{_MAP_SCREEN.relative_to(_REPO).as_posix()} não existe, mas web/src existe.\n"
        "Se a tela foi movida/renomeada, atualize ESTE teste — ele é a única trava "
        "entre FAIXA_LABELS e o filtro 'melhores hexes' do piloto."
    )
    fonte = _MAP_SCREEN.read_text(encoding="utf-8")
    bloco = _BLOCO_RE.search(fonte)
    assert bloco is not None, (
        "não achei o mapa `const FAIXA_FILTROS = {...}` em "
        f"{_MAP_SCREEN.relative_to(_REPO).as_posix()}.\n"
        "Se o filtro mudou de nome/formato, atualize este teste — sem ele, renomear "
        "FAIXA_LABELS quebra o filtro do piloto em silêncio."
    )
    achados = [a or b for a, b in _STR_RE.findall(bloco.group("corpo"))]
    assert achados, (
        "o bloco FAIXA_FILTROS não tem nenhum rótulo literal — formato inesperado; "
        "atualize este teste."
    )
    return achados


def test_rotulos_do_filtro_do_piloto_existem_em_faixa_labels() -> None:
    validos = set(FAIXA_LABELS.values())
    orfaos = sorted({r for r in _rotulos_do_filtro() if r not in validos})
    assert not orfaos, (
        "o filtro 'melhores hexes' do piloto compara rótulos que NÃO existem mais em "
        f"constants.FAIXA_LABELS: {orfaos}\n"
        f"Rótulos válidos hoje: {sorted(validos)}\n\n"
        "FAIXA_LABELS não é só exibição: renomear um label EXIGE atualizar o filtro em "
        "web/src/screens/MapScreen.tsx (FAIXA_FILTROS), que casa o rótulo acentuado como "
        "string vindo da API (web/server/app.py -> _faixa_label). Sem isso o filtro para "
        "de casar e o mapa do piloto fica vazio, sem erro."
    )
