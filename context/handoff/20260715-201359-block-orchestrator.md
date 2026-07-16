# Handoff — Block Orchestrator

## Skill que gerou este handoff
Block Orchestrator

## Próxima Skill recomendada
Planner (seguido de **gate humano de UX** entre Planner e Builder — ver Esteira recomendada). O Builder NÃO pode começar sem essa aprovação humana.

## Bloco refinado
**BLK-TP-03-FU1 — Overlay dos vazios competitivos no Mapa Territorial (Opção B).** Follow-up do BLK-TP-03 (concluído 2026-07-02): expõe no dashboard, como camada visual READ-ONLY, os hexes de "vazio competitivo" do concorrente low-cost já materializados em `data/staging/vazios_competitivos_lc.parquet` (229 hexes, contrato `vazios_competitivos_v1`). É a Opção B que o gate humano do BLK-TP-03 deferiu para bloco sucessor (a Opção A — só parquet — já foi entregue e é o que este bloco consome).

## Objetivo
Adicionar ao Mapa Territorial um toggle (sidebar, default OFF) que, quando ativado, desenha um realce visual sobre os hexes marcados como vazio competitivo, com tooltip (`membros_gt5km_concorrente_lc`, `uf`, `nome_municipio`, `score_priorizacao`), sem alterar score, ranking, carteira, plano ou qualquer artefato oficial do M1.

## Escopo permitido
- Criar/estender leitura lazy e cacheada (offline, sem rede — §2) do parquet `data/staging/vazios_competitivos_lc.parquet` (já gerado pelo módulo `src/motor_expansao/demanda_revelada/vazios_competitivos.py`, existente desde o BLK-TP-03).
- Adicionar toggle na sidebar do dashboard (padrão dos demais toggles de camada em `pages.py`), default **OFF**.
- Se o parquet não existir no ambiente, o toggle deve ficar **oculto ou desabilitado**, com mensagem clara — nunca lançar exceção.
- Adicionar uma camada de realce (`PolygonLayer`/`H3HexagonLayer`, no padrão dos pins/camadas de concorrente já existentes em `components.py`) que desenha **apenas** os hexes do parquet de vazios, em cor distinta da paleta já usada (turquesa Ultra / magenta concorrente), com o tooltip especificado.
- Testes de integração novos em `tests/integration/test_streamlit_app.py` cobrindo: (a) toggle existe e é default OFF; (b) com toggle ON + parquet sintético/mock, o layer é adicionado; (c) score/carteira/plano permanecem inalterados com overlay ON.
- Housekeeping de ciclo: `tasks/backlog.md` (marcar BLK-TP-03-FU1 concluído), `tasks/completed.md`, `tasks/current_task.md`, `context/handoff.md` + cópia versionada.

## Fora de escopo
- Qualquer recálculo ou alteração de `score_priorizacao`, `hex_score_estrutural`, pesos (`renda=0.40`/`pop=0.60`), carteira, plano curto prazo, plano de domínio ou qualquer artefato oficial do M1.
- Alterar `_downsample_map_index`, `MAP_POINT_LIMIT` (35000) / `MAP_POINT_LIMIT_LARGE` (18000) ou `MAP_SOURCE_COLUMNS_M1`/`MAP_SOURCE_COLUMNS_HYBRID` (`src/motor_expansao/dashboard/constants.py`) — o overlay é um conjunto pequeno (229 hexes) e não deve regredir o cap dos 4 modos do mapa (M1/Híbrido/Censitário/Residual).
- Editar `src/motor_expansao/demanda_revelada/vazios_competitivos.py`, `contrato.py` ou `ingestao.py` — são consumidos, não regerados neste bloco (o parquet já existe do BLK-TP-03; se precisar regenerar por ambiente, usar o módulo como está).
- Qualquer dependência de rede na carga/interatividade do dashboard (§2 — guardrail permanente).
- Alterar `flag_sam`, `oferta_efetiva_disponivel`, `sam_fitness_potencial` ou qualquer campo do pipeline de mercado — só leitura, se necessário para o tooltip.
- Dados reais/PII em teste — testes devem usar parquet sintético/mock, nunca o parquet real de produção nem `NAO_ABRA/`.
- Iniciar ou avançar qualquer outro bloco do backlog (ex.: BLK-TP-09, BLK-RELMUN-03) — escopo estrito a este bloco.

