> Handoff de repositorio criado em maio/2026 para o deploy inicial (Streamlit).
> **Revisado em 2026-08-03 (DEC-022):** o Streamlit foi aposentado; o app de producao
> e o piloto web (`web/`). As secoes abaixo descrevem o estado atual; runbooks vigentes
> em `docs/deploy_piloto_web.md` e `docs/infra_producao.md`.

# Handoff do repositorio

Contrato curto para compartilhar o repo com a equipe e operar o deploy do piloto web em VPS.

## Escopo do handoff

- Piloto web em `web/` (SPA React/Vite + backend FastAPI num unico container, porta
  interna 8899), lendo Parquets locais via o motor compartilhado em
  `src/motor_expansao/dashboard/`.
- Deploy via imagens do GHCR (`motor-expansao-web` e `motor-expansao-api`, buildadas de
  `Dockerfile.web`/`Dockerfile.api` pelo CI) pinadas por digest no `docker-compose.prod.yml`.
- Sem PostGIS obrigatorio, Prefect ou recalculo nacional no deploy.
- `score_priorizacao` e o score oficial do M1; `hex_score_estrutural` e artefatos oficiais nao devem mudar sem aprovacao explicita.
- Quartis sao apoio de ranking relativo; para reporte executivo e carteira, priorizar regua absoluta, churn esperado, receita esperada perdida e capacidade operacional.

## Mapa de pastas

| caminho | papel | handoff |
| --- | --- | --- |
| `web/` | piloto web (SPA React/Vite + FastAPI) — app de producao | codigo principal do deploy |
| `config.py` | parametros canonicos e defaults | manter junto do repo |
| `src/motor_expansao/` | pacote interno com o motor compartilhado (`dashboard/`), core e pipelines M1 | codigo modular do projeto |
| `src/motor_expansao/pipelines/` | pipelines analiticos e geracao de artefatos | nao rodar no deploy |
| `docs/` | contratos tecnicos e runbooks | fonte de consulta da equipe |
| `tests/` | validacoes automatizadas em `unit/`, `integration/` e `contracts/` | rodar suite rapida antes de handoff |
| `data/outputs/` | artefatos minimos consumidos pelos apps | enviar como pacote de dados externo ou volume |
| `data/staging/` | bases intermediarias nacionais/censitarias | pesado; externo ao repo compartilhavel |
| `data/raw/` | dados brutos e sensiveis | nao versionar |
| `concorrentes/` e `data/ultra/` | insumos operacionais locais | tratar como dado externo/sensivel |
| `Dockerfile.web`, `Dockerfile.api` e `docker-compose.prod.yml` | deploy VPS (imagens GHCR por digest) | caminho oficial do deploy |
| `fora_primeira_fase/` | legado PostGIS/Prefect, M2/M3, pesquisas e Power BI | fora do deploy |

## Artefatos de dados minimos do piloto web

O contrato de dados vigente esta em `docs/deploy_piloto_web.md` §2. Em resumo (tudo
montado `:ro` no container; sem o dado, a feature degrada em silencio):

| artefato | destino | uso |
| --- | --- | --- |
| `hexagonos_dashboard_enriquecido/` (particoes `uf=XX/`) | `data/outputs/` | **obrigatorio** — Mapa Territorial, carga por UF |
| `setores_censitarios_2022_geo/` | `data/outputs/` | Relatorio Pontual (malha real IBGE) |
| `base_calibracao_maduras.parquet` | `data/staging/` | semente p50/faixa da Viabilidade |
| `uplift_renda_domiciliar_municipio.parquet`, `uplift_composicao_setor.parquet`, `fator_temporal_renda.json` | `data/staging/` | renda domiciliar municipal (sem eles, fallback nacional) |
| `growth_api_historico.parquet`, `concorrentes_mapeados.parquet`, `unidades_ultra_performance_hex.parquet` | `data/staging/` | Visao Executiva + pins |
| `logo_<rede>.png` | `concorrentes/` | logos das bandeiras (sem eles, fallback sigla+cor) |

Os artefatos do handoff original de maio/2026 (`hexagonos_brasil_dashboard.parquet`,
`oportunidades_expansao_hibrido.parquet`, `carteira_expansao_acionavel.parquet`,
`plano_expansao_curto_prazo.parquet`) **continuam existindo e validos** (M1 READ-ONLY;
DEC-020/DEC-022) — carteira e plano apenas deixaram de ser superficie de app.

Camadas `data/staging/censo2022_setores_*.parquet` enriquecem rastreabilidade quando presentes. Elas sao opcionais para handoff leve e devem ser enviadas como artefatos externos se a equipe precisar auditar a origem censitaria.

## Comandos oficiais

Instalacao local:

```bash
python -m pip install -e ".[dev]"
copy .env.example .env
```

Piloto web em dev local (sobe o front Vite na porta 5000 e o backend FastAPI na 8899):

