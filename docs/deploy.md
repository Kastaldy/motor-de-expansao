# Deploy do piloto web — modo PULL (imagem do GHCR)

Runbook curto para atualizar o piloto web no VPS **puxando** a imagem publicada no
GitHub Container Registry (GHCR), sem `build` no servidor. Desde a DEC-022 (2026-08-03)
o piloto web e o app de producao (o dashboard Streamlit foi aposentado). A imagem e
construida e publicada pelo job `publish-web` do workflow `CI`
(`.github/workflows/ci.yml`), que so publica quando o job `test` conclui com sucesso
(gate `needs: [test]`); o servidor so faz `pull` + `up -d`. O runbook completo
(DNS, Caddy, Authelia, dados, checklist pos-deploy) e `docs/deploy_piloto_web.md` —
este doc cobre so o ciclo rotineiro de atualizacao.

> GUARDRAIL CLAUDE.md §6: nenhum comando e executado no VPS por agente/MCP/SSH sem
> confirmacao explicita do usuario, **comando a comando**. Os passos abaixo sao
> documentacao operacional — a execucao no servidor e SEMPRE passo humano.

## Visao geral

- O job `publish-web` do workflow `CI` builda `Dockerfile.web` (estagio Node para o
  Vite + estagio Python para o backend FastAPI) e publica em
  `ghcr.io/kastaldy/motor-de-expansao/motor-expansao-web` com:
  - tag `sha-<commit>` (rastreavel por commit) e
  - tag `latest` (apenas em push na `main`).
  Publica SOMENTE quando o job `test` conclui com sucesso (`needs: [test]`) e, em push
  na `main`, apenas se o diff tocar o path-filter (`Dockerfile.web`, `web/**`,
  `src/motor_expansao/(dashboard|dimensionamento|api)/**`, `pyproject.toml`).
  Scan Trivy HIGH/CRITICAL e BLOQUEANTE antes do push.
- Um container serve tudo (`web`, container `motor_expansao_web`): o SPA (build do
  Vite) e a API em `/api/*` na porta interna `8899`, atras do Caddy + Authelia em
  `piloto.ultra-expansao.tech`. O subdominio `dashboard.ultra-expansao.tech` serve
  apenas `/tiles/*` (tileserver) e redireciona a raiz (301) para o piloto (DEC-022).
- O `docker-compose.prod.yml` referencia a imagem via variavel de override
  OBRIGATORIA (fail-closed, sem default cego):
  `image: ${WEB_IMAGE:?... ver docs/deploy_piloto_web.md}`.
  Producao DEVE definir `WEB_IMAGE` por digest imutavel (`@sha256:<digest>`);
  `up` sem a variavel falha de proposito. Nao ha `build:` ativo no compose de producao.
- A imagem **nao** embute dados nem segredos: `data/`, `concorrentes/`, `.env`,
  `Caddyfile`, `authelia/`, `secrets/` ficam fora do contexto de build (`.dockerignore`)
  e entram em runtime por volume read-only / variavel de ambiente.

## Pre-condicoes (no VPS, ja existentes)

- Imagem publicada no GHCR pelo workflow (tag `sha-<commit>` ou `latest`).
- `.env` (com `WEB_IMAGE` pinado), `Caddyfile`, `authelia/*` presentes em
  `/opt/motor-expansao/app/`.
- Parquets em `/opt/motor-expansao/data/{outputs,staging,ibge,ultra}` e
  `concorrentes/` (montados read-only). A lista do que o piloto precisa — e o que
  degrada em silencio sem cada arquivo — esta no §2 de `docs/deploy_piloto_web.md`.

## Login no GHCR (se o pacote for privado)

Se o pacote GHCR estiver privado, o servidor precisa autenticar uma vez com um PAT
(classic) com escopo `read:packages`:

```bash
echo "$GHCR_PAT" | docker login ghcr.io -u <usuario-github> --password-stdin
```

> O PAT `read:packages` e credencial de runtime do servidor — NAO e segredo de CI
> e NAO entra no repositorio. Se o pacote for publico, o login e dispensavel.

## Atualizacao (pull + up -d, SEM --build)

```bash
# 1. Pinar a imagem alvo no .env da VPS (/opt/motor-expansao/app/.env).
#    WEB_IMAGE e OBRIGATORIO (o compose e fail-closed: sem essa variavel,
#    `up`/`pull` falha de proposito). Preferir DIGEST imutavel:
WEB_IMAGE=ghcr.io/kastaldy/motor-de-expansao/motor-expansao-web@sha256:<digest>
#   alternativa rastreavel por commit: ...motor-expansao-web:sha-<commit>

# 2. Puxar a imagem (sem build)
docker compose -f docker-compose.prod.yml pull web

# 3. Subir/recriar so o servico web (SEM --build)
docker compose -f docker-compose.prod.yml up -d web

# 4. Conferir estado e saude
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=80 web
docker compose -f docker-compose.prod.yml exec web curl -fsS http://127.0.0.1:8899/api/health
```

## Rollback (por digest imutavel)

```bash
# Apontar WEB_IMAGE (no .env da VPS) para o DIGEST imutavel do deploy anterior
# (pin canonico) e refazer pull + up -d. O digest garante reproducao byte-identica.
WEB_IMAGE=ghcr.io/kastaldy/motor-de-expansao/motor-expansao-web@sha256:<digest_anterior>
#   alternativa rastreavel por commit: ...motor-expansao-web:sha-<commit_anterior>
docker compose -f docker-compose.prod.yml pull web
docker compose -f docker-compose.prod.yml up -d web
docker compose -f docker-compose.prod.yml ps
```

## Atualizacao de Parquets

Se apenas os Parquets mudarem (imagem inalterada), substituir os arquivos em
`/opt/motor-expansao/data/` (subdiretorio correspondente) e reiniciar o servico:

```bash
docker compose -f docker-compose.prod.yml restart web
```

## Troubleshooting

- `docker compose pull` falha com `denied`/`unauthorized`: pacote GHCR privado sem
  login — refazer o `docker login ghcr.io` com PAT `read:packages`.
- Healthcheck falha: `docker compose -f docker-compose.prod.yml logs web`.
- Imagem stale: mudanca fora do path-filter do `publish-web` nao republica —
  disparar manual:
  `gh workflow run ci.yml --ref main -f publish_web=true -f dispatch_build_sanity=false`.
- Primeira carga de uma UF lenta: o Mapa Territorial le a particao inteira de
  `hexagonos_dashboard_enriquecido` no primeiro acesso.

## Referencias

- Runbook completo do piloto (DNS, Caddy, Authelia, dados, checklist, gotchas):
  `docs/deploy_piloto_web.md`.
- Build local de sanity (independe do compose): `docker build -f Dockerfile.web -t test:web .`
- API GeoEspacial + bot Telegram (`API_IMAGE`): `docs/deploy_api_bot.md`.
- Infra real do servidor (Caddy/Authelia/tileserver): `docs/infra_producao.md`.
- Backup/restore de segredos e regeneracao de Parquets: `docs/backup_restore.md`.
