# Índice de `context/handoff/`

Snapshots append-only dos agentes da esteira (`block-orchestrator` · `planner` · `builder` · `qa`), um por
passo de ciclo, nomeados `AAAAMMDD-HHMMSS-<slug>.md`. **Nunca editar um snapshot existente** (convenção do
`.claude/commands/run-cycle.md`); a ordenação lexicográfica do nome = ordem cronológica.

## Volume (2026-07-19)
| Mês | Snapshots |
|---|---|
| 2026-05 | 88 |
| 2026-06 | 234 |
| 2026-07 | 218 |

## Política de retenção (proposta)
Os snapshots antigos não precisam viver no caminho de leitura primária. Proposta (a executar em janela **sem
ciclos em voo**, para não colidir com o loop): arquivar trimestres fechados num tarball fora do repo e manter
versionados só os ciclos recentes + este índice. A skill `/backlog-reconcile` (ou o Zelador do BLK-ORQ-12,
quando existir) regenera este índice.

> Reconciliação de 2026-07-19 (PR #134): índice criado; a **poda efetiva** foi deixada como passo separado —
> é destrutiva (remove trilha versionada) e precisa de decisão explícita.
