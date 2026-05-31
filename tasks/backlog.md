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

- BLK-SCORE-01a (concluído 2026-05-31) — ver tasks/completed.md


---

- BLK-SCORE-02 (concluído 2026-05-31) — ver tasks/completed.md


---

- BLK-SCORE-03 (concluído 2026-05-31) — ver tasks/completed.md


---

- BLK-SCORE-04 (concluído 2026-05-31) — ver tasks/completed.md


---

### BLK-SCORE-05 — Viabilidade de proxy exógeno de demanda (pré-requisito de modelagem)

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (LEITURA/ANÁLISE + engenharia de dados; READ-ONLY sobre M1) |
| **Esteira** | Block Orchestrator → Planner → `[REVISÃO HUMANA]` → Builder → QA |
| **Depende de** | **BLK-SCORE-02**, **BLK-SCORE-03 (DEC-001)**, **BLK-SCORE-04** |
| **Status** | Pendente |
| **Origem** | pergunta do usuário "dá para modelar demanda potencial por hex?" (2026-05-31) |

**Contexto / por que existe:** BLK-SCORE-02/04 mostraram que NÃO é possível, hoje, treinar um modelo
preditivo confiável de demanda. Três bloqueios estruturais: (1) **viés de seleção** — o único
desfecho (`alunos_recorrentes`) só existe onde JÁ há unidade; não há observação de demanda em hexes
vazios (sem contrafactual); (2) **alvo enviesado/ruidoso** — desfecho pós-seleção e pós-maturação,
sem `maturacao_status` real, heterogêneo entre redes; (3) **sinal exógeno ≈ nulo** — features de
mercado/competição com IC cruzando zero, OLS conjunto R²≈0.034; o sinal que sobra é endógeno (rede
própria). Conclusão: o gargalo é de DADOS, não de algoritmo. Este bloco é o **pré-requisito de
engenharia de dados ANTES de qualquer modelagem** — NÃO é um bloco de ML.

**Objetivo:** avaliar, read-only, a VIABILIDADE de obter (a) um sinal de **maturação** por unidade
(data de abertura ou proxy auditável) e (b) ao menos um **proxy de demanda EXÓGENO** — independente
da existência de academia no hex. Entregar um diagnóstico de disponibilidade/qualidade de fontes +
recomendação GO/NO-GO para um futuro bloco de modelagem, SEM construir modelo nem alterar score.

**Escopo permitido (read-only, diagnóstico):**
- Inventariar fontes candidatas de demanda exógena e checar cobertura/granularidade por hex/município:
  - **Penetração Wellhub/Gympass** (já há `sinal_wellhub`, `n_parcerias_wellhub` no dataset de
    validação — medir cobertura e se é exógeno ou colado a unidades existentes);
  - dados de **mobilidade/fluxo** ou **busca/intenção** (avaliar se há fonte acessível offline/legal,
    sem criar dependência de API ao vivo — guardrail do projeto);
  - sinais demográfico-comportamentais já no censo/IBGE não usados (faixa etária, vínculo formal,
    renda do trabalho) que correlacionem com propensão a academia.
- Avaliar viabilidade de **maturação**: existe data de abertura por unidade (Ultra real; concorrentes
  via mapeamento)? Que proxy auditável (ex.: primeira aparição em snapshot) seria aceitável?
- Estimar, com o que houver, se algum proxy exógeno tem correlação não-trivial com `alunos_recorrentes`
  CONTROLANDO maturação (reusar `analysis/score_backtest.py`/`feature_backtest_mercado.py`).
- Produzir relatório `data/analysis/viabilidade_demanda.md` (gitignored) com: matriz de fontes ×
  (cobertura, granularidade, exógena S/N, custo/risco de obtenção), achado de correlação controlada
  (se viável), e **recomendação GO/NO-GO** para um eventual `BLK-SCORE-06 — modelo de demanda`.

**Fora de escopo (invioláveis):**
- Construir/treinar qualquer modelo preditivo (isso seria o BLK-SCORE-06, só com GO + seu gate).
- Qualquer escrita/recálculo de M1 (`scoring.py`/`constants.py`/pesos/artefatos) — DEC-001 vigente.
- Criar dependência de API ao vivo no dashboard de produção (guardrail do CLAUDE.md).
- Inventar proxy de maturação/idade sem base auditável (lição do BLK-SCORE-02 §5).
- Saída fora de `data/analysis/`; qualquer PII (`nome_unidade`) no relatório.

**Arquivos a ler:** `data/analysis/relatorio_backtest.md`, `data/analysis/relatorio_backtest_mercado.md`,
`data/analysis/dataset_validacao.parquet` (colunas `sinal_wellhub`/`n_parcerias_wellhub`/`maturacao_status`),
`CLAUDE.md` §8 (DEC-001) e §4 (camadas), `analysis/feature_backtest_mercado.py` (reuso).
**Arquivos a alterar (read-only sobre M1):** novo script de diagnóstico em `analysis/` + testes
sintéticos; relatório em `data/analysis/` (gitignored). NENHUM artefato M1.

**Critérios de aceite:**
- Relatório `data/analysis/viabilidade_demanda.md` com matriz de fontes + veredito GO/NO-GO fundamentado.
- Diagnóstico explícito de maturação (disponível? proxy aceitável?) e de pelo menos 1 proxy exógeno.
- Se houver correlação controlada, reportada com incerteza (IC, N, confounds); sem forçar significância.
- ZERO escrita em M1/artefatos oficiais; ZERO PII; reprodutível (seed fixo; script versionado).

**Guardrails específicos:** READ-ONLY sobre M1; diagnóstico de viabilidade, NÃO modelagem; sem
dependência de API ao vivo; alimenta a decisão sobre os gates G1/G2/+contrafactual da DEC-001.

**Risco:** baixo (read-only). O valor é evitar investir em ML sobre dados que não identificam demanda;
o entregável é um GO/NO-GO honesto, não um modelo.

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
