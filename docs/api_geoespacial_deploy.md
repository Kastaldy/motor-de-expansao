# API GeoEspacial — Deploy e operação (BLK-API-06)

> Guia operacional para subir a **API GeoEspacial** e o **bot Telegram** em produção.
> Complementa o contrato (`api_geoespacial_contrato.md`) e o OpenAPI (`api_geoespacial_openapi.yaml`).
> READ-ONLY sobre o M1 (CLAUDE.md §5). A API não recalcula nem altera nenhum artefato oficial.

## 1. O que sobe

Dois processos independentes (o bot fala com a API por HTTP, desacoplado):

| Processo | O que é | Porta |
|---|---|---|
| **API** | FastAPI/uvicorn — `GET /health`, `POST /api/v1/analisar` (JSON/PDF) | 8077 (default) |
| **Bot** | Long-polling do Telegram que consome a API | — |

O bot é opcional: a API funciona sozinha (qualquer cliente HTTP com token).

## 2. Instalação

```bash
# Na raiz do repo (motor-de-expansao/):
pip install -e ".[api_mvp,basemap,geocoder]"
```

Extras necessários e o que cada um cobre:

- **`api_mvp`** — `fastapi`, `uvicorn`, `pydantic`, `pydantic-settings` (a API em si). **Obrigatório.**
- **`basemap`** — `contextily`: fundo de ruas online do PDF (DEC-004). Sem ele, o PDF cai em
  fallback offline (mapas sem ruas), não quebra.
- **`geocoder`** — `selenium`, `webdriver-manager`: geocoder primário de **endereço+CEP** via Google
  Maps. Sem ele, o geocoding cai no Nominatim (`geopy`, já na base). **Requer Google Chrome instalado
  no host.**

As demais deps (pandas, pyarrow, pyproj, shapely, h3, fpdf2, pillow, geopy) já estão na base do
`pyproject.toml`. Python ≥ 3.11 (validado em 3.14).

## 3. Dados (READ-ONLY)

A API lê duas bases locais (nunca escreve):

- **Setores censitários:** `setores_censitarios_2022_geo/uf=XX/cod_municipio=NNNNNNN/part-000.parquet`
  (27 UFs, 5.571 municípios, 468.099 setores). Aponte via `API_CENSO_GEO_DIR`.
- **Malha municipal IBGE:** `municipios_*.geojson` (resolve coordenada → município). Via `API_IBGE_DIR`.

Opcionais (enriquecem o PDF; ausência = fallback gracioso): `API_ULTRA_DIR` (branding),
`API_STAGING_DIR` (SAM/concorrentes/Ultra), `API_COMPETITORS_LOGOS_DIR` (logos dos pins).

> **Importante (performance):** mantenha os dados em **disco local**, não no OneDrive. Medido: PDF de
> área densa cai de ~211 s (OneDrive) para ~9–27 s (local). Hoje em `C:/APIGeoEspacial-dados/`.

### Volumes do serviço `api` (docker-compose.prod.yml)

O serviço `api` monta os seguintes volumes read-only do host:

| Volume host | Caminho no container | Env correspondente | Obrigatório |
|---|---|---|---|
| `/opt/motor-expansao/data/outputs` | `/app/data/outputs` | `API_CENSO_GEO_DIR` | Sim |
| `/opt/motor-expansao/data/ibge` | `/app/data/ibge` | `API_IBGE_DIR` | Sim |
| `/opt/motor-expansao/data/staging` | `/app/data/staging` | `API_STAGING_DIR` | Não (SAM/concorrentes) |
| `/opt/motor-expansao/data/ultra` | `/app/data/ultra` | `API_ULTRA_DIR` | Não (branding PDF) |
| `/opt/motor-expansao/concorrentes` | `/app/concorrentes` | `API_COMPETITORS_LOGOS_DIR` | Não (logos pins) |

> O diretório `/opt/motor-expansao/concorrentes` já existe no host (usado também pelo serviço `web`).
> Sem este volume, os pins do mapa de Concorrentes caem em sigla de texto (fallback gracioso).

## 4. Configuração — variáveis de ambiente

Todas têm prefixo `API_` e podem ir no `.env` (gitignored) ou no ambiente do processo. Mapa completo
(campo de `settings.py` → env):

| Env | Default | Para quê |
|---|---|---|
| `API_ENVIRONMENT` | `development` | `production` desliga `/docs` e `/redoc`. |
| `API_TOKENS` | `{"dev-token":"dev-local"}` | Mapa JSON `token→consumidor` (auth). **Trocar em prod.** |
| `API_CORS_ORIGINS` | `["*"]` | Origens CORS. **Restringir em prod** (ver §6). |
| `API_CENSO_GEO_DIR` | `data/outputs/setores_censitarios_2022_geo` | Partições censitárias. |
| `API_IBGE_DIR` | `data/ibge` | Malha municipal. |
| `API_ULTRA_DIR` | `data/ultra` | Branding do PDF (opcional). |
| `API_STAGING_DIR` | `data/staging` | SAM/concorrentes/Ultra (opcional). |
| `API_COMPETITORS_LOGOS_DIR` | `None` (não definido) | Logos dos pins (opcional). Em produção VPS: `/app/concorrentes` (montado via volume). |
| `API_GOOGLE_MAPS_API_KEY` | `""` | Se preenchida, geocoding/reverse via Google; senão Nominatim. |
| **Bot** | | |
| `API_TELEGRAM_TOKEN` | `""` | Token do @BotFather. **Nunca commitar.** |
| `API_BASE_URL` | `http://127.0.0.1:8077` | Base da API que o bot consome. |
| `API_CALL_TOKEN` | `dev-token` | Token com que o bot se autentica (deve existir em `API_TOKENS`). |
| `API_BOT_SENHA` | `trocar-esta-senha` | Senha de acesso ao bot. **Trocar em prod.** |
| `API_BOT_SESSOES_PATH` | `bot_sessoes.json` | Onde persistir quem já logou (sobrevive a restart). |

