# Deploy do dashboard Streamlit — modo PULL (imagem do GHCR)

Runbook curto para atualizar o dashboard no VPS **puxando** a imagem publicada no
GitHub Container Registry (GHCR), sem `build` no servidor. A imagem e construida e
publicada pelo job `publish` do workflow `CI` (`.github/workflows/ci.yml`), que so
publica quando o job `test` conclui com sucesso (gate `needs: [test]`); o servidor so
faz `pull` + `up -d`.

> GUARDRAIL CLAUDE.md §6: nenhum comando e executado no VPS por agente/MCP/SSH sem
> confirmacao explicita do usuario, **comando a comando**. Os passos abaixo sao
> documentacao operacional — a execucao no servidor e SEMPRE passo humano.

## Visao geral

- O job `publish` do workflow `CI` (`.github/workflows/ci.yml`) builda
  `Dockerfile.streamlit` e publica em
  `ghcr.io/kastaldy/motor-de-expansao/motor-expansao-streamlit` com:
  - tag `sha-<commit>` (rastreavel por commit) e
  - tag `latest` (apenas em push na `main`).
  Publica SOMENTE quando o job `test` conclui com sucesso (`needs: [test]`).
- O `docker-compose.prod.yml` referencia a imagem via variavel de override
  OBRIGATORIA (fail-closed, sem default cego):
  `image: ${STREAMLIT_IMAGE:?... ver docs/infra_producao.md}`.
  Producao DEVE definir `STREAMLIT_IMAGE` por digest imutavel (`@sha256:<digest>`);
  `up` sem a variavel falha de proposito. Nao ha mais `build:` ativo no compose de producao.
- A imagem **nao** embute dados nem segredos: `data/`, `concorrentes/`, `.env`,
  `Caddyfile`, `authelia/`, `secrets/` ficam fora do contexto de build (`.dockerignore`)
  e entram em runtime por volume read-only / variavel de ambiente.

## Pre-condicoes (no VPS, ja existentes)

- Imagem publicada no GHCR pelo workflow (tag `sha-<commit>` ou `latest`).
- `.env`, `Caddyfile`, `authelia/*` presentes em `/opt/motor-expansao/`.
- Parquets em `/opt/motor-expansao/data/outputs/` (montados read-only).
- `concorrentes/` e `data/ultra/` presentes se a aba censitaria/mercado exigir.

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
# 1. Definir a imagem alvo. STREAMLIT_IMAGE e OBRIGATORIO (o compose e fail-closed:
#    sem essa variavel, `up`/`pull` falha de proposito). Preferir DIGEST imutavel:
export STREAMLIT_IMAGE=ghcr.io/kastaldy/motor-de-expansao/motor-expansao-streamlit@sha256:<digest>
#   alternativa rastreavel por commit: ...motor-expansao-streamlit:sha-<commit>

# 2. Puxar a imagem (sem build)
docker compose -f docker-compose.prod.yml pull streamlit

# 3. Subir/recriar so o servico streamlit (SEM --build)
docker compose -f docker-compose.prod.yml up -d streamlit

# 4. Conferir estado e saude
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=80 streamlit
curl -fsS http://127.0.0.1:8501/_stcore/health
```

## Rollback (por digest imutavel)

```bash
# Apontar para o DIGEST imutavel do deploy anterior (pin canonico) e refazer pull + up -d.
# O digest garante reproducao byte-identica da imagem anterior.
export STREAMLIT_IMAGE=ghcr.io/kastaldy/motor-de-expansao/motor-expansao-streamlit@sha256:<digest_anterior>
#   alternativa rastreavel por commit: ...motor-expansao-streamlit:sha-<commit_anterior>
docker compose -f docker-compose.prod.yml pull streamlit
docker compose -f docker-compose.prod.yml up -d streamlit
docker compose -f docker-compose.prod.yml ps
```

## Atualizacao de Parquets

Se apenas os Parquets mudarem (imagem inalterada), substituir os arquivos em
`/opt/motor-expansao/data/outputs/` e reiniciar o servico:

```bash
docker compose -f docker-compose.prod.yml restart streamlit
```

## Troubleshooting

- `docker compose pull` falha com `denied`/`unauthorized`: pacote GHCR privado sem
  login — refazer o `docker login ghcr.io` com PAT `read:packages`.
- Healthcheck falha: `docker compose -f docker-compose.prod.yml logs streamlit`.
- App lento no primeiro acesso: carga inicial dos Parquets + cache do Streamlit.

## Referencias

- Build local de sanity (independe do compose): `docker build -f Dockerfile.streamlit -t test:ci .`
- Runbook anterior (modo build) e contexto de proxy/HTTPS/Authelia: `docs/deploy_vps_streamlit.md`.
- Backup/restore de segredos e regeneracao de Parquets: `docs/backup_restore.md`.
