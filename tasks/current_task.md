# Current Task

## Bloco atual

ID: BLK-TP-08
Nome: Ingestão anti-PII das academias menores (WellHub/TotalPass) na camada de oferta
Status: aprovado (QA 2026-07-02 15:02:01 — APROVADO; suíte full 1251 passed, 1 skipped; anti-PII confirmado no parquet real 15 cols ZERO PII; mtime M1 intacto; isolamento AST ok). Pendente: Passo 6.0 do orquestrador (housekeeping_move_block.py BLK-TP-08 + commit por path).
Tipo: engenharia de dados / ingestão (camada paralela — READ-ONLY sobre o M1)
Criticidade: alta
Esteira: Block Orchestrator → Planner → [REVISÃO HUMANA OBRIGATÓRIA — anti-PII + dedup] → Builder → QA
Skill atual: QA
Próxima Skill: QA

## Resultado do Builder (2026-07-02)
- Módulo novo `src/motor_expansao/demanda_revelada/oferta_academias_menores.py` (isolado; contrato `oferta_menores_v1` + ingestão anti-PII + relatório DEDUP).
- Parquet REAL gerado (gitignored): 24.045 academias / 1.920.955 alunos → 6.785 hexes res-7; 99,2% casam com o universo; DEDUP vs concorrentes = 1.425 hexes overlap (39,4% acad / 62,7% alunos em hex coberto).
- Prova anti-PII: parquet com 15 colunas, ZERO PII (sem lat/lng/nome/cluster/total_alunos_cluster).
- Testes: 241 passed (subconjunto demanda_revelada + streamlit); ruff/mypy limpos; import ok.
- mtime dos 4 artefatos M1 INALTERADO (antes/depois). READ-ONLY sobre o M1 confirmado.
Gate humano: APROVADO pelo usuário em 2026-07-02 — D1–D4 = recomendações do Planner (dedup por hex só-relatório; aceitar coords ~1km; contrato com distribuição por Plano; só ingere, não integra ao residual)

## Objetivo
Ingerir `03_Competidores.xlsx` (24.045 academias menores WellHub/TotalPass, em NAO_ABRA/) como camada de
OFERTA agregada por hex (res-7), anti-PII na fronteira (drop Lat/Lng/Nome), materializando
`data/staging/oferta_academias_menores_h3.parquet` (gitignored/NÃO oficial) + relatório de qualidade e
DEDUP vs `concorrentes_mapeados.parquet`. NÃO recompõe `score_oportunidade_residual` nem regenera parquets
de mercado (follow-up). READ-ONLY sobre o M1.

## Autorização do usuário (2026-07-02)
- "dispare tp-08, está autorizado a editar e rodar o que precisar" → prosseguir a esteira; rodar comandos
  (pandas/pytest/etc.) sem pedir permissão por ação. O gate humano de anti-PII/dedup do Planner permanece
  (decisão de método) — apresentar decisões compactas antes do Builder.

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: opus (override +1: forense anti-PII do schema de uma planilha externa nova + escopo de DEDUP)
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-TP-08 (criada a partir de main @ HEAD 8a7cfb8).

## Paths do ciclo (commitar só estes por path)
- a definir pelo Planner (candidatos: src/motor_expansao/demanda_revelada/*, scripts/*, tests/*, data/analysis/* ou data/reports/*, docs/*)
- tasks/backlog.md (bloco BLK-TP-08), tasks/current_task.md, tasks/completed.md
- context/handoff.md, context/handoff/

## Guardrails
- §5 (READ-ONLY M1): zero recálculo de score/pesos/carteira/plano/artefatos oficiais; NÃO recompor o residual.
- DEC-012 (anti-PII POR CONSTRUÇÃO): consumir só agregado por hex; drop Lat/Lng/Nome individual na fronteira;
  zero PII em artefato/log/teste (`COLUNAS_PII_PROIBIDAS` + teste `test_zero_pii`); fonte real em NAO_ABRA/ (gitignored, nunca versionada); fixtures sintéticas.
- DEC-013 (parte 3): dedup + capacidade por tipo ANTES de qualquer integração ao residual; este bloco só INGERE + relatório de dedup.
- Isolamento: pacote da camada paralela NÃO importa de pipelines/m1, dashboard, censo_*, api.
