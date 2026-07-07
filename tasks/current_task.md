# Current Task

## Bloco atual

ID: BLK-ACENTO-02
Nome: Acentuação dos relatórios gerados (PDF/CSV)
Status: APROVADO (QA 2026-07-07, re-verificação pós follow-up) — ressalva das legendas PIL RESOLVIDA
        (relatorio_municipal.py:106,112 agora "Aprovado (dado próprio)"). Suíte serial autoritativa:
        1434 passed / 2 skipped / 1 failed (única falha = pré-existente/ambiental do M2
        test_run_readonly_m1_por_mtime, parquet gitignored ausente; não relacionada). ruff limpo,
        mypy só 6 pré-existentes (0 novo), import ok. Aguardando fechamento do orquestrador
        (housekeeping move + commit por path). Revisão visual humana dos 3 PDFs recomendada.
Tipo: manutenção (texto de relatório PDF/CSV)
Criticidade: média
Esteira: Block Orchestrator → Planner → Builder → QA (sem gate humano)
Skill atual: QA/Quality Analyzer (concluído)
Próxima Skill: Fechamento manual (orquestrador)

## Objetivo
Acentuar corretamente o texto dos relatórios gerados (Relatório Pontual Censitário 1,5 km e
Relatório Municipal), renderizando via latin-1 (core font Helvetica do fpdf2), SEM trocar
fonte/biblioteca e SEM introduzir caracteres fora de latin-1 que virem "?" (banir tipografia
"esperta": travessão, bullet, seta, reticências unicode, aspas curvas, ©). READ-ONLY sobre o M1;
núcleo funcional censo_* (interseção/raio/estrutura de páginas/marca d'água) INTOCADO — só STRINGS.

## Branch do ciclo (COMPARTILHADA — decisão do usuário)
ciclo/BLK-ACENTO-01 (MESMA branch do BLK-ACENTO-01, já commitado em 10d7023).
Decisão explícita de Vinicius (2026-07-07): rodar BLK-ACENTO-02 no estado atual, na mesma branch,
para abrir UM PR com os dois blocos juntos após a conclusão. NÃO criar branch nova ciclo/BLK-ACENTO-02.

## Tiering de modelo (Passo 4) — Média
- Block Orchestrator: sonnet
- Planner: sonnet
- Builder: opus (override +1: volume ~50 _ascii em censo_report.py + ~142 em relatorio_municipal.py,
  atualização de ~26+40 asserts de bytes, sutileza latin-1/"?" em texto de relatório auditável)
- QA: opus 4.8 (sempre)

## Paths do ciclo (commit por path — NUNCA git add -A)
- src/motor_expansao/dashboard/censo_report.py (strings COM acento; comentário-fonte corrigido)
- src/motor_expansao/dashboard/relatorio_municipal.py (strings COM acento)
- tests/unit/test_relatorio_municipal.py, tests/unit/test_relatorio_pontual_censitario_export.py
- (novo teste anti-"?" de regressão)
- tasks/current_task.md, tasks/completed.md, tasks/backlog.md (fechamento)
- context/handoff.md, context/handoff/

## Guardrails
- §5 READ-ONLY M1: zero recálculo/alteração de score/pesos/carteira/plano/artefatos oficiais.
- Núcleo censo_* INTOCADO: setor_censitario_intersecao_area_1p5km, raio 1,5 km,
  RAIO_CENSITARIO_DEFAULT_KM, contagem/ordem/estrutura de páginas, grid de Big Numbers, marca
  d'água anti-PII (BLK-EST-03), set_compression(False), pdf_version — SÓ as STRINGS mudam.
- Manter _ascii() como salvaguarda; NÃO trocar core font por TTF Unicode (latin-1 basta).
- Banir tipografia "esperta" no texto de PDF (— – • → … aspas curvas ©) → ASCII (- " (c) ...).
- Teste anti-"?" de regressão: gerar PDFs e assertar zero byte b"?" inesperado (ou _ascii com
  errors="strict" em modo auditoria).
- Anti-PII inalterado: .pptx/PDF nunca versionados, image24.png nunca embutido.
- Fora de escopo: UI do dashboard (BLK-ACENTO-01, já concluído).
