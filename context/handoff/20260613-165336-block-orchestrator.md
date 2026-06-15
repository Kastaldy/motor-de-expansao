# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Sumário do bloco
BLK-DIM-01R faz a calibração REAL da Camada 1 (aderência/penetração) do Motor de
Dimensionamento, corrigindo os dois vícios do spike BLK-DIM-01: (a) fixture sintética
circular onde o teste gerava dados da própria equação do modelo (R²=0.897 garantido por
construção), e (b) endogeneidade mecânica onde o alvo `penetração = pagantes/pop` tem
`log(pop)` no denominador, criando anti-correlação artefatual de −0.91 com a feature
`log(pop)`. O bloco deve modelar `log(pagantes_steady_state)` diretamente (sem a razão),
calcular R²_LOO honesto, e reportar veredito GO/NO-GO com base nos dados reais.

## Estado dos dados (base_calibracao_maduras.parquet)

- Path: `data/staging/base_calibracao_maduras.parquet`
- Shape: 54 linhas × 22 colunas
- `flag_madura`: 100% True (todas as 54 unidades são maduras — limiar = 8 meses; range
  de `meses_desde_inauguracao`: 15–65 meses, mediana 26,5)
- NaNs em `pop_captacao` e `renda_per_capita_captacao`: 1 linha cada (mesma unidade,
  provavelmente sem cobertura censitária no catchment)
- N efetivo após remover NaN + outlier de penetração > 1: **52 linhas**
  - 1 unidade sem pop/renda (NaN de catchment)
  - 1 unidade com penetração = 1.10 (pagantes > pop_captacao do catchment — outlier)
  - n_setores_captacao == 0: nenhum (todos têm setores)

Faixas das variáveis chave (N=53 com pop/renda):
- `pagantes_steady_state`: min=418, q25=1012, mediana=1193, q75=1801, max=4057
- `pop_captacao`: min=1.403, q25=29.550, mediana=35.517, q75=71.918, max=128.326
- `renda_per_capita_captacao`: min=599, q25=1.256, mediana=1.760, q75=2.763, max=16.875
- `penetracao = pagantes/pop`: min=0.004, mediana=0.033, max=1.10 (1 outlier)

## Features disponíveis para modelagem

### Exógenas ao alvo (não derivam de pagantes nem de penetração):
- `pop_captacao` — tamanho do catchment 1.5 km; ATENÇÃO: ao modelar log(pagantes) diretamente,
  log(pop) é feature legítima (o denominador do alvo antigo sumiu); correlação moderada com
  pagantes: corr(log_pop, log_pagantes) = **-0.30** (negativa — unidades em catchments maiores
  tendem a ter MENOS pagantes, sinal do confound de seleção urbana)
- `renda_per_capita_captacao` — renda média do catchment; corr(log_renda, log_pagantes) = **+0.17**
  (fraca positiva, plausível)
- `n_setores_captacao` — proxy de granularidade/qualidade do catchment (não usar como predictor
  direto de demanda, mas útil como flag de outlier)
- `meses_desde_inauguracao` — maturação real (15–65 meses); pode ser controlado mas com cautela
  (unidades maduras variam no nível de maturação — usar como covariável de controle apenas)
- `metragem` — m² da unidade; ENDÓGENA ao negócio (não é feature de mercado), não usar

### Endógenas / contaminadas (NÃO usar como features):
- `penetracao = pagantes / pop_captacao` — NÃO usar como alvo (é o vício central que este bloco corrige)
- `alunos_por_m2`, `ticket_medio_aluno`, `faturamento` — outcomes de operação, não preditores de mercado
- `churn_steady`, `ticket_steady`, `cancelados_steady`, `ativos_total_steady`,
  `inadimplente_steady` — séries operacionais da unidade, não features de mercado externo

### Ausentes (não existem na base):
- Perfil etário 18-45 por catchment — NÃO disponível neste parquet
- Densidade urbana por catchment — NÃO disponível neste parquet
- Vínculo formal/renda do trabalho por catchment — NÃO disponível neste parquet
- Concorrentes no catchment da unidade — NÃO disponível neste parquet
(Essas features serão o escopo do BLK-DIM-05 — dependente do BLK-DIM-01R)

## Resultado da análise de endogeneidade (dados reais, executado pelo BO)

### Endogeneidade confirmada numericamente:
- `corr(log_pop, log_penet) = -0.9075` — quase perfeitamente mecânica
  (log penet = log pagantes − log pop → log(pop) aparece com sinal −1 por definição)
- O spike modelava log(penet) com log(pop) como feature → o modelo "aprendia"
  fundamentalmente a identidade algébrica, não relação econômica real

### R²_LOO honesto com alvo corrigido (log(pagantes) diretamente, alpha=1.0):
- **R²_LOO no espaço log = -0.028** (negativo — pior que baseline da média)
- **R²_LOO no espaço de pagantes = -0.069** (também negativo)
- Modelo log(pagantes) ~ log(renda) apenas: R²_LOO = -0.081

