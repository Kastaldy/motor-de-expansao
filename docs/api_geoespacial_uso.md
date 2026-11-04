# API GeoEspacial — Guia de uso ponta-a-ponta

> Fonte única de USO da API GeoEspacial Ultra Academia.
> Para o contrato/decisões de design: [docs/api_geoespacial_contrato.md](api_geoespacial_contrato.md)
> Para a spec OpenAPI: [docs/api_geoespacial_openapi.yaml](api_geoespacial_openapi.yaml)
> Para instalação, deploy e VPS: [docs/api_geoespacial_deploy.md](api_geoespacial_deploy.md) / [docs/deploy_api_bot.md](deploy_api_bot.md)
> READ-ONLY sobre o M1 (CLAUDE.md §5).

---

## 1. Visão geral e arquitetura

A API GeoEspacial é uma camada de consumo **on-demand** do Motor de Expansão, complementar ao
piloto web (o app de produção — DEC-022). Ela expõe o **Relatório Pontual Censitário 1,0 km** (KPIs em JSON e PDF de
7 páginas base, ou até 11 com viabilidade e dados do imóvel) e o **Relatório Municipal** (PDF) para qualquer cliente HTTP com token — incluindo o
bot Telegram "Paulo".

**Dois serviços independentes** (desacoplados; o bot consome a API por HTTP):

| Serviço | O que é | Porta |
|---|---|---|
| **API** | FastAPI/uvicorn — `GET /health`, `POST /api/v1/analisar` (JSON/PDF), `GET /api/v1/faixa-alunos` e as rotas do Relatório Municipal (`GET /api/v1/ufs`, `GET /api/v1/municipios/{uf}`, `POST /api/v1/analisar-municipio`) | 8077 (interna) |
| **Bot** | Long-polling Telegram 24/7 que consome a API | — |

**Diagrama simplificado:**

```
telegram-bot ──HTTP──> api ──Parquets locais──> motor censo_*
```

**Versão do contrato:** `api-geoespacial/v1` (campo `versao_contrato` na resposta JSON).

**Dados lidos (READ-ONLY):**
- `data/outputs/setores_censitarios_2022_geo/` — malha censitária (27 UFs, 5.571 municípios)
- `data/ibge/municipios_*.geojson` — resolve coordenada → município
- `data/staging/` — concorrentes/Ultra/SAM: **opcional** no Relatório Pontual só em dev (ausência = `"n/d"` nos
  Big Numbers / fallback textual no mapa) — em produção (`MOTOR_DATA_DIR` setado) a API não sobe sem os insumos da renda (`uplift_renda_domiciliar_municipio.parquet`, `uplift_composicao_setor.parquet`) e o carimbo k da malha (`censo2022_hex_da_malha.parquet`); **obrigatório** nas rotas do Relatório Municipal — sem
  `hexagonos_mercado_mapeado.parquet` as três respondem `500 erro_interno` (não há fallback)

**Docs interativos** (`/docs` Swagger UI e `/redoc`): disponíveis **apenas** quando
`API_ENVIRONMENT != "production"`. Em produção, usar `docs/api_geoespacial_openapi.yaml` localmente.

**Raio padrão: 1,0 km — no Relatório Pontual.** Não é número de entrada — é o método canônico
`setor_censitario_intersecao_area_1km`, INTOCÁVEL (CLAUDE.md §4); só o PDF Estudo troca de recorte, pelo campo `alcance` (raio de 2 km ou 5/10 min de carro, DEC-074, Emenda 3; ver "Estudo por alcance"). O Relatório Municipal não usa
raio: agrega o município inteiro.
Dois mapas do PDF pontual usam escala só de **render** (nunca de análise): os painéis de
Socioeconomia e de Residual Fitness são **enquadrados** por um raio automático, de 3 a 7 km conforme a região (`censo_map.raio_enquadramento_hex_km`; os 5 km de `RAIO_RESIDUAL_DISPLAY_KM` são só fallback), ambos
**condicionais** — viram fallback textual sem a base de mercado/hexágonos. O enquadramento não é **desenhado** (**BLK-RELPON-14**): sem círculo e sem rótulo "Raio X km"; o ponto aparece
pelo pin central e pela borda fina do hexágono H3 que o contém.

