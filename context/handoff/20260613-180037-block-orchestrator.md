# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

---

## Dados disponíveis

### data/staging/ — arquivos relevantes para o BLK-DIM-06

| Arquivo | Shape | Colunas chave |
|---|---|---|
| `base_calibracao_maduras.parquet` | 54 × 22 | `unidade`, `uf`, `metragem`, `faturamento`, `pagantes_steady_state`, `ticket_steady`, `churn_steady`, `ativos_total_steady`, `inadimplente_steady`, `meses_desde_inauguracao`, `pop_captacao`, `renda_per_capita_captacao`, `n_setores_captacao` |
| `growth_api_historico.parquet` | 61844 × 29 | `unidade`, `data`, `faturamento`, `pagantes`, `ativos_total`, `inadimplente`, `alunos_gympass`, `alunos_totalpass`, `faturamento_sem_agregador`, `ticket_medio_pagantes` |
| `unidades_ultra_catchment.parquet` | 54 × 9 | `unidade`, `uf`, `lat`, `lng`, `pop_captacao`, `renda_per_capita_captacao`, `n_setores_captacao` |
| `unidades_ultra_performance_hex.parquet` | 54 × 57 | `unidade`, `lat`, `lng`, `faturamento`, `ativos_pag`, `alunos_gympass`, `alunos_totalpass`, `metragem`, `score_priorizacao` |
| `concorrentes_mapeados.parquet` | — | `lat`, `lng`, `flag_coord_valida`, `flag_duplicado_rede_coord` |

### Campos reais disponíveis para o backtest

**Camada 1 (aderência):** `pop_captacao`, `renda_per_capita_captacao` (catchment 1.5 km) — alvo real `pagantes_steady_state`.

**Camada 3+4 (simulador DRE):**
- `pagantes_steady_state` = mediana de `pagantes` (growth_api) — BALCAO apenas (sem agregadores)
- `ticket_steady` = mediana de `ticket_medio_pagantes` — ticket do BALCAO
- `metragem` — m² da unidade
- `churn_steady` — em PERCENTUAL (2–6), precisa dividir por 100 para o simulador
- `faturamento` — mediana da receita bruta total (balcão + agr + personal)
- `faturamento_sem_agregador` — disponível na growth_api; permite decompor backteste

**O que NAO existe no parquet:**
- `aluguel_mes` — ausente em todos os parquets; o simulador precisa de valor default ou goal-seek
- alunos de agregadores em steady-state separados (não há campo direto; podem ser derivados do growth_api)

**Cobertura do growth_api:** apenas 19 das 54 maduras têm histórico na growth_api (match por nome normalizado). As outras 35 têm dados de steady-state já consolidados no `base_calibracao_maduras.parquet` (faturamento, pagantes, ticket como mediana snapshot).

---

## Interfaces reais mapeadas

### `aderencia.calibrar_aderencia(df, limiar_r2=0.05) -> AderenciaModel`
```python
# df obrigatorio: pagantes_steady_state, pop_captacao, renda_per_capita_captacao
# opcional: n_setores_captacao (0 ou NaN remove a linha)
# Retorna AderenciaModel com:
#   r2_loo_log, r2_loo_pagantes, rmse_loo_log, rmse_loo_pagantes
#   veredito ("GO"/"NO-GO"), nota_honesta
# NO-GO nao levanta excecao — e resultado valido
```

### `aderencia.prever_aderencia(pop_captacao, renda_per_capita, modelo) -> (pagantes, ic_lower, ic_upper)`
```python
# pop/renda -> pagantes previstos em alunos absolutos (exp do log-linear)
# IC = +/-1 RMSE_LOO_log back-transformado
# modelo.flag_extrapolacao(pop, renda) -> bool (fora do envelope min-max de treino)
# pop/renda <= 0 -> (1.0, 1.0, 1.0)
```

### `simulador.viabilidade(alunos_maturidade, m2, aluguel_mes, ticket_medio, **kwargs) -> ViabilidadeResult`
```python
# alunos_maturidade = alunos BALCAO pre-churn (NAO pagantes pos-churn)
# churn default = 0.06 (fracao, NAO percentual)
# inadimplencia default = 0.02
# alunos_agregadores default = 651
# ticket_agregador default = 82
# personal_mes default = 5000 (receita)
# pessoal_mes default = 50128 (custo de folha)
# outros_fixos_mes default = 38150
# aluguel afeta APENAS custos/ebitda/payback, NAO o faturamento bruto
# Retorna: faturamento_mensal_steady, ebitda_mensal, margem_ebitda_pct, payback_meses, flag_viavel
```

