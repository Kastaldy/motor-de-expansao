# M1.1 — Arquitetura de Enriquecimento Territorial

> Contrato de design para a camada de enriquecimento territorial paralela ao M1.
> Data: 2026-04-08 | Status: RASCUNHO | Responsavel: Felipe Silva
> Dependencia: M1 nacional fechado e em GO. Nenhum artefato oficial do M1 e alterado.

---

## 1. Principios de governanca

### 1.1 Camadas de qualidade de fonte

| camada | definicao | exemplos |
| --- | --- | --- |
| **gold** | oficial brasileira, auditavel, cobertura nacional, refresh previsivel (censal ou anual) | IBGE Censo 2022, IBGE Grade Estatistica, IBGE CNEFE, Receita Federal CNPJ |
| **silver** | aberta robusta, boa cobertura nacional, nao oficial brasileira, licenca clara | Kontur Population, MapBiomas, INEP Censo Escolar, OpenStreetMap |
| **bronze** | fragmentada, municipal, oportunistica ou piloto; cobertura parcial | portais municipais de geoprocessamento, dados de prefeituras, scraping pontual |

### 1.2 Criterios de promocao ao score executivo

Uma camada so pode ser incorporada ao score executivo (`score_territorial_expandido` ou futuro substituto de `score_priorizacao`) se atender **todos** os criterios abaixo:

| # | criterio | descricao |
| --- | --- | --- |
| 1 | cobertura nacional | >= 90% dos hexagonos H3-r7 com valor valido em pelo menos 25 das 27 UFs |
| 2 | atualizacao previsivel | fonte com ciclo de refresh documentado (censal, anual, semestral) |
| 3 | licenca clara | licenca aberta ou uso permitido para fins analiticos internos sem restricao de redistribuicao |
| 4 | reproducao em lote | ingestao 100% automatizavel via download ou API publica sem intervencao manual |
| 5 | latencia operacional | ingestao nacional completa em < 4h em maquina padrao (8 cores, 32 GB RAM) |
| 6 | rastreabilidade por linha | cada hexagono registra fonte, data de referencia, metodo de agregacao e cobertura |
| 7 | coerencia com M1 | nao contradiz parametros canonicos de `config.py`; output final em H3_RESOLUTION = 7 |
| 8 | validacao com performance real | correlacao positiva demonstrada com metricas de unidades Ultra existentes (churn, LTV, conversao local) |

---

## 2. Regra espacial oficial do M1.1

### 2.1 Resolucao de saida

O output oficial do M1.1 permanece em **H3_RESOLUTION = 7** (conforme `config.py`).
Todos os parquets enriquecidos devem ter `hex_id` em resolucao 7 como chave primaria.

### 2.2 Granularidade de ingestao

Camadas brutas podem ser calculadas em granularidade mais fina que H3-r7:

| fonte | granularidade nativa | metodo de atribuicao a H3-r7 |
| --- | --- | --- |
| Censo 2022 setores censitarios | setor censitario (~300 domicilios) | spatial join ponderado por area de intersecao |
| Grade Estatistica 200m | celula 200x200m | soma de celulas contidas + prorrata de celulas parciais |
| CNEFE enderecos | ponto (lat/lon) | contagem de pontos por hexagono |
| CNPJ estabelecimentos | ponto (lat/lon via CEP) | contagem + buffer de distancia (1km, 2km) |
| MapBiomas | raster 30m | percentual de pixels por classe dentro do hexagono |
| Kontur Population | celula H3-r8 (400m) | soma de celulas filhas dentro do hexagono pai |
| Entorno dos Domicilios | setor censitario | media ponderada por domicilios do setor |

### 2.3 Registro de agregacao

Cada camada deve gravar uma coluna `metodo_agregacao_<camada>` com valor padronizado:
`media_ponderada_area`, `soma`, `contagem`, `maximo`, `percentual_pixels`, `media_ponderada_domicilios`.

---

