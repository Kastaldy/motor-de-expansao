# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-TP-05 — Re-teste honesto do elo demanda→captura (LOO vs baseline)**

Re-testa a regressão/Huff `alunos ~ membros + dist_concorrente_lc + n_concorrente_lc` agora com
**demanda observada** (camada BLK-TP-01, `data/staging/demanda_revelada_h3.parquet`), usando
LOO/k-fold repetido vs baseline da média. Emite veredito GO/NO-GO honesto.

## Objetivo
Determinar, com validação honesta (LOO-CV vs baseline, sem R² in-sample), se a demanda observada
por hex (`membros`) — que no protótipo deu Spearman +0,75 vs `alunos_parceiras` e OLS R²_in-sample
≈ 0,45 — sustenta sinal preditivo sobre alunos capturados quando avaliada fora da amostra.

## Variáveis principais do modelo

### Desfecho (alvo)
- **`alunos_parceiras`** (coluna de `data/staging/demanda_revelada_h3.parquet`):
  soma de alunos das academias parceiras no hex; único desfecho disponível com cobertura e resolução
  H3 res-7 adequada (n estimado ~27 mil na base, mas N efetivo após filtragem deve ser confirmado
  pelo Planner). Excluir hexes com `alunos_parceiras == 0` ou decidir tratamento explícito.
  - Alternativa/suplemento: `alunos_total`/`ativos_pag` de
    `data/staging/unidades_ultra_performance_hex.parquet` (n=54 unidades Ultra) — N muito pequeno
    para LOO estável; usar apenas como cross-check secundário.

### Features candidatas
- `membros` — demanda paga agregada ao hex (coluna BLK-TP-01, insumo OBSERVADO).
- `dist_concorrente_lc_min_m` — menor distância ao concorrente low-cost de referência no hex (m).
- `n_concorrente_lc` — número de unidades do concorrente LC no hex.
- `membros_gt5km_concorrente_lc` — subconjunto de membros a >5 km do concorrente LC.
- `n_acad_parceiras` (densidade de oferta do ecossistema parceiro — possível confound).

### Join principal
O join ocorre dentro do próprio `demanda_revelada_h3.parquet` (todas as colunas já estão no mesmo
artefato). Enriquecimento opcional por `hex_id` com `hexagonos_mercado_mapeado.parquet`
(ex.: `score_oportunidade_residual`, `renda_per_capita`) é permitido como feature adicional.

## Fontes de dados confirmadas no repositório

| Artefato | Caminho | Conteúdo relevante |
|---|---|---|
| Camada de demanda revelada | `data/staging/demanda_revelada_h3.parquet` | 9 colunas do contrato (membros, dist_concorrente_lc_min_m, n_concorrente_lc, alunos_parceiras…) |
| Contrato canônico | `src/motor_expansao/demanda_revelada/contrato.py` | CONTRATO_COLUNAS, COLUNAS_PII_PROIBIDAS, VERSAO_CONTRATO |
| Ingestão | `src/motor_expansao/demanda_revelada/ingestao.py` | ingerir_demanda_revelada(), FONTE_DEFAULT, DESTINO_DEFAULT |
| Pacote demanda_revelada | `src/motor_expansao/demanda_revelada/__init__.py` | ponto de importação |
| Performance Ultra (alvo secundário, n=54) | `data/staging/unidades_ultra_performance_hex.parquet` | alunos_total, ativos_pag, metragem, renda_per_capita_setor_2022_calibrada, n_concorrentes_mapeados_1km |
| Concorrentes mapeados | `data/staging/concorrentes_mapeados.parquet` | rede, lat, lng (n=3.296 un.; cross-check) |
| Scores M1 + mercado | `data/staging/hexagonos_mercado_mapeado.parquet` | score_oportunidade_residual, renda_per_capita (enriquecimento opcional) |
| Fixture sintética de teste | `tests/fixtures/demanda_revelada_fake.html` | HTML fake sem PII (NUNCA usar dado real nos testes) |
| Testes de ingestão BLK-TP-01 | `tests/unit/test_demanda_revelada_ingestao.py` | contrato de 9 colunas, anti-PII, res-7 |

