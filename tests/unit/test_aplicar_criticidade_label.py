"""Testes da logica pura do auto-criticidade (scripts/aplicar_criticidade_label.py).

Garante que o nivel derivado do backlog casa com o que o `review-gate` (guard.yml) exige:
mapa de niveis, FAIXA = maximo, estrategica -> critica, e no-op seguro quando o bloco nao e
unicamente identificavel.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

_HELPER = (
    pathlib.Path(__file__).resolve().parents[2] / "scripts" / "aplicar_criticidade_label.py"
)
_spec = importlib.util.spec_from_file_location("aplicar_criticidade_label", _HELPER)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

MAPA_BACKLOG = _mod.MAPA_BACKLOG
NIVEIS = _mod.NIVEIS
NIVEIS_AUTO_MERGE = _mod.NIVEIS_AUTO_MERGE
EXIGEM_HUMANO = _mod.EXIGEM_HUMANO
criticidade_do_bloco = _mod.criticidade_do_bloco
sem_acento = _mod.sem_acento

BACKLOG = """# Backlog

### BLK-FOO-01 — Bloco de teste baixa

| Campo | Valor |
|---|---|
| **Criticidade** | **Baixa** (so testes; READ-ONLY sobre o M1). |
| **Status** | Pendente. |

---

### BLK-FOO-02 — Bloco media

| **Criticidade** | **Média** (mexe no dashboard). |

---

### BLK-FOO-03 — Bloco alta

| **Criticidade** | **Alta** (leitura de score). |

---

### BLK-FOO-04 — Bloco critico

| **Criticidade** | **Crítica** (altera pesos do M1). |

---

### BLK-FOO-05 — Bloco em faixa

| **Criticidade** | **Alta/Crítica** (depende do dado). |

---

### BLK-FOO-06 — Bloco estrategico

| **Criticidade** | **Estratégica** (nova camada). |

---

### BLK-FOO-07 — Criticidade em formato simples

**Criticidade**: Média (fora de tabela)

---

### BLK-FOO-10 — Prefixo que colide com BLK-FOO-1

| **Criticidade** | **Crítica** (id mais longo). |
"""


@pytest.mark.parametrize(
    ("branch", "titulo", "esperado"),
    [
        ("ciclo/BLK-FOO-01", "BLK-FOO-01 — algo", "baixa"),
        ("ciclo/BLK-FOO-02", "BLK-FOO-02 — algo", "media"),
        ("ciclo/BLK-FOO-03", "BLK-FOO-03 — algo", "alta"),
        ("ciclo/BLK-FOO-04", "BLK-FOO-04 — algo", "critica"),
        # FAIXA "Alta/Crítica" -> exige o MAXIMO (critica), como o review-gate (N6).
        ("ciclo/BLK-FOO-05", "BLK-FOO-05 — faixa", "critica"),
        # "Estratégica" mapeia para a label `critica`.
        ("ciclo/BLK-FOO-06", "BLK-FOO-06 — estrategico", "critica"),
        # Criticidade em formato simples (fora de tabela).
        ("ciclo/BLK-FOO-07", "BLK-FOO-07 — simples", "media"),
    ],
)
def test_nivel_por_bloco(branch: str, titulo: str, esperado: str) -> None:
    assert criticidade_do_bloco(BACKLOG, branch, titulo) == esperado


def test_id_mais_especifico_vence_o_prefixo() -> None:
    # BLK-FOO-10 contem "BLK-FOO-1" como substring; o mais especifico (FOO-10) deve vencer.
    assert criticidade_do_bloco(BACKLOG, "ciclo/BLK-FOO-10", "BLK-FOO-10 — x") == "critica"


def test_sem_bloco_identificavel_retorna_none() -> None:
    # PR de housekeeping/ad-hoc: nenhum ID de bloco no branch/titulo.
    assert criticidade_do_bloco(BACKLOG, "chore/housekeeping", "arruma o backlog") is None


def test_bloco_fora_da_base_retorna_none() -> None:
    # Bloco novo, ainda nao presente no backlog da base.
    assert criticidade_do_bloco(BACKLOG, "ciclo/BLK-NOVO-99", "BLK-NOVO-99 — novo") is None


def test_ambiguidade_dois_blocos_retorna_none() -> None:
    # Dois IDs distintos no alvo -> ambiguidade -> None (fail-safe; passo manual decide).
    assert (
        criticidade_do_bloco(BACKLOG, "ciclo/x", "BLK-FOO-01 + BLK-FOO-03 juntos") is None
    )


def test_mapa_backlog_cobre_todos_os_niveis_do_review_gate() -> None:
    # Guarda de sincronia com guard.yml: mesmos textos de backlog -> mesmas labels.
    assert MAPA_BACKLOG == {
        "baixa": "baixa",
        "media": "media",
        "alta": "alta",
        "critica": "critica",
        "estrategica": "critica",
    }


def test_sem_acento() -> None:
    assert sem_acento("Crítica") == "Critica"
    assert sem_acento("Estratégica") == "Estrategica"


def test_particao_auto_merge_vs_humano() -> None:
    # DEC-016: Baixa/Media auto-mergeiam; Alta/Critica exigem humano. Juntos cobrem TODOS os niveis
    # e nao se sobrepoem -> nenhum nivel fica sem regra nem com regra dupla.
    assert NIVEIS_AUTO_MERGE | EXIGEM_HUMANO == NIVEIS
    assert NIVEIS_AUTO_MERGE & EXIGEM_HUMANO == set()