## 3. Dicionario de colunas novas do H3 enriquecido

### 3.1 Demanda residente — Tier A (IBGE Censo 2022 setores censitarios)

| coluna | fonte | qualidade | descricao | agregacao H3-r7 | rastreabilidade |
| --- | --- | --- | --- | --- | --- |
| `pop_total_setor_2022` | IBGE Censo 2022 | gold | populacao total por setor censitario, agregada ao hexagono; coluna canonica de populacao (trava 18-45 removida em 2026-05-15) | soma ponderada por area | `fonte_censo_2022`, `data_referencia_censo_2022`, `metodo_agregacao_censo_2022`, `coverage_pct_censo_2022`, `qualidade_censo_2022` |
| `renda_per_capita_setor_2022` | IBGE Censo 2022 | gold | renda per capita domiciliar media do setor, agregada ao hexagono | media ponderada por populacao do setor | (idem) |
| `domicilios_setor_2022` | IBGE Censo 2022 | gold | total de domicilios particulares permanentes por setor | soma ponderada por area | (idem) |
| `cobertura_setor_2022_pct` | IBGE Censo 2022 | gold | percentual da area do hexagono coberta por setores censitarios | calculado diretamente (area coberta / area hexagono) | (idem) |

### 3.2 Demanda residente auxiliar — Tier A (IBGE Grade Estatistica 2022)

| coluna | fonte | qualidade | descricao | agregacao H3-r7 | rastreabilidade |
| --- | --- | --- | --- | --- | --- |
| `pop_grade_200m` | IBGE Grade Estatistica 2022 | gold | populacao estimada agregada das celulas 200m contidas no hexagono | soma (celulas inteiras) + prorrata (celulas parciais) | `fonte_grade_2022`, `data_referencia_grade_2022`, `metodo_agregacao_grade_2022`, `coverage_pct_grade_2022`, `qualidade_grade_2022` |
| `domicilios_grade_200m` | IBGE Grade Estatistica 2022 | gold | domicilios estimados agregados das celulas 200m | soma + prorrata | (idem) |

### 3.3 Densidade de enderecos — Tier A (IBGE CNEFE)

| coluna | fonte | qualidade | descricao | agregacao H3-r7 | rastreabilidade |
| --- | --- | --- | --- | --- | --- |
| `dens_end_residenciais_cnefe` | IBGE CNEFE 2022 | gold | densidade de enderecos residenciais (contagem / area do hexagono em km2) | contagem de pontos no hexagono | `fonte_cnefe`, `data_referencia_cnefe`, `metodo_agregacao_cnefe`, `coverage_pct_cnefe`, `qualidade_cnefe` |
| `dens_end_nao_residenciais_cnefe` | IBGE CNEFE 2022 | gold | densidade de enderecos nao residenciais (contagem / area do hexagono em km2) | contagem de pontos no hexagono | (idem) |

### 3.4 Qualidade urbana — Tier A (IBGE Entorno dos Domicilios)

| coluna | fonte | qualidade | descricao | agregacao H3-r7 | rastreabilidade |
| --- | --- | --- | --- | --- | --- |
| `indice_entorno_urbano_ibge` | IBGE Entorno dos Domicilios 2022 | gold | indice sintetico de qualidade do entorno (iluminacao, pavimentacao, arborizacao, calcada) normalizado 0-100 | media ponderada por domicilios do setor | `fonte_entorno`, `data_referencia_entorno`, `metodo_agregacao_entorno`, `coverage_pct_entorno`, `qualidade_entorno` |

### 3.5 Concorrencia real — Tier A (Receita Federal CNPJ)

