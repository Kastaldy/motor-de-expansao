# Current Task

## Bloco atual

ID: BLK-TP-05
Nome: Re-teste honesto do elo demanda→captura (LOO vs baseline)
Status: aprovado (QA — 2026-06-30)
Tipo: modelagem/análise (READ-ONLY sobre o M1)
Criticidade: alta
Esteira: Block Orchestrator → Planner → [aprovação humana] → Builder → QA
Skill atual: QA/Quality Analyzer (concluído — APROVADO; handoff em context/handoff.md + snapshot 20260630-153845-qa.md)
Próxima Skill: Fechamento manual (move backlog→completed via scripts/housekeeping_move_block.py + commit pelo humano)

## Veredito do QA (2026-06-30)
APROVADO. GO honesto reproduzido independentemente do parquet real: R²_oof_log=+0,5750,
IC95 [+0,5576, +0,5959], n=5.341, zeros=11.234, alpha=10, kfold_5x5. Auditoria do GO honesto OK
(R² in-sample só rotulado; n_acad_parceiras excluído do modelo principal; métrica OOF sem
vazamento vs baseline da média; 6 confounds na nota; sem reabertura da Camada 2/Huff).
Suíte full: 1117 passed, 1 skipped, 0 failed (-n auto, sem bug de xdist). ruff (escopo+repo) /
mypy / import streamlit_app limpos. READ-ONLY M1 confirmado; pacote disjunto (DEC-012);
anti-PII por construção. Housekeeping verificado pré-fechamento (helper sadio, bloco íntegro no
backlog linha 953). Nenhum commit feito (fechamento humano).

## Resultado do Builder (2026-06-30)
- VEREDITO REAL = **GO** (R²_oof_log=+0,5750; IC95 [+0,5576, +0,5959]; n=5.341; alpha=10; kfold_5x5).
- Validações: pytest 18 passed/0 failed/0 skipped (test_backtest_tp05 + test_demanda_revelada_ingestao);
  ruff 0 erros; mypy 0 erros; import streamlit_app ok. Relatório real gerado em
  data/analysis/backtest_tp05.md (gitignored).
- READ-ONLY sobre o M1 mantido; pacote disjunto; anti-PII por construção. Reabertura da Camada 2
  (Huff) é gate humano, FORA deste bloco.

## Objetivo
Re-testar a regressão/Huff `alunos ~ demanda + dist_concorrente + concorrência` com **demanda
observada** (camada BLK-TP-01, não imputada), usando **LOO/k-fold repetido vs baseline da média**
(DEC-008; proibido R² in-sample). Reportar R²_LOO vs baseline com intervalos + flag de extrapolação
e emitir veredito GO/NO-GO honesto. Re-teste do que a DEC-009 marcou como NO-GO com demanda imputada.
NÃO altera score/pesos/artefatos M1.

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: sonnet
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-TP-05 (criada a partir de main @ c99bbff, escolha do humano: base = main limpo).

## Paths pré-sujos (NÃO commitar — alheios ao ciclo)
- data/raw/ibge/malha_brasil.geojson (D), data/raw/ibge/malha_uf_brasil.geojson (D)
- data/outputs/setores_censitarios_2022_geo/_report.md (??)
- scripts/backtest_smartfit_scores.py (??)

## Dependência
- BLK-TP-01 (camada `data/staging/demanda_revelada_h3.parquet`) — concluído e merged.

## Fora de escopo
- score/pesos/artefatos M1; recalibrar M1; usar demanda como preditor geográfico de magnitude
  (DEC-009); persistir PII; deploy VPS.

## Guardrails
- §5 (READ-ONLY M1); DEC-008 (LOO/k-fold vs baseline, banir R² in-sample, intervalos + flag de
  extrapolação); DEC-009 (demanda = insumo observado, NUNCA preditor geográfico de magnitude);
  DEC-012 (camada demanda revelada, anti-PII por construção, pacote disjunto).
