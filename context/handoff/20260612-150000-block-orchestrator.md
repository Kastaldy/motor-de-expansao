# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-UI-02 — Follow-up UX do dashboard: destaque do campo de coordenada, tooltip cortado e densificação por filtro de município

## Objetivo
Corrigir três pontos de UX no Mapa Territorial sem tocar em score, pesos ou artefatos M1: (1) destacar visualmente o campo de busca por coordenada na sidebar; (2) reduzir o corte do tooltip na borda inferior do mapa via CSS de fonte/padding; (3) comunicar e facilitar o filtro de município como mecanismo de densificação (decisão de produto já fixada por Felipe/Vini em 2026-06-12).

## Escopo permitido
- `src/motor_expansao/dashboard/pages.py` — destaque visual de `render_coord_search_sidebar` (linhas 523-541)
- `src/motor_expansao/dashboard/components.py` — redução de fonte/padding no `style` dos tooltips `_shared_map_tooltip` (linhas 1047-1073) e `_hybrid_compact_tooltip` (linhas 1083-1104); eventual ajuste de `maxWidth`/`fontSize` no dict `style`
- `src/motor_expansao/dashboard/components.py` — ajuste do texto em `build_map_scope_caption` (linhas 383-400) para reforçar que filtrar por município densifica o mapa
- `src/motor_expansao/dashboard/pages.py` — eventual dica/caption na UI do Mapa Territorial orientando o usuário a usar o filtro de município para obter densidade total
- Testes correspondentes em `tests/integration/test_streamlit_app.py`

## Fora de escopo
- Recalcular qualquer score (`score_priorizacao`, `score_setor_2022_calibrado`, residual, SAM) ou artefatos M1
- Remover ou elevar o cap `MAP_POINT_LIMIT`/`MAP_POINT_LIMIT_LARGE` sem o mecanismo de escopo
- Introduzir evento de zoom-awareness (pydeck/Streamlit não suporta; decisão de produto pré-fixada não inclui isso)
- Reabertura da decisão de produto nº3: a abordagem aprovada é exclusivamente filtro de município/área
- Modificar `render_sidebar_filters`, `apply_global_filters`, lógica de carga lazy (Bloco 4), render lazy de abas (Bloco 5)
- Quebrar guardrail Bloco 6 anti-OOM: nenhuma mudança pode elevar o payload global ao cliente acima dos caps existentes
- Tocar em PRD.md, artefatos de staging/outputs ou pipelines M1

## Arquivos que devem ser lidos
- `src/motor_expansao/dashboard/pages.py` (focar linhas 453-541 sidebar/coord e 2704-2940 render_mapa_territorial)
- `src/motor_expansao/dashboard/components.py` (focar linhas 366-400 resolve_map_view/scope_caption, 1047-1104 tooltips, 1309-1332 _downsample_map_index, 1396-1580 build_map_figure, 1650-1800 build_hybrid_map_figure, 3008-3105 build_unified_map_figure)
- `src/motor_expansao/dashboard/constants.py` (linhas 98-119 caps)
- `streamlit_app.py` (linhas 460-563 — fluxo principal: render_sidebar_filters → render_coord_search_sidebar → render_mapa_territorial)
- `tests/integration/test_streamlit_app.py` (buscar por `render_coord_search_sidebar`, `_shared_map_tooltip`, `_hybrid_compact_tooltip`, `MAP_POINT_LIMIT`, `_downsample_map_index`)

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/pages.py`
- `src/motor_expansao/dashboard/components.py`
- `tests/integration/test_streamlit_app.py`

## Âncoras confirmadas no código (file:line real)

### #1 — Campo de coordenada camuflado
- Função: `render_coord_search_sidebar` em `pages.py:523-541`
- Chamada: `streamlit_app.py:470` — chamada ÚNICA, SEMPRE presente (independente da aba ativa), logo após `render_sidebar_filters`
- Situação atual: separador `---` + heading `### Busca por coordenada` + `st.sidebar.caption` + `st.sidebar.text_input` — sem destaque visual além do heading markdown
- Fix proposto: adicionar `st.sidebar.info(...)` ou `st.sidebar.success(...)` container leve, ou mudar o heading/caption para tornar a seção mais visível — decisão de estilo para o Planner detalhar

