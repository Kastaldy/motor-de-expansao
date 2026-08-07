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
- A oferta competitiva aqui e `oferta mapeada`, nao `oferta total do mercado`, porque a base atual cobre grandes redes mapeadas, nao academias independentes.

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

Arquivos: todos os `concorrentes/unidades_*.csv` descobertos automaticamente por `descobrir_csvs()` em `normalizar_concorrentes.py`. Atualmente **28 redes** mapeadas.

Colunas minimas esperadas em cada CSV:

- `nome_unidade`
- `latitude`
- `longitude`
- `data_coleta`

Separador detectado automaticamente (`;` ou `,`) por `_detectar_sep()` nos primeiros 500 caracteres do arquivo.

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
| `rede` | string | derivado automaticamente do nome do arquivo: `unidades_<rede>.csv -> <rede>` via `p.stem.removeprefix("unidades_")`; cobre todos os `unidades_*.csv` de `concorrentes/` |
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

1. Descobrir todos os `unidades_*.csv` em `concorrentes/` via glob; derivar nome da rede pelo stem do arquivo.
2. Detectar separador automaticamente (`;` vs `,`) por `_detectar_sep()`.
3. Padronizar os nomes de colunas para o contrato acima.
4. Descartar linhas com coordenadas ausentes ou fora do envelope do Brasil.
5. Descartar duplicatas exatas por rede + coordenada.
6. Nao deduplicar nomes iguais com coordenadas diferentes.

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
| `n_redes_mapeadas` | int | contagem dinamica de redes unicas validas em `concorrentes_mapeados.parquet`; calculado via `_contar_redes_mapeadas()` no Bloco 5; atualmente **28** (todos os `unidades_*.csv` de `concorrentes/`) |

### 5.2 Demanda potencial (TAM)

| coluna | tipo | regra exata |
| --- | --- | --- |
| `demanda_granularidade` | string | `hex_censo` quando `flag_censo_elegivel=True` e `pop_total_setor_2022.notna()`; senao `municipio_proxy` |
| `pop_hex_base` | float | `pop_total_setor_2022` positivo quando existe censo elegivel; senao `populacao_proxy` positiva; senao `null` |
| `fonte_pop_hex_base` | string | `censo_2022_hex`, `m1_municipal_proxy` ou `sem_populacao_valida` |
| `tam_populacao_base` | float | `pop_total_setor_2022` quando `demanda_granularidade='hex_censo'`; senao `populacao_proxy` |
| `tam_renda_base` | float | `renda_per_capita_setor_2022_calibrada` quando `demanda_granularidade='hex_censo'` e a coluna estiver preenchida; senao `renda_per_capita` |
| `tam_indice_demanda` | float | `score_expansao_hibrido` quando `flag_hex_hibrido_elegivel=True` e `score_expansao_hibrido.notna()`; senao `score_priorizacao` |
| `tam_indice_demanda_norm` | float | `tam_indice_demanda / 100.0` |
| `tam_pop_total_base` | float | `populacao_proxy` (= `pop_total`; trava 18-45 removida em 2026-05-15) |
| `tam_populacao_hex` | float | alias auditavel de `pop_hex_base` para sizing absoluto do Bloco 5 |
| `taxa_fitness_mercado_calibrada` | float | taxa de penetracao fitness calibrada em runtime por `calibrar_taxa_fitness_mercado(df)`: mediana de `(n_total_academias_2km * 2000) / pop_hex_base` nos hexes com >= 1 academia e populacao > 0; clip `[0.05, 0.50]`; fallback `TAXA_FITNESS_MERCADO_FALLBACK = 0.10` se < 10 hexes com academias na base; com todos os 28 CSVs mapeados resulta em **20%** |
| `taxa_fitness_calibrada` | float | alias de `taxa_fitness_mercado_calibrada` mantido para compatibilidade retroativa |
| `tam_fitness_potencial` | float | `tam_populacao_hex * taxa_fitness_mercado_calibrada` |

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

