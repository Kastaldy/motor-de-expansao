# Resumo Executivo Fase 1

Metricas, ranking e faixas derivados de `data/staging/hexagonos_brasil_oportunidades.parquet`, sem recalculo de score ou alteracao de regras de negocio.
Score oficial de priorizacao executiva do M1 nacional: `score_priorizacao` (replicado em `score_oficial`).
Base estrutural oficial preservada em `hex_score_estrutural`; ajuste executivo auditavel exposto em `ajuste_executivo`.
OSM permanece `nao_aplicado_mvp_nacional` no fechamento oficial da Fase 1 e nao participa do ranking executivo.
Rotulos de municipio enriquecidos apenas para exibicao via lookup oficial do IBGE em `data/ibge/municipios_nomes_ibge.parquet`.

## Indicadores-chave

- total_hexagonos: 1.532.645
- total_viaveis: 383.312
- pct_viaveis: 25.01%
- amostra_mapa_top_30_pct: 459.794 hexagonos

## Top 10 cidades com mais oportunidades viaveis

| uf | cidade | oportunidades_viaveis | score_medio | melhor_rank_brasil |
| --- | --- | --- | --- | --- |
| MS | Corumbá | 12432 | 87.06 | 112281 |
| RO | Porto Velho | 6478 | 92.19 | 74617 |
| MT | Juína | 4991 | 84.05 | 143255 |
| MT | Aripuanã | 4672 | 82.65 | 159569 |
| MT | Cáceres | 4657 | 87.93 | 103715 |
| MT | Paranatinga | 4338 | 74.26 | 253640 |
| MT | Juara | 4160 | 82.12 | 166478 |
| MT | Comodoro | 4126 | 65.87 | 373722 |
| MT | Apiacás | 3729 | 59.07 | 482613 |
| MS | Ribas do Rio Pardo | 3337 | 75.33 | 237181 |

## Top 10 UFs

| uf | total_viaveis | pct_viaveis | score_medio | qtd_prioridade_maxima |
| --- | --- | --- | --- | --- |
| DF | 999 | 100.00 | 100.00 | 999 |
| RJ | 3169 | 40.14 | 73.66 | 4728 |
| MS | 42751 | 61.65 | 69.45 | 37735 |
| SC | 17459 | 86.86 | 68.84 | 8284 |
| RS | 49156 | 80.83 | 68.46 | 28044 |
| SP | 31094 | 65.96 | 68.39 | 20358 |
| MT | 121202 | 73.44 | 66.02 | 61168 |
| ES | 3146 | 38.56 | 65.94 | 2900 |
| PR | 24204 | 60.12 | 63.89 | 14117 |
| RO | 13401 | 29.16 | 62.59 | 14173 |

## Distribuicao por faixa_oportunidade

| faixa_oportunidade | hexagonos | pct_hexagonos |
| --- | --- | --- |
| prioridade_maxima | 307005 | 20.03 |
| alta | 229838 | 15.00 |
| media | 229677 | 14.99 |
| baixa | 230076 | 15.01 |
| descartado | 536049 | 34.98 |

