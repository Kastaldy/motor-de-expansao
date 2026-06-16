# Current Task

## Bloco atual

ID: BLK-UI-07
Nome: Refinos de UX/UI do dashboard (2x2 do Relatório Censitário + filtros/busca na tela principal)
Status: APROVADO COM RESSALVAS (recorte) — ciclo fechado; bloco amplo BLK-UI-07 permanece ABERTO
Tipo: feature (UX/UI no dashboard de produção; READ-ONLY sobre M1)
Criticidade: alta
Esteira: Block Orchestrator → Planner → [aprovação humana ✅ D1–D4] → Builder ✅ → QA ✅ APROVADO COM RESSALVAS
Skill atual: Fechamento (commit por path na branch ciclo/BLK-UI-07 + PR para main)
Próxima Skill: Merge (passo humano)

## Veredito do QA (2026-06-16, Opus 4.8)
APROVADO COM RESSALVAS. Validações re-executadas sem bypass: import ok; ruff All checks passed; mypy Success (2 arquivos);
alvo test_streamlit_app.py 199 passed; suíte full 963 passed / 1 skipped / 1 flaky pré-existente
(test_classico_template_recente_inalterado — passa isolado e após os testes alterados; censo_report.py intocado →
NÃO é regressão deste ciclo; follow-up BLK-FIX-14 criado). Escopo respeitado (só pages.py/streamlit_app.py/
test_streamlit_app.py); READ-ONLY M1 confirmado. Housekeeping: N/A (recorte — bloco amplo permanece aberto, sem move/close).
Detalhe em context/handoff.md e snapshot context/handoff/20260616-161446-qa.md. Sucessor placeholder BLK-UI-08 criado.

## Estado da auditoria READ-ONLY do QA (orquestrador, sem Bash)
- F1 ✓ grade 2x2 (pages.py L2871-2892), ordem densidade/renda→score/concorrentes, captions byte-a-byte, use_container_width=True.
- F2 ✓ via st.* (zero st.sidebar.* em pages.py); carga lazy por UF intacta (UF L458 antes de load_uf_slice L466; st.stop() L460-462; st.info sem "na barra lateral"); contrato de 8 retornos preservado; Município+Faixa em st.columns(2); avançados em st.expander no corpo.
- F3 ✓ key="coord_search_input" preservada; trio search_pin L515-517 antes de render_tab_selector L524.
- D2 ✓ initial_sidebar_state="collapsed" (streamlit_app.py L182).
- Testes ✓ assert reescrito (col.image==4, st.image==0, ≥2 st.columns(2)) + 3 testes de namespace-corpo.
- PENDENTE (precisa de Bash): suíte full, ruff, mypy, import smoke, git diff. Builder reportou 199 passed/0 em test_streamlit_app.py, import ok, ruff+mypy limpos.

## Decisões de produto aprovadas (Vinicius, 2026-06-16)
- D1 = Expander "Filtros avancados" no CORPO (st.expander, expanded=False).
- D2 = initial_sidebar_state "collapsed" (streamlit_app.py).
- D3 = UF (selectbox) sozinho no corpo antes do load_uf_slice; Município+Faixa numa st.columns(2) abaixo; busca por coordenada imediatamente acima de render_tab_selector.
- D4 = use_container_width=True nas 4 imagens do grid 2x2.

## Objetivo
Aplicar três mudanças de UX/UI no dashboard de produção, sem regressão funcional nem do M1:
1. As 4 imagens do Relatório Pontual Censitário em arranjo 2x2 (ocupar menos espaço vertical).
2. Filtros UF / município / faixa de oportunidade: remover do menu lateral e integrar na tela principal.
3. Busca por coordenada: remover do menu lateral e aplicar como barra de pesquisa na tela principal,
   próxima ao seletor de abas.

## Escopo citado pelo usuário (Vinicius, 2026-06-16)
- 4 imagens do Relatório Pontual Censitário organizadas em 2x2.
- Seletores de UF, município e faixa de oportunidade saem do menu lateral → tela principal.
- Busca sai do menu lateral → barra de pesquisa na tela principal, perto do seletor de tabs.

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: sonnet
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-UI-07 (criada a partir de main / HEAD db53cad)

## Paths pré-sujos (NÃO commitar — alheios ao ciclo)
- data/outputs/setores_censitarios_2022_geo/_metadata.json
- data/reports/relatorio_pontual_censitario_base_geo.md

## Dívida operacional herdada (NÃO é regressão deste ciclo)
3 failures pré-existentes na suíte full, comprovados em tree limpo:
- test_csvs_concorrentes_legiveis[csv_path1-223] e [csv_path2-472] — drift de snapshot de CSV real local.
- test_parquet_final_respeita_guardrails_do_piloto — gate DEC-006 (regeneração de parquets paralelos é passo pós-merge).
