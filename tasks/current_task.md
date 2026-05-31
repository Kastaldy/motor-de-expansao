# Current Task

## Bloco atual

ID: BLK-SCORE-03
Nome: Proposta de recalibração + DEC
Status: aprovado
Tipo: feature (recalibração de score M1 — CRÍTICA por definição)
Criticidade: crítica
Esteira: Block Orchestrator → Planner → [APROVAÇÃO HUMANA OBRIGATÓRIA] → Builder → QA
Skill atual: QA (Builder concluído)
Próxima Skill: QA
dry_run: false

## APROVADO POR Felipe Silva EM 2026-05-31
Decisão: NÃO recalibrar o M1 (manter renda=0.40 / pop=0.60; fórmula e artefatos M1 INALTERADOS).
Escopo aprovado de escrita (somente documentação/backlog — ZERO código/fórmula/artefato M1):
1. Registrar DEC-001 (manter) em CLAUDE.md.
2. Corrigir o enquadramento da §1 "Norte" do CLAUDE.md (M1 = camada executiva entre várias;
   censitário = camada primária operacional do dia a dia).
3. Adicionar BLK-SCORE-04 (backtest read-only multivariado mercado/censitário) ao backlog.
Observação: a string de aprovação para recalibração de M1 NÃO se aplica (nenhum peso/fórmula muda).

## Objetivo
Se o backtest (BLK-SCORE-02) justificar, propor recalibração dos pesos/fórmula do M1
(`score_priorizacao`) e, somente após DEC registrada e APROVAÇÃO HUMANA explícita,
implementá-la — preservando reprodutibilidade, staging e versionamento de proveniência.

## Contexto de abertura
- Branch isolado: `ciclo/BLK-SCORE-03`, criado a partir de `main` (HEAD 5acdbc0, BLK-SCORE-02 já mergeado).
- Worktree pré-sujo (NÃO commitar neste ciclo): `M CLAUDE.md`. Commit SÓ por path; nunca `git add -A`.
- Criticidade CRÍTICA ⇒ gate de aprovação humana APÓS o Planner, ANTES do Builder.
- Insumo analítico: `data/analysis/relatorio_backtest.md` (BLK-SCORE-02): M1 `score_priorizacao`
  rho≈0 (nulo, IC95% atravessa zero); pop (+0.095) marginalmente > renda (+0.067), ambos n.s.;
  censitário (+0.148) é o único positivo mas é camada paralela.
- DECISIONS.md NÃO existe → DEC vai em CLAUDE.md.
