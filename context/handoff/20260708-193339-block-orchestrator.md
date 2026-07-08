# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco
BLK-VIAB-07

## Criticidade confirmada
Alta

## Escopo confirmado (READ-ONLY M1)
Nada do seguinte será tocado:
- `config.py` e qualquer parâmetro canônico do §3
- `src/motor_expansao/pipelines/m1/` (nenhum arquivo)
- `score_priorizacao`, `hex_score_estrutural`, pesos `renda=0.40`/`pop=0.60`
- Artefatos oficiais: `brasil_estrutural.parquet`, `brasil_priorizados.parquet`, `hexagonos_brasil_oportunidades.parquet`, `hexagonos_brasil_dashboard.parquet` e derivados
- `Dockerfile.*`, `docker-compose*`, Caddyfile, `authelia/`, `secrets/`, `.env`
- Nenhuma escrita em VPS, nenhuma chamada de rede, nenhum PII persistido

## Arquivos-alvo
- **Produção (modificar):** `src/motor_expansao/dimensionamento/viabilidade_ponto.py`
- **Testes (adicionar casos):** `tests/unit/dimensionamento/test_viabilidade_ponto.py`
- **Relatório de validação (criar, gitignored):** `data/analysis/viabilidade_formato_oof.md`
- **Parquet de suporte lido (read-only):** `data/staging/unidades_ultra_performance_hex.parquet`
- **Parquet de suporte lido (read-only):** `data/staging/base_calibracao_multirede.parquet`

## Colunas disponíveis no parquet

### `unidades_ultra_performance_hex.parquet` — N=54 linhas, 57 colunas

Colunas relevantes para o bloco:
- `unidade` — nome da unidade (string)
- `uf` — estado (SP, DF, GO, ES, PR, RJ, MT, RS, SC, MG)
- `cidade` — cidade da unidade
- `metragem` — área em m² (float; min=750, max=2800, mediana=1500, sem nulos)
- `alunos_total` — alunos totais reais (int; target da validação; min=1206, max=6251)
- `alunos_por_m2` — densidade real (float; min=0.71, max=3.24, mediana=1.57)
- `ativos_pag`, `agregadores` — breakdown de alunos
- `faturamento`, `ticket_medio_aluno` — dados financeiros

**CRÍTICO:** Não existe coluna `rede`, `formato` ou `tipo` neste parquet. Todas as 54 unidades são Ultra (low-cost/massa). A base é homogênea em formato — não há boutique nem outra rede.

### `base_calibracao_multirede.parquet` — N=426 linhas, 9 colunas

Colunas: `unidade`, `marca`, `uf`, `cidade`, `lat`, `lng`, `alunos_reais`, `metragem`, `flag_qualidade_match`

Distribuição por `marca`:
- `ultra`: 54 linhas, metragem 100% preenchida
- `engenharia_do_corpo`: 61 linhas, metragem 60/61 preenchida (1 nulo)
- `skyfit`: 311 linhas, metragem 100% NULA (inutilizável para curva de densidade)

**Consequência direta:** SkyFit não pode entrar na curva de densidade (metragem=NaN em 311/311). A base útil para validação out-of-fold é Ultra (54) + Engenharia do Corpo (60 com metragem válida) = até 114 unidades.

## Mapeamento rede → formato proposto

| `marca` (parquet) | `formato` proposto | Justificativa | N com metragem |
|---|---|---|---|
| `ultra` | `"low_cost_massa"` | Posicionamento explícito §1 CLAUDE.md; ticket ~R$87; 750–2800 m² | 54 |
| `engenharia_do_corpo` | `"boutique_premium"` | Academia premium/personal; ticket mais alto; porte diferente | 60 |
| `skyfit` | `"low_cost_massa"` | Concorrente low-cost direto comparável (§1); metragem 100% nula → EXCLUIR da curva | 0 úteis |

**Importante:** O mapeamento `rede → formato` deve ser definido como dicionário local em `viabilidade_ponto.py` ou módulo auxiliar em `src/motor_expansao/dimensionamento/`. Não deve ir para `config.py` (fonte canônica do M1, intocável).

