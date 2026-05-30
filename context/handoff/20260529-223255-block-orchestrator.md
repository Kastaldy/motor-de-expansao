# Handoff — Block Orchestrator — BLK-ARCH-01

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-ARCH-01 — Concluir migração `src/` e remover legado.** Eliminar a dualidade
`src/motor_expansao/` vs. legado de raiz/flat. Hoje o repo tem TRÊS camadas de
import convivendo: (a) o pacote real `src/motor_expansao/`; (b) wrappers de raiz que
re-apontam `sys.modules` para o pacote; (c) módulos de raiz/flat que ainda são a
implementação real (`dashboard/` flat, `jobs/pipelines/*`, `ibge_censo.py`,
`poi_enrichment.py`, `config.py`). O objetivo é uma única fonte de verdade por
função, sem quebrar o dashboard nem alterar nenhum valor de output M1.

## Objetivo
Consolidar toda a implementação viva em `src/motor_expansao/`, atualizar imports e
remover wrappers/legado morto — em passos pequenos, reversíveis e com prova de
equivalência por hash dos artefatos M1.

## Mapa do legado (evidência real do repo)

### A. Wrappers de raiz (re-apontam `sys.modules` para `src/`) — implementação JÁ migrada
Estes três NÃO têm lógica; só fazem `sys.modules[__name__] = _impl` apontando para
`motor_expansao.pipelines.m1`. A implementação real já vive em `src/`.
- `base_h3_brasil.py` (raiz) -> `src/motor_expansao/pipelines/m1/base_h3_brasil.py`
  - importado por: `tests/integration/test_base_h3_brasil.py:6` (`from base_h3_brasil import ...`)
- `hex_enrichment.py` (raiz) -> `src/motor_expansao/pipelines/m1/hex_enrichment.py`
  - importado por: `tests/unit/test_scoring.py:4`, `tests/integration/test_hex_enrichment_brasil.py:3`,
    `fora_primeira_fase/tests/test_scoring.py:21` (este último é legado fora de fase)
- `fase1_bi_exports.py` (raiz) -> `src/motor_expansao/pipelines/m1/fase1_bi_exports.py`
  - importado por: `tests/integration/test_fase1_bi_exports.py:5`
  - **Destino:** remover wrappers; reapontar os imports dos testes para
    `motor_expansao.pipelines.m1.<modulo>`.

### B. `dashboard/` flat (raiz) — IMPLEMENTAÇÃO REAL ainda aqui (não é wrapper)
`dashboard/__init__.py` está VAZIO. `dashboard/constants.py` e `dashboard/utils.py`
contêm o código de verdade; o pacote `src/motor_expansao/dashboard/*` IMPORTA de volta
de `dashboard.constants`/`dashboard.utils` (acoplamento invertido).
- `dashboard/constants.py` (real) — consumido por:
  - `streamlit_app.py:11`
  - `src/motor_expansao/dashboard/pages.py:13`, `data.py:11`, `components.py:11`
  - `src/motor_expansao/pipelines/m1/fase1_bi_exports.py:11`
  - testes: `tests/integration/test_streamlit_app.py:7`, `test_fase1_bi_exports.py:4`,
    `test_expansao_dominio.py:11`
- `dashboard/utils.py` (real; `from dashboard.constants import RESIDUAL_SCORE_BANDS`) — consumido por:
  - `streamlit_app.py:42`
  - `src/motor_expansao/dashboard/pages.py:26`, `components.py:26`
  - **Destino:** mover `constants.py`/`utils.py` para `src/motor_expansao/dashboard/`,
    inverter a direção do import e remover o `dashboard/` flat (pacote vazio).
    Atualizar todos os call sites acima.

### C. `jobs/pipelines/*` — IMPLEMENTAÇÃO REAL (não migrada); ainda só importada por testes/entre si
`jobs/__init__.py` e `jobs/pipelines/__init__.py` existem; 21 módulos reais em
`jobs/pipelines/`. Importados por:
- entre si (acoplamento interno): `validar_penetracao_ultra_hex.py:25`,
  `enriquecer_outputs_residual_mercado.py:19`, `fase_a_piloto_expandido.py:20-25`,
  `fase_a_nacional_completo.py:18-27`
