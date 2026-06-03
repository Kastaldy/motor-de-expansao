# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-FIX-06-C — Orla não renderiza no dashboard (display/render; dados já corretos)**

Bug de DISPLAY/RENDER: os hexes da orla (Mongaguá `87a810998ffffff`, PG-Mongaguá
`87a810d4cffffff`) estão presentes nos parquets servidos em produção (verificado via
docker exec, 2026-06-03). O problema é que o caminho de render os oculta ou descarta.
NÃO é falta de dados.

## Objetivo
Fazer os hexes da orla aparecerem visivelmente no mapa do dashboard (modo M1 e,
idealmente, modos operacionais) corrigindo exclusivamente o caminho de render/display,
sem mexer em M1/score/artefatos/dados.

## Escopo permitido
- `src/motor_expansao/dashboard/components.py` — render/cor/cap/legenda dos builders de mapa
- `src/motor_expansao/dashboard/constants.py` — constantes de display (POP_MIN_ACIONAVEL, MAP_POINT_LIMIT_*)
- `src/motor_expansao/dashboard/data.py` — derive_pop_cut_columns (lógica de flag_pop_min_5k)
- `src/motor_expansao/dashboard/pages.py` — chamadas aos builders, legenda, texto explicativo
- `src/motor_expansao/dashboard/utils.py` — helpers visuais se aplicável
- Testes correspondentes em `tests/`

## Fora de escopo
- `src/motor_expansao/pipelines/m1/base_h3_brasil.py` e qualquer outro pipeline M1
- Artefatos oficiais do M1 (brasil_estrutural.parquet, brasil_priorizados.parquet, etc.)
- Regenerar parquets ou redeploy de dados ao VPS (dados já corretos)
- Mudar pesos/fórmula de score_priorizacao, hex_score_estrutural ou qualquer score
- `config.py` (parâmetros canônicos M1 — não tocar)

## Arquivos que devem ser lidos
- `src/motor_expansao/dashboard/components.py` — inteiro (foco: linha 1107 `_DISCARDED_FILL`; linha 1111 `_apply_pop_cut_colors`; linhas 1322–1414 `build_map_figure` M1; linhas 1563–1665 `build_hybrid_map_figure`; linhas 1737–1793 `build_residual_heatmap_figure`; linha 1235 `_downsample_map_index`)
- `src/motor_expansao/dashboard/constants.py` — foco: linha 98 `MAP_POINT_LIMIT`; linha 103 `MAP_POINT_LIMIT_LARGE`; linha 118 `POP_MIN_ACIONAVEL`; linhas 331–364 `COLOR_MODES`; linha 196 `MAP_SORT_COLUMNS`
- `src/motor_expansao/dashboard/data.py` — foco: linhas 564–609 `derive_pop_cut_columns`
- `src/motor_expansao/dashboard/pages.py` — foco: linhas 1269–1279 e 1656–1666 (filtro hard `view = view[view["flag_pop_min_5k"]]`)
- `tasks/backlog.md` — bloco BLK-FIX-06-C (linhas 44–101) para hipóteses completas
- `CLAUDE.md` — §2 (guardrail criticidade score), §3 (parâmetros canônicos), §5 (DEC-002/DEC-003)

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/components.py`
- `src/motor_expansao/dashboard/constants.py`
- `src/motor_expansao/dashboard/data.py`
- `src/motor_expansao/dashboard/pages.py`
- `src/motor_expansao/dashboard/utils.py` (se necessário)
- Arquivos de teste em `tests/` correspondentes aos módulos acima
- `CLAUDE.md` §5 (nota de fechamento de ciclo, apenas ao concluir)
- `tasks/current_task.md` (tracking de ciclo)

## Critérios de aceite
1. Hexes da orla de Praia Grande/Mongaguá aparecem visivelmente no mapa do dashboard no modo M1 após `Ctrl+Shift+R` (não cinza translúcido, não ausentes).
2. Modos operacionais (Híbrido, Censitário, Residual) também mostram hexes costeiros existentes, mesmo que com NaN em score censitário (renderizar com fallback de cor em vez de sumir).
3. `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo e artefatos oficiais M1 inalterados (nenhum recálculo de score).
4. Suite de testes verde: `pytest -q` sem novos falhos (baseline atual: 532 passed, 1 skipped).
5. `import streamlit_app` (ou equivalente de smoke test) passa sem erro.
6. Sem regressão de performance (builders não carregam datasets maiores desnecessariamente).

