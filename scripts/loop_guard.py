#!/usr/bin/env python3
"""Guard do ralph loop autonomo (BLK-LOOP-01).

Substitui o gate humano dos blocos Alta no modo loop: inspeciona as mudancas com INTENCAO DE
MERGE (commitadas entre --base e HEAD + staged/--cached) e ABORTA (exit 1) se qualquer caminho
proibido for tocado. NAO olha o working tree nao-staged (commit-by-path nao mergeia isso; evita
falso-positivo de churn de CRLF/__pycache__). Caminhos proibidos = nucleo do M1, score/pesos,
artefatos oficiais, VPS/deploy, CI e segredos. READ-ONLY: nao altera nada; so audita o diff.

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
# Regras ANCORADAS a caminhos especificos do M1 — NAO casar nomes genericos (ex.: o modulo
# paralelo legitimo `src/motor_expansao/dimensionamento/config.py` NAO pode ser bloqueado).
_DENY: list[tuple[str, str]] = [
    (r"^src/motor_expansao/config\.py$", "config.py raiz — parametros canonicos do M1"),
    (r"^src/motor_expansao/pipelines/m1/", "pipeline oficial do M1"),
    (r"(^|/)[^/]*scoring[^/]*\.py$", "arquivo de score (scoring)"),
    (r"^src/motor_expansao/(core|dashboard)/constants\.py$", "constants.py — pesos/constantes M1/mapa"),
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
    """Caminhos com INTENCAO de merge: commitados (base..HEAD) + staged (--cached).

    NAO inclui o working tree nao-staged/untracked de proposito: o loop commita POR PATH, entao
    so o que esta commitado/staged seria mergeado. Modificacoes transitorias nao-staged (ex.: churn
    de CRLF do container Linux, __pycache__, artefatos regenerados) NAO representam intencao de
    merge e davam falso-positivo. O `.gitattributes` (eol=lf) elimina o churn de line-ending.
    """
    paths: set[str] = set()
    # Commitados desde o inicio do loop.
    for line in _git("diff", "--name-only", f"{base}..HEAD").splitlines():
        if line.strip():
            paths.add(line.strip())
    # Staged (indexado para o proximo commit).
    for line in _git("diff", "--cached", "--name-only").splitlines():
        if line.strip():
            paths.add(line.strip())
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
