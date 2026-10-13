# Anatomia dos erros do modelo base (maduras de 2025)

Modelo base: log faturamento ~ log m² + log renda c10 + log pop c10. N = 39. Erro = real / previsto − 1, fora da amostra (LOO).

- Quanto a base explica, fora da amostra: faturamento R² 0.31; **alunos R² 0.12; ticket R² 0.15**.
- Erro típico (mediana do |erro|): 25%. Da variância do erro de faturamento, alunos respondem por 92% e ticket por 19% (covariância -11%).

## Unidades com maior erro

| unidade | UF | m² | fat. real | previsto | erro | por alunos | por ticket | Gold | % agreg. | churn | idade | rank jan–set |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| VILA MARIANA | SP | 1,500 | 527,883 | 255,682 | **+106%** | +84% | +12% | 167 | 52% | 5.1 | 46 | 1.00 |
| SUZANO | SP | 1,350 | 326,312 | 175,273 | **+86%** | +103% | -8% | 147 | 63% | 8.0 | 14 | 2.00  ⚠ -52% de ativos abr-ago/26 (agregadores 2.964 -> 919) |
| SANTOS | SP | 2,000 | 523,895 | 298,270 | **+76%** | +32% | +33% | 147 | 43% | 5.8 | 42 | 3.00 |
| PRAIA GRANDE | SP | 2,500 | 496,559 | 306,143 | **+62%** | +117% | -25% | 167 | 77% | 7.4 | 16 | 4.00 |
| VILA MATILDE | SP | 1,500 | 297,143 | 194,733 | **+53%** | +36% | +12% | 157 | 53% | 8.4 | 16 | 5.00 |
| PLAZA SUL | SP | 1,500 | 343,958 | 225,600 | **+52%** | +25% | +22% | 157 | 34% | 3.9 | 46 | 6.00 |
| SANTA MARIA | DF | 1,400 | 314,158 | 208,117 | **+51%** | +33% | +13% | 137 | 30% | 8.2 | 16 | 8.00 |
| SOBRADINHO | DF | 1,400 | 191,808 | 283,680 | **-32%** | -31% | -3% | 137 | 30% | 6.3 | 24 | 32.00 |
| CARAPICUIBA | SP | 1,100 | 115,276 | 172,133 | **-33%** | -32% | -1% | 127 | 41% | 10.3 | 16 | 31.00 |
| BRASILANDIA | SP | 1,400 | 120,779 | 183,471 | **-34%** | -20% | -17% | 137 | 53% | 10.3 | 36 | 33.00  ⚠ vale de receita -45% out/25-mai/26 com ativos estaveis |
| JUNDIAI | SP | 1,920 | 184,198 | 290,982 | **-37%** | -25% | -16% | 147 | 56% | 5.6 | 46 | 35.00 |
| CAMPO LIMPO | SP | 1,220 | 95,042 | 159,129 | **-40%** | -32% | -12% | 117 | 55% | 8.4 | 30 | 34.00 |
| LAGO SUL | DF | 2,000 | 294,004 | 495,970 | **-41%** | -30% | -15% | 147 | 41% | 4.5 | 44 | 36.00  ⚠ isocrona_pe_degenerada (0,16 km2): atributos a pe anulados |
| SETOR OESTE | GO | 1,700 | 140,035 | 284,211 | **-51%** | -48% | -6% | 147 | 32% | 4.9 | 28 | 37.00 |

(as 7 primeiras linhas faturam acima do previsto; as 7 últimas, abaixo. 'por alunos' e 'por ticket' somam o erro, em log.)

## O erro anda junto com o quê? (Spearman; lista fixada antes; exploratório)

Com 22 variáveis e N ≈ 39, espera-se ~1 correlação com p < 0,05 por acaso.

