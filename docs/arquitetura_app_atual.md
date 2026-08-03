# Arquitetura do app atual — inventário e mapa de dependências

> Nasceu como artefato do BLK-REV-02 (epic BLK-REV, 2026-07-08), descrevendo o
> dashboard Streamlit. Atualizado em **2026-08-03 (DEC-022)**: o Streamlit foi
> aposentado e o app de produção passou a ser o **piloto web**. A **parte A**
> descreve o app atual; a **parte B** preserva, como HISTÓRIA, o inventário do
> Streamlit (é o registro mais detalhado da arquitetura que o corte removeu, e o
> motor compartilhado descrito lá continua vivo). READ-ONLY sobre o M1 nas duas
> partes.

---

# Parte A — O app atual: piloto web (desde 2026-08-03, DEC-022)

## A.1 Visão geral

O app de produção é o **piloto web** em `web/`: uma SPA **React + Vite + deck.gl**
(`web/src/`) servida por um backend **FastAPI** (`web/server/app.py`, porta `8899`)
que embrulha as funções puras do motor compartilhado e lê os Parquets read-only
(`MOTOR_DATA_DIR`). Em produção, **um único container** (`motor_expansao_web`,
imagem `motor-expansao-web`) serve o `dist/` do Vite via `StaticFiles` e a API em
`/api/*` na mesma porta, atrás de Caddy + Authelia no subdomínio
`piloto.ultra-expansao.tech`. O subdomínio `dashboard.ultra-expansao.tech` ficou
vivo **apenas** como host de `/tiles/*` (tileserver que alimenta o basemap dos
PDFs); a raiz redireciona 301 para o piloto (DEC-022 §3).

São **3 superfícies** (DEC-020 definiu esse escopo; "substituir 100% o Streamlit"
= paridade destas três):

- **Mapa Territorial** (default) — porta de entrada por UF, funil de 4 camadas
  (Potencial → setores quentes → residual → white spaces → aberturas) com
  drill-down até o município, multi-hex, filtro "MELHORES", busca por
  coordenada/link/endereço e geração dos Relatórios Municipal e Pontual.
- **Visão Executiva** — a rede Ultra REAL por estado (Growth API,
  `growth_api_historico.parquet`, ingestão semanal — DEC-013): bubble map,
  KPIs com variação vs M-1, ranking de unidades, seletor de competência.
- **Viabilidade do ponto** — stress-test determinístico de um imóvel; o backend
  chama `simular()` (`dimensionamento/simulador.py`) e serve o
  `viabilidade_payload_v1` único que tela, API e PDF consomem sem recalcular.

O Dock mostra `Expansão de domínio` e `Carteira e plano` desabilitadas de
propósito: a DEC-020 decidiu que Domínio não vira tela (a Fase 4 do Mapa cobre a
análise) e que Carteira/Plano vira, no futuro, "Oportunidades Imobiliárias"
(placeholder; epic própria pendente de DEC + spec).

## A.2 Peças e dependências

```
web/
  server/app.py         backend FastAPI do piloto (paralelo a src/motor_expansao/api/)
  src/
    lib/                contrato de tipos, cliente HTTP, formatação pt-BR
    components/         dock, mapa deck.gl, painel narrativo, stepper, gráficos
    screens/            MapScreen, ViabilityScreen
    styles/tokens.css   paleta e escalas
```

Endpoints do backend (`web/server/app.py`): `GET /api/health`, `/api/ufs`,
`/api/geocode`, `/api/municipios/{uf}`, `/api/uf/{uf}`,
`/api/municipio/{uf}/{municipio}`, `/api/faixa-alunos`, `/api/executiva/{uf}`;
`POST /api/viabilidade`, `/api/relatorio/municipal`, `/api/relatorio/pontual`,
`/api/simulador/xlsx`.

O backend **importa, não duplica** o motor compartilhado em
`src/motor_expansao/dashboard/` — que sobreviveu ao corte por inteiro:
`data.py` (carga lazy por UF via `read_enriched_uf_partition`, agregadores puros),
`constants.py`, `schemas.py`, `utils.py`, `competitors.py`, `censo_point.py`,
`censo_map.py`, `censo_report.py`, `relatorio_municipal.py` e
`viabilidade_charts.py`. Esses módulos são consumidos por 4 clientes: o piloto,
a API GeoEspacial (`src/motor_expansao/api/`, container `motor_expansao_api`,
consumida pelo bot Telegram), o próprio bot e o `fase1_bi_exports` (que
materializa o dataset enriquecido). O que saiu no corte foi só o subgrafo
Streamlit-only: `pages.py`, `components.py`, `ui_theme.py`, `ui_proto.py`,
`ui_spike_deckgl.py`, `streamlit_app.py` e `.streamlit/` (detalhe na parte B —
o inventário histórico descreve esses módulos como vivos).

## A.3 Modelo de interação (por que a arquitetura mudou)

O diagnóstico do ciclo BLK-REV (ver `docs/system_design_referencia.md` §2 e a
parte B §6 abaixo) mostrou que o gargalo do app antigo era o ciclo
rerun/reserialização do Streamlit + pydeck, não o volume de dados. O piloto adota
o padrão dos produtos de referência: **instância deck.gl persistente no cliente**
— trocar cor/camada muta só o atributo alterado (`updateTriggers`/`visible`), sem
reenviar hexes nem re-executar backend. O backend só entra quando há dado novo
(troca de UF/município, geocoding, relatório, viabilidade).