| coluna | fonte | qualidade | descricao | agregacao H3-r7 | rastreabilidade |
| --- | --- | --- | --- | --- | --- |
| `n_academias_cnpj_1km` | Receita Federal / CNPJ aberto | gold | numero de estabelecimentos CNAE 9313-1/00 (atividades de condicionamento fisico) em raio de 1 km do centroide do hexagono | contagem em buffer 1km | `fonte_cnpj`, `data_referencia_cnpj`, `metodo_agregacao_cnpj`, `coverage_pct_cnpj`, `qualidade_cnpj` |
| `n_academias_cnpj_2km` | Receita Federal / CNPJ aberto | gold | idem em raio de 2 km | contagem em buffer 2km | (idem) |
| `dens_estabelecimentos_cnpj` | Receita Federal / CNPJ aberto | gold | densidade total de estabelecimentos ativos (todos os CNAEs) no hexagono (contagem / area km2) | contagem no hexagono | (idem) |

### 3.6 Forma urbana / viabilidade — Tier B (MapBiomas)

| coluna | fonte | qualidade | descricao | agregacao H3-r7 | rastreabilidade |
| --- | --- | --- | --- | --- | --- |
| `pct_urbanizado_mapbiomas` | MapBiomas Uso e Cobertura | silver | percentual da area do hexagono classificada como area urbanizada | percentual de pixels classe "Area Urbanizada" | `fonte_mapbiomas`, `data_referencia_mapbiomas`, `metodo_agregacao_mapbiomas`, `coverage_pct_mapbiomas`, `qualidade_mapbiomas` |
| `classe_dominante_mapbiomas` | MapBiomas Uso e Cobertura | silver | classe de uso do solo com maior area no hexagono | moda por area | (idem) |
| `filtro_inviabilidade_uso_solo` | MapBiomas Uso e Cobertura | silver | flag booleano: true se > 80% do hexagono e agua, floresta ou agropecuaria (inviavel para unidade fisica) | derivado de `pct_urbanizado_mapbiomas` e classes de uso | (idem) |

### 3.7 Colunas de rastreabilidade padrao

Para cada camada `<c>`, as seguintes colunas sao obrigatorias:

| coluna | tipo | descricao |
| --- | --- | --- |
| `fonte_<c>` | string | identificador canonico da fonte (ex: `ibge_censo_2022`, `receita_federal_cnpj_2025`) |
| `data_referencia_<c>` | string (YYYY-MM) | data de referencia do snapshot usado |
| `metodo_agregacao_<c>` | string | metodo de agregacao aplicado (conforme secao 2.3) |
| `coverage_pct_<c>` | float [0-100] | percentual da area do hexagono com cobertura efetiva da fonte |
| `qualidade_<c>` | string | `gold`, `silver` ou `bronze` |

---

## 4. Separacao entre score oficial e score experimental

### 4.1 Score oficial do M1 — intocavel

```
score_priorizacao  (M1_SCORE_OFICIAL em config.py)
```

- Definido na secao 7 do CLAUDE.md.
- Inputs: `renda_per_capita` e `populacao_proxy` (= `pop_total`) em nivel municipal (SIDRA). Alterado em 2026-05-15: trava 18-45 removida.
- Nenhuma alteracao permitida no calculo, nos pesos, nos inputs ou nos artefatos de saida.
- `hex_score_estrutural`, `ajuste_executivo` e `score_priorizacao` permanecem como estao.

### 4.2 Score experimental do M1.1

```
score_territorial_expandido  (novo, experimental, nao oficial)
```

- Nasce como coluna **experimental** no parquet `brasil_territorial_enriquecido.parquet`.
- **NAO substitui** `score_priorizacao` em nenhum artefato oficial.
- **NAO aparece** no app executivo (piloto web ou Power BI) ate aprovacao explicita.
- Formula inicial proposta (sujeita a calibracao):

```python
score_territorial_expandido = clip(
    0.40 * renda_pct_setor_2022 +
    0.25 * pop_pct_setor_2022 +
    0.15 * (1 - concorrencia_normalizada) +
    0.10 * entorno_normalizado +
    0.10 * urbanizacao_normalizada,
    0, 100
)
```

- Pesos sao hipotese inicial. Calibracao definitiva depende da validacao com performance real.

