# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-SAM-02 — Afrouxar o gate do SAM: apenas Faixa M1 elegível + população ≥ 5000 (remover flag_viavel e ~canibal)**

Mudança de semântica no gate do SAM em `calcular_colunas_mercado.py`:
- DE: `flag_sam = flag_viavel & faixa_oportunidade∈{baixa,media,alta,prioridade_maxima} & flag_pop_min_5k & ~flag_canibalizacao_ultra_1km`
- PARA: `flag_sam = faixa_oportunidade∈{baixa,media,alta,prioridade_maxima} & flag_pop_min_5k`

Reverte 2 sub-decisões da DEC-006 (BLK-SAM-01). Decisão de produto RESOLVIDA pelo usuário Vinicius
em 2026-06-10 com ciência do impacto (flag_sam 27.996 → 479.568, ×17). Requer nova DEC-007 no CLAUDE.md §8.

## Objetivo
Remover `flag_viavel` e `~flag_canibalizacao_ultra_1km` do gate do SAM, mantendo apenas
`faixa_oportunidade ∈ {baixa,media,alta,prioridade_maxima}` e `flag_pop_min_5k (≥5000)`, e
registrar a reversão da DEC-006 em nova DEC-007 com aprovador Vinicius (2026-06-10).

## Escopo permitido
- Alterar a linha de composição `df["flag_sam"]` em `calcular_colunas_mercado.py` (§5.4)
  de `flag_viavel & faixa_elegivel & flag_pop_ok & ~flag_canibal` para `faixa_elegivel & flag_pop_ok`
- Atualizar o comentário da linha (referência DEC-006 → DEC-007)
- `flag_sam_fitness` segue `== flag_sam` (sem mudança de semântica — já era assim)
- `sam_fitness_potencial` segue derivado de `flag_sam_fitness` (sem mudança)
- Atualizar os testes do gate em `tests/integration/test_modelo_mercado_hexagonos.py`:
  - `test_calcular_bloqueia_sam_quando_ha_canibalizacao`: hex h1 (canibal=True) AGORA passa; h2 segue passando
  - `test_flag_sam_e_conjuncao_dos_quatro_criterios`: parametrize reduzido de 4 para 2 critérios de reprova;
    remover os casos `flag_canibalizacao_ultra_1km=True` e `flag_viavel=False` como bloqueadores do SAM;
    mantendo apenas faixa inelegível e pop<5000 como False
  - `test_parquet_final_respeita_guardrails_do_piloto`: remover assert de `(flag_sam & flag_canibalizacao).sum()==0`
    (pois SAM agora pode coexistir com canibalizacao)
  - Adicionar repro ≥1 hex que passa a calcular por ter sido reprovado só em `flag_viavel` (renda<RENDA_MIN)
  - Adicionar repro ≥1 hex que passa a calcular por ter sido reprovado só em `~canibal`
- Registrar nova **DEC-007** em `CLAUDE.md §8` documentando a reversão e o aprovador (Vinicius, 2026-06-10)
- Atualizar `tasks/current_task.md`, `tasks/backlog.md`, `tasks/completed.md`, `context/handoff.md`

## Fora de escopo
- `score_priorizacao`, `hex_score_estrutural`, pesos (renda=0.40/pop=0.60), `faixa_oportunidade`: READ-ONLY (DEC-001)
- Artefatos oficiais do M1 (nenhum `.parquet` M1 é tocado): `brasil_estrutural.parquet`,
  `brasil_priorizados.parquet`, `hexagonos_brasil_oportunidades.parquet`, `hexagonos_brasil_dashboard.parquet`,
  `hexagonos_mapa_sample.parquet`
- `pop_corte.py` (helper `derive_confianca_geografica`/`derive_pop_cut_columns`/`has_censo_signal`): INTOCADO
- `flag_pop_min_5k` / `populacao_corte_hex` / `POP_MIN_SAM_GATE`: INTOCADOS (só consumidos)
- `flag_viavel` e `flag_canibalizacao_ultra_1km` continuam sendo DERIVADOS no pipeline (não são removidos
  como colunas — só saem do gate do `flag_sam`)
- `sam_granularidade` ainda usa `flag_canibal` como critério de rótulo (valor `"bloqueado_rede_ultra"`);
  isso NÃO é o gate do SAM — é label separado; manter intacto
- Regeneração de parquets paralelos: passo OPERACIONAL pós-merge (fora do fechamento do ciclo);
  o Builder NÃO regenera parquets — só garante que o código esteja correto
