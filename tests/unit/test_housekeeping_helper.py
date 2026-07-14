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


# --------------------------------------------------------------------------------------------
# BLK-ORQ-24: is_done / emit_delta (seleção do loop + delta do PR de lote, sem substring)
# --------------------------------------------------------------------------------------------

# completed.md realista: um bloco movido (### heading), um resumo de fechamento (## heading) e
# MENÇÕES em prosa a blocos que estavam ABERTOS quando o resumo foi escrito.
COMPLETED_ORQ24 = """# Completed Tasks

## Histórico

### BLK-DONE-01 — Bloco movido pelo helper (modo merge-humano)

Conteúdo. Sucessor: BLK-OPEN-99 (ainda aberto no backlog).

## Fechamento de ciclo — BLK-DONE-02 (2026-07-14)

Resumo do ciclo auto-merge. Próximo recomendado: BLK-OPEN-98. Depende de BLK-DONE-01.

### BLK-DONE-02b — Follow-up ja concluido
"""


def test_is_done_detecta_heading_movido_e_fechamento():
    # ### BLK-X (bloco movido) e ## Fechamento — BLK-Y (resumo auto-merge) contam como DONE.
    assert hk.is_done(COMPLETED_ORQ24, "BLK-DONE-01") is True
    assert hk.is_done(COMPLETED_ORQ24, "BLK-DONE-02") is True
    assert hk.is_done(COMPLETED_ORQ24, "BLK-DONE-02b") is True


def test_is_done_ignora_mencao_em_prosa():
    # Blocos citados SÓ em prosa (sucessor/próximo/depende) NÃO contam — senão o loop pularia
    # para sempre um bloco loop-safe ainda aberto (achado MEDIA do red-team ORQ-24).
    assert hk.is_done(COMPLETED_ORQ24, "BLK-OPEN-99") is False
    assert hk.is_done(COMPLETED_ORQ24, "BLK-OPEN-98") is False


def test_is_done_nao_confunde_prefixo():
    # Igualdade de TOKEN, não substring: DONE-02 concluído não marca DONE-021 como done.
    assert hk.is_done("### BLK-DONE-02b — x\n", "BLK-DONE-02") is False
    assert hk.is_done("### BLK-DONE-02 — x\n", "BLK-DONE-02b") is False


def test_emit_delta_so_blocos_abertos_no_backlog_e_concluidos():
    backlog = (
        "## Pendentes\n\n"
        "### BLK-DONE-02 — ainda com heading aberto no backlog\n\nx\n\n---\n\n"
        "### BLK-OPEN-99 — aberto e NAO concluido\n\ny\n\n---\n"
    )
    delta = hk.emit_delta(backlog, COMPLETED_ORQ24)
    # DONE-02 tem heading aberto no backlog E fechamento em completed -> entra.
    assert "BLK-DONE-02" in delta
    # OPEN-99 está aberto no backlog mas NÃO concluído -> fora.
    assert "BLK-OPEN-99" not in delta
    # DONE-01 está concluído mas NÃO tem mais heading aberto no backlog -> fora (nada a stubar).
    assert "BLK-DONE-01" not in delta


def test_emit_delta_nao_colide_prefixo():
    # BLK-FIX-06 ABERTO no backlog + só BLK-FIX-06-C concluído em completed -> NÃO stuba o -06.
    backlog = "## P\n\n### BLK-FIX-06 — aberto\n\nx\n\n---\n"
    completed = "## H\n\n### BLK-FIX-06-C — concluido\n\ny\n"
    assert hk.emit_delta(backlog, completed) == []


def test_cli_is_done_exit_codes(tmp_path):
    b, c = _write_tmp(tmp_path, "## P\n", COMPLETED_ORQ24)
    assert hk.main(["BLK-DONE-02", "--is-done", "--backlog", b, "--completed", c]) == 0
    assert hk.main(["BLK-OPEN-99", "--is-done", "--backlog", b, "--completed", c]) == 1


def test_cli_emit_delta_sem_block_id(tmp_path):
    backlog = "## P\n\n### BLK-DONE-02 — aberto\n\nx\n\n---\n"
    b, c = _write_tmp(tmp_path, backlog, COMPLETED_ORQ24)
    # --emit-delta dispensa block_id posicional.
    assert hk.main(["--emit-delta", "--backlog", b, "--completed", c]) == 0


def test_cli_sem_block_id_fora_de_emit_delta_erra(tmp_path):
    b, c = _write_tmp(tmp_path, FAKE_BACKLOG, FAKE_COMPLETED)
    with pytest.raises(SystemExit):
        hk.main(["--is-done", "--backlog", b, "--completed", c])
