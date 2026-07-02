# Current Task

## Bloco atual

ID: BLK-TP-03
Nome: Vazio competitivo do concorrente low-cost (feature/overlay)
Status: aprovado (QA em 2026-07-02 — APROVADO; housekeeping 6.0 OK; commit por path na branch ciclo/BLK-TP-03)
Tipo: feature (visualização/análise — READ-ONLY sobre o M1)
Criticidade: média
Esteira: Block Orchestrator → Planner → [REVISÃO HUMANA — produto/UX: Opção A aprovada] → Builder → QA
Skill atual: Ciclo fechado (housekeeping 6.0 OK; commit por path na branch ciclo/BLK-TP-03)
Próxima Skill: Merge pelo humano (revisar branch ciclo/BLK-TP-03)

## Objetivo
Identificar hexes com demanda paga relevante a >5km do concorrente low-cost de referência e SEM
unidade dele no hex — tese de entrada low-cost mais limpa (demanda comprovada, concorrente direto
ausente). Reproduzível, READ-ONLY sobre o M1. Decisão de produto no gate: lista/parquet apenas vs.
overlay no Mapa Territorial.

## Tiering de modelo (Passo 4) — Média
- Block Orchestrator: sonnet
- Planner: opus (override +1: gate de produto/UX overlay-vs-parquet + guardrails anti-PII DEC-012)
- Builder: sonnet
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-TP-03 (criada a partir de main @ HEAD).

## Paths do ciclo (commitar só estes por path)
- a definir pelo Planner (candidatos: src/motor_expansao/demanda_revelada/*, scripts/*, tests/*)
- tasks/backlog.md (bloco BLK-TP-03), tasks/current_task.md, tasks/completed.md
- context/handoff.md, context/handoff/

## Guardrails
- §5 (READ-ONLY M1): zero recálculo de score/pesos/carteira/plano/artefatos oficiais.
- DEC-012 (anti-PII): consumir só camada agregada; zero PII em artefato/log/teste; fonte real em NAO_ABRA/ (gitignored).
- Sem dependência de rede nova; camada paralela isolada (não importa de pipelines/m1, censo_*, dashboard core do M1).
