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

### BLK-SCORE-04 — Backtest read-only multivariado das features mercado/censitárias vs. desfecho

| Campo | Valor |
|---|---|
| **Criticidade** | **Alta** (LEITURA/ANÁLISE read-only, sem escrita em M1) |
| **Esteira** | Block Orchestrator → Planner → Builder → QA |
| **Depende de** | **BLK-SCORE-02** e **BLK-SCORE-03** (DEC-001) |
| **Status** | Pendente |
| **Origem** | revisão do BLK-SCORE-03 (resposta à pergunta do usuário "outras variáveis ajudam?") |
| **Insumo** | `data/analysis/dataset_validacao.parquet` (BLK-SCORE-02) + `data/staging/hexagonos_mercado_mapeado.parquet` (131 cols, populadas) + `score_setor_2022_calibrado` |

**Objetivo:** medir, read-only, o poder preditivo INDIVIDUAL e CONJUNTO das features reais das
camadas mercado/censitária contra o desfecho `alunos_recorrentes`, para fundamentar (com
evidência) um eventual enriquecimento dos scores OPERACIONAIS (censitário/mercado) — e, no longo
prazo e somente após popular as colunas zeradas, do M1. Responde diretamente "outras variáveis
além de pop/renda ajudam/são significativas?".

**Escopo (read-only, estilo BLK-SCORE-02):**
- NÃO toca M1: sem editar `scoring.py`/`constants.py`/artefatos oficiais; sem recalcular `score_priorizacao`.
- Join por `hex_id` do `dataset_validacao` com `hexagonos_mercado_mapeado` (reportar taxa de match).
- Saída SÓ em `data/analysis/` (gitignored): relatório agregado/anonimizado, sem PII (sem `nome_unidade`).

**Colunas candidatas (verificadas como populadas e variando):**
- Mercado/competição: `n_concorrentes_mapeados_1km`, `n_concorrentes_mapeados_2km`,
  `dist_concorrente_mais_proximo_m`, `oferta_efetiva_mapeada_1km`, `oferta_efetiva_mapeada_2km`,
  `gap_competitivo_2km`, `pressao_concorrencial_score_2km`, `n_unidades_ultra_1km`,
  `n_unidades_ultra_2km`, `share_*_2km`.
- Demanda/densidade: `densidade_pop_setor_hab_km2`, `pop_total_setor_2022`, `coverage_pct_setor_2022`.
- Censitário: `score_setor_2022_calibrado` (baseline positivo já conhecido, +0.148) como âncora.

**Método:**
- Reusar `analysis/score_backtest.py` (Spearman rho + Pearson r, p-valor; pairwise por célula;
  `to_numeric` coerce; seed=42).
- Por feature: correlação por rede (ultra/skyfit/engcorpo) e AGG.
- Piso N_MIN = 10 (não calcular célula com N<10); IC bootstrap (percentil 2.5/97.5, n_boot=2000,
  seed 42) para N>=30.
- Opcional read-only: regressão multivariável simples / importância relativa para ler sinal
  CONJUNTO (sem produzir um score novo — só diagnóstico de quais features carregam sinal).
- Reportar limitações herdadas do BLK-SCORE-02 (§5): maturação, heterogeneidade, N pequeno,
  precisão de hex, EngCorpo estimado.

**Guardrails (invioláveis):**
- READ-ONLY sobre M1 e sobre todos os artefatos oficiais. Nenhuma escrita fora de `data/analysis/`.
- Não criar/alterar score; só MEDIR. Sem PII no relatório.
- Resultado é base de EVIDÊNCIA; qualquer mudança de score posterior é outro bloco (com seu gate).

**Critérios de aceite:**
- Relatório `data/analysis/relatorio_backtest_mercado.md` com tabela por feature × célula
  (rho/p/r/p/N/flag), ranking por |rho| AGG, e seção de limitações.
- Taxa de match do join reportada; features com input constante marcadas "indefinido".
- Zero escrita em M1/artefatos oficiais; zero PII.
- Reprodutível (seed fixo; script versionado).

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
