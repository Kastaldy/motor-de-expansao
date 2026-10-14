# BLK-UNI-05B — alavancas do operador: resultado

Protocolo `protocolo_alavancas.md` (SHA-256 `4a2d213ee097f0ee…`). Rodado uma vez.

## D — Quanto rende um aluno de agregador (premissa do simulador)

- 418 meses de 43 unidades maduras em 2025 (0 meses fora: sem alunos de agregador, sem recorrentes ou com componente do Financeiro ausente).
- Receita mensal por aluno de agregador: **R$ 62**. Por recorrente: **R$ 136** (R$ 136 sem o desconto do Tem Saúde, que é 0.0% do faturamento na mediana).
- **ρ = 47%** (mediana dos meses; quartis 42–57%; mediana por unidade 48%; bruto 47%). Wellhub 47% (413 meses), TotalPass 50% (395 meses). **O simulador supõe 60%.**

## A — Aceitar agregador (entrada do TotalPass, dentro da unidade)

### Eventos

| unidade | 1º mês com TotalPass | 1º mês com receita TP no Financeiro | mês de vida | meses antes | meses depois | controles | testa o placebo | papel |
|---|---|---|---|---|---|---|---|---|
| augusta-sp | 2022-06 | 2022-04 | 17 | 1 | 13 (11 com receita) | 0 | não | fora (datação: Financeiro antes) |
| santos-sp | 2022-10 | 2023-10 | 10 | 4 | 13 (1 com receita) | 7 | não | principal |
| taubate-sp | 2022-10 | 2023-10 | 6 | 0 | 13 (1 com receita) | 7 | não | fora |
| aclimacao-sp | 2023-01 | 2023-10 | 24+ (placeholder) | 8 | 13 (4 com receita) | 2 | sim | sensibilidade |
| mooca-sp | 2023-01 | 2023-10 | 24+ (placeholder) | 8 | 13 (4 com receita) | 2 | sim | sensibilidade |
| plaza-sul-sp | 2023-01 | 2023-10 | 24+ (placeholder) | 8 | 13 (4 com receita) | 2 | sim | sensibilidade |
| campo-limpo-sp | 2023-01 | 2023-10 | 1 | 0 | 8 (4 com receita) | 2 | não | fora |
| vila-mariana-sp | 2023-01 | 2023-10 | 24+ (placeholder) | 8 | 13 (4 com receita) | 2 | sim | sensibilidade |
| jundiai-sp | 2023-02 | 2023-10 | 18 | 9 | 13 (5 com receita) | 2 | sim | sensibilidade |
| brasilandia-sp | 2023-02 | 2023-10 | 8 | 2 | 13 (5 com receita) | 2 | não | fora |
| vila-guilherme-sp | 2023-02 | 2023-10 | 6 | 0 | 13 (5 com receita) | 2 | não | fora |
| cruzeiro-df | 2023-03 | 2023-10 | 2 | 0 | 9 (6 com receita) | 2 | não | fora |
| aguas-claras-df | 2023-05 | 2023-10 | 2 | 0 | 9 (9 com receita) | 2 | não | fora |
| cabo-frio-rj | 2023-07 | 2023-08 | 1 | 0 | 8 (8 com receita) | 3 | não | fora |
| lago-sul-df | 2023-10 | 2023-10 | 23 | 12 | 13 (13 com receita) | 3 | sim | principal |
| sobradinho-df | 2023-10 | 2023-10 | 3 | 0 | 10 (10 com receita) | 3 | não | fora |
| arapoanga-planaltina-df | 2023-11 | 2023-11 | 1 | 0 | 8 (8 com receita) | 5 | não | fora |
| setor-oeste-go | 2023-12 | 2023-02 | 10 | 4 | 13 (13 com receita) | 6 | não | fora (datação: Financeiro antes) |
| ceilandia-df | 2024-01 | 2023-11 | 2 | 0 | 9 (9 com receita) | 5 | não | fora (datação: Financeiro antes) |
| jardim-botanico-df | 2024-03 | 2024-07 | 16 | 10 | 13 (13 com receita) | 13 | sim | principal |
| serra-es | 2024-05 | 2024-05 | 1 | 0 | 8 (8 com receita) | 14 | não | fora |
| campo-largo-pr | 2024-05 | 2024-05 | 1 | 0 | 8 (8 com receita) | 14 | não | fora |
| unai-mg | 2025-04 | 2025-04 | 1 | 0 | 4 (4 com receita) | 27 | não | fora |
| alexandrina-go | 2025-06 | 2025-01 | 5 | 0 | 6 (6 com receita) | 34 | não | fora (datação: Financeiro antes) |
| americana-centro-sp | 2025-09 | 2025-09 | 1 | 0 | 0 (0 com receita) | 38 | não | fora |
| buritis-mg | 2025-09 | 2025-09 | 1 | 0 | 0 (0 com receita) | 38 | não | fora |
| sao-goncalo-shopping-rj | 2025-12 | nan | 3 | 0 | 0 (0 com receita) | 0 | não | fora |

