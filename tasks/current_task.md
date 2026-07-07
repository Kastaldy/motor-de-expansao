# Current Task

## Bloco atual

ID: BLK-VIAB-02
Nome: Faixa de demanda-premissa por tier de metragem (comparáveis reais)
Status: aprovado
Tipo: feature (insumo de premissa do motor)
Criticidade: média
Esteira: Block Orchestrator -> Planner -> Builder -> QA (autônoma no loop)
Skill atual: fechamento (housekeeping concluído)
Próxima Skill: — (ciclo encerrado)

## Objetivo
Derivar faixa de demanda-premissa (p10/p50/p90 de alunos por unidade) POR TIER de metragem
a partir dos comparáveis reais, materializando `data/staging/demanda_premissa_por_tier.parquet`.

## Resultado do Builder
- `src/motor_expansao/dimensionamento/demanda_premissa.py` criado (6 funções públicas)
- `tests/unit/dimensionamento/test_demanda_premissa.py` criado (28 testes, fixture sintética)
- 28/28 testes passaram; ruff 0 erros; mypy 0 erros; smoke import ok
- Parquet materializado: 5 linhas (1 por tier), N por tier = 17/46/36/11/2 (total 112)
- Relatório de qualidade gerado em data/analysis/demanda_premissa_qualidade.md
- 2 testes pré-existentes falham em test_streamlit_app.py (Plus Code geocoder — não regressões deste bloco)
- Artefatos M1 (brasil_estrutural, brasil_priorizados): mtime INALTERADO (1780501621 / 1780501631)

## Branch do ciclo
ciclo/loop-20260707-123809 (branch do loop autônomo atual)

## Paths do ciclo
- src/motor_expansao/dimensionamento/demanda_premissa.py (novo módulo)
- tests/unit/dimensionamento/test_demanda_premissa.py (testes novos)
- data/staging/demanda_premissa_por_tier.parquet (gitignored — NÃO commitado)
- data/analysis/demanda_premissa_qualidade.md (gitignored — NÃO commitado)
- tasks/current_task.md, tasks/completed.md, tasks/backlog.md (fechamento)
- context/handoff.md, context/handoff/

## Guardrails
- §5 READ-ONLY M1: nenhuma escrita em config.py/pipelines/m1/artefatos oficiais.
- DEC-009: alvo = alunos_totais REAIS (Ultra alunos_total / Eng Alunos Totais), NUNCA membros/preditor geográfico.
- viabilidade_ponto.py INTOCADO.
- Saída em data/staging/ + data/analysis/ (gitignored).
- Sem rede, sem VPS.

## Tiering de modelo — Média
- Block Orchestrator: sonnet
- Planner: sonnet
- Builder: sonnet
- QA: opus 4.8 (sempre)
