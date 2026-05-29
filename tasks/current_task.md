# Current Task

## Bloco atual

ID: BLK-OPS-01-FU4
Nome: Corrigir `encrypt_one` no `setup_secrets_vps.sh`
Status: aprovado
Tipo: bug / tooling
Criticidade: média
Esteira: Block Orchestrator → Planner → Builder → QA
Skill atual: QA/Quality Analyzer (concluído)
Próxima Skill: Fechamento manual (commit por path → merge humano)
Status execução: QA APROVADO — ver context/handoff.md. Não dispara dry-run pós-merge (ciclo não altera a orquestração; só `scripts/setup_secrets_vps.sh` + `docs/backup_restore.md`).
Branch do ciclo: ciclo/BLK-OPS-01-FU4
Paths do ciclo: scripts/setup_secrets_vps.sh (+ docs/backup_restore.md se o §7 referenciar o padrão); arquivos de controle: tasks/current_task.md, tasks/completed.md, tasks/backlog.md, context/handoff.md, context/handoff/

## Objetivo
Corrigir a função `encrypt_one` para usar o padrão `cp SRC DST && sops -e -i DST` (SOPS 3.8.1 casa `path_regex` pelo caminho do DST, que vive em `secrets/`), com guarda de erro: se `sops -e -i` falhar, remover o DST para não deixar plaintext em `secrets/`.
