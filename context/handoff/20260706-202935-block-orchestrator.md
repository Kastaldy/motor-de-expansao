# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-ATR-04 — Visualização dos resultados do funil (gráficos + números concretos para decisão)

Módulo `viz_atratividade.py` no pacote disjunto `demanda_revelada/` que carrega os dois parquets
existentes, roda o harness ATR-03 inline e materializa PNGs + markdown em `data/analysis/viz_atratividade/`.

## Objetivo
Produzir um relatório visual completo (PNGs via matplotlib + markdown-resumo) com os números
concretos do funil de atratividade para subsidiar a decisão humana sobre estrutura (matriz vs
composto) e o gate do BLK-ATR-05.

## Fonte dos dados — decisão crítica do BO

Os artefatos gitignored dos blocos anteriores (concorrentes_densos.parquet, estrutura_funil.md)
NÃO foram materializados. O módulo NÃO depende deles: **roda o harness ATR-03 inline**.

Fontes disponíveis em disco (existem):
- `data/staging/hexagonos_mercado_mapeado.parquet` — 1.542.531 linhas, 139 colunas, inclui os
  3 eixos: `score_priorizacao`, `score_oportunidade_residual`, `share_captura_huff`,
  `score_setor_2022_calibrado`, `renda_per_capita`, `uf`, `populacao_corte_hex`, `pop_total`.
- `data/staging/demanda_revelada_h3.parquet` — 16.575 linhas com `membros`.

Join inner por `hex_id`: 16.411 linhas. Após gate ATR-02 (pop >= 5.000 AND renda_pc >= 1.500):
**4.630 linhas** (~28%). Concentração: SP 32%, MG 10%, PR 9%, RS 9%, SC 8%.

`flag_gate_atratividade` NÃO existe no parquet do mercado (ATR-02 adicionou ao
`calcular_colunas_mercado.py` mas o parquet de staging não foi regenerado). O módulo replica o
gate inline reusando `aplicar_gate_atratividade` do ATR-03.

## Biblioteca de visualização — decisão do BO

**Matplotlib via backend Agg** (sem display).

Justificativa: Plotly está nas deps base, mas `kaleido` (necessário para PNG) não está instalado
e não funciona neste ambiente headless (falha com erro de processo). Matplotlib NÃO está no
`pyproject.toml` como dep base — o Builder deve adicioná-la. Não é dep nova de produção: já é
transitivamente instalada pelo ambiente, e vai formalmente para as deps base em `pyproject.toml`
(seção `# Analise`). O backlog cita "Plotly ou Matplotlib"; o current_task.md já especifica
"apenas Matplotlib (sem Plotly/kaleido — evitar dep nova)". Matplotlib é stdlib de análise
científica Python, não acarreta dep transitiva nova relevante.

Import obrigatório no módulo: `import matplotlib; matplotlib.use("Agg")` antes de qualquer
`import matplotlib.pyplot`.

## Escopo permitido
- Criar `src/motor_expansao/demanda_revelada/viz_atratividade.py` (módulo novo).
- Criar `tests/unit/demanda_revelada/test_viz_atratividade.py` com fixtures sintéticas.
- Adicionar `"matplotlib>=3.7.0"` às deps base de `pyproject.toml` (seção Analise).
- Materializar `data/analysis/viz_atratividade/` com PNGs + markdown (gitignored, não commitar).
- Gravar `context/handoff.md` e snapshot datado.
- Atualizar `tasks/current_task.md`, `tasks/completed.md`, `tasks/backlog.md`.

## Gráficos a gerar (conteúdo mínimo do backlog, mapeado para dados reais disponíveis)

### (a) Cobertura do Huff — hexes com share < 1.0 por UF
- Fonte: `hexagonos_mercado_mapeado.parquet` coluna `share_captura_huff`.
- Dado: 0,35% do universo total tem share < 1.0 (~5.468 hexes). Mostrar por UF (barras).
- Nota honesta: a "base densa" do ATR-01 não foi materializada; este gráfico usa a base atual.
  Sem "antes/depois" — só "estado atual". O módulo documenta essa limitação no markdown.

