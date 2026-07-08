# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-VIAB-03 — Batch de viabilidade sobre candidatos limpos (coordless) + ranking por margem de segurança**

Novo módulo `batch_viabilidade.py` que itera sobre os 23 candidatos do parquet limpo (VIAB-01),
seleciona a faixa de demanda p10/p50/p90 pelo tier de metragem (VIAB-02), chama
`analisar_viabilidade_ponto` em modo COORDLESS (`setores_df=None`) para cada candidato e
materializa ranking por margem de segurança (`aluguel_teto(p50) − aluguel_pedido`).

## Objetivo
Rodar o motor de viabilidade (`analisar_viabilidade_ponto`) sobre os 23 candidatos limpos com a
faixa de demanda-premissa por tier, em modo coordless, e produzir
`data/staging/viabilidade_candidatos.parquet` + relatório ranqueado
`data/analysis/viabilidade_candidatos.md`.

## Contexto técnico (lido dos fontes reais)

### Assinatura de `analisar_viabilidade_ponto` (viabilidade_ponto.py L275-291)
```python
def analisar_viabilidade_ponto(
    lat: float,
    lng: float,
    m2: float,
    aluguel_pedido: float,
    demanda_premissa: float,   # ← p10, p50 ou p90 do tier
    *,
    ticket_medio: float = SIM_MENSALIDADE_BALCAO,   # 137 (default — usar)
    margem_alvo: float = 0.10,                       # 10% (default — usar)
    share_balcao: float = SHARE_BALCAO_DEFAULT,      # 0.69 (default — usar)
    raio_km: float = RAIO_CATCHMENT_KM,
    base_calibracao_df: pd.DataFrame | None = None,  # ← injetar base de comparáveis
    setores_df: pd.DataFrame | None = None,          # ← SEMPRE None no batch (coordless)
    alunos_range: tuple[float, ...] = ALUNOS_RANGE_DEFAULT,
    aluguel_range_fator: tuple[float, ...] = ALUGUEL_RANGE_FATOR,
    **kwargs,
) -> ViabilidadePontoResult
```

**Modo coordless:** `setores_df=None` → catchment não roda; `flag_zona_morta=None`,
`pop_captacao=None`, `renda_per_capita_captacao=None`. Todos os candidatos atuais têm
`flag_sem_coord=True` (23/23), logo mesmo se tivéssemos setores_df, as coords são NaN.

**`base_calibracao_df`:** DataFrame com coluna `alunos_por_m2` (e opcionalmente `metragem`).
O batch deve derivar esse DataFrame a partir do parquet de comparáveis existente
(`data/staging/unidades_ultra_performance_hex.parquet`) com as colunas `metragem` e
`alunos_total`, calculando `alunos_por_m2 = alunos_total / metragem`. A `faixa_alunos_por_densidade`
interna usa a janela ±20% de metragem (±50% se N<3).

**`demanda_premissa`:** para o batch, chamar o motor 3 vezes por candidato — com p10, p50 e p90
do tier correspondente — ou usar p50 como cenário principal e p10/p90 como banda. Decisão
pré-fixada no backlog: usar p50 como cenário do ranking; reportar a banda p10..p90.

### Dados dos candidatos (confirmados)
- `imoveis_candidatos_limpos.parquet`: 23 linhas, colunas relevantes:
  `ID`, `NOME`, `ÁREA` (m²), `ALUGUEL`, `STATUS`, `flag_sem_coord` (todos True).
- Colunas coord: `LATITUDE`, `LONGITUDE` (todas NaN — coordless puro).

### Faixa de demanda-premissa por tier (confirmada)
| Tier (m²)  | N  | p10   | p50   | p90   | flag_extrap |
|---|---|---|---|---|---|
| <1000      | 17 | 1.467 | 2.063 | 3.589 | False |
| 1000-1499  | 46 | 1.559 | 2.532 | 3.889 | False |
| 1500-1999  | 36 | 1.763 | 2.748 | 4.578 | False |
| 2000-2999  | 11 | 2.870 | 3.888 | 4.752 | False |
| >=3000     |  2 | 2.578 | 5.706 | 8.833 | True  |

Dos 23 candidatos: 1 acima de 3.000 m² (FORTALEZA_JARDIM_DAS_OLIVEIRAS, 4.000 m²) cai no tier
`>=3000` com `flag_extrapolacao=True` — aviso obrigatório no relatório.