A carga continua **lazy por UF**: o backend lê só a partição `uf=XX` de
`data/outputs/hexagonos_dashboard_enriquecido/` (a 1ª leitura de uma UF carrega a
partição inteira e demora alguns segundos — esperado). Cores e tooltip do mapa
são porte 1:1 do dashboard antigo (`score_band_to_color`, faixas de 10 pontos,
corte `<5k hab` em cinza), então a leitura visual não mudou com a troca de stack.

## A.4 Dados consumidos

| Artefato | Uso |
| --- | --- |
| `data/outputs/hexagonos_dashboard_enriquecido/uf=XX/` | fonte principal do Mapa (obrigatório) |
| `data/outputs/setores_censitarios_2022_geo/` | Relatório Pontual (malha real IBGE) |
| `data/ibge/municipios_XX.geojson` | malha municipal dos relatórios |
| `data/staging/concorrentes_mapeados.parquet` + `unidades_ultra_performance_hex.parquet` | pins no mapa |
| `data/staging/growth_api_historico.parquet` | Visão Executiva (404 sem ele) |
| `data/staging/base_calibracao_maduras.parquet` | semente p50 da Viabilidade |
| `data/staging/hexagonos_mercado_mapeado.parquet` | residual do ponto no Relatório Pontual |
| `data/staging/uplift_*.parquet` + `fator_temporal_renda.json` | renda domiciliar municipal (fallback nacional sem eles) |

Tudo montado `:ro` em produção; guardrail permanente: o piloto **não recalcula**
`score_priorizacao`, `hex_score_estrutural`, carteira, plano nem artefato oficial.

## A.5 O que o corte removeu (perdas aceitas)

A DEC-022 §1 lista os fluxos do Streamlit que deixaram de existir sem equivalente
no piloto (fila/lote de relatórios, export CSV de setores, painel de entorno H3
1,6 km, 20 dos 25 KPIs do multi-hex, ranking completo de 1.000 linhas, grade de
sensibilidade na UI, filtro por rede, Visão Executiva territorial M1, rodapé de
proveniência). O porte prioritário pós-corte é a **fila/lote de relatórios**
(BLK-WEB-22). Deploy: `docs/deploy_piloto_web.md`.

---

# Parte B — HISTÓRIA: arquitetura do dashboard Streamlit (aposentado em 2026-08-03)

> **Tudo abaixo descreve o app como era em 2026-07-08** (artefato do BLK-REV-02;
> fontes: código em `src/motor_expansao/dashboard/`, `streamlit_app.py`,
> `src/motor_expansao/api/` e o baseline `data/analysis/perf_baseline_app_2026.md`).
> O dashboard de 5 abas foi aposentado pela **DEC-022** (escopo do corte na
> **DEC-020**); `streamlit_app.py`, `pages.py`, `components.py` e os `ui_*` citados
> adiante **não existem mais no repo**. O texto é preservado no tempo verbal
> original porque documenta decisões (carga lazy por UF, render lazy, fonte de
> mapa enxuta, caps) que continuam explicando o desenho do motor compartilhado.

## 1. Sumário executivo

O app é um dashboard **Streamlit** de expansão territorial da Ultra Academia, com
ponto de entrada em `/repo/streamlit_app.py`. Ele lê Parquets locais (offline, sem API
ao vivo na carga/interatividade — CLAUDE.md §2) e renderiza mapas hexagonais H3 via
**pydeck** (deck.gl/WebGL no browser), tabelas, KPIs e gráficos. A superfície de UI tem
**5 abas** (`Mapa`, `Executivo`, `Expansão de Domínio`, `Carteira e Plano`, `Viabilidade`)
mais uma barra de busca por coordenada/endereço/link e geração de dois relatórios PDF
(Pontual Censitário 1,0 km e Municipal).

O código do dashboard vive em **~14 módulos** sob `src/motor_expansao/dashboard/`
(`data.py`, `components.py`, `pages.py`, `constants.py`, `censo_point.py`, `censo_map.py`,
`censo_report.py`, `relatorio_municipal.py`, `competitors.py`, `utils.py`, `schemas.py`,
`ui_proto.py`, `ui_theme.py`) mais uma camada de **API FastAPI** paralela em
`src/motor_expansao/api/` (consumida por bots, não pelo dashboard). O motor de viabilidade
determinístico vive em `src/motor_expansao/dimensionamento/`.

O padrão arquitetural principal é **carga lazy por UF + render lazy de aba + fonte de
mapa enxuta**, três decisões do ciclo de performance de mai/2026 (Blocos 4/5/6). O
`streamlit_app.py:main()` monta a árvore de render a cada rerun, mas só a aba ativa é
computada e só a partição `uf=XX` do dataset enriquecido é lida. O guardrail permanente
(§5) atravessa todas as camadas: visualização, análise radial, relatórios e API são
**READ-ONLY sobre o M1** — nunca recalculam `score_priorizacao`, `hex_score_estrutural`,
carteira, plano ou artefatos oficiais.

## 2. Modelo de rerun do Streamlit

O Streamlit reexecuta o script inteiro (`main()`) a cada interação (mudança de widget,
clique no mapa, digitação na busca). O que evita recomputar o mundo a cada rerun é o
**cache** e o **render lazy de aba**.

### 2.1 Caches no projeto

Os loaders de `streamlit_app.py` usam DOIS decoradores distintos:

- **`@st.cache_resource(show_spinner=False)`** — para os DataFrames pesados que devem
  existir como um único objeto compartilhado entre sessões/reruns, sem cópia por
  chamador: `load_data`, `load_hybrid_data`, `load_censo_trace_data`,
  `load_estrutural_pop`, `build_dashboard_dataset`, `load_uf_slice(uf)`. `load_uf_slice`
  é cacheado **por UF** (a chave inclui o argumento `uf`), então trocar de UF lê nova
  partição; voltar a uma UF já vista é servido do cache.
