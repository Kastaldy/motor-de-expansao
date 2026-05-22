# Baseline de performance do dashboard

> Gerado por `scripts/profile_dashboard.py` em 2026-05-22.
> Reproduzir: `python scripts/profile_dashboard.py`. Mede a carga a frio dos loaders
> e do merge `enrich_dashboard_data`, sem alterar o runtime do app.

## Ambiente

- Python: 3.14.0 (Windows 11)
- pandas: 2.3.3
- Backend de memoria: psutil 7.1.1 (RSS do processo)
- RSS no import do app (baseline): 144.2 MB

## Insumos em disco

| artefato | tamanho (MB) | presente |
| --- | ---: | :---: |
| `data/outputs/hexagonos_brasil_dashboard.parquet` | 46.6 | sim |
| `data/outputs/oportunidades_expansao_hibrido.parquet` | 105.0 | sim |
| `data/staging/censo2022_setores_calibrado.parquet` | 10.5 | sim |
| `data/staging/censo2022_setores_calibrado_piloto_expandido.parquet` | 15.1 | sim |
| `data/staging/censo2022_setores_validado_v2.parquet` | 6.8 | sim |
| `data/staging/brasil_estrutural.parquet` | 33.7 | sim |

## Custo por etapa (cold start)

| etapa | linhas | tempo (s) | RSS antes (MB) | RSS depois (MB) | RSS delta (MB) |
| --- | ---: | ---: | ---: | ---: | ---: |
| `load_data` | 1_532_645 | 8.43 | 144.2 | 702.7 | 558.5 |
| `load_hybrid_data` | 1_532_645 | 28.06 | 702.7 | 662.1 | -40.6 |
| `load_censo_trace_data` | 280_874 | 2.24 | 662.1 | 760.6 | 98.5 |
| `load_estrutural_pop` | 1_532_645 | 1.42 | 760.6 | 865.0 | 104.4 |
| `enrich_dashboard_data` | 1_532_645 | 70.49 | 865.0 | 766.8 | -98.2 |
| **total** |  | **110.65** |  | **865.0** (pico) |  |

Frame enriquecido final: **1,532,645** linhas x **82** colunas, **449 MB** em memoria (`memory_usage(deep=True)`).

## Peso de memoria por UF (frame enriquecido, deep)

Ordenado por numero de hexagonos. O app hoje retem o frame nacional inteiro
mesmo exibindo 1 UF por vez; esta tabela dimensiona o ganho do carregamento lazy.

Nota: a soma por UF (TOTAL abaixo) excede o frame nacional (449 MB) porque fatiar por UF duplica o dicionario das colunas `category`; trate os valores por UF como teto superior do slice isolado, nao como fracao exata do frame unico.

| UF | hexagonos | memoria deep (MB) |
| --- | ---: | ---: |
| AM | 292,793 | 89.7 |
| PA | 213,997 | 66.1 |
| MT | 165,033 | 51.4 |
| MG | 104,078 | 33.2 |
| BA | 93,918 | 30.1 |
| MS | 69,344 | 22.8 |
| RS | 60,811 | 20.2 |
| GO | 59,952 | 20.0 |
| MA | 53,180 | 17.9 |
| SP | 47,139 | 16.1 |
| TO | 46,302 | 15.9 |
| RO | 45,962 | 15.8 |
| RR | 43,424 | 15.0 |
| PI | 40,869 | 14.3 |
| PR | 40,261 | 14.1 |
| AC | 28,370 | 10.5 |
| AP | 24,162 | 9.2 |
| CE | 23,975 | 9.2 |
| SC | 20,100 | 8.0 |
| PE | 16,013 | 6.8 |
| PB | 9,223 | 4.8 |
| RN | 8,555 | 4.6 |
| ES | 8,158 | 4.5 |
| RJ | 7,895 | 4.4 |
| AL | 4,544 | 3.4 |
| SE | 3,588 | 3.1 |
| DF | 999 | 2.3 |
| **TOTAL** | **1,532,645** | **513.3** |

## Bloco 2 — retencao de cache antes/depois (2026-05-22)

Mudanca: `build_dashboard_dataset` passou a ler e fundir via helpers nao-cacheados
(`_read_m1_frame`/`_read_hybrid_frame`/`_read_censo_trace_frame`/`_read_estrutural_pop_frame`).
Os insumos intermediarios viram locais liberados apos o merge; no caminho real do app
(`main` -> `build_dashboard_dataset`) os caches `load_data`/`load_hybrid_data`/
`load_censo_trace_data`/`load_estrutural_pop` ficam vazios (so chamados em testes/uso pontual).

Reproduzir (2 processos isolados): em cada um, `import streamlit_app`, `gc.collect()`, ler RSS via psutil,
executar o caminho e reler RSS.