- por testes de integração/unit: `test_validar_penetracao_ultra_hex`,
  `test_validar_fase_a_censo2022`, `test_teste_setor_censitario_2010`,
  `test_normalizar_unidades_ultra`, `test_modelo_mercado_hexagonos`,
  `test_calcular_penetracao_ultra_hex`, `test_modelo_hibrido_expansao`,
  `test_materializar_setores_censitarios_geo`, `test_fase_a_piloto_expandido`,
  `test_fase_a_nacional_completo`, `test_fase_a_censo2022`, `test_comparar_geofusion_vs_hex`,
  `test_carteira_plano_nacional`, `tests/unit/test_pop_censo_v0001.py:18`,
  `tests/unit/test_expansao_dominio.py:12`
- **NÃO** importados por `streamlit_app.py` (dashboard não depende de `jobs/`).
- **Destino:** migrar para `src/motor_expansao/pipelines/` (provavelmente subpacotes:
  `fase_a/`, `mercado/`, `dominio/`, `penetracao/` — o Planner decide a partição).
  Volume alto + acoplamento interno => **candidato a sub-bloco próprio.**

### D. Implementação flat de raiz consumida pelo M1 (`ibge_censo.py`, `poi_enrichment.py`)
ATENÇÃO: os docstrings dizem "jobs/pipelines/..." mas os arquivos FISICAMENTE vivem na
RAIZ. `jobs/pipelines/ibge_censo.py` e `jobs/pipelines/poi_enrichment.py` NÃO existem.
O import com try/except em `hex_enrichment.py:30-35` e `fase1_bi_exports.py:22-24`
tem branch `from jobs.pipelines.ibge_censo ...` que SEMPRE falha (ModuleNotFoundError)
e cai no fallback `from ibge_censo ...` (raiz). Mesmo padrão para `from api.config`
(inexistente) -> fallback `from config` em `hex_enrichment.py:25-28` e
`poi_enrichment.py:19-22`.
- `ibge_censo.py` (raiz) — importado por: `src/.../hex_enrichment.py:31/34`,
  `src/.../fase1_bi_exports.py:22/24`, `tests/integration/test_hex_enrichment_brasil.py:11`,
  `tests/contracts/test_fontes_gratuitas.py` (×9, `from ibge_censo import IBGECenso`)
- `poi_enrichment.py` (raiz) — importado por: `src/.../hex_enrichment.py:32/35`,
  `test_hex_enrichment_brasil.py:12`, `tests/contracts/test_fontes_gratuitas.py` (×13)
- **Destino:** mover para `src/motor_expansao/pipelines/m1/` (junto do consumidor) ou
  um subpacote de fontes; **simplificar os try/except** removendo o branch morto
  `jobs.pipelines.*` (decisão do Planner). Atualizar testes de contrato.

### E. `config.py` (raiz) — settings flat; branch `api.config` morto
- Consumido por: `hex_enrichment.py`, `poi_enrichment.py` (via fallback), provavelmente
  outros pipelines. O branch `from api.config import settings` nunca resolve (`api/`
  não existe). **Destino sugerido:** mover para `src/motor_expansao/core/config.py` ou
  `src/motor_expansao/config.py` e limpar o branch morto. (Avaliar custo/benefício:
  é tocado por muitos módulos; pode virar sub-bloco.)

### F. `concorrentes/geo_skyfit.py` — script de geocodificação standalone
- Não importado por ninguém (script CLI isolado; lê `Sky Fit dados.xlsx`). **Provável
  destino:** `scripts/` ou deixar onde está (decisão do Planner; baixo acoplamento).

