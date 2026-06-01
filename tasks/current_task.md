# Current Task

## Sprint de fixes (multi-track, paralelo) — 2026-06-01

Modo: paralelizar + pré-autorizar em lote (decisão de Felipe 2026-06-01).
FIX-06 (litoral, CRÍTICA+DEC) mantido BLOQUEADO — fora desta sprint.

### Track A — `ciclo/BLK-FIX-04` (combinado FU1 + FIX-04)
- BLK-FIX-04: clique de hex não dispara seleção/Análise Pontual (Média-Alta).
- BLK-FIX-03-FU1: caption "capped" falso positivo na janela 18k–35k (Baixa) — pega carona (mesmos arquivos).
- Criticidade do track: Média-Alta. Arquivos: pages.py (render mapa ~2294/2535), components.py (builders/pickable), data.py.

### Track B — `ciclo/BLK-FIX-05` (tema claro do SO)
- BLK-FIX-05: abas/caixas de filtro ficam claras em tema claro do SO (Média).
- Arquivos: .streamlit/config.toml, pages.py (inject_styles ~121, render_tab_selector ~359), constants.py (COLORS).

## Fase atual
PLANEJAMENTO em paralelo (read-only) → apresentar planos em lote → aprovação humana →
Builders em worktrees isolados (paralelo) → QA independente por track → merge A, depois B → CI.

Status: planejamento em andamento.
dry_run: false

## Guardrails
Zero M1/score/artefatos/regra de cor. Commit por path por track. Merge limpo (regiões distintas de pages.py).
