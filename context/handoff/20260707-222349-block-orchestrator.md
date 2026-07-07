# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
BLOQUEADO — não avançar para Planner.

## Bloco refinado
BLK-VIAB-05 — Recalibrar/validar a curva m²→densidade com a base ampliada (out-of-fold)

## Veredito
**BLOQUEADO** — o incremento de dados que justificava o bloco não existe.

---

## Investigação realizada

### 1. Existe `calibracao_curva.py`?
**SIM.** Está em `/repo/src/motor_expansao/demanda_revelada/calibracao_curva.py` e foi
criado no BLK-TP-04 (concluído 2026-07-02). Implementa exatamente o harness que o VIAB-05
descreve: k-fold 5×5 repetido vs baseline da média, R² in-sample banido, IC95 bootstrap
seed=42, veredito GO/NO-GO.

### 2. A base tem metragem+alunos para ~1.100 academias?
**NÃO.** A base real com metragem+alunos válidos é **N=112** (Ultra 54 + Eng Corpo 58),
idêntica à base do VIAB-02 e à base que o BLK-TP-04 já usou.

Confirmado por inspeção direta do `data/staging/base_calibracao_multirede.parquet` (426
linhas totais):

| Marca               | Total | Com metragem > 0 |
|---------------------|-------|-----------------|
| ultra               | 54    | 54              |
| engenharia_do_corpo | 61    | 58 (1 NaN, 2 zero) |
| skyfit              | 311   | **0**           |
| **TOTAL válido**    | 426   | **112**         |

### 3. Smart Fit e Sky Fit têm metragem?
**Smart Fit NÃO:** `KPIs_Smart_2025_02 (1).xlsx` — colunas `Data_Ref, Sigla, Nome,
Propriedade, Alunos Totais SF, Acessos SF, Frequencia`. Sem metragem em nenhuma sheet.

**Sky Fit NÃO:** `data/validacao/Sky Fit dados.xlsx` — colunas confirmadas:
`ID SKY, NOMENCLATURA UNIDADE, ENDERECO, CIDADE, ESTADO, Alunos EVO, Alunos Gympass,
Alunos TotalPass`. Sem metragem.

### 4. O BLK-TP-04 já fez a validação da curva?
**SIM.** O BLK-TP-04 (concluído 2026-07-02, aprovado pelo humano Felipe) **já executou**
a validação honesta da curva m²→densidade sobre N=112, usando exatamente o harness
DEC-008: k-fold 5×5, IC95 seed=42, go/no-go. Resultado documentado em
`data/analysis/calibracao_curva_densidade.md` (gitignored). O módulo `calibracao_curva.py`
existe, está testado e operacional.

### 5. Qual seria o incremento real do VIAB-05?
**Zero.** O VIAB-05 pressupõe "~1.100 academias reais com metragem+alunos" — mas essa
estimativa estava **errada desde o rascunho do backlog**. A base disponível é exatamente
a mesma N=112 do VIAB-02 e do BLK-TP-04. Não há nova base a incorporar.

Executar o VIAB-05 hoje seria reduplificar o BLK-TP-04 com a mesma base e o mesmo harness,
sem nenhum incremento de dados nem de método.

---

## Objetivo (como descrito no backlog)
Revalidar/recalibrar a curva metragem→densidade (alunos/m²) sobre base ampliada,
out-of-fold (k-fold 5×5 seed=42 vs baseline da média, DEC-008).

## Razão do bloqueio
A "base ampliada" mencionada no backlog não existe. A base disponível com metragem+alunos
reais é N=112 (Ultra 54 + Eng Corpo 58) — idêntica à já usada no BLK-TP-04. O bloco não
tem incremento técnico realizável com os dados existentes.

## Condição para reabertura
O bloco poderá ser reaberto **somente** quando houver uma fonte nova com `metragem` real
de academias (além de Ultra e Eng Corpo), por exemplo:
- Smart Fit disponibilizar dados de área por unidade (não consta em nenhum arquivo atual);
- Sky Fit disponibilizar dados de área por unidade (não consta);
- Outra base de academias low-cost com metragem+alunos reais.

Enquanto isso, a validação da curva está coberta pelo BLK-TP-04 concluído.

## Arquivos inspecionados
- `/repo/src/motor_expansao/dimensionamento/demanda_premissa.py`
- `/repo/src/motor_expansao/demanda_revelada/calibracao_curva.py`
- `/repo/src/motor_expansao/dimensionamento/config.py`
- `/repo/data/staging/base_calibracao_multirede.parquet` (426 linhas; 112 com metragem)
- `/repo/data/validacao/Sky Fit dados.xlsx` (sem metragem)
- `/repo/data/validacao/KPIs_Smart_2025_02 (1).xlsx` (sem metragem)
- `/repo/scripts/_scratch_atr_alvo_alunos_totais.py` (usa alunos_totais, não metragem)
- `/repo/tasks/completed.md` (BLK-TP-04 concluído 2026-07-02)
- `/repo/tasks/backlog.md` (BLK-VIAB-05)

## Escopo permitido
N/A — bloco bloqueado.

## Fora de escopo
- Qualquer implementação (bloco bloqueado, sem incremento de dados)
- Reutilização do BLK-TP-04 como substituto nominal do VIAB-05 (já concluído)

## Critérios de aceite
N/A — bloco bloqueado.

## Criticidade classificada
Alta (mantida do backlog — READ-ONLY sobre o M1)

## Esteira recomendada
BLOQUEADO. Ação recomendada: marcar VIAB-05 como "bloqueado por falta de dados" no backlog.
Nenhuma Skill subsequente deve ser acionada.

## Riscos identificados
- Nenhum risco de execução (bloco não será executado)
- Risco de confusão: o backlog cita "~1.100 academias" — essa estimativa estava errada desde
  o rascunho. O BLK-TP-04 já cobre a validação com os dados reais disponíveis (N=112).

## Guardrails ativos
- §5 READ-ONLY M1: não toca score_priorizacao/pesos/artefatos oficiais.
- DEC-008: out-of-fold vs baseline; R² in-sample BANIDO; IC95 seed=42.
- DEC-009: alvo = alunos_totais REAIS, nunca membros/agregador.
- viabilidade_ponto.py INTOCADO.
