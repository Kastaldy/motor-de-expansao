# Modelo de Mercado por Hexagono

Especificacao da camada de mercado por hexagono usando apenas variaveis ja disponiveis no repositorio em 2026-04-23.

Status do piloto em 2026-04-23:

- blocos 1 a 9 fechados;
- staging materializado em `data/staging/concorrentes_mapeados.parquet`, `data/staging/unidades_ultra_mapeadas.parquet` e `data/staging/hexagonos_mercado_mapeado.parquet`;
- pipeline nacional para 21 UFs pronto em `fase_a_nacional_completo.py`; parquet pendente de execucao real sobre `data/raw/CENSO 2022/`;
- suite minima do piloto em `tests/integration/test_modelo_mercado_hexagonos.py` usada como validacao de handoff;
- `score_priorizacao` segue como score oficial; a camada abaixo continua operacional e paralela.

## 1. Escopo

Objetivo: criar uma camada operacional para comparar demanda potencial, oferta mapeada e capacidade real de captura por hexagono.

Importante:

- O M1 oficial continua sendo o gate principal de prioridade territorial.
- A camada abaixo nao substitui `score_priorizacao`.
- A camada abaixo usa apenas dados ja disponiveis no repo.
- A oferta competitiva aqui e `oferta mapeada`, nao `oferta total do mercado`, porque hoje so existem 3 bases de concorrentes no workspace.

## 2. Fontes disponiveis

### 2.1 Base principal

Arquivo: `data/outputs/oportunidades_expansao_hibrido.parquet`

Colunas-chave disponiveis:

- `hex_id`, `uf`, `cidade`
- `score_priorizacao`, `score_oficial`, `hex_score_estrutural`
- `renda_per_capita`, `populacao_proxy`
- `faixa_oportunidade`, `flag_viavel`, `flag_prioridade`
- `top_municipio`, `flag_hex_hibrido_elegivel`
- `score_expansao_hibrido`
- `score_setor_2022_calibrado`, `coverage_pct_setor_2022`, `qualidade_join_uf`, `flag_join_uf_restrito`, `flag_baixa_pop_setor`, `flag_censo_elegivel`

### 2.2 Base estrutural complementar

Arquivo: `data/staging/brasil_estrutural.parquet`

Colunas adicionais disponiveis:

- `lat`, `lng`
- `cod_municipio`, `nome_municipio`
- `pop_total`, `n_domicilios`, `densidade_dom` (trava 18-45 removida em 2026-05-15; `populacao_proxy` = `pop_total`)
- `renda_pct_nacional`, `pop_pct_nacional`

### 2.3 Base censitaria complementar

Arquivo: `data/staging/censo2022_setores_calibrado.parquet`

Colunas adicionais disponiveis:

- `pop_total_setor_2022`
- `renda_per_capita_setor_2022_calibrada`
- `coverage_pct_setor_2022`
- `qualidade_join_uf`
- `flag_join_uf_restrito`
- `flag_baixa_pop_setor`
- `score_setor_2022_calibrado`

### 2.4 Bases de concorrentes disponiveis

Arquivos:

- `concorrentes/unidades_smart_fit.csv`
- `concorrentes/unidades_bluefit.csv`
- `concorrentes/unidades_panobianco.csv`

Colunas disponiveis nos 3 CSVs:

- `nome_unidade`
- `latitude`
- `longitude`
- `data_coleta`

### 2.5 Base de unidades Ultra

Arquivo:

- `data/ultra/Ultra.csv`

Colunas disponiveis no arquivo bruto:

- `UNIDADE`
- `ESTADO`
- `CIDADE`
- `Latitude`
- `Longitude`

Observacao:

- o arquivo possui 1 linha inicial de metadado antes do cabecalho real;
- a leitura deve ignorar a primeira linha, usar `sep=";"` e tratar latitude/longitude com virgula decimal.

## 3. Camada 1 - concorrentes normalizados

Arquivo proposto: `data/staging/concorrentes_mapeados.parquet`

