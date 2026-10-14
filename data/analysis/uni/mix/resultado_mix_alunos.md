# BLK-UNI-05C — o que explica a fatia do agregador nos alunos ativos (UX): resultado

Protocolo `protocolo_mix.md` (SHA-256 `311e4509674e0c11…`). Rodado uma vez.

- Exploração (2025, aceita os dois agregadores): **37 unidades**; fatia do agregador nos alunos ativos (UX): mediana 41% (p10 22%, p90 61%); desvio-padrão entre unidades 17.0 p.f. (a faixa de irrelevância de ±5 p.f. equivale a 0.29 desvio-padrão da fatia).
- Aceita só um agregador em 2025: 2 (asa-norte-df (Wellhub), lago-norte-df (Wellhub)); não aceita nenhum: ['boa-vista-ba'].
- Confirmação (novas, maduras em 2026, aceita os dois): **13 unidades**; mediana 44%.
- R² LOO só com renda e população (amostra comum, N = 37): 0.008.

## Testes

Efeito em pontos de fração por 1 desvio-padrão de X (X7: diferença bruta shopping × não). Controles: renda e população c10. IC HC3 e IC agrupado por metro. A e B entram na classificação; S (inclui quem aceita só um, com aceitação como controle) e C (sem anomalias) são reportadas.

| teste | X | natureza | sinal esp. | N | efeito | IC 90% HC3 | IC 90% por metro | ΔR² LOO | estável metro / UF | h máx. | A | B | S | C | classe |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| X1 | renda da praça | antes de abrir | ± | 37 | **+0.9 p.f.** | [-3.5 p.f.; +5.2 p.f.] | [-3.1 p.f.; +4.9 p.f.] (11 metros) | -0.042 | não / sim | 0.26 | +0.2 p.f. | -0.2 p.f. | +0.9 p.f. | +2.3 p.f. | **inconclusiva** |
| X2 | escritórios a pé | antes de abrir | + | 36 | **+7.9 p.f.** | [+3.4 p.f.; +12.5 p.f.] | [+4.9 p.f.; +11.0 p.f.] (11 metros) | +0.153 | sim / sim | 0.33 | +7.6 p.f. | +7.2 p.f. | +7.8 p.f. | +8.2 p.f. | **candidata** |
| X3 | demanda revelada de TotalPass | foto atual | + | 37 | **+11.1 p.f.** | [+5.8 p.f.; +16.4 p.f.] | [+5.2 p.f.; +17.0 p.f.] (11 metros) | +0.298 | sim / sim | 0.26 | +10.9 p.f. | +11.6 p.f. | +10.9 p.f. | +10.5 p.f. | **candidata** |
| X4 | tier do Wellhub | decisão do operador | ± | 37 | **+2.6 p.f.** | [-2.7 p.f.; +8.0 p.f.] | [-4.3 p.f.; +9.6 p.f.] (11 metros) | -0.031 | não / não | 0.26 | +0.4 p.f. | +3.0 p.f. | +2.6 p.f. | +4.7 p.f. | **inconclusiva** |
| X5 | independentes no agregador | foto atual | ± | 37 | **+21.3 p.f.** | [+11.7 p.f.; +30.8 p.f.] | [+12.8 p.f.; +29.7 p.f.] (11 metros) | +0.330 | sim / sim | 0.31 | +21.1 p.f. | +21.0 p.f. | +20.6 p.f. | +20.7 p.f. | **candidata** |
| X6 | preço do plano Gold | decisão do operador | ± | 37 | **+7.9 p.f.** | [+0.7 p.f.; +15.0 p.f.] | [+2.0 p.f.; +13.7 p.f.] (11 metros) | +0.083 | sim / sim | 0.32 | +6.7 p.f. | +7.2 p.f. | +7.7 p.f. | +7.4 p.f. | **candidata** |
| X7 | em shopping | antes de abrir | ± | 36 | **+8.8 p.f.** | [-6.8 p.f.; +24.4 p.f.] | [-1.3 p.f.; +18.9 p.f.] (11 metros) | -0.045 | sim / sim | 0.34 | +7.6 p.f. | +7.2 p.f. | +8.2 p.f. | +10.1 p.f. | **inconclusiva** |

