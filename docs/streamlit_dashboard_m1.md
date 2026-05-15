# Dashboard Executivo M1 + Hibrido no Streamlit

## Estrutura atual do app

- `Visao Executiva`: KPIs principais do M1, mapa do recorte atual, top cidades por score medio e top UFs por oportunidades viaveis.
- `Analise Territorial`: dispersao entre `renda_per_capita` e `populacao_proxy`, distribuicao de `score_priorizacao`, comparativo por `faixa_oportunidade` e indicadores medios.
- `Ranking e Priorizacao`: tabela executiva ordenada por `rank_brasil` com as colunas oficiais do M1.
- `Comparacao por UF`: oportunidades viaveis por UF, score medio por UF e comparativo entre top e bottom UFs.
- `Modelo Hibrido`: quatro subtabs executivas para `Oportunidades Hibridas`, `Ranking Intraurbano`, `M1 vs Censitario` e `Municipios + Melhores Hexes`.

## Fontes e governanca

- Base oficial preservada: `data/outputs/hexagonos_brasil_dashboard.parquet`
- Camada hibrida operacional: `data/outputs/oportunidades_expansao_hibrido.parquet`
- Camadas censitarias de apoio e rastreabilidade:
  - `data/staging/censo2022_setores_calibrado.parquet`
  - `data/staging/censo2022_setores_calibrado_piloto_expandido.parquet`
  - `data/staging/censo2022_setores_validado_v2.parquet`
- Concorrentes mapeados: CSVs locais em `concorrentes/`, carregados apenas como pins visuais nos mapas do dashboard.
- O app carrega a base oficial do M1 primeiro e depois faz apenas enriquecimento local com as colunas censitarias/hibridas.
- `score_priorizacao` continua sendo o score oficial de expansao.

## Como interpretar os modelos

- `M1 = decisao municipal`: usar `score_priorizacao`, `rank_municipio_uf` e `top_municipio` para decidir quais mercados entram na fila.
- `Censitario = decisao intraurbana`: usar `score_setor_2022_calibrado`, `rank_hex_intraurbano` e `top_hex_intraurbano` para escolher bairros e hexes dentro de municipios aprovados.
- `Hibrido = uso combinado`: usar `score_expansao_hibrido` e `top_oportunidade_municipio` para ordenar a carteira operacional sem substituir o M1.

## Filtros globais

- `UF`
- `Municipio`
- `Faixa de oportunidade`
- `Elegibilidade hibrida`
- `Cobertura censitaria`
- `Qualidade da camada`
- `Apenas top_municipio`
- `Apenas top_hex_intraurbano`

## KPIs executivos adicionais

- Municipios elegiveis no hibrido
- Hexes elegiveis
- Municipios cobertos pela camada censitaria
- Registros prontos para monitoramento
- Comparativo entre oportunidades M1 e oportunidades hibridas

## Rastreabilidade visual

- Hover do mapa intraurbano com `qualidade_join_uf`, `flag_join_uf_restrito`, `flag_baixa_pop_setor`, `flag_outlier_espacial`, `causa_outlier_espacial` e `coverage_pct_setor_2022`.
- Pins de concorrentes aparecem sobre os mapas quando as coordenadas validas dos CSVs caem no recorte geografico exibido.
- Tabelas executivas com flags de join restrito, baixa populacao e outlier espacial.
- Regra editorial: dado restrito ou de baixa confianca nao deve ser interpretado como evidencia forte isolada.

## Pins de concorrentes

- A camada usa `src/motor_expansao/dashboard/competitors.py` para ler e normalizar CSVs locais em `concorrentes/`.
- Smart Fit, Bluefit, Panobianco e Sky Fit aparecem como pins sobre a camada H3 nos mapas principal e hibrido.
- Os pins sao apoio visual de oferta mapeada; nao entram em `score_priorizacao`, `score_expansao_hibrido`, ranking, carteira ou plano.
- Cores/iniciais dos pins ficam em `COMPETITOR_BRANDS`.
- Imagens oficiais podem substituir o SVG gerado em `competitor_icon_data()`, mantendo `url`, `width`, `height` e `anchorY` no formato esperado pelo `pydeck.IconLayer`.
- Tamanho dos pins: ajustar `comp["icon_size"]`, `size_min_pixels` e `size_max_pixels` em `_build_competitor_icon_layer()` dentro de `src/motor_expansao/dashboard/components.py`.

## Pins das unidades Ultra

- Arquivo opcional: `data/ultra/Ultra.csv` (`sep=";"`, `encoding=latin-1`, 1 linha de metadado inicial).
- Loader: `load_ultra_points` em `src/motor_expansao/dashboard/competitors.py`; retorna DataFrame vazio se arquivo ausente ou sem colunas obrigatorias.
- Pin vermelho (#C8001E, sigla `UA`), tamanho 38px para distincao visual frente aos concorrentes.
- Layer `_build_ultra_icon_layer` empilhado apos concorrentes em `build_map_figure`/`build_hybrid_map_figure`.
- Legenda `render_ultra_legend` aparece somente quando `ultra_df` nao estiver vazio.
- Camada puramente visual: nao altera `score_priorizacao`, ranking, carteira ou plano.

## Busca por coordenada

- Widget na sidebar (`render_coord_search_sidebar`); formatos: `lat, lng` ou `lat lng`.
- `parse_coordinate_input` valida e converte; `lookup_hex_by_coord` encontra o `hex_id` H3 correspondente.
- Mapa centraliza no pin com zoom 10; pin de marcacao via `_build_search_pin_layer`.
- Hex pesquisado recebe `H3HexagonLayer` amarelo destacado (`_build_search_hex_layer`) — aparece mesmo fora dos filtros ou descartado.
- Card de detalhe `render_hex_search_result` exibe score, ranking, renda e populacao; avisa quando hex esta fora do recorte ou descartado pela regua 5k.
- Funciona 100% offline; nao altera score nem artefatos oficiais.

## Regua visual de populacao minima (5k hab)

- Constante: `POP_MIN_ACIONAVEL = 5_000` em `dashboard/constants.py`.
- Colunas derivadas em `enrich_dashboard_data`: `populacao_corte_hex`, `fonte_populacao_corte`, `flag_pop_min_5k`.
- Fonte preferencial: `pop_total_setor_2022` (UFs A/B); fallback: `populacao_proxy` (municipal).
- Mapas: hexes com `flag_pop_min_5k=False` recebem cor cinza `[120,120,140,70]`; legenda "Descartado <5k hab" via `render_pop_cut_legend`.
- Abas Carteira e Plano filtram esses hexes via lookup por `hex_id`.
- Tooltip do hex descartado exibe sufixo " — Descartado <5k hab".
- M1 (`score_priorizacao`, artefatos oficiais) nao e alterado.

## Performance e limites locais

- O app continua offline e usa apenas arquivos locais.
- O mapa limita a renderizacao aos hexes mais relevantes do recorte para manter fluidez.
- As tabelas continuam limitadas a `1.000` linhas por visao.

## Como rodar localmente

1. Instale as dependencias do projeto, se necessario: `python -m pip install -e .`
2. Garanta a presenca do dataset oficial do M1: `data/outputs/hexagonos_brasil_dashboard.parquet`
3. Garanta a presenca das camadas opcionais censitarias/hibridas, se quiser a visao completa
4. Execute: `streamlit run streamlit_app.py`

Sem as camadas censitarias/hibridas, as abas oficiais do M1 continuam funcionando.
