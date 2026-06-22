# Current Task

## Bloco atual

ID: BLK-DIM-17
Nome: Fix: limiar de renda da zona morta (3.000 → 1.600)
Status: aprovado
Tipo: bug fix (constante de alerta; READ-ONLY sobre M1)
Criticidade: média
Esteira: Block Orchestrator → Planner → Builder → QA
Skill atual: QA (concluída)
Próxima Skill: Fechamento manual (housekeeping pós-merge)

## Objetivo
Corrigir `RENDA_ZONA_MORTA_MIN` de 3.000 para 1.600 em `viabilidade_ponto.py` e adicionar testes de fronteira do novo limiar (os testes existentes não asseriam o valor 3000 explicitamente).

## Modo
LOOP AUTÔNOMO — sem gate humano (bloco loop-safe, READ-ONLY sobre M1)

## Tiering de modelo (Média)
- Block Orchestrator: sonnet
- Planner: sonnet
- Builder: sonnet
- QA: opus (sempre)

## Handoff disponível
`context/handoff.md` — gerado pelo Builder em 2026-06-22 14:14:38
