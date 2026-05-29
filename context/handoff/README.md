# Handoffs versionados (append-only)

Este diretório guarda os snapshots de auditoria dos handoffs de cada Skill da esteira de orquestração.

## Regra append-only

Nunca edite nem sobrescreva um arquivo já gravado aqui. Cada execução de Skill cria um arquivo NOVO.

## Formato de nome

```
AAAAMMDD-HHMMSS-<slug>.md
```

- `AAAAMMDD` — data da execução (ex.: `20260529`).
- `HHMMSS` — hora COM segundos (ex.: `143052`). Os segundos evitam colisão quando o mesmo papel grava mais de um snapshot no mesmo minuto (ciclo re-entrante ou re-execução do QA após correção).
- `<slug>` — papel que gerou o handoff, em minúsculas sem espaços.

Exemplo: `20260529-143052-planner.md`.

## Slugs válidos

- `block-orchestrator`
- `planner`
- `builder`
- `qa`

## Relação com `context/handoff.md`

`context/handoff.md` (raiz de `context/`) é o handoff corrente; os arquivos aqui são snapshots de auditoria, nunca editados após criados.
