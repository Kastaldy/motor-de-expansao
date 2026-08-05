# Motor de Expansao Ultra Academia

Base territorial do MVP nacional do `motor-de-expansao`.

O contrato canonico do projeto esta em `CLAUDE.md`; detalhes do ciclo ativo ficam em `PRD.md`.

O app de producao e o **piloto web** (`web/` — SPA React/Vite + deck.gl no front, FastAPI em `web/server/app.py` no back), com **3 superficies**: **Mapa Territorial** (porta de entrada por UF, funil de 5 camadas ate a recomendacao por municipio), **Visao Executiva** (a rede Ultra real, via Growth API) e **Viabilidade do ponto** (stress-test deterministico de um imovel). Os relatorios em PDF (Pontual Censitario 1,0 km e Municipal) saem do Mapa e da Viabilidade. Em producao tudo roda num unico container (`motor_expansao_web`) em `piloto.ultra-expansao.tech`, atras de Caddy + Authelia. Detalhes de produto em `web/README.md`; arquitetura em `docs/arquitetura_app_atual.md`.

O dashboard Streamlit — o app original, estabilizado nos ciclos de mai/2026 — foi **aposentado em 2026-08-03 pela DEC-022** (escopo do corte definido na DEC-020: paridade de Mapa + Visao Executiva + Viabilidade; Expansao de Dominio e Carteira/Plano nao viraram telas). O **motor compartilhado** que ele usava (`src/motor_expansao/dashboard/` — dados, censo, relatorios, concorrentes, viabilidade) continua vivo e e consumido pelo piloto, pela API GeoEspacial, pelo bot Telegram e pelo `fase1_bi_exports`; so a UI Streamlit saiu do repo. Historia dos ciclos: `tasks/completed.md` e `docs/decisions/DEC-020.md`/`DEC-022.md`.

## Quickstart local

Requisitos: Python 3.11+, Node.js (npm) e os Parquets locais (gitignored — ver `docs/artefatos_dados.md`).

```bash
python -m pip install -e ".[dev,api_mvp]"
copy .env.example .env
iniciar-piloto-web.cmd
```

O `.cmd` sobe as duas pecas e abre o browser: back-end FastAPI em `127.0.0.1:8899` e front Vite em `localhost:5000`. Ele aponta `MOTOR_DATA_DIR` para o `data/` do checkout; sobrescreva a variavel se o seu caminho for outro. Manual, se preferir:

```bash
cd web/server && MOTOR_DATA_DIR=<repo>/data python -m uvicorn app:app --port 8899 --reload
cd web && npm run dev
```

O `.[dev]` traz o motor compartilhado e os testes rapidos; o `.[api_mvp]` traz
FastAPI/uvicorn, necessarios ao back do piloto. Extras opcionais: `.[basemap]`
(tiles dos PDFs), `.[ml]`, `.[scraping]`.

Validacao rapida recomendada antes de handoff:

```bash
python -m pytest -q tests/unit/test_enrich_dashboard_data.py tests/unit/test_data_io_e_filtros.py
cd web && npm test
```

Suite de mercado (requer artefatos de staging):

```bash
python -m pytest -q tests/integration/test_modelo_mercado_hexagonos.py
```

## Piloto web

Backend: `web/server/app.py` (le os Parquets read-only e embrulha as funcoes puras do motor compartilhado). Frontend: `web/src/` (React + Vite + deck.gl).

O app le Parquets locais apontados por `MOTOR_DATA_DIR` (montados `:ro` em producao). Para a experiencia completa, manter estes artefatos:

| arquivo | uso no piloto | obrigatoriedade |
| --- | --- | --- |
| `data/outputs/hexagonos_dashboard_enriquecido/uf=XX/` | Mapa Territorial (carga lazy por UF) | obrigatorio |
| `data/outputs/setores_censitarios_2022_geo/uf=XX/cod_municipio=NNNNNNN/part-000.parquet` | Relatorio Pontual Censitario 1,0 km | por municipio |
| `data/staging/concorrentes_mapeados.parquet` e `unidades_ultra_performance_hex.parquet` | pins de concorrentes/Ultra no mapa | recomendado |
| `data/staging/growth_api_historico.parquet` | Visao Executiva (numeros reais da rede) | recomendado; sem ele a tela responde 404 |
| `data/staging/base_calibracao_maduras.parquet` | semente p50 da demanda na Viabilidade | recomendado |
| `data/staging/hexagonos_mercado_mapeado.parquet` | residual fitness do ponto no Relatorio Pontual | opcional |
| `data/staging/uplift_renda_domiciliar_municipio.parquet`, `uplift_composicao_setor.parquet`, `fator_temporal_renda.json` | renda media domiciliar municipal (tooltip e PDF) | opcional (fallback nacional) |

