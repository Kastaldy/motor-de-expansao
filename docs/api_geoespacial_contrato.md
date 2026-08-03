# API GeoEspacial — Contrato tecnico (G1 / BLK-API-01)

> Documento de contrato/design produzido no bloco **BLK-API-01** (G1). Define a arquitetura,
> a superficie de endpoints, os schemas e a decomposicao de blocos para que o Juan implemente
> G2 sem re-discussao. **ZERO codigo de producao neste bloco** — este arquivo descreve o que
> sera criado nos blocos sucessores. **READ-ONLY sobre o M1** (CLAUDE.md §5).
> As decisoes-chave foram aprovadas por Felipe Silva em 2026-06-10 — **ver DEC-005 (§8 do CLAUDE.md)**.

## 1. Cabecalho e escopo

- **Proposito:** API complementar ao Motor de Expansao, on-demand, para integracao com bots de
  **Telegram/WhatsApp**, dando autonomia de estudos geoespaciais internos. O caso de uso central do
  MVP e: o usuario manda um ponto (coordenada ou link do Google Maps) ao bot e recebe o estudo do
  **Relatorio Pontual Censitario 1.0 km** (KPIs em JSON e/ou o PDF de 7 paginas; raio 1,5 km ate a DEC-021, 2026-07-29).
- **ClickUp:** tarefa `86e1rtfe3` (G1), subtarefa de `86e1rtfcy` (projeto API GeoEspacial / `PROJETOS - DEG`).
- **Papeis do projeto:** G1 = arquitetura/contrato (Felipe — este bloco); G2 = backend/rotas (Juan);
  G3 = integracao com o motor + testes fim-a-fim/observabilidade (Felipe+Juan); G4 = clientes
  Telegram/WhatsApp (Juan).
- **Versao do contrato:** `v1` (carimbada como `versao_contrato = "api-geoespacial/v1"`).
- **Data:** 2026-06-10.
- **Status:** contrato aprovado (gate humano resolvido — DEC-005).

## 2. Premissas canonicas inegociaveis (registrar, NAO reabrir)

Fixadas por Felipe (2026-06-09) e reafirmadas na DEC-005 (2026-06-10):

1. **On-demand a partir do motor; PostGIS FORA do MVP.** A API serve o relatorio importando a camada
   `censo_*` e lendo os Parquets locais de `data/outputs/setores_censitarios_2022_geo/`. PostGIS e
   evolucao futura, fora do MVP.
2. **Fronteira "importa, nao edita `censo_*`".** A API trata `censo_point.py` / `censo_map.py` /
   `censo_report.py` como interface ESTAVEL; nunca os edita (trilha do Vini — dashboard/PDF/UX).
   Mudancas nesses modulos sao solicitadas, nao feitas pela trilha da API.
3. **Codigo novo so em `src/motor_expansao/api/`** (pasta disjunta). Nada de logica da API fora dela.
4. **Dependencias so em extra opcional** do `pyproject.toml`, fora do install base (regra escrita
   quando o deploy base era o Streamlit, aposentado pela DEC-022, 2026-08-03; segue valendo para nao
   inflar as imagens `motor-expansao-web`/`motor-expansao-api`). Materializado no extra `[api_mvp]`
   (mais `[basemap]`/`[geocoder]`, pos-contrato) — o `[api]` e o bloco LEGADO PostGIS e nao deve ser
   instalado (§11).