**ATENCAO — armadilha do churn:**
O campo `churn_steady` no parquet esta em **percentual** (ex.: 3.8 = 3,8%). O simulador espera **fracao** (0.038). Divisao por 100 obrigatoria.

**ATENCAO — alunos_maturidade vs pagantes_steady_state:**
O simulador calcula `pagantes_balcao = alunos_maturidade * (1 - churn)`. Logo, para usar pagantes reais:
`alunos_maturidade = pagantes_steady_state / (1 - churn_fracao)`.

### `features_exogenas.comparar_modelos_aderencia(df_features, ...) -> dict[str, ResultadoModeloFeatures]`
```python
# df_features precisa de: pagantes_steady_state, pop_captacao, renda_per_capita_captacao
# + opcionais: n_concorrentes_raio_1_5km, densidade_pop_catchment_hab_km2
# LOO-CV honesto por feature_set; mesma logica de aderencia.py
```

---

## Análise de escopo — o que é backtestavel agora

### Backtest A — Camada 1 (aderência) LOO honesto
**Disponivel:** 54 unidades, todas com `pagantes_steady_state`, `pop_captacao`, `renda_per_capita_captacao`.
- O `calibrar_aderencia` ja faz LOO internamente; o harness reusa as predicoes LOO
- Resultado confirmado do BLK-DIM-01R: **r2_loo_log = -0.0134 → NO-GO**
- O harness reporta o MAPE e R2 no espaco de ALUNOS (exp das predicoes LOO vs pagantes_reais)
- Flag de extrapolacao por ponto via `modelo.flag_extrapolacao(pop, renda)`

### Backtest B — Camada 3+4 (simulador DRE) dado alunos reais
**Disponivel:** `pagantes_steady_state`, `ticket_steady`, `metragem`, `churn_steady`, `faturamento`
**Lacuna principal:** `aluguel_mes` — usar default R$20.000 (valor do Excel) com flag de suposicao
- O DRE e deterministico (sem calibracao/LOO); erro medido nas 54 unidades diretamente
- Alvo mais honesto: `faturamento_mensal_steady` vs `faturamento` real
- Opcional: para 19 unidades com growth_api, decompor via `faturamento_sem_agregador`
- Estimativa exploratoria BO: MAPE ~35-44%, R2 ~0.13 (reflete variabilidade de agregadores nao modelados e aluguel fixo)

### Backtest C — End-to-end LOO (Camada 1 → Camada 3+4)
- LOO de 54 folds: cada fold treina aderencia em 53 → prevê alunos da unidade deixada de fora → passa para viabilidade → fatura previsto vs real
- Mede o erro TOTAL do pipeline quando a demanda nao e conhecida
- Com NO-GO da Camada 1, o MAPE end-to-end e esperado >>50% — isso e o objetivo: documentar o erro real antes de qualquer decisao

---

## Proposta de arquitetura do harness

### `src/motor_expansao/dimensionamento/backtest_dim.py`

```python
# Funcoes publicas:
#
# backtest_camada1_loo(df_maduras) -> BacktestCamada1
#   - Chama calibrar_aderencia (LOO interno) e reconstroe predicoes LOO
#   - Calcula MAPE/R2 no espaco de pagantes (exp das predicoes LOO)
#   - Flag de extrapolacao por ponto
#
# backtest_camada34_dado_alunos_reais(df_maduras, aluguel_default=20_000.0) -> BacktestCamada34
#   - Para cada unidade: converte churn_steady% para fracao, deriva alunos_maturidade
#   - Chama viabilidade(alunos_maturidade_real, m2, aluguel_default, ticket_steady, churn=real)
#   - Coleta faturamento_mensal_steady; compara vs faturamento_real
#   - Sem LOO (DRE deterministico)
#
# backtest_end_to_end_loo(df_maduras, aluguel_default=20_000.0) -> BacktestEndToEnd
#   - LOO: para cada fold i (1 teste, 53 treino):
#     - Treina calibrar_aderencia nos 53
#     - Prevê alunos_i = prever_aderencia(pop_i, renda_i, modelo)[0]
#     - Passa para viabilidade(alunos_i, m2_i, aluguel_default, ticket_i)
#     - Coleta faturamento previsto
#   - Compara vs faturamento real; MAPE/R2 end-to-end
#
# escrever_relatorio_backtest(resultados_dict, path) -> None
#   - Tabela por camada: MAPE / R2 / RMSE / N / % extrapolacao
#   - Secao de confounds (aluguel_default, N=54, NO-GO Camada 1)
#   - nota_honesta consolidada
#
# @dataclass BacktestResultado:
#   mape: float
#   r2: float
#   rmse: float
#   n: int
#   flag_extrapolacao_pct: float
#   nota: str
```

