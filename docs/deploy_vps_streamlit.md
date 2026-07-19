> **[HISTORICO]** Runbook generico de VPS Streamlit, sobreposto por `docs/infra_producao.md` + `docs/deploy.md`.

# Deploy Streamlit em VPS

Runbook curto para publicar o dashboard executivo em uma VPS usando Docker.

## Escopo

- Sobe somente o `streamlit_app.py`.
- Le Parquets locais em `data/outputs/` montados como volume.
- Nao usa API/FastAPI, PostGIS, Prefect, scraping ou recalculo do M1.
- Nao embute dados na imagem.
- Nao exige internet/API externa em runtime.

## Pre-requisitos

- Docker Engine e Docker Compose plugin instalados na VPS.
- Repositorio clonado no servidor.
- Pacote minimo de Parquets copiado para `data/outputs/`.
- Porta interna do app: `8501`.
- Proxy HTTPS externo recomendado, com autenticacao para uso interno.

Artefatos minimos esperados:

```text
data/outputs/hexagonos_brasil_dashboard.parquet
data/outputs/oportunidades_expansao_hibrido.parquet
data/outputs/carteira_expansao_acionavel.parquet
data/outputs/plano_expansao_curto_prazo.parquet
```

Validar artefatos antes do build:

```bash
python scripts/check_artifacts.py
```

## Build e subida

```bash
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps
```

Para usar porta externa diferente:

```bash
STREAMLIT_PORT=8080 docker compose -f docker-compose.prod.yml up -d
```

## Smoke test

No servidor:

```bash
curl -fsS http://127.0.0.1:8501/_stcore/health
docker compose -f docker-compose.prod.yml logs --tail=80 streamlit
```

De uma maquina autorizada, abrir:

```text
http://IP_DA_VPS:8501
```

Em producao, preferir expor apenas o proxy HTTPS e manter a porta `8501` restrita no firewall.

## Proxy HTTPS e autenticacao

Recomendacao operacional:

- publicar o app atras de Nginx, Caddy, Traefik ou proxy gerenciado;
- ativar HTTPS;
- proteger com autenticacao no proxy, VPN, allowlist de IP ou SSO;
- nao colocar credenciais no repositorio nem em `docker-compose.prod.yml`.

Exemplo conceitual de rota no proxy:

```text
https://dashboard.ultra-interno.example -> http://127.0.0.1:8501
```

## Atualizacao

> **Modo recomendado (pull):** a imagem agora e buildada no CI e publicada no GHCR; o
> servidor faz `pull` + `up -d` sem `--build`. Ver o runbook canonico em `docs/deploy.md`.
> O fluxo `git pull` + `build` abaixo permanece como alternativa de build local.

```bash
git pull
python scripts/check_artifacts.py
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps
```

Se os Parquets mudarem, substituir os arquivos em `data/outputs/` e reiniciar:

```bash
docker compose -f docker-compose.prod.yml restart streamlit
```

## Troubleshooting

- `check_artifacts.py` falha: copiar os 4 Parquets minimos para `data/outputs/`.
- Healthcheck falha: ver `docker compose -f docker-compose.prod.yml logs streamlit`.
- Aba censitaria degradada: montar tambem os Parquets opcionais de `data/staging/`, se a auditoria local exigir.
- App lento no primeiro acesso: carregamento inicial dos Parquets e cache do Streamlit.