### #2 — Tooltip cortado na borda inferior
- `_shared_map_tooltip()`: `components.py:1047-1073` — 14 linhas (`tooltip_title` + `tooltip_line_1..14`); usado por `build_map_figure` (modo M1), `build_residual_heatmap_figure`, e como fallback nos outros modos
- `_hybrid_compact_tooltip()`: `components.py:1083-1104` — 8 linhas (`tooltip_title` + `tooltip_line_1..8`); usado quando `_HYBRID_TOOLTIP_SHOW_DETAIL = False` (default), pelos modos híbrido e censitário
- Estilo atual (`style` dict, ambos): `backgroundColor`, `color`, `border`, `borderRadius`, `fontFamily` — SEM `fontSize`, `padding` nem `maxWidth`
- Limitação nativa pydeck/deck.gl: o tooltip é renderizado dentro do iframe no cursor e recortado pela borda — "des-recorte" total não é nativo; a mitigação real é reduzir a altura total do tooltip
- Fix proposto: adicionar `"fontSize": "11px"`, `"padding": "6px 8px"`, `"maxWidth": "260px"` (ou similar) ao dict `style`; para `_shared_map_tooltip` (14 linhas), avaliar também enxugar linhas vazias/redundantes do HTML (`{tooltip_line_X}` sem conteúdo renderiza como `<br/>` vazio — o Planner deve verificar `_apply_hex_tooltip_fields` para identificar quais linhas tipicamente ficam vazias no recorte)

### #3 — Compactação do mapa em zoom próximo (DECISÃO DE PRODUTO PRÉ-FIXADA)
- DECISÃO PRÉ-FIXADA (Felipe/Vini, 2026-06-12): abordagem = filtro de município/área. NÃO reabertura.
- Situação atual: `selected_cities` já é aplicado via `scope` ANTES do `_downsample_map_index` em TODOS os builders (`build_map_figure` linha ~1418-1427, `build_hybrid_map_figure` linha ~1678-1681, e os demais). Portanto, ao selecionar um município no filtro da sidebar, o cap de 35k/18k já cobre APENAS os hexes daquele município — a densificação já é NATIVA no código.
- O que falta: a UX não comunica isso proativamente. O texto de `build_map_scope_caption` (components.py:383-400) já diz "Aplique filtros de municipio para ver o recorte completo" apenas quando `capped=True`. A dica não aparece quando o usuário está em escopo amplo e se questiona sobre a compactação.
- Fix proposto: (a) `build_map_scope_caption` — reforçar ou tornar a dica de município mais proativa/visível mesmo sem `capped`; (b) no `render_mapa_territorial` (pages.py) — caption ou dica explicativa junto ao seletor de modo; decisão de estilo para o Planner detalhar
- Guardrail Bloco 6 ATIVO: qualquer mudança no cap ou no downsample que eleve o payload global é BLOQUEADA; a densificação só é válida dentro do recorte de município (escopo estreito), que naturalmente tem < 35k hexes na maioria dos casos

## Critérios de aceite
- #1: Campo "Busca por coordenada" na sidebar tem destaque visual claramente diferenciado dos demais filtros (ex.: bordas, cor de container, ícone, ou heading mais proeminente)
- #2: Tooltip de 14 linhas (modo M1/residual) e de 8 linhas (modo híbrido/censitário) têm fonte/padding reduzidos; o tooltip cabe na tela sem recorte em monitor padrão (1080p) ao hover próximo da borda inferior
- #3: A UX comunica proativamente que selecionar município entrega densidade total do mapa; nenhum cap foi alterado; nenhum OOM introduzido
- Suite pytest completa passa (baseline: 695 passed, 1 skipped, 3 failures pré-existentes conhecidas — ver handoff QA do BLK-UI-01); ruff+mypy limpos
- READ-ONLY sobre M1: `score_priorizacao`, `hex_score_estrutural`, carteira, plano, artefatos oficiais INALTERADOS