### Efeito de passar a aceitar o TotalPass

Estimativa principal: 3 unidades tratadas, 15 unidades no total, 521 meses-unidade. Nos desfechos de receita (faturamento, ticket): 3 tratadas, 433 meses-unidade (meses sem a linha TotalPass no Financeiro ficam fora).

| desfecho | principal | IC 90% (CR1) | placebo (evento 6 meses antes) | IC placebo |
|---|---|---|---|---|
| total de alunos | **+8.8%** | [-0.1%; +18.6%] | +8.2% | [+1.0%; +15.8%] |
| recorrentes (balcão) | **+17.9%** | [+1.7%; +36.7%] | +16.3% | [+2.8%; +31.5%] |
| faturamento | **+10.2%** | [-0.6%; +22.1%] | +2.0% | [-7.9%; +12.9%] |
| ticket médio | **+3.7%** | [-1.9%; +9.7%] | -1.1% | [-8.2%; +6.7%] |

IC 90% do faturamento por bootstrap de unidades: [-0.3%; +27.2%]. Eventos que testam o placebo: 2 de 3.

**Sensibilidades** (efeito no faturamento, alunos, recorrentes, ticket; N tratadas):

| sensibilidade | tratadas | alunos | recorrentes | faturamento | ticket |
|---|---|---|---|---|---|
| 1. com o grupo de SP de 2023-01/02 | 8 | -5.8% [-13.0%; +2.0%] | -3.6% [-16.1%; +10.7%] | -6.6% [-17.4%; +5.5%] | +1.3% [-5.0%; +8.0%] |
| 2. só meses com mes_vida ≥ 12 | 3 | +5.4% [-0.4%; +11.6%] | +17.7% [+1.1%; +36.9%] | +7.5% [-1.8%; +17.6%] | +1.8% [-4.4%; +8.4%] |
| 3. controles só 'nunca' e 'ainda não' (eventos principais com ≥ 2 controles) | 2 | +2.3% [+0.9%; +3.7%] | -0.2% [-2.6%; +2.2%] | -1.2% [-3.1%; +0.8%] | -2.6% [-5.6%; +0.5%] |
| 4. sem placeholder como controle | 3 | +9.7% [-0.1%; +20.5%] | +17.7% [+1.1%; +37.0%] | +9.6% [-1.6%; +22.1%] | +2.8% [-2.2%; +7.9%] |

(Grupo de SP na sensibilidade 1: 5 eventos, com 2 controles.)

**Retirando cada evento** (efeito principal sem ele):

| evento retirado | alunos | recorrentes | faturamento | ticket | s |
|---|---|---|---|---|---|
| santos-sp | +11.3% | +24.2% | +10.1% | +2.7% | 3.63 |
| lago-sul-df | +12.9% | +20.6% | +20.1% | +8.1% | -7.41 |
| jardim-botanico-df | +2.0% | +2.6% | +0.7% | -0.4% | -0.43 |

**Cada evento sozinho** (descritivo; um só tratado, sem IC):

| evento | alunos | recorrentes | faturamento | ticket |
|---|---|---|---|---|
| santos-sp (sem faixas) | +1.9% | -0.4% | +10.0% | +16.0% |
| lago-sul-df | +2.0% | +3.9% | -0.1% | -1.8% |
| jardim-botanico-df | +20.1% | +35.1% | +21.5% | +4.9% |

**Perfil no tempo** (meses em relação à entrada; referência = mês −1; o Financeiro recebe o agregador com atraso, então os primeiros meses depois subestimam a receita):

| faixa | alunos | recorrentes | faturamento | ticket |
|---|---|---|---|---|
| −12 a −7 | -9.2% [-15.6%; -2.4%] | -20.2% [-32.3%; -5.8%] | -2.9% [-14.9%; +10.8%] | -0.3% [-9.9%; +10.3%] |
| −6 a −4 | -3.9% [-8.8%; +1.4%] | -8.5% [-15.0%; -1.6%] | -4.3% [-8.9%; +0.5%] | -2.1% [-6.7%; +2.6%] |
| −3 a −2 | +3.5% [+1.3%; +5.8%] | +1.8% [-1.9%; +5.8%] | +4.0% [+1.8%; +6.4%] | +0.6% [-1.5%; +2.8%] |
| 0 a 2 | +5.3% [+2.2%; +8.5%] | +3.0% [-0.1%; +6.1%] | +3.8% [-1.8%; +9.8%] | +0.0% [-4.1%; +4.3%] |
| 3 a 5 | +9.2% [+2.0%; +16.9%] | +8.0% [-1.0%; +17.7%] | +8.9% [+1.1%; +17.3%] | +0.0% [-6.2%; +6.8%] |
| 6 a 8 | +2.8% [-5.6%; +11.9%] | +7.7% [-4.0%; +20.7%] | +9.9% [-0.2%; +21.0%] | +5.0% [-1.8%; +12.2%] |
| 9 a 12 | +4.0% [-3.9%; +12.4%] | +11.1% [-3.1%; +27.4%] | +12.2% [-0.8%; +26.9%] | +6.8% [+0.9%; +13.1%] |