### (b) Impacto do gate ATR-02 por UF
- Fonte: join demanda x mercado (16.411 → 4.630 após gate).
- Gráfico: barras empilhadas por UF (aprovados vs reprovados por gate).

### (c) Distribuições dos 3 eixos normalizados (pós-gate)
- Fonte: chamar `normalizar_eixos(df_pos_gate)` do ATR-03 nos dados reais.
- Histogramas (3 subplots: sociodemo, mercado, disputa).

### (d) Matriz de quadrantes residual x disputa
- Eixo X: `score_oportunidade_residual` (dividido na mediana).
- Eixo Y: `1 - share_captura_huff` = disputa (dividido na mediana).
- 4 quadrantes com contagens reais e rótulos semânticos:
  - Q1 (alto residual, alta disputa): "Mercado grande e disputado"
  - Q2 (alto residual, baixa disputa): "Nicho defensável (oportunidade prime)"
  - Q3 (baixo residual, alta disputa): "Espaço saturado"
  - Q4 (baixo residual, baixa disputa): "Mercado maduro"
- Contagens reais pós-gate (referência): Q1~1309, Q2~1006, Q3~1006, Q4~1309.

### (e) Comparação R2_oof por modelo (com IC95)
- Fonte: chamar `avaliar_estrutura_funil(df_join_real)` — roda o harness ATR-03 nos dados reais.
- Gráfico de barras horizontais (baseline, sociodemo, mercado, disputa, censitário, composto)
  com IC95 como barras de erro. Veredito "GO-composto" ou "MATRIZ" destacado no título.
- ATENCAO: esta é operação relativamente cara (k-fold 5×5 sobre ~4k linhas). Aceitável para
  execução offline; os testes usam fixture sintética pequena.

### (f) Correlações cruzadas entre eixos
- Heatmap 3×3 dos eixos normalizados (Spearman) — dados do `EstruturaFunilResult.correlacoes_cruzadas`.

## Estrutura do módulo `viz_atratividade.py`

Funções puras (testáveis com fixture sintética):
- `gerar_grafico_gate_por_uf(df_join, df_pos_gate, *, out_dir) -> Path`
- `gerar_grafico_distribuicoes_eixos(df_norm, *, out_dir) -> Path`
- `gerar_grafico_quadrantes(df_pos_gate, *, out_dir) -> Path`
- `gerar_grafico_r2_modelos(result: EstruturaFunilResult, *, out_dir) -> Path`
- `gerar_grafico_cobertura_huff(df_mercado, *, out_dir) -> Path`
- `gerar_grafico_correlacoes(result: EstruturaFunilResult, *, out_dir) -> Path`
- `gerar_relatorio_markdown(result, paths_png, *, out_dir) -> Path`

Orquestrador (caminho de disco — pragma: no cover):
- `executar(mkt_path, dem_path, *, out_dir) -> None`

Cada função de gráfico recebe dados já carregados (DataFrames ou EstruturaFunilResult) e
`out_dir: Path`, salva o PNG e retorna o Path. O orquestrador faz o join real, chama
`avaliar_estrutura_funil` e chama cada função. O `if __name__ == "__main__"` delega para
`executar`.

## Testes

Arquivo: `tests/unit/demanda_revelada/test_viz_atratividade.py`

Fixtures sintéticas (igual ao padrão ATR-03): DataFrames pequenos (N=50 a 100), sem I/O real.
Testes:
- Que cada função de gráfico aceita o fixture e devolve um Path existente.
- Que o PNG gerado tem tamanho > 1 kB (não vazio).
- Que o markdown-resumo referencia os caminhos dos PNGs.
- Anti-PII: nenhum token de COLUNAS_PII_PROIBIDAS no markdown gerado.
- Isolamento: nenhum import de `pipelines/m1`, `dashboard`, `censo_*`, `api`.
Usar `tmp_path` do pytest para `out_dir` (os PNGs dos testes ficam no tmp do pytest).

