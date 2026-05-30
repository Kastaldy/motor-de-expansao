# Current Task

## Bloco atual

ID: BLK-OPS-10
Nome: Automatizar housekeeping de concluídos no Passo 6 do /run-cycle (helper versionado)
Status: APROVADO (aguardando commit por path + merge humano + dry-run 6.c pós-merge)
Tipo: manutenção / orquestração + tooling
Criticidade: alta (altera a própria orquestração → dispara dry-run autônomo no 6.c)
Esteira: Block Orchestrator → Planner → [APROVAÇÃO HUMANA: ok] → Builder → QA → (pós-merge: dry-run 6.c)
Skill atual: run-cycle (fechamento)
dry_run: false

## Resultado (APROVADO pelo QA)
- Helper versionado scripts/housekeeping_move_block.py (move_block/verify_moved puros + CLI;
  byte-identity por fatia literal; CRLF preservado via newline=""; EXIT_AD_HOC=3).
- tests/unit/test_housekeeping_helper.py: 10 testes (inclui idempotência re-entrante + CRLF).
- .claude/commands/run-cycle.md: Passo 6.0 (move via helper, antes de 6.a) + bullet 6.c (dummy block na
  branch do dry-run, abandona sem merge) + guardrail permanente. Rótulos 6.a–6.d preservados.
- prompts/qa_analyzer.md: checklist de housekeeping exigindo o helper (--check + byte-identity + pytest).
- Validações: pytest -q → 542 passed, 1 skipped; ruff clean; smoke CLI contra conteúdo REAL (CRLF) ok.
- Defeitos achados no QA e corrigidos: regex do stub em CRLF (verify_moved) + ruff I001 (import sort).

## Paths do ciclo (commit por path — NUNCA git add -A)
scripts/housekeeping_move_block.py · tests/unit/test_housekeeping_helper.py ·
.claude/commands/run-cycle.md · prompts/qa_analyzer.md · tasks/current_task.md ·
context/handoff.md · context/handoff/

## Pendência humana
- Revisar a branch ciclo/BLK-OPS-10 e fazer o merge em main.
- PÓS-MERGE: este ciclo ALTERA a orquestração → o orquestrador roda o dry-run autônomo (6.c)
  exercitando o novo 6.0 num ciclo dummy Baixa (bloco dummy na branch, abandona sem merge).
