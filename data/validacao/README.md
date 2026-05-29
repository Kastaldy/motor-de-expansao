# data/validacao/ — fontes de validação de scores

Pasta dedicada às **bases brutas de redes concorrentes usadas para validar/testar os scores**
(M1, censitário, residual, domínio). É insumo do **BLK-SCORE-01** (dataset rotulado de validação) →
**BLK-SCORE-02** (poder preditivo) → **BLK-SCORE-03** (recalibração com DEC).

## Arquivos (gitignored — NÃO commitar)

Os arquivos de dados abaixo são **dados reais de concorrentes** e ficam fora do git por `*.xlsx`
no `.gitignore` (mesma política do `data/ultra/Ultra.csv`). Apenas este `README.md` é versionado,
para deixar a localização explícita no repo. Cada contribuidor coloca os arquivos localmente aqui.

| Arquivo | Rede | Conteúdo |
|---|---|---|
| `Sky Fit dados.xlsx` | Skyfit | unidades + sinal de alunos (estimado vs. medido — ver cautela abaixo) |
| `academias_engenharia_do_corpo.xlsx` | Engenharia do Corpo | unidades com **alunos por m²** e **metragem** |

Adicionados por Felipe em 2026-05-29. As unidades de ambas as redes já estão mapeadas na camada de
concorrentes do projeto, o que permite ligar cada unidade ao score do hex/setor onde ela cai e usar
`alunos_totais` / alunos-por-m² como desfecho observado independente no backtest.

## Convenções e guardrails

- **Não commitar os dados brutos** (gitignored). Não colar conteúdo agregável a PII em logs/handoff.
- CSVs derivados locais: `sep=";"`, `encoding="utf-8-sig"`. (Os fontes aqui são `.xlsx`.)
- Artefato de análise gerado a partir destes fontes vai para `data/analysis/` (ex.:
  `dataset_validacao.parquet`), **nunca** para `data/outputs/` (não é artefato de produto M1).
- **Cautela de rótulo (Skyfit):** confirmar se os números são medidos ou estimados antes de tratar
  como verdade — tratar a auditoria de qualidade de rótulo como critério de aceite do BLK-SCORE-01.
- Leitura/join são **read-only sobre o M1**: nenhuma escrita em artefato M1 ou alteração de score.
