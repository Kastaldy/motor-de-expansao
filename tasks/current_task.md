# Current Task

## Bloco atual

ID: BLK-DIM-18
Nome: Fix — faixa de alunos pela metragem ausente em produção (fallback para parquet de unidades)
Status: aprovado (QA APROVADO — 2026-07-01)
Tipo: bug (fix de produção; READ-ONLY sobre o M1)
Criticidade: alta
Esteira: Block Orchestrator → Planner → [aprovação humana] → Builder → QA
Skill atual: Builder (concluído)
Próxima Skill: QA (Opus 4.8)

## Objetivo
Adicionar fallback em `load_base_calibracao()` (streamlit_app.py) para usar
`data/staging/unidades_ultra_performance_hex.parquet` (colunas `metragem`/`alunos_reais`) quando
`data/staging/base_calibracao_multirede.parquet` não existir em produção, restaurando a exibição da
faixa de alunos p10/p50/p90 pela metragem no dashboard. Sem tocar M1/score/artefatos oficiais.

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: sonnet
- Planner: sonnet (override −1: fallback único totalmente especificado no backlog; design mínimo)
- Builder: opus (mantém tabela — mudança em código de produção streamlit_app.py)
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-DIM-18 (criada a partir de main @ HEAD).

## Paths pré-sujos (NÃO commitar — alheios ao ciclo)
- data/raw/ibge/malha_brasil.geojson (D), data/raw/ibge/malha_uf_brasil.geojson (D)
- scripts/backtest_smartfit_scores.py (??)

## Escopo permitido
- streamlit_app.py → função `load_base_calibracao()`: fallback para
  `STAGING_DIR / "unidades_ultra_performance_hex.parquet"` antes de retornar DataFrame vazio;
  derivar `alunos_por_m2` no fallback (mesma lógica existente).
- 1 teste cobrindo o caminho de fallback.

## Fora de escopo (invioláveis)
- regenerar o multirede; tocar viabilidade_ponto.py/simulador.py; M1; artefatos oficiais.

## Guardrails
- §5 (READ-ONLY M1); DEC-009 (dimensionamento consome demanda, não a prevê). Nenhuma coluna M1 alterada.