### G. Já migrado e correto (NÃO tocar a não ser para receber novos imports)
- `src/motor_expansao/core/{scoring.py,constants.py}` — fonte de verdade do score.
- `src/motor_expansao/pipelines/m1/{base_h3_brasil,hex_enrichment,fase1_bi_exports}.py`
- `src/motor_expansao/dashboard/{competitors,censo_map,censo_point,censo_report,components,data,pages}.py`
- `src/motor_expansao/data/__init__.py` — subpacote VAZIO (placeholder; pode receber
  helpers de acesso a dados se o Planner quiser, mas não é requisito).

### Infra de import (chave para o plano)
- `pyproject.toml:105` `pythonpath = [".", "src"]` — é o que torna importáveis tanto
  raiz (`dashboard`, `jobs`, `ibge_censo`, `config`, wrappers) quanto `src` (`motor_expansao`).
  Manter `"."` durante a transição; só removê-lo (ou o legado) quando nada mais
  depender de imports de raiz. NÃO remover `"src"`.

## Escopo permitido
- Mapear (feito aqui) e migrar APENAS o que está vivo para `src/motor_expansao/`.
- Mover `dashboard/constants.py` + `dashboard/utils.py` para o pacote e inverter imports.
- Reapontar imports de testes/wrappers de `base_h3_brasil`/`hex_enrichment`/`fase1_bi_exports`
  para `motor_expansao.pipelines.m1.*` e remover os 3 wrappers de raiz.
- Migrar `ibge_censo.py`/`poi_enrichment.py` e (opcionalmente) `config.py` para `src/`,
  limpando os branches `try/except` mortos (`jobs.pipelines.*`, `api.config`).
- Migrar `jobs/pipelines/*` para `src/motor_expansao/pipelines/` (forte candidato a
  SUB-BLOCO separado por volume/acoplamento — Planner decide se quebra).
- Cada passo: `pytest -q` verde antes de avançar; usar `git mv` para preservar histórico.

## Fora de escopo
- Mudar qualquer comportamento de scoring, valores de output, ou artefatos M1.
- Refatorar lógica além do necessário para mover (sem renomear funções, sem mudar
  assinaturas, sem otimizar).
- Tocar em `fora_primeira_fase/*` (API/PostGIS/M2-M3/PowerBI — legado declaradamente
  fora de fase; seus imports `jobs.scrapers.*`/`jobs.pipelines.geocoding` são órfãos
  e NÃO devem ser "consertados" aqui).
- Mudar `H3_RESOLUTION`, pesos, guardrails de `config.py`/`CLAUDE.md`.
- Remover `"."` de `pythonpath` se ainda restar qualquer dependência de raiz.

## Arquivos que devem ser lidos
- `CLAUDE.md`, `PRD.md`, `tasks/backlog.md` (BLK-ARCH-01, linhas ~115-160), `tasks/current_task.md`
- `pyproject.toml` (`pythonpath`, packages)
- `streamlit_app.py`
- `dashboard/constants.py`, `dashboard/utils.py`, `dashboard/__init__.py` (vazio)
- `src/motor_expansao/pipelines/m1/{base_h3_brasil,hex_enrichment,fase1_bi_exports}.py`
- `src/motor_expansao/dashboard/{pages,data,components,competitors,censo_*}.py`
- Raiz: `base_h3_brasil.py`, `hex_enrichment.py`, `fase1_bi_exports.py` (wrappers),
  `ibge_censo.py`, `poi_enrichment.py`, `config.py`
- `jobs/pipelines/*.py` (todos, p/ planejar sub-bloco)
- Testes que importam legado: `tests/contracts/test_fontes_gratuitas.py`,
  `tests/integration/test_{base_h3_brasil,hex_enrichment_brasil,fase1_bi_exports,streamlit_app}.py`,
  `tests/unit/test_scoring.py`, `tests/unit/test_pop_censo_v0001.py` e os de `jobs.pipelines.*`

## Arquivos que podem ser alterados
- Mover/remover: `dashboard/constants.py`, `dashboard/utils.py`, `dashboard/__init__.py`,
  wrappers `base_h3_brasil.py`/`hex_enrichment.py`/`fase1_bi_exports.py` (raiz),
  `ibge_censo.py`, `poi_enrichment.py`, `config.py` (avaliar), `jobs/pipelines/*` (sub-bloco)
