# API GeoEspacial — Guia de uso ponta-a-ponta

> Fonte única de USO da API GeoEspacial Ultra Academia.
> Para o contrato/decisões de design: [docs/api_geoespacial_contrato.md](api_geoespacial_contrato.md)
> Para a spec OpenAPI: [docs/api_geoespacial_openapi.yaml](api_geoespacial_openapi.yaml)
> Para instalação, deploy e VPS: [docs/api_geoespacial_deploy.md](api_geoespacial_deploy.md) / [docs/deploy_api_bot.md](deploy_api_bot.md)
> READ-ONLY sobre o M1 (CLAUDE.md §5).

---

## 1. Visão geral e arquitetura

A API GeoEspacial é uma camada de consumo **on-demand** do Motor de Expansão, complementar ao
dashboard Streamlit. Ela expõe o **Relatório Pontual Censitário 1,5 km** (KPIs em JSON e PDF de
7 páginas) para qualquer cliente HTTP com token — incluindo o bot Telegram "Paulo".

**Dois serviços independentes** (desacoplados; o bot consome a API por HTTP):

| Serviço | O que é | Porta |
|---|---|---|
| **API** | FastAPI/uvicorn — `GET /health` + `POST /api/v1/analisar` (JSON/PDF) | 8077 (interna) |
| **Bot** | Long-polling Telegram 24/7 que consome a API | — |

**Diagrama simplificado:**

```
telegram-bot ──HTTP──> api ──Parquets locais──> motor censo_*
```

**Versão do contrato:** `api-geoespacial/v1` (campo `versao_contrato` na resposta JSON).

**Dados lidos (READ-ONLY):**
- `data/outputs/setores_censitarios_2022_geo/` — malha censitária (27 UFs, 5.571 municípios)
- `data/ibge/municipios_*.geojson` — resolve coordenada → município
- `data/staging/` — concorrentes/Ultra/SAM (opcional; ausência = fallback gracioso)

**Docs interativos** (`/docs` Swagger UI e `/redoc`): disponíveis **apenas** quando
`API_ENVIRONMENT != "production"`. Em produção, usar `docs/api_geoespacial_openapi.yaml` localmente.

**Raio fixo: 1,5 km.** Não é parâmetro de entrada — é o método canônico
`setor_censitario_intersecao_area_1p5km`, INTOCÁVEL (CLAUDE.md §4).

---

## 2. Autenticação

Todas as rotas — exceto `GET /health` — exigem autenticação por **Bearer token**.

**Header obrigatório:**
```
Authorization: Bearer <token>
```

**Mapa token → consumidor:** configurado via variável de ambiente `API_TOKENS` (JSON string).
```bash
# Exemplo de configuração no .env:
API_TOKENS='{"tok-real":"bot-telegram","tok-felipe":"felipe"}'
```

**Comportamento em caso de erro:**
- Token ausente ou inválido → HTTP `401` com corpo:
  ```json
  {"detail": "Token invalido", "codigo": "nao_autenticado"}
  ```

**Padrão dev (default de settings):**
```
dev-token  →  dev-local
```
O default funciona sem `.env` em ambiente de desenvolvimento local; **nunca usar em produção**.

**Como criar/rotacionar tokens:** editar `API_TOKENS` no `.env` e reiniciar o processo.
A lista é estática no MVP — sem endpoint de admin.

**Gotcha de produção:** `API_TOKENS` deve ser JSON válido com aspas externas no shell:
```bash
# CORRETO
API_TOKENS='{"tok-real":"bot-telegram"}'

# ERRADO (parse falhará)
API_TOKENS=tok-real:bot-telegram
```

---

## 3. Endpoints

### 3a. `GET /health`

Liveness check — **sem autenticação**.

```
GET /health
```

Resposta `200`:
```json
{"status": "ok", "environment": "development"}
```

Também disponível como alias (sem auth): `GET /api/v1/health`.

Uso típico: monitoramento do load balancer e do docker compose.

---

### 3b. `POST /api/v1/analisar`

Endpoint principal. Recebe um ponto geográfico e devolve o estudo censitário em **JSON** (default)
ou **PDF** (7 páginas).

