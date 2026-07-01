# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-LTV-03 — Análise de correlação território × retenção/LTV `[GATE DE DECISÃO]`**

Análise de correlação READ-ONLY entre features territoriais do hexágono e métricas de
retenção/LTV por unidade. Entrega rho + IC bootstrap por par de variáveis, confounds declarados
e veredito GO/NO-GO honesto. Gate de decisão do epic BLK-LTV: GO habilita BLK-LTV-04 (score M2,
com DEC + gate humano próprios); NO-GO encerra o epic em consolidação de dados (LTV-01/02 como
ativo, sem score).

## Objetivo
Correlacionar as features territoriais do dataset `unidade_territorio_retencao.parquet` (N=56 com
hex_id) com `PROB_CANCEL_90D_MEDIA` / `LTV_PROSPECTIVO_12M_MEDIANO` via Spearman + bootstrap/IC,
declarando confounds obrigatórios, e emitir veredito GO/NO-GO honesto para decidir se o eixo
retenção territorial segue para score (BLK-LTV-04) ou se o epic encerra em consolidação.

## Escopo permitido

### Dataset de entrada (confirmado por inspeção)
- `data/staging/unidade_territorio_retencao.parquet` — 88 linhas × 36 colunas
- Subsets efetivos para correlação territorial:
  - **N=56** unidades com `hex_id` não-nulo (universo principal)
  - **N=44** dessas com `prob_cancel_90d_media_absoluta` não-nula (eixo absoluto; USAR_PROB_ABSOLUTA="Sim" AND hex_id notna)
  - **N=52** com `USAR_RANKING="Sim"` AND hex_id notna (eixo ranking)

### Features territoriais disponíveis (cobertura entre os 56 com hex)
- `renda_per_capita`: 56/56 não-nulo
- `score_priorizacao`: 56/56 não-nulo (READ; não alterado)
- `n_concorrentes_mapeados_1km`: 56/56 não-nulo
- `score_expansao_hibrido`: 56/56 não-nulo
- `score_oportunidade_residual`: 56/56 não-nulo
- `densidade_pop_setor_hab_km2`: 49/56 não-nulo (7 NaN sem censo setorial)
- `score_setor_2022_calibrado`: 49/56 não-nulo (mesmo 7 NaN)

### Variáveis-alvo (retenção/LTV)
- `PROB_CANCEL_90D_MEDIA` — probabilidade média de cancelamento em 90d (presente em todos os 56)
- `LTV_PROSPECTIVO_12M_MEDIANO` — LTV prospectivo mediano por unidade (presente em todos os 56)
- `prob_cancel_90d_media_absoluta` — variante somente para unidades com prob. absoluta confiável
  (N=44 com hex); coluna derivada do BLK-LTV-02, já presente no parquet

### Metodologia obrigatória (DEC-008)
- Spearman rho + bootstrap IC95 (>=500 reamostras, seed fixo) por par (feature × target)
- Sem R² in-sample; proibido `fit(X,y)→predict(X)` como métrica de desempenho
- Scatter plots por par (opcional, mas recomendado para o relatório de decisão)
- Declarar N utilizado por par (pode variar por NaN de `densidade_pop_setor_hab_km2`)
- Critério de GO: rho materialmente diferente de zero com IC95 sem cruzar zero

### Respeito ao USAR_PROB_ABSOLUTA
- Para análise de churn absoluto: usar `prob_cancel_90d_media_absoluta` restrito ao subset N=44
  (hex_id notna AND USAR_PROB_ABSOLUTA="Sim")
- Para análise de ranking/ordenação: usar `PROB_CANCEL_90D_MEDIA` no subset N=56 com nota de
  que 12 unidades são "Apenas Ranking" (não calibradas em probabilidade absoluta)

### Onde o código deve viver
- `src/motor_expansao/lifetime/correlacao_territorio_retencao.py` (novo módulo, dentro do pacote
  `lifetime/` já estabelecido pelo BLK-LTV-01/02; mantém consistência arquitetural)
