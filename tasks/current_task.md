# Current Task

## Bloco atual

ID: BLK-MAP-02
Nome: Filtro de marcas de concorrentes do mapa em menu expansível (fechado por padrão)
Status: aprovado (QA)
Tipo: feature (UI)
Criticidade: baixa
Esteira: Block Orchestrator → Builder → QA (APROVADO)
Skill atual: Fechamento (orquestrador) CONCLUÍDO
Skill anterior: QA (APROVADO 2026-07-08)
Próxima Skill: merge ciclo/BLK-MAP-02 -> integracao/map02-relmun05-06 (orquestrador), depois ciclo BLK-RELMUN-05

## Objetivo
Envolver o st.multiselect("Redes de concorrentes", ...) (pages.py:4382, em render_mapa_territorial)
num st.expander(..., expanded=False) para o filtro nascer fechado, preservando a lógica BLK-MAP-01
(seleção vazia => esconde concorrentes), key, default e format_func. READ-ONLY sobre o M1.

## Fluxo de branch (integração — decisão de Vinicius 2026-07-08)
- Branch do ciclo: ciclo/BLK-MAP-02, ramificada da SECUNDÁRIA integracao/map02-relmun05-06 (não da main).
- Ao fechar (QA aprovado + commit por path), o orquestrador MERGEIA ciclo/BLK-MAP-02 -> integracao/map02-relmun05-06.
- PR para main só após os 3 ciclos (MAP-02, RELMUN-05, RELMUN-06) aprovados e mergeados na secundária.

## Tiering de modelo (Passo 4) — Baixa
- Block Orchestrator: haiku
- Builder: sonnet
- QA: opus 4.8 (sempre)
- Nota: incluo QA mesmo sendo Baixa (a esteira padrão Baixa é BO->Builder) porque no fluxo de
  integração não há revisão humana por ciclo até o PR final — QA é o gate de qualidade.

## Paths do ciclo (commit por path — NUNCA git add -A)
- src/motor_expansao/dashboard/pages.py
- tests/integration/test_streamlit_app.py (se algum assert travar label/posição)
- tasks/current_task.md, tasks/completed.md, tasks/backlog.md (fechamento)
- context/handoff.md, context/handoff/

## Guardrails
- §5 READ-ONLY M1: zero recálculo/alteração de score/pesos/carteira/plano/artefatos.
- Preservar key="mapa_territorial_redes_concorrentes", options/default=_all_redes, format_func,
  e a lógica BLK-MAP-01 (seleção vazia => competitors_df_filtered=None => esconde concorrentes).
- Não tocar lógica de filtragem/legenda/cluster; COMPETITOR_BRANDS; nenhum artefato M1.
