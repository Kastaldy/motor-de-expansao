# Handoff — Block Orchestrator — BLK-ARCH-01a

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner

## Bloco refinado
BLK-ARCH-01a — Migrar `jobs/pipelines/*` para `src/motor_expansao/pipelines/` e limpar `pythonpath`.
É a FATIA-2 (e final) de BLK-ARCH-01. A FATIA-1 (núcleo M1 + dashboard + `config.py`/`ibge_censo.py`/`poi_enrichment.py`) já foi mergeada em main em 2026-05-29. RESTA apenas o cluster `jobs/pipelines/*` (20 módulos + `__init__.py`) na raiz, mais a remoção de `"."` do `pythonpath`. Migração estritamente MECÂNICA: sem renomear funções/assinaturas/valores; provada por hash dos 4 artefatos M1.

## Objetivo
Mover os 20 módulos de `jobs/pipelines/*` para `src/motor_expansao/pipelines/`, reapontar imports internos e de teste, e só então remover `"."` de `pythonpath`, eliminando a última fonte de imports de raiz viva sem alterar nenhum output M1.

## Inventário dos 21 módulos jobs/pipelines/*
(21 arquivos `.py` = 20 módulos + `__init__.py`)

1. `__init__.py` — apenas docstring; sem código.
2. `calcular_colunas_mercado.py` — mercado/residual (TAM/SAM/SOM, sizing). `sys.path.insert(ROOT)`.
3. `calcular_penetracao_ultra_hex.py` — penetração. `sys.path.insert(ROOT)`.
4. `calibrar_renda_setor_2022.py` — fase-A / calibração de renda.
5. `comparar_geofusion_vs_hex.py` — penetração/validação (GeoFusion vs H3). `sys.path.insert(ROOT)`.
6. `enriquecer_outputs_residual_mercado.py` — mercado/residual. `sys.path.insert(ROOT)`.
7. `enriquecimento_espacial_hexagonos.py` — enriquecimento espacial. `sys.path.insert(ROOT)`.
8. `fase_a_censo2022_setores.py` — fase-A (motor de setores censo 2022). Importa `motor_expansao.pipelines.m1.hex_enrichment`.
9. `fase_a_nacional_completo.py` — fase-A (orquestrador nacional).
10. `fase_a_piloto_expandido.py` — fase-A (piloto).
11. `gerar_carteira_acionavel.py` — domínio/carteira.
12. `gerar_plano_expansao_curto_prazo.py` — domínio/plano.
13. `gerar_plano_expansao_dominio.py` — domínio/plano.
14. `gerar_relatorio_expansao_dominio.py` — domínio/relatório.
15. `materializar_setores_censitarios_geo.py` — fase-A / geo de setores.
16. `modelo_hibrido_expansao.py` — domínio/híbrido.
17. `normalizar_concorrentes.py` — normalização. `sys.path.insert(ROOT)`.
18. `normalizar_unidades_ultra.py` — normalização. `sys.path.insert(ROOT)`.
19. `teste_setor_censitario_2010.py` — fase-A (auxiliar setor 2010). Importa `motor_expansao.pipelines.m1.hex_enrichment`.
20. `validar_fase_a_censo2022.py` — fase-A / validação.
21. `validar_modelo_ultra.py` — validação (sem import interno; só referência em docstring `python -m ...`).
22. `validar_penetracao_ultra_hex.py` — penetração/validação. `sys.path.insert(ROOT)`.

## Grafo de imports interno (jobs.pipelines.* -> jobs.pipelines.*)
Arestas reais (quem importa quem). Setas = "depende de":

- `fase_a_piloto_expandido` → `fase_a_censo2022_setores`, `calibrar_renda_setor_2022`, `validar_fase_a_censo2022`
- `fase_a_nacional_completo` → `fase_a_censo2022_setores`, `calibrar_renda_setor_2022`, `fase_a_piloto_expandido`, `validar_fase_a_censo2022`
- `fase_a_censo2022_setores` → `teste_setor_censitario_2010` (import condicional/lazy, dentro de função)
- `validar_fase_a_censo2022` → `fase_a_censo2022_setores` (import condicional/lazy)
- `materializar_setores_censitarios_geo` → `calibrar_renda_setor_2022` (import condicional/lazy)
- `enriquecer_outputs_residual_mercado` → `gerar_carteira_acionavel`
- `validar_penetracao_ultra_hex` → `comparar_geofusion_vs_hex`