Dados brutos e staging nacionais grandes sao artefatos externos ao codigo (`docs/artefatos_dados.md`).

### Pins de concorrentes e Ultra no mapa

O piloto sobrepoe pins de concorrentes e das unidades Ultra no Mapa Territorial. A camada e visual: nao altera `score_priorizacao`, ranking nem nenhum artefato oficial.

- Pontos: `data/staging/concorrentes_mapeados.parquet` (concorrentes) e `unidades_ultra_performance_hex.parquet` (Ultra).
- Logos: `logo_<rede>.png` em `concorrentes/` (gitignored; sobrescreva com `MOTOR_COMPETITORS_LOGO_DIR`). Sem o PNG, fallback de sigla + cor da marca (`COMPETITOR_BRANDS` em `src/motor_expansao/dashboard/competitors.py`).
- Os CSVs em `concorrentes/` (`unidades_smart_fit.csv` etc.) continuam sendo a FONTE do pipeline: `normalizar_concorrentes.py` os consolida no parquet que o piloto e os PDFs consomem.

### Busca por coordenada

A lupa no cabecalho do piloto aceita coordenada (`lat, lng`, ponto ou virgula decimal), link do Google Maps ou endereco livre. Coordenada/link resolvem offline (parser puro, bbox do Brasil); endereco cai no geocoding (`/api/geocode`, Nominatim — DEC-010, com cache e fallback gracioso). Ao encontrar, o mapa voa ate o ponto, marca o hexagono H3 res-7 e abre o atalho "Estudo pontual" para a Viabilidade.

### Relatorios em PDF

- **Relatorio Pontual Censitario 1,0 km** (`POST /api/relatorio/pontual`): intersecao real setor censitario x circulo em CRS metrico (`setor_censitario_intersecao_area_1km`; raio 1,0 km desde a DEC-021). Contrato: `docs/relatorio_pontual_censitario.md`.
- **Relatorio Municipal** (`POST /api/relatorio/municipal`): 9 paginas, gerado no 4o passo do funil do Mapa. Contrato: `docs/relatorio_municipal_template.md`.

Ambos usam os geradores do motor compartilhado (`censo_report.py`, `relatorio_municipal.py`) — os mesmos da API GeoEspacial e do bot Telegram.

### Regua visual de populacao minima (5k hab)

Hexagonos com menos de 5.000 habitantes sao pintados de cinza no mapa e ficam fora do passo 1 (Potencial) do funil — o corte propaga pelas 5 camadas.

- Constante: `POP_MIN_ACIONAVEL = 5_000` em `src/motor_expansao/dashboard/constants.py`
- Fonte preferencial de populacao: `pop_total_setor_2022` (granular); fallback: `populacao_proxy` = `pop_total` municipal
- M1 (`score_priorizacao`) nao e alterado por este corte

## Deploy VPS (piloto web)

O deploy de producao e por **imagem publicada no GHCR e pinada por digest** — nunca build na VPS, nunca `:latest`. O job `publish-web` do CI roda em todo push na `main` que toque `web/**`, `Dockerfile.web`, o motor compartilhado ou o `pyproject.toml` (path-filter).

```bash
python scripts/check_artifacts.py
# na VPS (comando a comando, com aprovacao — CLAUDE.md §6):
docker compose -f docker-compose.prod.yml pull web && docker compose -f docker-compose.prod.yml up -d web
docker compose -f docker-compose.prod.yml exec web curl -fsS http://127.0.0.1:8899/api/health
```

Runbook completo: `docs/deploy_piloto_web.md`. API GeoEspacial + bot: `docs/deploy_api_bot.md`.

Recomendacoes operacionais:

