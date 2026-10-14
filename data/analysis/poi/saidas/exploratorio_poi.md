# Exploratório pós-desfecho do teste de POI (não decide; p sem correção)

## E8 Limiar do teste em R$

- R² parcial 0.10 (poder 0,38–0,55) = 13% de faturamento por 1 desvio-padrão de F (resíduo base σ = 0.372 em log)
- R² parcial 0.20 (poder 0,79–0,89) = 20% de faturamento por 1 desvio-padrão de F (resíduo base σ = 0.372 em log)

## E1 Isócrona a pé degenerada (< 0,5 km²): ['lago-sul-df'] (áreas [0.16])


## E2 Âncoras vindas de relação OSM: 78 de 2869

- S1: unidades cuja F3 muda com as relações: ['praia-grande-sp'] (F3 run2 = [1.0])

## E4 S2 com efeito fixo de metrô (metrôs com >= 5 unidades): 12 metrôs, N = 418; maior = 182 unidades

- R² LOO base com efeito fixo de metrô = +0.175 (sem = +0.001)

## E7 S2: mediana da fração exata de F2 por metrô: {'1': 0.0, '42': 0.0, '25': 0.01, '13': 0.12, '20': 0.23, '27': 0.25, '18': 0.26, '11': 0.31} ... metrôs com < 0,2: ['1', '13', '25', '42']


## E9 Crosswalk Smart Fit: Spearman(log alunos 2025 mediana, log alunos crosswalk jan/26) = +0.946 (N = 454)

## Testes exploratórios

| teste                                                      |   N |     dR2 |   p_perm |   coef_padr |
|:-----------------------------------------------------------|----:|--------:|---------:|------------:|
| E1 S1 sem pe degenerada | F1                               |  52 | -0.0303 |    0.59  |       0.055 |
| E1 S1 sem DF | F1                                          |  34 | -0.0351 |    0.334 |       0.176 |
| E1 S1 sem pe degenerada | F3                               |  52 | -0.03   |    0.764 |       0.048 |
| E1 S1 sem DF | F3                                          |  34 | -0.0287 |    0.274 |       0.152 |
| E3 S1 idade>=12 | F3 + dummy DF                            |  36 |  0.0458 |    0.048 |       0.26  |
| E3 S1 idade>=12 | F3 GroupKFold UF                         |  36 |  0.0148 |    0.284 |       0.272 |
| E3 S1 idade>=12 sem DF | F3                                |  21 |  0.0456 |    0.132 |       0.293 |
| E4 S2 dentro do metrô | F1                                 | 418 |  0.0097 |    0.008 |      -0.136 |
| E4 S2 dentro do metrô | F2                                 | 418 |  0.0113 |    0.008 |      -0.139 |
| E4 S2 dentro do metrô | F3                                 | 418 | -0.0037 |    0.7   |      -0.018 |
| E4 S2 dentro do metrô | F5                                 | 418 | -0.0043 |    0.934 |       0.012 |
| E4b S2 dentro do metrô | log pop a pé sozinha              | 418 |  0.0098 |    0.016 |       0.137 |
| E4b S2 dentro do metrô | log n F1 com log pop a pé na base | 418 |  0.0024 |    0.078 |      -0.1   |
| E5 S1 | F3 ou em_shopping                                  |  53 | -0.0183 |    0.368 |       0.093 |
| E5 S1 | em_shopping                                        |  53 | -0.0434 |    0.87  |       0.031 |
| E5 S1 | F3 com em_shopping na base                         |  53 | -0.0305 |    0.74  |       0.069 |
| E5 S2 | F3 ou em_shopping                                  | 454 | -0.0035 |    0.45  |       0.018 |
| E5 S2 | em_shopping                                        | 454 |  0.0114 |    0.086 |       0.11  |
| E5 S2 | F3 com em_shopping na base                         | 454 | -0.003  |    0.46  |       0.018 |
| E6 S1 | log n F1 com log pop a pé na base                  |  53 | -0.0335 |    0.786 |       0.069 |
| E6 S1 | log n F2 com log pop a pé na base                  |  53 | -0.028  |    0.702 |       0.067 |
| E6 S2 | log n F1 com log pop a pé na base                  | 454 | -0.0311 |    0.982 |      -0.036 |
| E6 S2 | log n F2 com log pop a pé na base                  | 454 | -0.0235 |    0.976 |      -0.063 |
| E7 S2 sem metrôs de geocodificação ruim | F1               | 406 | -0.0395 |    0.96  |      -0.044 |
| E7 S2 sem metrôs de geocodificação ruim | F3               | 406 | -0.0068 |    0.484 |       0.025 |
| E7 S2 sem metrôs de geocodificação ruim | F5               | 406 | -0.0087 |    0.01  |      -0.173 |

26 testes sem correção: com α = 0,05, espera-se ~1.3 'p < 0,05' só por acaso.