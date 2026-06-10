# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-SAM-01 — Redefinir gate do SAM: Faixa M1 ∈ {baixa,media,alta,prioridade_maxima} AND população ≥ 5000**

Substituição cirúrgica do gate do SAM em `calcular_colunas_mercado.py`:
- REMOVE: `top_municipio` (critério de priorização M1 que excluía municípios fora do top-20%);
  REMOVE: `tam_populacao_hex > 0` (piso trivial da pop rateada por hex).
- MANTÉM: `flag_viavel` (guarda de renda + faixa + população ≥ 1); `~flag_canibalizacao_ultra_1km`.
- ADICIONA: `faixa_oportunidade.isin({baixa,media,alta,prioridade_maxima})` (leitura somente do M1);
  `populacao_corte_hex >= 5000` (régua operacional da camada de dashboard, a ser disponibilizada no pipeline).

Gate efetivo resultante:
```
flag_sam = flag_viavel
           & faixa_oportunidade.isin({"baixa","media","alta","prioridade_maxima"})
           & (populacao_corte_hex >= 5000)
           & ~flag_canibalizacao_ultra_1km
```

A sub-decisão `flag_viavel` é inofensiva e preserva o filtro de renda (`renda_target_proxy >= RENDA_MIN`).
A verificação de faixa em `flag_viavel` (já exclui `descartado`/`inviavel`) torna a segunda condição
de faixa semanticamente redundante, mas explícita e auditável — manter ambas é mais seguro.

## Objetivo
Corrigir a semântica do SAM na camada paralela de mercado/residual para que reflita
hexes com Faixa M1 elegível (≠ descartado/inviavel) **e** população ≥ 5000 via régua operacional
`populacao_corte_hex`, eliminando dependência de `top_municipio` e do piso trivial de `tam_populacao_hex`.

## Escopo permitido
- Modificar `flag_sam` / `flag_sam_fitness` / `sam_fitness_potencial` em `src/motor_expansao/pipelines/calcular_colunas_mercado.py` (seção 5.4, linhas 267–284).
- Implementar lógica de `populacao_corte_hex` equivalente à `derive_pop_cut_columns` do dashboard dentro de `calcular_colunas_mercado.py` (sem duplicação divergente — ver Risco 1).
- Adicionar `faixa_oportunidade` a `SOURCE_REQUIRED_COLS` se ausente (verificar; campo já flui do enriquecimento M1 via parquet de entrada).
- Parametrizar o limiar 5000 via constante (ex.: `POP_MIN_SAM_GATE = 5_000`) em `calcular_colunas_mercado.py` ou `config.py`; escolha do Planner.
- Atualizar testes em `tests/integration/test_modelo_mercado_hexagonos.py` (incluindo repro do hex `87a91b18dffffff` de Santo Amaro da Imperatriz/SC).
- Registrar a nova DEC no `CLAUDE.md §8`.
- Atualizar `tasks/current_task.md`, `context/handoff.md` e snapshot `context/handoff/`.
- Parquets paralelos de staging: se o Planner decidir regenerar, seguir a ordem canônica híbrido → mercado → `calcular_colunas_mercado` → carteira → plano → domínio → residual → `fase1_bi_exports`.

## Fora de escopo
- `score_priorizacao`, `hex_score_estrutural`, pesos do score, `faixa_oportunidade` (campo é LIDO, não recalculado — DEC-001 vigente).
- Artefatos oficiais do M1: `brasil_estrutural.parquet`, `brasil_priorizados.parquet`, `hexagonos_brasil_oportunidades.parquet`, `hexagonos_brasil_dashboard.parquet`, `top_oportunidades_resumo.csv`, `resumo_por_uf.csv`.
- `hex_enrichment.py`, `base_h3_brasil.py`, `scoring.py`, `fase1_bi_exports.py` (camada M1 — READ-ONLY).
- Alterar a lógica de `derive_pop_cut_columns` em `data.py` (fonte canônica do dashboard — não mexer).
- Alterar `POP_MIN_ACIONAVEL` em `dashboard/constants.py` (constante do dashboard — não mexer).
- Alterar qualquer parâmetro de `config.py` §3 (H3_RESOLUTION, DIST_MIN_ULTRA_KM, RENDA_MIN, etc.).
- Inventar população onde não há base auditável.
- Qualquer pipeline de API (`src/motor_expansao/api/`).

## Arquivos que devem ser lidos

### Fontes canônicas obrigatórias
- `CLAUDE.md` — completo (§1, §2, §3, §4, §5, §8)
- `tasks/current_task.md`
- `tasks/backlog.md` — bloco BLK-SAM-01 completo (perto da linha 316)
- `docs/modelo_mercado_hexagonos.md` — contrato técnico de colunas e cálculos de mercado/residual

