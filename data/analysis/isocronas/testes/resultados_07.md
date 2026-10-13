# Resultados dos testes pré-registrados (07_testes.py)

Bases: ultra 97 | pref_revelada 39927 ({'controle': 27358, 'academia': 12569}) | hex_funil 260 | canibal 266 pares | metros com isócronas: 46
## T1 — Medição: isócrona x círculo de 1 km x hexágono res-7

**ultra** (N=97)

| cenario   |   n |   area_km2_med |   razao_pop_med |   razao_pop_p10 |   razao_pop_p90 |   rho_pop_vs_1km |   rho_oferta_vs_1km |   rho_renda_vs_1km |
|:----------|----:|---------------:|----------------:|----------------:|----------------:|-----------------:|--------------------:|-------------------:|
| carro_5   |  97 |         14.169 |           3.924 |           2.14  |           7.359 |            0.793 |               0.664 |              0.961 |
| carro_10  |  97 |         77.454 |          17.609 |           7.588 |          36.422 |            0.695 |               0.466 |              0.853 |
| carro_15  |  97 |        216.704 |          37.256 |          11.798 |          84.516 |            0.671 |               0.372 |              0.716 |
| pe_10     |  97 |          0.756 |           0.267 |           0.13  |           0.381 |            0.926 |               0.715 |              0.977 |
| pe_15     |  97 |          1.889 |           0.688 |           0.448 |           0.833 |            0.968 |               0.877 |              0.99  |
| hex_r7    |  97 |          5.396 |           1.573 |           0.697 |           2.289 |            0.842 |               0.74  |              0.943 |

**hex_carteira** (N=195)

| cenario   |   n |   area_km2_med |   razao_pop_med |   razao_pop_p10 |   razao_pop_p90 |   rho_pop_vs_1km |   rho_oferta_vs_1km |   rho_renda_vs_1km |
|:----------|----:|---------------:|----------------:|----------------:|----------------:|-----------------:|--------------------:|-------------------:|
| carro_5   | 195 |          6.639 |           2.291 |           0.391 |           5.364 |            0.947 |               0.909 |              0.922 |
| carro_10  | 195 |         41.422 |          12.193 |           3.733 |          61.824 |            0.916 |               0.861 |              0.802 |
| carro_15  | 195 |        114.565 |          30.361 |           9.207 |         248.049 |            0.878 |               0.792 |              0.73  |
| pe_10     | 195 |          0.331 |           0.209 |           0.03  |           0.373 |            0.897 |               0.774 |              0.924 |
| pe_15     | 195 |          0.947 |           0.614 |           0.082 |           0.791 |            0.934 |               0.931 |              0.942 |
| hex_r7    | 195 |          5.29  |           1.683 |           1.374 |           2.203 |            0.988 |               0.969 |              0.989 |

## T2 — Preferência revelada (academia x ponto aleatório da malha)

**todas**: N=36175 (academias 11986, controles 24189; 3752 excluídos sem rede) — AUC OOF B=0.822 | I=0.844 | só isócronas=0.843 | ganho I−B=+0.022 IC95 [+0.020; +0.024] → critério ATENDIDO
coeficientes padronizados (modelo I, in-sample, só para leitura): oferta_ponderada__pe_15=+1.26, n_nos__carro_15=+1.12, pop__pe_15=+1.12, n_nos__pe_15=-0.88, km_rua__carro_15=-0.81, pop__carro_5=+0.57, pop__carro_15=-0.52, km_rua__pe_15=+0.49

**independentes**: N=32142 (academias 7953, controles 24189; 3634 excluídos sem rede) — AUC OOF B=0.799 | I=0.827 | só isócronas=0.825 | ganho I−B=+0.028 IC95 [+0.026; +0.031] → critério ATENDIDO
coeficientes padronizados (modelo I, in-sample, só para leitura): pop__pe_15=+2.13, n_nos__carro_15=+1.31, km_rua__carro_15=-1.10, n_nos__pe_15=-1.07, oferta_ponderada__pe_15=+1.01, pop__circulo_1km=-0.87, km_rua__pe_15=+0.68, pop__carro_15=-0.57

**cadeias**: N=28222 (academias 4033, controles 24189; 3287 excluídos sem rede) — AUC OOF B=0.871 | I=0.887 | só isócronas=0.887 | ganho I−B=+0.017 IC95 [+0.014; +0.019] → critério não atendido
coeficientes padronizados (modelo I, in-sample, só para leitura): oferta_ponderada__pe_15=+1.60, n_nos__carro_15=+0.84, pop__carro_5=+0.63, renda_pc__pe_15=+0.58, km_rua__carro_5=+0.58, oferta_ponderada__carro_5=-0.49, pop__hex_r7=-0.46, n_nos__pe_15=-0.44

## T3 — Previsão de desempenho (E8, molde E7)

N = 53 unidades maduras com metragem, coordenada de confiança alta/média e isócrona.

**ativos_por_m2_mad** (N=51): R² OOF LOO — B1 metragem -0.024 | B2 círculo -0.068 | I isócronas -0.089 IC95 [-0.46; +0.13] | só isócronas -0.106 | ganho I−B2 -0.022 IC95 [-0.19; +0.13] | GroupKFold por UF: I -0.105 → **NO-GO**
Spearman desfecho x feature: pop__circulo_1km=-0.02, renda_pc__circulo_1km=+0.38, oferta_ponderada__circulo_1km=+0.15, pop__carro_5=-0.11, pop__pe_15=+0.02, oferta_ponderada__carro_5=+0.04, n_ultra__carro_10=+0.05, pop_por_academia__carro_5=-0.29, metragem=-0.27

