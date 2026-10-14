# Resultados v2 (08_testes_v2.py)

Bases v2: ultra 97 (com isócrona de carro 97, a pé 96) | pref_revelada 34528 {'controle': 24316, 'academia': 10212} | hex_funil 175 | canibal 266 | metros 46
- truncamento carro_5: academias 0.0% | controles 0.3% | Ultra 0.0%
- truncamento carro_10: academias 16.5% | controles 21.6% | Ultra 1.0%
- truncamento carro_15: academias 51.3% | controles 61.1% | Ultra 37.1%
## T1 — Medição: isócrona x círculo de 1 km x hexágono res-7

**ultra** (N=97)

| cenario   |   n |   area_km2_med |   razao_pop_med |   razao_pop_p10 |   razao_pop_p90 |   rho_pop_vs_1km |   rho_oferta_vs_1km |   rho_renda_vs_1km |
|:----------|----:|---------------:|----------------:|----------------:|----------------:|-----------------:|--------------------:|-------------------:|
| carro_5   |  97 |         14.169 |           3.924 |           2.135 |           7.299 |            0.792 |               0.639 |              0.961 |
| carro_10  |  97 |         77.454 |          17.603 |           7.594 |          36.555 |            0.689 |               0.452 |              0.86  |
| carro_15  |  97 |        216.704 |          37.246 |          11.797 |          84.529 |            0.67  |               0.368 |              0.72  |
| pe_10     |  97 |          0.765 |           0.267 |           0.135 |           0.385 |            0.926 |               0.705 |              0.977 |
| pe_15     |  97 |          1.926 |           0.685 |           0.461 |           0.831 |            0.968 |               0.873 |              0.99  |
| hex_r7    |  97 |          5.396 |           1.597 |           0.715 |           2.289 |            0.868 |               0.761 |              0.943 |

**hex_carteira** (N=161)

| cenario   |   n |   area_km2_med |   razao_pop_med |   razao_pop_p10 |   razao_pop_p90 |   rho_pop_vs_1km |   rho_oferta_vs_1km |   rho_renda_vs_1km |
|:----------|----:|---------------:|----------------:|----------------:|----------------:|-----------------:|--------------------:|-------------------:|
| carro_5   | 161 |          6.795 |           2.402 |           0.334 |           5.421 |            0.934 |               0.921 |              0.939 |
| carro_10  | 161 |         47.64  |          12.719 |           3.879 |          53.016 |            0.909 |               0.888 |              0.785 |
| carro_15  | 161 |        131.692 |          32.199 |          10.342 |         308.271 |            0.884 |               0.827 |              0.723 |
| pe_10     | 161 |          0.419 |           0.185 |           0.015 |           0.368 |            0.919 |               0.794 |              0.943 |
| pe_15     | 161 |          1.027 |           0.514 |           0.054 |           0.799 |            0.942 |               0.941 |              0.964 |
| hex_r7    | 161 |          5.303 |           1.733 |           1.457 |           2.207 |            0.987 |               0.974 |              0.988 |

## T2 (v2) — Preferência revelada, bootstrap por metro
- **todas / pre_registrada_carro15_nao_truncado**: N=13806 (4558 academias) — AUC B 0.763 | I 0.796 | ganho +0.033 IC95 (metro) [+0.010; +0.045] → ATENDIDO
- **todas / sem_carro15_todos**: N=33144 (9362 academias) — AUC B 0.756 | I 0.778 | ganho +0.022 IC95 (metro) [+0.013; +0.031] → ATENDIDO
- **independentes / pre_registrada_carro15_nao_truncado**: N=12522 (3274 academias) — AUC B 0.752 | I 0.791 | ganho +0.039 IC95 (metro) [+0.019; +0.050] → ATENDIDO
- **independentes / sem_carro15_todos**: N=30635 (6853 academias) — AUC B 0.743 | I 0.771 | ganho +0.028 IC95 (metro) [+0.020; +0.038] → ATENDIDO
- **cadeias / pre_registrada_carro15_nao_truncado**: N=10532 (1284 academias) — AUC B 0.793 | I 0.821 | ganho +0.028 IC95 (metro) [+0.000; +0.041] → ATENDIDO
- **cadeias / sem_carro15_todos**: N=26291 (2509 academias) — AUC B 0.793 | I 0.811 | ganho +0.019 IC95 (metro) [+0.010; +0.025] → não atendido

## T3 — Previsão de desempenho (E8, molde E7)

N = 54 unidades maduras com metragem, coordenada de confiança alta/média e isócrona.

