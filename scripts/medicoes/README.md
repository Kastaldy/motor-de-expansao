# `scripts/medicoes/` — medições, comparações e backtests avulsos

Scripts que se rodam à mão, da raiz do repositório, para medir, comparar ou testar uma hipótese. Nenhum
código, CI ou rotina do servidor os chama; o resultado costuma ir para `data/analysis/` (fora do git) ou
para um documento. Até 01/11/2026 eles ficavam soltos em `scripts/`, e é por esse caminho que os registros
antigos (DECs, `tasks/completed.md`, `context/handoff/`) os citam.

| Script | O que faz (1ª linha da docstring) |
|---|---|
| `_scratch_atr_alvo_alunos_totais.py` | SCRATCH (READ-ONLY M1): revalida a estrutura ATR-03 trocando o ALVO de demanda de |
| `backtest_smartfit_scores.py` | Backtest de validacao (READ-ONLY M1): os scores correlacionam com a |
| `backtest_viab_multirede.py` | BLK-VIAB-04-FU: backtest do motor de viabilidade com N MAIOR (Ultra 54 + Eng Corpo 58 = 112) |
| `benchmark_hexid_category.py` | Benchmark: hex_id como category vs string em parquets de staging |
| `comparar_artefato_geo.py` | Gate de igualdade do artefato geo: prova que o rerun so' mudou o que deveria |
| `comparar_pressao_1km.py` | Comparativo: pressao concorrencial 2 km do centroide (atual) vs 1 km por area (novo) |
| `medir_impacto_litoral_blk_fix_06.py` | BLK-FIX-06 / FASE A (MEDICAO) — Impacto do criterio geometrico HIBRIDO no litoral |
| `medir_impacto_litoral_blk_fix_06b.py` | BLK-FIX-06-B (MEDICAO) — Impacto da geracao de candidatos por OVERLAP no litoral |
| `medir_sweep_litoral_06b.py` | BLK-FIX-06-B (LEQUE) — Recuperacao costeira por limiar de fracao-de-terra |
| `movimentacao_concorrencial.py` | Relatório de movimentação concorrencial — snapshot único (READ-ONLY sobre o M1) |
| `smoke_test_fontes.py` | scripts/medicoes/smoke_test_fontes.py — Smoke test das fontes de dados gratuitas |
| `validar_formato_viabilidade.py` | Validacao out-of-fold do filtro por formato na curva tamanho->densidade (BLK-VIAB-07) |
