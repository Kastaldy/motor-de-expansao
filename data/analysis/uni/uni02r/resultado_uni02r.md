# UNI-02 (reforço) — réplica da hipótese do diretor em outras redes

Protocolo `protocolo_uni02r.md` (SHA-256 `011f2ef62ae549d6…`). Rodado uma vez.

Efeito = quanto a elasticidade de alunos (ou faturamento) ao m² aumenta por 1 desvio-padrão da fração de academias independentes na isócrona de carro 10 min. IC 90% HC3.

| amostra | desfecho | N | cidades | efeito | IC 90% | mín. detectável | mesmo sinal ao tirar cada cidade | classe |
|---|---|---|---|---|---|---|---|---|
| **Engenharia do Corpo (primária)** | alunos | 36 | 27 | +0.30 | [-0.40, +1.01] | 1.06 | 27 de 27 | **inconclusivo** |
| EdC + Pacer (efeito fixo de rede) | alunos | 45 | 28 | +0.35 | [-0.27, +0.97] | 0.93 | 28 de 28 | inconclusivo |
| Ultra (referência, UNI-01) | faturamento | 39 | – | +0.34 | [+0.04, +0.65] | – | – | – |
| Ultra (referência) | alunos | 39 | – | +0.40 | [+0.12, +0.69] | – | – | – |

- O valor da Ultra (+0,34, faturamento) está dentro do IC da Engenharia do Corpo.
- Unidades da Pacer usadas: 9 (as 2 de Sertãozinho ficam fora do grafo).

## Insumos (SHA-256)

- `protocolo_uni02r.md`: `011f2ef62ae549d62d0821df908064704d18b442b920fe56c6264c35eb11f419`
- `01_replica_t09.py`: `cb93f7a1cc0cf50f98726877213cef5b3e768a798f26a855be8d21c0ff8953f6`
- `perfil.parquet`: `093ea5d4218f129b3b01e2ed57b01e922e3891a607b1deca592c5a74eb4c9754`
- `pacer_atributos_metro_43.parquet`: `ce7a2fa4699f168203edc2f73a8e90b44024ee6a19889f1b4c93b282fda315a3`
- `alunos_reais_por_unidade.parquet`: `81ade0cfc0335d0eb26b5e02b4cba198dce39bf7d2a895e3c2fbf9af9a65a1be`