#### 5.3.1 Base ALTERNATIVA: 1 km repartido por area (colunas paralelas, NAO em producao)

Implementacao em `src/motor_expansao/pipelines/pressao_concorrencial_1km.py`
(2026-08-05, a pedido de Felipe). Cada concorrente vira uma fonte com disco de
influencia de **1 km** e a capacidade dele (`2500` alunos) e' repartida entre os
hexagonos que o disco cobre, na proporcao da **area de intersecao**, com kernel
uniforme (cada m2 do disco pesa igual):

```
share(concorrente c -> hex h) = area(disco_1km_c ∩ hex_h) / area(disco_1km_c)
SOMA_h share(c -> h) = 1                     # conservacao de massa, exata
oferta_efetiva_1km_area[h] = SOMA_c share(c -> h)
```

| coluna | tipo | regra exata |
| --- | --- | --- |
| `oferta_efetiva_1km_area` | float | soma dos `share` de todos os concorrentes que cobrem o hex |
| `n_concorrentes_influencia_1km` | int | quantos concorrentes distintos tem `share > 0` no hex |
| `consumo_concorrentes_1km_area` | float | `oferta_efetiva_1km_area * capacidade_default_concorrente_alunos` |
| `gap_competitivo_1km_area` | float | `1 / (1 + oferta_efetiva_1km_area)` |
| `pressao_concorrencial_score_1km_area` | float | `100 * (1 - gap_competitivo_1km_area)` |

**Status: PARALELO, nao consumido pelo residual.** Nenhuma coluna do bloco 2 km muda, e
`oferta_consumida_mercado_estimada` continua lendo `oferta_efetiva_mapeada_2km`. Migrar
o residual para esta base exige DEC (afeta `som_indice_mapeado`, `tese_entrada`,
`prioridade_mercado_mapeado`, carteira e plano).

Diferencas contra o modelo de 2 km. ATENCAO ao que o teste realmente trava: ele cobre a
conservacao de massa do modelo novo, a contencao de alcance e a ordem `media_1km >
media_2km`. Os extremos (`0,73`/`0,98`) e todos os numeros de DADOS REAIS abaixo NAO sao
travados por teste - os parquets sao gitignored, entao o CI nao regride se mudarem:

- **Massa.** Em SAO PAULO o modelo de 2 km injeta `0,73` a `0,98` unidade por concorrente
  conforme a posicao dentro do hexagono (media `0,80`): subestima ~20%, de forma desigual.
  **O sinal do desvio NAO e' universal** — em Porto Alegre a media e' `0,95` com 14 de 60
  posicoes ACIMA de `1,00` (max `1,04`, ou seja SOBRE-injeta), e em Belem a media cai para
  `0,68`. O que vale em geral e' a irregularidade, nao a direcao. O de 1 km por area
  injeta exatamente `1,00` em qualquer posicao (conferido: 3.179,0 para 3.179 validos).
- **Alcance.** Contra-intuitivo: o raio de 2 km NAO espalha mais. Na malha NACIONAL a
  distancia entre centroides vizinhos vai de `1.999` a `2.682 m` (mediana `2.496`) — a
  faixa `2.387-2.513 m` citada antes era do hexagono de Sao Paulo, e 67% da malha cai
  fora dela. Como quase tudo fica acima de 2.000 m, 2 km do centroide quase sempre nao
  alcanca vizinho (10 hexes no pais sao excecao). Em SP: `2,4` hexes na media contra
  `3,3` do modelo novo.