### 4.3 Criterio de promocao ao score executivo

O `score_territorial_expandido` so pode substituir `score_priorizacao` apos:

1. Validacao de correlacao com metricas reais de unidades Ultra existentes (churn, LTV, taxa de conversao local).
2. Cobertura nacional >= 90% com fonte gold.
3. Aprovacao explicita do responsavel do projeto.
4. Atualizacao formal do `CLAUDE.md` secao 7 com nova regra canonica.

---

## 5. Modelo operacional de staging

### 5.1 Estrutura de pastas

```
data/
  raw/
    ibge_censo_2022/        ano=2022/
    ibge_grade_2022/        ano=2022/
    ibge_cnefe_2022/        ano=2022/
    ibge_entorno_2022/      ano=2022/
    receita_cnpj/           ano=2025/ mes=MM/
    mapbiomas/              ano=2023/
    kontur_population/      ano=2024/
    inep/                   ano=2024/
  staging/
    censo_2022_h3_res7.parquet
    grade_2022_h3_res7.parquet
    cnefe_2022_h3_res7.parquet
    entorno_2022_h3_res7.parquet
    cnpj_h3_res7.parquet
    mapbiomas_h3_res7.parquet
    kontur_h3_res7.parquet
    brasil_territorial_enriquecido.parquet   <- join de todas as camadas
  outputs/
    (artefatos oficiais M1 — nao alterados)
```

### 5.2 Regras operacionais

1. **Nenhuma fonte nova deve ser consultada ao vivo durante o fechamento nacional.** Tudo deve ser snapshot versionado e cacheado em Parquet dentro de `data/raw/`.
2. Cada snapshot em `data/raw/` deve conter um arquivo `_metadata.json` com: `fonte`, `url_origem`, `data_download`, `data_referencia`, `licenca`, `hash_sha256`.
3. Parquets intermediarios em `data/staging/` sao sempre keyed por `hex_id` (H3-r7).
4. O join final em `brasil_territorial_enriquecido.parquet` e um left join do `brasil_estrutural.parquet` oficial com todas as camadas novas — preservando 100% das linhas do M1.
5. Formato de staging: Parquet com compressao snappy, particionado por UF quando > 1 GB.

---

## 6. Roadmap de ingestao por fase

### Fase A — Censo 2022 setores censitarios + spatial join H3

| item | valor |
| --- | --- |
| **fonte** | IBGE Censo Demografico 2022 — microdados por setor censitario |
| **colunas geradas** | `pop_total_setor_2022`, `renda_per_capita_setor_2022`, `domicilios_setor_2022`, `cobertura_setor_2022_pct` |
| **metodo de ingestao** | download dos shapefiles de setores + tabulacoes do Censo 2022; spatial join setor x H3-r7 com ponderacao por area de intersecao |
| **criterio de qualidade minimo** | cobertura >= 85% dos hexagonos por UF em pelo menos 25 UFs; amplitude intraurbana p95-p05 > 50 em capitais testadas; colunas de rastreabilidade sem nulos em > 5% dos hexagonos |
| **dependencia** | nenhuma (primeira fase) |
| **estimativa de volume** | ~300k setores censitarios → ~600k hexagonos H3-r7 |

### Fase B — CNPJ CNAE 9313 + geocodificacao por CEP

| item | valor |
| --- | --- |
| **fonte** | Receita Federal — base publica de CNPJ (dados abertos, atualizada mensalmente) |
| **colunas geradas** | `n_academias_cnpj_1km`, `n_academias_cnpj_2km`, `dens_estabelecimentos_cnpj` |
| **metodo de ingestao** | download do dump CNPJ aberto; filtro por CNAE 9313-1/00 (condicionamento fisico) + situacao cadastral ativa; geocodificacao por tabela CEP→lat/lon (base DNE Correios ou similar aberta); contagem em buffers 1km e 2km do centroide H3 |
| **criterio de qualidade minimo** | >= 80% dos CEPs de academias ativas geocodificados com precisao de logradouro; validacao cruzada com amostra de unidades Ultra conhecidas |
| **dependencia** | nenhuma (independente da Fase A) |
| **restricao** | NAO usar Nominatim publico para geocodificacao em lote; NAO usar OSM como unica fonte |