### 3.1 Dicionario de colunas

| coluna | tipo | regra exata |
| --- | --- | --- |
| `concorrente_id` | string | `sha1(f"{rede}|{nome_unidade}|{lat:.6f}|{lng:.6f}")` |
| `rede` | string | mapeamento fixo do nome do arquivo: `unidades_smart_fit.csv -> smart_fit`, `unidades_bluefit.csv -> bluefit`, `unidades_panobianco.csv -> panobianco` |
| `nome_unidade` | string | valor original de `nome_unidade` com `strip()` |
| `lat` | float | `to_numeric(latitude)` |
| `lng` | float | `to_numeric(longitude)` |
| `data_coleta` | datetime/string | valor original do CSV |
| `arquivo_origem` | string | nome do arquivo de origem |
| `flag_coord_valida` | bool | `lat.notna() and lng.notna() and -34 <= lat <= 6 and -75 <= lng <= -28` |
| `flag_duplicado_rede_coord` | bool | duplicado por `['rede', 'lat', 'lng']`, mantendo a primeira linha |
| `status_registro` | string | `descartado_coord` se `flag_coord_valida=False`; `descartado_duplicado` se `flag_duplicado_rede_coord=True`; senao `valido` |
| `hex_id_res7` | string | `h3.latlng_to_cell(lat, lng, 7)` quando `status_registro='valido'` |

### 3.2 Regras de limpeza

1. Ler os 3 CSVs com `sep=";"`.
2. Padronizar os nomes de colunas para o contrato acima.
3. Descartar linhas com coordenadas ausentes ou fora do envelope do Brasil.
4. Descartar duplicatas exatas por rede + coordenada.
5. Nao deduplicar nomes iguais com coordenadas diferentes.

## 4. Camada 2 - mercado mapeado por hexagono

Arquivo proposto: `data/staging/hexagonos_mercado_mapeado.parquet`

Base de montagem:

1. `data/outputs/oportunidades_expansao_hibrido.parquet`
2. left join com `data/staging/brasil_estrutural.parquet` por `hex_id`
3. left join com `data/staging/censo2022_setores_calibrado.parquet` por `hex_id`
4. enriquecimento espacial com `data/staging/concorrentes_mapeados.parquet`
5. enriquecimento espacial com as unidades Ultra georreferenciadas

### 4.1 Camada auxiliar - unidades Ultra normalizadas

Arquivo proposto: `data/staging/unidades_ultra_mapeadas.parquet`

| coluna | tipo | regra exata |
| --- | --- | --- |
| `ultra_id` | string | `sha1(f"{unidade}|{lat:.6f}|{lng:.6f}")` |
| `unidade` | string | valor original de `UNIDADE` com `strip()` |
| `uf` | string | valor original de `ESTADO` |
| `cidade` | string | valor original de `CIDADE` |
| `lat` | float | `to_numeric(Latitude.replace(',', '.'))` |
| `lng` | float | `to_numeric(Longitude.replace(',', '.'))` |
| `flag_coord_valida` | bool | `lat.notna() and lng.notna() and -34 <= lat <= 6 and -75 <= lng <= -28` |
| `hex_id_res7` | string | `h3.latlng_to_cell(lat, lng, 7)` quando `flag_coord_valida=True` |

Regras de leitura:

1. ignorar a primeira linha do arquivo;
2. usar `sep=";"`;
3. converter latitude e longitude de virgula decimal para ponto.

## 5. Dicionario de colunas novas

### 5.1 Chaves e auditoria

| coluna | tipo | regra exata |
| --- | --- | --- |
| `data_snapshot_mercado` | string | data da execucao da camada |
| `fonte_demanda_principal` | string | `censo_2022_hex` quando `flag_censo_elegivel=True` e `pop_total_setor_2022.notna()`; senao `m1_municipal_proxy` |
| `fonte_oferta_principal` | string | valor fixo `csv_big_players_mapeados` |
| `n_redes_mapeadas` | int | valor fixo `3` enquanto a camada usar apenas Smart Fit, Bluefit e Panobianco |

