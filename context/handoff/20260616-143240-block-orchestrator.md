# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner (criticidade Alta → gate humano após o Planner, antes do Builder)

## Bloco refinado
**BLK-UI-07 — Refinos de UX/UI do dashboard (2x2 do Relatório Censitário + filtros/busca na tela principal)**

Três mudanças concretas de layout/UX no dashboard de produção. READ-ONLY sobre o M1: zero alteração em score, pesos, artefatos ou contratos de performance (carga lazy por UF, render lazy de abas, fonte de mapa enxuta — Blocos 4-6).

## Objetivo
Reorganizar o layout do dashboard em três pontos precisos — arranjo 2x2 das 4 imagens do Relatório Pontual Censitário, migração dos filtros UF/município/faixa para o corpo principal, e migração da busca por coordenada para uma barra no corpo principal próxima ao seletor de abas — sem regressão funcional nem do M1.

## Escopo permitido

### F1 — Arranjo 2x2 das 4 imagens do Relatório Pontual Censitário
- Arquivo: `src/motor_expansao/dashboard/pages.py`
- Localização atual: função `render_relatorio_pontual_censitario`, linhas 2859-2878 — 4 chamadas `st.image(...)` sequenciais com `width=_CENSUS_PREVIEW_WIDTH_PX` (720 px cada).
- Mudança: substituir as 4 chamadas lineares por 2 pares em `st.columns(2)`, ajustando o `width` para caber em metade da largura disponível (ex.: `_CENSUS_PREVIEW_WIDTH_PX // 2` ou valor fixo menor). A constante `_CENSUS_PREVIEW_WIDTH_PX` (linha 113) pode ser ajustada ou um novo valor pode ser usado inline.
- Invariantes: `render_mapas_censitarios_combinados`, `censo_map.py`, `censo_report.py`, `censo_point.py` e o método de interseção/raio INTOCADOS. Apenas o layout de exibição das imagens muda.

### F2 — Migração de UF / município / faixa de oportunidade para o corpo principal
- Arquivos: `src/motor_expansao/dashboard/pages.py` + `streamlit_app.py`
- Estado atual:
  - `render_uf_selectbox` (pages.py linhas 431-465): renderiza o selectbox de UF em `st.sidebar.*`. É chamado em `streamlit_app.py` linha 458, antes de `load_uf_slice` (carga lazy). O retorno `selected_uf` é o gatilho do `st.stop()` (linha 460-462) que bloqueia a carga do Brasil inteiro quando nenhuma UF está selecionada.
  - `render_sidebar_filters` (pages.py linhas 511-575): renderiza os multiselects de Município e Faixa de oportunidade em `st.sidebar.*` (linhas 520-533), mais os filtros avançados num expander lateral (linhas 537-565). Chamado em `streamlit_app.py` linha 491.
- Mudança: trocar `st.sidebar.*` por `st.*` para UF, município e faixa de oportunidade (primeiros dois multiselects). Sugestão de layout: linha horizontal com `st.columns([1,2,2])` ou similar para UF (selectbox) + Município (multiselect) + Faixa (multiselect). Os filtros avançados (Elegibilidade híbrida, Cobertura censitária, Qualidade, checkboxes) podem permanecer num expander no corpo ou migrar também — o Planner decide.
- Invariantes: a lógica de `selected_uf → load_uf_slice → st.stop() se vazio` deve ser preservada integralmente (carga lazy Bloco 4). A assinatura de retorno de `render_sidebar_filters` (8 valores) não deve mudar. O comportamento de `apply_global_filters` não muda. Os filtros avançados colapsados no expander podem ficar onde estiverem desde que não quebrem o fluxo.

### F3 — Migração da busca por coordenada para barra no corpo principal
- Arquivos: `src/motor_expansao/dashboard/pages.py` + `streamlit_app.py`
- Estado atual:
  - `render_coord_search_sidebar` (pages.py linhas 582-600): renderiza `st.sidebar.markdown`, `st.sidebar.caption` e `st.sidebar.text_input` (key `"coord_search_input"`). Chamado em `streamlit_app.py` linha 493, após `render_sidebar_filters` e antes de `apply_global_filters`.
  - O resultado `search_pin` alimenta `render_hex_search_result` (corpo principal, `streamlit_app.py` linha 541) e `render_relatorio_pontual_censitario` (aba Mapa Territorial, `pages.py` linha 3470). Ambos já estão no corpo principal.
- Mudança: mover `text_input` (e label/caption associados) para o corpo principal, próximo ao `render_tab_selector`. Trocar `st.sidebar.*` por `st.*`. O posicionamento sugerido é entre o `render_tab_selector` (linha 518) e o `render_pdf_download_topo` (linha 522), ou logo acima do seletor de abas. O Planner decide a posição exata.
- Invariantes: a key `"coord_search_input"` deve ser preservada (usada em testes). A lógica de parsing em `parse_coordinate_input` e o retorno `search_pin: tuple[float, float] | None` não mudam. `render_hex_search_result` e `render_relatorio_pontual_censitario` não mudam.

