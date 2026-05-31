# Backlog

## Priorização atual

Próximo ciclo recomendado: validar a estrutura de Skills com uma tarefa real do projeto.

> Blocos BLK-OPS-02/03/04, BLK-ARCH-01 e BLK-SCORE-01/02/03 originados do "Programa de
> Melhorias — Referência do Master Orchestrator" (PRD.md), migrados em 2026-05-29.
> Mapa de dependências e ordem recomendada do programa: ver §3 do PRD.md original.
> Ordem deste backlog: arquitetura (BLK-ARCH-01) à frente da trilha de score (BLK-SCORE-*).

---

## Tarefas pendentes

- BLK-OPS-06 (concluído 2026-05-29) — ver tasks/completed.md
- BLK-OPS-07 (concluído 2026-05-29) — ver tasks/completed.md
- BLK-PRD-01 (concluído 2026-05-29) — ver tasks/completed.md
- BLK-OPS-02 (concluído 2026-05-29) — ver tasks/completed.md
- BLK-OPS-02b (concluído 2026-05-29) — ver tasks/completed.md
- BLK-OPS-08 (concluído 2026-05-29) — ver tasks/completed.md

---

- BLK-OPS-03 (concluído 2026-05-30) — ver tasks/completed.md


---

- BLK-OPS-04 (concluído 2026-05-30) — ver tasks/completed.md



- BLK-FIX-01 (concluído 2026-05-30) — ver tasks/completed.md



- BLK-FIX-02 (concluído 2026-05-30) — ver tasks/completed.md


---

- BLK-SCORE-01 (concluído 2026-05-31) — ver tasks/completed.md


---

### BLK-SCORE-01a — Melhorar match de nome do Engenharia do Corpo

| Campo | Valor |
|---|---|
| **Criticidade** | Alta *(read-only sobre M1 — só leitura/join, mesmo padrão do BLK-SCORE-01)* |
| **Esteira** | Block Orchestrator → Planner → `[revisão humana]` → Builder → QA |
| **Depende de** | BLK-SCORE-01 (mergeado) |
| **Status** | Pendente |

**Origem:** no BLK-SCORE-01, o match do Engenharia do Corpo (EngCorpo) ficou em ~31/61 unidades porque
foi feito por **nome exato normalizado**, mas a planilha de desfecho e o staging usam convenções de nome
diferentes: a planilha prefixa toda unidade com `EC -`/`ECB -` (ex.: `EC - VACARIA, RS`) enquanto o staging
usa o nome cru (`Vacaria, RS`). O usuário apontou (2026-05-31) que o nome "vem um pouco diferente, mas ainda
daria para encontrar" — confirmado por análise: removendo o prefixo `EC`/`ECB` + fuzzy determinístico
(difflib ≥0.80) a recuperação sobe para ~38/61, e parte do restante é resolvível por sinônimo de
bairro/cidade (ex.: `EC - FLORIANOPOLIS, SC` ~ `Estreito - Florianópolis, SC`; `EC - BLUMENAU` ~ `Centro - Blumenau`).

**Objetivo:** elevar a cobertura de hex/scores do EngCorpo no `dataset_validacao.parquet` melhorando o
match de nome (sem inventar correspondências), mantendo tudo read-only sobre o M1 e marcando os não-casados.

**Escopo permitido:**
- Em `analysis/build_validation_dataset.py`, melhorar a etapa de match EngCorpo: normalização que remove
  prefixo `EC`/`ECB` e ruído; **cascata determinística** nome_exato → nome_fuzzy (difflib, cutoff documentado)
  → fallback cidade+UF (espelhando o padrão já aprovado para o Skyfit no BLK-SCORE-01).
- **Avaliar usar `concorrentes/unidades_engenharia_do_corpo.csv`** (e/ou `concorrentes/Unidades/unidades_engenharia_do_corpo.csv`)
  como fonte de coordenadas direta para resolver hex via `latlng_to_h3`, em vez de depender só do staging
  `concorrentes_mapeados.parquet` (mesma abordagem coords-por-CSV + match-por-nome do Skyfit). Verificar schema/coords antes.
- Anexar `hex_origem`/`hex_precisao` ao EngCorpo (já existem no esquema) refletindo a origem do match.
- Regerar `data/analysis/dataset_validacao.parquet` + `data/analysis/relatorio_auditoria_rotulo.md`.

**Fora de escopo:** **qualquer escrita em artefato M1 ou alteração de score.** Apenas leitura e join.
Fuzzy não-determinístico (que quebre o CI). Geocodificação de endereço ao vivo (BLK-PROD-05).