### 5.2 Demanda potencial (TAM)

| coluna | tipo | regra exata |
| --- | --- | --- |
| `demanda_granularidade` | string | `hex_censo` quando `flag_censo_elegivel=True` e `pop_total_setor_2022.notna()`; senao `municipio_proxy` |
| `tam_populacao_base` | float | `pop_total_setor_2022` quando `demanda_granularidade='hex_censo'`; senao `populacao_proxy` |
| `tam_renda_base` | float | `renda_per_capita_setor_2022_calibrada` quando `demanda_granularidade='hex_censo'` e a coluna estiver preenchida; senao `renda_per_capita` |
| `tam_indice_demanda` | float | `score_expansao_hibrido` quando `flag_hex_hibrido_elegivel=True` e `score_expansao_hibrido.notna()`; senao `score_priorizacao` |
| `tam_indice_demanda_norm` | float | `tam_indice_demanda / 100.0` |
| `tam_pop_total_base` | float | `populacao_proxy` (= `pop_total`; trava 18-45 removida em 2026-05-15) |

Observacao:

- Fora das UFs com camada censitaria elegivel, `tam_populacao_base` continua sendo um proxy municipal repetido por hexagono.
- Por isso a leitura nacional deve usar `tam_indice_demanda` como ranking, nao `tam_populacao_base` como volume local absoluto.
- Quando `tam_indice_demanda` herda `score_expansao_hibrido`, ele preserva o bonus local de desempate do modelo hibrido e pode passar marginalmente de `100` (ate `100.001` no desenho atual). Nessa situacao, a leitura continua sendo de ranking operacional, nao de score absoluto novo.

### 5.3 Oferta mapeada de concorrentes

Todos os calculos abaixo usam o centroide do hex (`lat`, `lng`) contra cada concorrente valido em `concorrentes_mapeados`.

Distancia base:

`dist_m = haversine_metros((hex_lat, hex_lng), (comp_lat, comp_lng))`

Pesos de proximidade:

- `peso_1km = max(0, 1 - dist_m / 1000)` quando `dist_m <= 1000`, senao `0`
- `peso_2km = max(0, 1 - dist_m / 2000)` quando `dist_m <= 2000`, senao `0`

| coluna | tipo | regra exata |
| --- | --- | --- |
| `n_concorrentes_mapeados_1km` | int | contagem de concorrentes com `dist_m <= 1000` |
| `n_concorrentes_mapeados_2km` | int | contagem de concorrentes com `dist_m <= 2000` |
| `n_smart_fit_2km` | int | contagem de concorrentes com `rede='smart_fit'` e `dist_m <= 2000` |
| `n_bluefit_2km` | int | contagem de concorrentes com `rede='bluefit'` e `dist_m <= 2000` |
| `n_panobianco_2km` | int | contagem de concorrentes com `rede='panobianco'` e `dist_m <= 2000` |
| `dist_concorrente_mais_proximo_m` | float | menor `dist_m` entre todos os concorrentes validos; `null` se nenhum concorrente existir na base |
| `dist_smart_fit_mais_proximo_m` | float | menor `dist_m` entre concorrentes `smart_fit`; `null` se inexistente |
| `dist_bluefit_mais_proximo_m` | float | menor `dist_m` entre concorrentes `bluefit`; `null` se inexistente |
| `dist_panobianco_mais_proximo_m` | float | menor `dist_m` entre concorrentes `panobianco`; `null` se inexistente |
| `oferta_efetiva_mapeada_1km` | float | soma de `peso_1km` dos concorrentes com `dist_m <= 1000` |
| `oferta_efetiva_mapeada_2km` | float | soma de `peso_2km` dos concorrentes com `dist_m <= 2000` |
| `share_smart_fit_2km` | float | `n_smart_fit_2km / n_concorrentes_mapeados_2km` se o denominador > 0; senao `0` |
| `share_bluefit_2km` | float | `n_bluefit_2km / n_concorrentes_mapeados_2km` se o denominador > 0; senao `0` |
| `share_panobianco_2km` | float | `n_panobianco_2km / n_concorrentes_mapeados_2km` se o denominador > 0; senao `0` |
| `rede_dominante_2km` | string | rede com maior contagem em 2 km; em empate usar ordem alfabetica; `null` se `n_concorrentes_mapeados_2km=0` |
| `flag_white_space_2km` | bool | `n_concorrentes_mapeados_2km == 0` |
| `gap_competitivo_2km` | float | `1 / (1 + oferta_efetiva_mapeada_2km)` |
| `pressao_concorrencial_score_2km` | float | `100 * (1 - gap_competitivo_2km)` |

