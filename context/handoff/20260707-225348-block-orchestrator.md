# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-PROD-06 — Relatório de movimentação concorrencial (a partir de staging)

Gerar `data/analysis/movimentacao_concorrencial.md` com retrato atual da concorrência: contagem
de unidades por rede/UF/cidade, oferta consumida e impacto nas oportunidades residuais, a partir
dos parquets já disponíveis em `data/staging/`. READ-ONLY sobre o M1.

## Objetivo
Materializar `data/analysis/movimentacao_concorrencial.md` a partir dos parquets de concorrentes
em staging, sem tocar score/artefatos do M1 e sem fazer coleta ao vivo.

## Escopo permitido
- Criar `scripts/movimentacao_concorrencial.py` (script NOVO, analítico, read-only)
- Gerar `data/analysis/movimentacao_concorrencial.md` (gitignored, não oficial)
- Ler: `concorrentes_mapeados.parquet`, `concorrentes_densos.parquet`, `hexagonos_mercado_mapeado.parquet`
- Join via `hex_id_res7` para obter `uf`/`nome_municipio` por unidade concorrente (match 99,5%)
- Adicionar testes unitários/de integração para o script (suíte verde obrigatória)

## Fora de escopo
- Coleta ao vivo de concorrentes (essa é a DEC-013/VPS, fora do loop)
- Alteração de `score_priorizacao`, `hex_score_estrutural`, carteira, plano, artefatos M1 oficiais
- Alteração de qualquer parquet em `data/staging/` (READ-ONLY)
- Delta temporal entre snapshots (APENAS 1 snapshot disponível — veja seção de dados)
- Deploy ou push para VPS
- Integração com coleta semanal (já existe via DEC-013)

## Dados disponíveis (investigação concluída pelo BO)

### `data/staging/concorrentes_mapeados.parquet`
- Shape: 3.296 × 11 colunas
- Colunas: `concorrente_id`, `rede`, `nome_unidade`, `lat`, `lng`, `data_coleta`, `arquivo_origem`,
  `flag_coord_valida`, `flag_duplicado_rede_coord`, `status_registro`, `hex_id_res7`
- 28 redes mapeadas; 3.179 registros válidos (`status_registro='valido'`)
- Sem UF/cidade diretamente — join necessário via `hex_id_res7`
- Datas de coleta: 2026-04-22 a 2026-05-04 (ÚNICO snapshot)

### `data/staging/concorrentes_densos.parquet`
- Shape: 10.165 × 8 colunas
- Colunas: `hex_id_res7`, `lat`, `lng`, `rede_normalizada`, `fonte`, `flag_da_base_atual`,
  `n_unidades_no_hex`, `versao_contrato`
- Fontes: `base_atual` (2.701), `totalpass` (5.969), `wellhub` (730), `unidades` (765)
- 40 redes (inclui academias independentes/bairro via TotalPass/Wellhub)
- ATENCAO: TotalPass/Wellhub NAO entram no `oferta_consumida_mercado_estimada` do parquet de
  mercado — mencionar como base complementar, sem dupla contagem

### `data/staging/hexagonos_mercado_mapeado.parquet` (join de geo + oferta)
- Shape: 1.542.531 × 139 colunas
- Colunas relevantes: `hex_id`, `uf`, `cidade`, `nome_municipio`, `n_concorrentes_mapeados_1km`,
  `n_concorrentes_mapeados_2km`, `n_smart_fit_2km`, `n_bluefit_2km`, `n_panobianco_2km`,
  `dist_concorrente_mais_proximo_m`, `oferta_efetiva_mapeada_1km`, `oferta_efetiva_mapeada_2km`,
  `rede_dominante_2km`, `gap_competitivo_2km`, `pressao_concorrencial_score_2km`, `n_redes_mapeadas`,
  `oferta_consumida_mercado_estimada`, `oferta_efetiva_disponivel`
- data_snapshot_mercado: '2026-06-11' (UNICO snapshot)

