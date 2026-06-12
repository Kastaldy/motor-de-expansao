# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-UI-03 — 4 ajustes finos de UX (reverter coord, tooltip meio-termo, preview menor [fecha BLK-FIX-10], destaque seletor de abas)

## Objetivo
Quatro ajustes READ-ONLY sobre o M1 no dashboard: reverter a alteração de sidebar do BLK-UI-02 no campo de coordenadas, calibrar o fontSize/espaçamento dos tooltips para um meio-termo legível, controlar a largura das pré-visualizações do Relatório Pontual Censitário na tela (fecha BLK-FIX-10), e reforçar o destaque visual do `st.segmented_control` via CSS puro.

## Itens detalhados

### Item 1 — Reverter campo de coordenadas (render_coord_search_sidebar)
**Arquivo:** `src/motor_expansao/dashboard/pages.py`
**Âncora:** `def render_coord_search_sidebar()` — linha 523.
**Estado atual (BLK-UI-02):** linhas 526-529 contêm `st.sidebar.info("**Busca por coordenada** — localize um hexagono pela coordenada. Offline, sem API externa.")`.
**O que reverter:** substituir o `st.sidebar.info(...)` de volta para o par anterior:
```python
st.sidebar.markdown("### Busca por coordenada")
st.sidebar.caption("...")
```
O texto exato do `st.sidebar.caption` não está no handoff do Builder do BLK-UI-02 (o Builder registrou apenas que "heading+caption foram substituídos por `st.sidebar.info`"). O Planner deve confirmar o texto original do caption via `git diff` ou `git show` antes do BLK-UI-02 — ou propor texto equivalente caso não seja recuperável (ex.: `"Localize um hexagono pela coordenada. Offline, sem API externa."`).
**O que preservar intacto:** `st.sidebar.markdown("---")` acima (linha 525); `st.sidebar.text_input(...)` (linha 530-534); `parse_coordinate_input`; `st.sidebar.error(...)`; assinatura `() -> tuple[float, float] | None`; chamada em `streamlit_app.py:470`. Bloco 5 intacto.

### Item 2 — Tooltip meio-termo (fontSize/padding/maxWidth/lineHeight)
**Arquivo:** `src/motor_expansao/dashboard/components.py`
**Âncoras:**
- `def _shared_map_tooltip()` — linha 1048; dict `style` nas linhas 1067-1077; chaves adicionadas pelo BLK-UI-02: linha 1073 `"fontSize": "11px"`, linha 1074 `"padding": "6px 8px"`, linha 1075 `"maxWidth": "260px"`, linha 1076 `"lineHeight": "1.25"`.
- `def _hybrid_compact_tooltip()` — linha 1088; dict `style` nas linhas 1102-1112; mesmas 4 chaves nas linhas 1108-1111.

**Estado anterior ao BLK-UI-02:** sem as 4 chaves (deck.gl usava default ~13-14px, sem padding/maxWidth/lineHeight explícitos).
**Estado atual (BLK-UI-02):** `fontSize=11px`, `padding=6px 8px`, `maxWidth=260px`, `lineHeight=1.25` — usuário achou 11px pequeno demais.
**Direção do ajuste (meio-termo):** aumentar `fontSize` para `"13px"` (valor sugerido; Planner confirma), afrouxar `padding` para `"8px 10px"`, manter ou ampliar `maxWidth` (ex. `"300px"`), manter `lineHeight` em `"1.35"`. NÃO remover as chaves; apenas ajustar valores. Aplicar de forma idêntica em AMBAS as funções para consistência.
**O que preservar:** chaves pré-existentes (`backgroundColor`, `color`, `border`, `borderRadius`, `fontFamily`) e todo o `html` de ambas as funções, INALTERADOS.

### Item 3 — [BLK-FIX-10] Preview menor do Relatório Pontual Censitário
**Arquivo:** `src/motor_expansao/dashboard/pages.py`
**Âncoras:** linhas 2596-2614 — 4 chamadas `st.image(mapas[...], caption="...", width="stretch")` dentro de `render_relatorio_pontual_censitario`.
**Estratégia de controle de largura:** substituir `width="stretch"` por `width=N` pixels (ex.: 700-800 px) ou envolver cada `st.image` em colunas Streamlit (`st.columns([col_img, col_spacer])`), de forma que o preview ocupe ~60-70% da largura da área de conteúdo em vez de 100%. O Planner decide entre largura fixa em px vs colunas; ambas são válidas. Opção recomendada: `width=720` (ou constante nomeada `_CENSUS_PREVIEW_WIDTH_PX = 720` em `pages.py` ou `constants.py`).
**O que NÃO tocar:**
- O PDF exportado (`gerar_pdf_relatorio_pontual_censitario` / `censo_report.py`) — intocável.
- `render_mapas_censitarios_combinados` em `censo_map.py` — intocável.
- Lógica de cálculo, intersecção, raio 1,5 km, `setor_censitario_intersecao_area_1p5km` — intocáveis.
- Qualquer artefato M1 ou score.