```bash
iniciar-piloto-web.cmd
```

Validacao rapida:

```bash
python -m pytest -q -o addopts='' tests/unit/test_piloto_web_api.py tests/unit/test_piloto_web_endpoints.py tests/integration/test_carteira_plano_nacional.py
cd web && npm test   # vitest do front
```

Validacao de artefatos:

```bash
python scripts/check_artifacts.py
```

Deploy do piloto web em VPS (modo PULL por digest — nada de `build` no servidor; runbook
completo em `docs/deploy_piloto_web.md`):

```bash
# .env da VPS: WEB_IMAGE=ghcr.io/kastaldy/motor-de-expansao/motor-expansao-web@sha256:<digest>
docker compose -f docker-compose.prod.yml pull web
docker compose -f docker-compose.prod.yml up -d web
docker compose -f docker-compose.prod.yml exec web curl -fsS http://127.0.0.1:8899/api/health
```

Recalculo analitico do M1, fora do deploy:

```bash
python -m motor_expansao.pipelines.m1.base_h3_brasil
python -m motor_expansao.pipelines.m1.hex_enrichment
python -m motor_expansao.pipelines.m1.fase1_bi_exports
```

## Arquivos sensiveis ou pesados

- Nao versionar `.env`, credenciais, planilhas privadas, dados brutos, staging nacional ou outputs temporarios.
- Tratar `data/raw/`, `data/staging/`, `data/ultra/`, `concorrentes/` e planilhas locais como dados externos ao codigo.
- Para VPS, montar `data/outputs/` como volume ou copiar o pacote minimo de Parquets para o servidor.

## Docker/API

O caminho oficial do deploy e `Dockerfile.web`/`Dockerfile.api` + `docker-compose.prod.yml`
(imagens do GHCR pinadas por digest), documentado em `docs/deploy_piloto_web.md` e
`docs/deploy_api_bot.md`.
O compose/API legado de PostGIS e Prefect fica arquivado em `fora_primeira_fase/api_postgis/`.

## Pacote de arquivos externos ao git

A equipe deve receber os seguintes arquivos **fora** do repositorio git (via drive, S3 ou transferencia direta):

| arquivo | destino na VPS | obrigatorio |
| --- | --- | --- |
| `hexagonos_dashboard_enriquecido/` (particoes `uf=XX/`) | `data/outputs/` | sim |
| `setores_censitarios_2022_geo/` | `data/outputs/` | sim (Relatorio Pontual) |
| `base_calibracao_maduras.parquet` | `data/staging/` | sim (Viabilidade) |
| `growth_api_historico.parquet`, `concorrentes_mapeados.parquet`, `unidades_ultra_performance_hex.parquet` | `data/staging/` | sim (Visao Executiva + pins) |
| `uplift_renda_domiciliar_municipio.parquet`, `uplift_composicao_setor.parquet`, `fator_temporal_renda.json` | `data/staging/` | recomendado (renda municipal) |
| `logo_<rede>.png` | `concorrentes/` | recomendado (logos dos pins) |
| `.env` (com `WEB_IMAGE`/`API_IMAGE` por digest + segredos reais) | raiz do projeto | sim |
| `censo2022_setores_calibrado.parquet` | `data/staging/` | sim |

Apos copiar, validar com `python scripts/check_artifacts.py` antes do deploy.

## Rollback

Se um deploy com novos Parquets introduzir regressao:

```bash
# 1. Parar o container
docker compose -f docker-compose.prod.yml stop web

# 2. Substituir os Parquets pelo conjunto anterior (manter backup antes de qualquer atualizacao)
cp /backup/data/outputs/*.parquet data/outputs/

# 3. Validar os artefatos
python scripts/check_artifacts.py

# 4. Reiniciar
docker compose -f docker-compose.prod.yml start web

# 5. Confirmar saude
docker compose -f docker-compose.prod.yml exec web curl -fsS http://127.0.0.1:8899/api/health
```

Recomendacao: manter pelo menos uma versao anterior dos Parquets minimos em `/backup/data/outputs/` antes de qualquer atualizacao de dados. Rollback de **imagem** e por digest (`WEB_IMAGE` anterior no `.env` + `pull` + `up -d web` — ver `docs/infra_producao.md`).

## Checklist de handoff

- Repo compartilhado com codigo, docs, testes, manifests e arquivos Docker do piloto web e da API.
- Pacote externo enviado com os artefatos minimos de dados (ver tabela acima).
- `.env` real e credenciais fora do git; usar `.env.example` como referencia.
- Suite rapida executada antes do envio: `tests/unit/test_piloto_web_api.py`, `tests/unit/test_piloto_web_endpoints.py` e `tests/integration/test_carteira_plano_nacional.py`.
- Smoke do piloto executado localmente (`iniciar-piloto-web.cmd`) ou na VPS.
- PostGIS, Prefect, scraping e pipelines nacionais pesados comunicados como fora do deploy.
