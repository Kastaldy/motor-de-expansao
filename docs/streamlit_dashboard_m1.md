> **[HISTORICO]** Descreve o dashboard de 4 abas (maio/2026). O app atual tem 5 abas — ver o canonico `docs/arquitetura_app_atual.md`.

# Dashboard Executivo M1 + Hibrido no Streamlit

## Estrutura de abas

```
Visao Executiva | Mapa Territorial | Expansao de Dominio | Carteira e Plano
```

---

## Visao Executiva

Aba institucional da rede Ultra e panorama de mercado. **Nao renderiza hexagonos nem heatmap.**

**Conteudo:**
- 4 KPIs do M1: oportunidades viaveis, hexagonos priorizados, UF e cidade lideres.
- Cards de negocio: onde expandir, o que priorizar, onde evitar.
- Mapa Ultra-only (`build_ultra_presence_map`): somente pins das unidades proprias, sem H3HexagonLayer. Filtrado por UF/cidade. Estado vazio quando `data/ultra/Ultra.csv` ausente.
- 6 KPIs de rede e mercado: unidades Ultra no recorte, cidades com Ultra, score medio M1, residual total, oportunidades sem Ultra proxima, ancoras de dominio.
- 3 graficos: residual por UF, distribuicao de `score_oportunidade_residual`, top cidades com alto residual e baixa presenca Ultra.
- Graficos comparativos por UF: top cidades e top UFs por score.

**Guardrail:** nenhuma interacao nesta aba altera `score_priorizacao`, ranking, carteira, plano ou artefatos oficiais do M1.

---

## Mapa Territorial

Mapa unificado com modos de cor selecionaveis. Mantém todos os modos ativos do ciclo anterior.

**Modos de cor:**
| modo | score base | quando disponivel |
| --- | --- | --- |
| `m1` | `score_priorizacao` / `faixa_oportunidade` | sempre |
| `hibrido` | `score_expansao_hibrido` | quando `oportunidades_expansao_hibrido.parquet` carregado |
| `censitario` | `score_setor_2022_calibrado` | quando dado granular disponivel |
| `residual` | `score_oportunidade_residual` | quando coluna presente no dataset hibrido |
| `dominio` | `tese_dominio` + `ordem_expansao_cidade` | quando `plano_expansao_dominio.parquet` carregado |

**Regra visual canonica (Bloco 9 em diante):** todos os modos quantitativos usam faixas de 10 pontos via `RESIDUAL_SCORE_BANDS`:

| modo | score-fonte |
| --- | --- |
| M1 | `score_priorizacao` |
| Censitario | `score_setor_2022_calibrado` |
| Hibrido | `score_expansao_hibrido` |
| Residual | `score_oportunidade_residual` |

`faixa_oportunidade` continua util para filtros e tooltip no modo M1, mas a cor deve ser derivada de `score_priorizacao`. Modo Hibrido nao herda `score_oportunidade_residual` automaticamente. Padronizacao visual nao altera scores nem artefatos oficiais.

**Overlays:** concorrentes, Ultra, hex pesquisado, descartados <5k hab.

**Analise Pontual de Entorno** (expander ao fim da aba):
- Ativada automaticamente quando ha coordenada na session_state (`click_coord` ou busca da sidebar).
- Raio default `1.6 km` (~8.04 km2 = pi*1.6^2); leitura por centroide documentada como aproximada.
- Mapa com hexes no raio, circulo laranja, ponto central rosa e `IconLayer` para concorrentes/Ultra filtrados por raio quando existirem.
- KPIs: hexes no raio, populacao, renda per capita media, residual total, score residual medio, score M1 medio, concorrentes e Ultra.
- Quando colunas de consumo presentes no dataset: exibe `consumo_concorrentes_raio` e `consumo_ultra_raio` agregados dos hexes no raio, mais `consumo total instalado`. Leitura de mercado — nao score oficial.
- Coordenada copiavel em formato `lat,lng` para Google Maps.
- Funcao principal: `analisar_entorno_ponto(lat, lng, df, raio_km=1.6)` em `data.py`; nao muta os DataFrames de entrada.
- Tabela de entorno exibe populacao/renda usadas por hex e colunas de consumo fitness quando presentes; sem concorrentes ou Ultra no raio, o app mostra estado vazio discreto.

**Captura por clique — decisao tecnica (Bloco 12 concluido):**
- `st.pydeck_chart(..., on_select="rerun", key="main_unified_map")` captura selecao de objeto de camada.
- `_extract_click_coord_from_selection(event)` extrai `lat`/`lng` do centroide do hex selecionado.
- **Decisao: manter `st.pydeck_chart` com centroide.** `streamlit-folium` (+2 deps, visual inconsistente) e componente customizado (JS/React, fora de escopo) foram descartados.
- Clique em espaco vazio nao dispara evento; botao direito nao suportado.
- Nota visual exibida quando clique ativo: `"centroide do hex selecionado. Para coordenada exata, use lat,lng na barra lateral."`.
- Fallback: campo `lat,lng` na sidebar permanece o caminho padrao para precisao exata.

