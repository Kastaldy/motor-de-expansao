# Current Task

## Bloco atual

ID: BLK-LTV-04
Nome: Score M2 territorial de retenção (cria eixo de score novo)
Status: em execução
Tipo: feature (cria SCORE paralelo M2; camada paralela READ-ONLY sobre o M1)
Criticidade: estratégica
Esteira: Block Orchestrator → Planner → [APROVAÇÃO HUMANA + DEC] → Builder → QA
Skill atual: QA (concluído)
Próxima Skill: Fechamento manual (orquestrador Passo 6.0 housekeeping + merge humano)
Status final: **APROVADO** (QA, 2026-07-01) — NO-GO honesto, reprodutível, READ-ONLY M1; suíte full 1193 passed / 1 skipped / 0 failed; ruff+mypy limpos; sem parquet de score (DEC-014 decisão 2). Housekeeping `--check` = FALHA (estado pré-close correto; move é do orquestrador).

## Resultado do Builder (2026-07-01)
- DEC-014 implementada (4 decisões de produto do gate aplicadas): pesos A 0.50/0.50; fallback NO-GO = encerrar sem score; Ridge numpy puro (sem sklearn); nomenclatura `score_retencao`.
- **VEREDITO REAL = NO-GO** (honesto, DEC-014 decisão 2). Melhor modelo `score_priorizacao` sozinho: R²_oof=+0.0399 (IC [-0.101,+0.120] cruza zero), rho_oof=-0.073 (<0.30, IC cruza zero). Parquet de score NÃO gerado; só relatório `data/analysis/relatorio_score_retencao.md` (gitignored).
- Validações: 237 passed (subset novo+LTV-03+streamlit), ruff clean, mypy src OK (88 files), import ok, mtime M1 inalterado.
- Novos: `src/motor_expansao/lifetime/score_retencao_territorial.py`, `tests/unit/test_score_retencao_territorial.py`.

## Objetivo
Compor um score de expansão paralelo (M2) ponderando captação + LTV/retenção territorial, como camada
paralela READ-ONLY sobre o M1 (não altera score_priorizacao/pesos/artefatos). Exige DEC própria antes
do Builder (disciplina DEC-001/DEC-008). Pesos aprovados em DEC; validação LOO/k-fold vs baseline.

## Tiering de modelo (Passo 4) — Crítica/Estratégica
- Block Orchestrator: opus
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Gate humano + DEC
APÓS o Planner: PARAR e apresentar o plano ao usuário para APROVAÇÃO EXPLÍCITA + registro de DEC
própria (numeração DEC-0XX) em CLAUDE.md §8 antes do Builder. NÃO é loop-safe (cria score).

## Branch do ciclo
ciclo/BLK-LTV-04 (criada a partir de ciclo/BLK-LTV-03 @ HEAD; contém LTV-02/01-hk/03).

## Paths pré-sujos (NÃO commitar — alheios ao ciclo)
- data/raw/ibge/malha_brasil.geojson (D), data/raw/ibge/malha_uf_brasil.geojson (D)
- scripts/backtest_smartfit_scores.py (??)

## Dependência
- BLK-LTV-03 = GO (concluído): sinal território→LTV maturidade-robusto.
- Dataset: data/staging/unidade_territorio_retencao.parquet (88×36).

## Evidência fresca (preview exploratório 2026-07-01, read-only) que informa o desenho do M2
- score_priorizacao × LTV = +0.391; SOBREVIVE controle de maturidade (+0.370) e maturidade+renda (+0.306, IC[+0.034,+0.550]).
- Renda SOZINHA colapsa ao controlar maturidade → carregador é o COMPOSTO score_priorizacao (renda+pop), não renda pura.
- Maturidade: driver forte do churn-90d (−0.394) mas ~independente do score (+0.145 n.s.).
- Data de inauguração real disponível em data/staging/growth_api_historico.parquet (campo `inauguracao`, 89 unidades) — gate G1 da DEC-001 satisfeito.
- CAVEAT DE DESENHO: maturidade é atributo de UNIDADE, não de hex candidato → serve de CONTROLE de validação, NÃO de feature do score territorial por hex.

## Guardrails
- §5 (READ-ONLY M1); DEC-001 intacta (score_priorizacao/pesos/artefatos M1 INALTERADOS; M2 só LÊ score_priorizacao).
- DEC-008: validação LOO/k-fold vs baseline da média; PROIBIR R² in-sample e fit(X,y)→predict(X); N pequeno (56) exige IC + honestidade.
- DEC-009: M2 é score de RETENÇÃO territorial, NÃO preditor de magnitude de demanda.
- Este bloco EXIGE DEC registrada antes do Builder.