---

## 2. Autenticação

Todas as rotas — exceto `GET /health` e seu alias `GET /api/v1/health` — exigem autenticação por
**Bearer token**.

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
{"status": "ok", "environment": "development",
 "artefatos_oferta": {"concorrentes_mapeados": true, "vulnerabilidade_ma_redes": true, "vulnerabilidade_ma_nomeadas": true},
 "oferta_completa": true, "renda_fatores": {"versao": "2026-10_pnad2025_v1", "fixada_por_env": false}}
```

Também disponível como alias (sem auth): `GET /api/v1/health`.

Uso típico: monitoramento do load balancer e do docker compose.

---

### 3b. `POST /api/v1/analisar`

Endpoint principal. Recebe um ponto geográfico e devolve o estudo censitário em **JSON** (default)
ou **PDF** (8 páginas sem `viabilidade`: as 7 de base + a Conclusão só-estudo; ver a tabela abaixo).

#### Request body (`AnalisarRequest`)

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `lat` | `float` | Sim (se sem `maps_url`) | Latitude decimal |
| `lng` | `float` | Sim (se sem `maps_url`) | Longitude decimal |
| `maps_url` | `string` | Alternativa a `lat`/`lng` | Link do Google Maps; parser puro, sem rede |
| `formato` | `"json"` / `"pdf"` | Não (default `"json"`) | Atalho de negociação no body |
| `rotulo` | `string` / `null` | Não | Nome do endereço/estabelecimento na capa do PDF |
| `solicitante` | `string` / `null` | Não | Nome de quem pediu; carimba a marca d'água. Omitido, vale o consumidor do token |
| `info_imovel` | `object` / `null` | Não | Dados do imóvel (`metragem_m2`, `aluguel_pedido`, `valor_venda`, `pe_direito_m`, `vagas`, `tipo_imovel`, `endereco`, `observacoes`) → página "Imóvel · Informações" |
| `viabilidade` | `object` / `null` | Não | Cenário financeiro (`m2`, `aluguel`, `demanda` obrigatórios) → páginas de Viabilidade + Conclusão com selo financeiro |
| `alcance` | `"raio_1km"` / `"raio_2km"` / `"carro_5min"` / `"carro_10min"` / `null` | Não | Recorte do Estudo (DEC-074, Emenda 3). Fora do raio de 1 km: só no PDF e sem `viabilidade` nem `info_imovel` (ver "Estudo por alcance" abaixo) |

**`viabilidade` não repete `lat`/`lng`** — a coordenada é a do próprio request (ou a resolvida
do `maps_url`). Dois lugares para o mesmo ponto seria um lugar para eles discordarem.

**`demanda` é premissa de quem pede** (pela DEC-078, a tela do piloto sugere uma demanda pelo modelo de praça, que a API não usa). A API não deriva demanda da
geografia: sem o objeto `viabilidade`, o relatório sai sem as páginas financeiras — não sai com
uma demanda arbitrada.

O payload de viabilidade é montado pela **mesma função que o piloto web usa**
(`motor_expansao.dimensionamento.payload_viabilidade`), com a mesma malha de catchment que a
própria rota já carregou — não há segunda régua (FIN-VIAB-01).

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
| `raio_km` | `float` | Raio do estudo (1,0 km) |
| `area_km2` | `float \| null` | Área da interseção em km² |
| `metodo` | `string` | `"setor_censitario_intersecao_area_1km"` |
| `n_setores` | `int` | Setores IBGE 2022 cruzados |
| `pop_total_raio` | `float \| null` | População total no raio |
| `renda_per_capita_media_raio` | `float \| null` | Renda **domiciliar per capita** média ponderada (conceito IBGE/SIDRA). ⚠️ **Escala mudou em 2026-08-14**: antes saía da coluna calibrada (~19% abaixo do IBGE); agora = renda domiciliar ÷ moradores — o valor SOBE ~50% para o mesmo ponto |
| `renda_media_domiciliar_raio` | `float \| null` | Renda média **domiciliar** do raio (R$/mês por domicílio), ponderada por domicílios, com uplift de composição setorial e fator temporal — **igual a `renda_domiciliar_total_raio`** e ao card do PDF. ⚠️ **Escala mudou na E1 do plano de correção da renda (2026-10)**: até então era a base **pré-uplift** (renda do responsável, V06004 bruta, ~0,53x do card); para o mesmo ponto o valor SOBE. Não aplique uplift nem fator sobre ele. Nome e tipo inalterados |
| `renda_domiciliar_total_raio` | `float \| null` | Renda **por domicílio** (R$/mês) com uplift setorial + fator temporal — NÃO é massa/somatório; é o valor exibido no PDF. ⚠️ Escala corrigida em 2026-08-14 (fim da dupla contagem do `k`: cai ÷1,2335 para o mesmo ponto) |
| `domicilios_total_raio` | `float \| null` | Domicílios estimados no raio |
| `metodo_renda_domiciliar_raio` | `string \| null` | `"ponderada_domicilios_estimados"`, `"ponderada_populacao_ou_area"` ou `"ausente"` |
| `fracao_uplift_extrapolado_raio` | `float \| null` | **ADITIVO 2026-08-14**: fração (0–1, por peso de domicílios) do raio cuja renda depende de uplift **extrapolado** para fora do envelope de calibração — pede leitura cautelosa |
| `densidade_pop_raio_hab_km2` | `float \| null` | Densidade populacional (hab/km²) |
| `score_setor_medio` | `float \| null` | Score censitário médio ponderado |
| `score_setor_max` | `float \| null` | Score censitário máximo no raio |
| `n_concorrentes` | `int` | Academias concorrentes no raio |
| `n_ultra` | `int` | Unidades Ultra no raio |
| `versao_contrato` | `string` | `"api-geoespacial/v1"` |
| `versao_score` | `string` | `"score_setor_2022_calibrado"` |
| `gerado_em` | `string` | Timestamp ISO 8601 UTC |
| `consumidor` | `string \| null` | Token → consumidor (rastreio LGPD) |

**Nota sobre SAM/residual:** desde a DEC-070 (2026-10-14), SAM, consumo (concorrentes de rede + Ultra, card
"Mercado ocupado") e residual do Big Numbers são do **raio de 1,0 km** (`api.service._mercado_do_ponto`):
a taxa de penetração e a faixa M1 vêm do hexágono do ponto em `data/staging/hexagonos_mercado_mapeado.parquet`,
e o consumo, de `concorrentes_mapeados` + `vulnerabilidade_ma_redes` e de `unidades_ultra_mapeadas` + `unidades_ultra_performance_hex`, no mesmo staging. O mesmo Parquet alimenta o choropleth de **Residual Fitness** do
slide "Socioeconomia e Residual Fitness". Ausência é silenciosa: Big Numbers saem como `"n/d"` e
a camada de Residual Fitness cai em fallback textual (o JSON não tem esses campos).
`score_oportunidade_residual` também é lido do Parquet, mas **não é exibido** em nenhuma página.

#### Response PDF

```
Content-Type: application/pdf
Content-Disposition: inline; filename="relatorio_pontual_censitario.pdf"
```

PDF de 7 páginas **base**: Capa → Socioeconomia e Residual Fitness → Mapas de calor
(grid 2×2: densidade, renda, score censitário, renda média domiciliar) → Concorrentes →
Perfil do Bairro/Distrito → Big Numbers → Realização/Crédito. A página "Imagem do Entorno"
(mapa de quadra) saiu no **BLK-RELPON-14** — eram 8.

**O que sai de fato**, medido contra a base real:

| Request | Páginas | Composição |
|---|---|---|
| sem `viabilidade` | **8** | 7 base + Conclusão em modo só-estudo (`conclusao_so_estudo`, BLK-CONC-ESTUDO) |
| com `viabilidade` + `info_imovel` | **11** | as 8 acima + Imóvel · Informações + Viabilidade (números) + Viabilidade (grade) |

Com o cenário financeiro presente, a Conclusão deixa o modo só-estudo e volta a carimbar os
**dois selos** da DEC-030 (demográfico e financeiro) em vez de apenas o demográfico.

É a variante "Apresentação Clássica Ultra" (`gerar_pdf_relatorio_pontual_classico`), a mesma que o
piloto web entrega e, desde o BLK-RELPON-14, o **gerador único** do relatório pontual. Das páginas
**opcionais** do gerador, o endpoint agora usa duas — **dados do imóvel** e **viabilidade** — e, com `API_ARCGIS_API_KEY` definida, a vista aérea (DEC-018), que soma 1 página às contagens acima. As
**fotos do imóvel** continuam fora: o corpo da API é JSON e não carrega binário.

#### Estudo por alcance (DEC-074, Emenda 3)

Com `alcance` = `raio_2km`, `carro_5min` ou `carro_10min`, o PDF é o **Estudo** daquele recorte —
o mesmo do botão "Estudo" da análise de ponto do piloto: população, renda, mercado e mapas medidos
no recorte, metas de totais escaladas pela área (`fator = área / π`) e a Conclusão só com o selo
demográfico. Os minutos de carro são **sem trânsito**, pela isócrona do serviço de rotas próprio
(`MOTOR_ROTAS_URL`).

| Pedido | Resposta |
|---|---|
| `alcance` ausente ou `raio_1km` | o de sempre (nada muda) |
| `alcance` + PDF, sem `viabilidade` e sem `info_imovel` | 200, PDF Estudo do recorte |
| `alcance` + saída JSON | 400 `alcance_so_no_pdf` |
| `alcance` + `viabilidade` ou `info_imovel` | 400 `alcance_so_no_estudo` — o relatório completo é do raio de 1 km |
| minutos de carro com o serviço de rotas fora | 503 `rotas_indisponiveis` |
| ponto a mais de 300 m de qualquer rua, ou área acima dos tetos | 400 `alcance_invalido` |

Em nenhum caso o pedido de recorte cai, em silêncio, para o raio de 1 km.

**Performance:** a primeira chamada pode levar de 10 a 30 s (cold load dos Parquets +
busca de tiles de mapa). Chamadas subsequentes ao mesmo município são mais rápidas
(cache em memória). Timeout do bot: 240 s.

---

### 3bb. `GET /api/v1/faixa-alunos`

Faixa plausível de alunos para uma metragem, da curva tamanho→densidade dos comparáveis Ultra.

**Não é previsão de demanda** (esta rota não usa a praça). Ela depende **só** de `m2` e da base de comparáveis —
não recebe `lat`/`lng` e não sabe nada da praça. Dois imóveis do mesmo tamanho em cidades opostas
recebem a mesma faixa.

Existe porque `viabilidade.demanda` é obrigatório no `POST /api/v1/analisar` e é **premissa de
quem pede**. Sem esta rota, o consumidor precisa cravar um número fixo — o mesmo para um imóvel
de 600 m² e um de 10.000 m².

| Parâmetro | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `m2` | `float` (> 0) | Sim | Área útil do imóvel |
| `formato` | `string` / `null` | Não | Restringe os comparáveis ao mesmo formato de operação |

```bash
curl -s "https://api.ultra-expansao.tech/api/v1/faixa-alunos?m2=1500"   -H "Authorization: Bearer $TOKEN"
```

```json
{
  "m2": 1500.0,
  "p10": 620.0,
  "p50": 980.0,
  "p90": 1420.0,
  "n_comparaveis": 23,
  "fonte": "base_calibracao_maduras.parquet (oficial)"
}
```

**`n_comparaveis` e `fonte` não são acessórios.** A janela de metragem alarga sozinha quando há
poucos comparáveis (±20% → ±50% → base inteira), então um `n` baixo significa faixa menos
recortada. E `fonte` denuncia a degradação silenciosa: sem `base_calibracao_maduras.parquet` o
motor cai num fallback, e a mesma faixa passa a descrever **outra** população de comparáveis.

Sem base nenhuma, a resposta é `200` com os percentis `null`, `n_comparaveis: 0` e a `fonte`
dizendo que está indisponível — ausência de base é resposta prevista pelo contrato, não erro.

---

### 3c. Rotas do Relatório Municipal

`GET /api/v1/ufs` e `GET /api/v1/municipios/{uf}` listam as UFs e os municípios de uma UF. Existem
para clientes HTTP montarem a escolha de UF/município — o bot Telegram **não** as consome: ele usa
uma lista de 27 UFs embutida (`telegram_bot._UFS`) e deixa o casamento do nome digitado para o
próprio `POST /analisar-municipio` (que responde `404` com sugestões).
`POST /api/v1/analisar-municipio` devolve o **Relatório Municipal** em PDF (no Brasil, 8 páginas fixas + as 4 da praça + uma por parte dos Bairros Oficiais em município grande) —
outro estudo, que agrega um município inteiro (não um raio). Body (`AnalisarMunicipioRequest`):
`uf`, `municipio` (aceita sem acento), `formato` (`"pdf"`), `unidade` (`"bairro"`, default, ou `"hexagono"`) e `solicitante` (carimba a marca
d'água). Exigem o mesmo Bearer token; timeout do bot: 300 s.

**Custo de memória:** no Brasil (DEC-077), `POST /analisar-municipio` lê só a partição enriquecida da UF
(`outputs/hexagonos_dashboard_enriquecido/uf=XX`, a base da tela; sem ela, `503 base_da_tela_ausente`); a base de mercado inteira (~1,9 GB residentes, 1× por processo) só é carregada no país sem régua de recomendação (Argentina). As duas rotas `GET` leem só 3 colunas (~50 MB) e não
pagam esse custo.

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

### Estudo de 10 min de carro (PDF, sem viabilidade)

```bash
curl -s -X POST http://localhost:8077/api/v1/analisar \
  -H "Authorization: Bearer dev-token" \
  -H "Content-Type: application/json" \
  -d '{"lat": -21.9180, "lng": -46.6855, "formato": "pdf", "alcance": "carro_10min"}' \
  -o estudo_10min.pdf
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

