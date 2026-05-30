# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-FIX-02 — Corrigir `MessageSizeError` para UFs grandes.

O dashboard Streamlit lança `MessageSizeError` ao renderizar UFs grandes (relato ~240 MB)
porque algum payload enviado ao frontend excede o limite default do Streamlit
(`server.maxMessageSize` = 200 MB). O bloco tem duas frentes: (a) elevar o limite no
`.streamlit/config.toml` para 500 MB; (b) reduzir o tamanho do payload do caminho que estoura,
sem recalcular score nem alterar artefatos M1.

A investigação read-only do Block Orchestrator estreitou a suspeita: o caminho do **mapa
unificado** (pydeck `H3HexagonLayer`) é o candidato dominante. Embora já exista cap de 35k pontos
(`MAP_POINT_LIMIT`), o `map_df` passado a `pdk.Layer(data=map_df)` carrega TODAS as colunas
(fonte + colunas auxiliares `_fmt`/`_label`/`tooltip_residual_*` + 14 `tooltip_line_*` +
`tooltip_title` + `fill_color`/`line_color`). O pydeck serializa o DataFrame inteiro como JSON
dentro da spec do deck — ou seja, ~35k linhas × ~50+ colunas (muitas de texto verboso) viram um
JSON gigante. Esse é o vetor mais provável dos ~240 MB. As tabelas `st.dataframe` já estão
capeadas (`TABLE_ROW_LIMIT=1000`) ou são agregadas (top por UF / carteira), então NÃO são o
suspeito primário.

## Objetivo
Eliminar o `MessageSizeError` em UFs grandes elevando `maxMessageSize` para 500 MB e enxugando o
payload do caminho que estoura (mapa pydeck), sem tocar score/carteira/plano/artefatos M1.

## Escopo permitido
- Adicionar `maxMessageSize = 500` ao bloco `[server]` de `.streamlit/config.toml`.
- Reduzir o tamanho do payload enviado ao `pdk.Layer`/`pdk.Deck` no caminho que estoura:
  materializar para o pydeck SOMENTE as colunas que o layer/tooltip realmente consome
  (`hex_id`, `fill_color`, `line_color`, `tooltip_title`, `tooltip_line_1..14` e posição), e
  DESCARTAR as colunas auxiliares (`*_fmt`, `*_label`, `tooltip_residual_*`, e as colunas-fonte
  não usadas pelo deck.gl) antes de instanciar a `Layer`. Aplica-se aos builders M1 e Híbrido
  (`build_map_figure`, `build_hybrid_map_figure`) e, se necessário, ao builder residual/domínio.
- Adicionar teste que documente/garanta o enxugamento (ex.: o DataFrame passado ao layer não
  contém colunas auxiliares ou tem ≤ N colunas) e/ou que o cap de 35k segue aplicado.
- Atualizar `tasks/current_task.md`, `tasks/backlog.md`, `tasks/completed.md` e handoff.

## Fora de escopo
- Recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, `score_expansao_hibrido`,
  carteira, plano curto prazo, plano de domínio ou qualquer artefato oficial do M1.
- Alterar o cap `MAP_POINT_LIMIT` (35k) ou a chave de ordenação/dedup do downsample — o cap atual
  deve permanecer idêntico (mesmos top-N por prioridade).
- Alterar o conteúdo dos tooltips visíveis ao usuário (a UX de tooltip deve ser preservada;
  apenas remover do payload colunas que não alimentam o tooltip nem o render).
- Mexer em pipelines M1, geometria censitária, ou geração de Parquets.
- Resolver outros blocos do backlog.
- Commitar `CLAUDE.md` (worktree pré-sujo) ou `PROMPT-portar-run-cycle.md`. Commit só por path.

