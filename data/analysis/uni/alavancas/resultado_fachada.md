# Fachada × desempenho — resultado

Protocolo `protocolo_fachada.md` (SHA-256 `5fdd3100473c71c4…`). Rodado uma vez.

- Unidades com fachada avaliada: 37; com resíduo do M0 fora da amostra: **15** ({'treino (LOO)': 10, 'teste UNI-02': 5}).
- Concordância entre avaliadores (nota), 4 unidades avaliadas pelos dois: botafogo-rj 2/2; buritis-mg 3/3; centro-comendador-pr 1/1; cotia-sp 2.5/3.

| X | N | Spearman com o resíduo | IC 90% | inclinação | leitura |
|---|---|---|---|---|---|
| nota da fachada (1–5) | 14 | +0.37 | [-0.20; +0.86] | +8% por ponto | **inconclusivo** |
| índice dos 6 itens (0–1) | 15 | +0.22 | [-0.20; +0.54] | +12% de 0 a 1 | **inconclusivo** |

| unidade | origem | nota | índice | faturou vs. previsto |
|---|---|---|---|---|
| jundiai-sp | treino (LOO) | 3 | 0.83 | -37% |
| vila-guilherme-sp | treino (LOO) | 3 | 0.83 | -22% |
| cesario-mg | teste UNI-02 | – | 0.33 | -21% |
| centro-comendador-pr | treino (LOO) | 1 | 0.33 | -20% |
| aguas-claras-df | treino (LOO) | 3 | 0.20 | -8% |
| lago-norte-df | treino (LOO) | 4 | 0.17 | -7% |
| floriano-mg | teste UNI-02 | 4 | 1.00 | -2% |
| samambaia-df | treino (LOO) | 4 | 0.83 | -2% |
| recanto-das-emas-df | treino (LOO) | 4 | 0.50 | +0% |
| cotia-sp | teste UNI-02 | 2.75 | 0.90 | +2% |
| serra-es | treino (LOO) | 4 | 1.00 | +42% |
| santa-maria-df | treino (LOO) | 4 | 0.33 | +51% |
| vila-matilde-sp | treino (LOO) | 4 | 0.83 | +53% |
| butanta-sp | teste UNI-02 | 5 | 0.83 | +90% |
| botafogo-rj | teste UNI-02 | 2 | 0.50 | +185% |

Turma de 2026: notas de fachada registradas para 13 das 16 unidades com previsão congelada (`previsao_2026/fachada_turma_2026.csv`).

## Insumos (SHA-256)

- `protocolo_fachada.md`: `5fdd3100473c71c4497928e93236dcdcc8c1155f583372c84245035f8af06684`
- `04_fachada.py`: `e504ade4c2390e25d389685887572554bacb2f916fed0f1e9826e83bfdcb99b4`
- `planilha_felipe_2026-09-28.xlsx`: `9a550aee04b46af78aa65db5e3b88115d698b80570482257d3388fcd9a8ea393`
- `planilha_vini_2026-09-29.xlsx`: `ad6f2a4834ac33bfccf52a4709b560dae661aa48552b278cd555000a41975a3e`
- `fato_unidade_mes.parquet`: `cffc6b276d930905ace08bffe1c5f0b7e15d207b5fd7389c8afd0a19ebc8fa87`
- `dim_unidade.parquet`: `c6ecef57365c1ac8730802386adb55eb5610a056665b0999746ccb12395230b8`
- `confirmacao_por_unidade.csv`: `ba9b3e9f9f45ebdd238b6214bb67f5c4ca4ce6ffd5677341b6e4be257f5cbbe9`
