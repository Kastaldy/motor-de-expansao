# Current Task

## Bloco atual

ID: BLK-REV-01
Nome: Baseline de performance ponta-a-ponta (instrumentação + medição)
Status: aprovado
Tipo: instrumentação/medição (READ-ONLY sobre o M1; loop-safe)
Criticidade: Alta
Esteira: Block Orchestrator → Planner → Builder → QA (APROVADO)
Skill atual: QA (concluído)
Próxima Skill: Block Orchestrator (fechamento)

## Objetivo
Instrumentar timing por caminho e medir (frio/quente, por tamanho de UF).
Relatório `data/analysis/perf_baseline_app_2026.md` gerado (18 linhas de benchmark).
READ-ONLY M1. Não altera app/artefatos.

## Resultados principais
- AM (294k hexes): carga 2.72s cold / Render M1 2.1s
- SC (20k hexes): carga 0.55s cold / Render M1 0.9s
- PDF Pontual headless: 0.15s / Municipal: 0.08s
- Filtro município e multi-hex: < 35ms

## Branch do ciclo
ciclo/BLK-REV-01
