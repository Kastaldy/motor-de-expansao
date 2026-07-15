#!/usr/bin/env python3
"""Garimpeiro (BLK-ORQ-22) — seletor do próximo bloco LOOP-SAFE elegível do backlog.

A routine na nuvem (Garimpeiro) roda o loop `/run-cycle` de forma autônoma e entrega o trabalho como
PR em branch `claude/*` (sem merge). Este seletor decide QUAL bloco trabalhar, com o **marcador
ANCORADO** exigido pelo bloco: só entra bloco cuja linha de Autonomia **começa** com `loop-safe`.

Por que ancorado: `| **Autonomia** | **manual (NÃO loop-safe)** |` CONTÉM a substring "loop-safe" —
um `grep loop-safe` ingênuo daria falso-positivo e o loop pegaria um bloco manual. O regex exige que,
logo após `| **Autonomia** |`, o valor **comece** com `loop-safe` (opcionalmente em negrito), o que
NÃO casa com `**manual (NÃO loop-safe)**` (começa com "manual").

Além do marcador, respeita `Depende de` (só blocos cujas dependências já estão em `completed.md`) e
pula blocos já concluídos (heading de conclusão em `completed.md`, com fronteira exata para não
confundir `BLK-X` com `BLK-X-FU1`).

Uso:
    python scripts/garimpeiro_select_block.py            # imprime o próximo BLK-* elegível (ou nada)
    python scripts/garimpeiro_select_block.py --list     # imprime todos os elegíveis, um por linha
Lê `tasks/backlog.md` e `tasks/completed.md` do checkout atual (READ-ONLY).
"""
from __future__ import annotations

import argparse
import pathlib
import re

RE_HEADING = re.compile(r"^#{2,4}\s*(BLK-[A-Z0-9]+(?:-[0-9A-Za-z]+)+)")
# Marcador ANCORADO: logo após "| **Autonomia** |", o valor começa com `loop-safe` (talvez em
# negrito). NÃO casa "**manual (NÃO loop-safe)**" (começa com "manual").
RE_LOOP_SAFE = re.compile(r"^\|\s*\*\*Autonomia\*\*\s*\|\s*\*{0,2}loop-safe\b", re.IGNORECASE)
RE_DEPENDE = re.compile(r"^\|\s*\*\*Depende de\*\*\s*\|(.+)$")
RE_BLK = re.compile(r"BLK-[A-Z0-9]+(?:-[0-9A-Za-z]+)+")


def parse_blocos(backlog: str) -> list[dict]:
    """Blocos com heading `### BLK-*`: `{id, loop_safe (ancorado), deps: [BLK-*]}`."""
    blocos: list[dict] = []
    atual: dict | None = None
    for ln in backlog.splitlines():
        m = RE_HEADING.match(ln)
        if m:
            atual = {"id": m.group(1), "loop_safe": False, "deps": []}
            blocos.append(atual)
            continue
        if atual is None:
            continue
        if RE_LOOP_SAFE.match(ln):
            atual["loop_safe"] = True
        dep = RE_DEPENDE.match(ln)
        if dep:
            atual["deps"] = [d for d in RE_BLK.findall(dep.group(1)) if d != atual["id"]]
    return blocos


def concluido(completed: str, block_id: str) -> bool:
    """True se `completed.md` tem um heading de conclusão do bloco. Fronteira EXATA `(?![-\\w])`:
    procurar `BLK-X` NÃO casa `BLK-X-FU1`. Aceita o heading padrão (`### <id>`) e o de fechamento
    (`## Fechamento ... <id>`)."""
    esc = re.escape(block_id)
    padrao = re.compile(rf"^#{{2,4}}\s*{esc}(?![-\w])", re.M)
    fechamento = re.compile(rf"^#{{2,4}}\s*Fechamento\b[^\n]*?{esc}(?![-\w])", re.M)
    return bool(padrao.search(completed) or fechamento.search(completed))


def elegiveis(backlog: str, completed: str) -> list[str]:
    """IDs dos blocos LOOP-SAFE ainda NÃO concluídos cujas dependências JÁ estão em `completed.md`,
    na ordem em que aparecem no backlog."""
    out: list[str] = []
    for b in parse_blocos(backlog):
        if not b["loop_safe"]:
            continue
        if concluido(completed, b["id"]):
            continue
        if all(concluido(completed, dep) for dep in b["deps"]):
            out.append(b["id"])
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Seletor de bloco loop-safe do Garimpeiro (BLK-ORQ-22).")
    ap.add_argument("--list", action="store_true", help="imprime todos os elegíveis (default: só o 1º)")
    ap.add_argument("--backlog", default="tasks/backlog.md")
    ap.add_argument("--completed", default="tasks/completed.md")
    args = ap.parse_args(argv)

    backlog = pathlib.Path(args.backlog).read_text(encoding="utf-8")
    completed = pathlib.Path(args.completed).read_text(encoding="utf-8")
    elig = elegiveis(backlog, completed)
    if args.list:
        print("\n".join(elig))
    elif elig:
        print(elig[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