**Arquivos a ler:** `analysis/build_validation_dataset.py` · `data/validacao/academias_engenharia_do_corpo.xlsx`
(sheet `Academias`) · `data/staging/concorrentes_mapeados.parquet` (`rede=="engenharia_do_corpo"`) ·
`concorrentes/unidades_engenharia_do_corpo.csv` · `concorrentes/Unidades/unidades_engenharia_do_corpo.csv` ·
`context/handoff/20260530-235959-planner.md` (seção REVISÃO 2 Skyfit — padrão de cascata a espelhar).
**Arquivos a alterar:** `analysis/build_validation_dataset.py` · `tests/unit/test_validation_dataset.py`
(casos novos de match EngCorpo) · artefatos regerados em `data/analysis/` (gitignored).

**Critérios de aceite:**
- Match EngCorpo materialmente acima do baseline (31/61); cada unidade casada tem `hex_origem`/`hex_precisao`
  coerentes; não-casados **marcados** (`rotulo_casado=False`/`hex_resolvido=False`), nunca descartados nem
  casados de forma incorreta.
- Cascata determinística (mesmo input → mesmo output; verde no CI sem dados reais).
- Relatório de auditoria atualizado com a nova cobertura EngCorpo por `hex_origem` e a lista (agregada, sem PII)
  de não-casados remanescentes.
- Nenhum falso-positivo introduzido: validar uma amostra dos pares fuzzy aceitos (cidade/UF batem).

**Validações obrigatórias:**
```
pytest -q tests/unit/test_validation_dataset.py
pytest -q                                   # sem regressão
python -m analysis.build_validation_dataset # regenera dataset + relatório fim a fim
```

**Guardrails específicos:**
- READ-ONLY sobre o M1; artefato em `data/analysis/`, nunca `data/outputs/`. PII fora de logs/handoff/relatório.
- CSVs do projeto `sep=";"`, `utf-8-sig`. H3_RESOLUTION=7. Sem fuzzy não-determinístico.

**Risco:** médio — fuzzy pode introduzir falso-positivo (casar unidade errada da mesma cidade). Mitigar
exigindo concordância de cidade+UF no match fuzzy e auditando os pares aceitos.

---

### BLK-SCORE-02 — Poder preditivo dos scores vs. desfecho

| Campo | Valor |
|---|---|
| **Criticidade** | Alta *(read-only sobre M1 — ver §2 do PRD)* |
| **Esteira** | Block Orchestrator → Planner → `[revisão humana]` → Builder → QA |
| **Depende de** | **BLK-SCORE-01** |
| **Status** | Pendente |

**Objetivo:** medir, sobre o dataset rotulado, quanto cada score (M1, censitário, residual,
domínio) prevê `alunos_recorrentes` — por rede e no agregado — e onde discordam do real.

**Escopo permitido:**
- Análise exploratória: correlação score×desfecho, por rede e segmento de maturação.
- Decomposição do M1: renda vs. pop — qual componente carrega o sinal? (testa empiricamente o 0.40/0.60).
- Relatório de achados em `data/analysis/` (markdown + figuras), **sem proposta de mudança ainda**.

**Fora de escopo:** alterar pesos, fórmula ou artefatos M1 — isso é o BLK-SCORE-03.

**Arquivos a ler:** `data/analysis/dataset_validacao.parquet` · `core/scoring.py` · `core/constants.py`.
**Arquivos a criar:** `analysis/score_backtest.py` · relatório `data/analysis/relatorio_backtest.md`.

**Critérios de aceite:**
- Relatório responde, com números: (a) qual score melhor prevê recorrentes; (b) o 0.40/0.60 se
  sustenta?; (c) casos onde score alto ≠ desfecho bom (e hipótese do porquê — ex.: saturação de concorrente).
- Análise controla por maturação (não comparar unidade de 2 meses com uma de 5 anos).

**Validações obrigatórias:**
```
pytest -q             # nada quebrado
python analysis/score_backtest.py   # roda fim a fim e gera o relatório
```

**Guardrails específicos:**
- Estritamente **analítico e read-only**. Nenhuma alteração em `scoring.py`/`constants.py`/artefatos.

**Risco:** baixo a médio (qualidade da análise estatística). N pequeno por rede pode limitar
conclusões — relatar incerteza honestamente, não forçar significância.

---

### BLK-SCORE-03 — Proposta de recalibração + DEC

| Campo | Valor |
|---|---|
| **Criticidade** | **CRÍTICA** |
| **Esteira** | Block Orchestrator → Planner → `[APROVAÇÃO HUMANA OBRIGATÓRIA]` → Builder → QA |
| **Depende de** | **BLK-SCORE-02** |
| **Status** | Pendente |

**Objetivo:** *se* o backtest justificar, propor recalibração dos pesos/fórmula e, somente após
DEC registrada e aprovação humana, implementá-la — preservando reprodutibilidade e versionamento.

**Escopo permitido (em duas fases separadas pelo gate):**
- **Antes do gate (Planner):** proposta de recalibração fundamentada no relatório de BLK-SCORE-02,
  com impacto esperado no ranking, e minuta de DEC (`DEC-00X`).
