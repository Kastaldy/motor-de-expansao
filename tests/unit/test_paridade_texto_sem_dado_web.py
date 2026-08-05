"""Trava a paridade do texto de "dado ausente" entre o núcleo Python e o piloto web.

A string existe DUAS vezes, como cópia manual — não há import nem geração de código
entre as duas linguagens:

  - Python: ``constants.TEXTO_SEM_DADO`` -> os PDFs do piloto, da API e do bot;
  - TypeScript: ``TEXTO_SEM_DADO`` (``web/src/lib/constants.ts``) -> as telas do piloto web.

O próprio comentário do ``.ts`` pede "se mudar aqui, mude lá" — e nada garantia isso.
Quando a sigla "n/d" virou "Não disponível" (pedido de Juan, 2026-08-03), bastava um
dos lados ficar para trás para a MESMA ausência de dado aparecer com dois nomes na
mesma jornada (mapa web -> PDF). Este teste lê o ``.ts``, extrai o literal e compara
com o Python. Ele NÃO define o texto — apenas trava que as duas cópias andem juntas.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from motor_expansao.dashboard.constants import TEXTO_SEM_DADO

_REPO = Path(__file__).resolve().parents[2]  # tests/unit/ -> raiz do worktree
_WEB_SRC = _REPO / "web" / "src"
_CONSTANTS_TS = _WEB_SRC / "lib" / "constants.ts"

# `export const TEXTO_SEM_DADO = 'Não disponível'` (aspas simples/duplas ou template
# literal, com ou sem anotação de tipo e com ou sem ponto e vírgula).
_DECL_RE = re.compile(
    r"export\s+const\s+TEXTO_SEM_DADO\s*(?::[^=]+)?=\s*"
    r"(?P<aspa>['\"`])(?P<valor>[^'\"`]*)(?P=aspa)"
)

# O piloto web só existe na branch do piloto; sem ele não há paridade a travar.
pytestmark = pytest.mark.skipif(
    not _WEB_SRC.is_dir(),
    reason="piloto web (web/src) ausente nesta árvore — nada a comparar",
)


def _texto_web() -> str:
    """Literal de `TEXTO_SEM_DADO` como está escrito no constants.ts."""
    assert _CONSTANTS_TS.is_file(), (
        f"{_CONSTANTS_TS.relative_to(_REPO).as_posix()} não existe, mas web/src existe.\n"
        "Se o arquivo foi movido/renomeado, atualize ESTE teste — ele é a única trava "
        "entre o texto de dado ausente do piloto web e o do núcleo Python (TEXTO_SEM_DADO)."
    )
    fonte = _CONSTANTS_TS.read_text(encoding="utf-8")
    decl = _DECL_RE.search(fonte)
    assert decl is not None, (
        "não achei `export const TEXTO_SEM_DADO = '...'` em "
        f"{_CONSTANTS_TS.relative_to(_REPO).as_posix()}.\n"
        "Se a constante mudou de nome/formato, atualize este teste — sem ele o texto de "
        "dado ausente do piloto web e o dos PDFs divergem em silêncio."
    )
    return decl.group("valor")


def test_texto_sem_dado_web_bate_com_o_nucleo_python() -> None:
    web = _texto_web()
    assert web == TEXTO_SEM_DADO, (
        "o texto de dado ausente DIVERGIU entre o núcleo Python e o piloto web:\n"
        f"  constants.py -> TEXTO_SEM_DADO = {TEXTO_SEM_DADO!r}\n"
        f"  constants.ts -> TEXTO_SEM_DADO = {web!r}\n\n"
        "Os dois arquivos precisam andar juntos (são cópias manuais, sem import):\n"
        "  - src/motor_expansao/dashboard/constants.py (PDFs do piloto, da API e do bot)\n"
        "  - web/src/lib/constants.ts (telas do piloto web)\n"
        "Ajuste o lado que ficou para trás; a mesma ausência de dado não pode ter dois "
        "nomes na mesma jornada."
    )


def test_texto_sem_dado_web_nao_e_vazio() -> None:
    """Um literal vazio passaria despercebido no `.ts` e deixaria a célula em branco.

    Em branco, quem lê não distingue "não temos o dado" de "o valor é zero" — que é
    exatamente o que a constante existe para evitar.
    """
    web = _texto_web()
    assert web.strip(), (
        "TEXTO_SEM_DADO está vazio em web/src/lib/constants.ts: a célula sem dado ficaria "
        "em branco e viraria ambígua com um valor zero."
    )
