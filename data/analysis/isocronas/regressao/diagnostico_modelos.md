# Diagnóstico: modelo de faturamento x modelo de alunos/m² (Ultra, N = 54, fora da amostra LOO)

## 1. Variáveis e pesos (ajuste em todas as unidades; coeficientes em log, IC95 bootstrap)

| modelo              | variavel     |   coef | IC95           |   R2_dentro_da_amostra |
|:--------------------|:-------------|-------:|:---------------|-----------------------:|
| MF: log faturamento | log_metragem |  0.685 | [+0.33; +1.05] |                  0.526 |
| MF: log faturamento | log_renda    |  0.45  | [+0.27; +0.62] |                  0.526 |
| MF: log faturamento | log_pop      | -0.139 | [-0.25; -0.03] |                  0.526 |
| MA: log alunos/m²   | log_metragem | -0.462 | [-0.79; -0.09] |                  0.295 |
| MA: log alunos/m²   | log_renda    |  0.257 | [+0.13; +0.38] |                  0.295 |
| MA: log alunos/m²   | log_pop      | -0.06  | [-0.15; +0.02] |                  0.295 |

Leitura: em MF o coeficiente de m² é a elasticidade do faturamento ao tamanho; em MA, o de m² é essa elasticidade menos 1 (densidade cai com o tamanho). Renda e população têm o mesmo significado nos dois.

## 2. Precisão fora da amostra (todas as 54)

| modelo                       |   R2_log |   R2_real |   rho |   erro_mediano |   MAPE |   erro_p75 |   erro_p90 |
|:-----------------------------|---------:|----------:|------:|---------------:|-------:|-----------:|-----------:|
| MF faturamento               |    0.447 |     0.374 | 0.682 |          0.243 |  0.28  |      0.357 |      0.575 |
| MA alunos/m2 -> faturamento  |    0.398 |     0.317 | 0.681 |          0.25  |  0.292 |      0.395 |      0.604 |
| V viabilidade -> faturamento |    0.117 |     0.034 | 0.277 |          0.266 |  0.325 |      0.473 |      0.6   |
| MA alunos/m2 -> alunos       |    0.295 |     0.24  | 0.571 |          0.225 |  0.231 |      0.3   |      0.449 |
| V viabilidade -> alunos      |    0.08  |     0.123 | 0.214 |          0.224 |  0.251 |      0.359 |      0.482 |

## 3. Onde o erro está (erro = previsto/real − 1; negativo = unidade fatura MAIS que o previsto)

**Distribuição do erro absoluto (faturamento):**

| quantil   |    MF |    MA |     V |
|:----------|------:|------:|------:|
| p10       | 0.066 | 0.039 | 0.066 |
| p25       | 0.116 | 0.106 | 0.121 |
| p50       | 0.242 | 0.25  | 0.266 |
| p75       | 0.357 | 0.395 | 0.472 |
| p90       | 0.576 | 0.605 | 0.6   |
| p100      | 1.021 | 1.099 | 1.273 |

**10 maiores erros (MF) e o que eles têm em comum:**

| unidade           |   m2 |   faturamento |   alunos |   alunos_por_m2 |   fat_por_aluno |   erro_MF_fat |   erro_MA_fat |   erro_V_fat |
|:------------------|-----:|--------------:|---------:|----------------:|----------------:|--------------:|--------------:|-------------:|
| mococa-sp         | 1311 |        118203 |     1587 |            1.21 |              74 |         1.021 |         0.915 |        0.644 |
| setor-oeste-go    | 1700 |        154821 |     1423 |            0.84 |             109 |         0.973 |         0.865 |        0.602 |
| lago-sul-df       | 2000 |        312265 |     2580 |            1.29 |             121 |         0.831 |         0.323 |        0.01  |
| campo-limpo-sp    | 1220 |         87594 |     1150 |            0.94 |              76 |         0.682 |         1.099 |        1.171 |
| botafogo-rj       | 1230 |        708987 |     4024 |            3.27 |             176 |        -0.627 |        -0.643 |       -0.743 |
| cariacica-es      | 1300 |        361856 |     3029 |            2.33 |             119 |        -0.589 |        -0.501 |       -0.479 |
| brasilandia-sp    | 1400 |        112414 |     1515 |            1.08 |              74 |         0.544 |         0.8   |        0.846 |
| poa-barra-sul-rs  | 2800 |        327613 |     2892 |            1.03 |             113 |         0.475 |         0.21  |        0.261 |
| alexandrina-go    | 1400 |        151339 |     1596 |            1.14 |              95 |         0.463 |         0.503 |        0.371 |
| vila-guilherme-sp | 1466 |        156928 |     1988 |            1.36 |              79 |         0.436 |         0.509 |        0.336 |