## Infraestrutura de LOO/Ridge já no repositório (reuso prioritário)

O módulo `src/motor_expansao/dimensionamento/aderencia.py` já implementa:
- `_r2_loo_para_alpha()` — LOO-CV de Ridge(alpha) com varredura de ALPHA_GRID
- `AderenciaModel` dataclass — r2_loo_log, r2_loo_pagantes, rmse_loo_log, r2_insample_log
  (só auditoria), flag_extrapolacao, veredito GO/NO-GO, nota_honesta
- `LIMIAR_R2_GO = 0.05` (parâmetro de materialidade para GO/NO-GO)

O módulo `src/motor_expansao/dimensionamento/huff.py` já implementa LOO anti-circular para modelo
gravitacional (beta re-otimizado leave-one-unit-out). Se o Planner optar por variante Huff/gravitacional,
reutilizar a ideia de LOO anti-circular deste módulo.

O módulo `src/motor_expansao/dimensionamento/backtest_dim.py` implementa `_r2/_mape/_rmse` puros.

**O BLK-TP-05 NÃO deve duplicar esta infraestrutura — reutilizar (importar) sempre que possível.**

## Precedentes metodológicos da epic BLK-DIM (referência)

| Módulo | Caminho | Resultado |
|---|---|---|
| Aderência (BLK-DIM-01R) | `src/motor_expansao/dimensionamento/aderencia.py` | R²_LOO=-0,01 com pop+renda → NO-GO honesto |
| Huff (BLK-DIM-02R) | `src/motor_expansao/dimensionamento/huff.py` | LOO gravitacional anti-circular; AUC de ranking vs baseline |
| Backtest honesto (BLK-DIM-06) | `src/motor_expansao/dimensionamento/backtest_dim.py` | _mape/_rmse/_r2 puros; alvo real NUNCA saída do simulador |
| Discriminação residual (BLK-DIM-08) | `src/motor_expansao/dimensionamento/residual_discriminacao.py` | AUC 0,48 ≈ acaso; IC bootstrap; p-valor de permutação |
| Features exógenas (BLK-DIM-05) | `src/motor_expansao/dimensionamento/features_exogenas.py` | NO-GO confirmado com features exógenas |
| Backtest Smart Fit | `scripts/backtest_smartfit_scores.py` | n=871, M1 rho≈+0,12; padrão de join hex por coordenada |

Relatórios anteriores (`data/analysis/*.md`) são gitignored — o Builder gera novos relatórios
em `data/analysis/` (gitignored).

## Escopo permitido
- Criar módulo `src/motor_expansao/demanda_revelada/backtest_tp05.py` (ou nome equivalente no
  pacote `demanda_revelada/`) com a regressão/Huff LOO vs baseline.
- Consumir `data/staging/demanda_revelada_h3.parquet` (READ-ONLY) e opcionalmente
  `data/staging/hexagonos_mercado_mapeado.parquet` para enriquecimento de features.
- Reportar R²_LOO vs baseline da média com IC (bootstrap ≥ 500 reamostras ou ±RMSE_LOO analítico)
  e flag de extrapolação por ponto.
- Emitir veredito GO/NO-GO honesto com nota legível em PT, sem PII.
- Gravar relatório em `data/analysis/backtest_tp05.md` (gitignored).
- Criar testes unitários com fixtures sintéticas (NUNCA dado real) em `tests/unit/`.

## Fora de escopo
- Alterar `score_priorizacao`, `hex_score_estrutural`, pesos (renda=0.40/pop=0.60), carteira,
  plano curto prazo, plano de domínio ou qualquer artefato oficial do M1.
- Usar `membros` ou qualquer coluna da camada BLK-TP-01 como preditor geográfico de magnitude
  para ajustar o `score_priorizacao` (DEC-009 intacta).
- Persistir qualquer PII (DEC-012 anti-PII por construção).
- Importar de `pipelines/m1/`, `censo_*` ou `dashboard/` dentro do pacote `demanda_revelada/`.
- R² in-sample como métrica de desempenho (pode existir apenas como campo de auditoria rotulado
  explicitamente "apenas auditoria — NÃO usar como desempenho", DEC-008).
