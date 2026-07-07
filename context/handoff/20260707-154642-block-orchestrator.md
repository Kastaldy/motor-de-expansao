# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-ATR-01-FU1 — Cruzar a base densa de concorrentes com as unidades reais do NAO_ABRA (aferição de precisão/overlap)

## Objetivo
Produzir, para cada referência do NAO_ABRA (`01_SmartFit.xlsx` e `03_Competidores.xlsx`), as métricas de recall, precisão-proxy e overlap por rede contra `concorrentes_densos.parquet`, num relatório em `data/analysis/` (gitignored) que responda se a base densa é suficiente ou precisa de ajuste.

## Contexto técnico levantado pelo Block Orchestrator

### Insumos reais (lidos apenas para análise; nunca versionados)

**`/repo/NAO_ABRA/01_SmartFit.xlsx`** — 970 unidades Smart Fit com colunas `ID`, `Nome`, `Latitude`, `Longitude`. Coordenadas de alta precisão (6–7 casas decimais). Nenhum NaN. Ao converter para H3 res-7, gera 748 hexes únicos.

**`/repo/NAO_ABRA/03_Competidores.xlsx`** — 24.045 linhas, colunas `Latitude`, `Longitude`, `Cluster_ID` (100% NaN), `Total_Academias`, `Total_Alunos_Cluster`, `Nome_Academia`, `Plano`, `Alunos_Academia`, `Município`. O campo `Município` contém modalidades (musculação, pilates, crossfit…), não nome de cidade. O campo `Plano` indica plano TotalPass (tp1..tp7). Coordenadas com **1–2 casas decimais** (~1–10 km de imprecisão, maior que o diâmetro de um hex res-7 de 1,4 km de aresta). Rede identificável via `Nome_Academia` + `classificar_rede`.

### Estado atual de `concorrentes_densos.parquet`

- 10.165 pares únicos `(hex_id_res7, rede_normalizada)`.
- 40 redes. Fontes: `base_atual` (2.701), `totalpass` (5.969), `unidades` (765), `wellhub` (730).
- Colunas do contrato: `hex_id_res7`, `lat`, `lng`, `rede_normalizada`, `fonte`, `flag_da_base_atual`, `n_unidades_no_hex`, `versao_contrato`.

### Achados do cruzamento exploratório (não persistidos)

**vs 01_SmartFit.xlsx (smart_fit):**
- 748 hexes únicos no 01_SmartFit vs 790 na base densa.
- Interseção: 733 hexes → **recall = 97,9%** (só 15 hexes SmartFit ausentes da base densa).
- 57 hexes na base densa sem correspondente no 01_SmartFit (podem ser unidades abertas após a coleta do xlsx, ou duplicatas não-colapsadas).

**vs 03_Competidores.xlsx (todas as redes):**
- 24.045 linhas → 7.253 pares únicos `(hex, rede)` após `classificar_rede`.
- Interseção com base densa: 5.109 pares → **recall = 70,4%**.
- **Atenção: este recall é artificialmente baixo** porque as coordenadas de 03_Competidores têm precisão 1–2 casas decimais (~1–10 km), o que faz o mesmo estabelecimento mapear para hexes diferentes dos registrados via CSVs TotalPass/WellHub (que têm coordenadas completas). Não é gap de cobertura real — é imprecisão de coordenada. O relatório deve documentar isso explicitamente.
- 2.144 pares de 03_Competidores sem correspondente na base densa (maioria `independente`).

**Gap de token — SKYFIT:**
- 03_Competidores tem 339 linhas com `Nome_Academia` contendo "SKYFIT"; `classificar_rede("SKYFIT ACADEMIA X")` retorna `independente` (o token `sky_fit`/`skyfit` não existe em `classificacao_rede_menor.py`).
- Na base densa, `skyfit` tem 469 unidades, todas vindas de `fonte=unidades` (`concorrentes/Unidades/unidades_skyfit.csv`).
- Consequência: o cruzamento "por rede" entre 03_Competidores e a base densa subestima o recall de SKYFIT. O relatório deve sinalizar esse gap de token como **caveat**, não como falha de cobertura da base densa.

