# Current Task

## Bloco atual

ID: BLK-OPS-04
Nome: Validação de schema no carregamento
Status: APROVADO — ciclo fechado (housekeeping --check verde + commit por path); aguardando merge humano
Tipo: feature
Criticidade: Média (confirmada pelo Block Orchestrator — trigger "Crítica" NÃO se aplica: validação é read-only, só lê e rejeita; não recalcula/muta score nem artefato M1)
Esteira: Block Orchestrator → Planner → Builder → QA (sem gate humano)
Skill atual: Fechamento (orquestrador) — concluído
Próxima Skill: Merge humano da branch ciclo/BLK-OPS-04
dry_run: false

## Objetivo
O dashboard deve falhar de forma clara (não mostrar lixo) se um Parquet vier corrompido ou
com schema/range inesperado: asserções de schema no caminho de load (`data.py`) — colunas
obrigatórias, dtypes, scores em `[0, 100]`, chaves não-nulas, `h3` válido — com mensagem de
erro útil. Validação é **read-only**: nunca corrige/preenche dados silenciosamente.

## Paths do ciclo (commit por path — NUNCA git add -A)
- src/motor_expansao/dashboard/schemas.py  (módulo novo de schema)
- src/motor_expansao/dashboard/data.py  (+import +1 chamada em read_enriched_uf_partition)
- streamlit_app.py  (+import +1 chamada em _read_m1_frame — plumbing mínimo autorizado pelo BO)
- tests/unit/test_schema_validation.py  (NOVO)
- tests/integration/test_streamlit_app.py  (fixtures migrados p/ H3 real — QA julgou desvio aceitável)
- tasks/current_task.md · tasks/backlog.md · tasks/completed.md
- context/handoff.md · context/handoff/

## Contexto de abertura
- Branch isolado: `ciclo/BLK-OPS-04` (criado a partir do HEAD de main, worktree limpo).
- Backlog classifica como **Média** (esteira sem gate humano). O Block Orchestrator deve
  avaliar EXPLICITAMENTE se o trigger Crítica do run-cycle/CLAUDE.md ("menção a
  score_priorizacao / artefato M1") se aplica — sendo a validação estritamente read-only
  (lê colunas de score dos artefatos M1, não muta nem recalcula nada).
- Este ciclo NÃO altera a orquestração → dry-run 6.c NÃO dispara.
- Guardrail: validação não pode recalcular/alterar score, carteira, plano ou artefatos M1.
