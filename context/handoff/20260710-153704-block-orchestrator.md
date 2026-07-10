# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-PERF-01a — Shared transformer no render censitário + pré-filtro do agregar_municipio (PDFs 86×)**

Dois fixes de performance puramente internos ao caminho de render/agregação de relatórios, sem alteração de lógica, estrutura de páginas ou saída visual.

## Objetivo
Eliminar (1) a criação redundante de transformer pyproj por setor no loop de `render_mapas_censitarios_combinados` (ganho 86×, Pontual quente ~9,5 s → ~0,7 s) e (2) o full-scan nacional de 1,5 M hexes em `agregar_municipio` (ganho ~2,1 s, Municipal quente ~4,5 s → ≤2,5 s), ambos READ-ONLY sobre o M1.

## Escopo permitido

### Fix 1 — Shared transformer em `censo_map.py`
- Em `render_mapas_censitarios_combinados` (~linha 712–729): criar o transformer UMA única vez antes do loop de setores:
  ```python
  crs_local = _local_metric_crs(lat, lng)
  to_3857 = _transformer(crs_local, CRS_WEB_MERCATOR)
  ```
- Substituir as chamadas `_to_mercator(geom, lat, lng)` dentro do loop por `_project_geometry(geom, to_3857)` (função já existente, importada de `censo_point`).
- As chamadas a `_to_mercator` e `_point_to_mercator` FORA do loop (linhas 714–716: `circle_3857`, `center_3857`, `frame_3857`) devem ser convertidas da mesma forma para também reusar `to_3857`.
- A função `_to_mercator` (linha 372) e `_point_to_mercator` (linha 378) PERMANECEM no módulo (podem ser usadas por outros callers — não remover); apenas a chamada interna do loop é substituída.
- Mesma matemática de projeção, mesmos parâmetros de transformer — saída visual IDÊNTICA pixel a pixel.

### Fix 2 — Pré-filtro em `agregar_municipio` (`relatorio_municipal.py`)
- A função `agregar_municipio` (linha 586) já chama `_municipio_mask(df, nome_municipio)` na linha 606 e cria `df_muni = df.loc[mask].copy()`.
- O problema: os callers em `pages.py` (3 ocorrências, linhas 3223, 3294, 4195) passam o `df` NACIONAL (1,5 M hexes); o caller em `api/service.py` (linha 493) também passa `df` nacional (carrega o parquet full).
- **Abordagem recomendada (inline, beneficia todos os callers automaticamente):** o filtro por município já está na linha 606–607, mas é feito APÓS a assinatura. Verificar se há operações caras ANTES da linha 606 e, se houver, garantir que o filtro seja a PRIMEIRA operação. Atualmente a linha 606 já é a primeira — portanto o gargalo real pode estar no próprio `_municipio_mask` operando sobre 1,5 M linhas.
- **Alternativa 1 (caller-side, se inline não for suficiente):** nos 3 pontos de `pages.py`, passar `df_muni` (já filtrado antes de chamar `agregar_municipio`) em vez de `df` nacional. Atenção: `pages.py` linha 3234–3243 já refiltra `df` para obter `df_muni` DEPOIS da chamada — esse refilter pode ser antecipado.
- **Alternativa 2 (parâmetro opcional):** adicionar parâmetro `df_filtrado: pd.DataFrame | None = None` a `agregar_municipio`; quando presente, usa direto em vez de aplicar a máscara no df nacional. Padrão `None` = comportamento IDÊNTICO ao atual (sem regressão).
- A escolha de alternativa fica para o Planner; critério: byte-idêntico no output, todos os callers cobertos (dashboard E API), sem regressão.
- `api/service.py` linha 493 já filtra `df_muni` antes (linha 476), mas passa `df` (nacional) para `agregar_municipio` — cobrir esse caller também.

### Testes e validação
- Teste de regressão de PNGs: confirmar que os bytes dos mapas são idênticos antes/depois do Fix 1 (fixtures sintéticas em `tests/unit/test_relatorio_pontual_censitario_mapa.py` existem; verificar se cobrem ou criar cobertura explícita de byte-identity para `render_mapas_censitarios_combinados`).
- Teste de pré-filtro: cobrir o caminho municipal pré-filtrado (ex.: passar `df` de 10 hexes com 1 município e confirmar que o resultado de `agregar_municipio` é idêntico ao passar o `df` nacional filtrado à mão).
- Re-rodar o harness B6 (`scripts/perf_baseline_app.py`, seção B6) e documentar os tempos antes/depois no PR (não é teste formal, é evidência de ganho).
- Suíte completa verde: `pytest -q` (baseline: `532 passed, 1 skipped, 9 warnings` em 2026-05-28; a contagem atual pode ser maior).
- `ruff check` e `mypy` limpos.
- `loop_guard.py` limpo (não toca `config.py`, `pipelines/m1`, artefatos oficiais, deploy, secrets, CI).

## Fora de escopo
- **O2 (ThreadPool de setores)** e **O4 (pre-fetch de tiles de basemap)**: explicitamente excluídos do BLK-PERF-01a; avaliar em bloco posterior se a UX exigir.
- Raio de 1,5 km e método `setor_censitario_intersecao_area_1p5km`: INTOCADOS.
- Qualquer alteração de lógica de negócio, estrutura de páginas do PDF, faixas de cor, scores, pesos, artefatos M1.
- `config.py`, `pipelines/m1/`, artefatos oficiais do M1 (`brasil_estrutural.parquet`, `brasil_priorizados.parquet`, `hexagonos_brasil_oportunidades.parquet`, `hexagonos_brasil_dashboard.parquet`).
- Deploy, VPS, secrets, Dockerfile, CI.
- BLK-PERF-01b (cache de builders de mapa + `@st.fragment`): bloco separado, não entra aqui.

