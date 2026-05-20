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
- Coordenada copiavel em formato `lat,lng` para Google Maps.
- Funcao principal: `analisar_entorno_ponto(lat, lng, df, raio_km=1.6)` em `data.py`; nao muta os DataFrames de entrada.
- Tabela de entorno exibe populacao/renda usadas por hex; sem concorrentes ou Ultra no raio, o app mostra estado vazio discreto.

**Captura por clique — decisao tecnica (Bloco 12 concluido):**
- `st.pydeck_chart(..., on_select="rerun", key="main_unified_map")` captura selecao de objeto de camada.
- `_extract_click_coord_from_selection(event)` extrai `lat`/`lng` do centroide do hex selecionado.
- **Decisao: manter `st.pydeck_chart` com centroide.** `streamlit-folium` (+2 deps, visual inconsistente) e componente customizado (JS/React, fora de escopo) foram descartados.
- Clique em espaco vazio nao dispara evento; botao direito nao suportado.
- Nota visual exibida quando clique ativo: `"centroide do hex selecionado. Para coordenada exata, use lat,lng na barra lateral."`.
- Fallback: campo `lat,lng` na sidebar permanece o caminho padrao para precisao exata.

---

## Expansao de Dominio

Visualizacao das ancoras de expansao sequencial com mapa H3 de tese e ordem.

---

## Carteira e Plano

Tabelas operacionais filtradas pela regua <5k hab. Ordenacao por `rank_brasil` (M1) seguida de hibrido.

---

## Fontes e governanca

| arquivo | uso | obrigatoriedade |
| --- | --- | --- |
| `data/outputs/hexagonos_brasil_dashboard.parquet` | base M1 oficial | obrigatorio |
| `data/outputs/oportunidades_expansao_hibrido.parquet` | hibrido/censitario/residual | obrigatorio no app atual |
| `data/outputs/carteira_expansao_acionavel.parquet` | carteira operacional | recomendado |
| `data/outputs/plano_expansao_curto_prazo.parquet` | plano curto prazo | recomendado |
| `data/outputs/plano_expansao_dominio.parquet` | modo dominio e ancoras | recomendado |
| `data/ultra/Ultra.csv` | pins Ultra e KPIs de rede | opcional |
| `concorrentes/*.csv` | pins de concorrentes | opcional |

- `score_priorizacao` e o score oficial; nenhuma aba ou interacao altera esse valor.
- App funciona 100% offline com Parquets locais.
- Loaders criticos usam `@st.cache_resource`; overlays leves usam `@st.cache_data`.
- `MAP_POINT_LIMIT = 35.000` aplicado antes do tooltip em todos os builders de mapa.

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
3. Analise pontual usa centroides de hexes H3 como proxy de localizacao; sem geometrias de setor/rua, a leitura e aproximada.
4. Sem as camadas hibrido/censitario, modos `hibrido`, `censitario` e `residual` exibem aviso de indisponibilidade.