- **`@st.cache_data(show_spinner=False)`** — para retornos leves/serializáveis
  (catálogos e frames menores): `load_uf_catalog`, `load_censo_geo_municipios(uf)`,
  `load_censo_geo_setores(uf, cod)`, `load_base_calibracao`, `load_competitors`,
  `load_ultra`, `load_carteira`, `load_plano`, `load_plano_dominio`.

**Nenhum TTL é configurado** em nenhum loader (sem `ttl=`): os caches vivem enquanto o
processo do servidor Streamlit estiver de pé. Isso é seguro porque os Parquets são
estáticos entre deploys; um novo deploy reinicia o processo e reconstrói os caches a frio.

### 2.2 O que é cacheado vs. recomputado a cada rerun

**Cacheado (custo pago uma vez por chave):** leitura dos Parquets e o merge
`enrich_dashboard_data` — via `load_uf_slice`, que lê a partição `uf=XX` do dataset
enriquecido (`read_enriched_uf_partition`) e só cai no `build_dashboard_dataset()`
(merge nacional filtrado) se a partição não existir. Também os overlays de concorrentes/
Ultra e as tabelas de carteira/plano/domínio.

**Recomputado a cada rerun (não cacheado):** tudo dentro de `main()` fora dos loaders —
`build_pop_cut_lookup`, `apply_global_filters` (barato, ~3-6 ms mesmo em AM), os
`build_city_summary`/`build_uf_summary` (só quando a aba ativa os consome), e **todos os
builders de mapa** (`build_map_figure`, `build_hybrid_map_figure`, etc.). O baseline
BLK-REV-01 confirma: uma **troca de cor** no Mapa Territorial reexecuta o builder inteiro
(downsample + cap + color-map + tooltip) — custo integral de ~0,7-3,3 s por rerun (é o
maior custo Python recorrente da interação; ver §6). Os builders **não** são cacheados
porque dependem de muitos parâmetros mutáveis (filtros, cor, pin de busca) e retornam
objetos `pydeck.Deck` grandes.

### 2.3 Chamadas que disparam rerun

- Seleção de UF (`render_uf_selectbox`) — dispara carga da partição da UF.
- Widgets de filtro da sidebar/corpo (`render_sidebar_filters`: multiselects de município,
  faixa, elegibilidade híbrida, cobertura, qualidade de join; checkboxes top).
- Troca de aba no `render_tab_selector` (`st.segmented_control`).
- Digitação/submit na busca por coordenada (`render_coord_search_sidebar`).
- Clique num hexágono no mapa: o `pydeck_chart(on_select="rerun")` dentro do
  fragment de mapa dispara rerun para propagar a coordenada clicada.
- Troca de modo de cor / overlays no Mapa Territorial.
- Geração/baixa de PDF (Pontual/Municipal), botões de cenário multi-hex.

### 2.4 Render lazy das abas

`render_tab_selector(labels)` usa **`st.segmented_control`** com o estado persistido em
`st.session_state` (chave `dashboard_active_tab_last`), no lugar de `st.tabs` (que
executaria o corpo de TODAS as abas por rerun). Ele devolve **apenas o label da aba
ativa**; em `main()` um bloco `if active_tab == ...` chama só o `render_*` correspondente.
Consequência: por rerun, roda apenas o render de uma aba. Os summaries executivos
(`build_city_summary`/`build_uf_summary`) só são calculados quando `active_tab` é
`Executivo` ou `Mapa` (os únicos consumidores). Na troca de aba, um pequeno JS injetado
rola a página para o topo.

O seletor de abas e a barra de busca vivem lado a lado num container `nav_search_bar`
(um `st.columns([3, 2])`) que o CSS de `inject_styles` fixa (sticky) no topo ao rolar.

## 3. Camadas da arquitetura

### 3a. Camada de dados — `dashboard/data.py`

**Responsabilidade:** ler/normalizar/fundir os Parquets, derivar colunas de exibição e
prover os agregadores puros (entorno, multi-hex, corte populacional). Não recalcula score.

**Funções de carga (leitura de disco):**
- `list_partitioned_ufs(base_dir)` — cataloga UFs inspecionando os diretórios de partição
  `uf=XX` do dataset enriquecido, sem carregar dados (catálogo leve para a sidebar).
- `read_enriched_uf_partition(base_dir, uf)` — lê SÓ a partição `uf=XX` do dataset
  enriquecido (via `pyarrow.dataset` com filtro hive), valida schema e restaura tipos
  via `_prepare_dataframe`. Retorna vazio se dataset/partição não existir.
- `read_censo_geo_partition(base_dir, uf, cod_municipio=None)` / `list_censo_geo_municipios`
  / `resolve_cod_municipio_from_geo_dir` — leitura particionada dos setores IBGE geo
  (`setores_censitarios_2022_geo/uf=XX/cod_municipio=NNNNNNN`) para os relatórios.
- Helpers privados `_read_parquet_subset` / `_read_optional_parquet_subset` — leem só as
  colunas requeridas (obrigatórias vs. opcionais), erguendo erro se faltar coluna obrigatória.

**Merge e derivação:**
- `enrich_dashboard_data(base_df, hybrid_df, censo_df, estrutural_pop_df)` — funde M1 +
  híbrido + traço censitário + `pop_total` estrutural por `hex_id` (left joins),
  coalesce de colunas duplicadas (`_coalesce_columns`), deriva rótulos híbridos
  (`_derive_hybrid_labels`: elegibilidade, bucket de cobertura, qualidade de camada),
  confiança geográfica e o corte populacional; termina em `_prepare_dataframe`.
