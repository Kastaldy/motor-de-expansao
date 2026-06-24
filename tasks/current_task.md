# Current Task

## Bloco atual

ID: BLK-RELMUN-02
Nome: "Bairros por Zona" com nomes reais de bairro (resolve o D9 do BLK-RELMUN-01)
Status: APROVADO COM RESSALVAS (QA 2026-06-24) — CICLO FECHADO (housekeeping feito via helper; commit d6f259f na branch ciclo/BLK-RELMUN-02); aguardando merge humano
Tipo: feature (enriquecimento da base geo + mudança de página do Relatório Municipal; READ-ONLY sobre M1)
Criticidade: alta (confirmada pelo Block Orchestrator — READ-ONLY M1; enriquecimento de base geo + mudança de página do relatório exigem gate humano)
Esteira: Block Orchestrator → Planner → [REVISÃO HUMANA — gate: escolha da direção A/B/C] → Builder → QA
Skill atual: QA/Quality Analyzer (concluído)
Próxima Skill: Fechamento manual (housekeeping_move_block.py BLK-RELMUN-02 --date 2026-06-24 + --check; merge humano)
Veredito QA: APROVADO COM RESSALVAS. Suíte serial 1095 passed / 1 skipped; ruff check / mypy / import ok; 9 páginas / /Count 9; READ-ONLY M1 confirmado; coexistência do Relatório Pontual intocada. Ressalva LEVE não bloqueante: ruff format --check reporta os 4 arquivos tocados como "would reformat" — VERIFICADO pré-existente (idêntico nas versões HEAD); gate do projeto é ruff check (passa). xdist (-n auto) falha por ambiente (Windows/Py3.14 execnet), não por código. Pendência operacional pós-merge: re-materializar malha geo para popular nome_bairro em produção.
Direção escolhida (gate humano): A2 — APROVADO POR Vinicius EM 2026-06-24 (re-materializa a malha geo com nome_bairro; relatório lê a partição on-demand; cadeia hot do dashboard intocada).

## Objetivo
Dar à página "Bairros por Zona" do Relatório Municipal a lista de bairros reais agrupados por
zona (Âncora central / Flancos laterais / Cerco), fiel ao template, com fallback gracioso,
sem regressão do Relatório Pontual Censitário nem do M1 (READ-ONLY).

## Tiering de modelo (Passo 4) — Alta (provisório)
- Block Orchestrator: sonnet
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-RELMUN-02 (criada a partir de main @ 3c128c1).

## Paths pré-sujos (NÃO commitar — alheios ao ciclo)
- (worktree estava limpo no início do ciclo)

## Fora de escopo
- score/pesos/artefatos M1; alterar o Relatório Pontual Censitário (coexistência);
  dependência de API ao vivo em lote na carga do dashboard; quebrar contratos de performance
  (Blocos 4–6).