#### Request body (`AnalisarRequest`)

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `lat` | `float` | Sim (se sem `maps_url`) | Latitude decimal |
| `lng` | `float` | Sim (se sem `maps_url`) | Longitude decimal |
| `maps_url` | `string` | Alternativa a `lat`/`lng` | Link do Google Maps; parser puro, sem rede |
| `formato` | `"json"` / `"pdf"` | Não (default `"json"`) | Atalho de negociação no body |
| `rotulo` | `string` / `null` | Não | Nome do endereço/estabelecimento na capa do PDF |

**Regra:** fornecer `{lat, lng}` **OU** `maps_url` — ambos ausentes → `422`.

#### Negociação de conteúdo (JSON × PDF)

JSON é o padrão. PDF é ativado por qualquer das 3 formas abaixo (em ordem de precedência):

1. Header `Accept: application/pdf` na request
2. Query param `?formato=pdf`
3. Campo `"formato": "pdf"` no body JSON

#### Response JSON (`AnalisarResponseJSON`) — campos completos

| Campo | Tipo | Descrição |
|---|---|---|
| `lat` | `float` | Latitude resolvida |
| `lng` | `float` | Longitude resolvida |
| `raio_km` | `float` | Raio do estudo (1,5 km) |
| `area_km2` | `float \| null` | Área da interseção em km² |
| `metodo` | `string` | `"setor_censitario_intersecao_area_1p5km"` |
| `n_setores` | `int` | Setores IBGE 2022 cruzados |
| `pop_total_raio` | `float \| null` | População total no raio |
| `renda_per_capita_media_raio` | `float \| null` | Renda per capita média ponderada |
| `densidade_pop_raio_hab_km2` | `float \| null` | Densidade populacional (hab/km²) |
| `score_setor_medio` | `float \| null` | Score censitário médio ponderado |
| `score_setor_max` | `float \| null` | Score censitário máximo no raio |
| `n_concorrentes` | `int` | Academias concorrentes no raio |
| `n_ultra` | `int` | Unidades Ultra no raio |
| `versao_contrato` | `string` | `"api-geoespacial/v1"` |
| `versao_score` | `string` | `"score_setor_2022_calibrado"` |
| `gerado_em` | `string` | Timestamp ISO 8601 UTC |
| `consumidor` | `string \| null` | Token → consumidor (rastreio LGPD) |

**Nota sobre SAM/residual:** os campos de mercado (`sam_fitness_potencial`,
`oferta_efetiva_disponivel`, `score_oportunidade_residual`, `oferta_consumida_mercado_estimada`)
são preenchidos no Big Numbers do PDF quando `data/staging/hexagonos_mercado_mapeado.parquet`
existir no path configurado. Ausência é silenciosa (campos `null`).

#### Response PDF

```
Content-Type: application/pdf
Content-Disposition: inline; filename="relatorio_pontual_censitario.pdf"
```

PDF de 7 páginas: Capa → População → Renda → Score censitário → Concorrentes →
Big Numbers → Realização/Crédito.

**Performance:** a primeira chamada pode levar de 10 a 30 s (cold load dos Parquets +
busca de tiles de mapa). Chamadas subsequentes ao mesmo município são mais rápidas
(cache em memória). Timeout do bot: 240 s.

---

## 4. Exemplos curl

### Health (sem auth)

```bash
curl http://localhost:8077/health
```

### Analisar por lat/lng — retorno JSON

```bash
curl -s -X POST http://localhost:8077/api/v1/analisar \
  -H "Authorization: Bearer dev-token" \
  -H "Content-Type: application/json" \
  -d '{"lat": -21.9180, "lng": -46.6855}'
```

### Analisar por link do Maps — retorno JSON

```bash
curl -s -X POST http://localhost:8077/api/v1/analisar \
  -H "Authorization: Bearer dev-token" \
  -H "Content-Type: application/json" \
  -d '{"maps_url": "https://maps.google.com/?q=-21.9180,-46.6855"}'
```

### Analisar e baixar o PDF — as 3 formas equivalentes

