# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-VIAB-04 — Backtest do motor de viabilidade contra as 54 unidades Ultra reais

## Veredito
**VIÁVEL** — dados suficientes para backtest honesto. Sem bloqueio de dados.

## Objetivo
Rodar `analisar_viabilidade_ponto` em modo LOO (Leave-One-Out) sobre as 54 unidades Ultra maduras, usando m² e alunos reais como entradas, e medir o erro da curva densidade (faixa_alunos_p50 predito vs alunos_total real) e do aluguel-teto calculado. Relatório `data/analysis/viabilidade_backtest_ultra.md` com MAE/viés e identificação dos casos de erro material.

## Dados disponíveis — auditoria de colunas

### `data/staging/unidades_ultra_performance_hex.parquet` (N=54, 57 colunas)

Colunas disponíveis para o backtest:

| Coluna | Tipo | Completude | Uso no backtest |
|--------|------|-----------|----------------|
| `unidade` | object | 54/54 | identificador |
| `metragem` | int64 | 54/54 | input do motor (`m2`) |
| `alunos_total` | int64 | 54/54 | alvo real (DEC-009) |
| `ticket_medio_aluno` | float64 | 54/54 | parâmetro `ticket_medio` |
| `ativos_pag` | int64 | 54/54 | referência secundária |
| `faturamento` | int64 | 54/54 | referência (faturamento real) |
| `alunos_por_m2` | float64 | 54/54 | densidade real observada |
| `lat` | float64 | 53/54 | não usado (modo coordless) |
| `lng` | float64 | 53/54 | não usado (modo coordless) |

**Coluna `aluguel` (aluguel real): AUSENTE.** Não há dado de aluguel real neste parquet.

### `data/staging/base_calibracao_maduras.parquet` (N=54, 22 colunas)

Colunas relevantes: `unidade`, `metragem`, `alunos_por_m2`, `ticket_medio_aluno`, `pagantes_steady_state`, `faturamento`, `flag_madura`. Esta é a base de calibração usada pelo motor para a curva de densidade.

## Métricas possíveis com os dados disponíveis

### Métricas PRIMÁRIAS (comparação predito vs realizado)

**Eixo 1 — Curva de densidade (LOO obrigatório):**
- Predito: `faixa_alunos_p10/p50/p90` via `faixa_alunos_por_densidade(m2_real, base_loo)`
- Real: `alunos_total` (DEC-009)
- Métricas: MAE, viés (bias), cobertura do intervalo (% de unidades onde real está em [p10, p90])
- LOO é OBRIGATÓRIO: para cada unidade i, base_calibracao = todas as 54 EXCETO a unidade i

**Eixo 2 — Aluguel-teto calculado (com demanda real como premissa):**
- Input: `m2=metragem_real`, `demanda_premissa=alunos_total_real`, `ticket_medio=ticket_medio_aluno_real`, `aluguel_pedido=SIM_ALUGUEL_MES` (default R$ 20.000)
- Predito: `aluguel_teto_calculado` (máximo de aluguel que mantém margem_alvo=10%)
- Referência: benchmarke vs SIM_ALUGUEL_MES e distribuição de aluguel_teto/m² em R$/m²
- Métricas: distribuição de aluguel_teto, mediana, IQR; % unidades onde aluguel_teto > SIM_ALUGUEL_MES

**Eixo 3 — Breakeven:**
- Predito: `alunos_breakeven` (alunos mínimos para viabilidade a SIM_ALUGUEL_MES)
- Real: `alunos_total`
- Métrica: margem_seguranca = (alunos_total - alunos_breakeven) / alunos_breakeven; % flag_viavel=True

### O que NÃO é possível medir (dado ausente):
- Comparação direta aluguel_teto_calculado vs aluguel_real (coluna ausente no parquet)
- Payback real vs predito (requer capex/aluguel reais)

## Decisão de design LOO (crítica para honestidade)

A curva de densidade `faixa_alunos_por_densidade` usa a base de calibração que INCLUI a própria unidade sendo avaliada. Para backtest honesto (DEC-008), o Builder DEVE implementar LOO:

```python
for i, row in df_ultra.iterrows():
    base_loo = df_calibracao.drop(index=i)  # exclui a própria unidade
    resultado = faixa_alunos_por_densidade(row['metragem'], base_loo)
```

Casos especiais de LOO confirmados:
- COTIA (750 m²): apenas 2 comparáveis no LOO com tolerância 20% — alarga para 50% (8 comparáveis)
- POA BARRA SUL (2800 m²): apenas 1 comparável no LOO com 20% — alarga para 50% (50 comparáveis)
Ambos são cobertos pelo fallback nativo de `faixa_alunos_por_densidade` (tolerancia_alargada=0.50).

## Modo de chamada do motor