- **Direcao do efeito.** PROVADO em teste (120 amostras, so' em SP): o alcance do modelo
  de 1 km CONTEM o do de 2 km, logo nenhum hexagono passa de "com pressao" para "sem
  pressao". MEDIDO na malha NACIONAL (1.542.531 hexes): o residual cai na esmagadora
  maioria, mas **81 hexes GANHAM residual** — 68 no RS, 8 em SC, 5 no PR — com ganho
  maximo de `168` alunos (Pelotas/RS). Concentra-se no Sul, onde a celula e' menor: uma
  medicao restrita a SP/MG/RJ/PR/BA acha so' 5 casos e sugere que e' desprezivel.
  Conter o alcance nao impede o consumo de um hex especifico de diminuir; uma versao
  anterior deste paragrafo afirmava "nunca sobe", o que nao decorre do teste.

- **LIMITACAO CONHECIDA - massa retida na borda da base.** `shares_por_hex` conserva massa
  sobre todas as celulas H3 que o disco cobre, mas `anexar_pressao_1km_area` faz `merge`
  contra o DataFrame de hexes: o share que cai em celula FORA da base (litoral, fronteira,
  hexagono podado por `M1_HEX_LAND_FRACTION_MIN`) e' descartado em silencio. Medido:
  **119 dos 3.179 concorrentes (3,7%) perdem parte da conta** — mediana `15,8%`, ate
  `100%` — somando `27,4` unidades (`68.431` alunos) que somem. Subestima a pressao em
  hexes de borda. NAO corrigido neste ciclo; renormalizar ou sinalizar a perda por
  hexagono sao os caminhos, e a escolha fica para a DEC.

Comparativo executavel: `python scripts/comparar_pressao_1km.py` (usa os parquets reais
se existirem; senao roda um cenario sintetico rotulado como DEMO).

### 5.4 Mercado atendivel (SAM)

Colunas de corte de populacao (materializadas no pipeline via helper compartilhado
`pipelines/pop_corte.py`, mesma regua do dashboard — DEC-006):

| coluna | tipo | regra exata |
| --- | --- | --- |
| `populacao_corte_hex` | float | `pop_total_setor_2022` quando o hex e `granular`; senao fallback `pop_total` municipal |
| `fonte_populacao_corte` | string | `setor_2022` / `total_municipal` / `ausente` |
| `flag_pop_min_5k` | bool | `populacao_corte_hex >= 5000` (`POP_MIN_SAM_GATE`, espelha `POP_MIN_ACIONAVEL`) |

> **`granular`** (regua do corte) = `qualidade_join_uf in {A,B}` **AND** (`flag_censo_disponivel`
> OR `score_setor_2022_calibrado` notna). NAO e `flag_censo_elegivel` nem `mask_hex_censo`
> (`flag_censo_elegivel & pop_total_setor_2022.notna()`). Um hex pode ter
> `flag_censo_elegivel=False` e ainda ser `granular` — nesse caso o corte usa o setor 2022.

| coluna | tipo | regra exata |
| --- | --- | --- |
| `flag_sam` | bool | `faixa_oportunidade in {baixa,media,alta,prioridade_maxima} and flag_pop_min_5k` (DEC-007: `flag_viavel` e `not flag_canibalizacao_ultra_1km` SAIRAM do gate) |
| `flag_sam_fitness` | bool | `== flag_sam` (piso `tam_populacao_hex > 0` removido por redundancia com o corte `>= 5000`) |
| `sam_indice_operavel` | float | `tam_indice_demanda` quando `flag_sam=True`; senao `0` |
| `sam_populacao_base` | float | `tam_populacao_base` quando `flag_sam=True`; senao `0` |
| `sam_fitness_potencial` | float | `tam_fitness_potencial` (coercido, sem NaN, nao-negativo) quando `flag_sam_fitness=True`; senao `0` |
| `sam_granularidade` | string | `hex_censo` quando `flag_hex_hibrido_elegivel=True`; senao `municipio_priorizado` quando `flag_sam=True`; `bloqueado_rede_ultra` quando `flag_canibalizacao_ultra_1km=True`; senao `fora_escopo_atual` |

> Nota DEC-007 sobre `sam_granularidade`: a logica do `np.select` NAO mudou, mas como o
> gate agora admite hexes canibais no SAM, um hex `flag_sam=True and flag_canibalizacao_ultra_1km=True`
> (nao hibrido) recebe `municipio_priorizado` (a clausula `flag_sam` vence `flag_canibal` na
> precedencia), nao `bloqueado_rede_ultra`. O rotulo `bloqueado_rede_ultra` segue valido apenas
> para hexes canibais que NAO entram no SAM (faixa inelegivel ou populacao `< 5000`).

Leitura:

- `flag_sam` representa o que o modelo atual considera atendivel agora.
- O gate (DEC-006/DEC-007) substituiu `top_municipio` por Faixa M1 elegivel + populacao `>= 5000`
  na regua `populacao_corte_hex`. A DEC-007 reverteu 2 sub-decisoes da DEC-006: o gate deixou de
  exigir `flag_viavel` (some o filtro de renda `renda_target_proxy >= RENDA_MIN` e o guard `pop >= 1`
  que vinham de brinde) e deixou de exigir `not flag_canibalizacao_ultra_1km` (o SAM passa a INCLUIR
  areas Ultra `< 1 km`). O SAM existe fora do recorte top-20%/UF, e o corte `>= 5000` sobre
  `populacao_corte_hex` e o unico filtro remanescente (forte, nao aniquilador).

Gate de viabilidade absoluto (Etapa 1 do funil de atratividade, BLK-ATR-02) — coluna
PARALELA e independente de `flag_sam`:

| coluna | tipo | regra exata |
| --- | --- | --- |
| `flag_gate_atratividade` | bool | `flag_pop_min_5k` (`populacao_corte_hex >= 5000`) **AND** `renda_per_capita >= 1500` (`RENDA_PER_CAPITA_MIN_ATR`, constante LOCAL de `calcular_colunas_mercado.py`) |

> `flag_gate_atratividade` e o filtro da **Etapa 1 do funil de atratividade** (epic BLK-ATR).
> Reutiliza `flag_pop_min_5k` (mesma regua do corte, DEC-006/DEC-007) e le `renda_per_capita`
> direto do M1 (nao `renda_target_proxy` nem a renda censitaria calibrada). `renda_per_capita`
> NaN ou `0.0` (hex sem dado IBGE) -> `renda < 1500` -> `False` (conservador). Tipo `bool` puro,
> sem NaN, dominio `{True, False}`.
>
> **NAO substitui** `flag_viavel` (que usa `RENDA_MIN = 4500`, config.py) **nem** `flag_sam`
> (gate DEC-007). E coluna paralela: NAO entra no `np.select` de `tese_entrada`/
> `prioridade_mercado_mapeado`. READ-ONLY sobre o M1 — o piso `1500` e da camada de mercado,
> **nao** e parametro do M1 (§3) e **nao** e `RENDA_MIN`.

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
| `capacidade_default_concorrente_alunos` | float | `2500`; capacidade proxy por unidade grande mapeada ate existir calibracao por rede |
| `oferta_consumida_mercado_estimada` | float | `oferta_efetiva_mapeada_2km * capacidade_default_concorrente_alunos` |
| `oferta_consumida_ultra_real` | float | soma de `alunos_total` das unidades Ultra reais no mesmo `hex_id`, quando disponivel em `unidades_ultra_performance_hex.parquet`; senao `0` |
| `oferta_consumida_ultra_estimada` | float | `oferta_consumida_ultra_real` quando > 0; senao `n_unidades_ultra_2km * 2500` (proxy de capacidade Ultra) |
| `oferta_consumida_total_estimada` | float | `oferta_consumida_mercado_estimada + oferta_consumida_ultra_estimada`; total de alunos estimados ja atendidos (concorrentes + Ultra) |
| `oferta_efetiva_disponivel` | float | `max(sam_fitness_potencial - oferta_consumida_total_estimada, 0)` |
| `penetracao_fitness_mercado_estimada` | float | `oferta_consumida_total_estimada / tam_fitness_potencial` quando o denominador for positivo; senao `0` |
| `share_ultra_estimado_hex` | float | `oferta_consumida_ultra_real / (oferta_consumida_ultra_real + oferta_consumida_mercado_estimada)` quando o denominador for positivo; senao `0` |
| `score_oportunidade_residual` | float | `clip(100 * oferta_efetiva_disponivel / 2500, 0, 100)`; 100 representa residual suficiente para uma unidade grande proxy |
| `quartil_oportunidade_residual` | string | quartil relativo de `oferta_efetiva_disponivel` positiva (`Q1_menor_residual` a `Q4_maior_residual`); `sem_residual` quando nao houver residual positivo |

Leitura:

- `residual_indice_mapeado` = demanda potencial ajustada pela oferta mapeada dos players monitorados.
- `som_indice_mapeado` = parte operavel desse residual no modelo atual.
- `som_populacao_mapeada` so deve ser lido como proxy volumetrico quando a granularidade for `hex_censo`.
- `oferta_efetiva_disponivel` e `score_oportunidade_residual` sao sizing absoluto inicial em alunos potenciais, nao substituem `score_priorizacao`.
- `oferta_consumida_total_estimada` desconta tanto os concorrentes mapeados quanto a propria Ultra; e o denominador correto para penetracao total, nao apenas de terceiros.
- A capacidade concorrente de `2500` alunos e uma proxy conservadora e deve ser substituida quando houver capacidade real por rede/unidade.
- `quartil_oportunidade_residual` e apenas apoio visual de ranking relativo; nao deve ser usado como sizing absoluto nem como substituto do M1.

### 5.7 Classificacoes executivas

| coluna | tipo | regra exata |
| --- | --- | --- |
| `tese_entrada` | string | `proteger_rede_atual` se `flag_canibalizacao_ultra_1km=True`; `abrir_agora` se `flag_sam=True and flag_white_space_2km=True`; `abrir_com_disputa` se `flag_sam=True and flag_white_space_2km=False`; `monitorar` se `flag_viavel=True and top_municipio=False`; senao `descartar` |
| `prioridade_mercado_mapeado` | string | `alta` se `som_indice_mapeado >= 75`; `media` se `som_indice_mapeado >= 50`; `baixa` se `som_indice_mapeado > 0`; `nula` se `som_indice_mapeado == 0` |

Leitura:

- `tese_entrada` NAO muda de logica com a DEC-007: `proteger_rede_atual` (1o criterio, `flag_canibalizacao_ultra_1km`) tem precedencia sobre `flag_sam`, entao um hex canibal que agora entra no SAM continua rotulado `proteger_rede_atual`.
- `prioridade_mercado_mapeado` usa regua absoluta de `som_indice_mapeado`; quartis e percentis servem apenas como apoio de ranking relativo fora do contrato principal.

## 6. Ordem de calculo recomendada

1. Descobrir e normalizar todos os `unidades_*.csv` de `concorrentes/` (auto-discovery); separador detectado automaticamente.
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
12. Propagar os campos acionaveis com `enriquecer_outputs_residual_mercado.py` para `oportunidades_expansao_hibrido.parquet`, `carteira_expansao_acionavel.parquet` e `plano_expansao_curto_prazo.parquet`; a carteira tambem reanexa esses campos ao ser regenerada.

## 7. O que esta fora desta versao

Itens abaixo nao devem entrar nesta primeira camada porque ainda nao existem como variaveis confiaveis e estruturadas no repo:

- ticket medio por rede concorrente
- capacidade fisica real por concorrente
- area da unidade concorrente
- rating e reviews por unidade
- dados de churn/conversao por hexagono
- score de mudanca de bandeira
- oferta de academias independentes e boutiques

Consequencia pratica:

- a camada atual modela `oferta mapeada de grandes players`, nao a oferta total do mercado;
- `mudanca de bandeira` ainda nao deve ser calculada nesta etapa.

Nota (BLK-TP-08 / DEC-012 / DEC-013 parte 3): a oferta de academias menores agregadoras (WellHub/TotalPass) foi ingerida ANTI-PII e materializada como camada SEPARADA `data/staging/oferta_academias_menores_h3.parquet` (contrato `oferta_menores_v1`, H3 res-7, gitignored, NAO oficial). Ela ainda **NAO** esta integrada ao residual (`oferta_efetiva_disponivel`/`score_oportunidade_residual` inalterados) — o DEDUP vs `concorrentes_mapeados` (medido ~1.425 hexes em comum, 39% das academias / 63% dos alunos em hex ja coberto) e apenas QUANTIFICADO no relatorio `data/reports/scratch/oferta_academias_menores_qualidade.md`. A subtracao de oferta / capacidade por tipo (Huff) e follow-up sob gate (BLK-TP-09).

Nota (BLK-TP-08-FU / DEC-012, gate humano 2026-07-02): a re-ingestao das academias menores adiciona um passo de CLASSIFICACAO de REDE na FRONTEIRA (deriva `rede_menor` do `Nome_Academia` cru por matching de TOKEN com word-boundary contra a lista curada das 28 redes de `concorrentes_mapeados`, e DROPA o nome/coords/cluster imediatamente). Materializa 2 camadas SEPARADAS gitignored/NAO oficiais: (a) `data/staging/oferta_academias_menores_rede_h3.parquet` (contrato `oferta_menores_rede_v1`, formato LONGO `hex_id × rede_menor × n_academias_menores × alunos_academias_menores`, join por `hex_id`+`rede_menor`) e (b) `data/staging/capacidade_media_por_rede.parquet` (contrato `capacidade_media_rede_v1`, `rede_menor → media_alunos, mediana_alunos, n_filiais, flag_confiavel` N≥10). `rede_menor` e sempre CATEGORIA (nunca o nome); rede com N<3 filiais colapsa em `independente` (anti-reidentificacao). Cobertura real: ~2,2% classificada / ~97,8% `independente`; 13 redes na tabela, 10 confiaveis (N≥10). O DEDUP FINO por `(hex_id, rede_menor)` vs `concorrentes_mapeados` corrige a super-deducao grosseira do TP-08: de 62,7% para **8,3%** dos alunos realmente duplicados (a maior parte da oferta menor num hex de concorrente e rede DISTINTA = adicao legitima a saturacao). Ainda **NAO** subtrai oferta nem recompoe o residual (isso e BLK-TP-06-FU1 / BLK-TP-09 sob gate). Relatorio: `data/reports/scratch/rede_menor_classificacao_qualidade.md`.

## 8. Recomendacao de uso executivo

Para a diretoria:

- `tam_indice_demanda`: onde existe demanda.
- `oferta_efetiva_mapeada_2km` e `pressao_concorrencial_score_2km`: onde os grandes players ja estao fortes.
- `dist_ultra_mais_proxima_m` e `flag_canibalizacao_ultra_1km`: onde a propria rede ja ocupa o mercado local.
- `residual_indice_mapeado`: onde existe demanda com menor pressao mapeada.
- `som_indice_mapeado`: onde o modelo atual consegue capturar primeiro.
- `oferta_efetiva_disponivel`: sizing absoluto inicial em alunos potenciais depois da oferta mapeada.
- `score_oportunidade_residual`: leitura de capacidade residual em escala 0-100, ancorada em uma unidade grande proxy de 2500 alunos.
- `quartil_oportunidade_residual`: apoio visual relativo para filtros e leitura rapida; nao substitui a regua absoluta.
- `tese_entrada`: como agir agora.

Para a equipe de dados:

- manter o M1 como gate principal;
- tratar `som_populacao_mapeada` como proxy apenas nas UFs com `hex_censo`;
- para sizing e corte executivo desta camada, priorizar `flag_sam`, `oferta_efetiva_disponivel`, `score_oportunidade_residual`, `tese_entrada` e capacidade operacional disponivel, sem reinterpretar quartis como capacidade absoluta;
- nao chamar `residual` de "mercado vazio" enquanto a base de concorrentes nao incluir independentes.
