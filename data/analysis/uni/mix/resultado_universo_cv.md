# BLK-UNI-05C v1.3 — universo inteiro com validação cruzada (proporção de agregadores nos ativos)

Protocolo `protocolo_mix.md` §11 (SHA-256 `4cfb0336e1676b90…`). Rodado uma vez.

- **Universo: 64 unidades** (aceitam ≥ 1 agregador; ≥ 3 meses com mês de vida ≥ 6 em jan/25–ago/26), em 20 metrôs; 5 aceitam só um; 16 'jovens' (mês de vida médio < 12).
- Proporção de agregadores nos ativos: mediana 42% (p10 25%, p90 65%).
- Correlação (Spearman) escritórios × escritórios privados: +0.99.

## Validação cruzada

Erro = erro médio absoluto em pontos de fração da proporção. LOO = cada unidade prevista sem ela; por metro = cada metrópole prevista sem ela.

| controles | candidata | N | erro LOO: base → com X | IC 90% da diferença | erro por metro: base → com X | Spearman LOO | leitura |
|---|---|---|---|---|---|---|---|
| com controle 'só um' | E1 escritórios a pé | 64 | 12.7 → 11.6 | [-2.3; +0.0] | 14.3 → 14.5 | +0.35 → +0.45 | não melhora |
| com controle 'só um' | E2 escritórios privados a pé | 64 | 12.7 → 11.7 | [-2.2; +0.1] | 14.3 → 14.5 | +0.35 → +0.43 | não melhora |
| com controle 'só um' | E3 grupo de estado (SP / DF-GO / outros) | 64 | 12.7 → 9.8 | [-4.6; -1.2] | 14.3 → 9.5 | +0.35 → +0.66 | **melhora a previsão** |
| com controle 'só um' | E4 escritórios privados + estado | 64 | 12.7 → 9.6 | [-4.8; -1.4] | 14.3 → 10.4 | +0.35 → +0.69 | **melhora a previsão** |
| sem controle 'só um' | E1 escritórios a pé | 64 | 12.6 → 11.4 | [-2.3; -0.1] | 14.4 → 13.7 | +0.37 → +0.46 | **melhora a previsão** |
| sem controle 'só um' | E2 escritórios privados a pé | 64 | 12.6 → 11.6 | [-2.0; +0.0] | 14.4 → 13.8 | +0.37 → +0.44 | **melhora a previsão** |
| sem controle 'só um' | E3 grupo de estado (SP / DF-GO / outros) | 64 | 12.6 → 9.7 | [-4.4; -1.2] | 14.4 → 10.2 | +0.37 → +0.67 | **melhora a previsão** |
| sem controle 'só um' | E4 escritórios privados + estado | 64 | 12.6 → 9.8 | [-4.4; -1.1] | 14.4 → 10.5 | +0.37 → +0.68 | **melhora a previsão** |

## Tamanho do efeito (universo todo, com os controles; IC 90% agrupado por metro)

- E1 escritórios a pé: +6.7 p.f. por desvio-padrão [+4.0 p.f.; +9.5 p.f.] (20 metrôs).
- E2 escritórios privados a pé: +6.3 p.f. por desvio-padrão [+3.4 p.f.; +9.2 p.f.].
- E4 (escritórios privados + estado): escritórios privados +4.4 p.f./dp [+2.1 p.f.; +6.8 p.f.]; SP contra DF/GO +20.8 p.f. [+17.2 p.f.; +24.3 p.f.]; outros contra DF/GO +5.1 p.f. [-1.1 p.f.; +11.2 p.f.].
- **Efeito prático (E2):** de uma praça com poucos escritórios privados (p10) para uma com muitos (p90), a proporção de agregadores prevista muda +16.2 p.f..

## Regra só por estado (E3), ajustada no universo

- SP contra DF/GO: +23.1 p.f. [+20.0 p.f.; +26.1 p.f.]; outros contra DF/GO: +9.3 p.f. [+2.4 p.f.; +16.2 p.f.] (IC agrupado por metro: otimista, poucos metros por grupo).
- Mediana observada (UX) por grupo: DFGO 32% (n=24); SP 56% (n=24); outros 43% (n=16).
- Regra: proporção = -0.457 +0.027·l_renda +0.044·l_pop +0.082·jovem +0.106·so_um +0.231·g_SP +0.093·g_outros.

## Regra ajustada no universo (E2, para a v2 avaliar)

proporção de agregadores = -0.170 -0.035·l_renda +0.093·l_pop +0.050·jovem +0.031·so_um +0.041·escr_priv (escr_priv = log(1 + escritórios privados a pé) − log(1 + população a pé); para uma unidade nova, jovem = 0 e só_um conforme a política).

## Insumos (SHA-256)

- `protocolo_mix.md`: `4cfb0336e1676b90ee930588c54119df0165f91b25222dd16f7a91b9616e56d8`
- `03_universo_cv.py`: `14a276a27ba602fd211cb2cc1edc9b4b2c9a3742edf206daf322a88d65574d0b`
- `01_mix.py`: `d608f102cd8ee0ef5c02bf0ecad653e2c82253e89e4d017e150d9f5dee789356`
- `01_exploracao.py`: `d4147998b23859bcb4d813d7cbd724f3a0e321cb3b0f27f7f45493db244f7c8d`
- `fato_unidade_mes.parquet`: `cffc6b276d930905ace08bffe1c5f0b7e15d207b5fd7389c8afd0a19ebc8fa87`
- `dim_unidade.parquet`: `c6ecef57365c1ac8730802386adb55eb5610a056665b0999746ccb12395230b8`
- `f1_privado_ultra.parquet`: `63f38d3c0523e06f048977e3fa922f88491e4601b19ef35b3f46af383c74c8ba`
