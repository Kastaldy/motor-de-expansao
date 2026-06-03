# Current Task

## Bloco atual

ID: BLK-FIX-06-C
Nome: Orla não renderiza no dashboard apesar dos dados corretos (display/render)
Status: aprovado (QA, 2026-06-03)
Tipo: bug
Criticidade: alta
Esteira: Block Orchestrator → Planner → [aprovação humana] → Builder → QA
Skill atual: QA (Builder concluído por Felipe em 2026-06-03; handoff em context/handoff.md)
Próxima Skill: QA
dry_run: false

## Decisões de produto aprovadas no gate (Felipe, 2026-06-03)
- (i) Cor descartado <5k: `_DISCARDED_FILL = [150,150,170,150]` (alpha 150, visível).
- (ii) Score NaN nos modos operacionais: relaxar scope + cor de fallback `_NAN_SCORE_FILL` (orla aparece em todos os modos).
- (iii) Tabelas de carteira/domínio: NÃO mexer neste ciclo.
- (iv) Duas cores de exceção DISTINTAS (descartado-<5k ≠ sem-score-NaN).

## Nota de classificação (override de tiering, 1 linha)
Bloco rotulado "Média" no backlog, mas a esteira do bloco pede [revisão humana] e o fix
interage com LEITURA de score (cap por `score_priorizacao`, cor por colunas de score) →
CLAUDE.md §2 "LEITURA/ANÁLISE de score → Alta (revisão humana antes do Builder)". Classificado
como **Alta**: gate humano + Planner/Builder em Opus (risco de re-misdiagnóstico data-vs-render).
QA sempre Opus 4.8.

## Objetivo
Fazer os hexes da orla (Praia Grande/Mongaguá/litoral) aparecerem VISIVELMENTE no dashboard
(M1 e, idealmente, modos operacionais) corrigindo o caminho de RENDER/DISPLAY — sem mexer em
M1/score/artefatos/dados (já corretos e deployados no VPS).

## Escopo permitido
- src/motor_expansao/dashboard/* (render/cor/legenda/cap)
- testes correspondentes

## Fora de escopo
- base_h3_brasil.py / M1 / artefatos oficiais (BLK-FIX-06-B já fechou)
- regenerar dados / redeploy de parquets
- mudar pesos/fórmula/score

## Paths candidatos do ciclo (a confirmar pelo Planner)
- src/motor_expansao/dashboard/components.py (_apply_pop_cut_colors, build_*_map_figure)
- src/motor_expansao/dashboard/constants.py (POP_MIN_ACIONAVEL, COLOR_MODES, MAP_POINT_LIMIT_*)
- src/motor_expansao/dashboard/utils.py (score_band_to_color, se aplicável)
- tests/ correspondentes