```python
# COORDLESS — setores_df=None, lat/lng fictícios (0.0), aluguel padrão
resultado = analisar_viabilidade_ponto(
    lat=0.0,
    lng=0.0,
    m2=float(row['metragem']),
    aluguel_pedido=SIM_ALUGUEL_MES,               # R$ 20.000 default
    demanda_premissa=float(row['alunos_total']),   # alunos reais (DEC-009)
    ticket_medio=float(row['ticket_medio_aluno']),
    base_calibracao_df=base_loo,                  # LOO: exclui a própria unidade
    setores_df=None,                              # modo coordless
)
```

**`viabilidade_ponto.py` permanece INTOCADO.**

## Escopo permitido

- Criar `src/motor_expansao/dimensionamento/backtest_viabilidade.py` (novo módulo)
- Criar `tests/unit/dimensionamento/test_backtest_viabilidade.py` (mínimo 8 testes)
- Gerar `data/analysis/viabilidade_backtest_ultra.md` (gitignored, NÃO commitado)
- Ler `data/staging/unidades_ultra_performance_hex.parquet` e `data/staging/base_calibracao_maduras.parquet`

## Fora de escopo

- NÃO modificar `viabilidade_ponto.py` (INTOCADO)
- NÃO modificar `simulador.py` (INTOCADO)
- NÃO modificar `config.py` de nenhuma camada
- NÃO tocar artefatos oficiais do M1 (score_priorizacao, hex_score_estrutural, carteira, plano)
- NÃO ajustar parâmetros do motor com base nos erros encontrados (só medir — DEC-008)
- NÃO usar lat/lng das unidades reais (modo coordless: setores_df=None)
- NÃO persistir PII (exceto `unidade` como label de negócio)
- NÃO usar `alunos_gympass`/`alunos_totalpass`/`agregadores` como alvo — usar só `alunos_total` (DEC-009)

## Arquivos que devem ser lidos

- `/repo/src/motor_expansao/dimensionamento/viabilidade_ponto.py` (assinatura de `analisar_viabilidade_ponto` e `faixa_alunos_por_densidade`)
- `/repo/src/motor_expansao/dimensionamento/simulador.py` (constante SIM_ALUGUEL_MES)
- `/repo/src/motor_expansao/dimensionamento/backtest_dim.py` (referência estrutural: helpers `_mape`, `_rmse`, `_r2`)
- `/repo/src/motor_expansao/dimensionamento/batch_viabilidade.py` (referência de limpeza de base e rodar_candidato)
- `/repo/data/staging/unidades_ultra_performance_hex.parquet` (dados reais, 54 unidades)
- `/repo/data/staging/base_calibracao_maduras.parquet` (base de calibração da curva de densidade)
- `/repo/CLAUDE.md` §2/§5/§6.1

## Arquivos que podem ser alterados

- `src/motor_expansao/dimensionamento/backtest_viabilidade.py` — **CRIAR NOVO**
- `tests/unit/dimensionamento/test_backtest_viabilidade.py` — **CRIAR NOVO**
- `data/analysis/viabilidade_backtest_ultra.md` — **GERAR** (gitignored, NÃO commitado)
- `tasks/completed.md` — atualizar ao fechar
- `tasks/backlog.md` — marcar BLK-VIAB-04 como concluído
- `context/handoff.md` — atualizar ao passar para próxima Skill

## Estrutura do módulo novo

### Funções públicas de `backtest_viabilidade.py`

```python
VERSAO_CONTRATO = "backtest_viabilidade_v1"
COLS_OBRIGATORIAS = ("unidade", "metragem", "alunos_total", "ticket_medio_aluno")

def carregar_ultra_performance(path: Path) -> pd.DataFrame:
    """Carrega e valida unidades_ultra_performance_hex.parquet."""

def rodar_backtest_loo(
    df_ultra: pd.DataFrame,
    base_calibracao_df: pd.DataFrame,
    *,
    aluguel_ref: float = SIM_ALUGUEL_MES,
    margem_alvo: float = 0.10,
) -> pd.DataFrame:
    """LOO: para cada unidade, remove-a da base e roda o motor. Retorna DataFrame de resultados."""

def calcular_metricas_agregadas(df_resultados: pd.DataFrame) -> dict:
    """Calcula MAE, RMSE, vies, cobertura de intervalo e % flag_viavel."""

def gerar_relatorio(df_resultados: pd.DataFrame, metricas: dict, path_out: Path) -> None:
    """Escreve data/analysis/viabilidade_backtest_ultra.md."""

def run(
    path_ultra: Path | None = None,
    path_calibracao: Path | None = None,
    path_relatorio: Path | None = None,
) -> pd.DataFrame:
    """Entry point: carrega, roda LOO, calcula métricas, gera relatório."""
```