## Arquivos que devem ser lidos
- `CLAUDE.md` (completo, com atenção a §2, §4, §5)
- `tasks/current_task.md`
- `tasks/backlog.md` (bloco BLK-TP-03-FU1, linha ~1036)
- `tasks/completed.md` (seção `### BLK-TP-03`, linha ~6405 — contrato do parquet gerado)
- `context/handoff/20260702-104651-planner.md` (plano técnico do BLK-TP-03; passos 6–9 detalham este follow-up: leitura de `constants.py`, toggle, layer, testes)
- `src/motor_expansao/dashboard/constants.py` (constantes `MAP_POINT_LIMIT`, `MAP_POINT_LIMIT_LARGE`, `MAP_SOURCE_COLUMNS_M1`, `MAP_SOURCE_COLUMNS_HYBRID`)
- `src/motor_expansao/dashboard/components.py` (`_downsample_map_index`, os 4 builders de mapa, padrão de camadas de pins/concorrente existentes)
- `src/motor_expansao/dashboard/pages.py` (onde ficam os toggles de camada e `render_coord_search_sidebar` / seção do Mapa Territorial)
- `src/motor_expansao/demanda_revelada/vazios_competitivos.py` (contrato de colunas do artefato: `hex_id`, `membros`, `membros_gt5km_concorrente_lc`, `dist_concorrente_lc_min_m`, `n_concorrente_lc`, `flag_vazio_competitivo`, `hex_lat`, `hex_lng`, `uf`, `nome_municipio`, `score_priorizacao`, `oferta_efetiva_disponivel`, `versao_contrato`)
- `tests/unit/test_vazios_competitivos.py` (padrão de teste já usado no pacote `demanda_revelada/`)
- `tests/integration/test_streamlit_app.py` (padrão de teste de integração existente para toggles/camadas)

## Arquivos que podem ser alterados
- `src/motor_expansao/dashboard/pages.py` (toggle na sidebar; leitura lazy do parquet)
- `src/motor_expansao/dashboard/components.py` (layer de realce READ-ONLY)
- `tests/integration/test_streamlit_app.py` (novos testes do toggle/layer)
- `tasks/backlog.md`, `tasks/completed.md`, `tasks/current_task.md`, `context/handoff.md`, `context/handoff/AAAAMMDD-HHMMSS-*.md` (housekeeping de ciclo)

**Não alterar** (apenas ler): `src/motor_expansao/dashboard/constants.py`, `src/motor_expansao/demanda_revelada/vazios_competitivos.py`, `src/motor_expansao/demanda_revelada/contrato.py`, `src/motor_expansao/demanda_revelada/ingestao.py`, `CLAUDE.md`.

## Critérios de aceite
- Toggle "Vazio competitivo LC" (ou nome equivalente decidido no gate de UX) na sidebar do Mapa Territorial, **default OFF**.
- Com o toggle ON, a camada desenha exatamente os hexes presentes em `data/staging/vazios_competitivos_lc.parquet` (ou fixture de teste equivalente), em cor visualmente distinta das camadas de score/pins existentes, com tooltip mostrando `membros_gt5km_concorrente_lc`, `uf`, `nome_municipio` e `score_priorizacao`.
- Leitura do parquet é **lazy e cacheada**, sem chamada de rede.
- Se o parquet não existir no ambiente, o toggle fica oculto/desabilitado com mensagem clara — sem exceção não tratada.
- `score_priorizacao`, carteira, plano e demais artefatos M1 permanecem **byte-idênticos** com o overlay ON (teste de integração cobre isso).
- `_downsample_map_index`, `MAP_POINT_LIMIT`, `MAP_POINT_LIMIT_LARGE`, `MAP_SOURCE_COLUMNS_M1`, `MAP_SOURCE_COLUMNS_HYBRID` permanecem **inalterados** (diff zero nesses símbolos).
- Novos testes de integração cobrem: existência+default do toggle, ativação do layer com parquet mock/sintético, e imutabilidade de score/carteira/plano com overlay ON.
- `import streamlit_app` funciona sem erro.
- Suíte completa (`pytest -q` ou `pytest -n auto`) passa sem falhas nem erros de coleta; ruff limpo; mypy 0 issues no escopo alterado.
- `mtime` dos 4 artefatos oficiais do M1 inalterado após o ciclo (QA verifica).
- Decisão de UX (cor exata do realce, texto do toggle, formato do tooltip) registrada no gate humano ANTES do Builder começar.

## Criticidade classificada
**Média** — camada de visualização/overlay no dashboard de produção, estritamente READ-ONLY sobre o M1 (não altera score/pesos/artefatos). Não é "Alta/Crítica" porque não toca fórmula, peso ou artefato oficial — mas por tocar `dashboard/` em produção e envolver decisão de produto/UX, a esteira exige gate humano explícito entre Planner e Builder (declarado no backlog e em `tasks/current_task.md`).

