#!/usr/bin/env python3
"""Guard do ralph loop autonomo (BLK-LOOP-01).

Substitui o gate humano dos blocos Alta no modo loop: inspeciona TODAS as mudancas do loop
(commitadas entre --base e HEAD + working tree) e ABORTA (exit 1) se qualquer caminho proibido
for tocado. Caminhos proibidos = nucleo do M1, score/pesos, artefatos oficiais, VPS/deploy,
CI e segredos. READ-ONLY: nao altera nada; so audita o diff.

Uso:
    python scripts/loop_guard.py --base <ref>     # ref = HEAD do inicio do loop
Saida: exit 0 se limpo; exit 1 (+ lista no stderr) se tocar caminho proibido.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys

# Padroes de caminho PROIBIDOS no modo loop (READ-ONLY sobre o M1; sem VPS/segredo).
# Comentario de cada regra ao lado.
_DENY: list[tuple[str, str]] = [
    (r"(^|/)config\.py$", "config.py — parametros canonicos do M1"),
    (r"^src/motor_expansao/pipelines/m1/", "pipeline oficial do M1"),
    (r"scoring", "qualquer arquivo de score (*scoring*)"),
    (r"(^|/)constants\.py$", "constants.py — pesos/constantes M1/mapa"),
    (r"brasil_(estrutural|priorizados)", "artefato oficial M1 (brasil_*)"),
    (r"hexagonos_brasil", "artefato oficial M1 (hexagonos_brasil*)"),
    (r"top_oportunidades_resumo|resumo_por_uf", "artefato oficial M1 (resumos)"),
    (r"^deploy/", "deploy/ (VPS)"),
    (r"^Dockerfile\.(streamlit|api)$", "imagem de producao"),
    (r"docker-compose", "compose de producao"),
    (r"(^|/)Caddyfile", "Caddy (VPS)"),
    (r"^authelia/", "Authelia (VPS)"),
    (r"(^|/)\.env($|\.)", ".env / segredos"),
    (r"^secrets/", "secrets/"),
    (r"\.enc\.", "arquivo encriptado (segredo)"),
    (r"^\.github/workflows/", "CI (.github/workflows)"),
]
_DENY_RES = [(re.compile(p), motivo) for p, motivo in _DENY]


def _git(*args: str) -> str:
    out = subprocess.run(
        ["git", *args], capture_output=True, text=True, check=False
    )
    return out.stdout


def _changed_paths(base: str) -> set[str]:
    """Uniao dos caminhos: commitados (base..HEAD) + working tree (staged/unstaged/untracked)."""
    paths: set[str] = set()
    # Commitados desde o inicio do loop.
    for line in _git("diff", "--name-only", f"{base}..HEAD").splitlines():
        if line.strip():
            paths.add(line.strip())
    # Working tree (porcelain cobre staged, modificados e untracked).
    for line in _git("status", "--porcelain").splitlines():
        # formato: "XY <path>"  (rename: "R  old -> new")
        raw = line[3:] if len(line) > 3 else ""
        if "->" in raw:
            raw = raw.split("->", 1)[1]
        raw = raw.strip().strip('"')
        if raw:
            paths.add(raw)
    return paths


def main() -> int:
    ap = argparse.ArgumentParser(description="Guard de M1/VPS do ralph loop autonomo.")
    ap.add_argument("--base", required=True, help="ref git do inicio do loop (HEAD inicial)")
    args = ap.parse_args()

    paths = _changed_paths(args.base)
    violacoes: list[tuple[str, str]] = []
    for path in sorted(paths):
        for rx, motivo in _DENY_RES:
            if rx.search(path):
                violacoes.append((path, motivo))
                break

    if violacoes:
        print("GUARD: caminho(s) PROIBIDO(s) tocado(s) pelo loop:", file=sys.stderr)
        for path, motivo in violacoes:
            print(f"  - {path}  ->  {motivo}", file=sys.stderr)
        return 1

    print(f"GUARD OK: {len(paths)} caminho(s) alterado(s), nenhum proibido.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