## Criticidade classificada
**Alta**

Justificativa: o fix lê colunas de score (`score_priorizacao` no sort/cap via `MAP_SORT_COLUMNS`
em `build_map_figure`; colunas de score nos builders híbrido/residual). Conforme CLAUDE.md §2:
"LEITURA/ANÁLISE de score sem escrita em artefato M1 → Alta (revisão humana antes do Builder)".
NÃO há escrita em artefato M1 — permanece Alta, não sobe para Crítica. Gate humano obrigatório
antes do Builder.

ALERTA EXPLÍCITO: qualquer mudança que altere `score_priorizacao`, `hex_score_estrutural`,
carteira, plano ou parquets oficiais VIRA CRÍTICA imediatamente e deve parar para aprovação + DEC.
Esse risco é baixo dado o escopo (só display), mas o Planner e Builder devem verificar
explicitamente que nenhuma escrita em artefato M1 ocorre.

## Esteira recomendada
Block Orchestrator (concluído) → **Planner** → [revisão humana / gate] → Builder → QA

Modelos sugeridos por papel (conforme BLK-ORQ-01):
- Planner: Opus 4.8
- Builder: Sonnet (criticidade Alta; Opus se ambiguidade persistir pós-Planner)
- QA: Opus 4.8 (sempre)

## Riscos identificados
1. **Re-misdiagnóstico data-vs-render**: risco de um sub-agente investigar os dados em vez
   do render. GUARDRAIL: os dados ESTÃO corretos nos parquets do VPS. O trabalho é de
   display. Não reabrir BLK-FIX-06-B.
2. **Tocar score por descuido**: builders leem `score_priorizacao` para sort/cap (MAP_SORT_COLUMNS:
   `constants.py:196`) — qualquer mudança no sort deve ser aprovada explicitamente (não altera
   o score em si, mas pode mudar quais hexes entram no cap).
3. **Três hipóteses, decisão de produto pendente**: o fix pode envolver trade-offs de UX
   (toggle para `POP_MIN_ACIONAVEL`? elevar opacidade do cinza? tratar NaN de score com
   fallback de cor?). Felipe deve decidir antes do Builder executar.
4. **Cap MAP_POINT_LIMIT_LARGE=18000 para UFs grandes**: SP tem 47.389 hexes enriquecidos;
   hexes costeiros de score baixo podem não entrar no top-18k mesmo após fix do cinza.
   Felipe relatou filtro de poucas cidades — verificar se o filtro de cidade estava ativo
   (scope < 35k → cap não morde).
5. **NaN em score censitário/híbrido nos modos operacionais**: `build_hybrid_map_figure`
   (components.py:1582) e `build_residual_heatmap_figure` (components.py:1754) têm scope
   `hdf["score_setor_2022_calibrado"].notna()` — hexes costeiros sem setor censitário são
   descartados ANTES do cap nesses modos. Fix pode requerer relaxar o scope ou usar fallback
   de cor para NaN de score.
6. **Filtro hard nas tabelas além do mapa**: `pages.py:1279` e `pages.py:1666` fazem
   `view = view[view["flag_pop_min_5k"]]`, removendo hexes costeiros das tabelas de
   carteira/domínio também. O Planner deve decidir se o fix cobre só o mapa ou também tabelas.

## Guardrails ativos
- CLAUDE.md §2: "LEITURA/ANÁLISE de score sem escrita em artefato M1 → Alta (revisão humana
  antes do Builder)"; "ALTERAÇÃO de fórmula, pesos, ou qualquer artefato M1 → Crítica
  (aprovação obrigatória + DEC)".
