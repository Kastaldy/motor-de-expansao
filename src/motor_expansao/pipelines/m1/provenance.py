"""Manifesto de proveniencia dos outputs do M1 (BLK-OPS-03).

Modulo ADITIVO e NAO-MUTANTE: apenas LE parametros canonicos (`settings`,
`PESOS_HEX_SCORE_ESTRUTURAL`), hasheia os BYTES BRUTOS do `Ultra.csv` e escreve
um JSON irmao dos artefatos oficiais em `data/outputs/_manifest.json`. Nunca
reescreve qualquer parquet/CSV do M1, nunca recalcula score.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from motor_expansao.config import settings
from motor_expansao.core.constants import PESOS_HEX_SCORE_ESTRUTURAL

MANIFEST_PATH = Path("data/outputs/_manifest.json")
ULTRA_CSV_PATH = Path("data/ultra/Ultra.csv")
IBGE_VINTAGE = "censo_2022"
SCHEMA_VERSION = 1

# Raiz do repo a partir deste arquivo: src/motor_expansao/pipelines/m1/provenance.py
# parents[0]=m1, [1]=pipelines, [2]=motor_expansao, [3]=src, [4]=raiz do repo.
_REPO_ROOT = Path(__file__).resolve().parents[4]

_COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")


def _sha256_file(path: Path) -> str | None:
    """sha256 dos BYTES BRUTOS do arquivo; ``None`` se nao existe.

    Le em modo binario (independe de encoding) — correto para o legado
    `Ultra.csv` (latin-1, 1 linha de metadado).
    """
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_commit() -> str | None:
    """Hash do commit atual via ``git rev-parse HEAD``; ``None`` em qualquer falha.

    Nunca derruba o pipeline: git ausente, nao-repo ou erro retornam ``None``.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    commit = result.stdout.strip()
    if not _COMMIT_RE.match(commit):
        return None
    return commit


def build_manifest(
    *,
    ultra_csv_path: Path = ULTRA_CSV_PATH,
    ibge_vintage: str = IBGE_VINTAGE,
) -> dict[str, Any]:
    """Funcao PURA: retorna o dict do manifesto sem escrever em disco."""
    return {
        "schema_version": SCHEMA_VERSION,
        "ibge_vintage": ibge_vintage,
        "ultra_csv_sha256": _sha256_file(ultra_csv_path),
        "code_commit": _git_commit(),
        "generated_at": datetime.now(UTC).isoformat(),
        "h3_resolution": settings.H3_RESOLUTION,
        "pesos": {
            "renda": PESOS_HEX_SCORE_ESTRUTURAL["renda_per_capita"],
            "pop": PESOS_HEX_SCORE_ESTRUTURAL["populacao_proxy"],
        },
        "dist_min_ultra_km": settings.DIST_MIN_ULTRA_KM,
        "renda_min": settings.RENDA_MIN,
    }


def write_manifest(
    path: Path = MANIFEST_PATH,
    *,
    ultra_csv_path: Path = ULTRA_CSV_PATH,
    ibge_vintage: str = IBGE_VINTAGE,
) -> Path:
    """Escreve o manifesto em JSON UTF-8 puro (sem BOM) e retorna o caminho.

    So LE parametros/sha e ESCREVE o JSON novo; jamais toca artefatos M1.
    """
    manifest = build_manifest(ultra_csv_path=ultra_csv_path, ibge_vintage=ibge_vintage)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path
