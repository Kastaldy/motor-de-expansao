# Current Task

## Bloco atual

ID: BLK-CENSO-01
Nome: Relatório censitário — camadas combinadas + fundo de ruas + faixas GeoFusion + pins com logo
Status: aprovado (QA 2026-06-05)
Tipo: feature
Criticidade: alta
Esteira: Block Orchestrator → Planner → [aprovação humana + DEC-004 tiles] → Builder → QA
Skill atual: QA concluído (APROVADO em 2026-06-05)
Próxima Skill: Fechamento manual (orquestrador — housekeeping Passo 6.0 + commit + deploy/validação visual)
Gate: DEC-004 (tiles online CartoDB Positron) APROVADA por Felipe em 2026-06-05 → Builder concluído; subconjunto verde (192 passed), ruff+mypy limpos, import ok
dry_run: false

## Tiering de modelo (Passo 4)
- Block Orchestrator: opus (override +1 da tabela Alta=sonnet — ciclo toca guardrail de API ao vivo + exige formalizar DEC; vale leitura de contexto mais cuidadosa)
- Planner: opus (Alta)
- Builder: opus (Alta)
- QA: opus 4.8 (sempre)

## Objetivo
Entregar UMA exportação do Relatório Pontual Censitário com renda + população + concorrentes
juntos, fundo de ruas (tiles online só na geração, com cache + fallback offline), faixas de cor
absolutas estilo GeoFusion e pins com logo — READ-ONLY sobre M1/score.

## Paths do ciclo (a confirmar/expandir pelo Planner)
- src/motor_expansao/dashboard/censo_map.py
- src/motor_expansao/dashboard/pages.py
- src/motor_expansao/dashboard/censo_report.py
- src/motor_expansao/dashboard/competitors.py (reuso preload_logos)
- pyproject.toml (extra de basemap/tiles)
- tests/unit/test_relatorio_pontual_censitario_{motor,mapa,export}.py
- tests/integration/test_streamlit_app.py
- docs/relatorio_pontual_censitario.md
- CLAUDE.md (§4 linha do relatório + DEC §8)

## Fora de escopo (invioláveis)
- Recálculo/escrita de M1 (scoring/pesos/artefatos oficiais)
- Mudar método de interseção setor x 1.5 km ou o raio
- Tornar o dashboard interativo dependente de internet (desvio de tiles só no relatório)
- Template/diagramação final do PDF (BLK-CENSO-02)
