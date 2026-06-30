# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-UI-11 — Aprimoramento estético e clareza de conteúdo do dashboard (caminho de produção)**

Polimento geral das 4 abas do dashboard Streamlit (Visão Executiva, Mapa Territorial, Expansão de
Domínio, Carteira e Plano): estética, clareza de conteúdo, hierarquia de informação e redução de
ruído. Caminho de PRODUÇÃO atual (pydeck/abas existentes). O Planner levanta e propõe os ajustes
concretos; o gate humano (Vinicius) aprova antes do Builder executar.

## Objetivo
Melhorar a experiência visual e a clareza do conteúdo das 4 abas do dashboard Streamlit, sem alterar
nenhuma lógica de cálculo, score, ranking ou artefato oficial do M1.

## Escopo permitido
- CSS injetado via `st.markdown` (temas, espaçamento, tipografia, cores de UI)
- Reorganização de containers/colunas dentro das abas (sem alterar qual dado é exibido, só disposição)
- Textos, rótulos, legendas e microcopy das abas (títulos de seção, labels de KPI, tooltips, mensagens de ajuda, estado vazio)
- Redução de redundância: remover ou fundir elementos que exibem a mesma informação duas vezes
- Ajuste de densidade de informação: reordenar ou ocultar elementos de baixo valor de leitura
- Hierarquia visual: weight de títulos, separadores, agrupamento lógico de controles relacionados
- Tooltips e mensagens de `st.info`/`st.warning` que ajudem o operador a entender o que está vendo
- Ajustes nos renders de legendas (`render_score_bands_legend`, `render_competitor_legend`, `render_ultra_legend`, `render_pop_cut_legend`, `render_geographic_source_legend`, `render_dominio_tese_legend`, `render_ancoras_dominio_legend`) — só texto e posicionamento, não lógica
- Ajustes nos `render_*` de cada aba em `pages.py` — somente display (texto/layout/containers), não cálculo

## Fora de escopo
- score/pesos/artefatos M1 (`score_priorizacao`, `hex_score_estrutural`, carteira, plano, artefatos oficiais) — ABSOLUTO
- Qualquer lógica de cálculo: `build_map_figure`, `build_hybrid_map_figure`, `build_dominio_map_figure`, `build_unified_map_figure`, `build_kpis`, `build_residual_*`, `build_ranking_table` — funções de dados intocadas
- Contratos de performance dos Blocos 4–6: `load_uf_slice`, `read_enriched_uf_partition`, `build_dashboard_dataset`, `render_tab_selector` (segmented_control + session_state) — intocados
- O PoC BLK-UI-10 (trilha separada opt-in, não confundir com este bloco)
- Dependência de API ao vivo nova (sem adicionar chamada de rede na carga/interatividade do dashboard)
- Recalcular ou alterar qualquer valor de dado (ordenação, filtros, contagens)
- Alterar a estrutura de abas (as 4 abas existentes permanecem; só o conteúdo interno pode ser reorganizado)
- Adicionar dependência nova ao `pyproject.toml` base

## Arquivos que devem ser lidos
- `src/motor_expansao/dashboard/pages.py` — render de cada aba; microcopy atual; distribuição de containers
- `src/motor_expansao/dashboard/components.py` — builders e renders de legendas, KPIs, tabelas, gráficos
- `streamlit_app.py` — estrutura geral, `render_tab_selector`, `apply_exec_layout`, constantes visuais globais
- `src/motor_expansao/dashboard/utils.py` — helpers de formatação (`format_int`, `format_pct`, `format_score`, etc.)
- `src/motor_expansao/dashboard/constants.py` — `COLORS`, `RESIDUAL_SCORE_BANDS`, `FAIXA_COLORS`, `COLOR_MODES`, `OVERLAYS`
- `tests/integration/test_streamlit_app.py` — testes de render/UI que os ajustes não podem quebrar

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/pages.py` — container layout, textos, rótulos, microcopy, tooltips nas 4 abas
- `src/motor_expansao/dashboard/components.py` — textos de legendas, helpers de render visual (display-only)
- `streamlit_app.py` — CSS injetado globalmente, títulos de app, mensagens de header/footer
- `src/motor_expansao/dashboard/utils.py` — formatadores de valor (se houver oportunidade de clareza)
- `tests/integration/test_streamlit_app.py` — atualizar assertions de texto/label que mudarem

## Critérios de aceite
- As 4 abas seguem renderizando sem erro (smoke de import + render ok)
- Nenhum valor de dado alterado: os mesmos hexes, scores, KPIs e tabelas são exibidos; só a apresentação muda
- Suite verde: `ruff check`, `mypy`, `pytest -q` (incluindo `test_streamlit_app.py`) sem regressão
- READ-ONLY M1 comprovado: zero diff em `config.py`, `pipelines/m1`, artefatos oficiais, `score_priorizacao`
- Performance dos Blocos 4–6 não regredida: `render_tab_selector`, `load_uf_slice` e `read_enriched_uf_partition` intocados
- O plano concreto de ajustes (lista de mudanças por aba) foi aprovado pelo gate humano (Vinicius) antes do Builder executar

## Criticidade classificada
**Alta**

Justificativa: superfície ampla (as 4 abas do dashboard de produção; `pages.py` e `components.py`
têm centenas de funções e são os arquivos centrais do dashboard); gate humano desejado antes do
Builder (o Planner propõe, Vinicius aprova o plano); READ-ONLY M1 (sem toque em score/artefatos).
Não é Crítica porque não toca o M1. Não é Média porque qualquer ajuste mal feito em `pages.py`/
`components.py` pode quebrar a suíte ou introduzir regressão visual difícil de rastrear num arquivo
de produção central.

## Esteira recomendada
Block Orchestrator (concluído) → **Planner** → [REVISÃO HUMANA — gate Vinicius aprova o plano de mudanças] → Builder → QA

## Riscos identificados
- `pages.py` e `components.py` são grandes; o Builder pode inadvertidamente tocar funções de cálculo ao editar texto próximo — o Planner deve listar mudanças linha-a-linha para o Builder não extrapolar
- Testes em `test_streamlit_app.py` fazem assertions de strings/cores; ajustes de microcopy podem quebrar testes de forma esperada (atualizar junto no mesmo PR)
- O contrato de performance dos Blocos 4–6 é frágil: qualquer refactor que mova o `render_tab_selector` para dentro de um `if/else` convencional destrói a carga lazy — o Planner deve listar esse ponto explicitamente como intocável
- O BLK-UI-10 (PoC) tem direção visual definida (Space Grotesk, paleta turquesa/magenta via CDN); o BLK-UI-11 pode ou não se inspirar nela, mas não deve criar dependência nova de fonte/lib — o Planner deve anotar essa tensão e propor se as fontes serão via CDN ou só CSS nativo do Streamlit

## Guardrails ativos
- §5 (CLAUDE.md): visualizações, análise radial e interações de mapa **não podem** recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano de domínio ou artefatos oficiais do M1 sem aprovação explícita.
- §2 (CLAUDE.md): não criar dependência de API ao vivo no dashboard de produção.
- Blocos 4–6 (CLAUDE.md §4): `render_tab_selector`, `load_uf_slice`/`read_enriched_uf_partition` e `_downsample_map_index` são contratos de performance intocáveis.
- Gate humano obrigatório: o Planner entrega um plano de mudanças por aba; o Builder **só executa após aprovação do Vinicius**.
