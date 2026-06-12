# Current Task

## Bloco atual

ID: BLK-UI-02
Nome: Follow-up UX do dashboard (coord destaque, tooltip cortado, densificação por zoom)
Status: aprovado
Tipo: feature (UX/UI)
Criticidade: alta
Esteira: Block Orchestrator → Planner → [REVISÃO HUMANA do plano] → Builder → QA
Skill atual: QA (concluído)
Próxima Skill: Fechamento manual

## Objetivo
Endereçar 3 observações de UX levantadas por Felipe/Vini ao testar o BLK-UI-01:
(1) destacar o campo de busca por coordenada (hoje camuflado na sidebar);
(2) reduzir o corte do tooltip do hexágono na borda inferior do mapa;
(3) dar densidade total ao mapa em recortes pequenos — a compactação (cap MAP_POINT_LIMIT
+ downsample) hoje persiste mesmo com zoom próximo, pois não é ciente de zoom.

## Observações do usuário (origem)
- O menu de seleção fica camuflado ao inserir coordenadas — destacá-lo.
- Hover sobre hexágono mostra dados, mas parte inferior fica oculta (recorte na borda do mapa).
- O mapa territorial compacta os pontos para otimizar visualização em área larga, mas a
  compactação continua em áreas menores, impedindo a visualização ideal.

## Decisão de produto pré-fixada pelo usuário (2026-06-12)
- Nº3 (densificação): abordagem aprovada = **filtro de município/área** — ao estreitar o
  escopo, o cap passa a cobrir aquela área com densidade total, preservando o guardrail
  Bloco 6 (anti-OOM client-side). O Planner detalha file:line e o humano confirma no gate.

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: sonnet
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Gate humano
Esteira Alta exige REVISÃO HUMANA do plano do Planner antes do Builder.

## Branch do ciclo
ciclo/BLK-UI-02 (a partir de ciclo/BLK-UI-01 @ HEAD; UI-01 e UI-02 ainda não mergeados em main — stack)

## Âncoras no código (confirmadas na investigação)
- #1 coord: `render_coord_search` em src/motor_expansao/dashboard/pages.py:524-529
- #2 tooltip: `_shared_map_tooltip` (14 linhas) / `_hybrid_compact_tooltip` (8 linhas) em
  src/motor_expansao/dashboard/components.py:1047-1104 (limitação de recorte do pydeck no iframe)
- #3 cap/downsample: `_downsample_map_index` (components.py:1309) + MAP_POINT_LIMIT/MAP_POINT_LIMIT_LARGE
  (constants.py:98-103); builders `build_unified_map_figure`/hybrid em components.py; `resolve_map_view`

## Escopo permitido
- src/motor_expansao/dashboard/ (pages.py, components.py, utils.py, constants.py visuais)
- preservar carga lazy por UF (Bloco 4), render lazy de abas (Bloco 5), fonte de mapa enxuta (Bloco 6)
- testes correspondentes

## Fora de escopo (invioláveis)
- recalcular qualquer score (score_priorizacao, score_setor_2022_calibrado, residual, SAM) ou artefatos M1
- remover o cap anti-OOM do Bloco 6 sem o mecanismo de escopo (densificação só dentro de recorte estreito)
- recolocar dependência de API ao vivo no dashboard de produção
- quebrar contratos de performance já entregues

## Paths pré-sujos (NÃO commitar — alheios ao ciclo)
- data/outputs/setores_censitarios_2022_geo/_metadata.json
- data/reports/relatorio_pontual_censitario_base_geo.md

dry_run: false
