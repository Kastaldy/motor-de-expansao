# Current Task

## Bloco atual

ID: BLK-PROD-02
Nome: Limpar leftovers de staging
Status: aprovado
Tipo: manutenção
Criticidade: baixa
Esteira: Block Orchestrator → Builder (baixa criticidade, sem Planner/QA)
Skill atual: fechamento (housekeeping concluído)
Próxima Skill: — (ciclo encerrado)

## Objetivo
Remover exclusivamente `tmp_codex_runtime/` e `data/outputs/*.tmp.parquet` (paths pré-aprovados no backlog).

## Resultado do Builder
- `/repo/tmp_codex_runtime/` removido (continha: manual_pytest, pytest, pytest_alt, qa_pytest_full.log, write_test.txt)
- `/repo/data/outputs/monitoramento_expansao_hibrido_base.tmp.parquet` removido
- `/repo/data/outputs/oportunidades_expansao_hibrido.tmp.parquet` removido
- Artefatos M1 (brasil_estrutural, brasil_priorizados, hexagonos_brasil_dashboard): mtime INALTERADO
- ruff: All checks passed!
- smoke import: ok
- Housekeeping BLK-PROD-02: OK (stub no backlog + bloco em completed.md)

## Branch do ciclo
ciclo/loop-20260707-123809

## Paths do ciclo (commit por path — NUNCA git add -A)
- tasks/current_task.md, tasks/completed.md, tasks/backlog.md
- context/handoff.md, context/handoff/
