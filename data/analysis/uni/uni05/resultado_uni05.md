# BLK-UNI-05 — viabilidade v2 × atual (só análise) — v1.1

v1.1 corrige a assimetria do ajuste de calendário (na v1.0 só a V2 o recebia) e tira os erros do teste da faixa pessimista. A v1.0 está em `resultado_uni05_v1_0.md`.

Protocolo `protocolo_uni05.md` (SHA-256 `e9051067bcf48eee…`). Rodado uma vez.

- Premissas iguais para todos: ticket R$ 137, balcão 69%, aluguel R$ 20,000, obra R$ 2,340,000. Receita por aluno no simulador (regime pleno): R$ 115.
- Faixa da V2 usada aqui (erros LOO do treino): p10 -35%, p90 +54%. Com os erros do teste juntados (proposta para o futuro): p10 -35%, p90 +67%.
- Ajuste de calendário 2025→2026 aplicado ao ATUAL e à V2 no teste: -2%. Rampa observada: 64% em t = 0 (≈67% no mês 1), 100% no mês 11.
- Payback além de 60 meses conta como 61. REAL = simulador com o faturamento que a unidade de fato teve e a rampa observada.
- Unidades viáveis no REAL: teste 8 de 18; treino 16 de 39.

## Principal — 18 unidades de teste (abertas em 2025)

| cenário | faturamento: erro / viés | payback: erro típico / viés (meses) | payback: erro só nas não censuradas | decisão igual ao REAL | aprovações indevidas | rejeições indevidas |
|---|---|---|---|---|---|---|
| ATUAL | 33% / -24% | 20 / -4 | 20 | 72% | 0 | 5 |
| V2 | 22% / +1% | 8 / +0 | 14 | 67% | 1 | 5 |
| V2 pessimista | 54% / +54% | 2 / +2 | 32 | 61% | 0 | 7 |
| A: demanda ATUAL + rampa obs. | – | 19 / -6 | 19 | 61% | 3 | 4 |
| B: demanda V2 + rampa 500/8 | – | 8 / +0 | 16 | 72% | 0 | 5 |

- Linha de base 'reprovar tudo': acerta 56% das decisões.
- Soma da safra (previsto/real − 1): ATUAL -12%, V2 -18%.
- Unidades não censuradas (REAL < 61 meses): 10; V2 erra menos o payback em 6, ATUAL em 4.

## Secundária — 39 maduras de 2025 (leave-one-out)

| cenário | faturamento: erro / viés | payback: erro típico / viés (meses) | payback: erro só nas não censuradas | decisão igual ao REAL | aprovações indevidas | rejeições indevidas |
|---|---|---|---|---|---|---|
| ATUAL | 25% / -12% | 11 / -3 | 8 | 54% | 10 | 8 |
| V2 | 22% / -4% | 7 / +0 | 8 | 72% | 6 | 5 |
| V2 pessimista | 46% / +46% | 20 / +20 | 23 | 67% | 0 | 13 |
| A: demanda ATUAL + rampa obs. | – | 11 / -5 | 9 | 56% | 14 | 3 |
| B: demanda V2 + rampa 500/8 | – | 6 / +0 | 8 | 77% | 4 | 5 |

- Linha de base 'reprovar tudo': acerta 59% das decisões.
- Soma da safra (previsto/real − 1): ATUAL +6%, V2 -4%.
- Unidades não censuradas (REAL < 61 meses): 28; V2 erra menos o payback em 12, ATUAL em 14.

**V2 recomendada para DEC? NÃO** (critério fixado antes, nas 18 unidades de teste).

Viés de payback negativo = o cenário promete retorno mais rápido que o real (otimista).

## Por unidade (teste)

| unidade | UF | faturamento real | ATUAL | V2 (p10–p90) | payback REAL | ATUAL | V2 | viável REAL / ATUAL / V2 |
|---|---|---|---|---|---|---|---|---|
| JARDIM APURA | SP | 114 mil | 205 mil | 172 mil (112 mil–265 mil) | 61 | 56 | 61 | não / não / não |
| MOCOCA | SP | 122 mil | 231 mil | 260 mil (170 mil–401 mil) | 61 | 46 | 36 | não / não / sim |
| ALEXANDRINA | GO | 150 mil | 250 mil | 233 mil (153 mil–361 mil) | 61 | 40 | 43 | não / não / não |
| UNAI | MG | 153 mil | 212 mil | 193 mil (126 mil–299 mil) | 61 | 52 | 60 | não / não / não |
| COTIA | SP | 155 mil | 199 mil | 153 mil (100 mil–236 mil) | 61 | 58 | 61 | não / não / não |
| CESARIO | MG | 157 mil | 254 mil | 198 mil (129 mil–306 mil) | 61 | 39 | 58 | não / não / não |
| TAGUATINGA SUL | DF | 180 mil | 250 mil | 210 mil (137 mil–324 mil) | 61 | 40 | 52 | não / não / não |
| CAMBUI CAMPINAS | SP | 191 mil | 263 mil | 171 mil (112 mil–264 mil) | 61 | 37 | 61 | não / não / não |
| CPA | MT | 193 mil | 263 mil | 248 mil (162 mil–384 mil) | 60 | 38 | 39 | não / não / não |
| FLORIANO | MG | 198 mil | 267 mil | 203 mil (133 mil–314 mil) | 57 | 37 | 55 | não / não / não |
| PARANOA PARQUE | DF | 271 mil | 301 mil | 271 mil (177 mil–418 mil) | 34 | 31 | 34 | sim / sim / sim |
| VILA GUANABARA | SC | 281 mil | 263 mil | 236 mil (154 mil–364 mil) | 32 | 38 | 42 | sim / não / não |
| CARIACICA | ES | 344 mil | 229 mil | 172 mil (112 mil–266 mil) | 25 | 46 | 61 | sim / não / não |
| VALPARAISO | GO | 348 mil | 319 mil | 232 mil (151 mil–358 mil) | 25 | 29 | 43 | sim / sim / não |
| BOTANIC MALL | DF | 358 mil | 206 mil | 302 mil (197 mil–467 mil) | 24 | 55 | 29 | sim / não / sim |
| BUTANTA | SP | 455 mil | 255 mil | 239 mil (156 mil–369 mil) | 18 | 39 | 41 | sim / não / não |
| NOROESTE | DF | 693 mil | 301 mil | 436 mil (285 mil–674 mil) | 12 | 31 | 19 | sim / sim / sim |
| BOTAFOGO | RJ | 697 mil | 210 mil | 245 mil (160 mil–378 mil) | 12 | 53 | 40 | sim / não / não |

## Insumos (SHA-256)

- `protocolo_uni05.md`: `e9051067bcf48eeecab6d984fe721f3284b2d508c97896c9bb50ecb01e637311`
- `01_comparacao.py`: `7320ae60a18db68d7a1ff93c2bf8953fa80f6aa15db5eb6c285fd8b435495508`
- `fato_unidade_mes.parquet`: `cffc6b276d930905ace08bffe1c5f0b7e15d207b5fd7389c8afd0a19ebc8fa87`
- `dim_unidade.parquet`: `c6ecef57365c1ac8730802386adb55eb5610a056665b0999746ccb12395230b8`
- `metragem_estimada.csv`: `acaa55425abb6ab272329444815b6136d645f317565c7b27c72d912f5c0a3504`
- `01_confirmacao.py`: `e61ad34fb7023b5f3c098e3628541c2d7a7f344b5ce68461872b56334a11d7cf`
