# Handoff — QA / Quality Analyzer

## VEREDITO: APROVADO

Bloco: BLK-FIX-02 — Corrigir MessageSizeError para UFs grandes
Skill que gerou este handoff: QA / Quality Analyzer
Próxima Skill recomendada: Orquestrador (fechamento: housekeeping move byte-idêntico + commit por path + merge)

## Justificativa
A entrega do Builder cumpre integralmente o escopo do BLK-FIX-02 (fix de transporte/render,
sem tocar score/M1). Re-executei TODAS as validações obrigatórias por conta própria (sem
bypass) e todas passaram: 150 testes da suíte do dashboard, 570 passed / 1 skipped na suíte
completa (567 baseline + 3 testes novos, zero regressões), import do app ok, ruff limpo, mypy
limpo. Diff conferido linha a linha: o helper `_deck_layer_frame` apenas PROJETA colunas
(render + tooltip presentes), NÃO muta `map_df`, e é aplicado via `data=layer_df` nos 4
builders de `H3HexagonLayer` (M1/híbrido/residual/domínio). Nenhum path de
`pipelines/`, `core/`, `data/`, `constants.py` ou `pages.py` foi tocado. `MAP_POINT_LIMIT`,
`MAP_SORT_COLUMNS` e `_downsample_map_index` permanecem intactos. Os 3 asserts de regressão
ajustados preservam a INTENÇÃO original validando a consequência visível (line_color/fill_color)
em vez de mascarar com `assert True`. Os 3 testes novos exercitam os builders reais (NO-BYPASS).
Pré-condição de housekeeping confirmada (`--check` falha com `stub ausente`, não `BlockNotFound`).

## Problemas
### Críticos
- Nenhum.

### Médios
- Nenhum.

### Leves
- O helper foi aplicado também ao builder de **domínio** (`build_dominio_map_figure`), além
  dos 3 previstos explicitamente no plano (M1/híbrido/residual). Foi autorizado pelo passo 5
  do plano (após grep) e é consistente com o critério "payload do layer só com render+tooltip".
  Observação: NÃO há teste novo cobrindo especificamente o payload do builder de domínio
  (os 3 novos cobrem M1, híbrido e residual). Como o domínio usa o MESMO helper puro
  `_deck_layer_frame` já coberto pelos outros 3, o risco é baixo; registrado como leve, não
  bloqueia aprovação.

## Testes faltantes (não bloqueantes)
- Teste de payload enxuto específico para `build_dominio_map_figure` (cobertura indireta via
  helper compartilhado já existe). Opcional para ciclo futuro.

## Riscos
- Nenhum risco funcional. Tooltips e cores idênticos (mesmas `tooltip_line_*`, mesmos
  fill/line). O fix é seleção de colunas pré-serialização (puro, sem efeito colateral).
- `maxMessageSize = 500` apenas eleva o teto de transporte; o cap real de pontos do mapa
  continua sendo `MAP_POINT_LIMIT=35000` via downsample inalterado.

## Saída literal das validações (re-executadas pelo QA)

### python -m pytest -q tests/integration/test_streamlit_app.py
```
........................................................................ [ 48%]
........................................................................ [ 96%]
......                                                                   [100%]
150 passed in 14.22s
```

### python -m pytest -q  (suíte completa)
```
570 passed, 1 skipped, 9 warnings in 112.33s (0:01:52)
```

### python -c "import streamlit_app; print('import ok')"
```
(warnings de ScriptRunContext/cache em modo bare — esperados)
import ok
```

### python -m ruff check src/motor_expansao/dashboard/components.py tests/integration/test_streamlit_app.py
```
All checks passed!
```

### python -m mypy src/motor_expansao/dashboard/components.py
```
Success: no issues found in 1 source file
```

