# Resumo Executivo Fase 1

Metricas, ranking e faixas derivados de `data/staging/hexagonos_brasil_oportunidades.parquet`, sem recalculo de score ou alteracao de regras de negocio.
Score oficial de priorizacao executiva do M1 nacional: `score_priorizacao` (replicado em `score_oficial`).
Base estrutural oficial preservada em `hex_score_estrutural`; ajuste executivo auditavel exposto em `ajuste_executivo`.
OSM permanece `nao_aplicado_mvp_nacional` no fechamento oficial da Fase 1 e nao participa do ranking executivo.
Rotulos de municipio enriquecidos apenas para exibicao via lookup oficial do IBGE em `data/ibge/municipios_nomes_ibge.parquet`.

## Indicadores-chave

- total_hexagonos: 1.532.645
- total_viaveis: 361.835
- pct_viaveis: 23.61%
- amostra_mapa_top_30_pct: 459.794 hexagonos

## Top 10 cidades com mais oportunidades viaveis

| uf | cidade | oportunidades_viaveis | score_medio | melhor_rank_brasil |
| --- | --- | --- | --- | --- |
| MS | Corumbá | 12432 | 90.09 | 95569 |
| RO | Porto Velho | 6478 | 96.11 | 45264 |
| MT | Juína | 4991 | 84.97 | 132184 |
| MT | Aripuanã | 4672 | 72.98 | 263744 |
| MT | Cáceres | 4657 | 90.23 | 89627 |
| MT | Paranatinga | 4338 | 69.10 | 321126 |
| MT | Juara | 4160 | 77.95 | 217881 |
| MT | Comodoro | 4126 | 56.83 | 528227 |
| MT | Apiacás | 3729 | 44.29 | 822992 |
| MS | Ribas do Rio Pardo | 3337 | 66.78 | 359090 |

## Top 10 UFs

| uf | total_viaveis | pct_viaveis | score_medio | qtd_prioridade_maxima |
| --- | --- | --- | --- | --- |
| DF | 999 | 100.00 | 100.00 | 999 |
| RJ | 3169 | 40.14 | 73.77 | 4928 |
| MS | 41950 | 60.50 | 64.68 | 30062 |
| ES | 3146 | 38.56 | 63.89 | 2927 |
| SP | 28781 | 61.06 | 62.09 | 18032 |
| RS | 45723 | 75.19 | 61.15 | 25000 |
| RO | 13401 | 29.16 | 60.01 | 14173 |
| PA | 173 | 0.08 | 59.55 | 67139 |
| SC | 16702 | 83.09 | 57.93 | 6060 |
| MT | 113751 | 68.93 | 57.40 | 48480 |

## Distribuicao por faixa_oportunidade

| faixa_oportunidade | hexagonos | pct_hexagonos |
| --- | --- | --- |
| prioridade_maxima | 306797 | 20.02 |
| alta | 229787 | 14.99 |
| media | 230192 | 15.02 |
| baixa | 233709 | 15.25 |
| descartado | 532160 | 34.72 |
| inviavel | 0 | 0.00 |

