# Current Task

## Bloco atual

ID: BLK-20260528-03
Nome: Atualizar base de concorrentes (CSVs + Logos)
Status: em execução
Tipo: manutenção / dados
Criticidade: média
Esteira: Block Orchestrator → Builder → QA
Skill atual: Builder
Próxima Skill: QA

## Objetivo

Substituir CSVs e logos de concorrentes com versões atualizadas de `concorrentes/Unidades/`
e `concorrentes/Logos/`, registrar 11 novas redes no `competitors.py`, normalizar nomes
de logos legados e sincronizar com o servidor VPS via MCP.

## Escopo

**CSVs atualizados (substituição):** 28 arquivos existentes em concorrentes/ (versões novas de Unidades/)
**CSVs novos:** a_fitness, biohit, evolve, feira_fitness, formula, motion_fit, my_box, pacer, pro3, redfit, skyfit
**Logos atualizados:** ~18 logos com naming normalizado (ex: bluefit_academia_logo → logo_bluefit)
**Logos novos:** a_fitness, biohit, contorno_do_corpo (separado), evolve, feira_fitness, formula,
               kore (renomeado), live (renomeado), motion_fit, my_box, pacer, pro3, redfit, skyfit, vidya_studio (typo corrigido)
**competitors.py:** COMPETITOR_SPECS + COMPETITOR_BRANDS + COMPETITOR_LOGO_FILES atualizados
**Nota:** SkyFit reincluída — arquivo fornecido explicitamente pelo usuário (decisão anterior de exclusão revogada)
