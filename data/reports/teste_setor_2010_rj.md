# Teste Paralelo - Setor Censitario IBGE 2010

## Escopo
- cidades testadas: 3304557/NA
- resolucao H3: 7
- base oficial preservada: `data\staging\brasil_estrutural.parquet`
- geometria de setor: `data\staging\teste_setor_2010\rj_setores.geojson`
- atributos censitarios: `data\staging\teste_setor_2010\basico_rj_semantico.csv`

## Variaveis 2010 usadas
- codigo de setor: `cod_setor`
- codigo de municipio: `derivado_do_cod_setor`
- renda: `renda_media`
- populacao target: `nao_encontrada`
- populacao total fallback: `pop_total`
- colunas descartadas na leitura: `cod_municipio`, `renda_setor_2010`, `pop_total_setor_2010`, `pop_target_setor_2010`, `pop_setor_2010`, `fonte_renda`, `fonte_pop`, `pop_setor_2010_fallback`

## Validacao objetiva
- hexagonos enriquecidos com setor 2010: 185 de 189
- cobertura espacial: 97.88%
- houve ganho de diferenciacao intraurbana? sim
- cidades com aumento de valores distintos no score: 3304557
- o topo do ranking ficou mais plausivel? leitura positiva
- custo computacional aceitavel? leitura preliminar: sim para escopo reduzido (189 hexagonos)
- vale evoluir para modulo oficial futuro? somente se a cobertura espacial e a separacao intraurbana se confirmarem com mais cidades

## Metricas por cidade
| cidade | hex_total | hex_com_setor | cobertura_pct | score_oficial_distintos | score_setor_distintos | score_oficial_std | score_setor_std | score_oficial_p95_p05 | score_setor_p95_p05 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3304557 | 185 | 185 | 100.0 | 1 | 146 | 0.0 | 22.89 | 0.0 | 74.31 |

## Distribuicao de score
- score oficial atual: {'count': 189, 'min': 99.81, 'max': 99.81, 'media': 99.81, 'mediana': 99.81, 'std': 0.0, 'p90': 99.81, 'p95': 99.81}
- score setor 2010: {'count': 185, 'min': 2.39, 'max': 98.8, 'media': 50.0, 'mediana': 53.48, 'std': 22.89, 'p90': 81.86, 'p95': 85.39}

## Top 10 por cidade - modelo atual
| cidade | hex_id | hex_score_estrutural |
| --- | --- | --- |
| 3304557 | 87a8a0212ffffff | 99.81 |
| 3304557 | 87a8a0213ffffff | 99.81 |
| 3304557 | 87a8a0218ffffff | 99.81 |
| 3304557 | 87a8a0219ffffff | 99.81 |
| 3304557 | 87a8a021affffff | 99.81 |
| 3304557 | 87a8a021bffffff | 99.81 |
| 3304557 | 87a8a021effffff | 99.81 |
| 3304557 | 87a8a0280ffffff | 99.81 |
| 3304557 | 87a8a0281ffffff | 99.81 |
| 3304557 | 87a8a0282ffffff | 99.81 |

## Top 10 por cidade - modelo censitario
| cidade | hex_id | hex_score_setor_2010 | diferenca_score |
| --- | --- | --- | --- |
| 3304557 | 87a8a0755ffffff | 98.8 | -1.01 |
| 3304557 | 87a8a0745ffffff | 96.41 | -3.4 |
| 3304557 | 87a8a0626ffffff | 93.91 | -5.9 |
| 3304557 | 87a8a078dffffff | 93.8 | -6.01 |
| 3304557 | 87a8a0756ffffff | 91.41 | -8.4 |
| 3304557 | 87a8a0634ffffff | 90.0 | -9.81 |
| 3304557 | 87a8a0624ffffff | 89.89 | -9.92 |
| 3304557 | 87a8a0620ffffff | 86.63 | -13.18 |
| 3304557 | 87a8a071bffffff | 86.41 | -13.4 |
| 3304557 | 87a8a0636ffffff | 85.65 | -14.16 |

## Observacoes
- `hex_score_estrutural` oficial nao foi alterado.
- hex sem setor permaneceram como `sem_match_setor`; nao houve preenchimento silencioso com zero.
- o experimento usa percentis apenas no subconjunto testado, entao a leitura principal aqui e de separacao espacial intraurbana, nao de ranking nacional.
