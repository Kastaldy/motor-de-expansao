# Current Task

## Bloco atual

ID: BLK-UI-01
Nome: Refatoração UX/UI da plataforma (recorte: menu lateral, loading, limpeza visual)
Status: aprovado (recorte) — QA APROVADO em 2026-06-12; bloco amplo BLK-UI-01 permanece ABERTO
Tipo: feature (UX/UI)
Criticidade: alta
Esteira: Block Orchestrator → Planner → [REVISÃO HUMANA do plano] → Builder → QA
Skill atual: QA (concluído 2026-06-12; VEREDITO APROVADO — recorte do BLK-UI-01)
Próxima Skill: Fechamento manual (registrar recorte em completed.md SEM fechar o bloco amplo)

## Objetivo
Recorte focado do BLK-UI-01: (1) deixar o menu lateral mais aparente, (2) criar indicador
visual nos momentos de carregamento das telas, (3) limpeza de poluição visual — sem regressão
funcional e READ-ONLY sobre o M1.

## Sugestões de melhorias (pedido do usuário)
- Deixar o menu lateral mais aparente
- Criar indicador visual para os momentos de carregamento das telas
- Limpeza de poluição visual

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: sonnet
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Gate humano
Esteira Alta exige REVISÃO HUMANA do plano do Planner antes do Builder.

## Branch do ciclo
ciclo/BLK-UI-01 (a partir de ciclo/BLK-EST-02 @ HEAD; BLK-EST-02 ainda não mergeado em main)

## Escopo permitido (do backlog BLK-UI-01)
- src/motor_expansao/dashboard/ (pages/components/utils/constants visuais)
- preservar carga lazy por UF, render lazy de abas e fonte de mapa enxuta (Blocos 4–6)
- testes correspondentes

## Fora de escopo (invioláveis)
- recalcular qualquer score (score_priorizacao, score_setor_2022_calibrado, residual, SAM)
- artefatos M1 oficiais
- recolocar dependência de API ao vivo no dashboard de produção
- quebrar contratos de performance já entregues (carga lazy / render lazy / mapa enxuto)

## Paths pré-sujos (NÃO commitar — alheios ao ciclo)
- data/outputs/setores_censitarios_2022_geo/_metadata.json
- data/reports/relatorio_pontual_censitario_base_geo.md

dry_run: false