- APIs, PostGIS, Prefect, pipelines pesados: fora de escopo

## Arquivos que devem ser lidos
- `CLAUDE.md` (§1, §3, §4, §5, §8 — DEC-001, DEC-006, guardrails READ-ONLY M1)
- `tasks/current_task.md` (decisão de produto RESOLVIDA pelo Vinicius, paths do ciclo)
- `tasks/backlog.md` (BLK-SAM-02 completo: contexto, critérios de aceite, fora de escopo)
- `src/motor_expansao/pipelines/calcular_colunas_mercado.py` (gate §5.4: linha 298 `df["flag_sam"] = ...`; contexto §5.5 `flag_sam_fitness`, `sam_fitness_potencial`, `sam_granularidade`)
- `src/motor_expansao/pipelines/pop_corte.py` (helper consumido; INTOCADO neste bloco)
- `tests/integration/test_modelo_mercado_hexagonos.py` (testes do gate criados no BLK-SAM-01:
  `test_calcular_bloqueia_sam_quando_ha_canibalizacao` linha ~171;
  `test_flag_sam_e_conjuncao_dos_quatro_criterios` linha ~436 — parametrize de 4 critérios;
  `test_parquet_final_respeita_guardrails_do_piloto` linha ~456 — assert de ~canibal)
- `context/handoff.md` (este arquivo — para o Planner)

## Arquivos que podem ser alterados
- `src/motor_expansao/pipelines/calcular_colunas_mercado.py` — apenas linha 298 (`df["flag_sam"]`) + comentário
- `tests/integration/test_modelo_mercado_hexagonos.py` — atualizar/remover testes do BLK-SAM-01 que assertam
  os critérios `flag_viavel` e `~canibal` como bloqueadores; adicionar repros dos novos critérios
- `CLAUDE.md` — adicionar DEC-007 em §8
- `tasks/current_task.md`, `tasks/backlog.md`, `tasks/completed.md` (housekeeping do ciclo)
- `context/handoff.md` e `context/handoff/` (snapshots da esteira)

## Critérios de aceite
1. **Gate implementado:** `df["flag_sam"] = faixa_elegivel & flag_pop_ok` (sem `flag_viavel`, sem `~flag_canibal`);
   verificável por inspeção e por teste parametrizado.
2. **Repro flag_viavel:** ≥1 hex sintético que antes reprovava só por `flag_viavel=False` (renda < RENDA_MIN,
   faixa e pop ok, canibal=False) agora tem `flag_sam=True`. Documentar no teste com causa.
3. **Repro ~canibal:** ≥1 hex sintético que antes reprovava só por `flag_canibalizacao_ultra_1km=True`
   (faixa e pop ok, viavel=True) agora tem `flag_sam=True`. Documentar no teste com causa.
4. **Volume ≈ 479.568:** verificação read-only no parquet real (se disponível), ou confiar na medição
   pré-existente do backlog (dados reais 2026-06-10); mencionar no handoff do Builder.
5. **DEC-007 registrada** em `CLAUDE.md §8` com: data 2026-06-10, aprovador Vinicius, reversão explícita
   das 2 sub-decisões da DEC-006, impacto medido, status APROVADA.
6. **Suíte completa verde:** `pytest -q` passa (sem `-n auto` por incompatibilidade Windows/Python 3.14);
   `ruff check src/ tests/` limpo; `mypy src/motor_expansao/pipelines/calcular_colunas_mercado.py` limpo.
7. **READ-ONLY sobre M1 verificado:** `git diff --name-only` não toca `pipelines/m1/`, `scoring.py`,
   `config.py`, `dashboard/constants.py` nem artefato `.parquet` oficial.
8. **sam_granularidade intacto:** label `"bloqueado_rede_ultra"` permanece para hexes com `flag_canibal=True`
   (o rótulo ainda funciona; só o gate do SAM mudou).

## Criticidade classificada
**Alta**

Justificativa: altera a semântica do gate do SAM (camada PARALELA de mercado/residual, §4);
reverte 2 sub-decisões de uma DEC aprovada (DEC-006, Felipe, 2026-06-10); impacto ×17 no volume
de hexes SAM elegíveis (27.996 → 479.568). NÃO é M1 oficial — `score_priorizacao`,
`hex_score_estrutural` e artefatos M1 são READ-ONLY. Guardrails §2/§4/§5 do CLAUDE.md ativos.
Decisão de produto RESOLVIDA pelo usuário Vinicius em 2026-06-10 com ciência do impacto —
NÃO reabrir produto no Planner ou Builder.

