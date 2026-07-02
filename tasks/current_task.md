# Current Task

## Bloco atual

ID: BLK-RELMUN-03
Nome: Validar hexágono só por Residual Fitness (remover o filtro de SAM Fitness)
Status: aprovado (QA — APROVADO COM RESSALVAS, 2026-07-02; ressalva não-bloqueadora: 1 falha pré-existente e fora de escopo em test_score_retencao_territorial por artefato de staging ausente no ambiente)
Tipo: feature (visualização/relatório — READ-ONLY sobre o M1)
Criticidade: alta
Esteira: Block Orchestrator → Planner → [REVISÃO HUMANA — produto + emenda DEC-011] → Builder → QA
Skill atual: Ciclo fechado (housekeeping 6.0 OK — bloco movido p/ completed.md via helper, --check verde; commit por path na branch ciclo/BLK-RELMUN-03)
Próxima Skill: Merge pelo humano (revisar branch ciclo/BLK-RELMUN-03 + revisão visual do PDF do Relatório Municipal por Vinicius antes do merge)

## Objetivo
Remover o filtro de SAM Fitness (≥ 3.000) de `_hex_destacado_mask` no Relatório Municipal,
mantendo apenas Residual Fitness (`oferta_efetiva_disponivel` ≥ 2.000) como critério de validação
do hexágono. Atualizar textos/legendas/testes e registrar emenda à DEC-011. READ-ONLY sobre o M1.

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: sonnet
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-RELMUN-03 (criada a partir de chore/backlog-relmun-residual-only @ HEAD, que já contém
as refinações de backlog do BLK-RELMUN-03: confirmação do alvo = Relatório Municipal).

## Paths do ciclo (commitar só estes por path)
- src/motor_expansao/dashboard/relatorio_municipal.py (alvo principal)
- tests/unit/test_relatorio_municipal.py (testes que fixam critério/números)
- CLAUDE.md (emenda à DEC-011)
- tasks/backlog.md (bloco BLK-RELMUN-03), tasks/current_task.md, tasks/completed.md
- context/handoff.md, context/handoff/

## Guardrails
- §5 (READ-ONLY M1): zero recálculo de score/pesos/carteira/plano/artefatos oficiais.
- Fora de escopo: `flag_sam`/gate do SAM no pipeline de mercado (DEC-006/DEC-007) — NÃO tocar;
  Relatório Pontual (raio 1,5 km) — fora do escopo (confirmado por Vini).
- Marca d'água anti-PII + `set_compression(False)` + 8 páginas mantidos.
- Sem dependência de rede nova.