| caminho | objetos vivos retidos (deep) | RSS pos-merge (MB) |
| --- | --- | ---: |
| antes (4 intermediarios + enriquecido cacheados) | intermediarios 768.2 + enriquecido 449.3 | 794.5 |
| depois (so enriquecido cacheado) | enriquecido 449.3 | 685.1 |

- Intermediarios deep medidos: M1 189.6 / hibrido 360.6 / censo 112.8 / estrutural 105.2 = **768.2 MB**.
- Ganho: **~768 MB de objetos vivos** deixam de ficar residentes apos o merge; RSS de estado estavel
  cai **~109 MB (~14%)** nesta maquina. O delta de RSS e menor que o peso dos objetos porque o
  alocador do processo nao devolve todas as paginas liberadas ao SO; o ganho pratico aparece sob
  pressao de memoria (paginas liberadas ficam disponiveis para reuso, em vez de crescer o RSS).
- O pico do cold build nao muda (o merge ainda toca os 4 insumos uma vez); o alvo do bloco e a
  retencao apos o merge, nao o pico. Tempo de build observado ~76s (Bloco 1 ~110s; variancia de cache de SO).

## Bloco 4 — carga lazy por UF (2026-05-22)

Mudanca: `main()` carrega apenas a UF selecionada. `load_uf_catalog` lista as particoes
`uf=XX` do dataset enriquecido (Bloco 3) sem ler dados (fallback: coluna `uf` do parquet oficial M1).
`load_uf_slice(uf)` le so a particao `uf=XX` via `read_enriched_uf_partition` (cache por UF) e
cai em `build_dashboard_dataset()` filtrado quando a particao nao existe. Nenhum score recalculado.

Reproduzir: `import streamlit_app`; ler RSS (psutil); `read_enriched_uf_partition(ENRIQUECIDO_DIR, uf)`
para AM/PA/SP medindo `memory_usage(deep=True)` e RSS apos cada carga isolada.

| UF | hexagonos | deep (MB) | RSS apos carga isolada (MB) |
| --- | ---: | ---: | ---: |
| AM (maior) | 292,793 | 90.0 | 439 |
| PA | 213,997 | 66.5 | 385 |
| SP | 47,139 | 15.5 | 256 |

- RSS no import: ~155 MB. A maior UF (AM) chega a ~439 MB de RSS, **abaixo do pico nacional ~865 MB** (Bloco 1)
  e ~5x menor em deep que o frame nacional (449 MB). UFs tipicas (ex.: SP ~15 MB) ficam muito abaixo.
- O caminho lazy nao funde o Brasil em runtime: a particao ja vem materializada (Bloco 3), entao a carga
  e uma leitura parquet + `_prepare_dataframe`, sem os ~70s do `enrich_dashboard_data` nacional.
- Limitacao registrada: a busca por coordenada agora resolve dentro da UF carregada; uma coordenada
  de outra UF cai no caminho "hex nao encontrado" ate trocar a UF na sidebar.

## Bloco 5 — render lazy das abas (2026-05-22)

Mudanca: `main()` deixou de usar `st.tabs` (que executa o corpo das 4 abas a cada rerun) e passou a
usar `render_tab_selector` (`st.segmented_control` com estado em `session_state`). So o `render_*`
da aba ativa e chamado por rerun; os summaries `build_city_summary`/`build_uf_summary` so sao
calculados para as abas que os consomem (Visao Executiva e Mapa Territorial). As funcoes `render_*`
ficaram intactas — muda apenas quando sao invocadas. Nenhum score recalculado.

Custo por interacao (estrutural, medido pelos testes de chamada):

| caminho | render_* construidos por rerun | summaries construidos |
| --- | ---: | --- |
| antes (`st.tabs`) | 4 de 4 (Visao + Mapa + Dominio + Carteira) | sempre city+uf |
| depois (selector) | 1 de 4 (apenas a aba ativa) | so na aba Visao/Mapa |

- Cada rerun (clique no mapa, filtro, troca de UF) deixou de reconstruir as 3 abas inativas. O ganho
  pratico e maior quando a aba ativa nao e o Mapa Territorial (a mais pesada: mapa unificado + camada
  multi-hex + expanders com detalhe hibrido), que antes era montada mesmo na aba Carteira ou Dominio.
- Validacao: `test_main_renderiza_apenas_a_aba_ativa` prova que apenas o renderer da aba ativa roda e
  que os summaries nao sao computados fora de Visao/Mapa; `test_render_tab_selector_*` cobrem selecao
  e fallback de desmarcacao. Suite: 507 passed, 1 skipped.
- Limitacao registrada: trocar de aba dispara um rerun (a aba escolhida e construida sob demanda); o
  estado de clique/cenario multi-hex persiste em `session_state`, entao a Analise Pontual e o cenario
  sobrevivem a troca de aba e ao retorno ao Mapa Territorial.

## Bloco 6 — fonte de mapa enxuta (downsample antes do cap) (2026-05-22)

