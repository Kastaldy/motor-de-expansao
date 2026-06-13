# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-API-08 — Documentação ponta-a-ponta da API GeoEspacial (uso + manipulação)**

Criar `docs/api_geoespacial_uso.md` como **fonte única de USO** da API: autenticação,
endpoints JSON e PDF, exemplos `curl`, fluxo bot Telegram, tabela de erros, variáveis
`API_*` e ponteiros para os docs existentes. Tarefa puramente documental; zero alteração
de código ou artefatos do M1.

## Objetivo
Produzir um único documento que permita a qualquer usuário usar a API (JSON e PDF) e o
bot Telegram do zero, e a qualquer mantenedor entender env/erros/operação — sem precisar
juntar peças de múltiplos docs.

## Escopo permitido
- Criar `docs/api_geoespacial_uso.md` (arquivo novo; a única entrega de código do bloco).
- Seção de visão geral e arquitetura (2 containers: api porta 8077 interna + telegram-bot long-polling).
- Seção de autenticação: header `Authorization: Bearer <token>`, mapa token→consumidor, como obter/rotacionar via `API_TOKENS`.
- Seção de endpoints: `GET /health` (sem auth); `POST /api/v1/analisar` com schema request (`lat`, `lng`, `maps_url`, `formato`, `rotulo`) e response JSON (`AnalisarResponseJSON`), incluindo negociação JSON vs PDF (`?formato=pdf` / `Accept: application/pdf`), raio fixo 1.5 km e carimbo de versão (`versao_contrato`, `versao_score`, `gerado_em`, `consumidor`).
- Exemplos prontos: `curl` para JSON e para PDF; fluxo do bot Telegram (senha → nome → menu → localização → PDF).
- Tabela de erros `{detail, codigo}`: 400 `coordenada_invalida`, 401 `nao_autenticado`, 404 `base_geo_ausente`, 500 `erro_interno`.
- Seção de operação/env: todas as variáveis `API_*` com valor default, descrição e exemplo de produção (coletadas de `settings.py`).
- Rodar local: `uvicorn motor_expansao.api.main:app --reload`.
- Ponteiros (não duplicação) para: `docs/api_geoespacial_contrato.md`, `docs/api_geoespacial_openapi.yaml`, `docs/api_geoespacial_deploy.md`, `docs/deploy_api_bot.md`.
- Seção de limitações e roadmap (PostGIS = BLK-API-05; docs interativas `/docs`/`/redoc` só fora de produção).
- Atualização dos arquivos de processo do ciclo: `tasks/current_task.md`, `context/handoff.md`, `context/handoff/<timestamp>-block-orchestrator.md`.

## Fora de escopo
- Qualquer alteração em `src/motor_expansao/api/` ou qualquer outro código de produção.
- Alteração de `score_priorizacao`, `hex_score_estrutural`, pesos, carteira, plano, artefatos oficiais do M1 (READ-ONLY absoluto).
- Alteração do método de interseção `setor_censitario_intersecao_area_1p5km` ou do raio 1.5 km.
- Duplicar conteúdo dos docs existentes (linkar, não copiar).
- Qualquer comando no servidor VPS (GUARDRAIL §6).
- Criar outros docs além de `docs/api_geoespacial_uso.md`.
- Atualizar `tasks/backlog.md` com marcação de bloco concluído (isso é feito no fechamento do ciclo pelo orquestrador, não pelo Builder).

## Arquivos que devem ser lidos (para o Builder coletar a verdade técnica)

### Código da API (verdade técnica de schemas, endpoints, env e fluxo do bot)
- `src/motor_expansao/api/__init__.py` — versão `__version__ = "api-geoespacial/v1"`
- `src/motor_expansao/api/main.py` — rotas registradas, prefixo `/api/v1`, `/health` sem auth, `docs_url`/`redoc_url` só fora de produção
- `src/motor_expansao/api/settings.py` — **TODAS** as variáveis `API_*` com defaults: `API_ENVIRONMENT`, `API_API_PREFIX`, `API_CENSO_GEO_DIR`, `API_IBGE_DIR`, `API_ULTRA_DIR`, `API_COMPETITORS_LOGOS_DIR`, `API_STAGING_DIR`, `API_CORS_ORIGINS`, `API_TOKENS`, `API_TELEGRAM_TOKEN`, `API_BASE_URL`, `API_API_CALL_TOKEN`, `API_BOT_SENHA`, `API_GOOGLE_MAPS_API_KEY`, `API_BOT_SESSOES_PATH`
- `src/motor_expansao/api/auth.py` — header `Authorization: Bearer <token>`, comportamento 401
- `src/motor_expansao/api/routes/analisar.py` — `POST /api/v1/analisar`, negociação JSON/PDF, campos `formato` (query param) + `payload.formato` + `Accept: application/pdf`, `rotulo` no PDF
- `src/motor_expansao/api/schemas/__init__.py` — `AnalisarRequest`, `AnalisarResponseJSON`, `ErrorResponse` (campos exatos)
- `src/motor_expansao/api/errors.py` — slugs de `codigo`: `nao_autenticado`, `coordenada_invalida`, `erro_interno`
- `src/motor_expansao/api/coord.py` — formatos aceitos de `maps_url` (padrões regex: `!3dLAT!4dLNG`, `@lat,lng`, query params, `"lat,lng"` cru)
- `src/motor_expansao/api/service.py` — fluxo interno: ponto→município (malha IBGE)→partição censitária→`analisar_ponto_censitario_setores`→KPIs; `_VERSAO_SCORE = "score_setor_2022_calibrado"`
- `src/motor_expansao/api/geo.py` — geocoding de endereço+CEP (Nominatim/Google Geocoding API; fallback)
- `src/motor_expansao/api/maps_geocoder.py` — geocoder Selenium (Chrome headless) para endereço+CEP mais preciso; padrões de URL suportados
- `src/motor_expansao/api/telegram_bot.py` — máquina de estados do bot: estados `autorizado`, `aguardando_nome`, `aguardando_local`; fluxo senha→nome→menu→localização→PDF; nome do bot "Paulo"; 3 formas de localização (Maps link, `lat,lng`, endereço+CEP); persistência de sessões em `bot_sessoes_path`

