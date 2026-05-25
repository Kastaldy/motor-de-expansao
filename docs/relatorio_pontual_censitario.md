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

## 6. Mapa estatico do relatorio

Implementacao do Bloco 4: `src/motor_expansao/dashboard/censo_map.py`.

Funcao principal: `render_mapa_censitario_estatico_png(lat, lng, setores_df, raio_km=1.5, metric_column="pop_estimada_intersecao", competitors_df=None, ultra_df=None)`.

Regras implementadas:
- PNG gerado offline com `Pillow`, sem screenshot obrigatorio de pydeck.
- Reutiliza o motor `analisar_ponto_censitario_setores` e redesenha as intersecoes reais setor x circulo em CRS metrico local.
- Choropleth de setores por metrica selecionada; metricas canonicas iniciais: `pop_estimada_intersecao`, `renda_per_capita_setor_2022_calibrada`, `score_setor_2022_calibrado`, `peso_area_setor`.
- Exibe circulo de 1.5 km, ponto central, pins de concorrentes/Ultra quando presentes, legenda, escala visual, coordenada central e metodologia no rodape.
- Estado vazio ou ausencia de concorrentes/Ultra nao quebra a geracao; o mapa ainda mostra circulo, ponto central, escala e aviso.
- Dependencia direta registrada: `pillow>=10.0.0`.

Validacao minima: `tests/unit/test_relatorio_pontual_censitario_mapa.py` gera PNG com dataset minimo, verifica dimensao/conteudo e cobre estado vazio sem concorrentes.

## 7. Export CSV e PDF

Implementacao do Bloco 5: `src/motor_expansao/dashboard/censo_report.py`.

Funcoes principais:
- `gerar_csv_setores_censitarios(result)`: retorna bytes CSV da tabela de setores intersectados, com `sep=";"` e `encoding="utf-8-sig"`, sem incluir geometria bruta.
- `gerar_pdf_relatorio_pontual_censitario(result, mapa_png_bytes=None)`: retorna bytes PDF executivo em memoria, com capa/KPIs, mapa quando fornecido, concorrencia, tabela resumida, metodologia e limites.
- `gerar_payloads_download_relatorio_censitario(...)` e `render_downloads_relatorio_censitario(...)`: preparam nomes/bytes e botoes `st.download_button` para CSV/PDF.

Decisao operacional:
- O PDF usa writer leve interno + `Pillow` apenas para converter o PNG do mapa em imagem embutida; nenhuma dependencia nova foi adicionada.
- A geracao e sob demanda e retorna bytes; nao escreve artefatos permanentes fora de cache/temp controlado.
- A UI completa chama estes helpers no Bloco 6, sem escrever artefatos permanentes.

Validacao minima: `tests/unit/test_relatorio_pontual_censitario_export.py` cobre bytes CSV/PDF, secoes obrigatorias, mapa embutido e helper de download.

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
- Quartis continuam apenas apoio relativo; sizing executivo deve priorizar regua absoluta, populacao estimada, renda, residual, receita esperada perdida e capacidade operacional.

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