**Veredito preliminar: NO-GO.** Com as features disponíveis (pop_captacao + renda_per_capita),
modelar pagantes honestamente dá R²_LOO negativo, indicando que a média é uma previsão melhor
que o modelo. Isso é CONSISTENTE com a DEC-001 (o próprio M1 teve Spearman ≈ 0 no backtest),
e é um resultado VÁLIDO e ESPERADO — não é falha do bloco.

## Arquivos-alvo

Criar (não existe no main, existe como referência no spike branch ciclo/BLK-DIM-01):
- `src/motor_expansao/dimensionamento/aderencia.py` — módulo de calibração; REUTILIZAR o
  esqueleto do spike (LOO-CV, Ridge, AderenciaModel dataclass, anti-PII, IC, flag_extrapolacao)
  com as seguintes mudanças obrigatórias:
  (a) alvo = `log(pagantes_steady_state)` em vez de `log(penetracao)` — corrige endogeneidade
  (b) `prever_aderencia` retorna `(pagantes_previstos, ic_lower, ic_upper)` em alunos (não fração)
  (c) `AderenciaModel` documenta o confound sem endogeneidade (corr_pop_pagantes=-0.30)
  (d) R²_LOO calculado no espaço de pagantes (linearizado) OU no espaço log — ambos reportados
  (e) `relatorio_honesto` deve declarar o veredito GO/NO-GO esperado (provavelmente NO-GO)

- `tests/unit/dimensionamento/test_aderencia.py` — testes; REUTILIZAR estrutura do spike com:
  (a) REMOVER: `test_calibrar_aderencia_go` com R²>0.5 sobre dados circulares (df_log_sinal
      gerado via y = a*pop + b*renda + ruído → circular porque o modelo aprendia a equação)
  (b) SUBSTITUIR `df_log_sinal` por fixture onde pagantes ~ pop^0.8 + ruído REAL (relação
      não-trivial mas não circular: log(pagantes) = b0 + b1*log(pop) + eps, sem razão/denominador)
  (c) ADICIONAR controle negativo OBRIGATÓRIO: fixture onde `pagantes_steady_state` é constante
      (sem dependência de pop/renda) → R²_LOO deve ser ≤ 0 (sem GO espúrio)
  (d) MANTER: testes de outlier, clamp, flag_extrapolacao, determinismo, colunas ausentes

- `data/analysis/aderencia_real.md` — relatório gitignored com:
  N=52, faixa de pagantes/pop observada, R²_LOO real, coeficientes Ridge, veredito GO/NO-GO,
  confounds documentados (seleção + dilution de catchment)

Modificar:
- `tasks/current_task.md` — atualizar status
- `tasks/completed.md` — stub de fechamento
- `tasks/backlog.md` — stub BLK-DIM-01R
- `context/handoff.md` + `context/handoff/AAAAMMDD-HHMMSS-*.md` — cada skill

NÃO tocar:
- Qualquer artefato M1 (`config.py` raiz, `pipelines/m1/`, `brasil_*.parquet`, etc.)
- `data/staging/base_calibracao_maduras.parquet` (READ-ONLY)
- `src/motor_expansao/dimensionamento/calibracao_maduras.py` (sem alterações)
- `src/motor_expansao/dimensionamento/catchment_batch.py` (sem alterações)
- `src/motor_expansao/dimensionamento/config.py` — apenas leitura (sem novos parâmetros neste bloco)

## Análise de risco

**R1 (provável): NO-GO é o resultado honesto.** Com N=52 e apenas pop+renda como features,
R²_LOO = -0.028 (pior que baseline). Risco: o Builder pode tentar "forçar" GO através de
seleção de features, alpha tuning ou mudança de escala. Mitigação: o Planner deve deixar
EXPLÍCITO que NO-GO é resultado válido e que o critério de aceite é honestidade, não GO.

**R2 (técnico): redefinição do que `prever_aderencia` retorna.** O spike retornava
(penetração, ic_lower, ic_upper) como fração [0.001, 1.0]. O novo modelo retorna pagantes
em alunos. A interface muda — o Planner precisa definir a nova assinatura clara para não
quebrar downstream (BLK-DIM-02 / BLK-DIM-04 esperam a saída desta função). Mitigação:
manter o nome `prever_aderencia` mas com docstring que documenta a mudança de unidade.

**R3 (endogeneidade residual): `meses_desde_inauguracao` como feature.** Unidades com mais
meses tendem a ter mais pagantes (maturação). Mas pode criar viés preditivo (ao prever um
hex novo, não sabemos quantos meses de vida ele terá). O Planner deve decidir se inclui
como feature de controle apenas (para estimar steady-state de uma unidade madura arbitrária)
ou exclui. Recomendação do BO: incluir como covariável de controle mas NÃO como predictor
de novos hexes — reportar o coeficiente como informativo, não causal.