### Docs existentes (para linkar, não duplicar)
- `docs/api_geoespacial_contrato.md` — contrato técnico (DEC-005), arquitetura de decisões, premissas canônicas
- `docs/api_geoespacial_openapi.yaml` — spec OpenAPI completa (schema detalhado)
- `docs/api_geoespacial_deploy.md` — instalação local (extras `api_mvp`/`basemap`/`geocoder`), dados necessários, hardening, observabilidade
- `docs/deploy_api_bot.md` — containerização VPS, `Dockerfile.api`, compose, segredos, dados na VPS

## Arquivos que podem ser alterados
- `docs/api_geoespacial_uso.md` — **novo** (criação; entrega principal do bloco)
- `tasks/current_task.md` — atualizar Skill atual / Próxima Skill
- `context/handoff.md` — atualizado pelo Planner e depois pelo Builder ao final (quando passar para QA)
- `context/handoff/<timestamp>-planner.md`, `context/handoff/<timestamp>-builder.md` — snapshots do ciclo

## Critérios de aceite
1. `docs/api_geoespacial_uso.md` existe e cobre todos os tópicos do escopo: visão geral, autenticação, endpoints (JSON + PDF), exemplos `curl` (JSON e PDF), fluxo do bot Telegram passo a passo, tabela de erros com os 4 códigos, todas as variáveis `API_*` com defaults, instrução de execução local, ponteiros para os 4 docs existentes, limitações e roadmap.
2. Um usuário novo consegue, só com o doc, autenticar + chamar `/analisar` em JSON e em PDF.
3. Um usuário do bot consegue, só com o doc, entender o fluxo senha→nome→localização→PDF e as 3 formas de envio de localização.
4. Quem mantém consegue, só com o doc, entender quais vars `API_*` configurar e onde ver mais detalhe de deploy.
5. O doc linka (não duplica) os 4 docs existentes: `api_geoespacial_contrato.md`, `api_geoespacial_openapi.yaml`, `api_geoespacial_deploy.md`, `deploy_api_bot.md`.
6. READ-ONLY sobre o M1: nenhum artefato oficial, score, peso ou parâmetro canônico é alterado.
7. O QA confirma que nenhum arquivo fora da lista "Arquivos que podem ser alterados" foi tocado.
8. Suite de testes passa sem regressão (bloco é documentação pura; não há testes a criar, mas a suite não pode quebrar).

## Criticidade classificada
Média

## Esteira recomendada
Block Orchestrator (este handoff) → **Planner** → Builder → QA (Opus 4.8)

Sem gate humano (criticidade Média, bloco documental, READ-ONLY sobre o M1).

## Riscos identificados
- **Verdade espalhada:** as variáveis `API_*` estão todas em `settings.py`; o Builder deve lê-las com cuidado para não omitir nenhuma (há 15 variáveis com prefixo `API_`, incluindo as do bot Telegram).
- **Slug `base_geo_ausente`:** verificar se esse código de erro existe em `errors.py` ou `service.py` — o backlog cita `404 base_geo_ausente` mas o `errors.py` analisado só define `APIError` genérico; o Builder deve grep em `service.py`/`routes/analisar.py` para confirmar o slug exato antes de documentar.
- **Fluxo do bot com estados extras:** a máquina de estados do `telegram_bot.py` tem estado `aguardando_nome` além dos citados no backlog; o Builder deve ler o arquivo completo para documentar o fluxo correto.
- **Docs interativas `/docs`/`/redoc`:** só disponíveis quando `API_ENVIRONMENT != "production"`; importante mencionar no doc para evitar confusão em produção.
- **Gotcha de CORS em produção:** `API_CORS_ORIGINS` precisa ser JSON (`["*"]` ou lista de origens), não string CSV — documentado na memória do projeto; o Builder deve mencionar isso na seção de operação.
- **Formato de `API_TOKENS`:** valor JSON string no env (`'{"tok":"consumidor"}'`); precisa de aspas externas no shell — mencionar no doc.

## Guardrails ativos
- READ-ONLY sobre o M1 (CLAUDE.md §2 e §5): nenhum artefato oficial, score, peso ou parâmetro canônico é alterado.
- GUARDRAIL ABSOLUTO VPS (CLAUDE.md §6): nenhum comando no servidor sem confirmação humana por comando.
- Nenhuma trilha paralela pode alterar o M1 sem aprovação explícita (CLAUDE.md §1).
- `setor_censitario_intersecao_area_1p5km` e raio 1.5 km INTOCADOS (CLAUDE.md §4).
