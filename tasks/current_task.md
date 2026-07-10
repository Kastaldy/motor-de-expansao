# Current Task

## Bloco atual

ID: BLK-RELMUN-06
Nome: Texto dinâmico das zonas de atuação no slide Síntese (quadros finais)
Status: APROVADO — fechamento concluído (housekeeping move + commit por path + merge na secundária)
Tipo: manutenção (texto de relatório)
Criticidade: média
Esteira: Block Orchestrator → Planner → [gate D1 APROVADO] → Builder → QA (APROVADO)
Skill atual: Fechamento (orquestrador) CONCLUÍDO
Próxima Skill: FIM DOS 3 CICLOS — secundária integracao/map02-relmun05-06 pronta; PR NÃO aberto (aguarda verificação de Vinicius)
Status QA: APROVADO (FINAL). Suíte completa autoritativa (orquestrador, serial): 1545 passed, 2 skipped, 1 failed. Única falha = test_score_retencao_territorial.py::test_run_readonly_m1_por_mtime (camada M2 lifetime/, parquet gitignored ausente) — PRÉ-EXISTENTE/AMBIENTAL, alheia a este bloco. +9 vs baseline = os 9 testes novos. Validações rápidas todas verdes (ruff pass; mypy 6 pré-existentes/0 novo; import ok; subconjunto 50 passed; git diff --stat só nos 4 arquivos do ciclo). Ver context/handoff.md (QA). Próximo: housekeeping via helper + merge para integracao/map02-relmun05-06 (sem PR).

## Gate humano D1 — APROVADO por Vinicius em 2026-07-08
- Os 4 textos do card 3 "Movimento Recomendado" APROVADOS como propostos pelo Planner:
  - 0 zonas: "Movimento Recomendado: hexágonos aprovados insuficientes para zonas de atuação neste município."
  - 1 zona (Âncora central): "Movimento Recomendado: adensar o núcleo central, concentrando a expansão na região de maior aprovação."
  - 2 zonas (Âncora + Flancos): "Movimento Recomendado: adensar o núcleo central e avançar pelos flancos, capturando os residuais laterais."
  - 3 zonas (Âncora + Flancos + Cerco): "Movimento Recomendado: posicionamento periférico, cercar o núcleo pelos flancos antes da concorrência." (texto atual, mantido)
- Página Domínio (_dominio_page): FORA de escopo (só o slide Síntese).

## Objetivo
No slide Síntese (_sintese_page, relatorio_municipal.py:1949 — 3 cards finais; card 3 "Movimento
Recomendado"), substituir o texto CONSTANTE das zonas de atuação por um texto GERADO a partir dos
tipos de zona efetivamente encontrados (result["zonas_geo"] / _ZONA_GEO_ROTULOS = Âncora central /
Flancos laterais / Cerco), com fallback para 0 zonas. READ-ONLY sobre o M1; só display.

## Gate humano (produto) — D1 REAL (precisa da aprovação de Vinicius)
As regras do texto por combinação de zonas. O Planner propõe o mapeamento (ex.: só Âncora central ->
adensar o núcleo; +Flancos laterais -> cercar pelos flancos; +Cerco -> estratégia completa de cerco);
o orquestrador PARA e apresenta ao humano para aprovação antes do Builder.

## Fluxo de branch (integração — decisão de Vinicius 2026-07-08)
- Branch do ciclo: ciclo/BLK-RELMUN-06, ramificada da SECUNDÁRIA integracao/map02-relmun05-06.
- Ao fechar (QA aprovado + commit por path), o orquestrador MERGEIA ciclo/BLK-RELMUN-06 -> integracao/map02-relmun05-06.
- APÓS os 3 ciclos, NÃO abrir PR (Vinicius pediu para verificar o resultado primeiro); parar na secundária.

## Tiering de modelo (Passo 4) — Média
- Block Orchestrator: sonnet
- Planner: sonnet
- Builder: sonnet (mudança de texto localizada; menor risco que RELMUN-05)
- QA: opus 4.8 (sempre)

## Paths do ciclo (commit por path — NUNCA git add -A)
- src/motor_expansao/dashboard/relatorio_municipal.py
- tests/unit/test_relatorio_municipal.py
- tasks/current_task.md, tasks/completed.md, tasks/backlog.md (fechamento)
- context/handoff.md, context/handoff/

## Guardrails
- §5 READ-ONLY M1: zero recálculo/alteração de score/pesos/carteira/plano/artefatos.
- Só LEITURA de result["zonas_geo"]/_zonas_geometricas/_zonas_do_municipio (a zonificação em si não muda);
  dominio_df, flag_sam, score intactos.
- Manter os outros 2 cards da Síntese (penetração, residual) e o VALOR "N zonas de atuação" inalterados.
- Núcleo censo_* / estrutura de páginas / marca d'água / set_compression: intocados.
- §2 acentuação: texto novo COM acento; não acentuar identificadores. Sem tipografia fora de latin-1
  (só - " (c) ...) — é texto de PDF.
