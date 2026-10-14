# Portões sem desfecho — protocolo_poi_uni00 v1.1

S1 Ultra N = 53 (plaza-sul-sp fora: pino errado); S2 Smart Fit N = 454 (confiança alta, nome|UF único, madura, com isócrona).

Idade S1 (mês mediano válido de 2025): mín 8, faixas 6–11 = 17, 12–23 = 16, ≥ 24 = 20. S2: 12–23 = 59, ≥ 24 = 395.

## P1 colinearidade (Pearson, S1)

|               |    F1 |    F2 |    F3 |    F5 |
|:--------------|------:|------:|------:|------:|
| log_m2        |  0.11 |  0.23 |  0.05 |  0.01 |
| log_renda     |  0.46 |  0.44 |  0.1  |  0.23 |
| log_pop       | -0.11 | -0.03 |  0.36 |  0.3  |
| idade_6_11    |  0.01 | -0.09 | -0.02 | -0.04 |
| idade_12_23   | -0.25 | -0.12 | -0.06 | -0.3  |
| log_area_pe15 | -0.19 | -0.08 |  0.39 |  0.29 |
| log_area_c10  |  0.15 |  0.16 |  0.16 | -0.11 |
| conc          |  0.49 |  0.46 | -0.03 |  0.17 |
| idade_m       |  0.22 |  0.23 |  0.07 |  0.35 |

Entre famílias:

|    |   F1 |   F2 |   F3 |   F5 |
|:---|-----:|-----:|-----:|-----:|
| F1 | 1    | 0.9  | 0.21 | 0.5  |
| F2 | 0.9  | 1    | 0.22 | 0.52 |
| F3 | 0.21 | 0.22 | 1    | 0.35 |
| F5 | 0.5  | 0.52 | 0.35 | 1    |
- F2: |r| >= 0,8 com família anterior -> fundida na anterior

## P2 suporte F3 (S1): 32 com F3 = 1, 21 com F3 = 0; em shopping (fato): 11
(S2: 385 de 454 com F3 = 1; em shopping 135)

## P3 idade e metragem

- F1: r(idade) = +0.22; r(log m²) = +0.11
- F2: r(idade) = +0.23; r(log m²) = +0.23
- F3: r(idade) = +0.07; r(log m²) = +0.05
- F5: r(idade) = +0.35; r(log m²) = +0.01
- guarda C2 F1: ρ(F, log m²) Ultra+EdC (N = 88 de 89) = -0.13 -> C2 avaliável
- guarda C2 F2: ρ(F, log m²) Ultra+EdC (N = 88 de 89) = +0.01 -> C2 avaliável
- guarda C2 F3: ρ(F, log m²) Ultra+EdC (N = 88 de 89) = -0.06 -> C2 avaliável
- guarda C2 F5: ρ(F, log m²) Ultra+EdC (N = 89 de 89) = -0.09 -> C2 avaliável

## Funil da S2

- S2 smart_fit alta no crosswalk: 876
- S2 alta + isocrona: 591
- S2 nome|UF unico no crosswalk: 591
- S2 casada a Sigla (nome unico no ultimo mes): 590
- S2 madura (no painel ate 2024-07): 457
- S2 com atributos da isocrona: 454
- S2 com features completas: 454

## P4 poder (famílias testadas: ['F1', 'F3', 'F5']; limiar do 1º passo do Holm = 0.0167; permutação restrita dentro de UF em S1 e de metrô em S2)

| familia   | S1 pr2=0.03   | S1 pr2=0.05   | S1 pr2=0.1   | S1 pr2=0.2   | S2 pr2=0.01   | S2 pr2=0.02   | S2 pr2=0.05   |
|:----------|:--------------|:--------------|:-------------|:-------------|:--------------|:--------------|:--------------|
| F1        | 0.14 ± 0.02   | 0.19 ± 0.03   | 0.38 ± 0.03  | 0.79 ± 0.03  | 0.41 ± 0.05   | 0.79 ± 0.04   | 0.99 ± 0.01   |
| F3        | 0.16 ± 0.03   | 0.18 ± 0.03   | 0.52 ± 0.04  | 0.89 ± 0.02  | 0.52 ± 0.05   | 0.80 ± 0.04   | 1.00 ± 0.00   |
| F5        | 0.04 ± 0.01   | 0.04 ± 0.01   | 0.07 ± 0.02  | 0.17 ± 0.03  | 0.24 ± 0.04   | 0.45 ± 0.05   | 0.77 ± 0.04   |

(Poder de S1 medido com α/3 (regra pré-P5); o limiar real de S1 após o P5 é 0,05/len(s1_fams), então o poder de S1 publicado é conservador.)

(± = erro Monte Carlo. S1: 200 réplicas, B = 399, LOO. S2: 100 réplicas, B = 199, GroupKFold por metrô. N efetivo: S1 53, S2 454.)

## P5 (v1.1): famílias com poder < 0,20 em S1 (R² parcial 0,10) saem do Holm de S1

S1 testa ['F1', 'F3']; S2 testa ['F1', 'F3', 'F5'].