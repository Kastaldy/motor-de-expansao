# Relatório de Validação — Fase 1 Motor de Expansão
## Cidade Piloto: Goiânia / GO

**Data de execução:** 2026-04-02 (iniciado 20:16) → 2026-04-03 (concluído 05:23)
**Tempo total:** ~9h (bloqueado por N chamadas Nominatim — corrigido, ver seção de problemas)
**Resolução H3:** 7 (~0.7 km² por hexágono)
**Raio de cobertura:** 15 km a partir do centroid de Goiânia
**Output:** `data/staging/hexagonos_goiania_go.parquet`

---

## 1. Fonte Demográfica Utilizada

| Fonte | Hexágonos | % |
|-------|-----------|---|
| `fallback_padrao` | 469 | 100% |
| `ibge_setor_2022` | 0 | 0% |
| `ibge_sidra_municipio_2022` | 0 | 0% |

**Causa:** O Nominatim (reverse geocoding) falhou com DNS errors a partir de ~i=350 durante a execução. Nos primeiros 350 hexágonos a conectividade estava instável (lenta), e nos últimos 119 o DNS falhou completamente. Como o `_cod_municipio_padrao` não estava definido nessa execução (o fix foi feito após o pipeline iniciar), cada hexágono tentou resolver seu próprio município via Nominatim.

**Status do shapefile IBGE 2022:** URL `ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios/Shapefile/GO_Malha_Preliminar_2022.zip` retornou **404** — shapefile ainda não disponível nesse caminho.

---

## 2. Estatísticas do hex_score

| Métrica | Valor |
|---------|-------|
| Mínimo | 37.50 |
| Máximo | 62.50 |
| Média | 61.49 |
| Mediana | 62.50 |
| Desvio Padrão | 4.10 |
| Hexágonos fora de [0,100] | 0 |

**Interpretação:** A variação limitada (37.5–62.5) é consequência direta da falha do IBGE:
- `renda_norm` e `pop_norm` foram constantes em 50.0 (série zerada → normalização constante)
- `vitalidade_norm` constante em 50.0 (sem Google key)
- Apenas `concorrencia_norm` (OSM) variou

Score efetivo = `50×0.35 + 50×0.25 + concorrencia×0.25 + 50×0.15` = `37.5 + concorrencia×0.25`

Com IBGE funcionando, a variação esperada é de 0–100.

---

## 3. Cobertura OSM (academias)

| n_academias_osm | Hexágonos |
|-----------------|-----------|
| 0 | 441 (94%) |
| 1 | 16 (3,4%) |
| 2 | 8 (1,7%) |
| 3 | 1 |
| 4 | 1 |
| 5 | 1 |
| 7 | 1 |

**Total de academias mapeadas no bbox:** 41  
**Hexágonos com pelo menos 1 academia:** 28 (6%)  
**Query OSM:** 1 única request para o bbox da cidade (solução bulk — OK)

---

## 4. Top 10 Hexágonos por Score

> **Atenção:** ranking atual reflete apenas ausência de concorrência (IBGE zerado).
> Reprocessar após correção do IBGE para rankings válidos.

| # | hex_id | lat | lng | n_acad | renda | hex_score |
|---|--------|-----|-----|--------|-------|-----------|
| 1 | 87a8c0d03ffffff | -16.95289 | -49.25219 | 0 | 0 | 62.50 |
| 2 | 87a8c0d0effffff | -16.94037 | -49.27281 | 0 | 0 | 62.50 |
| 3 | 87a8c0cf1ffffff | -16.69158 | -49.22306 | 0 | 0 | 62.50 |
| 4 | 87a8c0d08ffffff | -16.92785 | -49.29343 | 0 | 0 | 62.50 |
| 5 | 87a8c0d09ffffff | -16.91532 | -49.31405 | 0 | 0 | 62.50 |
| 6 | 87a8c0d54ffffff | -16.90279 | -49.33467 | 0 | 0 | 62.50 |
| 7 | 87a8c0d55ffffff | -16.89026 | -49.35529 | 0 | 0 | 62.50 |
| 8 | 87a8c0d42ffffff | -16.87773 | -49.37590 | 0 | 0 | 62.50 |
| 9 | 87a8c0cf5ffffff | -16.71442 | -49.22377 | 0 | 0 | 62.50 |
| 10 | 87a8c0cf0ffffff | -16.70411 | -49.20244 | 0 | 0 | 62.50 |

---

## 5. Validação do Schema

