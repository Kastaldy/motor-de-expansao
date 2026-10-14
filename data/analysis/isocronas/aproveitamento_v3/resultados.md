# Aproveitamento v3 — interação metragem x concorrência e crescimento na conta

Ultra, faturamento do Financeiro de agosto/2026 (Guarujá corrigido). N = 54.

| variante                       |   rho_esperado_x_real | ic95           |   rho_por_m2 | rho_sorteios_p10_p90   |   unidades_leitura_robusta |   aprov_x_cres_mun |
|:-------------------------------|----------------------:|:---------------|-------------:|:-----------------------|---------------------------:|-------------------:|
| v2 (sem teto, sem crescimento) |                 0.374 | [+0.11; +0.58] |        0.13  | +0.07 a +0.54          |                         37 |              0.41  |
| + teto de capacidade           |                 0.439 | [+0.19; +0.64] |        0.17  | +0.17 a +0.59          |                         43 |              0.406 |
| + crescimento                  |                 0.393 | [+0.12; +0.60] |        0.164 | +0.04 a +0.56          |                         36 |              0.241 |
| v3: teto + crescimento         |                 0.471 | [+0.22; +0.66] |        0.23  | +0.15 a +0.59          |                         41 |              0.168 |
- ganho de aderência de '+ teto de capacidade' sobre v2: +0.065 IC95 [+0.005; +0.129]
- ganho de aderência de '+ crescimento' sobre v2: +0.019 IC95 [-0.051; +0.096]
- ganho de aderência de 'v3: teto + crescimento' sobre v2: +0.097 IC95 [-0.001; +0.203]

Checagem com a mediana de 12 meses (v3): esperado x real rho +0.44; concordância do aproveitamento agosto x 12 m +0.96.

## Leitura por unidade (v3)

{'abaixo (robusto)': 21, 'acima (robusto)': 20, 'depende das premissas': 13}