### Estrutura do `ViabilidadePontoResult` retornado (dataclass)
Campos relevantes para o batch:
- `aluguel_teto_calculado` — aluguel-teto com demanda=p50 (usado no ranking)
- `alunos_breakeven` — break-even real (margem 0%)
- `alunos_para_margem_alvo` — alunos para 10% de margem
- `viabilidade` — `ViabilidadeResult` (flag_viavel, margem_ebitda_pct, payback_meses)
- `faixa_alunos_p10/p50/p90` — derivados da curva metragem→densidade (base_calibracao_df)
- `grade_sensibilidade` — DataFrame alunos×aluguel (30 pares = 6×5)
- `demanda_fonte` = "premissa_explicita" (guardrail DEC-009)

### Lógica do ranking (decisões pré-fixadas no backlog)
```
margem_seguranca = aluguel_teto_calculado(demanda=p50) − aluguel_pedido
flag_robusto     = (aluguel_pedido < aluguel_teto(p10))           # passa até no pior cenário
flag_no_go       = (aluguel_pedido > aluguel_teto(p50))           # não viável no cenário central
```
Ordem do ranking: `margem_seguranca` DESC (maiores primeiro).

### Defaults do motor a usar (sem inventar)
- `ticket_medio`: `SIM_MENSALIDADE_BALCAO = 137` (config.py L96)
- `margem_alvo`: `0.10`
- `share_balcao`: `SHARE_BALCAO_DEFAULT = 0.69` (viabilidade_ponto.py L55)

## Escopo permitido
- Criar `src/motor_expansao/dimensionamento/batch_viabilidade.py` (módulo novo).
- Criar `tests/unit/dimensionamento/test_batch_viabilidade.py`.
- Materializar `data/staging/viabilidade_candidatos.parquet` (gitignored — NÃO commitado).
- Materializar `data/analysis/viabilidade_candidatos.md` (gitignored — NÃO commitado).
- Atualizar `tasks/current_task.md`, `tasks/completed.md`, `tasks/backlog.md` (fechamento).
- Atualizar `context/handoff.md` e `context/handoff/` (snapshots).

## Fora de escopo
- **NUNCA modificar** `viabilidade_ponto.py` (git diff deve ser VAZIO — guardrail explícito).
- Não tocar `config.py` do dimensionamento (`src/motor_expansao/dimensionamento/config.py`).
- Não tocar `config.py` raiz do M1 (`src/motor_expansao/config.py`).
- Não recalcular `score_priorizacao`, `hex_score_estrutural`, pesos, carteira, plano ou artefatos M1.
- Não fazer fetch HTTP, não chamar APIs ao vivo, não usar lat/lng como preditor de demanda.
- Não criar UI (dashboard) neste bloco.
- Não geocodificar os endereços (lat/lng são NaN e assim permanecem — coordless).
- Não tocar `data/staging/brasil_*.parquet` ou qualquer artefato oficial do M1.

## Arquivos que devem ser lidos (pelo Planner/Builder)
- `/repo/src/motor_expansao/dimensionamento/viabilidade_ponto.py` — assinatura completa e ViabilidadePontoResult
- `/repo/src/motor_expansao/dimensionamento/simulador.py` — ViabilidadeResult, aluguel_teto, alunos_minimos_viaveis
- `/repo/src/motor_expansao/dimensionamento/config.py` — SIM_MENSALIDADE_BALCAO e demais defaults
- `/repo/src/motor_expansao/dimensionamento/demanda_premissa.py` — TIERS e _assign_tier (para mapear m² → tier)
- `/repo/src/motor_expansao/dimensionamento/imoveis_candidatos.py` — colunas do parquet de candidatos
- `/repo/data/staging/imoveis_candidatos_limpos.parquet` — inspecionar colunas reais
- `/repo/data/staging/demanda_premissa_por_tier.parquet` — p10/p50/p90 por tier
- `/repo/data/staging/unidades_ultra_performance_hex.parquet` — para derivar base_calibracao_df
- `/repo/tasks/backlog.md` (BLK-VIAB-03, linhas 902–931) — decisões pré-fixadas
- `/repo/tasks/current_task.md` — guardrails e paths do ciclo

## Arquivos que podem ser alterados
- `src/motor_expansao/dimensionamento/batch_viabilidade.py` (NOVO — criar)
- `tests/unit/dimensionamento/test_batch_viabilidade.py` (NOVO — criar)
- `tasks/current_task.md` (atualizar skill)
- `tasks/completed.md` (fechamento pós-QA)
- `tasks/backlog.md` (mover stub BLK-VIAB-03)
- `context/handoff.md` (atualizar por cada Skill)
- `context/handoff/` (snapshots append-only)

