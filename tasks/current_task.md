# Current Task

## Sprint de fixes (multi-track, paralelo) — 2026-06-01 — CONCLUÍDA

Modo: paralelizar + pré-autorizar em lote (decisão de Felipe 2026-06-01).
Status: **APROVADA** (QA independente por track) — ciclos fechados; mergeados na `main`.
dry_run: false

### Track A — `ciclo/BLK-FIX-04` (FU1 + FIX-04) — APROVADO, mergeado
- BLK-FIX-04: clique de hex → seleção/Análise Pontual restaurado (hex_id→centróide).
- BLK-FIX-03-FU1: caption "amostrado" honesto (atributo de cap real no Deck).

### Track B — `ciclo/BLK-FIX-05` (tema claro do SO) — APROVADO, mergeado
- `[theme] base=dark` no config.toml + CSS baseweb endurecido. Verificação visual final = manual (Felipe).

## Fechamento (orquestrador, 2026-06-01)
- Worktrees isolados (Builders+QA em paralelo); merges A→B auto-mergearam sem conflito.
- Validação na main pós-merge: `646 passed, 1 skipped` (baseline 639 + 7 novos); ruff/mypy ok; import ok.
- Housekeeping 6.0: BLK-FIX-03-FU1, BLK-FIX-04, BLK-FIX-05 movidos via helper (stubs + `--check` OK).
- Commit por path por track; housekeeping commit por path na main.
- Dry-run de orquestração: NÃO se aplica (não tocou run-cycle/prompts/esteira).

## Pendências / próximos
- Verificação visual do FIX-05 em SO tema claro (Felipe).
- BLK-FIX-06 (litoral): BLOQUEADO em DEC (fora da sprint).
- BLK-FIX-07-B (clustering, Fase B): follow-up pendente.