- Convencão dos blocos anteriores: módulo em `src/motor_expansao/lifetime/` + teste unitário em
  `tests/unit/test_correlacao_territorio_retencao.py`

### Relatório de saída
- `data/analysis/relatorio_correlacao_ltv.md` — gitignored (padrão `data/analysis/**` confirmado
  no .gitignore); arquivo texto com rho + IC por par, confounds declarados, veredito GO/NO-GO
- Convencão confirmada: `backtest_tp05.py` escreve em `data/analysis/backtest_tp05.md`;
  `scripts/backtest_smartfit_scores.py` usa `OUT = ROOT / "data/analysis"`

## Fora de escopo

- Criar qualquer score, campo novo em parquets existentes ou artefato de staging além do relatório
- Avançar para BLK-LTV-04 (bloqueado; depende do GO e de DEC + gate humano próprios)
- Alterar qualquer artefato do M1 (`brasil_estrutural.parquet`, `brasil_priorizados.parquet`,
  `hexagonos_brasil_oportunidades.parquet`, `hexagonos_brasil_dashboard.parquet`,
  `hexagonos_mapa_sample.parquet`, `top_oportunidades_resumo.csv`, `resumo_por_uf.csv`)
- Alterar `score_priorizacao`, `hex_score_estrutural`, pesos `renda=0.40`/`pop=0.60` ou qualquer
  parâmetro canônico do §3 do CLAUDE.md
- Controlar por maturidade da unidade (ver confound abaixo — impossível; não silenciar)
- Modelagem preditiva (regressão geográfica de demanda, Huff, previsão de magnitude)
- Alterar `data/ultra/unidade_para_motor.parquet` ou qualquer fonte de entrada
- Tocar VPS, secrets, deploy, CI fora do PR do ciclo
- Criar dependência nova em `pyproject.toml` além de scipy (se já não presente)

## Confound obrigatório a declarar no relatório

**Maturidade da unidade — confound estrutural, não contornável neste bloco:**
- `unidade_para_motor.parquet` NÃO tem data de abertura nem idade da unidade (confirmado por
  inspeção: nenhuma coluna com "data", "abertura", "open", "matur", "age", "idade", "inicio"
  entre as 50 colunas). `maturacao_status` está 100% `maturacao_indisponivel` (DEC-001/DEC-008
  gate G1).
- A correlação território × retenção mistura localização com tempo de operação da unidade. Uma
  unidade nova pode ter churn alto por razões de rampa, não por território ruim.
- Declarar como confound no relatório; NÃO descartar o resultado — um sinal forte mesmo sem
  controle de maturidade é informativo; um sinal fraco é igualmente honesto.

**Outros confounds obrigatórios:**
- N pequeno (N=56, N=44 no eixo absoluto): IC bootstrap obrigatório; significância estatística
  pode não ser atingível mesmo com sinal real
- Seleção de sobreviventes: as 88 unidades são unidades OPERANDO; unidades fechadas (churn total)
  não entram — pode subestimar o efeito real do território
- 32 unidades sem hex_id (36% da base Lifetime): pode haver viés geográfico sistemático
  (unidades não geocodificadas são a amostra com pior match de nome)

## Arquivos que devem ser lidos

### Contexto do projeto
- `CLAUDE.md` — completo (§1 posicionamento Ultra low-cost; §3 parâmetros canônicos M1; §5 guardrail READ-ONLY M1; DEC-001, DEC-008, DEC-009)
- `data/ultra/unidade_para_motor_DICIONARIO.md` — semântica das colunas de retenção/LTV e regra USAR_PROB_ABSOLUTA

### Dataset de entrada (produção)
- `data/staging/unidade_territorio_retencao.parquet` — 88×36; grão: unidade; join territorial já feito

### Código de referência para convenções
- `src/motor_expansao/lifetime/join_territorio_retencao.py` — módulo irmão (padrão de guardrails, logging, docstring)
- `src/motor_expansao/demanda_revelada/backtest_tp05.py` — padrão de análise: Spearman, bootstrap IC95, veredito GO/NO-GO, escrita em `data/analysis/`
- `src/motor_expansao/dimensionamento/aderencia.py` — padrão de validação cruzada (útil se o Builder quiser reaproveitar infraestrutura de bootstrap)

