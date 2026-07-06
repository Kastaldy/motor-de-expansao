# Current Task

## Bloco atual

ID: BLK-ATR-03
Nome: Testar a estrutura de leitura — matriz de eixos vs score composto (GO/NO-GO)
Status: CICLO FECHADO — APROVADO (housekeeping OK + commit por path feito; merge = humano)
Tipo: modelagem (validação out-of-fold, GO/NO-GO — READ-ONLY M1)
Criticidade: alta
Esteira: Block Orchestrator → Planner → Builder → QA (autônoma no loop)
Skill atual: QA (concluído)
Próxima Skill: nenhuma (pronto para revisão humana + merge)

## Veredito QA (2026-07-06)
APROVADO. Suíte FULL 1344 passed / 4 skipped / 4 failed (as 4 falhas são PRÉ-EXISTENTES do
openlocationcode; regressões novas = 0). ruff limpo; isolamento DEC-012 confirmado (grep vazio +
loop_guard OK); mtime dos 4 oficiais M1 inalterado; import streamlit_app ok; corretude confirmada
(gate inline, R² in-sample fora do veredito, membros só ALVO, degradação graciosa em share=1.0).
Housekeeping: BLK-ATR-03 movido para completed + stub no backlog. Ver context/handoff.md.

## Objetivo
Validar out-of-fold (k-fold 5×5 seed=42/IC95 vs membros) se um score composto dos 3 eixos prevê
a demanda melhor que cada eixo isolado e melhor que a matriz. Default = matriz; composto só
recomendado se vencer materialmente. Veredito em data/analysis/ (gitignored). READ-ONLY M1.

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: sonnet
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-ATR-03

## Dados disponíveis (confirmados)
- data/staging/demanda_revelada_h3.parquet: 16.575 hexes com 'membros' (alvo)
- data/staging/hexagonos_mercado_mapeado.parquet: share_captura_huff (100% não-null), score_priorizacao, score_oportunidade_residual, score_setor_2022_calibrado, renda_per_capita
- Join demanda×mercado: n=16.411; 28,1% com share<1.0 (competitivos)
- Spearman vs membros: share_huff rho=-0,581; score_priorizacao +0,490; score_residual +0,517; score_setor +0,234
- DECISÃO BO: Opção A (share existente; concorrentes_densos.parquet NÃO materializado; não é requisito do ATR-03)

## Paths do ciclo (commit por path — NUNCA git add -A)
- src/motor_expansao/demanda_revelada/estrutura_funil.py (novo módulo)
- tests/unit/demanda_revelada/ (testes)
- data/analysis/ (relatório gitignored)
- tasks/current_task.md, tasks/completed.md, tasks/backlog.md (fechamento)
- context/handoff.md, context/handoff/

## Guardrails
- §5 (READ-ONLY M1): mtime dos 4 oficiais M1 inalterado.
- DEC-008: out-of-fold vs baseline; R² in-sample BANIDO; IC95 seed=42.
- DEC-009: membros/demanda é ALVO; NUNCA preditor de magnitude.
- DEC-012 (anti-PII): fixtures sintéticas; zero PII em artefato/log/teste.
- Não materializa nada em produção (só data/analysis gitignored).
- Isolamento: módulo NÃO importa de pipelines/m1, dashboard, censo_*, api.

## Depende de (satisfeito)
- BLK-ATR-01 (módulo concorrentes_densos.py — concluído 2026-07-06)
- BLK-ATR-02 (flag_gate_atratividade — concluído 2026-07-06)
