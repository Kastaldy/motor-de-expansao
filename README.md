# Motor de Expansao Ultra Academia

Base territorial do MVP nacional do `motor-de-expansao`.

O contrato canonico do projeto esta em `CLAUDE.md`; detalhes do ciclo ativo ficam em `PRD.md`.
O objetivo atual e deixar o repositorio compartilhavel com a equipe e subir o dashboard Streamlit em VPS com Parquets locais, sem API ao vivo, sem PostGIS obrigatorio e sem recalculo do M1 no deploy inicial.

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

Camadas de apoio em `data/staging/` podem enriquecer rastreabilidade censitaria, mas dados brutos e staging nacionais grandes devem ser tratados como artefatos externos ao codigo.

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
- `docs/modelo_mercado_hexagonos.md`: contrato tecnico da camada de mercado.
- `fora_primeira_fase/README.md`: inventario dos codigos, docs e dados separados do deploy inicial.

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
