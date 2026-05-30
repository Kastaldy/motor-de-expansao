# Current Task

## Bloco atual

ID: BLK-FIX-02
Nome: Corrigir MessageSizeError para UFs grandes
Status: aprovado
Tipo: bug
Criticidade: Média (bloqueia usabilidade de alguns estados em produção; NÃO toca score/M1)
Esteira: Block Orchestrator → Planner → Builder → QA
Skill atual: QA (concluído — APROVADO)
Próxima Skill: Orquestrador (fechamento: housekeeping move + commit por path + merge)
dry_run: false

## Objetivo
Eliminar o `MessageSizeError` que impede o dashboard de renderizar UFs grandes: (a) elevar
`server.maxMessageSize` no `.streamlit/config.toml` (alvo 500 MB) e (b) identificar qual caminho
envia ~240 MB ao frontend e verificar se o downsampling (`MAP_POINT_LIMIT`/`_downsample_map_index`)
está sendo aplicado corretamente nesse caminho.

## Achados do orquestrador (pré-Block Orchestrator)
- `.streamlit/config.toml` NÃO define `server.maxMessageSize` hoje (default Streamlit = 200 MB).
  Alvo do backlog: 500. Bloco `[server]` já existe (headless/address/port/fileWatcherType/xsrf).
- Infra de downsampling de mapa existe: `MAP_POINT_LIMIT = 35000` (constants.py:98),
  `_downsample_map_index` (components.py:960) — ordena/dedup/head antes de materializar
  `MAP_SOURCE_COLUMNS_M1`/`MAP_SOURCE_COLUMNS_HYBRID`. Usado em 3 builders de mapa
  (components.py:1045, :1288, :1438) e referenciado em pages.py:2535.
- HIPÓTESE a confirmar pelo Block Orchestrator/Planner: o caminho de 240 MB pode NÃO ser o mapa
  (que já tem cap 35k), mas sim o envio de um DataFrame grande ao frontend — ex.: `st.dataframe`
  de tabela completa por UF, payload de carga lazy por UF, ou tooltip/source não capeado.
  Investigar antes de assumir que basta subir o limite.
- Guardrail CLAUDE.md (§5): visualizações/mapa NÃO podem recalcular/alterar score_priorizacao,
  hex_score_estrutural, carteira, plano ou artefatos M1. O fix é de transporte/render, não de score.

## Paths prováveis do ciclo (commit por path — NUNCA git add -A; CLAUDE.md NÃO entra)
- .streamlit/config.toml
- src/motor_expansao/dashboard/components.py · pages.py · constants.py  (só se o caminho de 240 MB exigir)
- tests/ (teste que documente o caminho corrigido / cap aplicado)
- tasks/current_task.md · tasks/backlog.md · tasks/completed.md
- context/handoff.md · context/handoff/
- (Parquets em data/outputs/ são artefatos gerados — não versionar.)

## Contexto de abertura
- Branch isolado: `ciclo/BLK-FIX-02`, criado a partir de `main` (HEAD ddba6c5, BLK-FIX-01 já mergeado).
- Worktree pré-sujo (NÃO commitar neste ciclo): `M CLAUDE.md`, `?? PROMPT-portar-run-cycle.md`.
  Commit SÓ por path; nunca `git add -A`.
- Criticidade Média ⇒ esteira sem gate humano (Block Orchestrator → Planner → Builder → QA).
