# BLK-UNI-05C v1.2 — confirmação ampliada (proporção de agregadores nos ativos)

Protocolo `protocolo_mix.md` §10 (SHA-256 `9a8e3374240b1b2e…`). Rodado uma vez.

- Exploração (2025): 37 unidades (as mesmas da v1.1).
- Confirmação ampliada (`mes_vida` ≥ 6): **19 unidades** (≥ 9: 17; ≥ 12, a da v1.1: 13); mês de vida mediano nos meses usados: 12 (de 7 a 16).
- Proporção observada na confirmação ampliada: mediana 43% (exploração: 41%).

Erro = erro médio absoluto em pontos de fração; "reajustado" = com o intercepto reajustado na amostra (tira o nível mais baixo das unidades jovens). Consistente = erro reajustado cai, Spearman não piora e IC 90% da diferença < 0.

| teste | X | natureza | amostra | N | erro reajustado: só controles → com X | IC 90% da diferença | erro bruto | Spearman | leitura |
|---|---|---|---|---|---|---|---|---|---|
| X1 | renda da praça | antes de abrir | mês ≥ 6 (principal) | 19 | 9.1 → 8.8 | [-0.5; -0.1] | 10.8 → 10.6 | +0.59 → +0.64 | **consistente** |
| X1 | renda da praça | antes de abrir | mês ≥ 9 | 17 | 8.7 → 8.4 | [-0.5; -0.1] | 10.2 → 10.0 | +0.68 → +0.71 | **consistente** |
| X1 | renda da praça | antes de abrir | mês ≥ 12 (v1.1) | 13 | 6.4 → 6.1 | [-0.5; +0.0] | 7.3 → 7.1 | +0.65 → +0.72 | não se repete |
| X2 | escritórios a pé (candidata) | antes de abrir | mês ≥ 6 (principal) | 19 | 8.9 → 9.1 | [-2.2; +2.7] | 10.7 → 9.0 | +0.59 → +0.65 | não se repete |
| X2 | escritórios a pé (candidata) | antes de abrir | mês ≥ 9 | 17 | 8.5 → 8.2 | [-2.9; +2.4] | 10.1 → 7.8 | +0.68 → +0.75 | não se repete |
| X2 | escritórios a pé (candidata) | antes de abrir | mês ≥ 12 (v1.1) | 13 | 6.2 → 5.9 | [-3.2; +2.4] | 7.2 → 5.9 | +0.65 → +0.70 | não se repete |
| X3 | demanda revelada de TotalPass (candidata) | foto atual | mês ≥ 6 (principal) | 19 | 8.8 → 7.9 | [-3.6; +1.9] | 10.6 → 10.1 | +0.64 → +0.71 | não se repete |
| X3 | demanda revelada de TotalPass (candidata) | foto atual | mês ≥ 9 | 17 | 8.4 → 8.3 | [-2.6; +2.3] | 10.0 → 9.9 | +0.71 → +0.70 | não se repete |
| X3 | demanda revelada de TotalPass (candidata) | foto atual | mês ≥ 12 (v1.1) | 13 | 6.1 → 6.9 | [-2.3; +3.4] | 7.1 → 8.9 | +0.72 → +0.60 | não se repete |
| X4 | tier do Wellhub | decisão do operador | mês ≥ 6 (principal) | 19 | 8.8 → 8.3 | [-1.5; +0.3] | 10.6 → 9.2 | +0.64 → +0.68 | não se repete |
| X4 | tier do Wellhub | decisão do operador | mês ≥ 9 | 17 | 8.4 → 7.7 | [-1.5; +0.4] | 10.0 → 8.6 | +0.71 → +0.75 | não se repete |
| X4 | tier do Wellhub | decisão do operador | mês ≥ 12 (v1.1) | 13 | 6.1 → 6.2 | [-1.6; +1.1] | 7.1 → 6.2 | +0.72 → +0.76 | não se repete |
| X5 | independentes no agregador (candidata) | foto atual | mês ≥ 6 (principal) | 19 | 8.8 → 13.6 | [-0.5; +10.1] | 10.6 → 13.4 | +0.64 → +0.47 | não se repete |
| X5 | independentes no agregador (candidata) | foto atual | mês ≥ 9 | 17 | 8.4 → 14.3 | [+0.7; +11.4] | 10.0 → 14.0 | +0.71 → +0.48 | não se repete |
| X5 | independentes no agregador (candidata) | foto atual | mês ≥ 12 (v1.1) | 13 | 6.1 → 14.6 | [+2.0; +13.9] | 7.1 → 13.9 | +0.72 → +0.33 | não se repete |
| X6 | preço do plano Gold (candidata) | decisão do operador | mês ≥ 6 (principal) | 19 | 8.8 → 10.0 | [-1.1; +3.1] | 10.6 → 11.0 | +0.64 → +0.56 | não se repete |
| X6 | preço do plano Gold (candidata) | decisão do operador | mês ≥ 9 | 17 | 8.4 → 9.5 | [-1.0; +3.2] | 10.0 → 10.3 | +0.71 → +0.67 | não se repete |
| X6 | preço do plano Gold (candidata) | decisão do operador | mês ≥ 12 (v1.1) | 13 | 6.1 → 7.2 | [-1.3; +2.9] | 7.1 → 7.6 | +0.72 → +0.70 | não se repete |
| X7 | em shopping | antes de abrir | mês ≥ 6 (principal) | 19 | 8.9 → 9.7 | [-0.2; +1.8] | 10.7 → 11.3 | +0.59 → +0.59 | não se repete |
| X7 | em shopping | antes de abrir | mês ≥ 9 | 17 | 8.5 → 8.9 | [-0.7; +1.6] | 10.1 → 10.3 | +0.68 → +0.69 | não se repete |
| X7 | em shopping | antes de abrir | mês ≥ 12 (v1.1) | 13 | 6.2 → 6.7 | [-1.0; +1.7] | 7.2 → 7.6 | +0.65 → +0.70 | não se repete |

## Insumos (SHA-256)

- `protocolo_mix.md`: `9a8e3374240b1b2ea63f0ab7768d59c5dd2778f8819f145e942ffd3e0e88aa31`
- `02_confirmacao_ampliada.py`: `86988fc33f0521f3157701ceff1f1aeb9aec16de40127410d9eaccbb0aa9d925`
- `01_mix.py`: `d608f102cd8ee0ef5c02bf0ecad653e2c82253e89e4d017e150d9f5dee789356`
- `01_exploracao.py`: `d4147998b23859bcb4d813d7cbd724f3a0e321cb3b0f27f7f45493db244f7c8d`
- `fato_unidade_mes.parquet`: `cffc6b276d930905ace08bffe1c5f0b7e15d207b5fd7389c8afd0a19ebc8fa87`
- `dim_unidade.parquet`: `c6ecef57365c1ac8730802386adb55eb5610a056665b0999746ccb12395230b8`
- `LOCAL_demanda_totalpass_por_unidade.parquet`: `80eacc2807979bb64fe165dcc47d52108aad5af1f02f9ce84e0afa14fde02c0c`
