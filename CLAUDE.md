# Motor de Expansão Ultra Academia — CLAUDE.md

> Arquivo de contexto para o Claude Code e Codex. Leia este arquivo antes de qualquer tarefa.
> Responsável: Felipe Silva | Estratégia e Growth | Ultra Academia
> Versão: Abril 2026

---

## Visão Geral do Projeto

Sistema de expansão ativa contínua para a rede Ultra Academia (79 unidades ativas + 80 planejadas).
O sistema roda diariamente e responde 4 perguntas:

1. **Onde vale expandir?** → Inteligência territorial via hexágonos H3 + IBGE Censo 2022 + OSM
2. **Quem já atua ali?** → Radar competitivo via scraping (Wellhub, TotalPass, redes)
3. **Quais imóveis estão disponíveis?** → Pipeline imobiliário via APIs + scraping
4. **Qual ponto tem maior chance de sucesso?** → Score preditivo via ML

---

## Contexto de Negócio

- **Empresa:** Ultra Academia — rede brasileira, operando desde 2020
- **Unidades ativas:** 79 + 80 em abertura nos próximos 2 anos
- **Objetivo:** Acelerar expansão com inteligência de dados
- **Planos da rede:** GOLD, GOLDPASS, GOLDPRO, ULTRA360, STUDIOULTRA
- **Ticket médio:** GOLD R$117 | GOLDPASS R$147 | GOLDPRO R$127 | ULTRA360 R$110 | STUDIOULTRA R$197
- **LTV por cluster:** Veteranos R$4.528 | Novos c/ Fidelidade R$1.757 | GOLD Padrão R$1.259

### Clusters de Alunos (usados no scoring de potencial)
```
Novos c/ Fidelidade  → GOLDPRO/ULTRA360 → lifetime fixo 12m → risco moderado
Veteranos Mistos     → freq>8 + lifetime>12 → lifetime 16.4m → risco baixo
GOLD Padrão          → demais → lifetime 5m → risco alto
```

### Perfil de Unidade Ultra Academia
- Área mínima: 1200m² | ideal: 1500–2000m²
- Pé direito mínimo: 3.5m
- Estacionamento: obrigatório para unidades fora de shopping
- Distância mínima entre unidades Ultra: 1km (anti-canibalização)
- Zoneamento: ZC (comercial), ZM (misto), ZI (industrial adaptado)
- Público-alvo: 18–45 anos, renda domiciliar ≥ R$4.500/mês

---

## Arquitetura do Sistema

Inclui tambem uma camada de consumo e visualizacao (BI-ready) para artefatos executivos e uso direto em Power BI.

```
motor-expansao/
├── api/                    # FastAPI — backend REST
│   ├── routes/             # Endpoints por domínio
│   ├── schemas/            # Pydantic models
│   └── services/           # Lógica de negócio
├── jobs/                   # Pipelines agendados
│   ├── scrapers/           # Coleta de dados externos
│   ├── pipelines/          # ETL e enriquecimento
│   └── ml/                 # Inferência em batch
├── ml/                     # Machine Learning
│   ├── models/             # Treino e artefatos
│   ├── features/           # Feature engineering
│   └── validation/         # Backtesting e métricas
├── web/                    # Frontend React/Next.js
│   ├── components/         # Componentes reutilizáveis
│   ├── pages/              # Páginas da aplicação
│   └── maps/               # Componentes de mapa (Mapbox/Leaflet)
├── db/                     # Banco de dados
│   ├── migrations/         # Alembic migrations
│   └── seeds/              # Dados iniciais
├── tests/                  # Testes (ver seção dedicada)
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   ├── data/
│   └── contracts/
├── infra/                  # Docker, CI/CD, configs
├── docs/                   # Documentação técnica
├── scripts/                # Scripts utilitários
├── CLAUDE.md               # Este arquivo
├── .env.example            # Variáveis de ambiente
├── docker-compose.yml      # Ambiente local
└── pyproject.toml          # Dependências Python
```

