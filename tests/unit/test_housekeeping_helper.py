"""Testes do helper de housekeeping (BLK-OPS-10).

Carrega ``scripts/housekeeping_move_block.py`` por caminho de arquivo (scripts/ não é
pacote), exercitando: byte-identity por fatia literal, stub no backlog, append em
completed, bloco inexistente, ``verify_moved`` e idempotência re-entrante.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re

import pytest

_HELPER = (
    pathlib.Path(__file__).resolve().parents[2]
    / "scripts"
    / "housekeeping_move_block.py"
)
_spec = importlib.util.spec_from_file_location("housekeeping_move_block", _HELPER)
assert _spec and _spec.loader
hk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hk)


FAKE_BACKLOG = """# Backlog

## Tarefas pendentes

### BLK-FAKE-01 — Bloco de teste para mover

Status: CONCLUÍDO (2026-05-29)
Conteúdo arbitrário do bloco fake 01.
Linha com acento: ção, é, travessão —.

---

### BLK-FAKE-02 — Bloco que deve permanecer

Status: Pendente
Conteúdo do bloco fake 02.

---
"""

FAKE_COMPLETED = """# Completed Tasks

## Histórico

Bloco antigo qualquer.
"""

KEPT_BLOCK = (
    "### BLK-FAKE-02 — Bloco que deve permanecer\n\n"
    "Status: Pendente\nConteúdo do bloco fake 02."
)


def test_moved_is_literal_byte_identical_slice():
    nb, nc, moved = hk.move_block(FAKE_BACKLOG, FAKE_COMPLETED, "BLK-FAKE-01", "2026-05-29")
    # fatia literal do original
    assert moved in FAKE_BACKLOG
    assert moved.startswith("### BLK-FAKE-01 — Bloco de teste para mover")
    assert "Conteúdo arbitrário do bloco fake 01." in moved
    # não captura separador nem o bloco seguinte
    assert "BLK-FAKE-02" not in moved
    assert "---" not in moved


def test_stub_replaces_block_in_backlog_and_keeps_others():
    nb, _nc, _moved = hk.move_block(FAKE_BACKLOG, FAKE_COMPLETED, "BLK-FAKE-01", "2026-05-29")
    assert "- BLK-FAKE-01 (concluído 2026-05-29) — ver tasks/completed.md" in nb
    assert re.search(r"(?m)^### +BLK-FAKE-01\b", nb) is None  # heading removido
    assert KEPT_BLOCK in nb  # bloco pendente preservado verbatim


def test_completed_is_append_only_with_block():
    _nb, nc, moved = hk.move_block(FAKE_BACKLOG, FAKE_COMPLETED, "BLK-FAKE-01", "2026-05-29")
    assert nc.startswith(FAKE_COMPLETED.rstrip("\n"))  # append-only
    assert moved in nc  # bloco byte-idêntico presente


def test_block_not_found_raises():
    with pytest.raises(hk.BlockNotFound):
        hk.move_block(FAKE_BACKLOG, FAKE_COMPLETED, "BLK-NOPE-99", "2026-05-29")


def test_verify_moved_passes_after_and_fails_before():
    nb, nc, _moved = hk.move_block(FAKE_BACKLOG, FAKE_COMPLETED, "BLK-FAKE-01", "2026-05-29")
    hk.verify_moved(nb, nc, "BLK-FAKE-01")  # não levanta
    with pytest.raises(AssertionError):
        hk.verify_moved(FAKE_BACKLOG, FAKE_COMPLETED, "BLK-FAKE-01")  # pré-move: sem stub


def test_idempotent_reentrant_second_move_raises():
    nb, nc, _moved = hk.move_block(FAKE_BACKLOG, FAKE_COMPLETED, "BLK-FAKE-01", "2026-05-29")
    with pytest.raises(hk.BlockNotFound):
        hk.move_block(nb, nc, "BLK-FAKE-01", "2026-05-29")


def _write_tmp(tmp_path, backlog_text, completed_text):
    b = tmp_path / "b.md"
    c = tmp_path / "c.md"
    b.write_text(backlog_text, encoding="utf-8", newline="")
    c.write_text(completed_text, encoding="utf-8", newline="")
    return str(b), str(c)


def test_cli_move_then_check_returns_0(tmp_path):
    b, c = _write_tmp(tmp_path, FAKE_BACKLOG, FAKE_COMPLETED)
    assert hk.main(["BLK-FAKE-01", "--date", "2026-05-29", "--backlog", b, "--completed", c]) == 0
    assert hk.main(["BLK-FAKE-01", "--check", "--backlog", b, "--completed", c]) == 0


def test_cli_adhoc_block_returns_exit_ad_hoc(tmp_path):
    b, c = _write_tmp(tmp_path, FAKE_BACKLOG, FAKE_COMPLETED)
    rc = hk.main(["BLK-NOPE-99", "--date", "2026-05-29", "--backlog", b, "--completed", c])
    assert rc == hk.EXIT_AD_HOC == 3


def test_cli_check_before_move_returns_1(tmp_path):
    b, c = _write_tmp(tmp_path, FAKE_BACKLOG, FAKE_COMPLETED)
    assert hk.main(["BLK-FAKE-01", "--check", "--backlog", b, "--completed", c]) == 1


def test_crlf_preserved_and_byte_identical():
    backlog = FAKE_BACKLOG.replace("\n", "\r\n")
    completed = FAKE_COMPLETED.replace("\n", "\r\n")
    nb, nc, moved = hk.move_block(backlog, completed, "BLK-FAKE-01", "2026-05-29")
    assert moved in backlog  # fatia literal do source CRLF
    assert "\r\n" in moved
    # nenhuma quebra LF solta (todo \n precedido de \r) nos arquivos resultantes
    assert re.search(r"(?<!\r)\n", nb) is None
    assert re.search(r"(?<!\r)\n", nc) is None
    # verify_moved deve passar mesmo em CRLF (stub termina com \r\n)
    hk.verify_moved(nb, nc, "BLK-FAKE-01")
