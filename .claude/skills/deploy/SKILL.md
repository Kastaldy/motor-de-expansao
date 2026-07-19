---
name: deploy
description: Conduz o deploy de produção do Motor (Streamlit + API/bot Telegram) na VPS, por digest imutável, passo a passo. Cobre o gotcha do publish-api (mudança só em dashboard/ NÃO rebuilda a imagem api/bot) e a matriz de capacidade da VPS. Use ao pedir "faça o deploy", "leve para prod", "suba na VPS", "atualize produção".
---

# /deploy — deploy de produção por digest (Streamlit + API/bot)

Encapsula a sequência de deploy para não virar 7 idas-e-voltas por sessão. **Deploy é SEMPRE manual,
por digest, e cada comando na VPS exige confirmação explícita do Felipe (CLAUDE.md §6, guardrail
absoluto).** Esta skill organiza o procedimento e não dispensa a confirmação comando-a-comando.

## Gotcha crítico (a causa nº 1 de "o bot ficou velho")
O `publish-api` tem **filtro de path**: um PR/commit que muda **só `dashboard/`** publica a imagem do
Streamlit mas **NÃO rebuilda a imagem `api`/`telegram-bot`**. Se a feature toca render usado pela API/bot,
republicar manualmente após o merge:
```
gh workflow run ci.yml --ref main -f publish_api=true -f dispatch_build_sanity=false
```
→ deploya `api` + `telegram-bot` por `API_IMAGE`. Runbook: `docs/deploy_api_bot.md`.

## Matriz de capacidade da VPS (consulte ANTES de dizer "não consigo")
- `scp` para a VPS = **SIM**, via `~/.ssh/id_ultra_mcp` (o classificador bloqueia `ssh` remoto, não `scp`; memória `deploy-vps-scp-arquivos`). Validar por `md5sum` na VPS.
- `ssh` remoto interativo = **NÃO** (bloqueado). Use o MCP `ssh-vps-ultra` (read/edit) para inspeção.
- Nunca declarar incapacidade de enviar arquivo à VPS sem antes **testar** o `scp`.

## Passos
1. **Determinar o alvo.** `git diff --name-only origin/main~1 origin/main` (ou os paths do ciclo): mudou só `dashboard/`? tocou `api/`/core? → decide se precisa do `publish_api=true`.
2. **Confirmar CI verde + imagem publicada no GHCR** (deploy só por digest de imagem que passou CI). Se só-dashboard e a feature afeta a API/bot → disparar o `publish-api` (comando acima) e **aguardar** (prometa "te aviso quando publicar" + PushNotification).
3. **Na VPS (cada comando com confirmação do Felipe, §6):** pull por **digest** → `up -d`/`restart` dos serviços afetados (`streamlit`, `api`, `telegram-bot`) → healthcheck.
4. **Healthcheck:** dashboard + `api.ultra-expansao.tech` respondendo; conferir os **digests** dos 3 serviços.
5. **Reportar** os digests + tag ao Felipe (ele valida de relance). Nunca deployar sem CI verde; nunca usar `ssh` remoto.

## Guardrails
- §6 absoluto: NUNCA rodar comando na VPS sem confirmação explícita, comando-a-comando; não encadear.
- READ-ONLY sobre o M1: deploy não recalcula score nem regenera artefatos.
- Auto-merge NÃO deploya (push na main só publica no GHCR; subir na VPS é sempre passo humano).
- Runbooks canônicos: `docs/infra_producao.md`, `docs/deploy_api_bot.md`, `docs/portao_merge_orq21.md`.
