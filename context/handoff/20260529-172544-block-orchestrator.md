# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
**BLK-OPS-02 — CI completo + build via registry (fora da prod)**

Hoje o gate do `main` (`.github/workflows/ci.yml`) roda apenas 2 arquivos de teste + 1 smoke import. O deploy no VPS faz `build` local da imagem. Este bloco quer: (1) o CI rodar a suíte completa (`pytest -q`, baseline 532 passed / 1 skipped) e ficar verde no runner; (2) um workflow que builda a imagem no CI e a empurra para um registry (ex.: GHCR) com tag por commit; (3) atualizar o runbook de deploy para o servidor fazer `pull` + `up -d` em vez de `--build`. NÃO inclui executar deploy no VPS.

## Objetivo
Fazer o CI rodar a suíte completa verde e publicar imagem em registry por commit, deixando o servidor em modo `pull` (não `build`), sem tocar em scoring, artefatos M1 nem no VPS.

## Escopo permitido
- Estender `.github/workflows/ci.yml` para rodar `pytest -q` completo (ou o máximo viável de forma estável).
- Resolver as dependências de dados dos testes no runner via **fixtures sintéticas / amostras pequenas versionadas** (nunca os Parquets/CSVs de produção).
- Criar workflow de build → push de imagem para registry (ex.: GHCR), com tag por commit (SHA).
- Atualizar runbook de deploy (`docs/deploy.md`) para `pull` + `up -d` sem `--build` no servidor.
- Opcionalmente adicionar passos de qualidade (`ruff check .`, `mypy src/`) ao CI (consistente com as validações obrigatórias do bloco).

## Fora de escopo
- Alterar lógica de scoring (`score_priorizacao`, `hex_score_estrutural`, `ajuste_executivo`).
- Alterar qualquer artefato oficial do M1, carteira, plano curto prazo ou plano de domínio.
- Executar deploy efetivo no VPS (passo humano, fora deste bloco). Nenhum comando SSH/MCP no servidor.
- Resolver outros blocos do backlog. Um bloco por vez.

## Arquivos que devem ser lidos
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\.github\workflows\ci.yml`
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\Dockerfile.streamlit`
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\docker-compose.prod.yml`
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\pyproject.toml` (config ruff/mypy/pytest; extra `[dev]`)
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\conftest.py` (fixtures globais + override de `tmp_path` para `tmp_codex_runtime/`)
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\.gitignore` (confirma que data/staging, data/ultra, concorrentes são ignorados)
- Testes acoplados a dados reais (mapear antes de planejar):
  - `tests\integration\test_normalizar_concorrentes.py`
  - `tests\integration\test_modelo_mercado_hexagonos.py`
  - `tests\integration\test_calcular_penetracao_ultra_hex.py`
  - `tests\integration\test_comparar_geofusion_vs_hex.py`
  - `tests\integration\test_validar_penetracao_ultra_hex.py`
  - `tests\integration\test_normalizar_unidades_ultra.py`
  - `tests\integration\test_expansao_dominio.py` (já tem skipif; bom modelo de padrão)
  - `tests\unit\test_pop_censo_v0001.py` (lê `data/staging/censo2022_setores_h3_res7.parquet`)
- Docs de governança: `docs/infra_producao.md` (manutenção/deploy), `docs/deploy.md` se já existir.
- `CLAUDE.md` (atenção §2 regras operacionais, §3 núcleo M1, §5 baseline pytest, §6 VPS). Observação: a spec do backlog cita "§3.4/§3.5", mas o `CLAUDE.md` atual não usa essa numeração; o conteúdo correspondente (núcleo M1 e camadas/dashboard) está em §3 e §4/§5.

