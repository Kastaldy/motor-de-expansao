"""Testes do guard do ralph loop (BLK-LOOP-02).

Tranca a matriz de caminhos PROIBIDOS/PERMITIDOS: o guard deve bloquear o nucleo do M1, score,
VPS/deploy, CI e segredos, e NAO pode bloquear o modulo paralelo legitimo `dimensionamento/`
(incluindo o `constants.py` proprio dele). Regressao do falso-positivo que abortou o loop por
casar `config.py` generico.

ATUALIZADO em BLK-ORQ-20 (furo F7): `src/motor_expansao/dimensionamento/config.py` saiu dos
PERMITIDOS e virou CRITICO — nao por se chamar `config.py` (o regex e ancorado ao caminho EXATO,
e o guardrail original segue valido para qualquer outro modulo), mas pelo CONTEUDO: ele carrega
as premissas financeiras do motor de viabilidade e a lista anti-PII `PII_COLUNAS_PROIBIDAS`
(DEC-009/DEC-012). Os demais arquivos de `dimensionamento/` continuam permitidos.
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
        # BLK-ORQ-20 (F1) — arquivos que ARMAM o proprio check `test` do CI.
        "pyproject.toml",
        "constraints.txt",
        "conftest.py",
        "Dockerfile.loop",
        # BLK-ORQ-20 (F7) — premissas financeiras + lista anti-PII do motor de viabilidade.
        "src/motor_expansao/dimensionamento/config.py",
        # BLK-ORQ-20 (N1) — config de ferramenta na raiz (precede o pyproject) + .pth.
        "setup.py",
        "setup.cfg",
        "ruff.toml",
        ".ruff.toml",
        "mypy.ini",
        "sitecustomize.py",
        "evil.pth",
        # BLK-ORQ-20 (N3) — malha IBGE versionada (universo de hexes do M1) + lancadores que
        # manuseiam o CLAUDE_CODE_OAUTH_TOKEN.
        "data/ibge/municipios_SP.geojson",
        "data/raw/ibge/malha_brasil.geojson",
        "iniciar-loop.cmd",
        "scripts/iniciar_loop.ps1",
    ],
)
def test_caminhos_proibidos_sao_bloqueados(path: str) -> None:
    assert _bloqueado(path), f"deveria BLOQUEAR: {path}"


@pytest.mark.parametrize(
    "path",
    [
        # Modulo paralelo legitimo — NUNCA bloquear (era o falso-positivo do loop).
        # `config.py` saiu daqui em BLK-ORQ-20 (F7); os vizinhos seguem permitidos, provando que o
        # guard nao voltou a casar `config.py`/`constants.py` por NOME.
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
        # BLK-ORQ-20 (N3) — governanca da esteira: no ralph e AVISO (nao bloqueia), logo NAO esta em
        # `_DENY_RES` (so CRITICO). O gate humano deles e o label no PR (modo --stdin do CI).
        "prompts/builder.md",
        ".codex/skills/codex-run-cycle/SKILL.md",
        "scripts/housekeeping_move_block.py",
        "data/osm_cache/bbox_ok_test.json",
        ".streamlit/config.toml",
    ],
)
def test_caminhos_permitidos_nao_sao_bloqueados(path: str) -> None:
    assert not _bloqueado(path), f"NAO deveria bloquear (modulo paralelo/docs): {path}"
