# Current Task

## Bloco atual

ID: BLK-SCORE-04
Nome: Backtest read-only multivariado das features mercado/censitárias vs. desfecho
Status: APROVADO (QA 2026-05-31 deu APROVADO COM RESSALVAS; ressalva MÉDIA endereçada pelo orquestrador antes do fechamento — cautela de endogeneidade adicionada ao relatório §4/§6, regenerado determinístico, suíte 624 passed/1 skipped). Ciclo fechado; commit por path; aguarda merge humano de `ciclo/BLK-SCORE-04`.
Tipo: feature (análise estatística / backtest — READ-ONLY sobre M1)
Criticidade: Alta (LEITURA/ANÁLISE de score sem escrita em artefato M1 → revisão humana antes do Builder; regra CLAUDE.md 2026-05-30)
Esteira: Block Orchestrator → Planner → [REVISÃO HUMANA] → Builder → QA
Skill atual: QA
Próxima Skill: (orquestrador fecha o ciclo)
dry_run: false

## REVISÃO HUMANA — APROVADO por Felipe Silva EM 2026-05-31
Plano do Planner aprovado como está (read-only sobre M1). Confirmadas as 4 decisões: (a) poda 19→12
features; (b) manter sentinela de distância; (c) âncora censitária vinda do dataset; (d) incluir OLS
diagnóstico restrito. Builder pode executar. Paths do ciclo (commit por path):
- analysis/feature_backtest_mercado.py (novo)
- tests/unit/test_feature_backtest_mercado.py (novo)
- data/analysis/relatorio_backtest_mercado.md (+figuras) — gitignored, NÃO versionar
- tasks/current_task.md · tasks/backlog.md · tasks/completed.md · context/handoff.md · context/handoff/

## Objetivo
Medir, read-only, o poder preditivo individual e conjunto das features reais das camadas
mercado/censitária (`hexagonos_mercado_mapeado.parquet`) contra `alunos_recorrentes`, para
fundamentar com evidência um eventual enriquecimento dos scores OPERACIONAIS — respondendo à
pergunta "outras variáveis além de pop/renda ajudam/são significativas?". SEM qualquer escrita
em fórmula/peso/artefato do M1.

## Contexto de abertura
- Branch isolado: `ciclo/BLK-SCORE-04`, criado a partir do HEAD da `ciclo/BLK-SCORE-03` (17536e9),
  que ainda AGUARDA merge humano. BLK-SCORE-04 depende de BLK-SCORE-03 (DEC-001) e da definição do
  bloco que vive nesse commit — daí a base. Stacked branch; git resolve ao mergear.
- Worktree limpo (BLK-SCORE-03 já commitado). Commit SÓ por path; nunca `git add -A`.
- Criticidade Alta ⇒ gate de REVISÃO humana após o Planner, antes do Builder (mais leve que o gate
  CRÍTICO do BLK-SCORE-03; ainda assim obrigatório).
- Insumo: `data/analysis/dataset_validacao.parquet` (BLK-SCORE-02, gitignored) +
  `data/staging/hexagonos_mercado_mapeado.parquet` (131 cols populadas). Reusar `analysis/score_backtest.py`.
- Saída só em `data/analysis/` (gitignored); sem PII; read-only sobre M1.
