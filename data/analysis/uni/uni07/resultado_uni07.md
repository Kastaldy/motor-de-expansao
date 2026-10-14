# BLK-UNI-07 — incerteza do modelo e faixas de segurança: resultado

Protocolo `protocolo_uni07.md` (SHA-256 `b5854bc92929795d…`). Rodado uma vez. Calendário 2026: -2%.
Sanidade: 39 de treino, 18 de teste, todas com master; M0 no teste: erro típico 21.5%, viés +0.7% (UNI-02: 21,5% e +0,7%).
Premissas do simulador (config.py): ticket R$ 137, balcão 69%, agregador a 60%, aluguel R$ 20,000, obra R$ 2,340,000, custo do estúdio R$ 6,000/mês; rampa (0.64, 11).

## 1. Quanto o modelo erra (fora da amostra)

| modelo | amostra | N | desvio-padrão do erro (log) | erro típico | viés (mediana) | p10 do erro | p90 do erro |
|---|---|---|---|---|---|---|---|
| v2 (praça + estúdios + master) | treino (LOO) | 39 | 0.355 | 23% | -6% | -37% | +58% |
| v2 (praça + estúdios + master) | teste (fora do tempo) | 18 | 0.416 | 22% | -1% | -25% | +67% |
| v2 (praça + estúdios + master) | juntos | 57 | 0.373 | 23% | -4% | -34% | +64% |
| M0 (só praça) | treino (LOO) | 39 | 0.343 | 22% | -4% | -35% | +54% |
| M0 (só praça) | teste (fora do tempo) | 18 | 0.454 | 22% | +1% | -34% | +93% |
| M0 (só praça) | juntos | 57 | 0.378 | 22% | -2% | -35% | +67% |

## 2. Faixas e cobertura (v2)

| construção | faixa | limites em torno da previsão | cobertura no teste | IC 90% | cobertura total (57) | IC 90% |
|---|---|---|---|---|---|---|
| (A) só treino — teste limpo | 80% | -37% a +58% | 72% (13/18) | [50; 88] | – | – |
| (B) conjunta, sem a própria (não é teste limpo) | 80% | -34% a +64% | 78% (14/18) | [56; 92] | 79% (45/57) | [68; 87] |
| (A) só treino — teste limpo | 50% | -22% a +21% | 39% (7/18) | [20; 61] | – | – |
| (B) conjunta, sem a própria (não é teste limpo) | 50% | -21% a +24% | 39% (7/18) | [20; 61] | 49% (28/57) | [38; 61] |

**Faixa adotada (regra do §3): (A)**, de -37% a +58% em torno da previsão; p50 -6%.

## 3. O erro é igual para todas as unidades? (mediana de |erro|, v2)

| divisão | grupo | N | erro típico |
|---|---|---|---|
| metragem | oficial | 54 | 23% |
| metragem | satélite | 3 | 23% |
| faturamento previsto | menor | 19 | 23% |
| faturamento previsto | médio | 19 | 24% |
| faturamento previsto | maior | 19 | 21% |
| estado | DF-GO | 23 | 17% |
| estado | SP | 21 | 32% |
| estado | outros | 13 | 24% |
| estúdio | 0.0 | 26 | 23% |
| estúdio | 1.0 | 31 | 21% |
| treino × teste (fora do tempo; não é critério) | teste | 18 | 22% |
| treino × teste (fora do tempo; não é critério) | treino | 39 | 23% |

Faixa por grupo (todos os grupos com ≥ 10 e razão ≥ 1,5): estado. Levado à decisão do Felipe; a §4 usa a faixa única.

## 4. Faixas de segurança dos indicadores (custos-padrão, rampa observada; estúdio com custo de 1 estúdio)

