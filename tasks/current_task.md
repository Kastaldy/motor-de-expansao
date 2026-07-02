# Current Task

## Bloco atual

ID: BLK-TP-04
Nome: Calibração da curva tamanho→densidade do BLK-DIM com alunos/unidade
Status: aprovado (QA 2026-07-02 — suíte full 1231 passed / 1 skipped; mtime M1 idêntico; isolamento e anti-PII OK; ruff+mypy limpos; sem ressalvas bloqueantes)
Tipo: modelagem (análise/calibração — READ-ONLY sobre o M1)
Criticidade: alta
Esteira: Block Orchestrator → Planner → [REVISÃO HUMANA — modelagem] → Builder → QA
Skill atual: QA (próxima)
Próxima Skill: QA
Veredito real da curva (Builder, 2026-07-02): PRINCIPAL (dummy marca) GO fraco R2_oof=+0.2590 IC95[+0.0973,+0.3840]; pooled NO-GO IC95[-0.0227,+0.2065]; Ultra N=54 NO-GO IC95[-0.1651,+0.1144] — o sinal é o degrau de TIER, não metragem sozinha (consistente com DIM-07). Subconjunto: 221 passed. mtime M1 idêntico. ruff+mypy limpos.
Gate humano: APROVADO pelo usuário em 2026-07-02 — D1–D7 = todas na opção A (recomendação do Planner)

## Objetivo
Usar `alunos_parceiras` (amostra real de alunos/unidade por tier) como insumo para calibrar/validar a
curva tamanho→densidade do `viabilidade_ponto.py` (BLK-DIM), sob a disciplina da DEC-008 (LOO/k-fold vs
baseline, banir R² in-sample, intervalos + flag de extrapolação) e alinhado à DEC-009 (dimensionamento
consome demanda, NÃO a prevê pela geografia). READ-ONLY sobre o M1.

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: sonnet
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-TP-04 (criada a partir de main @ HEAD 8ef4f55).

## Paths do ciclo (commitar só estes por path)
- src/motor_expansao/demanda_revelada/calibracao_curva.py (NOVO)
- tests/unit/demanda_revelada/test_calibracao_curva.py (NOVO) + tests/unit/demanda_revelada/__init__.py (se ausente)
- data/analysis/calibracao_curva_densidade.md (NOVO, gitignored)
- tasks/backlog.md (bloco BLK-TP-04), tasks/current_task.md, tasks/completed.md
- context/handoff.md, context/handoff/
- NÃO tocar: src/motor_expansao/dimensionamento/viabilidade_ponto.py (curva em produção); 4 artefatos oficiais M1

## Guardrails
- §5 (READ-ONLY M1): zero recálculo de score/pesos/carteira/plano/artefatos oficiais.
- DEC-008: LOO/k-fold vs baseline da média; R² in-sample BANIDO; intervalos de predição + flag de extrapolação.
- DEC-009: demanda entra como PREMISSA/insumo OBSERVADO; PROIBIDO reintroduzir regressão geográfica de demanda como preditor; curva é metragem→densidade (NÃO geografia).
- DEC-012 (anti-PII): consumir só camada agregada `alunos_parceiras`; zero PII em artefato/log/teste.
