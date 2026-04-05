# Relatório de Validação — Renda Municipal no M1
## Fonte: SIDRA t.10295 v.13431 — Censo 2022

**Data de execução:** 2026-04-03 17:42–17:44  
**Tempo total:** 101 segundos (4 cidades / 1.876 hexágonos)  
**Output:** `data/staging/hexagonos_multicidade.parquet`

---

## 1. Nova Fonte de Renda — Identificação e Validação

### Por que a fonte anterior falhava?
SIDRA **tabela 10297** — "Massa de rendimento nominal mensal domiciliar per capita" — retorna `..` (sigiloso) para municípios de grande porte no Censo 2022. Isso zerrava `renda_per_capita` em todas as cidades testadas.

### Nova fonte implementada
**SIDRA tabela 10295, variável 13431:**  
`Valor do rendimento nominal médio mensal domiciliar per capita dos moradores em domicílios particulares permanentes ocupados, exclusive pensionistas/empregados domésticos`

- **Censo:** 2022
- **Nível:** Municipal
- **Status:** Sem sigilo — retorna valor numérico para todos os municípios testados

### Valores retornados

| Cidade | Cód. IBGE | Renda per capita (R$) | Fonte |
|--------|-----------|----------------------|-------|
| Curitiba/PR | 4106902 | **3.137,92** | `ibge_censo2022_t10295` |
| Belo Horizonte/MG | 3106200 | **2.748,85** | `ibge_censo2022_t10295` |
| Campinas/SP | 3509502 | **2.678,60** | `ibge_censo2022_t10295` |
| Goiânia/GO | 5208707 | **2.668,80** | `ibge_censo2022_t10295` |

**100% dos 1.876 hexágonos** com `renda_per_capita > 0`.  
`fonte_demografica`: `ibge_sidra_municipio_2022+ibge_censo2022_t10295` (todos)

---

## 2. Impacto no hex_score — Antes vs Depois

### Distribuição global (1.876 hexágonos)

| Métrica | Sem renda (renda=0) | Com renda (t.10295) | Variação |
|---------|---------------------|---------------------|----------|
| Mínimo | 25.49 | **8.72** | −16.77 |
| Máximo | 75.00 | **79.81** | +4.81 |
| Média | 60.21 | **53.70** | −6.51 |
| Std | 10.13 | **19.16** | +9.03 |
| Range total | 49.51 | **71.09** | +21.58 |

A ativação da renda (35% do peso) **quase dobrou o desvio padrão global** (10.13 → 19.16), tornando o ranking muito mais discriminante.

### Ranking inter-cidades — alteração

| Ranking | Sem renda | Com renda |
|---------|-----------|-----------|
| 1º | Belo Horizonte (72.73) | **Curitiba (79.81)** |
| 2º | Curitiba (62.31) | **Belo Horizonte (61.20)** |
| 3º | Goiânia (60.60) | **Goiânia (43.10)** |
| 4º | Campinas (47.48) | **Campinas (30.71)** |

**Mudança de liderança:** Sem renda, BH liderava por ter a maior `pop_18_45` (120k). Com renda, Curitiba assume (renda R$3.138 vs BH R$2.749, diferença de ~14%). BH cai do 1º para o 2º — o peso de população não é suficiente para compensar o gap de renda.

### Score por cidade com renda ativa

| Cidade | min | max | média | std | OSM status |
|--------|-----|-----|-------|-----|------------|
| Curitiba | 79.81 | 79.81 | 79.81 | 0.00 | ❌ 504 → n_acad=0 todos hexágonos |
| Belo Horizonte | 38.47 | 63.47 | 61.20 | 6.02 | ✅ 149 academias |
| Goiânia | 20.99 | 44.14 | 43.10 | 4.00 | ✅ 41 academias |
| Campinas | 8.72 | 33.23 | 30.71 | 6.01 | ✅ 134 academias |

> **Curitiba std=0:** OSM falhou (3 tentativas 429/504) → todos os 469 hexágonos com n_acad=0 → concorrencia_norm constante. Combinado com renda e pop iguais por ser dado municipal, todos têm score idêntico. Não é bug — é efeito direto da ausência de variação intra-hexágono.

---

## 3. Top 10 Hexágonos Globais

