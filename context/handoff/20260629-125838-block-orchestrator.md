# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-UI-11 — Aprimoramento estético e clareza de conteúdo do dashboard (caminho de produção)

## Objetivo
Polir a estética e a clareza das 4 abas do dashboard Streamlit de produção (Visão Executiva, Mapa Territorial, Expansão de Domínio, Carteira e Plano), sem tocar nenhum dado, score, cálculo ou artefato M1.

## Escopo permitido
- Estilo/CSS: ajustes em `inject_styles()` (CSS injetado via `st.markdown`), tipografia, espaçamento, hierarquia visual, paleta dentro do tema atual
- Layout/containers: reorganização de colunas, expanders, tabs, espaçamentos, alinhamentos — sem alterar a lógica de render ou os contratos de performance dos Blocos 4–6
- Textos/rótulos/legendas: revisão e simplificação de títulos, subtítulos, labels de filtros, legendas de cores, captions de mapa, mensagens de ajuda e tooltips
- Remoção de redundância/ruído: retirar conteúdo duplicado, seções pouco úteis ou confusas, reduzir densidade de informação onde prejudica a leitura
- Hierarquia de informação: promover informação de alto valor (KPIs principais, ações) e rebaixar detalhes técnicos
- Tooltips e mensagens de ajuda: adicionar ou revisar para orientar o operador sem poluir a tela

## Fora de escopo
- Qualquer campo, cálculo ou peso do M1 (`score_priorizacao`, `hex_score_estrutural`, `renda_per_capita`, `pop_total`, pesos 0.40/0.60, etc.)
- Lógica de cálculo: `build_map_figure`, `build_hybrid_map_figure`, `build_dominio_map_figure`, `build_unified_map_figure` e todas as funções `build_*` que retornam dados ou camadas
- Contratos de performance dos Blocos 4–6: `load_uf_slice`, `read_enriched_uf_partition`, `build_dashboard_dataset`, `render_tab_selector`, `_downsample_map_index` — intocados
- Artefatos oficiais do M1: `brasil_estrutural.parquet`, `brasil_priorizados.parquet`, `hexagonos_brasil_oportunidades.parquet`, `hexagonos_brasil_dashboard.parquet`, etc.
- Carteira e plano: `carteira_expansao_acionavel.parquet`, `plano_expansao_curto_prazo.parquet`
- Dependência de API ao vivo nova (fora das já aprovadas nas DEC-004/DEC-010/DEC-011)
- O PoC BLK-UI-10 (trilha separada, opt-in atrás de flag — este bloco é o caminho de produção)
- Alterações em `data.py`, `constants.py`, `schemas.py` (lógica e contratos de dados)
- Alterações em pipelines (`src/motor_expansao/pipelines/`)
- `censo_point.py`, `censo_map.py`, `censo_report.py` (superfície do Relatório Pontual Censitário — outra trilha)
- `relatorio_municipal.py` (superfície do Relatório Municipal — outra trilha)
- Quaisquer paths pré-sujos: `data/outputs/setores_censitarios_2022_geo/_metadata.json`, `data/outputs/setores_censitarios_2022_geo/_report.md`

## Arquivos que devem ser lidos
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\CLAUDE.md` — guardrails, §2, §4, §5
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\tasks\backlog.md` — linhas 978–1012 (BLK-UI-11) e 1014–1040 (BLK-UI-10, para não confundir escopos)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\tasks\current_task.md` — estado atual do ciclo
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\dashboard\pages.py` — funções render por aba, `inject_styles()`, sidebar, seletor de abas
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\dashboard\components.py` — componentes visuais reutilizáveis (legendas, cards, captions)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\dashboard\constants.py` — constantes de cor, rótulos, ordens
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\dashboard\utils.py` — helpers de formatação e cor
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\streamlit_app.py` — ponto de entrada, `st.set_page_config`, imports, estrutura de alto nível
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\tests\integration\test_streamlit_app.py` — testes de integração do dashboard (suíte que o QA valida)

## Arquivos que podem ser alterados
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\dashboard\pages.py` — `inject_styles()`, funções `render_*` (layout, textos, labels, legenda)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\dashboard\components.py` — componentes visuais reutilizáveis (tooltips, legendas, captions, render de cards)
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\dashboard\constants.py` — SOMENTE constantes de rótulo/texto; NÃO alterar constantes que afetam lógica de cálculo, score ou performance
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\src\motor_expansao\dashboard\utils.py` — SOMENTE helpers de formatação e exibição
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\streamlit_app.py` — SOMENTE `st.set_page_config` e estrutura visual de alto nível; NÃO tocar caminhos de dados ou imports de lógica
- `C:\Users\Vinicius Cruz\Downloads\Projetos\motor-de-expansao\tests\integration\test_streamlit_app.py` — atualizar testes de cor/texto que reflitam as mudanças visuais aprovadas; NÃO remover testes de comportamento