- montar `/opt/motor-expansao/data/{outputs,staging,ibge,ultra}` e `concorrentes/` como volumes `:ro`;
- expor o app somente atras do Caddy + Authelia (subdominio `piloto.ultra-expansao.tech`);
- `dashboard.ultra-expansao.tech` fica vivo APENAS para `/tiles/*` (tileserver dos PDFs); a raiz redireciona 301 para o piloto (DEC-022);
- nao embutir dados ou secrets na imagem Docker;
- deploy e sempre passo manual do Felipe, por digest (DEC-016/§6 do CLAUDE.md — auto-merge nao deploya).

## Contrato oficial do M1

Fluxo oficial:

1. `base_h3_brasil.py` gera a base H3 nacional particionada por UF em `data/staging/brasil/uf=XX/hexagonos.parquet`.
2. `hex_enrichment.py` enriquece a base estrutural nacional, calcula score estrutural, ajuste executivo, score de priorizacao, corte top 20% por UF e camada de oportunidade.
3. `fase1_bi_exports.py` gera os artefatos executivos/BI estaveis em `data/outputs/` (inclusive o dataset enriquecido particionado que alimenta o piloto).

Regra canonica de score:

```python
# populacao_proxy = pop_total (trava de faixa etária 18-45 removida em 2026-05-15)
renda_pct_nacional = percentil_nacional(renda_per_capita)
pop_pct_nacional = percentil_nacional(populacao_proxy)

hex_score_estrutural = 100 * (
    0.40 * renda_pct_nacional +
    0.60 * pop_pct_nacional
)

score_priorizacao = clip(hex_score_estrutural + ajuste_executivo, 0, 100)
score_oficial = score_priorizacao
```

Campos oficiais esperados:

- `renda_pct_nacional`
- `pop_pct_nacional`
- `hex_score_estrutural`
- `ajuste_executivo`
- `score_priorizacao`
- `score_oficial`
- `score_oficial_nome`
- `score_percentil_nacional`

Parametros canonicos:

- `H3_RESOLUTION=7`
- `DIST_MIN_ULTRA_KM=1.0`
- `RENDA_MIN=4500` para renda domiciliar minima, nao per capita
- `M1_SCORE_OFICIAL=score_priorizacao`
- `M1_PRIORIZACAO_TOP_PCT_POR_UF=0.20`
- `M1_OSM_ENABLED=false`
- `M1_SETOR_CENSITARIO_OBRIGATORIO=false`
- `M1_POP_MINIMA_PROXY=1`

## Artefatos oficiais

- `data/staging/brasil_estrutural.parquet`
- `data/staging/brasil_priorizados.parquet`
- `data/staging/hexagonos_brasil_oportunidades.parquet`
- `data/outputs/hexagonos_brasil_dashboard.parquet`
- `data/outputs/hexagonos_mapa_sample.parquet`
- `data/outputs/top_oportunidades_resumo.csv`
- `data/outputs/resumo_por_uf.csv`

O contrato curto dos outputs esta em `docs/m1_outputs_oficiais.md`.
O contrato de handoff do repositorio esta em `docs/handoff_repositorio.md`.

## Mapa de docs

- `CLAUDE.md`: contrato canonico curto e guardrails permanentes.
- `PRD.md`: ciclo operacional atual e status dos blocos.
- `web/README.md`: produto e telas do piloto web.
- `docs/arquitetura_app_atual.md`: arquitetura do app atual (piloto web) + historia do Streamlit.
- `docs/deploy_piloto_web.md`: runbook de deploy do piloto na VPS (digest, Caddy, Authelia).
- `docs/handoff_repositorio.md`: checklist para compartilhar o repo com a equipe.
- `docs/artefatos_dados.md`: manifesto de dados, politica de versionamento e artefatos externos.
- `docs/streamlit_dashboard_m1.md`: governanca do dashboard Streamlit (HISTORICO — app aposentado pela DEC-022).
- `docs/analise_pontual_entorno.md`: contrato de UX, metricas de raio e limites tecnicos da analise pontual e Visao Executiva Ultra.
- `docs/modelo_mercado_hexagonos.md`: contrato tecnico da camada de mercado.
- `docs/api_geoespacial_contrato.md`: contrato da API GeoEspacial on-demand (implementada; container `motor_expansao_api`, consumida pelo bot Telegram — runbook em `docs/deploy_api_bot.md`).
- `fora_primeira_fase/README.md`: inventario dos codigos, docs e dados separados do deploy inicial.

## Orquestração de Agentes