## Esteira recomendada
Block Orchestrator → Planner → [REVISÃO HUMANA do plano técnico] → Builder → QA

## Riscos identificados

### Risco 1 — Testes do BLK-SAM-01 que assertam os 4 critérios precisam ser reescritos (BLOQUEADOR se não tratado)
- `test_calcular_bloqueia_sam_quando_ha_canibalizacao`: hex h1 (canibal=True) hoje asserta `flag_sam=False`;
  após o BLK-SAM-02 ele PASSA (canibal não bloqueia mais) — o teste vai falhar se não for atualizado.
- `test_flag_sam_e_conjuncao_dos_quatro_criterios`: os casos `flag_canibalizacao_ultra_1km=True` e
  `flag_viavel=False` hoje esperam `esperado_sam=False`; após o BLK-SAM-02 esses casos passam a True.
- `test_parquet_final_respeita_guardrails_do_piloto`: o assert
  `(flag_sam & flag_canibalizacao_ultra_1km).sum() == 0` falha após a regeneração (SAM coexiste com canibal).
  Para o parquet ainda não regenerado, o assert passa por acidente (valores antigos). O Builder DEVE
  remover ou adaptar esse assert.

### Risco 2 — `flag_sam_fitness` e `sam_granularidade` precisam de atenção semântica
- `flag_sam_fitness == flag_sam` era verdade no BLK-SAM-01 e continua sendo — sem mudança.
- `sam_granularidade` usa `flag_canibal` como critério de rótulo (`"bloqueado_rede_ultra"`); com o novo
  gate, um hex pode ter `sam_granularidade == "bloqueado_rede_ultra"` MAS `flag_sam == True` (paradoxo
  de label). Decisão: o `sam_granularidade` usa `np.select` com precedência
  `[flag_hibrid_elig, flag_sam, flag_canibal]` — para hexes que são `flag_sam=True` e `flag_canibal=True`,
  a linha `flag_sam` vence antes de `flag_canibal`, então o label será `"municipio_priorizado"` (não
  `"bloqueado_rede_ultra"`). Isso é correto semanticamente: se o SAM aceita o hex, ele não é bloqueado.
  O Planner deve confirmar essa semântica e o Builder deve cobrir com teste.

### Risco 3 — Regeneração de parquets paralelos fora do fechamento
- Os parquets em `data/staging/hexagonos_mercado_mapeado.parquet` e derivados continuam com
  `flag_sam` antigo até a regeneração operacional pós-merge.
- Enquanto não regenerados, o dashboard de produção continua servindo valores antigos.
- NÃO é risco ao M1 oficial. É pendência operacional documentada — o Builder deve deixar clara no handoff.
- Ordem canônica de regeneração: híbrido → mercado → `calcular_colunas_mercado` → carteira → plano →
  domínio → residual → `fase1_bi_exports` (+ enriquecido derivado do dashboard).

### Risco 4 — `sam_indice_operavel` e `sam_populacao_base` derivam de `flag_sam`; `oferta_efetiva_disponivel` deriva de `sam_fitness_potencial`
- Com 479.568 hexes SAM em vez de 27.996, os campos derivados expandem proporcionalmente.
- NÃO há risco de regressão no código — são `np.where(flag_sam, ...)` diretos.
- Risco é apenas de expectativas de volume nos testes do parquet real (skips já existem para pré-regen).

### Risco 5 — DEC-007 conflita explicitamente com DEC-006
- A DEC-007 reverte sub-decisões de Felipe (DEC-006). O handoff deve deixar explícito que:
  (a) Vinicius é o aprovador da DEC-007 com ciência do impacto;
  (b) o Planner NÃO deve questionar a decisão de produto — apenas planejar a implementação segura.

## Guardrails ativos
- `score_priorizacao`/`hex_score_estrutural`/pesos/`faixa_oportunidade`/artefatos oficiais M1: READ-ONLY (DEC-001; §3; §5).
- `pop_corte.py` INTOCADO (fonte única de verdade da régua pop; §4 "regeneração de parquets paralelos como passo operacional").
- Visualizações e camadas paralelas NÃO recalculam nem alteram o M1 sem aprovação explícita (§5 guardrail permanente).
- Não expandir escopo para BLK-API-02 nem qualquer outro bloco.
- Commitar apenas paths do ciclo; nunca `git add -A`.
- Decisão de produto JÁ RESOLVIDA pelo usuário Vinicius (2026-06-10): NÃO reabrir.