**ativos_por_m2_mad** (N=54): R² OOF LOO — B1 metragem +0.000 | B2 círculo -0.070 | I isócronas -0.079 IC95 [-0.42; +0.12] | só isócronas -0.071 | ganho I−B2 -0.008 IC95 [-0.16; +0.15] | GroupKFold por UF: I -0.154 → **NO-GO**
Spearman desfecho x feature: pop__circulo_1km=-0.00, renda_pc__circulo_1km=+0.37, oferta_ponderada__circulo_1km=+0.18, pop__carro_5=-0.11, pop__pe_15=+0.05, oferta_ponderada__carro_5=+0.04, n_ultra__carro_10=+0.02, pop_por_academia__carro_5=-0.27, metragem=-0.30

**fat_por_m2_mad** (N=54): R² OOF LOO — B1 metragem -0.044 | B2 círculo -0.015 | I isócronas -0.088 IC95 [-0.60; +0.16] | só isócronas -0.102 | ganho I−B2 -0.073 IC95 [-0.25; +0.03] | GroupKFold por UF: I -0.324 → **NO-GO**
Spearman desfecho x feature: pop__circulo_1km=-0.18, renda_pc__circulo_1km=+0.27, oferta_ponderada__circulo_1km=-0.05, pop__carro_5=-0.25, pop__pe_15=-0.15, oferta_ponderada__carro_5=-0.09, n_ultra__carro_10=+0.21, pop_por_academia__carro_5=-0.26, metragem=-0.07

**pag_por_m2_mad** (N=54): R² OOF LOO — B1 metragem +0.020 | B2 círculo -0.068 | I isócronas -0.148 IC95 [-0.41; +0.10] | só isócronas -0.105 | ganho I−B2 -0.081 IC95 [-0.19; +0.04] | GroupKFold por UF: I -0.320 → **NO-GO**
Spearman desfecho x feature: pop__circulo_1km=-0.18, renda_pc__circulo_1km=+0.17, oferta_ponderada__circulo_1km=-0.10, pop__carro_5=-0.22, pop__pe_15=-0.15, oferta_ponderada__carro_5=-0.10, n_ultra__carro_10=+0.25, pop_por_academia__carro_5=-0.20, metragem=-0.18

**pct_agregador_mad** (N=54): R² OOF LOO — B1 metragem -0.091 | B2 círculo -0.050 | I isócronas -0.090 IC95 [-0.46; +0.19] | só isócronas -0.052 | ganho I−B2 -0.040 IC95 [-0.23; +0.16] | GroupKFold por UF: I -0.415 → **NO-GO**
Spearman desfecho x feature: pop__circulo_1km=+0.23, renda_pc__circulo_1km=+0.11, oferta_ponderada__circulo_1km=+0.27, pop__carro_5=+0.16, pop__pe_15=+0.25, oferta_ponderada__carro_5=+0.11, n_ultra__carro_10=-0.25, pop_por_academia__carro_5=+0.05, metragem=-0.10

**churn_med_12m** (N=54): R² OOF LOO — B1 metragem +0.004 | B2 círculo +0.012 | I isócronas +0.076 IC95 [-0.50; +0.38] | só isócronas +0.004 | ganho I−B2 +0.063 IC95 [-0.16; +0.33] | GroupKFold por UF: I -0.153 → **NO-GO**
Spearman desfecho x feature: pop__circulo_1km=-0.17, renda_pc__circulo_1km=-0.60, oferta_ponderada__circulo_1km=-0.29, pop__carro_5=-0.17, pop__pe_15=-0.22, oferta_ponderada__carro_5=-0.32, n_ultra__carro_10=-0.38, pop_por_academia__carro_5=+0.17, metragem=-0.30

## T4 (v2) — rótulo do funil com hexágonos de snap 700 m e na cascata real

## T4 — Funil: rótulo de concorrência com isócrona de 5 min de carro x raio de 1 km

**cadeias_carro_5**: troca de rótulo em 9.9% dos 161 hexágonos; rho contagem = +0.93; mediana 1 km = 3, isócrona = 1

| funil_1km   |   Adensar |   Disputa |   Livre |
|:------------|----------:|----------:|--------:|
| Adensar     |        14 |         0 |       3 |
| Disputa     |         9 |        68 |       4 |
| Livre       |         0 |         0 |      63 |

**total_carro_5**: troca de rótulo em 14.9% dos 161 hexágonos; rho contagem = +0.87; mediana 1 km = 3, isócrona = 6