### Arquivo a NÃO ler

`/repo/NAO_ABRA/totalpass_final (72) (1).html` — dump pessoal; proibido por DEC-012 e pelo marcador `loop-safe`.

## Escopo permitido

- Novo módulo de análise em `src/motor_expansao/demanda_revelada/aferir_overlap_nao_abra.py` (ou nome equivalente): lê os dois XLSXs, converte lat/lng → hex res-7, aplica `classificar_rede` ao `Nome_Academia`, computa métricas de recall/overlap por rede contra `concorrentes_densos.parquet` e gera relatório markdown.
- Relatório `data/analysis/relatorio_overlap_nao_abra.md` (gitignored).
- Testes unitários com fixtures sintéticas em `tests/unit/test_aferir_overlap_nao_abra.py` (nunca leem arquivos reais de `/repo/NAO_ABRA/`).
- Atualização de `tasks/completed.md`, `tasks/backlog.md`, `tasks/current_task.md` e arquivos de handoff.

## Fora de escopo

- Leitura de `/repo/NAO_ABRA/totalpass_final*.html` (dado pessoal; DEC-012).
- Leitura de qualquer outro arquivo do NAO_ABRA além de `01_SmartFit.xlsx` e `03_Competidores.xlsx`.
- Reescrita de `concorrentes_densos.parquet` (READ-ONLY).
- Adição de token `skyfit` em `classificacao_rede_menor.py` (fora do escopo; sinalizar como caveat).
- Integração ao residual/carteira/plano (isso é BLK-TP-09 / DEC-013 §3, sob gate humano).
- Qualquer escrita em artefatos M1 oficiais ou em `pipelines/m1/`.
- Deploy, VPS, segredos.

## Arquivos que devem ser lidos

- `/repo/CLAUDE.md` — fonte canônica (§2, §4, §5, DEC-012)
- `/repo/src/motor_expansao/demanda_revelada/concorrentes_densos.py` — contrato e estrutura da base densa
- `/repo/src/motor_expansao/demanda_revelada/classificacao_rede_menor.py` — função `classificar_rede` e tokens
- `/repo/src/motor_expansao/demanda_revelada/contrato.py` — constante `H3_RES_CONTRATO`
- `/repo/data/staging/concorrentes_densos.parquet` — schema e conteúdo (leitura via pandas)
- `/repo/NAO_ABRA/01_SmartFit.xlsx` — estrutura: 970 linhas × 4 colunas (`ID`, `Nome`, `Latitude`, `Longitude`)
- `/repo/NAO_ABRA/03_Competidores.xlsx` — estrutura: 24.045 linhas × 9 colunas; coords arredondadas 1–2 decimais
- `/repo/tasks/backlog.md` (trecho BLK-ATR-01-FU1, linhas ~1017–1048)
- `/repo/tasks/completed.md` (entrada BLK-ATR-01 para entender o que foi produzido)

## Arquivos que podem ser alterados

Apenas arquivos NOVOS (não modificar os existentes do ATR-01):

- `src/motor_expansao/demanda_revelada/aferir_overlap_nao_abra.py` — módulo de análise (novo)
- `tests/unit/test_aferir_overlap_nao_abra.py` — testes com fixtures sintéticas (novo)
- `data/analysis/relatorio_overlap_nao_abra.md` — relatório gitignored (novo, não commitado)
- `tasks/current_task.md`, `tasks/completed.md`, `tasks/backlog.md` — housekeeping do bloco
- `context/handoff.md`, `context/handoff/` — handoffs de ciclo

**READ-ONLY obrigatório:**
- `data/staging/concorrentes_densos.parquet` — não reescrever
- Todos os artefatos M1 oficiais (`brasil_estrutural.parquet`, `brasil_priorizados.parquet`, `hexagonos_brasil_oportunidades.parquet`, `hexagonos_brasil_dashboard.parquet`)
- `src/motor_expansao/demanda_revelada/concorrentes_densos.py` e demais módulos existentes
- `src/motor_expansao/demanda_revelada/classificacao_rede_menor.py`