**Relatorio Pontual Censitario 1.5 km** (expander ao fim da aba):
- Complementar a Analise Pontual H3; usa setores censitarios reais, nao hexagonos.
- Ativado pela coordenada ativa do clique ou da busca da sidebar; raio fixo `1.5 km`.
- Carga lazy/cacheada por `uf` e `cod_municipio` via `load_censo_geo_setores` e `read_censo_geo_partition`.
- Base esperada: `data/outputs/setores_censitarios_2022_geo/uf=XX/cod_municipio=NNNNNNN/part-000.parquet`.
- Metodo canonico: `setor_censitario_intersecao_area_1p5km`, com intersecao real setor x circulo em CRS metrico local e ponderacao por area/populacao.
- Exibe KPIs, mapa PNG offline (`render_mapa_censitario_estatico_png`), tabela de setores intersectados e downloads CSV/PDF em memoria.
- Sem base municipal, mostra mensagem clara e nao tenta carregar shapefile nacional.
- Guardrail: nao recalcula `score_priorizacao`, carteira, plano, plano dominio nem artefatos oficiais do M1.

**Cenario Multi-Hex (Bloco 14+):**
- Selecao multi-hex e estado de UI/session_state; nao altera artefatos M1.
- Usuario adiciona/remove hexes via clique ou cola de lista de `hex_id`; hexes selecionados recebem camada visual propria sem mudar cores dos modos M1/Censitario/Hibrido/Residual/Dominio.
- Agregacoes do cenario:
  - `populacao`: soma de `pop_total_setor_2022` (fallback `populacao_proxy`).
  - `renda per capita`: media ponderada por populacao.
  - `residual` (`oferta_efetiva_disponivel`): soma.
  - consumo fitness instalado (concorrentes, Ultra, total): soma quando colunas presentes.
  - `n_concorrentes_hex`: soma; presenca Ultra: OR sobre os hexes.
  - scores (M1, censitario, hibrido, residual, dominio): media ponderada por populacao; maximo exibido quando util para tese.
- Colunas de consumo consultadas quando presentes: `oferta_consumida_mercado_estimada`, `oferta_consumida_ultra_real`, `oferta_consumida_total_estimada`, `n_concorrentes_hex`, `flag_canibalizacao_ultra_1km`.
- Quando coluna ausente no artefato, exibir `-` sem quebrar o app.

---

## Expansao de Dominio

Visualizacao das ancoras de expansao sequencial com mapa H3 de tese e ordem. Tabela inclui `Consumo Conc. (est.)` e `Consumo Ultra (real)` quando colunas presentes no artefato — leitura de mercado, nao score oficial.

---

## Carteira e Plano

Tabelas operacionais filtradas pela regua <5k hab. Ordenacao por `rank_brasil` (M1) seguida de hibrido. Colunas `Consumo Conc. (est.)` e `Consumo Ultra (real)` aparecem quando presentes no artefato — leitura de mercado, nao score oficial.

**Semantica padrao de consumo fitness:**
- `Consumo Conc. (est.)` = `oferta_consumida_mercado_estimada`: alunos estimados em concorrentes no hex (estimativa de demanda ocupada).
- `Consumo Ultra (real)` = `oferta_consumida_ultra_real`: alunos reais nas unidades Ultra no hex.
- `Consumo Total Instalado` = soma dos dois acima; exibido nos KPIs agregados do cenario multi-hex e na analise pontual.

---

## Fontes e governanca

| arquivo | uso | obrigatoriedade |
| --- | --- | --- |
| `data/outputs/hexagonos_brasil_dashboard.parquet` | base M1 oficial | obrigatorio |
| `data/outputs/oportunidades_expansao_hibrido.parquet` | hibrido/censitario/residual | obrigatorio no app atual |
| `data/outputs/carteira_expansao_acionavel.parquet` | carteira operacional | recomendado |
| `data/outputs/plano_expansao_curto_prazo.parquet` | plano curto prazo | recomendado |
| `data/outputs/plano_expansao_dominio.parquet` | modo dominio e ancoras | recomendado |
| `data/outputs/setores_censitarios_2022_geo/uf=XX/cod_municipio=NNNNNNN/part-000.parquet` | relatorio pontual censitario | opcional por municipio |
| `data/ultra/Ultra.csv` | pins Ultra e KPIs de rede | opcional |
| `concorrentes/*.csv` | pins de concorrentes | opcional |

- `score_priorizacao` e o score oficial; nenhuma aba ou interacao altera esse valor.
- App funciona 100% offline com Parquets locais.
- Loaders criticos usam `@st.cache_resource`; overlays leves usam `@st.cache_data`.
- `MAP_POINT_LIMIT = 35.000` aplicado antes do tooltip em todos os builders de mapa.
- Cap efetivo dinamico (BLK-FIX-03): nos 3 builders quantitativos (M1/hibrido/residual), recortes
  cujo numero de hexes candidatos satura `MAP_POINT_LIMIT` (UFs grandes: SP/AM/PA/MT/MG/BA) caem no cap
  reduzido `MAP_POINT_LIMIT_LARGE = 18.000` (mitiga OOM client-side / JS heap+WebGL ao renderizar ~35k
  hexagonos H3 em GPU); nesse modo a camada simplifica (`auto_highlight=False`/`stroked=False`). Recortes
  com `<= MAP_POINT_LIMIT` hexes ficam byte-identicos ao comportamento anterior (cap cheio). Nao altera
  `score_priorizacao`/`MAP_POINT_LIMIT` global/regra de cor; o caption "capped" exibe o cap efetivo aplicado.

