# Current Task

## Bloco atual

ID: BLK-VIAB-07
Nome: Curva de densidade por formato (rótulo opcional) — validação out-of-fold + parâmetro
Status: aprovado
Tipo: feature + validação (READ-ONLY sobre o M1; loop-safe)
Criticidade: Alta
Esteira: Block Orchestrator → Planner → Builder → QA (APROVADO)
Skill atual: QA (concluído)
Próxima Skill: Block Orchestrator (fechamento)

## Objetivo
(1) Rotular comparáveis Ultra por `formato` (low_cost_massa / boutique / outro);
(2) adicionar param OPCIONAL `formato` em `faixa_alunos_por_densidade` que filtra
comparáveis do mesmo formato (default None = byte-idêntico ao atual);
(3) validar out-of-fold (k-fold 5×5 vs baseline, DEC-008). Veredito: GO
(delta MAPE 9.13 p.p., IC [6.60, 11.77]).
READ-ONLY sobre o M1. DEC-008 honrada.

## Branch do ciclo
ciclo/BLK-VIAB-07

## Guardrails
- §5 READ-ONLY M1: nenhuma escrita em config.py/pipelines/m1/artefatos oficiais.
- §6.1 loop-safe: sem VPS, sem rede. Consome data/staging existente.
- DEC-008: LOO-CV/k-fold vs baseline; R² in-sample BANIDO; veredito por MAPE oof.
- DEC-009: alvo = alunos totais REAIS (nunca membros/agregador).