| pid                     |   metragem |     real |   esperado_mediana |   aprov_mediana |   aprov_p10 |   aprov_p90 |   frac_acima | leitura               |
|:------------------------|-----------:|---------:|-------------------:|----------------:|------------:|------------:|-------------:|:----------------------|
| botafogo-rj             |       1230 | 708987   |             165909 |            2.15 |        1.58 |        3.15 |         1    | acima (robusto)       |
| botanic-mall-df         |       1206 | 337898   |              80287 |            2.11 |        1.63 |        3.24 |         1    | acima (robusto)       |
| jardim-botanico-df      |       1000 | 342181   |              88344 |            1.95 |        1.39 |        3.02 |         1    | acima (robusto)       |
| lago-norte-df           |       1800 | 483304   |             130573 |            1.83 |        1.22 |        2.89 |         0.98 | acima (robusto)       |
| guaruja-sp              |        943 | 217526   |              62313 |            1.77 |        1.35 |        2.31 |         1    | acima (robusto)       |
| santa-maria-df          |       1400 | 281681   |              80557 |            1.77 |        1.36 |        2.38 |         1    | acima (robusto)       |
| arapoanga-planaltina-df |       1500 | 258679   |              81629 |            1.59 |        1.17 |        2.23 |         0.99 | acima (robusto)       |
| noroeste-df             |       2000 | 703049   |             243423 |            1.48 |        0.96 |        2.39 |         0.87 | acima (robusto)       |
| cariacica-es            |       1300 | 361856   |             126541 |            1.44 |        1.13 |        1.9  |         0.98 | acima (robusto)       |
| taubate-sp              |       1600 | 284672   |              98338 |            1.43 |        1.26 |        1.71 |         1    | acima (robusto)       |
| lago-sul-df             |       2000 | 312265   |             120729 |            1.31 |        0.8  |        2.6  |         0.74 | depende das premissas |
| cotia-sp                |        750 | 156290   |              59287 |            1.31 |        1.04 |        1.72 |         0.95 | acima (robusto)       |
| valparaiso-go           |       1800 | 324878   |             123693 |            1.31 |        1    |        1.72 |         0.9  | acima (robusto)       |
| santos-sp               |       2000 | 508764   |             196478 |            1.3  |        1.05 |        1.64 |         0.96 | acima (robusto)       |
| vila-mariana-sp         |       1500 | 535428   |             210394 |            1.27 |        0.91 |        1.9  |         0.81 | acima (robusto)       |
| cambui-campinas-sp      |        880 | 195442   |              79830 |            1.25 |        1    |        1.52 |         0.91 | acima (robusto)       |
| suzano-sp               |       1350 | 188999   |              76109 |            1.24 |        0.99 |        1.64 |         0.89 | acima (robusto)       |
| asa-norte-df            |       1700 | 490309   |             200957 |            1.21 |        0.8  |        1.94 |         0.73 | depende das premissas |
| sobradinho-df           |       1400 | 246075   |             104570 |            1.18 |        1.01 |        1.39 |         0.92 | acima (robusto)       |
| praia-grande-sp         |       2500 | 478570   |             204295 |            1.18 |        1.05 |        1.33 |         0.98 | acima (robusto)       |
| paranoa-parque-df       |       2000 | 238627   |             102996 |            1.18 |        0.82 |        1.73 |         0.71 | depende das premissas |
| recanto-das-emas-df     |       1100 | 177003   |              77761 |            1.15 |        0.88 |        1.49 |         0.75 | depende das premissas |
| serra-es                |       2200 | 404926   |             177889 |            1.14 |        0.92 |        1.6  |         0.75 | depende das premissas |
| vila-guanabara-sc       |       1500 | 252989   |             113872 |            1.12 |        1.01 |        1.26 |         0.93 | acima (robusto)       |
| unai-mg                 |        800 | 149523   |              66764 |            1.12 |        0.96 |        1.36 |         0.82 | acima (robusto)       |
| sorriso-mt              |        940 | 168558   |              80037 |            1.05 |        0.85 |        1.33 |         0.62 | depende das premissas |
| taguatinga-df           |       1356 | 202244   |              95958 |            1.05 |        0.96 |        1.2  |         0.73 | depende das premissas |
| campo-largo-pr          |       1500 | 256193   |             121477 |            1.03 |        0.85 |        1.32 |         0.6  | depende das premissas |
| cruzeiro-df             |       1500 | 426860   |             225555 |            0.95 |        0.66 |        1.45 |         0.42 | depende das premissas |
| poa-barra-sul-rs        |       2800 | 327613   |             176835 |            0.94 |        0.68 |        1.4  |         0.39 | depende das premissas |
| ceilandia-df            |       1500 | 196523   |             107925 |            0.91 |        0.72 |        1.16 |         0.31 | depende das premissas |
| ceilandia-sul-df        |       1500 | 172948   |             100455 |            0.86 |        0.73 |        1.05 |         0.17 | abaixo (robusto)      |
| centro-comendador-pr    |       1352 | 209218   |             122500 |            0.86 |        0.67 |        1.15 |         0.26 | depende das premissas |
| augusta-sp              |       1100 | 211770   |             126905 |            0.83 |        0.59 |        1.27 |         0.29 | depende das premissas |
| mooca-sp                |       1300 | 238207   |             151872 |            0.79 |        0.66 |        0.98 |         0.08 | abaixo (robusto)      |
| vicente-pires-df        |       1689 | 276925   |             178611 |            0.78 |        0.63 |        1    |         0.09 | abaixo (robusto)      |
| cabo-frio-rj            |       1513 | 246548   |             160952 |            0.77 |        0.62 |        0.97 |         0.07 | abaixo (robusto)      |
| cpa-mt                  |       1500 | 180516   |             118519 |            0.77 |        0.64 |        0.93 |         0.03 | abaixo (robusto)      |
| plaza-sul-sp            |       1500 | 333590   |             226897 |            0.74 |        0.55 |        1.01 |         0.11 | abaixo (robusto)      |
| taguatinga-sul-df       |       1400 | 178132   |             123978 |            0.72 |        0.65 |        0.83 |         0    | abaixo (robusto)      |
| aguas-claras-df         |       1700 | 248765   |             181137 |            0.71 |        0.54 |        0.93 |         0.04 | abaixo (robusto)      |
| jundiai-sp              |       1920 | 241897   |             175482 |            0.7  |        0.63 |        0.78 |         0    | abaixo (robusto)      |
| aguas-lindas-go         |       1500 | 148987   |             107543 |            0.69 |        0.46 |        1.06 |         0.15 | abaixo (robusto)      |
| samambaia-df            |       1500 | 167094   |             122533 |            0.69 |        0.62 |        0.78 |         0    | abaixo (robusto)      |
| mococa-sp               |       1311 | 118203   |              86029 |            0.68 |        0.55 |        0.91 |         0.03 | abaixo (robusto)      |
| vila-matilde-sp         |       1500 | 229839   |             178623 |            0.66 |        0.5  |        0.84 |         0    | abaixo (robusto)      |
| jardim-apura-sp         |       1200 | 117867   |              96820 |            0.62 |        0.45 |        0.87 |         0.03 | abaixo (robusto)      |
| alexandrina-go          |       1400 | 151339   |             131263 |            0.58 |        0.48 |        0.72 |         0    | abaixo (robusto)      |
| aclimacao-sp            |       1468 | 236740   |             213706 |            0.55 |        0.42 |        0.79 |         0.01 | abaixo (robusto)      |
| carapicuiba-sp          |       1100 | 108941   |             111583 |            0.49 |        0.37 |        0.66 |         0    | abaixo (robusto)      |
| vila-guilherme-sp       |       1466 | 156928   |             172549 |            0.46 |        0.39 |        0.54 |         0    | abaixo (robusto)      |
| campo-limpo-sp          |       1220 |  87594.1 |             103873 |            0.43 |        0.33 |        0.55 |         0    | abaixo (robusto)      |
| setor-oeste-go          |       1700 | 154821   |             189530 |            0.42 |        0.32 |        0.54 |         0    | abaixo (robusto)      |
| brasilandia-sp          |       1400 | 112414   |             138665 |            0.41 |        0.33 |        0.5  |         0    | abaixo (robusto)      |

