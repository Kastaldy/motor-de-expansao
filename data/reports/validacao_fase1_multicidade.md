# Relatório de Validação — Fase 1 Motor de Expansão
## Batch Multi-Cidade: Goiânia/GO · Campinas/SP · Belo Horizonte/MG · Curitiba/PR

**Data de execução:** 2026-04-03 17:22–17:24  
**Tempo total:** 131 segundos (~2,2 min para 4 cidades / 1.876 hexágonos)  
**Resolução H3:** 7 | **Raio por cidade:** 15 km  
**Output consolidado:** `data/staging/hexagonos_multicidade.parquet`  
**Outputs individuais:** mantidos em `data/staging/hexagonos_{cidade}_{uf}.parquet`

---

## 1. Coleta por Cidade

| Cidade | UF | Cód. IBGE | Hexágonos | OSM Academias | Tempo (s) |
|--------|----|-----------|-----------|---------------|-----------|
| Goiânia | GO | 5208707 | 469 | 41 | 11.5 |
| Campinas | SP | 3509502 | 469 | 134 | 54.6 (2 retries OSM) |
| Belo Horizonte | MG | 3106200 | 469 | 149 | 53.1 (2 retries OSM) |
| Curitiba | PR | 4106902 | 469 | 96 | 11.7 |
| **Total** | | | **1.876** | **420** | **131** |

Todos os municípios resolvidos via IBGE Localidades API sem Nominatim.  
Todos os hexágonos enriquecidos com `ibge_sidra_municipio_2022` — **0 fallback_padrao**.

---

## 2. Normalização Global — Funcionamento

A normalização é aplicada sobre o DataFrame consolidado de 1.876 hexágonos (4 cidades juntas), fazendo com que cada feature seja min-max escalada no universo total — não por cidade.

### Valores SIDRA municipais (base da normalização de pop)

| Cidade | pop_18_45 (SIDRA) | pop_norm global |
|--------|-------------------|-----------------|
| Belo Horizonte | 120.135 | 100.0 (máximo) |
| Curitiba | 91.592 | ~50 |
| Goiânia | 90.092 | ~48 |
| Campinas | 63.923 | 0.0 (mínimo) |

### Composição do score global

| Feature | Contribuição real | Motivo |
|---------|-------------------|--------|
| `renda_norm` | 0 para todas as cidades | SIDRA t.10297 retorna `..` (sigiloso) — renda_per_capita=0 em todos os 1.876 hexágonos |
| `pop_norm` | **Diferencia cidades** (0–100) | Escalonado globalmente por pop_18_45 SIDRA |
| `concorrencia_norm` | **Diferencia hexágonos** (dentro de cada cidade) | OSM academias no raio — varia por hexágono |
| `vitalidade_norm` | 50.0 constante | Sem Google API key |

Score efetivo: `renda×0.35 (=0) + pop×0.25 + concorrencia×0.25 + 50×0.15`

---

## 3. Resultados do hex_score Global

### Distribuição consolidada (1.876 hexágonos)

| Métrica | Valor |
|---------|-------|
| Mínimo | 25.49 |
| Máximo | **75.00** |
| Média | 60.21 |
| Mediana | 61.64 |
| Desvio Padrão | 10.50 |

### Score por cidade (no contexto global)

| Cidade | min | max | média | std | Interpretação |
|--------|-----|-----|-------|-----|---------------|
| Belo Horizonte | 50.00 | **75.00** | 72.73 | 6.02 | Maior pop SIDRA → top do ranking global |
| Curitiba | 38.43 | 62.31 | 60.04 | 5.79 | Pop mediana, densidade OSM moderada |
| Goiânia | 38.49 | 61.64 | 60.60 | 4.00 | Pop próxima de Curitiba, menos academias OSM |
| Campinas | 25.49 | **50.00** | 47.48 | 6.01 | Menor pop SIDRA → base do ranking global |

> **Nota:** O spread de scores intra-cidade (std~6) vem exclusivamente do OSM (concorrência). O posicionamento relativo entre cidades vem do `pop_18_45` municipal — o único dado IBGE sem sigilo nas 4 cidades.

---

## 4. Top 10 Hexágonos Globais

Todos os top 10 são de Belo Horizonte (maior `pop_18_45` municipal + zero academias OSM no entorno).

| # | Cidade | lat | lng | pop_18_45 | n_acad | score |
|---|--------|-----|-----|-----------|--------|-------|
| 1–10 | Belo Horizonte/MG | -20.18 a -20.06 | -44.14 a -43.79 | 120.135 | 0 | 75.00 |

