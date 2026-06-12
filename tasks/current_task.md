# Current Task

## Bloco atual

ID: BLK-UI-03
Nome: Ajustes finos de UX (reverter coord, tooltip meio-termo, preview menor [BLK-FIX-10], destaque do seletor de abas)
Status: aprovado (QA — Opus 4.8, 2026-06-12; suíte FULL 696 passed/1 skipped/3 failed pré-existentes provados; D1..D4 aderentes; Bloco 5 byte-idêntico; BLK-FIX-10 pronto para mover via helper no fechamento)
Tipo: feature (UX/UI)
Criticidade: alta
Esteira: Block Orchestrator → Planner → [REVISÃO HUMANA do plano] → Builder → QA
Skill atual: Builder concluído (Opus — D1..D4 implementados; gate humano aprovado por Felipe 2026-06-12)
Próxima Skill: QA (opus 4.8)

## Objetivo
Quatro ajustes de UX no dashboard (READ-ONLY M1), a partir do teste do BLK-UI-02:
(1) reverter a alteração do campo de coordenadas feita no BLK-UI-02 (remover a caixa `st.sidebar.info`,
    voltar ao heading+caption simples de `render_coord_search_sidebar`);
(2) tooltip do hexágono: buscar um meio-termo entre a fonte/espaçamento ANTERIOR (default, sem fontSize)
    e a ATUAL do BLK-UI-02 (11px/6px8px/260px/1.25) — algo intermediário (~12-13px);
(3) [FECHA BLK-FIX-10] diminuir a proporção da pré-visualização dos estudos no Relatório Pontual
    Censitário (largura/altura controladas em pages.py), SEM afetar o PDF exportado;
(4) destacar melhor o menu de seleção de telas (o st.segmented_control entre Visão Executiva |
    Mapa Territorial | Expansão de Domínio | Carteira e Plano) — SÓ estilo, sem mexer na lógica de
    render lazy (Bloco 5).

## Observações do usuário (origem, 2026-06-12)
- Na sidebar, reverter a alteração no campo de coordenadas em BLK-UI-02.
- No tooltip, buscar um meio termo entre a fonte/espaçamento anterior e a atual.
- Na região de Relatório Pontual Censitário diminuir a proporção da pré-visualização dos estudos,
  como indicado em BLK-FIX-10.
- Deixar melhor destacado o menu de seleção de telas na página de conteúdo (Visão Executiva |
  Mapa Territorial | Expansão de Domínio | Carteira e Plano).

## Bloco do backlog fechado por este ciclo
- BLK-FIX-10 (Baixa) — "Diminuir tamanho da pré-visualização dos estudos" (item nº3). No fechamento,
  mover via scripts/housekeeping_move_block.py.

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: sonnet
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Gate humano
Esteira Alta exige REVISÃO HUMANA do plano do Planner antes do Builder.

## Branch do ciclo
ciclo/BLK-UI-03 (a partir de ciclo/BLK-UI-02 @ HEAD; UI-01/UI-02/UI-03 ainda não mergeados — stack)

## Âncoras no código (a confirmar pelo BO/Planner)
- #1 coord: `render_coord_search_sidebar` em src/motor_expansao/dashboard/pages.py (st.sidebar.info do BLK-UI-02 a reverter)
- #2 tooltip: `_shared_map_tooltip` / `_hybrid_compact_tooltip` em src/motor_expansao/dashboard/components.py (style dict)
- #3 preview: container/`st.image` do preview no Relatório Pontual Censitário em pages.py (BLK-FIX-10) — NÃO afetar PDF
- #4 seletor de abas: `render_tab_selector` (st.segmented_control) — Bloco 5 render lazy, SÓ estilo (CSS em inject_styles)

## Escopo permitido
- src/motor_expansao/dashboard/ (pages.py, components.py, constants.py visuais)
- testes correspondentes

## Fora de escopo (invioláveis)
- recalcular qualquer score (score_priorizacao, score_setor_2022_calibrado, residual, SAM) ou artefatos M1
- alterar a LÓGICA de render lazy de abas (Bloco 5) — só estilo do seletor
- alterar o PDF exportado do Relatório Pontual Censitário (item nº3 é só o preview na tela)
- quebrar contratos de performance (Bloco 4/5/6) ou recolocar dependência de API ao vivo

## Paths pré-sujos (NÃO commitar — alheios ao ciclo)
- data/outputs/setores_censitarios_2022_geo/_metadata.json
- data/reports/relatorio_pontual_censitario_base_geo.md

dry_run: false