## Criticidade classificada
Alta

Justificativa: toca contratos de performance do Bloco 6 anti-OOM e a navegação do dashboard de produção; READ-ONLY sobre o M1; esteira Alta exige revisão humana do plano do Planner antes do Builder.

## Esteira recomendada
Block Orchestrator (concluído) → Planner (opus) → [REVISÃO HUMANA do plano] → Builder (opus) → QA (opus 4.8)

## Riscos identificados
- **Risco #2 tooltip font-size**: reduzir `fontSize` pode cortar texto dos valores se a fonte ficar pequena demais; o Planner deve propor um valor de font-size que equilibre legibilidade e altura total
- **Risco #2 linhas vazias**: `_shared_map_tooltip` renderiza 14 `<br/>` mesmo quando linhas estão vazias; enxugar o HTML (remover linhas sistematicamente vazias) pode ser mais eficaz que só CSS, mas requer inspecionar `_apply_hex_tooltip_fields` (components.py) para cada modo — escopo restrito ao dict `style` é mais seguro como primeira abordagem
- **Risco #3 payload**: se o Planner propuser qualquer mudança em `_downsample_map_index`, `MAP_POINT_LIMIT`, `MAP_POINT_LIMIT_LARGE` ou no scope dos builders, o QA deve verificar explicitamente que o cap global não foi elevado
- **Risco de regressão de testes**: há testes que verificam exatamente `MAP_POINT_LIMIT_LARGE` como `n` retornado pelos builders em UF grande; qualquer mudança no cap exige atualização desses testes E justificativa de por que não é OOM
- **Risco #1 sidebar**: a sidebar já tem vários separadores `---`; adicionar destaque excessivo pode criar ruído visual; o Planner deve propor uma solução mínima e focada

## Guardrails ativos
- **Bloco 6 anti-OOM (ativo)**: `MAP_POINT_LIMIT=35000` / `MAP_POINT_LIMIT_LARGE=18000` são guardrais de performance client-side (JS heap/WebGL). A densificação do nº3 SÓ pode valer dentro de recorte de município (escopo estreito). NÃO remover o cap. NÃO elevar o payload global.
- **Bloco 4 carga lazy por UF**: o `df` passado aos builders já é a partição `uf=XX`; nenhuma mudança pode forçar carga de UFs adicionais
- **Bloco 5 render lazy de abas**: `render_coord_search_sidebar` é chamada SEMPRE (fora do branch de aba); qualquer refatoração deve preservar esse comportamento
- **READ-ONLY sobre M1**: visualizações, CSS de tooltip e dicas de UX não recalculam nem alteram `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano domínio ou artefatos oficiais do M1
- **Decisão de produto nº3 pré-fixada**: NÃO propor zoom-awareness, NÃO remover o cap; a abordagem é exclusivamente filtro de município/área já nativo no código

## Observação para o Planner
O mecanismo de densificação do #3 já existe no código: `selected_cities` é aplicado no `scope` de todos os builders antes do `_downsample_map_index`. A tarefa real do #3 é COMUNICAR isso ao usuário (UX/dica), não reimplementar lógica. O Planner deve confirmar se basta melhorar `build_map_scope_caption` + um caption no render, ou se é necessário algum sinal adicional na UI.

## Paths pré-sujos (NÃO tocar — alheios ao ciclo)
- data/outputs/setores_censitarios_2022_geo/_metadata.json
- data/reports/relatorio_pontual_censitario_base_geo.md
