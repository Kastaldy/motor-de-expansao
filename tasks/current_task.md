# Current Task

## Bloco atual

ID: BLK-FIX-13
Nome: Data-drift em `test_csvs_concorrentes_legiveis` (2 falhas pré-existentes na suíte full)
Status: concluído (APROVADO — ciclo Baixa, gate final do orquestrador; suíte full 884 passed, 1 skipped, 0 failed)
Tipo: bug (teste/manutenção; READ-ONLY sobre M1)
Criticidade: baixa
Esteira: Block Orchestrator → Builder (sem QA; Builder é o último gate)
Skill atual: Fechamento (orquestrador) — concluído
Próxima Skill: nenhuma (merge pelo humano)
dry_run: false

## Objetivo
Reconciliar `test_csvs_concorrentes_legiveis` (em `tests/integration/test_modelo_mercado_hexagonos.py`)
com os CSVs reais de concorrentes regenerados, deixando a suíte full 100% verde, sem mascarar regressão.

## Fatos confirmados (pré-ciclo, pelo orquestrador)
- O teste é parametrizado por `CSV_SOURCES` (linhas ~26-29) com contagens FIXAS de linhas:
  `unidades_smart_fit.csv: 1000`, `unidades_bluefit.csv: 223`, `unidades_panobianco.csv: 472`.
  Assert: `len(df) == expected_rows` (linha 153).
- Contagens REAIS atuais: smart_fit **1000** (OK), bluefit **226** (drift +3), panobianco **455** (drift −17).
- Os CSVs em `concorrentes/` são **GITIGNORED** (dados locais reais, regenerados pelo pipeline de
  mapeamento) → mudança é refresh legítimo de dados, NÃO regressão de código.
- Em CI os CSVs não existem → o teste dá `pytest.skip` (linha 149-150); o VERMELHO é só no run LOCAL.
  CI não está quebrado; o objetivo é o run local 100% verde.

## Decisão de abordagem (a confirmar pelo BO)
- (A) Atualizar as contagens em `CSV_SOURCES` (223→226, 472→455). Simples; volta a driftar se os dados
  forem regenerados de novo.
- (B) Tornar o teste robusto a drift (manter colunas/parseabilidade + trocar `==` exato por piso/sanidade,
  ex. `len(df) > 0`). Mais robusto; perde o "snapshot" exato.
BO recomenda a abordagem; Builder implementa.

## Tiering de modelo (Passo 4) — Baixa
- Block Orchestrator: haiku
- Builder: sonnet
- (Baixa: sem Planner/QA. O Builder DEVE rodar a SUÍTE FULL para confirmar 0 falhas — critério de aceite
  explícito e não há gate de QA.)

## Branch do ciclo
ciclo/BLK-FIX-13 (a partir de main)

## Paths do ciclo (commit por path no fechamento)
- tests/integration/test_modelo_mercado_hexagonos.py (o fix)
- tasks/backlog.md, tasks/completed.md (housekeeping 6.0 — move BLK-FIX-13)
- context/handoff.md + context/handoff/

## Paths pré-sujos / pendentes que ACOMPANHAM o working tree (documentar; NÃO são deste fix)
- tasks/backlog.md / tasks/completed.md já contêm edições pendentes não-commitadas: o bloco NOVO
  **BLK-EST-05** + o **rename FIX-07→FIX-13** (correção de colisão de ID). Como vivem no MESMO arquivo,
  entrarão no commit de backlog/completed deste ciclo — documentar no fechamento.
- data/outputs/setores_censitarios_2022_geo/_metadata.json (M) — alheio
- data/reports/relatorio_pontual_censitario_base_geo.md (M) — alheio
- data/outputs/SIMULACAO_relatorio_caiubi_classico.pdf (untracked) — simulação descartável; NÃO commitar

## Fora de escopo (invioláveis)
- score/pesos/artefatos M1 (READ-ONLY; DEC-001); regenerar artefatos M1
- regenerar os próprios CSVs de concorrentes (dado real local)