O projeto usa uma esteira de agentes especializados para manter cada ciclo pequeno, rastreável e proporcional ao risco. O mesmo protocolo funciona no Claude Code e no Codex: a tarefa entra por um orquestrador, passa por papéis com escopo definido e deixa o próximo passo registrado em `context/handoff.md`.

### Estrutura de controle

| Caminho | Papel |
| --- | --- |
| `tasks/current_task.md` | Tarefa ativa: ID, status, escopo, criticidade, esteira e próxima etapa |
| `tasks/backlog.md` | Tarefas pendentes, prioridades e criticidade esperada |
| `tasks/completed.md` | Histórico resumido dos ciclos concluídos |
| `context/handoff.md` | Passagem objetiva entre agentes; é atualizado a cada etapa |
| `prompts/` | Prompts versionados dos papéis: Orchestrator, Planner, Builder e QA |
| `.claude/commands/run-cycle.md` | Comando `/run-cycle` do Claude Code |
| `.codex/skills/codex-run-cycle/SKILL.md` | Skill do Codex que replica a esteira com os mesmos arquivos de controle |

### Papéis dos agentes

| Agente | Responsabilidade |
| --- | --- |
| **Block Orchestrator** | Delimita o bloco, reduz ambiguidade, define escopo, fora de escopo, arquivos e critérios de aceite. Não implementa. |
| **Planner** | Converte o bloco em plano técnico numerado, com riscos, dependências e validações. Não implementa. |
| **Builder** | Executa somente o que foi autorizado no handoff, com mudanças mínimas e rastreáveis. |
| **QA / Quality Analyzer** | Audita a entrega, verifica aderência ao escopo, valida evidências e emite veredito. |
| **Codex chefe** | No Codex, é o agente principal: coordena a esteira, decide quando usar sub-agentes, cobra handoff e pede aprovação humana quando necessário. |

### Esteiras por criticidade

| Criticidade | Exemplos | Esteira |
| --- | --- | --- |
| Baixa | ajuste textual, bug isolado, documentação simples | Block Orchestrator → Builder |
| Média | melhoria localizada, nova função pequena, nova tela simples | Block Orchestrator → Planner → Builder → QA |
| Alta | feature nova, mudança em pipeline, impacto operacional relevante | Block Orchestrator → Planner → aprovação humana → Builder → QA |
| Crítica | `score_priorizacao`, ranking, artefato M1, KPI executivo, carteira ou plano oficial | Block Orchestrator → Planner → aprovação humana obrigatória → Builder → QA |
| Estratégica | redesenho arquitetural, nova fase, mudança de premissa central | Block Orchestrator → Planner → aprovação humana obrigatória → Builder → QA |

Qualquer tarefa que toque `score_priorizacao`, `hex_score_estrutural`, pesos do score, carteira, plano curto prazo ou artefatos oficiais do M1 deve ser tratada como crítica.

### Como usar no Claude Code

Acione o comando `/run-cycle` com a descrição objetiva do bloco:

```text
/run-cycle "Adicionar filtro de renda mínima no funil do Mapa Territorial"
```

O Claude Code lê `CLAUDE.md`, verifica `tasks/current_task.md`, classifica a criticidade, registra a tarefa ativa, executa a esteira correta e atualiza `context/handoff.md` entre as etapas. Se a criticidade for alta, crítica ou estratégica, o ciclo pausa antes do Builder e aguarda aprovação explícita.

### Como usar no Codex

No Codex, peça explicitamente para usar a skill `codex-run-cycle` e descreva a tarefa. O Codex usa os mesmos arquivos do Claude Code, mas atua como orquestrador principal do ciclo.

Exemplo de documentação simples:

```text
Use codex-run-cycle para atualizar o README.md com instruções de uso do piloto web.
```

Exemplo de melhoria média:

```text
Use codex-run-cycle para adicionar um filtro de UF na Visão Executiva do piloto.
```

Exemplo crítico:

```text
Use codex-run-cycle para revisar a regra de score_priorizacao.
```

Nesse último caso, o Codex deve parar após o Planner, mostrar o handoff completo e só executar o Builder depois de uma resposta explícita como `aprovar`.

### Fluxo operacional no Codex

