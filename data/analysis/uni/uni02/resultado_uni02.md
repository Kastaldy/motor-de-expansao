# BLK-UNI-02 — confirmação do modelo de faturamento maduro

Protocolo `protocolo_uni02.md` (SHA-256 `fc89a194b7d7db3b…`). Rodado uma vez.

- Treino: 39 maduras de 2025. Teste: **18 unidades** maduras só em 2026 (15 com metragem oficial, 3 por satélite).
- Ajuste de calendário 2025→2026 (mediana nas unidades de treino): -2%.
- Unidades de teste fora do envelope do treino (m², renda ou população): ['unai-mg', 'butanta-sp', 'cambui-campinas-sp', 'cotia-sp', 'mococa-sp'].

## Resultado principal

| modelo | erro típico | viés | ordenação (Spearman) | IC 90% |
|---|---|---|---|---|
| ATUAL | 27% | -17% | +0.35 | [-0.09; +0.74] |
| INGÊNUO | 37% | -19% | +nan | [+nan; +nan] |
| M0 | 22% | +1% | +0.50 | [+0.12; +0.78] |
| M0d | 20% | +8% | +0.51 | [+0.08; +0.85] |

Faixa p10–p90 do M0: cobertura no teste 67% (esperado ≈ 80%).

**M0 se confirma? SIM.** **Hipótese do diretor (M0d) se confirma? SIM.** (critério fixado antes)

## Sensibilidades (erro típico; ordenação)

| cenário | N teste | ATUAL | INGÊNUO | M0 | M0d |
|---|---|---|---|---|---|
| principal | 18 | 27%; ρ +0.35 | 37%; ρ +nan | 22%; ρ +0.50 | 20%; ρ +0.51 |
| (a) só metragem oficial | 15 | 22%; ρ +0.31 | 38%; ρ +nan | 22%; ρ +0.47 | 22%; ρ +0.45 |
| (b) satélite sem correção | 18 | 22%; ρ +0.41 | 37%; ρ +nan | 24%; ρ +0.51 | 24%; ρ +0.51 |
| (c) sem ajuste de calendário | 18 | 29%; ρ +0.35 | 39%; ρ +nan | 23%; ρ +0.50 | 19%; ρ +0.51 |

## Por unidade de teste

| unidade | UF | m² (fonte) | aceita agregador | real | previsto M0 | erro M0 | previsto ATUAL | erro ATUAL |
|---|---|---|---|---|---|---|---|---|
| MOCOCA | SP | 1,311 (oficial) | sim | 121,639 | 259,778 | -53% | 211,923 | -43% |
| ALEXANDRINA | GO | 1,400 (oficial) | sim | 149,598 | 233,484 | -36% | 229,794 | -35% |
| JARDIM APURA | SP | 1,200 (oficial) | sim | 113,788 | 171,794 | -34% | 187,745 | -39% |
| CPA | MT | 1,500 (oficial) | sim | 193,268 | 248,444 | -22% | 242,475 | -20% |
| UNAI | MG | 800 (oficial) | sim | 153,197 | 193,426 | -21% | 194,912 | -21% |
| CESARIO | MG | 1,073 (satélite) | sim | 157,043 | 198,166 | -21% | 234,360 | -33% |
| TAGUATINGA SUL | DF | 1,400 (oficial) | sim | 180,032 | 209,801 | -14% | 229,794 | -22% |
| FLORIANO | MG | 1,126 (satélite) | sim | 198,499 | 203,078 | -2% | 246,078 | -19% |
| PARANOA PARQUE | DF | 2,000 (oficial) | sim | 270,828 | 270,930 | -0% | 278,197 | -3% |
| COTIA | SP | 750 (oficial) | sim | 155,321 | 152,995 | +2% | 182,730 | -15% |
| CAMBUI CAMPINAS | SP | 880 (oficial) | sim | 191,252 | 170,888 | +12% | 242,836 | -21% |
| BOTANIC MALL | DF | 1,206 (oficial) | sim | 357,827 | 302,191 | +18% | 188,684 | +90% |
| VILA GUANABARA | SC | 1,500 (oficial) | sim | 281,254 | 235,798 | +19% | 242,475 | +16% |
| VALPARAISO | GO | 1,800 (oficial) | sim | 348,105 | 231,943 | +50% | 295,450 | +18% |
| NOROESTE | DF | 2,000 (oficial) | sim | 692,706 | 436,460 | +59% | 278,197 | +149% |
| BUTANTA | SP | 1,453 (satélite) | sim | 454,569 | 238,641 | +90% | 234,812 | +94% |
| CARIACICA | ES | 1,300 (oficial) | sim | 343,952 | 171,980 | +100% | 210,145 | +64% |
| BOTAFOGO | RJ | 1,230 (oficial) | NÃO | 697,407 | 244,762 | +185% | 192,439 | +262% |

## Insumos (SHA-256)

- `protocolo_uni02.md`: `fc89a194b7d7db3be1202317957657f036d03c515e29975e38c8a8cbd4251c6a`
- `01_confirmacao.py`: `e61ad34fb7023b5f3c098e3628541c2d7a7f344b5ce68461872b56334a11d7cf`
- `fato_unidade_mes.parquet`: `cffc6b276d930905ace08bffe1c5f0b7e15d207b5fd7389c8afd0a19ebc8fa87`
- `dim_unidade.parquet`: `c6ecef57365c1ac8730802386adb55eb5610a056665b0999746ccb12395230b8`
- `metragem_estimada.csv`: `acaa55425abb6ab272329444815b6136d645f317565c7b27c72d912f5c0a3504`
- `planilha_felipe_2026-09-28.xlsx`: `9a550aee04b46af78aa65db5e3b88115d698b80570482257d3388fcd9a8ea393`
- `planilha_vini_2026-09-28.xlsx`: `f12851f2517d8238629eabae7ea8c2d551e40ab206b3d57440b1699b0fce66de`