- `_prepare_dataframe(df)` — coerção de tipos (Float32 para `FLOAT_COLUMNS`, boolean para
  `BOOL_COLUMNS`, categóricos ordenados para faixa/elegibilidade/cobertura/qualidade),
  ordenação estável por `MAP_SORT_COLUMNS`, e cria colunas de conveniência `UF`,
  `nome_municipio`, `score_exibicao (= score_priorizacao)`.
- `derive_pop_cut_columns(df, pop_min=POP_MIN_ACIONAVEL)` — delega ao helper compartilhado
  `pipelines/pop_corte.py` (fonte única): produz `populacao_corte_hex`,
  `fonte_populacao_corte` e `flag_pop_min_5k` (régua ≥5.000, setor 2022 quando granular,
  fallback municipal). `build_pop_cut_lookup` extrai o lookup leve `{hex_id → colunas de corte}`.
- `apply_global_filters(df, *, selected_ufs, selected_cities, selected_faixas, ...)` —
  aplica máscara booleana pelos filtros da UI; barato (~3-6 ms). Retorna `df.loc[mask]`.

**Agregadores puros (não mutam df):**
- `build_city_summary` / `build_uf_summary` — groupby de KPIs por cidade/UF.
- `analisar_entorno_ponto(lat, lng, hex_df, raio_km=1.6, ...)` — agrega pop/renda/scores/
  residual/consumo dos hexes cujo centroide cai no raio (haversine); conta pins de
  concorrente/Ultra/âncoras no raio. Aproximação por centroide.
- `agregar_cenario_multihex(df, hex_ids)` — agrega KPIs de uma lista de hex_ids (retorna
  ~25 campos incluindo domínio híbrido `clip(0.60·censo + 0.40·residual, 0, 100)`).
- `lookup_hex_by_coord(lat, lng, df, h3_res=7)` — converte coordenada → `hex_id` (h3) e
  procura no df; base da busca por coordenada.
- `parse_coordinate_input` / `parse_hex_ids_from_text` / `haversine_km` / `_validate_brazil_bbox`
  — parsers e utilitários puros.

**Dependências internas:** `constants`, `schemas` (validação), `pipelines/pop_corte`
(régua compartilhada). Não importa `components`/`pages`.

### 3b. Camada de componentes/mapa — `dashboard/components.py`

**Responsabilidade:** construir figuras de mapa pydeck, gráficos, tabelas e legendas.
É o maior módulo do dashboard (~129 KB). READ-ONLY: visualização não recalcula M1.

**Builders de mapa (retornam `tuple[pdk.Deck | None, int]` salvo indicado):**
- `build_map_figure(df, *, selected_ufs, selected_cities, competitors_df, ultra_df, search_pin, search_hex_id, cluster_competitors=False, show_discarded=True)` — mapa executivo M1 (colore por `score_priorizacao`).
- `build_hybrid_map_figure(hdf, *, color_col="score_expansao_hibrido", ...)` — mapa híbrido/censitário; `color_col` seleciona `score_expansao_hibrido` ou `score_setor_2022_calibrado`.
- `build_residual_heatmap_figure(hdf, ...)` — mapa residual (`score_oportunidade_residual`).
- `build_dominio_map_figure(plano, ...)` — mapa de Expansão de Domínio (colore por `ordem_expansao_cidade`; sem cap por volume baixo).
- `build_unified_map_figure(df, *, color_mode="m1", enabled_overlays, ...)` — **dispatcher**: escolhe o builder pelo `color_mode ∈ {m1, hibrido, censitario, residual, dominio}` (ver `COLOR_MODES` em `constants`).
- `build_ultra_presence_map(ultra_df, ...)` — pins Ultra (IconLayer) da Visão Executiva.
- `build_analise_pontual_map(lat, lng, raio_km, hexes_entorno, ...)` → `pdk.Deck | None` — ponto + círculo de raio + hexes + pins.
- `build_multihex_analysis_map(hex_ids, lat=None, lng=None, raio_km=1.6, ...)` → `pdk.Deck | None` — hexes destacados do cenário multi-hex.

**Downsample — `_downsample_map_index(key_df, *, sort_columns, ascending, limit=MAP_POINT_LIMIT, dedup_column=None)`:** projeta um slice leve só com as chaves de ordenação/dedup, ordena de forma estável, deduplica (`drop_duplicates(keep="first")`) e faz `head(limit)`; retorna o `Index` dos sobreviventes para `df.loc[...]`. Isso evita copiar as colunas completas das UFs grandes (ex.: AM ~294k linhas) antes do corte.

**Caps e projeção de colunas:**
- `MAP_POINT_LIMIT = 35000` (cap global) e `MAP_POINT_LIMIT_LARGE = 18000` (cap reduzido
  para UFs grandes que saturam o cap — mitiga OOM client-side de WebGL/JS heap ao
  renderizar dezenas de milhares de hexes H3 em GPU).
- `MAP_SOURCE_COLUMNS_M1` / `MAP_SOURCE_COLUMNS_HYBRID` (em `constants`) — listas de
  colunas que cada modo materializa; os builders projetam por essas listas antes de montar
  o frame do mapa, só materializando colunas completas para os ≤cap sobreviventes.
