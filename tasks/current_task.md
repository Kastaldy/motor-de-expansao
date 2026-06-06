# Current Task

## Bloco atual

ID: BLK-CENSO-02
Nome: Relatório censitário — template e visual padrão do PDF
Status: APROVADO (QA) — pronto para fechamento manual do orquestrador
Tipo: feature
Criticidade: média
Esteira: Block Orchestrator → Planner → [REVISÃO HUMANA das decisões visuais] → Builder → QA
Skill atual: QA concluído (VEREDITO: APROVADO)
Próxima Skill: Fechamento manual (orquestrador) — mover BLK-CENSO-02 via scripts/housekeeping_move_block.py

## Veredito QA (2026-06-05)
- APROVADO. Suíte full `672 passed, 1 skipped` (idêntica em -n auto e serial; 0 falhas, 0 collection errors).
- ruff "All checks passed", mypy "no issues" (fpdf2 ship py.typed → não é falso-verde).
- READ-ONLY M1 confirmado (git scope vazio em pipelines/scoring/censo_point/censo_map/config).
- Anti-PII verificado sobre bytes reais do PDF (2 modos: com assets / offline fallback); nada de data/referencias ou data/ultra staged/rastreado.
- No-bypass: fallback offline exercita o writer real (810KB→93KB sem assets), sem mock.
dry_run: false

## Decisão do gate humano (2026-06-05)
- APROVADO com ALTERAÇÃO de D1: adotar **biblioteca de PDF nova = `fpdf2`** (Felipe escolheu
  "Aprovar, mas com lib de PDF nova" + lib = fpdf2). NÃO estender o writer manual PDF-1.4.
- Consequência: `fpdf2` entra como dependência (base, pois o export do PDF é caminho de produção do
  dashboard); writer reescrito sobre fpdf2; exige rebuild da imagem Docker + redeploy por digest na
  VPS (guardrail §6, SSH gated — passo de OPS após merge, não neste ciclo de código).
- D2 (assets), estrutura de 7 páginas e 6 métricas do Big Numbers: APROVADOS como no plano.
- Guardrail anti-PII (image24.png NUNCA embutido; .pptx/PDF nunca versionados): mantido.

## Tiering de modelo (Passo 4)
- Block Orchestrator: sonnet (Média)
- Planner: opus (override +1 da tabela Média=sonnet — exige extrair sistema de design do .pptx, decidir lib de PDF e reestruturar seções/Big Numbers com lookup cross-layer por hex; atipicamente complexo p/ Média)
- Builder: opus (override +1 da tabela Média=sonnet — código de template novo + assets de branding + Big Numbers via hex H3 + offline-safe; alto risco de regressão visual)
- QA: opus 4.8 (sempre)

## Objetivo
Dar ao PDF do Relatório Pontual Censitário um template e visual padrão Ultra (fundo do
`Teste Modelo.pptx` + logos + cores turquesa/magenta), com a estrutura de seções aprovada por
Felipe (sem endereço/micro-área/polos de fluxo; com concorrentes; slides de população, renda,
score censitário e Big Numbers; último slide creditando o Motor de Expansão), offline-seguro e
READ-ONLY sobre M1.

## Nota de segurança (PII)
- `data/referencias/` está UNTRACKED e contém PII real (PDF de Hortolândia: nome/telefone/e-mail).
  O Planner/Builder DEVE garantir regra de gitignore ANTES de qualquer commit; jamais versionar o
  PDF de referência nem reproduzir a PII no template.

## Paths do ciclo (a confirmar/expandir pelo Planner)
- src/motor_expansao/dashboard/censo_report.py
- src/motor_expansao/dashboard/pages.py (chamada de export)
- pyproject.toml (se nova lib de PDF aprovada)
- .gitignore (data/referencias/)
- tests/unit/test_relatorio_pontual_censitario_export.py
- tests/integration/test_streamlit_app.py
- docs/relatorio_pontual_censitario.md

## Fora de escopo (invioláveis)
- Recálculo/escrita de M1 (scoring/pesos/artefatos oficiais)
- Mudar dados/métricas das camadas (só apresentação e composição)
- Reintroduzir polos de fluxo / slide de endereço / micro-área
- Geocodificação de endereço (BLK-PROD-05)
- Reintroduzir dependência de internet na GERAÇÃO do PDF
