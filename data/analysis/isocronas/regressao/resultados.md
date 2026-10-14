# Regressão com validação fora da amostra

Variáveis fixadas antes de rodar (docstring de `17_regressao.py`). Área de referência: isócrona de carro de 10 min. Desfechos em log.

## R1 alunos Ultra + Engenharia do Corpo (N = 89, {'ultra': 53, 'engenharia_do_corpo': 36})

| modelo                       |   R2_LOO_ols |   R2_LOO_ridge |   R2_UF_ridge | IC95_R2_LOO_ridge   |
|:-----------------------------|-------------:|---------------:|--------------:|:--------------------|
| B0 só rede/intercepto        |        0.066 |          0.06  |         0.064 | [-0.09; +0.18]      |
| B1 + metragem                |        0.275 |          0.275 |         0.276 | [+0.11; +0.40]      |
| B2 + renda                   |        0.264 |          0.265 |         0.266 | [+0.10; +0.39]      |
| B3 + população               |        0.25  |          0.248 |         0.217 | [+0.07; +0.38]      |
| B4 + concorrência            |        0.234 |          0.235 |         0.179 | [+0.06; +0.37]      |
| B5 + metragem x concorrência |        0.239 |          0.245 |         0.203 | [+0.07; +0.37]      |
| B6 + canibalização           |        0.221 |          0.242 |         0.163 | [+0.09; +0.36]      |
| B7 completo (+ crescimento)  |        0.121 |          0.178 |         0.023 | [-0.02; +0.31]      |

Ganho de cada passo (R² LOO ridge, bootstrap pareado):

- + metragem: +0.215 IC95 [+0.070; +0.347]
- + renda: -0.011 IC95 [-0.037; +0.018]
- + população: -0.017 IC95 [-0.034; -0.003]
- + concorrência: -0.013 IC95 [-0.057; +0.024]
- + metragem x concorrência: +0.009 IC95 [-0.057; +0.071]
- + canibalização: -0.002 IC95 [-0.017; +0.014]
- completo (+ crescimento): -0.064 IC95 [-0.176; +0.010]

Pesos (OLS completo; peso padronizado = efeito de +1 desvio-padrão da variável, em desvios-padrão do desfecho; coef_bruto em log):

| variavel                |   peso_padronizado |   IC95_baixo |   IC95_alto | exclui_zero   |   coef_bruto |
|:------------------------|-------------------:|-------------:|------------:|:--------------|-------------:|
| ultra                   |             -0.474 |       -0.682 |      -0.272 | True          |       -0.376 |
| log_metragem            |              0.395 |        0.197 |       0.608 | True          |        0.526 |
| metragem_x_concorrencia |             -0.256 |       -0.558 |       0.04  | False         |       -0.552 |
| cresc_municipal         |             -0.109 |       -0.363 |       0.109 | False         |       -0.005 |
| log_renda               |              0.102 |       -0.236 |       0.421 | False         |        0.076 |
| cresc_hex               |              0.065 |       -0.445 |       0.229 | False         |        0.003 |
| log_pop                 |             -0.063 |       -0.304 |       0.218 | False         |       -0.031 |
| concorrencia            |              0.062 |       -0.352 |       0.386 | False         |        0.047 |
| canibalizacao           |             -0.046 |       -0.291 |       0.202 | False         |       -0.004 |

## R2 faturamento Ultra (Financeiro ago/26) (N = 54)

| modelo                       |   R2_LOO_ols |   R2_LOO_ridge |   R2_UF_ridge | IC95_R2_LOO_ridge   |
|:-----------------------------|-------------:|---------------:|--------------:|:--------------------|
| B0 só rede/intercepto        |       -0.038 |         -0.038 |        -0.11  | [-0.15; -0.04]      |
| B1 + metragem                |        0.168 |          0.17  |         0.108 | [-0.03; +0.31]      |
| B2 + renda                   |        0.41  |          0.412 |         0.372 | [+0.17; +0.55]      |
| B3 + população               |        0.447 |          0.445 |         0.416 | [+0.19; +0.62]      |
| B4 + concorrência            |        0.389 |          0.395 |         0.342 | [+0.06; +0.60]      |
| B5 + metragem x concorrência |        0.379 |          0.386 |         0.285 | [-0.01; +0.60]      |
| B6 + canibalização           |        0.388 |          0.4   |         0.323 | [+0.05; +0.60]      |
| B7 completo (+ crescimento)  |        0.308 |          0.317 |         0.188 | [-0.03; +0.53]      |

Ganho de cada passo (R² LOO ridge, bootstrap pareado):

- + metragem: +0.208 IC95 [+0.036; +0.369]
- + renda: +0.242 IC95 [+0.032; +0.397]
- + população: +0.033 IC95 [-0.061; +0.124]
- + concorrência: -0.050 IC95 [-0.160; +0.013]
- + metragem x concorrência: -0.009 IC95 [-0.091; +0.052]
- + canibalização: +0.014 IC95 [-0.028; +0.063]
- completo (+ crescimento): -0.082 IC95 [-0.167; -0.014]

Pesos (OLS completo; peso padronizado = efeito de +1 desvio-padrão da variável, em desvios-padrão do desfecho; coef_bruto em log):

| variavel                |   peso_padronizado |   IC95_baixo |   IC95_alto | exclui_zero   |   coef_bruto |
|:------------------------|-------------------:|-------------:|------------:|:--------------|-------------:|
| log_renda               |              0.644 |        0.219 |       1.078 | True          |        0.496 |
| log_metragem            |              0.367 |        0.149 |       0.614 | True          |        0.66  |
| log_pop                 |             -0.3   |       -0.655 |      -0.082 | True          |       -0.174 |
| metragem_x_concorrencia |             -0.202 |       -0.484 |       0.021 | False         |       -0.997 |
| canibalizacao           |              0.191 |       -0.054 |       0.46  | False         |        0.02  |
| concorrencia            |             -0.147 |       -0.639 |       0.426 | False         |       -0.159 |
| cresc_hex               |              0.123 |       -0.397 |       0.29  | False         |        0.005 |
| cresc_municipal         |              0.013 |       -0.277 |       0.255 | False         |        0.001 |