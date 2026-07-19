# Relatório de Análise de Mercado — Ultra Academia
**Data:** 2026-05-18
**Base de referência:** artefatos gerados em 2026-05-15 (cadeia completa com v0001 corrigido)
**Fontes:** `data/outputs/carteira_expansao_acionavel.parquet`, `data/outputs/plano_expansao_curto_prazo.parquet`, `data/reports/validacao_penetracao_ultra_hex.md`, `data/reports/validacao_geofusion_vs_hex.md`, `jobs/pipelines/enriquecimento_espacial_hexagonos.py`, `jobs/pipelines/calcular_colunas_mercado.py`

---

## 1. Penetração Ultra por Hexágono

**Amostra:** 54 unidades Ultra analisadas; 49 com população de hex válida.

| Fonte de população do hex | n |
|---|---:|
| censo_2022_hex (dado real do setor) | 28 |
| m1_municipal_proxy | 21 |
| hex_nao_encontrado | 4 |
| sem_hex_id_res7 | 1 |

### Distribuição das métricas de desempenho

| Métrica | n válido | Min | P25 | **Mediana** | P75 | Max |
|---|---:|---:|---:|---:|---:|---:|
| Alunos totais | 54 | 1.206 | 1.667 | **2.304** | 2.820 | 6.251 |
| Faturamento (R$) | 54 | 76.568 | 141.853 | **198.450** | 258.621 | 617.061 |
| Penetração alunos totais | 49 | 0,01% | 0,42% | **2,70%** | 4,79% | 13,14% |
| Receita por habitante (R$) | 49 | 0,01 | 0,33 | **2,11** | 3,76 | 9,10 |
| Ticket médio por aluno (R$) | 54 | 51,56 | 71,12 | **84,12** | 98,39 | 154,88 |
| Pagantes | 54 | 529 | 1.116 | **1.496** | 1.995 | 3.984 |

### Outliers detectados por IQR (mantidos na análise)

| Métrica | Unidade | UF | Tipo | Valor | Fonte pop |
|---|---|---|---|---:|---|
| Alunos totais | PRAIA GRANDE | SP | alto | 6.251 | hex_nao_encontrado |
| Pagantes | BOTAFOGO | RJ | alto | 3.984 | m1_municipal_proxy |
| Faturamento | BOTAFOGO | RJ | alto | R$ 617.061 | m1_municipal_proxy |
| Faturamento | NOROESTE | DF | alto | R$ 525.038 | m1_municipal_proxy |
| Faturamento | PRAIA GRANDE | SP | alto | R$ 454.048 | hex_nao_encontrado |
| Faturamento | SANTOS | SP | alto | R$ 451.068 | m1_municipal_proxy |
| Penetração | SUZANO | SP | alto | 13,14% | censo_2022_hex |
| Receita/hab | ASA NORTE | DF | alto | R$ 9,10 | censo_2022_hex |
| Ticket médio | BOTAFOGO | RJ | alto | R$ 154,88 | m1_municipal_proxy |

> **Cautela canônica:** penetração e receita/habitante usam `pop_hex_base` como denominador. As 21 unidades com proxy municipal têm o mesmo valor de população para todos os hexes do município — comparações entre fontes censo e proxy devem ser feitas com reserva.

---

## 2. Correlações — Principais Associações (Spearman, n=49)

Ordenadas por maior associação absoluta. Correlações com população/densidade do hex são diagnósticas da fórmula, não causais.

| Métrica | Variável | Spearman |
|---|---|---:|
| Penetração | População do hex | −0,950 |
| Penetração | Densidade do hex | −0,940 |
| Receita/hab | População do hex | −0,939 |
| Receita/hab | Densidade do hex | −0,934 |
| Penetração | Score híbrido | +0,395 *(maior associação não-derivada de pop)* |
| Receita/hab | Score híbrido | +0,414 *(maior associação não-derivada de pop)* |
| Faturamento | Delta densidade hex vs GeoFusion | +0,355 |
| Ticket médio | Renda per capita M1 | +0,315 |

---

## 3. TAM / SAM / Oferta Efetiva — Market Sizing

### Parâmetros do modelo

| Parâmetro | Valor | Origem |
|---|---|---|
| `taxa_fitness_mercado_calibrada` | **20%** | calibrada em runtime: mediana de `(n_academias_2km × 2.000) / pop_hex_base` em todos os hexes com academia; era 4,5% com 3 redes |
| `CAPACIDADE_MIN_ACADEMIA_ALUNOS` | 2.000 | lower-bound conservador para calibração da taxa |
| `CAPACIDADE_DEFAULT_CONCORRENTE_ALUNOS` | 2.500 | proxy por unidade para desconto do residual |
| `SCORE_RESIDUAL_CAPACIDADE_REFERENCIA` | 2.500 | base do `score_oportunidade_residual` |
| Redes mapeadas | 28 | auto-discovery de `concorrentes/unidades_*.csv` |
| Unidades concorrentes válidas | 3.179 | status_registro == "valido" |

### Totais nacionais — carteira completa (4.892 hexes)

| Métrica | Total | Média/hex | Mediana/hex | Std/hex |
|---|---:|---:|---:|---:|
| TAM fitness potencial | **2.385.008 alunos** | 487 | 7 | 1.899 |
| SAM fitness potencial *(2.529 hexes elegíveis)* | **1.623.277 alunos** | 642 | 7 | 2.274 |
| Oferta efetiva disponível *(residual)* | **1.091.913 alunos** | 432 | 6 | 1.513 |

> A mediana por hex de 6–7 alunos versus média de 432–642 evidencia distribuição fortemente assimétrica: o residual está concentrado em poucos hexes de alta densidade urbana.

