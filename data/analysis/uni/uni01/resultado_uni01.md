# BLK-UNI-01 — resultado da exploração (dados até dez/2025)

Protocolo: `protocolo_uni01.md` (SHA-256 `835c0e055995a60e…`). Rodado uma vez.

## Amostras

- Primária (maduras, jan–dez/2025, ≥ 3 meses com `mes_vida >= 12`): **40 unidades** em 12 metros; UF {'SP': 16, 'DF': 15, 'GO': 2, 'PR': 2, 'BA': 1, 'RJ': 1, 'RS': 1, 'ES': 1, 'MT': 1}.
- Sensibilidade A (maturidade ajustada; nível medido em 2025 com `mes_vida >= 6`): 55 unidades. Efeito da faixa no log do faturamento, contra 24+: {'f06': np.float64(-0.081), 'f09': np.float64(-0.025), 'f12': np.float64(0.017), 'f18': np.float64(-0.007)}.
- Sensibilidade B (jan–set/2025): 37 unidades.
- Desvio-padrão entre unidades (primária): log faturamento 0.409, log ativos 0.346, log ticket 0.166, % agregador 0.176, churn 1.90 pp.

## Testes

Efeito = 1 desvio-padrão de X (interação: variação da elasticidade ao m² por 1 dp do modificador). IC 90% HC3 (T12: agrupado por município). ΔR² LOO contra a base nas mesmas unidades. Estável = mesmo sinal ao retirar cada metro (T12: município; entre parênteses, quantas retiradas). A e B = efeito nas sensibilidades.

