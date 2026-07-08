# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-ATR-03-FU1 — Re-rodar o teste de estrutura (matriz vs composto) sobre o Huff DENSO

## Objetivo
Re-rodar `avaliar_estrutura_funil` (k-fold 5×5, seed=42, IC95) com o `share_captura_huff` recalculado
a partir da **base densa** do ATR-01 (`concorrentes_densos.parquet`, 10.165 pares, 40 redes) em vez do
original (~3,3 mil concorrentes), reportar R²_oof atualizado do composto vs eixos isolados vs baseline,
e re-emitir o veredito **matriz vs composto**. READ-ONLY sobre o M1; veredito em `data/analysis/` (gitignored).

## Contexto técnico levantado pelo Block Orchestrator

### Estado dos insumos disponíveis

**`data/staging/concorrentes_densos.parquet`** — 10.165 pares únicos `(hex_id_res7, rede_normalizada)`,
40 redes, colunas `hex_id_res7`, `lat`, `lng`, `rede_normalizada`, `fonte`, `flag_da_base_atual`,
`n_unidades_no_hex`, `versao_contrato`. As colunas `lat`/`lng` são centroides dos hexes derivados por
`h3.cell_to_latlng` — já prontas como `(conc_lat, conc_lng)` para `calibrar_huff_captura`.

**`data/staging/demanda_revelada_h3.parquet`** — 16.575 hexes, coluna `membros` (alvo observado).

**`src/motor_expansao/demanda_revelada/estrutura_funil.py`** — harness completo já existente:
`avaliar_estrutura_funil(df_join)` é PURA (sem I/O), recebe o frame já joinado e entrega
`EstruturaFunilResult` com todos os modelos, veredito e nota honesta. O `executar()` ao final faz o join
`demanda x mercado` e chama `avaliar_estrutura_funil`. O campo `share_captura_huff` do mercado é o eixo
de disputa — o FU1 precisa substituir esse eixo pelo share recomputado sobre a base densa.

**`src/motor_expansao/demanda_revelada/huff_captura.py`** — contém `calcular_share_por_hex` (puro,
sem alvo) e `calibrar_huff_captura` que já fazem a seleção de beta out-of-fold. O ATR-01 usou exatamente
esse harness para re-validar o Huff com a base densa (`concorrentes_densos.py::revalidar_huff_densa`).

### Diferença entre o ATR-03 original e o FU1

O **BLK-ATR-03** rodou `avaliar_estrutura_funil` com o join `demanda x hexagonos_mercado_mapeado.parquet`,
onde `share_captura_huff` veio do pipeline de mercado (base original ~3,3 mil concorrentes; cobertura útil
≈ 62% de hexes com share < 1). Resultado: **GO-composto**, R²_oof do composto +0,48, melhor eixo isolado
+0,37.

O **BLK-ATR-01** re-validou o Huff sozinho com a base densa: cobertura útil aumentou de 28%→73%,
R²_oof Huff +0,44→+0,46, rho +0,44→+0,71. Logo o eixo de disputa denso é **mais forte** que o original.

O **BLK-ATR-03-FU1** precisa repetir o ATR-03 substituindo SÓ o eixo `disputa` = `share_captura_huff`
pelo share recomputado sobre `concorrentes_densos.parquet`, mantendo os outros dois eixos
(`score_priorizacao` e `score_oportunidade_residual`) idênticos.

### Caminho de implementação recomendado

Novo script/módulo `estrutura_funil_densa.py` (ou equivalente) dentro de `demanda_revelada/` que:
1. Carrega `concorrentes_densos.parquet` → extrai `(conc_lat, conc_lng)` via `_coords_densas`
   (já disponível em `concorrentes_densos.py`).
2. Carrega o join de demanda × mercado via `_carregar_join` do `estrutura_funil.py` (ou equivalente
   inline) para obter todas as colunas necessárias: `hex_id`, `membros`, `score_priorizacao`,
   `score_oportunidade_residual`, `score_setor_2022_calibrado`, `renda_per_capita`, `uf`,
   `populacao_corte_hex`, etc.
