# Handoff — Block Orchestrator (BLK-OPS-02b — Saneamento ruff/mypy)

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
**Planner**

## Bloco refinado
**ID:** BLK-OPS-02b
**Nome:** Saneamento ruff/mypy (violações que exigem refatoração) + tornar os steps bloqueantes no CI
**Tipo:** refatoração / qualidade
**Branch ativo:** `ciclo/BLK-OPS-02b` (já criado — não trocar/criar)

## Objetivo
Zerar `ruff check .` → 0 e `mypy src/` → 0, preferindo **correção** a supressão, e tornar os steps
`ruff`/`mypy` **bloqueantes** no CI (remover `continue-on-error: true`) — sem alterar lógica de
scoring, artefatos M1 ou semântica de testes M1, mantendo `pytest -q` em `532 passed, 1 skipped`
(zero regressão) e os hashes dos Parquets M1 inalterados pré/pós.

## INVENTÁRIO FRESCO (rodado agora, 2026-05-29 — insumo central do Planner)

> ATENÇÃO: a baseline do backlog (de BLK-OPS-02) está levemente desatualizada. Os números canônicos
> deste ciclo são os abaixo. Diferenças: backlog dizia "228 auto-fixáveis" → hoje **219**; "14× F601"
> → hoje **15×**; F821 `pdk` em `pages.py:2511` → hoje **`pages.py:2518`**.

### ruff — `ruff check . --statistics`
**Total: 286 erros** | **219 auto-fixáveis com `--fix`** (67 remanescentes; +46 "hidden" só com `--unsafe-fixes`).
> Nota de config: o `pyproject.toml` ainda usa `select`/`ignore` no top-level `[tool.ruff]`
> (regras `E,F,I,UP,B`, `ignore=["E501"]`); ruff emite *deprecation warning* sugerindo migrar
> para `[tool.ruff.lint]`. Migração da config é candidata (mecânica, não muda regras), mas **não é**
> critério de aceite — decidir no plano.

Distribuição por regra:
| Regra | Qtd | Auto-fix | Classe |
|---|---|---|---|
| UP045 non-pep604-annotation-optional | 66 | sim | (a) mecânico |
| I001 unsorted-imports | 50 | sim | (a) mecânico |
| F401 unused-import | 44 | sim | (a) mecânico |
| UP037 quoted-annotation | 41 | sim | (a) mecânico |
| E712 true-false-comparison | 20 | não | (b) trivial em volume |
| F541 f-string-missing-placeholders | 15 | sim | (a) mecânico |
| **F601 multi-value-repeated-key-literal** | **15** | **não** | **(c) SENSÍVEL — testes M1** |
| B905 zip-without-explicit-strict | 13 | não | (b) trivial em volume |
| F841 unused-variable | 7 | não | (b) trivial em volume |
| **B019 cached-instance-method** | **3** | **não** | **(c) SENSÍVEL — memory leak** |
| B007 unused-loop-control-variable | 2 | não | (b) trivial |
| E731 lambda-assignment | 2 | não | (b) trivial |
| E741 ambiguous-variable-name | 2 | não | (b) trivial |
| UP035 deprecated-import | 2 | sim | (a) mecânico |
| B017 assert-raises-exception | 1 | não | (b) trivial |
| B023 function-uses-loop-variable | 1 | não | (b) trivial |
| E401 multiple-imports-on-one-line | 1 | sim | (a) mecânico |
| **F821 undefined-name** | **1** | **não** | **(c) SENSÍVEL — bug latente real** |

Top arquivos por volume ruff (escopo `.`):
- `src/motor_expansao/dashboard/pages.py` — ~51 (39+7+5)
- `fora_primeira_fase/api_postgis/models.py` — ~54 (legado, fora do deploy)
- `tests/integration/test_streamlit_app.py` — 16
- `tests/integration/test_hex_enrichment_brasil.py` — 18 (15 = F601 M1)
- `ibge_censo.py` (raiz) — 10 (inclui 3× B019)
- `src/motor_expansao/pipelines/m1/hex_enrichment.py` — 9 (**produção M1**)
- `tests/integration/test_fase_a_censo2022.py` — 10
- dashboard `components.py`/`data.py`/`censo_point.py`; `jobs/pipelines/*`; demais `fora_primeira_fase/*`.

