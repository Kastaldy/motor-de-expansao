# Current Task

## Bloco atual

ID: BLK-VIAB-01
Nome: Validação/limpeza da base de imóveis candidatos
Status: aprovado
Tipo: feature (camada paralela de dados)
Criticidade: média
Esteira: Block Orchestrator → Planner → Builder → QA (autônoma no loop)
Skill atual: fechamento (housekeeping concluído)
Próxima Skill: — (ciclo encerrado)

## Objetivo
Ler `data/ultra/Imoveis_*.xlsx`, aplicar as 4 regras PRÉ-FIXADAS (metragem/aluguel/coordenada/status)
e materializar `data/staging/imoveis_candidatos_limpos.parquet` + `data/analysis/imoveis_qualidade.md`.

## Resultado do Builder
- `src/motor_expansao/dimensionamento/imoveis_candidatos.py` criado (4 funções puras: ler_imoveis_xlsx, validar_e_limpar, materializar, run)
- `tests/unit/dimensionamento/test_imoveis_candidatos.py` criado (13 testes, fixture sintética)
- 13/13 testes passaram; ruff 0 erros; mypy 0 erros; smoke import ok
- Parquet materializado: 23 linhas (28 entrada - 5 descartados: 4 área + 1 placeholder)
- Relatório de qualidade gerado em data/analysis/imoveis_qualidade.md
- 2 testes pré-existentes falham em test_streamlit_app.py (Plus Code geocoder — confirmados pré-existentes, não regressões deste bloco)
- Artefatos M1 (brasil_estrutural, brasil_priorizados): mtime Jun 3 15:47 INALTERADO

## Branch do ciclo
ciclo/loop-20260707-123809 (branch do loop autônomo atual)

## Paths do ciclo (commit por path — NUNCA git add -A)
- src/motor_expansao/dimensionamento/imoveis_candidatos.py (novo módulo)
- tests/unit/dimensionamento/ (testes novos)
- data/staging/imoveis_candidatos_limpos.parquet (gitignored — NÃO commitado)
- data/analysis/imoveis_qualidade.md (gitignored — NÃO commitado)
- tasks/current_task.md, tasks/completed.md, tasks/backlog.md (fechamento)
- context/handoff.md, context/handoff/

## Guardrails
- §5 READ-ONLY M1: nenhuma escrita em config.py/pipelines/m1/artefatos oficiais.
- DEC-009: demanda NUNCA prevista pela geografia; alvo = alunos_totais REAIS, nunca membros.
- Saída em data/staging/ + data/analysis/ (gitignored).
- Sem rede, sem VPS.

## Tiering de modelo (Passo 4) — Média
- Block Orchestrator: sonnet
- Planner: sonnet
- Builder: sonnet
- QA: opus 4.8 (sempre)
