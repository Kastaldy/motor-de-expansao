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

## Subir/atualizar (build na VPS, comando a comando)

A API/bot **não** seguem o modelo PULL-por-digest do Streamlit (sem job de publish ainda);
a imagem é construída na VPS a partir do código já versionado (`git pull` na pasta `app/`).

```bash
cd /opt/motor-expansao/app
git pull                                   # traz Dockerfile.api + serviços no compose
# (preencher os API_* no .env antes — ver acima)
docker compose -f docker-compose.prod.yml build api          # ~Chrome+deps, alguns minutos
docker compose -f docker-compose.prod.yml up -d api telegram-bot
docker compose -f docker-compose.prod.yml ps
# saúde da API (sem porta no host -> via container):
docker exec motor_expansao_api curl -fsS http://127.0.0.1:8077/health
docker compose -f docker-compose.prod.yml logs --tail=50 telegram-bot
```

- Caddy/Authelia/Streamlit **não** reiniciam.
- Sessões do bot persistem no volume `bot_data` (restart não desloga usuários).
- O primeiro geocode por endereço baixa o chromedriver (webdriver-manager) — precisa de
  internet na VPS (já tem). `lat,lng`/link do Maps não dependem disso.

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
