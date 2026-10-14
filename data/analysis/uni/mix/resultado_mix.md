# BLK-UNI-05C — o que explica a fatia do agregador: resultado

Protocolo `protocolo_mix.md` (SHA-256 `3ba12fa43d4cca94…`). Rodado uma vez.

- Exploração (2025, aceita os dois agregadores): **37 unidades**; fatia do agregador na receita: mediana 27% (p10 11%, p90 40%); desvio-padrão entre unidades 13.2 p.f. (a faixa de irrelevância de ±5 p.f. equivale a 0.38 desvio-padrão da fatia).
- Aceita só um agregador em 2025: 2 (asa-norte-df (Wellhub), lago-norte-df (Wellhub)); não aceita nenhum: ['boa-vista-ba'].
- Confirmação (novas, maduras em 2026, aceita os dois): **13 unidades**; mediana 26%.
- R² LOO só com renda e população (amostra comum, N = 37): 0.004.

## Testes

Efeito em pontos de fração por 1 desvio-padrão de X (X7: diferença bruta shopping × não). Controles: renda e população c10. IC HC3 e IC agrupado por metro. A e B entram na classificação; S (inclui quem aceita só um, com aceitação como controle) e C (sem anomalias) são reportadas.

| teste | X | natureza | sinal esp. | N | efeito | IC 90% HC3 | IC 90% por metro | ΔR² LOO | estável metro / UF | h máx. | A | B | S | C | classe |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| X1 | renda da praça | antes de abrir | ± | 37 | **+0.5 p.f.** | [-3.0 p.f.; +4.0 p.f.] | [-1.8 p.f.; +2.7 p.f.] (11 metros) | -0.046 | não / sim | 0.26 | -0.2 p.f. | -0.2 p.f. | +0.5 p.f. | +1.4 p.f. | **descartada** |
| X2 | escritórios a pé | antes de abrir | + | 36 | **+5.8 p.f.** | [+2.2 p.f.; +9.5 p.f.] | [+3.5 p.f.; +8.1 p.f.] (11 metros) | +0.133 | sim / sim | 0.33 | +5.4 p.f. | +5.5 p.f. | +5.7 p.f. | +5.8 p.f. | **candidata** |
| X3 | demanda revelada de TotalPass | foto atual | + | 37 | **+8.7 p.f.** | [+4.9 p.f.; +12.6 p.f.] | [+4.9 p.f.; +12.6 p.f.] (11 metros) | +0.308 | sim / sim | 0.26 | +8.4 p.f. | +8.8 p.f. | +8.5 p.f. | +8.4 p.f. | **candidata** |
| X4 | tier do Wellhub | decisão do operador | ± | 37 | **+3.8 p.f.** | [-0.2 p.f.; +7.7 p.f.] | [-1.7 p.f.; +9.2 p.f.] (11 metros) | +0.017 | sim / não | 0.26 | +2.0 p.f. | +3.9 p.f. | +3.8 p.f. | +5.2 p.f. | **inconclusiva** |
| X5 | independentes no agregador | foto atual | ± | 37 | **+16.5 p.f.** | [+8.7 p.f.; +24.3 p.f.] | [+9.7 p.f.; +23.4 p.f.] (11 metros) | +0.321 | sim / sim | 0.31 | +16.3 p.f. | +16.2 p.f. | +15.9 p.f. | +16.2 p.f. | **candidata** |
| X6 | preço do plano Gold | decisão do operador | ± | 37 | **+5.6 p.f.** | [-0.1 p.f.; +11.3 p.f.] | [+1.0 p.f.; +10.2 p.f.] (11 metros) | +0.048 | sim / sim | 0.32 | +4.6 p.f. | +5.1 p.f. | +5.5 p.f. | +5.3 p.f. | **inconclusiva** |
| X7 | em shopping | antes de abrir | ± | 36 | **+7.9 p.f.** | [-4.3 p.f.; +20.0 p.f.] | [+0.8 p.f.; +14.9 p.f.] (11 metros) | -0.030 | sim / sim | 0.34 | +7.0 p.f. | +7.6 p.f. | +7.5 p.f. | +8.7 p.f. | **inconclusiva** |

Contagem: {'candidata': 3, 'inconclusiva': 3, 'descartada': 1}.

## Confirmação (unidades novas, 2026)