**Links compactados** (ex.: `maps.app.goo.gl/...`, `goo.gl/maps/...`, encurtadores em geral) **não
são aceitos** em `maps_url`: o parser da API é puro (sem rede) e devolve `400 coordenada_invalida`.
Quem segue o redirect é o bot Telegram, num passo anterior — ele envia `{lat, lng}` já resolvidos.

**Bounding box de validação:** lat ∈ [-34,0; 5,5], lng ∈ [-74,0; -28,0] (inclui ilhas oceânicas:
Fernando de Noronha, Trindade). Pontos fora → `400 coordenada_invalida`.

---

## 6. Bot Telegram — Paulo

O bot "Paulo" é a interface conversacional da API para usuários do Telegram. Funciona por
**long-polling 24/7** na VPS, consumindo o `POST /api/v1/analisar` (Relatório Pontual) e o
`POST /api/v1/analisar-municipio` (Relatório Municipal) por HTTP.

### Fluxo da máquina de estados

```
0. Chat fora da allowlist (`API_BOT_ALLOWLIST_PATH`, por `chat_id`, fail-closed, desde 2026-09-24)
   → "Este chat nao tem acesso a este bot..." — nada mais roda (nem senha, nem comando)

1. Qualquer mensagem (1a interação)
   → "Olá! Eu sou o Paulo... Envie a senha de acesso."

2. Senha
   → Correta: "Senha correta! Como posso te chamar?"
   → Incorreta: repete pedido de senha

3. Nome/login
   → "Prazer, <nome>!" + menu [Relatorio Pontual | Municipal (hexagonos) | Municipal (bairros) | Ajuda]
   → "Me envie a localização do ponto agora."

4. Menu (qualquer momento após autorizado)
   /start / "menu" / /menu                → volta ao menu
   "Relatorio Pontual" / /relatorio       → pedido de localização
   "Municipal (hexagonos)" / /municipal  → escolha da UF → digitar o município → PDF municipal (hexágonos)
   "Municipal (bairros)" / /bairros      → idem, com os mapas por bairro
   "Relatorio Municipal" (botão antigo)  → avisa que a opção virou duas e troca o teclado
   "Ajuda" / /ajuda / /help               → mensagem de ajuda

4b. Dentro do fluxo municipal (etapas "escolha da UF" e "digite o município") a mensagem
    não-comando é CONSUMIDA por esse fluxo (vira UF / nome de município), não vira localização.
    Saídas: "⬅️ Voltar" / "cancelar" ou qualquer comando global do passo 4.

5. Qualquer mensagem não-comando FORA do fluxo municipal (= localização)
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
| `/start` / `menu` / `/menu` | Volta ao menu |
| `Relatorio Pontual` / `pontual` / `relatorio` / `/relatorio` | Pede localização para novo estudo pontual |
| `Municipal (hexagonos)` / `hexagonos` / `municipal` / `/municipal` / `/hexagonos` | Pede UF e município para o Relatório Municipal por hexágono |
| `Municipal (bairros)` / `bairros` / `bairro` / `/bairros` | Idem, com os mapas por bairro |
| `Relatorio Municipal` (botão antigo, em cache no Telegram) | Explica que a opção virou duas e troca o teclado |
| `/acessos` | Só no chat de ops (`API_ACESSOS_ADMIN_CHAT_ID`): agregado de uso do piloto (DEC-027) |
| `Ajuda` / `/ajuda` / `/help` | Mostra descrição e formas de localização |
| `⬅️ Voltar` / `voltar` / `cancelar` | Só no fluxo municipal: de "digite o município" volta à escolha da UF; da UF volta ao menu |

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
| `404` | `base_geo_ausente` | `"Materialize setores_censitarios_2022_geo/ para SP/3550308"` | Partição censitária ausente para o município do ponto (`POST /analisar`) |
| `404` | `municipio_nao_encontrado` | `"Municipio 'Palmas' nao encontrado em TO. Voce quis dizer: ...?"` | Nome não casa nenhum município da UF em `POST /analisar-municipio` (o `detail` já traz até 6 sugestões) |
| `404` | `municipio_sem_dados` | `"Municipio 'X' (UF) sem hexagonos"` | Município existe no índice, mas não tem hexágonos na base de mercado (`POST /analisar-municipio`) |
| `500` | `erro_interno` | `"Erro interno ao gerar o estudo"` | Qualquer exceção não tratada (stack trace no log do servidor) — inclui `hexagonos_mercado_mapeado.parquet` ausente nas rotas municipais |
| `429` | `rate_limited` | `"Muitas requisicoes. Tente novamente em instantes."` | Mais de 120 requisições por minuto do mesmo token (ou IP) — BLK-SEC-05 |
| `503` | `base_da_tela_ausente` | `"Base da tela ausente neste servidor: o Relatorio Municipal nao sai sem ela"` | Brasil: partição enriquecida da UF ausente em `POST /analisar-municipio` (DEC-077) |

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
| `API_STAGING_DIR` | `staging_dir` | `data/staging` | Parquets de mercado/concorrentes/Ultra (READ-ONLY). Opcional no Relatório Pontual só em dev — em produção a subida exige os insumos da renda e o carimbo k da malha; **obrigatório** nas rotas do Relatório Municipal |
| `API_CORS_ORIGINS` | `cors_origins` | `["*"]` | Origens CORS; em produção restringir: `'["https://meudominio.com"]'` |
| `API_TOKENS` | `tokens` | `{"dev-token": "dev-local"}` | Mapa token→consumidor (JSON string) |
| `API_TELEGRAM_TOKEN` | `telegram_token` | `""` | Token do bot (@BotFather). **NUNCA commitar.** |
| `API_API_BASE_URL` | `api_base_url` | `"http://127.0.0.1:8077"` | URL base que o bot usa para chamar a API |
| `API_API_CALL_TOKEN` | `api_call_token` | `"dev-token"` | Token que o bot usa para autenticar na própria API (deve existir em `API_TOKENS`) |
| `API_BOT_SENHA` | `bot_senha` | `"trocar-esta-senha"` | Senha de acesso ao bot Telegram. **Trocar em produção.** |
| `API_GOOGLE_MAPS_API_KEY` | `google_maps_api_key` | `""` | Chave Google Geocoding API (opcional; sem ela geocoding de endereço cai em Nominatim) |
| `API_BOT_SESSOES_PATH` | `bot_sessoes_path` | `bot_sessoes.json` (raiz do repo) | Arquivo de persistência de sessões do bot |
| `API_BOT_ALLOWLIST_PATH` | `bot_allowlist_path` | `None` | Allowlist de chats do bot por `chat_id` (fail-closed; em produção `/cadastro/bot_allowlist.json`) |
| `API_BOT_TRILHA_DIR` | `bot_trilha_dir` | `None` | Trilha persistente do bot (JSONL por dia, 90 dias) |
| `API_ACESSO_LOG_DIR` | `acesso_log_dir` | `None` | Trilha de acesso do piloto lida pelo `/acessos` (DEC-027) |
| `API_ACESSOS_ADMIN_CHAT_ID` | `acessos_admin_chat_id` | `""` | Único chat autorizado a usar o `/acessos` |
| `API_ARCGIS_API_KEY` | `arcgis_api_key` | `""` | Vista aérea (satélite Esri) do PDF pontual (DEC-018); vazia, a página sai |

### Gotchas de produção

**`API_CORS_ORIGINS`:** JSON é a forma recomendada — tanto `["*"]` quanto lista com domínios
específicos. O parser também aceita lista separada por vírgula sem brackets.
```bash
# RECOMENDADO (JSON)
API_CORS_ORIGINS='["*"]'
API_CORS_ORIGINS='["https://ultra.app","https://api.ultra.app"]'