## Esteira recomendada
Block Orchestrator → Planner → **[REVISÃO HUMANA — UX: cor do realce / texto do toggle / formato do tooltip]** → Builder → QA.

- O Planner já tem o plano técnico detalhado nos passos 6–9 de `context/handoff/20260702-104651-planner.md` — pode reaproveitar/confirmar em vez de redesenhar do zero, mas deve produzir seu próprio handoff formal para este bloco (BLK-TP-03-FU1), citando explicitamente os itens de UX que precisam de decisão humana antes do Builder.
- O Builder só pode começar após o gate humano decidir os itens de UX (cor do contorno/realce, texto exato do toggle, campos e formato do tooltip).
- QA sempre em Opus 4.8 (regra dura, independentemente da criticidade Média).
- **Autonomia:** este bloco é **manual, NÃO loop-safe** (toca `src/motor_expansao/dashboard/`, envolve decisão de produto/UX) — não marcar com o marcador `| **Autonomia** | loop-safe ... |` em `tasks/backlog.md`.

## Riscos identificados
- **Regressão no cap dos 4 modos de mapa** se o overlay acidentalmente entrar no fluxo de `_downsample_map_index`/`MAP_POINT_LIMIT` em vez de ser desenhado como camada separada — mitigar lendo `constants.py` e os builders de mapa ANTES de codar (exigência explícita do plano técnico do Planner anterior).
- **Parquet de origem ausente neste worktree**: verificado nesta delimitação que `data/staging/vazios_competitivos_lc.parquet`, `data/staging/demanda_revelada_h3.parquet` e `data/staging/hexagonos_mercado_mapeado.parquet` **NÃO existem** em `wt-BLK-TP-03-FU1` (são gitignored/staging, não versionados). O Builder deve tratar isso como caso real do critério "parquet ausente → toggle oculto" nos testes de integração, e — se precisar validar a geração real — pode rodar `vazios_competitivos.py` como módulo (`python -m motor_expansao.demanda_revelada.vazios_competitivos` ou equivalente) desde que os parquets de entrada existam no ambiente; isso é validação local, não deve virar dependência do teste automatizado (que deve usar fixture sintética).
- **Superfície de teste de integração aumenta** ao tocar `pages.py`/`components.py` — risco de quebrar os 4 modos existentes (M1/Híbrido/Censitário/Residual) se o layer novo não for estritamente aditivo/opcional.
- **Confusão de cor com camadas já existentes** (pins de concorrente em magenta, Ultra em turquesa) — decisão de cor faz parte do gate de UX, não deve ser escolhida unilateralmente pelo Builder.
- **`pytest -n auto` com WinError 6** é instabilidade conhecida do ambiente Python 3.14 local — cair para `pytest -q` serial se ocorrer (já documentado no plano técnico anterior).

## Guardrails ativos
- **§5 (READ-ONLY M1, permanente):** visualizações, análise radial e interações de mapa não podem recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano de domínio ou artefatos oficiais do M1 sem aprovação explícita.
- **§2:** não criar dependência de API ao vivo no dashboard de produção; CSVs/Parquets locais seguem os padrões do projeto.
- **§4 (padrão visual e cap do mapa):** faixas de 10 pontos via `RESIDUAL_SCORE_BANDS` para os 4 modos quantitativos existentes (não se aplica diretamente ao overlay, que é camada categórica de apoio, não um modo de score); cap `MAP_POINT_LIMIT`/`MAP_POINT_LIMIT_LARGE` e `_downsample_map_index` (Bloco 6 do ciclo de Performance) não podem regredir.
- **§4 (pins/logos):** "Pins/logos de concorrentes e Ultra no dashboard são camada visual de apoio; não alteram score, ranking, carteira nem artefatos oficiais" — mesmo princípio se aplica ao overlay de vazios competitivos.
- **DEC-012 (anti-PII por construção):** o parquet de origem já é agregado e sem PII (contrato `vazios_competitivos_v1`, colunas `hex_lat`/`hex_lng` no lugar de `lat`/`lng` para não colidir com `COLUNAS_PII_PROIBIDAS`); o dashboard consome o parquet como está, sem reintroduzir PII.
- **DEC-001 (pesos M1 inalterados):** `renda=0.40`/`pop=0.60` — nada neste bloco toca a fórmula do `score_priorizacao`.
- **§6.1 (loop autônomo):** este bloco é `manual`, NÃO deve receber o marcador `loop-safe` (toca `dashboard/`, decisão de produto/UX).
