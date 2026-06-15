# Current Task

## Bloco atual

ID: BLK-EST-03
Nome: Fonte real do solicitante (token→consumidor da API) para a marca d'água do PDF
Status: aprovado (APROVADO COM RESSALVAS)
Tipo: feature (rastreabilidade/LGPD; READ-ONLY sobre M1)
Criticidade: alta
Esteira: Block Orchestrator → Planner → [APROVAÇÃO HUMANA] → Builder → QA
Skill atual: QA concluído
Próxima Skill: Fechamento manual (orquestrador Passo 6.0) + abrir BLK-FIX-07 (data-drift CSVs concorrentes)

## Veredito do QA (2026-06-15)
APROVADO COM RESSALVAS. Wiring consumidor→solicitante correto, mínimo, READ-ONLY M1, anti-PII,
provado por 2 testes novos que PASSAM (não skipped). Ressalva (não bloqueadora): suíte full tem 2
falhas PRÉ-EXISTENTES (`test_csvs_concorrentes_legiveis`, data-drift dos CSVs reais 226≠223 / 455≠472),
provadas independentes do bloco via git stash. Recomendo BLK-FIX-07 separado. xdist instável no
ambiente (Py 3.14) → gate rodado serial.

## Objetivo
Passar o `consumidor` já autenticado (token→consumidor, `auth.py`) ao parâmetro `solicitante` do PDF gerado
pela API (`service.py::gerar_pdf_ponto`), de modo que todo PDF emitido via `POST /analisar?formato=pdf`
carregue o nome real do consumidor na marca d'água, com fallback seguro ("Ultra Academia") para geração
anônima. READ-ONLY sobre o M1.

## Decisão do Block Orchestrator
- Bloco é **executável AGORA** na trilha da API (recorte A).
- Trilha do dashboard (pages.py) permanece **bloqueada**: zero infraestrutura de autenticação no Streamlit.
- Lacuna confirmada: `gerar_pdf_ponto` em `service.py` (linha ~306-308) não passa `solicitante=consumidor`
  para `gerar_pdf_relatorio_pontual_censitario`, embora `consumidor` já esteja disponível no escopo.

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: sonnet
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-EST-03 (a partir de main atualizada)

## Paths pré-sujos (NÃO commitar — alheios ao ciclo)
- data/outputs/setores_censitarios_2022_geo/_metadata.json
- data/reports/relatorio_pontual_censitario_base_geo.md
