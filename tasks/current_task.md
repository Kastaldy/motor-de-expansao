# Current Task

## Bloco atual

ID: BLK-DIM-12
Nome: UI da esteira property-first: ferramenta de viabilidade do imóvel no dashboard
Status: aprovado
Tipo: feature (nova tela no dashboard de produção; READ-ONLY sobre M1)
Criticidade: alta
Esteira: Block Orchestrator → Planner → [aprovação humana — Felipe/Vini] → Builder → QA
Skill atual: QA
Próxima Skill: Fechamento manual (Passo 6.0 — housekeeping move BLK-DIM-12 via helper + merge)

## Veredito do QA (2026-06-15)
APROVADO. Suíte full `955 passed, 1 skipped` (exit 0); ruff/mypy limpos; import ok;
7 novos testes verdes. READ-ONLY M1 confirmado (só pages.py/streamlit_app.py/test
mudaram em 871d3db; engine BLK-DIM-11 e config M1 intocados). DEC-009 anti-geográfico
verificado por código e por teste. Offline/performance preservados. Housekeeping --check
falha PRÉ-move como esperado; move a executar no fechamento. Detalhe em context/handoff.md.

## Resultado do Builder (aguardando QA)
- Implementado Opção B (5ª aba "Viabilidade do Imovel"); engine BLK-DIM-11 reusado e INTOCADO.
- Subconjunto: ruff OK, mypy OK, `import streamlit_app` OK, `tests/integration/test_streamlit_app.py` 190 passed (-n auto), 7 novos testes verdes.
- Handoff: context/handoff.md + snapshot context/handoff/20260615-174958-builder.md.

## Gate humano (APROVADO)
APROVADO POR Felipe Silva EM 2026-06-15.
Decisão de UX: **Opção B — nova aba "Viabilidade do Imóvel"** (5ª aba via render_tab_selector).
Plano técnico do Planner aprovado integralmente, com o delta da Opção B (passos 3 e 5).

## Objetivo
Tela no dashboard onde o operador insere um imóvel real (lat,lng + m² + aluguel
pedido + demanda como premissa explícita) e lê a viabilidade (break-even, aluguel-teto,
ROI, sensibilidade, faixa de alunos, contexto do entorno), reusando o engine
`analisar_viabilidade_ponto` (BLK-DIM-11). Sem nunca prever demanda pela geografia.
READ-ONLY M1; offline; preserva performance do dashboard.

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: sonnet
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-DIM-12

## Paths pré-sujos (NÃO commitar — alheios ao ciclo)
- data/raw/ibge/malha_brasil.geojson (deletado no worktree)
- data/raw/ibge/malha_uf_brasil.geojson (deletado no worktree)
