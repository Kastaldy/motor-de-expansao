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
| sem controle 'só um' | E2 escritórios privados a pé | 64 | 12.6 → 11.5 | [-2.1; +0.0] | 14.4 → 13.8 | +0.37 → +0.44 | **melhora a previsão** |
| sem controle 'só um' | E3 grupo de estado (SP / DF-GO / outros) | 64 | 12.6 → 9.7 | [-4.4; -1.2] | 14.4 → 10.2 | +0.37 → +0.67 | **melhora a previsão** |
| sem controle 'só um' | E4 escritórios privados + estado | 64 | 12.6 → 9.8 | [-4.5; -1.1] | 14.4 → 10.5 | +0.37 → +0.68 | **melhora a previsão** |

## Tamanho do efeito (universo todo, com os controles; IC 90% agrupado por metro)

- E1 escritórios a pé: +6.7 p.f. por desvio-padrão [+4.0 p.f.; +9.5 p.f.] (20 metrôs).
- E2 escritórios privados a pé: +6.4 p.f. por desvio-padrão [+3.5 p.f.; +9.2 p.f.].
- E4 (escritórios privados + estado): escritórios privados +4.6 p.f./dp [+2.1 p.f.; +7.1 p.f.]; SP contra DF/GO +20.8 p.f. [+17.2 p.f.; +24.3 p.f.]; outros contra DF/GO +4.9 p.f. [-1.2 p.f.; +11.1 p.f.].
- **Efeito prático (E2):** de uma praça com poucos escritórios privados (p10) para uma com muitos (p90), a proporção de agregadores prevista muda +16.4 p.f..

## Regra ajustada no universo (E2, para a v2 avaliar)

proporção de agregadores = -0.172 -0.036·l_renda +0.093·l_pop +0.049·jovem +0.031·so_um +0.041·escr_priv (escr_priv = log(1 + escritórios privados a pé) − log(1 + população a pé); para uma unidade nova, jovem = 0 e só_um conforme a política).

## Insumos (SHA-256)

- `protocolo_mix.md`: `4cfb0336e1676b90ee930588c54119df0165f91b25222dd16f7a91b9616e56d8`
- `03_universo_cv.py`: `38dffb8eb6e12a0df0d29dc11bdb3b8e8bf7d27b7b3aed0b36b63e5650194e10`
- `01_mix.py`: `d608f102cd8ee0ef5c02bf0ecad653e2c82253e89e4d017e150d9f5dee789356`
- `01_exploracao.py`: `d4147998b23859bcb4d813d7cbd724f3a0e321cb3b0f27f7f45493db244f7c8d`
- `fato_unidade_mes.parquet`: `cffc6b276d930905ace08bffe1c5f0b7e15d207b5fd7389c8afd0a19ebc8fa87`
- `dim_unidade.parquet`: `c6ecef57365c1ac8730802386adb55eb5610a056665b0999746ccb12395230b8`
- `f1_privado_ultra.parquet`: `a30739d1d6978267abbba6d671d03f5c6fc98e0fca7e81d2372fbd5394a401c4`