# TAMBÉM ACEITO (sem brackets — split por vírgula)
API_CORS_ORIGINS=*
API_CORS_ORIGINS=https://ultra.app,https://api.ultra.app
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

# 2. Subir a API na porta 8077 (a mesma do Dockerfile.api).
#    Sem --port o uvicorn usa 8000 e os curl da seção 4 falham com connection refused.
uvicorn motor_expansao.api.main:app --reload --port 8077

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
| [docs/relatorio_municipal_template.md](relatorio_municipal_template.md) | Estrutura/template do Relatório Municipal (11 páginas de `PDF_SECTION_HEADERS`; 8 fixas no Brasil, DEC-077) (`POST /api/v1/analisar-municipio`) |

---

## 11. Limitações e roadmap

| Limitação | Detalhe |
|---|---|
| **Raio fixo 1,0 km (Relatório Pontual)** | Não é parâmetro de entrada — é o método canônico `setor_censitario_intersecao_area_1km`, INTOCÁVEL (CLAUDE.md §4). O Relatório Municipal não usa raio |
| **PostGIS fora do MVP** | Persistência e queries geoespaciais em banco; evolução futura (BLK-API-05) |
| **Docs interativas em produção** | `/docs` e `/redoc` desabilitados quando `API_ENVIRONMENT=production`; usar `api_geoespacial_openapi.yaml` localmente |
| **Geocoding de endereço+CEP** | Requer Google Chrome instalado no host (extra `[geocoder]`); sem Chrome, cai em Nominatim (gratuito, menos preciso para localidades brasileiras) |
| **SAM/residual só no PDF** | Não fazem parte do `AnalisarResponseJSON`; aparecem no Big Numbers e no mapa de Residual Fitness do PDF quando `data/staging/hexagonos_mercado_mapeado.parquet` existir no path configurado; ausência é silenciosa (`"n/d"` / fallback textual) |
| **Autenticação MVP** | Lista estática de tokens — sem endpoint de admin; rotação via edição do `.env` e restart do processo |
| **Performance — 1ª chamada** | Cold load dos Parquets + busca de tiles pode levar até ~30 s em área densa; chamadas subsequentes ao mesmo município são mais rápidas (cache em memória) |
