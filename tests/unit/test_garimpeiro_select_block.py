"""Testes do seletor de bloco do Garimpeiro (scripts/garimpeiro_select_block.py, BLK-ORQ-22).

Critério de aceite #1: bloco `manual (NÃO loop-safe)` NÃO é selecionado; bloco `loop-safe` É —
usando os DOIS formatos reais do backlog.md. Também: respeita `Depende de`, pula concluídos e não
confunde `BLK-X` com `BLK-X-FU1`.
"""
from __future__ import annotations

import importlib.util
import pathlib

_HELPER = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "garimpeiro_select_block.py"
_spec = importlib.util.spec_from_file_location("garimpeiro_select_block", _HELPER)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

elegiveis = _mod.elegiveis
parse_blocos = _mod.parse_blocos
concluido = _mod.concluido

# Formatos REAIS do backlog.md: loop-safe em negrito; manual contém a substring "loop-safe".
BACKLOG = """# Backlog

### BLK-AAA-01 — bloco loop-safe simples

| Campo | Valor |
|---|---|
| **Criticidade** | **Baixa** |
| **Depende de** | — (nenhuma) |
| **Autonomia** | **loop-safe** — toca só `tests/`, READ-ONLY sobre o M1, sem VPS/rede. |

---

### BLK-BBB-02 — bloco manual (armadilha do grep)

| **Autonomia** | **manual (NÃO loop-safe)** — muda um score em produção; NUNCA loop-safe. |

---

### BLK-CCC-03 — loop-safe mas depende de bloco AINDA aberto

| **Depende de** | **BLK-ZZZ-99** (ainda não concluído). |
| **Autonomia** | **loop-safe** — determinístico, READ-ONLY M1. |

---

### BLK-DDD-04 — loop-safe com dependência JÁ concluída

| **Depende de** | **BLK-AAA-01** (concluído). |
| **Autonomia** | **loop-safe** — determinístico. |

---

### BLK-EEE-05 — loop-safe mas JÁ concluído

| **Autonomia** | **loop-safe** — headless. |
"""

COMPLETED = """# Completed Tasks

### BLK-EEE-05 — loop-safe mas JÁ concluído
Resumo: entregue.

## Fechamento de ciclo - BLK-DDD-04 (2026-07-15)
(este só conta se DDD estiver em completed; usado noutro teste)
"""


def test_loop_safe_selecionado_e_manual_ignorado():
    # Critério #1: com completed VAZIO, AAA-01 (loop-safe) entra; BBB-02 (manual) NÃO.
    elig = elegiveis(BACKLOG, "# Completed Tasks\n")
    assert "BLK-AAA-01" in elig
    assert "BLK-BBB-02" not in elig  # a armadilha do grep loop-safe


def test_manual_nunca_e_loop_safe():
    blocos = {b["id"]: b for b in parse_blocos(BACKLOG)}
    assert blocos["BLK-AAA-01"]["loop_safe"] is True
    assert blocos["BLK-BBB-02"]["loop_safe"] is False  # **manual (NÃO loop-safe)**


def test_depende_de_bloqueia_e_libera():
    # Só AAA-01 concluído -> DDD-04 (dep=AAA-01) libera; CCC-03 (dep=ZZZ-99 aberto) NÃO.
    completed = "# Completed\n\n### BLK-AAA-01 — x\n"
    elig = elegiveis(BACKLOG, completed)
    assert "BLK-DDD-04" in elig
    assert "BLK-CCC-03" not in elig


def test_concluido_e_pulado():
    # EEE-05 está em completed -> não entra, mesmo sendo loop-safe.
    elig = elegiveis(BACKLOG, COMPLETED)
    assert "BLK-EEE-05" not in elig


def test_fronteira_exata_nao_confunde_fu():
    # "BLK-X" concluído NÃO deve marcar "BLK-X-FU1" como concluído.
    completed = "# C\n\n### BLK-AAA-01 — x\n"
    assert concluido(completed, "BLK-AAA-01") is True
    assert concluido(completed, "BLK-AAA-01-FU1") is False


def test_fechamento_heading_conta_como_concluido():
    completed = "# C\n\n## Fechamento de ciclo - BLK-AAA-01 (2026-07-15)\nresumo\n"
    assert concluido(completed, "BLK-AAA-01") is True


def test_ordem_preservada():
    elig = elegiveis(BACKLOG, "# Completed Tasks\n")
    # AAA-01 aparece antes de DDD-04 no backlog (DDD depende de AAA, ainda não concluído -> DDD fora)
    assert elig[0] == "BLK-AAA-01"
