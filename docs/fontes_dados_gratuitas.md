# Fontes de Dados Gratuitas — Motor de Expansão Ultra Academia

> Documentação das fontes de dados gratuitas que substituem (ou complementam) o GeoFusion.
> Cobertura estimada: ~85–90% da qualidade necessária para triagem de regiões.

---

## Visão Geral

O Motor de Expansão utiliza três fontes gratuitas para enriquecer os hexágonos H3:

| Fonte | Dado fornecido | Módulo | Cobertura |
|-------|---------------|--------|-----------|
| **IBGE Censo 2022** | Renda, população, densidade demográfica | `ibge_censo.py` | Nacional |
| **OSM / Overpass API** | Academias e equipamentos fitness concorrentes | `poi_enrichment.py` | Nacional |
| **Google Places** | Vitalidade comercial (supermercados, shoppings, farmácias) | `poi_enrichment.py` | Nacional (free tier) |

### Comparativo com GeoFusion

| Dimensão | GeoFusion | IBGE + OSM + Google | Diferença |
|----------|-----------|---------------------|-----------|
| Renda domiciliar | Alta precisão (setores) | Boa (setores Censo 2022) | ~10% inferior em granularidade |
| População 18–45 | Alta precisão | Boa (setores/SIDRA) | ~10% inferior |
| Concorrência fitness | Não cobre | Excelente (OSM) | OSM supera GeoFusion neste eixo |
| Vitalidade comercial | Score proprietário | Proxy via Google Places | ~15% inferior em precisão |
| Fluxo de pessoas | Cobre | Não cobre | Gap real — mitigado pela vitalidade |
| Custo mensal | R$3.000–8.000 | R$0–200 (Google) | Redução >95% |
| **Qualidade geral** | **100%** | **~85–90%** | Adequado para Fase 0–3 |

---

## 1. IBGE Censo 2022

### O que fornece
- **Renda per capita** domiciliar por setor censitário
- **População total** e faixa etária 18–45 anos
- **Densidade de domicílios** por km²
- **Área** do setor em km²

### Endpoints usados

```
# Malha de setores censitários (Shapefile) — download único por UF
https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios/Shapefile/{UF}_Malha_Preliminar_2022.zip

# API SIDRA — renda per capita por município (tabela 10297)
https://apisidra.ibge.gov.br/values/t/10297/n6/{cod_municipio}/v/allxp/p/last

# API SIDRA — população por faixa etária (tabela 9514)
https://apisidra.ibge.gov.br/values/t/9514/n6/{cod_municipio}/v/93/p/last/c287/93070,93071,93072,93073,93074,93075

# Localidades — busca de código IBGE por nome de município
https://servicodados.ibge.gov.br/api/v1/localidades/municipios
```

### Como funciona no código (`ibge_censo.py`)

1. **`IBGECenso.features_para_coordenada(lat, lng, uf)`** — ponto de entrada principal
   - Tenta lookup por setor censitário (shapefile local)
   - Fallback: consulta SIDRA por município via Nominatim + API IBGE
2. **`IBGECenso.features_para_hex(hex_id, uf)`** — wrapper para hexágonos H3
3. **`IBGECenso.baixar_renda_todos_municipios()`** — pré-carrega renda de todos os municípios em Parquet (execução única)

### Cache e performance
- Shapefiles salvos em `data/ibge/{UF}/` após primeiro download
- Renda por município salva em `data/ibge/renda_municipios_2022.parquet`
- Lookup por setor: `O(n)` no GeoDataFrame — otimizar com spatial index se necessário

### Setup necessário
```bash
pip install geopandas shapely requests h3 pandas pyarrow structlog
```

### Limitações
- Dados do Censo 2022 — atualização decenal (próxima: 2032)
- SIDRA tem rate limiting implícito — o código usa `time.sleep(0.5)` entre chamadas
- Variável `V6531` (renda) pode não estar disponível em todos os setores preliminares

---

## 2. OpenStreetMap via Overpass API

### O que fornece
- **Academias e equipamentos fitness** mapeados pela comunidade OSM
- Nome, coordenadas, tipo (fitness_centre, sports_centre, gym)
- Cobertura excelente em cidades médias e grandes brasileiras

### Endpoint usado

```
POST https://overpass-api.de/api/interpreter
Content-Type: application/x-www-form-urlencoded

data=[out:json][timeout:30];
(
  node["leisure"="fitness_centre"](around:1500,{lat},{lng});
  node["leisure"="sports_centre"](around:1500,{lat},{lng});
  node["sport"="fitness"](around:1500,{lat},{lng});
  node["sport"="gym"](around:1500,{lat},{lng});
  node["amenity"="gym"](around:1500,{lat},{lng});
);
out body;
```

