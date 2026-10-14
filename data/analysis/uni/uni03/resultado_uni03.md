# BLK-UNI-03 — resultado da curva de rampa

Protocolo `protocolo_uni03.md` v1.1 (SHA-256 `d75b31150fa1c4db…`). Rodado uma vez.

- Exploração (monta a curva): **33 unidades**; confirmação: **22 unidades** (inauguradas de 2024-12 a 2025-08). Elegíveis que pararam de reportar antes do mês 13: 0.
- Nível maduro mediano (exploração, meses 11–13): 2,213 alunos. Fração mediana do mês da inauguração já aberta (f0): 0.53.

## P1 — curva do 1º ano (% do nível maduro; exploração)

| mês | alunos (mediana) | alunos p10–p90 | balcão | agregador | faturamento | simulador hoje* |
|---|---|---|---|---|---|---|
| 0 | 80% | 42%–102% | 91% | 53% | – | – |
| 1 | 68% | 50%–90% | 76% | 49% | 52% | 37% |
| 2 | 77% | 60%–106% | 86% | 58% | 64% | 47% |
| 3 | 84% | 68%–105% | 89% | 64% | 75% | 57% |
| 4 | 88% | 74%–103% | 94% | 70% | 77% | 66% |
| 5 | 90% | 81%–105% | 96% | 74% | 83% | 76% |
| 6 | 92% | 83%–105% | 97% | 80% | 85% | 86% |
| 7 | 97% | 84%–108% | 99% | 82% | 87% | 95% |
| 8 | 95% | 88%–107% | 101% | 89% | 90% | 100% |
| 9 | 99% | 91%–109% | 102% | 94% | 95% | 100% |
| 10 | 100% | 92%–110% | 103% | 98% | 94% | 100% |
| 11 | 101% | 96%–105% | 102% | 100% | 98% | 100% |
| 12 | 101% | 96%–103% | 101% | 101% | 102% | 100% |

\* rampa do simulador (modo padrão) para o nível maduro mediano, no tempo de operação mediano (k + 0.53).

Alunos medianos (absolutos) nos meses 0/1/3/6/12: 1,528 / 1,469 / 1,744 / 1,966 / 2,228. Participação do agregador nos meses 1/3/6/12: 18% / 24% / 24% / 26%.
Linear recalibrada na exploração: começa em 62% do nível maduro e chega a 100% no mês 8 (erro médio 11%).

## P2 — previsão do 1º ano nas unidades de confirmação

(a) = erro médio mês a mês (meses 1–10); (b) = erro na soma do 1º ano (mediana do erro absoluto; entre parênteses, o viés).

**ativos** (22 unidades) — curva vence o simulador atual? **sim**; curva erra menos em 21 de 22 unidades; basta recalibrar 500/8 (critério fixado antes).

| braço | (a) erro mensal | (b) erro na soma do 1º ano |
|---|---|---|
| curva | 10% | 6% (-4%) |
| sim_padrao | 21% | 15% (-15%) |
| sim_balcao | 11% | 8% (-7%) |
| linear_recal | 10% | 5% (-5%) |
| sim_padrao_sem_f0 | 24% | 18% (-18%) |

**faturamento** (22 unidades) — curva vence o simulador atual? **sim**; curva erra menos em 21 de 22 unidades; o formato da rampa importa (critério fixado antes).

| braço | (a) erro mensal | (b) erro na soma do 1º ano |
|---|---|---|
| curva | 12% | 4% (-3%) |
| sim_padrao | 17% | 8% (-7%) |
| sim_balcao | 14% | 6% (+3%) |
| linear_recal | 13% | 6% (+5%) |
| sim_padrao_sem_f0 | 19% | 9% (-9%) |

## P3 — alerta precoce: projetar o nível maduro a partir do mês k

| mês | faixa de erro p10–p90 (exploração, leave-one-out) | erro típico (exploração) | erro típico (confirmação) | cobertura na confirmação | compatível (57–93%)? |
|---|---|---|---|---|---|
| 1 | -24% a +36% | 17% | 21% | 59% (22 unid.) | sim |
| 3 | -20% a +23% | 11% | 9% | 77% (22 unid.) | sim |
| 6 | -13% a +11% | 8% | 9% | 64% (22 unid.) | sim |

**Antes de abrir × mês 3** (13 unidades da confirmação com metragem): erro típico da projeção pela metragem (função da viabilidade, base = exploração) = 22%; pelo mês 3 = 5%.

## P4 — depois do mês 12 (% do nível dos meses 11–13; todas as unidades, dados até ago/2026)

| mês | N | mediana | p10 | p90 |
|---|---|---|---|---|
| 13 | 51 | 99% | 96% | 104% |
| 15 | 47 | 97% | 88% | 109% |
| 18 | 41 | 99% | 79% | 111% |
| 21 | 33 | 104% | 86% | 118% |
| 24 | 29 | 98% | 73% | 118% |

Nível dos meses 22–24 sobre o dos meses 11–13 (mediana, 31 unidades): 101%. Dentro de ±5%: o nível dos meses 11–13 vale como nível maduro.

## Insumos (SHA-256)

- `protocolo_uni03.md`: `d75b31150fa1c4db409f123f6aec4e32ca917ac45fe54d1fe9c9131ddc9ae3d3`
- `01_curva_rampa.py`: `fd983491472df96d3f49b6b57ca8032ae4bd09d78b56ddf950e91ffa924f1a48`
- `fato_unidade_mes.parquet`: `cffc6b276d930905ace08bffe1c5f0b7e15d207b5fd7389c8afd0a19ebc8fa87`
- `dim_unidade.parquet`: `c6ecef57365c1ac8730802386adb55eb5610a056665b0999746ccb12395230b8`