---

## Stack Técnica

### Backend
- **Linguagem:** Python 3.11+
- **API:** FastAPI + Uvicorn
- **ORM:** SQLAlchemy 2.0 (async) + Alembic
- **Banco:** PostgreSQL 15 + PostGIS
- **Validação:** Pydantic v2
- **Jobs/Agendamento:** Prefect 2 (ou cron + scripts estruturados no MVP)
- **ML:** scikit-learn, XGBoost, LightGBM, h3-py
- **Scraping:** Playwright + requests + BeautifulSoup4
- **Geocodificação:** geopy + Google Maps API
- **Dados tabulares:** pandas, pyarrow (Parquet)
- **Testes:** pytest + pytest-asyncio + pytest-cov

### Frontend
- **Framework:** React + Next.js 14 (App Router)
- **Mapas:** Mapbox GL JS ou Leaflet + react-leaflet
- **UI:** Tailwind CSS + shadcn/ui
- **Testes:** Vitest + React Testing Library
- **E2E:** Playwright

### Infra
- **Containers:** Docker + Docker Compose
- **CI/CD:** GitHub Actions
- **Monitoramento:** Sentry + logs estruturados (structlog)
- **Deploy MVP:** Railway ou Render
- **Storage:** Parquet local/cloud para staging

---

## Convenções de Código

### Python
```python
# Separador CSV: sempre ponto e vírgula
df.to_csv("arquivo.csv", sep=";", encoding="utf-8-sig", index=False)

# Encoding padrão
encoding = "utf-8-sig"

# Paleta de cores Ultra Academia (matplotlib/visualizações)
CORES = {
    'purple': '#6B21A8',
    'cyan':   '#06B6D4',
    'red':    '#E63946',
    'green':  '#2A9D8F',
    'orange': '#F4A261',
    'blue':   '#457B9D',
    'pink':   '#EC4899',
    'white':  '#FFFFFF',
    'teal':   '#0D9488',
}

# Resolução H3 padrão
H3_RESOLUTION = 7  # ~1210m de raio — ideal para cidades médias/grandes

# Distância mínima anti-canibalização
DIST_MIN_ULTRA_KM = 1.0

# Renda mínima do entorno (R$/mês domiciliar)
RENDA_MIN = 4500
```

### Nomenclatura de Arquivos
```
jobs/scrapers/wellhub_scraper.py
jobs/scrapers/totalpass_scraper.py
jobs/pipelines/hex_enrichment.py
jobs/pipelines/imovel_qualification.py
ml/models/score_abertura.py
ml/features/hex_features.py
```

### Nomenclatura de Variáveis
- snake_case para Python, camelCase para JS/TS
- Prefixo `df_` para DataFrames pandas
- Prefixo `hex_` para dados de hexágonos H3
- Sufixo `_score` para outputs de scoring (0–100)
- Sufixo `_est` para estimativas de modelos ML

### Banco de Dados
- Nomes de tabela: snake_case, plural (`hexagonos`, `concorrentes`, `imoveis`)
- PKs: `id` UUID por padrão
- Timestamps: `created_at`, `updated_at` em todas as tabelas
- Todas as tabelas com dados geoespaciais: coluna `geom` PostGIS

### Git
- Branches: `feat/`, `fix/`, `chore/`, `data/`
- Commits: conventional commits (`feat: adiciona scraper wellhub`)
- Nenhum PR sobe sem CI verde

---

## Módulos do Sistema

### M1 — Geográfico (Prioridade: ALTA)
Hexagonalização do Brasil via H3 + enriquecimento GeoFusion.
- `hex_id`: identificador H3
- Features: renda_media, densidade_pop, pop_18_45, fluxo, potencial_consumo
- Output: `hex_score` (0–100) por hexágono

### M1 — Camada de Oportunidade
Transforma o score estrutural nacional em priorização acionável para expansão.
- Classificação de hexágonos por potencial
- Ranking nacional e regional
- Base pronta para BI e diretoria