Leitura:

- `oferta_efetiva_mapeada_2km` e a oferta espacialmente ponderada dos players mapeados.
- `gap_competitivo_2km` e o espaco residual frente aos players mapeados.
- `pressao_concorrencial_score_2km` vai de `0` a perto de `100`; quanto maior, maior a pressao dos players mapeados.

### 5.4 Mercado atendivel (SAM)

| coluna | tipo | regra exata |
| --- | --- | --- |
| `flag_sam` | bool | `flag_viavel.fillna(False) and top_municipio.fillna(False) and not flag_canibalizacao_ultra_1km` |
| `sam_indice_operavel` | float | `tam_indice_demanda` quando `flag_sam=True`; senao `0` |
| `sam_populacao_base` | float | `tam_populacao_base` quando `flag_sam=True`; senao `0` |
| `sam_granularidade` | string | `hex_censo` quando `flag_hex_hibrido_elegivel=True`; senao `municipio_priorizado` quando `flag_sam=True`; `bloqueado_rede_ultra` quando `flag_canibalizacao_ultra_1km=True`; senao `fora_escopo_atual` |

Leitura:

- `flag_sam` representa o que o modelo atual considera atendivel agora.
- O gate escolhido usa apenas variaveis ja disponiveis: viabilidade M1 + municipio no topo da fila atual + restricao de distancia minima para a rede Ultra.

### 5.5 Rede propria Ultra e canibalizacao

Parametro canonico ja existente em `config.py`:

- `DIST_MIN_ULTRA_KM = 1.0`

Todos os calculos abaixo usam o centroide do hex (`lat`, `lng`) contra cada unidade valida em `unidades_ultra_mapeadas`.

Distancia base:

`dist_ultra_m = haversine_metros((hex_lat, hex_lng), (ultra_lat, ultra_lng))`

| coluna | tipo | regra exata |
| --- | --- | --- |
| `n_unidades_ultra_1km` | int | contagem de unidades Ultra com `dist_ultra_m <= 1000` |
| `n_unidades_ultra_2km` | int | contagem de unidades Ultra com `dist_ultra_m <= 2000` |
| `dist_ultra_mais_proxima_m` | float | menor `dist_ultra_m` entre todas as unidades Ultra validas |
| `flag_canibalizacao_ultra_1km` | bool | `dist_ultra_mais_proxima_m < 1000` |
| `gap_rede_propria_1km` | float | `1 / (1 + n_unidades_ultra_1km)` |

Leitura:

- `flag_canibalizacao_ultra_1km` implementa a restricao operacional minima de distancia da rede propria com os dados disponiveis hoje.
- `gap_rede_propria_1km` pode ser usado em analises auxiliares, mas o bloqueio principal da primeira versao e booleano.

### 5.6 Residual mapeado e SOM

| coluna | tipo | regra exata |
| --- | --- | --- |
| `residual_indice_mapeado` | float | `tam_indice_demanda * gap_competitivo_2km` |
| `residual_populacao_mapeada` | float | `tam_populacao_base * gap_competitivo_2km` quando `demanda_granularidade='hex_censo'`; senao `null` |
| `capacidade_captura_mapeada` | float | `(sam_indice_operavel / 100.0) * gap_competitivo_2km` |
| `som_indice_mapeado` | float | `100 * capacidade_captura_mapeada` |
| `som_populacao_mapeada` | float | `sam_populacao_base * gap_competitivo_2km` quando `demanda_granularidade='hex_censo'`; senao `null` |

