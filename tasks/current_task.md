# Current Task

## Bloco atual

ID: BLK-VIAB-03
Nome: Batch de viabilidade sobre candidatos limpos (coordless) + ranking por margem de segurança
Status: aguardando QA
Tipo: feature (entrega o coração do produto de viabilidade)
Criticidade: alta
Esteira: Block Orchestrator → Planner → Builder → QA (autônoma no loop)
Skill atual: Builder (concluído)
Próxima Skill: QA

## Objetivo
Rodar `analisar_viabilidade_ponto` para cada candidato limpo (VIAB-01) com a faixa de
demanda-premissa (VIAB-02), em modo coordless (setores_df=None), e materializar
`data/staging/viabilidade_candidatos.parquet` + relatório ranqueado por margem de segurança.

## Dependências (ambas concluídas)
- BLK-VIAB-01: data/staging/imoveis_candidatos_limpos.parquet (23 candidatos)
- BLK-VIAB-02: data/staging/demanda_premissa_por_tier.parquet (5 tiers, N=112)

## Branch do ciclo
ciclo/loop-20260707-123809

## Paths do ciclo
- src/motor_expansao/dimensionamento/batch_viabilidade.py (novo módulo)
- tests/unit/dimensionamento/test_batch_viabilidade.py (testes novos)
- data/staging/viabilidade_candidatos.parquet (gitignored — NÃO commitado)
- data/analysis/viabilidade_candidatos.md (gitignored — NÃO commitado)
- tasks/current_task.md, tasks/completed.md, tasks/backlog.md (fechamento)
- context/handoff.md, context/handoff/

## Guardrails
- §5 READ-ONLY M1: nenhuma escrita em config.py/pipelines/m1/artefatos oficiais.
- DEC-009: demanda SÓ como premissa explícita (faixa p10/p50/p90 por tier) — NUNCA prevista por lat/lng.
- viabilidade_ponto.py INTOCADO (reusa sem modificar).
- Modo COORDLESS: setores_df=None → sem rede/catchment, sem fetch HTTP.
- Saída gitignored.
- Sem rede, sem VPS.

## Tiering de modelo — Alta
- Block Orchestrator: sonnet
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)
