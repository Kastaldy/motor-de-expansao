# Fachada × desempenho — amostra ampliada (v1.1)

Protocolo `protocolo_fachada.md` v1.1 (SHA-256 `5a09f35ca3e8af81…`). Rodado uma vez.

| amostra | N | Spearman nota × resíduo | IC 90% | inclinação | leitura |
|---|---|---|---|---|---|
| principal (maduras com metragem) | 14 | +0.37 | [-0.17; +0.85] | +8% por ponto | **inconclusivo** |
| ampliada (+ jovens projetadas + shopping) | 22 | +0.32 | [-0.09; +0.66] | +10% por ponto | **inconclusivo** |

Descritivo (sem Botafogo, a maior exceção): Spearman +0.50, N = 21.

Média do resíduo por nota (ampliada): nota 1: -20% (n=1); nota 2: +185% (n=1); nota 3: -16% (n=8); nota 4: +13% (n=8); nota 5: +39% (n=4).

| unidade | origem | nota | faturou vs. previsto |
|---|---|---|---|
| buritis-mg | jovem, projetada do mês 12 | 3 | -59% |
| americana-centro-sp | jovem, projetada do mês 12 | 3 | -42% |
| jundiai-sp | treino (LOO) | 3 | -37% |
| vila-guilherme-sp | treino (LOO) | 3 | -22% |
| centro-comendador-pr | treino (LOO) | 1 | -20% |
| asa-sul-df | jovem, projetada do mês 6 | 4 | -9% |
| aguas-claras-df | treino (LOO) | 3 | -8% |
| lago-norte-df | treino (LOO) | 4 | -7% |
| bertioga-sp | jovem, projetada do mês 11 | 5 | -3% |
| floriano-mg | teste UNI-02 | 4 | -2% |
| samambaia-df | treino (LOO) | 4 | -2% |
| recanto-das-emas-df | treino (LOO) | 4 | +0% |
| cotia-sp | teste UNI-02 | 2.75 | +2% |
| jardim-das-americas-mt | jovem, projetada do mês 6 | 3 | +16% |
| guarapari-es | jovem, projetada do mês 8 | 5 | +33% |
| serra-es | treino (LOO) | 4 | +42% |
| santa-maria-df | treino (LOO) | 4 | +51% |
| vila-matilde-sp | treino (LOO) | 4 | +53% |
| boa-vista-ba | madura sem metragem (modelo sem m²) | 5 | +54% |
| bangu-rj | madura sem metragem (modelo sem m²) | 3 | +90% |
| butanta-sp | teste UNI-02 | 5 | +90% |
| botafogo-rj | teste UNI-02 | 2 | +185% |

## Insumos (SHA-256)

- `protocolo_fachada.md`: `5a09f35ca3e8af810a312201368835299ee9d492aa7b625846e4f6a9b1caecd8`
- `05_fachada_ampliada.py`: `de7c70c082a1bb87db5c318f98e30ff1a2f7e55c82764075993dcc6d750e18f1`
- `planilha_felipe_2026-09-28.xlsx`: `9a550aee04b46af78aa65db5e3b88115d698b80570482257d3388fcd9a8ea393`
- `planilha_vini_2026-09-29.xlsx`: `ad6f2a4834ac33bfccf52a4709b560dae661aa48552b278cd555000a41975a3e`
- `fato_unidade_mes.parquet`: `cffc6b276d930905ace08bffe1c5f0b7e15d207b5fd7389c8afd0a19ebc8fa87`
- `dim_unidade.parquet`: `c6ecef57365c1ac8730802386adb55eb5610a056665b0999746ccb12395230b8`
- `confirmacao_por_unidade.csv`: `ba9b3e9f9f45ebdd238b6214bb67f5c4ca4ce6ffd5677341b6e4be257f5cbbe9`
- `curva_uni03.csv`: `e0fd0b0f0fc32ed4d6374aeeed175e0acf0187b7a4ed4d5f511a603dcfead4f8`
