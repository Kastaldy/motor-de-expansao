# Estúdios × master — resultado (exploratório, pós-hoc)

Protocolo `protocolo_estudios_master.md` (SHA-256 `17a9312ed3c19040…`). Rodado uma vez.

## Composição

| grupo de master | treino: com estúdio / sem | teste: com estúdio / sem |
|---|---|---|
| DF/GO | 10 / 7 | 5 / 1 |
| ULTRA | 5 / 4 | 0 / 6 |
| RJ/SP 01 | 3 / 4 | 1 / 0 |
| outros | 5 / 1 | 2 / 3 |

## Q1 — Estúdios com e sem a master (treino, 39 unidades)

| modelo | efeito dos estúdios | IC 90% | R² LOO | estável ao retirar cada metro |
|---|---|---|---|---|
| M0 + estúdios | **+30.3%** | [+6.8%; +59.0%] | 0.375 | sim (11) |
| M0 + master + estúdios | **+27.9%** | [+3.9%; +57.5%] | 0.278 | sim (11) |

Retenção do efeito com a master: 93% (em log). **Leitura: estúdio sobrevive.**

Master no treino (M0 + master, contra DF/GO; R² LOO do M0 0.306 → 0.221): ULTRA +23.4% [-3.7%; +58.2%]; RJSP01 +4.1% [-22.0%; +38.9%]; outros +24.9% [-12.2%; +77.8%].

**Dentro de cada master** (mediana do erro LOO do M0; positivo = fatura acima do previsto):

| grupo | com estúdio | sem estúdio |
|---|---|---|
| DF/GO | -0.6% (n=10) | -22.2% (n=7) |
| ULTRA | +1.1% (n=5) | +49.3% (n=4) |
| RJ/SP 01 | +52.6% (n=3) | -28.4% (n=4) |
| outros | +41.6% (n=5) | -36.7% (n=1) |

## Q2 e Q3 — Fora da amostra (18 unidades de teste)

| comparação | versão | N | erro antes | erro depois | diferença IC 90% | ordenação antes → depois |
|---|---|---|---|---|---|---|
| Q2: M0 → M0 + master | com Botafogo | 18 | 21.5% | 30.3% | [-4.6; +9.7] p.p. | +0.50 → +0.39 |
| Q2: M0 → M0 + master | sem Botafogo | 17 | 20.8% | 30.0% | [-5.7; +9.7] p.p. | +0.49 → +0.38 |
| **Q2: M0 → M0 + master** | **leitura** | | | | | **não se repete** |
| Q3: M0 + master → + estúdios | com Botafogo | 18 | 30.3% | 20.6% | [-11.0; +0.4] p.p. | +0.39 → +0.73 |
| Q3: M0 + master → + estúdios | sem Botafogo | 17 | 30.0% | 20.2% | [-11.2; +6.2] p.p. | +0.38 → +0.71 |
| **Q3: M0 + master → + estúdios** | **leitura** | | | | | **consistente** |

## Insumos (SHA-256)

- `protocolo_estudios_master.md`: `17a9312ed3c19040de2c3a94a4313108fcbebb5b4d4bdb69b3af602006f8ccbb`
- `02_estudios_master.py`: `6d303f62e115bdfa697b4e5b21a42e26ce1d53c65e2db94181314a2aae5dbe38`
- `01_alavancas.py`: `4b6cefdeb5c862b1ccb3a088998462943178b350200bec1c7941adbca2aaa616`
- `fato_unidade_mes.parquet`: `cffc6b276d930905ace08bffe1c5f0b7e15d207b5fd7389c8afd0a19ebc8fa87`
- `dim_unidade.parquet`: `c6ecef57365c1ac8730802386adb55eb5610a056665b0999746ccb12395230b8`
