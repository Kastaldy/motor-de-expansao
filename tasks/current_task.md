# Current Task

## Bloco atual

ID: BLK-OPS-08
Nome: Atualizar actions do CI para Node 24 (fim do Node 20)
Status: CONCLUÍDO (Builder aplicou; esteira Baixa não inclui QA). Liberado para MERGE humano.
Tipo: operação / infraestrutura
Criticidade: baixa
Esteira: Block Orchestrator → Builder
Skill atual: Builder (concluído)
Próxima Skill: MERGE humano (fechamento) — confirmar aviso Node 20 sumiu no run pós-merge
Branch do ciclo: ciclo/BLK-OPS-08
dry_run: false

## Objetivo
Atualizar `.github/workflows/ci.yml` e `.github/workflows/docker-publish.yml` para versões de
actions que rodam em Node 24 (eliminar o aviso de descontinuação do Node 20), sem alterar
comportamento de testes/build, scoring ou artefatos M1.

## Paths candidatos do ciclo (commit por path no fechamento)
- Infra: `.github/workflows/ci.yml`, `.github/workflows/docker-publish.yml`.
- Controle: `tasks/current_task.md`, `tasks/completed.md`, `tasks/backlog.md` (marcar BLK-OPS-08),
  `context/handoff.md`, `context/handoff/`.
- NÃO arrastar `PRD.md` nem `tasks/backlog.md` edição pré-existente não relacionada.

## Guardrails ativos
- Fora de escopo: mudar lógica de CI, steps de teste, scoring, artefatos M1.
- CLAUDE.md §6: nenhum comando no VPS.

## Nota de orquestração
Este ciclo NÃO altera a própria orquestração (run-cycle.md / prompts / esteira) → NÃO dispara dry-run.
