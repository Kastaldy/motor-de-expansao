Oferta: 24,273 academias; capacidade real 1201, mediana da rede 427, cadeia sem dado 3320, independentes 19325.
Unidades no modelo: 54 (metragem + faturamento 12 m + isócrona; coordenada não baixa).

Premissas estressadas (2.000 sorteios): {"taxa": [0.1, 0.25], "elast_renda": [0.0, 1.0], "elast_ticket": [0.0, 0.6], "proxy_indep": [150, 800], "proxy_cadeia": [1000, 2500], "dens_ref": [1.2, 2.2], "peso_cresc": [0.0, 0.3]}; pesos dos catchments (carro 5, carro 10, a pé 15) sorteados; renda de referência R$ 1,971; receita por aluno de referência R$ 84.

**Leitura por unidade:** abaixo da rede para o potencial (robusto) 21, acima da rede para o potencial (robusto) 20, depende das premissas 13
Amplitude do rank (p90 − p10) mediana: 14 posições em 54.

**10 com maior aproveitamento**

| unidade_id              |   metragem |   fat_12m |   fat_esperado_mediana |   aprov_fat_mediana |   aprov_fat_p10 |   aprov_fat_p90 |   frac_acima_de_1 |   rank_p10 |   rank_p90 | leitura                                  |
|:------------------------|-----------:|----------:|-----------------------:|--------------------:|----------------:|----------------:|------------------:|-----------:|-----------:|:-----------------------------------------|
| botanic-mall-df         |       1206 |    286300 |                  83993 |                2.55 |            1.84 |            3.98 |              1    |        1   |         11 | acima da rede para o potencial (robusto) |
| botafogo-rj             |       1230 |    683305 |                 208276 |                2.45 |            1.53 |            3.86 |              1    |        1   |         16 | acima da rede para o potencial (robusto) |
| jardim-botanico-df      |       1000 |    307447 |                  98989 |                2.38 |            1.5  |            3.82 |              1    |        2   |         17 | acima da rede para o potencial (robusto) |
| santa-maria-df          |       1400 |    235763 |                  84799 |                2.07 |            1.52 |            2.85 |              1    |        1   |         15 | acima da rede para o potencial (robusto) |
| sorriso-mt              |        940 |    179167 |                  68280 |                2.01 |            1.48 |            2.47 |              1    |        2.9 |         16 | acima da rede para o potencial (robusto) |
| cotia-sp                |        750 |    152460 |                  56221 |                2    |            1.54 |            2.64 |              1    |        2   |         14 | acima da rede para o potencial (robusto) |
| valparaiso-go           |       1800 |    280943 |                 104993 |                1.99 |            1.5  |            2.55 |              1    |        3   |         15 | acima da rede para o potencial (robusto) |
| lago-norte-df           |       1800 |    338998 |                 131502 |                1.93 |            1.16 |            3.29 |              0.97 |        3   |         24 | acima da rede para o potencial (robusto) |
| vila-guanabara-sc       |       1500 |    245042 |                 101973 |                1.81 |            1.6  |            2.01 |              1    |        7   |         14 | acima da rede para o potencial (robusto) |
| arapoanga-planaltina-df |       1500 |    204890 |                  85720 |                1.77 |            1.28 |            2.55 |              1    |        3   |         20 | acima da rede para o potencial (robusto) |

**10 com menor aproveitamento**