| unidade | estúdio | faturamento maduro p10 · p50 · p90 | alunos p10 · p50 · p90 | margem EBITDA p10 · p50 · p90 | payback (meses) p10 · p50 · p90 | chance de ser viável | real no simulador: faturamento / payback |
|---|---|---|---|---|---|---|---|
| unidade típica (mediana das previsões, nível 2026) | não | 144 mil · **215 mil** · 358 mil | 1,209 · 1,827 · 3,078 | 22% · 36% · 47% | >60 · 50 · 24 | **38%** | – |
| MOCOCA | não | 161 mil · **240 mil** · 400 mil | 1,356 · 2,047 · 3,446 | 27% · 39% · 48% | >60 · 41 · 21 | **41%** | 122 mil / >60 |
| ALEXANDRINA | não | 119 mil · **177 mil** · 295 mil | 989 · 1,499 · 2,531 | 14% · 30% · 43% | >60 · >60 · 30 | **21%** | 150 mil / >60 |
| JARDIM APURA | não | 103 mil · **154 mil** · 256 mil | 853 · 1,295 · 2,191 | 6% · 25% · 40% | >60 · >60 · 37 | **10%** | 114 mil / >60 |
| CPA | não | 156 mil · **233 mil** · 389 mil | 1,318 · 1,989 · 3,350 | 26% · 38% · 48% | >60 · 43 · 21 | **41%** | 193 mil / 60 |
| UNAI | não | 123 mil · **184 mil** · 307 mil | 1,029 · 1,558 · 2,629 | 16% · 31% · 44% | >60 · >60 · 29 | **21%** | 153 mil / >60 |
| CESARIO | não | 128 mil · **191 mil** · 320 mil | 1,074 · 1,625 · 2,741 | 18% · 33% · 45% | >60 · >60 · 27 | **21%** | 157 mil / >60 |
| TAGUATINGA SUL | sim | 137 mil · **205 mil** · 342 mil | 1,153 · 1,743 · 2,939 | 16% · 32% · 44% | >60 · >60 · 26 | **21%** | 180 mil / >60 |
| FLORIANO | não | 131 mil · **196 mil** · 326 mil | 1,098 · 1,660 · 2,801 | 18% · 33% · 45% | >60 · 59 · 27 | **21%** | 198 mil / 57 |
| PARANOA PARQUE | sim | 169 mil · **253 mil** · 422 mil | 1,433 · 2,161 · 3,636 | 25% · 38% · 48% | >60 · 41 · 20 | **41%** | 271 mil / 37 |
| COTIA | não | 101 mil · **150 mil** · 251 mil | 834 · 1,266 · 2,143 | 5% · 24% · 40% | >60 · >60 · 38 | **8%** | 155 mil / >60 |
| CAMBUI CAMPINAS | não | 103 mil · **154 mil** · 258 mil | 857 · 1,301 · 2,201 | 7% · 25% · 40% | >60 · >60 · 37 | **10%** | 191 mil / >60 |
| BOTANIC MALL | sim | 187 mil · **279 mil** · 466 mil | 1,586 · 2,390 · 4,019 | 29% · 40% · 49% | >60 · 35 · 18 | **56%** | 358 mil / 25 |
| VILA GUANABARA | não | 138 mil · **206 mil** · 343 mil | 1,156 · 1,747 · 2,946 | 21% · 35% · 46% | >60 · 54 · 25 | **26%** | 281 mil / 32 |
| VALPARAISO | sim | 149 mil · **222 mil** · 370 mil | 1,251 · 1,889 · 3,182 | 20% · 34% · 46% | >60 · 52 · 24 | **38%** | 348 mil / 26 |
| NOROESTE | sim | 264 mil · **394 mil** · 658 mil | 2,255 · 3,389 · 5,686 | 39% · 47% · 53% | 38 · 22 · 13 | **87%** | 693 mil / 12 |
| BUTANTA | sim | 178 mil · **266 mil** · 444 mil | 1,507 · 2,272 · 3,822 | 27% · 39% · 48% | >60 · 38 · 19 | **46%** | 455 mil / 19 |
| CARIACICA | sim | 130 mil · **194 mil** · 324 mil | 1,089 · 1,647 · 2,778 | 14% · 30% · 43% | >60 · >60 · 28 | **21%** | 344 mil / 26 |
| BOTAFOGO | sim | 158 mil · **237 mil** · 395 mil | 1,337 · 2,018 · 3,398 | 22% · 36% · 47% | >60 · 46 · 22 | **41%** | 697 mil / 12 |

**Conferência da chance (sem vazamento: só os 39 erros do treino; 'viável' = seria viável no simulador com o faturamento real e custos-padrão):** das 2 unidades com chance ≥ 50%, 2 seriam viáveis; das 16 com chance < 50%, 5. Brier 0.175 contra 0.238 da taxa-base (7/18 viáveis).

## 5. Depois de abrir (referência do UNI-03; outra grandeza)

- Antes de abrir (v2, faixa adotada de 80%): faturamento maduro de -37% a +58% em torno da previsão.
- UNI-03 mede outra coisa: o erro dos **alunos** maduros (meses 11–13) projetados do mês k. No mês 3: −20% a +23% (p10–p90 da exploração), com cobertura de 77% na confirmação; no mês 6: −13% a +11%, com cobertura de 64% (abaixo do nominal). Leitura: depois de abrir, os 3 primeiros meses dão uma referência bem mais estreita sobre o volume; a comparação direta com a faixa de faturamento não é exata.

## Insumos (SHA-256)

- `protocolo_uni07.md`: `b5854bc92929795de36db213dcae7f3dc9369f98de4a2d6adb9052e255a4990f`
- `01_incerteza.py`: `16189a95d5309184ee5cc0ed92b7adf17f7db78733600fc0d42f741bff3d6569`
- `fato_unidade_mes.parquet`: `cffc6b276d930905ace08bffe1c5f0b7e15d207b5fd7389c8afd0a19ebc8fa87`
- `dim_unidade.parquet`: `c6ecef57365c1ac8730802386adb55eb5610a056665b0999746ccb12395230b8`
- `master_id_cadastro.csv`: `bdc8ecbb2db49b339590ed1e8f3272b89407ad72a0286993d5150393c67120c9`
- `confirmacao_por_unidade.csv`: `ba9b3e9f9f45ebdd238b6214bb67f5c4ca4ce6ffd5677341b6e4be257f5cbbe9`
- `01_comparacao.py`: `7320ae60a18db68d7a1ff93c2bf8953fa80f6aa15db5eb6c285fd8b435495508`
- `01_exploracao.py`: `d4147998b23859bcb4d813d7cbd724f3a0e321cb3b0f27f7f45493db244f7c8d`
- `01_alavancas.py`: `4b6cefdeb5c862b1ccb3a088998462943178b350200bec1c7941adbca2aaa616`
- `01_confirmacao.py`: `e61ad34fb7023b5f3c098e3628541c2d7a7f344b5ce68461872b56334a11d7cf`
- `config.py`: `d8e45927a3d4c10428d3fca47edd26de76efbe70b88c459e039d2480b9846faa`
- `simulador.py`: `e06af858a2b5c3bde7befc409e0ee20c88205eb52b5209c57fcad5b14e59c2c3`