### Código principal a modificar
- `src/motor_expansao/pipelines/calcular_colunas_mercado.py` — gate do SAM (seção 5.4, linhas 267–284); `SOURCE_REQUIRED_COLS` (linhas 35–51); `calcular()` completo para entender o contexto de `mask_hex_censo`

### Código a entender (para replicar lógica sem divergência)
- `src/motor_expansao/dashboard/data.py` — função `derive_pop_cut_columns` (linhas 564–609) e `build_pop_cut_lookup` (linhas 612–617); importação de `POP_MIN_ACIONAVEL`
- `src/motor_expansao/dashboard/constants.py` — constante `POP_MIN_ACIONAVEL = 5_000` (linha 118)

### Testes a atualizar
- `tests/integration/test_modelo_mercado_hexagonos.py` — testes de `flag_sam`, `flag_sam_fitness`, `sam_fitness_potencial` (linhas 52–56, 181–191, 233, 333)

### Referência para entender `faixa_oportunidade` no pipeline de entrada
- `src/motor_expansao/pipelines/m1/hex_enrichment.py` — `_definir_faixa_oportunidade` (linha 503); `flag_viavel` (linha 651)

## Arquivos que podem ser alterados
- `src/motor_expansao/pipelines/calcular_colunas_mercado.py` — **primário**: gate SAM (seção 5.4) + `SOURCE_REQUIRED_COLS` (adicionar `faixa_oportunidade` se necessário)
- `tests/integration/test_modelo_mercado_hexagonos.py` — novos testes do gate + repro do hex de referência
- `CLAUDE.md` — adicionar nova DEC em §8 (decisões de produto do BLK-SAM-01 já aprovadas por Felipe)
- `tasks/current_task.md`, `context/handoff.md`, `context/handoff/<snapshot>.md`
- `config.py` ou constante local em `calcular_colunas_mercado.py` — parametrizar limiar 5000 (a critério do Planner)

## Critérios de aceite

1. **Gate correto implementado:** `flag_sam = flag_viavel & faixa_oportunidade.isin({"baixa","media","alta","prioridade_maxima"}) & (populacao_corte_hex >= 5000) & ~flag_canibalizacao_ultra_1km`. Verificável via assert/teste.

2. **Repro de referência verificado:**
   - Hex `87a91b18dffffff` (Santo Amaro da Imperatriz/SC): `pop_corte ≈ 35,4` < 5000 → `flag_sam=False` → `sam_fitness_potencial=0`. Teste explícito ou documentação de evidência nos critérios de aceite do PR.
   - Pelo menos 1 hex que **passa a calcular SAM** sob a nova regra (ex.: hex com boa faixa + `pop_corte >= 5000` mas fora do `top_municipio` antigo).

3. **`populacao_corte_hex` equivalente ao dashboard:** lógica idêntica a `derive_pop_cut_columns` (setor 2022 quando granular via `mask_hex_censo`, fallback `populacao_proxy`). Diferença de `confianca_geografica` vs `mask_hex_censo` é intencional e documentada.

4. **M1 intocado:** `score_priorizacao`, `hex_score_estrutural`, pesos, artefatos oficiais inalterados. Verificado por scope check (`git diff` não toca `pipelines/m1/`, `scoring.py`, `config.py`, artefatos).

5. **Suíte verde:** `pytest -q` (ou `-p no:xdist` em ambiente Windows/Python 3.14) com 0 failed, incluindo testes novos do gate e regressão `test_modelo_mercado_hexagonos.py`.

6. **ruff + mypy limpos** em `src/` e `tests/`.

7. **DEC registrada:** nova entrada em `CLAUDE.md §8` com as 3 decisões de produto aprovadas por Felipe (2026-06-09).

## Criticidade classificada
**Alta**

Justificativa: altera o valor numérico do SAM (`sam_fitness_potencial`) e o escopo de hexes elegíveis na camada PARALELA de mercado/residual (não M1 oficial). Redefine semântica de um campo ativo no dashboard. Não altera `score_priorizacao` nem artefatos M1. A Faixa M1 é LIDA (DEC-001 vigente), não recalculada. Decisões de produto TODAS resolvidas por Felipe (2026-06-09) — o gate humano obrigatório da esteira Alta JÁ foi satisfeito; o Builder pode implementar direto após o Planner detalhar o plano técnico.