Folhas (não importam nenhum outro `jobs.pipelines.*`): `calibrar_renda_setor_2022`, `teste_setor_censitario_2010`, `comparar_geofusion_vs_hex`, `gerar_carteira_acionavel`, `calcular_colunas_mercado`, `calcular_penetracao_ultra_hex`, `enriquecimento_espacial_hexagonos`, `gerar_plano_expansao_curto_prazo`, `gerar_plano_expansao_dominio`, `gerar_relatorio_expansao_dominio`, `modelo_hibrido_expansao`, `normalizar_concorrentes`, `normalizar_unidades_ultra`, `validar_modelo_ultra`.

Dependência externa para `src/` (FATIA-1, já migrada): `fase_a_censo2022_setores` e `teste_setor_censitario_2010` importam `motor_expansao.pipelines.m1.hex_enrichment`. Direção é `jobs/` → `src/`; `src/` NÃO importa `jobs/` (confirmado).

Ordem topológica segura para mover (folhas primeiro):
1. Folhas sem dependência interna (normalização, mercado leaf, domínio leaf, `calibrar_renda_setor_2022`, `teste_setor_censitario_2010`, `comparar_geofusion_vs_hex`, `gerar_carteira_acionavel`).
2. Dependentes diretos: `enriquecer_outputs_residual_mercado` (após `gerar_carteira_acionavel`), `validar_penetracao_ultra_hex` (após `comparar_geofusion_vs_hex`), `fase_a_censo2022_setores` (após `teste_setor_censitario_2010`), `validar_fase_a_censo2022` (após `fase_a_censo2022_setores`), `materializar_setores_censitarios_geo` (após `calibrar_renda_setor_2022`).
3. Topo do grafo fase-A: `fase_a_piloto_expandido`, depois `fase_a_nacional_completo`.

## Consumidores externos (testes etc.)
Testes que importam `jobs.pipelines.*` (precisam reaponte de import na migração):
- `tests/unit/test_expansao_dominio.py` → `gerar_plano_expansao_dominio`
- `tests/unit/test_pop_censo_v0001.py` → `fase_a_censo2022_setores`
- `tests/integration/test_comparar_geofusion_vs_hex.py` → `comparar_geofusion_vs_hex`
- `tests/integration/test_calcular_penetracao_ultra_hex.py` → `calcular_penetracao_ultra_hex`
- `tests/integration/test_expansao_dominio.py` → `gerar_plano_expansao_dominio`
- `tests/integration/test_modelo_mercado_hexagonos.py` → `calcular_colunas_mercado`, `normalizar_unidades_ultra`
- `tests/integration/test_teste_setor_censitario_2010.py` → `teste_setor_censitario_2010`
- `tests/integration/test_modelo_hibrido_expansao.py` → `modelo_hibrido_expansao`
- `tests/integration/test_validar_penetracao_ultra_hex.py` → `validar_penetracao_ultra_hex`
- `tests/integration/test_materializar_setores_censitarios_geo.py` → `materializar_setores_censitarios_geo`
- `tests/integration/test_validar_fase_a_censo2022.py` → `fase_a_censo2022_setores`, `validar_fase_a_censo2022`
- `tests/integration/test_fase_a_nacional_completo.py` → `fase_a_nacional_completo`, `fase_a_piloto_expandido`, `validar_fase_a_censo2022`
- `tests/integration/test_normalizar_unidades_ultra.py` → `normalizar_unidades_ultra`
- `tests/integration/test_fase_a_piloto_expandido.py` → `fase_a_piloto_expandido`
- `tests/integration/test_fase_a_censo2022.py` → `fase_a_censo2022_setores`
- `tests/integration/test_carteira_plano_nacional.py` → (referência `jobs.*`; confirmar alvo no Builder)
- `tests/contracts/test_fontes_gratuitas.py` → apenas COMENTÁRIO mencionando `jobs.pipelines.ibge_censo/poi_enrichment` (sem import vivo; não precisa reaponte, só limpeza opcional do comentário).

Confirmação `streamlit_app.py` / `src/` NÃO dependem de `jobs/`:
- `streamlit_app.py`: as 4 ocorrências de "jobs" são TEXTO DE AJUDA/docstring (`python -m jobs.pipelines.gerar_*`), não imports. Nenhum import vivo de `jobs/`.
- `src/motor_expansao/dashboard/pages.py`: as 4 ocorrências de "jobs" são igualmente STRINGS de mensagem ao usuário ("Execute `python -m jobs.pipelines...`"), não imports. Nenhum import vivo.
- Nenhum outro arquivo em `src/` importa `jobs`. Direção do acoplamento é unidirecional: `jobs/` → `src/`.