### M2 — Radar Competitivo (Prioridade: ALTA)
Scraping diário de academias concorrentes.
- Fontes: Wellhub, TotalPass, SmartFit, Bluefit, Bodytech, Companhia Athletica
- Classificação: rede_grande, rede_media, boutique, independente, low_cost
- Output: mapa de pressão competitiva por hexágono + lista de alvos de aquisição

### M3 — Motor Imobiliário (Prioridade: ALTA)
Captação e triagem automática de imóveis.
- Fontes: ZAP Imóveis, VivaReal, OLX, QuintoAndar Comercial
- Filtros obrigatórios: área ≥1200m², comercial, coordenada válida
- Filtros desejáveis: pé direito ≥3.5m, estacionamento, fachada
- Output: esteira de oportunidades para o time imobiliário

### M4 — Scoring Preditivo (Prioridade: MÉDIA — após dados estabilizados)
Modelos ML para estimativa de rentabilidade de novos pontos.
- Base de treino: dados históricos das 79 unidades Ultra
- Targets: alunos_12m_est, faturamento_est, ltv_medio_est, payback_est, score_abertura
- Reusa padrões do Projeto Lifetime (validação temporal pré-2025/pós-2025)

### M5 — Operacional
Esteira de workflow para o time imobiliário.
- Status: novo → qualificado → em_analise → proposta → aprovado | descartado
- Histórico de decisões auditável

### M6 — Observabilidade
Monitoramento de jobs, validação de dados, alertas de falha.
- Sentry para exceções
- Logs estruturados por job (structlog)
- Dashboard de saúde dos pipelines

---

## Entidades Principais do Banco

```sql
-- Hexágonos e potencial territorial
hexagonos (id, hex_id H3, geom, cidade, uf, hex_score, renda_media,
           densidade_pop, pop_18_45, potencial_consumo, created_at, updated_at)

-- Features enriquecidas por hexágono
hex_features (id, hex_id, fonte, chave, valor, coletado_em)

-- Concorrentes mapeados
concorrentes (id, nome, rede, tipo, endereco, lat, lng, hex_id,
              fonte, ativo, coletado_em, created_at, updated_at)

-- Imóveis candidatos
imoveis (id, titulo, tipo, area_m2, preco_aluguel, endereco, lat, lng,
         hex_id, fonte, url, status, qualificado, imovel_score,
         created_at, updated_at)

-- Oportunidades rankeadas (imóvel + área)
oportunidades (id, imovel_id, hex_id, score_area, score_competitivo,
               score_imovel, score_abertura, alunos_est, faturamento_est,
               ltv_est, payback_est, status, created_at, updated_at)

-- Execuções de pipelines
pipeline_runs (id, job_name, status, started_at, finished_at,
               records_processed, errors, log)

-- Histórico de decisões imobiliárias
decisoes_imovel (id, imovel_id, status_anterior, status_novo,
                 responsavel, motivo, created_at)
```

---

## Regras de Scoring

### Score de Área (hex_score) — pesos implementados (`hex_enrichment.py`)
```python
PESOS_HEX_SCORE = {
    'renda_normalizada':     0.35,  # IBGE SIDRA renda per capita (ou setor censitário quando disponível)
    'pop_jovem_normalizada': 0.25,  # IBGE pop 18–45 anos
    'ausencia_concorrencia': 0.25,  # OSM academias no raio de 1500m (invertido)
    'vitalidade_comercial':  0.15,  # Google Places (fallback 50.0 sem API key)
}
```

### Fase 1 Brasil — arquitetura ativa
Pipeline ativo para fechar o MVP nacional sem dependência operacional do OSM:

1. `hex_score_estrutural` nacional sem OSM
   - Inputs: `renda_per_capita` + proxy populacional (`pop_18_45`, fallback `pop_total`)
   - Normalização global
   - Pesos reponderados proporcionalmente às variáveis disponíveis
   - Saída: `data/staging/brasil_estrutural.parquet`