| Check | Status |
|-------|--------|
| Total hexágonos | ✅ 469 |
| Colunas esperadas presentes | ✅ 16/16 |
| NaN em `hex_id` | ✅ 0 |
| NaN em `lat` | ✅ 0 |
| NaN em `lng` | ✅ 0 |
| NaN em `hex_score` | ✅ 0 |
| hex_score em [0,100] | ✅ 0 fora do range |
| Hexágonos dentro do Brasil | ✅ 469/469 |
| OSM bulk query (1 request) | ✅ 41 academias |
| IBGE dados demográficos | ❌ fallback_padrao (DNS failure) |

---

## 6. Problemas Encontrados e Correções Aplicadas

### P1 — IBGE shapefile 404
**Problema:** URL `ftp.ibge.gov.br/.../GO_Malha_Preliminar_2022.zip` retorna 404. O shapefile do Censo 2022 preliminar por setores não está disponível nesse path ainda.  
**Correção aplicada:** `ibge_censo.py` agora testa 3 URLs candidatas e cacheia a falha em `_uf_download_falhou` (evita 1 tentativa por hexágono). Fallback automático para SIDRA município.

### P2 — Nominatim por hexágono (causa do tempo de 9h)
**Problema:** `_geocodigo_municipio(lat, lng)` era chamado para cada um dos 469 hexágonos. O `lru_cache` não ajudava pois cada hexágono tem lat/lng único. Com 469 Nominatim calls × 1.1s de sleep + timeout DNS = ~9h.  
**Correção aplicada:**
- `ibge_censo.py`: novo método `set_municipio_padrao(cod)` que define um municipality override, evitando Nominatim por hexágono
- `hex_enrichment.py`: prewarm resolve o município UMA VEZ antes do loop e chama `set_municipio_padrao`. Tempo esperado na próxima execução: **~2–5 min** (1 Nominatim + 1 SIDRA + bulk OSM)

### P3 — OSM rate limiting (429/504)
**Problema:** Versão anterior fazia 1 request Overpass por hexágono → bloqueio imediato.  
**Correção aplicada:** `poi_enrichment.py` ganhou `buscar_academias_bbox()` — 1 request para o bbox da cidade inteira. `hex_enrichment.py` refatorado para usar bulk + `contar_academias_proximas()` (cálculo local sem HTTP).

### P4 — IBGE SIDRA retorna `'..'` (dado sigiloso)
**Problema:** `float('..')` levanta `ValueError`.  
**Correção aplicada:** `ibge_censo.py` trata `".."`, `"..."`, `"-"`, `"X"` como valor zero.

### P5 — API h3 v4 (breaking change)
**Problema:** `h3.h3_to_geo`, `h3.geo_to_h3`, `h3.k_ring` não existem na v4.  
**Correção aplicada:** Substituídos por `h3.cell_to_latlng`, `h3.latlng_to_cell`, `h3.grid_disk`.

---

## 7. Recomendações para Próxima Execução

### Imediatas (antes de reprocessar Goiânia)
1. **Executar com código corrigido** — `set_municipio_padrao` elimina o problema de 9h. Tempo esperado: ~3 min.
2. **Código do município de Goiânia:** `5208707` (pode ser passado diretamente no pipeline se necessário)
3. **Validar conectividade IBGE SIDRA** antes de iniciar: `curl "https://apisidra.ibge.gov.br/values/t/10297/n6/5208707/v/allxp/p/last"`

### Para próximas cidades
4. **Passar `unidades_ultra`** com coordenadas reais das unidades Ultra em GO para ativar o filtro de anti-canibalização
5. **Google Maps API key** — sem ela, `score_vitalidade` fica fixo em 50.0 e o peso de 15% é desperdiçado
6. **Monitorar IBGE FTP** — quando o shapefile 2022 estiver disponível, o enriquecimento por setor censitário será muito mais preciso que o SIDRA município
7. **Cidades recomendadas após Goiânia:** São Paulo (SP), Belo Horizonte (MG), Curitiba (PR) — mercados com maior densidade e mais academias concorrentes para validar o score de concorrência

### Configuração sugerida para próxima run
```python
rodar_pipeline_hex(
    cidade="Goiania",
    uf="GO",
    raio_km=15.0,
    unidades_ultra=[
        (-16.6869, -49.2648),  # exemplo: unidade Setor Bueno
        (-16.7200, -49.2800),  # adicionar coords reais das unidades GO
    ]
)
```
