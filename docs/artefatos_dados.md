# Manifesto de Artefatos de Dados

> Politica: dados brutos, staging e outputs pesados ficam fora do git.
> Entram via volume Docker, S3/GCS ou copia manual documentada aqui.
> Validar presenca com: `python scripts/check_artifacts.py`
> Consumidor "piloto web" = backend `web/server/app.py` (app de producao desde a DEC-022, 2026-08-03).

## 1. Artefatos criticos do app (`data/outputs/`)

Fonte principal do piloto web e o dataset enriquecido particionado; os 4 parquets
seguintes sao os INSUMOS do merge que o materializa (e continuam artefatos do M1 /
camadas paralelas por direito proprio).

| Arquivo | Tam. aprox | Produtor | Consumidor |
|---------|-----------|----------|------------|
| `hexagonos_dashboard_enriquecido/uf=XX/` | 257 MB | `fase1_bi_exports.py` (merge offline de M1 + hibrido + censo) | piloto web (Mapa Territorial, carga lazy por UF — obrigatorio) |
| `setores_censitarios_2022_geo/uf=XX/cod_municipio=NNNNNNN/` | 1.2 GB | `materializar_setores_censitarios_geo` | Relatorio Pontual Censitario (piloto web, API, bot) |
| `hexagonos_brasil_dashboard.parquet` | 47 MB | `fase1_bi_exports.py` | insumo do merge do enriquecido (base oficial M1) |
| `oportunidades_expansao_hibrido.parquet` | 109 MB | `jobs/pipelines/modelo_hibrido_expansao.py` | insumo do merge do enriquecido (hibrido/censitario/residual) |
| `carteira_expansao_acionavel.parquet` | 600 KB | `jobs/pipelines/gerar_carteira_acionavel.py` | sem superficie de exibicao desde a DEC-022 (artefato oficial da camada de mercado; pipeline e testes seguem) |
| `plano_expansao_curto_prazo.parquet` | 80 KB | `jobs/pipelines/gerar_plano_expansao_curto_prazo.py` | idem — perdeu superficie, continua produzido e valido |
| `staging/crescimento_municipal.parquet` | 2 MB | `data/reports/crescimento/` (10 scripts, ordem no README) | piloto web, passo 4 do funil — OPCIONAL, ausente degrada so o passo |
| `staging/crescimento_hex.parquet` | 370 KB | idem | piloto web, passo 4 — cor do mapa por taxa de crescimento do hexagono |

Artefatos executivos complementares (nao bloqueantes):

| Arquivo | Tam. aprox | Notas |
|---------|-----------|-------|
| `hexagonos_mapa_sample.parquet` | 14 MB | amostra para exploracao rapida (legado; nenhum builder atual usa) |
| `plano_expansao_dominio.parquet` | 1.4 MB | Expansao de Dominio (sem tela desde a DEC-020; analise coberta pela Fase 4 do Mapa) |
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
| `censo2022_setores_calibrado.parquet` | 11 MB | `calibrar_renda_setor_2022.py` | `fase1_bi_exports.py` (traco censitario do merge enriquecido) |
| `censo2022_setores_calibrado_piloto_expandido.parquet` | 16 MB | `fase_a_piloto_expandido.py` | idem (cobertura expandida do traco censitario) |
| `censo2022_setores_validado_v2.parquet` | 6.8 MB | `validar_fase_a_censo2022.py` | validacao da cadeia censitaria |
| `censo2022_setores_calibrado_nacional_completo.parquet` | 84 MB | `fase_a_nacional_completo.py` | `modelo_hibrido_expansao.py` |
| `hexagonos_mercado_mapeado.parquet` | 204 MB | `calcular_colunas_mercado.py` | `modelo_hibrido_expansao.py`; piloto web (residual do ponto no Relatorio Pontual) |
| `concorrentes_mapeados.parquet` | 250 KB | `normalizar_concorrentes.py` | piloto web (pins), API/PDFs, `modelo_hibrido_expansao.py` |
| `unidades_ultra_performance_hex.parquet` | 53 KB | `calcular_penetracao_ultra_hex.py` | piloto web (pins Ultra; fallback da faixa de alunos) |
| `growth_api_historico.parquet` | 3.4 MB | `scripts/ingerir_growth_api.py` (ingestao semanal, DEC-013) | piloto web (Visao Executiva — a tela responde 404 sem ele) |
| `base_calibracao_maduras.parquet` | 21 KB | `scripts/consolidar_base_calibracao.py` | piloto web (semente p50 da demanda na Viabilidade) |
| `uplift_renda_domiciliar_municipio.parquet`, `uplift_composicao_setor.parquet`, `fator_temporal_renda.json` | — | pipeline de renda domiciliar | piloto web + PDFs (renda media domiciliar municipal; sem eles, fallback nacional ~4,55x) |

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
| `concorrentes/logo_<rede>.png` | Logos das bandeiras dos pins (piloto web e PDFs; fallback sigla+cor sem elas) | PNG |

Os CSVs sao a FONTE do pipeline de concorrentes: `normalizar_concorrentes.py` os
consolida em `data/staging/concorrentes_mapeados.parquet`, que e o que o piloto
web e os PDFs consomem. Medir as duas pontas ao auditar cobertura.

Politica: nao versionar. Solicitar acesso ao responsavel do projeto.

## 5. Dados geograficos IBGE (`data/ibge/`) — versionados no git

- `municipios_XX.geojson` (27 UFs): geometrias municipais usadas na resolucao de
  municipio e nos relatorios (piloto web, API e bot).
- Fonte publica IBGE, sem dados sensiveis. Tamanho total ~49 MB.
- Versionados pois sao entrada necessaria ao app sem pipeline de geracao local.

## 6. Cache OSM (`data/osm_cache/`) — nao versionar

Arquivos JSON gerados automaticamente por consultas OSM. Regeneraveis.
Bloqueado por `data/osm_cache/` no `.gitignore`.
