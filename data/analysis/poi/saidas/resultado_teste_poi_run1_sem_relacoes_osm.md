# Teste pré-registrado de POI — protocolo v1.1

Famílias testadas (portões): ['F1', 'F3', 'F5']

## S1 — Ultra, faturamento Financeiro 2025 (N = 53; R² LOO base = +0.285)

| familia   |   dR2_LOO_OLS | IC95_boot        |   p_perm |   coef_padr | sinal_ok   | mais_influente   |   dR2_sem_ela |   p_holm |
|:----------|--------------:|:-----------------|---------:|------------:|:-----------|:-----------------|--------------:|---------:|
| F1        |       -0.0311 | [-0.055; -0.016] |    0.714 |      0.0093 | True       | lago-norte-df    |       -0.0316 |        1 |
| F3        |       -0.0318 | [-0.063; -0.008] |    0.781 |      0.0416 | True       | lago-sul-df      |       -0.0323 |        1 |

## S2 — Smart Fit, alunos 2025 (N = 454; R² GroupKFold-metrô base = -0.111)

| familia   |   dR2_GKF_metro_OLS | IC95_boot_cluster   |   p_perm |   coef_padr | sinal_ok   |   dR2_LOO_OLS |   p_holm |
|:----------|--------------------:|:--------------------|---------:|------------:|:-----------|--------------:|---------:|
| F1        |             -0.0429 | [-0.096; +0.021]    |    0.989 |     -0.095  | False      |        0.0015 |    0.989 |
| F3        |             -0.0025 | [-0.015; +0.003]    |    0.457 |      0.0282 | True       |       -0.0041 |    0.914 |
| F5        |             -0.0137 | [-0.079; +0.013]    |    0.205 |     -0.066  | True       |        0.0004 |    0.615 |

## Critério (§7)

| familia   | C1                 | C1b   | C2    | veredito                     |
|:----------|:-------------------|:------|:------|:-----------------------------|
| F1        | False              | False | False | sem ganho detectável neste N |
| F3        | False              | False | False | sem ganho detectável neste N |
| F5        | não avaliável (P5) | -     | False | sem ganho detectável neste N |

## Relatado sem decidir (§8) — p sem correção, leitura exploratória

| amostra                     | variavel          | validacao        |   N |     dR2 |   p_perm |   coef_padr |
|:----------------------------|:------------------|:-----------------|----:|--------:|---------:|------------:|
| S1                          | F1                | GroupKFold UF    |  53 | -0.0528 |    0.732 |      0.0093 |
| S1                          | F1                | LOO ridge        |  53 | -0.0404 |  nan     |    nan      |
| S1                          | F3                | GroupKFold UF    |  53 | -0.0819 |    0.81  |      0.0416 |
| S1                          | F3                | LOO ridge        |  53 | -0.0312 |  nan     |    nan      |
| S1                          | F5                | GroupKFold UF    |  53 | -0.1167 |    0.648 |      0.087  |
| S1                          | F5                | LOO ridge        |  53 | -0.0294 |  nan     |    nan      |
| S1                          | F1_all            | LOO              |  53 | -0.0343 |    0.844 |     -0.0236 |
| S1                          | F2                | LOO              |  53 | -0.0269 |    0.6   |      0.0113 |
| S1                          | F2_all            | LOO              |  53 | -0.0269 |    0.532 |     -0.0355 |
| S1                          | F1_c10            | LOO              |  53 | -0.0419 |    0.974 |      0.1653 |
| S1                          | F2_c10            | LOO              |  53 | -0.0119 |    0.5   |      0.228  |
| S1                          | F2b               | LOO              |  53 | -0.0126 |    0.308 |     -0.09   |
| S1                          | F5                | LOO              |  53 | -0.0287 |    0.594 |      0.087  |
| S1                          | F5_pre_inaug      | LOO              |  53 | -0.0354 |    0.67  |      0.058  |
| S1 idade>=12                | F1                | LOO              |  36 | -0.046  |    0.638 |      0.0784 |
| S1 + dummy DF               | F1                | LOO              |  53 | -0.0295 |    0.694 |     -0.0471 |
| S1 idade>=12                | F3                | LOO              |  36 |  0.0113 |    0.13  |      0.2275 |
| S1 + dummy DF               | F3                | LOO              |  53 | -0.0325 |    0.828 |      0.0315 |
| S1 idade>=12                | F5                | LOO              |  36 |  0.0245 |    0.024 |      0.2715 |
| S1 + dummy DF               | F5                | LOO              |  53 | -0.0434 |    0.95  |      0.0342 |
| S1 estabilidade 2026-01..08 | F1                | LOO              |  53 | -0.0285 |    0.824 |      0.005  |
| S3 Ultra ativos 2025        | F1                | LOO              |  53 | -0.0263 |    0.514 |      0.1221 |
| S1 estabilidade 2026-01..08 | F3                | LOO              |  53 | -0.0216 |    0.584 |      0.0748 |
| S3 Ultra ativos 2025        | F3                | LOO              |  53 | -0.0312 |    0.602 |      0.0733 |
| S1 estabilidade 2026-01..08 | F5                | LOO              |  53 | -0.0289 |    0.856 |      0.0348 |
| S3 Ultra ativos 2025        | F5                | LOO              |  53 | -0.0013 |    0.104 |      0.1992 |
| S2                          | F2                | GroupKFold metrô | 454 | -0.023  |    0.99  |     -0.1205 |
| S2                          | F5                | GroupKFold metrô | 454 | -0.0137 |    0.232 |     -0.066  |
| S1                          | todas as famílias | LOO              |  53 | -0.0952 |  nan     |    nan      |
| S2                          | todas as famílias | GroupKFold metrô | 454 | -0.0476 |  nan     |    nan      |
| skyfit                      | F1                | LOO              | 175 | -0.0043 |    0.408 |      0.0392 |
| skyfit                      | F3                | LOO              | 175 | -0.0043 |    0.362 |     -0.0431 |
| skyfit                      | F5                | LOO              | 176 | -0.014  |    0.866 |     -0.0383 |
| engenharia_do_corpo         | F1                | LOO              |  35 | -0.0438 |    0.706 |     -0.0811 |
| engenharia_do_corpo         | F3                | LOO              |  35 | -0.0731 |    0.914 |     -0.0688 |
| engenharia_do_corpo         | F5                | LOO              |  36 |  0.0294 |    0.088 |      0.2615 |