## Critérios de aceite

1. Módulo `aferir_overlap_nao_abra.py` isolado no pacote `demanda_revelada/`: sem import de `pipelines/m1/`, `dashboard/`, `censo_*`, `api/`, `config.py`.
2. Lê SOMENTE `01_SmartFit.xlsx` e `03_Competidores.xlsx` do NAO_ABRA; nunca toca `totalpass_final*.html`.
3. PII textual (nome de unidade) é usada em memória apenas para `classificar_rede`; não persistida no relatório nem em qualquer artefato (relatório só contém contagens/métricas agregadas).
4. Testes unitários com fixtures sintéticas (DataFrames construídos no teste); não leem arquivos reais de `/repo/NAO_ABRA/`.
5. Teste equivalente a `test_zero_pii`: verificar que o relatório gerado pela fixture não contém strings de nome de unidade.
6. Relatório `data/analysis/relatorio_overlap_nao_abra.md` inclui:
   - Recall por rede para `01_SmartFit.xlsx` (join por hex_id_res7 + rede `smart_fit`).
   - Recall/overlap por rede para `03_Competidores.xlsx` com caveat explícito de imprecisão de coordenada (1–2 decimais → viés de hex).
   - Nota sobre gap de token SKYFIT (classificado como `independente` em 03_Competidores; presente na base densa via `fonte=unidades`).
   - Recomendação clara: a base densa é suficiente para o Huff ou precisa de ajuste?
7. `concorrentes_densos.parquet` não reescrito (mtime inalterado).
8. mtime dos 4 artefatos oficiais M1 inalterado.
9. Suíte pytest verde (`pytest -q`); `import streamlit_app` ok.
10. ruff e mypy limpos nos arquivos novos.

## Criticidade classificada
Média

## Esteira recomendada
Block Orchestrator → Planner → Builder → QA

## Riscos identificados

- **Imprecisão de coordenada em 03_Competidores** (coords 1–2 decimais): o join por hex res-7 vai artificialmente subestimar o recall (~70% observado). O Builder precisa documentar isso no relatório e NÃO tratar como gap de cobertura real. Uma abordagem de join alternativo (buffer de coordenada ou join por nome normalizado) pode ser considerada pelo Planner para complementar a métrica.
- **Gap de token SKYFIT**: `classificar_rede` não reconhece "SKYFIT" → classifica como `independente`, distorcendo o recall de SKYFIT no 03_Competidores. Não é escopo deste bloco corrigir o token; apenas documentar.
- **03_Competidores representa academias menores** (maioria `independente` = 97,8% das linhas): o recall "por rede" é dominado por independentes, onde a base densa tem menos representação direta. O relatório deve estratificar por rede para evitar conclusões enganosas.
- **Fixtures sintéticas**: os testes não podem usar dados reais (NAO_ABRA/ nunca versionado). O Builder deve criar fixtures minimais que exercitem os caminhos de cálculo sem depender de leitura de disco.

## Guardrails ativos

- §5 READ-ONLY M1: zero recálculo de score/pesos/carteira/plano/artefatos oficiais.
- DEC-012: lê SÓ dado de estabelecimento (`lat/long/nome de unidade`); NUNCA o dump pessoal `totalpass_final*.html`; persiste ZERO PII (nome de unidade só em memória para classificar rede).
- DEC-013: concorrentes só na camada de mercado/residual (este bloco é de análise/validação, não integração).
- Pacote disjunto: `demanda_revelada/` sem import de `pipelines/m1/`, `dashboard/`, `censo_*`, `api/`, `config.py`.
- `concorrentes_densos.parquet` só LIDO (não reescrito sem necessidade de nova materialização).
- Testes com fixtures sintéticas (nunca leem `/repo/NAO_ABRA/` real).
