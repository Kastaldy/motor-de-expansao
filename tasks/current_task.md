# Current Task

## Bloco atual

ID: BLK-FIX-07
Nome: Camada de pins de academias escalável (manter logos; alvo ~40k concorrentes)
Status: em execução
Tipo: bug (produção; render/transporte do dashboard — não toca M1/score)
Criticidade: Alta
Esteira: Block Orchestrator → Planner → [aprovação humana ✓ 2026-06-01] → Builder → QA
Skill atual: run-cycle (fechamento concluído)
Próxima Skill: (ciclo fechado) — merge humano de `ciclo/BLK-FIX-07` na base
Status: APROVADO (QA 2026-06-01) — ciclo fechado pelo orquestrador; aguarda merge humano
dry_run: false

## Fechamento (orquestrador, 2026-06-01)
- Housekeeping 6.0 FEITO via `python scripts/housekeeping_move_block.py BLK-FIX-07 --date 2026-06-01`
  (stub no backlog + bloco byte-idêntico em completed; `--check` OK; content-identity confirmada;
  `test_housekeeping_helper.py` 10 passed; suíte completa `639 passed, 1 skipped`).
- Resumo de fechamento adicionado a `tasks/completed.md` (## Fechamento BLK-FIX-07).
- Follow-up `BLK-FIX-07-B — Clustering server-side por recorte (Fase B)` adicionado ao backlog
  (recomendação Planner/QA; não-bloqueante — bound de 40k já garantido pela Fase A).
- Commit por path na branch `ciclo/BLK-FIX-07` (sem `git add -A`; `PRD.md`/dados/`config.py` não arrastados).
- Dry-run de orquestração: NÃO se aplica (não tocou run-cycle/prompts/esteira; só dashboard render + testes + docs).

## Veredito QA (2026-06-01)
VEREDITO: APROVADO (sem bloqueadores). 5 validações verdes (159 integração; 639 passed/1 skipped =
baseline 631 + 8 novos; import ok; ruff/mypy limpos). Rigor próprio confirmou: pitfall pydeck `@@=`
neutralizado (iconAtlas literal); cap 40k -> 6.000 linhas ~2,05 MB; SP-like 1.381 sem corte ~484 KB e
tooltips idênticos; logos realmente embutidos no atlas (2.276 px no tile/offset correto); caption só
acima do cap; center/zoom da Visão Executiva preservados. Sem bypass; guardrails M1/cor/BLK-FIX-02/03
intactos; data/config/scoring/pipelines não tocados; backlog não tocado. Housekeeping --check = stub
ausente (não movido; Passo 6.0 do orquestrador). Detalhe em context/handoff.md + snapshot
20260601-125252-qa.md.

## Aprovação humana
APROVADO por Felipe Silva em 2026-06-01. Escopo: Fase A (atlas + payload enxuto + cap duro).
Fase B (clustering) fica como follow-up BLK-FIX-07-B. Instrução explícita: QA rígido — garantir
integridade do código e funcionamento real do app, não só suíte verde.

## Objetivo
Tornar a camada de pins de concorrentes/Ultra do Mapa Territorial escalável a ~40k concorrentes
mantendo os logos, sem crash de memória client-side (SP real, 1.381 pins, deixa de travar), sem
recalcular/alterar M1/score/artefatos.

## Paths prováveis do ciclo (commit por path)
- src/motor_expansao/dashboard/components.py
- src/motor_expansao/dashboard/competitors.py
- src/motor_expansao/dashboard/constants.py
- src/motor_expansao/dashboard/pages.py
- tests/integration/test_streamlit_app.py
- (docs se necessário) docs/streamlit_dashboard_m1.md
- tasks/current_task.md · tasks/backlog.md · tasks/completed.md
- context/handoff.md · context/handoff/
