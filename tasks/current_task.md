# Current Task

## Bloco atual

ID: BLK-PRD-01
Nome: Reescrever PRD.md como PRD padrão do projeto
Status: APROVADO (QA concluído)
Tipo: doc
Criticidade: média (com gate de revisão humana do outline — explícito no bloco)
Esteira: Block Orchestrator → Planner → [revisão humana do outline] → Builder → QA
Skill atual: QA (concluído)
Próxima Skill: Fechamento manual (commit por path de PRD.md pelo orquestrador)
Branch do ciclo: ciclo/BLK-PRD-01
dry_run: false

## Objetivo
Reescrever `PRD.md` como um PRD padrão de produto do Motor de Expansão Ultra Academia — documento canônico subordinado ao `CLAUDE.md`, que referencia (não duplica) score/guardrails do `CLAUDE.md` e o roadmap de `tasks/backlog.md`.

## Paths do ciclo (commit por path no fechamento)
- Entregável: `PRD.md` (reescrita completa; substitui o conteúdo pré-existente "Programa de Melhorias")
- Controle: `tasks/current_task.md`, `tasks/completed.md`, `context/handoff.md`, `context/handoff/`
- ATENÇÃO escopo: `tasks/backlog.md` está pré-sujo (`M`, ~127 linhas de migração de blocos NÃO relacionada a este ciclo). NÃO será incluído no commit por path — `git add tasks/backlog.md` arrastaria conteúdo alheio. Marcação de BLK-PRD-01 como concluído fica em `tasks/completed.md`; backlog.md deixado ao humano (igual ao fechamento do BLK-OPS-06).
- Nenhum arquivo de código/artefato M1/`CLAUDE.md` é tocado.

## Nota de orquestração
Ciclo doc-only. NÃO altera a própria orquestração (run-cycle.md / prompts / esteira) → NÃO dispara dry-run pós-merge.
