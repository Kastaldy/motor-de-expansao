# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-ATR-02 — Gate de viabilidade absoluto (`flag_gate_atratividade`) na camada de mercado

Adiciona uma coluna binária `flag_gate_atratividade = populacao_corte_hex >= 5000 AND renda_per_capita >= 1500`
na camada paralela de mercado, **sem tocar** `flag_viavel`, `RENDA_MIN`, `config.py` nem nenhum artefato M1.
É o filtro binário da Etapa 1 do funil de atratividade (abaixo de qualquer piso → fora do ranking das etapas seguintes).

## Objetivo
Materializar `flag_gate_atratividade` em `calcular_colunas_mercado.py` reutilizando `populacao_corte_hex`
(já derivado por `pop_corte.py`) e `renda_per_capita` (coluna existente do M1 no dataframe de mercado),
reportar contagem de hexes aprovados e distribuição por UF em comentário de validação.

## Escopo permitido
- Adicionar a constante `RENDA_PER_CAPITA_MIN_ATR = 1_500` em `calcular_colunas_mercado.py`
  (constante local da camada de mercado/paralela — **NÃO** entra em `config.py` nem em `src/motor_expansao/config.py`).
- Adicionar a coluna `flag_gate_atratividade` na função `calcular()` de `calcular_colunas_mercado.py`,
  após a derivação de `populacao_corte_hex` / `flag_pop_min_5k` (seção 5.4, após a linha `df = derive_pop_cut_columns(...)`).
- Lógica: `flag_gate_atratividade = flag_pop_min_5k & (renda_per_capita >= RENDA_PER_CAPITA_MIN_ATR)`,
  onde `renda_per_capita` é a coluna já presente no dataframe de entrada (vem do M1 via `hex_enrichment.py`
  e consta em `SOURCE_REQUIRED_COLS`). Converter para numérico com `pd.to_numeric(..., errors="coerce")`
  antes do comparador; NaN → False.
- Adicionar `flag_gate_atratividade` ao conjunto `required` da função `validar()` e imprimir
  contagem + percentual de aprovados, além de distribuição por UF (`.groupby("uf")["flag_gate_atratividade"].sum()`).
- Escrever testes unitários em `tests/unit/test_calcular_colunas_mercado_gate.py` (arquivo novo):
  1. Hex acima dos dois pisos → `flag_gate_atratividade = True`.
  2. Hex abaixo do piso de população → `False`.
  3. Hex abaixo do piso de renda → `False`.
  4. Hex com `renda_per_capita` NaN → `False`.
  5. Hex com `renda_per_capita` exatamente em 1.500 → `True` (limiar inclusivo `>=`).
  6. `score_priorizacao` e `hex_score_estrutural` inalterados após o cálculo.
- Atualizar `docs/modelo_mercado_hexagonos.md` seção 5.4 para registrar a nova coluna: nome,
  tipo bool, fórmula, constante local `RENDA_PER_CAPITA_MIN_ATR`, e nota de que não substitui
  `flag_viavel` nem `flag_sam`.

## Fora de escopo
- Alterar `flag_viavel`, `RENDA_MIN`, `renda_target_proxy` ou qualquer lógica do M1 (`pipelines/m1/`).
- Alterar `src/motor_expansao/config.py` — a constante `RENDA_PER_CAPITA_MIN_ATR` fica exclusivamente em `calcular_colunas_mercado.py`.
- Alterar `pop_corte.py` — reutilizar como está; `flag_pop_min_5k` já é derivado corretamente pela função existente.
- Alterar o gate `flag_sam` (DEC-007) — `flag_gate_atratividade` é coluna paralela independente; não substituí-la em `tese_entrada`/`prioridade_mercado_mapeado`.
- Usar `renda_target_proxy` (proxy domiciliar escalado) como régua de renda — usar `renda_per_capita` direto.
- Usar `renda_per_capita_setor_2022_calibrada` como valor do gate (não previsto no backlog; `renda_per_capita` basta).
- Regenerar artefatos M1 oficiais (`brasil_estrutural.parquet`, `brasil_priorizados.parquet`, `hexagonos_brasil_oportunidades.parquet`, `hexagonos_brasil_dashboard.parquet`).
- Deploy, VPS, Docker, CI workflows.
- Etapas 2–N do funil de atratividade (BLK-ATR-03 e seguintes).

