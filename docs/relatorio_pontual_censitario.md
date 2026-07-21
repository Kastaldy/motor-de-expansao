# Contrato: Relatorio Pontual Censitario 1.5 km

> Contrato tecnico do ciclo `Relatorio Pontual Censitario 1.5 km`.
> Versao: 2026-05-22.

## 1. Objetivo

Criar uma analise pontual complementar ao H3 atual, usando geometria real de setores censitarios IBGE 2022 e intersecao geometrica com um circulo de raio fixo `1.5 km` ao redor de uma coordenada.

Esta feature permanece no dashboard Streamlit atual, com carregamento lazy/cacheado de artefatos locais otimizados. Nao cria API obrigatoria, nao depende de internet em producao e nao substitui a Analise Pontual H3 nem qualquer decisao do M1 oficial.

## 2. Entradas inventariadas

### Malha de setores

| item | valor |
| --- | --- |
| Arquivo | `data/raw/CENSO 2022/BR_setores_CD2022/BR_setores_CD2022.shp` |
| Componentes presentes | `.shp`, `.dbf`, `.shx`, `.prj`, `.cpg` |
| Tamanho principal | `.shp` ~1.25 GB; `.dbf` ~988 MB |
| Features | 468.099 setores |
| CRS | `EPSG:4674` |
| Geometria amostrada | `Polygon` |

Colunas confirmadas na malha: `CD_SETOR`, `SITUACAO`, `CD_SIT`, `CD_TIPO`, `AREA_KM2`, `CD_REGIAO`, `NM_REGIAO`, `CD_UF`, `NM_UF`, `CD_MUN`, `NM_MUN`, `CD_DIST`, `NM_DIST`, `CD_SUBDIST`, `NM_SUBDIST`, `CD_BAIRRO`, `NM_BAIRRO`, `CD_NU`, `NM_NU`, `CD_FCU`, `NM_FCU`, `CD_AGLOM`, `NM_AGLOM`, `CD_RGINT`, `NM_RGINT`, `CD_RGI`, `NM_RGI`, `CD_CONCURB`, `NM_CONCURB`, `geometry`.

### CSV Basico

| item | valor |
| --- | --- |
| Arquivo | `data/raw/CENSO 2022/Agregados_por_setores_basico_BR_20250417/Agregados_por_setores_basico_BR_20250417.csv` |
| Encoding confirmado | `latin-1` |
| Separador | `;` |
| Linhas | 468.099 |
| Colunas | 36 |

Colunas essenciais confirmadas: `CD_SETOR`, `CD_UF`, `CD_MUN`, `AREA_KM2`, `v0001`, `v0002`, `v0005`, `v0007`.

Semantica canonica:
- `v0001`: populacao total do setor, usar como `pop_total_setor_2022`.
- `v0002`: total de domicilios, nao usar como populacao.
- `v0005`: media de moradores, usar como apoio para renda per capita quando necessario.
- `v0007`: domicilios particulares ocupados, apoio para consistencia.

### CSV renda responsavel

| item | valor |
| --- | --- |
| Arquivo | `data/raw/CENSO 2022/Agregados_por_setores_renda_responsavel_BR_csv/Agregados_por_setores_renda_responsavel_BR.csv` |
| Encoding confirmado | `utf-8-sig` na amostra; codigo legado tambem tolera `latin-1` |
| Separador | `;` |
| Linhas | 458.772 |
| Colunas | 6 |

Colunas confirmadas: `CD_SETOR`, `V06001`, `V06002`, `V06003`, `V06004`, `V06005`.

Uso recomendado:
- `V06004`: rendimento medio mensal do responsavel, proxy de renda a calibrar.
- `V06001`: quantidade de domicilios/responsaveis com renda, apoio para totalizacao.
- `V06005`: manter apenas como campo auditavel; o pipeline atual evita usa-lo como renda principal por inconsistencias de escala.

### Parquets censitarios atuais

Arquivos confirmados:
- `data/staging/censo2022_setores_h3_res7.parquet`: 114.986 linhas, 22 colunas.
- `data/staging/censo2022_setores_validado_v2.parquet`: 114.986 linhas, 41 colunas.
- `data/staging/censo2022_setores_calibrado.parquet`: 114.986 linhas, 54 colunas.
- `data/staging/censo2022_setores_calibrado_nacional_completo.parquet`: 1.251.771 linhas, 50 colunas.
- `data/outputs/oportunidades_expansao_hibrido.parquet`: 1.532.645 linhas, 82 colunas.

Colunas censitarias uteis ja existentes: `hex_id`, `lat`, `lng`, `uf`, `cod_municipio`, `nome_municipio`, `pop_total_setor_2022`, `renda_per_capita_setor_2022`, `renda_per_capita_setor_2022_calibrada`, `coverage_pct_setor_2022`, `qualidade_join_uf`, `flag_baixa_pop_setor`, `densidade_pop_setor_hab_km2`, `score_setor_2022_calibrado`.

Confirmacao importante: esses Parquets sao agregados por H3/hex e nao possuem `geometry` nem geometria serializada. Eles servem para rastreabilidade e fallback, mas nao bastam para intersecao real setor x circulo.

## 3. Saidas esperadas

O subsistema deve retornar, sob demanda:
- KPIs do ponto: populacao estimada no raio, renda ponderada, densidade, score censitario medio/maximo, numero de setores intersectados, area analisada e flags de qualidade.
- Tabela de setores intersectados com pesos de area e metricas ponderadas.
- Mapa estatico PNG com setores, circulo de 1.5 km, ponto central e pins opcionais de concorrentes/Ultra.
- CSV da tabela de setores.
- PDF executivo com metodologia, qualidade e limitacoes.

Nenhuma saida deve recalcular ou alterar `score_priorizacao`, `hex_score_estrutural`, carteira, plano curto prazo, plano dominio ou artefatos oficiais do M1.

**BLK-RELPON-05:** alem dos agregados ponderados do raio, `result` expoe 5 campos com o valor BRUTO do setor censitario que CONTEM o ponto pesquisado (nao o agregado do raio nem valor por hex): `cod_setor_ponto`, `renda_per_capita_setor_ponto`, `densidade_pop_setor_ponto`, `score_setor_2022_calibrado_ponto` e `flag_setor_ponto_encontrado`. Quando o ponto cai fora de qualquer setor da malha (agua/orla, setor com geometria invalida), os 5 campos ficam `None`/`False`. Esses 5 campos permanecem no `result` para CSV/auditoria; **a partir do BLK-RELPON-06 eles NAO alimentam mais a faixa superior do mapa** (ver `densidade_pop_raio_valida_hab_km2` abaixo e §6).

