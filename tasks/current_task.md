# Current Task

## Bloco atual

ID: BLK-TP-07
Nome: Huff/gravitacional de captura de concorrentes com demanda observada (reabertura da Camada 2 do BLK-DIM)
Status: CICLO FECHADO — APROVADO COM RESSALVAS (housekeeping OK + commit por path feito; merge = humano)
Tipo: modelagem (captura/share gravitacional — validação out-of-fold, READ-ONLY sobre o M1)
Criticidade: alta
Esteira: Block Orchestrator → Planner → [APROVAÇÃO HUMANA — modelagem] → Builder → QA
Skill atual: Fechamento (orquestrador) CONCLUÍDO
Próxima Skill: revisão + merge da branch ciclo/BLK-TP-07 pelo humano (6.b). Sem dry-run (não tocou orquestração).

## Veredito REAL do Builder (out-of-fold, seed=42)
GO (âncora R²): R²_oof_log = +0.4391 IC95 [+0.4251, +0.4523] (> 0.05, IC > 0) E supera o baseline
geométrico (R²_base_geo = +0.2922) ⇒ a distância agrega. β_selecionado = 0.5 (out-of-fold);
rho_oof = +0.4354 IC95 [+0.4213, +0.4491]; R²_insample (auditoria, banido) = +0.4392; n_join =
16.575 (~1.07% do universo, viés SP/MG/RJ). Sensibilidades D1b (capacidade, +0.357) e D4c (Ultra,
+0.4755) reportadas FORA do gate. Integração ao residual/carteira = BLK-TP-09 (fora deste bloco).
Validações: novos testes 11 passed; subset demanda_revelada 96 passed; import streamlit ok; ruff+mypy
limpos; mtime dos 4 oficiais M1 inalterado; isolamento AST sem imports proibidos. READ-ONLY M1.

## Objetivo
Modelar a captura/share gravitacional (Huff) de um ponto candidato — atratividade × distância aos
concorrentes mapeados, com saturação e canibalização da rede Ultra — e validá-la out-of-fold contra a
demanda OBSERVADA da Demanda Revelada (`membros`/`alunos_parceiras`) sob a disciplina DEC-008. Veredito
honesto GO/NO-GO em `data/analysis/` (gitignored). READ-ONLY sobre o M1.

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: opus (override +1: forense de viabilidade do insumo Huff + isolamento anti-PII/DEC-012)
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-TP-07 (criada a partir de main @ HEAD af9c9ec).

## Paths do ciclo (commit por path — NUNCA git add -A)
- src/motor_expansao/demanda_revelada/ (módulo novo do Huff)
- tests/unit/ (testes do módulo)
- data/analysis/ (relatório gitignored — não versionado)
- tasks/current_task.md, tasks/completed.md, tasks/backlog.md (fechamento)
- context/handoff.md, context/handoff/

## Guardrails
- §5 (READ-ONLY M1): zero recálculo de score/pesos/carteira/plano/artefatos oficiais; mtime dos 4 oficiais
  M1 inalterado. Integrar ao residual/carteira/plano = follow-up com gate próprio (NÃO este bloco).
- DEC-008: out-of-fold vs baseline; R² in-sample BANIDO; IC95 seed=42; intervalos + flag de extrapolação.
- DEC-009: demanda (`membros`/`alunos_parceiras`) é ALVO OBSERVADO de validação; NUNCA preditor geográfico
  de magnitude.
- DEC-012 (anti-PII): camada agregada; fixtures sintéticas; zero PII em artefato/log/teste; fonte real
  nunca versionada.
- Isolamento: módulo NÃO importa de pipelines/m1, dashboard, censo_*, api.

## Depende de (satisfeito)
- BLK-TP-05 (GO demanda→captura, R²_oof_log +0,575, concluído 2026-06-30) — destrava a reabertura da Camada 2/Huff.
- concorrentes_mapeados.parquet + helper de catchment analisar_entorno_ponto.