## Critérios de aceite
1. `data/staging/viabilidade_candidatos.parquet` materializado com 23 linhas (uma por candidato) e colunas mínimas: `ID`, `NOME`, `ÁREA`, `ALUGUEL`, `tier_label`, `flag_extrapolacao`, `aluguel_teto_p50`, `margem_seguranca`, `flag_robusto`, `flag_no_go`, `alunos_breakeven`, `demanda_p10`, `demanda_p50`, `demanda_p90`, `demanda_fonte`.
2. `data/analysis/viabilidade_candidatos.md` com tabela ranqueada por `margem_seguranca` DESC, sinalizando NO-GO (vermelho/texto), ROBUSTO e flag_extrapolacao.
3. Grade de sensibilidade por candidato disponível (pode ser salva num parquet separado ou incorporada via JSON/serialização).
4. `git diff src/motor_expansao/dimensionamento/viabilidade_ponto.py` = VAZIO (intocado).
5. `demanda_fonte = "premissa_explicita"` em todas as linhas (DEC-009).
6. Testes unitários cobrem: mapeamento tier correto, chamada coordless (setores_df=None), cálculo de margem_seguranca e flags, flag_extrapolacao propagada do tier, determinismo (mesma entrada → mesma saída), ausência de PII/geo no artefato.
7. `ruff check` e `mypy` sem erros nos arquivos novos.
8. `pytest tests/unit/dimensionamento/test_batch_viabilidade.py` 100% verde.
9. `pytest -n auto` (full) sem regressões novas além das 4 falhas + 1 erro de ambiente pré-existentes (Plus Code/openlocationcode, matplotlib).
10. `loop_guard.py` limpo (zero toque em config.py/pipelines/m1/artefatos M1).
11. Artefatos M1 com mtime inalterado (verificar `brasil_estrutural.parquet`, `brasil_priorizados.parquet`).

## Criticidade classificada
**Alta** — READ-ONLY sobre o M1; camada paralela de viabilidade; `viabilidade_ponto.py` intocado.

## Esteira recomendada
Block Orchestrator → **Planner** → Builder → QA

## Riscos identificados
1. **`base_calibracao_df`**: o módulo `viabilidade_ponto.py` espera um DataFrame com coluna `alunos_por_m2`. O batch deve derivá-la de `unidades_ultra_performance_hex.parquet` (`alunos_por_m2 = alunos_total / metragem`), verificando que a coluna existe e que os valores são finitos e positivos antes de injetar.
2. **Tier `>=3000` com N=2**: candidato FORTALEZA_JARDIM_DAS_OLIVEIRAS (4.000 m²) cai neste tier instável. O relatório deve exibir aviso explícito. O `flag_extrapolacao` do tier já está disponível no parquet de tiers.
3. **Todos os candidatos com `flag_sem_coord=True`**: o batch usa modo puro coordless (lat=0.0/lng=0.0 ou qualquer placeholder), sem catchment. O Planner deve definir qual placeholder de lat/lng usar quando a coord é NaN (ex: 0.0, NaN, ou omitir o catchment explicitamente passando setores_df=None).
4. **Grade de sensibilidade por candidato**: `grade_sensibilidade` é um DataFrame de 30 linhas por candidato. O Planner deve decidir como materializar isso (parquet separado com coluna `ID` para join, JSON embedded no parquet principal via `.to_json()`, ou só no relatório Markdown).
5. **Chamada 3× por candidato** (p10, p50, p90): o motor é puro/determinístico, então é barato; mas o Planner deve documentar que `aluguel_teto_calculado` será calculado com cada um dos três valores de demanda para produzir `aluguel_teto_p10`, `aluguel_teto_p50`, `aluguel_teto_p90`.

## Guardrails ativos
- **§5 READ-ONLY M1:** nenhuma escrita em `config.py` raiz, `pipelines/m1/`, carteira, plano, artefatos oficiais.
- **DEC-009:** demanda SÓ como premissa explícita (faixa p10/p50/p90 por tier de metragem). NUNCA derivada de lat/lng ou preditor geográfico. `demanda_fonte = "premissa_explicita"` obrigatório em cada linha.
- **`viabilidade_ponto.py` INTOCADO:** `git diff` deve ser ZERO linhas.
- **Modo COORDLESS:** `setores_df=None` em todas as chamadas do batch. Sem fetch HTTP, sem rede.
- **Saída gitignored:** `data/staging/viabilidade_candidatos.parquet` e `data/analysis/viabilidade_candidatos.md` NÃO entram no commit (verificar `.gitignore`).
- **Loop-safe confirmado:** READ-ONLY M1; sem rede/VPS/PII/credencial.
