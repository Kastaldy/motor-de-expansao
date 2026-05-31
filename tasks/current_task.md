# Current Task

## Bloco atual

ID: BLK-SCORE-02
Nome: Poder preditivo dos scores vs. desfecho
Status: aprovado (QA 2026-05-31 — APROVADO; 617 passed/1 skipped; READ-ONLY M1 confirmado; pronto para fechamento pelo orquestrador)
Tipo: feature (análise estatística / backtest — read-only sobre M1)
Criticidade: Alta (LEITURA/ANÁLISE de score sem escrita em artefato M1 → revisão humana antes do Builder; regra CLAUDE.md 2026-05-30; backlog classifica Alta)
Esteira: Block Orchestrator → Planner → [revisão humana] → Builder → QA
Skill atual: Orquestrador (fechamento concluído)
Próxima Skill: — (ciclo concluído; merge pelo humano)
Status final: APROVADO (QA 2026-05-31). Housekeeping via helper OK (stub no backlog + bloco em completed.md). Commit por path feito; aguarda merge humano de `ciclo/BLK-SCORE-02`.
dry_run: false

## Objetivo
Medir, sobre o dataset rotulado (`data/analysis/dataset_validacao.parquet`), quanto cada score
(M1/`score_priorizacao`, censitário, residual, domínio) prevê `alunos_recorrentes` — por rede e no
agregado —, decompor o M1 (renda vs. pop, testando empiricamente o 0.40/0.60), controlar por
maturação e relatar os achados em `data/analysis/relatorio_backtest.md`, SEM proposta de mudança
(isso é o BLK-SCORE-03) e sem qualquer escrita em artefato/fórmula/peso do M1.

## Guardrails do ciclo (do backlog)
- Estritamente ANALÍTICO e READ-ONLY. Nenhuma alteração em `scoring.py`/`constants.py`/artefatos M1.
- FORA DE ESCOPO: alterar pesos, fórmula ou artefatos M1 (isso é o BLK-SCORE-03).
- N pequeno por rede pode limitar conclusões — relatar incerteza honestamente, não forçar significância.
- Saída só em `data/analysis/` (gitignored), nunca `data/outputs/`. PII fora de logs/handoff/relatório.

## Paths prováveis do ciclo (commit por path — NUNCA git add -A; CLAUDE.md NÃO entra)
- analysis/score_backtest.py (novo — script de backtest fim a fim)
- tests/unit/test_score_backtest.py (novo — testes do backtest, se aplicável)
- data/analysis/relatorio_backtest.md (+ figuras) (regenerado — gitignored)
- tasks/current_task.md · tasks/backlog.md · tasks/completed.md
- context/handoff.md · context/handoff/
- Arquivos a LER (não alterar): data/analysis/dataset_validacao.parquet ·
  src/motor_expansao/core/scoring.py · src/motor_expansao/core/constants.py

## Contexto de abertura
- Branch isolado: `ciclo/BLK-SCORE-02`, criado a partir de `main` (HEAD 121a4eb, BLK-SCORE-01a já mergeado).
- Worktree pré-sujo (NÃO commitar neste ciclo): `M CLAUDE.md`. Commit SÓ por path; nunca `git add -A`.
- Criticidade Alta ⇒ gate de revisão humana APÓS o Planner, ANTES do Builder.
- Depende de BLK-SCORE-01/01a (dataset rotulado já entregue: 441 linhas; Ultra 53/54, Skyfit 301/326, EngCorpo 37/61).