### Situação de snapshots temporais
SNAPSHOT UNICO — não há série histórica. O relatório deve ser retrato atual com nota explícita
de limitação (conforme decisão pré-fixada do backlog: "se só 1 snapshot → gerar retrato atual,
documentando a limitação").

## Estrutura sugerida para o relatório (orientação ao Planner)

1. **Resumo executivo** — total de unidades mapeadas, redes ativas, data do snapshot único
2. **Contagem por rede** — top redes por número de unidades válidas (`concorrentes_mapeados`)
3. **Distribuição por UF** — join `hex_id_res7` → `hexagonos_mercado_mapeado.uf`
4. **Top cidades/municípios** — por número de unidades concorrentes
5. **Oferta consumida** — `oferta_consumida_mercado_estimada` e `oferta_efetiva_mapeada` agregadas por UF
6. **Impacto no residual** — `oferta_efetiva_disponivel` por UF/cidade
7. **Rede dominante por UF** — via `rede_dominante_2km` agregado por hexágono
8. **Base complementar (densos)** — TotalPass/Wellhub com nota de não-inclusão no residual
9. **Limitação: snapshot único** — sem delta; estrutura preparada para futuros snapshots

## Arquivos que devem ser lidos
- `/repo/CLAUDE.md` (§2/§5/§6.1)
- `/repo/tasks/backlog.md` (seção BLK-PROD-06)
- `/repo/data/staging/concorrentes_mapeados.parquet` (inspecionar)
- `/repo/data/staging/concorrentes_densos.parquet` (inspecionar)
- `/repo/data/staging/hexagonos_mercado_mapeado.parquet` (só colunas relevantes)
- `/repo/scripts/loop_guard.py` (confirmar que nenhum arquivo proibido é tocado)

## Arquivos que podem ser alterados
- `/repo/scripts/movimentacao_concorrencial.py` — NOVO (script analítico read-only)
- `/repo/data/analysis/movimentacao_concorrencial.md` — NOVO output (gitignored)
- `/repo/tests/` — novos testes para o script (suíte verde obrigatória)
- `/repo/tasks/current_task.md` — atualização de status

## Arquivos que NAO podem ser alterados
- `/repo/src/motor_expansao/` (nenhum arquivo de produção)
- `/repo/data/staging/` (nenhum parquet — READ-ONLY)
- Qualquer `config.py`
- Artefatos oficiais do M1

## Critérios de aceite
- `data/analysis/movimentacao_concorrencial.md` gerado e determinístico (re-execução = mesmo resultado)
- Script `scripts/movimentacao_concorrencial.py` executa sem rede, sem escrita em artefatos M1
- `loop_guard.py` limpo (zero arquivos proibidos tocados)
- Suíte pytest verde (sem regressão + novos testes do script)
- ruff limpo
- Relatório contém nota explícita de limitação de snapshot único
- Nenhuma coluna de `score_priorizacao`/carteira/plano alterada

## Criticidade classificada
Média (analytics READ-ONLY sobre o M1; bloco loop-safe)

## Esteira recomendada
Block Orchestrator (concluído) → Planner → Builder → QA

## Riscos identificados
- Join via `hex_id_res7` tem 99,5% de match (17 unidades sem hex): tratar graciosamente (drop com log)
- `hexagonos_mercado_mapeado.parquet` é grande (1,5 M linhas × 139 cols): ler só as colunas necessárias
  (usar `columns=[...]` no `pd.read_parquet`) para evitar consumo excessivo de memória
- TotalPass/Wellhub no `concorrentes_densos` têm muitas academias já duplicadas nos mapeados:
  reportar separadamente e NAO somar na oferta consumida do M1 (evitar dupla contagem)
- Script deve ser idempotente (re-execução substitui o `.md` sem deixar estado residual)

## Guardrails ativos
- §2: READ-ONLY M1; sem dependência de API ao vivo; output em `data/analysis/` (gitignored)
- §5 guardrail permanente: análises NAO podem recalcular ou alterar `score_priorizacao`,
  `hex_score_estrutural`, carteira, plano ou artefatos oficiais do M1
- §6.1 loop-safe: sem VPS, sem rede, sem chave de deploy, sem artefatos M1; `loop_guard.py` obrigatório
- DEC-013: a COLETA de concorrentes é da VPS/cron — este bloco só LÊ o que já está em staging