Correlação entre os erros absolutos de MF e MA: +0.82 (perto de 1 = erram nas mesmas unidades).
Parcela do erro quadrático total (MF) concentrada nas 5 piores unidades: 51%; nas 10 piores: 69%.

## 4. É outlier ou é o padrão? (modelos REAJUSTADOS sem as unidades removidas, LOO)

| amostra                | modelo                       |   R2_log |   rho |   erro_mediano |   MAPE |
|:-----------------------|:-----------------------------|---------:|------:|---------------:|-------:|
| todas (54)             | MF faturamento               |    0.447 | 0.682 |          0.243 |  0.28  |
| todas (54)             | MA alunos/m2 -> faturamento  |    0.398 | 0.681 |          0.25  |  0.292 |
| todas (54)             | V viabilidade -> faturamento |    0.117 | 0.277 |          0.266 |  0.325 |
| sem as 5 piores        | MF faturamento               |    0.561 | 0.74  |          0.205 |  0.231 |
| sem as 5 piores        | MA alunos/m2 -> faturamento  |    0.481 | 0.731 |          0.232 |  0.252 |
| sem as 5 piores        | V viabilidade -> faturamento |    0.16  | 0.298 |          0.268 |  0.301 |
| sem os 10% piores (6)  | MF faturamento               |    0.645 | 0.806 |          0.208 |  0.217 |
| sem os 10% piores (6)  | MA alunos/m2 -> faturamento  |    0.561 | 0.797 |          0.212 |  0.234 |
| sem os 10% piores (6)  | V viabilidade -> faturamento |    0.215 | 0.368 |          0.25  |  0.289 |
| sem os 20% piores (11) | MF faturamento               |    0.708 | 0.824 |          0.203 |  0.192 |
| sem os 20% piores (11) | MA alunos/m2 -> faturamento  |    0.605 | 0.791 |          0.209 |  0.208 |
| sem os 20% piores (11) | V viabilidade -> faturamento |    0.208 | 0.296 |          0.194 |  0.273 |

Atenção: tirar os piores sempre melhora qualquer modelo (inclusive o da viabilidade). O que importa é se o modelo GANHA da viabilidade depois da limpeza e quanto o erro TÍPICO cai.

**Distância de Cook (MF):** 4 unidades influentes (> 4/N): botafogo-rj, cariacica-es, lago-sul-df, mococa-sp.
| modelo                            |   R2_log |   R2_real |   rho |   erro_mediano |   MAPE |   erro_p75 |   erro_p90 |
|:----------------------------------|---------:|----------:|------:|---------------:|-------:|-----------:|-----------:|
| MF Huber (robusta)                |    0.448 |     0.361 | 0.69  |          0.213 |  0.277 |      0.351 |      0.552 |
| MA Huber (robusta) -> faturamento |    0.41  |     0.311 | 0.684 |          0.234 |  0.281 |      0.411 |      0.56  |

**Jackknife (MF):** R² fora da amostra tirando uma unidade por vez varia de +0.396 a +0.510 (mediana +0.446); a unidade cuja saída mais muda o R² é cariacica-es.