**R4 (N pequeno): LOO com N=52 tem alta variância.** R²_LOO pode variar bastante entre
alphas. O Planner deve instruir o Builder a varrer o ALPHA_GRID completo
(0.01, 0.1, 1.0, 10.0, 100.0) e reportar o melhor, com RMSE_LOO.

**R5 (teste circular remanescente): `df_log_sinal` gera dados via log(penet) = b0+b1*log(pop)+eps
e `pagantes = penet*pop`.** Se o Builder simplesmente trocar o alvo para log(pagantes) mas
mantiver a fixture assim gerada, cria nova circularidade: log(pagantes) = log(penet) + log(pop)
= b0 + b1*log(pop) + b2*log(renda) + pop → ainda correlacionado com pop! A fixture nova deve
gerar log(pagantes) = b0 + b1*log(pop) + b2*log(renda) + ruído DIRETAMENTE sem passar por
penetração. Mitigação: o Planner deve especificar a fixture nova explicitamente.

## Contexto para o Planner

### O que é reutilizável do spike (ciclo/BLK-DIM-01:src/motor_expansao/dimensionamento/aderencia.py):
- Estrutura `AderenciaModel` (dataclass com todos os campos) — manter quase intacta, apenas
  renomear `coef_log_pop`/`coef_log_renda` para clareza, e mudar a documentação de "penetração"
  para "pagantes"
- `_r2_loo_para_alpha` — função de LOO-CV: REUTILIZAR sem alteração
- `calibrar_aderencia` — estrutura geral (remoção de outliers, seleção de alpha, LOO, modelo final):
  REUTILIZAR, mudando apenas o alvo (y = log(pagantes) em vez de log(penet))
- `prever_aderencia` / `aderencia_calibrada` — função de predição com IC: REUTILIZAR mas retornar
  pagantes em alunos (não fração de penetração) e ajustar clamp (min=1 aluno, max sem limite fixo)
- `flag_extrapolacao` — REUTILIZAR sem alteração
- `relatorio_aderencia` — REUTILIZAR com linguagem atualizada

### O que deve ser DESCARTADO / SUBSTITUÍDO:
- Fixture `df_log_sinal`: gerava dados via `log(penet) = b0 + b1*log(pop) + eps` depois calculava
  `pagantes = penet * pop` — circular. Substituir por fixture que gera log(pagantes) diretamente.
- Fixture `df_sem_sinal`: OK para o controle negativo MAS precisa de novo controle negativo mais
  forte: `pagantes_steady_state` constante ou ruído independente de pop (não apenas permutado).
- Testes `test_calibrar_aderencia_go` / `test_r2_loocv_positivo_com_sinal_forte` / `test_coef_log_pop_negativo`:
  todos verificam que o modelo aprende de dados circulares — REMOVER.
- Constante `PENETRACAO_MIN/MAX` — renomear ou remover (não há mais clamp de fração 0-1;
  o output agora é em alunos).

### Abordagem sugerida para o Planner:
1. Definir alvo = `log(pagantes_steady_state)` (sem razão); documentar a correção da endogeneidade
2. Features = `[log(pop_captacao), log(renda_per_capita_captacao)]` — AMBAS são válidas agora
   (pop não aparece mais no denominador do alvo)
3. Outlier: manter remoção de `n_setores_captacao == 0` e `pagantes <= 0` / `pop <= 0`; remover
   `penetracao > 1.0` pois penetração não é mais o alvo
4. LOO-CV com ALPHA_GRID completo; R²_LOO no espaço log E no espaço de pagantes
5. Gate GO = R²_LOO_log > LIMIAR_R2_GO (manter 0.05); com dados reais esperamos NO-GO
6. Fixture nova (anti-circular): `log_pagantes = -1.0 + 0.8*log_pop + 0.1*log_renda + ruído(sigma=0.3)`
   sem intermediar por penetração
7. Controle negativo: `pagantes = constante (ou ruído puro) independente de pop/renda` → R²_LOO ≤ 0
8. `relatorio_honesto` deve incluir: N, R²_LOO (log e linear), RMSE_LOO, veredito, confounds
   (corr_pop_pagantes=-0.30: unidades em catchments grandes têm menos pagantes; viés de seleção Ultra)

### Notas adicionais:
- A suíte completa atual tem 833 passed, 4 skipped (baseline do BLK-DIM-03R, QA 2026-06-13)
- Nenhum teste de aderência existe em `tests/unit/dimensionamento/` no main (o arquivo foi
  criado apenas no branch ciclo/BLK-DIM-01, não mergeado)
- O `data/analysis/aderencia_real.md` é gitignored — confirmar que está em `.gitignore` antes
  de criar (ou usar `data/analysis/` que já é coberto pelo gitignore existente)
- READ-ONLY M1: o módulo `dimensionamento/` é completamente paralelo; nenhum arquivo de M1
  precisa ser tocado
