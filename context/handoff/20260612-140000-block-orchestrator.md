# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-UI-01 (recorte focado): Sidebar mais aparente + indicadores de carregamento + limpeza de poluição visual

## Objetivo
Melhorar a percepção e usabilidade do dashboard em três pontos pontuais de UX sem alterar score, pesos, artefatos M1 ou os contratos de performance (carga lazy por UF, render lazy de abas, fonte de mapa enxuta).

## Escopo permitido

### Melhoria 1 — Sidebar mais aparente
- Mudar `initial_sidebar_state="collapsed"` para `"expanded"` em `streamlit_app.py:180`.
- Reforçar visualmente o bloco de sidebar com CSS adicional em `inject_styles()` (`pages.py`): borda lateral mais destacada e/ou indicador de "filtros ativos" no cabeçalho da sidebar.
- Adicionar um título/label mais visível no topo da sidebar antes de `render_uf_selectbox`. Atualmente o primeiro elemento é `"### Filtros globais"` — pode virar um bloco com identidade visual mais forte.
- O seletor de UF (`render_uf_selectbox` em `pages.py:382`) é o gate da carga lazy: qualquer mudança deve manter o selectbox como PRIMEIRO elemento da sidebar (a carga lazy depende deste valor ser capturado antes de `load_uf_slice`).

### Melhoria 2 — Indicadores de carregamento
- Envolver `load_uf_slice(selected_uf)` em `streamlit_app.py:442` com `st.spinner("Carregando dados da UF...")` para feedback imediato quando o usuário seleciona uma nova UF (ponto de maior latência: lê Parquet particionado ou funde o Brasil inteiro como fallback).
- Envolver `build_unified_map_figure(...)` em `pages.py:2800` (dentro de `render_mapa_territorial`) com `st.spinner("Construindo mapa...")`, pois é o builder mais pesado (downsampling + cap de 35k pontos).
- Envolver `render_mapas_censitarios_combinados(...)` em `pages.py:2550` com `st.spinner("Gerando mapas censitários...")`, pois inclui fetch de tiles online (DEC-004) e composição de imagens.
- Spinners são puramente decorativos — não alteram o fluxo de dados. O padrão `with st.spinner("..."):` é seguro e não quebra cache nem carga lazy.

### Melhoria 3 — Limpeza de poluição visual
Candidatos identificados no código (o Planner deve validar e priorizar cada um):

- **`streamlit_app.py:485-493`** — dois `st.caption()` seguidos com mensagem técnica sobre proveniência ("Base oficial preservada: `data/outputs/...`"). Mover para expander colapsado "Sobre os dados" ou remover se o rodapé do manifesto (`render_manifest_footer`) já cobre.
- **`pages.py:363-379` (`render_header()`)** — as pills com nomes internos (`score_priorizacao`, `score_setor_2022_calibrado`, `score_expansao_hibrido`, "UFs censo: DF GO MG RJ RS SP") são informações técnicas que poluem a visão executiva. Simplificar para 2-3 pills com linguagem de usuário ou mover as pills técnicas para um tooltip/expander.
- **`pages.py:2026-2030`** — caption explicando limitações do `st.pydeck_chart` ("Botão direito: não suportado...") aparece no estado vazio da Análise Pontual antes de qualquer interação. Remover ou mover para expander "Dica de uso".
- **`pages.py:1028-1033`** — dois `st.caption()` repetitivos em `render_modelo_hibrido_v2` repetem orientações já presentes nos cards de modelo. Avaliar remoção ou consolidação em um único caption curto.
- Legendas de scores (ex.: `render_geographic_source_legend` em modo M1) podem ser escondidas atrás de expander "Legenda" para reduzir área visual fixa — a avaliar pelo Planner com base em impacto real na usabilidade.

## Fora de escopo

- Refatoração completa das 4 abas (BLK-UI-01 amplo).
- Qualquer alteração em `score_priorizacao`, `hex_score_estrutural`, `score_setor_2022_calibrado`, `score_expansao_hibrido`, `score_oportunidade_residual` ou artefatos oficiais do M1.
- Alterar os builders de mapa (`build_unified_map_figure`, `build_map_figure`, `build_hybrid_map_figure`, etc.) além de envolvê-los com spinner.
- Alterar `render_tab_selector` / `st.segmented_control` (render lazy de abas — Bloco 5).
- Alterar `load_uf_slice`, `read_enriched_uf_partition`, `load_uf_catalog` (carga lazy por UF — Bloco 4).
- Alterar `_downsample_map_index` ou `MAP_SOURCE_COLUMNS_M1`/`MAP_SOURCE_COLUMNS_HYBRID` (fonte de mapa enxuta — Bloco 6).
- Alterar qualquer lógica de score, pesos, carteira, plano ou SAM.
- Criar novas abas ou reorganizar a estrutura de 4 abas.
- Introduzir dependências de API ao vivo no dashboard de produção.

## Arquivos que devem ser lidos

