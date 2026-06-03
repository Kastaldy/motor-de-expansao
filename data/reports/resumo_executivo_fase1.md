# Resumo Executivo Fase 1

Metricas, ranking e faixas derivados de `data/staging/hexagonos_brasil_oportunidades.parquet`, sem recalculo de score ou alteracao de regras de negocio.
Score oficial de priorizacao executiva do M1 nacional: `score_priorizacao` (replicado em `score_oficial`).
Base estrutural oficial preservada em `hex_score_estrutural`; ajuste executivo auditavel exposto em `ajuste_executivo`.
OSM permanece `nao_aplicado_mvp_nacional` no fechamento oficial da Fase 1 e nao participa do ranking executivo.
Rotulos de municipio enriquecidos apenas para exibicao via lookup oficial do IBGE em `data/ibge/municipios_nomes_ibge.parquet`.

## Indicadores-chave

- total_hexagonos: 1.538.424
- total_viaveis: 363.372
- pct_viaveis: 23.62%
- amostra_mapa_top_30_pct: 461.528 hexagonos

## Top 10 cidades com mais oportunidades viaveis

| uf | cidade | oportunidades_viaveis | score_medio | melhor_rank_brasil |
| --- | --- | --- | --- | --- |
| MS | Corumbá | 12568 | 90.08 | 95890 |
| RO | Porto Velho | 6533 | 96.11 | 45517 |
| MT | Juína | 4991 | 84.96 | 133192 |
| MT | Cáceres | 4729 | 90.21 | 89876 |
| MT | Aripuanã | 4672 | 72.97 | 265363 |
| MT | Paranatinga | 4338 | 69.09 | 322532 |
| MT | Juara | 4160 | 77.94 | 219044 |
| MT | Comodoro | 4142 | 56.83 | 530398 |
| MT | Apiacás | 3729 | 44.27 | 826327 |
| MS | Ribas do Rio Pardo | 3337 | 66.78 | 360615 |

## Top 10 UFs

| uf | total_viaveis | pct_viaveis | score_medio | qtd_prioridade_maxima |
| --- | --- | --- | --- | --- |
| DF | 999 | 100.00 | 100.00 | 999 |
| RJ | 3319 | 40.91 | 74.07 | 5107 |
| MS | 42101 | 60.42 | 64.65 | 30210 |
| ES | 3200 | 38.83 | 63.88 | 2987 |
| SP | 28883 | 61.08 | 62.14 | 18142 |
| RS | 46333 | 75.04 | 61.21 | 25480 |
| RO | 13456 | 29.09 | 59.97 | 14228 |
| PA | 173 | 0.08 | 59.52 | 67149 |
| SC | 16857 | 83.22 | 58.04 | 6146 |
| MT | 113842 | 68.89 | 57.40 | 48552 |

## Distribuicao por faixa_oportunidade

| faixa_oportunidade | hexagonos | pct_hexagonos |
| --- | --- | --- |
| prioridade_maxima | 308285 | 20.04 |
| alta | 230465 | 14.98 |
| media | 230612 | 14.99 |
| baixa | 234909 | 15.27 |
| descartado | 534153 | 34.72 |
| inviavel | 0 | 0.00 |