**BLK-RELPON-06 (D1, reverte a fonte da faixa do BLK-RELPON-05):** `result` expoe tambem `densidade_pop_raio_valida_hab_km2` = `pop_total_raio / (area_intersecao_total_m2 / 1e6)` -- populacao do RAIO dividida pela area de espaco VALIDO (soma das areas de intersecao dos setores IBGE com o circulo; o IBGE nao cobre agua/vazio). Diferente de `densidade_pop_raio_hab_km2` (divide por `pi*raio_km**2` FIXO, incluindo agua/vazio dentro do circulo -- subestima a densidade em pontos com rio/mar no raio, ex.: Rio Branco/AC). `None` ("n/d" no display) quando nao ha setores intersectados ou a area valida e 0. Os 3 mapas choropleth (Densidade/Renda/Score) passam a exibir os agregados do RAIO numa faixa superior ("Renda no raio: R$ 3.321", "Densidade no raio: 678 hab/km2", "Score no raio: 70"; "n/d" quando nao ha setores/area valida); a camada Concorrentes e Ultra fica byte-a-byte igual (sem faixa).

**BLK-RELPON-08 (novo campo `domicilios_total_raio`):** `result` expoe tambem `domicilios_total_raio` -- soma de `domicilios_particulares_ocupados_setor_2022 * peso_area_setor` sobre os setores intersectados ao circulo de 1.5 km, EXATAMENTE o mesmo padrao de peso de area de `pop_total_raio` (nao a coluna `domicilios_total` do BLK-RELPON-07, que agrega por bairro/distrito, escopo diferente). `None` ("n/d") quando nenhum setor intersectado tem a coluna de domicilios. Nao persistido como coluna em `setores_intersectados`/CSV auditavel -- so o agregado do raio.

## 4. Colunas canonicas do artefato geo

O Bloco 2 deve materializar um artefato local otimizado, preferencialmente particionado por `uf` e `cod_municipio`, com estas colunas minimas:

| coluna | origem/regra |
| --- | --- |
| `cod_setor` | `CD_SETOR` normalizado como string de 15 digitos |
| `uf` | sigla derivada de `CD_UF` |
| `cod_uf` | `CD_UF` |
| `cod_municipio` | `CD_MUN` |
| `nome_municipio` | `NM_MUN` |
| `situacao_setor` | `SITUACAO` |
| `area_setor_km2_ibge` | `AREA_KM2` da malha/CSV |
| `geometry` ou `geometry_wkb` | geometria real do setor |
| `crs_origem` | `EPSG:4674` |
| `pop_total_setor_2022` | `v0001` do Basico |
| `renda_per_capita_setor_2022` | proxy derivada de `V06004`, calibravel |
| `renda_per_capita_setor_2022_calibrada` | valor calibrado quando disponivel |
| `score_setor_2022_calibrado` | score operacional paralelo, quando disponivel |
| `densidade_pop_setor_hab_km2` | populacao / area metrificada |
| `bbox_minx`, `bbox_miny`, `bbox_maxx`, `bbox_maxy` | bbox para recorte rapido |
| `flag_renda_disponivel` | renda valida no setor |
| `flag_geometria_valida` | geometria presente e valida |
| `qualidade_join_uf` | qualidade herdada quando houver join com Parquets atuais |

**BLK-RELPON-07:** `cod_bairro`/`nome_bairro`/`nome_subdistrito`/`nome_distrito`, `domicilios_particulares_ocupados_setor_2022`, `renda_responsavel_media_setor_2022` e `area_setor_m2` ja existem no artefato geo (confirmados em `COLUNAS_ARTEFATO`, `materializar_setores_censitarios_geo.py`) mesmo nao estando na tabela "minima" acima; o BLK-RELPON-07 e o primeiro consumidor de `cod_bairro`/`nome_bairro`/`nome_distrito`/`domicilios_particulares_ocupados_setor_2022`/`renda_responsavel_media_setor_2022` no motor pontual (`nome_subdistrito` segue nao utilizado, descartado por D1 -- ver abaixo).

### Implementacao do Bloco 2

Pipeline criado: `jobs/pipelines/materializar_setores_censitarios_geo.py`.

Saida padrao: `data/outputs/setores_censitarios_2022_geo/uf=XX/cod_municipio=NNNNNNN/part-000.parquet`, com `geometry_wkb` e colunas de bbox para recorte rapido. A geometria fica serializada em WKB no CRS original `EPSG:4674`; `area_setor_m2` e `densidade_pop_setor_hab_km2` sao calculadas em `EPSG:5880`.

Regras implementadas:
- Join malha x Basico por posicao dentro da UF, preservando o alinhamento confirmado no Bloco 1.
- Join da renda por posicao dentro da UF, porque `CD_SETOR` do CSV de renda vem truncado em notacao cientifica e o arquivo tem menos linhas que a malha/Basico.
- `renda_per_capita_setor_2022 = V06004 / v0005`; quando `data/staging/brasil_estrutural.parquet` esta disponivel, `renda_per_capita_setor_2022_calibrada` usa multiplicador global contra a mediana M1.
- `score_setor_2022_calibrado` e operacional paralelo: `0.60*renda_pct_nacional_calibrado + 0.40*pop_pct_municipal`, com ajuste executivo equivalente ao usado na camada censitaria. Nao altera o M1.

Validacao real executada no DF: 5.418 setores, 1 arquivo, 3,46 MB, ~35s, 97,16% de cobertura de renda/score. Relatorio em `data/reports/relatorio_pontual_censitario_base_geo.md`.

## 5. Metodo de intersecao

1. Receber `lat`, `lng` e usar `raio_km=1.5` fixo no fluxo do relatorio.
2. Identificar UF/municipio provavel para carregar apenas particoes relevantes do artefato geo.
3. Reprojetar ponto e setores candidatos para CRS metrico apropriado ao local antes de criar buffer e medir area.
4. Criar circulo/buffer de `1.500 m`.
5. Filtrar setores por bbox e depois por `intersects`.
6. Calcular `area_setor_m2`, `area_intersecao_m2` e `peso_area_setor = area_intersecao_m2 / area_setor_m2`.
7. Ponderar metricas por area intersectada. Populacao estimada = `pop_total_setor_2022 * peso_area_setor`; renda e scores devem ser medias ponderadas pela populacao estimada quando houver populacao positiva, com fallback para peso de area.
8. Reaproveitar pins de concorrentes/Ultra por distancia haversine ao ponto, sem alterar suas bases.

Metodo canonico de resultado: `setor_censitario_intersecao_area_1p5km`.