**Implicação da base real:** Como `unidades_ultra_performance_hex.parquet` tem apenas Ultra (low_cost_massa) e nenhuma coluna `formato`, o parâmetro `formato=None` filtrará da `base_calibracao_df` injetada pelo chamador. O chamador precisa adicionar a coluna `formato` antes de passar o DataFrame — ou a função recebe `formato` como string e faz o filtro internamente sobre a coluna `marca`/`formato` se existir.

## Análise da função `faixa_alunos_por_densidade`

### Assinatura atual (linha 113–183 de `viabilidade_ponto.py`)

```python
def faixa_alunos_por_densidade(
    m2: float,
    base_calibracao_df: pd.DataFrame,
    *,
    tolerancia: float = FAIXA_M2_TOLERANCIA,           # 0.20
    tolerancia_alargada: float = FAIXA_M2_TOLERANCIA_ALARGADA,  # 0.50
    n_min: int = N_MIN_COMPARAVEIS,                     # 3
) -> dict:
```

A função:
1. Filtra `base_calibracao_df` por `alunos_por_m2 > 0` e finito
2. Aplica janela `+/-tolerancia` em `metragem` → se N < `n_min`, alarga para `+/-tolerancia_alargada` → se ainda N < `n_min`, usa toda a base
3. Retorna percentis p10/p50/p90 de `alunos_por_m2 * m2`

### O que muda para aceitar `formato=None`

Adicionar parâmetro `formato: str | None = None` como keyword-only. Comportamento:
- `formato=None` → **byte-idêntico ao atual** (sem filtro de formato, usa toda a base)
- `formato="low_cost_massa"` → filtra `df` mantendo só linhas onde `df["formato"] == formato` (ou coluna equivalente como `marca`)

**Guardrail de robustez:** se `formato` não for None mas a coluna `formato`/`marca` não existir na base, ou se após o filtro N < `n_min` total (não só na janela de metragem), degradar graciosamente para usar a base completa sem filtro (com `n_comparaveis` refletindo o fallback).

**Ponto de chamada em `analisar_viabilidade_ponto`** (linha 339):
```python
faixa = faixa_alunos_por_densidade(m2, base_calibracao_df)
# passa a ser:
faixa = faixa_alunos_por_densidade(m2, base_calibracao_df, formato=formato)
```
E `analisar_viabilidade_ponto` ganha `formato: str | None = None` nos parâmetros.

**`ViabilidadePontoResult`** não precisa de campo novo (o parâmetro é de filtro, não de output) — mas adicionar `formato_calibracao: str | None = None` para rastreabilidade/auditoria é opcional e aceitável.

## Plano de validação out-of-fold (DEC-008)

### Configuração
- **Método:** k-fold 5 repetições × 5 folds = 25 combinações, seed=42 (mesmo harness DEC-008/BLK-LTV-04)
- **Alvo:** `alunos_total` real por unidade (`unidades_ultra_performance_hex.parquet`); **NUNCA `membros`/agregador externo**
- **Base:** Ultra (54 unidades, todas com metragem) — a única com metragem 100% preenchida e formato homogêneo
- **Comparação primária:** `formato=None` (baseline atual, toda a base) vs `formato="low_cost_massa"` (filtrado)

### Protocolo

Para cada fold de validação:
1. Separar N_test unidades no fold de teste
2. `base_train` = unidades restantes (N-N_test)
3. Para cada unidade de teste:
   - Chamar `faixa_alunos_por_densidade(m2_real, base_train, formato=None)` → p50_sem_formato
   - Chamar `faixa_alunos_por_densidade(m2_real, base_train, formato="low_cost_massa")` → p50_com_formato
4. Calcular `erro_abs = |p50 - alunos_total_real|` e `erro_rel = erro_abs / alunos_total_real`

### Métricas a reportar
- **MAPE_oof_sem_formato** e **MAPE_oof_com_formato** (métrica primária de veredito)
- **MAE_oof**, **Viés** (mean(pred-real)) em ambos os cenários
- **Cobertura [p10,p90]** em ambos os cenários
- **Baseline da média:** predizer sempre `mean(alunos_total_train)` — se o modelo não bate este baseline, é NO-GO