| teste | destino | hipótese | Y | sinal esp. | N | efeito | IC 90% | ΔR² LOO | estável | A | B | mín. detectável | classe | falhou |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| T01 | mecanismo | renda x ticket | l_ticket | + | 39 | +8.0% | [+3.5%, +12.7%] | +0.201 | sim (11) | +11.3% | +7.5% | 6.6% | **candidata** |  |
| T02 | mecanismo | renda x agregador | agr | ± | 39 | -0.4 p.f. | [-5.0 p.f., +4.3 p.f.] | -0.056 | não (11) | -1.6 p.f. | -1.2 p.f. | 7.1 p.f. | **inconclusiva** |  |
| T03 | mecanismo | tier Wellhub x ticket | l_ticket | ± | 39 | +3.8% | [-1.8%, +9.7%] | -0.022 | sim (11) | +4.9% | +3.6% | 8.7% | **descartada** |  |
| T04 | mecanismo | tier Wellhub x agregador | agr | − | 39 | +1.9 p.f. | [-4.2 p.f., +8.0 p.f.] | -0.052 | não (11) | +1.3 p.f. | +2.5 p.f. | 9.2 p.f. | **inconclusiva** |  |
| T05 | UNI-02 | preco relativo a concorrencia | l_fat | ± | 38 | +7.7% | [-5.5%, +22.7%] | -0.018 | não (10) | +9.2% | +9.1% | 21.7% | **inconclusiva** |  |
| T06 | UNI-06 | agregador traz volume | l_ativos | + | 39 | +17.9% | [+8.5%, +28.0%] | +0.210 | sim (11) | +5.8% | +18.5% | 13.2% | **candidata** |  |
| T07 | UNI-06 | agregador dilui ticket | l_ticket | − | 39 | -10.4% | [-12.9%, -7.9%] | +0.499 | sim (11) | -9.8% | -10.5% | 4.3% | **candidata** |  |
| T08 | UNI-02 | tamanho x praca boa (diretor) | l_fat | + | 39 | -0.323 | [-0.770, +0.124] | -0.001 | sim (11) | -0.354 | -0.307 | 0.672 | **inconclusiva** |  |
| T09 | UNI-02 | tamanho x concorrencia de estrutura menor (diretor) | l_fat | + | 39 | +0.344 | [+0.037, +0.651] | +0.021 | sim (11) | +0.358 | +0.315 | 0.461 | **candidata** |  |
| T10 | UNI-02 | saturacao x faturamento | l_fat | − | 39 | +5.3% | [-12.1%, +26.2%] | -0.037 | sim (11) | +3.2% | +5.3% | 31.3% | **inconclusiva** |  |
| T11 | mecanismo | saturacao x volume | l_ativos | − | 39 | +2.9% | [-13.5%, +22.5%] | -0.051 | não (11) | -0.8% | +3.7% | 29.9% | **inconclusiva** |  |
| T12 | UNI-02 | crescimento do municipio | l_fat | + | 39 | -2.6% | [-12.1%, +7.9%] | -0.032 | sim (17) | +4.7% | -2.1% | 16.6% | **inconclusiva** |  |
| T13 | UNI-02 | crescimento do hexagono | l_fat | + | 36 | -3.2% | [-12.3%, +6.8%] | -0.020 | não (10) | +2.2% | -1.7% | 15.9% | **inconclusiva** |  |
| T14 | UNI-06 | demanda revelada TotalPass (so' local) | l_fat | + | 39 | +14.4% | [+3.4%, +26.5%] | +0.056 | sim (11) | +2.9% | +14.0% | 16.3% | **candidata** |  |
| T15 | UNI-02 | populacao a pe na mesma cidade | l_fat | + | 31 | -8.7% | [-24.0%, +9.7%] | -0.030 | não (4) | -2.2% | -8.3% | 31.7% | **inconclusiva** |  |
| T16 | UNI-06 | rampa preve o nivel maduro | l_ativos | + | 30 | +32.3% | [+24.5%, +40.6%] | +0.632 | sim (10) | +36.3% | +32.5% | 9.5% | **candidata** |  |
| T17 | mecanismo | renda x churn | churn | − | 39 | -1.29 pp | [-1.72 pp, -0.86 pp] | +0.491 | sim (11) | -1.25 pp | -1.31 pp | 0.65 pp | **candidata** |  |
| T18 | UNI-06 | agregador x churn | churn | ± | 39 | +0.64 pp | [+0.18 pp, +1.11 pp] | +0.085 | sim (11) | +0.59 pp | +0.76 pp | 0.70 pp | **candidata** |  |
| T19 | mecanismo | saturacao x churn | churn | + | 39 | -0.21 pp | [-1.00 pp, +0.59 pp] | -0.036 | não (11) | -0.79 pp | -0.47 pp | 1.19 pp | **inconclusiva** |  |

Contagem: {'inconclusiva': 10, 'candidata': 8, 'descartada': 1}.

**Candidatas ao UNI-02** (Y1, X conhecido antes de abrir; no máximo 2, por ΔR² LOO): T09 (tamanho x concorrencia de estrutura menor (diretor), ΔR² LOO +0.021).

Unidades com valor ≤ 0 em atributo logaritmizado (viram ausentes): {'tam_metragem_m2': 0, 'iso_renda_pc__carro_10': 0, 'iso_pop__carro_10': 0, 'conc_alunos_por_mil_hab__carro_10': 0, 'iso_pop__pe_15': 0, 'rampa_ativos_m3': 0}.

## Descritivos

- **% agregador por UF** (média dos 6 últimos meses válidos até dez/25, `mes_vida >= 6`; unidades na rede hoje por UF: {'SP': 30, 'DF': 28, 'RJ': 13, 'GO': 5, 'MG': 5, 'PR': 5, 'MT': 4, 'ES': 3, 'SC': 2, 'BA': 1, 'PE': 1, 'RS': 1}):

| UF | unidades | mediana | mín. | máx. |
|---|---|---|---|---|
| SP | 21 | 55% | 36% | 77% |
| DF | 20 | 29% | 19% | 53% |
| GO | 4 | 30% | 15% | 33% |
| RJ | 3 | 0% | 0% | 64% |
| MG | 3 | 34% | 20% | 47% |
| PR | 2 | 40% | 21% | 58% |
| ES | 2 | 51% | 45% | 57% |
| MT | 2 | 28% | 25% | 32% |
| BA | 1 | 1% | 1% | 1% |
| RS | 1 | 55% | 55% | 55% |
| SC | 1 | 25% | 25% | 25% |

- **Tier do agregador × renda da praça** (Spearman, todas as unidades com os dois): Wellhub ρ = +0.53 (N = 69, p = 0.000); TotalPass ρ = +0.20 (N = 62, p = 0.112).

## Insumos (SHA-256)

- `protocolo_uni01.md`: `835c0e055995a60e426159e0411a1510d2e5d813ac5f081fcdef4b5fb0afa740`
- `01_exploracao.py`: `d4147998b23859bcb4d813d7cbd724f3a0e321cb3b0f27f7f45493db244f7c8d`
- `fato_unidade_mes.parquet`: `cffc6b276d930905ace08bffe1c5f0b7e15d207b5fd7389c8afd0a19ebc8fa87`
- `dim_unidade.parquet`: `c6ecef57365c1ac8730802386adb55eb5610a056665b0999746ccb12395230b8`
- `LOCAL_demanda_totalpass_por_unidade.parquet`: `80eacc2807979bb64fe165dcc47d52108aad5af1f02f9ce84e0afa14fde02c0c`
