# Current Task

## Bloco atual

ID: BLK-VIAB-06
Nome: Guardrail de envelope de metragem no motor de viabilidade
Status: aprovado
Tipo: feature (READ-ONLY sobre o M1; loop-safe)
Criticidade: Média
Esteira: Block Orchestrator → Planner → Builder → QA (APROVADO)
Skill atual: QA (concluído)
Próxima Skill: Block Orchestrator (fechamento)

## Objetivo
Adicionar `flag_fora_envelope` em `analisar_viabilidade_ponto` quando o `m2` do imóvel
cai fora de [600, 3000] m², para a UI avisar sobre extrapolação não confiável.
READ-ONLY sobre o M1. Envelope = [600, 3000] m² (pré-fixado).

## Branch do ciclo
ciclo/BLK-VIAB-06

## Guardrails
- §5 READ-ONLY M1: nenhuma escrita em config.py/pipelines/m1/artefatos oficiais.
- §6.1 loop-safe: sem VPS, sem rede.
- loop_guard.py limpo obrigatório.
- Só FLAG, NÃO recusa por padrão (a UI decide bloquear/exibir).
- Comportamento existente byte-idêntico exceto a flag nova.
