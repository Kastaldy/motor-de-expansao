# Motor de Expansao Ultra Academia

Base territorial do MVP nacional do `motor-de-expansao`.

O contrato canonico do projeto esta em `CLAUDE.md`; detalhes do ciclo ativo ficam em `PRD.md`.
O dashboard Streamlit esta estabilizado (ciclos Blocos 1-19 concluidos em 2026-05-21): Visao Executiva Ultra-only, Analise Pontual de Entorno com populacao/renda/pins de concorrentes, Cenario Multi-Hex com agregacao de potencial regional, Expansao de Dominio por score hibrido censitario-residual, consumo fitness instalado em todo o app, regua visual 10-em-10 para M1/Censitario/Hibrido/Residual, captura por clique com centroide de hex e Relatorio Pontual Censitario 1.0 km com setor real, mapa PNG e export CSV/PDF. Roda offline com Parquets locais, sem API ao vivo, sem PostGIS obrigatorio e sem recalculo do M1 no deploy inicial.
O ciclo `Performance e Refatoracao do Dashboard` (concluido em 2026-05-22) tornou a carga lazy por UF: o app le apenas a particao `uf=XX` do dataset enriquecido materializado (`data/outputs/hexagonos_dashboard_enriquecido/`), renderiza so a aba ativa e usa fonte de mapa enxuta. Medicoes em `data/reports/perf_baseline_dashboard.md`.

## Quickstart local

```bash
python -m pip install -e ".[dev]"
copy .env.example .env
python -m streamlit run streamlit_app.py
```

O instalar `.[dev]` inclui apenas as dependencias do dashboard e dos testes rapidos.
Extras opcionais: `.[api]` (FastAPI/PostGIS), `.[ml]` (XGBoost/LightGBM), `.[scraping]`.

Validacao rapida recomendada antes de handoff:

```bash
python -m pytest -q tests/integration/test_streamlit_app.py tests/integration/test_carteira_plano_nacional.py
python -c "import streamlit_app; print('ok')"
```

Suite de mercado (requer artefatos de staging):

```bash
python -m pytest -q tests/integration/test_modelo_mercado_hexagonos.py
```

## Dashboard Streamlit

Arquivo principal: `streamlit_app.py`.

O app roda offline e le Parquets locais. Para a experiencia completa do dashboard atual, manter estes artefatos em `data/outputs/`:

| arquivo | uso no dashboard | obrigatoriedade |
| --- | --- | --- |
| `hexagonos_brasil_dashboard.parquet` | base oficial M1, KPIs, ranking e mapa executivo | obrigatorio |
| `oportunidades_expansao_hibrido.parquet` | enriquecimento hibrido/censitario e filtros combinados | obrigatorio no app atual |
| `carteira_expansao_acionavel.parquet` | aba de carteira operacional | recomendado |
| `plano_expansao_curto_prazo.parquet` | aba de plano curto prazo | recomendado |
| `setores_censitarios_2022_geo/uf=XX/cod_municipio=NNNNNNN/part-000.parquet` | Relatorio Pontual Censitario 1.0 km | opcional, por municipio |

Camadas de apoio em `data/staging/` podem enriquecer rastreabilidade censitaria, mas dados brutos e staging nacionais grandes devem ser tratados como artefatos externos ao codigo.

### Pins de concorrentes no mapa

O dashboard tambem pode sobrepor pins dos concorrentes nos mapas principal e hibrido. A camada e visual: nao altera `score_priorizacao`, ranking, carteira nem nenhum artefato oficial.

Arquivos usados:

- CSVs em `concorrentes/` (`unidades_smart_fit.csv`, `unidades_bluefit.csv`, `unidades_panobianco.csv`, `SkyFit_unidades_geocodificado.csv`)
- Loader: `src/motor_expansao/dashboard/competitors.py`
- Camada de mapa: `src/motor_expansao/dashboard/components.py`

Como alterar imagem/cor das logos:

1. Para mudar cores ou iniciais dos pins atuais, edite `COMPETITOR_BRANDS` em `src/motor_expansao/dashboard/competitors.py`.
2. Para usar logos oficiais em vez do SVG com iniciais, altere `competitor_icon_data()` no mesmo arquivo para retornar um `url` da imagem, de preferencia em `data:image/png;base64,...` ou `data:image/svg+xml;base64,...` para manter o dashboard offline.
3. Mantenha o retorno no formato esperado pelo `pydeck.IconLayer`: `{"url": "...", "width": 128, "height": 128, "anchorY": 122}`.

Como diminuir o tamanho dos pins:

1. Abra `src/motor_expansao/dashboard/components.py`.
2. Na funcao `_build_competitor_icon_layer()`, reduza `comp["icon_size"] = 34`.
3. Se necessario, ajuste tambem `size_min_pixels=24` e `size_max_pixels=42` na criacao do `pdk.Layer("IconLayer", ...)`.
4. Rode `python -m pytest -q tests/integration/test_streamlit_app.py` para validar a camada.

### Pins das unidades Ultra no mapa

O dashboard sobrepoe pins das unidades proprias da Ultra Academia nos mapas principal e hibrido. A camada e visual e nao altera `score_priorizacao`, ranking nem artefatos do M1.