### Item 4 — Destaque do seletor de abas (SÓ CSS)
**Arquivo:** `src/motor_expansao/dashboard/pages.py`
**Âncora CSS:** `inject_styles()` — linha 129; regras do segmented control nas linhas 301-319:
```python
[data-testid="stSegmentedControl"] button { background; color; border }          # linha 301-307
[data-testid="stSegmentedControl"] button:hover { ... }                          # linha 308-312
[data-testid="stSegmentedControl"] button[aria-checked="true"] { ... }           # linha 313-319
```
**O que pode ser reforçado (exemplos; Planner decide exatos):**
- Aumentar `font-weight` dos botões (ex. `600` ou `700`) e `font-size` (ex. `0.95rem` ou `1rem`).
- Aumentar `padding` dos botões (ex. `0.5rem 1.1rem`).
- Reforçar o botão ativo (`aria-checked="true"`): `border-color` mais vivo (ex. `rgba(25,183,255,0.9)`), `box-shadow` sutil (ex. `0 0 8px rgba(25,183,255,0.35)`), `font-weight: 700`.
- Adicionar `border-radius` explícito (ex. `10px`) se não houver.
**Âncora lógica:** `def render_tab_selector(...)` — linha 426. Esta função é Bloco 5 (render lazy) e é **ABSOLUTAMENTE INTOCÁVEL** — zero alteração de lógica, `session_state`, `st.segmented_control`, `options`, `key`, `label_visibility`, `default`.
**Regra:** mudança é APENAS dentro do bloco `<style>` em `inject_styles()`, nas regras que já referenciam `stSegmentedControl`.

## Escopo permitido
- `src/motor_expansao/dashboard/pages.py` — itens 1, 3 e 4 (CSS em `inject_styles`)
- `src/motor_expansao/dashboard/components.py` — item 2
- `tests/integration/test_streamlit_app.py` — atualizar/adicionar testes de smoke para os 4 itens
- `src/motor_expansao/dashboard/constants.py` — APENAS se o Planner decidir extrair a constante de largura do preview (item 3) para lá

## Fora de escopo
- Qualquer recálculo de `score_priorizacao`, `hex_score_estrutural`, `score_setor_2022_calibrado`, `score_oportunidade_residual`, SAM ou qualquer artefato oficial do M1
- Lógica de render lazy de abas (Bloco 5) — `render_tab_selector`, `session_state`, `st.segmented_control` chamada — intocáveis
- PDF exportado do Relatório Pontual Censitário (`censo_report.py`, `gerar_pdf_relatorio_pontual_censitario`)
- `censo_map.py` e `render_mapas_censitarios_combinados` (geração das imagens)
- Bloco 4 (carga lazy por UF) e Bloco 6 (fonte de mapa enxuta) — intocáveis
- `MAP_POINT_LIMIT*`, `_downsample_map_index`, scope/cap dos builders — intocáveis
- Dependências de API ao vivo

