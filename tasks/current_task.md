# Current Task

## Bloco atual

ID: BLK-RELMUN-04
Nome: Relatório Municipal em lote — gerar um relatório por município quando vários selecionados
Status: aprovado (APROVADO COM RESSALVAS — revisão visual humana da UI nova pendente antes do merge)
Tipo: feature (UI/visualização/relatório — READ-ONLY sobre o M1)
Criticidade: média
Esteira: Block Orchestrator → Planner → Builder → QA
Skill atual: Ciclo fechado (housekeeping 6.0 OK — bloco movido p/ completed.md via helper, --check verde; commit por path na branch ciclo/BLK-RELMUN-04)
Próxima Skill: Merge pelo humano (revisar branch ciclo/BLK-RELMUN-04 + revisão visual da UI multi-município no dashboard antes do merge)

## Objetivo
Ao selecionar mais de um município, a função de gerar Relatório Municipal deve gerar um relatório
PDF para CADA município selecionado. Após a geração, aparece um botão de download por município,
rotulado com o nome do município a que se refere.

## Decisões de produto (coletadas de Vinicius, 2026-07-02, antes do ciclo)
- GATILHO: geração SOB DEMANDA por BOTÃO ("Gerar Relatórios (N)"), com indicador de progresso;
  os botões de download aparecem DEPOIS da geração. (Evita regenerar N PDFs a cada rerun.)
- ONDE: AMBOS os pontos de geração — `render_relatorio_municipal_download_topo` (topo) e
  `render_relatorio_municipal_expander` (Mapa Territorial).
- Comportamento de 1 município: preservado (não regredir o fluxo atual).

## Tiering de modelo (Passo 4) — Média (com override)
- Block Orchestrator: sonnet
- Planner: opus (override +1: reestrutura o gate "1 município" em DOIS pontos de UI com session_state)
- Builder: opus (override +1: expander hoje auto-gera; risco de regressão no fluxo de produção)
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-RELMUN-04 (criada a partir de ciclo/BLK-RELMUN-03 @ HEAD — empilha sobre o RELMUN-03
já APROVADO e aguardando merge humano; feature é em pages.py, disjunta do relatorio_municipal.py do 03).

## Paths do ciclo (commitar só estes por path)
- src/motor_expansao/dashboard/pages.py (alvo principal — os 2 pontos de geração)
- tests/ (testes do fluxo multi-município — a definir pelo Planner)
- tasks/backlog.md (bloco BLK-RELMUN-04), tasks/current_task.md, tasks/completed.md
- context/handoff.md, context/handoff/

## Guardrails
- §5 (READ-ONLY M1): zero recálculo de score/pesos/carteira/plano/artefatos oficiais.
- Reusa a geração existente (`agregar_municipio`, `render_mapas_municipio`,
  `gerar_payloads_download_relatorio_municipal`) — não altera `relatorio_municipal.py` (motor do PDF).
- Sem dependência de rede nova além da já existente (tiles do basemap, DEC-011).
- Marca d'água anti-PII + `set_compression(False)` + estrutura do PDF mantidos.
