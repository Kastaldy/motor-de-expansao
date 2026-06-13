# Current Task

## Bloco atual

ID: BLK-API-08
Nome: Documentação ponta-a-ponta da API GeoEspacial (uso + manipulação)
Status: aprovado (condicionado ao move de housekeeping no Passo 6.0 do fechamento)
Tipo: doc
Criticidade: média
Esteira: Block Orchestrator → Planner → Builder → QA
Skill atual: QA/Quality Analyzer
Próxima Skill: Fechamento manual (orquestrador — Passo 6.0 housekeeping + commit por path)
dry_run: false

## Tiering de modelo (Passo 4) — Média
- Block Orchestrator: sonnet
- Planner: sonnet
- Builder: sonnet
- QA: opus 4.8 (sempre)

## Objetivo
Criar `docs/api_geoespacial_uso.md` como fonte única de USO ponta-a-ponta da API
GeoEspacial (visão geral/arquitetura, autenticação por token, endpoints `GET /health`
e `POST /api/v1/analisar` em JSON e PDF, exemplos `curl` + fluxo do bot Telegram,
tabela de erros, operação/env `API_*` e ponteiros — linkando, não duplicando, os docs
existentes). READ-ONLY sobre o M1.

## Branch do ciclo
ciclo/BLK-API-08 (a partir de main @ e969712)

## Paths do ciclo (commit por path no fechamento)
- docs/api_geoespacial_uso.md (novo — alvo principal)
- tasks/current_task.md
- tasks/completed.md
- tasks/backlog.md (stub via helper no 6.0)
- context/handoff.md + context/handoff/

## Fora de escopo (invioláveis)
- score_priorizacao/hex_score_estrutural/pesos/artefatos oficiais do M1 (READ-ONLY)
- código de produção da API (`src/motor_expansao/api/`) — doc não altera código
- método de interseção setor_censitario_intersecao_area_1p5km / raio 1.5 km
- GUARDRAIL VPS §6: nenhum comando no servidor sem confirmação humana por comando

## Worktree pré-sujo (não tocar)
- data/raw/ibge/malha_brasil.geojson (D) — não relacionado
- data/raw/ibge/malha_uf_brasil.geojson (D) — não relacionado