## Grupos funcionais sugeridos (subpacotes candidatos)
(sugestão; o Planner decide a partição final)
- `fase_a/`: `calibrar_renda_setor_2022`, `fase_a_censo2022_setores`, `fase_a_piloto_expandido`, `fase_a_nacional_completo`, `validar_fase_a_censo2022`, `materializar_setores_censitarios_geo`, `teste_setor_censitario_2010`. (Cluster fortemente acoplado entre si — mover como bloco coeso, folhas primeiro.)
- `mercado/`: `calcular_colunas_mercado`, `enriquecer_outputs_residual_mercado`, `gerar_carteira_acionavel`. (residual/mercado; `enriquecer → gerar_carteira`.)
- `dominio/`: `gerar_plano_expansao_dominio`, `gerar_plano_expansao_curto_prazo`, `gerar_relatorio_expansao_dominio`, `modelo_hibrido_expansao`.
- `penetracao/`: `calcular_penetracao_ultra_hex`, `validar_penetracao_ultra_hex`, `comparar_geofusion_vs_hex`. (`validar → comparar`.)
- `normalizacao/`: `normalizar_unidades_ultra`, `normalizar_concorrentes`.
- `validacao/` (ou solto): `validar_modelo_ultra`. (Standalone; sem import interno.)
- `enriquecimento_espacial_hexagonos`: solto (sem import interno; o Planner decide o destino — candidato a `mercado/` ou raiz de `pipelines/`).

Nota: agrupar em subpacotes torna o reaponte de imports nos testes mais verboso (caminho `motor_expansao.pipelines.<grupo>.<modulo>`). Alternativa mais simples e igualmente válida: mover tudo flat para `src/motor_expansao/pipelines/` (caminho `motor_expansao.pipelines.<modulo>`). Decisão do Planner — ambas atendem ao critério de aceite.

## Estado do pythonpath e dependências de raiz remanescentes
- `pyproject.toml` linha 105: `pythonpath = [".", "src"]`. O `"."` é o último resíduo a remover.
- Único importador de raiz VIVO em escopo: `jobs/pipelines/*` (resolve `jobs` como top-level via `"."`).
- FORA DE ESCOPO (não travam a remoção de `"."`): `fora_primeira_fase/*` importa `api.config` e `from hex_enrichment import ...` (órfãos por design — NÃO consertar). `concorrentes/geo_skyfit.py` é standalone (não importa raiz; confirmado fora do grep).
- Resíduo de import legado da FATIA-1: NENHUM em código vivo. Grep por `config|ibge_censo|poi_enrichment|base_h3_brasil|hex_enrichment|fase1_bi_exports|core|data|api|dashboard` como top-level só retorna ocorrências dentro de `fora_primeira_fase/*` (órfão).
- `sys.path.insert(0, str(ROOT))` (ROOT = parents[2] = raiz do repo) presente em 8 módulos (`calcular_colunas_mercado`, `calcular_penetracao_ultra_hex`, `comparar_geofusion_vs_hex`, `enriquecer_outputs_residual_mercado`, `enriquecimento_espacial_hexagonos`, `normalizar_unidades_ultra`, `normalizar_concorrentes`, `validar_penetracao_ultra_hex`). Após FATIA-1 esses hacks são vestigiais para resolução de imports (nenhum importa bare-root); ROOT segue usado legitimamente para montar caminhos de dados (`ROOT / "data" / ...`). Ao mover para `src/`, `parents[2]` muda de profundidade — ATENÇÃO: recalcular o nível de `ROOT` para que `ROOT / "data"` continue apontando para a raiz do repo. O Planner deve decidir entre (a) ajustar `parents[N]` e remover os `sys.path.insert`, ou (b) centralizar resolução de raiz. Remoção de `"."` do `pythonpath` é o ÚLTIMO passo e só após grep limpo.

## Escopo permitido
- Mover os 20 módulos (`__init__.py` incluso) de `jobs/pipelines/` para `src/motor_expansao/pipelines/` (flat ou em subpacotes — decisão do Planner) via `git mv`, em passos pequenos e reversíveis.
- Reapontar imports internos `jobs.pipelines.* → motor_expansao.pipelines.*` e os imports nos testes listados.
- Ajustar `ROOT`/`sys.path.insert` afetados pela mudança de profundidade dos arquivos (mecânico; preservar caminhos de dados).
- Remover `"."` de `pythonpath` em `pyproject.toml` SOMENTE ao final e SÓ se grep confirmar zero dependência de raiz viva (excl. `fora_primeira_fase/`).

