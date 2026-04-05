# Enriquecimento H3 Brasil

## Respostas objetivas

- pipeline nacional executou sem erros? Nao.
- score esta variando de forma consistente? Nao avaliado em escala nacional, porque a coleta OSM nacional nao concluiu.
- existem anomalias por UF? Sim, a coleta OSM por UF densa segue sujeita a timeout/504/429 no Overpass.
- dados estao prontos para criacao de ranking nacional? Nao.

## O que ficou pronto

- Leitura nacional em lote por UF implementada em `hex_enrichment.py`.
- Enriquecimento demografico municipal implementado via malha municipal IBGE + cache nacional SIDRA em `data/ibge/demografia_municipios_2022.parquet`.
- Fonte de renda mantida em `SIDRA t.10295 v.13431`.
- Proxy `pop_18_45` corrigido em `SIDRA 9514` com ponderacao:
  - `15-19`: 0.4
  - `20-44`: 1.0
  - `45-49`: 0.2
- OSM batch reforcado com:
  - retry com backoff
  - fallback entre mirrors
  - cache local por bbox em `data/osm_cache/`
  - split adaptativo de bbox
  - erro bloqueante quando nenhuma fonte responde

## Evidencias de execucao

- Smoke IBGE/DF:
  - 50/50 hexagonos com `renda_per_capita > 0`
  - 50/50 hexagonos com proxy populacional preenchido
  - `fonte_demografica = ibge_sidra_municipio_2022+ibge_censo2022_t10295+ibge_censo2022_t9514_18_45_proxy`
- OSM:
  - bbox pequeno no DF respondeu
  - bboxes densos e execucao de UF inteira continuam intermitentes, com combinacao de `504 Gateway Timeout`, `429 Too Many Requests`, `ReadTimeout` e `SSLEOFError`
  - por regra do projeto, a pipeline aborta em vez de preencher `n_academias_osm = 0` silenciosamente

## Artefatos gerados nesta tarefa

- `data/ibge/demografia_municipios_2022.parquet`
- `data/ibge/municipios_DF.geojson`
- `data/osm_cache/*.json`

## Bloqueio atual

- A coleta OSM nacional nao concluiu no ambiente atual dentro da janela operacional desta tarefa.
- O output final `data/staging/brasil_enriquecido.parquet` nao foi materializado, para evitar publicar base nacional incompleta ou com concorrencia zerada artificialmente.
