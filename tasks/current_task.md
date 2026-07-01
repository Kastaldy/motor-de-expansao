# Current Task

## Bloco atual

ID: BLK-LTV-03
Nome: Análise de correlação território × retenção/LTV [GATE DE DECISÃO]
Status: em execução
Tipo: análise (correlação; camada paralela READ-ONLY sobre o M1)
Criticidade: alta
Esteira: Block Orchestrator → Planner → [REVISÃO HUMANA — decisão do eixo] → Builder → QA
Skill atual: QA (concluído)
Próxima Skill: Fechamento manual (orquestrador — Passo 6.0)
Status: aprovado (QA 2026-07-01 — APROVADO; suíte full 1180 passed/1 skipped; M1 preservado; GATE GO honesto)

## Objetivo
Correlacionar território (renda, densidade, `score_priorizacao`, concorrência) ×
`PROB_CANCEL_90D_MEDIA` e `LTV_PROSPECTIVO_12M_MEDIANO`, controlando por maturidade quando houver
dado (caveat estrutural do epic). Método DEC-008: Spearman + bootstrap/IC, sem R² in-sample; scatter +
significância. Gate de decisão: correlação fraca → epic vira consolidação de dados (LTV-01/02 como
ativo, sem score); forte → avança para BLK-LTV-04. Entregar rho + IC bootstrap por par, confounds
declarados (maturidade, N, sobrevivência), veredito GO/NO-GO honesto.

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: sonnet
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Gate humano
APÓS o Planner: PARAR e apresentar o handoff ao usuário para aprovação explícita antes do Builder
(esteira Alta + gate de decisão do eixo). NÃO é loop-safe.

## Branch do ciclo
ciclo/BLK-LTV-03 (criada a partir de ciclo/BLK-LTV-02 @ HEAD; contém LTV-02 + housekeeping LTV-01).

## Paths pré-sujos (NÃO commitar — alheios ao ciclo)
- data/raw/ibge/malha_brasil.geojson (D), data/raw/ibge/malha_uf_brasil.geojson (D)
- scripts/backtest_smartfit_scores.py (??)

## Dependência
- BLK-LTV-02 concluído: `data/staging/unidade_territorio_retencao.parquet` (88×36) disponível.

## Guardrails
- §5 (READ-ONLY M1); DEC-001 intacta. Nenhuma coluna/artefato M1 alterado.
- DEC-008: Spearman + bootstrap/IC; PROIBIR R² in-sample e fit(X,y)→predict(X); N pequeno (56 com hex_id).
- Confounds obrigatórios no relatório: maturidade (sem data de abertura), N pequeno, seleção de sobreviventes.
- Este bloco NÃO cria score (isso é BLK-LTV-04, condicional ao GO e com DEC própria).
