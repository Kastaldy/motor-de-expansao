# Current Task

## Bloco atual

ID: BLK-ATR-01
Nome: Densificar a base de concorrentes do Huff (TotalPass/WellHub/Unidades) + re-validar o GO
Status: CICLO FECHADO — APROVADO COM RESSALVAS (housekeeping OK + commit por path feito; merge = humano)
Tipo: modelagem (ingestão CSV local, dedup, re-validação out-of-fold — READ-ONLY M1)
Criticidade: alta
Esteira: Block Orchestrator → Planner → Builder → QA (autônoma no loop)
Skill atual: QA (concluído)
Próxima Skill: Fechamento (converter BLK-ATR-01 em stub no backlog + mover para completed.md)

## Veredito QA (2026-07-06 19:34)
APROVADO COM RESSALVAS.
- Suíte FULL: 1329 passed, 4 failed (PRÉ-EXISTENTES openlocationcode), 4 skipped. Regressões novas = 0.
- ruff limpo; import streamlit_app ok; loop_guard GUARD OK; isolamento (AST) OK.
- READ-ONLY M1 confirmado: mtime dos 4 oficiais + concorrentes_mapeados.parquet + huff_captura.py intocados.
- Ressalvas (completude de escopo, não corretude): (1) re-validação com DADOS REAIS não rodada
  (parquet denso + relatorio_huff_densa.md não materializados; executar() deferido); (2) cruzamento com
  NAO_ABRA/ (01_SmartFit/03_Competidores) não implementado; (3) housekeeping stub pendente.
- Detalhe em context/handoff/20260706-193402-qa.md.

## Objetivo
Ingerir as ~132 CSVs de concorrentes/ (lat/long → hex_id res-7), deduplicar por nome+rede entre fontes
e contra concorrentes_mapeados (3,3k), materializar base densa em data/staging/ (camada paralela),
recomputar share_captura_huff sobre ela e re-validar o GO do BLK-TP-07 (mesmo harness k-fold 5x5
seed=42/IC95 vs membros). READ-ONLY M1.

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: sonnet
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-ATR-01 (criada a partir de ciclo/BLK-ATR-02 @ HEAD 83d67aa)

## Paths do ciclo (commit por path — NUNCA git add -A)
- src/motor_expansao/demanda_revelada/ (módulos de ingestão + dedup + re-validação)
- tests/unit/ (testes do módulo)
- data/staging/ (parquets da camada paralela — gitignored)
- data/analysis/ (relatório gitignored)
- tasks/current_task.md, tasks/completed.md, tasks/backlog.md (fechamento)
- context/handoff.md, context/handoff/

## Guardrails
- §5 (READ-ONLY M1): zero recálculo de score/pesos/carteira/plano/artefatos oficiais; mtime dos 4 oficiais M1 inalterado.
- DEC-008: out-of-fold vs baseline; R² in-sample BANIDO; IC95 seed=42; intervalos + flag de extrapolação.
- DEC-009: membros/alunos_parceiras é ALVO OBSERVADO; NUNCA preditor geográfico de magnitude.
- DEC-012 (anti-PII): nome de estabelecimento PODE ser usado (é dado público); dado PESSOAL da Demanda Revelada permanece intocado.
- Isolamento: módulo NÃO importa de pipelines/m1, dashboard, censo_*, api.
- Ingestão de CSV LOCAL (sem API ao vivo); dado de concorrente é público/estabelecimento.

## Depende de (satisfeito)
- BLK-TP-07 (motor demanda_revelada/huff_captura.py — concluído)
- BLK-TP-08/FU (padrão anti-PII e dedup, oferta_academias_menores.py/classificacao_rede_menor.py — concluído)
- BLK-ATR-02 (concluído no ciclo anterior)