## Fora de escopo
- Materializar `concorrentes_densos.parquet` ou `estrutura_funil.md` (operações caras, gitignored).
- Gráfico "antes/depois da densificação" do ATR-01 (base densa não existe; documentar limitação).
- Alterar qualquer pipeline ou parquet de staging.
- Qualquer escrita em artefatos M1 oficiais.
- Interatividade (sem Streamlit, sem Dash, sem Plotly interativo).
- Deploy ou VPS.
- Alterar `calcular_colunas_mercado.py` ou qualquer pipeline de mercado.

## Arquivos que devem ser lidos
- `/repo/src/motor_expansao/demanda_revelada/estrutura_funil.py` — funções puras reusadas
- `/repo/src/motor_expansao/demanda_revelada/contrato.py` — COLUNAS_PII_PROIBIDAS
- `/repo/tests/unit/demanda_revelada/test_estrutura_funil.py` — padrão de fixture sintética
- `/repo/pyproject.toml` — onde adicionar matplotlib
- `/repo/tasks/current_task.md`
- `/repo/tasks/backlog.md` (seção BLK-ATR-04)

## Arquivos que podem ser alterados
- `src/motor_expansao/demanda_revelada/viz_atratividade.py` (CRIAR — módulo novo)
- `tests/unit/demanda_revelada/test_viz_atratividade.py` (CRIAR — testes)
- `pyproject.toml` (adicionar `"matplotlib>=3.7.0"` às deps base)
- `tasks/current_task.md`, `tasks/completed.md`, `tasks/backlog.md`
- `context/handoff.md`, `context/handoff/`

NÃO ALTERAR:
- Qualquer arquivo em `pipelines/m1/`, `pipelines/`, `dashboard/`, `censo_*`, `api/`
- `calcular_colunas_mercado.py` ou qualquer pipeline de mercado
- Artefatos oficiais do M1
- `estrutura_funil.py` (só importado, não editado)

## Critérios de aceite
- `src/motor_expansao/demanda_revelada/viz_atratividade.py` existe e passa ruff + mypy.
- `tests/unit/demanda_revelada/test_viz_atratividade.py` passa com fixtures sintéticas.
- Suite completa verde (`pytest -q` sem novos falhos).
- `import streamlit_app` ok.
- Módulo isolado: nenhum import de `pipelines/m1`, `dashboard`, `censo_*`, `api`.
- `matplotlib` adicionado ao `pyproject.toml`.
- `data/analysis/viz_atratividade/` materializado com PNGs + markdown (não commitado).
- Mtime dos 4 artefatos oficiais M1 inalterado.
- Nenhum PII em imagens/markdown.

## Criticidade classificada
Média

## Esteira recomendada
Block Orchestrator (este) → Planner → Builder → QA

## Riscos identificados
- `avaliar_estrutura_funil` com dados reais (~4.630 linhas, k-fold 5×5) levará alguns segundos
  de CPU — aceitável offline, mas os testes unitários NÃO devem chamar `executar` (fixture
  sintética). A função `executar` deve ter `pragma: no cover`.
- matplotlib não está formalmente no pyproject.toml — o Builder deve adicioná-la para que o
  CI instale corretamente via `pip install -e ".[dev]"`.
- O gráfico de "cobertura antes/depois" (ATR-01) só pode mostrar "estado atual" (base densa não
  materializada). Documentar a limitação honestamente no markdown; não é bug.
- Compatibilidade mypy com matplotlib: usar `# type: ignore[import-untyped]` se necessário
  (matplotlib não tem stubs tipados nativos).
- Plotly está nas deps mas não gera PNG sem kaleido (kaleido falha neste ambiente headless).
  Confirmar que o módulo usa SOMENTE matplotlib para geração de PNG.

## Guardrails ativos
- CLAUDE.md §5 (READ-ONLY M1): mtime dos 4 artefatos oficiais M1 inalterado.
- DEC-012: pacote disjunto — sem imports de `pipelines/m1/`, `dashboard/`, `censo_*`, `api/`.
- DEC-012: sem PII em nenhuma imagem/legenda (só contagens/métricas agregadas).
- DEC-009: `membros` é ALVO; não usar como preditor de magnitude.
- `data/analysis/viz_atratividade/` é gitignored — não commitar PNGs.
- CI não deve regredir (suite verde, ruff, mypy limpos).
