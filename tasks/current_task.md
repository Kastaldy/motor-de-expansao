# Current Task

## Bloco atual

ID: BLK-TP-01
Nome: Ingestão e contrato da camada de Demanda Revelada (H3, sem PII)
Status: aprovado (QA APROVADO em 2026-06-24)
Tipo: feature (nova camada paralela de dados; READ-ONLY sobre M1)
Criticidade: Alta
Esteira: Block Orchestrator → Planner → [REVISÃO HUMANA — APROVADA por Felipe Silva 2026-06-24] → Builder → QA (APROVADO)
Skill atual: QA/Quality Analyzer (concluído)
Próxima Skill: Fechamento manual — orquestrador commita por path (housekeeping já feito via helper)

## Objetivo
Materializar uma camada paralela, READ-ONLY sobre o M1, agregada em H3 e SEM PII
(`data/staging/demanda_revelada_h3.parquet`), casável por `hex_id` com
`hexagonos_mercado_mapeado.parquet`, base para os blocos sucessores (BLK-TP-02..05).
Anti-PII por construção: consome apenas dados já agregados; identificadores/coordenadas
individuais nunca são lidos para o staging nem persistidos; a agregação para H3 ocorre na entrada.

## Dependência / DEC
- **DEC-012 APROVADA por Felipe Silva em 2026-06-24** (adoção da camada de Demanda Revelada;
  licença plenamente liberada). Registrada em CLAUDE.md §8 pelo Builder.

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: sonnet
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-TP-01 (criada a partir de main @ 3c128c1).

## Paths pré-sujos (NÃO commitar — alheios ao ciclo)
- .gitignore (M), CLAUDE.md (M), tasks/backlog.md (M)
- data/raw/ibge/malha_brasil.geojson (D), data/raw/ibge/malha_uf_brasil.geojson (D)
- scripts/backtest_smartfit_scores.py (??)

## Fora de escopo
- score/pesos/artefatos M1; persistir qualquer PII; ingestão ao vivo na carga do dashboard;
  deploy ao VPS; as análises em si (sucessores BLK-TP-02..05).

## Handoff do Block Orchestrator
- Gerado em: 2026-06-24 21:59:35
- Snapshot: context/handoff/20260624-215935-block-orchestrator.md
- Handoff corrente: context/handoff.md

## Handoff do Planner
- Gerado em: 2026-06-24 22:07:08
- Snapshot: context/handoff/20260624-220708-planner.md
- Handoff corrente: context/handoff.md
- ALERTA: tarefa Alta — REVISÃO HUMANA OBRIGATÓRIA antes do Builder (LGPD/anonimização + DEC-012).
  Humano deve responder às 6 perguntas do gate e aprovar a DEC-012 rascunhada no handoff.
- R2 RESOLVIDO na investigação: fonte = dump HTML (vars JS CELLS/GYMS_PTS/SF/BANDS, já agregado,
  em NAO_ABRA/, gitignored); h3=v4.4.2 (latlng_to_cell); R6 resolvido (concorrentes_mapeados.parquet).