| teste | X | N | erro médio: só controles → com X | IC 90% da diferença | com intercepto reajustado | Spearman | leitura |
|---|---|---|---|---|---|---|---|
| X1 | renda da praça | 13 | 7.1 → 6.9 p.f. | [-0.3; -0.1] | 7.0 → 6.7 p.f. | +0.47 → +0.47 | consistente |
| X2 | escritórios a pé | 13 | 6.8 → 5.6 p.f. | [-3.2; +0.8] | 6.7 → 5.5 p.f. | +0.54 → +0.73 | não se repete |
| X3 | demanda revelada de TotalPass | 13 | 6.9 → 7.5 p.f. | [-2.0; +3.4] | 6.7 → 5.3 p.f. | +0.47 → +0.67 | não se repete |
| X4 | tier do Wellhub | 13 | 6.9 → 6.4 p.f. | [-2.0; +1.1] | 6.7 → 6.2 p.f. | +0.47 → +0.62 | não se repete |
| X5 | independentes no agregador | 13 | 6.9 → 11.5 p.f. | [-0.1; +9.2] | 6.7 → 11.4 p.f. | +0.47 → +0.52 | não se repete |
| X6 | preço do plano Gold | 13 | 6.9 → 7.1 p.f. | [-1.2; +1.6] | 6.7 → 6.4 p.f. | +0.47 → +0.48 | não se repete |
| X7 | em shopping | 13 | 6.8 → 7.3 p.f. | [-0.7; +1.7] | 6.7 → 7.1 p.f. | +0.54 → +0.51 | não se repete |

## Correlações entre os X (Spearman, exploração)

| | l_renda | escritorios | l_tpd | tier_wh | l_indep | preco | shopping |
|---|---|---|---|---|---|---|---|
| l_renda | +1.00 | +0.50 | +0.31 | +0.56 | +0.50 | +0.48 | +0.21 |
| escritorios | +0.50 | +1.00 | +0.08 | +0.62 | +0.26 | +0.53 | +0.35 |
| l_tpd | +0.31 | +0.08 | +1.00 | +0.11 | +0.73 | +0.25 | +0.11 |
| tier_wh | +0.56 | +0.62 | +0.11 | +1.00 | +0.16 | +0.38 | +0.28 |
| l_indep | +0.50 | +0.26 | +0.73 | +0.16 | +1.00 | +0.41 | +0.14 |
| preco | +0.48 | +0.53 | +0.25 | +0.38 | +0.41 | +1.00 | +0.34 |
| shopping | +0.21 | +0.35 | +0.11 | +0.28 | +0.14 | +0.34 | +1.00 |

## Descritivo por UF e regional do Growth (exploração + confirmação; aceita os dois)

| grupo | unidades | fatia na receita (mediana) | fatia nos alunos, UX (mediana) |
|---|---|---|---|
| UF DF | 17 | 15% | 27% |
| UF ES | 2 | 31% | 49% |
| UF GO | 4 | 15% | 32% |
| UF MG | 3 | 29% | 44% |
| UF MT | 2 | 18% | 34% |
| UF PR | 2 | 28% | 38% |
| UF RJ | 1 | 36% | 61% |
| UF RS | 1 | 33% | 57% |
| UF SP | 18 | 37% | 53% |
| regional DF/GO | 21 | 15% | 30% |
| regional ES | 2 | 31% | 49% |
| regional PR | 3 | 40% | 56% |
| regional RJ/SP 01 | 7 | 36% | 61% |
| regional SP 02 | 2 | 47% | 64% |
| regional SP 03 | 2 | 36% | 49% |
| regional ULTRA | 13 | 29% | 44% |

Spearman entre fatia na receita e fatia nos alunos: +0.96.

## Insumos (SHA-256)

- `protocolo_mix.md`: `3ba12fa43d4cca949f11f276adffe4edb38990b71cd8be5ae5cb9c59c9ceb4da`
- `01_mix.py`: `3f3b787dba80aeeec27121db4ca19b314a84c20c2e5dc4a9f0a9ca05b41da144`
- `01_exploracao.py`: `d4147998b23859bcb4d813d7cbd724f3a0e321cb3b0f27f7f45493db244f7c8d`
- `fato_unidade_mes.parquet`: `cffc6b276d930905ace08bffe1c5f0b7e15d207b5fd7389c8afd0a19ebc8fa87`
- `dim_unidade.parquet`: `c6ecef57365c1ac8730802386adb55eb5610a056665b0999746ccb12395230b8`
- `LOCAL_demanda_totalpass_por_unidade.parquet`: `80eacc2807979bb64fe165dcc47d52108aad5af1f02f9ce84e0afa14fde02c0c`