## Arquivos que devem ser lidos
- `.streamlit/config.toml` — bloco `[server]` (hoje SEM `maxMessageSize`; default 200 MB).
- `src/motor_expansao/dashboard/components.py` — builders de mapa:
  - `build_map_figure` (linha ~986): monta `map_df`, aplica `_prepare_m1_tooltip_fields` +
    `_apply_hex_tooltip_fields` e passa `data=map_df` ao `H3HexagonLayer` (linha ~1092-1106) sem
    enxugar colunas.
  - `build_hybrid_map_figure` (linha ~1242) — mesmo padrão.
  - `_downsample_map_index` (linha ~960) — cap de 35k (NÃO alterar a lógica de cap).
  - `_apply_hex_tooltip_fields` (linha ~433) — cria `tooltip_line_*` a partir de muitas colunas
    auxiliares `_fmt`/`_label` que permanecem no DataFrame.
  - `_apply_residual_tooltip_fields` / `_prepare_m1_tooltip_fields` — criam mais colunas auxiliares.
- `src/motor_expansao/dashboard/constants.py` — `MAP_POINT_LIMIT=35000` (98), `TABLE_ROW_LIMIT=1000`
  (99), `MAP_SOURCE_COLUMNS_M1` (184), `MAP_SOURCE_COLUMNS_HYBRID` (216), `MAP_SORT_COLUMNS` (178).
- `src/motor_expansao/dashboard/pages.py` — onde os mapas são renderizados: `st.pydeck_chart`
  (604, 832, 1025, 1120, 1472, 1876, 2066, 2541) e `render_mapa_pydeck_fragment` (~2520).
- `tests/integration/test_streamlit_app.py` — testes de import/render do app (sem assert de tamanho
  de payload hoje); base para adicionar o novo teste.

## Arquivos que podem ser alterados
- `.streamlit/config.toml`
- `src/motor_expansao/dashboard/components.py` (e, só se o caminho exigir, `pages.py`/`constants.py`)
- `tests/` (novo teste documentando o enxugamento / cap aplicado)
- `tasks/current_task.md` · `tasks/backlog.md` · `tasks/completed.md`
- `context/handoff.md` · `context/handoff/`
- (Parquets em `data/outputs/` são gerados — NÃO versionar.)

## Critérios de aceite
- `.streamlit/config.toml` define `maxMessageSize = 500` dentro do bloco `[server]` existente.
- O DataFrame efetivamente passado ao `pdk.Layer`/`H3HexagonLayer` contém apenas as colunas
  consumidas pelo render e pelo tooltip (sem colunas auxiliares `*_fmt`/`*_label`/`tooltip_residual_*`
  nem colunas-fonte não usadas), comprovado por teste.
- Cap `MAP_POINT_LIMIT` (35k) permanece inalterado; mesma chave de ordenação/dedup.
- Tooltips visíveis ao usuário permanecem com o mesmo conteúdo.
- `pytest -q` verde (baseline atual: 532 passed, 1 skipped); app importa e renderiza ok.
- Nenhum valor de score, carteira, plano ou artefato M1 alterado.

## Criticidade classificada
**Média.** Justificativa: o bloco é de transporte/render (limite de mensagem + enxugamento de
payload do mapa). NÃO toca fórmula, pesos, score, carteira, plano de domínio nem artefatos oficiais
do M1 — está coberto pelo guardrail §5 (visualizações não recalculam score). Bloqueia usabilidade de
UFs grandes em produção, mas não tem risco sobre o núcleo oficial. Esteira sem gate humano:
Block Orchestrator → Planner → Builder → QA.
(Alerta de §2/§5: se o Builder, ao enxugar colunas, precisar tocar QUALQUER coluna de score ou
recalcular algo, escalar para CRÍTICA e parar — isso sairia do escopo deste bloco.)

## Esteira recomendada
Planner → Builder → QA.

## Riscos identificados
- Apenas elevar `maxMessageSize` para 500 MB "mascara" o problema sem reduzir o payload: o app fica
  lento e ainda pode estourar em UFs maiores. Tratar (a) e (b) juntos — o enxugamento é o fix real.
- Ao remover colunas antes do `pdk.Layer`, quebrar inadvertidamente o tooltip ou o
  `get_fill_color`/`get_line_color` (que referenciam colunas por nome). Manter exatamente as colunas
  consumidas: `hex_id`, `fill_color`, `line_color`, `tooltip_title`, `tooltip_line_1..14` (e
  lat/lng se algum layer usar).
- A busca por hex fora do recorte (`search_hex_id`/`search_tooltip_source`) e os layers de
  competidores/Ultra também passam DataFrames — verificar que o enxugamento não os afeta.
