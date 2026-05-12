# Manifesto de Artefatos de Dados

> Politica: dados brutos, staging e outputs pesados ficam fora do git.
> Entram via volume Docker, S3/GCS ou copia manual documentada aqui.
> Validar presenca com: `python scripts/check_artifacts.py`

## 1. Artefatos criticos do dashboard (`data/outputs/`)

Sem esses 4 arquivos o `streamlit_app.py` nao sobe.

| Arquivo | Tam. aprox | Produtor | Consumidor |
|---------|-----------|----------|------------|
| `hexagonos_brasil_dashboard.parquet` | 47 MB | `fase1_bi_exports.py` | `streamlit_app.py` (mapa principal) |
| `oportunidades_expansao_hibrido.parquet` | 67 MB | `jobs/pipelines/modelo_hibrido_expansao.py` | `streamlit_app.py` (aba Hibrido) |
| `carteira_expansao_acionavel.parquet` | 416 KB | `jobs/pipelines/gerar_carteira_acionavel.py` | `streamlit_app.py` (aba Carteira) |
| `plano_expansao_curto_prazo.parquet` | 53 KB | `jobs/pipelines/gerar_plano_expansao_curto_prazo.py` | `streamlit_app.py` (aba Plano) |

Artefatos executivos complementares (nao bloqueantes):

| Arquivo | Tam. aprox | Notas |
|---------|-----------|-------|
| `hexagonos_mapa_sample.parquet` | 14 MB | amostra para exploracao rapida |
| `monitoramento_expansao_hibrido_base.parquet` | 65 KB | base de monitoramento |
| `carteira_expansao_acionavel.csv` | 2.5 MB | export CSV da carteira |
| `plano_expansao_curto_prazo.csv` | 127 KB | export CSV do plano |
| `top_oportunidades_resumo.csv` | 56 KB | resumo top oportunidades |
| `resumo_por_uf.csv` | 1.2 KB | resumo por UF |

Politica: nao versionar no git (bloqueado por `*.parquet` e `*.csv` no `.gitignore`).

## 2. Artefatos de staging (`data/staging/`)

| Arquivo | Tam. aprox | Produtor | Consumidor |
|---------|-----------|----------|------------|
| `brasil_estrutural.parquet` | 34 MB | `hex_enrichment.py` | `modelo_hibrido_expansao.py`, `fase1_bi_exports.py` |
| `brasil_priorizados.parquet` | 6.9 MB | `hex_enrichment.py` | `fase1_bi_exports.py` |
| `censo2022_setores_calibrado.parquet` | 11 MB | `calibrar_renda_setor_2022.py` | `streamlit_app.py` (aba Censitario — core) |
| `censo2022_setores_calibrado_piloto_expandido.parquet` | 16 MB | `fase_a_piloto_expandido.py` | `streamlit_app.py` (aba Censitario) |
| `censo2022_setores_validado_v2.parquet` | 6.8 MB | `validar_fase_a_censo2022.py` | `streamlit_app.py` (aba Censitario) |
| `censo2022_setores_calibrado_nacional_completo.parquet` | 84 MB | `fase_a_nacional_completo.py` | `modelo_hibrido_expansao.py` |
| `hexagonos_mercado_mapeado.parquet` | 123 MB | `enriquecimento_espacial_hexagonos.py` | `modelo_hibrido_expansao.py` |
| `concorrentes_mapeados.parquet` | 136 KB | `normalizar_concorrentes.py` | `modelo_hibrido_expansao.py` |

Politica: nao versionar no git (bloqueado por `data/staging/` e `*.parquet`).

## 3. Dados brutos (`data/raw/`) — 11 GB

Fonte: IBGE CENSO 2022. Tabelas de setores censitarios + shapefile nacional.
Nao versionar. Baixar em: <https://www.ibge.gov.br/estatisticas/downloads-estatisticas.html>

## 4. Dados sensiveis (`data/ultra/`, `concorrentes/`) — acesso restrito

| Arquivo | Descricao | Encoding |
|---------|-----------|---------|
| `data/ultra/Ultra.csv` | Localizacoes das unidades Ultra (legado) | latin-1, sep=";", 1 linha de metadado antes do header |
| `data/ultra/dados_academias.xlsx` | Dados operacionais das unidades | Excel |
| `concorrentes/unidades_smart_fit.csv` | Unidades Smart Fit geocodificadas | UTF-8 |
| `concorrentes/unidades_bluefit.csv` | Unidades Bluefit geocodificadas | UTF-8 |
| `concorrentes/unidades_panobianco.csv` | Unidades Panobianco geocodificadas | UTF-8 |
| `concorrentes/SkyFit_unidades_geocodificado.csv` | Unidades Sky Fit geocodificadas | UTF-8 |

Politica: nao versionar. Solicitar acesso ao responsavel do projeto.

## 5. Dados geograficos IBGE (`data/ibge/`) — versionados no git

- `municipios_XX.geojson` (27 UFs): geometrias municipais usadas no mapa executivo.
- Fonte publica IBGE, sem dados sensiveis. Tamanho total ~49 MB.
- Versionados pois sao entrada necessaria ao dashboard sem pipeline de geracao local.

## 6. Cache OSM (`data/osm_cache/`) — nao versionar

Arquivos JSON gerados automaticamente por consultas OSM. Regeneraveis.
Bloqueado por `data/osm_cache/` no `.gitignore`.