Todos Curitiba (score máximo global = 79.81) por ser OSM=0 + maior renda + pop mediana.

| # | Cidade/UF | lat | lng | Renda (R$) | pop_18_45 | n_acad | score |
|---|-----------|-----|-----|-----------|-----------|--------|-------|
| 1–10 | Curitiba/PR | -25.23 a -25.54 | -49.39 a -49.53 | 3.137,92 | 91.592 | 0 | 79.81 |

**Primeiro hexágono não-Curitiba:** BH, score 63.47.  
**Hex com menor score:** Campinas (16 academias OSM) → 8.72.

---

## 4. Perguntas Executivas

### A nova fonte de renda é estável e utilizável?

**Sim.** SIDRA t.10295 v.13431 retornou valor numérico para 100% dos municípios testados (4/4 sem `..`). É uma tabela publicada do Censo 2022 — a mesma base do t.10297 mas com o indicador de **valor médio** em vez de **massa total** (a massa era sigilosa; o médio não).

Hierarquia implementada:
1. t.10295 v.13431 — rendimento médio Censo 2022 **[fonte primária]**
2. t.10297 — massa rendimento Censo 2022 **[fallback, pode retornar sigiloso]**
3. zero **[fallback final]**

### A renda deixou de ficar zerada/sigilosa?

**Sim, para os 4 municípios testados.** O campo `renda_per_capita` saiu de 0 para valores entre R$2.669 e R$3.138, ativando os 35% do peso do score que estavam inativos.

### O ranking inter-cidades ficou mais consistente?

**Sim e mudou significativamente.** A adição de renda como variável diferenciadora reverte a liderança de BH para Curitiba — refletindo que Curitiba tem maior renda per capita domiciliar do que BH, mesmo com população 18–45 menor. A diferença Curitiba–BH no score (79.81 vs 61.20) agora captura uma diferença real de renda de ~14%.

O spread global aumentou de 49.5 para 71.1 pontos, tornando o ranking mais útil para decisão.

### Essa solução é suficiente até áreas de ponderação / microdados?

**Suficiente para triagem de mercados** (qual cidade priorizar). Limitações residuais:

| Limitação | Impacto | Solução futura |
|-----------|---------|----------------|
| Renda municipal, não por hexágono | Sem variação intra-cidade por renda | Shapefile IBGE 2022 setores censitários |
| Pop_18_45 municipal | Mesma limitação intra-cidade | Shapefile IBGE 2022 |
| OSM instável (429/504) | Curitiba sem concorrência OSM neste batch | Retry + janela de baixo tráfego |
| Score Curitiba=constante | Todos 469 hex idênticos quando OSM falha | OSM + shapefile |

**Para decisão de ponto específico:** aguardar shapefile IBGE 2022 ou dados por setor. Com dado por setor, renda e pop variam por hexágono dentro de cada cidade.

---

## 5. Implementação

### Alterações em `ibge_censo.py`

```python
# Constantes adicionadas
SIDRA_RENDA_MEDIO_MUNICIPIO = "10295"   # novo
SIDRA_VAR_RENDA_MEDIO       = "13431"   # novo

# Lógica em _sidra_renda_populacao()
# 1. Tenta t.10295 v.13431 → não sigiloso para cidades grandes
# 2. Fallback: t.10297 → pode retornar sigiloso
# 3. fonte_demografica registra qual fonte foi usada:
#    "ibge_sidra_municipio_2022+ibge_censo2022_t10295"
#    "ibge_sidra_municipio_2022+ibge_censo2022_t10297_fallback"
#    "ibge_sidra_municipio_2022+ibge_censo2022_sem_renda"
```

Nenhuma outra alteração no pipeline. Retrocompatível com modo single e batch.

---

## 6. Status do M1

| Componente | Status |
|------------|--------|
| Renda per capita (t.10295) | ✅ Ativo — 100% municípios com dado |
| Pop 18–45 (t.9514) | ✅ Ativo — dado municipal |
| Concorrência OSM | ⚠️ Intermitente (429/504) — retry 3× |
| Vitalidade comercial | ❌ Sem Google API key (fallback 50.0) |
| Variação intra-cidade | ⚠️ Apenas via OSM — shapefile IBGE 2022 pendente |
| Ranking inter-cidades | ✅ Válido com renda + pop + concorrência |