### Critério de GO/NO-GO
- **GO:** `MAPE_oof_com_formato < MAPE_oof_sem_formato` E `MAPE_oof_com_formato < MAPE_baseline_média` E ganho >= 1 p.p. de MAPE
- **NO-GO:** qualquer um dos critérios falha → encerrar sem expor o parâmetro `formato` no código de produção (reverter a adição ou manter com `raise NotImplementedError`)
- R² in-sample é **BANIDO** do veredito (DEC-008)
- O NO-GO é resultado válido e honesto — não silenciar

### Nota sobre N
Com N=54 Ultra e k-fold 5×5, cada fold tem ~10-11 unidades de teste e ~43-44 de treino. A janela de metragem ±20% sobre base de 43 unidades deve cobrir ≥3 comparáveis para a maioria dos pontos. Se `formato="low_cost_massa"` em treino reduz a base a 43 (todos Ultra anyway, já que a base de validação é Ultra-only), o filtro de formato não tem efeito com a base atual — isso é um achado importante a reportar.

**Implicação crítica:** Se toda a `unidades_ultra_performance_hex.parquet` for `formato="low_cost_massa"`, o filtro só faz diferença quando a `base_calibracao_df` injetada mistura formatos (ex.: Ultra + Engenharia do Corpo). O teste real do ganho deve usar `base_calibracao_multirede.parquet` (Ultra 54 + EngCorpo 60 com metragem) como base de comparáveis e validar LOO com `formato="low_cost_massa"` vs sem filtro. Isso é o que o BLK-VIAB-04-FU mediu: MAPE Ultra 26.8% (base só Ultra) vs 35.3% (base mista Ultra+EngCorpo), confirmando que misturar formatos piora.

## Riscos / alertas

1. **Base de validação homogênea:** `unidades_ultra_performance_hex.parquet` não tem coluna `formato` nem `rede` — é 100% Ultra. O parâmetro `formato` só faz diferença quando a `base_calibracao_df` injetada é mista (ex.: `base_calibracao_multirede.parquet`). O Builder deve testar com base mista para demonstrar o ganho.

2. **SkyFit inutilizável:** 311/311 linhas de SkyFit em `base_calibracao_multirede.parquet` têm `metragem=NaN`. Não entram na curva de densidade; não precisam de `formato` para serem excluídas (já são descartadas pelo filtro `alunos_por_m2 > 0` + `metragem.notna()`).

3. **Ganho esperado pequeno (~1,7 p.p. MAPE):** O BLK-VIAB-04-FU mostrou que Ultra-only (MAPE 26.8%) vs mista (MAPE Ultra 35.3%) — o ganho de filtrar por formato é real mas modesto. Com N=54 o IC bootstrap pode cruzar zero (resultado honesto = NO-GO).

4. **Parâmetro `formato` no `analisar_viabilidade_ponto`:** O chamador atual (dashboard, UI) passa `base_calibracao_df=df_ultra` (só Ultra). Se `formato=None` é o default, o dashboard fica byte-idêntico. Risco de regressão zero se o default for respeitado.

5. **N_MIN_COMPARAVEIS=3 com filtro de formato:** Se a base injetada tem poucos exemplos do formato pedido na janela de metragem, a função vai alargar a janela ou usar toda a base filtrada — comportamento correto, mas deve ser testado explicitamente.

6. **Guardrail DEC-009 ativo:** O alvo é `alunos_total` reais (nunca `membros` do insumo externo BLK-TP-01). O relatório deve explicitar que `demanda_premissa` é entrada do operador e que a curva de densidade produz faixa de referência, não predição geográfica.

7. **loop_guard:** O Builder deve verificar que `loop_guard.py` não bloqueia o diff (a mudança é restrita a `dimensionamento/viabilidade_ponto.py` e `tests/unit/dimensionamento/` — nenhum arquivo sensível).