- Múltiplos `st.pydeck_chart` (8 ocorrências); confirmar qual é o caminho do mapa unificado de UF
  grande (`render_mapa_pydeck_fragment` / `main_unified_map`) para focar o fix sem regressão nos outros.
- Regressão de cap: não alterar `MAP_POINT_LIMIT` nem a ordenação/dedup do downsample.

## Guardrails ativos
- CLAUDE.md §5 (Guardrail permanente): "visualizacoes, analise radial e interacoes de mapa nao podem
  recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo,
  plano dominio ou artefatos oficiais do M1 sem aprovacao explicita."
- CLAUDE.md §5 (Performance/Fonte de mapa enxuta, Bloco 6): o cap e a chave de downsample atuais
  devem ser preservados (mesmos top-N por prioridade).
- CLAUDE.md §2: "Toda mudanca relevante entra com teste; nenhum PR deve subir com CI quebrado."
- Commit SÓ por path; NUNCA `git add -A`. `CLAUDE.md` (M) e `PROMPT-portar-run-cycle.md` (??) do
  worktree pré-sujo NÃO entram neste ciclo.

## Investigação (evidências coletadas)
- `.streamlit/config.toml`: bloco `[server]` existe (headless/address/port/fileWatcherType/
  enableXsrfProtection) mas NÃO tem `maxMessageSize` → default Streamlit 200 MB. Confirma o limite.
- Cap de mapa REAL e aplicado: `MAP_POINT_LIMIT = 35000` (constants.py:98); `_downsample_map_index`
  (components.py:960-983) ordena/dedup/`head(limit)` sobre projeção leve de chaves. Logo, o mapa
  NÃO envia centenas de milhares de pontos — o estouro NÃO é número de linhas.
- VETOR PRIMÁRIO (largura do payload, não altura): em `build_map_figure` (components.py:986-1135),
  após o cap o `map_df` recebe `_prepare_m1_tooltip_fields` + `_apply_hex_tooltip_fields(mode="m1")`
  (linhas 1064/1073), que criam `tooltip_title` + `tooltip_line_1..14` E MANTÊM todas as colunas
  auxiliares (`*_fmt`, `*_label`, `tooltip_residual_*`) e todas as `MAP_SOURCE_COLUMNS_M1` (~30).
  O `pdk.Layer("H3HexagonLayer", data=map_df, ...)` (1092-1106) usa só `hex_id`/`fill_color`/
  `line_color`, mas o pydeck serializa o DataFrame INTEIRO como JSON na spec → ~35k linhas × ~50+
  colunas de texto verboso ≈ payload na casa das centenas de MB. Compatível com o relato de ~240 MB.
- Mesmo padrão no Híbrido: `build_hybrid_map_figure` (components.py:1242+) com
  `MAP_SOURCE_COLUMNS_HYBRID` (~33 colunas, constants.py:216) + tooltips sem enxugamento.
- `_apply_hex_tooltip_fields` (components.py:433-486) evidencia o volume de colunas-texto derivadas
  (modo m1: 14 tooltip_line; híbrido: 8 ou 14 conforme `_HYBRID_TOOLTIP_SHOW_DETAIL`).
- Tabelas NÃO são o suspeito primário: `render_ranking_priorizacao` (pages.py:693-703) e as tabelas
  de carteira/plano usam `.head(TABLE_ROW_LIMIT=1000)` (pages.py:1354, 1521) ou já são agregadas
  (top por UF: 1295, 1669; top 50 + top 10/UF: 1716). Não enviam DataFrames brutos por UF.
- Não há teste atual cobrindo `MessageSizeError`/`maxMessageSize`/tamanho de payload de pydeck
  (grep sem matches em `tests/`).
- Conclusão para o Planner (não é causa-raiz definitiva, é foco): atacar (a) `maxMessageSize=500` +
  (b) materializar para o pydeck apenas as colunas consumidas, descartando auxiliares — começando
  por `build_map_figure`/`build_hybrid_map_figure`. Validar empiricamente o tamanho do payload
  antes/depois numa UF grande (ex.: AM/SP) se o ambiente permitir.
