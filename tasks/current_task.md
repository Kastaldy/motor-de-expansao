# Current Task

## Bloco atual

ID: BLK-FIX-11
Nome: Tornar funcionais os 3 overlays "mortos" do Mapa Territorial (Alternativa A)
Status: APROVADO (QA 2026-06-10) — ciclo FECHADO pelo orquestrador (housekeeping feito: bloco em completed.md, stub no backlog; commit por path na branch ciclo/BLK-FIX-11). Aguardando MERGE humano. NÃO dispara dry-run (ciclo não altera a orquestração).
Tipo: bug (display/interação; READ-ONLY M1)
Criticidade: média
Esteira: Block Orchestrator → Planner → [REVISÃO HUMANA das decisões visuais ✓ 2026-06-10] → Builder ✓ → QA ✓ (APROVADO)
Skill atual: Fechamento (orquestrador) — concluído
Próxima Skill: Merge humano da branch ciclo/BLK-FIX-11
dry_run: false

## Tiering de modelo (Passo 4) — Média + gate humano de decisões visuais
- Block Orchestrator: sonnet
- Planner: sonnet
- Builder: opus  (override +1: nova camada de mapa `ancoras_dominio` + fiação de 3 overlays em 3 arquivos é atípicamente complexo p/ Média)
- QA: opus 4.8 (sempre)

## Objetivo
Fazer os 3 toggles inertes do Mapa Territorial (`hex_pesquisado`, `descartados_5k`, `ancoras_dominio`) realmente ligarem/desligarem suas camadas, coerentes com a legenda, sem regressão em `concorrentes`/`ultra` e READ-ONLY sobre o M1.

## Branch do ciclo
ciclo/BLK-FIX-11 (a partir de main @ b2770da)

## Worktree pré-sujo
(limpo no início; commitar SÓ paths do ciclo por path, nunca git add -A)

## Paths prováveis do ciclo (a confirmar pelo Planner)
- src/motor_expansao/dashboard/components.py
- src/motor_expansao/dashboard/pages.py
- src/motor_expansao/dashboard/constants.py (se ajustar OVERLAYS)
- tests/integration/test_streamlit_app.py
- tasks/backlog.md + tasks/current_task.md + tasks/completed.md
- context/handoff.md + context/handoff/

## Fora de escopo (invioláveis)
- Recalcular/alterar score/carteira/plano/artefatos M1 (§5)
- Mudar cap de pontos (MAP_POINT_LIMIT*/COMPETITOR_PIN_LIMIT/ULTRA_PIN_LIMIT) sem aprovação
- Tocar pipelines/m1/, scoring.py, config.py (parâmetros de score)
