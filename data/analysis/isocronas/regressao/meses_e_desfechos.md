# Modelo de faturamento em vários meses e outros desfechos (Ultra, N até 54)

## (a) Mês a mês e mediana de 12 meses — faturamento do Financeiro

| mes          |   n |   R2_modelo |   rho_modelo |   erro_mediano_modelo |   R2_viabilidade |   rho_viabilidade |   erro_mediano_viabilidade |
|:-------------|----:|------------:|-------------:|----------------------:|-----------------:|------------------:|---------------------------:|
| 2025-09      |  54 |       0.355 |        0.594 |                 0.267 |            0.156 |             0.363 |                      0.277 |
| 2025-10      |  54 |       0.369 |        0.611 |                 0.266 |            0.172 |             0.381 |                      0.306 |
| 2025-11      |  54 |       0.368 |        0.614 |                 0.287 |            0.16  |             0.36  |                      0.283 |
| 2025-12      |  54 |       0.38  |        0.628 |                 0.271 |            0.171 |             0.386 |                      0.299 |
| 2026-01      |  54 |       0.385 |        0.619 |                 0.286 |            0.133 |             0.318 |                      0.3   |
| 2026-02      |  54 |       0.376 |        0.615 |                 0.286 |            0.126 |             0.271 |                      0.337 |
| 2026-03      |  54 |       0.399 |        0.637 |                 0.244 |            0.142 |             0.327 |                      0.27  |
| 2026-04      |  54 |       0.391 |        0.628 |                 0.248 |            0.1   |             0.258 |                      0.258 |
| 2026-05      |  54 |       0.408 |        0.63  |                 0.235 |            0.109 |             0.297 |                      0.278 |
| 2026-06      |  54 |       0.42  |        0.641 |                 0.243 |            0.095 |             0.274 |                      0.281 |
| 2026-07      |  54 |       0.415 |        0.647 |                 0.259 |            0.091 |             0.235 |                      0.274 |
| 2026-08      |  54 |       0.447 |        0.682 |                 0.243 |            0.117 |             0.277 |                      0.266 |
| mediana 12 m |  54 |       0.393 |        0.623 |                 0.23  |            0.141 |             0.315 |                      0.304 |

Mês a mês (12 meses): R² do modelo entre +0.35 e +0.45; viabilidade entre +0.09 e +0.17.

## (b) Validação temporal

Ajustado com a mediana de set/25–fev/26 e aplicado à mediana de mar–ago/26 (N = 54): R² +0.494 (com nível recentrado +0.494), rho +0.69, erro mediano 23%.
Persistência pura (usar o próprio faturamento do 1º semestre para prever o 2º): rho +0.98 — é o teto do que qualquer modelo sem histórico pode sonhar.

## (c) Mesmas variáveis prevendo outros resultados (mediana 12 m, LOO)

| desfecho          |   n |   R2_fora_amostra | IC95           |    rho |   coef_m2 |   coef_renda |   coef_pop |
|:------------------|----:|------------------:|:---------------|-------:|----------:|-------------:|-----------:|
| faturamento       |  54 |             0.393 | [+0.11; +0.59] |  0.623 |     0.696 |        0.408 |     -0.139 |
| alunos (ativos)   |  54 |             0.24  | [-0.08; +0.44] |  0.533 |     0.585 |        0.21  |     -0.067 |
| alunos/m²         |  54 |             0.088 | [-0.22; +0.29] |  0.352 |    -0.415 |        0.21  |     -0.067 |
| receita por aluno |  54 |             0.302 | [-0.01; +0.53] |  0.578 |     0.112 |        0.198 |     -0.072 |
| % agregador       |  53 |             0.007 | [-0.28; +0.20] |  0.24  |    -0.18  |       -0.557 |      7.86  |
| churn %           |  54 |             0.38  | [+0.17; +0.56] |  0.65  |    -0.948 |       -1.511 |     -0.286 |
| NPS               |  54 |            -0.129 | [-0.36; +0.00] | -0.129 |    12.43  |       -7.339 |      2.65  |
| visitas/mês       |  54 |             0.109 | [-0.23; +0.36] |  0.397 |     0.544 |       -0.062 |     -0.184 |
| conversão %       |  54 |             0.075 | [-0.20; +0.23] |  0.303 |   -11.234 |       -3.979 |     -2.187 |

(desfechos com escala proporcional em log; churn, % agregador, conversão e NPS em nível)