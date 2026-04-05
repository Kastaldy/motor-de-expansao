# Resumo Executivo Fase 1

Metricas, ranking e faixas derivados de `data/staging/hexagonos_brasil_oportunidades.parquet`, sem recalculo de score ou alteracao de regras de negocio.
Rotulos de municipio enriquecidos apenas para exibicao via lookup oficial do IBGE em `data/ibge/municipios_nomes_ibge.parquet`.

## Indicadores-chave

- total_hexagonos: 1.532.645
- total_viaveis: 383.312
- pct_viaveis: 25.01%
- amostra_mapa_top_30_pct: 459.794 hexagonos

## Top 10 cidades com mais oportunidades viaveis

| uf | cidade | oportunidades_viaveis | score_medio | melhor_rank_brasil |
| --- | --- | --- | --- | --- |
| MS | Corumbá | 12432 | 16.97 | 341116 |
| RO | Porto Velho | 6478 | 18.82 | 229533 |
| MT | Juína | 4991 | 19.20 | 194716 |
| MT | Aripuanã | 4672 | 23.00 | 64330 |
| MT | Cáceres | 4657 | 17.33 | 317528 |
| MT | Paranatinga | 4338 | 17.61 | 301710 |
| MT | Juara | 4160 | 19.28 | 185501 |
| MT | Comodoro | 4126 | 16.87 | 356678 |
| MT | Apiacás | 3729 | 19.61 | 166934 |
| MS | Ribas do Rio Pardo | 3337 | 18.87 | 221332 |

## Top 10 UFs

| uf | total_viaveis | pct_viaveis | score_medio | qtd_prioridade_maxima |
| --- | --- | --- | --- | --- |
| DF | 999 | 100.00 | 50.29 | 999 |
| SC | 17459 | 86.86 | 22.78 | 16824 |
| RS | 49156 | 80.83 | 19.86 | 42830 |
| SP | 31094 | 65.96 | 18.84 | 23745 |
| MT | 121202 | 73.44 | 18.35 | 97414 |
| PR | 24204 | 60.12 | 17.94 | 19431 |
| MS | 42751 | 61.65 | 17.19 | 27098 |
| RJ | 3169 | 40.14 | 17.18 | 2928 |
| GO | 35878 | 59.84 | 16.94 | 29842 |
| ES | 3146 | 38.56 | 15.05 | 1881 |

## Distribuicao por faixa_oportunidade

| faixa_oportunidade | hexagonos | pct_hexagonos |
| --- | --- | --- |
| prioridade_maxima | 306645 | 20.01 |
| alta | 229862 | 15.00 |
| media | 229942 | 15.00 |
| baixa | 230463 | 15.04 |
| descartado | 535733 | 34.95 |