```bash
# Forma 1: query param
curl -s -X POST "http://localhost:8077/api/v1/analisar?formato=pdf" \
  -H "Authorization: Bearer dev-token" \
  -H "Content-Type: application/json" \
  -d '{"lat": -21.9180, "lng": -46.6855, "rotulo": "Pastel da Sueli"}' \
  -o relatorio.pdf

# Forma 2: header Accept
curl -s -X POST http://localhost:8077/api/v1/analisar \
  -H "Authorization: Bearer dev-token" \
  -H "Content-Type: application/json" \
  -H "Accept: application/pdf" \
  -d '{"lat": -21.9180, "lng": -46.6855}' \
  -o relatorio.pdf

# Forma 3: campo no body
curl -s -X POST http://localhost:8077/api/v1/analisar \
  -H "Authorization: Bearer dev-token" \
  -H "Content-Type: application/json" \
  -d '{"lat": -21.9180, "lng": -46.6855, "formato": "pdf"}' \
  -o relatorio.pdf
```

---

## 5. Formatos de localização aceitos

O campo `maps_url` suporta 4 padrões de URL do Google Maps, aplicados em ordem de prioridade:

| Prioridade | Padrão | Exemplo | Observação |
|---|---|---|---|
| 1 | `!3d<lat>!4d<lng>` | `.../maps/place/...!3d-21.9180!4d-46.6855` | Pino exato do place — mais preciso |
| 2 | `@<lat>,<lng>` | `https://maps.google.com/...@-21.9180,-46.6855,17z` | Centro do viewport da câmera |
| 3 | Query params `?q=`, `?query=`, `?ll=`, `?sll=`, `?center=`, `?destination=` | `https://maps.google.com/?q=-21.9180,-46.6855` | Vários formatos de busca |
| 4 | `"lat,lng"` cru | `-21.9180,-46.6855` | String simples separada por vírgula |

**Links compactados** (ex.: `maps.app.goo.gl/...`, `goo.gl/maps/...`, encurtadores em geral):
expandidos automaticamente via redirect HTTP antes do parse — o bot faz isso de forma transparente.

**Bounding box de validação:** lat ∈ [-34,0; 5,5], lng ∈ [-74,0; -28,0] (inclui ilhas oceânicas:
Fernando de Noronha, Trindade). Pontos fora → `400 coordenada_invalida`.

---

## 6. Bot Telegram — Paulo

O bot "Paulo" é a interface conversacional da API para usuários do Telegram. Funciona por
**long-polling 24/7** na VPS, consumindo o `POST /api/v1/analisar` por HTTP.

### Fluxo da máquina de estados

```
1. Qualquer mensagem (1a interação)
   → "Olá! Eu sou o Paulo... Envie a senha de acesso."

2. Senha
   → Correta: "Senha correta! Como posso te chamar?"
   → Incorreta: repete pedido de senha

3. Nome/login
   → "Prazer, <nome>!" + menu [Relatorio | Ajuda]
   → "Me envie a localização do ponto agora."

4. Menu (qualquer momento após autorizado)
   "Relatorio" / /relatorio / /start  → pedido de localização
   "Ajuda"     / /ajuda    / /help    → mensagem de ajuda

5. Qualquer mensagem não-comando (localização)
   → ⏳ "Recebi! Estou localizando o ponto e gerando o Relatório..."
   → resolve coordenada (ver 3 formas abaixo)
   → se falhar: ❌ instrução dos formatos aceitos
   → se OK: PDF + "Pronto! Envie outra localização quando quiser."
```

### 3 formas de envio de localização

1. **Link do Google Maps** — completo ou compactado (expandido automaticamente):
   ```
   https://maps.app.goo.gl/xyz123
   https://www.google.com/maps/place/...!3d-21.9180!4d-46.6855
   ```

2. **Latitude, longitude** — separados por vírgula:
   ```
   -21.9180,-46.6855
   ```

3. **Endereço + CEP** — geocoding (Chrome/Selenium primário → Google Geocoding API → Nominatim):
   ```
   Av. Nossa Sra. do Loreto, 927, São Paulo - SP, 02232-000
   ```
   Recomendado apenas quando as opções 1 e 2 não estiverem disponíveis — menos preciso.

### Persistência de sessões

As sessões (quem já está logado) são salvas em `API_BOT_SESSOES_PATH`
(default: `bot_sessoes.json` na raiz do repo). Reiniciar o bot **não desloga** os usuários.

