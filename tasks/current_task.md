# Current Task

## Bloco atual

ID: BLK-REV-03
Nome: Diagnóstico de gargalo: render do mapa (pydeck)
Status: aprovado
Tipo: diagnóstico/análise (READ-ONLY sobre o M1; loop-safe)
Criticidade: Alta
Esteira: Block Orchestrator + Planner + Builder → QA (APROVADO)
Skill atual: QA (concluído)
Próxima Skill: Block Orchestrator (fechamento)

## Achado principal
Gargalo = deck.to_json() (F3): 0.6-1.0s, payload ~24 MB (65% tooltip strings).
Recomendação: (1) tooltip enxuto, (2) cap 18k→12k, (3) memoizar layer.
READ-ONLY M1.

## Branch do ciclo
ciclo/BLK-REV-03
