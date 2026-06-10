# Current Task

## Bloco atual

ID: BLK-SAM-01
Nome: Redefinir condições de cálculo do SAM (Faixa M1 + população ≥ 5000)
Status: aprovado
Tipo: feature (redefine semântica do gate do SAM; camada PARALELA de mercado/residual)
Criticidade: alta
Esteira: Block Orchestrator → Planner → [REVISÃO HUMANA do PLANO TÉCNICO ✓ aprovado 2026-06-10] → Builder ✓ → QA ✓ APROVADO
Skill atual: QA/Quality Analyzer (concluído — APROVADO)
Próxima Skill: Fechamento manual (orquestrador: housekeeping BLK-SAM-01 + regeneração operacional de parquets pós-merge)
dry_run: false

## Status Builder (2026-06-10)
- Plano técnico APROVADO por Felipe/usuário em 2026-06-10; Builder executou Passos 1–7 do handoff.
- Novo módulo `pipelines/pop_corte.py` (helper puro, fonte única); `dashboard/data.py` delega; gate do SAM
  reescrito em `calcular_colunas_mercado.py` (DEC-006); docs + DEC-006 no CLAUDE.md §8; 3 testes novos.
- Validações (serial, host Win/Py3.14): mercado 20 passed/4 skipped, streamlit 179 passed, import ok,
  ruff limpo, mypy limpo. Volume verificado read-only no parquet real: flag_sam 196.715 → 27.996.
- Regeneração dos parquets paralelos: pendência OPERACIONAL pós-merge (fora do fechamento — Passo 7/DEC-006).

## Plano técnico entregue (Planner, 2026-06-10)
- Handoff completo em context/handoff.md (+ snapshot context/handoff/20260610-123852-planner.md).
- ACHADO CRÍTICO: `mask_hex_censo` ≠ `granular` do dashboard. O Risco 1 do BO estava equivocado;
  usar `mask_hex_censo` daria pop_corte=27272 no repro 87a91b18dffffff (SAM>0, ERRADO). A régua canônica
  é o `granular` real (qualidade_join_uf A/B + censo signal) → pop_corte=35.4 → SAM=0 (CORRETO).
- Decisão técnica: extrair helper compartilhado `src/motor_expansao/pipelines/pop_corte.py` (fonte única),
  consumido por dashboard/data.py (lógica preservada) e calcular_colunas_mercado.py. Limiar em
  POP_MIN_SAM_GATE=5_000 (constante local do pipeline, não §3). `flag_sam_fitness = flag_sam` (piso removido).
  Regeneração de parquets = passo operacional pós-merge, fora do fechamento de testes.
- Validação de volume verificada: flag_sam True 196.715 → 27.996. DEC-006 com texto pronto no handoff.
- PENDENTE: aprovação humana do PLANO TÉCNICO antes do Builder (criticidade Alta).

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: sonnet
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Objetivo
Gatear o SAM (`flag_sam`/`flag_sam_fitness`/`sam_fitness_potencial` em `calcular_colunas_mercado.py`) por
Faixa M1 ∈ {baixa, media, alta, prioridade_maxima} **e** população ≥ 5000 (via régua `populacao_corte_hex`/
`flag_pop_min_5k`, `POP_MIN_ACIONAVEL=5000`), mantendo `flag_viavel` e `~flag_canibalizacao_ultra_1km`;
substituindo o `top_municipio` e o piso `tam_populacao_hex > 0`. READ-ONLY sobre o M1.

## Branch do ciclo
ciclo/BLK-SAM-01 (a partir de main @ d13ca15)

## Worktree pré-sujo
(limpo no início; commitar SÓ paths do ciclo por path, nunca git add -A)

## Decisões de produto (TODAS resolvidas por Felipe 2026-06-09 — registrar como nova DEC no CLAUDE.md §8)
1. Gate = `flag_viavel & faixa∈{baixa,media,alta,prioridade_maxima} & (pop_corte ≥ 5000) & ~flag_canibalizacao_ultra_1km`
   (mantém flag_viavel + canibal; remove top_municipio + piso tam_populacao_hex>0).
2. Campo de população do corte = `populacao_corte_hex`/`flag_pop_min_5k` (régua do dashboard, `derive_pop_cut_columns`),
   NÃO `pop_hex_base`/`tam_populacao_hex`. Builder torna isso disponível em `calcular_colunas_mercado` sem duplicar lógica divergente.
3. Limiar inclusivo `≥ 5000`.

## Repro de referência (verificado 2026-06-09)
- hex `87a91b18dffffff` (Santo Amaro da Imperatriz/SC): hoje SAM≈7,28; pop_corte=35,4 → flag_pop_min_5k=False → SAM deve ir a 0.

## Fora de escopo (invioláveis)
- `score_priorizacao`/`hex_score_estrutural`/pesos/`faixa_oportunidade`/artefatos oficiais do M1 (DEC-001; Faixa M1 é LIDA, não recalculada)
- inventar população onde não há base auditável

## Paths prováveis do ciclo (a confirmar pelo Planner)
- src/motor_expansao/pipelines/calcular_colunas_mercado.py
- src/motor_expansao/dashboard/data.py (derive_pop_cut_columns — fonte da régua a compartilhar)
- config.py/constants.py (se parametrizar o limiar 5000)
- tests/integration/test_modelo_mercado_hexagonos.py
- parquets paralelos regenerados na ordem canônica (se necessário)
- CLAUDE.md §8 (nova DEC) + tasks/* + context/handoff*