- CLAUDE.md §3: pesos `renda=0.40`/`pop=0.60` e fórmula `score_priorizacao` INALTERADOS
  (DEC-001 vigente).
- CLAUDE.md §5 guardrail permanente: "visualizações, análise radial e interações de mapa não
  podem recalcular ou alterar score_priorizacao, hex_score_estrutural, carteira, plano curto
  prazo, plano domínio ou artefatos oficiais do M1 sem aprovação explícita."
- CLAUDE.md §6: nunca executar comandos no VPS sem confirmação explícita por comando.
- NÃO reintroduzir falso diagnóstico de "dados faltando" — os dados ESTÃO nos parquets do VPS.

---

## Âncoras de código confirmadas (file:line)

### constants.py
- `MAP_POINT_LIMIT = 35000` → `constants.py:98`
- `MAP_POINT_LIMIT_LARGE = 18000` → `constants.py:103`
- `POP_MIN_ACIONAVEL = 5_000` → `constants.py:118`
- `MAP_SORT_COLUMNS = ["flag_prioridade", "flag_viavel", "score_priorizacao", "rank_brasil"]` → `constants.py:196`
- `COLOR_MODES` dict (m1/hibrido/censitario/residual/dominio) → `constants.py:331–364`

### components.py
- `_DISCARDED_FILL = [120, 120, 140, 70]` (alpha=70, cinza quase invisível em fundo escuro) → `components.py:1107`
- `_DISCARDED_LINE = [120, 120, 140, 180]` → `components.py:1108`
- `def _apply_pop_cut_colors(map_df)` → `components.py:1111`
  - `discarded = ~map_df["flag_pop_min_5k"].fillna(True)` — hexes sem flag ou com False → cinza
- `def _downsample_map_index(...)` → `components.py:1235`
- `def build_map_figure(...)` (modo M1) → `components.py:1322`
  - Scope: `df["score_priorizacao"].notna()` (linha 1339) — não descarta por setor censitário
  - `_apply_pop_cut_colors` chamada em `components.py:1414`
  - `H3HexagonLayer` instanciada em `components.py:1454`
- `def build_hybrid_map_figure(...)` (modo Híbrido) → `components.py:1563`
  - Scope: `hdf["score_setor_2022_calibrado"].notna()` (linha 1582) — **DESCARTA hexes sem setor**
  - `_apply_pop_cut_colors` chamada em `components.py:1665`
  - `H3HexagonLayer` instanciada em `components.py:1700`
- `def build_residual_heatmap_figure(...)` (modo Residual/Censitário) → `components.py:1737`
  - Scope: `hdf["score_setor_2022_calibrado"].notna()` (linha 1754) — **idem, descarta sem setor**
  - `_apply_pop_cut_colors` chamada em `components.py:1793`
  - `H3HexagonLayer` instanciada em `components.py:1829`
- `def build_dominio_map_figure(...)` → `components.py:1895`
  - Scope: apenas `hex_id/lat/lng notna()` — não descarta por score nem por setor

### data.py
- `def derive_pop_cut_columns(df, pop_min=POP_MIN_ACIONAVEL)` → `data.py:564`
  - `flag_pop_min_5k = populacao_corte_hex >= 5000` → `data.py:608`
  - Usa `pop_total_setor_2022` (granular) ou `pop_total`/`populacao_proxy` (municipal fallback)
  - Hexes costeiros com baixa pop residencial (ex.: Mongaguá=2.416 hab) → `flag_pop_min_5k=False`

### pages.py
- Filtro hard tabelas de carteira: `view = view[view["flag_pop_min_5k"]]` → `pages.py:1279`
- Filtro hard tabelas de domínio: `view = view[view["flag_pop_min_5k"]]` → `pages.py:1666`
- Texto "N oportunidades removidas pela régua de 5.000 habitantes" → `pages.py:1275–1276`
