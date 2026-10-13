# BLK-UNI-05 — viabilidade v2 × atual (só análise)

Protocolo `protocolo_uni05.md` (SHA-256 `e9051067bcf48eee…`). Rodado uma vez.

- Premissas iguais para todos: ticket R$ 137, balcão 69%, aluguel R$ 20,000, obra R$ 2,340,000. Receita por aluno no simulador (regime pleno): R$ 115.
- Faixa da V2 (erros fora da amostra juntados, N = 57): p10 -35%, p90 +67% em torno da previsão.
- Payback além de 60 meses conta como 61. REAL = simulador com o faturamento que a unidade de fato teve e a rampa observada.
- Unidades viáveis no REAL: teste 8 de 18; treino 16 de 39.

## Principal — 18 unidades de teste (abertas em 2025)

| cenário | faturamento: erro / viés | payback: erro típico / viés (meses) | decisão igual ao REAL | aprovações indevidas | rejeições indevidas |
|---|---|---|---|---|---|
| ATUAL | 34% / -25% | 20 / -6 | 61% | 2 | 5 |
| V2 | 22% / +1% | 8 / +0 | 67% | 1 | 5 |
| V2 pessimista | 55% / +55% | 2 / +2 | 61% | 0 | 7 |
| A: demanda ATUAL + rampa obs. | – | 18 / -8 | 61% | 4 | 3 |
| B: demanda V2 + rampa 500/8 | – | 8 / +0 | 72% | 0 | 5 |

## Secundária — 39 maduras de 2025 (leave-one-out)

| cenário | faturamento: erro / viés | payback: erro típico / viés (meses) | decisão igual ao REAL | aprovações indevidas | rejeições indevidas |
|---|---|---|---|---|---|
| ATUAL | 25% / -12% | 11 / -3 | 54% | 10 | 8 |
| V2 | 22% / -4% | 7 / +0 | 72% | 6 | 5 |
| V2 pessimista | 47% / +47% | 20 / +20 | 67% | 0 | 13 |
| A: demanda ATUAL + rampa obs. | – | 11 / -5 | 56% | 14 | 3 |
| B: demanda V2 + rampa 500/8 | – | 6 / +0 | 77% | 4 | 5 |

**V2 recomendada para DEC? SIM** (critério fixado antes, nas 18 unidades de teste).

Viés de payback negativo = o cenário promete retorno mais rápido que o real (otimista).

## Por unidade (teste)

| unidade | UF | faturamento real | ATUAL | V2 (p10–p90) | payback REAL | ATUAL | V2 | viável REAL / ATUAL / V2 |
|---|---|---|---|---|---|---|---|---|
| JARDIM APURA | SP | 114 mil | 209 mil | 172 mil (112 mil–288 mil) | 61 | 54 | 61 | não / não / não |
| MOCOCA | SP | 122 mil | 235 mil | 260 mil (169 mil–435 mil) | 61 | 44 | 36 | não / não / sim |
| ALEXANDRINA | GO | 150 mil | 255 mil | 233 mil (152 mil–391 mil) | 61 | 39 | 43 | não / não / não |
| UNAI | MG | 153 mil | 217 mil | 193 mil (126 mil–324 mil) | 61 | 50 | 60 | não / não / não |
| COTIA | SP | 155 mil | 203 mil | 153 mil (100 mil–256 mil) | 61 | 56 | 61 | não / não / não |
| CESARIO | MG | 157 mil | 260 mil | 198 mil (129 mil–332 mil) | 61 | 38 | 58 | não / não / não |
| TAGUATINGA SUL | DF | 180 mil | 255 mil | 210 mil (137 mil–351 mil) | 61 | 39 | 52 | não / não / não |
| CAMBUI CAMPINAS | SP | 191 mil | 269 mil | 171 mil (111 mil–286 mil) | 61 | 36 | 61 | não / sim / não |
| CPA | MT | 193 mil | 268 mil | 248 mil (162 mil–416 mil) | 60 | 37 | 39 | não / não / não |
| FLORIANO | MG | 198 mil | 272 mil | 203 mil (132 mil–340 mil) | 57 | 36 | 55 | não / sim / não |
| PARANOA PARQUE | DF | 271 mil | 307 mil | 271 mil (176 mil–454 mil) | 34 | 31 | 34 | sim / sim / sim |
| VILA GUANABARA | SC | 281 mil | 268 mil | 236 mil (154 mil–395 mil) | 32 | 37 | 42 | sim / não / não |
| CARIACICA | ES | 344 mil | 233 mil | 172 mil (112 mil–288 mil) | 25 | 45 | 61 | sim / não / não |
| VALPARAISO | GO | 348 mil | 326 mil | 232 mil (151 mil–388 mil) | 25 | 29 | 43 | sim / sim / não |
| BOTANIC MALL | DF | 358 mil | 210 mil | 302 mil (197 mil–506 mil) | 24 | 53 | 29 | sim / não / sim |
| BUTANTA | SP | 455 mil | 260 mil | 239 mil (155 mil–400 mil) | 18 | 38 | 41 | sim / não / não |
| NOROESTE | DF | 693 mil | 307 mil | 436 mil (284 mil–731 mil) | 12 | 31 | 19 | sim / sim / sim |
| BOTAFOGO | RJ | 697 mil | 214 mil | 245 mil (159 mil–410 mil) | 12 | 51 | 40 | sim / não / não |

## Insumos (SHA-256)

- `protocolo_uni05.md`: `e9051067bcf48eeecab6d984fe721f3284b2d508c97896c9bb50ecb01e637311`
- `01_comparacao.py`: `545dda88e3dc2135688ac26c4cda15e5d6ecd1293979c741463f75ac30bee2f1`
- `fato_unidade_mes.parquet`: `cffc6b276d930905ace08bffe1c5f0b7e15d207b5fd7389c8afd0a19ebc8fa87`
- `dim_unidade.parquet`: `c6ecef57365c1ac8730802386adb55eb5610a056665b0999746ccb12395230b8`
- `metragem_estimada.csv`: `acaa55425abb6ab272329444815b6136d645f317565c7b27c72d912f5c0a3504`
- `01_confirmacao.py`: `e61ad34fb7023b5f3c098e3628541c2d7a7f344b5ce68461872b56334a11d7cf`