## Arquivos que devem ser lidos
- `/repo/src/motor_expansao/pipelines/calcular_colunas_mercado.py` — local exato da nova constante e coluna (seção 5.4, após `derive_pop_cut_columns`).
- `/repo/src/motor_expansao/pipelines/pop_corte.py` — fonte única da régua de população (reutilizar sem alterar).
- `/repo/tests/unit/test_pop_cut.py` — padrão de fixture e asserção a seguir nos novos testes.
- `/repo/docs/modelo_mercado_hexagonos.md` — seção 5.4 a atualizar com o contrato da nova coluna.
- `/repo/scripts/loop_guard.py` — confirmar que nenhum path alterado dispara abort.

## Arquivos que podem ser alterados
- `/repo/src/motor_expansao/pipelines/calcular_colunas_mercado.py` — adicionar constante, coluna e validação.
- `/repo/tests/unit/test_calcular_colunas_mercado_gate.py` — criar (arquivo novo de testes unitários).
- `/repo/docs/modelo_mercado_hexagonos.md` — atualizar seção 5.4.
- `/repo/tasks/current_task.md`, `/repo/tasks/backlog.md`, `/repo/tasks/completed.md` — fechamento do ciclo (apenas no passo de fechamento pós-QA).
- `/repo/context/handoff.md`, `/repo/context/handoff/` — snapshots de handoff.

## Critérios de aceite
- `flag_gate_atratividade` existe no dataframe após `calcular()`: tipo bool, sem NaN, domínio `{True, False}`.
- Lógica verificável: `(flag_gate_atratividade == True)` ↔ `populacao_corte_hex >= 5000 AND renda_per_capita >= 1500`.
- Constante `RENDA_PER_CAPITA_MIN_ATR = 1_500` declarada em `calcular_colunas_mercado.py` e em nenhum outro arquivo.
- `flag_viavel`, `RENDA_MIN`, `renda_target_proxy`, `pipelines/m1/` **inalterados** (grep + `loop_guard` confirmam).
- mtime dos 4 artefatos M1 oficiais inalterado.
- Testes unitários verdes: mínimo dos 6 casos listados no escopo.
- `pytest -q` (suíte completa) verde sem regressão.
- `import streamlit_app` ok sem erro.
- `loop_guard.py` não acusa toque em path proibido.
- `validar()` imprime contagem de hexes aprovados pelo gate e distribuição por UF.

## Criticidade classificada
Alta

## Esteira recomendada
Block Orchestrator (concluído) → **Planner** → Builder → QA

## Riscos identificados
- **`renda_per_capita` pode ser 0.0** para hexes sem dado IBGE (`hex_enrichment` preenche com 0 quando ausente). Gate resulta `False` nesses hexes — comportamento correto e conservador; sem risco de regressão.
- **`flag_gate_atratividade` não deve substituir `flag_sam`** nas classificações executivas de `tese_entrada`/`prioridade_mercado_mapeado`. O Builder deve confirmar que a nova flag é coluna paralela apenas, sem alterar o `np.select` da seção 5.7.
- **Constante fora de `config.py`**: o `loop_guard` aborta se `config.py` for tocado. A constante `RENDA_PER_CAPITA_MIN_ATR` deve ficar exclusivamente em `calcular_colunas_mercado.py`.
- **Limiar calibrável depois**: o valor 1.500 é ponto de partida (decisão Felipe 2026-07-06). Não duplicar em mais de um lugar.

## Guardrails ativos
- §5 READ-ONLY M1: zero recálculo de `score_priorizacao`, `hex_score_estrutural`, carteira, plano, artefatos oficiais; mtime dos 4 oficiais inalterado.
- `flag_viavel`/`RENDA_MIN`/`renda_target_proxy`/`pipelines/m1/` INTOCADOS.
- Constante do gate na camada paralela (`calcular_colunas_mercado.py`), NÃO em `config.py` (loop_guard abortaria).
- DEC-001 intacta: pisos do funil de atratividade ≠ pesos do M1 (`renda=0.40`/`pop=0.60`).
- DEC-007 intacta: gate `flag_sam` (faixa M1 elegível AND pop ≥ 5.000) não é alterado.
- loop-safe confirmado no backlog: READ-ONLY M1, sem VPS/deploy/segredos, flag nova só na camada paralela.