- `streamlit_app.py` — entry point, `set_page_config` (linha 177), `main()` (linha 423), loaders cacheados (`load_uf_slice` linha 317, `build_dashboard_dataset` linha 288)
- `src/motor_expansao/dashboard/pages.py` — `inject_styles()` (linha 129), `render_header()` (linha 363), `render_uf_selectbox()` (linha 382), `render_sidebar_filters()` (linha 433), `render_tab_selector()` (linha 406), `render_mapa_territorial()` (linha 2691), `render_mapa_pydeck_fragment()` (linha 2630), `render_relatorio_pontual_censitario()` (linha 2490), `render_analise_pontual()` (linha 1992), `render_modelo_hibrido_v2()` (linha 956)
- `src/motor_expansao/dashboard/constants.py` — `COLORS` (linha 270), `FAIXA_COLORS` (linha 288)
- `src/motor_expansao/dashboard/components.py` — `render_manifest_footer()`, legendas (`render_geographic_source_legend`, `render_pop_cut_legend`, etc.)

## Arquivos que podem ser alterados

- `streamlit_app.py` — `set_page_config` (`initial_sidebar_state`), wrapper `st.spinner` ao redor de `load_uf_slice`
- `src/motor_expansao/dashboard/pages.py` — `inject_styles()` (CSS sidebar), `render_header()` (pills), `render_uf_selectbox()` (label sidebar), `render_mapa_territorial()` (spinner no builder de mapa), `render_relatorio_pontual_censitario()` (spinner nos mapas censitários), captions de poluição visual
- `src/motor_expansao/dashboard/constants.py` — apenas se precisar de nova constante de cor/estilo para a sidebar (baixo risco, opcional)
- `tests/integration/test_streamlit_app.py` — cobrir mudanças de UX (smoke import deve seguir verde)

## Critérios de aceite

- Sidebar aparece expandida no primeiro carregamento (`initial_sidebar_state="expanded"`) e o seletor de UF continua sendo o primeiro elemento da sidebar.
- Spinner visível ao trocar de UF (ponto `load_uf_slice` em `streamlit_app.py:442`) e ao construir o mapa no Mapa Territorial (`build_unified_map_figure` em `pages.py:2800`).
- Os dois captions técnicos de proveniência na área principal (`streamlit_app.py:485-493`) removidos ou movidos para expander colapsado.
- Pelo menos um item de poluição visual do header (`render_header` pills técnicas) simplificado.
- Suíte de testes verde sem regressão (`pytest -q`, baseline 532 passed).
- Smoke import: `python -c "import streamlit_app"` sem erro.
- Ruff e mypy limpos.
- Carga lazy por UF (Bloco 4), render lazy de abas (Bloco 5) e fonte de mapa enxuta (Bloco 6) sem regressão de comportamento.
- M1: `score_priorizacao`, pesos, artefatos oficiais, carteira, plano intocados.

## Criticidade classificada
Alta

## Esteira recomendada
Block Orchestrator → Planner → [REVISÃO HUMANA do plano] → Builder → QA

## Riscos identificados

- **Sidebar expandida por padrão**: em telas pequenas pode consumir espaço horizontal e ocultar conteúdo principal. O Planner deve decidir se aplica media query CSS ou mantém expandida globalmente.
- **Spinner ao redor de `load_uf_slice`**: `@st.cache_resource` entrega da cache quente em milissegundos — spinner aparece só na primeira carga por UF (comportamento correto). Verificar que o wrapper `with st.spinner(...)` não afeta o bloco `try/except (FileNotFoundError, ValueError)` no `main()` — o spinner deve ficar DENTRO do try.
- **Spinner em `build_unified_map_figure`**: builder está dentro de `render_mapa_territorial`, chamado no branch `if active_tab == "Mapa Territorial"` — render lazy de abas (Bloco 5) preservado. Spinner é interno ao render, sem efeito no `render_tab_selector`.
- **Remoção de captions técnicos**: alguns captions de "não altera M1" têm função de rastreabilidade para Felipe/Vini. NÃO remover os captions de `render_mapa_pydeck_fragment` e `render_analise_pontual` que mencionam centroide H3 — são guardrails visuais de produto. Remover apenas os que repetem proveniência técnica já coberta pelo rodapé do manifesto.
- **CSS da sidebar**: o seletor `[data-testid="stSidebar"]` já tem background gradient e `border-right` em `inject_styles()`. Qualquer CSS adicional deve ser testado em Streamlit 1.26+ (versão mínima do projeto). Evitar `!important` desnecessário; preferir especificidade por `data-testid`.

## Guardrails ativos

- §5 CLAUDE.md: visualizações, análise radial e interações de mapa NÃO podem recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano domínio ou artefatos oficiais do M1 sem aprovação explícita.
- §2 CLAUDE.md: não criar dependência de API ao vivo no dashboard de produção.
- Preservar carga lazy por UF (Bloco 4), render lazy de abas (Bloco 5) e fonte de mapa enxuta (Bloco 6) — sem regressão de performance.
- Toda mudança relevante entra com teste; nenhum PR deve subir com CI quebrado.
- O seletor de UF (`render_uf_selectbox`) deve continuar sendo o primeiro elemento renderizado na sidebar — a carga lazy depende deste valor.
