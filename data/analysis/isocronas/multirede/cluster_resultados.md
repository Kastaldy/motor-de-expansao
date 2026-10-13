Ficha: 273 unidades {'skyfit': 182, 'ultra': 53, 'engenharia_do_corpo': 38} | vagas casadas: Ultra 53/53, EdC 38/38 | tipo de imóvel EdC 38/38

## Nível 1 — perfil de região

N = 271 unidades (sem dado completo: 2). Variáveis: log_pop_1km, log_razao_alcance, log_km_rua_5min, fracao_pe, log_renda_5min, log_pressao_oferta.

|   k |   silhueta |   estabilidade_ARI_mediana |   ARI_p10 |
|----:|-----------:|---------------------------:|----------:|
|   3 |      0.173 |                      0.334 |     0.125 |
|   4 |      0.183 |                      0.461 |     0.311 |
|   5 |      0.197 |                      0.559 |     0.364 |
|   6 |      0.205 |                      0.553 |     0.349 |

Escolhido k = 5 (menor k com estabilidade ARI ≥ 0,75; senão o mais estável).

|   cluster_regiao |   n |   ultra |   edc |   skyfit |   pop_1km |   pop_5min |   razao_alcance |   km_rua_5min |   fracao_pe |   renda_5min |   pressao_oferta |   alunos_rel_rede |   alunos_por_m2 |
|-----------------:|----:|--------:|------:|---------:|----------:|-----------:|----------------:|--------------:|------------:|-------------:|-----------------:|------------------:|----------------:|
|                0 |  72 |      10 |    20 |       42 |  13662.7  |    87251.6 |            5.89 |        212.61 |        0.71 |      1880.75 |             1.5  |              1    |            2.11 |
|                1 |  28 |      17 |     5 |        6 |  24867.4  |    79719.2 |            3.82 |        173.4  |        0.81 |      4099.72 |             2.43 |              1    |            1.74 |
|                2 |  20 |       7 |     1 |       12 |   6133.83 |    39819.4 |            4.31 |        103.35 |        0.32 |      1727.71 |             2.16 |              1.05 |            1.66 |
|                3 |  87 |      10 |     6 |       71 |   8923.65 |    30274.9 |            3.24 |        117.78 |        0.73 |      1741.03 |             2.21 |              1    |            1.7  |
|                4 |  64 |       9 |     5 |       50 |  18156    |    53273.2 |            2.93 |        132.76 |        0.73 |      1350.04 |             1    |              0.93 |            1.88 |

Alunos relativos à mediana da própria rede, por cluster: Kruskal-Wallis H=1.99, p=0.737.
- só ultra: H=5.73, p=0.220
- só skyfit: H=3.27, p=0.513
- alunos/m² (Ultra + EdC): H=2.26, p=0.688

## Nível 2 — imóvel (Ultra + Engenharia do Corpo com metragem)

N = 90; vagas presentes em 90.


**porte**

| porte          |   ('n', 'engenharia_do_corpo') |   ('n', 'ultra') |   ('alunos_por_m2', 'engenharia_do_corpo') |   ('alunos_por_m2', 'ultra') |
|:---------------|-------------------------------:|-----------------:|-------------------------------------------:|-----------------------------:|
| até 1.300 m²   |                             21 |               14 |                                       2.57 |                         2.14 |
| 1.300–1.800 m² |                             10 |               31 |                                       2.09 |                         1.49 |
| > 1.800 m²     |                              6 |                8 |                                       1.82 |                         1.55 |

**estacionamento**

| estacionamento   |   ('n', 'engenharia_do_corpo') |   ('n', 'ultra') |   ('alunos_por_m2', 'engenharia_do_corpo') |   ('alunos_por_m2', 'ultra') |
|:-----------------|-------------------------------:|-----------------:|-------------------------------------------:|-----------------------------:|
| sem/pouca vaga   |                              4 |                3 |                                       2.11 |                         2.25 |
| média            |                              9 |               13 |                                       2.07 |                         1.49 |
| muita vaga       |                             24 |               37 |                                       2.63 |                         1.59 |

**tipo_imovel**

| tipo_imovel      |   ('n', 'engenharia_do_corpo') |   ('alunos_por_m2', 'engenharia_do_corpo') |
|:-----------------|-------------------------------:|-------------------------------------------:|
| CENTRO COMERCIAL |                             11 |                                       2.71 |
| SALA DE RUA      |                             20 |                                       2.3  |
| SHOPPING         |                              6 |                                       2.26 |

**cluster de região x porte (contagem)**

|   cluster_regiao |   até 1.300 m² |   1.300–1.800 m² |   > 1.800 m² |
|-----------------:|---------------:|-----------------:|-------------:|
|                0 |             13 |               13 |            3 |
|                1 |              6 |               11 |            5 |
|                2 |              3 |                1 |            4 |
|                3 |              4 |               11 |            1 |
|                4 |              8 |                5 |            1 |

Spearman vagas/1.000 m² x alunos/m²: -0.00

## Modelo simples out-of-fold (log alunos), GroupKFold por metro

- B0 só rede: R² OOF +0.029
- B1 rede + círculo 1 km: R² OOF +0.014
- I rede + círculo + isócrona: R² OOF -0.002
- ganho da isócrona sobre o círculo: -0.016 IC95 [-0.038; +0.033] (N = 263, 113 metros)