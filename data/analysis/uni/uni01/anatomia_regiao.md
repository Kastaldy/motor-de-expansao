# Seguimento: quanto do erro é região? (exploratório, desenhado depois de ver a anatomia)

| modelo | faturamento R² LOO | alunos R² LOO | ticket R² LOO |
|---|---|---|---|
| base | 0.31 | 0.12 | 0.15 |
| base + SP | 0.35 | 0.29 | 0.19 |
| base + SP + DF | 0.33 | 0.25 | 0.21 |
| base + metro (4 metros com ≥ 2 unid.) | 0.40 | 0.37 | -0.09 |
| base + política de agregador da UF | 0.35 | 0.18 | 0.09 |
| base + SP + política de agregador da UF | 0.33 | 0.21 | 0.17 |
| base + preço Gold | 0.32 | 0.13 | 0.09 |
| base + SP + preço Gold | 0.35 | 0.27 | 0.13 |

Preço Gold mediano: SP 147, DF 137, outros 147. % agregador mediano (2025): SP 53%, DF 27%, outros 43%.

## Correlações do erro dentro de cada região (Spearman)

| variável | erro | toda a amostra | só SP (N=16) | só DF (N=15) |
|---|---|---|---|---|
| preço Gold | alunos | +0.47* | +0.63* | +0.03 |
| preço Gold | ticket | -0.13 | +0.17 | -0.29 |
| % agregador | alunos | +0.34* | +0.36 | -0.11 |
| % agregador | ticket | -0.61* | -0.76* | -0.15 |
| fração de independentes | alunos | +0.31 | +0.06 | -0.15 |
| fração de independentes | ticket | -0.51* | -0.30 | -0.54* |
| escritórios a pé | alunos | +0.32* | +0.53* | +0.03 |
| escritórios a pé | ticket | -0.27 | +0.14 | -0.52 |
| sobreposição com outra Ultra | alunos | -0.02 | +0.22 | -0.12 |
| sobreposição com outra Ultra | ticket | +0.39* | +0.44 | -0.15 |

\* p < 0,05 sem correção. Com N = 15–16, só correlações acima de ~0,5 passam de 5%.