**fat_por_m2_mad** (N=51): R² OOF LOO — B1 metragem -0.048 | B2 círculo -0.025 | I isócronas -0.097 IC95 [-0.59; +0.12] | só isócronas -0.102 | ganho I−B2 -0.072 IC95 [-0.26; +0.03] | GroupKFold por UF: I -0.306 → **NO-GO**
Spearman desfecho x feature: pop__circulo_1km=-0.18, renda_pc__circulo_1km=+0.26, oferta_ponderada__circulo_1km=-0.07, pop__carro_5=-0.25, pop__pe_15=-0.15, oferta_ponderada__carro_5=-0.07, n_ultra__carro_10=+0.22, pop_por_academia__carro_5=-0.28, metragem=-0.05

**pag_por_m2_mad** (N=51): R² OOF LOO — B1 metragem +0.006 | B2 círculo -0.056 | I isócronas -0.139 IC95 [-0.46; +0.11] | só isócronas -0.115 | ganho I−B2 -0.083 IC95 [-0.19; +0.03] | GroupKFold por UF: I -0.302 → **NO-GO**
Spearman desfecho x feature: pop__circulo_1km=-0.20, renda_pc__circulo_1km=+0.20, oferta_ponderada__circulo_1km=-0.11, pop__carro_5=-0.22, pop__pe_15=-0.17, oferta_ponderada__carro_5=-0.08, n_ultra__carro_10=+0.28, pop_por_academia__carro_5=-0.23, metragem=-0.15

**pct_agregador_mad** (N=51): R² OOF LOO — B1 metragem -0.089 | B2 círculo -0.060 | I isócronas -0.113 IC95 [-0.48; +0.16] | só isócronas -0.059 | ganho I−B2 -0.053 IC95 [-0.24; +0.15] | GroupKFold por UF: I -0.541 → **NO-GO**
Spearman desfecho x feature: pop__circulo_1km=+0.23, renda_pc__circulo_1km=+0.08, oferta_ponderada__circulo_1km=+0.25, pop__carro_5=+0.17, pop__pe_15=+0.24, oferta_ponderada__carro_5=+0.10, n_ultra__carro_10=-0.25, pop_por_academia__carro_5=+0.09, metragem=-0.07

**churn_med_12m** (N=51): R² OOF LOO — B1 metragem -0.005 | B2 círculo -0.013 | I isócronas +0.020 IC95 [-0.52; +0.30] | só isócronas +0.021 | ganho I−B2 +0.033 IC95 [-0.21; +0.29] | GroupKFold por UF: I -0.209 → **NO-GO**
Spearman desfecho x feature: pop__circulo_1km=-0.18, renda_pc__circulo_1km=-0.60, oferta_ponderada__circulo_1km=-0.32, pop__carro_5=-0.15, pop__pe_15=-0.22, oferta_ponderada__carro_5=-0.36, n_ultra__carro_10=-0.37, pop_por_academia__carro_5=+0.24, metragem=-0.30

## T4 — Funil: rótulo de concorrência com isócrona de 5 min de carro x raio de 1 km

**cadeias_carro_5**: troca de rótulo em 12.8% dos 195 hexágonos; rho contagem = +0.91; mediana 1 km = 2, isócrona = 1

| funil_1km   |   Adensar |   Disputa |   Livre |
|:------------|----------:|----------:|--------:|
| Adensar     |        19 |         0 |       8 |
| Disputa     |         9 |        76 |       6 |
| Livre       |         2 |         0 |      75 |

**total_carro_5**: troca de rótulo em 21.5% dos 195 hexágonos; rho contagem = +0.86; mediana 1 km = 2, isócrona = 5

| funil_1km   |   Adensar |   Disputa |   Livre |
|:------------|----------:|----------:|--------:|
| Adensar     |         5 |        21 |       1 |
| Disputa     |         2 |        86 |       3 |
| Livre       |         8 |         7 |      62 |

**cadeias_pe_15**: troca de rótulo em 48.7% dos 195 hexágonos; rho contagem = +0.75; mediana 1 km = 2, isócrona = 0

| funil_1km   |   Adensar |   Disputa |   Livre |
|:------------|----------:|----------:|--------:|
| Adensar     |         3 |         0 |      24 |
| Disputa     |        40 |        20 |      31 |
| Livre       |         0 |         0 |      77 |

rho do residual (pop×17,35% − oferta×2.500) 1 km x carro 5 min = +0.79; x a pé 15 min = +0.85

## T5 — Canibalização (descritivo)

carro 5 min: 66 pares; 43 unidades com sobreposição (mediana 66% entre as que têm); rho x ativos_por_m2_mad=+0.07, rho x fat_por_m2_mad=+0.27, rho x pct_agregador_mad=-0.22, rho x churn_med_12m=-0.19

carro 10 min: 200 pares; 66 unidades com sobreposição (mediana 100% entre as que têm); rho x ativos_por_m2_mad=+0.11, rho x fat_por_m2_mad=+0.28, rho x pct_agregador_mad=-0.14, rho x churn_med_12m=-0.24