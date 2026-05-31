# Current Task

## Bloco atual

ID: BLK-SCORE-01
Nome: Dataset rotulado de validação (Ultra + Skyfit + Wellhub)
Status: APROVADO COM RESSALVAS no QA (pronto para fechamento)
Tipo: feature (análise / dataset de validação — read-only sobre M1)
Criticidade: Alta (LEITURA/ANÁLISE de score sem escrita em artefato M1 → revisão humana antes do Builder; ratificada com usuário em 2026-05-30)
Esteira: Block Orchestrator → Planner → [revisão humana] → Builder → QA
Skill atual: QA
Próxima Skill: Orquestrador (fechamento)
dry_run: false

## Veredito QA (2026-05-31)
APROVADO COM RESSALVAS. Pytest REAL: 21 passed no arquivo novo (Builder disse 23 — imprecisão a
corrigir); suite completa 591 passed, 1 skipped (bate; sem regressão — baseline real do branch é
570+21, não 532+23). `python -m analysis.build_validation_dataset` roda exit 0 e grava os 2
artefatos: dataset_validacao.parquet (441 linhas, 31 colunas, esquema/flags coerentes, cod_municipio
string, maturacao_indisponivel em todas) e relatorio_auditoria_rotulo.md (64 linhas, bem-formado,
sem PII, distingue medido/estimado). M1 READ-ONLY preservado (nenhum artefato/código M1 alterado;
data/analysis/ gitignored). housekeeping --check: exit 0 (bloco reconhecido). Desvios (a) caminho do
domínio em data/outputs/ e (b) EngCorpo 31/61 com 30 flagados: ambos aceitáveis/esperados.
Ressalva única bloqueante-zero: corrigir contagem de testes no handoff. Detalhes em
`context/handoff.md` (snapshot `context/handoff/20260531-010148-qa.md`).

## Objetivo
Montar a base que liga cada unidade existente (Ultra, Skyfit e Engenharia do Corpo) ao score do
hex/setor onde caiu (M1, censitário, residual, domínio) e ao desfecho observado (alunos
recorrentes; Wellhub/Totalpass como proxy de demanda independente). Gravar artefato de análise em
`data/analysis/dataset_validacao.parquet` (fora de `data/outputs/`). Insumo do backtest (BLK-SCORE-02).

## Guardrails do ciclo (do backlog)
- FORA DE ESCOPO: qualquer escrita em artefato M1 ou alteração de score. Apenas leitura e join.
- Dados sensíveis (Ultra/Skyfit/Wellhub) NÃO entram em logs/handoff em texto agregável a PII.
- Artefato vive em `data/analysis/`, nunca em `data/outputs/`. CSVs `sep=";"`, `utf-8-sig`; `Ultra.csv` permanece `latin-1`.
- Auditoria de qualidade de rótulo é critério de aceite, não opcional (outliers/nulos em `alunos_recorrentes`,
  nota sobre confiabilidade dos números de Skyfit: estimados vs. medidos).
- Flag de maturação presente; unidades imaturas marcadas, não descartadas silenciosamente.

## Paths prováveis do ciclo (commit por path — NUNCA git add -A; CLAUDE.md NÃO entra)
- analysis/build_validation_dataset.py (script de montagem — nome a confirmar pelo Planner)
- data/analysis/dataset_validacao.parquet (artefato gerado — avaliar se versiona; provavelmente gitignored)
- tests/unit/test_validation_dataset.py
- tasks/current_task.md · tasks/backlog.md · tasks/completed.md
- context/handoff.md · context/handoff/
- (Parquets de data/outputs/ são artefatos gerados — não versionar. Bases de data/validacao/ são gitignored.)

## Contexto de abertura
- Branch isolado: `ciclo/BLK-SCORE-01`, criado a partir de `main` (HEAD 38fd73e, BLK-FIX-02 já mergeado).
- Worktree pré-sujo (NÃO commitar neste ciclo): `M CLAUDE.md`. Commit SÓ por path; nunca `git add -A`.
- Criticidade Alta ⇒ gate de revisão humana APÓS o Planner, ANTES do Builder.

## Próximos passos (revisado pelo Planner em 2026-05-30)
Revisão pontual por instrução do gate humano: Skyfit TEM coordenadas em `concorrentes/`, logo
resolve `hex_id` (H3 res.7) via `latlng_to_h3`. Decisão #1 do checklist reescrita; #2–#7 inalteradas.
Achados de disco: coords primárias em `concorrentes/SkyFit_unidades_geocodificado.csv` (`sep=";"`,
utf-8-sig, 326 linhas, tem `ID SKY`+`NOMENCLATURA`, mas coords corrompidas por separador de milhar,
só 142 OK); fallback `concorrentes/unidades_skyfit.csv` (482 coords limpas, sem `ID SKY`, naming
diferente). Join desfecho↔coords por `ID SKY` = 326/326 (100%).

1. **Gate de revisão humana** (Alta; sem DEC pois read-only): usuário ratifica as 7 decisões do
   checklist em `context/handoff.md` (seção "Checklist de aprovação"); atenção à decisão #1 revisada.
2. Após aprovação: **Builder** implementa `analysis/build_validation_dataset.py` +
   `tests/unit/test_validation_dataset.py` conforme contratos e esquema do handoff
   (inclui merge Skyfit por `ID SKY`, reparo de coord e resolução de hex via `latlng_to_h3`).
3. QA: `pytest -q tests/unit/test_validation_dataset.py` verde e `pytest -q` sem regressão
   (baseline 532 passed, 1 skipped).

Plano técnico completo: `context/handoff.md`
(snapshot append-only mais recente: `context/handoff/20260530-234809-planner.md`).