---

## Filtros globais (sidebar)

- UF, Municipio, Faixa de oportunidade, Elegibilidade hibrida, Cobertura censitaria, Qualidade da camada, apenas `top_municipio`, apenas `top_hex_intraurbano`.

## Busca por coordenada

- Widget `render_coord_search_sidebar`; formatos: `lat, lng` ou `lat lng`.
- `parse_coordinate_input` valida e converte; `lookup_hex_by_coord` encontra o `hex_id` H3.
- Mapa centraliza com zoom 10; hex pesquisado recebe destaque amarelo.
- Card de detalhe com score, ranking, renda e populacao.
- Coordenada da busca alimenta automaticamente a Analise Pontual de Entorno.

## Pins de concorrentes

- CSVs em `concorrentes/`; loader em `src/motor_expansao/dashboard/competitors.py`.
- Camada puramente visual: nao altera scores, ranking nem artefatos oficiais.
- Cores/iniciais em `COMPETITOR_BRANDS`.

### Atlas de icones e cap de render (BLK-FIX-07 Fase A)

- O logo de cada rede (e da Ultra) entra no mapa via **atlas de icone unico** por recorte
  (`build_icon_atlas(redes)` em `competitors.py`), nao mais como data-URI base64 repetida por
  linha. Cada ponto da `IconLayer` carrega so a chave (`rede` / `__ultra__`) em `get_icon`; o
  atlas + `iconMapping` ficam em nivel de layer. Logos 100% preservados; payload por linha
  ~3x menor (1.381 pins SP: de ~7 MB para ~0,5 MB; cap de 6.000 fica em ~2 MB independente do
  total de pins). Atlas cacheado por `frozenset` de redes (`_ATLAS_CACHE`).
- **Pitfall pydeck:** uma data-URI base64 passada direta em `icon_atlas` vira acessor invalido
  (`@@=...`) porque `pydeck.types.Image.validate` rejeita data-URIs. Workaround: passar o atlas
  entre aspas (`icon_atlas='"'+atlas+'"'`). Trava de regressao no teste
  `test_icon_atlas_nao_vira_expressao_pydeck`.
- **Cap duro de render:** `COMPETITOR_PIN_LIMIT = 6000` / `ULTRA_PIN_LIMIT = 6000` em
  `constants.py` limitam o numero de pins por camada (amostragem deterministica: ordenacao
  estavel + `head(N)`), garantindo o bound de ~40k concorrentes sem OOM client-side. Quando o
  recorte excede o cap, o Mapa Territorial exibe um caption "amostrado"
  (`count_pins_in_scope`/`pins_amostrados_caption`) deixando claro que e **limite de render**:
  nao afeta score, ranking nem carteira. Refine o filtro de municipio para ver todos os pins.

## Pins das unidades Ultra

- Arquivo: `data/ultra/Ultra.csv` (`sep=";"`, `encoding=latin-1`, 1 linha de metadado).
- Pin vermelho (#C8001E, sigla `UA`), 38px; empilhado apos concorrentes.
- `load_ultra_points` retorna DataFrame vazio se arquivo ausente.

## Regua visual <5k hab

- `POP_MIN_ACIONAVEL = 5_000` em `dashboard/constants.py`.
- Fonte: `pop_total_setor_2022` (UFs A/B) ou `populacao_proxy` como fallback.
- Hexes descartados recebem cor cinza `[120,120,140,70]` nos mapas.
- Abas Carteira e Plano filtram esses hexes via lookup por `hex_id`.

## Limitacoes tecnicas conhecidas

1. Clique no mapa funciona apenas em objetos de camada; espaco vazio nao dispara evento.
2. Botao direito nao e suportado pelo `st.pydeck_chart`.
3. Analise pontual H3 e selecao multi-hex usam centroides de hexes H3 como proxy de localizacao; sem geometrias de setor/rua, a leitura e aproximada.
4. Sem as camadas hibrido/censitario, modos `hibrido`, `censitario` e `residual` exibem aviso de indisponibilidade.
5. Colunas de consumo fitness (`oferta_consumida_mercado_estimada`, `oferta_consumida_ultra_real`) e dominio hibrido (`score_setor_2022_calibrado`) sao opcionais por artefato; exibem `-` quando ausentes no Parquet carregado.
6. Cobertura censitaria parcial: UFs com `qualidade_join_uf=C` (AM, RR e outras) sao filtradas pelo modelo hibrido; score censitario nao disponivel para esses hexes.
7. Relatorio Pontual Censitario depende do artefato geo municipal materializado; a distribuicao intrassetor e aproximada por area e nao promete precisao de rua, lote ou quadra.