### mypy — `mypy src/`
**Total: 23 erros em 6 arquivos** (18 source files checados). Distribuição por arquivo:
| Arquivo | Erros | Natureza | Classe |
|---|---|---|---|
| `src/motor_expansao/dashboard/pages.py` | 8 | arg-type (float/int None), call-overload, **F821 `pdk` espelha no name-defined `pdk` linha 2518** | (b)/(c) |
| **`src/motor_expansao/pipelines/m1/hex_enrichment.py`** | **6** | implicit-Optional (`unidades_ultra=None` em 2 assinaturas), dict-item (int em dict bool/str/None), **no-redef de `generate_fase1_bi_artifacts` (import + def duplicada, linha 1596)** | **(c) PRODUÇÃO M1** |
| `config.py` (raiz, importado por src/) | 5 | `SettingsConfigDict`/assign-to-type, no-redef de `Settings` (linhas 16-17, 99) | (b)/(c) |
| `src/motor_expansao/dashboard/censo_map.py` | 2 | return-value `FreeTypeFont` vs `ImageFont` | (b) |
| **`src/motor_expansao/pipelines/m1/base_h3_brasil.py`** | **1** | return-type de generator (linha 117) | **(c) PRODUÇÃO M1** |
| `src/motor_expansao/dashboard/components.py` | 1 | arg-type `float(object)` linha 365 | (b) |

## TRÊS CLASSES DE RISCO (separação explícita p/ o Planner)

### (a) Auto-fixáveis mecânicos — `ruff check . --fix`
219 violações: UP045 (66), I001 (50), F401 (44), UP037 (41), F541 (15), UP035 (2), E401 (1).
Diff amplo (~52 arquivos). Aplicar de uma vez e **provar não-regressão com `pytest -q` + hashes M1**.
Risco baixo, mas o volume cruza produção M1 (imports/anotações) → validar mesmo assim.

### (b) Não-auto-fixáveis triviais em volume
~52 violações ruff (E712 20, B905 13, F841 7, B007 2, E731 2, E741 2, B017 1, B023 1) +
mypy de baixo risco (`censo_map.py` 2, `components.py` 1, parte de `pages.py`/`config.py`).
Correção um-a-um, mecânica mas manual. `# noqa`/`# type: ignore` só pontual e documentado.

### (c) ITENS SENSÍVEIS — exigem cuidado / não suprimir cego
1. **F601 — 15× `"pop_total"` repetido em `tests/integration/test_hex_enrichment_brasil.py`**
   (linhas 118, 128, 138, 148, 166–175, 189). **M1**: em dict literal Python, chave repetida faz o
   **último valor vencer**; mexer na chave muda *qual valor o fixture entrega ao pipeline M1*.
   → **Antes de tocar, provar invariância do fixture** (o que o teste de fato injeta hoje vs. depois).
   Proibido alterar a semântica do teste M1.
2. **F821 `pdk` em `src/motor_expansao/dashboard/pages.py:2518`** — **bug latente real**: nome `pdk`
   usado sem `import pydeck as pdk` no escopo. Não é cosmético; é um `NameError` em runtime se aquele
   caminho executar. → Corrigir o import/uso de verdade (avaliar se é dead code ou caminho vivo).
3. **B019 `lru_cache`/`cache` em método — 3× em `ibge_censo.py` (raiz; linhas 292, 363, 381)** —
   **memory leak**: `lru_cache` em método retém `self` para sempre. → **Refatorar** (mover cache p/
   função de módulo, ou `cached_property`, ou cache por chave explícita), **não** `# noqa`.
