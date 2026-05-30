# Current Task

## Bloco atual

ID: BLK-OPS-02b
Nome: Saneamento ruff/mypy (violações que exigem refatoração)
Status: em execução
Tipo: refatoração / qualidade
Criticidade: alta
Esteira: Block Orchestrator → Planner → [aprovação humana] → Builder → QA
Skill atual: QA / Quality Analyzer (concluído)
Status execução: aprovado
Veredito QA: APROVADO (2026-05-29 20260529-205955) — ruff 0, mypy 0, pytest 532/1, import ok, 4 hashes M1 idênticos, parâmetros canônicos intactos. Handoff em context/handoff.md + snapshot context/handoff/20260529-205955-qa.md.
Próxima Skill: Fechamento manual (orquestrador commita por path e encerra o ciclo)
Gate de aprovação humana: APROVADO POR Felipe Silva EM 2026-05-29 (plano de 13 passos como está; F601/F821/mypy corrigidos, B019 suprimido com # noqa documentado, CI bloqueante ao fim; prova anti-regressão pytest 532/1 + hashes M1 a cada passo).
Branch do ciclo: ciclo/BLK-OPS-02b
dry_run: false

## Objetivo
Zerar as violações ruff/mypy descobertas em BLK-OPS-02 (286 ruff + 23 mypy), preferindo correção
a supressão, e tornar os steps ruff/mypy bloqueantes no CI — sem alterar lógica de scoring,
artefatos M1 ou semântica de testes M1, e mantendo `pytest -q` em 532 passed/1 skipped (zero regressão).

## Paths candidatos do ciclo (commit por path no fechamento)
- Código/infra: a serem listados pelo Planner após mapear as violações (produção `src/`, dashboard,
  `jobs/`, legado `fora_primeira_fase/`, testes, `pyproject.toml`/config de lint, `.github/workflows/ci.yml`).
- Controle: `tasks/current_task.md`, `tasks/completed.md`, `tasks/backlog.md` (marcar BLK-OPS-02b),
  `context/handoff.md`, `context/handoff/`.
- NÃO arrastar `PRD.md` nem edições não relacionadas.

## Guardrails ativos (CRÍTICOS para este bloco)
- Toca CÓDIGO DE PRODUÇÃO M1 (`hex_enrichment.py`, `base_h3_brasil.py`) — additivo/mecânico, mas
  exige prova anti-regressão a cada passo.
- Fora de escopo: alterar lógica de scoring/pesos, alterar artefatos M1, mudar semântica de testes
  M1 (F601 só pode ser tocado provando invariância do fixture).
- Preferir correção a supressão; `# noqa`/`# type: ignore` SEMPRE documentado quando o fix for arriscado.
- Critério de aceite: `ruff check .` → 0; `mypy src/` → 0; steps bloqueantes no CI; `pytest -q` mantém
  532 passed/1 skipped; hashes dos Parquets M1 inalterados.
- CLAUDE.md §6: nenhum comando no VPS.

## Gate de aprovação humana
OBRIGATÓRIO antes do Builder (criticidade Alta). Planner apresenta plano; orquestrador PARA e aguarda.

## Nota de orquestração
Este ciclo altera `.github/workflows/ci.yml` (tornar ruff/mypy bloqueantes) mas NÃO altera a própria
orquestração (run-cycle.md / prompts / esteira) → NÃO dispara dry-run pós-merge.