### Implementacao do Bloco 3

Motor criado em `src/motor_expansao/dashboard/censo_point.py`: `analisar_ponto_censitario_setores(lat, lng, setores_df, raio_km=1.5, competitors_df=None, ultra_df=None)`.

Regras implementadas:
- entrada setorial por `DataFrame` ja recortado/carregado, com `geometry_wkb` em `EPSG:4674`;
- CRS metrico local azimutal equidistante centrado no ponto para criar o buffer de `1.500 m` e medir areas;
- pre-filtro por bbox quando `bbox_minx/bbox_miny/bbox_maxx/bbox_maxy` existem;
- `area_intersecao_m2`, `peso_area_setor`, `pop_estimada_intersecao` e tabela auditavel de setores intersectados;
- renda e score medios ponderados por populacao estimada, com fallback por area de intersecao quando nao ha populacao positiva;
- concorrentes/Ultra filtrados por distancia haversine ao ponto, sem mutar as bases de entrada.

O retorno explicita `metodo = setor_censitario_intersecao_area_1p5km` e permanece paralelo ao M1.

**BLK-RELPON-05:** o mesmo laco de intersecao ja decodifica/projeta a geometria de cada setor candidato para o CRS metrico local; reaproveitando essa geometria, cada `record` ganha `contains_ponto = geom_metric.covers(Point(0, 0))` (o proprio ponto pesquisado, origem do CRS local). Depois de montar `intersectados`, o setor que cobre o ponto (tie-break por maior `peso_area_setor` quando mais de um "cobre" por ruido de ponto flutuante) alimenta os 5 campos `*_ponto` do `result`. Nao recalcula geometria nova, nao altera `setores_intersectados`/agregados do raio/metodo/raio.

## 6. Mapa do relatorio (camadas combinadas + fundo de ruas)

Implementacao: `src/motor_expansao/dashboard/censo_map.py`. Atualizado no ciclo BLK-CENSO-01 (DEC-004).