Contagem: {'candidata': 4, 'inconclusiva': 3}.

## Confirmação (unidades novas, 2026)

| teste | X | N | erro médio: só controles → com X | IC 90% da diferença | com intercepto reajustado | Spearman | leitura |
|---|---|---|---|---|---|---|---|
| X1 | renda da praça | 13 | 7.3 → 7.1 p.f. | [-0.5; +0.1] | 6.4 → 6.1 p.f. | +0.65 → +0.72 | não se repete |
| X2 | escritórios a pé | 13 | 7.2 → 5.9 p.f. | [-3.8; +1.3] | 6.2 → 5.9 p.f. | +0.65 → +0.70 | não se repete |
| X3 | demanda revelada de TotalPass | 13 | 7.1 → 8.9 p.f. | [-1.5; +5.1] | 6.1 → 6.9 p.f. | +0.72 → +0.60 | não se repete |
| X4 | tier do Wellhub | 13 | 7.1 → 6.2 p.f. | [-2.0; +0.2] | 6.1 → 6.2 p.f. | +0.72 → +0.76 | não se repete |
| X5 | independentes no agregador | 13 | 7.1 → 13.9 p.f. | [+1.0; +12.6] | 6.1 → 14.6 p.f. | +0.72 → +0.33 | não se repete |
| X6 | preço do plano Gold | 13 | 7.1 → 7.6 p.f. | [-1.5; +2.4] | 6.1 → 7.2 p.f. | +0.72 → +0.70 | não se repete |
| X7 | em shopping | 13 | 7.2 → 7.6 p.f. | [-0.8; +1.4] | 6.2 → 6.7 p.f. | +0.65 → +0.70 | não se repete |

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

| grupo | unidades | fatia nos alunos ativos (UX) (mediana) | fatia na receita (Financeiro) (mediana) |
|---|---|---|---|
| UF DF | 17 | 27% | 15% |
| UF ES | 2 | 49% | 31% |
| UF GO | 4 | 32% | 15% |
| UF MG | 3 | 44% | 29% |
| UF MT | 2 | 34% | 18% |
| UF PR | 2 | 38% | 28% |
| UF RJ | 1 | 61% | 36% |
| UF RS | 1 | 57% | 33% |
| UF SP | 18 | 53% | 37% |
| regional DF/GO | 21 | 30% | 15% |
| regional ES | 2 | 49% | 31% |
| regional PR | 3 | 56% | 40% |
| regional RJ/SP 01 | 7 | 61% | 36% |
| regional SP 02 | 2 | 64% | 47% |
| regional SP 03 | 2 | 49% | 36% |
| regional ULTRA | 13 | 44% | 29% |

Spearman entre fatia nos alunos ativos (UX) e fatia na receita (Financeiro): +0.96.

## Insumos (SHA-256)

- `protocolo_mix.md`: `311e4509674e0c11ab29d5ab768bac7ea7749b63bc8afccc271f8da760967825`
- `01_mix.py`: `d608f102cd8ee0ef5c02bf0ecad653e2c82253e89e4d017e150d9f5dee789356`
- `01_exploracao.py`: `d4147998b23859bcb4d813d7cbd724f3a0e321cb3b0f27f7f45493db244f7c8d`
- `fato_unidade_mes.parquet`: `cffc6b276d930905ace08bffe1c5f0b7e15d207b5fd7389c8afd0a19ebc8fa87`
- `dim_unidade.parquet`: `c6ecef57365c1ac8730802386adb55eb5610a056665b0999746ccb12395230b8`
- `LOCAL_demanda_totalpass_por_unidade.parquet`: `80eacc2807979bb64fe165dcc47d52108aad5af1f02f9ce84e0afa14fde02c0c`