## Fora de escopo
- Qualquer mudança de scoring, artefatos M1, ou lógica além do necessário para mover.
- `fora_primeira_fase/*` (imports órfãos — NÃO consertar).
- `concorrentes/geo_skyfit.py` (standalone isolado).
- Renomear funções/assinaturas/valores.

## Arquivos que devem ser lidos
- Todos os `jobs/pipelines/*.py` (21).
- `pyproject.toml` (`pythonpath` linha 105, `packages` linha 109).
- Os 16 testes que importam `jobs.pipelines.*` (listados em "Consumidores externos").

## Arquivos que podem ser alterados
- `jobs/pipelines/*` (mover via `git mv` para `src/motor_expansao/pipelines/`).
- Imports internos entre os módulos movidos.
- Imports nos testes listados em "Consumidores externos".
- `pyproject.toml` (remover `"."` de `pythonpath` — só ao final).
- Opcional: comentário em `tests/contracts/test_fontes_gratuitas.py` (sem import vivo).

## Critérios de aceite
- Nenhum import VIVO aponta para `jobs.pipelines.*` nem para módulo de raiz removido (grep limpo, excl. `fora_primeira_fase/`).
- `python -c "import streamlit_app; print('ok')"` ok.
- `pytest -q` verde (baseline atual: 541 passed, 1 skipped após FATIA-1).
- `ruff check .` limpo e `mypy src/` limpo.
- `pythonpath` sem `"."` (se e só se nada vivo depender de raiz).
- **Prova de não-mutação M1 (sha256 idêntico pré/pós)** dos 4 artefatos oficiais:
  - `data/staging/brasil_priorizados.parquet`
  - `data/staging/brasil_estrutural.parquet`
  - `data/staging/hexagonos_brasil_oportunidades.parquet`
  - `data/outputs/hexagonos_brasil_dashboard.parquet`

## Criticidade classificada
Alta

## Esteira recomendada
Block Orchestrator → Planner → [APROVAÇÃO HUMANA] → Builder → QA

## Riscos identificados
- Volume (20 módulos) + acoplamento interno do cluster fase-A (7 módulos entrelaçados) e arestas `enriquecer→gerar_carteira`, `validar_penetracao→comparar_geofusion`. Mitigação: mover por grupo funcional, `pytest -q` verde a cada grupo, folhas primeiro (ordem topológica acima). NÃO fazer big-bang.
- `sys.path.insert(0, str(ROOT))` + `ROOT = parents[2]` em 8 módulos: a profundidade muda ao ir para `src/`; se `parents[N]` não for recalculado, caminhos de dados (`ROOT / "data"`) quebram e podem fazer testes lerem/escreverem no lugar errado. Tratar como passo mecânico explícito.
- Imports condicionais/lazy (dentro de funções: `fase_a_censo2022_setores→teste_setor_censitario_2010`, `validar_fase_a_censo2022→fase_a_censo2022_setores`, `materializar→calibrar_renda`) podem não falhar no import-time — exigem teste de execução real, não só `import`. Cobertos pelos testes de integração.
- Risco de mutação acidental de output M1: baixo (migração mecânica), mas a prova por hash dos 4 artefatos é obrigatória pré/pós.

## Guardrails ativos
- Migração MECÂNICA: não alterar nenhum valor de output M1 (provado por hash dos 4 artefatos). Score/ranking/artefatos M1 não mudam.
- Não renomear funções/assinaturas/valores; sem refatorar lógica além do mover.
- Avançar só com `pytest -q` verde a cada grupo movido; remoção de `"."` do `pythonpath` é o ÚLTIMO passo.
- NÃO tocar `fora_primeira_fase/*` nem `concorrentes/geo_skyfit.py`.
- Guardrail permanente §5 CLAUDE.md: nenhuma alteração pode recalcular `score_priorizacao`/`hex_score_estrutural`/carteira/plano/artefatos oficiais sem aprovação explícita.
- Params canônicos M1 intactos: H3_RESOLUTION=7, pesos renda=0.40/pop=0.60, DIST_MIN_ULTRA_KM=1.0, RENDA_MIN=4500.0, AREA_MIN_M2=1200.0.
