# Current Task

## Bloco atual

ID: BLK-RELPON-01
Nome: Três mapas de calor (população/renda/score) num único slide do Relatório Pontual
Status: aprovado (QA — APROVADO COM RESSALVAS; ressalva = gate visual humano do PDF, não bloqueante de testes)
Tipo: feature (visualização/relatório — READ-ONLY sobre o M1)
Criticidade: alta
Esteira: Block Orchestrator → Planner → [aprovação humana] → Builder → QA
Skill atual: Ciclo fechado (housekeeping 6.0 OK; commit por path na branch ciclo/BLK-RELPON-01)
Próxima Skill: Merge pelo humano (revisar branch ciclo/BLK-RELPON-01 + gate visual humano do PDF antes do merge)

## Objetivo
Consolidar os 3 choropleths censitários (População/Densidade, Renda, Score) — hoje 1 slide cada
(páginas 2–4 do PDF de 7 páginas) — em UM único slide "Mapas de calor", lado a lado, legíveis e
sem sobreposição, nas variantes `classico` e `censitario` do Relatório Pontual; atualizar `/Count`
(7→5) nos testes travados. READ-ONLY sobre o M1.

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: sonnet
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-RELPON-01 (criada a partir de main @ HEAD atual).

## Paths do ciclo (commitar só estes por path)
- src/motor_expansao/dashboard/censo_report.py
- src/motor_expansao/dashboard/censo_map.py (só se precisar do param opcional de render)
- tests/unit/test_relatorio_pontual_censitario_export.py
- tasks/backlog.md (bloco BLK-RELPON-01 já adicionado por Vini — pré-sujo, parte do ciclo)
- tasks/current_task.md, tasks/completed.md, context/handoff.md, context/handoff/

## Fora de escopo
- Concorrentes e Big Numbers (slides próprios); método `setor_censitario_intersecao_area_1p5km`,
  raio 1,5 km, score, M1 e artefatos oficiais (INTOCADOS); Relatório Municipal (outro template).

## Guardrails
- §5 (READ-ONLY M1): zero recálculo de score/pesos/carteira/plano/artefatos.
- Caminho do dashboard sem os params novos preservado byte-a-byte (default = comportamento atual).
- Sem dependência de rede nova (DEC-004/DEC-005 inalteradas). Marca d'água anti-PII + `set_compression(False)` + `%PDF-1.4` mantidos.