3. Recomputa `share_captura_huff` por hex usando `calcular_share_por_hex` (de `huff_captura.py`) com
   o beta selecionado out-of-fold sobre a base densa. **Atenção**: o beta deve ser escolhido out-of-fold
   sobre a base densa — o ATR-01 já fez isso via `calibrar_huff_captura`; o FU1 pode reusar o beta
   encontrado (documentado no relatório ATR-01) ou re-selecionar inline. A opção mais limpa é
   re-selecionar inline com o mesmo BETA_GRID, pois o FU1 roda como análise nova.
4. Substitui `share_captura_huff` no frame antes de chamar `avaliar_estrutura_funil(df_join_denso)`.
5. Chama `escrever_relatorio` para materializar em `data/analysis/estrutura_funil_densa.md` (gitignored).

**Alternativa mais direta** (menos código): extender `estrutura_funil.py` com um parâmetro
`conc_lat/conc_lng` opcional em `executar()` — se fornecido, recomputa o share antes do join; se não,
usa o share do parquet de mercado. O Planner decide.

### Números de referência (do backlog)

- ATR-03 original (base ~3,3k): composto R²_oof = **+0,48**, melhor eixo isolado = **+0,37**,
  cobertura Huff ≈ **62%**. Veredito: **GO-composto**.
- ATR-01 (Huff isolado com base densa): R²_oof = **+0,46**, rho = **+0,71**, cobertura = **73%**.
- ATR-03-FU1 esperado: o composto provavelmente **sobe** (eixo de disputa mais forte), mas o
  número honesto precisa ser recomputado — é isso que este bloco entrega.

### Guardrails críticos

O harness `avaliar_estrutura_funil` não toca `score_priorizacao` (só o lê como feature).
O `share_captura_huff` recomputado é geometricamente PURO (sem alvo). O eixo `disputa` = `1 - share`
— mesma transformação do ATR-03 original, só com a base de concorrentes mais densa.
O veredito final vai para `data/analysis/estrutura_funil_densa.md` (gitignored); nada é materializado
em produção (isso é BLK-ATR-05, separado, com gate humano).

## Escopo permitido

- Novo script de análise em `src/motor_expansao/demanda_revelada/` (nome a definir pelo Planner;
  ex.: `estrutura_funil_densa.py` ou extensão de `estrutura_funil.py` com parâmetro de base densa).
- Reuso de `_coords_densas` (de `concorrentes_densos.py`) para extrair lat/lng da base densa.
- Reuso de `calcular_share_por_hex` e `BETA_GRID` (de `huff_captura.py`) para recomputar o share.
- Reuso de `avaliar_estrutura_funil` (de `estrutura_funil.py`) sem alteração — função PURA.
- Relatório `data/analysis/estrutura_funil_densa.md` (gitignored, sem PII).
- Testes unitários com fixtures sintéticas em `tests/unit/demanda_revelada/`.
- Atualização de housekeeping: `tasks/current_task.md`, `tasks/completed.md`, `tasks/backlog.md`.
- Arquivos de handoff: `context/handoff.md`, `context/handoff/`.

## Fora de escopo

- Materializar o share denso em nenhum parquet de staging ou produção (isso é BLK-ATR-05).
- Alterar `hexagonos_mercado_mapeado.parquet` ou qualquer artefato do pipeline de mercado/residual.
- Alterar `concorrentes_densos.parquet` (READ-ONLY).
- Alterar `estrutura_funil.py`, `huff_captura.py`, `concorrentes_densos.py` (preferir só leitura;
  se extensão for necessária, o Planner decide o que é minimamente invasivo).
- Qualquer escrita em artefatos M1 oficiais (`brasil_estrutural.parquet`, `brasil_priorizados.parquet`,
  `hexagonos_brasil_oportunidades.parquet`, `hexagonos_brasil_dashboard.parquet`).