### Colunas de saída do `rodar_backtest_loo`

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `unidade` | str | nome da unidade |
| `metragem` | int | m² real |
| `alunos_total_real` | int | alvo real (DEC-009) |
| `ticket_real` | float | ticket médio real |
| `faixa_alunos_p10` | float | predicao p10 da curva LOO |
| `faixa_alunos_p50` | float | predicao p50 da curva LOO |
| `faixa_alunos_p90` | float | predicao p90 da curva LOO |
| `n_comparaveis` | int | comparáveis usados no LOO |
| `alunos_breakeven` | float | mínimo de alunos para viabilidade |
| `aluguel_teto_calculado` | float | aluguel-teto com demanda real |
| `flag_viavel` | bool | viabilidade a SIM_ALUGUEL_MES |
| `erro_abs_p50` | float | faixa_alunos_p50 - alunos_total_real |
| `erro_rel_p50` | float | erro_abs_p50 / alunos_total_real |
| `alunos_por_m2_real` | float | densidade real observada |
| `alunos_por_m2_predito_p50` | float | faixa_alunos_p50 / metragem |
| `flag_extrapolacao` | bool | True se tolerância alargada foi usada |
| `versao_contrato` | str | "backtest_viabilidade_v1" |

## Critérios de aceite

1. `git diff src/motor_expansao/dimensionamento/viabilidade_ponto.py` vazio (motor INTOCADO)
2. `git diff src/motor_expansao/dimensionamento/simulador.py` vazio
3. `git diff src/motor_expansao/dimensionamento/config.py` vazio
4. `data/analysis/viabilidade_backtest_ultra.md` gerado com N=54 unidades processadas, MAE e vies numéricos explícitos
5. Se motor errar de forma material e sistematica (MAE > 40% no p50): registrado como necessidade de recalibração no relatório, NÃO silenciado
6. Suite de testes: mínimo 8 testes verdes (além das 5 falhas pré-existentes por deps opcionais)
7. `ruff check` e `mypy` limpos nos novos arquivos
8. `loop_guard.py` limpo (nenhum arquivo protegido modificado)
9. Relatório NÃO commitado no git (gitignored)

## Testes mínimos obrigatórios (8)

1. `test_carregar_ultra_performance_retorna_df` — carrega com fixture sintética, valida N e colunas
2. `test_carregar_ultra_performance_falha_col_ausente` — levanta ValueError se coluna obrigatória faltar
3. `test_rodar_backtest_loo_n_correto` — roda LOO com fixture de 5+ unidades, valida N de linhas e colunas de saída
4. `test_rodar_backtest_loo_exclui_propria_unidade` — verifica que a unidade avaliada nao está na base LOO (mock de `faixa_alunos_por_densidade`)
5. `test_calcular_metricas_mae_zero` — com predito == real, MAE=0 e vies=0
6. `test_calcular_metricas_coverage` — intervalo [p10, p90] sempre cobre o real quando p10=0 e p90=alunos_real+1
7. `test_gerar_relatorio_cria_arquivo` — chama `gerar_relatorio` com fixture sintética, verifica que arquivo existe e contém "MAE"
8. `test_sem_pii_nas_colunas` — df de saída nao contém colunas de PII_COLUNAS_PROIBIDAS (de config.py)

## Criticidade classificada
**Alta** — valida o motor antes de confiar nele; READ-ONLY sobre o M1.

## Esteira recomendada
Block Orchestrator (concluído) → **Planner** → Builder → QA

## Tiering de modelo
- Block Orchestrator: sonnet (concluído)
- Planner: opus
- Builder: opus
- QA: opus (sempre)

## Riscos identificados

1. **LOO com N pequeno nos extremos de metragem**: COTIA (750 m²) e POA BARRA SUL (2800 m²) têm poucos comparáveis no LOO com tolerância 20% — cobertos pelo fallback nativo de tolerância 50%, mas o Builder deve verificar que `flag_extrapolacao=True` é atribuído nesses casos.

2. **Ausência de aluguel real**: o motor calcula `aluguel_teto_calculado` mas nao há aluguel real para comparar. O relatório deve deixar explícito que o eixo de aluguel é análise interna de capacidade, NÃO validação vs valor de mercado.

3. **Contaminação da curva por outliers**: PRAIA GRANDE (2500 m², 6251 alunos) e BOTAFOGO (1230 m², 3984 alunos de balcão — ticket 154) sao outliers. O LOO os trata corretamente (cada um só perturba a sua janela de m²).

4. **Unit CAMPO LIMPO sem lat/lng**: 1 unidade sem coordenadas — sem impacto no modo coordless.

## Guardrails ativos

- §5 READ-ONLY M1: zero escrita em `config.py`/`pipelines/m1`/artefatos oficiais.
- §6.1 loop-safe: sem rede, sem VPS, sem PII persistido, consome só `data/staging`.
- DEC-008: out-of-fold vs baseline; nao ajustar o motor neste bloco (só medir).
- DEC-009: demanda SÓ como premissa explícita (`alunos_total_real`), nunca prevista pela geo.
- `viabilidade_ponto.py` INTOCADO em todo o bloco.
- Fixtures sintéticas nos testes; fonte real nunca versionada.