- Pins têm caps duros próprios: `COMPETITOR_PIN_LIMIT`/`ULTRA_PIN_LIMIT = 6000`; em
  recortes amplos há clustering server-side de concorrentes (`COMPETITOR_CLUSTER_RES=4`,
  `COMPETITOR_CLUSTER_LIMIT=2000`).

**Serialização pydeck:** os hexágonos usam **`H3HexagonLayer`** (`get_hexagon="hex_id"`,
`get_fill_color`, `get_line_color`, `pickable`, `extruded=False`); os pins de concorrente/
Ultra usam **`IconLayer`** (icon atlas via `competitors`); pontos/círculos/clusters usam
**`ScatterplotLayer`**. O frame passado à layer é enxugado por um helper que projeta só
`hex_id`, `fill_color`, `line_color` e os `tooltip_*` presentes — não copia o `map_df`
inteiro para o payload. O `Deck` é montado com `map_style` CARTO dark, `ViewState`
(centro/zoom de `resolve_map_view`) e um `tooltip` HTML template. Em cap grande,
`stroked`/`auto_highlight` são desligados para reduzir vértices na GPU.

**Cores:** `score_band_to_color` (de `utils`) mapeia score 0-100 → RGBA em 10 faixas
(`RESIDUAL_SCORE_BANDS`). `_apply_pop_cut_colors` pinta de cinza (`_DISCARDED_FILL =
[150,150,170,150]`) os hexes descartados por `flag_pop_min_5k=False` quando
`show_discarded=True`; score NaN cai num fallback visível `_NAN_SCORE_FILL =
[110,116,140,150]` antes do corte (precedência BLK-FIX-06-C/FU1).

**Auxiliares:** `resolve_map_view(df, ...)` → `(center, zoom)` conforme escopo
(Brasil/UF/cidade); `build_map_scope_caption(...)` → legenda honesta de quantos pontos
foram usados e se houve amostragem/cap. Dezenas de `build_*_figure` (gráficos plotly/
altair) e `render_*_legend`.

**Dependências internas:** `competitors` (icon atlas/legendas), `constants`, `data`
(`haversine_km`, `_has_censo_signal`, `_normalized_join_quality`), `utils`.

### 3c. Camada de páginas — `dashboard/pages.py`

**Responsabilidade:** orquestrar o layout de cada aba, a sidebar/busca e os botões de
relatório; é o módulo mais extenso (~193 KB). Chama os builders de `components`, os
agregadores de `data` e os relatórios.

**Abas (`DASHBOARD_TAB_LABELS = ["Mapa", "Executivo", "Expansão de Domínio", "Carteira e Plano", "Viabilidade"]`):**
- `render_mapa_territorial(...)` — mapa unificado com seletor de modo de cor (M1/Híbrido/
  Censitário/Residual/Domínio) + overlays (concorrentes/Ultra/âncoras/descartados) +
  análise pontual por clique + relatório pontual censitário e municipal no expander.
- `render_visao_executiva(...)` — KPIs de rede, top UF/cidade, presença Ultra, residual por
  UF, comparativos.
- `render_expansao_dominio(...)` — plano de domínio (sequência de âncoras por cidade, teses).
- `render_carteira_e_plano(...)` — wrapper com sub-abas: `render_carteira_expansao` +
  `render_plano_expansao`.
- `render_viabilidade_ponto(...)` — stress-test de viabilidade de imóvel (break-even,
  aluguel-teto, ROI/payback, sensibilidade, projeção 60 meses) — usa
  `dimensionamento.viabilidade_ponto` e `dimensionamento.simulador`.

**Seletor de aba — `render_tab_selector(labels)`:** `st.segmented_control` + `session_state`
(chave `dashboard_active_tab_last`); devolve só o label da aba ativa (render lazy).

**Sidebar/busca:**
- `render_uf_selectbox(uf_catalog)` — seletor de UF antes da carga (gate da carga lazy).
- `render_sidebar_filters(df, uf)` — devolve 8-tupla: UFs, municípios, faixas,
  elegibilidade híbrida, buckets de cobertura, qualidade de join, `only_top_municipio`,
  `only_top_hex_intraurbano`.
- `render_coord_search_sidebar()` — aceita coordenada `lat,lng`, link do Google Maps e
  endereço livre. Cascata: `parse_coordinate_input` (numérico, offline, sempre primeiro) →
  link do Maps (`extract_any_coord` offline para URL longa; `resolve_short_link` HTTP para
  link curto) → Plus Code → endereço via `resolve_endereco_http` (Nominatim). Todos os
  helpers de rede vêm de `api.maps_geocoder` por **import lazy**, com fallback gracioso
  para link clicável (DEC-010/DEC-011 emendas). Valida bounding box do Brasil.

**Relatórios (botões de topo):**
- `render_pdf_download_topo(search_pin, df, ...)` — gera/baixa o PDF Pontual Censitário do
  ponto pesquisado sob demanda (chama `censo_report.gerar_payloads_download_relatorio_censitario`).
- `render_relatorio_pontual_lote(...)` — fila de endereços + geração em lote do Pontual.
- `render_relatorio_municipal_download_topo(df, ...)` — gera/baixa o PDF Municipal para 1
  ou N municípios selecionados (chama `relatorio_municipal`).
- `render_relatorio_pontual_censitario(...)` — no expander do Mapa Territorial.

**Fragment de mapa — `render_mapa_pydeck_fragment(...)`:** decorado com **`@st.fragment`**
(pages.py:4099). Renderiza o `st.pydeck_chart(..., on_select="rerun")` e captura o clique
(`_extract_click_coord_from_selection`), atualizando a coordenada no `session_state`.

