# Current Task

## Bloco atual

ID: BLK-ATR-01-FU1
Nome: Cruzar a base densa de concorrentes com as unidades reais do NAO_ABRA (aferição de precisão/overlap)
Status: aprovado — housekeeping corrigido (--check OK); ciclo pronto para fechamento
Tipo: feature (análise/validação)
Criticidade: média
Esteira: Block Orchestrator → Planner → Builder → QA (autônoma no loop)
Skill atual: QA (APROVADO) → Fechamento (commit por path + merge)
Próxima Skill: Fechamento — commit por path + merge (nenhuma pendência remanescente)

## Objetivo
Aferir a precisão/cobertura da base densa de concorrentes (BLK-ATR-01) contra as unidades reais de
estabelecimento do NAO_ABRA/ (01_SmartFit.xlsx e 03_Competidores.xlsx), reportando recall, precisão-proxy
e overlap por rede em relatório em data/analysis/ (gitignored), READ-ONLY sobre o M1.

## Tiering de modelo (Passo 4) — Média
- Block Orchestrator: sonnet
- Planner: sonnet
- Builder: sonnet
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/loop-20260707-123809 (branch do loop autônomo atual)

## Paths do ciclo (commit por path — NUNCA git add -A)
- src/motor_expansao/demanda_revelada/ (módulo de análise — apenas arquivos novos do FU1)
- tests/ (testes novos do FU1)
- data/analysis/ (relatório gitignored — não commitado)
- tasks/current_task.md, tasks/completed.md, tasks/backlog.md (fechamento)
- context/handoff.md, context/handoff/

## Guardrails
- §5 READ-ONLY M1: zero recálculo de score/pesos/carteira/plano/artefatos oficiais.
- DEC-012: lê SÓ dado de estabelecimento (lat/long/rede/nome de unidade); NUNCA o dump pessoal totalpass_final*.html.
- Zero PII persistida em disco/log.
- Isolamento: demanda_revelada/, sem import de pipelines/m1, dashboard, censo_*, api, config.py.
- data/staging/concorrentes_densos.parquet só LIDO (não reescrito).