### Comandos disponíveis

| Comando / Botão | Ação |
|---|---|
| `/start` | Reinicia / pede localização |
| `Relatorio` / `/relatorio` | Pede localização para novo estudo |
| `Ajuda` / `/ajuda` / `/help` | Mostra descrição e formas de localização |

### Rodar o bot (com a API já no ar)

```bash
API_TELEGRAM_TOKEN=<token-do-botfather> python -m motor_expansao.api.telegram_bot
```

---

## 7. Tabela de erros

Todos os erros da API seguem o formato `{"detail": "<mensagem>", "codigo": "<slug>"}`.

| HTTP | `codigo` | Exemplo de `detail` | Quando ocorre |
|---|---|---|---|
| `400` | `coordenada_invalida` | `"Coordenada fora do Brasil"` | `lat`/`lng` fora do bounding box; `maps_url` não parseável; ponto sem município na malha |
| `401` | `nao_autenticado` | `"Token invalido"` | Header `Authorization` ausente ou token não encontrado no mapa |
| `404` | `base_geo_ausente` | `"Materialize setores_censitarios_2022_geo/ para SP/3550308"` | Partição censitária ausente para o município do ponto |
| `500` | `erro_interno` | `"Erro interno ao gerar o estudo"` | Qualquer exceção não tratada (stack trace no log do servidor) |

**Nota sobre `422`:** FastAPI retorna `422` (sem campo `codigo`) para erros de validação do
body Pydantic (ex.: body malformado, campos com tipo errado). Não faz parte do contrato
`{detail, codigo}`, mas pode ocorrer se o payload estiver sintaticamente inválido.

---

## 8. Variáveis de ambiente `API_*`

Todas as configurações usam o prefixo `API_` (pydantic-settings). Podem ser definidas
no `.env` na raiz do repo ou exportadas como variáveis de ambiente antes de subir o processo.

| Variável de env | Campo em `Settings` | Default | Descrição |
|---|---|---|---|
| `API_ENVIRONMENT` | `environment` | `"development"` | Ambiente; `"production"` desativa `/docs` e `/redoc` |
| `API_API_PREFIX` | `api_prefix` | `"/api/v1"` | Prefixo de versão das rotas |
| `API_CENSO_GEO_DIR` | `censo_geo_dir` | `data/outputs/setores_censitarios_2022_geo` | Malha censitária (READ-ONLY) |
| `API_IBGE_DIR` | `ibge_dir` | `data/ibge` | GeoJSONs municipais IBGE para ponto→município (READ-ONLY) |
| `API_ULTRA_DIR` | `ultra_dir` | `data/ultra` | Assets de branding do PDF (READ-ONLY, opcional) |
| `API_COMPETITORS_LOGOS_DIR` | `competitors_logos_dir` | `None` | Pasta com `logo_<rede>.png` para pins do mapa (opcional; fallback = sigla de texto) |
| `API_STAGING_DIR` | `staging_dir` | `data/staging` | Parquets de mercado/concorrentes/Ultra (READ-ONLY, opcional) |
| `API_CORS_ORIGINS` | `cors_origins` | `["*"]` | Origens CORS; em produção restringir: `'["https://meudominio.com"]'` |
| `API_TOKENS` | `tokens` | `{"dev-token": "dev-local"}` | Mapa token→consumidor (JSON string) |
| `API_TELEGRAM_TOKEN` | `telegram_token` | `""` | Token do bot (@BotFather). **NUNCA commitar.** |
| `API_BASE_URL` | `api_base_url` | `"http://127.0.0.1:8077"` | URL base que o bot usa para chamar a API |
| `API_API_CALL_TOKEN` | `api_call_token` | `"dev-token"` | Token que o bot usa para autenticar na própria API (deve existir em `API_TOKENS`) |
| `API_BOT_SENHA` | `bot_senha` | `"trocar-esta-senha"` | Senha de acesso ao bot Telegram. **Trocar em produção.** |
| `API_GOOGLE_MAPS_API_KEY` | `google_maps_api_key` | `""` | Chave Google Geocoding API (opcional; sem ela geocoding de endereço cai em Nominatim) |
| `API_BOT_SESSOES_PATH` | `bot_sessoes_path` | `bot_sessoes.json` (raiz do repo) | Arquivo de persistência de sessões do bot |