5. **READ-ONLY sobre o M1 (§5).** A API e camada paralela de consumo: NAO recalcula nem altera
   `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano dominio ou
   qualquer artefato oficial do M1.
6. **Parametros canonicos imutaveis.** `H3_RESOLUTION=7`, pesos `renda=0.40`/`pop=0.60`, **raio fixo
   1.0 km** (`RAIO_CENSITARIO_DEFAULT_KM`) e o **metodo de intersecao** censitario
   (`setor_censitario_intersecao_area_1km`) so mudam por DEC explicita — apenas DESCRITOS aqui.
   (Emenda DEC-021, 2026-07-29: raio e rotulo do metodo passaram de 1,5 km/`..._1p5km` para
   1,0 km/`..._1km`; o metodo de intersecao em si e os demais parametros seguem os da DEC-005.)

## 3. Layout do pacote `src/motor_expansao/api/` (descritivo — a CRIAR em G2)

> Proposta de modulos de G1 (2026-06-10). **NENHUM arquivo e criado no BLK-API-01.** A pasta nasce
> no BLK-API-02 junto do esqueleto real. A tabela fica como registro do PLANO: o pacote HOJE tem
> tambem `errors.py` (handler `500`, §9), `geo.py`, `maps_geocoder.py`, `telegram_bot.py` e
> `routes/analisar_municipio.py` (§6), todos nascidos pos-contrato.

| Modulo | Responsabilidade | Bloco de criacao |
|---|---|---|
| `__init__.py` | Marca o pacote. | BLK-API-02 |
| `main.py` | App `FastAPI(...)` + CORS + montagem dos routers + `GET /health`. | BLK-API-02 |
| `settings.py` | `pydantic-settings` (`Settings`): environment, prefixo `/api/v1`, dir dos Parquets, mapa token->consumidor. | BLK-API-02 |
| `auth.py` | Dependencia de autenticacao por **token de portador** (Decisao 2): valida o header e resolve o **consumidor** (rastreio do solicitante). | BLK-API-02 |
| `routes/analisar.py` | Rota `POST /analisar` (negociacao JSON/PDF). | BLK-API-03 / BLK-API-04 |
| `schemas/` | Modelos Pydantic de request/response (`AnalisarRequest`, `AnalisarResponseJSON`, `HealthResponse`, `ErrorResponse`). | BLK-API-03 |
| `service.py` | Camada FINA: resolve `{lat,lng}`/`maps_url` -> `(uf, cod_municipio)`, carrega a particao via `read_censo_geo_partition`, chama `analisar_ponto_censitario_setores` (JSON) e, para PDF, `render_mapas_censitarios_combinados` + `gerar_pdf_relatorio_pontual_classico` (variante CLASSICA, default de producao desde o BLK-EST-05). **So importa `censo_*`, nunca edita.** | BLK-API-03 / BLK-API-04 |
| `coord.py` | Utilitario PURO de coordenada: parser de link do Google Maps -> `(lat,lng)` (Decisao 4) + validacao de bounding box do Brasil. Sem dependencia do motor. | BLK-API-03 |

## 4. Fronteira "importa, nao edita `censo_*`" — assinaturas REAIS importadas

A API importa (e NUNCA edita) as funcoes abaixo, com as assinaturas reais confirmadas no codigo:

- `dashboard.censo_point.analisar_ponto_censitario_setores(lat: float, lng: float, setores_df: pd.DataFrame, raio_km: float = RAIO_CENSITARIO_DEFAULT_KM, competitors_df: pd.DataFrame | None = None, ultra_df: pd.DataFrame | None = None) -> dict`
  — **pura**, nao muta inputs, nao recalcula nenhum artefato oficial do M1. Retorna o `result` dict
  (campos no §7).
- `dashboard.censo_point.agregar_perfil_bairro_distrito(setores_df: pd.DataFrame, *, cod_bairro: str | None = None, nome_bairro: str | None = None, nome_distrito: str | None = None, nome_municipio: str | None = None, uf: str | None = None) -> dict[str, object]`
  — insumo do slide "Perfil do Bairro/Distrito" (BLK-RELPON-07). Sem ele a pagina existe mesmo assim,
  com "n/d" gracioso.
- `dashboard.censo_report.gerar_pdf_relatorio_pontual_classico(result: dict[str, Any], mapas: dict[str, bytes] | bytes | None = None, *, residual: dict[str, Any] | None = None, perfil_bairro: dict[str, Any] | None = None, ultra_dir: Path | str | None = None, solicitante: str | None = None, rotulo: str | None = None, now: datetime | None = None, fotos: list[bytes] | None = None, info_imovel: dict[str, Any] | None = None, viabilidade: dict[str, Any] | None = None) -> bytes`
  — gera o PDF de 7 paginas (Capa -> Socioeconomia e Residual Fitness -> Mapas
  de calor -> Concorrentes -> Perfil do Bairro/Distrito -> Big Numbers -> Realizacao), **offline, sem
  PII**. E a variante CLASSICA, default de producao desde o BLK-EST-05 e, desde o **BLK-RELPON-14**,
  a IMPLEMENTACAO UNICA: a gemea `gerar_pdf_relatorio_pontual_censitario` virou wrapper fino
  DEPRECIADO (`DeprecationWarning`) que repassa os kwargs para esta. A pagina "Imagem do Entorno"
  (BLK-RELPON-11) foi REMOVIDA no mesmo bloco (8 -> 7 paginas). Paginas OPCIONAIS nao usadas pela
  API: `fotos` e `info_imovel` entram logo apos a capa e `viabilidade` entre Big Numbers e
  Realizacao (1 pagina, ou 2 quando ha `graficos`) — teto de 11 paginas. O carimbo de versao no rodape
  (Decisao 6) esta **PREVISTO E NAO IMPLEMENTADO**: hoje o rodape e credito Ultra + atribuicao
  CARTO (`_draw_footer`) e o unico carimbo por pagina e a marca d'agua `Ultra Academia |
  {solicitante}`; a API chama o gerador sem passar versao alguma.
- `dashboard.censo_map.render_mapas_censitarios_combinados(lat: float, lng: float, setores_df: pd.DataFrame, *, raio_km: float = RAIO_CENSITARIO_DEFAULT_KM, competitors_df=None, ultra_df=None, width: int = 1000, height: int = 760, basemap: bool = True, logos_dir: Path | None = None, ultra_logo_dir: Path | None = None, street_ceil: int | None = None, street_gain: float | None = None, street_cap: int | None = None, choropleth_alpha: int | None = None, hexes_df: pd.DataFrame | None = None) -> dict[str, bytes]`
  — retorna ate 7 PNGs para o PDF: `{"densidade","renda","score","renda_domiciliar","socioeconomia","residual","concorrentes"}` (a chave `entorno` saiu no BLK-RELPON-14).
  A chave `residual` e CONDICIONAL (so aparece com `hexes_df` e ao menos 1 hex desenhavel; ausente ->
  fallback textual no slide); as demais sao incondicionais. **Nota de deploy:** com
  `basemap=True` busca tiles online (DEC-004); a API deve permitir `basemap=False` como fallback
  gracioso/offline quando o ambiente nao tiver internet. **Nota de render:** a API sobrescreve so
  no seu caminho `street_ceil=215`, `street_gain=1.3`, `street_cap=200` e `choropleth_alpha=110`
  (arruamento mais visivel sob o choropleth); o dashboard segue com os defaults do modulo
  (160 / 2.2 / 210 / 140). Alem disso a API usa o canvas DEFAULT `1000x760`, enquanto o dashboard
  renderiza em `1280x760` — como o lado MENOR do frame e o invariante (`_frame_box_metric`), o
  enquadramento e o mesmo no eixo curto e mais estreito no eixo longo da API. Fontes, faixas e
  metodo geometrico sao o mesmo render.
- `dashboard.data.read_censo_geo_partition(base_dir: Path, uf: str, cod_municipio: str | None = None) -> pd.DataFrame`
  — loader dos Parquets `data/outputs/setores_censitarios_2022_geo/uf=XX/cod_municipio=NNNNNNN`
  (`geometry_wkb` em EPSG:4674). Retorna DataFrame vazio quando a base nao existe.

**Regra:** qualquer necessidade de mudanca nessas funcoes vira um pedido a trilha do Vini; a API se
adapta a interface, nao a altera.

**Excecao pos-contrato (import no sentido inverso):** `dashboard/censo_report.py:14` importa
`motor_expansao.api.maps_geocoder.build_search_url` (helper PURO de URL). A fronteira segue de mao
unica quanto a EDICAO, mas ha um import dashboard -> `api` em nivel de modulo. Nenhuma dep do extra
`[api_mvp]`/`[geocoder]` entra no deploy base por causa disso: `api/__init__.py` so define
`__version__` e `maps_geocoder` importa apenas stdlib no topo (selenium so em `MapsGeocoder.__init__`).

## 5. Resolucao de coordenada -> particao

O `service.py` precisa resolver `(uf, cod_municipio)` a partir da coordenada para carregar a particao
certa via `read_censo_geo_partition`. Contrato (implementacao e G2/G3):

1. **Entrada (Decisao 4):** `{lat, lng}` direto OU `maps_url` (link do Google Maps). Quando vem
   `maps_url`, `coord.py` extrai `(lat, lng)` por parsing PURO de string (formatos `@lat,lng`, `?q=lat,lng`,
   `!3dLAT!4dLNG`); sem chamada de rede, sem tocar o motor.
2. **Validacao:** rejeitar coordenada fora do bounding box do Brasil -> erro `400` (§9).
3. **Mapeamento coord -> (uf, cod_municipio):** o dataset M1 base nao tem `cod_municipio`; ele flui do
   censo. O `service.py` resolve a particao via lookup geografico do ponto (ex.: ponto-em-poligono na
   malha municipal IBGE ja disponivel em `data/`), reutilizando os mesmos artefatos do dashboard.
   Detalhe de implementacao fica para G2/G3; o **contrato** e: "o ponto resolve uma e so uma particao
   `uf=XX/cod_municipio=NNNNNNN`; se nao houver particao materializada, retorna `404` com a mensagem
   espelhada do dashboard".
4. **Carga:** `read_censo_geo_partition(base_dir, uf, cod_municipio)` -> `setores_df`; em seguida
   `analisar_ponto_censitario_setores(lat, lng, setores_df, ...)`.

## 6. Endpoints do MVP (Decisao 3 = (a) minimo)

Superficie minima do MVP:

- `GET /health` — liveness. Resposta `200 {status, environment}`.
- `POST /analisar` — analise de um ponto (Relatorio Pontual Censitario 1.0 km). Negociacao de conteudo
  JSON/PDF (Decisao 1 = (c)).

**Alem do MVP (pos-contrato, ja em producao):** o Relatorio Municipal adicionou `GET /ufs`,
`GET /municipios/{uf}` e `POST /analisar-municipio` (`routes/analisar_municipio.py`) — PDF proprio de
9 paginas, READ-ONLY, fora do escopo deste §6.

**Fora do MVP (roadmap — ver §13 / BLK-API-05):** `POST /lookup-hex` (M1) e `GET /mercado/...`
(camada de mercado/residual). NAO entram no MVP; ficam documentados como escopo estendido condicional.

## 7. Schemas request/response

### 7.1 `POST /analisar` — request (`AnalisarRequest`)
```jsonc
{
  // exatamente UMA das duas formas de coordenada (Decisao 4):
  "lat": -23.95,          // float, opcional se houver maps_url
  "lng": -46.33,          // float, opcional se houver maps_url
  "maps_url": "https://maps.google.com/...",  // string, opcional se houver lat/lng
  "formato": "json",      // "json" (default) | "pdf" (Decisao 1); ?formato= ou Accept: application/pdf
  "rotulo": "Pastel da Sueli - Av. ..."  // string, OPCIONAL: nome do local p/ a capa do PDF
}
```
- Regra de validacao: fornecer `{lat,lng}` OU `maps_url` (nao ambos vazios). Raio e **fixo 1.0 km**
  (Decisao 5, emendada pela DEC-021) — NAO e parametro de entrada.
- `rotulo` (aditivo compativel em `v1`, §10): quando presente e nao for apenas `"lat,lng"`, vai para a
  capa do PDF no lugar de "Coordenada: ...". Ignorado na saida JSON. Adicionado pela trilha do bot
  (BLK-API-07) para carimbar o nome do local no relatorio.

### 7.2 `POST /analisar` — response JSON (`AnalisarResponseJSON`, Decisao 6 inclusa)
KPIs derivados do `result` de `analisar_ponto_censitario_setores` (READ-ONLY):
```jsonc
{
  "lat": -23.95,
  "lng": -46.33,
  "raio_km": 1.0,
  "area_km2": 3.14,
  "metodo": "setor_censitario_intersecao_area_1km",
  "n_setores": 12,
  "pop_total_raio": 18432.0,
  "renda_per_capita_media_raio": 5210.0,
  // renda domiciliar (pos-contrato, PRs #124/#126/#129): os dois campos de renda sao
  // R$/mes POR DOMICILIO, NAO soma do raio ("total" = renda do domicilio inteiro,
  // com uplift de composicao SETORIAL + fator temporal)
  "renda_media_domiciliar_raio": 15790.0,
  "renda_domiciliar_total_raio": 25740.0,
  "domicilios_total_raio": 6084.0,
  "metodo_renda_domiciliar_raio": "ponderada_domicilios_estimados",
  "densidade_pop_raio_hab_km2": 5870.0,
  "score_setor_medio": 64.2,
  "score_setor_max": 91.0,
  "n_concorrentes": 3,
  "n_ultra": 1,
  // carimbo de versao/reprodutibilidade (Decisao 6):
  "versao_contrato": "api-geoespacial/v1",
  "versao_score": "score_setor_2022_calibrado",
  "gerado_em": "2026-06-10T12:00:00Z",
  "consumidor": "bot-telegram"   // resolvido pelo token (Decisao 2), p/ rastreio
}
```
> Os campos `concorrentes_raio` / `ultra_raio` / `setores_intersectados` do `result` podem ser
> expostos como detalhe opcional; o payload padrao do bot e o conjunto de KPIs acima — incluindo
> os 4 campos de renda domiciliar, aditivos compativeis em `v1` (§10). Campo a campo (tipos,
> nulabilidade, semantica) em `docs/api_geoespacial_openapi.yaml` (§15), que e a spec canonica.

### 7.3 `POST /analisar` — response PDF
- `Content-Type: application/pdf`; corpo = `bytes` de `gerar_pdf_relatorio_pontual_classico(result, mapas, ...)` — 7 paginas (BLK-RELPON-14; eram 8 com o slide "Imagem do Entorno").
- O **carimbo de versao** no rodape do PDF (Decisao 6) segue PREVISTO E NAO IMPLEMENTADO — ver §4.
  O PDF entregue hoje carimba a marca d'agua `Ultra Academia | {solicitante}` (BLK-EST-03) e o
  rodape de credito/atribuicao; a versao do contrato/score so existe no caminho JSON (§7.2).
- Gerado quando `?formato=pdf` ou `Accept: application/pdf`.

### 7.4 `GET /health` — response (`HealthResponse`)
```jsonc
{ "status": "ok", "environment": "production" }
```

## 8. Autenticacao (Decisao 2 = token por consumidor/bot)

- **Esquema:** token de portador por consumidor (header). MVP = lista/tabela ESTATICA
  `token -> consumidor` em `settings.py` (sem IdP), evoluivel para Authelia/JWT depois.
- **Rastreio:** o token resolve o **consumidor** (ex.: `bot-telegram`, `bot-whatsapp`), que e
  carimbado no JSON (`consumidor`) e disponivel para a marca d'agua/log LGPD do BLK-EST-01
  (quem pediu o estudo).
- **Aplicacao:** dependencia `auth.py` em todas as rotas exceto `GET /health`. Token invalido -> `401`.
- **`403` sem_permissao = RESERVADO:** previsto para escopos por consumidor, mas **nao emitido no MVP**
  (todo token valido tem acesso). O slug fica documentado para evolucao futura; hoje `auth.py` nunca o levanta.

## 9. Erros — modelo padrao

Corpo de erro padrao (`ErrorResponse`): `{ "detail": "<mensagem>", "codigo": "<slug>" }`.

| HTTP | Quando | Corpo (exemplo) |
|---|---|---|
| `400` | Coordenada invalida / `maps_url` nao parseavel / ponto fora do Brasil OU dentro do bbox mas fora de qualquer municipio (offshore) | `{"detail":"Coordenada fora do Brasil","codigo":"coordenada_invalida"}` |
| `401` | Token ausente/invalido | `{"detail":"Token invalido","codigo":"nao_autenticado"}` |
| `403` | Token valido sem permissao — **RESERVADO, nao emitido no MVP** (§8) | `{"detail":"Acesso negado","codigo":"sem_permissao"}` |
| `404` | Base geo ausente para a UF/municipio resolvidos | `{"detail":"Materialize setores_censitarios_2022_geo/ para esta UF/municipio","codigo":"base_geo_ausente"}` |
| `422` | Falha de validacao Pydantic (corpo malformado / nem lat/lng nem maps_url) | corpo padrao FastAPI (`{"detail":[<erros>]}`) — **sem** `codigo` |
| `500` | Erro inesperado na geracao do estudo/PDF | `{"detail":"Erro interno ao gerar o estudo","codigo":"erro_interno"}` |

> A mensagem do `404` espelha a do dashboard ("Materialize `setores_censitarios_2022_geo/`...").
> O `500` e garantido pelo handler catch-all (`unexpected_error_handler`), que converte QUALQUER
> excecao nao tratada no corpo `{detail, codigo:"erro_interno"}` — nenhum 500 vaza o corpo cru do FastAPI.
> Ponto offshore (dentro do bbox, sem municipio na malha IBGE) cai em `400 coordenada_invalida`, nao `404`.

## 10. Versionamento e carimbo

- **Prefixo:** todas as rotas sob `/api/v1` (`GET /api/v1/health`, `POST /api/v1/analisar`).
- **Politica:** mudanca incompativel de contrato -> `/api/v2`; aditivos compativeis ficam em `v1`.
- **Carimbo (Decisao 6):** `versao_contrato` + `versao_score` + `gerado_em` no JSON — implementado.
  A versao do contrato/score + data no rodape do PDF continua PREVISTA E NAO IMPLEMENTADA (§4/§7.3):
  a decisao segue valendo (e da DEC-005), mas o PDF de hoje nao a carrega.

## 11. Dependencias — extra `[api_mvp]` (o `[api]` e legado PostGIS)

**Subset MVP (manter):** `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`.
Conforme Decisao 2/4, podem entrar tambem `python-multipart` (formularios/uploads, se necessario);
o parser de `maps_url` e puro e nao exige `httpx`. Implementado no extra `[api_mvp]` do `pyproject.toml`,
isolado do bloco legado `[api]` (isolamento pedido por esta secao).

**Extras adicionais do runtime (pos-contrato, opcionais e isolados):**
- `[basemap]` (`contextily`) — fundo de ruas do PDF, import lazy + fallback offline (DEC-004, BLK-API-04).
- `[geocoder]` (`selenium`, `webdriver-manager`) — geocoder primario de **endereco+CEP** via Google Maps
  (`api/maps_geocoder.py`, requer Chrome no host). **Opcional por design:** ausente, `geo.py` cai no
  Nominatim (`geopy`, ja na base). Nasceu apos o contrato (2026-06-12); declarado para deploy reproduzivel.

**Legado PostGIS — FORA do MVP (NAO arrastar):** `sqlalchemy`, `asyncpg`, `psycopg2-binary`,
`alembic`, `geoalchemy2`, `sentry-sdk[fastapi]`, `prefect`, `httpx`, `aiohttp`, `python-jose`,
`passlib`. G1 recomenda que G2 instale apenas o subset MVP (idealmente isolando-o do bloco legado do
extra `[api]`); essas libs sao do desenho PostGIS antigo e nao tem uso no MVP on-demand.

**Guardrail de deploy:** as deps da API ficam em extras (`[api_mvp]` + `[basemap]`/`[geocoder]`),
fora do install base, para nao acoplar o motor compartilhado `dashboard/` — e as imagens que o
embarcam, como a `motor-expansao-web` — as deps da API (a regra nasceu para proteger o deploy base
do Streamlit, aposentado pela DEC-022, 2026-08-03). (Ha um import dashboard -> `api.maps_geocoder`,
mas sem arrastar dependencia — ver a excecao no §4.)

## 12. O que se aproveita do scaffold legado (`fora_primeira_fase/api_postgis/main.py`)

- **Aproveitavel como referencia:** o esqueleto `FastAPI(title=..., version=..., docs_url=...)`,
  o `CORSMiddleware` e o handler `GET /health` (`{"status": ..., "environment": ...}`).
- **Descartar:** `sentry_sdk.init(...)` e `structlog`; os routers PostGIS comentados
  (`hexagonos`/`concorrentes`/`imoveis`/`oportunidades`/`pipeline`); o `@app.on_event("startup")`
  (API deprecada do FastAPI — usar `lifespan` se necessario).
- **Divergencia de pasta:** o scaffold vive em `fora_primeira_fase/api_postgis/`; o codigo novo nasce
  em `src/motor_expansao/api/` (premissa §2.3). O scaffold legado nao e movido nem editado.

## 13. Decomposicao G2+ (BLK-API-02..07) — tambem em `tasks/backlog.md`

Parametrizada pela Decisao 3 = (a) (MVP minimo). Mapeada a G2/G3/G4 do ClickUp `86e1rtfcy`.

- **BLK-API-02 — Esqueleto do app + `/health` + settings + auth (G2 base).** Cria
  `src/motor_expansao/api/` real (`__init__.py`, `main.py`, `settings.py`, `auth.py`), CORS, `/health`.
  Sem logica de analise. Auth por token->consumidor (Decisao 2).
- **BLK-API-03 — `POST /analisar` JSON (G2).** `schemas/`, `routes/analisar.py`, `coord.py` (parser
  Maps + validacao Brasil, Decisao 4), `service.py` (resolucao coord->particao +
  `read_censo_geo_partition` + `analisar_ponto_censitario_setores`), carimbo de versao (Decisao 6).
- **BLK-API-04 — Saida PDF (G2/G3).** `?formato=pdf` / `Accept: application/pdf` via
  `render_mapas_censitarios_combinados` + `gerar_pdf_relatorio_pontual_censitario` *(plano de
  2026-06-10; hoje o caminho real usa a gemea `gerar_pdf_relatorio_pontual_classico` — ver §3/§4)*
  (Decisao 1 = (c)), com fallback `basemap=False` quando offline; rodape carimbado (Decisao 6,
  nao implementado — §7.3).
- **BLK-API-05 — Endpoints estendidos M1/mercado** *(CONDICIONAL / roadmap pos-MVP — so materializa
  se reaberta a Decisao 3 para (b)).* `POST /lookup-hex` (M1) e/ou `GET /mercado/...` (READ-ONLY).
- **BLK-API-06 — Integracao G3 (Felipe+Juan).** Testes de contrato fim-a-fim, observabilidade minima,
  doc de deploy da API.
- **BLK-API-07 — G4 Telegram/WhatsApp (Juan).** Clientes de bot consumindo `POST /analisar`.

## 14. Guardrails

- **§2 (fontes canonicas):** `config.py`/`CLAUDE.md`/`PRD.md` mandam nos parametros; ler o codigo real;
  toda mudanca com teste; nenhum PR com CI quebrado.
- **§5 (READ-ONLY M1):** a API e camada paralela de consumo — nao recalcula nem altera
  `score_priorizacao`, `hex_score_estrutural`, carteira, plano, artefatos oficiais.
- **§4 (camadas paralelas):** preservar 100% das linhas/colunas oficiais do M1; nao criar dependencia
  de API ao vivo no dashboard de producao.
- **Fronteira "importa-nao-edita `censo_*`"** e **"on-demand, PostGIS fora do MVP"** (Felipe, 2026-06-09):
  invioláveis.
- **Parametros canonicos imutaveis:** `H3_RESOLUTION=7`, pesos `renda=0.40`/`pop=0.60`, **raio 1.0 km**
  (DEC-021) e o **metodo de intersecao** censitario INTOCADOS.

## 15. Referencias

- DEC-005 (CLAUDE.md §8) — decisoes-chave do contrato aprovadas por Felipe em 2026-06-10.
- `docs/api_geoespacial_openapi.yaml` — esboco OpenAPI 3.1.0 dos endpoints do MVP.
- `docs/relatorio_pontual_censitario.md` — contrato do Relatorio Pontual Censitario (motor importado).
- `tasks/backlog.md` — bloco BLK-API-01 + decomposicao BLK-API-02..07.
- `fora_primeira_fase/api_postgis/main.py` — scaffold FastAPI legado (referencia).
- CLAUDE.md §2/§4/§5; PRD.md.