### Testes
- `tests/integration/test_streamlit_app.py`: adaptar/adicionar testes para as novas posições dos widgets (sidebar → corpo). Testes que hoje assertem `st.sidebar.*` para UF/município/faixa/busca devem ser atualizados.

## Fora de escopo
- Qualquer alteração em `score_priorizacao`, `hex_score_estrutural`, pesos, carteira, plano, ou artefatos oficiais do M1.
- Alteração nos módulos `censo_map.py`, `censo_report.py`, `censo_point.py`.
- Alteração no método de interseção geométrica, raio de 1,5 km ou lógica de análise pontual.
- Alteração em `components.py`, `constants.py`, `utils.py`, `config.py`, `pipelines/m1/`.
- Alteração no render lazy de abas (`render_tab_selector` em si), na carga lazy por UF (`load_uf_slice`/`load_uf_catalog`) ou na fonte de mapa enxuta (`_downsample_map_index`/`MAP_POINT_LIMIT`).
- Adição de dependências externas ou chamadas de API ao vivo.
- Filtros avançados (Elegibilidade híbrida, Cobertura censitária, Qualidade, checkboxes top_municipio/top_hex): incluir ou não na migração é DECISÃO DO PLANNER/GATE HUMANO — o escopo citado pelo usuário menciona apenas UF, município e faixa de oportunidade.
- Hero header contextual por UF (F2-E herdado do BLK-UI-01) — bloco futuro separado.

## Arquivos que devem ser lidos
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\dashboard\pages.py` — funções: `render_uf_selectbox` (L431-465), `render_tab_selector` (L484-508), `render_sidebar_filters` (L511-575), `render_coord_search_sidebar` (L582-600), `render_hex_search_result` (L603-680), `render_relatorio_pontual_censitario` (L2740-2882), `render_pdf_download_topo` (L2682-2738); constante `_CENSUS_PREVIEW_WIDTH_PX` (L113).
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\streamlit_app.py` — função `main()` (L450-618), sequência de chamadas: `render_uf_selectbox` (L458), `render_sidebar_filters` (L491), `render_coord_search_sidebar` (L493), `render_tab_selector` (L518), `render_hex_search_result` (L541).
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\tests\integration\test_streamlit_app.py` — identificar testes que assertem widgets de sidebar para UF/município/faixa/busca.
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\tasks\current_task.md` — paths pré-sujos e dívida herdada.