### Como funciona no código (`poi_enrichment.py`)

1. **`POIEnricher.buscar_academias_osm(lat, lng, raio_metros)`** — consulta Overpass
2. **`POIEnricher.buscar_academias_hex_osm(hex_id)`** — wrapper para hexágonos H3
3. O resultado `n_academias_osm` alimenta diretamente o eixo `ausencia_concorrencia` no `hex_score`

### Setup necessário
```bash
pip install requests h3 structlog
```
Nenhuma API key necessária.

### Limitações
- Overpass API pública: evitar mais de 1 req/segundo (o código usa `time.sleep(1.1)`)
- Cobertura depende de contribuições OSM — cidades menores podem ter gaps
- Para alto volume, considerar instância própria: `docker run -p 12345:80 wiktorn/overpass-api`

---

## 3. Google Places API

### O que fornece
- **Vitalidade comercial** do entorno: supermercados, shoppings, farmácias, restaurantes, gyms
- Usado como proxy de consumo — quanto mais estabelecimentos de alto tráfego, maior o potencial

### Endpoint usado

```
GET https://maps.googleapis.com/maps/api/place/nearbysearch/json
  ?location={lat},{lng}
  &radius=1500
  &type={tipo}
  &key={GOOGLE_MAPS_API_KEY}
```

Tipos consultados: `supermarket`, `gym`, `pharmacy`, `restaurant`, `shopping_mall`

### Como funciona no código (`poi_enrichment.py`)

1. **`POIEnricher.buscar_pois_google(lat, lng, raio, tipo)`** — consulta por tipo
2. **`POIEnricher.score_vitalidade_comercial(lat, lng)`** — agrega os 5 tipos com pesos:
   - shopping_mall: 3.5 | supermarket: 3.0 | gym: 2.0 | pharmacy: 2.0 | restaurant: 1.5
   - Score = min((total_ponderado / 50) * 100, 100)
3. **Fallback sem API key**: retorna `50.0` (score neutro)

### Setup e custo
```bash
# Variável de ambiente
GOOGLE_MAPS_API_KEY=AIza...

# Free tier: US$200/mês em créditos (~40.000 buscas de POI)
# Para ~500 hexágonos × 5 tipos = 2.500 chamadas ≈ US$12,50/mês
```

### Limitações
- Requer API key (conta Google Cloud)
- Free tier esgota com volumes muito altos (~40k requisições/mês)
- Sem API key, `score_vitalidade` retorna 50.0 (neutro) — sistema ainda funciona

---

## Integração no hex_score

O `hex_score` (0–100) é calculado em `hex_enrichment.py` com os seguintes pesos:

```python
PESOS_HEX_SCORE = {
    "renda_normalizada":     0.35,  # IBGE Censo 2022
    "pop_jovem_normalizada": 0.25,  # IBGE Censo 2022
    "ausencia_concorrencia": 0.25,  # OSM Overpass
    "vitalidade_comercial":  0.15,  # Google Places (fallback 50.0)
}
```

Cada dimensão é normalizada min-max (0–100) dentro do conjunto de hexágonos da cidade antes de aplicar os pesos. Séries constantes recebem valor 50.0.

### Fluxo completo

```
gerar_hexagonos_cidade()
    └── Nominatim (geocodificação da cidade)
    └── h3.k_ring() (geração dos hexágonos)
        │
        ▼
enriquecer_hexagono() × N hexágonos
    ├── IBGECenso.features_para_coordenada()
    │     ├── [se shapefile disponível] lookup por setor
    │     └── [fallback] SIDRA via Nominatim + API IBGE
    └── POIEnricher.features_para_hex()
          ├── buscar_academias_osm() → Overpass API
          └── score_vitalidade_comercial() → Google Places
              │
              ▼
calcular_hex_score()
    └── normalização + ponderação → hex_score (0–100)
        │
        ▼
data/staging/hexagonos_{cidade}_{uf}.parquet
```

---

## Variáveis de ambiente relevantes

```bash
GOOGLE_MAPS_API_KEY=   # Opcional — sem key, vitalidade cai para 50.0 neutro
# IBGE e OSM são 100% gratuitos e não precisam de key
```

---

## Quando migrar para GeoFusion

Considerar GeoFusion (ou fonte premium equivalente) quando:
- O projeto entrar na Fase 3+ e o fluxo de pessoas se tornar crítico para o score
- A acurácia de renda por setor mostrar desvio > 20% em backtesting
- O volume de hexágonos processados exigir dados em batch (API GeoFusion é mais eficiente que N chamadas SIDRA)
