---
name: deploy
description: Conduz o deploy de produção do Motor (piloto web + API/bot Telegram) na VPS, por digest imutável, passo a passo. Cobre os path-filters do publish-web e do publish-api (mudança só em dashboard/ NÃO rebuilda a imagem api/bot) e a matriz de capacidade da VPS. Use ao pedir "faça o deploy", "leve para prod", "suba na VPS", "atualize produção".
---

# /deploy — deploy de produção por digest (web + API/bot)

Encapsula a sequência de deploy para não virar 7 idas-e-voltas por sessão. **Deploy é SEMPRE manual,
por digest, e cada comando na VPS exige confirmação explícita do Felipe (CLAUDE.md §6, guardrail
absoluto).** Esta skill organiza o procedimento e não dispensa a confirmação comando-a-comando.

## Imagens e path-filters (desde a DEC-022, 2026-08-03, não há mais imagem Streamlit)
- **`motor-expansao-web`** (job `publish-web`, `Dockerfile.web`): publica no push da `main` com
  path-filter `Dockerfile.web | web/** | src/motor_expansao/(dashboard|dimensionamento|api)/** |
  pyproject.toml`. Deploy por **`WEB_IMAGE`** (serviço `web`, container `motor_expansao_web`,
  porta interna 8899, `https://piloto.ultra-expansao.tech`). Runbook: `docs/deploy_piloto_web.md`
  (ciclo curto pull+up: `docs/deploy.md`).
- **`motor-expansao-api`** (job `publish-api`, `Dockerfile.api`): path-filter
  `Dockerfile.api | src/motor_expansao/api/** | pyproject.toml`. Deploy por **`API_IMAGE`**
  (serviços `api` + `telegram-bot`). Runbook: `docs/deploy_api_bot.md`.

## Gotcha crítico (a causa nº 1 de "o bot ficou velho")
O `publish-api` tem **filtro de path**: um PR/commit que muda **só `dashboard/`** publica a imagem
`web` (o filtro do `publish-web` cobre `dashboard/`) mas **NÃO rebuilda a imagem `api`/`telegram-bot`**.
Se a feature toca render usado pela API/bot, republicar manualmente após o merge:
```
gh workflow run ci.yml --ref main -f publish_api=true -f dispatch_build_sanity=false
```
→ deploya `api` + `telegram-bot` por `API_IMAGE`. Análogo para o web (mudança fora do filtro do
`publish-web` que afete o runtime): `gh workflow run ci.yml --ref main -f publish_web=true -f dispatch_build_sanity=false`.

## Matriz de capacidade da VPS (consulte ANTES de dizer "não consigo")
- `scp` para a VPS = **SIM**, via `~/.ssh/id_ultra_mcp` (o classificador bloqueia `ssh` remoto, não `scp`; memória `deploy-vps-scp-arquivos`). Validar por `md5sum` na VPS.
- `ssh` remoto interativo = **NÃO** (bloqueado). Use o MCP `ssh-vps-ultra` (read/edit) para inspeção.
- Nunca declarar incapacidade de enviar arquivo à VPS sem antes **testar** o `scp`.

## Passos
1. **Determinar o alvo.** `git diff --name-only origin/main~1 origin/main` (ou os paths do ciclo):
   mudou `web/` ou `src/motor_expansao/(dashboard|dimensionamento|api)/`? → nova imagem `web`.
   Tocou `src/motor_expansao/api/`? → nova imagem `api`. Só `dashboard/`? → o `web` republica,
   a `api`/bot NÃO (gotcha acima) — decide se precisa do `publish_api=true`.
2. **Confirmar CI verde + imagem publicada no GHCR** (deploy só por digest de imagem que passou CI). Se faltar imagem → disparar o dispatch correspondente (comandos acima) e **aguardar** (prometa "te aviso quando publicar" + PushNotification).
3. **Na VPS (cada comando com confirmação do Felipe, §6):** pinar `WEB_IMAGE`/`API_IMAGE` por **digest** no `.env` → `pull` → `up -d`/`restart` dos serviços afetados (`web`, `api`, `telegram-bot`) → healthcheck.
4. **Healthcheck:** `piloto.ultra-expansao.tech` (`/api/health` no container `web`) + `api.ultra-expansao.tech` respondendo; conferir os **digests** dos serviços.
5. **Reportar** os digests + tag ao Felipe (ele valida de relance). Nunca deployar sem CI verde; nunca usar `ssh` remoto.

## Guardrails
- §6 absoluto: NUNCA rodar comando na VPS sem confirmação explícita, comando-a-comando; não encadear.
- READ-ONLY sobre o M1: deploy não recalcula score nem regenera artefatos.
- Auto-merge NÃO deploya (push na main só publica no GHCR; subir na VPS é sempre passo humano).
- Runbooks canônicos: `docs/deploy_piloto_web.md`, `docs/deploy_api_bot.md`, `docs/infra_producao.md`, `docs/portao_merge_orq21.md`.