### Fase C — Kontur Population + validacao cruzada

| item | valor |
| --- | --- |
| **fonte** | Kontur Population (dataset global aberto, derivado de multiplas fontes, celulas H3-r8) |
| **colunas geradas** | nenhuma coluna oficial nova; usado como validacao cruzada de `pop_total_setor_2022` e `pop_grade_200m` |
| **metodo de ingestao** | download do GeoPackage Brasil; agregacao de celulas H3-r8 filhas para H3-r7 pai por soma |
| **criterio de qualidade minimo** | correlacao de Pearson >= 0.80 com `pop_total_setor_2022` em capitais; desvios > 2 std investigados e documentados |
| **dependencia** | Fase A concluida (necessaria para validacao cruzada) |

### Fase D — Grade Estatistica 2022 + CNEFE + Entorno dos Domicilios

| item | valor |
| --- | --- |
| **fonte** | IBGE Grade Estatistica 2022, IBGE CNEFE 2022, IBGE Pesquisa Entorno dos Domicilios 2022 |
| **colunas geradas** | `pop_grade_200m`, `domicilios_grade_200m`, `dens_end_residenciais_cnefe`, `dens_end_nao_residenciais_cnefe`, `indice_entorno_urbano_ibge` |
| **metodo de ingestao** | Grade: download por UF, soma de celulas 200m por hexagono; CNEFE: download por UF, geocodificacao interna por setor+endereco, contagem por hexagono; Entorno: download por UF, media ponderada por domicilios |
| **criterio de qualidade minimo** | Grade: cobertura >= 80% dos hexagonos urbanos; CNEFE: >= 70% dos enderecos geocodificados por setor; Entorno: >= 75% dos setores urbanos com dados validos |
| **dependencia** | nenhuma (independente, mas recomendado apos Fase A para validacao cruzada) |

### Fase E — MapBiomas + INEP

| item | valor |
| --- | --- |
| **fonte** | MapBiomas Colecao 8+ (uso e cobertura do solo, raster 30m); INEP Censo Escolar (localizacao e porte de escolas) |
| **colunas geradas** | `pct_urbanizado_mapbiomas`, `classe_dominante_mapbiomas`, `filtro_inviabilidade_uso_solo` |
| **metodo de ingestao** | MapBiomas: download do raster por UF, reclassificacao para classes simplificadas, calculo de percentual de pixels por classe dentro do hexagono; INEP: download CSV, geocodificacao por CEP, contagem por hexagono (uso futuro) |
| **criterio de qualidade minimo** | MapBiomas: cobertura 100% do territorio nacional (raster completo); concordancia >= 90% com classificacao urbana do IBGE em capitais |
| **dependencia** | nenhuma (independente) |

### Diagrama de dependencias

```
Fase A (Censo 2022) ──────────────┐
                                   ├──> Fase C (Kontur - validacao cruzada)
Fase B (CNPJ)     ── independente  │
Fase D (Grade+CNEFE+Entorno) ─────┘
Fase E (MapBiomas+INEP) ── independente

Fases A, B, D, E podem rodar em paralelo.
Fase C depende de A.
```

---

## 7. Criterios de qualidade minimos para avancar a Fase A

O parquet `censo_2022_h3_res7.parquet` deve passar todos os gates abaixo antes de ser promovido como input do join em `brasil_territorial_enriquecido.parquet`:

### 7.1 Cobertura nacional

| metrica | threshold |
| --- | --- |
| UFs com cobertura de setores >= 85% dos hexagonos urbanos | >= 25 de 27 |
| hexagonos com `cobertura_setor_2022_pct` >= 50% | >= 80% do total nacional |
| hexagonos com `cobertura_setor_2022_pct` = 0% | <= 10% do total nacional |