> **NOTA IMPORTANTE:** as 3 decisões de produto deste bloco foram explicitamente resolvidas por Felipe em 2026-06-09 e registradas no backlog. A revisão humana pendente é de PLANO TÉCNICO (como implementar), não de produto (o que implementar). O orquestrador deve apresentar o handoff do Planner ao usuário para aprovação técnica antes de disparar o Builder.

## Esteira recomendada
Block Orchestrator → Planner → [REVISÃO HUMANA do plano técnico] → Builder → QA

## Riscos identificados

### Risco 1 — Compartilhamento da lógica de `derive_pop_cut_columns` sem duplicação divergente (PRINCIPAL)
`derive_pop_cut_columns` em `data.py` usa `confianca_geografica == "granular"` para preferir `pop_total_setor_2022`. O pipeline de mercado não tem a coluna `confianca_geografica`, mas JÁ computa `mask_hex_censo = flag_censo_elegivel & pop_total_setor_2022.notna()` — que é semanticamente equivalente. O Builder deve replicar a lógica usando `mask_hex_censo` existente (sem importar `derive_pop_cut_columns` do dashboard, que geraria dependência circular) e documentar a equivalência. Alternativa: mover a função para um módulo compartilhado (ex.: `src/motor_expansao/pipelines/pop_utils.py`) — decisão técnica do Planner.

### Risco 2 — `faixa_oportunidade` em `SOURCE_REQUIRED_COLS`
O campo `faixa_oportunidade` flui do enriquecimento M1 e está presente no parquet de entrada `hexagonos_mercado_mapeado.parquet` (confirmado via grep em `modelo_hibrido_expansao.py`). Porém NÃO está em `SOURCE_REQUIRED_COLS` (linhas 35–51 de `calcular_colunas_mercado.py`). O Planner deve decidir: (a) adicionar a `SOURCE_REQUIRED_COLS` (mais seguro, quebra cedo se campo sumir); ou (b) referenciar diretamente com `.fillna("descartado")` como fallback seguro. Ambas as opções são válidas; (a) é recomendada.

### Risco 3 — Impacto no volume do SAM
A remoção de `top_municipio` e adição de `pop_corte >= 5000` têm efeitos opostos: a remoção do `top_municipio` EXPANDE o SAM (municípios fora do top-20% passam a ser elegíveis); o corte de 5000 REDUZ o SAM (hexes de baixa pop rateada, mediana nacional ≈ 5 hab, são eliminados). O Planner deve incluir no plano uma validação quantitativa básica (ex.: imprimir `flag_sam.sum()` antes/depois) para garantir que o resultado é coerente — nem explosão nem colapso. O backlog documenta que ~14% dos hexes SP com SAM>0 passam pelo corte de 5000 em `populacao_corte_hex`.

### Risco 4 — Regeneração de parquets paralelos
`calcular_colunas_mercado.py` lê e escreve `hexagonos_mercado_mapeado.parquet` (Bloco 5). Os parquets downstream (carteira, plano, domínio, residual, `fase1_bi_exports`) dependem desse parquet. Se o Planner decidir que a regeneração é necessária para os testes de integração (não apenas testes unitários com fixtures), deve incluir a ordem canônica: híbrido → mercado → calcular_colunas_mercado → carteira → plano → domínio → residual → fase1_bi_exports. ZERO escrita em artefatos M1 oficiais.

### Risco 5 — Testes existentes podem falhar
Os testes atuais de `flag_sam` em `test_modelo_mercado_hexagonos.py` (linhas 181, 191, 233, 333) usam fixtures que incluem `top_municipio=True/False`. Com a mudança do gate, fixtures que antes geravam `flag_sam=True` via `top_municipio` precisarão ser atualizadas para incluir `faixa_oportunidade` elegível E `populacao_corte_hex >= 5000`. O Builder deve auditar cada fixture e atualizar consistentemente.

## Guardrails ativos
- `score_priorizacao`, `hex_score_estrutural`, pesos (`renda=0.40`/`pop=0.60`) e artefatos oficiais do M1 são READ-ONLY (DEC-001 vigente; CLAUDE.md §5 guardrail permanente).
- `faixa_oportunidade` é campo de leitura derivado do M1 — o pipeline de mercado consome, não recalcula.
- `derive_pop_cut_columns` em `data.py` é fonte canônica do dashboard — não alterar; replicar equivalência no pipeline documentando a diferença de `confianca_geografica` vs `mask_hex_censo`.
- Staging sempre em Parquet; CSVs com `sep=";"` e `encoding="utf-8-sig"`.
- Toda mudança relevante entra com teste; nenhum PR deve subir com CI quebrado.
- NO-BYPASS: nenhum verde de QA via `--config /dev/null` ou mock do caminho crítico.