2. Priorização nacional para execução comercial
   - Corte padrão: top 20% por UF
   - Saída: `data/staging/brasil_priorizados.parquet`
3. Camada de oportunidade e priorização executiva
   - Classificação executiva por faixa de oportunidade
   - Ranking Brasil, UF e município
   - Saídas: `data/staging/hexagonos_brasil_oportunidades.parquet` + `data/outputs/`
4. OSM pausado por hora
   - A estratégia incremental por município/cidade foi estudada e parcialmente implementada
   - A decisão atual do projeto é não usar OSM no MVP nacional enquanto o Overpass seguir inviável em escala
   - `brasil_oportunidades.parquet` com concorrência não é artefato ativo neste momento

### Score final da Fase 1 (`hex_score_final`)
- Escopo atual do MVP nacional: adiado
- Quando a fonte competitiva estiver estável, combinará `hex_score_estrutural` + `score_concorrencia`
- Até lá, a referência nacional de decisão é o `hex_score_estrutural` com corte por prioridade
- `hex_score_estrutural` é a métrica oficial do MVP nacional
- Concorrência permanece fora do escopo atual do fechamento executivo da Fase 1

### Score de Imóvel (imovel_score)
```python
PESOS_IMOVEL_SCORE = {
    'area_adequada':      0.35,  # ≥1.200m² = 100, <1.200m² = 0 (eliminatório)
    'preco_m2':           0.25,  # comparado à mediana da cidade
    'fachada':            0.20,  # booleano quando disponível
    'estacionamento':     0.20,  # booleano quando disponível
}
```

### Score de Abertura (score_abertura) — output do M4
```python
PESOS_SCORE_ABERTURA = {
    'hex_score':          0.30,
    'score_competitivo':  0.25,
    'imovel_score':       0.20,
    'alunos_est':         0.15,
    'payback_est':        0.10,  # invertido — menor payback = maior score
}
```

---

## Regras de Qualidade de Dados

### Eliminatórios (imóvel descartado automaticamente)
- `area_m2 < 1200`
- `lat` ou `lng` nulo / coordenada fora do Brasil
- `preco_aluguel` nulo
- Distância de unidade Ultra existente < 1km

### Alertas de Qualidade em Pipelines
- Volume de registros < 80% da coleta anterior → alerta crítico
- Taxa de geocodificação < 90% → alerta warning
- Scraper sem novos registros por 48h → alerta crítico
- Drift de score médio > 15% semana a semana → alerta warning

---

## Estratégia de Testes

### Regra de ouro
> Toda feature nova entra com teste. Nenhum PR sobe sem CI verde.

### Pirâmide
```
[E2E]          → Playwright — fluxos críticos do produto
[Integração]   → pytest — banco, APIs, jobs
[Contrato]     → snapshots de scrapers e payloads externos
[Unitário]     → pytest — scores, filtros, transformações, geo
[Dados]        → pandera/great_expectations — schema, nulls, ranges
[Modelos ML]   → métricas mínimas, ranges de output, estabilidade
```

### Testes obrigatórios por módulo
- **Scrapers:** teste de parsing com snapshot de HTML salvo + alerta se campos somem
- **Geocodificação:** teste com endereços conhecidos + validação de coordenada no Brasil
- **Score:** teste com inputs extremos (0, 100, nulos) + invariantes de ordenação
- **Pipeline ML:** teste de treino com subset + validação de range dos outputs
- **API:** teste de contrato (status, schema de resposta) para todos os endpoints

---

## Variáveis de Ambiente

Ver `.env.example` para lista completa. Variáveis críticas:

```
DATABASE_URL            # PostgreSQL + PostGIS
GOOGLE_MAPS_API_KEY     # Geocodificação
GEOFUSION_API_KEY       # Dados demográficos
SENTRY_DSN              # Monitoramento de erros
SECRET_KEY              # JWT / autenticação interna
MAPBOX_TOKEN            # Frontend — mapas
```

