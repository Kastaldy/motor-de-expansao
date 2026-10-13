# Viabilidade atual (alunos/m² por comparáveis) x regressão — fora da amostra (LOO)


**Ultra — ALUNOS (ativos agosto/26)** (N = 54)

| metodo                          |   erro_mediano |   MAPE |   erro_p75 |   dif_erro_mediano_vs_V | IC95             |
|:--------------------------------|---------------:|-------:|-----------:|------------------------:|:-----------------|
| V (viabilidade atual)           |          0.224 |  0.251 |      0.359 |                   0     | [+0.000; +0.000] |
| RA (alunos/m² ~ m², renda, pop) |          0.225 |  0.231 |      0.3   |                   0.001 | [-0.093; +0.056] |
| RA+ (+ concorrência)            |          0.213 |  0.237 |      0.31  |                  -0.011 | [-0.094; +0.070] |

**Ultra — FATURAMENTO (Financeiro agosto/26)** (N = 54)

| metodo                            |   erro_mediano |   MAPE |   erro_p75 |   dif_erro_mediano_vs_V | IC95             |
|:----------------------------------|---------------:|-------:|-----------:|------------------------:|:-----------------|
| V (viabilidade atual)             |          0.266 |  0.325 |      0.473 |                   0     | [+0.000; +0.000] |
| RA x receita/aluno                |          0.25  |  0.292 |      0.395 |                  -0.016 | [-0.096; +0.079] |
| RA+ x receita/aluno               |          0.254 |  0.301 |      0.374 |                  -0.012 | [-0.088; +0.082] |
| RF (faturamento ~ m², renda, pop) |          0.243 |  0.28  |      0.357 |                  -0.023 | [-0.148; +0.072] |

RA ajustado em todas: log(alunos/m²) = +2.54 -0.46·log m² +0.26·log renda -0.06·log pop

**Ultra + Engenharia do Corpo — ALUNOS (comparáveis da mesma rede)** (N = 89)

| metodo                                |   erro_mediano |   MAPE |   erro_p75 |   dif_erro_mediano_vs_V | IC95             |
|:--------------------------------------|---------------:|-------:|-----------:|------------------------:|:-----------------|
| V (viabilidade atual)                 |          0.264 |  0.299 |      0.382 |                   0     | [+0.000; +0.000] |
| RA (alunos/m² ~ rede, m², renda, pop) |          0.214 |  0.279 |      0.367 |                  -0.05  | [-0.070; +0.008] |
| RA+ (+ concorrência)                  |          0.219 |  0.276 |      0.379 |                  -0.045 | [-0.082; +0.009] |