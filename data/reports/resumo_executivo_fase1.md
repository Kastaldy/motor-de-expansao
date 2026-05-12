# Resumo Executivo Fase 1

Metricas, ranking e faixas derivados de `data/staging/hexagonos_brasil_oportunidades.parquet`, sem recalculo de score ou alteracao de regras de negocio.
Score oficial de priorizacao executiva do M1 nacional: `score_priorizacao` (replicado em `score_oficial`).
Base estrutural oficial preservada em `hex_score_estrutural`; ajuste executivo auditavel exposto em `ajuste_executivo`.
OSM permanece `nao_aplicado_mvp_nacional` no fechamento oficial da Fase 1 e nao participa do ranking executivo.
Rotulos de municipio enriquecidos apenas para exibicao via lookup oficial do IBGE em `data/ibge/municipios_nomes_ibge.parquet`.

## Indicadores-chave

- total_hexagonos: 1.532.645
- total_viaveis: 359.247
- pct_viaveis: 23.44%
- amostra_mapa_top_30_pct: 459.794 hexagonos

## Top 10 cidades com mais oportunidades viaveis

| uf | cidade | oportunidades_viaveis | score_medio | melhor_rank_brasil |
| --- | --- | --- | --- | --- |
| MS | Corumbá | 12432 | 89.74 | 96676 |
| RO | Porto Velho | 6478 | 96.16 | 43731 |
| MT | Juína | 4991 | 81.65 | 182741 |
| MT | Aripuanã | 4672 | 74.98 | 243251 |
| MT | Cáceres | 4657 | 89.97 | 92019 |
| MT | Paranatinga | 4338 | 69.85 | 311725 |
| MT | Juara | 4160 | 78.23 | 218190 |
| MT | Comodoro | 4126 | 58.83 | 494971 |
| MT | Apiacás | 3729 | 44.34 | 817216 |
| MS | Ribas do Rio Pardo | 3337 | 69.01 | 326956 |

## Top 10 UFs

| uf | total_viaveis | pct_viaveis | score_medio | qtd_prioridade_maxima |
| --- | --- | --- | --- | --- |
| DF | 999 | 100.00 | 100.00 | 999 |
| RJ | 3169 | 40.14 | 72.81 | 4655 |
| MS | 41950 | 60.50 | 64.75 | 31137 |
| ES | 3146 | 38.56 | 63.14 | 2961 |
| SP | 28455 | 60.36 | 61.63 | 17796 |
| RO | 13401 | 29.16 | 60.21 | 13784 |
| PA | 173 | 0.08 | 59.90 | 67139 |
| RS | 44884 | 73.81 | 59.69 | 24494 |
| MT | 113751 | 68.93 | 57.97 | 49618 |
| SC | 16370 | 81.44 | 57.87 | 6217 |

## Distribuicao por faixa_oportunidade

| faixa_oportunidade | hexagonos | pct_hexagonos |
| --- | --- | --- |
| prioridade_maxima | 306608 | 20.01 |
| alta | 230767 | 15.06 |
| media | 230619 | 15.05 |
| baixa | 232569 | 15.17 |
| descartado | 532082 | 34.72 |