- Deploy, VPS, segredos, CI de produção.
- BLK-ATR-05 (materialização em produção — gate humano separado).

## Arquivos que devem ser lidos

- `/repo/CLAUDE.md` — fonte canônica (§4/§5, DEC-008/009/012)
- `/repo/tasks/current_task.md` — escopo e guardrails do bloco atual
- `/repo/tasks/backlog.md` — linhas 1022–1052 (BLK-ATR-03-FU1) e 1055–1083 (BLK-ATR-05 para entender o que NÃO fazer)
- `/repo/src/motor_expansao/demanda_revelada/estrutura_funil.py` — harness completo (PURO, reusar)
- `/repo/src/motor_expansao/demanda_revelada/huff_captura.py` — `calcular_share_por_hex`, `BETA_GRID`, `_coords_densas` (via concorrentes_densos.py)
- `/repo/src/motor_expansao/demanda_revelada/concorrentes_densos.py` — `_coords_densas`, contrato do parquet denso
- `/repo/data/staging/concorrentes_densos.parquet` — 10.165 pares, colunas `lat`/`lng` prontas

## Arquivos que podem ser alterados

Apenas arquivos NOVOS (não modificar os módulos existentes do ATR-03/ATR-01):

- `src/motor_expansao/demanda_revelada/estrutura_funil_densa.py` — script de análise do FU1 (novo, ou extensão mínima conforme decisão do Planner)
- `tests/unit/demanda_revelada/test_estrutura_funil_densa.py` — testes com fixtures sintéticas (novo)
- `data/analysis/estrutura_funil_densa.md` — relatório gitignored (novo, não commitado)
- `tasks/current_task.md`, `tasks/completed.md`, `tasks/backlog.md` — housekeeping
- `context/handoff.md`, `context/handoff/` — handoffs de ciclo

**READ-ONLY obrigatório:**
- Todos os artefatos M1 oficiais (mtime inalterado verificado pelo QA)
- `data/staging/concorrentes_densos.parquet` (não reescrever)
- `data/staging/hexagonos_mercado_mapeado.parquet` (lido, não alterado)
- `src/motor_expansao/demanda_revelada/estrutura_funil.py` (reusar função pura `avaliar_estrutura_funil`)
- `src/motor_expansao/demanda_revelada/huff_captura.py` e `concorrentes_densos.py` (só importar)

## Critérios de aceite

1. O share `share_captura_huff` usado no FU1 é recomputado **geometricamente puro** sobre a base
   densa (`concorrentes_densos.parquet`, 10.165 pares), usando `calcular_share_por_hex` de
   `huff_captura.py` — sem alvo (`membros`) envolvido no cálculo.
2. Beta selecionado **out-of-fold** (mesma disciplina do ATR-01/ATR-07; não in-sample).
3. Relatório `data/analysis/estrutura_funil_densa.md` inclui:
   - Fonte exata do eixo de disputa ("`concorrentes_densos.parquet`, N=10.165").
   - Tabela comparativa: composto vs eixos isolados (sociodemo, mercado, disputa-denso) vs baseline,
     com R²_oof, IC95, rho_oof, RMSE_oof.
   - Cobertura útil do Huff denso (% hexes com share < 1).
   - Comparação ATR-03 original (R²_oof composto +0,48) vs FU1 (número novo).
   - Veredito honesto GO-composto-denso | GO-matriz | NO-GO com motivo explícito.
   - Todos os 8 confounds obrigatórios (cobertura ~1%, viés metropolitano, ruído coords, seleção
     plataforma, multicolinearidade, share=1 na maioria, DEC-009, matriz como default).
