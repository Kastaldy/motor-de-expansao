# BLK-UNI-04 parte A — renda da praça × churn

Protocolo `protocolo_uni04a.md` v1.1 (SHA-256 `63f7abede96352b8…`). Rodado uma vez.

Efeito = pontos percentuais de churn mensal por 1 desvio-padrão do log da renda da isócrona (régua do T17). IC 90% HC3.

## Q1/Q2 — confirmação

| amostra | N | efeito [IC 90%] | ΔR² LOO | classe |
|---|---|---|---|---|
| T17 (UNI-01, reproduzido) | 39 | -1.29 [-1.72; -0.86] | +0.491 |  |
| ponte: T17 sem m² | 39 | -1.31 [-1.67; -0.96] | +0.505 |  |
| Q1: unidades novas, com idade (DECIDE) | 17 | -0.20 [-1.10; +0.69] | -0.218 | inconclusivo |
| Q1 sem idade (sensibilidade) | 17 | -0.22 [-1.11; +0.66] | -0.183 |  |
| Q2: unidades do T17 em 2026 | 39 | -0.90 [-1.20; -0.61] | +0.476 |  |

- Unidades da Q1 (amadureceram só em 2026): 17. Maduras em 2025 que ficaram fora do UNI-01 e não entram: ['cotia-sp', 'jardim-apura-sp', 'mococa-sp'].
- Correlação renda × idade: T17 +0.51; Q1 -0.15; Q3 +0.30.

## Q3 — Lifetime: renda da isócrona × renda municipal (a da DEC-014), mesma amostra

N = 56 (SP 18, DF 20). Valores distintos de renda municipal: SP 9, DF 1. Controles: log pop e log idade. Efeito por 1 dp da renda na própria amostra.

| desfecho do Lifetime | renda | efeito [IC 90%] | ΔR² LOO |
|---|---|---|---|
| lt_eb_churn_60d | renda da isócrona | -0.00 [-0.01; -0.00] | +0.018 |
| lt_eb_churn_60d | renda municipal (M1, DEC-014) | -0.00 [-0.01; -0.00] | +0.019 |
| lt_e_meses_ativos_12m_mediano | renda da isócrona | +0.07 [-0.01; +0.15] | +0.000 |
| lt_e_meses_ativos_12m_mediano | renda municipal (M1, DEC-014) | +0.04 [-0.02; +0.10] | -0.005 |

Concordância entre as fontes (Spearman, churn da Growth em 2026 × Lifetime, mesma amostra): lt_eb_churn_60d ρ = +0.68; lt_e_meses_ativos_12m_mediano ρ = -0.49.

## Q4 — decomposição (unidades do T17, 2025; amostra fixa N = 39)

| modelo | efeito da renda [IC 90%] |
|---|---|
| sem controle adicional | -1.29 [-1.72; -0.86] |
| + ticket | -0.95 [-1.42; -0.49] |
| + % agregador | -1.27 [-1.69; -0.86] |
| + % inadimplente | -1.03 [-1.35; -0.71] |
| + % em cobrança | -0.94 [-1.47; -0.41] |
| + todos | -0.88 [-1.33; -0.43] |

Correlação (Spearman) da renda com: l_ticket +0.44; agr +0.09; inad -0.42; cobr -0.64.
Cautela: a inadimplência é em parte o próprio desfecho (cancelamento por falta de pagamento).

## Insumos (SHA-256)

- `protocolo_uni04a.md`: `63f7abede96352b8eab54191f002f8c08435f3e2b832686ab11e06ba49e4be4c`
- `01_renda_churn.py`: `a8e1ddf5773b487e3109f965016f934ee45c3f15d6eed89c538d86c5ac626b64`
- `01_exploracao.py`: `d4147998b23859bcb4d813d7cbd724f3a0e321cb3b0f27f7f45493db244f7c8d`
- `fato_unidade_mes.parquet`: `cffc6b276d930905ace08bffe1c5f0b7e15d207b5fd7389c8afd0a19ebc8fa87`
- `dim_unidade.parquet`: `c6ecef57365c1ac8730802386adb55eb5610a056665b0999746ccb12395230b8`
- `brasil_estrutural.parquet`: `619d4031b76a026329e22a2f2a6e1d0931f96aaec577570fd4e9b50fec6df619`
