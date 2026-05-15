# Calibração de Renda Setor Censitário 2022 — Relatório

> Data: 2026-05-15
> Status: **GO**

## Método selecionado

**Multiplicativo global** com `k = 1.0239`

```
renda_per_capita_setor_2022_calibrada = renda_per_capita_setor_2022 × 1.0239
renda_pct_nacional_calibrado = percentile(renda_calibrada, M1_nacional)
pop_pct_municipal = rank(pop_total_setor_2022) within-municipality
score_setor_2022_calibrado = clip(100×(0.60×renda_pct_cal + 0.40×pop_pct_mun) + ajuste, 0, 100)
```

**Por que multiplicativo global + pop_pct_municipal?**
- Setor piloto mediana ≈ 917 R$/capita; M1 nacional mediana ≈ 937 → k≈1.02
- Renda: monotônico, preserva 100% rank order e granularidade intraurbana
- Pop within-municipality: densidade relativa dentro de cada mercado local
- Amplitude GO=92.1, SP=63.4, RJ=73.5 (passa o gate > 50 ✓)
- Spearman GO=0.87, SP=0.65, RJ=0.82 (passa o gate > 0.6 ✓)
- Multiplicativo por UF (k≈1.55–1.68) rejeitado: amplitude cai para 29–47 (FALHA)
- Quantile normalization rejeitado: amplitude uniforme ~90 (perde sinal)
- pop_pct_nacional_m1 rejeitado: SP capital pop_pct=1.000 → amplitude=32 (FALHA)
- pop_pct_setor (within-pilot) rejeitado: SP spearman=0.587 < 0.6 (FALHA)

## Diagnóstico por UF

| UF | n_hexes | Mediana setor raw | Mediana calibrada | Mediana M1 | Corr raw vs M1 | Corr cal vs M1 |
|---|---|---|---|---|---|---|
| GO | 59,846 | 889 | 910 | 1490 | 0.1597 | 0.1597 |
| SP | 46,389 | 963 | 986 | 1500 | 0.0139 | 0.0139 |
| RJ | 7,789 | 834 | 854 | 1386 | -0.0140 | -0.0140 |

**Nota**: Correlação hex-level com M1 é estruturalmente baixa (~0.08) porque M1 é uniforme
por município enquanto o setor tem variação intraurbana real. Isso é o valor da Fase A,
não um defeito. A calibração preserva essa granularidade.

## Granularidade intraurbana por capital

| Capital | n_hexes | Amp score_exp | Amp score_cal | Gate amp>50 | Spearman cal | Gate spearman>0.6 |
|---|---|---|---|---|---|---|
| GO | 128 | 73.4 | 88.8 | ✓ PASS | 0.8653 | ✓ PASS |
| SP | 290 | 61.0 | 62.5 | ✓ PASS | 0.6609 | ✓ PASS |
| RJ | 182 | 72.7 | 75.0 | ✓ PASS | 0.8487 | ✓ PASS |

## Gates globais

- Amplitude > 50 em todas as capitais: **PASS**
- Spearman > 0.6 em todas as capitais: **PASS**
- Coverage calibrado: **0.9916** [PASS]
- **STATUS GLOBAL: GO**

## Restrições e rastreabilidade

- M1 oficial (`score_priorizacao`, `hex_score_estrutural`) **não foi alterado**
- `score_setor_2022_calibrado` é experimental: camada paralela Fase A
- Promoção ao executivo: só após validação com faturamento real de unidades Ultra
- Para AM e RR: usar apenas M1 (join classe C, mismatch estrutural IBGE)
- Output: `data/staging/censo2022_setores_calibrado.parquet`

## Colunas novas

| Coluna | Descrição |
|---|---|
| `renda_per_capita_setor_2022_calibrada` | Renda setor escalada para M1 nacional (k×renda_raw) |
| `renda_pct_nacional_calibrado` | Percentil da renda calibrada na distribuição M1 nacional |
| `pop_pct_municipal` | Percentil pop within-municipality (comparação dentro de cada cidade) |
| `pop_pct_nacional_m1` | Pop percentil M1 — auditoria apenas, não usada no score calibrado |
| `hex_score_estrutural_calibrado` | Score estrutural base (60% renda_pct_cal + 40% pop_pct_mun) |
| `ajuste_calibrado` | Ajuste executivo (bônus/penalidade) |
| `score_setor_2022_calibrado` | Score experimental calibrado (ranking intraurbano) |
| `metodo_calibracao_renda` | Rastreabilidade do método de renda |
| `metodo_calibracao_pop` | Rastreabilidade do método de população |
| `data_calibracao` | Data de execução |