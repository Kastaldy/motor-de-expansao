# Current Task

## Bloco atual

ID: BLK-REV-04
Nome: Diagnóstico de gargalo: troca de modos de cor / heat maps
Status: aprovado
Tipo: diagnóstico/análise (READ-ONLY sobre o M1; loop-safe)
Criticidade: Alta
Esteira: BO+Planner+Builder → QA (APROVADO)
Skill atual: QA (concluído)
Próxima Skill: Block Orchestrator (fechamento)

## Achado principal
H2 (cache_data nos builders) é a melhor opção: elimina 70-100% do custo B+C.
91.5% do payload JSON é invariante entre modos — só fill_color muda.
READ-ONLY M1.

## Branch do ciclo
ciclo/BLK-REV-04
