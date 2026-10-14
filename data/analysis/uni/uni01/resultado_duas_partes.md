# Modelo em duas partes (alunos × ticket) — resultado

Protocolo `protocolo_duas_partes.md` (SHA-256 `d36085476bee99db…`). N = 38 unidades maduras de 2025, as mesmas em todas as variantes (fora por falta de variável: ['boa-vista-ba', 'poa-barra-sul-rs']).

| variante | descrição | R² fora da amostra (LOO) | R² retirando a cidade | erro típico (LOO) | erro típico (sem a cidade) | supera o M0? |
|---|---|---|---|---|---|---|
| M0 | uma equação (referência atual) | 0.302 | 0.192 | 21% | 24% | não |
| M0d | uma equação + hipótese do diretor | 0.315 | 0.307 | 22% | 23% | não |
| M1 | duas partes | 0.268 | 0.256 | 25% | 22% | não |
| M2 | duas partes + diretor (em alunos) | 0.277 | 0.279 | 25% | 26% | não |
| M3 | duas partes + política de agregador da UF | 0.325 | 0.343 | 24% | 21% | sim |
| M4 | duas partes + diretor + política de agregador da UF | 0.309 | -0.376 | 24% | 44% | não |

Regra (fixada antes): supera o M0 só com +0,02 de R² nas duas avaliações; entre as que superam, vale a mais simples.

**Decisão:** a variante M3 (duas partes + política de agregador da UF) vira a estrutura candidata do UNI-02.

## Insumos (SHA-256)

- `protocolo_duas_partes.md`: `d36085476bee99db13c8a9e3ccc9ba16720ca826e6ed1d37ebb80f74bfa052d4`
- `05_duas_partes.py`: `f0dbe3ded1a71019ef9b076d5e7c9e8fb6cd2848cef5a4fe390babf36ee123e9`
- `fato_unidade_mes.parquet`: `cffc6b276d930905ace08bffe1c5f0b7e15d207b5fd7389c8afd0a19ebc8fa87`
- `dim_unidade.parquet`: `c6ecef57365c1ac8730802386adb55eb5610a056665b0999746ccb12395230b8`