Mudanca: os builders de mapa (`build_map_figure`, `build_hybrid_map_figure`,
`build_residual_heatmap_figure`) deixaram de copiar todas as colunas do mapa de toda a
UF antes de aplicar `MAP_POINT_LIMIT`. Agora o cap roda sobre uma projecao leve de chaves
(`_downsample_map_index`) e as colunas completas do mapa so sao materializadas para os
≤MAP_POINT_LIMIT sobreviventes. As listas de colunas viraram `MAP_SOURCE_COLUMNS_M1`/
`MAP_SOURCE_COLUMNS_HYBRID` em `dashboard/constants.py` (fonte unica de "colunas necessarias").
Sem regressao no cap: o mapa renderiza exatamente os mesmos top-MAP_POINT_LIMIT hexes por
prioridade (provado por `test_build_map_figure_downsample_mantem_exatamente_o_top_por_prioridade`).

Reproduzir: `read_enriched_uf_partition(ENRIQUECIDO_DIR, 'AM')` e comparar a copia antiga
(`df.loc[validez, MAP_SOURCE_COLUMNS_M1].copy()`, todas as linhas) com a nova fonte
(chave leve de todas as linhas + frame final ≤35k), medindo `memory_usage(deep=True)`.

| fonte do mapa (AM, 292.793 linhas validas, mapa M1) | memoria (MB) |
| --- | ---: |
| antes (copia de todas as linhas x 30 colunas, antes do cap) | 51.3 |
| depois (chave leve 9 cols x todas linhas) | 26.9 |
| depois (frame final ≤35k x 30 colunas) | 6.1 |
| **depois (total transitorio)** | **33.1** |

- Reducao da fonte do mapa na maior UF: **~18 MB (-35%)**; o ganho escala com o tamanho da UF
  (AM 293k, PA 214k, MT 165k) e e nulo nas UFs pequenas (ja abaixo do cap). O frame final de
  pydeck e identico ao anterior (mesmos hexes, mesma ordem) — o cap nao mudou.
- O pico durante a chamada inteira (`build_map_figure`) inclui a geracao de tooltips dos 35k
  hexes (inalterada) e domina o transitorio; o alvo do bloco e a fonte do mapa, nao o tooltip.
- Suite: 509 passed, 1 skipped (+2 testes: helper `_downsample_map_index` e paridade do cap M1).

## Bloco 7 — fechamento do ciclo: baseline vs pos-otimizacao (2026-05-22)

Consolidacao do ciclo `Performance e Refatoracao do Dashboard` (Blocos 1-6). A mudanca
estrutural: o app deixou de fundir o Brasil inteiro a frio para exibir 1 UF e passou a ler
apenas a particao materializada da UF selecionada, renderizando so a aba ativa. Nenhum score,
carteira, plano ou artefato oficial do M1 foi recalculado ou alterado no ciclo.

| dimensao | baseline (Bloco 1) | pos-otimizacao (Blocos 2-6) | ganho |
| --- | --- | --- | --- |
| caminho de carga | funde Brasil inteiro (1.532.645 linhas) em runtime | le so a particao `uf=XX` materializada (Bloco 3) | merge nacional sai do runtime do app |
| cold start (carga) | ~110s (inclui `enrich_dashboard_data` ~70s) | leitura parquet + `_prepare_dataframe` por UF | ~70s de merge nacional eliminados do app |
| RSS de pico (maior UF) | ~865 MB (frame nacional) | AM ~439 MB; SP ~256 MB | ~-49% na maior UF; muito maior nas tipicas |
| frame em memoria (deep) | 449 MB (nacional) | AM ~90 MB; SP ~15 MB | ~5x menor na maior UF |
| retencao pos-merge | intermediarios 768 MB + enriquecido 449 MB cacheados | so o enriquecido cacheado | ~768 MB de intermediarios liberados; RSS estavel -14% |
| abas por rerun | 4 de 4 (`st.tabs`) | 1 de 4 (selector + `session_state`) | 3 abas inativas deixam de ser montadas |
| fonte do mapa (maior UF) | 51.3 MB (todas as linhas x 30 cols) | 33.1 MB (chave leve + ≤35k final) | ~-35% |

- A materializacao offline do dataset particionado (Bloco 3) custa ~85s, roda 1x no pipeline de
  export e nao entra no caminho do app; em troca, cada carga de UF no dashboard vira uma leitura
  de parquet ja pronta. Os tempos sao snapshot desta maquina (variam com cache de SO), nao SLA.
- Limitacoes herdadas do ciclo (registradas nos blocos): busca por coordenada resolve dentro da
  UF carregada; trocar de aba dispara um rerun (estado persiste em `session_state`); UFs pequenas
  ja abaixo do cap `MAP_POINT_LIMIT` nao ganham com o downsample do mapa.
- Suite no fechamento: 509 passed, 1 skipped.

