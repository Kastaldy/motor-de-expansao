# Resumo Executivo Fase 1

Metricas, ranking e faixas derivados de `data/staging/hexagonos_brasil_oportunidades.parquet`, sem recalculo de score ou alteracao de regras de negocio.
Score oficial de priorizacao executiva do M1 nacional: `score_priorizacao` (replicado em `score_oficial`).
Base estrutural oficial preservada em `hex_score_estrutural`; ajuste executivo auditavel exposto em `ajuste_executivo`.
OSM permanece `nao_aplicado_mvp_nacional` no fechamento oficial da Fase 1 e nao participa do ranking executivo.
Rotulos de municipio enriquecidos apenas para exibicao via lookup oficial do IBGE em `data/ibge/municipios_nomes_ibge.parquet`.

## Indicadores-chave

- total_hexagonos: 1.537.950
- total_viaveis: 363.229
- pct_viaveis: 23.62%
- amostra_mapa_top_30_pct: 461.385 hexagonos

## Top 10 cidades com mais oportunidades viaveis

| uf | cidade | oportunidades_viaveis | score_medio | melhor_rank_brasil |
| --- | --- | --- | --- | --- |
| MS | Corumbá | 12561 | 90.08 | 95818 |
| RO | Porto Velho | 6524 | 96.11 | 45492 |
| MT | Juína | 4991 | 84.96 | 133106 |
| MT | Cáceres | 4723 | 90.22 | 89810 |
| MT | Aripuanã | 4672 | 72.97 | 265258 |
| MT | Paranatinga | 4338 | 69.09 | 322509 |
| MT | Juara | 4160 | 77.94 | 218944 |
| MT | Comodoro | 4138 | 56.83 | 530224 |
| MT | Apiacás | 3729 | 44.28 | 825983 |
| MS | Ribas do Rio Pardo | 3337 | 66.78 | 360497 |

## Top 10 UFs

| uf | total_viaveis | pct_viaveis | score_medio | qtd_prioridade_maxima |
| --- | --- | --- | --- | --- |
| DF | 999 | 100.00 | 100.00 | 999 |
| RJ | 3300 | 40.80 | 74.03 | 5086 |
| MS | 42093 | 60.43 | 64.66 | 30202 |
| ES | 3198 | 38.82 | 63.87 | 2985 |
| SP | 28871 | 61.07 | 62.13 | 18130 |
| RS | 46280 | 75.04 | 61.21 | 25443 |
| RO | 13447 | 29.09 | 59.97 | 14219 |
| PA | 173 | 0.08 | 59.53 | 67147 |
| SC | 16841 | 83.21 | 58.04 | 6142 |
| MT | 113832 | 68.89 | 57.40 | 48546 |

## Distribuicao por faixa_oportunidade

| faixa_oportunidade | hexagonos | pct_hexagonos |
| --- | --- | --- |
| prioridade_maxima | 308169 | 20.04 |
| alta | 230403 | 14.98 |
| media | 230570 | 14.99 |
| baixa | 234837 | 15.27 |
| descartado | 533971 | 34.72 |
| inviavel | 0 | 0.00 |