**Dependências internas:** `components`, `data`, `constants`, `censo_map`, `censo_point`,
`censo_report`, `relatorio_municipal`, `competitors`, `utils`, `dimensionamento.{config,
simulador,viabilidade_ponto}`, e (lazy) `api.maps_geocoder`.

### 3d. Camada de relatórios — `dashboard/censo_report.py` e `dashboard/relatorio_municipal.py`

Ambos geram PDF com **fpdf2** (classe `_UltraPDF(FPDF)`, páginas 16:9 widescreen 960×540,
PDF 1.4, compressão OFF para auditabilidade anti-PII).

**Relatório Pontual Censitário — `censo_report.py`:**
- `gerar_pdf_relatorio_pontual_classico(result, mapas=None, *, residual=None, perfil_bairro=None, ultra_dir=None, solicitante=None, rotulo=None, now=None, fotos=None, info_imovel=None, viabilidade=None, foto_satelite=None, foto_satelite_grande=False) -> bytes` — **7 páginas**: Capa → Socioeconomia e Residual Fitness (BLK-RELPON-10) → Mapas de calor (**grid 2×2**: Densidade/Renda/Score/Renda média domiciliar, cada PNG embutido) → Concorrentes → Perfil do Bairro/Distrito (BLK-RELPON-07) → Big Numbers (grid 4×2 de 8 métricas) → Realização/Crédito. A página "Imagem do Entorno" (mapa de quadra, BLK-RELPON-11) foi **removida no BLK-RELPON-14** (8 → 7). Recebe os PNGs de mapa já compostos (por `mapas`), embute e adiciona marca d'água; não faz fetch de tiles aqui (os PNGs vêm de `censo_map`). As páginas OPCIONAIS (`fotos`, `info_imovel`, `viabilidade`) não alteram essa ordem base; com todas presentes o teto é 11. É a variante que o dashboard baixa e que a API/bot entrega e, desde o BLK-RELPON-14, o **gerador único**: `gerar_pdf_relatorio_pontual_censitario` é um wrapper fino depreciado (`DeprecationWarning`) que repassa os kwargs para esta.
- Público auxiliar: `gerar_csv_setores_censitarios`, `gerar_payloads_download_relatorio_censitario`, `render_downloads_relatorio_censitario`.
- Deps: `censo_point` (constante de método), `api.maps_geocoder` (`build_search_url`).

**Relatório Municipal — `relatorio_municipal.py`:**
- `gerar_pdf_relatorio_municipal(municipio_result, mapas=None, *, ultra_dir=None, solicitante=None, versao=None) -> bytes` — **9 páginas** (Capa/Potencial de Entrada, Visão Geral do Município, Resumo da Região, Score Censitário, Residual Fitness, Expansão de Domínio, Bairros por Zona, Síntese, Espaço e academias). São 9 exatas — `PDF_SECTION_HEADERS` tem 9 entradas e os testes travam `/Count 9`; o antigo "~8-9" era imprecisão.
- `_hex_destacado_mask(df_muni)` — destaque de hex = `oferta_efetiva_disponivel >= OFERTA_DESTAQUE_MIN (2000)` (SAM removido na emenda DEC-011/BLK-RELMUN-03). "Espaço para academias" = round(Σ oferta dos destacados ÷ 2.500 — `CAPACIDADE_UNIDADE`).
- Compõe os mapas com **contextily** (basemap CartoDB Voyager, tiles online, **import lazy**, cache em `data/cache/basemap_tiles/`, fallback offline gracioso — DEC-011) + Pillow + h3 (lazy).
- Deps: `competitors` (`_render_pin_tile`), `utils` (`score_band_to_color`).

**Dependências opcionais (extra `[basemap]`):** `contextily` é importado `try/except`
DENTRO da função de fundo — a carga/interatividade do dashboard nunca faz fetch; só a
geração dos mapas dos relatórios busca tiles, sob demanda (DEC-004/DEC-011). `fpdf2` é
dependência base. Ausência de assets/tiles → fallback de cor sólida/canvas claro.

### 3e. Camada de API — `src/motor_expansao/api/`

**Responsabilidade:** API FastAPI on-demand (bots Telegram/WhatsApp), **paralela ao
dashboard** e READ-ONLY sobre o M1. Não é dependência de runtime do dashboard.

- `main.py` — factory `create_app()`: FastAPI + CORS + handlers de erro + middleware de
  log; `GET /health` (e `/api/v1/health`); monta os routers sob `settings.api_prefix`.
- Rotas (`routes/`): `analisar.py` → `POST /api/v1/analisar` (`{lat,lng}`/link, JSON ou
  `?formato=pdf`); `analisar_municipio.py` → `GET /ufs`, `GET /municipios/{uf}`,
  `POST /analisar-municipio`.
- `service.py` — núcleo: resolve o ponto na malha municipal (`_resolver_e_carregar`),
  monta residual do ponto, `analisar_ponto`, `gerar_pdf_ponto` (reusa o motor censitário
  e os geradores de PDF), `listar_ufs`/`listar_municipios`/`resolver_municipio`,
  `gerar_pdf_municipio`.
- Suporte: `auth.py` (token por consumidor), `settings.py` (pydantic-settings),
  `coord.py`/`errors.py`/`geo.py`, `maps_geocoder.py` (geocoding urllib puro, também
  reusado pelo dashboard), `telegram_bot.py`.
- Deps só no extra `[api]` (`fastapi`/`uvicorn`/`pydantic`/`pydantic-settings`), fora do
  deploy base do Streamlit. **Importa, não edita** a camada `censo_*` (com extensão de
  parâmetros opcionais de render aprovada — DEC-005 emenda 2026-06-12).

