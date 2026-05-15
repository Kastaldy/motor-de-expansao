# Fase A - Validacao consolidada do Censo 2022

> Data da validacao: 2026-05-15

## 1. Auditoria do join posicional por UF

| UF | Shapefile | Basico | Renda total | Renda valida | Mismatch total % | Seq municipio % | Alerta >5% |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AC | 2215 | 2215 | 2127 | 1981 | 3.97 | 100.0000 | NAO |
| AL | 6359 | 6359 | 6267 | 6167 | 1.45 | 100.0000 | NAO |
| AM | 10729 | 10729 | 9602 | 8438 | 10.50 | 100.0000 | SIM |
| AP | 1492 | 1492 | 1440 | 1359 | 3.49 | 100.0000 | NAO |
| BA | 30985 | 30985 | 30739 | 30507 | 0.79 | 100.0000 | NAO |
| CE | 20979 | 20979 | 20518 | 20096 | 2.20 | 100.0000 | NAO |
| DF | 5418 | 5418 | 5342 | 5264 | 1.40 | 100.0000 | NAO |
| ES | 8706 | 8706 | 8568 | 8472 | 1.59 | 100.0000 | NAO |
| GO | 12861 | 12861 | 12816 | 12625 | 0.35 | 100.0000 | NAO |
| MA | 16301 | 16301 | 16030 | 15571 | 1.66 | 100.0000 | NAO |
| MG | 51387 | 51387 | 50929 | 50289 | 0.89 | 100.0000 | NAO |
| MS | 6117 | 6117 | 6064 | 5985 | 0.87 | 100.0000 | NAO |
| MT | 9381 | 9381 | 9188 | 8794 | 2.06 | 100.0000 | NAO |
| PA | 16714 | 16714 | 16065 | 15527 | 3.88 | 100.0000 | NAO |
| PB | 9639 | 9639 | 9563 | 9469 | 0.79 | 100.0000 | NAO |
| PE | 19578 | 19578 | 19417 | 19201 | 0.82 | 100.0000 | NAO |
| PI | 7340 | 7340 | 7278 | 7212 | 0.84 | 100.0000 | NAO |
| PR | 23777 | 23777 | 23435 | 23178 | 1.44 | 100.0000 | NAO |
| RJ | 41700 | 41700 | 40519 | 39804 | 2.83 | 100.0000 | NAO |
| RN | 6095 | 6095 | 6013 | 5955 | 1.35 | 100.0000 | NAO |
| RO | 3456 | 3456 | 3304 | 3135 | 4.40 | 100.0000 | NAO |
| RR | 1783 | 1783 | 1612 | 1173 | 9.59 | 100.0000 | SIM |
| RS | 25569 | 25569 | 25300 | 24871 | 1.05 | 99.9922 | NAO |
| SC | 16736 | 16736 | 16435 | 16139 | 1.80 | 100.0000 | NAO |
| SE | 5346 | 5346 | 5244 | 5199 | 1.91 | 100.0000 | NAO |
| SP | 103319 | 103319 | 100928 | 99223 | 2.31 | 100.0000 | NAO |
| TO | 4117 | 4117 | 4029 | 3897 | 2.14 | 100.0000 | NAO |

## 2. Validacao da renda proxy

| UF | Corr proxy vs M1 | Corr V06004 vs M1 | MAE proxy | MAE V06004 | Ratio proxy | Ratio V06004 | V06004/v0005 melhor? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GO | 0.3652 | 0.3349 | 435.71 | 1163.39 | 0.6835 | 1.8001 | SIM |
| RJ | 0.2656 | 0.2175 | 412.59 | 1618.48 | 0.7614 | 1.9816 | SIM |
| SP | 0.0436 | 0.0223 | 515.01 | 1854.33 | 0.7378 | 1.9907 | SIM |

| UF | Setor mean | Setor median | Setor skew | Outlier % | Zeros % | M1 mean | M1 median | Distribuicao coerente? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GO | 974.71 | 889.19 | 4.49 | 1.54 | 1.72 | 1444.27 | 1489.52 | SIM |
| RJ | 1014.46 | 833.97 | 3.79 | 2.80 | 3.77 | 1402.80 | 1385.75 | SIM |
| SP | 1168.50 | 963.01 | 3.76 | 3.09 | 2.56 | 1551.84 | 1499.77 | SIM |