## Arquivos que podem ser alterados
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\.github\workflows\ci.yml`
- Novo workflow de build/push (ex.: `.github\workflows\build-image.yml` ou `docker-publish.yml`)
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\tests\fixtures\` (fixtures sintéticas versionadas — hoje só contém `dummy_secret.yaml`)
- `C:\Users\Felipe Silva\Downloads\motor-de-expansao\motor-de-expansao\docs\deploy.md` (criar/atualizar runbook)
- Os arquivos de teste acoplados a dados reais, SE necessário, apenas para introduzir skip-guard ou apontar para fixtures sintéticas — sem alterar asserts de lógica/scoring.

## Critérios de aceite
- `pytest -q` roda a **suíte completa** no runner e fica verde (baseline: 532 passed, 1 skipped). Skips adicionais para testes intrinsecamente dependentes de dados reais são aceitáveis SE justificados e contabilizados (o número de "passed" pode mudar; o Planner deve decidir a meta exata: full-green com fixtures vs. skip-guard documentado).
- Build de imagem publica no registry (ex.: GHCR) com tag por commit (SHA).
- Runbook de deploy descreve `pull` + `up -d` sem `--build` no servidor.
- `ruff check .` e `mypy src/` verdes (validação de qualidade do bloco).
- `docker build -f Dockerfile.streamlit -t test:ci .` builda localmente (sanity).
- Verificação externa (QA): push em branch de teste → run verde no GitHub Actions (workflow CI completo + workflow de build/push GHCR).

## Criticidade classificada
**Alta.**

ALERTA M1 (guardrail): este bloco NÃO altera score nem artefatos oficiais, MAS vários testes acoplados a dados reais fazem asserts diretos sobre colunas oficiais do M1 (`score_priorizacao`, `hex_score_estrutural`, `score_oficial`, carteira/plano). Qualquer fixture sintética introduzida para destravar esses testes deve preservar o schema/contrato dessas colunas e NÃO pode mascarar regressão de scoring. Tratar como sensível ao M1 mesmo sem recálculo.

## Esteira recomendada
Block Orchestrator → Planner → [aprovação humana] → Builder → QA

## Riscos identificados
- **Acoplamento alto a dados reais (risco principal, médio→alto):** ~7+ testes de integração leem Parquets/CSVs de produção que NÃO estão no git e NÃO existem num runner limpo. Eles usam `assert PATH.exists()` (hard fail, não skip) ou chamam `gerar_base()/gerar_comparacao()/gerar_analise()` que internamente leem dados reais. No CI atual eles nunca rodam (só 2 arquivos no gate), então o problema fica latente até habilitar a suíte completa.
- **Counts hardcoded de dados reais:** asserts como `len(...) == 54` (54 unidades Ultra), CSVs de concorrentes com `1000/223/472` linhas (Smart Fit/Bluefit/Panobianco). Fixtures sintéticas precisam ou substituir esses números ou os testes precisam de skip-guard. Risco de fixture conter resquício de dado real (Ultra/Skyfit/Wellhub) — guardrail explícito proíbe.
- **Tamanho/tempo da suíte no runner:** alguns testes materializam Parquets e fazem geoprocessamento (geopandas/shapely/pyproj/h3); a suíte completa pode ser lenta no runner. Considerar cache de pip e medir tempo.
- **`conftest.py` reescreve `tmp_path`** para `tmp_codex_runtime/manual_pytest/...` em vez do tmp do OS — funciona no runner (pasta relativa criada no checkout), mas o Planner deve confirmar que não gera lixo versionado.
- **Segredos de CI:** push para GHCR precisa de `GITHUB_TOKEN`/permissão `packages: write` (nativo do GitHub Actions, sem segredo manual). Build não deve embutir nenhum segredo (o `.env` de prod não vai pra imagem).
- **Sub-bloco de fixtures:** dado o acoplamento, é plausível quebrar em sub-bloco "BLK-OPS-02a — fixtures sintéticas para a suíte de integração" antes do CI completo. Recomendação ao Planner: avaliar fazer fixtures como primeiro entregável isolado.

## Achados do levantamento read-only
- **Total de arquivos de teste:** 35 (`tests/unit`, `tests/integration`, `tests/contracts`).
- **Estado atual do `ci.yml`:** confirmado — roda só `tests/integration/test_streamlit_app.py` + `tests/integration/test_carteira_plano_nacional.py` e um smoke `import streamlit_app`. Gatilhos: push em `main`/`codex-dashboard-m1-streamlit` e PR para `main`. Instala via `pip install -e ".[dev]"`. NÃO roda ruff nem mypy.
- **Nenhum workflow de build/registry existe:** `.github/workflows/` contém apenas `ci.yml`.
- **Deploy hoje faz build local:** `docker-compose.prod.yml` tem `build: { context: ., dockerfile: Dockerfile.streamlit }` + `image: motor-expansao-streamlit:latest`. Para virar `pull`, a imagem precisa vir de registry e o compose referenciar a tag remota.
- **Dados de produção NÃO estão no git:** `data/staging`, `data/ultra`, `concorrentes` são gitignored. `data/outputs` NÃO é ignorado, mas só tem 2 arquivos tracked (`setores_censitarios_2022_geo/_metadata.json`, `teste_setor_2010/.gitkeep`) — zero parquets. Logo, num runner limpo nenhum Parquet/CSV de produção existe.
- **Testes que JÁ usam fixtures sintéticas (passam em runner limpo):** `test_streamlit_app.py`, `test_carteira_plano_nacional.py`, `test_modelo_hibrido_expansao.py`, `test_fase1_bi_exports.py`, `test_fase_a_*` (constroem CSV/Parquet em `fixtures/_tmp_*` ou `tmp_path`), toda a pasta `tests/unit` exceto `test_pop_censo_v0001.py`, `tests/contracts`. `conftest.py` provê fixtures sintéticas globais (`imovel_base`, `df_hexagonos_sample`, etc.).
- **Testes ACOPLADOS a dados reais (vão quebrar na suíte completa em runner limpo):**
  - `test_normalizar_concorrentes.py` → `assert PARQUET.exists()` em `data/staging/concorrentes_mapeados.parquet`.
  - `test_modelo_mercado_hexagonos.py` → `assert MERCADO_PATH.exists()` (`hexagonos_mercado_mapeado.parquet`), `HIBRIDO_PATH`, `ULTRA_RAW_PATH`, CSVs de concorrentes com row-counts reais (1000/223/472), M1 artifacts (`brasil_estrutural/priorizados/oportunidades`, `hexagonos_brasil_dashboard`, `hexagonos_mapa_sample`).
  - `test_calcular_penetracao_ultra_hex.py` → `modulo.gerar_base()` + lê `unidades_ultra_performance.parquet`; assert `len == 54`.
  - `test_comparar_geofusion_vs_hex.py` → `modulo.gerar_comparacao()` (dados reais Ultra/GeoFusion).
  - `test_validar_penetracao_ultra_hex.py` → `modulo.gerar_analise()`; assert `len == 54`.
  - `test_normalizar_unidades_ultra.py` → provável leitura de `data/ultra/Ultra.csv` (verificar no Planner).
  - `test_pop_censo_v0001.py` → lê `data/staging/censo2022_setores_h3_res7.parquet`.
  - `test_expansao_dominio.py` → JÁ tem `pytest.mark.skipif(not MERCADO_PATH.exists())` e skips em cascata; é o padrão "bom comportamento" para os demais.
- **Vale sub-bloco de fixtures:** SIM, recomendado avaliar. O acoplamento a dados reais está concentrado em ~7 arquivos com asserts de schema + counts reais; criar fixtures sintéticas com schema fiel (ou skip-guards documentados) é o maior risco de variância do bloco.
- **Qualidade:** ruff configurado (`select E,F,I,UP,B`, line-length 100, ignore E501) e mypy (`strict=false`, `ignore_missing_imports=true`) em `pyproject.toml`. `[dev]` extra inclui ruff/mypy/pytest. `pytest.ini_options`: `testpaths=["tests"]`, `pythonpath=[".","src"]`.

## Guardrails ativos
- **CLAUDE.md §5 (guardrail permanente):** visualizações/análises/CI não podem recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano de domínio ou artefatos oficiais do M1 sem aprovação explícita.
- **CLAUDE.md §2:** toda mudança relevante entra com teste; nenhum PR sobe com CI quebrado. Tratar `config.py`, `CLAUDE.md` e `PRD.md` como fontes canônicas.
- **CLAUDE.md §6:** GUARDRAIL ABSOLUTO — nunca executar comando no VPS via MCP/SSH sem confirmação explícita por comando. Este bloco NÃO toca no servidor.
- **Spec do bloco:** fixtures de teste não contêm dados reais de Ultra/Skyfit/Wellhub. Deploy efetivo no VPS é passo humano, fora deste bloco.
- **Backup/segredos (BLK-OPS-01, concluído):** não embutir segredos reais na imagem nem em fixtures; o `.env` de produção fica fora do build.
