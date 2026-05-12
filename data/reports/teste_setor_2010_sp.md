# Teste Paralelo - Setor Censitario IBGE 2010

## Escopo
- cidades testadas: 3550308/NA, 3509502/NA
- resolucao H3: 7
- base oficial preservada: `data\staging\brasil_estrutural.parquet`
- geometria de setor: `data\staging\teste_setor_2010\sp_setores.geojson`
- atributos censitarios: `data\staging\teste_setor_2010\basico_sp_semantico.csv`

## Variaveis 2010 usadas
- codigo de setor: `cod_setor`
- codigo de municipio: `derivado_do_cod_setor`
- renda: `renda_media`
- populacao target: `nao_encontrada`
- populacao total fallback: `pop_total`
- colunas descartadas na leitura: `cod_municipio`, `renda_setor_2010`, `pop_total_setor_2010`, `pop_target_setor_2010`, `pop_setor_2010`, `fonte_renda`, `fonte_pop`, `pop_setor_2010_fallback`

## Validacao objetiva
- hexagonos enriquecidos com setor 2010: 442 de 445
- cobertura espacial: 99.33%
- houve ganho de diferenciacao intraurbana? sim
- cidades com aumento de valores distintos no score: 3509502, 3550308
- o topo do ranking ficou mais plausivel? leitura positiva
- custo computacional aceitavel? leitura preliminar: sim para escopo reduzido (445 hexagonos)
- vale evoluir para modulo oficial futuro? somente se a cobertura espacial e a separacao intraurbana se confirmarem com mais cidades

## Metricas por cidade
| cidade | hex_total | hex_com_setor | cobertura_pct | score_oficial_distintos | score_setor_distintos | score_oficial_std | score_setor_std | score_oficial_p95_p05 | score_setor_p95_p05 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3509502 | 149 | 149 | 100.0 | 1 | 92 | 0.0 | 17.17 | 0.0 | 54.61 |
| 3550308 | 293 | 293 | 100.0 | 1 | 246 | 0.0 | 22.81 | 0.0 | 69.06 |

## Distribuicao de score
- score oficial atual: {'count': 445, 'min': 99.76, 'max': 99.89, 'media': 99.85, 'mediana': 99.89, 'std': 0.06, 'p90': 99.89, 'p95': 99.89}
- score setor 2010: {'count': 442, 'min': 0.91, 'max': 98.41, 'media': 50.0, 'mediana': 52.92, 'std': 21.27, 'p90': 76.04, 'p95': 81.68}

## Top 10 por cidade - modelo atual
| cidade | hex_id | hex_score_estrutural |
| --- | --- | --- |
| 3509502 | 87a811413ffffff | 99.76 |
| 3509502 | 87a811418ffffff | 99.76 |
| 3509502 | 87a811419ffffff | 99.76 |
| 3509502 | 87a81141affffff | 99.76 |
| 3509502 | 87a81141bffffff | 99.76 |
| 3509502 | 87a811481ffffff | 99.76 |
| 3509502 | 87a811483ffffff | 99.76 |
| 3509502 | 87a811484ffffff | 99.76 |
| 3509502 | 87a811485ffffff | 99.76 |
| 3509502 | 87a811488ffffff | 99.76 |
| 3550308 | 87a810000ffffff | 99.89 |
| 3550308 | 87a810001ffffff | 99.89 |
| 3550308 | 87a810005ffffff | 99.89 |
| 3550308 | 87a810008ffffff | 99.89 |
| 3550308 | 87a810009ffffff | 99.89 |
| 3550308 | 87a81000affffff | 99.89 |
| 3550308 | 87a81000bffffff | 99.89 |
| 3550308 | 87a81000cffffff | 99.89 |
| 3550308 | 87a81000dffffff | 99.89 |
| 3550308 | 87a81000effffff | 99.89 |

## Top 10 por cidade - modelo censitario
| cidade | hex_id | hex_score_setor_2010 | diferenca_score |
| --- | --- | --- | --- |
| 3509502 | 87a813b0affffff | 98.41 | -1.35 |
| 3509502 | 87a813b16ffffff | 95.46 | -4.3 |
| 3509502 | 87a813b00ffffff | 93.65 | -6.11 |
| 3509502 | 87a813849ffffff | 89.71 | -10.05 |
| 3509502 | 87a813b01ffffff | 86.98 | -12.78 |
| 3509502 | 87a813b1cffffff | 86.39 | -13.37 |
| 3509502 | 87a813b31ffffff | 85.17 | -14.59 |
| 3509502 | 87a813b30ffffff | 84.67 | -15.09 |
| 3509502 | 87a813b04ffffff | 83.36 | -16.4 |
| 3509502 | 87a813b35ffffff | 81.68 | -18.08 |
| 3550308 | 87a8100f1ffffff | 91.07 | -8.82 |
| 3550308 | 87a81009bffffff | 86.21 | -13.68 |
| 3550308 | 87a8100deffffff | 85.12 | -14.77 |
| 3550308 | 87a810721ffffff | 84.99 | -14.9 |
| 3550308 | 87a81002dffffff | 84.85 | -15.04 |
| 3550308 | 87a8100e0ffffff | 84.04 | -15.85 |
| 3550308 | 87a8100eeffffff | 83.99 | -15.9 |
| 3550308 | 87a810052ffffff | 83.31 | -16.58 |
| 3550308 | 87a810019ffffff | 83.27 | -16.62 |
| 3550308 | 87a810775ffffff | 83.08 | -16.81 |

## Observacoes
- `hex_score_estrutural` oficial nao foi alterado.
- hex sem setor permaneceram como `sem_match_setor`; nao houve preenchimento silencioso com zero.
- o experimento usa percentis apenas no subconjunto testado, entao a leitura principal aqui e de separacao espacial intraurbana, nao de ranking nacional.