- Deploy ao VPS, alterações no Dockerfile ou CI.
- Ingestão ao vivo de dados externos durante testes (fixture sintética obrigatória).
- Expandir escopo para BLK-TP-03/04 ou qualquer outro bloco.
- Implementar a reabertura da Camada 2 (Huff) mesmo que o veredito seja GO — essa decisão é gate
  humano (Felipe) e está fora deste bloco.

## Arquivos que devem ser lidos (Planner e Builder)
- `CLAUDE.md` — completo (§1 low-cost, §2 regras operacionais, §4 camadas paralelas, §5 ciclos,
  DEC-001, DEC-008, DEC-009, DEC-012)
- `src/motor_expansao/demanda_revelada/contrato.py`
- `src/motor_expansao/demanda_revelada/ingestao.py`
- `src/motor_expansao/demanda_revelada/__init__.py`
- `src/motor_expansao/dimensionamento/aderencia.py` (infraestrutura LOO Ridge reutilizável)
- `src/motor_expansao/dimensionamento/huff.py` (infraestrutura Huff LOO reutilizável)
- `src/motor_expansao/dimensionamento/backtest_dim.py` (métricas puras _r2/_mape/_rmse)
- `src/motor_expansao/dimensionamento/residual_discriminacao.py` (padrão AUC/IC bootstrap)
- `src/motor_expansao/dimensionamento/config.py` (RAIO_CATCHMENT_KM, STAGING_DIR)
- `src/motor_expansao/dimensionamento/base_multirede.py` (CONCORRENTES_PATH, ULTRA_PERF_PATH)
- `scripts/backtest_smartfit_scores.py` (padrão de join hex por coordenada; NÃO alterar)
- `tests/unit/test_demanda_revelada_ingestao.py` (padrão de testes anti-PII)
- `tests/fixtures/demanda_revelada_fake.html` (fixture sintética — modelo para novos testes)
- `tasks/backlog.md` — linhas ~870–974 (epic BLK-TP e BLK-TP-05)
- `tasks/completed.md` — entradas BLK-DIM-01R/02R/05/06/08 (histórico metodológico)

## Arquivos que podem ser alterados/criados
- **CRIAR:** `src/motor_expansao/demanda_revelada/backtest_tp05.py`
- **CRIAR:** `tests/unit/test_backtest_tp05.py`
- **CRIAR:** `data/analysis/backtest_tp05.md` (gitignored)
- **ATUALIZAR (se necessário):** `src/motor_expansao/demanda_revelada/__init__.py`
- **ATUALIZAR:** `tasks/current_task.md` (ao avançar para Builder e QA)

NÃO ALTERAR (protegido): arquivos em `src/motor_expansao/pipelines/m1/`, `config.py` raiz do M1,
artefatos oficiais em `data/staging/brasil_*.parquet`, `hexagonos_brasil_*.parquet`,
`top_oportunidades_resumo.csv`, `resumo_por_uf.csv`, arquivos em `src/motor_expansao/censo_*`,
`src/motor_expansao/dashboard/`, e `scripts/backtest_smartfit_scores.py`.

## Critérios de aceite
1. R²_LOO vs baseline da média reportado em `data/analysis/backtest_tp05.md`, com IC (bootstrap
   ≥ 500 reamostras ou ±RMSE_LOO analítico).
2. Flag de extrapolação por ponto documentada (envelope min-max das features de treino).
3. Veredito GO/NO-GO emitido explicitamente com critério numérico claro (LIMIAR_R2_GO=0.05
   herdado de `aderencia.py`, ou limiar próprio justificado pelo Planner na aprovação humana).
4. R² in-sample, se reportado, marcado EXPLICITAMENTE como "apenas auditoria — NÃO usar como
   desempenho" (DEC-008).
5. Confounds documentados na nota_honesta: cobertura ~1% dos hexes nacionais, concentração SP,
   ruído de coords ~1 km, viés de seleção das academias parceiras.