4. Harness out-of-fold: k-fold 5×5, seed=42, IC95 bootstrap 2000 reamostras — IDÊNTICO ao ATR-03.
5. **R² in-sample BANIDO do veredito** (só campo de auditoria rotulado, conforme DEC-008).
6. `membros` é ALVO (nunca feature/preditor) — DEC-009.
7. Módulo novo no pacote `demanda_revelada/`: **zero import** de `pipelines/m1/`, `censo_*`,
   `dashboard/`, `api/`, `config.py` raiz (pacote disjunto, DEC-012).
8. Testes com fixtures sintéticas — nunca leem `/repo/NAO_ABRA/` real; exercitam o caminho de
   recomputa-share-denso + `avaliar_estrutura_funil`.
9. Teste de anti-PII: relatório gerado pela fixture não contém colunas de `COLUNAS_PII_PROIBIDAS`.
10. `concorrentes_densos.parquet` com mtime inalterado após a execução.
11. Mtime dos 4 artefatos M1 oficiais inalterado.
12. Suíte pytest verde (`pytest -q`); ruff e mypy limpos nos arquivos novos.
13. `import streamlit_app` ok.

## Criticidade classificada
alta

## Esteira recomendada
Block Orchestrator → Planner → Builder → QA (autônoma no loop — Alta, READ-ONLY M1)

## Riscos identificados

- **Beta denso vs beta original**: o ATR-01 encontrou um beta ótimo com a base densa que pode
  diferir do ATR-03 original (que usou o share do mercado). O FU1 deve re-selecionar o beta
  out-of-fold — não reutilizar o beta do ATR-03 cegamente.
- **Custo computacional**: recomputar o share Huff por hex para cada beta da grade sobre 10.165
  concorrentes × ~16.575 hexes × 5 betas é O(n×m×k). O ATR-01 já rodou isso (via
  `calibrar_huff_captura`); o FU1 pode reusar o resultado do ATR-01 (carregar o `share` já
  calculado se materializado) ou recalcular. O Planner deve verificar se o `HuffCapturaResult`
  do ATR-01 persiste em algum lugar; caso contrário, o recálculo é necessário.
- **Isolamento de imports**: o novo módulo NÃO pode importar de `estrutura_funil.executar()` de
  forma que quebre o isolamento de pacote — deve importar SÓ `avaliar_estrutura_funil` (função
  pura) e `escrever_relatorio`, que não têm I/O embutido.
- **Degradação graciosa onde o Huff não fala**: hexes sem concorrente na janela → share = 1.0 →
  eixo disputa = percentil baixo. Com base mais densa, menos hexes caem nesse caso (cobertura
  73% vs 62% original) — mas o caminho de share=1.0 deve continuar funcionando graciosamente.
- **Veredito pode ser diferente do ATR-03**: se o eixo de disputa denso for mais correlacionado
  com `score_priorizacao` ou `score_oportunidade_residual` (redundância), o composto pode ser
  classificado como MATRIZ apesar de R²_oof maior. O teste de redundância (`LIMIAR_REDUNDANCIA=0.95`)
  do harness original já trata isso — não contornar.

## Guardrails ativos

- **§5 READ-ONLY M1**: zero recálculo de `score_priorizacao`/`hex_score_estrutural`/pesos/carteira/plano/artefatos oficiais.
- **DEC-008**: out-of-fold obrigatório vs baseline (média); R² in-sample BANIDO do veredito; IC95 bootstrap seed=42; NO-GO é resultado válido.
- **DEC-009**: `membros` é ALVO OBSERVADO; PROIBIDO usar como preditor geográfico de magnitude ou ajuste de score.
- **DEC-012**: pacote `demanda_revelada/` disjunto — novo módulo NUNCA importa de `pipelines/m1/`, `censo_*`, `dashboard/`, `api/`, `config.py` raiz; sem PII pessoal (centroides derivados de `hex_id`, nunca coords brutas).
- **Veredito em `data/analysis/`** (gitignored); sem materialização em produção — isso é BLK-ATR-05 com gate humano separado.
- **loop_guard**: o Builder deve rodar `scripts/loop_guard.py` após as alterações; nenhum caminho proibido deve aparecer no diff.
