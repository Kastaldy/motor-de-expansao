# Current Task

## Bloco atual

ID: BLK-DIM-11
Nome: Esteira property-first: motor de viabilidade do imóvel (break-even, aluguel-teto, sensibilidade)
Status: aprovado (APROVADO)
Tipo: feature (nova esteira de produto; módulo isolado; READ-ONLY sobre M1)
Criticidade: alta
Esteira: Block Orchestrator → Planner → [no loop: guard automático] → Builder → QA
Skill atual: QA (concluído)
Próxima Skill: Fechamento (Passo 6.0)

## Veredito QA (2026-06-15)
APROVADO. Suíte FULL 936 passed, 4 skipped; ruff/mypy limpos; import ok.
Guardrails todos verificados: READ-ONLY M1, demanda sempre premissa explícita
(demanda_fonte="premissa_explicita"), faixa_alunos_por_densidade sem lat/lng,
catchment como dict, sem I/O parquet, sem PII, commit isolado (83e9727).
10 testes do módulo passaram; test_faixa_usa_curva_densidade_nao_geo verde (anti-geográfico).

## Objetivo
Dado um imóvel real (lat,lng + m² + aluguel pedido), devolver contexto + break-even +
aluguel-teto + ROI + grade de sensibilidade + faixa de plausibilidade — sem nunca prever
demanda pela geografia. Módulo isolado `viabilidade_ponto.py`, função pura + testes
determinísticos. Saída estruturada (dict/relatório), sem UI.

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: sonnet
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/loop-20260615-163258 (branch autônomo do loop)

## Paths pré-sujos (NÃO commitar — alheios ao ciclo)
- PRD.md, CLAUDE.md, README.md, .env.example, .github/workflows/ci.yml e outros arquivos do worktree
