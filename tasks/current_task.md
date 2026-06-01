# Current Task

## Bloco atual

ID: BLK-FIX-03
Nome: SP estoura "Out of Memory" no Mapa Territorial (verificar outras UFs grandes)
Status: APROVADO COM RESSALVAS (QA 2026-06-01) — ciclo fechado pelo orquestrador; aguarda merge humano de `ciclo/BLK-FIX-03`
Tipo: bug (produção; render do dashboard — não toca M1/score)
Criticidade: Alta
Esteira: Block Orchestrator → Planner → Builder → QA
Skill atual: run-cycle (fechamento concluído)
Próxima Skill: (ciclo fechado) — merge humano de `ciclo/BLK-FIX-03` na base
dry_run: false

## Fechamento (orquestrador, 2026-06-01)
- Housekeeping 6.0 FEITO via `python scripts/housekeeping_move_block.py BLK-FIX-03 --date 2026-06-01`
  (stub no backlog + bloco byte-idêntico em completed.md; `--check` OK; suíte `631 passed, 1 skipped`).
- Resumo de fechamento adicionado a `tasks/completed.md` (## Fechamento BLK-FIX-03).
- Ressalva do QA registrada como follow-up opcional `BLK-FIX-03-FU1` no backlog (caption "capped" pode
  dar falso positivo para recortes de 18k–35k hexes; cosmético, não-bloqueante).
- Commit por path na branch `ciclo/BLK-FIX-03` (sem `git add -A`; `PRD.md` não arrastado). O `backlog.md`
  já trazia, do worktree pré-sujo, a curadoria do Felipe (blocos BLK-FIX-03..06) — estado legítimo do
  projeto, entra no commit junto com o stub/FU1; nenhuma edição não relacionada (ex.: PRD.md) arrastada.
- Dry-run de orquestração: NÃO se aplica (não tocou run-cycle/prompts/esteira; só dashboard render + docs).

## Objetivo
Tornar o Mapa Territorial utilizável para SP — e qualquer UF grande — sem crash de memória client-side,
sem recalcular/alterar M1/score/artefatos.

## Paths do ciclo (commit por path)
- src/motor_expansao/dashboard/constants.py
- src/motor_expansao/dashboard/components.py
- src/motor_expansao/dashboard/pages.py
- tests/integration/test_streamlit_app.py
- docs/streamlit_dashboard_m1.md
- tasks/current_task.md · tasks/backlog.md · tasks/completed.md
- context/handoff.md · context/handoff/
