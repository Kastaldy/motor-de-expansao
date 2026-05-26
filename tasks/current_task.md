# Current Task

## Bloco atual

ID: BLK-20260525-01
Nome: Documentar estrutura de orquestração por Skills no README.md
Status: concluído
Tipo: doc
Criticidade: baixa
Esteira: Block Orchestrator → Builder
Skill atual: —
Próxima Skill: —
Dependências: nenhuma

## Objetivo

Adicionar ao README.md uma seção explicando a estrutura de orquestração por Skills do projeto — cobrindo os diretórios tasks/, context/, prompts/ e como usar o comando /run-cycle.

## Escopo permitido
- Adicionar uma seção nova ao README.md sobre orquestração por Skills
- Descrever os diretórios: tasks/, context/, prompts/, .claude/commands/
- Descrever os arquivos de controle: current_task.md, backlog.md, completed.md, handoff.md
- Descrever as Skills e seus papéis: Block Orchestrator, Planner, Builder, QA
- Descrever as esteiras por criticidade (baixa, média/alta, crítica/estratégica)
- Explicar como acionar o ciclo via /run-cycle com exemplo concreto

## Fora de escopo
- Não alterar nenhuma seção já existente do README.md
- Não alterar CLAUDE.md, PRD.md ou arquivos de prompts
- Não alterar código Python, pipelines ou parquets
- Não criar novos arquivos além dos já previstos no handoff
- Não documentar detalhes internos dos prompts (apenas comportamento observável)
- Não alterar tasks/backlog.md ou tasks/completed.md

## Arquivos que devem ser lidos
- README.md — estrutura atual completa
- .claude/commands/run-cycle.md — comportamento do orquestrador e tabela de criticidade
- prompts/block_orchestrator.md — papel da Skill
- prompts/builder.md — papel da Skill
- prompts/planner.md — papel da Skill
- prompts/qa_analyzer.md — papel da Skill

## Arquivos que podem ser alterados
- README.md — único arquivo a ser modificado neste bloco

## Critérios de aceite
- README.md contém seção nova sobre orquestração por Skills com título explícito
- Seção lista e descreve os quatro diretórios (tasks/, context/, prompts/, .claude/commands/)
- Seção descreve os arquivos de controle com uma linha cada
- Seção descreve as quatro Skills e seus papéis (uma linha cada)
- Seção apresenta esteiras por criticidade (baixa, média/alta, crítica/estratégica)
- Seção explica como usar /run-cycle com exemplo concreto de chamada
- Nenhuma seção existente do README.md foi removida ou alterada
- Nenhum arquivo fora do README.md foi modificado

## Validações obrigatórias
[ainda a ser definido pelo Planner]

## Riscos
- README.md pode ter formatação sensível a posição de seção; inserir sem quebrar âncoras existentes
- Risco de verbosidade excessiva: seção deve ser concisa e orientada ao usuário

## Handoff esperado
context/handoff.md gerado pelo Block Orchestrator

## Próximo passo após conclusão
Builder
