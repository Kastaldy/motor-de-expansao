# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner — produz o outline do PRD padrão e PARA no gate `[revisão humana do outline]` antes de qualquer escrita em `PRD.md`. Só o Builder escreve `PRD.md`, e somente após aprovação humana do outline.

## Bloco refinado
**BLK-PRD-01 — Reescrever PRD.md como PRD padrão do projeto.**
O `PRD.md` atual contém o "Programa de Melhorias — Referência do Master Orchestrator", conteúdo temporário cujos 9 blocos JÁ foram migrados para `tasks/backlog.md` (2026-05-29). Reescrever `PRD.md` como um PRD padrão de produto: documento canônico mas SUBORDINADO ao `CLAUDE.md` (fonte de verdade), que REFERENCIA (não redefine) score/guardrails do `CLAUDE.md` §3/§5 e REFERENCIA (não copia) o roadmap de `tasks/backlog.md`. Há uma edição não-commitada pré-existente em `PRD.md` (`M PRD.md`) que será absorvida/substituída pela reescrita.

## Objetivo
Substituir todo o conteúdo de `PRD.md` por um PRD padrão de produto do Motor de Expansão Ultra Academia, subordinado ao `CLAUDE.md`, sem duplicar valores canônicos nem o backlog.

## Escopo permitido
- Substituir TODO o conteúdo de `PRD.md` por um PRD padrão de produto. Estrutura sugerida (Planner refina e apresenta o outline para revisão humana antes do Builder escrever):
  - Visão e objetivo do produto (Motor de Expansão Ultra Academia)
  - Público-alvo (18–45) e contextos de uso
  - Escopo do produto / fora de escopo
  - Camadas e trilhas (M1 oficial territorial, censitário, híbrido, mercado/residual, Expansão de Domínio)
  - Score oficial e guardrails canônicos — REFERENCIAR `CLAUDE.md` §3/§5, NÃO redefinir valores
  - Requisitos funcionais e não-funcionais (dashboard offline, performance, sem API ao vivo)
  - Métricas de sucesso
  - Roadmap/fases — REFERENCIAR `tasks/backlog.md`, NÃO copiar os blocos
  - Dependências e restrições (infra/VPS)
- Commit final do `PRD.md` por path (entregável do ciclo), feito no fechamento.

## Fora de escopo
- Alterar `CLAUDE.md`, código, `config.py`, score (`score_priorizacao`, `hex_score_estrutural`, pesos), artefatos M1.
- Reescrever, mover ou re-duplicar blocos do `tasks/backlog.md`.
- Incluir `tasks/backlog.md` no commit (está pré-sujo com migração de blocos alheia a este ciclo — `git add tasks/backlog.md` arrastaria conteúdo não relacionado). Marcação de conclusão fica em `tasks/completed.md`; `backlog.md` deixado ao humano (igual ao fechamento do BLK-OPS-06).
- Qualquer comando no VPS.

## Arquivos que devem ser lidos
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\PRD.md` (estado atual + histórico git)
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\CLAUDE.md` (fonte canônica — referenciar, não copiar valores)
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\tasks\backlog.md` (referenciar o roadmap, NÃO duplicar)

## Arquivos que podem ser alterados
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\PRD.md` (ÚNICO entregável de conteúdo — escrito SOMENTE pelo Builder, pós-gate)
- Controle do ciclo (não-conteúdo): `tasks/current_task.md`, `tasks/completed.md`, `context/handoff.md`, `context/handoff/`

## Critérios de aceite
- `PRD.md` é um PRD padrão de produto coerente, subordinado ao `CLAUDE.md`, sem duplicar o backlog.
- Nenhum valor canônico contradiz o `CLAUDE.md` — o PRD REFERENCIA (não redefine) pesos (`renda=0.40`, `pop=0.60`), parâmetros (`H3_RESOLUTION=7`, `DIST_MIN_ULTRA_KM=1.0`, `RENDA_MIN=4500.0`, `AREA_MIN_M2=1200.0`) e o score oficial (`score_priorizacao`).
- Roadmap do PRD aponta para `tasks/backlog.md` em vez de copiar os blocos.
- `git --no-pager diff --stat -- PRD.md` mostra somente `PRD.md` alterado no entregável de conteúdo.
- `pytest -q` segue verde (doc-only: nenhum código tocado; baseline 532 passed, 1 skipped).
- `PRD.md` commitado por path, sem arrastar outros arquivos não relacionados.

## Criticidade classificada
Média.
Justificativa: bloco doc-only — NÃO escreve em `score_priorizacao`, `hex_score_estrutural`, carteira, plano, código, `config.py`, `CLAUDE.md` nem artefatos M1; portanto NÃO é CRÍTICA pela regra do score. Mantida em Média (não elevada para Alta), MAS o gate `[revisão humana do outline]` entre Planner e Builder é OBRIGATÓRIO por ser documento canônico — independentemente do rótulo de criticidade.

## Esteira recomendada
Block Orchestrator (concluído) → Planner → `[revisão humana do outline]` (gate obrigatório, antes do Builder) → Builder → QA.

## Riscos identificados
- Desalinhamento do formato/conteúdo do PRD com a expectativa do usuário — mitigado pelo gate de revisão humana do outline antes da escrita.
- Risco de redefinir valores canônicos no PRD (deriva em relação ao `CLAUDE.md`) — mitigado pela regra "referenciar, não redefinir" e pelo critério de aceite de não-contradição.
- Risco de escopo: `tasks/backlog.md` está pré-sujo (`M`, ~127 linhas de migração alheia). NÃO incluir no commit por path; commitar somente `PRD.md`.
- Edição pré-existente `M PRD.md` será substituída pela reescrita — esperado, não é regressão.

## Guardrails ativos
- Guardrail permanente (CLAUDE.md §5): visualizações/análises/interações NÃO podem recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano de domínio ou artefatos oficiais do M1 sem aprovação explícita. Este bloco é doc-only e NÃO os toca.
- O PRD deve apenas REFERENCIAR valores canônicos (score, pesos, parâmetros, guardrails) — JAMAIS redefini-los. `CLAUDE.md` permanece a fonte de verdade; o PRD é subordinado a ele.
- GUARDRAIL ABSOLUTO (CLAUDE.md §6): nenhum comando no VPS sem confirmação explícita do usuário, por comando. Este bloco não toca o VPS.
- Uma tarefa ativa por vez; não expandir escopo; não resolver múltiplos blocos; não implementar nada antes do gate.
