# Current Task

## Bloco atual

ID: BLK-DIM-21
Nome: UI: gráficos financeiros e curva de maturidade na aba de viabilidade
Status: em execução
Tipo: enriquecimento visual (READ-ONLY sobre M1)
Criticidade: média
Esteira: Block Orchestrator → Planner → Builder → QA
Skill atual: Builder
Próxima Skill: QA

## Objetivo
Adicionar 4 gráficos Plotly à seção de resultados da viabilidade no dashboard (`pages.py`), com nova função `gerar_serie_mensal()` em `simulador.py` que extrai a lógica do loop interno de maturação e retorna a série temporal mensal. Gráficos: curva de maturidade, faturamento+EBITDA, FCF acumulado, DRE breakdown (steady-state). Cards existentes preservados.

## Modo
LOOP AUTÔNOMO — sem gate humano (bloco loop-safe, READ-ONLY sobre M1)

## Tiering de modelo (Média)
- Block Orchestrator: sonnet
- Planner: sonnet
- Builder: sonnet
- QA: opus (sempre)

## Handoff disponível
`context/handoff.md` — gerado pelo Planner em 2026-06-22-152512