1. Ler `CLAUDE.md`, `README.md`, `tasks/current_task.md` e, se necessário, `tasks/backlog.md`.
2. Classificar a criticidade da demanda.
3. Registrar ou atualizar `tasks/current_task.md` quando o ciclo exigir controle formal.
4. Executar os papéis da esteira usando `prompts/` e `context/handoff.md`.
5. Para tarefas altas, críticas ou estratégicas, pausar antes do Builder e pedir aprovação humana.
6. Validar a entrega com os comandos definidos no handoff.
7. Fechar o ciclo com status, resumo, arquivos alterados e próximo passo recomendado.

Para tarefas simples de documentação, o ciclo costuma ser: delimitar escopo, editar o arquivo alvo, revisar o diff e reportar a validação executada.

## Recalculo do M1

Estes comandos sao de pipeline analitico, nao do deploy do piloto:

```bash
python base_h3_brasil.py
python hex_enrichment.py --brasil
python fase1_bi_exports.py
```

Testes relevantes do M1:

```bash
python -m pytest tests/integration/test_base_h3_brasil.py tests/integration/test_hex_enrichment_brasil.py tests/integration/test_fase1_bi_exports.py tests/contracts/test_fontes_gratuitas.py -v
```

## Camada censitaria — populacao v0001

A variavel correta para populacao total no Censo IBGE 2022 Basico e `v0001` (Total de pessoas). Antes de 2026-05-15 era usada `v0002` (Total de Domicilios), causando undercount de ~2.3x.

**Status atual:**
- Piloto GO/SP/RJ (`censo2022_setores_calibrado.parquet`): corrigido e rematerializado.
- Nacional — 21 UFs restantes (`censo2022_setores_calibrado_nacional_completo.parquet`): aguarda regeneracao (Bloco 8 do PRD).

**Cadeia de regeneracao** (em `jobs/pipelines/`, executar na ordem):

| passo | script | saida |
| --- | --- | --- |
| 1 | `fase_a_censo2022_setores.py` | `censo2022_setores_h3_res7.parquet`, `nacional_completo.parquet` |
| 2 | `validar_fase_a_censo2022.py` + copiar para `validado_v2` | `censo2022_setores_validado_v2.parquet` |
| 3 | `calibrar_renda_setor_2022.py` | `censo2022_setores_calibrado.parquet` |
| 4 | `modelo_hibrido_expansao.py` | `oportunidades_expansao_hibrido.parquet` |
| 5 | `calcular_colunas_mercado.py` | `hexagonos_mercado_mapeado.parquet` |
| 6 | `gerar_carteira_acionavel.py` | `carteira_expansao_acionavel.parquet` |
| 7 | `gerar_plano_expansao_curto_prazo.py` | `plano_expansao_curto_prazo.parquet` |

**Testes de regressao da camada censitaria:**

```bash
python -m pytest tests/unit/test_pop_censo_v0001.py -v
python -m pytest tests/integration/test_modelo_hibrido_expansao.py tests/integration/test_modelo_mercado_hexagonos.py -v
```

UFs com `qualidade_join_uf=C` (AM, RR, AL, AP, CE, MA, PA, PB, PE, RO, SE) sao filtradas automaticamente pelo modelo hibrido; nao afetam a carteira final.

## Docker, imagens e API

O caminho de producao usa duas imagens publicadas no GHCR pelo CI e pinadas por digest no `.env` da VPS (`docker-compose.prod.yml`):

- `motor-expansao-web` (`Dockerfile.web`): o piloto — estagio Node builda o Vite, estagio Python serve SPA + API na porta 8899.
- `motor-expansao-api` (`Dockerfile.api`): API GeoEspacial on-demand + bot Telegram (mesma imagem, dois containers).

A imagem `motor-expansao-streamlit` morreu com o corte (DEC-022); fica retida no GHCR por algumas semanas so para rollback. O legado de PostGIS/Prefect segue em `fora_primeira_fase/api_postgis/` e nao entra no caminho de producao.

## Fora do caminho de producao

- PostGIS obrigatorio
- Prefect
- pipelines nacionais pesados (rodam offline, fora dos containers)
- modulos M2/M3, pesquisas e legados em `fora_primeira_fase/`
- dados brutos e staging grandes dentro do repositorio compartilhavel

Pipelines e artefatos do M1 seguem offline (Parquet local, sem API ao vivo NELES). O piloto web e um app de API ao vivo por decisao explicita (DEC-022), mas READ-ONLY sobre os artefatos: nenhum score e recalculado em runtime.