Faixas anteriores ao evento com IC cobrindo zero: total de alunos não; recorrentes (balcão) não; faturamento não; ticket médio sim.

**Leitura (regra do §3): inconclusivo.**
- IC CR1 e bootstrap excluem zero: não.
- Sinal estável ao retirar cada evento: sim.
- Placebo: não testável (2 evento(s) o testam); cobre zero.

### Conta de substituição e "não aceita agregador"

- Em nível, por unidade: -20 alunos de agregador, +192 recorrentes, +173 no total (IC agregadores [-117; +77]; IC recorrentes [+2; +382]).
- **s = 9.79** recorrentes perdidos por aluno de agregador ganho (IC 90% bootstrap [-22.12; 26.56], 1995 reamostras válidas; sinal estável ao retirar cada evento: não).
- Com a fatia típica de agregador da rede (a = 41% dos alunos) e ρ = 47%, uma unidade **sem agregador** fatura **+486%** sobre a previsão da praça (faixa bootstrap conjunta -1113% a +1198%). Referências: sem canibalização (s = 0), -25%; com canibalização total (s = 1), +27%.
- Rótulo de m (§7): **não medida**. É extrapolação: mede-se a entrada de um agregador sobre o Wellhub já aceito.
- Ilustração (não teste), Botafogo: v2 R$ 244,762 → com "sem agregador" R$ 1,435,356 (real R$ 697,407).

### Confirmação de direção: saídas de agregador em 2025–2026

| unidade | agregador | 1º mês sem | com agregador nos 4 anteriores | alunos (média 3 anteriores) | receita Fin. antes → depois | analisável | alunos | recorrentes | faturamento | ticket |
|---|---|---|---|---|---|---|---|---|---|---|
| campo-largo-pr | TotalPass | 2026-05 | 4 | 45 | R$ 1,829 → R$ 0 | sim | -13.9% | -1.0% | +1.1% | +17.4% |
| vila-guanabara-sc | TotalPass | 2026-08 | 2 | 0 | R$ 0 → R$ nan | não | – | – | – | – |
| boa-vista-ba | Wellhub | 2025-03 | 4 | 586 | R$ 31,115 → R$ 0 | não | – | – | – | – |

Saídas consistentes (sinal oposto ao da entrada em alunos e faturamento, em todas as analisáveis): **não** (1 analisável(is)).

## B — Preço, estúdios, modalidades e vagas (39 maduras de 2025, sobre o M0)

Preço e vagas já tinham sido olhados contra o erro do modelo (protocolo §2): para eles, esta parte é exploratória.

| alavanca | desfecho | N | efeito (unidade de negócio) | IC 90% | ΔR² LOO | estável | sens. A | sens. B | classe | falhou |
|---|---|---|---|---|---|---|---|---|---|---|
| preço do plano Gold (por R$ 10) | faturamento | 39 | **+9.7%** | [-1.0%; +21.5%] | +0.016 | sim (11) | +10.4% | +9.8% | inconclusiva |  |
| preço do plano Gold (por R$ 10) | total de alunos | 39 | +11.4% | [-1.8%; +26.3%] | +0.014 | sim (11) | +11.9% | +11.1% |  |  |
| preço do plano Gold (por R$ 10) | ticket médio | 39 | -1.5% | [-5.6%; +2.7%] | -0.063 | não (11) | -1.3% | -1.2% |  |  |
| tem estúdios (ter × não ter) | faturamento | 39 | **+30.3%** | [+6.8%; +59.0%] | +0.069 | sim (11) | +30.7% | +29.9% | candidata |  |
| tem estúdios (ter × não ter) | total de alunos | 39 | +19.1% | [-1.6%; +44.1%] | +0.011 | sim (11) | +20.1% | +16.9% |  |  |
| tem estúdios (ter × não ter) | ticket médio | 39 | +9.4% | [+1.4%; +18.0%] | +0.051 | sim (11) | +8.9% | +11.1% |  |  |
| nº de modalidades (+1 modalidade) | faturamento | 39 | **+5.2%** | [-3.7%; +15.0%] | -0.020 | sim (11) | +5.0% | +4.1% | inconclusiva |  |
| nº de modalidades (+1 modalidade) | total de alunos | 39 | +0.4% | [-6.7%; +8.1%] | -0.042 | não (11) | +0.3% | -0.8% |  |  |
| nº de modalidades (+1 modalidade) | ticket médio | 39 | +4.8% | [+1.8%; +7.8%] | +0.101 | sim (11) | +4.7% | +4.9% |  |  |
| vagas de estacionamento (dobrar as vagas) | faturamento | 39 | **+1.1%** | [-4.6%; +7.2%] | -0.027 | não (11) | +1.0% | +0.4% | inconclusiva |  |
| vagas de estacionamento (dobrar as vagas) | total de alunos | 39 | -3.1% | [-9.9%; +4.3%] | -0.033 | sim (11) | -3.1% | -3.6% |  |  |
| vagas de estacionamento (dobrar as vagas) | ticket médio | 39 | +4.3% | [-0.0%; +8.9%] | +0.099 | sim (11) | +4.3% | +4.1% |  |  |