Nunca commitar `.env`. Usar `.env.example` como referência.

---

## Fontes Externas e Scrapers

| Fonte | Tipo | Frequência | Módulo |
|-------|------|-----------|--------|
| IBGE Censo 2022 (SIDRA + Shapefile) | API + FTP | Sob demanda | M1 |
| OSM Overpass | API gratuita | Sob demanda | M1/M2 |
| Wellhub (WheelHub) | Scraping Playwright | Diário | M2 |
| TotalPass | Scraping Playwright | Diário | M2 |
| SmartFit | Scraping requests | Diário | M2 |
| Bluefit | Scraping requests | Diário | M2 |
| ZAP Imóveis | Scraping Playwright | Diário | M3 |
| VivaReal | Scraping Playwright | Diário | M3 |
| OLX Comercial | API/Scraping | Diário | M3 |
| Google Places | API | Sob demanda | M2/M3 |

### Regras para scrapers
1. Sempre salvar snapshot do HTML coletado (para testes de contrato)
2. User-agent rotacionado + delays aleatórios (2–5s entre requests)
3. Retry com backoff exponencial (máx 3 tentativas)
4. Falha após 3 tentativas → registrar em `pipeline_runs` + alertar
5. Dados coletados sempre persistidos em staging (Parquet) antes do banco

---

## Projeto Lifetime — Integração

O Projeto Lifetime (churn + LTV por cluster) alimenta diretamente o Motor de Expansão:

- `ltv_medio_cluster_regiao`: média de LTV das unidades Ultra mais próximas do hexágono
- `churn_historico_regiao`: taxa de churn histórica de unidades similares
- `perfil_demografico_unidade`: fingerprint demográfico das 79 unidades (base de treino do M4)

Arquivos de referência do Projeto Lifetime:
```
base_limpa.parquet          # 289k registros tratados
base_lifetime_v2.csv        # Lifetime previsto por aluno
base_ltv_final.csv          # LTV completo por aluno
```

Convenções herdadas:
- `LIFETIME_MES` = (DATA_CANCELAMENTO ou hoje − DATA_COMPRA) / 30
- `FREQ_POR_MES` = FREQUENCIA / LIFETIME_MES.replace(0, 0.5)
- Validação temporal: treino pré-2025, teste 2025+

---

## Roadmap de Fases

```
FASE 0 — Foundation          (2 semanas)   ✅ concluída
FASE 1 — Mapa de Potencial   (4-6 semanas) ← você está aqui (piloto GO concluído)
FASE 2 — Radar Competitivo   (4-6 semanas)
FASE 3 — Motor Imobiliário   (4-6 semanas)
FASE 4 — Scoring Preditivo   (6-8 semanas)
FASE 5 — Operação Contínua   (3-4 semanas)
```

### Fase 0 — Checklist (concluída)
- [x] Estrutura de repositório criada
- [x] CLAUDE.md criado
- [x] config.py com settings (H3_RESOLUTION=7, AREA_MIN_M2=1200, DIST_MIN_ULTRA_KM=1.0)
- [x] Primeiros testes unitários (28 testes — `test_fontes_gratuitas.py`)
- [ ] PostgreSQL + PostGIS rodando via Docker
- [ ] .env.example preenchido
- [ ] Alembic configurado + primeira migration
- [ ] pyproject.toml com dependências
- [ ] GitHub Actions — CI básico (lint + testes)