Leitura:

- `residual_indice_mapeado` = demanda potencial ajustada pela oferta mapeada dos players monitorados.
- `som_indice_mapeado` = parte operavel desse residual no modelo atual.
- `som_populacao_mapeada` so deve ser lido como proxy volumetrico quando a granularidade for `hex_censo`.

### 5.7 Classificacoes executivas

| coluna | tipo | regra exata |
| --- | --- | --- |
| `tese_entrada` | string | `proteger_rede_atual` se `flag_canibalizacao_ultra_1km=True`; `abrir_agora` se `flag_sam=True and flag_white_space_2km=True`; `abrir_com_disputa` se `flag_sam=True and flag_white_space_2km=False`; `monitorar` se `flag_viavel=True and top_municipio=False`; senao `descartar` |
| `prioridade_mercado_mapeado` | string | `alta` se `som_indice_mapeado >= 75`; `media` se `som_indice_mapeado >= 50`; `baixa` se `som_indice_mapeado > 0`; `nula` se `som_indice_mapeado == 0` |

Leitura:

- `prioridade_mercado_mapeado` usa regua absoluta de `som_indice_mapeado`; quartis e percentis servem apenas como apoio de ranking relativo fora do contrato principal.

## 6. Ordem de calculo recomendada

1. Normalizar os 3 CSVs de concorrentes.
2. Materializar `concorrentes_mapeados.parquet`.
3. Ler `oportunidades_expansao_hibrido.parquet` como base principal.
4. Join por `hex_id` com `brasil_estrutural.parquet`.
5. Join por `hex_id` com `censo2022_setores_calibrado.parquet`.
6. Normalizar `data/ultra/Ultra.csv` e materializar `unidades_ultra_mapeadas.parquet`.
7. Calcular distancias hex x concorrentes com `BallTree` ou Haversine vetorizado.
8. Calcular distancias hex x unidades Ultra.
9. Materializar as colunas de oferta mapeada e de rede propria.
10. Calcular `tam_*`, `sam_*`, `residual_*`, `som_*`.
11. Exportar `hexagonos_mercado_mapeado.parquet`.

## 7. O que esta fora desta versao

Itens abaixo nao devem entrar nesta primeira camada porque ainda nao existem como variaveis confiaveis e estruturadas no repo:

- ticket medio por rede concorrente
- capacidade fisica por concorrente
- area da unidade concorrente
- rating e reviews por unidade
- dados de churn/conversao por hexagono
- score de mudanca de bandeira
- oferta de academias independentes e boutiques

Consequencia pratica:

- a camada atual modela `oferta mapeada de grandes players`, nao a oferta total do mercado;
- `mudanca de bandeira` ainda nao deve ser calculada nesta etapa.

## 8. Recomendacao de uso executivo

Para a diretoria:

- `tam_indice_demanda`: onde existe demanda.
- `oferta_efetiva_mapeada_2km` e `pressao_concorrencial_score_2km`: onde os grandes players ja estao fortes.
- `dist_ultra_mais_proxima_m` e `flag_canibalizacao_ultra_1km`: onde a propria rede ja ocupa o mercado local.
- `residual_indice_mapeado`: onde existe demanda com menor pressao mapeada.
- `som_indice_mapeado`: onde o modelo atual consegue capturar primeiro.
- `tese_entrada`: como agir agora.

Para a equipe de dados:

- manter o M1 como gate principal;
- tratar `som_populacao_mapeada` como proxy apenas nas UFs com `hex_censo`;
- para sizing e corte executivo desta camada, priorizar `flag_sam`, `som_indice_mapeado`, `tese_entrada` e capacidade operacional disponivel, sem reinterpretar quartis como capacidade absoluta;
- nao chamar `residual` de "mercado vazio" enquanto a base de concorrentes nao incluir independentes.
