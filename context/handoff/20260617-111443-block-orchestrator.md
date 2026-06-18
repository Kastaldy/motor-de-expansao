# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-FIX-14 — Isolamento do teste flaky `test_classico_template_recente_inalterado`

## Objetivo
Identificar, via bisseção por ordem de coleta, o teste poluidor externo que corrompe o estado global antes da posição 847 da suíte (onde o arquivo `test_relatorio_pontual_censitario_export.py` começa em 827), e corrigir o vazamento com teardown/reset exclusivamente em `tests/`.

## Diagnóstico do Block Orchestrator

### O que o teste verifica
`test_classico_template_recente_inalterado` (posição 847 na coleção serial) chama em sequência:
1. `gerar_pdf_relatorio_pontual_censitario(...)` → captura `antes`
2. `gerar_pdf_relatorio_pontual_classico(...)` (variante clássica)
3. `gerar_pdf_relatorio_pontual_censitario(...)` → captura `depois`
4. Asserta `antes == depois`

O teste falha na suíte full, mas:
- Passa isolado (`pytest ... ::test_classico_template_recente_inalterado`)
- Passa com o arquivo inteiro (22 passed)
- Passa após os testes do `test_streamlit_app.py` (200 passed)

**Conclusão: poluidor é externo ao arquivo e anterior à posição 827 da coleção.**

### Estado global candidato a vazamento
`censo_report.py` não tem `lru_cache`, `@st.cache_data`, nem variáveis globais mutáveis de estado. O fpdf2 cria `ImageCache` por instância — sem estado global de fonte/imagem.

O único vetor confirmado de estado global mutável que afeta os bytes dos mapas embutidos no PDF é em `src/motor_expansao/dashboard/competitors.py`:

- `_ICON_CACHE: dict[str, dict]` — dicionário de logos de módulo (linha 171). Populado por `preload_logos()` e acessado por `_render_pin_tile()` (usado dentro de `render_mapas_censitarios_combinados`, cujos PNGs são embutidos no PDF).
- `_ATLAS_CACHE: dict[frozenset, tuple]` — cache de atlas de pins (linha 483). Construído por `build_icon_atlas()`.
- `@functools.cache` em `_competitor_icon_svg` e `_ultra_icon_svg` (linhas 343 e 435) — caches de função imutáveis para as formas SVG (não afetam bytes do mapa se o _ICON_CACHE não tiver logo real).

**Mecanismo de poluição mais provável:** se um teste anterior chama `preload_logos(ultra_dir=<dir_com_logo_real>)` sem limpar `_ICON_CACHE["__ultra__"]` no teardown, o `_render_pin_tile("__ultra__")` passa a embutir o PNG da logo real no pin. O `render_mapas_censitarios_combinados` chamado em `antes` e `depois` produz então PNGs diferentes SOMENTE SE o `_ICON_CACHE` mudar entre as duas chamadas dentro do mesmo teste — o que só ocorre se o vazamento popula o cache APÓS a primeira chamada (improvável) OU se as duas chamadas usam caminhos diferentes de `_ICON_CACHE`.

**Hipótese alternativa mais forte:** Se um teste anterior MODIFICA uma variável de módulo em `censo_report.py` ou em `censo_map.py` via `setattr` direto (não `monkeypatch`) e não restaura, os bytes divergem. Por exemplo: se `_load_branding_assets` lê de `data/ultra/` e algum teste cria/modifica arquivos nesse diretório sem limpeza.

**Candidatos a poluidor na faixa 407-826 (entre o fim do test_streamlit_app.py e o início do export):**
- `tests/unit/test_api_geo.py` — pode usar a API que chama `gerar_pdf`
- `tests/integration/test_api_analisar.py` — tem `scope="module"` fixtures e gera PDFs (posições 31-40)
- Qualquer teste que chame `preload_logos` com `ultra_dir` real e não faça `_ICON_CACHE.pop("__ultra__", None)` no teardown

### Posições na coleção (referência para bisseção)
- Poluidor: faixa 1-826 (externo ao arquivo do teste flaky)
- `test_streamlit_app.py`: posições 208-406
- `test_relatorio_pontual_censitario_export.py`: posições 827-848
- `test_classico_template_recente_inalterado`: posição 847
- `test_ultra_pins.py`: posições 911+ (DEPOIS — não é o poluidor)

### Bisseção recomendada ao Builder
```bash
# Passo 1: reproduzir o failure (confirmar que o ambiente está sujo)
python -m pytest -q --cache-clear -p no:randomly 2>&1 | grep "FAILED\|passed\|failed"

# Passo 2: bisseção — rodar só a metade [1, 826] + o teste flaky
python -m pytest -q --collect-only 2>&1 | grep "^tests/" | awk 'NR<=413' | xargs python -m pytest -q "$@" tests/unit/test_relatorio_pontual_censitario_export.py::test_classico_template_recente_inalterado

# Passo 3: bisseção iterativa até isolar o arquivo poluidor
# Reduzir progressivamente até encontrar o intervalo mínimo que reproduz o failure

# Passo 4: dentro do arquivo poluidor, bisseção de função
python -m pytest -q <arquivo_poluidor>::<test_candidato> tests/unit/test_relatorio_pontual_censitario_export.py::test_classico_template_recente_inalterado
```

## Escopo permitido
- `tests/**` — fixtures, teardown, conftest.py, decoradores de teste
- No máximo um ajuste de teardown/reset em helper de teste (ex: fixture `autouse=True` que limpa `_ICON_CACHE` ou variável de módulo afetada)
- Criar `tests/conftest.py` se necessário para fixture de teardown global