**Mudaram de leitura entre v2 e v3 (14):**

| pid              | leitura_v2            |   aprov_mediana_v2 | leitura_v3            |   aprov_mediana_v3 |
|:-----------------|:----------------------|-------------------:|:----------------------|-------------------:|
| noroeste-df      | depende das premissas |               1.43 | acima (robusto)       |               1.48 |
| sorriso-mt       | acima (robusto)       |               1.38 | depende das premissas |               1.05 |
| serra-es         | acima (robusto)       |               1.28 | depende das premissas |               1.14 |
| campo-largo-pr   | acima (robusto)       |               1.26 | depende das premissas |               1.03 |
| sobradinho-df    | depende das premissas |               1.13 | acima (robusto)       |               1.18 |
| taguatinga-df    | acima (robusto)       |               1.12 | depende das premissas |               1.05 |
| cariacica-es     | depende das premissas |               1.08 | acima (robusto)       |               1.44 |
| vila-mariana-sp  | depende das premissas |               1.06 | acima (robusto)       |               1.27 |
| santos-sp        | depende das premissas |               1.02 | acima (robusto)       |               1.3  |
| ceilandia-sul-df | depende das premissas |               0.89 | abaixo (robusto)      |               0.86 |
| cpa-mt           | depende das premissas |               0.88 | abaixo (robusto)      |               0.77 |
| cabo-frio-rj     | depende das premissas |               0.88 | abaixo (robusto)      |               0.77 |
| aguas-lindas-go  | depende das premissas |               0.85 | abaixo (robusto)      |               0.69 |
| poa-barra-sul-rs | abaixo (robusto)      |               0.74 | depende das premissas |               0.94 |