## Arquivos que devem ser lidos
- `/repo/src/motor_expansao/dashboard/censo_map.py` — Fix 1: transformer loop (~linhas 372–381, 712–729)
- `/repo/src/motor_expansao/dashboard/relatorio_municipal.py` — Fix 2: `agregar_municipio` (~linha 586–607) e `_municipio_mask` (~linha 253–260)
- `/repo/src/motor_expansao/dashboard/pages.py` — callers de `agregar_municipio` (linhas 3223, 3294, 4195) e caller de `render_mapas_censitarios_combinados`
- `/repo/src/motor_expansao/api/service.py` — caller de `agregar_municipio` (linha 493) e contexto do `df_muni` já filtrado (linha 476)
- `/repo/src/motor_expansao/dashboard/censo_point.py` — `_local_metric_crs`, `_transformer`, `_project_geometry` (funções reutilizadas)
- `/repo/tests/unit/test_relatorio_pontual_censitario_mapa.py` — testes existentes dos mapas censitários
- `/repo/tests/unit/test_relatorio_municipal.py` — testes existentes de `agregar_municipio`
- `/repo/scripts/perf_baseline_app.py` — harness B6 para re-rodar antes/depois
- `/repo/tasks/backlog.md` linhas 1145–1187 — contrato do bloco

## Arquivos que podem ser alterados
- `/repo/src/motor_expansao/dashboard/censo_map.py` — Fix 1 (shared transformer no loop)
- `/repo/src/motor_expansao/dashboard/relatorio_municipal.py` — Fix 2 (pré-filtro em `agregar_municipio`)
- `/repo/src/motor_expansao/dashboard/pages.py` — Fix 2, se a abordagem caller-side for adotada
- `/repo/src/motor_expansao/api/service.py` — Fix 2, se o caller da API precisar passar `df_muni` pré-filtrado
- `/repo/tests/unit/test_relatorio_pontual_censitario_mapa.py` — ajustes/adição de teste de byte-identity do Fix 1
- `/repo/tests/unit/test_relatorio_municipal.py` — adição de teste do caminho pré-filtrado do Fix 2
- `/repo/tasks/current_task.md` — atualização de status
- `/repo/context/handoff.md` e `/repo/context/handoff/AAAAMMDD-HHMMSS-*.md` — handoffs de ciclo

## Critérios de aceite
1. PNGs dos mapas censitários byte-idênticos antes e depois do Fix 1 (cobertura por teste explícito ou confirmação via fixture existente).
2. PDFs Pontual e Municipal semanticamente idênticos (mesmo conteúdo/páginas/big numbers) após ambos os fixes.
3. Harness B6 re-rodado (`python scripts/perf_baseline_app.py`) com ganho documentado no PR: Pontual quente ≤3 s; Municipal quente ≤2,5 s (baseline de produção: Pontual 9,5 s quente / Municipal 4,5 s quente, medidos em 2026-07-10).
4. Teste cobrindo o caminho municipal pré-filtrado (`agregar_municipio` recebendo df pequeno vs. df nacional — resultado idêntico).
5. Suíte completa verde (`pytest -q`), `ruff check` limpo, `mypy` limpo.
6. `loop_guard.py` limpo: diff não toca `config.py`, `pipelines/m1/`, artefatos oficiais do M1, deploy, Dockerfile, compose, secrets, CI.
7. 1 validação visual humana de 1 PDF de cada tipo pós-merge (não bloqueia o ciclo — evidência no PR).

## Criticidade classificada
Média (performance de relatório; READ-ONLY sobre o M1; zero mudança de lógica/estrutura de páginas)

## Esteira recomendada
Block Orchestrator → **Planner** → Builder → QA

(Modo loop autônomo: BLK-PERF-01a está marcado `loop-safe` no backlog; não requer gate humano interativo.)

## Riscos identificados
- **Fix 1 — regressão visual:** se o transformer compartilhado diferir do recriado por lat/lng (improvável — mesmos parâmetros), os PNGs mudarão. Mitigação: teste de byte-identity confirma.
- **Fix 2 — caller API passa df nacional:** `api/service.py:493` passa `df` (nacional) para `agregar_municipio`, mesmo tendo `df_muni` já filtrado na linha 476. Se a abordagem for apenas inline (sem mudança caller-side), o ganho do API caller depende de quão rápido o `_municipio_mask` opera sobre 1,5 M linhas; verificar se o ganho é suficiente ou se o caller da API precisa ser ajustado também.
- **Fix 2 — múltiplos callers em `pages.py`:** 3 chamadas distintas (linhas 3223, 3294, 4195) com contextos diferentes; o Planner deve verificar se todas passam `df` nacional ou se alguma já passa df filtrado.
- **Compatibilidade de assinatura:** se `agregar_municipio` receber parâmetro novo, o caller da API precisa ser atualizado na mesma mudança para evitar regressão.

## Guardrails ativos
- §5 guardrail permanente: READ-ONLY sobre o M1 — `score_priorizacao`, `hex_score_estrutural`, carteira, plano, artefatos oficiais INTOCADOS.
- §2: não criar dependência de API ao vivo no dashboard de produção (não se aplica aqui — ambos os fixes são offline).
- §6.1 loop: `loop_guard.py` bloqueia se o diff tocar `config.py`, `pipelines/m1`, artefatos M1, `deploy/`, `Dockerfile.*`, compose, Caddy, authelia, `.env`, `secrets/`, CI.
- `setor_censitario_intersecao_area_1p5km` e raio 1,5 km INTOCADOS (pré-fixado no contrato do bloco).