6. ZERO colunas de `COLUNAS_PII_PROIBIDAS` em qualquer arquivo gerado (teste automatizado).
7. Testes unitários passando com fixture sintética (NUNCA dump real): LOO, baseline, IC,
   flag de extrapolação e zero-PII cobertos.
8. Suite completa (`pytest -q`) verde + ruff sem erros + mypy sem erros novos.
9. READ-ONLY sobre o M1 verificado: nenhum artefato oficial alterado.
10. Relatório inclui N de hexes usados, N descartados e range de alunos observados.

## Criticidade classificada
**Alta**

Justificativa: modelagem/análise READ-ONLY sobre o M1 — não altera `score_priorizacao`,
`hex_score_estrutural`, pesos, carteira, plano ou qualquer artefato oficial (§5 guardrail). A
interpretação operacional de 2026-05-30 registrada em CLAUDE.md §2 confirma: "LEITURA/ANÁLISE de
score sem escrita em artefato M1 → Alta". NÃO é Crítica.

## Esteira recomendada
Block Orchestrator (este handoff) → **Planner** → [aprovação humana — revisão de modelagem] →
Builder → QA

Tiering de modelo (registrado em `tasks/current_task.md`):
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Riscos identificados
1. **N pequeno após join:** cobertura ~1% dos hexes do Motor (~16.575 hexes; concentração SP).
   Após filtro de `alunos_parceiras > 0`, o N efetivo pode tornar LOO instável (< 30 observações
   → `flag_extrapolacao_padrao = True` na convenção do projeto). O Planner deve definir piso mínimo
   e estratégia alternativa (k-fold com k<N, reporte honesto de incerteza).

2. **Viés de seleção nas academias parceiras:** `alunos_parceiras` reflete academias que aderiram
   à plataforma — seleção não aleatória. Documentar como confound, não corrigir (sem dado adicional
   no escopo).

3. **Ruído de join por coords arredondadas:** `dist_concorrente_lc_min_m` e `n_concorrente_lc`
   derivam de coords agregadas (~1 km de resolução na fonte). Em hexes res-7 (~5,16 km²) é
   aceitável para ordem de grandeza; alertar na nota_honesta.

4. **Multicolinearidade entre features e alvo:** `membros`, `alunos_parceiras` e `n_acad_parceiras`
   vêm do mesmo dump. O Builder deve reportar correlações bivariadas antes do modelo e verificar
   que `alunos_parceiras` não tem relação trivialmente derivada de `membros`.

5. **GO espúrio por N pequeno:** com n < 10 hexes, LOO pode dar R² alto por artefato estatístico
   (análogo ao bug de fixture sintética do BLK-DIM-01). Flag de extrapolação global obrigatória
   quando n_treinamento < 30.

6. **Reabertura da Camada 2 (Huff) se GO:** gate HUMANO (Felipe), fora do escopo deste bloco.
   O Builder não implementa nada além do relatório mesmo que o veredito seja GO.

## Guardrails ativos
- **§5 guardrail permanente (READ-ONLY sobre o M1):** nenhuma análise, visualização ou interação
  pode recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto
  prazo, plano de domínio ou artefatos oficiais do M1 sem aprovação explícita.
- **DEC-008:** LOO/k-fold repetido SEMPRE vs baseline da média; BANIR R² in-sample como métrica
  de desempenho; começar simples (linear regularizado/GLM); toda saída com intervalo de predição
  + flag de extrapolação; NO-GO é resultado válido e esperado.
- **DEC-009:** a demanda entra como insumo OBSERVADO, NUNCA como preditor geográfico de magnitude
  para ajustar o score. Proibido usar `membros` ou qualquer coluna desta camada como input em
  regressão geográfica de demanda ou como ajuste do `score_priorizacao`.
- **DEC-012:** pacote `demanda_revelada/` é disjunto — NUNCA importa de `pipelines/m1/`, `censo_*`
  ou `dashboard/`; anti-PII por construção (zero PII em artefato/teste/log); fonte real
  (`NAO_ABRA/`) nunca versionada; testes sempre com fixture sintética.
- **DEC-001:** pesos `renda=0.40`/`pop=0.60` e fórmula de `score_priorizacao` INALTERADOS.