| funil_1km   |   Adensar |   Disputa |   Livre |
|:------------|----------:|----------:|--------:|
| Adensar     |         5 |        12 |       0 |
| Disputa     |         1 |        77 |       3 |
| Livre       |         6 |         2 |      55 |

**cadeias_pe_15**: troca de rótulo em 49.1% dos 161 hexágonos; rho contagem = +0.76; mediana 1 km = 3, isócrona = 0

| funil_1km   |   Adensar |   Disputa |   Livre |
|:------------|----------:|----------:|--------:|
| Adensar     |         2 |         0 |      15 |
| Disputa     |        38 |        17 |      26 |
| Livre       |         0 |         0 |      63 |

rho do residual (pop×17,35% − oferta×2.500) 1 km x carro 5 min = +0.79; x a pé 15 min = +0.89

**Cascata sem a camada 3** (score ≥ 30, pop hex ≥ 5.000, residual ≥ 2.000): N=25; troca de rótulo 24.0%; passam a camada 3 hoje: 8 | com carro 5 min: 13

| funil   |   Adensar |   Disputa |   Livre |
|:--------|----------:|----------:|--------:|
| Adensar |         5 |         0 |       1 |
| Disputa |         4 |        12 |       1 |
| Livre   |         0 |         0 |       2 |

## T5 — Canibalização (descritivo)

carro 5 min: 66 pares; 43 unidades com sobreposição (mediana 65% entre as que têm); rho x ativos_por_m2_mad=+0.05, rho x fat_por_m2_mad=+0.25, rho x pct_agregador_mad=-0.22, rho x churn_med_12m=-0.19

carro 10 min: 200 pares; 66 unidades com sobreposição (mediana 100% entre as que têm); rho x ativos_por_m2_mad=+0.10, rho x fat_por_m2_mad=+0.26, rho x pct_agregador_mad=-0.14, rho x churn_med_12m=-0.24

## T6 — Forma da rede x tamanho do catchment (círculo de área equivalente)
- **T6a todas**: N=33103 — AUC B 0.755 | B+isócrona 0.775 | B+círculo de área equivalente 0.777 | isócrona − círculo eq -0.002 IC95 (metro) [-0.006; +0.002] → forma da rede não acrescenta (critério ≥ +0,01)
- **T6a independentes**: N=30594 — AUC B 0.743 | B+isócrona 0.768 | B+círculo de área equivalente 0.769 | isócrona − círculo eq -0.001 IC95 (metro) [-0.005; +0.002] → forma da rede não acrescenta (critério ≥ +0,01)
- **T6a cadeias**: N=26251 — AUC B 0.793 | B+isócrona 0.810 | B+círculo de área equivalente 0.811 | isócrona − círculo eq -0.001 IC95 (metro) [-0.008; +0.004] → forma da rede não acrescenta (critério ≥ +0,01)

**T6b — concordância isócrona x círculo de área equivalente (Spearman)**

| base         | cenario   | variavel         |   n |   rho |   frac_troca_rank_gt10 |
|:-------------|:----------|:-----------------|----:|------:|-----------------------:|
| ultra        | carro_5   | pop              |  97 | 0.984 |                  0.072 |
| ultra        | carro_5   | renda_pc         |  97 | 0.993 |                  0     |
| ultra        | carro_5   | oferta_ponderada |  97 | 0.956 |                  0.175 |
| ultra        | pe_15     | pop              |  96 | 0.989 |                  0.031 |
| ultra        | pe_15     | renda_pc         |  96 | 0.992 |                  0.031 |
| ultra        | pe_15     | oferta_ponderada |  96 | 0.94  |                  0.125 |
| hex_carteira | carro_5   | pop              | 161 | 0.991 |                  0.062 |
| hex_carteira | carro_5   | renda_pc         | 160 | 0.961 |                  0.244 |
| hex_carteira | carro_5   | oferta_ponderada | 161 | 0.977 |                  0.124 |
| hex_carteira | pe_15     | pop              | 162 | 0.983 |                  0.105 |
| hex_carteira | pe_15     | renda_pc         | 158 | 0.967 |                  0.158 |
| hex_carteira | pe_15     | oferta_ponderada | 162 | 0.985 |                  0.043 |

**T6c — previsão (descritivo): mesmas colunas, isócrona x círculo equivalente**

- ativos_por_m2_mad: R² OOF LOO isócrona +0.001 (N=54) | círculo equivalente -0.131
- fat_por_m2_mad: R² OOF LOO isócrona +0.017 (N=54) | círculo equivalente +0.002
- churn_med_12m: R² OOF LOO isócrona +0.206 (N=54) | círculo equivalente +0.258