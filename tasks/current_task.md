# Current Task

## Bloco atual

ID: BLK-REV-06
Nome: Diagnóstico de gargalo: geração de PDF (Pontual + Municipal)
Status: APROVADO (QA 2026-07-10) — ciclo concluído, housekeeping feito (bloco em completed.md)
Tipo: diagnóstico/análise (READ-ONLY sobre o M1; loop-safe)
Criticidade: Alta
Esteira: Block Orchestrator → Planner → Builder → QA (autônoma no loop)
Skill atual: QA (concluída)
Próxima Skill: Fechamento manual / merge humano

## Veredito do QA
APROVADO. Diagnóstico puro READ-ONLY: zero código de produção alterado; root cause
confirmado por spot-check (`_to_mercator` cria `_transformer` por setor no loop,
censo_map.py l.372-375 → l.729); artefato `data/analysis/diagnostico_pdf.md`
gitignored; loop_guard GUARD OK; diff M1 vazio; housekeeping via helper (bloco
byte-idêntico em completed.md). Suíte: 1524 passed / 4 skipped; 4 failed + 1 error
são deps opcionais ausentes no ambiente (openlocationcode, matplotlib), NÃO deste
ciclo. Recomendação: bloco sucessor de IMPLEMENTAÇÃO para a Opção O1 (shared
transformer, ganho 86×).

## Objetivo
Medir cada etapa headless (intersecção geométrica de setores, fetch/cache de tiles,
render matplotlib, montagem fpdf2) e isolar o gargalo. Opções: cache de tiles mais
agressivo, pré-render, geometria simplificada, paralelismo.
Relatório `data/analysis/diagnostico_pdf.md`. Raio 1.5km e método de intersecção
INTOCADOS (só medidos). READ-ONLY M1.

## Branch do ciclo
ciclo/BLK-REV-06

## Guardrails
- §5 READ-ONLY M1; §6.1 loop-safe; data/analysis (gitignored).
- Raio 1,5 km e método de intersecção INTOCADOS.
