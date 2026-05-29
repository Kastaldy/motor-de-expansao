# Current Task

## Bloco atual

ID: BLK-OPS-02
Nome: CI completo + build via registry (fora da prod)
Status: aprovado com ressalvas (QA 2026-05-29 19:01 — CI completo verde no runner limpo 460 passed/73 skipped/0 failed no commit 4af99de run 26664015146; baseline local 532 passed/1 skipped intacto; M1/score/artefatos NÃO tocados; ressalvas aprovadas: ruff/mypy informativo→BLK-OPS-02b, Docker Publish verificado-na-fusão). Liberado para MERGE humano.
Tipo: operação / infraestrutura
Criticidade: alta
Esteira: Block Orchestrator → Planner → [aprovação humana] → Builder → QA → [merge humano]
Skill atual: QA (concluído)
Próxima Skill: MERGE humano (fechamento) — depois acompanhar 1º run docker-publish.yml no push à main
Gate de aprovação humana: APROVADO POR Felipe Silva EM 2026-05-29 (plano ajustado: PR de ciclo + .gitignore fixtures + ruff/mypy escopo limitado/BLK-OPS-02b)
Branch do ciclo: ciclo/BLK-OPS-02
dry_run: false

## Objetivo
O gate do `main` deve rodar a suíte completa de testes (hoje só 2 arquivos + smoke import)
e o deploy deve usar imagem buildada no CI e empurrada para um registry (ex.: GHCR) — o
servidor faz `pull`, não `build`.

## Paths candidatos do ciclo (commit por path no fechamento)
- Código/infra: `.github/workflows/ci.yml`, novo workflow de build/push, `tests/fixtures/` (se criadas), `docs/deploy.md`.
- Controle: `tasks/current_task.md`, `tasks/completed.md`, `tasks/backlog.md` (marcar BLK-OPS-02), `context/handoff.md`, `context/handoff/`.
- Pré-sujeira `M tasks/backlog.md`: edição interna ao próprio bloco BLK-OPS-02 (nota de verificação externa) — é path do ciclo, será incluída. NÃO arrastar `PRD.md` nem qualquer arquivo não relacionado.

## Guardrails ativos
- Fora de escopo: alterar lógica de scoring, alterar artefatos M1, executar deploy no VPS.
- Fixtures de teste NÃO contêm dados reais de Ultra/Skyfit/Wellhub.
- Deploy efetivo no VPS é passo humano, fora deste bloco.
- CLAUDE.md §6: nenhum comando no VPS sem confirmação humana por comando (não aplicável a este bloco, que é CI/build, mas vale como guardrail permanente).

## Nota de orquestração
Este ciclo NÃO altera a própria orquestração (run-cycle.md / prompts / esteira) → NÃO dispara dry-run pós-merge.