- Atualizar imports: `streamlit_app.py`, todos os `src/motor_expansao/dashboard/*`,
  `src/motor_expansao/pipelines/m1/*`, e os testes listados acima
- `pyproject.toml` (só ao final, se aplicável: limpeza de `pythonpath`/packages)

## Critérios de aceite
- Nenhum import aponta para caminho legado removido (grep limpo p/ módulos removidos).
- `python -c "import streamlit_app; print('ok')"` retorna `ok`; dashboard sobe localmente.
- `pytest -q` verde (baseline atual: `532 passed, 1 skipped`).
- `ruff check .` limpo e `mypy src/` sem erros (notas `annotation-unchecked` toleradas
  conforme histórico — não são erros).
- **Prova de não-mutação M1 (hash idêntico pré/pós):** capturar `sha256` ANTES de
  começar e comparar ao final dos artefatos oficiais materializados, em especial
  `brasil_priorizados.parquet`. NOTA: o arquivo vive em `data/staging/brasil_priorizados.parquet`
  (o caminho `data/outputs/...` citado no backlog está impreciso — usar o caminho real;
  estender a prova aos demais oficiais: `brasil_estrutural.parquet`,
  `hexagonos_brasil_oportunidades.parquet`, `hexagonos_brasil_dashboard.parquet`).
- Migração mecânica: sem mudança de assinatura/comportamento; só movimentação + imports.

## Criticidade classificada
Alta

## Esteira recomendada
Block Orchestrator → Planner → [APROVAÇÃO HUMANA] → Builder → QA

## Riscos identificados
- **Volume/acoplamento de `jobs/pipelines/*` (21 módulos com imports entre si)** —
  risco de big-bang. Mitigação: quebrar em sub-bloco próprio, mover por grupo
  funcional, testes verdes a cada grupo.
- **Acoplamento invertido `dashboard/` flat <- `src/dashboard/`** — mover constants/utils
  primeiro e inverter a direção; risco de import circular se feito na ordem errada.
- **Branches `try/except` mortos** (`jobs.pipelines.ibge_censo`, `api.config`) podem
  mascarar regressões; ao limpar, garantir que o fallback continua funcionando.
- **`pythonpath = ["."]`** mantém legado importável mesmo após mover — pode esconder
  import legado remanescente. Mitigação: grep explícito por módulos removidos + só
  limpar `pythonpath` no final.
- **Caminho do artefato de hash impreciso no backlog** (`data/outputs/` vs `data/staging/`)
  — usar o caminho real para a prova de equivalência.
- **Testes de contrato `test_fontes_gratuitas.py`** (~22 imports de `ibge_censo`/`poi_enrichment`)
  precisam reapontar em bloco; risco de esquecer ocorrências.
- **`fora_primeira_fase/*`** referencia `jobs.scrapers.*`/`jobs.pipelines.geocoding`
  (inexistentes) — NÃO confundir com legado vivo; ignorar.

## Guardrails ativos (de CLAUDE.md / backlog)
- **Migração é MECÂNICA: não pode alterar nenhum valor de output M1 (provado por hash).
  Score, ranking, carteira, plano e artefatos oficiais do M1 não mudam.**
- `score_priorizacao` é o score oficial; nenhuma trilha pode alterá-lo sem aprovação.
- Ler o repositório real antes de editar; preservar 100% das linhas/colunas oficiais do M1.
- `config.py`, `CLAUDE.md` e `PRD.md` são fontes canônicas de parâmetros/guardrails.
- Toda mudança relevante entra com teste; nenhum PR sobe com CI quebrado.
- Avançar só com CI verde a cada passo (dependência BLK-OPS-02 já satisfeita).
- Não criar dependência de API ao vivo no dashboard de produção.
- Um bloco por vez; não expandir escopo; não implementar nada nesta fase (só mapear/delimitar).