- Arquivo: `data/ultra/Ultra.csv` (opcional; formato: `sep=";"`, `encoding=latin-1`, 1 linha de metadado antes do cabecalho)
- Loader: `load_ultra_points` em `src/motor_expansao/dashboard/competitors.py`
- Pin vermelho (#C8001E) com sigla `UA`; tamanho ligeiramente maior que concorrentes para distincao visual
- Sem o arquivo, o app funciona normalmente sem a sobreposicao de pins Ultra

### Busca por coordenada

A sidebar do dashboard inclui um campo de busca de hexagono por coordenada geografica.

- Formatos aceitos: `lat, lng` (ex: `-23.55, -46.63`) ou `lat lng` separado por espaco
- O mapa centraliza na coordenada pesquisada com zoom 10
- O hex correspondente recebe destaque em amarelo em ambos os mapas (aparece mesmo fora dos filtros ou descartado pela regua 5k)
- Um card de detalhe acima das abas exibe `hex_id`, score, ranking, renda e populacao do hex
- Funciona offline sem API externa; nao altera score nem artefatos oficiais

### Analise Pontual de Entorno

A aba `Mapa Territorial` inclui uma analise de raio ao redor de uma coordenada.

- Raio default: `1.6 km` (area circular aproximada de `8.04 km2`)
- Clique via `st.pydeck_chart` retorna centroide do hex (decisao tecnica concluida no Bloco 12; pydeck mantido, folium descartado)
- Populacao total, renda per capita media e pins de concorrentes/Ultra filtrados por distancia haversine dentro do raio
- Nota visual exibida quando clique ativo; fallback por campo `lat,lng` na sidebar para coordenada exata
- Guardrail: a analise e visual/analitica e nao altera `score_priorizacao`, carteira, plano ou artefatos oficiais

### Relatorio Pontual Censitario 1.0 km

O expander `Relatorio Pontual Censitario`, na aba `Mapa Territorial`, usa a coordenada ativa do clique ou da busca da sidebar e raio fixo `1.0 km`.

- Base: `data/outputs/setores_censitarios_2022_geo/uf=XX/cod_municipio=NNNNNNN/part-000.parquet`
- Metodo: intersecao real setor censitario x circulo em CRS metrico local (`setor_censitario_intersecao_area_1km`)
- Saidas: KPIs, mapa PNG offline, tabela de setores intersectados e downloads CSV/PDF em memoria
- Sem base municipal, o app mostra mensagem clara e nao carrega shapefile nacional
- Guardrail: feature paralela; nao recalcula `score_priorizacao`, carteira, plano nem artefatos oficiais

### Regua visual de populacao minima (5k hab)

Hexagonos com menos de 5.000 habitantes sao descartados das abas Carteira e Plano e recebem cor cinza nos mapas.

- Constante: `POP_MIN_ACIONAVEL = 5_000` em `dashboard/constants.py`
- Fonte preferencial de populacao: `pop_total_setor_2022` (granular, UFs A/B); fallback: `populacao_proxy` = `pop_total` municipal (alterado 2026-05-15: removida trava 18-45)
- Cor dos hexes descartados nos mapas: `[120, 120, 140, 70]` (cinza semitransparente)
- Legenda "Descartado <5k hab" visivel nos mapas principal e hibrido
- M1 (`score_priorizacao`) nao e alterado por este corte

## Deploy VPS Streamlit

O deploy inicial de producao usa somente o dashboard Streamlit, com dados locais montados como volume.

```bash
python scripts/check_artifacts.py
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
curl -fsS http://127.0.0.1:8501/_stcore/health
```

Contrato completo: `docs/deploy_vps_streamlit.md`.

Recomendacoes operacionais:

- montar `data/outputs/` na VPS com os 4 Parquets minimos do dashboard;
- expor o app por proxy HTTPS com autenticacao, VPN ou allowlist;
- nao embutir dados ou secrets na imagem Docker;
- manter API/FastAPI, PostGIS, Prefect e pipelines pesados fora deste deploy inicial.

## Contrato oficial do M1

Fluxo oficial:

1. `base_h3_brasil.py` gera a base H3 nacional particionada por UF em `data/staging/brasil/uf=XX/hexagonos.parquet`.
2. `hex_enrichment.py` enriquece a base estrutural nacional, calcula score estrutural, ajuste executivo, score de priorizacao, corte top 20% por UF e camada de oportunidade.
3. `fase1_bi_exports.py` gera os artefatos executivos/BI estaveis em `data/outputs/`.

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
- `docs/handoff_repositorio.md`: checklist para compartilhar o repo com a equipe.
- `docs/artefatos_dados.md`: manifesto de dados, politica de versionamento e artefatos externos.
- `docs/deploy_vps_streamlit.md`: runbook Docker/Streamlit para VPS.
- `docs/streamlit_dashboard_m1.md`: governanca e uso do dashboard.
- `docs/analise_pontual_entorno.md`: contrato de UX, metricas de raio e limites tecnicos da analise pontual e Visao Executiva Ultra.
- `docs/modelo_mercado_hexagonos.md`: contrato tecnico da camada de mercado.
- `docs/api_geoespacial_contrato.md`: contrato da API GeoEspacial on-demand (status G1/BLK-API-01; ver DEC-005 no CLAUDE.md §8 e o esboco `docs/api_geoespacial_openapi.yaml`). Apenas contrato — sem API implementada.
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
/run-cycle "Adicionar filtro de renda mínima no painel de carteira"
```

O Claude Code lê `CLAUDE.md`, verifica `tasks/current_task.md`, classifica a criticidade, registra a tarefa ativa, executa a esteira correta e atualiza `context/handoff.md` entre as etapas. Se a criticidade for alta, crítica ou estratégica, o ciclo pausa antes do Builder e aguarda aprovação explícita.

### Como usar no Codex

No Codex, peça explicitamente para usar a skill `codex-run-cycle` e descreva a tarefa. O Codex usa os mesmos arquivos do Claude Code, mas atua como orquestrador principal do ciclo.

Exemplo de documentação simples:

```text
Use codex-run-cycle para atualizar o README.md com instruções de uso da carteira operacional.
```

Exemplo de melhoria média:

```text
Use codex-run-cycle para adicionar um filtro de UF na aba Carteira e Plano.
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

Estes comandos sao de pipeline analitico, nao do deploy Streamlit inicial:

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

## Docker, API e PostGIS

O deploy inicial deste ciclo usa `Dockerfile.streamlit` e `docker-compose.prod.yml`.
O legado de API/PostGIS/Prefect foi movido para `fora_primeira_fase/api_postgis/` e nao entra no caminho de producao do dashboard.

## Fora do deploy inicial

- API/FastAPI
- PostGIS obrigatorio
- Prefect
- pipelines nacionais pesados
- modulos M2/M3, pesquisas e legados em `fora_primeira_fase/`
- dados brutos e staging grandes dentro do repositorio compartilhavel
- dependencia de internet/API externa para o dashboard em producao
