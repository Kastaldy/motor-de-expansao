# Current Task

## Bloco atual

ID: BLK-LTV-02
Nome: Join territorial (pendurar retenção/LTV no hexágono da unidade)
Status: aprovado (QA — APROVADO, suíte full 1169 passed/1 skipped, M1 READ-ONLY confirmado)
Tipo: feature (join de dados; camada paralela READ-ONLY sobre o M1)
Criticidade: média
Esteira: Block Orchestrator → Planner → Builder → QA
Skill atual: Builder (concluído)
Próxima Skill: QA

## Objetivo
Via `hex_id` da ponte `data/staging/unidade_hex.parquet` (BLK-LTV-01), anexar a cada unidade as
features territoriais do Motor (`renda_per_capita`, densidade, `score_priorizacao`,
`score_expansao_hibrido`, `n_concorrentes_mapeados_1km/2km`, `pop_total_setor_2022`…) e as métricas
de retenção agregadas do Lifetime (`PROB_CANCEL_90D_MEDIA`, `LTV_PROSPECTIVO_12M_MEDIANO`),
respeitando `USAR_PROB_ABSOLUTA`/haircut. Entregável: `data/staging/unidade_territorio_retencao.parquet`.

## Tiering de modelo (Passo 4) — Média
- Block Orchestrator: sonnet
- Planner: sonnet
- Builder: sonnet
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-LTV-02 (criada a partir de ciclo/BLK-LTV @ HEAD, que contém BLK-LTV-01 commit 068b5fe).

## Paths pré-sujos (NÃO commitar — alheios ao ciclo)
- data/raw/ibge/malha_brasil.geojson (D), data/raw/ibge/malha_uf_brasil.geojson (D)
- scripts/backtest_smartfit_scores.py (??)

## Critérios de aceite (do backlog)
- 100% das linhas do M1 preservadas nas leituras; nenhuma escrita em artefato M1 oficial; suíte verde.

## Guardrails
- §5 (READ-ONLY M1); DEC-001 intacta. Nenhuma coluna/artefato M1 alterado.
- LTV_PROSPECTIVO_12M_* só no agregado por unidade; respeitar USAR_PROB_ABSOLUTA; haircut ~20%; N=88.
- Ultra.csv legado: sep=";", latin-1, 1 linha de metadado (se lido).
