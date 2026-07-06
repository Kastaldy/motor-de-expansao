# Current Task

## Bloco atual

ID: BLK-ATR-04
Nome: Visualização dos resultados do funil (gráficos + números concretos para decisão)
Status: CICLO FECHADO — APROVADO (housekeeping OK + commit por path feito; merge = humano)
Tipo: análise visual (relatório estático — READ-ONLY M1)
Criticidade: média
Esteira: Block Orchestrator → Planner → Builder → QA (autônoma no loop)
Skill atual: QA (concluído)
Próxima Skill: Fechamento manual (sucessor BLK-ATR-05 é manual/gate humano)

## Veredito QA
APROVADO. Suíte FULL 1354 passed / 4 failed (openlocationcode pré-existente, não relacionado);
ruff limpo; imports proibidos vazio; matplotlib declarada no pyproject; loop_guard OK;
import streamlit_app ok; mtime dos 4 oficiais M1 inalterado; housekeeping executado pelo helper
versionado (bloco byte-idêntico movido para completed.md, stub no backlog). Regressões novas = 0.

## Objetivo
Gerar relatório visual completo (gráficos PNG + markdown-resumo) em data/analysis/viz_atratividade/,
consumindo outputs dos blocos ATR-01/02/03. Conteúdo: cobertura Huff antes/depois, impacto do gate,
matriz de quadrantes residual×disputa, comparação matriz vs composto, distribuições dos 3 eixos.
READ-ONLY M1, sem produção/VPS.

## Tiering de modelo (Passo 4) — Média
- Block Orchestrator: sonnet
- Planner: sonnet
- Builder: sonnet
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-ATR-04

## Paths do ciclo (commit por path — NUNCA git add -A)
- src/motor_expansao/demanda_revelada/viz_atratividade.py (novo módulo de geração de gráficos)
- tests/unit/demanda_revelada/ (testes)
- data/analysis/viz_atratividade/ (PNGs + markdown — gitignored, não commitar)
- tasks/current_task.md, tasks/completed.md, tasks/backlog.md (fechamento)
- context/handoff.md, context/handoff/

## Guardrails
- §5 (READ-ONLY M1): mtime dos 4 oficiais M1 inalterado.
- Apenas Matplotlib (sem Plotly/kaleido — evitar dep nova).
- Sem PII pessoal em nenhuma imagem/legenda.
- data/analysis/viz_atratividade/ é gitignored (não commitar PNGs).
- Isolamento: módulo NÃO importa de pipelines/m1, dashboard, censo_*, api.
- DEC-012: só agregados/negócio nas imagens.

## Depende de (satisfeito)
- BLK-ATR-01 (concluído 2026-07-06 — módulo concorrentes_densos.py)
- BLK-ATR-02 (concluído 2026-07-06 — flag_gate_atratividade)
- BLK-ATR-03 (concluído 2026-07-06 — estrutura_funil.py)