### Fase 1 — Checklist atual (piloto Goiânia/GO)
- [x] `ibge_censo.py` — IBGECenso com SIDRA, resolver_municipio, bulk municipio
- [x] `poi_enrichment.py` — POIEnricher com OSM bulk bbox + retry 3× + fallback entre mirrors
- [x] `hex_enrichment.py` — pipeline H3 nacional: estrutural → priorização → OSM opcional/futuro → score final quando a fonte competitiva voltar a ser viável
- [x] `imovel_qualification.py` — score de imóvel com AREA_MIN_M2=1200
- [x] Pipeline executado em Goiânia/GO (469 hexágonos, 16s, fonte ibge_sidra_municipio_2022)
- [x] Relatório de validação Goiânia: `data/reports/validacao_fase1_goiania_v2.md`
- [x] Pipeline executado em Campinas/SP (469 hexágonos, 28.6s, 134 academias OSM via retry)
- [x] Relatório de validação Campinas: `data/reports/validacao_fase1_campinas.md`
- [x] Normalização multi-cidade: `rodar_pipeline_batch()` consolida N cidades antes de `normalizar_serie`
- [x] Batch GO + SP + MG + PR executado (1.876 hexágonos, 131s, score global 25.49–75.00)
- [x] Relatório multi-cidade: `data/reports/validacao_fase1_multicidade.md`
- [x] Renda municipal ativa: SIDRA t.10295 v.13431 (rendimento médio Censo 2022, sem sigilo)
- [x] Batch com renda real: score range 8.72–79.81, std 19.16 (era 25.49–75.00, std 10.50)
- [x] Relatório renda: `data/reports/validacao_renda_multicidade.md`
- [x] Auditoria OSM Curitiba/PR: causa raiz confirmada (429/504 no Overpass + cache vazio silencioso)
- [x] Curitiba revalidada (469 hexágonos, 96 academias OSM carregadas, `n_academias_osm` 0–11, `hex_score` voltou a variar)
- [x] Batch GO + SP + MG + PR reexecutado após correção OSM de Curitiba (1.876 hexágonos, ranking global válido)
- [x] Base nacional H3 do Brasil (resolução 7) gerada e validada em `data/staging/brasil/uf=XX/hexagonos.parquet`
- [x] Pipeline estrutural nacional sem OSM implementado com saída em `data/staging/brasil_estrutural.parquet`
- [x] Pipeline estrutural nacional executado (1.532.645 hexágonos, 135.8s, 100% preenchimento de renda e proxy populacional)
- [x] Seleção de áreas prioritárias implementada com corte padrão top 20% por UF e saída em `data/staging/brasil_priorizados.parquet`
- [x] Priorização nacional executada (`data/staging/brasil_priorizados.parquet`, 306.538 hexágonos, 985 municípios, 27 UFs)
- [x] Camada de priorização de negócio implementada
- [x] Ranking nacional gerado
- [x] Base pronta para consumo executivo
- [x] Dataset final para BI gerado
- [x] Tabelas executivas geradas
- [x] Base pronta para Power BI
- [x] Relatório executivo consolidado
- [ ] Concorrência OSM no MVP nacional — decisão atual: não utilizar por hora, fonte inviável em escala para o projeto
- [ ] Consolidação do `hex_score_final` com concorrência — adiada até nova decisão sobre fonte competitiva
- [ ] Relatório executivo final com concorrência (`data/reports/mvp_fase1_brasil.md`) — adiado junto com OSM
- [ ] Shapefile IBGE 2022 setores censitários (FTP retorna 404 — aguardar publicação IBGE)
- [ ] Configurar Google Maps API key (ativa peso de vitalidade comercial 15%)
- [ ] Persistência no banco PostgreSQL + PostGIS

### Saídas oficiais da Fase 1
- `data/staging/hexagonos_brasil_oportunidades.parquet`
- `data/outputs/hexagonos_brasil_dashboard.parquet`
- `data/outputs/top_oportunidades_resumo.csv`
- `data/outputs/resumo_por_uf.csv`
- `data/reports/resumo_executivo_fase1.md`

---

## Decisões de Design Registradas

