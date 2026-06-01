# Current Task

## Bloco atual

ID: BLK-SEC-01
Nome: Gate de publicação no CI (publish só com CI verde) + pin de imagem e rollback
Status: APROVADO COM RESSALVAS (QA 2026-06-01) — ciclo fechado pelo orquestrador; aguarda merge humano de `ciclo/BLK-SEC-01` + prova Nível 3 real no Actions
Tipo: operação / segurança (CI/CD; afeta artefato de produção — não toca M1/score)
Criticidade: Alta
Esteira: Block Orchestrator → Planner → [REVISÃO HUMANA] → Builder → QA
Skill atual: run-cycle (fechamento concluído)
Próxima Skill: (ciclo fechado) — merge humano de `ciclo/BLK-SEC-01` na base; pós-merge, prova Nível 3 no Actions + pin real por digest no deploy

## Fechamento (orquestrador, 2026-06-01)
- Housekeeping 6.0 FEITO via `scripts/housekeeping_move_block.py BLK-SEC-01 --date 2026-06-01`
  (stub no backlog + bloco byte-idêntico em completed.md; `--check` OK; suíte `626 passed, 1 skipped`).
- Resumo de fechamento adicionado a `tasks/completed.md` (## Fechamento BLK-SEC-01).
- Commit por path na branch `ciclo/BLK-SEC-01` (sem `git add -A`; `PRD.md` não arrastado).
- Dry-run de orquestração: NÃO se aplica (não tocou run-cycle/prompts/esteira; só CI/CD + docs).
- RESSALVA p/ o humano: prova Nível 3 real no Actions (quebra proposital → `publish` skipped → reverter, anotar run id) + pin real por digest (`STREAMLIT_IMAGE=...@sha256:<digest>`) no deploy.
dry_run: false

## Objetivo
Garantir que SÓ imagens de um commit com CI verde sejam publicadas no GHCR e tornar o
deploy reproduzível/reversível (tag por SHA + pin por digest/SHA no compose de prod + runbook de rollback).

## Paths candidatos do ciclo (commit por path)
- .github/workflows/docker-publish.yml
- .github/workflows/ci.yml (se o gate exigir alteração)
- docker-compose.prod.yml
- docs/infra_producao.md (runbook de rollback)
- tasks/current_task.md · tasks/backlog.md · tasks/completed.md · context/handoff.md · context/handoff/

## Contexto de abertura
- Branch isolado: `ciclo/BLK-SEC-01` criado a partir do HEAD de `main` (worktree limpo).
- Commit SÓ por path; nunca `git add -A`. NÃO arrastar `PRD.md` nem edições não relacionadas.
- Criticidade Alta ⇒ gate de REVISÃO HUMANA após o Planner, antes do Builder.
- Depende de BLK-OPS-11 (CI verde de verdade) — já mergeado em `main` (commit 719b2ae).
- O ciclo anterior (BLK-OPS-11) foi fechado/aprovado e mergeado; este current_task o sobrescreve.
