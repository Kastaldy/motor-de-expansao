# Current Task

## Bloco atual

ID: BLK-ARCH-01a
Nome: Migrar `jobs/pipelines/*` para `src/` e limpar `pythonpath`
Status: APROVADO COM RESSALVAS (housekeeping 6.0 feito; aguardando commit por path + merge humano)
Tipo: refatoração
Criticidade: alta
Esteira: Block Orchestrator → Planner → [APROVAÇÃO HUMANA: ok 2026-05-29] → Builder → QA
Skill atual: run-cycle (fechamento)
Próxima Skill: —
dry_run: false

## Resultado (APROVADO COM RESSALVAS pelo QA)
- FATIA-2 (final): os 20 módulos de `jobs/pipelines/*` movidos para `src/motor_expansao/pipelines/`
  (destino flat, via `git mv`); diretório `jobs/` removido; `pythonpath` `[".", "src"]` → `["src"]`.
- Única alteração de valor: `parents[2]` → `parents[3]` em 14 módulos (profundidade + `src/`);
  `sys.path.insert`+`import sys` removidos nos 8 que os tinham; 16 testes reapontados.
- 4 literais/docstrings cosméticos `jobs/pipelines/...` preservados (um asserido por teste).
- Validações (QA re-executou, sem bypass): `pytest -q` → 541 passed, 1 skipped, 0 failed;
  `import streamlit_app` ok; `ruff check .` limpo; `mypy src/` Success (44 arquivos); grep de import
  de raiz vivo VAZIO; zero `parents[2]` em `src/.../pipelines/`.
- Prova de não-mutação M1: 4 artefatos oficiais com sha256 byte-idêntico pré/pós. Params canônicos intactos.
- RESSALVA (não bloqueante): mover os módulos legados (nunca type-checked) para `src/` expôs 50 erros
  de tipo latentes ao gate `mypy src/`. Resolvido com `[[tool.mypy.overrides]] ignore_errors = true`
  NOMINAL aos 14 módulos (NÃO glob; QA confirmou que não mascara código antes checado). Dívida de
  tipagem registrada como BLK-ARCH-01b no backlog.
- Com BLK-ARCH-01a, a dualidade `src/` vs. legado de raiz está ELIMINADA.

## Paths do ciclo (commit por path — NUNCA git add -A)
src/motor_expansao/pipelines/*.py (20 módulos movidos) · pyproject.toml ·
tests/** (16 reapontados) · tasks/current_task.md · tasks/backlog.md · tasks/completed.md ·
context/handoff.md · context/handoff/ · (removidos: jobs/pipelines/*.py + jobs/)

## Pendência humana
- Revisar a branch ciclo/BLK-ARCH-01a e fazer o merge em main (Passo 6.b).
- Este ciclo NÃO altera a orquestração (run-cycle/prompts/esteira) → dry-run 6.c NÃO dispara.
- Bloco-filho aberto: BLK-ARCH-01b (tipar os 14 módulos + remover o override de mypy).
