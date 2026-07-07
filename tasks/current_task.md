# Current Task

## Bloco atual

ID: BLK-VIAB-04
Nome: Backtest do motor de viabilidade contra as 54 unidades Ultra reais
Status: delimitado
Tipo: validação (mede erro do motor; READ-ONLY sobre o M1)
Criticidade: Alta
Esteira: Block Orchestrator → Planner → Builder → QA (autônoma no loop)
Skill atual: QA (concluído)
Status: aprovado
Próxima Skill: Block Orchestrator (fechamento)

## Objetivo
Rodar `analisar_viabilidade_ponto` em modo LOO sobre as 54 unidades Ultra maduras,
usando m² e alunos reais como entradas, e medir o erro da curva de densidade
(faixa_alunos_p50 predito vs alunos_total real) e do aluguel-teto calculado.
Relatório `data/analysis/viabilidade_backtest_ultra.md` com MAE/vies e casos de erro material.

## Dependências
- data/staging/unidades_ultra_performance_hex.parquet (N=54, metragem/alunos_total/ticket todos disponíveis)
- data/staging/base_calibracao_maduras.parquet (base de calibração da curva de densidade)
- viabilidade_ponto.py (motor — INTOCADO)

## Branch do ciclo
ciclo/loop-20260707-123809

## Paths do ciclo
- src/motor_expansao/dimensionamento/backtest_viabilidade.py (CRIAR NOVO)
- tests/unit/dimensionamento/test_backtest_viabilidade.py (CRIAR NOVO, mínimo 8 testes)
- data/analysis/viabilidade_backtest_ultra.md (gitignored — NÃO commitado)
- tasks/current_task.md, tasks/completed.md, tasks/backlog.md (fechamento)
- context/handoff.md, context/handoff/

## Guardrails
- §5 READ-ONLY M1: nenhuma escrita em config.py/pipelines/m1/artefatos oficiais.
- DEC-008: out-of-fold vs baseline; NÃO ajustar o motor neste bloco (só medir).
- DEC-009: demanda SÓ como premissa explícita (alunos_total_real) — NUNCA prevista pela geo.
- viabilidade_ponto.py INTOCADO.
- Modo COORDLESS: setores_df=None — sem rede/catchment, sem fetch HTTP.
- LOO obrigatório: para cada unidade i, base_calibracao = todas as 54 EXCETO a unidade i.
- Saída gitignored (data/analysis/).
- Sem rede, sem VPS.

## Tiering de modelo — Alta
- Block Orchestrator: sonnet (concluído)
- Planner: opus
- Builder: opus
- QA: opus (sempre)
