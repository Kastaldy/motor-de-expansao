# Current Task

## Bloco atual

ID: BLK-MAP-01
Nome: Filtro individual de concorrentes nos overlays do Mapa Territorial
Status: aprovado (QA 2026-06-11)
Tipo: feature
Criticidade: média
Esteira: Block Orchestrator → Planner → [REVISÃO HUMANA leve — estilo do controle de UI] → Builder → QA
Skill atual: QA
Próxima Skill: —

## Gate humano leve — APROVADO por Felipe/usuário em 2026-06-11
- D1 = A: st.multiselect separado de redes (condicional ao overlay "concorrentes").
- D2 = A: seleção vazia esconde todos os concorrentes (competitors_df_filtered=None).
- D3 = A: lista = todas as redes do competitors_df carregado (estável).
- Builder executa o plano do Planner com a premissa D1=A/D2=A/D3=A (sem reabertura).
dry_run: false

## Objetivo
Permitir filtrar concorrentes individualmente por rede no Mapa Territorial (pins, clusters,
legenda e tooltips refletindo apenas as redes selecionadas), de forma puramente visual e
READ-ONLY sobre o M1 (sem recalcular score/carteira/plano/residual nem alterar artefatos oficiais).

## Tiering de modelo (Passo 4) — Média
- Block Orchestrator: sonnet
- Planner: sonnet
- Builder: sonnet
- QA: opus 4.8 (sempre)

## Gate humano (REVISÃO HUMANA leve — definido no backlog)
Após o Planner, PARAR para o humano escolher D1 (estilo do controle), D2 (semântica de seleção
vazia) e D3 (escopo da lista de redes) antes do Builder.

## Branch do ciclo
ciclo/BLK-MAP-01 (a partir de ciclo/BLK-EST-01 @ d4762d2 — carrega o registro do bloco no backlog)

## Escopo permitido (do backlog)
- src/motor_expansao/dashboard/pages.py (novo controle de UI em render_mapa_territorial; aplicar filtro em competitors_df antes de build_unified_map_figure)
- src/motor_expansao/dashboard/components.py (adaptar render_competitor_legend; coerência de pins/clusters/tooltips/legenda)
- tests/integration/test_streamlit_app.py e/ou unidade de components

## Fora de escopo (invioláveis)
- recálculo/alteração de score_priorizacao, hex_score_estrutural, carteira, plano, residual, SAM, canibalização ou artefatos M1 (READ-ONLY; filtragem puramente visual)
- overlay de Ultra, âncoras de domínio, overlay descartados_5k (BLK-FIX-11 intocado)
- quebrar otimizações de performance do mapa (carga lazy por UF, fonte enxuta, caps de pontos)
- dependência de API ao vivo

## Paths pré-sujos (NÃO commitar — alheios ao ciclo)
- data/outputs/setores_censitarios_2022_geo/_metadata.json
- data/reports/relatorio_pontual_censitario_base_geo.md
