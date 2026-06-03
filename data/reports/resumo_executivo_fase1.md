# Resumo Executivo Fase 1

Metricas, ranking e faixas derivados de `data/staging/hexagonos_brasil_oportunidades.parquet`, sem recalculo de score ou alteracao de regras de negocio.
Score oficial de priorizacao executiva do M1 nacional: `score_priorizacao` (replicado em `score_oficial`).
Base estrutural oficial preservada em `hex_score_estrutural`; ajuste executivo auditavel exposto em `ajuste_executivo`.
OSM permanece `nao_aplicado_mvp_nacional` no fechamento oficial da Fase 1 e nao participa do ranking executivo.
Rotulos de municipio enriquecidos apenas para exibicao via lookup oficial do IBGE em `data/ibge/municipios_nomes_ibge.parquet`.

## Indicadores-chave

- total_hexagonos: 1.542.531
- total_viaveis: 364.523
- pct_viaveis: 23.63%
- amostra_mapa_top_30_pct: 462.760 hexagonos

## Top 10 cidades com mais oportunidades viaveis

| uf | cidade | oportunidades_viaveis | score_medio | melhor_rank_brasil |
| --- | --- | --- | --- | --- |
| MS | Corumbá | 12666 | 90.07 | 96419 |
| RO | Porto Velho | 6567 | 96.10 | 45739 |
| MT | Juína | 4991 | 84.95 | 133922 |
| MT | Cáceres | 4769 | 90.20 | 90365 |
| MT | Aripuanã | 4672 | 72.96 | 266330 |
| MT | Paranatinga | 4338 | 69.08 | 323640 |
| MT | Juara | 4160 | 77.93 | 219917 |
| MT | Comodoro | 4149 | 56.83 | 531893 |
| MT | Apiacás | 3729 | 44.26 | 828705 |
| MS | Ribas do Rio Pardo | 3337 | 66.77 | 361744 |

## Top 10 UFs

| uf | total_viaveis | pct_viaveis | score_medio | qtd_prioridade_maxima |
| --- | --- | --- | --- | --- |
| DF | 999 | 100.00 | 100.00 | 999 |
| RJ | 3447 | 41.60 | 74.29 | 5259 |
| MS | 42214 | 60.37 | 64.63 | 30316 |
| ES | 3258 | 39.14 | 64.06 | 3047 |
| SP | 28954 | 61.10 | 62.18 | 18221 |
| RS | 46771 | 74.94 | 61.25 | 25821 |
| RO | 13490 | 29.04 | 59.94 | 14262 |
| PA | 173 | 0.08 | 59.50 | 67156 |
| SC | 16975 | 83.32 | 58.14 | 6216 |
| MT | 113889 | 68.86 | 57.39 | 48592 |

## Distribuicao por faixa_oportunidade

| faixa_oportunidade | hexagonos | pct_hexagonos |
| --- | --- | --- |
| prioridade_maxima | 309382 | 20.06 |
| alta | 230673 | 14.95 |
| media | 231376 | 15.00 |
| baixa | 235622 | 15.28 |
| descartado | 535478 | 34.71 |
| inviavel | 0 | 0.00 |