4. **mypy em PRODUÇÃO M1:**
   - `hex_enrichment.py` (6): implicit-Optional em `unidades_ultra=None` (linhas 129, 233 → tipar
     `list[...] | None`), dict-item int em dict bool/str/None (821, 822), **no-redef de
     `generate_fase1_bi_artifacts`** (1596: import + def com mesmo nome — resolver de verdade, é
     ambiguidade real de símbolo).
   - `base_h3_brasil.py` (1): return-type de função geradora (linha 117 → anotar `Generator/Iterator`).
   - Correções de tipo aqui são additivas, mas **tocam produção M1** → cada passo com prova anti-regressão.

## Escopo permitido
- Aplicar `ruff check . --fix` (classe a) e validar.
- Corrigir as classes (b) e (c) via refatoração mecânica/segura, **preferindo correção a supressão**.
- `# noqa: <code>` / `# type: ignore[<code>]` SOMENTE pontual e **sempre documentado** quando o fix
  for arriscado (justificativa inline).
- Tornar `ruff check .` e `mypy src/` **bloqueantes** no `ci.yml` (remover os 2 `continue-on-error: true`
  e os comentários de "informativo até BLK-OPS-02b").
- Opcional/decidir no plano: migrar config ruff `select/ignore` → `[tool.ruff.lint]` (silencia o
  deprecation warning; não muda regras).

## Fora de escopo
- Alterar lógica de scoring/pesos (`score_priorizacao`, `hex_score_estrutural`, ajuste executivo).
- Alterar qualquer valor/coluna/linha dos artefatos M1.
- Mudar a **semântica** de testes M1 (F601 só pode ser tocado **provando invariância** do fixture).
- Mass-suppress / desabilitar regra no `pyproject.toml` para "zerar" sem corrigir.
- Tocar VPS (CLAUDE.md §6). Não arrastar `PRD.md` nem edições não relacionadas.
- BLK-OPS-08 (upgrade actions Node 24) é bloco separado — não misturar.

## Arquivos que devem ser lidos
- `CLAUDE.md` (§2 guardrails, §3 score/parâmetros, §5).
- `pyproject.toml` (`[tool.ruff]`, `[tool.mypy]`).
- `.github/workflows/ci.yml` (steps ruff/mypy com `continue-on-error`).
- Produção M1: `src/motor_expansao/pipelines/m1/hex_enrichment.py`, `base_h3_brasil.py`,
  e `fase1_bi_exports.py` (origem do símbolo `generate_fase1_bi_artifacts`).
- Testes M1: `tests/integration/test_hex_enrichment_brasil.py` (fixture F601), `test_fase_a_censo2022.py`.
- Dashboard: `src/motor_expansao/dashboard/pages.py`, `components.py`, `censo_map.py`, `data.py`.
- Raiz: `config.py`, `ibge_censo.py`.

## Arquivos que podem ser alterados
- Produção `src/` (M1 + dashboard), conforme violações.
- Raiz `config.py`, `ibge_censo.py`; `jobs/pipelines/*`; legado `fora_primeira_fase/*`.
- Testes (`tests/**`) — F601 só com prova de invariância.
- `pyproject.toml` (config lint, opcional), `.github/workflows/ci.yml` (tornar bloqueante).
- Controle: `tasks/current_task.md`, `tasks/completed.md`, `tasks/backlog.md`,
  `context/handoff.md`, `context/handoff/`.

