# Current Task

## Bloco atual

ID: BLK-DIM-08
Nome: Teste discriminativo do mercado residual (performers × underperformers) + estrutura regional
Status: aprovado (APROVADO)
Tipo: análise (modelagem estatística; READ-ONLY sobre M1)
Criticidade: alta
Esteira: Block Orchestrator → Planner → [no loop: guard automático] → Builder → QA
Skill atual: QA (concluído)
Próxima Skill: Fechamento (housekeeping + commit)

## Veredito do QA (2026-06-15)
APROVADO. Suíte FULL 902 passed, 4 skipped (skips pré-existentes); 13 testes novos
verdes com wiring real (não skipped); ruff/mypy limpos; import streamlit ok.
NO-GO honesto (AUC 0.4801, IC [0.4233, 0.5354] cruza 0.5). Guardrails M1 READ-ONLY,
anti-PII, anti-circularidade LOO e sem previsão pontual verificados. Housekeeping
--check falha com "stub ausente" (EXIT 1) = ESPERADO pré-move (Passo 6.0 do orquestrador).

## Objetivo
Medir honestamente se o mercado residual discrimina unidades viáveis (≥2k alunos) das não-viáveis (<2k),
separando efeitos região × marca × domínio (partial pooling LOO-CV), e reportar GO/NO-GO da tese residual
com AUC + intervalo de confiança. READ-ONLY sobre o M1.

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: sonnet
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/loop-20260615-124342 (branch autônomo do loop)

## Paths pré-sujos (NÃO commitar — alheios ao ciclo)
- PRD.md, CLAUDE.md, README.md, .env.example, .github/workflows/ci.yml e outros arquivos do worktree
