# Current Task

## Bloco atual

ID: BLK-TP-08-FU
Nome: Re-ingestão das academias menores com rótulo de rede (fecha o dado para o BLK-TP-06-FU1)
Status: aprovado (QA 2026-07-02)
Tipo: engenharia de dados / re-ingestão (camada paralela — READ-ONLY sobre o M1)
Criticidade: alta
Esteira: Block Orchestrator → Planner → [REVISÃO HUMANA OBRIGATÓRIA — anti-PII + classificação de rede] → Builder → QA
Skill atual: QA (concluído — APROVADO)
Próxima Skill: Fechamento manual (orquestrador: housekeeping `BLK-TP-08-FU` no backlog + commit por path)
Gate humano: APROVADO pelo usuário em 2026-07-02 — A) matching token word-boundary + lista curada; B) rede <3 filiais→independente; C) formato longo; D) capacidade=mediana, flag_confiavel N≥10

## Objetivo
Re-ingerir `03_Competidores.xlsx` classificando cada academia numa CATEGORIA DE REDE (`rede_menor`) na
FRONTEIRA anti-PII (deriva a rede do `Nome_Academia` e DESCARTA o nome), produzindo: (a) oferta agregada
por hex COM quebra por rede (habilita dedup FINO vs `concorrentes_mapeados` por rede) e (b) uma tabela de
MÉDIA de alunos/unidade POR REDE (a partir de `Alunos_Academia` das filiais classificadas). Fecha as 2
lacunas de dado que pausaram o BLK-TP-06-FU1. READ-ONLY sobre o M1.

## Por que este bloco (contexto do gate humano 2026-07-02)
O BLK-TP-06-FU1 (re-validação do residual com candidatos A=incluir menores na saturação + C=capacidade
por rede) foi PAUSADO porque:
1. o parquet do TP-08 NÃO tem rótulo de rede (nome dropado no anti-PII) → dedup fino por rede impossível;
2. médias por rede só existem para 2 de 28 (SkyFit 2.295, Engenharia 3.283); Smart/Blue/Panobianco ausentes.
Felipe decidiu FECHAR O DADO PRIMEIRO. Este bloco resolve ambos: a classificação de rede na fronteira dá
o rótulo (para dedup) E permite calcular a média por rede das filiais presentes no dump.

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: opus (override +1: classificação de rede a partir de nome cru sob anti-PII — decisão delicada)
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-TP-08-FU (criada a partir de main @ HEAD 3ab5e8c).

## Paths do ciclo (commitar só estes por path)
- src/motor_expansao/demanda_revelada/classificacao_rede_menor.py (novo)
- src/motor_expansao/demanda_revelada/__init__.py (aditivo)
- tests/unit/demanda_revelada/test_classificacao_rede_menor.py (novo), tests/fixtures/ (fixture sintética, se necessária)
- data/reports/scratch/rede_menor_classificacao_qualidade.md (gitignored)
- docs/modelo_mercado_hexagonos.md (aditivo, se aprovado)
- (parquets data/staging/oferta_academias_menores_rede_h3.parquet e capacidade_media_por_rede.parquet são gitignored — NÃO commitados)
- tasks/backlog.md (novo bloco BLK-TP-08-FU), tasks/current_task.md, tasks/completed.md
- context/handoff.md, context/handoff/

## Bloco ad-hoc
Derivado da conversa/gate. No fechamento: Passo 6.0 é no-op (ad-hoc) → resumo vai a completed.md via 6.2;
adicionar bloco BLK-TP-08-FU ao backlog durante o ciclo; ao final, desbloquear o BLK-TP-06-FU1 (retomável).

## Guardrails
- §5 (READ-ONLY M1): zero recálculo de score/pesos/carteira/plano/artefatos oficiais; NÃO recompor o residual.
- DEC-012 (anti-PII POR CONSTRUÇÃO): a rede é classificada na FRONTEIRA e o `Nome_Academia`/Lat/Lng são
  DESCARTADOS na entrada; `rede_menor` é uma CATEGORIA (não o nome); zero PII em artefato/log/teste; fonte
  real em NAO_ABRA/ (gitignored, nunca versionada); fixtures sintéticas.
- DEC-013 (parte 3): dedup + capacidade por tipo é exatamente o que este bloco habilita (ainda sem integrar ao residual).
- Isolamento: pacote da camada paralela NÃO importa de pipelines/m1, dashboard, censo_*, api.
