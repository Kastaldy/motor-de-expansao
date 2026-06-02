# Current Task

## Bloco atual

ID: BLK-ORQ-01
Nome: Otimização de tempo de execução do /run-cycle (Fase 1 / Tier 1)
Status: aprovado
Tipo: performance
Criticidade: alta
Esteira: Block Orchestrator → Planner → [aprovação humana] → Builder → QA
Skill atual: QA/Quality Analyzer
Próxima Skill: Fechamento do orquestrador (6.0 housekeeping move + --check → 6.a commit por path → 6.b merge humano → 6.c dry-run autônomo)
dry_run: false

## Objetivo
Reduzir o tempo de relógio do /run-cycle (Fase 1: eliminar leitura dupla de contexto, instalar pytest-xdist/-n auto, suíte full uma única vez no QA) E adicionar tiering de modelo por agente × criticidade (QA SEMPRE Opus 4.8) — expansão v2 por instrução humana explícita (Felipe, 2026-06-02) — SEM degradar qualidade nem documentação/handoffs.

## Paths do ciclo (commit por path)
- .claude/commands/run-cycle.md
- prompts/block_orchestrator.md
- prompts/planner.md
- prompts/builder.md
- prompts/qa_analyzer.md
- pyproject.toml
- tasks/backlog.md (bloco BLK-ORQ-01 + housekeeping de fechamento)
- tasks/completed.md (housekeeping de fechamento)
- context/handoff.md + context/handoff/
- (demais paths conforme o plano do Planner)

## Observação de orquestração
Ciclo ALTERA a própria orquestração → dispara dry-run autônomo pós-merge (Passo 6.c). dry_run desta execução = false (ciclo real).
