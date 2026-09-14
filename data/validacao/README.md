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
| `KPIs_Smart_*.xlsx` | Smart Fit | **painel mensal** — 37 meses (jan/2023 a jan/2026), 961 unidades, `Alunos Totais SF` + acessos. A `Sigla` codifica a UF nas posições 3-4 (`SBRSPCABC01` → SP), que é o que permite recortar o join por estado numa planilha sem coluna de UF |
| `redfit_*.csv` | RedFit | **transcrição** de `RedFit*.jpeg` (relatório de faturamento entregue como print): total de ativos, pagantes e usuários WellHub por unidade |
| `pacer_*.csv` | Grupo Pacer | **transcrição** de `Grupo Pacer.jpeg`: 13 unidades em Ribeirão Preto / Sertãozinho / Bonfim Paulista com área m² e alunos ativos |

Skyfit e Engenharia adicionados por Felipe em 2026-05-29; Smart Fit em 2026-07-28; RedFit e Pacer
em 2026-09-09. As unidades já estão mapeadas na camada de concorrentes do projeto, o que permite
ligar cada uma ao score do hex/setor onde cai e usar `alunos_totais` / alunos-por-m² como desfecho
observado independente no backtest.

### Fontes entregues como IMAGEM

`RedFit - Junho 2026.jpeg`, `RedFit 2 - Junho 2026.jpeg` e `Grupo Pacer.jpeg` são prints de
planilha. O pipeline **não lê imagem**: a transcrição vira CSV (`sep=";"`, `utf-8-sig`) ao lado, e é
o CSV que `pipelines/alunos_reais.py` consome. Os `.jpeg`/`.jpg`/`.png` desta pasta são gitignored
pela mesma política dos `.xlsx` — antes de 2026-09-10 não eram, e ficavam untracked esperando um
`git add -A` distraído.

**Transcrever é ato de digitação, e digitação erra.** A do RedFit foi conferida contra os dois
totais impressos na própria imagem (12.326 ativos e 20.794 WellHub) e o `assert` está no script que
gerou o CSV. A do Pacer **não tem linha de total** para conferir — ela é o elo mais fraco desta
pasta, e qualquer número da Pacer que pareça estranho deve ser checado contra a imagem antes de
qualquer outra hipótese.

## Alunos = planos + agregadores

Convenção fixada por Felipe em 2026-09-10 e já praticada pelas próprias fontes: a Skyfit publica
`Alunos Totais = EVO + Gympass + TotalPass`, a Engenharia `= Ativos + Gympass`. O RedFit informa as
duas metades em colunas separadas (Matriz Pasteur: 371 ativos **e** 518 WellHub — o usuário de
agregador **não** está dentro do total de ativos). O crosswalk guarda `alunos_planos` e
`alunos_agregador` separados e soma em `alunos_total`, que é o número exibido no tooltip do pino.

## Convenções e guardrails

- **Não commitar os dados brutos** (gitignored). Não colar conteúdo agregável a PII em logs/handoff.
- CSVs derivados locais: `sep=";"`, `encoding="utf-8-sig"`. (Os fontes aqui são `.xlsx`.)
- Artefato de análise gerado a partir destes fontes vai para `data/analysis/` (ex.:
  `dataset_validacao.parquet`), **nunca** para `data/outputs/` (não é artefato de produto M1).
- **Cautela de rótulo (Skyfit):** confirmar se os números são medidos ou estimados antes de tratar
  como verdade — tratar a auditoria de qualidade de rótulo como critério de aceite do BLK-SCORE-01.
- Leitura/join são **read-only sobre o M1**: nenhuma escrita em artefato M1 ou alteração de score.