### Plano curto prazo (267 hexes)

| Categoria | n |
|---|---:|
| Estratégicos | 20 |
| Alta | 30 |
| Táticos | 217 |
| **Total** | **267** |

| Métrica | Total | Média/hex | Mediana/hex |
|---|---:|---:|---:|
| Oferta efetiva disponível | **459.116 alunos** | 1.720 | 1 |

---

## 4. Área de Influência por Academia — Decaimento Linear

### Como funciona

Cada academia concorrente **não consome exatamente 2.500 alunos de um único hex**. O modelo aplica um **peso de decaimento linear** proporcional à distância entre o centroide do hex e a academia, com raio de até 2 km.

Implementação em `enriquecimento_espacial_hexagonos.py` (linha 99):

```python
w2 = np.maximum(0.0, 1 - dm / 2000.0)   # dm = distância em metros
oferta_2km[gi] = w2.sum()               # soma dos pesos de todos os concorrentes no raio
```

A mesma academia contribui com pesos diferentes para **cada hex que ela alcança**:

| Distância ao centroide do hex | Peso | Alunos consumidos do hex |
|---|---|---:|
| 0 m (academia dentro do hex) | 1,00 | 2.500 |
| 300 m | 0,85 | 2.125 |
| 500 m | 0,75 | 1.875 |
| 1.000 m | 0,50 | 1.250 |
| 1.500 m | 0,25 | 625 |
| 2.000 m | 0,00 | 0 |

Essa soma acumulada gera a coluna `oferta_efetiva_mapeada_2km`, depois convertida em alunos:

```
oferta_consumida_mercado_estimada = oferta_efetiva_mapeada_2km × 2.500
```

> **Implicação:** o mesmo concorrente consome alunos em vários hexes simultaneamente. Não é alocação zero-sum — é um modelo de sobreposição geográfica que representa o catchment real de cada academia se espalhando além das fronteiras do hex.

---

## 5. Exemplo Prático — Hex em Pinheiros/SP

Hex hipotético em área urbana densa com dois concorrentes no entorno.

### Dados de entrada

| Dado | Valor |
|---|---|
| `pop_hex_base` (setor censitário real) | 15.000 hab |
| `taxa_fitness_mercado_calibrada` | 20% |
| Concorrente 1: Smart Fit a 300 m | — |
| Concorrente 2: Bluefit a 1.400 m | — |
| Ultra no hex / dentro de 2 km | nenhuma |
| `flag_sam_fitness` | True (top-município, sem canibalização, pop > 0) |

### Cadeia de cálculo

**Passo 1 — TAM fitness**
```
TAM = pop_hex_base × taxa_fitness
TAM = 15.000 × 20% = 3.000 alunos
```

**Passo 2 — SAM fitness**
```
SAM = TAM  (quando flag_sam_fitness = True)
SAM = 3.000 alunos
```

**Passo 3 — Pesos dos concorrentes**
```
Smart Fit (300 m):  peso = max(0, 1 − 300/2.000)  = 0,85 → 0,85 × 2.500 = 2.125 alunos
Bluefit (1.400 m):  peso = max(0, 1 − 1.400/2.000) = 0,30 → 0,30 × 2.500 =   750 alunos

oferta_efetiva_mapeada_2km        = 0,85 + 0,30 = 1,15
oferta_consumida_mercado_estimada = 1,15 × 2.500 = 2.875 alunos
```

**Passo 4 — Consumo Ultra**
```
Sem alunos reais mapeados, sem unidade Ultra a <2 km:
oferta_consumida_ultra_estimada = 0 alunos
```

**Passo 5 — Oferta efetiva disponível (residual)**
```
oferta_consumida_total = 2.875 + 0 = 2.875 alunos
oferta_efetiva_disponivel = max(3.000 − 2.875, 0) = 125 alunos residuais
```

**Passo 6 — Score de oportunidade residual**
```
score_oportunidade_residual = min(100, 100 × 125 / 2.500) = 5,0 / 100
```

### Resumo do exemplo

| Métrica | Valor |
|---|---:|
| TAM fitness | **3.000 alunos** |
| SAM fitness | **3.000 alunos** |
| Oferta consumida (mercado) | 2.875 alunos |
| Oferta consumida (Ultra) | 0 alunos |
| **Oferta efetiva disponível** | **125 alunos** |
| Score oportunidade residual | **5,0 / 100** |

---

## 6. Conclusões Operacionais

1. **Penetração mediana da Ultra é 2,70%** da população do hex — intervalo saudável, mas a dispersão é alta (IQR de 4,4 p.p.), indicando que contexto local importa muito.
2. **Taxa de mercado fitness de 20%** é calibrada dinamicamente a partir de 28 redes mapeadas — 4,4× maior que a estimativa anterior com 3 redes, corrigindo um undercount relevante de mercado.
3. **O residual nacional de 1,09M alunos** está concentrado em poucos hexes: mediana de 6 alunos por hex versus máximo de 15.111 — priorização por `score_oportunidade_residual` é essencial.
4. **O modelo de área de influência com decaimento linear** é mais realista que um simples contador binário: um concorrente a 300 m consome 85% da sua capacidade estimada, não 100%; um a 1.400 m consome apenas 30%. Isso evita superestimar a "proteção" de hexes com concorrentes distantes.
5. **Cautela sobre proxy municipal:** 21 das 49 unidades analisadas usam população municipal distribuída por hex — penetração e receita/hab nesses casos não são comparáveis com unidades em hexes com dado censitário real.

---

*Gerado a partir de análise conversacional em 2026-05-18. Números derivados dos artefatos de staging e outputs datados de 2026-05-15.*
