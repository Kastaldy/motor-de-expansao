# Por que a previsão de Manaus ficou baixa — diagnóstico (EXPLORATÓRIO)

- Moradores por domicílio na área de 10 min: Manaus 3.27; rede (mediana das isócronas) 2.66 (min 2.15, máx 3.28).
- Renda per capita: Manaus R$ 1,073 × mediana da rede R$ 1,953 (-45%).
- Renda domiciliar: Manaus R$ 3,511 × mediana da rede R$ 5,237 (-33%).
- Correlação per capita × domiciliar nas unidades (Spearman): +0.99.

## v2 (renda per capita)

R² LOO (treino) 0.257; teste: erro típico 22.1%, viés -0.6%, Spearman +0.69. **Manaus: R$ 247 mil/mês** (~2,107 alunos).

| variável | coeficiente | Manaus | unidade típica do treino | contribuição para Manaus × típica |
|---|---|---|---|---|
| l_m2 | +0.544 | 2,000 | 1,500 | +17% |
| l_renda | +0.277 | 1,073 | 2,055 | -16% |
| l_pop | -0.156 | 525,532 | 397,853 | -4% |
| mr_M2 | +0.221 | 0.00 | 0.26 | -6% |
| mr_M3 | +0.003 | 0.00 | 0.13 | -0% |
| mr_outras | +0.133 | 1.00 | 0.18 | +12% |
| studios | +0.229 | 1.00 | 0.59 | +10% |

## v2 (renda domiciliar)

R² LOO (treino) 0.264; teste: erro típico 22.1%, viés +0.3%, Spearman +0.69. **Manaus: R$ 261 mil/mês** (~2,234 alunos).

| variável | coeficiente | Manaus | unidade típica do treino | contribuição para Manaus × típica |
|---|---|---|---|---|
| l_m2 | +0.578 | 2,000 | 1,500 | +18% |
| l_renda_dom | +0.317 | 3,511 | 6,080 | -16% |
| l_pop | -0.149 | 525,532 | 397,853 | -4% |
| mr_M2 | +0.244 | 0.00 | 0.26 | -6% |
| mr_M3 | +0.022 | 0.00 | 0.13 | -0% |
| mr_outras | +0.154 | 1.00 | 0.18 | +14% |
| studios | +0.227 | 1.00 | 0.59 | +10% |

