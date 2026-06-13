"""Testes do guard do ralph loop (BLK-LOOP-02).

Tranca a matriz de caminhos PROIBIDOS/PERMITIDOS: o guard deve bloquear o nucleo do M1, score,
VPS/deploy, CI e segredos, e NAO pode bloquear o modulo paralelo legitimo `dimensionamento/`
(incluindo o `config.py`/`constants.py` proprios dele). Regressao do falso-positivo que abortou
o loop por casar `config.py` generico.
"""
from __future__ import annotations

import pytest

from scripts.loop_guard import _DENY_RES


def _bloqueado(path: str) -> bool:
    return any(rx.search(path) for rx, _ in _DENY_RES)


@pytest.mark.parametrize(
    "path",
    [
        "src/motor_expansao/config.py",  # config raiz do M1
        "src/motor_expansao/core/constants.py",
        "src/motor_expansao/dashboard/constants.py",
        "src/motor_expansao/pipelines/m1/hex_enrichment.py",
        "src/motor_expansao/pipelines/m1/base_h3_brasil.py",
        "tests/unit/test_scoring.py",
        "fora_primeira_fase/tests/test_scoring.py",
        "deploy/deploy.sh",
        "Dockerfile.api",
        "Dockerfile.streamlit",
        "docker-compose.prod.yml",
        ".env",
        ".env.example",
        "secrets/age.enc.env",
        ".github/workflows/ci.yml",
    ],
)
def test_caminhos_proibidos_sao_bloqueados(path: str) -> None:
    assert _bloqueado(path), f"deveria BLOQUEAR: {path}"


@pytest.mark.parametrize(
    "path",
    [
        # Modulo paralelo legitimo — NUNCA bloquear (era o falso-positivo do loop):
        "src/motor_expansao/dimensionamento/config.py",
        "src/motor_expansao/dimensionamento/constants.py",
        "src/motor_expansao/dimensionamento/aderencia.py",
        "src/motor_expansao/dimensionamento/calculadora.py",
        "src/motor_expansao/dimensionamento/huff.py",
        "src/motor_expansao/dimensionamento/pipeline.py",
        "tests/unit/dimensionamento/test_huff.py",
        "tasks/backlog.md",
        "tasks/completed.md",
        "docs/loop_autonomo.md",
        "context/handoff.md",
    ],
)
def test_caminhos_permitidos_nao_sao_bloqueados(path: str) -> None:
    assert not _bloqueado(path), f"NAO deveria bloquear (modulo paralelo/docs): {path}"
