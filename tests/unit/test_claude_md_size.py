"""Lint de 'manter curto' do CLAUDE.md + coerência do índice §8 <-> docs/decisions/.

Contexto: o ciclo de 2026-07-19 extraiu o corpo das DECs do CLAUDE.md §8 para
``docs/decisions/DEC-0XX.md``, deixando no §8 só 1 linha-índice por DEC. Estes testes
tornam a regra "manter curto" (topo do CLAUDE.md) VERIFICÁVEL em vez de aspiracional e
impedem o re-bloat / o drift entre o índice e os arquivos.

READ-ONLY: só leem CLAUDE.md e docs/decisions/; não tocam M1, score nem artefatos.
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

#: Teto de linhas do CLAUDE.md. Hoje ~179 (era 398 antes do split do §8). O teto é um
#: backstop contra o re-bloat — se estourar, mova o detalhe para docs/ (não relaxe sem decisão).
#:
#: 230 -> 231 na DEC-061 (2026-09-16). O backstop real é "nenhum CORPO de DEC no §8", e o §8 cresce
#: **1 linha por DEC** por contrato (a regra no topo do CLAUDE.md manda exatamente isso). Com o
#: arquivo parado no teto, toda DEC nova passaria a reprovar aqui — o teste deixaria de medir
#: re-bloat e viraria um pedágio. Subir 1 junto com a linha-índice é a manutenção prevista; o que
#: continua proibido é subir para acomodar PROSA, que pertence a docs/.
#:
#: 231 -> 232 na DEC-063 (2026-09-17), pela mesma manutenção prevista: uma DEC nova, uma linha-índice.
#:
#: 232 -> 233 na DEC-064 (2026-09-18), idem. O corpo da decisão (retenção integral da série, estado
#: incremental e ponte de identidade) está em docs/decisions/DEC-064.md; no §8 entrou 1 linha.
#:
#: 233 -> 234 na DEC-065 (2026-09-21), idem: 1 linha-índice, corpo em docs/decisions/DEC-065.md.
#:
#: 234 -> 235 na DEC-067 (2026-09-22), idem: 1 linha-índice, corpo em docs/decisions/DEC-067.md.
_TETO_LINHAS = 235


def _linhas(p: Path) -> int:
    return len(p.read_text(encoding="utf-8").splitlines())


def test_claude_md_sob_o_teto() -> None:
    claude = _ROOT / "CLAUDE.md"
    n = _linhas(claude)
    assert n <= _TETO_LINHAS, (
        f"CLAUDE.md tem {n} linhas (> teto {_TETO_LINHAS}). Regra 'manter curto' (topo do CLAUDE.md): "
        "mova o detalhe para docs/. Nova DEC -> docs/decisions/DEC-0XX.md, só 1 linha-índice no §8 "
        "(use a skill /registrar-decisao)."
    )


def test_indice_secao8_bate_com_docs_decisions() -> None:
    """Todo DEC linkado no §8 tem arquivo em docs/decisions/ e vice-versa (sem drift)."""
    claude_txt = (_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    decdir = _ROOT / "docs" / "decisions"

    # Links do índice: [DEC-016](docs/decisions/DEC-016.md)
    idx_ids = set(re.findall(r"\[(DEC-\d+)\]\(docs/decisions/DEC-\d+\.md\)", claude_txt))
    file_ids = {p.stem for p in decdir.glob("DEC-*.md")}

    assert idx_ids == file_ids, (
        "Índice do CLAUDE.md §8 e docs/decisions/ divergem. "
        f"Só no índice (link sem arquivo): {sorted(idx_ids - file_ids)}; "
        f"só em arquivos (sem linha-índice): {sorted(file_ids - idx_ids)}. "
        "Toda DEC deve ter arquivo E linha-índice (skill /registrar-decisao)."
    )
