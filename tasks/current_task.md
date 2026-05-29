# Current Task

## Bloco atual

ID: BLK-OPS-05
Nome: Hardening do sistema de orquestração
Status: aprovado
Tipo: manutenção (meta — altera o próprio mecanismo de ciclos)
Criticidade: alta
Esteira: Block Orchestrator → Planner → [revisão humana] → Builder → QA
Skill atual: QA/Quality Analyzer (concluído)
Próxima Skill: Fechamento manual (com dry-run pós-merge como gate)
Status execução: QA APROVADO — ver context/handoff.md; pendente apenas o dry-run pós-merge (validação humana fora deste ciclo, Passo 6.a)

## Objetivo
Fechar três lacunas de confiabilidade da orquestração: (1) QA re-executa testes em vez de
confiar no log do Builder; (2) handoffs versionados/auditáveis; (3) disciplina de git por ciclo
(branch/commit isolado + rollback documentado), portando as mudanças para Claude e Codex.
