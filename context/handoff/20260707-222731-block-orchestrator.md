# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Builder (relatório apenas — sem alteração de código de produção; criticidade Média não exige Planner)

## Bloco refinado
BLK-PROD-03 — Avaliar hex_id como category com benchmark

## Veredito
**VIÁVEL** — parquets existem, benchmark pré-conclusivo realizado durante delimitação.
A decisão pré-fixada de NÃO alterar código de produção está confirmada pelos números.

---

## Resultado do benchmark de delimitação (pré-conclusivo)

`hex_id` é **100% única** em todos os parquets principais (cardinalidade = N linhas):
- `hexagonos_mercado_mapeado.parquet`: 1.542.531 linhas, 1.542.531 hex_ids únicos
- `brasil_estrutural.parquet`: 1.542.531 / 1.542.531
- `brasil_priorizados.parquet`: 308.494 / 308.494
- `hexagonos_brasil_oportunidades.parquet`: 1.542.531 / 1.542.531

`category` é projetado para **BAIXA cardinalidade** — coluna de chave primária única é o pior caso.

Resultados medidos nesta delimitação:

| Operação | String | Category | Delta | Decisão pré-fixada |
|---|---|---|---|---|
| Merge (priorizados × mercado, 3 runs) | 0.626 s | 0.772 s | **−23% (category MAIS LENTO)** | ❌ NÃO aplica |
| isin (1.000 ids em 1,54M, 5 runs) | 0.0584 s | 0.0256 s | +56% (category mais rápido) | ✓ parcial* |
| Memória hex_id (mercado 1,54M linhas) | 98.7 MB | 138.7 MB | **+40 MB (+40% PIOR)** | ❌ NÃO aplica |

*isin é lookup pontual (< 0,1 s absoluto), não o gargalo de carga/join que o bloco avalia.

**Decisão pré-fixada: ganho ≥ 15% em tempo OU memória na operação de carga/join → NÃO atingido.**
O Builder deve apenas materializar o relatório `data/analysis/benchmark_hexid_category.md`.

---

## Objetivo
Materializar relatório reprodutível `data/analysis/benchmark_hexid_category.md` com benchmark
string vs category em carga/join dos parquets de staging, documentando a conclusão técnica.
**NÃO alterar código de produção.**

## Escopo permitido
- Criar `scripts/benchmark_hexid_category.py` — script reprodutível (não é produção)
- Criar `data/analysis/benchmark_hexid_category.md` — relatório (gitignored)
- Atualizar `tasks/completed.md` com entrada de conclusão do BLK-PROD-03

## Fora de escopo
- NÃO alterar nenhum arquivo de `src/`, `config.py`, `pipelines/m1/`, ou artefatos oficiais M1
- NÃO aplicar `category` em nenhum arquivo de carga/pipeline
- NÃO criar módulo novo em `src/`
- NÃO tocar VPS nem deploys
- NÃO fazer rede

## Parquets relevantes para o benchmark
| Arquivo | Tamanho | Linhas | hex_id únicos |
|---|---|---|---|
| `data/staging/hexagonos_mercado_mapeado.parquet` | 213 MB | 1.542.531 | 1.542.531 |
| `data/staging/brasil_estrutural.parquet` | 35 MB | 1.542.531 | 1.542.531 |
| `data/staging/brasil_priorizados.parquet` | 7 MB | 308.494 | 308.494 |
| `data/staging/hexagonos_brasil_oportunidades.parquet` | 49 MB | 1.542.531 | 1.542.531 |
| `data/staging/hexagonos_brasil_dashboard_base.parquet` | 49 MB | 1.542.531 | — |

Todos existem confirmados em `/repo/data/staging/`.

## Arquivos que devem ser lidos (pelo Builder)
- `/repo/data/staging/hexagonos_mercado_mapeado.parquet` (benchmark de join)
- `/repo/data/staging/brasil_estrutural.parquet`
- `/repo/data/staging/brasil_priorizados.parquet`
- `/repo/data/staging/hexagonos_brasil_oportunidades.parquet`
- `/repo/src/motor_expansao/dashboard/data.py` (padrões de join em produção)
- `/repo/src/motor_expansao/pipelines/calcular_colunas_mercado.py` (join mercado)

## Arquivos que podem ser alterados (pelo Builder)
- `scripts/benchmark_hexid_category.py` — CRIAR
- `data/analysis/benchmark_hexid_category.md` — CRIAR
- `tasks/completed.md` — acrescentar entrada BLK-PROD-03

## Critérios de aceite
- [ ] `data/analysis/benchmark_hexid_category.md` existe com tabela string vs category
      (tempo de merge, tempo de isin, memória de hex_id nos 4 parquets principais)
- [ ] Relatório documenta a razão técnica: hex_id é 100% única (cardinalidade = N linhas)
- [ ] Relatório conclui com "NÃO aplicar" e justificativa técnica
- [ ] Relatório referencia o critério: ganho ≥ 15% em tempo OU memória NÃO atingido
- [ ] ZERO alteração em arquivos de `src/`, `config.py`, `pipelines/m1/`, artefatos oficiais M1
- [ ] `loop_guard.py` limpo (sem diff em arquivos guardados)
- [ ] `pytest -q` verde (sem regressão; não é necessário criar novos testes)
- [ ] `ruff check src/` limpo

## Criticidade classificada
Média

## Esteira recomendada
Block Orchestrator (concluído) → Builder → QA

Justificativa: resultado pré-conclusivo e decisão pré-fixada clara. Não há ambiguidade de
produto nem de arquitetura. Planner pode ser pulado (criticidade Média, sem dúvidas abertas).

## Riscos identificados
- **Risco baixo:** o Builder pode ser tentado a aplicar `category` no isin (único caso mais
  rápido). GUARDRAIL: a decisão pré-fixada exige ganho em tempo OU memória na operação de
  **carga/join** — isin é lookup pontual (< 0,1 s absoluto), não o gargalo.
- **Risco baixo:** script pode carregar parquets de 213 MB inteiros desnecessariamente.
  Mitigação: usar `pd.read_parquet(..., columns=['hex_id'])` para medir memória isolada.

## Guardrails ativos
- §2 CLAUDE.md: "Tratar config.py, CLAUDE.md e PRD.md como fontes canônicas"
- §5 CLAUDE.md: guardrail permanente — não recalcular score_priorizacao nem artefatos M1
- §6.1 CLAUDE.md loop-safe: READ-ONLY M1; sem VPS; sem rede; escreve só `data/analysis`
- `loop_guard.py` aborta se diff tocar `config.py`/`pipelines/m1`/`*scoring*`/artefatos M1

## Notas para o Builder
1. Usar `time.perf_counter()` com N=5 repetições; descartar warmup (ou incluir mas marcar).
2. Fixar `random_state=42` para a amostra de isin.
3. Usar `pd.read_parquet(..., columns=['hex_id'])` para medição de memória isolada.
4. O relatório deve estar em `data/analysis/`, não conter PII, extensão `.md`.
5. Não é necessário criar teste pytest — é script/relatório, não código de produção.
6. Commitar apenas `scripts/benchmark_hexid_category.py` e `tasks/completed.md`.
   `data/analysis/benchmark_hexid_category.md` pode ser gitignored (verificar `.gitignore`).