### 7.2 Amplitude intraurbana

| metrica | threshold |
| --- | --- |
| amplitude p95-p05 de `renda_per_capita_setor_2022` em capitais de estado | > 50 pontos (referencia: experimento 2010 com p95-p05 entre 54 e 74) |
| valores distintos de score por capital | > 30% dos hexagonos da capital |
| desvio padrao do score censuario dentro de capitais | > 15 |

> **Nota de escala (DEC-039, 2026-08-26).** As duas linhas de SCORE acima foram escritas para a escala antiga, em que a componente de populacao era percentil DENTRO do municipio: cada capital era esticada de 0 a 100 por construcao, e os dois limiares eram satisfeitos de graca — mediam a normalizacao, nao a qualidade do dado. Com a regua ABSOLUTA a dispersao dentro da capital passou a depender do porte real da cidade, e estes limiares NAO valem mais como gate de aceite. A primeira linha da tabela (amplitude de `renda_per_capita_setor_2022`) NAO foi afetada: a renda setorial e' insumo da regua, nao saida dela.

### 7.3 Rastreabilidade

| metrica | threshold |
| --- | --- |
| hexagonos com `fonte_censo_2022` nula | <= 2% |
| hexagonos com `data_referencia_censo_2022` nula | <= 2% |
| hexagonos com `metodo_agregacao_censo_2022` nula | 0% |
| hexagonos com `coverage_pct_censo_2022` nula | 0% |
| hexagonos com `qualidade_censo_2022` nula | 0% |

### 7.4 Consistencia com M1

| metrica | threshold |
| --- | --- |
| total de hexagonos no parquet censuario vs. `brasil_estrutural.parquet` | diferenca <= 1% |
| correlacao de Pearson entre `renda_per_capita_setor_2022` (agregada por municipio) e `renda_per_capita` do M1 municipal | >= 0.85 |
| nenhuma coluna do M1 oficial alterada ou removida no join | obrigatorio |

---

## 8. Restricoes operacionais consolidadas

1. **NAO** alterar `hex_score_estrutural`, `score_priorizacao` nem nenhum artefato listado na secao 10 do CLAUDE.md.
2. **NAO** criar dependencia de API publica ao vivo no pipeline de fechamento nacional.
3. **NAO** usar Nominatim publico para geocodificacao em lote.
4. **NAO** usar OSM como unica fonte de concorrencia.
5. **NAO** promover nenhuma camada ao score executivo sem validacao com historico de unidades Ultra.
6. Manter coerencia com os parametros canonicos em `config.py` (H3_RESOLUTION=7, RENDA_MIN=4500 [renda domiciliar minima, nao per capita], DIST_MIN_ULTRA_KM=1.0).
7. Staging sempre em Parquet antes de qualquer persistencia posterior.
8. CSV sempre com `sep=";"` e `encoding="utf-8-sig"`.

---

## 9. Glossario rapido

| termo | definicao |
| --- | --- |
| M1 | pipeline oficial nacional da Fase 1, fechado e em GO |
| M1.1 | camada paralela de enriquecimento territorial, nao altera M1 |
| H3-r7 | hexagono H3 resolucao 7 (~5.16 km2), unidade espacial canonica |
| spatial join | operacao de intersecao geometrica entre dois datasets espaciais |
| prorrata | alocacao proporcional a area de intersecao |
| CNAE 9313-1/00 | codigo de atividade economica: "atividades de condicionamento fisico" |
| CNEFE | Cadastro Nacional de Enderecos para Fins Estatisticos do IBGE |
| Kontur | empresa que produz dataset global de populacao estimada em celulas H3 |

---

> Documento gerado em 2026-04-08. Status: RASCUNHO.
> Requer aprovacao do responsavel do projeto antes da execucao da Fase A.
