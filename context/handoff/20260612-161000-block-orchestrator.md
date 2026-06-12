# Handoff — Block Orchestrator

> Nota de auditoria: snapshot de delimitação registrado pelo orquestrador para fechar a trilha de
> auditoria do BLK-UI-03. O sub-agente de delimitação acumulou BO+Planner numa execução; o plano
> técnico autoritativo foi (re)produzido na sequência pelo Planner em Opus (snapshot `*-planner.md`
> posterior). Este arquivo registra a DELIMITAÇÃO (escopo), não o plano.

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-UI-03 — 4 ajustes finos de UX no dashboard (READ-ONLY M1), a partir do teste do BLK-UI-02. FECHA também o BLK-FIX-10 (item nº3).

## Objetivo
Reverter/afinar pontos de UX e melhorar destaque de navegação, sem tocar score/artefatos M1, sem alterar a lógica de render lazy (Bloco 5) e sem afetar o PDF exportado do Relatório Pontual.

## Escopo permitido (4 itens)
1. **Reverter coord** — `render_coord_search_sidebar` (src/motor_expansao/dashboard/pages.py ~523-543): remover o `st.sidebar.info(...)` do BLK-UI-02, voltar ao heading `### Busca por coordenada` + `st.sidebar.caption(...)`. Preservar `text_input`/parse/retorno `(lat,lng)|None` e a chamada única em `streamlit_app.py:470`.
2. **Tooltip meio-termo** — `_shared_map_tooltip` e `_hybrid_compact_tooltip` (components.py): ajustar os VALORES do `style` (fontSize/padding/maxWidth/lineHeight) para um meio-termo entre o default e o 11px do BLK-UI-02. Não remover chaves.
3. **[BLK-FIX-10] Preview menor** — as 4 `st.image(..., width="stretch")` do preview do Relatório Pontual (pages.py ~2596-2615): controlar largura na TELA. NÃO afetar o PDF exportado nem `censo_map.py`/`censo_report.py`/geração das imagens.
4. **Destaque do seletor de abas (SÓ CSS)** — regras do `stSegmentedControl` em `inject_styles()` (pages.py ~301-319). NÃO tocar `render_tab_selector` (pages.py ~426-450) nem a lógica de `session_state`/render lazy (Bloco 5).

## Fora de escopo
- Recalcular score (score_priorizacao, hex_score_estrutural, score_setor_2022_calibrado, residual, SAM) ou artefatos M1.
- Alterar a LÓGICA de render lazy de abas (Bloco 5) — só estilo do seletor.
- Alterar o PDF exportado / geração de mapas do Relatório Pontual (item nº3 é só o preview na tela).
- Quebrar Bloco 4 (carga lazy) / Bloco 6 (mapa enxuto); recolocar dependência de API ao vivo.

## Arquivos que devem ser lidos
- src/motor_expansao/dashboard/pages.py (523-543 coord; 2596-2615 preview; 301-319 CSS; 426-450 render_tab_selector)
- src/motor_expansao/dashboard/components.py (_shared_map_tooltip / _hybrid_compact_tooltip)
- tests/integration/test_streamlit_app.py (test_map_tooltips_tem_css_de_tamanho; test_inject_styles_cobre_componentes_baseweb)
- tasks/backlog.md (### BLK-FIX-10)

## Arquivos que podem ser alterados
- src/motor_expansao/dashboard/pages.py
- src/motor_expansao/dashboard/components.py
- tests/integration/test_streamlit_app.py

## Critérios de aceite
- #1 coord revertido ao heading+caption; retorno e chamada fora-de-aba intactos.
- #2 tooltips com valores meio-termo; chaves pré-existentes e html intactos; teste atualizado.
- #3 preview com largura controlada na tela; PDF e geração de mapas intocados (fecha BLK-FIX-10).
- #4 seletor de abas mais destacado SÓ via CSS; `render_tab_selector` byte-idêntico (Bloco 5).
- READ-ONLY M1; suíte sem novas falhas; ruff/mypy limpos.

## Criticidade classificada
Alta (toca o seletor de abas da produção/Bloco 5 e a navegação do dashboard; READ-ONLY M1). Esteira: Block Orchestrator → Planner → [REVISÃO HUMANA] → Builder → QA.

## Esteira recomendada
Block Orchestrator (concluído) → Planner (opus) → [REVISÃO HUMANA] → Builder (opus) → QA (opus 4.8)

## Riscos identificados
- Bloco 5: estilizar o seletor sem tocar `render_tab_selector`/`session_state`.
- Item nº3 não pode mudar o PDF, só o preview na tela.
- Reverter o coord sem quebrar o retorno `(lat,lng)|None`.
- Contrato do teste `test_map_tooltips_tem_css_de_tamanho` (assere os valores antigos) precisa ser atualizado junto.

## Guardrails ativos
- §5 visualização READ-ONLY sobre o M1; §4 Bloco 5 render lazy intocável; Relatório Pontual: PDF/geração intocados (item nº3 é só preview).

## Nota de housekeeping
Este ciclo FECHA o BLK-FIX-10 (bloco real do backlog). No fechamento, mover via `scripts/housekeeping_move_block.py BLK-FIX-10`.

## Paths pré-sujos (NÃO tocar)
- data/outputs/setores_censitarios_2022_geo/_metadata.json
- data/reports/relatorio_pontual_censitario_base_geo.md