## Arquivos que devem ser lidos (Planner/Builder)
- `src/motor_expansao/dashboard/pages.py` — `inject_styles` (linhas 129-361), `render_tab_selector` (linhas 426-450), `render_coord_search_sidebar` (linhas 523-543), `render_relatorio_pontual_censitario` (confirmar contexto ao redor das linhas 2596-2614)
- `src/motor_expansao/dashboard/components.py` — `_shared_map_tooltip` (linhas 1048-1078) e `_hybrid_compact_tooltip` (linhas 1088-1113)
- `context/handoff/20260612-150600-builder.md` — registro do que o BLK-UI-02 fez (especialmente o texto original do caption do item 1)
- `tests/integration/test_streamlit_app.py` — testes existentes de tooltip (`test_map_tooltips_tem_css_de_tamanho`) e caption

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/pages.py`
- `src/motor_expansao/dashboard/components.py`
- `tests/integration/test_streamlit_app.py`
- `src/motor_expansao/dashboard/constants.py` (opcional, só se extrair constante de largura)

## Critérios de aceite
1. **Item 1:** `render_coord_search_sidebar` não contém `st.sidebar.info`; contém `st.sidebar.markdown("### Busca por coordenada")` e `st.sidebar.caption(...)` com texto equivalente; `text_input`, `parse_coordinate_input`, `st.sidebar.error` e `st.sidebar.markdown("---")` acima intactos.
2. **Item 2:** `_shared_map_tooltip` e `_hybrid_compact_tooltip` têm `"fontSize"` entre `"12px"` e `"14px"` (valor aprovado pelo Planner); chaves `"padding"`, `"maxWidth"`, `"lineHeight"` presentes com valores ajustados; chaves pré-existentes inalteradas; teste `test_map_tooltips_tem_css_de_tamanho` atualizado para o novo valor.
3. **Item 3:** as 4 chamadas `st.image` em `render_relatorio_pontual_censitario` não usam `width="stretch"`; preview visivelmente menor na tela; PDF exportado intocado; sem alteração em `censo_map.py`/`censo_report.py`.
4. **Item 4:** regras CSS do `stSegmentedControl` em `inject_styles` com font-weight/font-size/padding/destaque ativo reforçados; `render_tab_selector` (linha 426-450) sem nenhuma alteração.
5. **Suíte de testes:** `pytest -q` sem novas falhas (baseline: `695 passed, 1 skipped, 3 failed pré-existentes`); ruff e mypy limpos nos arquivos tocados; `import streamlit_app` ok.
6. **M1 READ-ONLY:** zero alteração em score, pesos, fórmula ou artefatos oficiais.

## Criticidade classificada
Alta

## Esteira recomendada
Block Orchestrator → Planner → [REVISÃO HUMANA] → Builder → QA

## Riscos identificados
- **Item 1 (R1 — texto original do caption):** o handoff do Builder do BLK-UI-02 não registra o texto exato do `st.sidebar.caption` anterior. O Planner deve recuperar via `git log`/`git show` do commit anterior ao BLK-UI-02 ou propor texto equivalente semanticamente neutro. Risco baixo se o texto não for exato.
- **Item 2 (R2 — contrato de teste):** o teste `test_map_tooltips_tem_css_de_tamanho` criado no BLK-UI-02 assere o valor `"11px"`. O Builder DEVE atualizar esse teste para o novo valor aprovado pelo Planner; do contrário o teste falhará após a mudança.
- **Item 3 (R3 — width="stretch" é argumento posicional ou keyword):** confirmar que `st.image` aceita `width` como inteiro em px na versão Streamlit do projeto; testar `use_column_width` vs `width=int` (Streamlit ≥1.25 aceita `width` inteiro). Risco baixo, mas o Planner deve confirmar a API.
- **Item 4 (R4 — seletores CSS e versão do Streamlit):** `[data-testid="stSegmentedControl"]` pode variar entre versões do Streamlit; a presença das regras já no código indica que funcionam na versão atual. Risco baixo. Qualquer seletor novo introduzido deve ser verificado no tema dark do dashboard.
- **Item 4 (R5 — Bloco 5 intocável):** qualquer edição acidental na função `render_tab_selector` invalida o guardrail do Bloco 5. O Builder deve editar APENAS dentro do bloco `<style>` em `inject_styles()`.

## Guardrails ativos
- READ-ONLY sobre o M1: `score_priorizacao`, `hex_score_estrutural`, carteira, plano, artefatos oficiais INALTERADOS (CLAUDE.md §2, §3, §5).
- Guardrail permanente de visualização: "visualizações, análise radial e interações de mapa não podem recalcular ou alterar score_priorizacao... sem aprovação explícita" (CLAUDE.md §5).
- Bloco 5 render lazy (CLAUDE.md §4): `render_tab_selector`, `session_state`, `st.segmented_control` — intocáveis. Só CSS em `inject_styles`.
- Dashboard offline: nenhuma dependência de API ao vivo introduzida (CLAUDE.md §2).
- Nenhum PR sobe com CI quebrado (CLAUDE.md §2).
- Item 3 é READ-ONLY sobre PDF/geração de mapas: `censo_report.py`, `censo_map.py` intocáveis.

## Nota de fechamento de bloco secundário
Item nº3 = BLK-FIX-10 (Baixa — "Diminuir tamanho da pré-visualização dos estudos", ClickUp `86e1rteea`). No fechamento do ciclo BLK-UI-03, mover via `scripts/housekeeping_move_block.py`.
