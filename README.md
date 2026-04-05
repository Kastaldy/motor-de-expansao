# Motor de Expansão Ultra Academia

> Sistema de expansão ativa contínua — identifica, ranqueia e monitora oportunidades de abertura de novas unidades.

**Responsável:** Felipe Silva — Data Lead  
**Stack:** Python 3.11 · FastAPI · PostgreSQL + PostGIS · Playwright · scikit-learn · H3  
**Status:** Fase 0 — Foundation ✅

---

## Início Rápido (5 minutos)

```bash
# 1. Clonar e entrar no projeto
git clone <repo-url> motor-expansao
cd motor-expansao

# 2. Configurar variáveis de ambiente
cp .env.example .env
# Editar .env com suas chaves (Google Maps, GeoFusion, etc.)

# 3. Subir banco de dados
docker-compose up -d db

# 4. Instalar dependências Python
pip install -e ".[dev]"

# 5. Instalar browsers para scraping
playwright install chromium

# 6. Criar tabelas no banco
alembic upgrade head

# 7. Verificar setup
python scripts/setup.py --check

# 8. Rodar testes
pytest tests/unit -v

# 9. Iniciar API
uvicorn api.main:app --reload
# → http://localhost:8000/docs
```

---

## Estrutura do Projeto

```
motor-expansao/
│
├── CLAUDE.md               ← Contexto para Claude Code (ler primeiro!)
│
├── api/                    ← FastAPI
│   ├── main.py             ← Ponto de entrada
│   ├── config.py           ← Configurações centralizadas
│   ├── routes/             ← Endpoints por módulo
│   ├── schemas/            ← Pydantic models
│   └── services/           ← Lógica de negócio
│
├── jobs/                   ← Pipelines e scrapers
│   ├── daily_pipeline.py   ← Orquestrador diário (roda às 3h)
│   ├── scrapers/
│   │   ├── base_scraper.py         ← Classe base com retry/rate limiting
│   │   ├── imovel_scraper.py       ← ZAP, VivaReal, OLX (M3)
│   │   └── (wellhub, totalpass...) ← Concorrentes (M2) — ver base_scraper.py
│   └── pipelines/
│       ├── hex_enrichment.py       ← H3 + GeoFusion (M1)
│       ├── imovel_qualification.py ← Filtros e score de imóveis (M3)
│       ├── score_consolidado.py    ← Ranking final de oportunidades
│       └── geocoding.py            ← Geocodificação com cache
│
├── ml/                     ← Modelos preditivos (M4 — Fase 4)
│   ├── models/             ← Treino e artefatos
│   ├── features/           ← Feature engineering
│   └── validation/         ← Backtesting e métricas
│
├── db/
│   ├── models.py           ← SQLAlchemy ORM (todas as entidades)
│   ├── database.py         ← Engines async e sync
│   └── migrations/         ← Alembic migrations
│
└── tests/
    ├── conftest.py          ← Fixtures globais
    ├── unit/               ← Testes de scores, filtros, transformações
    ├── integration/        ← Testes de banco e API
    ├── contracts/          ← Testes de contrato de scrapers
    ├── data/               ← Validação de schema e qualidade
    └── e2e/                ← Playwright (fluxos do produto)
```

---

## Módulos do Sistema

| Módulo | Descrição | Status |
|--------|-----------|--------|
| **M1** Geográfico | Hexágonos H3 + GeoFusion | 🟡 Em desenvolvimento |
| **M2** Radar Competitivo | Wellhub, TotalPass, SmartFit, Bluefit | 🟡 Em desenvolvimento |
| **M3** Motor Imobiliário | ZAP, VivaReal, OLX + qualificação | 🟡 Em desenvolvimento |
| **M4** Scoring Preditivo | ML de rentabilidade | ⚪ Fase 4 |
| **M5** Operacional | Esteira imobiliária + workflow | ⚪ Fase 5 |
| **M6** Observabilidade | Sentry + logs + alertas | 🟡 Configurado |

---

## Comandos Úteis

```bash
# Rodar pipeline diário manualmente
python -m jobs.daily_pipeline --cidades "São Paulo,SP;Campinas,SP"

# Hexagonalizar uma cidade
python -m jobs.pipelines.hex_enrichment --cidade "Goiânia" --uf GO

# Coletar imóveis de uma cidade
python -m jobs.scrapers.imovel_scraper --cidade "Belo Horizonte" --uf MG

# Rodar testes unitários
pytest tests/unit -v

# Rodar testes com coverage
pytest tests/unit tests/integration --cov --cov-report=html

# Verificar linting
ruff check .

# Criar nova migration
alembic revision --autogenerate -m "descricao da mudanca"

# Aplicar migrations
alembic upgrade head
```

---

## Fluxo de Dados

```
GeoFusion API
    ↓
[M1] Hexagonalização H3
    ↓ hex_score por área
    ↓
[M2] Scrapers de concorrentes ──→ score_competitivo por área
    ↓
[M3] Scrapers de imóveis
    ↓ geocodificação + qualificação
    ↓ imovel_score
    ↓
[Score Consolidado]
    hex_score × 0.30
  + score_competitivo × 0.25
  + imovel_score × 0.20
  + alunos_est × 0.15
  + payback_est × 0.10
    = score_abertura (0-100)
    ↓
[Ranking de Oportunidades] → time imobiliário
    ↓
[M4 — Fase 4] ML de rentabilidade (79 unidades como treino)
```

---

## Convenções Obrigatórias

- **CSV:** `sep=";"`, `encoding="utf-8-sig"`
- **Parquet:** staging de todos os dados antes do banco
- **H3:** resolução 8 por padrão
- **Anti-canibalização:** 2km mínimo entre unidades Ultra
- **Score:** sempre entre 0 e 100
- **Git:** conventional commits, CI verde antes de merge
- **Testes:** toda feature nova entra com teste

---

## Contexto de Negócio

Ultra Academia — rede brasileira com 79 unidades ativas e 80 planejadas.

| Plano | Ticket Médio | LTV Estimado |
|-------|-------------|-------------|
| GOLD | R$117/mês | R$1.259 |
| GOLDPASS | R$147/mês | — |
| ULTRA360 | R$110/mês | R$1.757 |
| STUDIOULTRA | R$197/mês | — |

**Perfil ideal de unidade:** 800–1.500m², pé direito ≥3.5m, estacionamento, zoneamento ZC/ZM, público 18–45 anos, renda domiciliar ≥ R$3.000/mês.

---

## Projeto Relacionado

O **Projeto Lifetime** (churn + LTV por cluster) alimenta diretamente o Motor de Expansão com:
- LTV médio por cluster e região → input para estimativa de rentabilidade
- Perfil demográfico das 79 unidades → base de treino do M4
- Taxa de churn histórica por região → ajuste do score de abertura

Arquivos: `base_lifetime_v2.csv`, `base_ltv_final.csv`

---

## Dúvidas?

Ler o **CLAUDE.md** — todas as convenções, arquitetura, entidades e regras de negócio estão documentadas lá.