## Arquivos que podem ser alterados
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\dashboard\pages.py`
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\streamlit_app.py`
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\tests\integration\test_streamlit_app.py`
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\tasks\current_task.md` (housekeeping de ciclo)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\context\handoff.md` (cada Skill sobrescreve)

## Critérios de aceite

### F1 — 2x2 do Relatório Censitário
- [ ] As 4 imagens (densidade, renda, score, concorrentes) são exibidas em grade 2×2 — dois mapas por linha, sem scroll horizontal.
- [ ] Nenhuma das funções `censo_map.py` / `censo_report.py` / `censo_point.py` foi alterada.
- [ ] O método de interseção, raio 1,5 km e lógica de análise pontual estão intocados (grep zero diff em `setor_censitario_intersecao_area_1p5km`).
- [ ] Teste novo ou atualizado valida o arranjo 2×2 (ex.: assert de `st.columns` com 2 colunas para as imagens).

### F2 — Filtros no corpo principal
- [ ] Os widgets UF (selectbox), Município (multiselect) e Faixa de oportunidade (multiselect) aparecem no corpo principal da página, não na sidebar.
- [ ] A carga lazy por UF continua funcional: `load_uf_slice` só é chamado após o usuário selecionar UF; app exibe mensagem de orientação (não carrega o Brasil inteiro) quando UF é None.
- [ ] `apply_global_filters` recebe os mesmos 8 parâmetros de retorno da lógica de filtros, sem alteração de contrato.
- [ ] Testes de integração atualizados para refletir a nova posição dos widgets.

### F3 — Busca no corpo principal
- [ ] O campo de busca por coordenada aparece no corpo principal, próximo ao seletor de abas, não na sidebar.
- [ ] A key `"coord_search_input"` é preservada.
- [ ] `render_hex_search_result` e `render_relatorio_pontual_censitario` continuam recebendo `search_pin` corretamente e funcionam sem alteração.
- [ ] Testes de integração atualizados para a nova posição do widget.

### Gate geral
- [ ] Suíte completa verde: `pytest -q` sem failures novos (tolerância: dívida herdada listada em `current_task.md`).
- [ ] `ruff check` e `mypy` limpos nos arquivos alterados.
- [ ] `import streamlit_app` ok.
- [ ] `config.py`, `pipelines/m1/`, `components.py`, `constants.py`, `utils.py` INTOCADOS (grep diff confirma zero edição).
- [ ] Sem nova dependência de API ao vivo no dashboard.

## Criticidade classificada
**Alta**

Justificativa: mexe no dashboard de produção, reposiciona widgets de navegação e filtros que interagem com a carga lazy por UF (Bloco 4). Embora seja READ-ONLY sobre o M1, o risco de regressão no fluxo de carregamento é real. Esteira com gate humano obrigatório.

## Esteira recomendada
Block Orchestrator (este) → **Planner** → `[REVISÃO HUMANA — gate obrigatório]` → Builder → QA

## Riscos identificados

1. **Carga lazy por UF (Bloco 4) — CRÍTICO para F2:** `render_uf_selectbox` hoje está na sidebar e seu retorno é o gatilho de `st.stop()` que impede carregar o Brasil inteiro. Ao migrar para o corpo principal, o widget de UF precisa ser renderizado ANTES de qualquer acesso a `load_uf_slice`. No Streamlit, widgets no corpo principal são renderizados em ordem de execução do script — o `selected_uf = render_uf_selectbox(uf_catalog)` deve continuar sendo a primeira chamada significativa do `main()`, antes do `st.spinner("Carregando dados da UF...")`. O Planner deve detalhar a ordem exata dos widgets no corpo para garantir isso.

2. **Session state dos filtros — F2/F3:** ao mover widgets de `st.sidebar.*` para `st.*`, os keys de session_state (não definidos explicitamente no código, mas gerenciados pelo Streamlit internamente) mudam de namespace. Testes que hoje mockam `st.sidebar.selectbox`/`st.sidebar.multiselect`/`st.sidebar.text_input` precisam ser atualizados. Verificar se há algum key explícito (`key=...`) nos widgets de sidebar que conflite com o corpo.

3. **Key `"coord_search_input"` — F3:** a função `render_coord_search_sidebar` usa `key="coord_search_input"` no `text_input`. Esta key é referenciada nos testes de integração. Ao migrar para o corpo, a key deve ser preservada, mas verificar se algum teste verifica o namespace `st.sidebar` para este widget.

4. **Sidebar vazia após migração:** com UF, município, faixa e busca migrados para o corpo, a sidebar fica com apenas os filtros avançados (expander) e possivelmente nenhum widget visível por padrão. O comportamento de `initial_sidebar_state="expanded"` (linha 181 do `streamlit_app.py`) pode ser ajustado para `"collapsed"` ou `"auto"` — decisão de produto para o Planner/gate humano.

5. **Largura das imagens 2x2 — F1:** `_CENSUS_PREVIEW_WIDTH_PX = 720` foi calibrado para exibição full-width (sidebar aberta). Em grade 2×2, cada imagem ocupa ~50% da largura disponível; se `width=720` for mantido, pode causar overflow horizontal. O Builder deve ajustar o width para o contexto de coluna (tipicamente `use_container_width=True` ou um valor menor).

6. **Testes de sidebar existentes:** identificar em `test_streamlit_app.py` todos os asserts que envolvem `st.sidebar` para os widgets migrados — eles precisam ser atualizados antes do gate de QA.

## Guardrails ativos

- §2: Staging em Parquet; offline; sem dependência de API ao vivo no dashboard de produção.
- §3: Score oficial `score_priorizacao` e parâmetros canônicos INALTERADOS.
- §5 (guardrail permanente): visualizações, análise radial e interações de mapa não podem recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano domínio ou artefatos oficiais do M1 sem aprovação explícita.
- CLAUDE.md §4: carga lazy por UF (`load_uf_slice`/`load_uf_catalog`) e render lazy das abas (`render_tab_selector` + `session_state`) PRESERVADOS.
- DEC-001: pesos `renda=0.40`/`pop=0.60` e fórmula INALTERADOS.
- DEC-004: fundo de ruas por tiles online restrito ao caminho de geração do relatório (não ao dashboard interativo). O arranjo 2x2 não altera essa lógica.

## Estado da suíte ao iniciar o ciclo (referência)
- Suíte full serial (QA do recorte anterior, BLK-UI-01): `955 passed, 1 skipped, 0 failed`.
- Dívida herdada (NÃO regressão deste ciclo, listada em `current_task.md`):
  - `test_csvs_concorrentes_legiveis[csv_path1-223]` e `[csv_path2-472]` — drift de snapshot CSV real local.
  - `test_parquet_final_respeita_guardrails_do_piloto` — gate DEC-006.
