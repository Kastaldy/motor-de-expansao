# Current Task

## Bloco atual

ID: BLK-OPS-11
Nome: Pinar dependências e restaurar paridade CI/local (CI vermelho nos testes)
Status: APROVADO — ressalva FECHADA. QA deu APROVADO COM RESSALVAS em 2026-05-31; a ressalva única (CI verde de ponta a ponta no GitHub Actions Python 3.11) foi CONFIRMADA no fechamento: run `26722016904` (workflow_dispatch em `ciclo/BLK-OPS-11`) verde — Lint→mypy→Testes→Smoke todos ✓, 554 passed / 73 skipped / 0 falhas / 0 erros de collection (3.11; os 73 skips são testes gated em dados reais gitignored ausentes no CI — não silenciamento). Aguarda apenas o merge humano da branch.
Tipo: operação / manutenção (ambiente/CI/config — não toca M1)
Criticidade: Alta
Esteira: Block Orchestrator → Planner → [REVISÃO HUMANA] → Builder → QA
Skill atual: run-cycle (fechamento)
Próxima Skill: (ciclo fechado) — aguarda merge humano de `ciclo/BLK-OPS-11` + confirmação `gh run watch`
dry_run: false

## Fechamento (orquestrador, 2026-05-31)
- Housekeeping 6.0 FEITO via `scripts/housekeeping_move_block.py BLK-OPS-11 --date 2026-05-31`
  (stub no backlog linha 135 + bloco em completed.md; `--check` OK; helper tests 10 passed).
- Commit por path FEITO na branch `ciclo/BLK-OPS-11` (sem `git add -A`; `PRD.md` não arrastado).
- RESSALVA ABERTA p/ o merge: confirmar CI verde de ponta a ponta no GitHub Actions (Python 3.11)
  via `gh run watch` antes do merge na base. A cura é independente de versão; falta provar o run real.
- Dry-run de orquestração: NÃO se aplica (ciclo não alterou run-cycle/prompts/esteira).

## Objetivo
Restaurar a paridade CI/local e deixar o gate de testes do CI verde de verdade (sem mascarar
falhas), pinando dependências não-pinadas no `pyproject.toml` (causa raiz: pydantic novo quebra o
padrão `@property CORES` em `Settings`; pandas 3.0/numpy 2.4 latentes), sem tocar M1/score/artefatos.

## Paths candidatos do ciclo (commit por path)
- pyproject.toml (pins/faixas)
- src/motor_expansao/config.py (CORES/Settings — só se Opção B)
- .github/workflows/ci.yml (constraints/lock, se necessário)
- eventual requirements*.txt / lockfile
- tasks/current_task.md · tasks/backlog.md · tasks/completed.md · context/handoff.md · context/handoff/

## Contexto de abertura
- Branch isolado: `ciclo/BLK-OPS-11` criado a partir do HEAD de `main` (worktree limpo).
- Commit SÓ por path; nunca `git add -A`. NÃO arrastar `PRD.md` nem edições não relacionadas.
- Criticidade Alta ⇒ gate de REVISÃO HUMANA após o Planner, antes do Builder.
- O ciclo anterior (BLK-SCORE-04) foi fechado/aprovado; este current_task o sobrescreve.
