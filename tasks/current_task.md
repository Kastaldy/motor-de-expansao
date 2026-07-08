# Current Task

## Bloco atual

ID: BLK-PROD-06
Nome: Relatório de movimentação concorrencial (a partir de staging)
Status: aprovado
Tipo: analytics (READ-ONLY sobre o M1; loop-safe)
Criticidade: Média
Esteira: Block Orchestrator (concluído) → Planner → Builder (concluído) → QA (APROVADO)
Skill atual: QA (concluído)
Próxima Skill: Block Orchestrator (fechamento)

## Objetivo
Materializar `data/analysis/movimentacao_concorrencial.md` a partir dos parquets de concorrentes
em `data/staging/`, com contagem por rede/UF/cidade, oferta consumida e impacto no residual.
READ-ONLY sobre o M1. Sem coleta ao vivo.

## Dados confirmados pelo BO
- `data/staging/concorrentes_mapeados.parquet`: 3.296 linhas, 28 redes, 3.179 válidos; snapshot único (2026-04-22..05-04)
- `data/staging/concorrentes_densos.parquet`: 10.165 linhas, 40 redes (inclui TotalPass/Wellhub)
- `data/staging/hexagonos_mercado_mapeado.parquet`: join via `hex_id_res7` p/ uf/cidade/oferta; data_snapshot '2026-06-11'
- SNAPSHOT ÚNICO — retrato atual sem delta (conforme decisão pré-fixada do backlog)

## Branch do ciclo
ciclo/loop-20260707-123809

## Guardrails
- §5 READ-ONLY M1: nenhuma escrita em config.py/pipelines/m1/artefatos oficiais.
- §6.1 loop-safe: sem VPS, sem rede, escreve só data/analysis (gitignored).
- loop_guard.py limpo obrigatório.
- DEC-013: coleta de concorrentes é VPS/cron — este bloco só LÊ staging.
