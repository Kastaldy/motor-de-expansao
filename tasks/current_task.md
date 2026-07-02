# Current Task

## Bloco atual

ID: BLK-TP-06
Nome: Calibração/validação do score residual com demanda revelada observada
Status: aprovado (QA 2026-07-02) — pendente fechamento manual (orquestrador Passo 6.0 + commit)
Tipo: modelagem (validação/calibração — READ-ONLY sobre o M1)
Criticidade: alta
Esteira: Block Orchestrator → Planner → [REVISÃO HUMANA — modelagem] → Builder → QA
Skill atual: QA (próxima)
Próxima Skill: QA

## Resultado do Builder (2026-07-02)
- VEREDITO = **GO (âncora R²)**: R²_oof_log=+0,3119 IC95 [+0,2977,+0,3250]; rho_oof=+0,4615 IC95 [+0,4477,+0,4739]; n_join=16.411; cobertura ~1,06%; método kfold_5x5; alpha=100.
- Subconjunto: 231 passed / 0 failed / 0 skipped; import streamlit_app ok; isolamento ast limpo; ruff+mypy limpos nos 2 novos.
- mtime dos artefatos M1 inalterado (3 presentes idênticos antes/depois; dashboard.parquet ausente no checkout); nenhum parquet/mercado modificado no git.
- Novos: src/motor_expansao/demanda_revelada/calibracao_residual.py, tests/unit/demanda_revelada/test_calibracao_residual.py, data/analysis/calibracao_residual_demanda.md (gitignored).
- FOLLOW-UP (NÃO aplicado): recalibrar a fórmula do residual = BLK-TP-07 com DEC + gate; 03_Competidores.xlsx = BLK-TP-08.
Gate humano: APROVADO pelo usuário em 2026-07-02 — R4=(A) adiar 03_Competidores p/ BLK-TP-08; alvo=log1p(membros); GO/NO-GO R²-âncora+rho-suporte; membros=alvo único

## Objetivo
Medir out-of-fold quanto o `score_oportunidade_residual` (camada paralela de mercado/residual) prevê a
demanda OBSERVADA da camada Demanda Revelada (NAO_ABRA/ — HTML + planilhas), quantificando de forma
honesta (DEC-008) o +0,52 exploratório da DEC-012 e propondo (sem aplicar em produção) como calibrar
melhor. READ-ONLY sobre o M1.

## Contexto adicional do usuário (2026-07-02) — INCORPORAR
- A demanda observada da pasta NAO_ABRA NÃO foi usada para modelar o score residual, e NÃO tínhamos a
  localização dessas academias. Se o score já captura parte da demanda delas, "algo funciona" → entender
  como calibrar melhor e adaptar a modelagem para ganhar precisão.
- Considerar TAMBÉM academias menores (não-rede) que mapeamos via scrapers WellHub e TotalPass.
- CUIDADO com os DOIS tipos de "alunos" e "ativos" nos dados da pasta (distinguir/documentar — risco de
  confundir métricas).
- A pasta tem NÃO só o HTML, mas também PLANILHAS com dados importantes extraídos de lá — inventariar.

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: opus (override +1: inventário/forense anti-PII delicado do NAO_ABRA — 2 tipos de alunos/ativos + planilhas além do HTML)
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Branch do ciclo
ciclo/BLK-TP-06 (criada a partir de main @ HEAD a2bd10e).

## Paths do ciclo (commitar só estes por path)
- src/motor_expansao/demanda_revelada/calibracao_residual.py (NOVO)
- tests/unit/demanda_revelada/test_calibracao_residual.py (NOVO)
- data/analysis/calibracao_residual_demanda.md (NOVO, gitignored — via __main__, não teste)
- tasks/backlog.md (bloco BLK-TP-06), tasks/current_task.md, tasks/completed.md
- context/handoff.md, context/handoff/

## Guardrails
- §5 (READ-ONLY M1): zero recálculo de score_priorizacao/hex_score_estrutural/pesos/carteira/plano/artefatos oficiais.
- RECALIBRAR a FÓRMULA do `score_oportunidade_residual` em produção = FOLLOW-UP com gate próprio; este bloco VALIDA + PROPÕE.
- DEC-008: LOO/k-fold vs baseline da média; R² in-sample BANIDO; IC95 bootstrap seed fixa; intervalos + flag de extrapolação.
- DEC-009: demanda OBSERVADA como alvo/insumo; PROIBIDO usar como preditor geográfico de magnitude.
- DEC-012 (anti-PII): consumir só camada agregada; zero PII em artefato/log/teste; fonte real em NAO_ABRA/ (gitignored); fixtures sintéticas.