| unidade_id        |   metragem |   fat_12m |   fat_esperado_mediana |   aprov_fat_mediana |   aprov_fat_p10 |   aprov_fat_p90 |   frac_acima_de_1 |   rank_p10 |   rank_p90 | leitura                                   |
|:------------------|-----------:|----------:|-----------------------:|--------------------:|----------------:|----------------:|------------------:|-----------:|-----------:|:------------------------------------------|
| plaza-sul-sp      |       1500 |  250114   |                 323907 |                0.58 |            0.37 |            0.9  |              0.04 |         31 |         49 | abaixo da rede para o potencial (robusto) |
| jundiai-sp        |       1920 |  132167   |                 179491 |                0.55 |            0.47 |            0.65 |              0    |         41 |         47 | abaixo da rede para o potencial (robusto) |
| aguas-claras-df   |       1700 |  138611   |                 200247 |                0.53 |            0.34 |            0.74 |              0    |         39 |         50 | abaixo da rede para o potencial (robusto) |
| setor-oeste-go    |       1700 |  128115   |                 202337 |                0.48 |            0.32 |            0.67 |              0    |         42 |         51 | abaixo da rede para o potencial (robusto) |
| aclimacao-sp      |       1468 |  170501   |                 291165 |                0.44 |            0.28 |            0.68 |              0    |         42 |         52 | abaixo da rede para o potencial (robusto) |
| carapicuiba-sp    |       1100 |   70006.3 |                 127999 |                0.41 |            0.28 |            0.6  |              0    |         41 |         52 | abaixo da rede para o potencial (robusto) |
| augusta-sp        |       1100 |   81025   |                 148913 |                0.4  |            0.25 |            0.67 |              0    |         42 |         54 | abaixo da rede para o potencial (robusto) |
| brasilandia-sp    |       1400 |   78270.7 |                 194188 |                0.3  |            0.24 |            0.4  |              0    |         49 |         54 | abaixo da rede para o potencial (robusto) |
| campo-limpo-sp    |       1220 |   53568   |                 132416 |                0.3  |            0.22 |            0.42 |              0    |         48 |         54 | abaixo da rede para o potencial (robusto) |
| vila-guilherme-sp |       1466 |   87624.6 |                 232349 |                0.29 |            0.23 |            0.33 |              0    |         51 |         54 | abaixo da rede para o potencial (robusto) |

## Testes

- Esperado x real (faturamento): rho +0.22 (entre sorteios p10–p90: +0.01 a +0.37); por m²: -0.01. Sem correlação, o aproveitamento é dominado pelo real e o ranking vira o de faturamento/m² com ajuste de premissas.
- Aproveitamento x faturamento/m²: rho +0.75.
- Metragem x faturamento em praça boa (renda+pop acima da mediana): rho +0.51 (n=28) contra +0.36 fora (n=26); diferença +0.15 IC95 [-0.33; +0.63].
- Metragem x faturamento em concorrência per capita abaixo da mediana: rho +0.53 (n=27) contra +0.32 fora (n=27); diferença +0.21 IC95 [-0.27; +0.70].
- Vagas x faturamento: rho +0.53; vagas x faturamento/m²: +0.24 (n=54).
- Crescimento cres_hex_taxa (n=49): x faturamento/m² rho -0.04; x aproveitamento rho +0.25; x churn +0.37
- Crescimento dim_renda_pct (n=47): x faturamento/m² rho -0.16; x aproveitamento rho -0.01; x churn +0.30
- Crescimento dim_empresas_por1k (n=47): x faturamento/m² rho -0.16; x aproveitamento rho -0.41; x churn -0.25
- Crescimento dim_emprego_pct (n=47): x faturamento/m² rho +0.25; x aproveitamento rho +0.40; x churn +0.14
- Crescimento dim_pop_pct (n=47): x faturamento/m² rho +0.16; x aproveitamento rho +0.48; x churn +0.08
- Crescimento dim_media (n=47): x faturamento/m² rho +0.07; x aproveitamento rho +0.42; x churn +0.31

## Qual premissa mais mexe no resultado

| premissa              | faixa         |   rho_rank_extremos |   unidades_que_trocam_de_lado_de_1 |
|:----------------------|:--------------|--------------------:|-----------------------------------:|
| taxa                  | 0.1–0.25      |               1     |                                  0 |
| elast_renda           | 0.0–1.0       |               0.562 |                                 12 |
| elast_ticket          | 0.0–0.6       |               0.822 |                                 10 |
| proxy_indep           | 150–800       |               0.947 |                                  6 |
| proxy_cadeia          | 1000–2500     |               0.982 |                                  6 |
| dens_ref              | 1.2–2.2       |               0.993 |                                  4 |
| peso_cresc            | 0.0–0.3       |               0.966 |                                  4 |
| catchment só carro 5  | vs peso igual |               0.963 |                                  2 |
| catchment só carro 10 | vs peso igual |               0.909 |                                  8 |
| catchment só a pé 15  | vs peso igual |               0.83  |                                 10 |