| variável | N | erro do faturamento | erro de alunos | erro de ticket |
|---|---|---|---|---|
| preço do plano Gold | 39 | +0.31 | +0.47* | -0.13 |
| tier Wellhub (cadastro) | 39 | +0.21 | +0.23 | +0.12 |
| escritórios a pé (F1) | 38 | +0.15 | +0.32* | -0.27 |
| fração de independentes c10 | 39 | +0.15 | +0.31 | -0.51* |
| churn (2025) | 39 | -0.14 | -0.03 | -0.26 |
| renda a pé 15 min | 38 | +0.13 | +0.26 | -0.12 |
| comércio a pé (F2) | 38 | +0.12 | +0.28 | -0.27 |
| saturação (alunos conc./mil hab c10) | 39 | +0.09 | +0.11 | +0.08 |
| crescimento do hexágono | 36 | -0.08 | -0.15 | +0.06 |
| sobreposição com outra Ultra (c10) | 39 | +0.07 | -0.02 | +0.39* |
| retenção EB 60d (Lifetime) | 39 | -0.06 | -0.08 | -0.01 |
| crescimento do município | 39 | -0.05 | -0.11 | -0.08 |
| população a pé 15 min | 38 | -0.04 | +0.01 | -0.03 |
| % agregador (2025) | 39 | +0.04 | +0.34* | -0.61* |
| densidade (hab/km² c10) | 39 | +0.04 | +0.08 | -0.03 |
| vagas por 1.000 m² | 39 | +0.03 | -0.11 | +0.29 |
| metragem (m²) | 39 | -0.03 | -0.04 | +0.08 |
| em shopping | 38 | +0.03 | +0.12 | -0.08 |
| outras Ultras na isócrona c10 | 39 | +0.02 | -0.07 | +0.43* |
| tem TotalPass (cadastro) | 39 | -0.02 | -0.01 | -0.06 |
| idade média (meses, 2025) | 39 | +0.01 | +0.14 | -0.16 |
| nº academias c10 | 39 | -0.01 | +0.07 | +0.01 |

\* p < 0,05 sem correção.

## Quartil de cima × de baixo do erro (medianas)

| variável | acima do previsto (quartil sup.) | todas | abaixo do previsto (quartil inf.) |
|---|---|---|---|
| preço do plano Gold | 147 | 147 | 142 |
| tier Wellhub (cadastro) | 3.50 | 3.00 | 3.00 |
| tem TotalPass (cadastro) | 1.00 | 1.00 | 1.00 |
| % agregador (2025) | 0.53 | 0.41 | 0.47 |
| churn (2025) | 7.39 | 7.14 | 7.78 |
| idade média (meses, 2025) | 23.75 | 24.50 | 29.50 |
| fração de independentes c10 | 0.69 | 0.62 | 0.65 |
| saturação (alunos conc./mil hab c10) | 194 | 196 | 146 |
| nº academias c10 | 87.00 | 82.00 | 78.50 |
| sobreposição com outra Ultra (c10) | 0.24 | 0.38 | 0.00 |
| outras Ultras na isócrona c10 | 1.50 | 2.00 | 1.00 |
| em shopping | 0.00 | 0.00 | 0.00 |
| escritórios a pé (F1) | -7.20 | -7.41 | -8.84 |
| comércio a pé (F2) | -5.68 | -5.90 | -6.94 |
| densidade (hab/km² c10) | 9,281 | 4,915 | 6,009 |
| população a pé 15 min | 22,331 | 17,493 | 19,108 |
| renda a pé 15 min | 3,303 | 2,912 | 2,030 |
| crescimento do município | 51.00 | 53.00 | 53.00 |
| crescimento do hexágono | 4.80 | 5.35 | 6.05 |
| vagas por 1.000 m² | 37.86 | 36.46 | 36.09 |
| retenção EB 60d (Lifetime) | 0.92 | 0.93 | 0.93 |
| metragem (m²) | 1,500 | 1,500 | 1,483 |

## Erro por UF (mediana)

| UF | N | erro mediano |
|---|---|---|
| SP | 16 | +21% |
| DF | 15 | -5% |
| PR | 2 | -9% |
| GO | 2 | -36% |
| MT | 1 | +1% |
| ES | 1 | +42% |
| RJ | 1 | -5% |
| RS | 1 | -25% |
