---
name: backlog-reconcile
description: Reconcilia o estado real (git) com tasks/backlog.md e tasks/completed.md — detecta blocos "mergeados-mas-não-registrados" (furo que o --emit-delta NÃO pega), a dívida de stub pendente, branches órfãs e o ponteiro "próximo bloco" stale. Use ao pedir "reconcilie o backlog", "audite o backlog", "o que falta stubar", "qual o próximo bloco".
---

# /backlog-reconcile — auditoria de 3 fontes (git × completed × backlog)

O Zelador (BLK-ORQ-12) nunca foi construído. Esta skill implementa a reconciliação localmente e é um
**superset** do `housekeeping_move_block.py --emit-delta` (que só LÊ o `completed.md`, sendo cego a
"mergeado-mas-não-registrado" — o caso RELVIAB de jul/2026).

## Passos
1. **Coletar BLK-IDs mergeados na `main`** por git (`git log --oneline`, PRs, branches `ciclo/*`/`claude/*`).
2. **Cruzar 3 fontes** (casar por **fronteira de palavra**, nunca substring — senão `BLK-FIX-06` arrasta
   `BLK-FIX-06-C`):
   - **git × completed.md** → bloco mergeado **sem** `## Fechamento de ciclo`/`### BLK-` em `completed.md`
     = **"mergeado-mas-não-registrado"** (o furo que o `emit-delta` não vê). Risco: o loop autônomo pode
     **re-executar** trabalho já feito. Correção: append de `## Fechamento de ciclo — <ID>` ao FINAL do
     `completed.md` (append-only/`merge=union`) → `--is-done` passa a sair 0.
   - **backlog.md × completed.md** → bloco com `### BLK-` **aberto** no backlog **e** já concluído em
     completed = **dívida de stub** (= o que o `--emit-delta` entrega). Rodar
     `python scripts/housekeeping_move_block.py <ID> --date <AAAA-MM-DD>` para cada (PR de governança).
3. **Regenerar navegação:** atualizar/gerar no topo do backlog o índice de blocos ABERTOS por epic
   (id · Criticidade · Status · loop-safe · Depende-de) e calcular "**próximo loop-safe desbloqueado**" +
   "próximos manuais" — matando o ponteiro "Priorização atual" stale.
4. **Órfãos:** listar branches `ciclo/*`/`claude/*` sem PR aberto há > 3 dias e PRs parados há > 5 dias.

## Guardrails
- READ-ONLY sobre o M1. Só escreve em `backlog.md`/`completed.md`/índice (governança → PR humano).
- `completed.md` só por APPEND ao final (nunca reordenar — quebra `merge=union`).
- Agendável (skill `schedule`) para rodar como o Zelador que não existe.
