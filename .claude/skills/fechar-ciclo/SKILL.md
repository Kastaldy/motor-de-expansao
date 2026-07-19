---
name: fechar-ciclo
description: Executa o Passo 6 (fechamento) do /run-cycle de forma correta e determinística, em qualquer sessão — inclusive features ad-hoc fora do /run-cycle. Escolhe o modo merge-humano vs auto-merge, roda o helper de housekeeping, faz commit por path e sincroniza o bookkeeping. Use ao pedir "feche o ciclo", "faça o housekeeping", "registre a conclusão do bloco".
---

# /fechar-ciclo — o Passo 6 do run-cycle, empacotado

Executor único do fechamento. **Não é uma cópia da regra** — a fonte canônica é
`.claude/commands/run-cycle.md` (Passo 6) + DEC-016 (`docs/decisions/DEC-016.md`); esta skill só
executa esse procedimento de forma consistente, evitando a prosa densa repetida em vários lugares.

## Passos
1. **Ler a criticidade do bloco** na BASE (`tasks/backlog.md`). Define o modo:
   - **Baixa/Média** → **modo auto-merge**: NÃO tocar `tasks/backlog.md`; só **append** do resumo
     `## Fechamento de ciclo — <BLK-ID> (<data>)` ao FINAL de `tasks/completed.md` (respeita append-only/
     `merge=union`). O stub do backlog é DIFERIDO para o PR de housekeeping em lote (use `/backlog-reconcile`).
   - **Alta/Crítica / merge-humano** → mover o bloco com o helper versionado (byte-idêntico):
     ```
     python scripts/housekeeping_move_block.py <BLK-ID> --date <AAAA-MM-DD>
     python scripts/housekeeping_move_block.py <BLK-ID> --check     # valida antes do commit
     ```
2. **Sincronizar o contexto** quando a feature muda estado de produção: `CLAUDE.md` §5 (nota curta),
   `docs/<runbook>` afetado, e a DEC quando aplicável (use `/registrar-decisao`).
3. **Commit por path** (nunca `git add -A`): só os arquivos do ciclo + `context/handoff/` versionado.
   **NUNCA** commitar `context/handoff.md` nem `tasks/current_task.md` (locais/gitignored). No modo
   auto-merge, o commit **não inclui `backlog.md`** (só código + testes + `completed.md`).
4. **Merge por criticidade (DEC-016):** Baixa/Média → auto-merge nativo (`gh pr merge <N> --auto --squash`);
   Alta → label `aprovado-humano` (humano ≠ autor); Crítica → `critica-aprovada` (do dono). Deploy sempre manual.
5. **Conflito de `completed.md`/`backlog.md`:** resolver SEMPRE por APPEND (nunca reescrita/reordenação —
   quebra o `merge=union` e recria o conflito de arquivo inteiro).

## Guardrails
- `completed.md` é a **fonte única de verdade** de conclusão; a seleção do loop pula bloco já concluído lá.
- Ciclo ad-hoc (fora do backlog): o helper sai com `EXIT_AD_HOC` (código 3) = no-op; o resumo vai a `completed.md`.
- READ-ONLY sobre o M1. NO-BYPASS: veredito de QA nunca se baseia em verde obtido contornando a config real.
