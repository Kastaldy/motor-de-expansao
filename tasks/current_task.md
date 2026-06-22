# Current Task

## Bloco atual

ID: BLK-DIM-19
Nome: Fix: flag de viável (payback 60 → 36 meses) e exibir payback real (remover "Nunca")
Status: aprovado
Tipo: bug fix (constante de viabilidade e display; READ-ONLY sobre M1)
Criticidade: média
Esteira: Block Orchestrator → Planner → Builder → QA
Skill atual: QA
Próxima Skill: Block Orchestrator (fechamento + housekeeping move)

## Objetivo
Corrigir `payback_meses <= 60` para `<= 36` em `simulador.py` (flag_viavel), atualizar docstring, substituir `"> 60 / nunca"` por `"> 60 meses"` em `pages.py`, e atualizar os testes afetados (CA-07d: flag_viavel agora False para payback ~57 meses).

## Modo
LOOP AUTÔNOMO — sem gate humano (bloco loop-safe, READ-ONLY sobre M1)

## Tiering de modelo (Média)
- Block Orchestrator: sonnet
- Planner: sonnet
- Builder: sonnet
- QA: opus (sempre)

## Handoff disponível
`context/handoff.md` — gerado pelo Builder em 2026-06-22 14:45:32