**Hex com menor score global:** Campinas/SP, 16 academias no raio → score **25.49**

---

## 5. Top 5 por Cidade

| Cidade | Score máx local | n_acad | Nota |
|--------|-----------------|--------|------|
| Belo Horizonte | 75.00 | 0 | Periferias sem academias |
| Curitiba | 62.31 | 0 | Periferias sem academias |
| Goiânia | 61.64 | 0 | Periferias sem academias |
| Campinas | 50.00 | 0 | Máximo possível dado pop SIDRA mais baixa |

---

## 6. Cobertura OSM por Cidade

| Cidade | Total academias | Hex c/ academias | Max acad/hex |
|--------|-----------------|-----------------|--------------|
| Belo Horizonte | 191 | 61 (13%) | 24 |
| Campinas | 179 | 74 (16%) | 16 |
| Curitiba | 158 | 66 (14%) | 11 |
| Goiânia | 59 | 31 (7%) | 8 |

---

## 7. Perguntas Executivas

### A normalização multi-cidade foi implementada corretamente?

**Sim.** O `calcular_hex_score` é chamado uma vez sobre o DataFrame de 1.876 hexágonos. A função `normalizar_serie` recebe os valores de todas as 4 cidades juntos, fazendo min-max global. Scores de cidades diferentes são agora comparáveis entre si.

Prova: BH (pop=120k) score 75 vs Campinas (pop=64k) score máx 50 — a diferença reflete corretamente que BH tem ~88% mais população-alvo (18–45 anos) do que Campinas pelo dado SIDRA municipal.

### O ranking global entre cidades agora é válido?

**Válido com a ressalva da fonte.** O ranking é tecnicamente correto dentro dos dados disponíveis. A limitação real é que `pop_18_45` é nível **municipal** (não por hexágono) — todos os hexágonos de BH têm o mesmo valor, o que elimina diferenciação intra-cidade por população. O ranking inter-cidades é válido; o ranking intra-cidade depende exclusivamente do OSM.

Para ranking intra-cidade verdadeiro: necessário shapefile IBGE 2022 por setor censitário (indisponível no FTP até 2026-04-03).

### Houve problema de fonte, schema ou performance?

| Tipo | Ocorrência | Status |
|------|-----------|--------|
| Schema | 0 divergências | ✅ |
| NaN críticos | 0 | ✅ |
| Fonte IBGE | SIDRA sigiloso (`renda=0`) em todas as 4 cidades | ⚠️ Limitação conhecida |
| OSM 504 | Campinas e BH precisaram de 2 retries (30s de wait extra cada) | ⚠️ Retry resolveu |
| Compatibilidade parquets individuais | 4 arquivos gerados corretamente | ✅ |
| Tempo total | 131s (4 cidades) | ✅ |

### O M1 está pronto para escalar para mais cidades?

**Sim, com condições.**

**Pronto:**
- Arquitetura bulk: 1 call IBGE + 1 query OSM por cidade
- Retry OSM 3× com backoff
- Normalização global: basta adicionar cidades ao array `CIDADES_BATCH`
- Schema estável: 20 colunas consistentes em todas as cidades testadas
- Performance: ~33s/cidade em média (incluindo retries OSM)

**Condições para decisão real:**
1. `renda_per_capita = 0` nas 4 cidades — componente de 35% do score está inativa. Nenhuma cidade passa de 65 sem renda. Aguardar shapefile IBGE 2022 ou investigar tabela SIDRA alternativa.
2. Pop SIDRA municipal diferencia cidades mas não hexágonos dentro da mesma cidade — aceitável para triagem de mercados, insuficiente para seleção de ponto específico.
3. Sem Google Maps key: peso de 15% (vitalidade comercial) em fallback neutro.

**Recomendação:** M1 está apto para triagem de mercados (qual cidade priorizar). Para decisão de ponto (qual hexágono dentro de uma cidade), aguardar shapefile IBGE 2022.

---

## 8. Arquivos Gerados

| Arquivo | Conteúdo | Hexágonos |
|---------|----------|-----------|
| `data/staging/hexagonos_multicidade.parquet` | Consolidado — score global | 1.876 |
| `data/staging/hexagonos_goiania_go.parquet` | Goiânia — score global | 469 |
| `data/staging/hexagonos_campinas_sp.parquet` | Campinas — score global | 469 |
| `data/staging/hexagonos_belo_horizonte_mg.parquet` | BH — score global | 469 |
| `data/staging/hexagonos_curitiba_pr.parquet` | Curitiba — score global | 469 |
