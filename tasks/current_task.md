# Current Task

## Bloco atual

ID: BLK-OPS-03
Nome: Manifesto de proveniência nos outputs
Status: aprovado — ciclo fechado (housekeeping + commit por path); aguardando merge humano
Tipo: feature
Criticidade: crítica
Esteira: Block Orchestrator → Planner → [aprovação humana] → Builder → QA
Skill atual: Fechamento (orquestrador)
Próxima Skill: Merge humano da branch ciclo/BLK-OPS-03
dry_run: false

## Objetivo
Gerar `data/outputs/_manifest.json` como passo final isolado de `fase1_bi_exports.py`,
carregando a proveniência dos outputs (vintage IBGE, sha256 do `Ultra.csv`, `code_commit`,
`generated_at`, parâmetros canônicos: `h3_resolution`, `pesos={renda:0.40, pop:0.60}`,
`dist_min_ultra_km`, `renda_min`), expor no rodapé do dashboard (read-only) e cobrir com
teste de presença + schema — SEM tocar nenhum valor dentro dos artefatos M1
(não-mutação provada por hash sha256 idêntico pré/pós).

## Paths do ciclo (commit por path — NUNCA git add -A)
- src/motor_expansao/pipelines/m1/fase1_bi_exports.py
- (eventual módulo novo de manifesto, ex.: src/motor_expansao/pipelines/m1/provenance.py)
- componente de rodapé no dashboard (src/motor_expansao/dashboard/*)
- tests/unit/test_manifest.py
- tasks/current_task.md · tasks/backlog.md · tasks/completed.md
- context/handoff.md · context/handoff/

## Contexto de abertura
- Branch isolado: `ciclo/BLK-OPS-03` (criado a partir do HEAD de main, worktree limpo).
- Classificação: orchestrator override → Crítica (menciona pesos do score + artefatos M1);
  backlog marca "Alta". Ambos exigem aprovação humana após o Planner.
- Commitar SÓ por path; nunca arrastar PRD.md ou edições não relacionadas.
- Este ciclo NÃO altera a orquestração → dry-run 6.c NÃO dispara.
- Guardrail: manifesto fica AO LADO dos artefatos, nunca dentro do conteúdo de scoring.