- **Depois do gate (Builder, só com DEC aprovada):** alterar pesos/fórmula em `core/scoring.py` /
  `core/constants.py`, regerar artefatos via pipeline, registrar nova versão de proveniência.

**Fora de escopo:** qualquer escrita em M1 antes da string `APROVADO POR [usuário] EM [data]` no handoff.

**Arquivos a ler:** `data/analysis/relatorio_backtest.md` · `core/scoring.py` · `core/constants.py` ·
`CLAUDE.md` (DECs existentes).
**Arquivos a alterar (só pós-gate):** `core/scoring.py` · `core/constants.py` · `CLAUDE.md` (nova DEC) ·
regeneração de `data/outputs/` via pipeline.

**Critérios de aceite:**
- DEC registrada em `CLAUDE.md` (ou `DECISIONS.md` se já existir) com justificativa e data.
- Pesos antigos vs. novos documentados; ranking M1 antes/depois comparado e diferenças explicadas.
- Proveniência (BLK-OPS-03) reflete a nova versão.

**Validações obrigatórias:**
```
pytest -q tests/unit/test_scoring.py    # fórmulas — atualizar testes para os novos pesos
pytest -q                               # suíte completa verde
# Regeneração controlada (staging primeiro, nunca sobrescrever prod sem staging):
python -m motor_expansao.pipelines.m1.fase1_bi_exports   # ou comando canônico do repo
```

**Guardrails específicos (invioláveis):**
- Builder **não** altera nada de M1 sem `APROVADO POR [usuário] EM [data]` no handoff.
- Staging primeiro; jamais sobrescrever Parquets de produção sem passo de staging.
- QA verifica explicitamente que `H3_RESOLUTION=7`, `DIST_MIN_ULTRA_KM=1.0` e demais canônicos
  **não** foram tocados — só os pesos aprovados na DEC mudam.

**Risco:** crítico por definição. O gate humano + DEC + staging são a proteção. Não pular nenhum.

---

### BLK-ORQ-02 — Implementar estrutura Fase 2

Status: pendente (depende de BLK-ORQ-01 validado)
Criticidade: alta
Prioridade: média
Tipo: estrutura
Skill recomendada: /run-cycle
Resumo: Criar DECISIONS.md com migração das decisões do CLAUDE.md (DEC-001 a DEC-003),
context/active_context.md, tasks/blocked.md e 5 prompts adicionais
(master_orchestrator, approver, documenter, data_agent, metrics_agent).
Dependências: BLK-ORQ-01
Observações: CLAUDE.md não deve ser reescrito, apenas estendido com seção ## Skills.

---

### BLK-PROD-03 — Avaliar hex_id como category com benchmark

Status: pendente
Criticidade: média
Prioridade: baixa
Tipo: performance
Skill recomendada: /run-cycle
Resumo: hex_id é chave de join; avaliar se category ajuda ou prejudica performance.
Requer benchmark antes de qualquer mudança.
Dependências: nenhuma

---

### BLK-PROD-02 — Limpar leftovers de staging

Status: pendente
Criticidade: baixa
Prioridade: baixa
Tipo: manutenção
Skill recomendada: /run-cycle
Resumo: Remover data/outputs/*.tmp.parquet e diretório tmp_codex_runtime/.
Dependências: aprovação explícita do usuário para remoção de arquivos.
Observações: não executar sem confirmação explícita. Risco de remoção indevida.

---

### BLK-PROD-01 — Refatoração completa do repositório

Status: pendente
Criticidade: estratégica
Prioridade: média
Tipo: refatoração
Skill recomendada: /run-cycle (fluxo estratégico)
Resumo: Migrado do PRD.md. Próxima etapa de planejamento estrutural do repositório.
Dependências: nenhuma bloqueadora
Observações: requer planejamento detalhado antes de execução. Não iniciar sem aprovação.

---

### BLK-PROD-05 — Geocodificação offline/online de endereço

Status: pendente
Criticidade: alta
Prioridade: baixa
Tipo: feature
Skill recomendada: /run-cycle
Resumo: Implementar geocodificação de endereço apenas se dependência externa for
aprovada ou base local viável identificada.
Dependências: aprovação de dependência externa ou base local.

---

### BLK-PROD-06 — Relatório semanal de movimentação concorrencial

Status: pendente
Criticidade: alta
Prioridade: baixa
Tipo: feature / analytics
Skill recomendada: /run-cycle
Resumo: Snapshots, deltas por rede/cidade e impacto nas oportunidades.
Dependências: definição de fonte de dados concorrencial automatizável.

---

### BLK-PROD-07 — Cenários salvos por usuário e histórico de decisão

Status: pendente
Criticidade: alta
Prioridade: baixa
Tipo: feature
Skill recomendada: /run-cycle
Resumo: Apenas se o dashboard evoluir para produto web interno com múltiplos usuários.
Dependências: decisão de produto sobre evolução para web interno.

---