Funcao principal: `render_mapas_censitarios_combinados(lat, lng, setores_df, *, raio_km=1.5, competitors_df=None, ultra_df=None, width=1000, height=760, basemap=True, logos_dir=None, ultra_logo_dir=None) -> dict[str, bytes]`. Retorna `{"densidade", "renda", "score", "renda_domiciliar", "concorrentes"}` (5 camadas numa unica geracao — `score` restaurado no BLK-CENSO-03-FU5; `renda_domiciliar` adicionado em 2026-07-17, PR #126). O legado `render_mapa_censitario_estatico_png(...)` continua como wrapper fino (devolve uma das camadas pelo antigo `metric_column`: `score_setor_2022_calibrado` -> `score`).

**Camada `renda_domiciliar` (5o choropleth, PR #126; READ-ONLY M1):** renda media domiciliar por SETOR = `renda_pc_calibrada x moradores(avg_moradores_domicilio_setor_2022, fallback renda_responsavel_media_setor_2022) x uplift_composicao_por_setor(cod_setor,uf,cod_municipio)` [uplift SETORIAL, cada setor e' um poligono] `x FATOR_TEMPORAL_RENDA` — espelha a formula de `censo_point.py:328-352`; a faixa "no raio" usa `result["renda_domiciliar_total_raio"]` (COM uplift+temporal). Bandas `RENDA_MEDIA_DOMICILIAR_BANDS`: MESMA paleta da `RENDA_PER_CAPITA_BANDS` + faixas 2.000/4.600/8.000/14.000 + rotulo "ate" SEM acento (o font do PNG da legenda nao renderiza acento — excecao de RENDER a regra §2 do CLAUDE.md). No PDF (`censo_report.py`) o slide "Mapas de calor" virou **grid 2x2** `[densidade, renda, score, renda_domiciliar]` (`_map_grid_cells`, era tira 1x3); a variante CLASSICA (a que o dashboard baixa) tem header fixo -> celula 2x2 mais baixa -> legenda ~8pt (recente >=9pt). A renda media domiciliar TAMBEM aparece no tooltip do hex do Mapa Territorial, porem com uplift MUNICIPAL (hex res-7 cobre varios setores) — ver CLAUDE.md §4.

Regras implementadas:
- **4 camadas, 1 por mapa** (Densidade populacional, Renda per capita, Score censitario, Concorrentes e Ultra), geradas numa unica chamada e exibidas/embutidas juntas (UI sem dropdown que esconda camadas; PDF com uma pagina por camada). Densidade/Renda/**Score** compartilham basemap, bbox, projecao, pins e choropleth (varia so o fill dos setores + legenda/titulo); a camada **Score censitario** usa o choropleth de `score_setor_2022_calibrado` (`_color_for_score`) COM legenda de faixas 0-100 (`_score_legend_entries()`); a camada **Concorrentes e Ultra e SO de pins** (sem choropleth — BLK-CENSO-03): basemap + pins de concorrentes/Ultra + ponto central + legenda de pins.
- **Fundo de ruas por tiles online** (CartoDB **Voyager COM labels** — base CLARA estilo GeoFusion; realce de contraste `_BASEMAP_CONTRAST=1.15` + zoom+1; `_BASEMAP_PROVIDER_ATTR="Voyager"`/`_BASEMAP_CONTRAST`/`_BASEMAP_ZOOM_BUMP` em `censo_map.py`) SO na geracao, via `contextily` (DEC-004), com **import lazy** sob `try/except ImportError` dentro da funcao de fundo. Cache local em `data/cache/basemap_tiles/` (gitignored). **Fallback offline gracioso**: `basemap=False` OU import/fetch falha (sem internet, sem extra `[basemap]`) -> mapa sobre **canvas CLARO** `(245,245,245)` SEM ruas, sem excecao. O dashboard interativo NAO depende de internet.
- **Composicao em `EPSG:3857`** (CRS nativo dos tiles): os setores e o circulo de 1.5 km sao reprojetados do CRS metrico azimutal local -> 3857 SO para render, reusando o transformer do motor. O motor (`analisar_ponto_censitario_setores`, intersecao setor x circulo, raio 1.5 km) fica INTOCADO. Distorcao Mercator do circulo < 0,5% sobre ~3 km em latitudes brasileiras.
- **Faixas absolutas fixas por camada** (estilo GeoFusion), substituindo o quartil: `DENSIDADE_POP_BANDS` (rampa de vermelhos; cortes 1k/5k/10k/25k/inf hab/km2) e `RENDA_PER_CAPITA_BANDS` (rampa **amarelo -> laranja escuro -> verde** adaptada a PER CAPITA; cortes 1k/2k/3,5k/5k/inf R$/pessoa — NAO confundir com renda domiciliar do M1). O FILL usa `_CHOROPLETH_ALPHA=140` (translucido sobre o claro); a legenda usa a cor cheia da faixa. As **ruas/nomes ESCUROS do Voyager** sao recolocados POR CIMA do choropleth com os PROPRIOS pixels do tile (NAO edge-detection): luminancia `< _STREET_CEIL` vira opacidade (ganho `_STREET_GAIN`, teto `_STREET_CAP`) -> arruamento nitido sobre a cor, estilo GeoFusion. A camada Concorrentes e Ultra nao tem choropleth (so pins).
- **Cobertura de frame inteiro + transicao suave** (estilo GeoFusion): o choropleth cobre TODO o frame do mapa (setores recortados ao quadrado do frame = circulo + margem `_MAP_FRAME_MARGIN`, nao ao circulo), com os corners preenchidos; valores vindos da propria linha do setor (`setores_df`) p/ colorir tambem setores fora do circulo. SEM borda nos poligonos (transicao suave). O circulo de 1.5 km segue desenhado so como referencia visual do raio. Tudo display-only: a analise/KPIs (`analisar_ponto_censitario_setores`) segue circular e INTOCADA.
- **Marcador de concorrente/Ultra = LOGO QUADRADA** (BLK-RELPON-09) via `competitors._render_square_logo_tile` (`_paste_logo_pin`, lado `_PIN_LOGO_PX = 30` px do PNG-fonte, ancorado pelo CENTRO do quadrado no ponto): Ultra=`"__ultra__"`, concorrente pela coluna `rede`; placa branca quando ha logo, placa na cor da marca + sigla no fallback; borda branca de 2 px + sombra leve para contraste sobre o choropleth. Os logos sao lidos do `_ICON_CACHE` populado por `preload_logos` no boot do `streamlit_app.py`. `competitors._render_pin_tile` (balao teardrop 128x128) segue INTOCADO e continua servindo `build_icon_atlas`/o mapa interativo pydeck (`anchorY=122`).
- Exibe circulo de 1.5 km (referencia do raio), ponto central como **pin vermelho**, legenda por camada, escala visual, coordenada central, metodologia e atribuicao `(c) OpenStreetMap, (c) CARTO` no rodape.
- Estado vazio ou ausencia de concorrentes/Ultra nao quebra a geracao.
- Dependencias: `pillow>=10.0.0` (base), `pyproj`/`shapely` (base) para a reprojecao aeqd->3857; `contextily>=1.5.0` no **extra dedicado `[basemap]`** (fora do deploy base), import lazy.

- **Refinamento visual BLK-EST-02 (tema "Ultra Clean / GeoFusion", gate Felipe 2026-06-11):**
  - **Titulos curtos (D6=A):** os 4 mapas perderam o prefixo repetitivo `"Relatorio Pontual Censitario - "` (a camada ja aparece na faixa de titulo do PDF) -> `"Densidade populacional"`, `"Renda per capita"`, `"Score censitario"`, `"Concorrentes e Ultra"`. O **subtitulo tecnico** (coordenada/raio/setores) e mantido para auditoria inline (o PNG tambem serve a UI). Tamanho do titulo aumentado no BLK-RELPON-06 (ver abaixo).
  - **Legenda (D7=C subset seguro):** amostras de cor arredondadas (`draw.rounded_rectangle`, radius 5) + linha separadora fina antes do bloco de pins. `_map_box`/`legend_x`/largura da coluna foram REABERTOS e ampliados pelo BLK-RELPON-06 (ver abaixo) para acomodar as fontes maiores.
  - **Escala/rodape (D8=B):** barra de escala mais grossa (`width=5`) com box branco semi-translucido atras do label (legibilidade sobre qualquer cor do choropleth); rodape enxuto `"Raio 1,5 km - EPSG:3857 - {atribuicao}"`. A atribuicao CARTO/OSM (`_ATRIBUICAO_TILES`, constante nova) permanece quando ha basemap (licenca DEC-004) e some no fallback offline.

- **Faixa superior "\<variavel\> no raio" (BLK-RELPON-05, campo REVERTIDO para o raio pelo BLK-RELPON-06/D1):** `_render_camada` tem o parametro opcional `valor_ponto: str | None = None` (default `None` = render IDENTICO); quando informado, desenha uma 2a linha de texto em `(28, _VALOR_Y)` (`_font(_FS_VALOR_RAIO)`, tinta `_DARK_MAP_INK`), entre o titulo e o `map_box`. `render_mapas_censitarios_combinados` monta as 3 strings (`_legenda_valor_ponto` + `_format_valor_ponto_renda/_densidade/_score`) e as passa SO para `densidade_png`/`renda_png`/`score_png`; a chamada de `concorrentes_png` nao recebe o parametro (fica `None`, mapa so-pins byte-a-byte igual). Formato: moeda com separador de milhar `.` sem centavos (renda), inteiro com unidade ASCII `hab/km2` (densidade), inteiro 0-100 (score); `"n/d"` quando nao ha setores intersectados no raio (sem area valida). **A partir do BLK-RELPON-06 os 3 valores vem dos AGREGADOS DO RAIO** (`densidade_pop_raio_valida_hab_km2`, `renda_per_capita_media_raio`, `score_setor_medio`), NAO mais do valor bruto do setor que contem o ponto (os 5 campos `*_setor_ponto` do BLK-RELPON-05 continuam no `result` para CSV/auditoria, mas deixaram de alimentar esta faixa).

- **Legibilidade dos mapas — BLK-RELPON-06 (D3+D4, 2026-07-14):** o texto dos mapas estava quebrado em producao (dashboard **e** PDF): `_font()` chamava `ImageFont.truetype("arial.ttf", size)` e caia em `ImageFont.load_default()` **sem** `size` no `OSError` -- na imagem `python:3.11-slim` (sem NENHUMA fonte TrueType instalada) isso significava um bitmap fixo ~10px que IGNORAVA o `size` pedido (`_font(20)` e `_font(60)` renderizavam IGUAL). Fix: `_font()` passa a usar **exclusivamente** a fonte TrueType **embutida do Pillow** (`ImageFont.load_default(size=size)`, Pillow >= 10.1; o projeto pina `pillow==12.3.0`), **abandonando `arial.ttf`/TTF do sistema** -- o render fica IDENTICO em Windows e na VPS (determinismo auditavel), ao custo de mudar o visual local (Arial -> fonte embutida) e quebrar de proposito a byte-identidade dos PNGs vs. o estado anterior. Junto com isso, as fontes do mapa cresceram **na BASE** (dashboard, PDF e API com **UM UNICO render**, sem parametro de escala por-caminho -- `pages.py` INTOCADO):

  | Elemento | px antigo | px novo (constante) |
  |---|---|---|
  | Titulo do mapa | 20 | 44 (`_FS_TITULO`) |
  | Linha "\<variavel\> no raio" | 17 | 38 (`_FS_VALOR_RAIO`) |
  | Legenda — titulo "Legenda" | 17 | 34 (`_FS_LEGENDA_TITULO`) |
  | Legenda — subtitulo (ex. "Renda per capita (R$/pessoa)") | 13 | 22 (`_FS_LEGENDA_SUBTITULO`) |
  | Legenda — corpo (rotulos de faixa) | 13 | 32 (`_FS_LEGENDA_CORPO`) |
  | Legenda — captions ("Ponto central"/"Pins: Ultra e concorrentes") | 13 | 20 (`_FS_LEGENDA_CAPTION`) |
  | Mensagem "Sem setores intersectados no raio" | 12 | 26 (`_FS_BODY`) |
  | Rodape (atribuicao CARTO) | 11 | 22 (`_FS_FOOTER`) |
  | Barra de escala (label) | 11 | 24 (`_FS_ESCALA`) |

  O subtitulo e as captions da legenda ganharam constantes de fonte **proprias, menores** que o corpo (`_FS_LEGENDA_SUBTITULO`/`_FS_LEGENDA_CAPTION`) porque, no ajuste visual, o subtitulo mais longo ("Renda per capita (R$/pessoa)") e a frase "Pins: Ultra e concorrentes" transbordavam do canvas quando desenhados a `_FS_LEGENDA_TITULO`/`_FS_LEGENDA_CORPO` -- sao texto secundario/anotacao, como o rodape. Layout acompanhou o crescimento das fontes: `_map_box` usa `_MAP_TOP=132` (era 92) e a coluna da legenda alargou de `_LEGEND_COL_W=330` (era 252, `legend_x = width - _LEGEND_COL_W`) porque o rotulo de faixa mais longo (`"R$ 2.001-3.500"`, 14 chars) nao cabia mais na coluna antiga a 32px; a linha de dado usa `_VALOR_Y=78` (era 51). A area util do mapa encolheu de ~663x590 para ~585x550 px (inner) para abrir espaco -- o choropleth continua cobrindo o frame inteiro, sem mudanca de cor/faixa. Dimensionamento ancorado no **pior caso do PDF**: o PNG de 1000px entra numa celula de ~298,67pt na tira 1x3 do slide "Mapas de calor" (`ratio ~0,2987`), entao a legenda-corpo (32px) sai a ~9,6pt, acima do alvo de 9-10pt de legibilidade.

Validacao minima: `tests/unit/test_relatorio_pontual_censitario_mapa.py` gera as 4 camadas com `basemap=False`, verifica faixas fixas (nao quartil), que a camada `score` tem choropleth (modo de cor) e a `concorrentes` nao, pin com logo de concorrente/Ultra e o fallback offline sem tiles, alem do estado vazio; o teste `test_atribuicao_tiles_constante_e_legenda_arredondada_disponiveis` cobre o refinamento BLK-EST-02 (titulos curtos, legenda arredondada+separador, atribuicao); os testes `test_valor_ponto_repassado_aos_3_choropleths_nao_a_concorrentes`, `test_valor_raio_nao_e_nd_quando_setor_nao_cobre_o_ponto_mas_intersecta_raio`, `test_valor_raio_e_nd_quando_setor_fora_do_raio` e `test_valor_ponto_muda_pixels_do_png` cobrem a faixa "no raio" do BLK-RELPON-05/BLK-RELPON-06; `test_font_escala_com_o_size`, `test_font_nao_chama_truetype_do_sistema_no_proprio_codigo`, `test_font_nao_depende_de_ttf_do_sistema`, `test_legenda_corpo_atinge_o_alvo_de_legibilidade_no_pdf`, `test_rotulo_mais_longo_da_legenda_cabe_na_coluna`, `test_legenda_subtitulo_mais_longo_nao_transborda_do_canvas` e `test_legenda_caption_pins_nao_transborda_do_canvas` cobrem a fonte embutida (D3) e o contrato de legibilidade/layout do BLK-RELPON-06 (D4) em codigo, sem depender so de revisao visual.

## 7. Export CSV e PDF

Implementacao: `src/motor_expansao/dashboard/censo_report.py`. **Template Ultra reescrito sobre `fpdf2`** no ciclo BLK-CENSO-02 (gate humano de Felipe em 2026-06-05 aprovou trocar o writer manual PDF-1.4 por `fpdf2`, dependencia BASE em `pyproject.toml`). O writer roda com **compressao de stream desativada** (`set_compression(False)`) para auditabilidade anti-PII e asserts de texto cru — os PDFs sao pequenos. **Follow-up BLK-CENSO-02-FU1 (Felipe, 2026-06-06):** paginas em **proporcao 16:9 widescreen (960x540 pt)** em vez de A4 retrato (a capa 16:9 do `.pptx` deixou de distorcer e o titulo foi para a zona limpa inferior-direita, sem colidir com o logo "GRUPO ULTRA" embutido); Big Numbers passou a **grid 4x2 de 8 metricas** e o card de residual passou a exibir **Residual Fitness em alunos** (`oferta_efetiva_disponivel`) + **SAM Fitness em alunos** (`sam_fitness_potencial`) no lugar do `score_oportunidade_residual`.

Funcoes principais:
- `gerar_csv_setores_censitarios(result)`: retorna bytes CSV da tabela de setores intersectados, com `sep=";"` e `encoding="utf-8-sig"`, sem incluir geometria bruta. **INALTERADO** neste ciclo.
- `gerar_pdf_relatorio_pontual_censitario(result, mapas=None, *, residual=None, perfil_bairro=None, ultra_dir=None)`: retorna bytes PDF em memoria com a **estrutura de 6 paginas** (template Ultra; **BLK-RELPON-01** consolidou os 3 choropleths em 1 slide; **BLK-RELPON-07** inseriu a pagina "Perfil do Bairro/Distrito"), nesta ordem:
  1. **Capa** (16:9) — fundo de marca da capa (`relatorio_capa_bg.png`, ja com logo "GRUPO ULTRA" + faixa de marcas), titulo + coordenada `lat,lng` + `municipio/UF` + raio 1.5 km na **zona turquesa limpa do quadrante inferior-direito** (nao colide com o branding embutido). Sem o asset -> turquesa solido com o bloco centralizado.
  2. **Mapas de calor** — os 3 choropleths (`densidade`, `renda`, `score`) numa **tira 1x3 lado a lado** (BLK-RELPON-01), sobre fundo claro `#F8F8F8` + faixa de titulo. Cada PNG (do BLK-CENSO-01) e embutido **separadamente** (nao pre-composto), com sua **legenda embutida** (as 3 escalas sao distintas: densidade hab/km², renda R$/pessoa, score 0-100 — restaurado COM legenda no BLK-CENSO-03-FU5). Camada ausente -> fallback textual "Mapa indisponivel para esta camada." naquela celula (offline-safe).
  3. **Concorrentes** — mapa de concorrentes (mapa `concorrentes` SO de pins: basemap + pins de concorrentes/Ultra + ponto central, SEM choropleth) a esquerda + lista textual das redes no raio a direita (coluna `rede`/`nome_unidade`, NUNCA dados de pessoas).
  4. **Perfil do Bairro/Distrito** (BLK-RELPON-07) — titulo+unidade (bairro, com fallback distrito) + 4 cards (populacao, densidade demografica, domicilios, renda media) agregados sobre TODOS os setores da unidade administrativa que CONTEM o ponto, independente do raio de 1.5 km. SEM mapa (so texto/numero). "n/d" gracioso quando o ponto cai fora da malha ou a unidade nao tem dado suficiente.
  5. **Big Numbers** — grid 4x2 das 8 metricas (ver abaixo).
  6. **Realizacao/Credito** — fundo turquesa solido, texto fixo "Relatorio gerado pelo Motor de Expansao - Ultra Academia", atribuicao de tiles `(c) OpenStreetMap, (c) CARTO` e nota READ-ONLY. SEM PII.
  - `mapas` aceita o `dict[str,bytes]` das camadas combinadas OU, por retrocompat, `bytes` de um unico mapa legado (vai como camada `densidade` na tira de Mapas de calor; as demais celulas caem no fallback textual). PNGs passados ao fpdf2 via `io.BytesIO`.

**BLK-RELPON-07 (slide "Perfil do Bairro/Distrito", entre Concorrentes e Big Numbers):**
- **D1** (unidade geografica): BAIRRO com fallback para DISTRITO; `nome_subdistrito` descartado (nao usado como unidade).
- **D2** (escopo): agrega TODOS os setores da unidade administrativa que CONTEM o ponto -- nao o raio de 1.5 km usado pelo resto do relatorio.
- **D3** (4 blocos com dado fiel): populacao, densidade demografica, domicilios, renda media. Faixa etaria, faixa de renda ABEP e PEA NAO entram (sem dado).
- **D3.5** (formula da renda media): `renda_media_domiciliar` = media de `renda_responsavel_media_setor_2022` PONDERADA por `domicilios_particulares_ocupados_setor_2022` (Metodo A, leitura GeoFusion "Renda Media" -- distinta da renda per capita usada nas outras 2 paginas do PDF). Exclusao SIMETRICA: um setor so entra no numerador E denominador se renda E domicilios forem nao-nulos E domicilios > 0; sem nenhum setor valido -> `None` ("n/d").
- `analisar_ponto_censitario_setores` (`censo_point.py`) ganhou 5 campos novos no `result`: `cod_bairro_ponto`, `nome_bairro_ponto`, `nome_distrito_ponto`, `unidade_ponto_tipo` (`"bairro"`/`"distrito"`/`None`, identificador cru) e `unidade_ponto_rotulo` (nome de exibicao ja com o fallback resolvido) -- leitura do MESMO setor que contem o ponto (reaproveita o lookup do BLK-RELPON-05).
- Novo helper `agregar_perfil_bairro_distrito(setores_df, *, cod_bairro=None, nome_bairro=None, nome_distrito=None, nome_municipio=None, uf=None)` (`censo_point.py`) agrega populacao/domicilios/area/renda sobre TODOS os setores da unidade resolvida; funcao pura, "n/d" gracioso (sem excecao) quando o identificador esta ausente, as colunas nao existem ou a unidade nao tem setores.
- `perfil_bairro=None` (default, em `gerar_pdf_relatorio_pontual_censitario`/`gerar_pdf_relatorio_pontual_classico`/`gerar_payloads_download_relatorio_censitario`/`render_downloads_relatorio_censitario`) produz a pagina nova com texto "n/d" gracioso, sem excecao.
- **Nota de escopo:** `src/motor_expansao/api/service.py` (endpoint `POST /analisar` com `formato=pdf`, DEC-005) chama `gerar_pdf_relatorio_pontual_classico` DIRETAMENTE, sem passar `perfil_bairro` -- FORA do escopo deste bloco. O PDF gerado pela API ganha a pagina nova automaticamente (contagem 5->6 tambem la), mas com os 4 cards em "n/d".
- **Big Numbers (8 metricas, READ-ONLY):** **populacao total no raio**, **renda per capita media**, **numero de domicilios no raio** (`domicilios_total_raio`, BLK-RELPON-08) e **score censitario medio** (nessa ordem, linha 1) vem do `result` censitario; **SAM Fitness em alunos** (`sam_fitness_potencial`), **Residual Fitness em alunos** (`oferta_efetiva_disponivel`), **concorrentes no raio** (`n_concorrentes`) e **consumo de concorrentes** (`oferta_consumida_mercado_estimada`) vem de `lookup_hex_by_coord(lat, lng, df, h3_res=7)` lendo o `df` ja em escopo em `pages.py` — leitura pura, SEM load novo de parquet e SEM recalcular M1/residual. NB: SAM e Residual Fitness saem em **numero de alunos** (sizing absoluto da camada de mercado), nao em score. `score_setor_max` (antigo card "Score censitario maximo") SAIU do PDF a partir do BLK-RELPON-08 -- continua calculado em `result` para auditoria em CSV, so nao aparece mais como card. Campo ausente/NaN/hex-ausente -> **"n/d"** auditavel, com nota de fonte citando o metodo `setor_censitario_intersecao_area_1p5km`.
- `gerar_payloads_download_relatorio_censitario(...)` e `render_downloads_relatorio_censitario(...)`: preparam nomes/bytes e botoes `st.download_button`; propagam os kwargs `residual` e `ultra_dir` ao PDF.

Assets de branding (Fase 0):
- Dois fundos LIMPOS extraidos do `data/referencias/Teste Modelo.pptx` (zip Office) para `data/ultra/` (gitignored; ficam no host/volume `:ro`): `relatorio_capa_bg.png` (capa turquesa, de `ppt/media/image6.png`) e `relatorio_conteudo_bg.png` (fundo claro, de `ppt/media/image1.jpg` -> PNG). Otimizados com Pillow `optimize=True`.
- **Anti-PII (guardrail):** `ppt/media/image24.png` (cartao de contato com nome/telefone/e-mail reais) NUNCA e extraido, embutido ou versionado; o `.pptx` e qualquer PDF de saida NUNCA sao versionados. Teste `test_pdf_sem_pii_de_pessoas` e defesa em profundidade.
- **Fallback gracioso/offline-safe:** `_load_branding_assets` retorna `None` por asset em qualquer falha; o writer desenha entao fundo de cor solida (turquesa na capa, branco-gelo no conteudo). PDF valido SEM excecao mesmo em CI/checkout/deploy limpo (sem os assets). Geracao 100% offline (fpdf2 nao faz fetch; os tiles ficam so na geracao dos PNGs do BLK-CENSO-01/DEC-004).

Decisao operacional:
- `fpdf2` e pure-Python e offline; a geracao e sob demanda e retorna bytes, sem escrever artefatos permanentes.
- **Deploy:** adotar `fpdf2` exige rebuild da imagem Docker + redeploy por digest na VPS; os PNGs de `data/ultra/` (gitignored) precisam ser copiados ao volume `/opt/motor-expansao/data/ultra/` para o branding aparecer em producao (sem eles, o fallback solido garante PDF valido). Passo de OPS gated (guardrail §6).

**Consolidacao BLK-RELPON-01 (gate humano Vinicius 2026-07-01):** os 3 choropleths (Populacao/Renda/Score) — antes 1 pagina cada — foram consolidados em **UM slide "Mapas de calor"** (tira 1x3 lado a lado, sem sobreposicao, cada PNG embutido separadamente com sua legenda), levando o PDF de **7->5 paginas** (Capa->Mapas de calor->Concorrentes->Big Numbers->Realizacao), `/Count 7`->`/Count 5`, `PDF_SECTION_HEADERS` de 7->5 strings. Feito nas duas variantes (`censitario` e `classico`). READ-ONLY sobre o M1; metodo de intersecao/raio 1,5 km/score/artefatos oficiais INTOCADOS. Helpers `_map_page`/`_classico_map_page`/`_draw_map`/`_classico_draw_map` removidos (substituidos por `_mapas_calor_page`/`_classico_mapas_calor_page` + `_draw_maps_grid`/`_classico_draw_maps_grid` + `_map_grid_cells`).

**Insercao BLK-RELPON-07 (2026-07-15):** a pagina "Perfil do Bairro/Distrito" foi inserida entre Concorrentes e Big Numbers, levando o PDF de **5->6 paginas** (Capa->Mapas de calor->Concorrentes->Perfil do Bairro/Distrito->Big Numbers->Realizacao), `/Count 5`->`/Count 6`, `PDF_SECTION_HEADERS` de 5->6 strings. Feito nas duas variantes. Consequencia aceita da alternancia de tema por ordinal (`_tema_bicolor`): a cor de destaque da pagina Big Numbers muda de turquesa para magenta (era o 3o slide de conteudo, passa a ser o 4o); a nova pagina Perfil do Bairro/Distrito herda o turquesa que antes era de Big Numbers. Ver secao dedicada acima (§7 topo) para o contrato completo da pagina nova.

**Refinamento visual BLK-EST-02 (tema "Ultra Clean / GeoFusion", gate Felipe 2026-06-11):** so estilo/geometria/strings — o grid **4x2 de 8 metricas** READ-ONLY, `set_compression(False)` e `pdf_version="1.4"` permanecem INTOCADOS (a contagem de paginas/ordem foi atualizada pelo BLK-RELPON-01, acima).
- **Tipografia (D1=B):** capa titulo 30 pt; faixa de titulo de conteudo 22 pt (banda `band_h` 48->56, `set_xy(36,16)`); Realizacao 34/18/12 pt. Mantida a fonte core Helvetica (sem TTF/asset novo).
- **Cards Big Numbers (D2=B + D3=B):** rotulo em cinza-escuro `(45,45,45)` e valor grande em cinza-escuro `(40,40,40)` (acento so na barra do topo); `card_h=156`, `gap=16`, barra acento 6 pt, valor 26 pt, **borda fina** `(225,225,228)` via `rect(..., style="D")` apos o fill; rotulo em `y+20`, valor em `y+88`. As 8 metricas/ordem e a nota de fonte abaixo do grid seguem intactas.
- **Semaforo de cor de fundo dos cards (BLK-RELPON-08):** cada um dos 8 cards ganha um fundo pastel por meta -- verde `_CARD_VERDE_RGB=(205,236,217)` quando o valor bate a meta, vermelho `_CARD_VERMELHO_RGB=(248,209,209)` quando nao bate, cinza `_CARD_NEUTRO_RGB=(232,233,237)` quando o valor e "n/d" (indecidivel, sempre neutro, nunca reprovacao/aprovacao falsa). Metas nomeadas em `censo_report.py`: `_META_POP_TOTAL_RAIO=10000`, `_META_RENDA_PER_CAPITA_MEDIA_RAIO=1500`, `_META_DOMICILIOS_TOTAL_RAIO=3000`, `_META_SCORE_SETOR_MEDIO=60`, `_META_SAM_FITNESS_POTENCIAL=2000`, `_META_RESIDUAL_FITNESS_DISPONIVEL=2000`. Helper puro `_cor_por_meta(valor, meta)` cobre os 6 cards de meta simples (`>=meta` -> verde). O card "Consumo concorrentes (est.)" usa regra assimetrica via `_cor_consumo_concorrentes(sam, residual_disponivel)`: vermelho SO quando o mercado ja esta consumido (SAM Fitness >= meta E Residual Fitness < meta), verde caso contrario; o card "Concorrentes no raio" ESPELHA essa mesma cor (sem meta propria). Linha 1 reordenada: **Populacao total no raio -> Renda per capita media -> Numero de domicilios -> Score censitario medio**; o card "Score censitario maximo" SAIU do PDF (campo `score_setor_max` continua em `result`/CSV). Sao thresholds de DISPLAY locais a `censo_report.py`; nao alteram `flag_sam`/DEC-006/DEC-007 nem `sam_fitness_potencial`/`oferta_efetiva_disponivel` no pipeline de mercado.
- **Concorrentes (D4=B):** **bullet colorido por tipo** antes de cada linha (Ultra=turquesa, concorrente=magenta, `pdf.ellipse`); cabecalho com **contagem total** `"... (N no total)"` quando `total > 10` (`total = len(concorrentes_raio) + len(ultra_raio)`, guarda None/empty via `_safe_len`); linha `"... e mais {total-10}"` quando a lista trunca em 10. `_point_rows` passou a retornar `(texto, is_ultra)`; `name_col` segue restrito a colunas de UNIDADE (anti-PII).
- **Realizacao (D5=C):** logo Ultra (`assets["logo"]`) centralizado no topo (`y=90`, `w=160`) com **fallback gracioso** se ausente; metodo encurtado para 1 frase ("Intersecao de setores censitarios IBGE 2022 com circulo de 1,5 km; distribuicao intrassetor por area."); blocos de texto subidos. Nota READ-ONLY e atribuicao de tiles mantidas. Texto novo `_ascii()`-safe (latin-1).

Validacao minima: `tests/unit/test_relatorio_pontual_censitario_export.py` cobre bytes CSV/PDF, os **6** headers de secao, `/Count 6`, as 4 imagens de mapa embutidas no PDF (**3 choropleths separados no slide unico "Mapas de calor" + a de Concorrentes so-pins**, via `/Subtype /Image >= 4`), Big Numbers com/sem residual ("n/d"), fallback offline sem assets, anti-PII, atribuicao de tiles, retrocompat de `bytes` unico e helper de download; os testes `test_pdf_concorrentes_contagem_total_e_mais_n_quando_excede_10` e `test_pdf_concorrentes_sem_contagem_quando_ate_10` cobrem o cabecalho/contagem D4=B do BLK-EST-02 (sem PII). **BLK-RELPON-01** adiciona `test_slide_unico_tres_mapas_sem_sobreposicao` (bounding boxes das 3 celulas, recente + classico), `test_slide_unico_count_5_e_titulo_mapas_de_calor`, `test_slide_unico_offline_safe_por_camada` e `test_slide_unico_tres_imagens_embutidas`. **BLK-RELPON-05** nao muda logica em `censo_report.py` (a faixa ja vem "assada" nos PNGs recebidos como `mapas: dict[str, bytes]`); `test_pdf_estrutura_inalterada_com_faixa_valor_ponto_blk_relpon_05` reforca que `/Count 6`, contagem de imagens e headers permanecem identicos. **BLK-RELPON-07** adiciona `test_perfil_bairro_page_presente_com_4_metricas_recente`, `test_perfil_bairro_page_nd_quando_perfil_bairro_none` e `test_classico_perfil_bairro_page_presente_e_nd` (nova pagina "Perfil do Bairro/Distrito", com/sem `perfil_bairro`), alem de atualizar os 13 asserts `/Count 5`->`/Count 6` e as 2 contagens de marca d'agua `>= 5`->`>= 6` nos testes existentes (5->6 paginas); em `tests/unit/test_relatorio_pontual_censitario_motor.py`, `test_lookup_bairro_ponto_quando_setor_tem_bairro`, `test_lookup_distrito_ponto_fallback_quando_bairro_ausente` e os testes de `agregar_perfil_bairro_distrito` (agregacao, fallback, exclusao simetrica de renda, "n/d" sem identificador/DataFrame vazio) cobrem o motor novo.

### Implementacao do Bloco 6

O fluxo visual foi integrado ao dashboard em `render_relatorio_pontual_censitario`, dentro do expander `Relatorio Pontual Censitario` na aba `Mapa Territorial`. Ele reutiliza a coordenada ativa do clique no mapa ou da busca da sidebar, mantem raio fixo `1.5 km`, exibe KPIs, seletor de metrica do PNG, mapa censitario, tabela de setores e botoes de download CSV/PDF.

A carga operacional usa `load_censo_geo_setores` no `streamlit_app.py`, cacheada por Streamlit, e `read_censo_geo_partition` em `dashboard/data.py`. O caminho preferencial le apenas `data/outputs/setores_censitarios_2022_geo/uf=XX/cod_municipio=NNNNNNN`; se a base municipal nao existir, a UI mostra mensagem clara e nao tenta carregar shapefile nacional.

Baseline simples DF/Brasilia: `5.418` setores carregados, `34` setores intersectados, leitura `~0,04s`, analise `~0,16s`, pico Python via `tracemalloc` `~6,3 MB`.

## 8. Qualidade e limites

- A distribuicao intrassetor e aproximada por area; o relatorio nao promete precisao de rua, lote ou quadra.
- Setores extensos ou rurais podem diluir populacao/renda quando a ocupacao real nao for uniforme.
- Renda censitaria e proxy/calibrada; exibir metodologia e flags quando ausente, suprimida ou herdada por fallback.
- Setores com geometria invalida devem ser corrigidos com rotina explicita ou marcados por flag.
- Os Parquets H3 atuais nao devem ser tratados como base geometrica de setor.
- O choropleth do mapa usa **faixas absolutas fixas por camada** (`DENSIDADE_POP_BANDS`/`RENDA_PER_CAPITA_BANDS`/`RESIDUAL_SCORE_BANDS`), nao quartis relativos: cores comparaveis entre pontos diferentes. Quartis continuam apoio relativo em outras telas; sizing executivo deve priorizar regua absoluta, populacao estimada, renda, residual, receita esperada perdida e capacidade operacional.
- O fundo de ruas depende de tiles online so na geracao (CartoDB **Voyager COM labels**, base clara, via `contextily`, extra `[basemap]`); sem internet/extra o mapa cai em canvas CLARO sem ruas (fallback offline), sem afetar KPIs, CSV nem o motor de intersecao. A camada Concorrentes e Ultra e SO de pins (sem choropleth).

## 9. Decisao operacional

O relatorio permanece dentro do dashboard Streamlit no ciclo atual porque:
- o produto precisa conviver com a entrada por coordenada ja existente;
- o deploy inicial continua offline com dados locais;
- o processamento pesado pode ser amortizado por artefato GeoParquet/WKB particionado e cache;
- API/worker separado so entra no backlog se houver concorrencia de usuarios, fila de PDFs, historico por usuario ou deploy independente.

## 10. Validacao do Bloco 1

Comandos executados:
- `python -c "import geopandas, shapely, pandas; print('ok')"`: passou.
- Leitura da malha com `geopandas.read_file(..., rows=1)`: passou; CRS `EPSG:4674`.
- Inventario com `pyogrio.read_info`: 468.099 features.
- Leitura de cabecalho/amostra dos CSVs Basico e Renda: passou.
- Leitura de schemas dos Parquets com `pyarrow.parquet`: passou; nenhuma coluna `geometry` detectada nos Parquets censitarios atuais.
