# Deploy — API GeoEspacial + Bot Telegram (BLK-API-06/07)

> Complementa `docs/infra_producao.md`. A API e o bot rodam como **dois containers
> novos na MESMA VPS** (`root@2.25.137.241`), na mesma rede `app_net`, **sem porta
> pública**. O bot é long-polling: roda 24/7 na VPS, independente do PC do usuário.
> GUARDRAIL CLAUDE.md §6: todo comando na VPS é passo humano, comando a comando.
>
> **Relação com `docs/api_geoespacial_deploy.md` (BLK-API-06):** aquele doc descreve
> a API/bot como **processos** (uvicorn + `python -m`) e o contrato/config/observabilidade
> (variáveis `API_*`, logs, hardening). **Este** doc é a **containerização** (o "como
> empacotar" do §8 daquele) via `Dockerfile.api` + serviços no compose. Para o detalhe
> de cada variável de ambiente e do contrato, ver o doc do BLK-API-06; o extra das
> dependências do geocoder é o **`geocoder`** (`.[basemap,api_mvp,geocoder]`).

## Arquitetura

```
caddy ─► streamlit (dashboard)        [já existia]
     └─► authelia  (login)            [já existia]

telegram-bot ──HTTP interno──► api ──► volumes :ro (outputs + ibge + staging + ultra)
  (long-polling p/ Telegram,          (FastAPI/uvicorn, porta 8077 só na rede interna)
   Google Chrome p/ geocoder)
```

- **Imagem única** (`Dockerfile.api`) para os dois serviços; o bot inclui Google Chrome
  porque o geocoder de endereço+CEP usa Selenium (`maps_geocoder`).
- A API **não tem porta no host**; só o bot a consome via `http://api:8077`.
- Não afeta a imagem do Streamlit (`Dockerfile.streamlit`, `.[basemap]`).

## Pré-condições de dados na VPS (READ-ONLY, montados via volume)

| Caminho na VPS | Conteúdo | Obrigatório? |
|---|---|---|
| `data/outputs/setores_censitarios_2022_geo/` | malha de setores 2022 (~1,2 GB) | **Sim** (o relatório) |
| `data/ibge/municipios_*.geojson` | malha municipal (resolve lat,lng → município) | **Sim** (sem ela → 500) |
| `data/staging/{concorrentes_mapeados,unidades_ultra_mapeadas,hexagonos_mercado_mapeado}.parquet` | mercado/SAM + concorrentes/Ultra | Não (enriquece o PDF) |
| `data/ultra/` | assets de branding do PDF | Não (fallback de cor sólida) |

Subir os que faltam (do Windows, dev):
```powershell
scp -i "$env:USERPROFILE\.ssh\id_ultra" -r data/ibge   root@2.25.137.241:/opt/motor-expansao/data/
scp -i "$env:USERPROFILE\.ssh\id_ultra" data/staging/concorrentes_mapeados.parquet `
    data/staging/unidades_ultra_mapeadas.parquet data/staging/hexagonos_mercado_mapeado.parquet `
    root@2.25.137.241:/opt/motor-expansao/data/staging/
```

## Segredos (`.env` na VPS, gitignored)

Acrescentar ao `/opt/motor-expansao/app/.env` (modelo em `.env.example`):

| Var | O que é |
|---|---|
| `API_TOKENS` | JSON `token->consumidor`, ex.: `{"<tok-forte>":"bot-telegram"}` |
| `API_API_CALL_TOKEN` | token com que o bot chama a API — **deve** ser uma chave de `API_TOKENS` |
| `API_TELEGRAM_TOKEN` | token do bot do @BotFather |
| `API_BOT_SENHA` | senha de acesso ao bot |
| `API_GOOGLE_MAPS_API_KEY` | opcional; vazio = geocoder por Selenium/Chrome + Nominatim |

Gerar tokens fortes: `openssl rand -hex 24`.

## Subir/atualizar (PULL por digest, igual ao Streamlit)

A imagem `motor-expansao-api` é publicada no GHCR pelo job **`publish-api`** do CI
(`.github/workflows/ci.yml`) — **filtrado por caminho**: só rebuilda/publica quando mudam
`Dockerfile.api`, `src/motor_expansao/api/**` ou `pyproject.toml`. A VPS **puxa** por digest
(`API_IMAGE` no `.env`), sem buildar localmente. Execução na VPS é passo humano (§6).

> ⚠️ **GOTCHA — mudança em `dashboard/` NÃO dispara o rebuild da API.** A imagem da API
> **contém e executa** o código de `src/motor_expansao/dashboard/**` (o bot gera o PDF via
> `censo_report`/`censo_map`/`censo_point`). Mas o filtro de caminho do `publish-api` só olha
> `api/`/`Dockerfile.api`/`pyproject.toml` — então uma feature de **dashboard** (ex.: novo
> choropleth no Relatório Pontual, ajuste de legenda) sobe no **streamlit** pelo push na `main`,
> mas a imagem da **API/bot fica STALE**. Para propagar ao bot, **republique a API manualmente**
> após o merge: `gh workflow run ci.yml --ref main -f publish_api=true -f dispatch_build_sanity=false`,
> pegue o "API digest imutavel publicado" e faça o pull+up abaixo. Verificação de fechamento:
> `docker compose -f docker-compose.prod.yml exec -T api python -c "from motor_expansao.dashboard import censo_map as m; print(len(m.CAMADAS_CENSITARIAS), m.CAMADAS_CENSITARIAS)"`
> deve refletir o código novo. (Feito assim em 2026-07-17 para o mapa de renda domiciliar.)
> **Desde o BLK-RELPON-14 o esperado é `7` chaves** — a camada `entorno` saiu junto com o slide
> "Imagem do Entorno". Se a VPS ainda imprimir `8`, a imagem está **STALE**: hoje este contador é
> a forma mais barata de flagrar deploy velho da API/bot.

```bash
cd /opt/motor-expansao/app
# 1. Pinar o digest publicado (do job publish-api no Actions, "API digest imutavel publicado"):
#    edite API_IMAGE no .env:
#    API_IMAGE=ghcr.io/kastaldy/motor-de-expansao/motor-expansao-api@sha256:<digest>
# 2. Pull + up -d (SEM build)
docker compose -f docker-compose.prod.yml pull api telegram-bot
docker compose -f docker-compose.prod.yml up -d api telegram-bot
docker compose -f docker-compose.prod.yml ps
docker exec motor_expansao_api curl -fsS http://127.0.0.1:8077/health   # sem porta no host
docker compose -f docker-compose.prod.yml logs --tail=50 telegram-bot
```

- Caddy/Authelia/Streamlit **não** reiniciam.
- Sessões do bot persistem no volume `bot_data` (restart não desloga usuários).
- O primeiro geocode por endereço baixa o chromedriver (webdriver-manager) — precisa de
  internet na VPS (já tem). `lat,lng`/link do Maps não dependem disso.
- **Bootstrap / republish manual:** Actions → CI → "Run workflow" com `publish_api=true`
  (ou `gh workflow run ci.yml -f publish_api=true`). **Build local de dev/sanity:**
  `docker build -f Dockerfile.api -t motor-expansao-api:local .`
- **Rollback:** aponte `API_IMAGE` para o digest anterior e repita pull + up.

## Validação rápida do contrato

```bash
# JSON:
TOK=<tok de API_TOKENS>
docker exec motor_expansao_api curl -fsS -X POST http://127.0.0.1:8077/api/v1/analisar \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"lat":-23.55,"lng":-46.63}' | head -c 400
```

No Telegram: enviar a senha (`API_BOT_SENHA`) → menu → mandar `lat,lng`, link do Maps
ou endereço+CEP → recebe o PDF.

## Rollback

```bash
cd /opt/motor-expansao/app
docker compose -f docker-compose.prod.yml stop telegram-bot api
# (opcional) remover: docker compose -f docker-compose.prod.yml rm -f telegram-bot api
```
Os demais serviços seguem intactos. Nenhum artefato/score do M1 é tocado (READ-ONLY).