### Gotchas de produção

**`API_CORS_ORIGINS`:** deve ser JSON válido. Tanto `["*"]` quanto lista com domínios específicos.
```bash
# CORRETO
API_CORS_ORIGINS='["*"]'
API_CORS_ORIGINS='["https://ultra.app","https://api.ultra.app"]'

# ERRADO (string simples sem brackets — comportamento inesperado)
API_CORS_ORIGINS=*
```

**`API_TOKENS`:** deve ser JSON válido com aspas duplas nas chaves e valores.
```bash
# CORRETO
API_TOKENS='{"tok-telegram":"bot-telegram","tok-felipe":"felipe"}'

# ERRADO
API_TOKENS=tok-telegram:bot-telegram
```

---

## 9. Rodar localmente

```bash
# 1. Instalar dependências (na raiz do repo)
pip install -e ".[api_mvp,basemap,geocoder]"

# 2. Subir a API (porta padrão 8077)
uvicorn motor_expansao.api.main:app --reload

# 3. Subir o bot (em outro terminal, com a API no ar)
API_TELEGRAM_TOKEN=<token-do-botfather> python -m motor_expansao.api.telegram_bot
```

**Notas:**
- A API fica disponível em `http://localhost:8077`.
- `/docs` (Swagger UI) e `/redoc` ficam disponíveis quando `API_ENVIRONMENT != "production"`.
- Para override pontual de env: criar `.env` na raiz ou exportar variáveis antes do comando.
- Extras instalados: `api_mvp` (FastAPI/uvicorn) + `basemap` (fundo de ruas do PDF) +
  `geocoder` (Chrome/Selenium para endereço+CEP; requer Google Chrome instalado no host).
- Para detalhes de instalação, dados necessários e hardening de produção:
  ver [docs/api_geoespacial_deploy.md](api_geoespacial_deploy.md).
- Para containerização VPS (Docker Compose):
  ver [docs/deploy_api_bot.md](deploy_api_bot.md).

---

## 10. Documentos relacionados

| Documento | O que cobre |
|---|---|
| [docs/api_geoespacial_contrato.md](api_geoespacial_contrato.md) | Contrato técnico (DEC-005): arquitetura de decisões, premissas canônicas, decomposição de blocos |
| [docs/api_geoespacial_openapi.yaml](api_geoespacial_openapi.yaml) | Spec OpenAPI completa: schemas detalhados, exemplos de resposta, todos os endpoints |
| [docs/api_geoespacial_deploy.md](api_geoespacial_deploy.md) | Instalação local, variáveis de env, dados necessários, hardening, observabilidade |
| [docs/deploy_api_bot.md](deploy_api_bot.md) | Containerização VPS: `Dockerfile.api`, docker compose, segredos, volumes |

---

## 11. Limitações e roadmap

| Limitação | Detalhe |
|---|---|
| **Raio fixo 1,5 km** | Não é parâmetro de entrada — é o método canônico `setor_censitario_intersecao_area_1p5km`, INTOCÁVEL (CLAUDE.md §4) |
| **PostGIS fora do MVP** | Persistência e queries geoespaciais em banco; evolução futura (BLK-API-05) |
| **Docs interativas em produção** | `/docs` e `/redoc` desabilitados quando `API_ENVIRONMENT=production`; usar `api_geoespacial_openapi.yaml` localmente |
| **Geocoding de endereço+CEP** | Requer Google Chrome instalado no host (extra `[geocoder]`); sem Chrome, cai em Nominatim (gratuito, menos preciso para localidades brasileiras) |
| **SAM/residual no JSON** | Preenchidos apenas quando `data/staging/hexagonos_mercado_mapeado.parquet` existir no path configurado; ausência é silenciosa (campos `null`) |
| **Autenticação MVP** | Lista estática de tokens — sem endpoint de admin; rotação via edição do `.env` e restart do processo |
| **Performance — 1ª chamada** | Cold load dos Parquets + busca de tiles pode levar até ~30 s em área densa; chamadas subsequentes ao mesmo município são mais rápidas (cache em memória) |