Classe só no faturamento (regras do UNI-01; faixa de irrelevância ±10% por desvio-padrão).

## C — Confirmação nas unidades de teste (2026)

Ajuste de calendário do UNI-02: -2.0%.

| alavanca | versão | N | erro M0 | erro M0 + alavanca | diferença | IC 90% | ordenação M0 | ordenação M0 + alavanca | leitura |
|---|---|---|---|---|---|---|---|---|---|
| preço do plano Gold | com Botafogo | 18 | 21.5% | 23.3% | +1.8 p.p. | [-10.9; +6.8] | +0.50 | +0.71 | não se repete |
| preço do plano Gold | sem Botafogo | 17 | 20.8% | 23.1% | +2.3 p.p. | [-10.9; +6.1] | +0.49 | +0.66 | não se repete |
| tem estúdios | com Botafogo | 18 | 21.5% | 25.0% | +3.5 p.p. | [-11.0; +9.1] | +0.50 | +0.73 | não se repete |
| tem estúdios | sem Botafogo | 17 | 20.8% | 24.6% | +3.8 p.p. | [-10.8; +8.7] | +0.49 | +0.71 | não se repete |
| nº de modalidades | com Botafogo | 18 | 21.5% | 25.1% | +3.6 p.p. | [-7.7; +6.6] | +0.50 | +0.57 | não se repete |
| nº de modalidades | sem Botafogo | 17 | 20.8% | 22.1% | +1.3 p.p. | [-4.6; +7.4] | +0.49 | +0.56 | não se repete |
| vagas de estacionamento | com Botafogo | 15 | 22.2% | 22.7% | +0.5 p.p. | [-2.2; +0.5] | +0.47 | +0.45 | não se repete |
| vagas de estacionamento | sem Botafogo | 14 | 21.5% | 21.5% | -0.0 p.p. | [-1.9; +0.5] | +0.47 | +0.54 | consistente |

Consistente = consistente com e sem Botafogo.

## Entradas para a v2 (rótulo pelo §7; a decisão é do Felipe)

| alavanca | rótulo | efeito no faturamento |
|---|---|---|
| aceita mais um agregador (TotalPass sobre o Wellhub) | não medida | +10.2% [-0.6%; +22.1%] |
| não aceita agregador (extrapolação pela conta de substituição) | não medida | +486% [-1113%; +1198%] |
| preço do plano Gold (por R$ 10) | não medida | +9.7% [-1.0%; +21.5%] |
| tem estúdios (ter × não ter) | medida, não confirmada | +30.3% [+6.8%; +59.0%] |
| nº de modalidades (+1 modalidade) | não medida | +5.2% [-3.7%; +15.0%] |
| vagas de estacionamento (dobrar as vagas) | não medida | +1.1% [-4.6%; +7.2%] |

## Insumos (SHA-256)

- `protocolo_alavancas.md`: `4a2d213ee097f0eece3304267cd75dc03e07c29f143c22e57646f0bcee5f6ef2`
- `01_alavancas.py`: `4b6cefdeb5c862b1ccb3a088998462943178b350200bec1c7941adbca2aaa616`
- `fato_unidade_mes.parquet`: `cffc6b276d930905ace08bffe1c5f0b7e15d207b5fd7389c8afd0a19ebc8fa87`
- `dim_unidade.parquet`: `c6ecef57365c1ac8730802386adb55eb5610a056665b0999746ccb12395230b8`
- `01_exploracao.py`: `d4147998b23859bcb4d813d7cbd724f3a0e321cb3b0f27f7f45493db244f7c8d`
- `01_confirmacao.py`: `e61ad34fb7023b5f3c098e3628541c2d7a7f344b5ce68461872b56334a11d7cf`
- `metragem_estimada.csv`: `acaa55425abb6ab272329444815b6136d645f317565c7b27c72d912f5c0a3504`
- `comparacao_por_unidade.csv`: `afbb1865631ecd97035afea271895d62a186eebb0cbfc4794d67a8301b4445ef`