### `tests/unit/dimensionamento/test_backtest_dim.py`

Fixtures sinteticas (sem I/O de parquet, sem PII):
- `df_sintetico_5linhas`: 5 unidades com dados plausíveis
- Testa: `backtest_camada1_loo` retorna objeto com MAPE finito e n == 5
- Testa: `backtest_camada34_dado_alunos_reais` retorna resultado sem erro
- Testa: `backtest_end_to_end_loo` retorna resultado sem ValueError com N=5
- Testa: churn_steady em percentual e convertido corretamente (3.8 → 0.038)
- Testa: `alunos_maturidade` derivado como `pagantes / (1 - churn_fracao)`
- Testa: flag_extrapolacao presente nos resultados da Camada 1
- Testa: `escrever_relatorio_backtest` cria arquivo sem falha (tmp_path)

---

## Riscos e alertas

### Risco 1 — Erro alto e o objetivo, nao um defeito
O NO-GO da Camada 1 (r2_loo_log = -0.0134) **propaga** erro alto no backtest end-to-end. MAPE esperado >50%. O harness deve documentar isso claramente — nao tentar minimizar o erro relatado.

### Risco 2 — Aluguel ausente compromete backtest de ebitda/payback
`aluguel_mes` nao existe em nenhum parquet. O backtest da Camada 3+4 so pode medir `faturamento_mensal_steady` de forma honesta (aluguel nao afeta faturamento, so custos). Para `ebitda`, `margem` e `payback`, usar `aluguel_default=20_000` com flag explicita no relatorio.

### Risco 3 — Bug de unidade no churn (percentual vs fracao)
`churn_steady` esta em percentual (2.4, 3.9, 5.2...). Sem divisao por 100, `alunos_maturidade = pagantes / (1 - 3.9) < 0`. Validacao obrigatoria no harness.

### Risco 4 — Pagantes_steady_state e apenas BALCAO
Na growth_api, `pagantes` (balcao) e separado de `alunos_gympass` + `alunos_totalpass`. O harness deve usar `alunos_agregadores=0` como default conservador e documentar a suposicao, com nota que o faturamento real inclui agregadores.

### Risco 5 — Cobertura da growth_api (19 de 54 unidades)
Match por nome normalizado recupera apenas 19 de 54 maduras. Para as 35 sem historico, usar o `faturamento` da `base_calibracao_maduras` (snapshot real). Reportar a diferenca de fonte.

### Risco 6 — Sem R2 in-sample como metrica de desempenho
Por guardrail metodologico (spec §7): R2 in-sample existe apenas como auditoria. O backtest apresenta R2/MAPE LOO para Camada 1 e R2/MAPE sobre as 54 unidades (sem LOO) para o DRE deterministico.

### Risco 7 — Zero escrita em M1 (loop_guard)
O harness e READ-ONLY sobre M1. O loop_guard bloqueia automaticamente se qualquer diff tocar `config.py`, `pipelines/m1/`, artefatos oficiais, VPS ou CI.

---

## Resultado exploratório BO (sem PII)

Medicao preliminar Camada 3+4 com `alunos_maturidade = pagantes/1-churn`, `alunos_agr=0`, `aluguel_default=20k`:
- MAPE faturamento: ~35-44%
- R2 faturamento: ~0.13
- Implicacao: a variabilidade principal vem de agregadores nao modelados e aluguel fixo. O simulador e util para EBITDA goal-seek (dado alunos conhecidos), mas impreciso como preditor de faturamento bruto.

---

## Arquivos a criar (Builder)

```
src/motor_expansao/dimensionamento/backtest_dim.py   (CRIAR)
tests/unit/dimensionamento/test_backtest_dim.py      (CRIAR)
data/analysis/backtest_dim.md                        (gitignored; materializado pelo __main__)
tasks/current_task.md, tasks/completed.md, tasks/backlog.md
context/handoff.md + context/handoff/
```

**Arquivos a NAO tocar:** `aderencia.py`, `simulador.py`, `features_exogenas.py`, `catchment_batch.py`, qualquer arquivo de M1/score/artefatos oficiais.