## 4. Grafo de dependências (interno)

Direção: A → B significa "A importa B".

```
streamlit_app.py  (entry / hub)
  → data, components, pages, constants, schemas, utils,
    censo_map, censo_point, censo_report, competitors

pages.py  (hub de UI)
  → components, data, constants, utils,
    censo_map, censo_point, censo_report, relatorio_municipal, competitors,
    dimensionamento.{config, simulador, viabilidade_ponto},
    api.maps_geocoder (lazy)

components.py
  → competitors, constants, data, utils

data.py
  → constants, schemas, pipelines.pop_corte

relatorio_municipal.py
  → competitors, utils, (contextily/h3/PIL lazy)

censo_report.py
  → censo_point, api.maps_geocoder

censo_map.py
  → competitors, constants, utils, (contextily lazy)

censo_point.py, competitors.py, utils.py, constants.py, schemas.py, ui_theme.py
  → (folhas: sem deps de outros módulos do dashboard, ou só stdlib/terceiros)

api/  (paralelo)
  main → routes.{analisar, analisar_municipio} → service → censo_point/censo_map/
         censo_report/relatorio_municipal (importa, não edita) + geo/coord/auth/settings
```

**Folhas (sem deps internas do dashboard):** `constants.py`, `schemas.py`, `utils.py`,
`censo_point.py`, `competitors.py`, `ui_theme.py`. **Hubs:** `streamlit_app.py` (entry),
`pages.py` (orquestra tudo), `components.py` e `data.py` (consumidos amplamente).
`constants` e `utils` são as folhas mais reutilizadas.

## 5. Tamanho dos artefatos (disco e timing)

**Parquets consumidos pelo app (`du -sh`, 2026-07-08):**

| Artefato | Tamanho | Papel |
| --- | ---: | --- |
| `data/outputs/hexagonos_dashboard_enriquecido/` (particionado `uf=XX`) | 257 MB | **fonte principal do app** (carga lazy por UF) |
| `data/outputs/setores_censitarios_2022_geo/` (particionado uf/município) | 1,2 GB | malha IBGE geo dos relatórios (lazy por município) |
| `data/outputs/oportunidades_expansao_hibrido.parquet` | 109 MB | híbrido/censitário/residual (fallback do merge nacional) |
| `data/outputs/hexagonos_brasil_dashboard.parquet` | 47 MB | oficial M1 (base do merge; catálogo de UF de fallback) |
| `data/outputs/hexagonos_mapa_sample.parquet` | 15 MB | sample nacional legado (NÃO usado pelos builders atuais) |
| `data/outputs/plano_expansao_dominio.parquet` | 1,4 MB | Expansão de Domínio |
| `data/outputs/carteira_expansao_acionavel.parquet` | 600 KB | Carteira |
| `data/outputs/plano_expansao_curto_prazo.parquet` | 80 KB | Plano |
| `data/staging/brasil_estrutural.parquet` | 34 MB | `pop_total` para tooltip |
| `data/staging/censo2022_setores_calibrado*.parquet` | 11-83 MB | traço censitário (merge) |
| `data/staging/hexagonos_mercado_mapeado.parquet` | 204 MB | insumo da camada mercado/residual (pipeline, não carga direta) |

**Timing de carga por UF (BLK-REV-01, `read_enriched_uf_partition`, Python-side):**

| UF (tamanho) | hexes | t_frio (s) | t_quente (s) | pico RSS (MB) |
| --- | ---: | ---: | ---: | ---: |
| RO (pequena) | 46.455 | 0,996 | 0,673 | 329,7 |
| SC (média) | 20.373 | 0,446 | 0,382 | 342,3 |
| AM (grande) | 293.991 | 2,544 | 2,467 | 826,0 |

A carga lazy por UF substituiu o cold start NACIONAL do baseline de mai/2026 (dezenas de
segundos + RSS de centenas de MB para fundir o Brasil inteiro).

## 6. O que é cacheado vs. recomputado (tabela)

| Função | Cacheada? | Decorador | TTL | Custo típico (BLK-REV-01) |
| --- | --- | --- | --- | --- |
| `load_uf_catalog` | Sim | `@st.cache_data` | nenhum | trivial (lista diretórios) |
| `load_uf_slice(uf)` | Sim (por UF) | `@st.cache_resource` | nenhum | frio 0,4-2,5 s / UF; quente ~=frio |
| `build_dashboard_dataset` | Sim | `@st.cache_resource` | nenhum | só no fallback (merge nacional) |
| `load_data`/`load_hybrid_data`/`load_censo_trace_data`/`load_estrutural_pop` | Sim | `@st.cache_resource` | nenhum | insumos do merge (uso pontual/fallback) |
| `load_competitors`/`load_ultra`/`load_carteira`/`load_plano`/`load_plano_dominio` | Sim | `@st.cache_data` | nenhum | leve (KB-MB) |
| `load_censo_geo_municipios`/`load_censo_geo_setores` | Sim | `@st.cache_data` | nenhum | lazy por município (relatórios) |
| `load_base_calibracao` | Sim | `@st.cache_data` | nenhum | leve |
| `apply_global_filters` | **Não** | — | — | 0,003-0,006 s (barato) |
| `build_pop_cut_lookup` | **Não** | — | — | trivial |
| `build_city_summary`/`build_uf_summary` | **Não** (só se aba Executivo/Mapa) | — | — | groupby, barato |
| `build_map_figure` / `build_hybrid_map_figure` / `build_residual_heatmap_figure` | **Não** | — | — | **0,65-3,25 s por rerun** (custo integral: downsample+cap+color+tooltip) |
| `agregar_cenario_multihex` | **Não** | — | — | ~0,01-0,02 s |
| `gerar_pdf_relatorio_pontual_classico` (fpdf2, sem mapas) | **Não** (cacheia payload em session_state) | — | — | ~0,06-0,19 s (mapas PNG NÃO medidos) |
| `gerar_pdf_relatorio_municipal` (fpdf2, sem mapas) | **Não** | — | — | ~0,08-0,09 s (mapas PNG NÃO medidos) |

