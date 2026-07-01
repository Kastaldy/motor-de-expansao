# Current Task

## Bloco atual

ID: BLK-RELPON-03
Nome: Eliminar a barra cinza (letterbox) dos mapas do Relatório Municipal
Status: aprovado (QA em 2026-07-01 — APROVADO COM RESSALVAS; ressalva = gate VISUAL humano do PDF, requisito de fechamento, NÃO bloqueia testes)
Tipo: feature (visualização/render — READ-ONLY sobre o M1)
Criticidade: alta
Esteira: Block Orchestrator → Planner → [aprovação humana] → Builder → QA
Skill atual: Ciclo fechado (housekeeping 6.0 OK; commit por path na branch ciclo/BLK-RELPON-03)
Próxima Skill: Merge pelo humano (revisar branch ciclo/BLK-RELPON-03 + gate visual humano do PDF antes do merge)

## Objetivo
Os mapas do Relatório Municipal passam a preencher o painel sem a barra cinza (letterbox top/base),
casando a proporção do mapa ao painel, sem distorção grosseira nem sobreposição de moldura/título/
rodapé. Ajuste de RENDER em `relatorio_municipal.py`. READ-ONLY sobre o M1.

## Causa-raiz (medida)
PNG gerado em 1000×620 (aspect 1,613) vs. painel 540×380 (aspect 1,421); `_draw_map` usa contain
(`scale=min`) → letterbox de ~22,6px em cima/embaixo = a barra cinza do painel.

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: sonnet
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-RELPON-03 (criada a partir de main @ c890eb8; independente de RELPON-01/02).

## Paths do ciclo (commitar só estes por path)
- src/motor_expansao/dashboard/relatorio_municipal.py
- tests/unit/test_relatorio_municipal.py (e testes impactados)
- tasks/backlog.md (bloco BLK-RELPON-03), tasks/current_task.md, tasks/completed.md
- context/handoff.md, context/handoff/

## Fora de escopo
- Gate do SAM/`flag_sam` (DEC-006/007), score, M1, artefatos oficiais (INTOCADOS);
  Relatório Pontual (`censo_map.py`/`censo_report.py`); método de intersecção e raio.

## Guardrails
- §5 (READ-ONLY M1): zero recálculo de score/pesos/carteira/plano/artefatos. Só RENDER.
- Sem dependência de rede nova (DEC-011 inalterada). Marca d'água anti-PII + `set_compression(False)` + 8 páginas mantidos.