### Testes de referência
- `tests/unit/test_join_territorio_retencao.py` — padrão de testes do pacote `lifetime/`

## Arquivos que podem ser alterados

### Novos (este bloco)
- `src/motor_expansao/lifetime/correlacao_territorio_retencao.py` — módulo de análise (READ-ONLY; sem escrita em artefatos M1)
- `tests/unit/test_correlacao_territorio_retencao.py` — testes unitários do módulo
- `data/analysis/relatorio_correlacao_ltv.md` — relatório gitignored (veredito GO/NO-GO + rho + IC)
- `context/handoff.md` — sobrescrito por cada skill na sequência
- `context/handoff/<stamp>-*.md` — snapshots append-only

### Arquivos de orquestração (não-código)
- `tasks/current_task.md` — atualizado ao longo da esteira
- `tasks/backlog.md` — BLK-LTV-03 marcado como concluído no fechamento (via housekeeping)
- `tasks/completed.md` — entrada adicionada no fechamento

### NUNCA alterar
- Qualquer arquivo em `src/motor_expansao/pipelines/m1/`
- `config.py`
- `data/staging/brasil_*.parquet`, `data/staging/hexagonos_*.parquet`
- `data/staging/unidade_territorio_retencao.parquet` (somente leitura neste bloco)
- `data/ultra/unidade_para_motor.parquet`
- `pyproject.toml` (salvo adição de scipy em `[dev]` se ausente — verificar antes)

## Critérios de aceite verificáveis

1. **rho + IC bootstrap por par**: relatório `data/analysis/relatorio_correlacao_ltv.md` contém,
   para cada par `(feature_territorial × target)`, rho Spearman, IC95 por bootstrap (>=500
   reamostras), p-value e N efetivo utilizado. Pares mínimos obrigatórios:
   - `renda_per_capita` × `PROB_CANCEL_90D_MEDIA` (N=56)
   - `renda_per_capita` × `LTV_PROSPECTIVO_12M_MEDIANO` (N=56)
   - `score_priorizacao` × `PROB_CANCEL_90D_MEDIA` (N=56)
   - `score_priorizacao` × `LTV_PROSPECTIVO_12M_MEDIANO` (N=56)
   - `n_concorrentes_mapeados_1km` × `PROB_CANCEL_90D_MEDIA` (N=56)
   - `densidade_pop_setor_hab_km2` × `PROB_CANCEL_90D_MEDIA` (N=49, declara 7 NaN)
   - `prob_cancel_90d_media_absoluta` × `renda_per_capita` (N=44, eixo absoluto)

2. **Confounds declarados**: relatório contém seção explícita de confounds com pelo menos:
   - maturidade (sem data de abertura — impossível controlar; gap G1 da DEC-001)
   - N pequeno e IC bootstrap
   - seleção de sobreviventes (32 unidades sem hex_id)

3. **Veredito GO/NO-GO honesto**: relatório termina com veredito claro ("GO" ou "NO-GO") com
   justificativa baseada nos rhos/ICs; NO-GO é resultado legítimo e não deve ser evitado

4. **R² in-sample banido**: nenhuma métrica in-sample reportada como desempenho preditivo;
   qualquer R² deve ser rotulado explicitamente como "apenas auditoria" (padrão do backtest_tp05)

5. **READ-ONLY M1**: `git diff` após execução não toca nenhum artefato M1; mtime dos 4 artefatos
   oficiais inalterado (`brasil_priorizados.parquet`, `hexagonos_brasil_oportunidades.parquet`,
   `brasil_estrutural.parquet`, `hexagonos_mercado_mapeado.parquet`)

6. **Sem imports proibidos**: `correlacao_territorio_retencao.py` não importa de
   `pipelines.m1`, `dashboard`, `censo_*`, `api` (grep verificável)

7. **Suíte full verde**: `pytest -n auto -q` — zero falhas, zero collection errors

8. **ruff + mypy limpos**: `ruff check src/motor_expansao/lifetime/` e `mypy src/` sem erros novos

