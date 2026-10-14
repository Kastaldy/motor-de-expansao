# Previsão congelada da turma de 2026 — leitura precoce (descritiva)

Previsões congeladas em `previsoes_turma_2026.csv` (16 unidades). Calendário 2026: -2.0%. Faixa provisória p10–p90 do M0: -35% a +67%.

Projeção precoce = faturamento do último mês válido ÷ mediana da curva do UNI-03 naquele mês de vida (sinal antecipado, erro de 9–21% conforme o mês; não é a conferência).

| unidade | UF | abertura | mês de vida | estúdio | previsto M0 | previsto M0+E | previsto M0+ME | projeção precoce | projeção ÷ M0 |
|---|---|---|---|---|---|---|---|---|---|
| BURITIS | MG | 2025-08-25 | 12 | sim | R$ 317,153 | R$ 330,730 | R$ 379,172 | R$ 129,550 | -59% |
| AMERICANA CENTRO | SP | 2025-08-25 | 12 | não | R$ 146,465 | R$ 134,669 | R$ 145,429 | R$ 84,867 | -42% |
| BERTIOGA | SP | 2025-09-02 | 11 | não | R$ 257,715 | R$ 211,067 | R$ 235,091 | R$ 249,492 | -3% |
| GUARAPARI | ES | 2025-12-29 | 8 | não | R$ 294,707 | R$ 239,183 | R$ 266,168 | R$ 391,278 | +33% |
| CIDADE OCIDENTAL | GO | 2026-01-08 | 7 | sim | R$ 294,420 | R$ 308,447 | R$ 287,959 | R$ 389,568 | +32% |
| ASA SUL | DF | 2026-02-20 | 6 | sim | R$ 603,626 | R$ 590,728 | R$ 555,520 | R$ 547,855 | -9% |
| JARDIM DAS AMERICAS | MT | 2026-02-25 | 6 | ? | R$ 215,219 | – | – | R$ 249,575 | +16% |
| CEILANDIA QNM24 | DF | 2026-04-06 | 4 | sim | R$ 143,138 | R$ 172,312 | R$ 155,252 | R$ 204,940 | +43% |
| LARANJEIRAS | RJ | 2026-04-07 | 4 | não | R$ 269,898 | R$ 231,047 | R$ 225,352 | R$ 632,536 | +134% |
| VILA IZABEL | PR | 2026-04-17 | 4 | ? | R$ 141,807 | – | – | R$ 220,314 | +55% |
| GAMA | DF | 2026-05-25 | 3 | sim | R$ 254,808 | R$ 278,052 | R$ 256,437 | R$ 350,756 | +38% |

## Insumos (SHA-256)

- `protocolo_previsao_2026.md`: `cd06e6bc88d95732577a90dd18b0d625c041a2a624b6b925eb5329101f2f9132`
- `01_congelar.py`: `e47d4e0e2d1730d5d986e273a238f1c6f17eff1f44435105ebf652a39211c33d`
- `fato_unidade_mes.parquet`: `cffc6b276d930905ace08bffe1c5f0b7e15d207b5fd7389c8afd0a19ebc8fa87`
- `dim_unidade.parquet`: `c6ecef57365c1ac8730802386adb55eb5610a056665b0999746ccb12395230b8`
- `metragem_estimada.csv`: `acaa55425abb6ab272329444815b6136d645f317565c7b27c72d912f5c0a3504`
- `metragem_estimada_2026-09-29.csv`: `065b12b66165e55be73663968c528845852de78ac0e197768ee6a4790759a839`
- `curva_uni03.csv`: `e0fd0b0f0fc32ed4d6374aeeed175e0acf0187b7a4ed4d5f511a603dcfead4f8`
