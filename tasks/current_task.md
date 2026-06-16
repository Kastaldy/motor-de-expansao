# Current Task

## Bloco atual

ID: BLK-UI-01
Nome: Refatoração UX/UI da plataforma Motor de Expansão (2º recorte deste ciclo — Densidade/Navegação)
Status: APROVADO (RECORTE) — bloco amplo BLK-UI-01 permanece ABERTO
Tipo: feature (UX/UI no dashboard de produção; READ-ONLY sobre M1)
Criticidade: alta
Esteira: Block Orchestrator → Planner → [aprovação humana — Felipe/Vini ✅ APROVADO COM AJUSTES] → Builder ✅ → QA ✅ APROVADO
Skill atual: QA/Quality Analyzer (auditoria concluída; veredito APROVADO)
Próxima Skill: Fechamento manual (registrar em completed.md como entrega de RECORTE, sem mover/fechar o bloco amplo)

## Veredito do QA (2026-06-16 10:03:34)
APROVADO. Suíte FULL serial 955 passed / 1 skipped / 0 failed (xdist `-n auto` indisponível por bug
de ambiente Py3.14 — INTERNALERROR execnet, NÃO mascarado com `-p no:xdist`). Alvo 190 passed; ruff
"All checks passed!"; mypy "Success: no issues found"; import ok. Os 3 débitos herdados re-executados
e VERDES neste tree (resultado melhor que a tolerância "só esses 3"). Escopo respeitado (só
`pages.py`/`streamlit_app.py`/`test_streamlit_app.py`); READ-ONLY M1 confirmado; `censo_*`/`components`/
`constants`/`utils`/`config.py`/`pipelines/m1` INTOCADOS; parâmetros canônicos §3 intactos. Detalhe em
`context/handoff.md` e snapshot `context/handoff/20260616-100334-qa.md`. Housekeeping: N/A (recorte —
bloco amplo permanece aberto, sem move/close).

## GATE APROVADO COM AJUSTES (Felipe/Vini, 2026-06-16)
As 3 decisões de produto (F1-A sets, F2-A labels, F2-C expander) foram aprovadas, MAIS:
- **F2-A REVISADO — REORDER das abas:** nova ordem/labels `["Mapa", "Executivo", "Expansão de Domínio", "Carteira e Plano", "Viabilidade"]` (Mapa = 1ª aba/padrão ao carregar). Muda ordem de `DASHBOARD_TAB_LABELS`, default do `render_tab_selector` e o dispatch em `main()` (lockstep). Acentos UTF-8.
- **F2-F (NOVO):** mover o botão de download do relatório pontual censitário para o TOPO da seção do mapa (só reposicionar a chamada de UI em `render_relatorio_pontual_censitario`; `censo_*` INTOCADO).
- **F2-G (NOVO):** sidebar SEMPRE aberta no load/reload (manter `initial_sidebar_state="expanded"` + reforço CSS opcional offline; sem JS de auto-clique).
- **F2-H (NOVO):** `render_tab_selector` SEMPRE no topo do corpo principal de `main()`, acima de qualquer conteúdo condicional.
- **F2-I (NOVO):** info da coordenada pesquisada (`render_hex_search_result`) reposicionada para DEPOIS do seletor de abas (consistente com F2-H).
- F1-D: SEM AÇÃO (evidência registrada). F2-E: FUTURO (fora deste ciclo).
Plano consolidado em `context/handoff.md` (revisado pós-gate). Próximo passo: Builder.

## Foco do 1º recorte (decisão do usuário Vinicius, 2026-06-16)
Priorizar duas frentes no primeiro recorte deste bloco amplo:
1. **Densidade/clareza de dados** — reduzir poluição visual de tabelas/KPIs/tooltips e melhorar leitura de números.
2. **Navegação e fluxo** — seletor de abas, sidebar, ordem de seções, descoberta de funcionalidades.
O Planner deve propor um fatiamento concreto dentro destas duas frentes e marcar o que fica para recortes futuros.
O bloco amplo BLK-UI-01 PERMANECE ABERTO; este ciclo entrega apenas o 1º recorte.

## Objetivo
Melhorar usabilidade/consistência visual das 4 abas (Visão Executiva, Mapa Territorial,
Expansão de Domínio, Carteira e Plano) sem regressão funcional nem do M1, focando densidade/clareza
de dados e navegação/fluxo. Preservar carga lazy por UF, render lazy de abas e fonte de mapa enxuta
(Blocos 4–6). READ-ONLY M1; offline; sem dependência de API ao vivo.

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: sonnet
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-UI-01 (fast-forwarded para main c39ed17 no início deste ciclo)

## Paths pré-sujos (NÃO commitar — alheios ao ciclo)
- data/outputs/setores_censitarios_2022_geo/_metadata.json
- data/reports/relatorio_pontual_censitario_base_geo.md

## Dívida operacional herdada (NÃO é regressão deste ciclo — ver QA do recorte anterior)
3 failures pré-existentes na suíte full, comprovados em tree limpo:
- test_csvs_concorrentes_legiveis[csv_path1-223] e [csv_path2-472] — drift de snapshot de CSV real local.
- test_parquet_final_respeita_guardrails_do_piloto — gate DEC-006 (regeneração de parquets paralelos é passo pós-merge).