9. **Testes unitários do módulo**: `tests/unit/test_correlacao_territorio_retencao.py` cobre ao
   mínimo: (a) função principal retorna resultado com rho/IC por par, (b) N declarado por par bate
   com os não-nulos reais do subset, (c) sem escrita em artefatos M1

## Criticidade classificada
**Alta** — gate de decisão do epic BLK-LTV; READ-ONLY sobre o M1; exige revisão humana após o
Planner para decidir se o veredito GO/NO-GO é aceito e se o epic avança para BLK-LTV-04.

## Esteira recomendada

```
Block Orchestrator (este handoff)
    → Planner (opus)              [elabora plano técnico detalhado]
    → [REVISÃO HUMANA]            ← PARAR AQUI; apresentar plano ao Felipe antes do Builder
    → Builder (opus)              [implementa módulo + testes; produz relatório]
    → QA (opus 4.8)               [suite full; lê relatório; verifica critérios de aceite]
    → Fechamento (orquestrador)   [housekeeping; move BLK-LTV-03 backlog→completed]
```

**GATE HUMANO OBRIGATÓRIO**: após o Planner, PARAR e apresentar o plano ao usuário (Felipe)
para aprovação explícita antes de lançar o Builder. Criticidade Alta + gate de decisão do eixo.
NÃO é loop-safe.

## Riscos identificados

1. **N pequeno (N=44–56)**: IC bootstrap pode ser largo demais para distinguir rho real de ruído.
   O resultado honesto pode ser "inconclusivo" (ICs cruzando zero com rho não-nulo). Declarar
   explicitamente no relatório; não forçar GO.

2. **Maturidade como confound não-controlável**: sem data de abertura, não é possível distinguir
   "território ruim" de "unidade nova". O sinal pode ser subestimado (unidades novas em bons
   territórios com alto churn transitório) ou superestimado (unidades maduras em territórios
   ruins já selecionadas por sobrevivência).

3. **Colinearidade entre features territoriais**: `renda_per_capita`, `score_priorizacao` e
   `score_expansao_hibrido` são correlacionados entre si. Reportar correlações bivariadas sem
   tentar separar efeito parcial (sem regressão múltipla como métrica de desempenho).

4. **32 unidades sem hex_id (36%)**: o subset de análise (N=56) pode não ser representativo da
   rede toda. Se as unidades sem geocodificação se concentrarem em determinados perfis territoriais,
   o sinal pode estar enviesado.

5. **scipy como dependência nova**: verificar se `scipy` já está em `pyproject.toml` antes de
   adicionar (os módulos `aderencia.py` e `backtest_tp05.py` já usam `scipy.stats.spearmanr` —
   provável que já esteja presente).

## Guardrails ativos

- **§5 CLAUDE.md (guardrail permanente)**: análise de correlação READ-ONLY; NÃO recalcula
  `score_priorizacao`, `hex_score_estrutural`, carteira, plano, artefatos oficiais do M1.
- **DEC-001 intacta**: pesos `renda=0.40`/`pop=0.60` e fórmula do `score_priorizacao` inalterados.
  `score_priorizacao` é apenas uma das features territoriais LIDAS nesta análise.
- **DEC-008 (metodologia)**: Spearman + bootstrap/IC; BANIR R² in-sample como desempenho;
  N pequeno exige IC; NO-GO é resultado válido e honesto.
- **DEC-009 (escopo)**: esta análise correlaciona RETENÇÃO com território — diferente da previsão
  de DEMANDA que a DEC-009 encerrou. O escopo está correto; mas proibido usar qualquer output
  desta análise como preditor geográfico de magnitude de demanda ou ajuste do `score_priorizacao`.
- **Bloco NÃO cria score**: BLK-LTV-04 é bloco separado, condicional ao GO, com DEC própria e
  gate humano adicional (Crítica/Estratégica). Este bloco termina no relatório + veredito.
- **Pacote disjunto**: `src/motor_expansao/lifetime/` — não importa de `pipelines/m1/`, `dashboard/`,
  `censo_*`, `.api`.
