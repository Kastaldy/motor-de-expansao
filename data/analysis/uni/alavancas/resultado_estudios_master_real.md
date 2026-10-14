# Estúdios × master real do cadastro — resultado (v1.1)

Protocolo `protocolo_estudios_master.md` v1.1 (SHA-256 `2f31b3a14baade88…`). Rodado uma vez.

- Treino: 39 (0 com master imputada pela regional); teste: 18 (0 imputadas).
- Grupos: M1 (referência, 17 no treino), M2 (10), M3 (5), outras (7 no treino). Masters com < 4 unidades no treino vão para 'outras'.

## Q1 — estúdios com e sem a master real (treino)

| modelo | efeito dos estúdios | IC 90% | R² LOO | estável por metro |
|---|---|---|---|---|
| M0 + estúdios | +30.3% | [+6.8%; +59.0%] | 0.375 | sim |
| M0 + master real + estúdios | +25.7% | [-1.1%; +59.7%] | 0.257 | sim |

Retenção: 86%. **Leitura: não distingue.**

## Fora da amostra (18 unidades de teste)

| comparação | versão | N | erro antes | erro depois | IC 90% da diferença | ordenação antes → depois | leitura |
|---|---|---|---|---|---|---|---|
| Q2: M0 → M0 + master real | com Botafogo | 18 | 21.5% | 31.0% | [-3.9; +11.2] p.p. | +0.50 → +0.32 |  |
| Q2: M0 → M0 + master real | sem Botafogo | 17 | 20.8% | 30.7% | [-4.5; +11.4] p.p. | +0.49 → +0.42 | não se repete |
| Q3: M0 + master real → + estúdios | com Botafogo | 18 | 31.0% | 22.1% | [-10.7; +1.7] p.p. | +0.32 → +0.69 |  |
| Q3: M0 + master real → + estúdios | sem Botafogo | 17 | 30.7% | 21.7% | [-10.7; +5.5] p.p. | +0.42 → +0.70 | consistente |
| **v2 candidata: M0 → M0 + master real + estúdios** | com Botafogo | 18 | 21.5% | 22.1% | [-9.2; +5.1] p.p. | +0.50 → +0.69 |  |
| **v2 candidata: M0 → M0 + master real + estúdios** | sem Botafogo | 17 | 20.8% | 21.7% | [-12.0; +8.5] p.p. | +0.49 → +0.70 | não se repete |
| mesma, com a sigla regional (v1.0) | com Botafogo | 18 | 21.5% | 20.6% | [-9.6; +3.6] p.p. | +0.50 → +0.73 |  |
| mesma, com a sigla regional (v1.0) | sem Botafogo | 17 | 20.8% | 20.2% | [-13.6; +4.8] p.p. | +0.49 → +0.71 | consistente |
| M0 → M0 + estúdios (sem master) | com Botafogo | 18 | 21.5% | 25.0% | [-11.3; +9.0] p.p. | +0.50 → +0.73 |  |
| M0 → M0 + estúdios (sem master) | sem Botafogo | 17 | 20.8% | 24.6% | [-10.9; +8.7] p.p. | +0.49 → +0.71 | não se repete |

**Composição (treino / teste):** M1: 17 / 6 (com estúdio 10 / 5); M2: 10 / 6 (com estúdio 6 / 0); M3: 5 / 1 (com estúdio 1 / 1); M4: 3 / 1 (com estúdio 2 / 0); M5: 1 / 2 (com estúdio 1 / 1); M6: 2 / 1 (com estúdio 2 / 0); M7: 1 / 1 (com estúdio 1 / 1)

Previsões da turma de 2026 com a master real congeladas em `previsao_2026/previsoes_turma_2026_master_real.csv` (14 de 16 unidades).

## Insumos (SHA-256)

- `protocolo_estudios_master.md`: `2f31b3a14baade8886f4a46d7a3afceda1362e02f72e8d0aed0a8ef0220a071e`
- `07_estudios_master_real.py`: `0e763ec51656d512e49c839b70be0b7bd3dea804631924e41c3e22e2bad9d1f8`
- `02_estudios_master.py`: `6d303f62e115bdfa697b4e5b21a42e26ce1d53c65e2db94181314a2aae5dbe38`
- `master_id_cadastro.csv`: `bdc8ecbb2db49b339590ed1e8f3272b89407ad72a0286993d5150393c67120c9`
- `fato_unidade_mes.parquet`: `cffc6b276d930905ace08bffe1c5f0b7e15d207b5fd7389c8afd0a19ebc8fa87`
- `dim_unidade.parquet`: `c6ecef57365c1ac8730802386adb55eb5610a056665b0999746ccb12395230b8`