## Fora de escopo
- score/pesos/artefatos M1 (guardrail READ-ONLY)
- Alterar lógica de produção de `censo_report.py`, `censo_map.py`, `competitors.py` sem nova decisão
- Mascarar com `-p no:xdist`, `skip`, `xfail`, ou desabilitar o teste
- Suprimir o failure sem identificar a causa raiz
- Mudar a geração de PDF ou a lógica de comparação do teste

## Arquivos que devem ser lidos
- `tests/unit/test_relatorio_pontual_censitario_export.py` — o teste flaky e seus vizinhos (arquivo completo lido pelo BO)
- `src/motor_expansao/dashboard/competitors.py` — estado global `_ICON_CACHE`, `_ATLAS_CACHE`, `@functools.cache` em `_competitor_icon_svg`/`_ultra_icon_svg`
- `src/motor_expansao/dashboard/censo_report.py` — confirmar ausência de estado global (lido pelo BO; sem lru_cache nem variáveis mutáveis)
- `src/motor_expansao/dashboard/censo_map.py` — verificar se há estado global de módulo além das constantes
- `tests/unit/test_ultra_pins.py` — padrão de cleanup com `_ICON_CACHE.pop` (está DEPOIS do flaky, posição 911+; relevante como referência de padrão correto)
- Arquivo(s) poluidor(es) identificados na bisseção (faixa 1-826)
- `tests/integration/test_api_analisar.py` — tem `scope="module"` e gera PDFs (posições 31-40; skip-safe pela base geo ausente em CI)

## Arquivos que podem ser alterados
- `tests/conftest.py` (criar se não existir — atualmente ausente) — para fixture autouse de teardown global
- Arquivo(s) do(s) teste(s) poluidor(es) identificados — apenas o teardown/cleanup da função/fixture que vaza
- `tests/unit/test_relatorio_pontual_censitario_export.py` — somente se a correção exigir guardrail interno ao próprio teste (ex: garantir que `_ICON_CACHE` está limpo antes/depois)
- `tests/integration/test_streamlit_app.py` — se o poluidor estiver aqui (teardown de monkeypatch ou limpeza de cache)

## Critérios de aceite
1. `python -m pytest -q --cache-clear` (suíte full serial) **verde reproduzível** — zero failures
2. `python -m pytest -q tests/unit/test_relatorio_pontual_censitario_export.py::test_classico_template_recente_inalterado` — 1 passed (continua passando isolado)
3. `python -m pytest -q tests/unit/test_relatorio_pontual_censitario_export.py` — 22 passed (arquivo inteiro intacto)
4. Poluidor **identificado e documentado** no handoff do Builder (não apenas corrigido sem diagnóstico)
5. READ-ONLY M1: zero toque em `config.py`, `pipelines/m1/`, artefatos oficiais, `score_priorizacao`
6. `python -m ruff check` e `python -m mypy` sem novos erros nas alterações feitas
7. A correção resolve a CAUSA (estado global não revertido), não o sintoma

## Criticidade classificada
Média

## Esteira recomendada
Planner → Builder (opus, override +1 por complexidade de investigação) → QA (opus 4.8, sempre)

## Riscos identificados
- **O poluidor pode não ser `_ICON_CACHE`**: se a bisseção não convergir para `competitors.py`, o vazamento pode ser em outra variável de módulo não identificada nesta fase (ex: estado da PIL, cache do pyproj, ou variável de módulo em `censo_map.py`)
- **Bisseção pode ser custosa**: com 826 testes antes do flaky e a flakiness dependendo de ordem de coleta específica, cada rodada de bisseção pode levar vários minutos; o Builder deve usar `--collect-only` para obter a lista e bisetar por faixas progressivas
- **Reprodutibilidade da ordem**: sem `pytest-randomly` instalado ou com `--cache-clear`, a ordem é determinística por filesystem; confirmar que `python -m pytest -q --cache-clear` sem flags extras reproduz o failure antes de iniciar a bisseção
- **A correção não pode mascarar**: usar `_ICON_CACHE.clear()` em conftest global seria mascarar (eliminaria o sinal); a correção deve ser cirúrgica no teardown do teste/fixture poluidor
- **Testes com `scope="module"` em test_api_analisar.py**: o `client = TestClient(create_app())` é compartilhado; se a API popula `_ICON_CACHE` via `lifespan`/startup, o cache vaza para testes subsequentes — verificar se `create_app()` chama `preload_logos`

## Guardrails ativos
- READ-ONLY sobre o M1: não tocar `score_priorizacao`, `hex_score_estrutural`, carteira, plano, artefatos oficiais, `config.py`, `pipelines/m1/`
- Não mascarar flakiness com `skip`, `xfail`, `-p no:xdist`, nem supressão de coleta
- Não alterar lógica de produção de `censo_report.py` sem nova DEC aprovada
- Toda mudança entra com teste; nenhum PR deve subir com CI quebrado
- Paths pré-sujos (`data/outputs/setores_censitarios_2022_geo/_metadata.json`, `data/reports/relatorio_pontual_censitario_base_geo.md`) NÃO commitar

## Branch do ciclo
`ciclo/BLK-FIX-14`

## Tiering de modelo
- Planner: sonnet
- Builder: opus (override +1; investigação de isolamento atipicamente sutil)
- QA: opus 4.8 (sempre)