## Conferência de NO-BYPASS
- Os 3 testes novos (`test_build_map_figure_payload_do_layer_so_tem_colunas_de_render_e_tooltip`,
  `test_build_hybrid_map_figure_payload_do_layer_enxuto`,
  `test_build_residual_heatmap_figure_payload_do_layer_enxuto`) chamam os builders REAIS
  (`build_map_figure`/`build_hybrid_map_figure`/`build_residual_heatmap_figure`) e leem
  `pd.DataFrame(deck.layers[0].data)` — não são mocks vazios. Cada um assere: (a) `set(columns)`
  ⊆ keep-set `{hex_id, fill_color, line_color, tooltip_title, tooltip_line_1..14}`;
  (b) auxiliares/colunas-fonte AUSENTES; (c) render PRESENTES; (d) `tooltip_title` é string
  não vazia. Isso é teste de integração legítimo com fixtures in-memory — NÃO é bypass.
- Os 3 asserts de regressão ajustados NÃO foram trocados por `assert True`: validam a
  consequência visível (`confianca_geografica` ausente + line_color granular vs municipal
  âmbar `[245,158,11,220]`; `score_oportunidade_residual` ausente + fill_color por faixa).
  A intenção original (classificação granular×municipal; cor derivada do residual) é preservada.
- Tooltip preservado: `tooltip_title`/`tooltip_line_*` continuam no payload (derivação por
  `startswith("tooltip_line_")`), UX de tooltip intacta.

## Conferência cruzada com o handoff do Builder
- config.toml: `maxMessageSize = 500` no `[server]` — CONFIRMADO no diff.
- `_deck_layer_frame` + `_DECK_RENDER_COLUMNS`, dedup em loop explícito (mypy-safe) — CONFIRMADO.
- `data=map_df` → `data=layer_df` nos 4 builders — CONFIRMADO no diff (4 ocorrências).
- `map_df` não mutado (nenhum `map_df = ...`/`map_df[...] =` adicionado) — CONFIRMADO via grep.
- 2 regressões extras (linhas ~628 e ~1154) além da prevista (~493) — CONFIRMADO; tratadas
  sem reintroduzir coluna-fonte e preservando intenção.
- Contagens de teste (150 / 570 passed, 1 skipped) — REPRODUZIDAS de forma idêntica pelo QA.
- ruff/mypy limpos — REPRODUZIDOS.

## Guardrails verificados
- `score_priorizacao` / `hex_score_estrutural` NÃO alterados: SIM. Nenhuma coluna de score
  recalculada; o helper só seleciona (projeta) colunas. Nenhuma alteração em fórmula/pesos.
- Pesos canônicos 0.40/0.60, H3_RESOLUTION=7, DIST_MIN_ULTRA_KM=1.0, RENDA_MIN=4500.0 NÃO
  aparecem alterados (nenhum path de pipeline/core/config tocado).
- Artefatos M1 preservados: SIM (nenhum Parquet gerado/sobrescrito; nenhum path em
  `pipelines/`/`core/`/`data/`).
- `MAP_POINT_LIMIT` / `MAP_SORT_COLUMNS` / `_downsample_map_index` inalterados: SIM (grep).
- Dashboard offline mantido: SIM (nenhuma dependência de API ao vivo).
- Escopo NÃO excedido: o domínio entrou por consistência (autorizado no plano); fora isso o
  diff se restringe a config.toml + helper + swap de `data=` + testes.

## Housekeeping (Passo 6.0) — pré-condição
- `python scripts/housekeeping_move_block.py BLK-FIX-02 --check` → exit 1 com
  `FALHA --check: stub ausente no backlog para BLK-FIX-02` (ESPERADO antes do move; PROVA
  que o heading `### BLK-FIX-02` é localizável — NÃO é `BlockNotFound`).
- Heading `### BLK-FIX-02 — Corrigir MessageSizeError para UFs grandes` confirmado em
  `tasks/backlog.md:38`.
- `python -m pytest -q tests/unit/test_housekeeping_helper.py` → `10 passed in 0.09s` (verde).
- O move byte-idêntico é responsabilidade do ORQUESTRADOR no fechamento (QA não executa o move).

## Decisão recomendada
APROVADO. Seguir para o Orquestrador: executar housekeeping move (BLK-FIX-02, backlog → completed,
byte-idêntico), commitar por path (NUNCA `git add -A`; CLAUDE.md e PROMPT-portar-run-cycle.md
NÃO entram) e fazer merge de `ciclo/BLK-FIX-02` em `main`.