Observação: os builders de mapa são o **maior custo Python recorrente da interação**
(reexecutados a cada rerun). O render WebGL/paint no browser e o fetch de tiles dos PDFs
NÃO foram medidos (client-side / rede — fora do baseline).

## 7. Pontos de acoplamento e fragilidades

- **Contrato de colunas centralizado em `constants.py`:** `REQUIRED_COLUMNS`,
  `HYBRID_LOAD_COLS`, `CENSO_TRACE_LOAD_COLS`, `MAP_SOURCE_COLUMNS_M1/HYBRID`,
  `FLOAT/BOOL/TEXT_COLUMNS`. Mudar nome/tipo de coluna aqui reverbera em `data.py`
  (leitura/coerção), `components.py` (projeção/tooltip) e nos schemas. Coluna renomeada
  no pipeline sem atualizar essas listas quebra a carga (erro explícito em
  `_read_parquet_subset`) ou some silenciosamente do mapa.
- **`streamlit_app.py:main()` monta a árvore inteira:** a sidebar/busca, os botões de
  relatório de topo e o dispatch de abas dependem de `search_pin`/`search_hex_id`
  resolvidos ANTES do dispatch (comentado no código). Reordenar esses blocos pode deixar
  um consumidor sem `search_pin` definido. O `df` já está carregado (`load_uf_slice`) antes
  da busca, então a busca não depende dos filtros — mas `render_hex_search_result` usa
  `filtered_df`.
- **Dispatch por índice de `DASHBOARD_TAB_LABELS`:** os `if active_tab == tab_x` comparam
  contra `DASHBOARD_TAB_LABELS[i]`. Trocar a ordem/label sem ajustar os índices desalinha
  o dispatch. Os summaries só existem no branch `Executivo/Mapa` — chamar `render_*` de
  outra aba que espere `city_summary` quebraria (hoje não ocorre).
- **Caps de mapa e OOM client-side:** `MAP_POINT_LIMIT_LARGE`/pin caps existem justamente
  porque payloads pydeck grandes derrubam o browser (WebGL/JS heap). Aumentar caps sem
  medir reintroduz o risco. Busca por hex fora do recorte é lida do `df` completo (não do
  recorte capado), o que é intencional.
- **Fallback do merge nacional:** se a partição `uf=XX` do enriquecido não existir,
  `load_uf_slice` cai em `build_dashboard_dataset()` (merge nacional, caro). Um artefato
  particionado ausente/desatualizado degrada silenciosamente para o caminho lento.
- **Dependências opcionais de rede:** `contextily` (tiles dos relatórios) e
  `api.maps_geocoder` (geocoding da busca) são import lazy com fallback. Se o fallback
  quebrar, a interatividade offline do dashboard não pode ser afetada (guardrail §2).
- **`hexagonos_mapa_sample.parquet` (15 MB) é legado:** os builders atuais NÃO o usam
  (CLAUDE.md §4); remoção exigiria varredura para confirmar zero referências.

## 8. Decisões arquiteturais relevantes

- **Carga lazy por UF (Bloco 4, perf mai/2026):** o app lê só a partição `uf=XX` do
  dataset enriquecido em vez de fundir o Brasil inteiro a frio. Motivação: o cold start
  nacional (merge `enrich_dashboard_data` de ~600 MB de insumos) custava dezenas de
  segundos e RSS de centenas de MB. Com lazy, a carga cai para 0,4-2,5 s por UF (§5).
  Consequência: a busca por coordenada resolve dentro da UF carregada; catálogo leve de UF
  via diretórios de partição (`list_partitioned_ufs`).
- **Render lazy de abas (Bloco 5):** `render_tab_selector` (`st.segmented_control` +
  `session_state`) no lugar de `st.tabs`. Só o `render_*` da aba ativa roda por rerun,
  preservando a UX de abas. `build_city_summary`/`build_uf_summary` só computados nas abas
  que os consomem. Evita executar o corpo de todas as abas a cada interação.
- **Fonte de mapa enxuta com downsample (Bloco 6):** os builders fazem downsample ANTES do
  cap via `_downsample_map_index` (ordena/dedup/`head(N)` sobre projeção leve de chaves) e
  só materializam as colunas completas (`MAP_SOURCE_COLUMNS_*`) para os ≤cap sobreviventes.
  O frame da layer é enxugado a `hex_id`/cores/`tooltip_*`. Motivação: minimizar cópia de
  DataFrame e payload pydeck em UFs grandes, mantendo o mesmo top-N por prioridade. Não usa
  o sample nacional legado.
- **Extra `[basemap]` e `[api]` fora do deploy base:** `contextily` (tiles) e o stack
  FastAPI são extras opcionais, import lazy, com fallback — para não pesar/quebrar o deploy
  Streamlit e honrar o §2 (sem API ao vivo na carga do dashboard).
- **Fragment de mapa (`@st.fragment`):** isola o render + captura de clique do mapa para
  reduzir o custo do rerun disparado por interação no mapa.
