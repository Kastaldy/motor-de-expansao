# Handoff do repositorio

Contrato curto para compartilhar o repo com a equipe e preparar o deploy Streamlit em VPS.

## Escopo do handoff

- Dashboard Streamlit em `streamlit_app.py` lendo Parquets locais.
- Deploy inicial via `Dockerfile.streamlit` e `docker-compose.prod.yml`.
- Sem API ao vivo, PostGIS obrigatorio, Prefect ou recalculo nacional no deploy inicial.
- `score_priorizacao` e o score oficial do M1; `hex_score_estrutural` e artefatos oficiais nao devem mudar sem aprovacao explicita.
- Quartis sao apoio de ranking relativo; para reporte executivo e carteira, priorizar regua absoluta, churn esperado, receita esperada perdida e capacidade operacional.

## Mapa de pastas

| caminho | papel | handoff |
| --- | --- | --- |
| `streamlit_app.py` | dashboard executivo M1 + hibrido | codigo principal do deploy inicial |
| `config.py` | parametros canonicos e defaults | manter junto do repo |
| `src/motor_expansao/` | pacote interno com dashboard, core e pipelines M1 | codigo modular do projeto |
| `jobs/pipelines/` | pipelines analiticos e geracao de artefatos | nao rodar no deploy inicial |
| `docs/` | contratos tecnicos e runbooks | fonte de consulta da equipe |
| `tests/` | validacoes automatizadas em `unit/`, `integration/` e `contracts/` | rodar suite rapida antes de handoff |
| `data/outputs/` | artefatos minimos consumidos pelo dashboard | enviar como pacote de dados externo ou volume |
| `data/staging/` | bases intermediarias nacionais/censitarias | pesado; externo ao repo compartilhavel |
| `data/raw/` | dados brutos e sensiveis | nao versionar |
| `concorrentes/` e `data/ultra/` | insumos operacionais locais | tratar como dado externo/sensivel |
| `Dockerfile.streamlit` e `docker-compose.prod.yml` | deploy VPS do dashboard | caminho oficial do deploy inicial |
| `fora_primeira_fase/` | legado API/PostGIS/Prefect, M2/M3, pesquisas e Power BI | fora do deploy inicial |

## Artefatos minimos do dashboard

Metadados locais observados em 2026-05-12, sem recalculo:

| arquivo em `data/outputs/` | linhas | tamanho aprox. | uso |
| --- | ---: | ---: | --- |
| `hexagonos_brasil_dashboard.parquet` | 1.532.645 | 46,6 MB | base oficial M1 e mapa executivo |
| `oportunidades_expansao_hibrido.parquet` | 1.532.645 | 66,7 MB | filtros, camada hibrida e enriquecimento censitario |
| `carteira_expansao_acionavel.parquet` | 5.406 | 0,4 MB | carteira operacional |
| `plano_expansao_curto_prazo.parquet` | 269 | 0,1 MB | plano curto prazo |

Arquivos auxiliares em `data/outputs/`, como CSVs executivos e `hexagonos_mapa_sample.parquet`, sao uteis para BI/analise, mas nao compoem o contrato minimo do app completo atual.

Camadas `data/staging/censo2022_setores_*.parquet` enriquecem rastreabilidade quando presentes. Elas sao opcionais para handoff leve e devem ser enviadas como artefatos externos se a equipe precisar auditar a origem censitaria.

## Comandos oficiais

Instalacao local:

```bash
python -m pip install -e ".[dev]"
copy .env.example .env
```

Dashboard:

```bash
python -m streamlit run streamlit_app.py
```

Validacao rapida:

```bash
python -m pytest -q -o addopts='' tests/integration/test_streamlit_app.py tests/integration/test_carteira_plano_nacional.py
python -c "import streamlit_app; print('ok')"
```

Validacao de artefatos:

```bash
python scripts/check_artifacts.py
```

Deploy Streamlit em VPS:

```bash
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
curl -fsS http://127.0.0.1:8501/_stcore/health
```

Recalculo analitico do M1, fora do deploy inicial:

```bash
python base_h3_brasil.py
python hex_enrichment.py --brasil
python fase1_bi_exports.py
```

## Arquivos sensiveis ou pesados

- Nao versionar `.env`, credenciais, planilhas privadas, dados brutos, staging nacional ou outputs temporarios.
- Tratar `data/raw/`, `data/staging/`, `data/ultra/`, `concorrentes/` e planilhas locais como dados externos ao codigo.
- Para VPS, montar `data/outputs/` como volume ou copiar o pacote minimo de Parquets para o servidor.

## Docker/API

O caminho oficial do deploy inicial e `Dockerfile.streamlit` + `docker-compose.prod.yml`, documentado em `docs/deploy_vps_streamlit.md`.
O compose/API legado de PostGIS, FastAPI e Prefect fica arquivado em `fora_primeira_fase/api_postgis/`.

## Pacote de arquivos externos ao git

A equipe deve receber os seguintes arquivos **fora** do repositorio git (via drive, S3 ou transferencia direta):

| arquivo | destino na VPS | obrigatorio |
| --- | --- | --- |
| `hexagonos_brasil_dashboard.parquet` | `data/outputs/` | sim |
| `oportunidades_expansao_hibrido.parquet` | `data/outputs/` | sim |
| `carteira_expansao_acionavel.parquet` | `data/outputs/` | sim |
| `plano_expansao_curto_prazo.parquet` | `data/outputs/` | sim |
| `.env` (preenchido com valores reais) | raiz do projeto | sim |
| `censo2022_setores_calibrado.parquet` | `data/staging/` | sim |

Apos copiar, validar com `python scripts/check_artifacts.py` antes do build.

## Rollback

Se um deploy com novos Parquets introduzir regressao:

```bash
# 1. Parar o container
docker compose -f docker-compose.prod.yml stop streamlit

# 2. Substituir os Parquets pelo conjunto anterior (manter backup antes de qualquer atualizacao)
cp /backup/data/outputs/*.parquet data/outputs/

# 3. Validar os artefatos
python scripts/check_artifacts.py

# 4. Reiniciar
docker compose -f docker-compose.prod.yml start streamlit

# 5. Confirmar saude
curl -fsS http://127.0.0.1:8501/_stcore/health
```

Recomendacao: manter pelo menos uma versao anterior dos 4 Parquets em `/backup/data/outputs/` antes de qualquer atualizacao de dados.

## Checklist de handoff

- Repo compartilhado com codigo, docs, testes, manifests e arquivos Docker do Streamlit.
- Pacote externo enviado com os 4 Parquets minimos em `data/outputs/` (ver tabela acima).
- `.env` real e credenciais fora do git; usar `.env.example` como referencia.
- Suite rapida executada antes do envio: `tests/integration/test_streamlit_app.py` e `tests/integration/test_carteira_plano_nacional.py`.
- Smoke do dashboard executado localmente ou na VPS.
- API/FastAPI, PostGIS, Prefect, scraping e pipelines nacionais pesados comunicados como fora do deploy inicial.