Exemplo de `.env` mínimo de produção:

```dotenv
API_ENVIRONMENT=production
API_TOKENS={"tok-bot-telegram-aleatorio":"bot-telegram"}
API_CORS_ORIGINS=https://seu-front.exemplo.com
API_CENSO_GEO_DIR=C:/APIGeoEspacial-dados/outputs/setores_censitarios_2022_geo
API_IBGE_DIR=C:/APIGeoEspacial-dados/ibge
API_ULTRA_DIR=C:/APIGeoEspacial-dados/ultra
API_STAGING_DIR=C:/APIGeoEspacial-dados/staging
API_COMPETITORS_LOGOS_DIR=C:/APIGeoEspacial-dados/Logos
API_TELEGRAM_TOKEN=123456:ABC-token-do-botfather
API_CALL_TOKEN=tok-bot-telegram-aleatorio
API_BOT_SENHA=uma-senha-forte
```

## 5. Como rodar

A partir da raiz do repo, com o venv ativo:

```bash
# API (porta 8077)
PYTHONPATH=src python -m uvicorn motor_expansao.api.main:app --host 0.0.0.0 --port 8077

# Bot (processo separado)
PYTHONIOENCODING=utf-8 PYTHONPATH=src python -m motor_expansao.api.telegram_bot
```

Verificar:

```bash
curl http://127.0.0.1:8077/health
# {"status":"ok","environment":"production"}

# defina o token antes: export API_TOKEN="<token-do-API_TOKENS>"
curl -X POST http://127.0.0.1:8077/api/v1/analisar \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"lat":-23.5505,"lng":-46.6333}'
```

> **Nota Windows:** o `.venv\Scripts\python.exe` é um redirecionador — cada `python -m` aparece como
> 2 processos (pai redirector + filho real). 2 processos = **um** serviço lógico, não duplicata. Para
> matar zumbis de verdade, use `taskkill /F /PID <pid-do-filho>`.

## 6. Checklist de hardening de produção

- [ ] `API_ENVIRONMENT=production` (desliga a doc interativa `/docs` e `/redoc`).
- [ ] `API_TOKENS` com tokens reais e aleatórios (não `dev-token`).
- [ ] `API_BOT_SENHA` forte (o default é `trocar-esta-senha`).
- [ ] **Regenerar o token do bot** no @BotFather — o token anterior foi exposto em chat.
- [ ] `API_CORS_ORIGINS` restrito ao(s) front(s) reais. **Não** deixar `["*"]`: combinado com
      `allow_credentials=True`, o navegador rejeita; para clientes server-to-server (bot) é inócuo,
      mas restringir é a higiene correta.
- [ ] Dados em **disco local** (não OneDrive) — ver §3.
- [ ] Chrome instalado no host se quiser o geocoder de endereço+CEP (`[geocoder]`).
- [ ] Rodar atrás de um reverse proxy (TLS) se exposto fora da rede interna.

## 7. Observabilidade

A API loga em stdout pelo logger `motor_expansao.api` (handler próprio, idempotente):

- **Acesso:** uma linha `INFO` por request — `MÉTODO /rota -> status (N ms)`.
- **Erros 500:** o `unexpected_error_handler` grava `ERROR` com o **traceback completo**
  (`exc_info`) — nenhuma falha inesperada some silenciosamente. O corpo devolvido ao cliente segue o
  contrato §9: `{"detail":"Erro interno ao gerar o estudo","codigo":"erro_interno"}`.
- O bot loga `[ESTUDO] login=...` no stdout (rastreio de quem solicitou).

Para enviar a um coletor, redirecione o stdout dos processos (systemd journal, Docker logs, etc.).

## 8. Empacotamento

A API é containerizada pelo `Dockerfile.api` da raiz (imagem `motor-expansao-api`, compartilhada
com o bot — runbook em `docs/deploy_api_bot.md`; o `Dockerfile.web` é do piloto e o
`fora_primeira_fase/api_postgis/Dockerfile.api` é legado PostGIS — não usar). A receita: base
Python 3.11+, `".[api_mvp,basemap,geocoder]"` + Google Chrome, dados montados como volume
read-only e porta 8077 com o uvicorn do §5.

## 9. Referências

- `docs/api_geoespacial_contrato.md` — contrato técnico (DEC-005).
- `docs/api_geoespacial_openapi.yaml` — esquema OpenAPI 3.1.
- `docs/relatorio_pontual_censitario.md` — contrato do relatório importado.
- CLAUDE.md §2/§4/§5; DEC-004 (basemap), DEC-005 (API).
