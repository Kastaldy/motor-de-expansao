---
name: clickup-sync
description: Audita e sincroniza o ClickUp contra o trabalho real no GitHub, aplicando a rubrica de pontuação correta (que o agente já errou por adivinhação). Cobre frentes, pontos por tag/subtarefa, convenções de assignee/creator e o gap-audit GitHub↔ClickUp. Use ao pedir "audite o ClickUp", "pontue a semana", "sincronize as tarefas", "confira as pontuações".
---

# /clickup-sync — rubrica + gap-audit GitHub↔ClickUp

A rubrica vive na cabeça do Felipe; sem esta referência o agente inventa e o placar sai errado
(episódio real: escreveu "Operacional não pontua" — está errado). Use os tools MCP `clickup_*`.

## Rubrica de pontuação (canônica — NÃO adivinhar)
- **Frentes:** Operacional · Projeto · Análise.
- **Operacional = 1 ponto por tag**, incluindo **subtarefas** (não só tarefas). Operacional **pontua**.
- **Projeto / Análise:** por complexidade — **baixa = 1 · média = 3 · alta = 8**.
- **1 bloco ≠ 1 tarefa.** Uma tarefa = uma **entrega concreta** (pode agrupar vários blocos, ou um bloco
  virar várias tarefas). Não mapear 1:1 mecanicamente.

## Convenções
- **Assignee:** ao concluir/mover uma tarefa, confirmar que ela está atribuída à pessoa certa (o agente já
  fechou tarefa esquecendo de reatribuir — seguia com outra pessoa). Conferir `assignee` explicitamente.
- **Creator vs assignee:** distinguir quem criou de quem executa; a pontuação segue o executor.

## Gap-audit GitHub↔ClickUp
1. Puxar PRs/commits mergeados por período (por `BLK-ID` no título/branch).
2. Puxar tarefas do ClickUp no período por assignee (`clickup_filter_tasks`/`clickup_search`).
3. Reportar os gaps: (a) trabalho mergeado **sem tarefa**; (b) tarefa **não concluída** apesar do merge;
   (c) **assignee errado**; (d) pontuação divergente da rubrica.
4. Aplicar correções **sob confirmação** (`clickup_update_task`/`clickup_create_task`).

## Guardrails
- Nunca inferir regra de pontuação nova; se a rubrica não cobrir um caso, **perguntar**, não adivinhar.
- Read-only sobre o repositório; escreve só no ClickUp, sob confirmação.
- Relacionada à skill externa `produtividade-clickup-ultra` (Desktop/Cowork) — esta é a versão do repo.
