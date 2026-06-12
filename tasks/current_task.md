# Current Task

## Bloco atual

ID: BLK-FIX-12
Nome: Logos das concorrentes não aparecem no PDF do Relatório (API/bot; verificar dashboard)
Status: aprovado (QA APROVADO 2026-06-12 — pronto p/ housekeeping + merge)
Tipo: bug
Criticidade: média
Esteira: Block Orchestrator → Planner → Builder → QA
Skill atual: QA (concluído)
Próxima Skill: Fechamento manual (housekeeping move BLK-FIX-12 + merge pelo orquestrador)
dry_run: false

## Tiering de modelo (Passo 4) — Média
- Block Orchestrator: sonnet
- Planner: sonnet
- Builder: sonnet
- QA: opus 4.8 (sempre)

## Objetivo
Fazer o PDF do Relatório Pontual Censitário (página Concorrentes) renderizar a logo
correta por rede (sigla só quando a rede não tem asset), tanto na API/bot quanto no
dashboard. Diagnóstico: `data/Logos/` ausente no VPS + serviço `api` sem
`API_COMPETITORS_LOGOS_DIR`/volume + pacote não-editável resolvendo default para
site-packages. READ-ONLY sobre o M1.

## Branch do ciclo
ciclo/BLK-FIX-12 (a partir de main @ 37c7409)

## Fora de escopo (invioláveis)
- score_priorizacao/hex_score_estrutural/pesos/artefatos oficiais do M1 (READ-ONLY)
- método de interseção setor_censitario_intersecao_area_1p5km / raio 1.5 km
- GUARDRAIL VPS §6: nenhum comando no servidor sem confirmação humana por comando

## Worktree pré-sujo (não tocar)
- data/raw/ibge/malha_brasil.geojson (D) — não relacionado
- data/raw/ibge/malha_uf_brasil.geojson (D) — não relacionado