| Data | Decisão | Motivo |
|------|---------|--------|
| Abr/2026 | H3 resolução 7 (área ~0.7km² por hex, mais adequado para triagem de regiões urbanas) | Resolução 8 era granular demais para o estágio atual do projeto |
| Abr/2026 | Área mínima atualizada para 1.200m² (mínimo) e 1.500–2.000m²+ (ideal) | Perfil real de unidade Ultra Academia exige espaço para equipamentos, vestiários e circulação |
| Abr/2026 | Prefect sobre Airflow | Menor overhead operacional para time pequeno |
| Abr/2026 | PostGIS sobre MongoDB | Queries geoespaciais nativas + joins com dados analíticos |
| Abr/2026 | MVP sem frontend próprio | Power BI como consumo inicial, web app na Fase 5 |
| Abr/2026 | Staging em Parquet antes do banco | Rastreabilidade + facilita reprocessamento |
| Abr/2026 | GeoFusion substituído por IBGE Censo 2022 + OSM Overpass | Fontes 100% gratuitas suficientes para M1; GeoFusion mantido como opção futura se precisar de dados de fluxo |
| Abr/2026 | Arquitetura bulk: 1 query OSM bbox + 1 call IBGE Localidades por cidade | Eliminação de N calls por hexágono — performance 9h → 16s no piloto Goiânia |
| Abr/2026 | OSM com fallback entre mirrors + falha bloqueante no bbox | Evita transformar indisponibilidade externa em `n_academias_osm=0` silencioso e contaminar o ranking global |
| Abr/2026 | Sentinela `"__nenhum__"` em `set_municipio_padrao` quando resolver falha | Evita fallback para Nominatim por hexágono quando IBGE Localidades não resolve a cidade |
| Abr/2026 | SIDRA nível municipal como fallback para setor censitário | Shapefile IBGE 2022 ainda sem publicação no FTP; SIDRA dá dado de cidade, não de setor |
| Abr/2026 | SIDRA t.10295 v.13431 como fonte primária de renda (em vez de t.10297) | t.10297 retorna sigiloso (`..`) para todos os municípios grandes; t.10295 retorna valor médio sem restrição |
| Abr/2026 | Base nacional H3 salva em Parquet particionado por UF (`data/staging/brasil/uf=XX/hexagonos.parquet`) com filtro geométrico estrito na malha oficial do IBGE | Escala melhor para enriquecimento batch da Fase 1, reduz memória de escrita e garante ausência de hexágonos fora do Brasil |
| Abr/2026 | Enriquecimento nacional desenhado em 2 passadas (UF → partição temporária → consolidação global) | Mantém uso de memória previsível por UF e preserva normalização global única do `hex_score` |
| Abr/2026 | Proxy `pop_18_45` municipal corrigido na SIDRA 9514 com ponderação parcial das faixas 15–19 e 45–49 | Os códigos usados antes não representavam 18–45; a ponderação 0.4/1.0/0.2 aproxima melhor a faixa-alvo do negócio |
| Abr/2026 | OSM nacional com cache local por bbox + split adaptativo + fallback planejado para área administrativa por UF | Permite retomar janelas já concluídas e reduz risco de zerar uma UF inteira por falha transitória do Overpass |
| Abr/2026 | Fase 1 nacional reorganizada para `pipeline estrutural + priorização`; OSM removido do escopo imediato do MVP | O Overpass permaneceu inviável em escala nacional; o score estrutural entrega fechamento operacional agora sem bloquear o projeto |
| Abr/2026 | Critério padrão de priorização nacional definido como top 20% por UF | Mantém cobertura mínima por estado, facilita execução incremental e evita concentração total do ranking em poucas praças |
| Abr/2026 | Estratégia OSM incremental por município/cidade priorizada fica mantida apenas como caminho técnico futuro, não como dependência atual | Preserva aprendizado e código de fallback, mas evita basear o MVP numa fonte externa instável |

---

## Contato e Referências

- **Responsável técnico:** Felipe Castaldi Candido da Silva (Estratégia e Growth, Ultra Academia)
- **Projeto relacionado:** Projeto Lifetime (`contexto_projeto_lifetime_v2.md`)
- **Blueprint executiva:** `docs/blueprint_executiva.md`
- **Stack de referência do Lifetime:** Python 3.14, pandas, sklearn, SQLAlchemy, ODBC/VPN
