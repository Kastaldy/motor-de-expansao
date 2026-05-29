# Current Task

## Bloco atual

ID: BLK-OPS-06
Nome: Alinhar checkout do VPS via `git pull`
Status: APROVADO (concluído 2026-05-29)
Tipo: operação / infraestrutura
Criticidade: baixa
Esteira: Block Orchestrator → execução VPS conduzida pelo orquestrador (comando-a-comando §6) → Fechamento
Skill atual: Fechamento (concluído)
Próxima Skill: — (ciclo fechado)
Branch do ciclo: ciclo/BLK-OPS-06
dry_run: false
Resultado: VPS `/opt/motor-expansao/app` fast-forward `64e68b1 → 8218f38`; 5 `secrets/*.enc.*` agora tracked; HEAD do VPS == origin/main. Detalhes em tasks/completed.md e context/handoff.md. NÃO dispara dry-run (não altera a orquestração).

## Objetivo
Fazer `git pull --ff-only` no checkout do VPS (`/opt/motor-expansao/app`) para alinhá-lo ao `origin/main`, materializando os 5 `secrets/*.enc.*` como arquivos rastreados e eliminando o estado "atrás do origin".

## Nota de execução (GUARDRAIL §6)
A execução real é uma sequência de comandos no VPS de produção via MCP `ssh-vps-ultra`. Sob o GUARDRAIL ABSOLUTO da §6 do CLAUDE.md, NENHUM comando no servidor roda sem confirmação explícita do usuário, comando a comando. Por isso a fase de execução NÃO é delegada a um sub-agente Builder autônomo — é conduzida pelo orquestrador (main loop) com aprovação individual de cada comando. Block Orchestrator apenas refina/classifica e produz o handoff (não toca o VPS).

## Paths do ciclo (commit por path no fechamento)
- Controle: tasks/current_task.md, tasks/completed.md, tasks/backlog.md, context/handoff.md, context/handoff/
- ATENÇÃO escopo: `tasks/backlog.md` já tem 92 linhas de edição pré-existente NÃO relacionada (migração de blocos). Tratar no fechamento para não arrastar conteúdo alheio ao ciclo num commit por path. `PRD.md` (M, pré-existente) NÃO entra no ciclo.
- Nenhum arquivo de código/artefato M1 é tocado.
