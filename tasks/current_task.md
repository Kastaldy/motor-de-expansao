# Current Task

## Bloco atual

ID: BLK-TP-02
Nome: Validação: Demanda Revelada × Residual Fitness (relatório)
Status: APROVADO pelo QA (2026-06-25) — pronto para fechamento/merge humano
Tipo: análise/relatório (READ-ONLY sobre o M1)
Criticidade: média
Esteira: Block Orchestrator → Planner → Builder → QA
Skill atual: QA (concluído)
Próxima Skill: Fechamento manual (merge humano da branch ciclo/BLK-TP-02)

## Objetivo
Reproduzir e documentar a correlação demanda × `score_oportunidade_residual` (Spearman ~+0,52),
mapa de quadrantes (residual+ & demanda+) e divergências vs. o recorte top-20%/UF do M1.
Saída = relatório + (opcional) parquet de quadrantes. NÃO altera score/artefatos.

## Tiering de modelo (Passo 4) — Média
- Block Orchestrator: sonnet
- Planner: sonnet
- Builder: sonnet
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-TP-02 (criada a partir de main @ deb8f95).

## Paths pré-sujos (NÃO commitar — alheios ao ciclo)
- data/raw/ibge/malha_brasil.geojson (D), data/raw/ibge/malha_uf_brasil.geojson (D)
- scripts/backtest_smartfit_scores.py (??)

## Dependência
- BLK-TP-01 (camada `data/staging/demanda_revelada_h3.parquet`) — concluído e merged (PR #47).

## Fora de escopo
- score/pesos/artefatos M1; persistir PII; ingestão ao vivo na carga do dashboard; deploy VPS;
  os blocos sucessores BLK-TP-03..05.

## Estado do Builder (2026-06-25)

### Arquivos novos
- `src/motor_expansao/demanda_revelada/validacao.py` — 7 funções públicas + constantes
- `tests/unit/test_demanda_revelada_validacao.py` — 11 testes unitários (todos verde)
- `data/reports/demanda_revelada_validacao.md` — relatório gerado com dados reais

### Arquivos modificados
- `src/motor_expansao/demanda_revelada/__init__.py` — exporta `executar_validacao_completa`

### Resultados reais (N=16.411 hexes no inner join)
- Spearman primário: rho = 0.517, IC [0.506, 0.529], p ≈ 0 ***
- Spearman secundário: rho = 0.525, IC [0.513, 0.536], p ≈ 0 ***
- nota: score_oportunidade_residual tem mediana=0.0 no join → Q1+Q2 apenas (todos residual ≥ 0)

### Validações Builder
- pytest 19 passed, 0 failed (subconjunto impactado)
- ruff: All checks passed
- mypy: no issues found
- smoke import streamlit_app: OK

## Veredito QA (2026-06-25)
- VEREDITO: **APROVADO**
- Suíte full (gate único): **1115 passed, 1 skipped, 0 failed** (após instalar a dep BASE `openlocationcode`, ausente no ambiente local — 4 falhas de plus-code eram ambientais, fora do escopo do BLK-TP-02; provado instalando a lib).
- Subset impactado: 19 passed; ruff clean; mypy clean; import streamlit_app + módulo OK.
- READ-ONLY M1 confirmado: disjunção DEC-012 OK, artefatos M1/config intocados, DEC-001/009/012 intactas, anti-PII clean (relatório + parquet de quadrantes).
- Housekeeping: helper `--check` OK; `test_housekeeping_helper.py` 10 passed; backlog stub + bloco em completed.md; Autonomia marcada **loop-safe**.
- Próximo passo: fechamento/merge humano da branch ciclo/BLK-TP-02.
- Recomendação operacional não-bloqueante: re-rodar `pip install -e ".[dev]"` local.
