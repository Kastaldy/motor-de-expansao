# Current Task

## Bloco atual

ID: BLK-FIX-01
Nome: Corrigir clipping de score_expansao_hibrido e validação com tolerância float
Status: APROVADO — ciclo fechado (housekeeping --check verde + commit por path); aguardando merge humano
Tipo: bug
Criticidade: Alta (FIXADA pelo Planner, 2026-05-30) — SEM DEC, SEM regeneração de Parquet.
  Alternativa escolhida: (iii) remover `score_expansao_hibrido` da checagem de faixa [0,100] no
  validador read-only (`schemas.py`), validando-o só como numérico/não-nulo (chave de ordenação
  lexicográfica, não score [0,100]), + teste que documenta o teto técnico ~100.001. NÃO altera
  fórmula, pesos, `LOCAL_BONUS_DIVISOR`, semântica do desempate nem qualquer artefato. Solução
  só-validador ⇒ Alta com gate humano antes do Builder; não dispara Crítica+DEC.
Esteira: Block Orchestrator → Planner → [APROVAÇÃO HUMANA] → Builder → QA
Skill atual: Fechamento (orquestrador) — concluído
Próxima Skill: Merge humano da branch ciclo/BLK-FIX-01
dry_run: false

## Objetivo
O validador de schema do BLK-OPS-04 rejeita `score_expansao_hibrido` porque o cálculo híbrido
pode produzir ~100.001 (sem clip), estourando a faixa estrita [0,100]. Resolver de forma que
o dashboard carregue os Parquets reais e o OPS-04 possa ir a produção, SEM quebrar o desenho do
score (chave de ordenação lexicográfica) nem mutar o score M1 oficial.

## Achados do orquestrador (pré-Block Orchestrator)
- `src/motor_expansao/pipelines/modelo_hibrido_expansao.py:115` `calcular_score_expansao_hibrido`
  retorna `score_priorizacao + (score_setor_2022_calibrado / LOCAL_BONUS_DIVISOR)`, SEM clip.
  `LOCAL_BONUS_DIVISOR = 100_000.0` (linha 55) → bônus ≤ ~0.001 → hibrido ≤ ~100.001.
- `src/motor_expansao/dashboard/schemas.py` `_SCORE_RANGE_OPTIONAL` inclui `score_expansao_hibrido`
  e valida [0,100] estrito (sem tolerância) — daí a rejeição. (Criado no BLK-OPS-04, já em main.)
- TENSÃO DE DESIGN (delimitar, não decidir aqui): o docstring define `score_expansao_hibrido` como
  CHAVE DE ORDENAÇÃO LEXICOGRÁFICA (M1 primário + micro-desempate censitário), não score limitado a
  [0,100]. Clipar a 100 zeraria o desempate dos hexes com `score_priorizacao`≈100. Alternativas a
  avaliar pelo Planner: (i) clip na fórmula; (ii) só tolerância 1e-2 no validador; (iii) remover
  `score_expansao_hibrido` da checagem [0,100] (tratar como chave não-limitada); ou combinação.
- `score_dominio_hibrido` (Bloco 17) é DIFERENTE e já é `clip(...,0,100)` — não confundir.

## Paths prováveis do ciclo (commit por path — NUNCA git add -A; CLAUDE.md NÃO entra)
- src/motor_expansao/dashboard/schemas.py
- src/motor_expansao/pipelines/modelo_hibrido_expansao.py  (se o fix tocar a fórmula)
- tests/unit/test_schema_validation.py · (eventual) teste do cálculo híbrido
- tasks/current_task.md · tasks/backlog.md · tasks/completed.md
- context/handoff.md · context/handoff/
- (Parquets regenerados em data/outputs/ são artefatos gerados — não versionados; não commitar.)

## Contexto de abertura
- Branch isolado: `ciclo/BLK-FIX-01`, criado a partir de `main` JÁ COM o BLK-OPS-04 mergeado
  (merge feito pelo humano, commit 111471e). `schemas.py` presente.
- Worktree pré-sujo: edições não relacionadas em `CLAUDE.md` (nova regra de criticidade, decisão do
  usuário — NÃO commitar neste ciclo) e `tasks/backlog.md` (adiciona blocos BLK-FIX-01/02 — necessário
  para o housekeeping; entra no commit por path). Commitar SÓ por path; nunca `git add -A`.
- Gate humano obrigatório após o Planner (Alta e Crítica exigem aprovação). Builder só roda após
  "aprovar" explícito do usuário no handoff.
- Guardrail: NÃO alterar `score_priorizacao`/`hex_score_estrutural`/pesos M1/artefatos M1 oficiais.
  O fix mexe na camada HÍBRIDA (paralela) e no validador read-only.
