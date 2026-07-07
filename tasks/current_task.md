# Current Task

## Bloco atual

ID: BLK-VIAB-05
Nome: Recalibrar/validar a curva m²→densidade com a base ampliada (out-of-fold)
Status: BLOQUEADO — base ampliada não existe (N=112, idêntico ao BLK-TP-04 já concluído)
Tipo: validação da curva de densidade (READ-ONLY sobre o M1)
Criticidade: Alta
Esteira: Block Orchestrator → BLOQUEADO
Skill atual: Block Orchestrator (concluído — veredito BLOQUEADO)
Próxima Skill: NENHUMA (bloco bloqueado por falta de dados)

## Objetivo
Revalidar/recalibrar a curva metragem→densidade (alunos/m²) sobre base ampliada.
BLOQUEADO: a "base ampliada" mencionada no backlog não existe — a base disponível
com metragem+alunos é N=112 (Ultra 54 + Eng Corpo 58), idêntica à já usada no
BLK-TP-04 (concluído 2026-07-02).

## Razão do bloqueio
- Smart Fit: sem coluna de metragem em nenhuma fonte (KPIs_Smart_2025_02.xlsx, 7 cols apenas)
- Sky Fit: sem coluna de metragem (Sky Fit dados.xlsx, tem alunos mas não m²)
- base_calibracao_multirede.parquet: 426 linhas mas apenas 112 com metragem > 0
  (skyfit 311 linhas, todas sem metragem)
- BLK-TP-04 já executou validação honesta da curva com N=112 (mesmo conjunto)

## Condição para reabertura
Nova fonte com metragem+alunos reais de academias além de Ultra e Eng Corpo.

## Branch do ciclo
ciclo/loop-20260707-123809

## Guardrails
- §5 READ-ONLY M1: nenhuma escrita em config.py/pipelines/m1/artefatos oficiais.
- DEC-008: out-of-fold vs baseline; R² in-sample BANIDO.
- DEC-009: alvo = alunos_totais REAIS, nunca membros/agregador.
- viabilidade_ponto.py INTOCADO.
