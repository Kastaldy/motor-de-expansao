# Current Task

## Bloco atual

ID: BLK-SAM-02
Nome: Afrouxar o gate do SAM — apenas Faixa M1 elegível + população ≥ 5000 (remover flag_viavel e ~canibal)
Status: aprovado (QA 2026-06-10)
Tipo: feature (redefine semântica do gate do SAM; camada PARALELA de mercado/residual; reverte DEC-006)
Criticidade: alta
Esteira: Block Orchestrator → Planner → [REVISÃO HUMANA do plano técnico] → Builder → QA
Skill atual: QA (veredito APROVADO)
Próxima Skill: Fechamento manual (housekeeping Passo 6.0 + commit por path)
dry_run: false

## Tiering de modelo (Passo 4) — Alta
- Block Orchestrator: sonnet
- Planner: opus
- Builder: opus
- QA: opus 4.8 (sempre)

## Objetivo
Mudar o gate do SAM em `calcular_colunas_mercado.py` de
`flag_viavel & faixa_oportunidade∈{baixa,media,alta,prioridade_maxima} & flag_pop_min_5k & ~flag_canibalizacao_ultra_1km`
para `faixa_oportunidade∈{baixa,media,alta,prioridade_maxima} & flag_pop_min_5k` (remover flag_viavel e ~canibal).
READ-ONLY sobre o M1.

## Branch do ciclo
ciclo/BLK-SAM-02 (a partir de main @ 5bb790c)

## Decisão de produto (RESOLVIDA pelo usuário Vinicius 2026-06-10, com ciência do impacto — registrar como DEC-007)
- Remover `flag_viavel` (dropa o filtro de renda renda_target_proxy ≥ RENDA_MIN e o guard pop≥1).
- Remover `~flag_canibalizacao_ultra_1km` (SAM passa a incluir áreas Ultra<1km).
- Reverte 2 sub-decisões da DEC-006 (onde Felipe manteve ambos de propósito).
- Impacto medido (dados reais 2026-06-10): flag_sam 27.996 → 479.568 (+451.572 ≈ ×17;
  ~451.496 por dropar flag_viavel/renda, 76 por dropar ~canibal).

## Fora de escopo (invioláveis)
- score_priorizacao/hex_score_estrutural/pesos/faixa_oportunidade/artefatos oficiais do M1 (DEC-001; Faixa M1 é LIDA)
- régua populacao_corte_hex/flag_pop_min_5k e helper pop_corte.py (mantidos intactos; só consumidos)

## Paths do ciclo (confirmados pelo Block Orchestrator)
- src/motor_expansao/pipelines/calcular_colunas_mercado.py (gate §5.4 linha 298)
- tests/integration/test_modelo_mercado_hexagonos.py
- CLAUDE.md §8 (DEC-007)
- tasks/backlog.md + tasks/current_task.md + tasks/completed.md
- context/handoff.md + context/handoff/
- (regeneração de parquets paralelos = passo operacional pós-merge; Builder NÃO regenera)