## Critérios de aceite
- As 4 abas (Visão Executiva, Mapa Territorial, Expansão de Domínio, Carteira e Plano) seguem funcionais sem erros
- Suíte verde: `ruff`, `mypy` e `pytest` (incluindo `test_streamlit_app.py`) sem falhas novas introduzidas pelo ciclo
- Nenhuma função de cálculo alterada: `build_map_figure`, `build_hybrid_map_figure`, `build_dominio_map_figure`, `build_unified_map_figure`, `agregar_cenario_multihex`, `analisar_entorno_ponto`, `lookup_hex_by_coord`, etc.
- Contratos de performance dos Blocos 4–6 intocados: `read_enriched_uf_partition`, `render_tab_selector`, `_downsample_map_index`, `build_pop_cut_lookup` e similares sem modificação
- `score_priorizacao`, `hex_score_estrutural` e pesos 0.40/0.60 inalterados — zero escrita em artefatos M1
- Gate humano respeitado: o Planner propõe a lista concreta de ajustes; o humano (Vinicius) aprova antes do Builder executar
- Nenhum path pré-sujo (`_metadata.json`, `_report.md`) incluído em commits do ciclo

## Criticidade classificada
Alta

## Justificativa da criticidade
O bloco é READ-ONLY sobre o M1 (visualização e texto), sem tocar score/pesos/artefatos. A criticidade **Alta** (e não Média) é justificada por: (a) **superfície ampla** — as 4 abas do dashboard de produção em uso pelo time executivo; (b) **gate humano obrigatório** — o Planner propõe ajustes concretos antes de qualquer linha de código ser alterada, garantindo alinhamento de produto; (c) **risco de regressão acidental** em funções de cálculo ou contratos de performance que convivem no mesmo arquivo com o código visual.

## Esteira recomendada
Block Orchestrator → Planner → [REVISÃO HUMANA — gate] → Builder → QA

## Riscos identificados
- Superfície ampla (`pages.py` e `components.py` são arquivos grandes com funções de cálculo e visualização no mesmo arquivo): risco de editar acidentalmente lógica de dados ou performance ao modificar vizinhos de layout
- `inject_styles()` injeta CSS global que afeta todos os elementos; mudanças de CSS podem quebrar componentes não óbvios (ex.: `stMetric`, tooltips, sidebar)
- `render_tab_selector` usa `st.segmented_control` + `session_state` (contrato do Bloco 5); qualquer alteração nessa função quebraria o render lazy das abas
- Testes de integração em `test_streamlit_app.py` validam cores e textos específicos; mudanças visuais demandam atualização cuidadosa dos testes para não mascarar regressões
- O Planner precisa distinguir claramente o que é "ruído visual" de "informação técnica necessária" (ex.: legendas de score, labels de qualidade de join) — risco de remoção prematura de informação relevante para o operador
- O BLK-UI-10 (PoC) é trilha separada e não deve ser confundido com este bloco; mudanças no caminho de produção não devem introduzir elementos do PoC

## Guardrails ativos
- **§2 operacional**: não criar dependência de API ao vivo no dashboard de produção (exceto as já aprovadas em DEC-004, DEC-010, DEC-011).
- **§3 parâmetros canônicos**: `score_priorizacao`, `hex_score_estrutural`, pesos `renda=0.40`/`pop=0.60`, `H3_RESOLUTION=7`, `DIST_MIN_ULTRA_KM=1.0`, `RENDA_MIN=4500.0` e demais parâmetros — INALTERADOS.
- **§5 guardrail permanente**: visualizações, análise radial e interações de mapa não podem recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano domínio ou artefatos oficiais do M1 sem aprovação explícita.
- **Blocos 4–6 de performance**: `load_uf_slice`/`read_enriched_uf_partition`/`build_dashboard_dataset` (carga lazy por UF), `render_tab_selector` (render lazy de abas) e `_downsample_map_index` (fonte de mapa enxuta) são intocados.
- **Interpretação operacional de criticidade (2026-05-30)**: LEITURA/ANÁLISE de score sem escrita em artefato M1 → Alta (revisão humana antes do Builder); ALTERAÇÃO de fórmula, pesos ou qualquer artefato M1 → Crítica (aprovação obrigatória + DEC).
- **Paths pré-sujos fora do ciclo**: `data/outputs/setores_censitarios_2022_geo/_metadata.json` e `_report.md` NÃO devem ser incluídos em commits deste ciclo.
