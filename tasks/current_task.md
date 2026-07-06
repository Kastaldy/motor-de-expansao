# Current Task

## Bloco atual

ID: BLK-ATR-02
Nome: Gate de viabilidade absoluto (população ≥ 5.000 E renda per capita ≥ 1.500) na camada de mercado
Status: CICLO FECHADO — APROVADO COM RESSALVAS (housekeeping OK + commit por path feito; merge = humano)
Tipo: feature (flag paralela na camada de mercado)
Criticidade: alta
Esteira: Block Orchestrator → Planner → Builder → QA (autônoma no loop)
Skill atual: QA (concluído)
Próxima Skill: Block Orchestrator (fechamento)

## Veredito do QA (2026-07-06 18:50:08)
APROVADO COM RESSALVA. Subconjunto impactado 50/50 verde; ruff limpo; guardrails confirmados
(config.py sem a constante; RENDA_PER_CAPITA_MIN_ATR só em calcular_colunas_mercado.py; m1/
config intocados; loop_guard OK; mtime dos oficiais M1 inalterado); corretude confirmada
(NaN→False, limiar inclusivo >=1500, coluna paralela). import streamlit_app ok.
RESSALVA: full suite = 1318 passed / 4 failed / 4 skipped — as 4 falhas são de AMBIENTE
(pacote `openlocationcode` declarado no pyproject.toml mas não instalado; caminho Plus Code do
BLK-UI-09-FU2), sem qualquer relação com este bloco. Detalhe em context/handoff.md.

## Objetivo
Materializar uma flag de gate de viabilidade absoluto (`flag_gate_atratividade = populacao_corte_hex >= 5000 AND renda_per_capita >= 1500`) na camada de mercado/paralela, sem tocar flag_viavel existente, config.py nem M1.

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: sonnet
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-ATR-02 (criada a partir de ciclo/loop-20260706-152137)

## Paths do ciclo (commit por path — NUNCA git add -A)
- src/motor_expansao/pipelines/calcular_colunas_mercado.py (ou módulo paralelo para a flag)
- src/motor_expansao/pipelines/pop_corte.py (reutilizar)
- tests/unit/ (testes do novo gate)
- tasks/current_task.md, tasks/completed.md, tasks/backlog.md (fechamento)
- context/handoff.md, context/handoff/

## Guardrails
- §5 (READ-ONLY M1): zero recálculo de score/pesos/carteira/plano/artefatos oficiais; mtime dos 4 oficiais M1 inalterado.
- flag_viavel/RENDA_MIN/M1 INTOCADOS.
- Gate vive na camada de mercado/paralela (NÃO em config.py nem pipelines/m1).
- loop_guard.py não pode acusar toque em caminho proibido.
- DEC-001 intacta (pisos do funil ≠ pesos do M1).

## Depende de (satisfeito)
- Sem dependências (usa colunas pop e renda já existentes na camada de mercado/censitária).