### Capitais piloto

| UF | Cidade | Proxy mun | V06004 mun | M1 mun | Cobertura % |
| --- | --- | --- | --- | --- | --- |
| GO | Goiania | 1830.47 | 4525.52 | 2668.80 | 99.35 |
| RJ | Rio de Janeiro | 1764.64 | 4208.54 | 2515.32 | 99.14 |
| SP | Sao Paulo | 1961.10 | 5051.50 | 2713.36 | 99.11 |

## 3. Validacao intraurbana

| UF | Cidade | Hex | Std municipal | Std setor | Ganho std | Amp municipal | Amp setor | Ganho amplitude | Correlacao |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GO | Goiania | 128 | 0.00 | 22.97 | 22.97 | 0.00 | 73.38 | 73.38 | NA_baseline_uniforme |
| RJ | Rio de Janeiro | 189 | 0.00 | 23.63 | 23.63 | 0.00 | 72.66 | 72.66 | NA_baseline_uniforme |
| SP | Sao Paulo | 296 | 0.00 | 19.23 | 19.23 | 0.00 | 61.04 | 61.04 | NA_baseline_uniforme |

## 4. Consistencia espacial intraurbana

| UF | Cidade | Hex avaliados | Threshold | Outliers criticos | Status |
| --- | --- | --- | --- | --- | --- |
| GO | Goiania | 89 | 35.00 | 1 | REVIEW |
| RJ | Rio de Janeiro | 130 | 57.37 | 1 | REVIEW |
| SP | Sao Paulo | 217 | 35.00 | 1 | REVIEW |

## 5. Stress test tecnico

| UF | Hex | Setores | Tempo est. s | Peak RSS est. MB |
| --- | --- | --- | --- | --- |
| AC | 28370 | 2215 | 56.74 | N/A |
| AL | 4544 | 6359 | 9.09 | N/A |
| AM | 292793 | 10729 | 585.59 | N/A |
| AP | 24162 | 1492 | 48.32 | N/A |
| BA | 93918 | 30985 | 187.84 | N/A |
| CE | 23975 | 20979 | 47.95 | N/A |
| DF | 999 | 5418 | 2.00 | N/A |
| ES | 8158 | 8706 | 16.32 | N/A |
| GO | 59952 | 12861 | 119.90 | N/A |
| MA | 53180 | 16301 | 106.36 | N/A |
| MG | 104078 | 51387 | 208.16 | N/A |
| MS | 69344 | 6117 | 138.69 | N/A |
| MT | 165033 | 9381 | 330.07 | N/A |
| PA | 213997 | 16714 | 427.99 | N/A |
| PB | 9223 | 9639 | 18.45 | N/A |
| PE | 16013 | 19578 | 32.03 | N/A |
| PI | 40869 | 7340 | 81.74 | N/A |
| PR | 40261 | 23777 | 80.52 | N/A |
| RJ | 7895 | 41700 | 15.79 | N/A |
| RN | 8555 | 6095 | 17.11 | N/A |
| RO | 45962 | 3456 | 91.92 | N/A |
| RR | 43424 | 1783 | 86.85 | N/A |
| RS | 60811 | 25569 | 121.62 | N/A |
| SC | 20100 | 16736 | 40.20 | N/A |
| SE | 3588 | 5346 | 7.18 | N/A |
| SP | 47139 | 103319 | 94.28 | N/A |
| TO | 46302 | 4117 | 92.60 | N/A |

- Tempo nacional estimado (sequencial): 51.09 min
- Pico de memoria estimado na maior UF: N/A
- UFs com alerta de join >5%: AM, RR
- Gargalo principal: Overlay geopandas/shapely e o principal gargalo; o pico de memoria fica concentrado na maior UF processada sequencialmente.

## 6. Recomendacao

**NO-GO** para escala nacional imediata.

Motivos principais:
- join posicional ainda tem alerta estrutural >5% em AM e RR
- a calibracao municipal da renda proxy segue fraca frente ao M1 nas UFs piloto
- nao ha validacao com performance real das unidades Ultra no repositorio atual

## 7. Dados reais Ultra

- Dados de faturamento/alunos/churn nao foram encontrados no repositorio; a validacao com performance real permanece pendente.