## Critérios de aceite (verificáveis)
1. `ruff check .` → **0 erros**.
2. `mypy src/` → **0 erros**.
3. `.github/workflows/ci.yml`: steps ruff e mypy **sem `continue-on-error`** (bloqueantes).
4. `pytest -q` → **`532 passed, 1 skipped`** (zero regressão).
5. **Hashes dos Parquets M1 inalterados pré/pós** (prova anti-regressão de artefatos):
   - `data/staging/brasil_priorizados.parquet` = `c226954945ad0757a0429c84c43f410492c0ea7d15ca1d9b6a15f68727806567`
   - `data/staging/brasil_estrutural.parquet` = `7baa07a2cbc0b7d8f2a8878932cae0ebf9400fce00e9c48c366c9903215f131b`
   - `data/staging/hexagonos_brasil_oportunidades.parquet` = `805c65e28adfd800c7d5524e73fa9b0a044b992f17d617d0f2c6e40f9bbf61ca`
   - `data/outputs/hexagonos_brasil_dashboard.parquet` = `0cfb1015fc9df8b63776eb07ae3e666766905f768a4a78a406ae4d6b7cb6f618`
   > Nota: `brasil_priorizados`/`brasil_estrutural` vivem em `data/staging/` (fluxo §3), não em `outputs/`.
   > QA pode recomputar se o pipeline rodar; do contrário, o saneamento de lint/tipos NÃO deve nem tocar
   > esses arquivos (são read-only neste bloco).

## Criticidade classificada
**ALTA.**

### ⚠️ ALERTA M1 (explícito)
Este bloco **TOCA CÓDIGO DE PRODUÇÃO M1** (`hex_enrichment.py`, `base_h3_brasil.py`) e a
**semântica de testes M1** (F601 no fixture `test_hex_enrichment_brasil.py`). As mudanças devem ser
additivas (tipos/anotações/imports), **nunca** alterar scoring, pesos ou artefatos M1. Exige:
- **Prova anti-regressão a cada passo**: `pytest -q` verde (532/1) **e** hashes dos 4 Parquets M1
  idênticos pré/pós.
- **Gate de aprovação humana OBRIGATÓRIO antes do Builder** (o Planner apresenta o plano; o
  orquestrador PARA e aguarda o humano).

## Esteira recomendada
**Block Orchestrator → Planner → [aprovação humana] → Builder → QA**

## Riscos identificados
- **Regressão M1 silenciosa** ao "consertar" tipos/F601: chave de fixture trocada muda o input do
  pipeline. Mitigar: diff mínimo + hash dos artefatos + pytest a cada passo.
- **`--fix` em massa** (~52 arquivos) pode reordenar imports e remover símbolos usados só por
  side-effect → rodar `pytest -q` + smoke import imediatamente após.
- **F821 `pdk`** pode ser caminho vivo: "consertar" adicionando import sem entender o uso pode
  mascarar um bug maior; investigar o trecho antes.
- **B019 lru_cache**: refatoração errada pode mudar comportamento de cache (resultados diferentes
  entre chamadas) — validar que os consumidores de `ibge_censo` seguem corretos.
- **no-redef `generate_fase1_bi_artifacts`**: há símbolo importado E definido com mesmo nome —
  resolver pode mudar qual implementação executa; confirmar que é a correta.
- **Config ruff legada**: migrar para `[tool.ruff.lint]` muda o caminho de config; se feito, revalidar
  que o set de regras (`E,F,I,UP,B`, ignore E501) permanece idêntico.
- Baseline do backlog desatualizada (228→219 auto-fix, 14→15 F601) — usar os números deste handoff.

## Guardrails ativos
- CLAUDE.md §2: nenhum PR sobe com CI quebrado; toda mudança relevante entra com teste.
- CLAUDE.md §3 / §5: scoring, pesos, artefatos M1 são canônicos e read-only neste bloco.
- CLAUDE.md §6: **nenhum comando no VPS** (sem exceção).
- Guardrail permanente: nada pode recalcular/alterar `score_priorizacao`, `hex_score_estrutural`,
  carteira, plano ou artefatos oficiais M1 sem aprovação explícita.
- Nota de orquestração: este ciclo altera `ci.yml` (tornar ruff/mypy bloqueantes) mas **não** altera
  a orquestração (run-cycle.md / prompts / esteira) → **não dispara dry-run pós-merge**.

---
*Inventário e delimitação produzidos em 2026-05-29 (timestamp 20260529-194242). Read-only sobre o
código nesta etapa — nenhuma violação corrigida.*
